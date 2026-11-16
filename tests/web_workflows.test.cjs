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
    api=async()=>({scale:'Tree SHAP · điểm thô',rows:[{feature:'PAY_1',contribution:.1},{feature:'PAY_RATIO_1',contribution:-.03},{feature:'AGE',contribution:null}]});`);
  await run('explainSingle()');
  const html=run("$('explanation').innerHTML");
  assert.match(html,/Trạng thái trả nợ tháng gần nhất/);
  assert.match(html,/Tăng điểm/);
  assert.match(html,/Giảm điểm/);
  assert.match(html,/shap-bar/);
  assert.deepEqual(chartTooltips(html).map(row=>[row.yTitle,row.value,row.series]),[['Đóng góp SHAP','+0.1000','Tăng điểm'],['Đóng góp SHAP','-0.0300','Giảm điểm'],['Đóng góp SHAP','Không có dữ liệu','']]);
});

test('datasets and prediction history have separate pages and sidebar links',()=>{
  const html=fs.readFileSync('frontend/index.html','utf8');
  const management=html.split('id="page-datasets"')[1].split('</section>')[0];
  assert.match(management,/id="datasets-table"/);
  assert.doesNotMatch(management,/id="history-table"/);
  assert.match(management,/Quản lý dữ liệu/);
  const history=html.split('id="page-history"')[1].split('</section>')[0];
  assert.match(history,/id="history-table"/);
  assert.match(history,/id="history-search"/);
  assert.doesNotMatch(history,/id="datasets-table"|id="data-table"/);
  assert.match(html,/data-page="datasets" href="#datasets"/);
  assert.match(html,/data-page="history" href="#history"/);
  assert.doesNotMatch(html,/Đơn lẻ &amp; hàng loạt/);
});

test('history links open the dedicated history page',()=>{
  const {run,elements}=app();
  run("$('sidebar').classList={remove(){}};$('menu-toggle').setAttribute=()=>{};location.hash='#history'");
  let scrolled=false;
  run("$('history-title')");
  elements.get('history-title').scrollIntoView=()=>{scrolled=true;};
  elements.get('history-title').focus=()=>{};
  run('navigate()');
  assert.equal(run('document.title'),'Lịch sử dự báo · CreditRisk AI');
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

test('choosing a profile reveals its ID and enables editing without rebuilding the table',()=>{
  const {run}=app();
  run(`globalThis.profileSelect=null;globalThis.profileTableRenders=0;
    table=(id,columns,rows,options)=>{if(id==='data-table'){profileSelect=options.select;profileTableRenders++;}};
    pagination=()=>{};renderDatasets();`);
  assert.equal(run("$('edit-customer').disabled"),true);
  run("profileSelect({ID:'old'});");
  assert.match(run("$('data-caption').textContent"),/Đang chọn hồ sơ old/);
  assert.equal(run("$('edit-customer').disabled"),false);
  assert.equal(run('profileTableRenders'),1);
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
    setModelInfo=()=>{};resetFilters=()=>{};invalidateSingle=()=>{};batchTab=()=>{};navigate=()=>{};
    globalThis.opened=[];
    $('lookup-title').focus=options=>opened.push(['focus',options.preventScroll]);
    $('lookup-title').scrollIntoView=options=>opened.push(['scroll',options.block]);
    openRun(state.runs[1]);`);
  assert.equal(run('activeRun().id'),'old');
  assert.equal(run('location.hash'),'overview');
  assert.deepEqual(Array.from(run('opened'),row=>Array.from(row)),[['focus',true],['scroll','center']]);
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

function chartTooltips(html){
  return [...html.matchAll(/data-chart-data="([^"]+)"/g)].map(([,data])=>
    JSON.parse(data.replaceAll('&quot;','"').replaceAll('&amp;','&')));
}

test('bar tooltips distinguish the two axes, series, zero and missing values',()=>{
  const {run}=app();
  const html=run("barChart('PD','', ['30–40%','40–50%','50–60%'],[9536,0,null],{xAxis:'Khoảng PD',colors:['red','green','blue'],series:['Thấp','Trung bình','Cao'],threshold:.42})");
  const data=chartTooltips(html);
  assert.deepEqual(data[0],{xTitle:'Khoảng PD',x:'30–40%',yTitle:'Số hồ sơ',value:'9.536',series:'Thấp'});
  assert.equal(data[1].value,'0');
  assert.equal(data[2].value,'Không có dữ liệu');
  for(const color of ['red','green','blue']){
    assert.match(html,new RegExp('class="chart-bar"[^>]*fill="'+color+'"'));
  }
  assert.match(html,/<text class="chart-label"[^>]*>[^<]*%<\/text>/);
  assert.doesNotMatch(html,/class="number"|<title>/);
});

test('ROC selects the nearest plotted point and uses the rendered stroke color',()=>{
  const {run}=app();
  const data=run(`
    globalThis.DOMPoint=class {constructor(x,y){this.x=x;this.y=y;} matrixTransform(){return this;}};
    globalThis.getComputedStyle=()=>({stroke:'rgb(37, 99, 235)'});
    const target={dataset:{chartData:JSON.stringify({xTitle:'FPR',yTitle:'TPR',series:'ROC'})},
      classList:{contains:()=>true},getScreenCTM:()=>({inverse:()=>null}),getAttribute:()=>'45,195 45,25 475,25',
      closest:()=>({querySelector:()=>({matches:()=>true})})};
    chartHoverData(target,{clientX:50,clientY:28});
  `);
  assert.equal(data.x,'0.00%');
  assert.equal(data.value,'100.00%');
  assert.equal(data.color,'rgb(37, 99, 235)');
});

test('tooltip follows the pointer, uses each mark color and hides outside data',()=>{
  const {run}=app();
  run(`
    document.documentElement={clientWidth:400,clientHeight:300};
    globalThis.swatch={style:{}};
    document.createElement=()=>({style:{},offsetWidth:120,offsetHeight:64,hidden:false,
      firstElementChild:{firstElementChild:swatch},setAttribute(){}});
    document.body={append(){}};
    globalThis.getComputedStyle=mark=>mark.style;
  `);
  // Exercise the delegated handlers with the same SVG and HTML mark shapes as the charts.
  const source=fs.readFileSync('frontend/static/app.js','utf8');
  run("globalThis.chartHandlers={};document.addEventListener=(type,handler)=>chartHandlers[type]=handler;");
  run(source.slice(source.indexOf("document.addEventListener('pointermove'"),source.indexOf('function barChart(')));
  run(`
    globalThis.datum=(style,kind)=>{
      const mark={style,matches:selector=>selector===kind};
      const target={dataset:{chartData:JSON.stringify({xTitle:'Nhóm',x:'A',yTitle:'Chỉ số',value:'2',series:'Chuỗi A'})},
        classList:{contains:()=>false},closest:selector=>selector==='.chart-datum'?null:target,
        querySelector:()=>mark,contains:()=>false};
      return target;
    };
    globalThis.hover=(target,x,y)=>chartHandlers.pointermove({target,clientX:x,clientY:y,pointerType:'mouse'});
    globalThis.bar=datum({fill:'rgb(7, 127, 131)'},'.chart-bar');
    hover(bar,30,40);
  `);
  assert.equal(run('swatch.style.backgroundColor'),'rgb(7, 127, 131)');
  assert.match(run('chartTooltip.innerHTML'),/Chuỗi A.*Nhóm.*Chỉ số/);
  assert.equal(run('chartTooltip.style.left'),'42px');
  run("hover(datum({fill:'rgb(156, 104, 7)'},'.status-fill'),390,290);");
  assert.equal(run('swatch.style.backgroundColor'),'rgb(156, 104, 7)');
  assert.equal(run('chartTooltip.style.left'),'258px');
  assert.equal(run('chartTooltip.style.top'),'214px');
  run('chartHandlers.pointerout({target:bar,relatedTarget:null});');
  assert.equal(run('chartTooltip.hidden'),true);
});

test('status proportions retain all categories and count each version once',()=>{
  const {run}=app();
  run("models=[{digest:'rf',name:'RF'}];$('model-choice').value='RF';state.runs=[{datasetId:'b',modelHash:'rf'}]");
  const html=run("statusChart([{d:{id:'a'},v:{rows:[{}]},run:null},{d:{id:'b'},v:{rows:[{},{}]},run:null},{d:{id:'c'},v:{rows:[{}]},run:{}}])");
  const data=chartTooltips(html);
  assert.deepEqual(data.map(row=>row.value),['25.00% · 1 hồ sơ','25.00% · 1 hồ sơ','50.00% · 2 hồ sơ']);
  assert.match(html,/pie-chart/);
  assert.match(html,/Phiên bản đang chọn · Model đang chọn · Không áp dụng bộ lọc/);
});

test('pie charts show exact shares, zero categories, a full circle and an empty state',()=>{
  const {run}=app();
  const html=run("pieChart('Cơ cấu','Sau lọc',['Thấp','Cao','Không có'],[3,1,0],{colors:['#087f83','#bd2946','#56657d']})");
  assert.deepEqual(chartTooltips(html).map(row=>row.value),['75.00% · 3 hồ sơ','25.00% · 1 hồ sơ']);
  assert.match(html,/stroke-dasharray="75 100"/);
  assert.match(html,/stroke-dashoffset="-75"/);
  assert.match(html,/Không có.*0 hồ sơ.*0.00%/s);
  assert.match(html,/aria-label="Cơ cấu · 4 hồ sơ"/);
  assert.match(run("pieChart('Một nhóm','',['Có'],[1])"),/stroke-dasharray="100 100"/);
  const empty=run("pieChart('<script>','',['Không có'],[0])");
  assert.match(empty,/Chưa có hồ sơ/);
  assert.doesNotMatch(empty,/NaN|Infinity|class="pie-slice"|<script>/);
});

test('overview proportions follow filtered rows and actual labels use only valid targets',()=>{
  const {run}=app();
  run(`activeRun=()=>({modelName:'RF',thresholds:{decision:.39,basis:'raw',low:.2,high:.5},rows:[]});
    filteredRows=()=>[
      {AGE:30,LIMIT_BAL:20000,EDUCATION:2,SEX:1,MARRIAGE:1,PAY_0:0,probability:.1,raw_score:.1,risk_level:'Low',default_label:0,'default.payment.next.month':0},
      {AGE:40,LIMIT_BAL:30000,EDUCATION:4,SEX:2,MARRIAGE:2,PAY_0:2,probability:.8,raw_score:.8,risk_level:'High',default_label:1,'default.payment.next.month':null},
      {AGE:50,LIMIT_BAL:40000,EDUCATION:4,SEX:2,MARRIAGE:2,PAY_0:3,probability:.9,raw_score:.9,risk_level:'High',default_label:1,'default.payment.next.month':1}];
    $('chart-mode').value='risk';renderOverview();`);
  assert.match(run("$('charts').innerHTML"),/pie-chart/);
  assert.match(run("$('charts').innerHTML"),/66.67% · 2 hồ sơ/);
  assert.match(run("$('supplementary-charts').innerHTML"),/Nhãn cảnh báo.*pie-chart/s);
  run("$('chart-mode').value='data';renderOverview()");
  assert.equal((run("$('charts').innerHTML").match(/class="pie-chart"/g)||[]).length,3);
  assert.match(run("$('charts').innerHTML"),/Sau đại học|Đại học/);
  run("$('chart-mode').value='evaluation';renderOverview()");
  const html=run("$('charts').innerHTML");
  assert.match(html,/2 nhãn 0\/1 hợp lệ.*1 hồ sơ chưa có nhãn/s);
  assert.deepEqual(chartTooltips(html).filter(row=>row.yTitle==='Tỷ trọng hồ sơ').map(row=>row.value),['50.00% · 1 hồ sơ','50.00% · 1 hồ sơ']);
});

test('histogram threshold follows its domain and stays in bounds at either edge',()=>{
  const {run}=app();
  const html=run("barChart('PD','', ['0–50%','50–100%'],[1,2],{threshold:.39})");
  assert.match(html,/x1="223\.74"/);
  assert.equal(chartTooltips(html).at(-1).value,'39.00%');
  assert.match(html,/Ngưỡng τ = 39\.00%<\/text>/);
  assert.match(html,/<text class="chart-label"[^>]*>[^<]*%<\/text>/);
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
      thresholds:configuration(),rows:[{ID:'one',AGE:30,LIMIT_BAL:20000,probability:.75,risk_level:'High',default_label:1}]}];
    state.datasets[1].versions[0].id='v1';
    state.datasets[1].versions[0].rows=[{ID:'1'},{ID:'2'}];
    renderResults=()=>{};resetFilters();renderOverview();`);
  assert.match(run("$('portfolio-metrics').innerHTML"),/75\.00%/);
  run("selectDataset('b');renderOverview()");
  const metrics=run("$('portfolio-metrics').innerHTML");
  assert.match(metrics,/B \(2\)/);
  assert.doesNotMatch(metrics,/75\.00%|A \(1\)/);
  assert.equal(run("$('dashboard-content').hidden"),true);
  assert.equal(run("$('dashboard-awaiting').hidden"),false);
});


test('overview hosts batch controls and filters categories with OR within a field and AND between fields',()=>{
  const {run}=app();
  run(`activeRun=()=>({rows:[
    {ID:'a',AGE:30,LIMIT_BAL:20000,probability:.3,SEX:1,MARRIAGE:1},
    {ID:'b',AGE:40,LIMIT_BAL:30000,probability:.5,SEX:2,MARRIAGE:2},
    {ID:'c',AGE:60,LIMIT_BAL:40000,probability:.8,SEX:1,MARRIAGE:2}]});
    renderResults=()=>{};renderOverview=()=>{};resetFilters();
    document.querySelectorAll=selector=>selector==='[data-filter-field]:checked'?[
      {dataset:{filterField:'SEX'},value:'1'},
      {dataset:{filterField:'SEX'},value:'2'},
      {dataset:{filterField:'MARRIAGE'},value:'2'}]:[];
    $('max-age').value=50;`);
  assert.deepEqual(Array.from(run('filteredRows().map(r=>r.ID)')),['b']);
  run("$('max-age').value=100");
  assert.deepEqual(Array.from(run('filteredRows().map(r=>r.ID)')),['b','c']);
  run("document.querySelectorAll=()=>[]");
  assert.equal(run('filteredRows().length'),3);
  const html=fs.readFileSync('frontend/index.html','utf8');
  const overview=html.slice(html.indexOf('id="page-overview"'),html.indexOf('id="page-datasets"'));
  for(const id of ['batch-panel','run-batch','results-table','min-age','max-age'])assert.ok(overview.includes(`id="${id}"`));
  for(const key of ['SEX','MARRIAGE','EDUCATION'])assert.ok(overview.includes(`data-filter-field="${key}"`));
});


test('overview export uses the same filtered rows as the dashboard',async()=>{
  const {run}=app();
  run(`location.hash='#overview';activeRun=()=>({rows:[{ID:'all'}],thresholds:{decision:.42}});
    filteredRows=()=>[{ID:'selected'}];globalThis.exported=null;
    exportRows=async(rows,thresholds)=>{exported={rows,thresholds};};`);
  await run('exportCurrent()');
  assert.equal(run('exported.rows[0].ID'),'selected');
  assert.equal(run('exported.thresholds.decision'),.42);
});

test('empty dashboard filters show an empty state instead of plotting invalid values',()=>{
  const {run}=app();
  run(`activeRun=()=>({rows:[],modelName:'RF',thresholds:{decision:.42,basis:'raw'}});
    filteredRows=()=>[];renderOverview();`);
  assert.match(run("$('charts').innerHTML"),/Không có hồ sơ phù hợp/);
  assert.doesNotMatch(run("$('charts').innerHTML"),/NaN|Infinity/);
});


test('dashboard C has one run sheet before results and collapsed lookup filters',()=>{
  const html=fs.readFileSync('frontend/index.html','utf8');
  const overview=html.slice(html.indexOf('id="page-overview"'),html.indexOf('id="page-datasets"'));
  assert.equal((overview.match(/class="dataset-select"/g)||[]).length,1);
  assert.doesNotMatch(overview,/id="analyze-selected"|id="batch-dataset"/);
  assert.ok(overview.indexOf('id="run-batch"')<overview.indexOf('id="portfolio-metrics"'));
  assert.ok(overview.indexOf('id="portfolio-metrics"')<overview.indexOf('id="results-table"'));
  assert.doesNotMatch(overview,/<details[^>]*id="dashboard-filters"[^>]*\bopen/);
});

test('dashboard filter summary reveals active ranges and categories even when folded',()=>{
  const {run}=app();
  run(`renderResults=()=>{};renderOverview=()=>{};resetFilters();renderFilterSummary();`);
  assert.equal(run("$('filter-summary').textContent"),'Chưa áp dụng bộ lọc');
  run(`$('min-pd').value=25;document.querySelectorAll=selector=>selector==='[data-filter-field]:checked'?[{dataset:{filterField:'risk_level'},value:'High'}]:[];renderFilterSummary();`);
  assert.match(run("$('filter-summary').textContent"),/PD 25–100%/);
  assert.match(run("$('filter-summary').textContent"),/Mức rủi ro: Cao/);
});


test('PD charts retain percentage bin labels, axes and a keyboard-scrollable viewport',()=>{
  const {run}=app();
  const html=run(`barChart('PD','Distribution',['0–10%','10–20%'],[1,2],{xAxis:'Khoảng PD'})`);
  assert.match(html,/<text class="chart-label"[^>]*>0–10%<\/text>/);
  assert.match(html,/<text class="chart-label"[^>]*>10–20%<\/text>/);
  assert.match(html,/>Khoảng PD<\/text>/);
  assert.match(html,/class="chart-scroll" tabindex="0"/);
});
