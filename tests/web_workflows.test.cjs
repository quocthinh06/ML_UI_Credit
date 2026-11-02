const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const {webcrypto} = require('node:crypto');

function app() {
  const elements = new Map();
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, {value:'', disabled:false, hidden:false, handlers:{}, addEventListener(type,handler){this.handlers[type]=handler;},
        replaceChildren(){}, add(){}, showModal(){this.open=true;}, close(){this.open=false;}});
      return elements.get(id);
    }, querySelectorAll(){return [];}, addEventListener(){}
  };
  const context = vm.createContext({document, window:{addEventListener(){}}, location:{hash:''},
    crypto:webcrypto, structuredClone, performance, FormData, File, Blob, Response, AbortController, setTimeout, clearTimeout, console,
    localStorage:{values:new Map(),getItem(k){return this.values.get(k)||null;},setItem(k,v){this.values.set(k,String(v));},removeItem(k){this.values.delete(k);}},
    Option:function(text,value){this.text=text;this.value=value;}});
  const source = fs.readFileSync('creditrisk/static/app.js','utf8');
  vm.runInContext(source.slice(0, source.lastIndexOf('initialize().catch')), context);
  vm.runInContext(`globalThis.originalPersist=persist;globalThis.originalApi=api;persist=async()=>{};saveLocalState=async()=>{};renderAll=()=>{};notify=()=>{};
    state={datasets:[{id:'a',name:'A',versions:[{id:'v1',revision:1,rows:[{ID:'old',AGE:30}]}]},
      {id:'b',name:'B',versions:[{id:'v2',revision:1,rows:[]}]}],runs:[]};
    selectedDataset='a';selectedVersion='v1';singleInputs={ID:'new',AGE:40};`, context);
  return {run: code=>vm.runInContext(code,context), elements};
}

test('single transfer asks for destination and appends inputs to its latest version', async()=>{
  const {run,elements}=app();
  run('transferSingle()');
  assert.equal(elements.get('transfer-dialog')?.open,true);
  elements.get('transfer-target').value='b';
  await run('confirmTransfer({preventDefault(){}})');
  assert.equal(run("state.datasets[1].versions.at(-1).rows[0].ID"),'new');
  assert.equal(run('state.datasets[0].versions.length'),1);
  assert.equal(run('state.runs.length'),0);
});

test('local save completes without waiting for cloud and pending edits sync serially',async()=>{
  const {run}=app();
  run(`remoteEnabled=true;syncReady=true;saveLocalState=async()=>{};globalThis.saved=0;
    globalThis.release=null;api=async()=>{saved++;if(saved===1)await new Promise(resolve=>release=resolve);return {revision:saved};};`);
  await run('originalPersist()');
  assert.equal(run('saved'),1);
  assert.equal(run('localStorage.getItem(pendingKey())'),'1');
  await run("state.runs.push({id:'later'});originalPersist()");
  assert.equal(run('saved'),1);
  await run('release();cloudSyncTask');
  assert.equal(run('saved'),2);
  assert.equal(run('localStorage.getItem(pendingKey())'),null);
});

test('startup keeps conflicting local edits without asking to overwrite cloud',async()=>{
  const {run}=app();
  run(`remoteEnabled=true;localStorage.setItem(pendingKey(),'1');
    saveLocalState=async()=>{};globalThis.puts=0;
    api=async(path,data)=>{if(data)puts++;return {revision:7,state:{datasets:[],runs:[{id:'remote-only'}]}};};
    confirm=()=>{throw new Error('Unexpected destructive prompt');};`);
  await run('connectCloud()');
  assert.equal(run('state.datasets[0].id'),'a');
  assert.equal(run('puts'),0);
  assert.equal(run('syncReady'),false);
  assert.equal(run('localStorage.getItem(pendingKey())'),'1');
});

test('an import started during cloud loading is saved and cannot be overwritten',async()=>{
  const {run}=app();
  run(`remoteEnabled=true;globalThis.releaseRead=null;globalThis.draftSaves=0;
    saveLocalState=async()=>{draftSaves++;};
    api=async()=>new Promise(resolve=>releaseRead=()=>resolve({revision:2,state:{datasets:[],runs:[{id:'remote'}]}}));
    globalThis.loading=connectCloud();`);
  await run("addDataset('New import',[{ID:'NEW'}],{save:false})");
  assert.equal(run('draftSaves'),1);
  await run('releaseRead();loading');
  assert.equal(run('state.datasets[0].name'),'New import');
  assert.equal(run('localStorage.getItem(pendingKey())'),'1');
});

test('CSRF refresh retries only a rejected request for the same account',async()=>{
  const {run}=app();
  run(`currentAccount={id:'alice'};csrfToken='stale';globalThis.requests=[];
    fetch=async(path,opts)=>{requests.push({path,token:opts?.headers?.['X-CSRF-Token']});
      if(path==='/api/auth/session')return Response.json({user:{id:'alice'},csrf:'fresh'});
      return opts.headers['X-CSRF-Token']==='fresh'?Response.json({ok:true}):Response.json({error:'stale',code:'CSRF_STALE'},{status:403});};`);
  const result=await run("api('predict',{rows:[]})");
  assert.equal(result.ok,true);
  assert.equal(run('requests.length'),3);
});

test('large cloud snapshots use requests below one MiB and commit only at the end',async()=>{
  const {run}=app();
  run(`globalThis.uploaded=[];api=async(path,data)=>{uploaded.push({path,size:data instanceof Blob?data.size:JSON.stringify(data).length});
    return path.endsWith('/uploads')?{upload_id:'upload'}:{revision:1};};`);
  await run("sendCloudSnapshot({datasets:[],runs:[{id:'big',note:'x'.repeat(5*1024*1024)}]},0)");
  assert.ok(run('uploaded.length')>=7);
  assert.equal(run('uploaded.every(r=>r.size<=1024*1024)'),true);
  assert.match(run('uploaded.at(-1).path'),/commit$/);
});

test('a changed account or real permission denial is never retried',async()=>{
  const {run}=app();
  run(`currentAccount={id:'alice'};csrfToken='old';globalThis.calls=0;
    fetch=async(path)=>{calls++;return path==='/api/auth/session'?Response.json({user:{id:'bob'},csrf:'new'}):Response.json({error:'stale',code:'CSRF_STALE'},{status:403});};`);
  await assert.rejects(run("api('predict',{})"),/Tài khoản/);
  assert.equal(run('calls'),2);
  run(`calls=0;fetch=async()=>{calls++;return Response.json({error:'forbidden',code:'ROLE_FORBIDDEN'},{status:403});};`);
  await assert.rejects(run("api('predict',{})"),/forbidden/);
  assert.equal(run('calls'),1);
});

test('changing model recomputes an existing single prediction on the same input',async()=>{
  const {run,elements}=app();
  run(`models=[{name:'LR',threshold:.4}];$('model-choice').value='LR';$('decision-basis').value='raw';
    globalThis.predicted=null;predictSingle=async()=>{predicted={model:model().name,id:$('single-ID').value};};
    $('single-ID').value='new';runBatch=async()=>{};`);
  await elements.get('model-choice').handlers.change({});
  assert.equal(run('predicted?.model'),'LR');
  assert.equal(run('predicted?.id'),'new');
});

test('dataset removal retains versions and prediction history',async()=>{
  const {run}=app();
  run("confirm=()=>true;selectDataset=()=>{};state.runs=[{id:'run1',datasetId:'a',versionId:'v1'}]");
  await run('deleteDataset()');
  assert.equal(run('state.datasets[0].deleted'),true);
  assert.equal(run('state.datasets[0].versions[0].rows[0].ID'),'old');
  assert.equal(run('state.runs[0].id'),'run1');
});

test('renaming a dataset preserves historical run name',async()=>{
  const {run}=app();
  run("prompt=()=> 'Renamed';state.runs=[{id:'run1',name:'A',datasetId:'a'}]");
  await run('renameDataset()');
  assert.equal(run('state.datasets[0].name'),'Renamed');
  assert.equal(run('state.runs[0].name'),'A');
});

test('duplicate transfer is rejected without replacing existing input or history',async()=>{
  const {run,elements}=app();run('transferSingle()');
  elements.get('transfer-target').value='a';run("singleInputs.ID='old'");
  await assert.rejects(run('confirmTransfer({preventDefault(){}})'),/ID/);
  assert.equal(run('state.datasets[0].versions.length'),1);
  assert.equal(run('state.datasets[0].versions[0].rows[0].AGE'),30);
});

test('transfer to a copy keeps destination and prior results untouched',async()=>{
  const {run,elements}=app();run('transferSingle()');
  elements.get('transfer-target').value='a';elements.get('transfer-copy').checked=true;
  elements.get('transfer-copy-name').value='Copy A';
  await run('confirmTransfer({preventDefault(){}})');
  assert.equal(run('state.datasets.length'),3);
  assert.equal(run('state.datasets[0].name'),'Copy A');
  assert.equal(run('state.datasets[0].versions[0].rows.length'),2);
  assert.equal(run("state.datasets.find(d=>d.id==='a').versions.length"),1);
});

test('history opens the selected run even when a newer run has the same model and settings',()=>{
  const {run}=app();
  run(`models=[{name:'RF',digest:'hash'}];$('model-choice').value='RF';
    configuration=()=>({decision:.5,low:.2,high:.5,basis:'raw'});
    state.runs=['new','old'].map(id=>({id,datasetId:'a',versionId:'v1',modelName:'RF',modelHash:'hash',thresholds:configuration(),rows:[]}));
    setModelInfo=()=>{};resetFilters=()=>{};invalidateSingle=()=>{};batchTab=()=>{};
    openRun(state.runs[1]);`);
  assert.equal(run('activeRun().id'),'old');
});

test('performance compares unlabelled inputs, saves separate runs and reuses them',async()=>{
  const {run}=app();
  run(`models=[{name:'RF',digest:'rf',version:'v1',threshold:.39},{name:'LR',digest:'lr',version:'v1',threshold:.42}];
    configuration=()=>({decision:.39,low:.2,high:.5,basis:'raw'});
    globalThis.saves=0;persist=async()=>{saves++;};
    busy=async(_,fn)=>fn();renderModels=()=>{};globalThis.calls=[];
    inferRows=async(rows,m,config)=>{calls.push({name:m.name,decision:config.decision});return rows.map(r=>({...r,probability:.25,raw_score:.4,default_label:1,risk_level:'Medium'}));};`);
  await run('compareModels()');
  assert.equal(run('state.runs.length'),2);
  assert.equal(run('calls[1].decision'),.42);
  assert.equal(run('saves'),1);
  assert.equal(run('performanceRows()[0].mean_pd'),'25.00%');
  assert.equal(run('performanceRows()[0].Accuracy'),'—');
  await run('compareModels()');
  assert.equal(run('calls.length'),2);
  assert.equal(run('saves'),1);
  run("selectedDataset='b';selectedVersion='v2'");
  assert.equal(run("performanceRows().every(r=>r.status==='Chưa chạy')"),true);
});

test('batch progress counts completed records including the last chunk',async()=>{
  const {run}=app();
  run(`api=async(_,data)=>({rows:data.rows});`);
  await run("inferRows(Array.from({length:1000},(_,i)=>({ID:String(i)})),{name:'RF'},{})");
  assert.equal(run("$('busy-progress').value"),100);
  assert.match(run("$('busy-detail').textContent"),/1[.,]?000/);
});

test('stable batches preserve output order and allow only one request at a time',async()=>{
  const {run}=app();
  run(`globalThis.pending=0;globalThis.peak=0;
    api=async(_,data)=>{pending++;peak=Math.max(peak,pending);await new Promise(resolve=>setTimeout(resolve,data.rows[0].ID==='0'?20:1));pending--;return {rows:data.rows};};`);
  const output=await run("inferRows(Array.from({length:1200},(_,i)=>({ID:String(i)})),{name:'RF'},{})");
  assert.equal(run('peak'),1);
  assert.deepEqual(Array.from(output,r=>r.ID),Array.from({length:1200},(_,i)=>String(i)));
});

test('upload synchronizes the dataset and prediction together once',async()=>{
  const {run}=app();
  run(`globalThis.saves=0;persist=async()=>{saves++;};busy=async(_,fn)=>fn();
    api=async()=>({rows:[{ID:'new',AGE:40}]});runBatch=async()=>{await persist();};`);
  await run("upload({target:{files:[new File(['data'],'sample.csv')],value:'sample.csv'}})");
  assert.equal(run('saves'),1);
});

test('upload keeps imported inputs if prediction fails',async()=>{
  const {run}=app();
  run(`globalThis.saves=0;persist=async()=>{saves++;};busy=async(_,fn)=>fn();
    api=async()=>({rows:[{ID:'new',AGE:40}]});runBatch=async()=>{throw new Error('Prediction failed');};`);
  await assert.rejects(run("upload({target:{files:[new File(['data'],'sample.csv')],value:'sample.csv'}})"),/Prediction failed/);
  assert.equal(run('saves'),1);
  assert.equal(run('state.datasets[0].versions[0].rows[0].ID'),'new');
});


test('slow successful requests are not aborted by a short client deadline',async()=>{
  const {run}=app();
  run(`const realTimer=setTimeout;globalThis.deadlines=0;
    setTimeout=(fn,ms)=>{if(ms===20000||ms===25000){deadlines++;Promise.resolve().then(fn);return 0;}return realTimer(fn,ms);};
    fetch=async(_,options)=>{await new Promise(resolve=>realTimer(resolve,5));if(options.signal?.aborted)throw Object.assign(new Error('aborted'),{name:'AbortError'});return Response.json({ok:true});};`);
  assert.equal((await run("api('predict',{rows:[]})")).ok,true);
  assert.equal(run('deadlines'),0);
});
