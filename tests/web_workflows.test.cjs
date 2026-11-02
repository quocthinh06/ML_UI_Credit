const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const {webcrypto} = require('node:crypto');

function app() {
  const elements = new Map();
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, {value:'', disabled:false, hidden:false, addEventListener(){},
        replaceChildren(){}, add(){}, showModal(){this.open=true;}, close(){this.open=false;}});
      return elements.get(id);
    }, querySelectorAll(){return [];}, addEventListener(){}
  };
  const context = vm.createContext({document, window:{addEventListener(){}}, location:{hash:''},
    crypto:webcrypto, structuredClone, setTimeout, clearTimeout, console, Option:function(text,value){this.text=text;this.value=value;}});
  const source = fs.readFileSync('creditrisk/static/app.js','utf8');
  vm.runInContext(source.slice(0, source.lastIndexOf('initialize().catch')), context);
  vm.runInContext(`persist=async()=>{};renderAll=()=>{};notify=()=>{};
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
