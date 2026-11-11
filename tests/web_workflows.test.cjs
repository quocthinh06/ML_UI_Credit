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
    crypto:webcrypto, TextEncoder, structuredClone, performance, FormData, File, Blob, Response, AbortController, setTimeout, clearTimeout, console,
    localStorage:{values:new Map(),getItem(k){return this.values.get(k)||null;},setItem(k,v){this.values.set(k,String(v));},removeItem(k){this.values.delete(k);}},
    Option:function(text,value){this.text=text;this.value=value;}});
  const source = fs.readFileSync('frontend/static/app.js','utf8');
  vm.runInContext(source.slice(0, source.lastIndexOf('initialize().catch')), context);
  vm.runInContext(`globalThis.originalPersist=persist;globalThis.originalApi=api;persist=async()=>{};saveLocalState=async()=>{};renderAll=()=>{};notify=()=>{};
    state={datasets:[{id:'a',name:'A',versions:[{id:'v1',revision:1,rows:[{ID:'old',AGE:30}]}]},
      {id:'b',name:'B',versions:[{id:'v2',revision:1,rows:[]}]}],runs:[]};
    selectedDataset='a';selectedVersion='v1';singleInputs={ID:'new',AGE:40};`, context);
  return {run: code=>vm.runInContext(code,context), elements};
}

test('AI commentary escapes text, caches the same result and preserves missing-field provenance',async()=>{
  const {run}=app();
  run(`models=[{name:'RF'}];$('model-choice').value='RF';singleInputs={ID:'one',AGE:34};singleConfig={decision:.39};
    singleResult={imputation:{rows:[{fields:['AGE'],values:{AGE:34}}]}};globalThis.calls=0;
    api=async(path,data)=>{calls++;if(data.rows[0].AGE!==null)throw new Error('lost provenance');return {
      status:'ok',provider:'Groq',model:'test',insights:[{text:'<script>alert(1)</script>',features:['PAY_1']}],
      checks:[{text:'Xác minh trả nợ'}],evidence:[{feature:'PAY_1',value:2,contribution:.1}]};};`);
  await run('generateInsights();');
  await run('generateInsights();');
  assert.equal(run('calls'),1);
  assert.match(run("$('ai-insights').innerHTML"),/&lt;script&gt;/);
  assert.doesNotMatch(run("$('ai-insights').innerHTML"),/<script>/);
});

test('a delayed AI response cannot attach to edited input',async()=>{
  const {run}=app();
  run(`models=[{name:'RF'}];$('model-choice').value='RF';singleInputs={ID:'one'};singleResult={};singleConfig={};
    globalThis.releaseAI=null;api=async()=>new Promise(resolve=>releaseAI=()=>resolve({status:'ok'}));
    globalThis.pendingAI=generateInsights();invalidateSingle();`);
  await run('releaseAI();pendingAI');
  assert.equal(run('singleResult'),null);
  assert.equal(run("$('generate-insights').disabled"),true);
});

test('filled values retain provenance across a new prediction until explicitly edited',()=>{
  const {run}=app();
  run("features=['AGE'];$('single-ID').value='one';$('single-AGE').dataset={};markImputed({rows:[{fields:['AGE'],values:{AGE:34}}]})");
  assert.equal(run("$('single-AGE').value"),'34');
  assert.equal(run("formRow('single').AGE"),null);
  run("delete $('single-AGE').dataset.imputedValue");
  assert.equal(run("formRow('single').AGE"),34);
});

test('only supplementary inputs may be left blank',()=>{
  const {run}=app();
  run("features=['LIMIT_BAL','SEX','EDUCATION','MARRIAGE','AGE','PAY_0','PAY_AMT6'];inputFields('single-fields','single')");
  const html=run("$('single-fields').innerHTML");
  assert.match(html, /name="LIMIT_BAL"[^>]*required/);
  assert.match(html, /name="PAY_0"[^>]*required/);
  for(const name of ['SEX','EDUCATION','MARRIAGE','AGE','PAY_AMT6']){
    assert.doesNotMatch(html,new RegExp(`name="${name}"[^>]*required`));
  }
});

test('SHAP uses readable names and opposite directions for positive and negative values',async()=>{
  const {run}=app();
  run(`models=[{name:'RF'}];$('model-choice').value='RF';singleInputs={ID:'one'};
    api=async()=>({scale:'Tree SHAP · điểm thô',rows:[{feature:'PAY_1',contribution:.1},{feature:'PAY_RATIO_1',contribution:-.03}]});`);
  await run('explainSingle()');
  const html=run("$('explanation').innerHTML");
  assert.match(html,/Trạng thái trả nợ tháng gần nhất/);
  assert.match(html,/Tăng điểm/);
  assert.match(html,/Giảm điểm/);
  assert.match(html,/shap-bar/);
});

test('datasets and prediction history share one management page',()=>{
  const html=fs.readFileSync('frontend/index.html','utf8');
  const management=html.split('id="page-datasets"')[1].split('</section>')[0];
  assert.match(management,/id="datasets-table"/);
  assert.match(management,/id="history-table"/);
  assert.match(management,/Quản lý dữ liệu lịch sử/);
  assert.doesNotMatch(html,/data-page="history"|id="page-history"/);
  assert.doesNotMatch(html,/Đơn lẻ &amp; hàng loạt/);
});

test('old history links open the combined management page and its history',()=>{
  const {run,elements}=app();
  run("$('sidebar').classList={remove(){}};$('menu-toggle').setAttribute=()=>{};location.hash='#history'");
  let scrolled=false;
  run("$('history-title')");
  elements.get('history-title').scrollIntoView=()=>{scrolled=true;};
  elements.get('history-title').focus=()=>{};
  run('navigate()');
  assert.equal(run('document.title'),'Quản lý dữ liệu lịch sử · CreditRisk AI');
  assert.equal(scrolled,true);
});

test('view dataset selects its latest version and brings its content into view',()=>{
  const {run,elements}=app();
  const calls=[];
  run("globalThis.datasetAction=null;table=(id,columns,rows,options)=>{if(id==='datasets-table')datasetAction=options.action.run;};pagination=()=>{};renderDatasets()");
  const title=elements.get('data-title');
  title.focus=options=>calls.push(['focus',options.preventScroll]);
  title.scrollIntoView=options=>calls.push(['scroll',options.block]);
  run("dataPage=4;datasetAction({id:'b'})");
  assert.equal(run('selectedDataset'),'b');
  assert.equal(run('selectedVersion'),'v2');
  assert.equal(run('dataPage'),0);
  assert.deepEqual(calls,[['focus',true],['scroll','center']]);
});

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

test('upload registers normalized content once and does not start prediction',async()=>{
  const {run}=app();
  run(`globalThis.saves=0;persist=async()=>{saves++;};busy=async(_,fn)=>fn();
    api=async()=>({rows:[{ID:'new',AGE:40},{ID:'second',AGE:31}]});
    runBatch=async()=>{throw new Error('Unexpected automatic prediction');};`);
  await run("upload({target:{files:[new File(['data'],'sample.csv')],value:'sample.csv'}})");
  run("api=async()=>({rows:[{AGE:31,ID:'second'},{AGE:40,ID:'new'}]})");
  await run("upload({target:{files:[new File(['other'],'same.json')],value:'same.json'}})");
  assert.equal(run('saves'),1);
  assert.equal(run('state.datasets.length'),3);
  assert.equal(run('dataset().name'),'sample.csv');
  assert.equal(run('state.runs.length'),0);
});

test('slow successful requests are not aborted by a short client deadline',async()=>{
  const {run}=app();
  run(`const realTimer=setTimeout;globalThis.deadlines=0;
    setTimeout=(fn,ms)=>{if(ms===20000||ms===25000){deadlines++;Promise.resolve().then(fn);return 0;}return realTimer(fn,ms);};
    fetch=async(_,options)=>{await new Promise(resolve=>realTimer(resolve,5));if(options.signal?.aborted)throw Object.assign(new Error('aborted'),{name:'AbortError'});return Response.json({ok:true});};`);
  assert.equal((await run("api('predict',{rows:[]})")).ok,true);
  assert.equal(run('deadlines'),0);
});

test('profile details predict only canonical inputs without changing dataset or batch history',async()=>{
  const {run}=app();
  run(`features=['AGE'];location.hash='#datasets';$('batch-panel').hidden=true;dataPage=1;resultsPage=2;
    globalThis.filled=null;globalThis.predictions=0;
    inputFields=(_,prefix,row)=>{filled={prefix,row};};
    predictSingle=async()=>{predictions++;singleInputs=filled.row;};navigate=()=>{};batchTab=()=>{};
    globalThis.before=JSON.stringify(state);`);
  await run("openProfileDetails({ID:'old',AGE:30,probability:.8,default_label:1,model_name:'Other'})");
  assert.equal(run('filled.row.ID'),'old');
  assert.equal(run('Object.keys(filled.row).length'),2);
  assert.equal(run('predictions'),1);
  assert.equal(run('JSON.stringify(state)===before'),true);
  run("models=[{name:'LR',threshold:.42}];$('model-choice').value='LR';$('decision-basis').value='raw';globalThis.batchCalls=0;runBatch=async()=>{batchCalls++;};");
  await run("$('model-choice').handlers.change({})");
  assert.equal(run('predictions'),2);
  assert.equal(run('batchCalls'),0);
  assert.equal(run('location.hash'),'predict');
  run('dataPage=0;resultsPage=0;returnToProfiles()');
  assert.equal(run('location.hash'),'#datasets');
  assert.equal(run('selectedDataset'),'a');
  assert.equal(run('selectedVersion'),'v1');
  assert.equal(run('dataPage'),1);
  assert.equal(run('resultsPage'),2);
});

test('clear inputs empties every control and removes previous prediction and profile context',()=>{
  const {run}=app();
  run(`globalThis.fields=[
    {type:'text',value:'KH-001'},{type:'number',value:'0'},{type:'select-one',value:'2'},
    {type:'checkbox',checked:true}
  ];
  fields.forEach(f=>{f.setCustomValidity=()=>{};f.removeAttribute=()=>{};});
  $('single-form').querySelectorAll=()=>fields;
  $('single-ID').focus=()=>{globalThis.focused=true;};
  singleResult={probability:.8};singleConfig={decision:.39};profileOrigin={hash:'#datasets'};
  clearSingle({preventDefault(){globalThis.prevented=true;}});
  `);
  assert.equal(run('fields.slice(0,3).every(f=>f.value==="")'),true);
  assert.equal(run('fields[3].checked'),false);
  assert.equal(run('singleResult===null&&singleInputs===null&&singleConfig===null'),true);
  assert.equal(run('profileOrigin'),null);
  assert.equal(run('focused&&prevented'),true);
  assert.equal(run("$('save-single').disabled&&$('export-single').disabled&&$('explain-single').disabled&&$('transfer-single').disabled"),true);
});

test('a pending single response cannot restore a cleared or edited prediction',async()=>{
  const {run}=app();
  run(`models=[{name:'RF'}];$('model-choice').value='RF';
    $('decision-basis').value='probability';$('decision').value='39';$('low').value='20';$('high').value='50';
    formRow=()=>({ID:'one',AGE:30});busy=async(_,fn)=>fn();
    globalThis.releaseSingle=null;api=()=>new Promise(resolve=>{releaseSingle=resolve;});
    globalThis.pendingSingle=predictSingle({preventDefault(){}});
    invalidateSingle();
    releaseSingle({rows:[{probability:.8}]});`);
  await run('pendingSingle');
  assert.equal(run('singleResult'),null);
  assert.equal(run("$('export-single').disabled"),true);
});

test('histogram threshold follows its domain and stays in bounds at either edge',()=>{
  const {run}=app();
  const html=run("barChart('PD','', ['0–50%','50–100%'],[1,2],{threshold:.39})");
  assert.match(html,/x1="223\.74"/);
  assert.match(html,/Ngưỡng τ = 39\.00%/);
  assert.match(run("barChart('PD','', ['all'],[1],{threshold:0})"),/x1="42"/);
  assert.match(run("barChart('PD','', ['all'],[1],{threshold:1})"),/x1="508"/);
  assert.doesNotMatch(run("barChart('PD','', ['all'],[1])"),/threshold-marker/);
});


test('single prediction stores a local draft and renders SHAP without creating history',async()=>{
  const {run}=app();
  run(`models=[{name:'RF',digest:'rf',threshold:.39}];$('model-choice').value='RF';
    $('decision').value=39;$('low').value=20;$('high').value=50;$('decision-basis').value='raw';
    formRow=()=>({ID:'one',AGE:30});busy=async(_,fn)=>fn();
    globalThis.calls=[];
    api=async path=>{calls.push(path);return path==='predict'
      ?{rows:[{probability:.25,raw_score:.4,risk_level:'Medium',default_label:1}]}
      :{rows:[{feature:'AGE',contribution:.1}],scale:'Tree SHAP'};};`);
  await run('predictSingle({preventDefault(){}})');
  assert.deepEqual(Array.from(run('calls')),['predict','explain']);
  assert.equal(run('JSON.parse(localStorage.getItem(draftKey())).row.ID'),'one');
  assert.equal(run('state.runs.length'),0);
  assert.match(run("$('explanation').innerHTML"),/SHAP.*AGE/s);
});

test('existing copies with the same normalized content appear once in working datasets',async()=>{
  const {run}=app();
  await run(`state.datasets.push({id:'duplicate',name:'Old copy',versions:[{id:'duplicate-v1',rows:[{AGE:30,ID:'old'}]}]});
    indexDatasets(state);`);
  assert.deepEqual(Array.from(run('workingDatasets().map(d=>d.id)')),['a','b']);
});


test('overview only shows results for the selected dataset and version',()=>{
  const {run}=app();
  run(`models=[{name:'RF',digest:'hash'}];$('model-choice').value='RF';
    $('decision').value=39;$('low').value=20;$('high').value=50;$('decision-basis').value='raw';
    $('chart-mode').value='data';histogram=()=>[[],[]];barChart=()=> '';
    state.runs=[{id:'run-a',datasetId:'a',versionId:'v1',modelName:'RF',modelHash:'hash',
      thresholds:configuration(),rows:[{probability:.75,risk_level:'High',default_label:1}]}];
    state.datasets[1].versions[0].id='v1';
    state.datasets[1].versions[0].rows=[{ID:'1'},{ID:'2'}];
    renderOverview();`);
  assert.match(run("$('portfolio-metrics').innerHTML"),/75\.00%/);
  run("selectDataset('b');renderOverview()");
  const metrics=run("$('portfolio-metrics').innerHTML");
  assert.match(metrics,/B \(2\)/);
  assert.doesNotMatch(metrics,/75\.00%|A \(1\)/);
  assert.equal(run("$('dashboard-content').hidden"),true);
  assert.equal(run("$('dashboard-awaiting').hidden"),false);
});
