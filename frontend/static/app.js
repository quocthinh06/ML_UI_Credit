'use strict';

const $ = id => document.getElementById(id);
const fmt = n => Number(n || 0).toLocaleString('vi-VN', {maximumFractionDigits: 2});
const pct = n => n == null || !Number.isFinite(Number(n)) ? '—' : `${(Number(n) * 100).toFixed(2)}%`;
const date = s => new Date(s).toLocaleString('vi-VN');
const imputableFeatures = ['SEX','EDUCATION','MARRIAGE','AGE','PAY_AMT6'];
const riskNames = {Low: 'Thấp', Medium: 'Trung bình', High: 'Cao'};
const escapeHTML = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icons = {
  shield:'<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z"/><path d="m8 12 3 3 5-6"/>',
  overview:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  database:'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
  predict:'<path d="m13 2-9 12h7l-1 8 10-13h-7l1-7Z"/>',
  history:'<path d="M3 11a9 9 0 1 1 2.5 7M3 4v7h7M12 7v5l3 2"/>',
  performance:'<path d="M4 3v17h17M8 15l4-5 4 2 5-7"/>',
  download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  file:'<path d="M14 2H5v20h14V7l-5-5Zm0 0v5h5M8 12h8M8 16h8"/>',
  plus:'<path d="M12 5v14M5 12h14"/>', menu:'<path d="M4 6h16M4 12h16M4 18h16"/>'
};
function icon(name) { return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name] || icons.file}</svg>`; }
document.querySelectorAll('[data-icon]').forEach(el => el.innerHTML = icon(el.dataset.icon));

let state = {datasets: [], runs: []};
let models = [], features = [], selectedDataset = null, selectedVersion = null, selectedCustomer = null;
let singleResult = null, singleInputs = null, singleConfig = null, editId = null, database;
let selectedRunId = null, profileOrigin = null;
let displayedImputationReport = null;
let resultsPage = 0, dataPage = 0, toastTimer;
let singleGeneration = 0;
let remoteEnabled = false, cloudRevision = 0, revisionKnown = false;
let syncReady=false, cloudSyncTask=null, cloudReadTask=null, localGeneration=0;
let currentAccount = null, csrfToken = null, workspaceAccount = null;
const PAGE_SIZE = 25;

function cloudPath(suffix='') { const owner=workspaceAccount||currentAccount?.id;return 'workspace'+suffix+(owner?'?account_id='+encodeURIComponent(owner):''); }
function pendingKey() { return 'creditrisk-cloud-pending'+(currentAccount?'-'+currentAccount.id+'-'+(workspaceAccount||currentAccount.id):''); }

function workspaceKey() {
  let key = localStorage.getItem('creditrisk-workspace-key');
  if (!/^[0-9a-f]{64}$/.test(key || '')) {
    key = Array.from(crypto.getRandomValues(new Uint8Array(32)), value=>value.toString(16).padStart(2,'0')).join('');
    localStorage.setItem('creditrisk-workspace-key', key);
  }
  return key;
}

function notify(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 4500); }
function showError(error) { $('alert').textContent = error.message || String(error); $('alert').hidden = false; $('alert').scrollIntoView({block:'nearest', behavior:'smooth'}); }
function guarded(fn) { return async event => { try { $('alert').hidden = true; await fn(event); } catch(error) { showError(error); } }; }
async function busy(title, fn) {
  if (!$('busy').hidden) throw new Error('Một tác vụ khác đang xử lý.');
  $('busy-title').textContent = title; $('busy-detail').textContent = 'Vui lòng giữ trang mở.';
  $('busy-progress').removeAttribute('value'); $('busy').hidden = false;
  document.querySelector('.workspace').inert = true; $('sidebar').inert = true;
  const started=performance.now();
  const elapsed=()=>{$('busy-elapsed').textContent=`Đã chờ ${Math.floor((performance.now()-started)/1000)} giây · Giữ trang mở để nhận kết quả.`;};
  elapsed();const timer=setInterval(elapsed,1000);
  try { return await fn(); } finally { clearInterval(timer);$('busy').hidden = true; document.querySelector('.workspace').inert = false; $('sidebar').inert = false; }
}
async function api(path, data, options = {}, retried=false) {
  let headers = csrfToken ? {'X-CSRF-Token':csrfToken} : {}, body;
  if(data instanceof Blob){body=data;headers['Content-Type']='application/octet-stream';}
  else if (data instanceof FormData) body = data;
  else if (data !== undefined) {
    headers['Content-Type'] = 'application/json'; body = JSON.stringify(data);
    if (body.length > 100000 && 'CompressionStream' in window) {
      body = await new Response(new Blob([body]).stream().pipeThrough(new CompressionStream('gzip'))).blob();
      headers['Content-Encoding'] = 'gzip';
    }
  }
  const response=await fetch(`/api/${path}`,{method:data===undefined?'GET':'POST',body,...options,headers:{...headers,...options.headers}});
  if(response.status===403&&!retried){
    const denied=await response.clone().json().catch(()=>({}));
    if(denied.code==='CSRF_STALE'){
      const refreshed=await fetch('/api/auth/session',{cache:'no-store'});
      const auth=await refreshed.json();
      if(!auth.user||auth.user.id!==currentAccount?.id){
        throw new Error('Tài khoản đăng nhập đã thay đổi. Dữ liệu cục bộ vẫn được giữ; hãy tải lại trang.');
      }
      csrfToken=auth.csrf;
      return api(path,data,options,true);
    }
  }
  const type=response.headers.get('Content-Type')||'';
  const result=type.includes('json')?await response.json():await response.blob();
  if(!response.ok){
    if(response.status===401&&currentAccount)throw Object.assign(new Error('Phiên đăng nhập hết hạn. Dữ liệu cục bộ vẫn được giữ; hãy đăng nhập lại.'),{status:401});
    throw Object.assign(new Error(type.includes('json')?(result.error||'Không thể xử lý yêu cầu.'):`Máy chủ trả lỗi ${response.status}. Dữ liệu cục bộ vẫn được giữ.`),{status:response.status,code:result.code});
  }
  return result;
}
async function openStorage() {
  database = await new Promise((resolve, reject) => {
    const req = indexedDB.open('creditrisk-ai-v1'+(currentAccount?'-'+currentAccount.id+'-'+(workspaceAccount||currentAccount.id):''), 1);
    req.onupgradeneeded = () => req.result.createObjectStore('app');
    req.onsuccess = () => resolve(req.result); req.onerror = () => reject(new Error('Trình duyệt không cho phép lưu dữ liệu. Hãy bật IndexedDB.'));
  });
  const saved = await new Promise((resolve, reject) => {
    const req = database.transaction('app').objectStore('app').get('state');
    req.onsuccess = () => resolve(req.result); req.onerror = () => reject(req.error);
  });
  if(saved){await indexDatasets(saved);state=saved;}
  const revision=await new Promise((resolve,reject)=>{const req=database.transaction('app').objectStore('app').get('cloudRevision');req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});
  if(Number.isInteger(revision)){cloudRevision=revision;revisionKnown=true;}
}
async function saveLocalState(){
  try{
    await new Promise((resolve,reject)=>{
      const tx=database.transaction('app','readwrite'),store=tx.objectStore('app');store.put(state,'state');
      if(revisionKnown)store.put(cloudRevision,'cloudRevision');
      tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);
    });
  }catch{throw new Error('Không lưu được dữ liệu vào trình duyệt. Hãy sao lưu JSON trước khi đóng trang.');}
}
function syncMessage(message,problem=false){
  $('connection').textContent=problem?'Cục bộ · chưa đồng bộ':message.includes('đã đồng bộ')?'API & MongoDB đã đồng bộ':'API đã kết nối · đồng bộ nền';$('sync-status').hidden=false;
  $('sync-message').textContent=message;
  $('retry-sync').disabled=!!(cloudSyncTask||cloudReadTask);
  $('open-cloud-version').hidden=!problem;
}
function workspaceHeaders(){return currentAccount?{}:{Authorization:`Bearer ${workspaceKey()}`};}
async function persist(){
  localGeneration++;
  if(remoteEnabled)localStorage.setItem(pendingKey(),'1');
  await saveLocalState();
  if(remoteEnabled){
    syncMessage(syncReady?'Đã lưu trên thiết bị · đang chờ đồng bộ':'Đã lưu trên thiết bị · cloud chưa sẵn sàng. Có thể tiếp tục làm việc.',!syncReady);
    startCloudSync();
  }
}
function startCloudSync(){
  if(cloudSyncTask||!syncReady||!localStorage.getItem(pendingKey()))return;
  cloudSyncTask=(async()=>{
    try{
      while(syncReady&&localStorage.getItem(pendingKey())){
        const generation=localGeneration,snapshot=structuredClone(state);
        syncMessage('Đã lưu trên thiết bị · đang đồng bộ nền');
        const result=await sendCloudSnapshot(snapshot,cloudRevision);
        cloudRevision=result.revision;revisionKnown=true;
        await saveLocalState();
        if(generation===localGeneration)localStorage.removeItem(pendingKey());
      }
      syncMessage('API & MongoDB đã đồng bộ');$('sync-status').hidden=true;
    }catch(error){
      // A timed-out write may have committed: re-read the revision before retrying.
      syncReady=false;
      syncMessage(`${error.message} Chưa đồng bộ; bản cục bộ được giữ nguyên.`,true);
    }finally{cloudSyncTask=null;$('retry-sync').disabled=false;}
  })();
  $('retry-sync').disabled=true;
}
async function sendCloudSnapshot(snapshot,revision){
  let content=new Blob([JSON.stringify({state:snapshot,revision})],{type:'application/json'});
  if(content.size>128*1024*1024)throw new Error('Kho vượt 128 MB. Bản cục bộ vẫn được giữ; hãy sao lưu JSON.');
  if(content.size<=1024*1024)return api(cloudPath(),{state:snapshot,revision},{method:'PUT',headers:workspaceHeaders()});
  let encoding='json';
  if('CompressionStream' in window){content=await new Response(content.stream().pipeThrough(new CompressionStream('gzip'))).blob();encoding='gzip';}
  const size=1024*1024,parts=Math.ceil(content.size/size);
  const upload=await api(cloudPath('/uploads'),{revision,encoding,size:content.size,parts},{headers:workspaceHeaders()});
  for(let i=0;i<parts;i++){
    await api(cloudPath(`/uploads/${upload.upload_id}/${i}`),content.slice(i*size,(i+1)*size),{method:'PUT',headers:workspaceHeaders()});
    syncMessage(`Đã lưu trên thiết bị · đồng bộ nền ${i+1}/${parts} phần`);
  }
  return api(cloudPath(`/uploads/${upload.upload_id}/commit`),{},{headers:workspaceHeaders()});
}
function sameValue(a,b){
  if(a===b)return true;
  if(!a||!b||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)!==Array.isArray(b))return false;
  const keys=Object.keys(a);
  return keys.length===Object.keys(b).length&&keys.every(k=>Object.hasOwn(b,k)&&sameValue(a[k],b[k]));
}
function containsCloud(local,remote){
  if(!remote)return true;
  const equal=sameValue;
  return remote.runs.every(r=>local.runs.some(item=>item.id===r.id&&equal(item,r)))&&remote.datasets.every(d=>{
    const own=local.datasets.find(item=>item.id===d.id);
    if(!own)return false;
    const {versions:remoteVersions,...remoteMeta}=d,{versions:localVersions,...localMeta}=own;
    return equal(localMeta,remoteMeta)&&remoteVersions.every(v=>localVersions.some(item=>item.id===v.id&&equal(item,v)));
  });
}
function connectCloud(){
  if(cloudReadTask)return cloudReadTask;
  cloudReadTask=readCloud().finally(()=>{cloudReadTask=null;$('retry-sync').disabled=!!cloudSyncTask;});
  $('retry-sync').disabled=true;return cloudReadTask;
}
async function readCloud(){
  syncReady=false;syncMessage('Đang đọc kho dữ liệu · có thể tiếp tục làm việc');
  try{
    const result=await api(cloudPath(),undefined,{headers:workspaceHeaders()});
    if(result.state)await indexDatasets(result.state);
    let pending=!!localStorage.getItem(pendingKey());
    if(pending&&sameValue(state,result.state)){localStorage.removeItem(pendingKey());pending=false;}
    if(pending&&result.state){
      if(!(revisionKnown&&cloudRevision===result.revision)&&!containsCloud(state,result.state)){
        syncMessage('Có thay đổi ở cả thiết bị và kho. Bản cục bộ được giữ nguyên; hãy sao lưu hoặc chọn mở bản trên kho.',true);
        return;
      }
    }else if(result.state){
      state=result.state;await saveLocalState();
      selectDataset(state.datasets.find(d=>!d.deleted)?.id);
    }
    cloudRevision=result.revision;revisionKnown=true;syncReady=true;
    await saveLocalState();
    if(pending||(!result.state&&(state.datasets.length||state.runs.length))){
      localStorage.setItem(pendingKey(),'1');startCloudSync();
    }else{syncMessage('API & MongoDB đã đồng bộ');$('sync-status').hidden=true;}
  }catch(error){syncMessage(`${error.message} Có thể tiếp tục dùng dữ liệu trên thiết bị.`,true);}
}
async function openCloudVersion(){
  if(cloudSyncTask||cloudReadTask)throw new Error('Đang đồng bộ nền. Vui lòng chờ kết thúc hoặc thử lại.');
  if(!confirm('Mở bản trên kho sẽ thay bản làm việc trên thiết bị. Bản hiện tại được sao lưu JSON và giữ một bản phục hồi trên thiết bị. Tiếp tục?'))return;
  await busy('Đang mở bản trên kho',async()=>{
    const result=await api(cloudPath(),undefined,{headers:workspaceHeaders()});
    await new Promise((resolve,reject)=>{const tx=database.transaction('app','readwrite');tx.objectStore('app').put(state,'recovery-before-cloud');tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});
    if(result.state)await indexDatasets(result.state);
    backup();state=result.state||{datasets:[],runs:[]};cloudRevision=result.revision;revisionKnown=syncReady=true;
    await saveLocalState();localStorage.removeItem(pendingKey());
    selectDataset(state.datasets.find(d=>!d.deleted)?.id);$('sync-status').hidden=true;
  });
}
function dataset() { return state.datasets.find(d => d.id === selectedDataset); }
function version() { const d = dataset(); return d?.versions.find(v => v.id === selectedVersion) || d?.versions.at(-1); }
function model() { return models.find(m => m.name === $('model-choice').value); }
function configuration() {
  const config = {decision: Number($('decision').value) / 100, low: Number($('low').value) / 100, high: Number($('high').value) / 100, basis: $('decision-basis').value};
  if (!Object.values(config).slice(0,3).every(Number.isFinite) || config.low < 0 || config.high > 1 || config.low >= config.high || config.decision < 0 || config.decision > 1) throw new Error('Ngưỡng nhãn thuộc 0–100%; cần 0 ≤ PD thấp < PD cao ≤ 100.');
  return config;
}
function configMatches(a, b) { return ['decision','low','high','basis'].every(k => a[k] === b[k]); }
function activeRun() {
  let config; try { config = configuration(); } catch { return null; }
  const v=version(),m=model();
  if(!v||!m)return null;
  const matches=r=>r.datasetId===selectedDataset&&r.versionId===v.id&&r.modelHash===m.digest&&configMatches(r.thresholds,config);
  return state.runs.find(r=>r.id===selectedRunId&&matches(r))||state.runs.find(matches);
}
function selectDataset(id, vid) { selectedRunId=null; selectedDataset = id; selectedVersion = vid || dataset()?.versions.at(-1)?.id; selectedCustomer = null; resultsPage = dataPage = 0; renderAll(); }
function navigate() {
  const page = location.hash.slice(1) || 'overview';
  const current = page==='history' ? 'datasets' : ['overview','datasets','predict','models'].includes(page) ? page : 'overview';
  document.querySelectorAll('.page').forEach(el => el.hidden = el.id !== `page-${current}`);
  document.querySelectorAll('[data-page]').forEach(el => { el.classList.toggle('active', el.dataset.page === current); if (el.dataset.page === current) el.setAttribute('aria-current','page'); else el.removeAttribute('aria-current'); });
  $('sidebar').classList.remove('open'); $('menu-toggle').setAttribute('aria-expanded','false');
  if(current==='models'&&models.length)renderModels();
  if(current==='predict'&&!$('single-panel').hidden&&singleResult&&$('explanation').hidden)void explainSingle();
  if(page==='history'){$('history-title').focus({preventScroll:true});$('history-title').scrollIntoView({block:'center'});}
  document.title = `${({overview:'Tổng quan',datasets:'Quản lý dữ liệu lịch sử',predict:'Dự báo đơn lẻ',models:'Hiệu năng mô hình'})[current]} · CreditRisk AI`;
}
function batchTab(show) { if(show)clearProfileContext(); $('tab-batch').hidden=!show; $('single-panel').hidden = show; $('batch-panel').hidden = !show; $('tab-single').classList.toggle('active', !show); $('tab-batch').classList.toggle('active', show); $('tab-single').setAttribute('aria-selected', String(!show)); $('tab-batch').setAttribute('aria-selected', String(show)); $('tab-single').tabIndex=show?-1:0; $('tab-batch').tabIndex=show?0:-1; }
function setModelInfo() {
  if (!model()) return;
  $('model-meta').textContent = `${model().version} · τ = ${model().threshold.toFixed(4)}`;
  $('predict-model-title').textContent = `Mô hình dự báo: ${model().name}`;
  $('predict-model-detail').textContent = `${model().version} · CV AUC: ${model().cv_auc?.toFixed(4) ?? '—'} · Test AUC: ${model().test_auc?.toFixed(4) ?? '—'}`;
}
function invalidateSingle() {
  $('ai-insights').replaceChildren();$('generate-insights').disabled=true;
  $('explain-single').hidden=true;
  singleGeneration++;
  $('explanation').replaceChildren();$('draft-status').textContent='';
  singleResult = singleInputs = singleConfig = null;
  ['save-single','export-single','explain-single','transfer-single'].forEach(id => $(id).disabled = true);
  $('result-status').textContent = 'Cần dự báo'; $('result-status').className = 'tag';
  $('single-result').className = 'result-placeholder'; $('single-result').innerHTML = `${icon('shield')}<p>Nhập dữ liệu và chạy dự báo bằng model đang chọn.</p>`; $('explanation').hidden = true;
}

function table(container, columns, rows, {select, action, selected} = {}) {
  const wrap = $(container); wrap.replaceChildren();
  if (!rows.length) { const p = document.createElement('p'); p.className = 'table-empty'; p.textContent = 'Chưa có dữ liệu trong phạm vi đã chọn.'; wrap.append(p); return; }
  const el = document.createElement('table'), head = el.createTHead().insertRow();
  columns.forEach(([key, label]) => { const th = document.createElement('th'); th.scope = 'col'; th.textContent = label; head.append(th); });
  if (action) { const th = document.createElement('th'); th.textContent = 'Thao tác'; head.append(th); }
  const body = el.createTBody();
  rows.forEach(row => {
    const tr = body.insertRow();
    columns.forEach(([key]) => {
      const td = tr.insertCell(), value = row[key];
      if (key === 'risk_level') { const span = document.createElement('span'); span.className = `tag ${String(value).toLowerCase()}`; span.textContent = riskNames[value] || value || '—'; td.append(span); }
      else td.textContent = value == null ? '—' : ['probability','raw_score','actual_rate'].includes(key) ? pct(value) : key === 'created' ? date(value) : typeof value === 'number' ? fmt(value) : typeof value === 'object' ? JSON.stringify(value) : String(value);
      td.title = td.textContent;
    });
    if (select) { tr.className = 'selectable'; tr.tabIndex = 0; tr.setAttribute('aria-label', `Chọn hồ sơ ${row.ID ?? row.name}`); tr.addEventListener('click', () => select(row)); tr.addEventListener('keydown', event => { if(event.target!==tr)return; if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(row); } }); }
    if (selected?.(row)) tr.classList.add('selected');
    if (action) { const td = tr.insertCell(); const button = document.createElement('button'); button.type='button'; button.className = 'button secondary compact'; button.textContent = action.label; button.setAttribute('aria-label',`${action.label} ${row.ID??row.name??''}`); button.addEventListener('click', guarded(event => {event.stopPropagation();return action.run(row);})); td.append(button); }
  }); wrap.append(el);
}
function pagination(id, count, page, change) {
  const foot = $(id); foot.replaceChildren(); const total = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const text = document.createElement('span'); text.textContent = `${fmt(count)} hồ sơ · Trang ${page + 1}/${total}`; foot.append(text);
  const actions = document.createElement('div'); actions.className = 'actions';
  [['Trước',-1],['Sau',1]].forEach(([label, step]) => { const button = document.createElement('button'); button.textContent = label; button.className = 'button secondary compact'; button.disabled = page + step < 0 || page + step >= total; button.addEventListener('click', () => change(page + step)); actions.append(button); }); foot.append(actions);
}
function selectors() {
  const available=workingDatasets();
  document.querySelectorAll('.dataset-select').forEach(select => {
    select.replaceChildren(); if (!available.length) select.add(new Option('Chưa có tập hồ sơ', ''));
    available.forEach(d => {
      const v=d.id===selectedDataset?version():d.versions.at(-1);
      select.add(new Option(`${d.name} · ${fmt(v.rows.length)} hồ sơ · v${v.revision}`, d.id));
    });
    if(selectedDataset&&!available.some(d=>d.id===selectedDataset)&&dataset()){
      select.add(new Option(`${dataset().name} · phiên bản lịch sử`,selectedDataset));
    }
    select.value = selectedDataset || ''; select.disabled = !available.length;
  });
  $('version-choice').replaceChildren(); dataset()?.versions.slice().reverse().forEach(v => $('version-choice').add(new Option(`Phiên bản ${v.revision} · ${date(v.created)}`, v.id)));
  if (version()) $('version-choice').value = version().id;
}
function historyRows(runs) { return runs.map(r => ({...r, model: `${r.modelName} · ${r.modelVersion}`, count:r.rows.length, warnings:r.rows.filter(row=>row.default_label === 1).length, config:`${r.thresholds.basis} ≥ ${r.thresholds.decision.toFixed(4)}`})); }
function renderHistory() {
  const columns = [['name','Tập hồ sơ'],['created','Thời điểm chạy'],['model','Model / phiên bản'],['count','Số hồ sơ'],['warnings','Cảnh báo'],['config','Ngưỡng nhãn']];
  const query = $('history-search').value.toLowerCase();
  table('history-table', columns, historyRows(state.runs.filter(r => `${r.name} ${r.modelName}`.toLowerCase().includes(query))), {action:{label:'Xem kết quả',run:openRun}});
  table('recent-runs', columns.slice(0,5), historyRows(state.runs.filter(r=>r.datasetId===selectedDataset&&r.versionId===version()?.id).slice(0,5)), {action:{label:'Xem chi tiết',run:openRun}});
}
function renderDatasets() {
  const query = $('dataset-search').value.toLowerCase();
  const rows = workingDatasets().filter(d => d.name.toLowerCase().includes(query)).map(d => { const v = d.versions.at(-1), run = state.runs.find(r => r.datasetId === d.id && r.modelHash === model()?.digest); return {...d, count:v.rows.length, revision:v.revision, created:v.created, status: !run ? 'Chưa dự báo' : run.versionId === v.id ? 'Đã dự báo' : 'Cần dự báo lại'}; });
  table('datasets-table', [['name','Tên tập hồ sơ'],['count','Số hồ sơ'],['revision','Phiên bản'],['created','Cập nhật'],['status','Trạng thái model đang chọn']], rows, {action:{label:'Xem hồ sơ',run:r=>{selectDataset(r.id);$('data-title').focus({preventScroll:true});$('data-title').scrollIntoView({block:'center'});}},selected:r=>r.id===selectedDataset});
  const v = version(); renderImputationReport(v?.imputation); $('data-title').textContent = dataset()?.name || 'Nội dung tập hồ sơ';
  $('data-caption').textContent = v ? `Phiên bản ${v.revision} · ${fmt(v.rows.length)} dòng · ${Object.keys(v.rows[0] || {}).length} cột · Chọn dòng để sửa hoặc xóa` : 'Chọn một tập hồ sơ để xem.';
  const data=v?.rows||[],columns=[['ID','Mã hồ sơ'],['AGE','Tuổi'],['LIMIT_BAL','Hạn mức (TWD)'],['PAY_0','Trả nợ gần nhất']];
  if (dataPage >= Math.ceil(data.length / PAGE_SIZE)) dataPage = 0;
  table('data-table', columns, data.slice(dataPage * PAGE_SIZE, (dataPage + 1) * PAGE_SIZE), {select:r=>{selectedCustomer=r.ID;renderDatasets();}, selected:r=>r.ID===selectedCustomer,action:{label:'Xem chi tiết',run:showDatasetProfile}});
  pagination('data-footer', data.length, dataPage, page=>{dataPage=page;renderDatasets();});
  ['predict-dataset','add-customer','rename-dataset','delete-dataset'].forEach(id=>$(id).disabled=!v);
  ['edit-customer','delete-customer'].forEach(id=>$(id).disabled=!v || selectedCustomer==null);
}
function filteredRows() {
  const run = activeRun(); if (!run) return [];
  const q=$('result-search').value, risk=$('risk-filter').value, warning=$('warning-filter').value;
  return run.rows.filter(r => (!q || String(r.ID)===q) && (!risk || r.risk_level===risk) &&
    r.probability>=Number($('min-pd').value)/100 && r.probability<=Number($('max-pd').value)/100 &&
    r.AGE>=Number($('min-age').value) && r.AGE<=Number($('max-age').value) &&
    r.LIMIT_BAL>=Number($('min-limit').value) && r.LIMIT_BAL<=Number($('max-limit').value) &&
    ($('min-delay').value==='' || r.PAY_0===Number($('min-delay').value)) && (warning==='' || r.default_label===Number(warning)));
}
let filterRun;
function renderResults() {
  const run=activeRun();
  if(filterRun!==run){
    filterRun=run;
    $('result-search').replaceChildren(new Option('Tất cả mã hồ sơ',''));
    const options=(run?.rows||[]).map(row=>new Option(String(row.ID),String(row.ID)));
    $('result-search').append(...options);
  }
  for(const id of ['min-pd','max-pd','min-age','max-age','min-limit','max-limit']){
    const output=$(`${id}-value`);
    if(output)output.textContent=fmt($(id).value);
  }
  const rows=filteredRows();
  $('results-caption').textContent=run ? `${run.modelName} · ${run.modelVersion} · ${date(run.created)} · ${fmt(rows.length)}/${fmt(run.rows.length)} hồ sơ sau lọc` : 'Chưa có kết quả phù hợp với dữ liệu, model và ngưỡng hiện tại. Hãy chạy dự báo.';
  const order=['ID','probability','risk_level','default_label','raw_score','AGE','LIMIT_BAL','PAY_0'];
  const titles={ID:'Mã hồ sơ',raw_score:'Điểm thô',probability:'PD hiệu chỉnh',default_label:'Cảnh báo (0/1)',risk_level:'Mức rủi ro',AGE:'Tuổi',LIMIT_BAL:'Hạn mức (TWD)',PAY_0:'Trả nợ gần nhất'};
  if (resultsPage>=Math.ceil(rows.length/PAGE_SIZE)) resultsPage=0;
  table('results-table',order.map(c=>[c,titles[c]||c]),rows.slice(resultsPage*PAGE_SIZE,(resultsPage+1)*PAGE_SIZE),{action:{label:'Xem chi tiết',run:openProfileDetails}});
  pagination('results-footer',rows.length,resultsPage,page=>{resultsPage=page;renderResults();});
}

function stats(rows) { const labelled=rows.filter(r=>r['default.payment.next.month']===0||r['default.payment.next.month']===1); return {rows:rows.length,mean:rows.length?rows.reduce((s,r)=>s+r.probability,0)/rows.length:null,high:rows.filter(r=>r.risk_level==='High').length,warnings:rows.filter(r=>r.default_label===1).length,labelled,actual:labelled.length?labelled.reduce((s,r)=>s+r['default.payment.next.month'],0)/labelled.length:null}; }
let chartTooltip, tooltipKey, tooltipWidth, tooltipHeight;
const rocPoints = new WeakMap();

function chartData(xTitle, x, yTitle, value, series=''){
  return `data-chart-tooltip data-chart-data="${escapeHTML(JSON.stringify({xTitle,x,yTitle,value,series}))}"`;
}

function hideChartTooltip(){
  if(chartTooltip) chartTooltip.hidden=true;
}

function nearestRocPoint(points, x, y){
  let best=points[0], distance=Infinity;
  for(const point of points){
    const squared=(point[0]-x)**2+(point[1]-y)**2;
    if(squared<distance){best=point;distance=squared;}
  }
  return best;
}

function chartHoverData(target,event){
  const data=JSON.parse(target.dataset.chartData);
  if(target.classList.contains('roc-hit')){
    const matrix=target.getScreenCTM();
    if(!matrix) return null;
    const pointer=new DOMPoint(event.clientX,event.clientY).matrixTransform(matrix.inverse());
    if(!rocPoints.has(target)) rocPoints.set(target,target.getAttribute('points').split(' ').map(point=>point.split(',').map(Number)));
    const [x,y]=nearestRocPoint(rocPoints.get(target),pointer.x,pointer.y);
    data.x=pct((x-45)/430);
    data.value=pct((195-y)/170);
  }
  const chart=target.closest('.chart-datum')||target;
  const mark=chart.querySelector('.chart-bar,.roc-line,.shap-value,.status-fill');
  if(!mark) return null;
  const style=getComputedStyle(mark);
  const color=mark.matches('.roc-line')?style.stroke:style.fill;
  return {...data,color};
}

document.addEventListener('pointermove',event=>{
  const target=event.target.closest?.('[data-chart-tooltip]');
  if(!target||event.pointerType==='touch'){
    hideChartTooltip();
    return;
  }
  const data=chartHoverData(target,event);
  if(!data){hideChartTooltip();return;}
  const key=JSON.stringify(data);
  if(!chartTooltip){
    chartTooltip=document.createElement('div');
    chartTooltip.className='chart-tooltip';
    chartTooltip.setAttribute('aria-hidden','true');
    document.body.append(chartTooltip);
  }
  const needsMeasure=chartTooltip.hidden||key!==tooltipKey;
  if(key!==tooltipKey){
    tooltipKey=key;
    chartTooltip.innerHTML=`<div class="chart-tooltip-heading"><span class="chart-tooltip-color"></span>${escapeHTML(data.series||data.yTitle)}</div><div>${escapeHTML(data.xTitle)} <strong>${escapeHTML(data.x)}</strong></div><div>${escapeHTML(data.yTitle)} <strong>${escapeHTML(data.value)}</strong></div>`;
    chartTooltip.firstElementChild.firstElementChild.style.backgroundColor=data.color;
  }
  chartTooltip.hidden=false;
  if(needsMeasure){
    tooltipWidth=chartTooltip.offsetWidth;
    tooltipHeight=chartTooltip.offsetHeight;
  }
  const gap=12, viewport=document.documentElement;
  const x=event.clientX+gap, y=event.clientY+gap;
  chartTooltip.style.left=Math.max(4,Math.min(viewport.clientWidth-tooltipWidth-4,x+tooltipWidth>viewport.clientWidth-4?event.clientX-tooltipWidth-gap:x))+'px';
  chartTooltip.style.top=Math.max(4,Math.min(viewport.clientHeight-tooltipHeight-4,y+tooltipHeight>viewport.clientHeight-4?event.clientY-tooltipHeight-gap:y))+'px';
});

document.addEventListener('pointerout',event=>{
  const target=event.target.closest?.('[data-chart-tooltip]');
  if(target&&!target.contains(event.relatedTarget)) hideChartTooltip();
});
document.addEventListener('scroll',hideChartTooltip,true);
window.addEventListener('resize',hideChartTooltip);
window.addEventListener('blur',hideChartTooltip);

function barChart(title, subtitle, labels, values, {percent=false, colors, axis='Số hồ sơ', xAxis='Danh mục', series, threshold=null}={}) {
  const width=520,height=240,left=42,top=Number.isFinite(threshold)?64:22,bottom=65,plotH=height-top-bottom,plotW=width-left-12,max=percent?1:Math.max(1,Math.ceil(Math.max(...values.filter(Number.isFinite),1)/4))*4;
  let svg=`<svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHTML(title)}">`;
  for(let i=0;i<=4;i++){const y=top+plotH-i*plotH/4;svg+=`<line class="grid" x1="${left}" x2="${width-12}" y1="${y}" y2="${y}"/><text x="${left-7}" y="${y+4}" text-anchor="end">${escapeHTML(percent?`${Math.round(max*i/4*100)}%`:fmt(max*i/4))}</text>`;}
  const band=plotW/Math.max(labels.length,1),barW=Math.min(64,band*.65);
  labels.forEach((label,i)=>{
    const valid=Number.isFinite(values[i]);
    const v=valid?values[i]:0;
    const center=left+band*(i+.5), base=top+plotH, h=v/max*plotH;
    const tooltip=chartData(xAxis,label??'Thiếu danh mục',axis,valid?(percent?pct(v):fmt(v)):'Không có dữ liệu',series?.[i]);
    const labelWidth=String(label).length*6.5;
    const fitted=labelWidth>band-6?` textLength="${band-6}" lengthAdjust="spacingAndGlyphs"`: '';
    svg+=`<g class="chart-datum"><rect class="chart-bar" x="${center-barW/2}" y="${base-h}" width="${barW}" height="${h}" rx="3" fill="${colors?.[i]||'#2563eb'}"/>`;
    svg+=`<rect class="chart-hit" x="${center-barW/2}" y="${base-Math.max(8,h)}" width="${barW}" height="${Math.max(8,h)+4}" fill="transparent" ${tooltip}/></g>`;
    svg+=`<text class="chart-label" x="${center}" y="${base-h-6}" text-anchor="middle"${fitted}>${escapeHTML(label)}</text>`;
  });
  if(Number.isFinite(threshold)){
    const x=left+Math.max(0,Math.min(1,threshold))*plotW,labelX=Math.max(left+72,Math.min(width-84,x));
    svg+=`<g class="threshold-marker"><line x1="${x}" x2="${x}" y1="${top}" y2="${top+plotH}"/><rect x="${labelX-70}" y="22" width="140" height="20" rx="5"/><text x="${labelX}" y="36" text-anchor="middle">Ngưỡng τ = ${pct(threshold)}</text></g>`;
  }
  svg+=`<text class="axis-title" x="${left}" y="12">${escapeHTML(axis)}</text></svg>`;
  return `<article class="panel chart-card"><h3>${escapeHTML(title)}</h3><p class="chart-subtitle">${escapeHTML(subtitle)}</p>${svg}</article>`;
}
function histogram(rows, key, bins) {
  const numbers=rows.map(r=>Number(r[key])).filter(Number.isFinite),lo=Math.min(...numbers),hi=Math.max(...numbers),step=(hi-lo||1)/bins,counts=Array(bins).fill(0);
  numbers.forEach(n=>counts[Math.min(bins-1,Math.floor((n-lo)/step))]++);
  return [counts.map((_,i)=>`${fmt(lo+i*step)}–${fmt(lo+(i+1)*step)}`),counts];
}
function metrics(rows) {
  const known=stats(rows).labelled;if(!known.length)return null;
  let tn=0,fp=0,fn=0,tp=0;known.forEach(r=>{const y=r['default.payment.next.month'];if(y===0&&r.default_label===0)tn++;else if(y===0)fp++;else if(r.default_label===0)fn++;else tp++;});
  const precision=tp/(tp+fp)||0,recall=tp/(tp+fn)||0;
  let auc=null; const positive=tp+fn, negative=tn+fp;
  if(positive&&negative){let rankSum=0;const sorted=known.slice().sort((a,b)=>a.raw_score-b.raw_score);for(let i=0;i<sorted.length;){let j=i+1;while(j<sorted.length&&sorted[j].raw_score===sorted[i].raw_score)j++;const rank=(i+1+j)/2;for(let k=i;k<j;k++)if(sorted[k]['default.payment.next.month']===1)rankSum+=rank;i=j;}auc=(rankSum-positive*(positive+1)/2)/(positive*negative);}
  return {Accuracy:(tp+tn)/known.length,Precision:precision,Recall:recall,F1:2*precision*recall/(precision+recall)||0,AUC:auc,tn,fp,fn,tp,labelled:known.length};
}
function rocChart(rows) {
  const known=stats(rows).labelled,pos=known.filter(r=>r['default.payment.next.month']===1).length,neg=known.length-pos;
  if(!pos||!neg)return '<article class="panel empty"><h3>ROC cần nhãn cả hai lớp</h3><p>Tập hồ sơ cần có cả nhãn thực tế 0 và 1.</p></article>';
  let tp=0,fp=0,points=['45,195'];const sorted=known.slice().sort((a,b)=>b.raw_score-a.raw_score);
  for(let i=0;i<sorted.length;){let j=i;while(j<sorted.length&&sorted[j].raw_score===sorted[i].raw_score){if(sorted[j]['default.payment.next.month']===1)tp++;else fp++;j++;}points.push(`${45+fp/neg*430},${195-tp/pos*170}`);i=j;}
  return `<article class="panel chart-card"><h3>ROC · điểm thô</h3><p class="chart-subtitle">Điểm mô hình trước hiệu chỉnh</p><svg class="chart" viewBox="0 0 520 240" role="img" aria-label="Đường ROC"><path d="M45 25V195H475" fill="none" stroke="#d8e0ed"/><path d="M45 195L475 25" stroke="#b9c8dc" stroke-dasharray="5"/><g class="chart-datum"><polyline class="roc-line" pathLength="100" points="${points.join(' ')}" fill="none" stroke="#2563eb" stroke-width="2.5"/><polyline class="roc-hit" points="${points.join(' ')}" fill="none" stroke="transparent" stroke-width="16" ${chartData('Tỷ lệ dương tính giả (FPR)','', 'Tỷ lệ dương tính thật (TPR)','',`ROC · AUC ${metrics(rows).AUC.toFixed(4)}`)}/></g><text x="45" y="214">0</text><text x="475" y="214">1</text><text x="23" y="30">1</text><text x="180" y="236">False positive rate</text><text x="45" y="13">True positive rate</text></svg></article>`;
}
function statusChart(items){
  const groups=[['Chưa dự báo',0,'#56657d'],['Kết quả còn hiệu lực',0,'#087f83'],['Cần dự báo lại',0,'#9c6807']];
  items.forEach(({d,v,run})=>{const previous=state.runs.some(r=>r.datasetId===d.id&&r.modelHash===model()?.digest);groups[run?1:previous?2:0][1]+=v.rows.length;});
  const total=groups.reduce((sum,[,count])=>sum+count,0);
  const bars=groups.map(([label,count,color])=>{
    const share=total?count/total:0;
    const value=`${fmt(count)} hồ sơ · ${pct(share)}`;
    return `<li class="status-row">
      <div class="status-row-heading"><span>${escapeHTML(label)}</span><span>${value}</span></div>
      <div class="status-track" aria-hidden="true" ${chartData('Trạng thái hồ sơ',label,'Tỷ lệ hồ sơ',`${pct(share)} · ${fmt(count)} hồ sơ`)}><svg class="status-bar" width="100%" height="12"><rect class="status-fill" width="${share*100}%" height="12" rx="6" fill="${color}"/></svg></div>
    </li>`;
  }).join('');
  return `<article class="panel chart-card"><h3>Trạng thái hồ sơ danh mục</h3><p class="chart-subtitle">Phiên bản mới nhất · Model đang chọn</p><ul class="status-bars">${bars}</ul></article>`;
}
function renderOverview() {
  const v=version(),run=activeRun(),latest=v?[{d:dataset(),v,run}]:[];
  const scope=v?`Đang phân tích: ${dataset().name} (${fmt(v.rows.length)})`:'Chưa chọn tập hồ sơ';
  const summary=run?stats(filteredRows()):null;
  $('portfolio-metrics').hidden=!v;
  $('portfolio-metrics').innerHTML=[
    ['Hồ sơ sau lọc',run?summary.rows:v?.rows.length,'overview',''],
    ['PD trung bình',summary?.mean,'performance','teal'],
    ['Hồ sơ rủi ro cao',summary?.high,'shield','danger'],
    ['Hồ sơ cảnh báo',summary?.warnings,'predict','warning']
  ].map(([title,value,ico,tone])=>`<article class="metric ${tone}"><div class="metric-label">${title}</div><div class="metric-icon">${icon(ico)}</div><div class="metric-value">${value==null?'—':ico==='performance'?pct(value):fmt(value)}</div><p class="metric-note">${escapeHTML(scope)}</p></article>`).join('');
  $('dashboard-empty').hidden=!!v;$('dashboard-content').hidden=!run;
  $('dashboard-awaiting').hidden=!v||!!run;
  $('analyze-selected').disabled=!v?.rows.length;
  $('overview-context').textContent=v?`${scope} · Phiên bản ${v.revision}`:'Chưa có dữ liệu';
  if(!run)return;
  const rows=run.rows,s=stats(rows),mode=$('chart-mode').value;
  $('dashboard-caption').textContent=`${dataset()?.name} · ${run.modelName} · ${fmt(rows.length)} dòng · ${Object.keys(rows[0]||{}).length} cột`;
  $('insight-text').textContent=`PD trung bình ${pct(s.mean)}. ${fmt(s.warnings)}/${fmt(rows.length)} hồ sơ cảnh báo theo ngưỡng ${run.thresholds.decision} (${run.thresholds.basis}); ${fmt(s.high)} hồ sơ thuộc nhóm rủi ro cao. ${s.labelled.length?`Tỷ lệ vỡ nợ thực tế ${pct(s.actual)} trên ${fmt(s.labelled.length)} nhãn hợp lệ.`:'Chưa có nhãn thực tế để đánh giá chất lượng dự báo.'}`;
  let charts=[];
  if(mode==='risk'){
    charts.push(barChart('Phân nhóm rủi ro từ PD','risk_level · Số hồ sơ theo nhóm',['Thấp','Trung bình','Cao'],['Low','Medium','High'].map(k=>rows.filter(r=>r.risk_level===k).length),{xAxis:'Nhóm rủi ro',colors:['#087f83','#d49727','#bd2946']}));
    const pd=Array(10).fill(0);rows.forEach(r=>pd[Math.min(9,Math.floor(r.probability*10))]++);
    const pdGroups=pd.map((_,i)=>(i+.5)/10<run.thresholds.low?0:(i+.5)/10>=run.thresholds.high?2:1);
    charts.unshift(barChart('Phân bố xác suất vỡ nợ','PD đã hiệu chỉnh · Màu theo trung điểm khoảng: Thấp / Trung bình / Cao',pd.map((_,i)=>`${i*10}–${(i+1)*10}%`),pd,{xAxis:'Khoảng PD',series:pdGroups.map(group=>['Thấp','Trung bình','Cao'][group]),colors:pdGroups.map(group=>['#087f83','#9c6807','#bb2745'][group]),threshold:run.thresholds.basis==='probability'?run.thresholds.decision:null}));
    if(run.thresholds.basis==='raw'){
      const counts=Array(10).fill(0);rows.forEach(r=>counts[Math.max(0,Math.min(9,Math.floor(r.raw_score*10)))]++);
      charts.push(barChart('Ngưỡng cảnh báo trên điểm mô hình gốc','Ngưỡng điểm gốc khác ngưỡng xác suất đã hiệu chỉnh',counts.map((_,i)=>`${i*10}–${(i+1)*10}%`),counts,{xAxis:'Khoảng điểm mô hình gốc',threshold:run.thresholds.decision}));
    }
    charts.splice(1,0,statusChart(latest));
    const ages=[[18,29],[30,39],[40,49],[50,59],[60,100]],means=ages.map(([lo,hi])=>{const group=rows.filter(r=>r.AGE>=lo&&r.AGE<=hi);return group.length?stats(group).mean:0;});
    charts.push(barChart('PD trung bình theo tuổi','AGE · Nhóm không có hồ sơ hiển thị 0',['18–29','30–39','40–49','50–59','60+'],means,{percent:true,axis:'PD trung bình (%)',xAxis:'Nhóm tuổi',colors:Array(5).fill('#087f83')}));
    charts.push(barChart('Nhãn cảnh báo theo ngưỡng đã lưu','default_label · Cảnh báo hỗ trợ chuyên viên',['Nhãn 0','Nhãn 1'],[rows.length-s.warnings,s.warnings],{xAxis:'Nhãn cảnh báo',colors:['#087f83','#bd2946']}));
  }else if(mode==='data'){
    [['AGE','Phân bố tuổi'],['LIMIT_BAL','Phân bố hạn mức (TWD)']].forEach(([key,title])=>{const [labels,values]=histogram(rows,key,6);charts.push(barChart(title,key,labels,values,{xAxis:key==='AGE'?'Khoảng tuổi':'Khoảng hạn mức (TWD)'}));});
    [['EDUCATION','Trình độ học vấn'],['PAY_0','Trạng thái trả nợ gần nhất']].forEach(([key,title])=>{const counts=new Map();rows.forEach(r=>counts.set(r[key],(counts.get(r[key])||0)+1));const labels=[...counts.keys()].sort((a,b)=>a-b);charts.push(barChart(title,`${key} · Mã UCI`,labels,labels.map(k=>counts.get(k)),{xAxis:title,colors:labels.map(()=>'#087f83')}));});
  }else{
    const m=metrics(rows);
    if(!m){$('charts').innerHTML='<div class="panel empty"><h2>Chưa có nhãn thực tế hợp lệ</h2><p>Thêm cột default.payment.next.month với nhãn 0/1 để đánh giá model.</p></div>';return;}
    charts.push(barChart('Ma trận nhầm lẫn · thực tế / dự báo','0: không vỡ nợ · 1: vỡ nợ',['TN (0/0)','FP (0/1)','FN (1/0)','TP (1/1)'],[m.tn,m.fp,m.fn,m.tp],{xAxis:'Kết quả thực tế / dự báo'}));
    charts.push(rocChart(rows));const keys=['Accuracy','Precision','Recall','F1'];charts.push(barChart('Chỉ số trên nhãn hợp lệ',`${fmt(m.labelled)} hồ sơ có nhãn thực tế`,keys,keys.map(k=>m[k]),{percent:true,axis:'Tỷ lệ (%)',xAxis:'Chỉ số đánh giá'}));
    charts.push(barChart('Phân bố nhãn thực tế','default.payment.next.month',['Không vỡ nợ','Vỡ nợ'],[m.tn+m.fp,m.fn+m.tp],{xAxis:'Nhãn thực tế',colors:['#087f83','#bd2946']}));
  }
  $('charts').innerHTML=charts.join('');
}
function performanceConfig(m){
  const config=configuration();
  return {...config,decision:config.basis==='raw'&&m.name!==model()?.name?m.threshold:config.decision};
}
function performanceRun(m){
  const config=performanceConfig(m);
  return state.runs.find(r=>r.versionId===version()?.id&&r.modelHash===m.digest&&configMatches(r.thresholds,config));
}
function performanceRows(){
  return models.map(m=>{
    const run=performanceRun(m),values=run?metrics(run.rows):null,summary=run?stats(run.rows):null;
    return {name:m.name,status:run?'Đã có kết quả':'Chưa chạy',count:run?.rows.length??'—',
      mean_pd:summary?pct(summary.mean):'—',warnings:summary?.warnings??'—',high:summary?.high??'—',
      decision:performanceConfig(m).decision.toFixed(4),labelled:values?.labelled??0,
      ...Object.fromEntries(['Accuracy','Precision','Recall','F1','AUC'].map(k=>[k,values?.[k]==null?'—':values[k].toFixed(4)])),
      elapsed:run?.elapsedMs==null?'—':`${(run.elapsedMs/1000).toFixed(2)} s`};
  });
}
function renderModels() {
  table('model-table',[['name','Mô hình'],['version','Phiên bản'],['cv_auc','CV AUC gốc'],['test_auc','Test AUC gốc'],['threshold','Ngưỡng điểm thô']],models.map(m=>({...m,cv_auc:m.cv_auc?.toFixed(4),test_auc:m.test_auc?.toFixed(4),threshold:m.threshold.toFixed(4)})));
  const outputs=performanceRows();
  table('comparison-table',[['name','Mô hình'],['status','Trạng thái'],['count','Số hồ sơ'],['mean_pd','PD trung bình'],['warnings','Cảnh báo'],['high','Rủi ro cao'],['decision','Ngưỡng nhãn'],['elapsed','Thời gian dự báo lần đầu']],outputs);
  table('evaluation-table',[['name','Mô hình'],['labelled','Nhãn hợp lệ'],['Accuracy','Accuracy'],['Precision','Precision'],['Recall','Recall'],['F1','F1'],['AUC','AUC']],outputs);
  $('compare-models').disabled=!version()?.rows.length;
  const labelled=version()?.rows.filter(r=>[0,1].includes(r['default.payment.next.month'])).length||0;
  $('performance-context').textContent=version()?`${dataset().name} · Phiên bản ${version().revision} · ${fmt(version().rows.length)} hồ sơ · ${fmt(labelled)} nhãn hợp lệ`:'Chọn hoặc tải tập dữ liệu để đối chiếu ba mô hình.';
  $('performance-note').textContent=labelled?'Các chỉ số được tính trên nhãn thực tế hợp lệ. AUC/ROC cần cả hai lớp 0 và 1. Kết quả đã lưu được sử dụng lại khi dữ liệu, model và ngưỡng không đổi.':'Tệp chưa có nhãn thực tế default.payment.next.month (0/1). Vẫn xem được PD và cảnh báo; Accuracy, Precision, Recall, F1, AUC chưa thể tính nên hiển thị —.';
  const charts=[];
  for(const m of models){
    const run=performanceRun(m);if(!run)continue;
    const summary=stats(run.rows),values=metrics(run.rows);
    charts.push(barChart(`${m.name} · kết quả dự báo`,`${fmt(run.rows.length)} hồ sơ · ${run.thresholds.basis} ≥ ${run.thresholds.decision.toFixed(4)}`,['Thấp','Trung bình','Cao'],['Low','Medium','High'].map(k=>run.rows.filter(r=>r.risk_level===k).length),{xAxis:'Nhóm rủi ro',colors:['#087f83','#d49727','#bd2946']}));
    if(values){
      charts.push(barChart(`${m.name} · ma trận nhầm lẫn`,`${fmt(summary.labelled.length)} nhãn thực tế hợp lệ`,['TN (0/0)','FP (0/1)','FN (1/0)','TP (1/1)'],[values.tn,values.fp,values.fn,values.tp],{xAxis:'Kết quả thực tế / dự báo'}));
      charts.push(`<div><h3>${escapeHTML(m.name)}</h3>${rocChart(run.rows)}</div>`);
    }
  }
  $('performance-charts').innerHTML=charts.join('');
}
function renderAll() { selectors();setModelInfo();renderDatasets();renderResults();renderOverview();renderHistory();if(location.hash==='#models')renderModels(); }

const versionHashes = new WeakMap();
const resolvedHashes = new WeakMap();
function workingDatasets(){
  const seen=new Set();
  return state.datasets.filter(d=>{
    if(d.deleted)return false;
    const hash=resolvedHashes.get(d.versions.at(-1));
    if(!hash)return true;
    if(seen.has(hash))return false;
    seen.add(hash);
    return true;
  });
}
async function indexDatasets(snapshot){
  for(const d of snapshot.datasets){
    if(!d.deleted)await versionHash(d.versions.at(-1));
  }
}
async function datasetHash(rows) {
  const canonical = rows.map(row => JSON.stringify(Object.entries(row)
    .filter(([key, value]) => !key.startsWith('source_') && value != null)
    .sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0))).sort();
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(canonical)));
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2,'0')).join('');
}
function versionHash(v) {
  if(!versionHashes.has(v))versionHashes.set(v,datasetHash(v.rows).then(hash=>{resolvedHashes.set(v,hash);return hash;}));
  return versionHashes.get(v);
}
async function addDataset(name, rows, {save=true,imputation=null}={}) {
  const v={id:crypto.randomUUID(),revision:1,created:new Date().toISOString(),rows,imputation};
  const hash=await versionHash(v);
  for(const existing of workingDatasets()){
    const latest=existing.versions.at(-1);
    if(await versionHash(latest)===hash){
      selectDataset(existing.id,latest.id);
      notify('Nội dung này đã có trong tập ' + existing.name + '.');
      return existing.id;
    }
  }
  const id=crypto.randomUUID();
  state.datasets.unshift({id,name,versions:[v]});
  try{
    if(save)await persist();
    else if(save===false){localGeneration++;if(remoteEnabled)localStorage.setItem(pendingKey(),'1');await saveLocalState();}
  }catch(error){
    state.datasets=state.datasets.filter(d=>d.id!==id);
    throw error;
  }
  selectDataset(id,v.id);
  return id;
}
async function inferRows(rows,selected=model(),config=configuration()) {
  const output=[];
  $('busy-progress').value=0;
  $('busy-detail').textContent=`${selected.name} · Đang xử lý ${fmt(rows.length)} hồ sơ…`;
  for(let i=0;i<rows.length;i+=500){
    const result=await api('predict',{rows:rows.slice(i,i+500),model:selected.name,thresholds:config});
    output.push(...result.rows);
    $('busy-progress').value=Math.round(output.length/rows.length*100);
    $('busy-detail').textContent=`${selected.name} · Đã xử lý ${fmt(output.length)}/${fmt(rows.length)} hồ sơ`;
  }
  return output;
}
async function ensureRun(d,v,m,config){
  const cached=state.runs.find(r=>r.datasetId===d.id&&r.versionId===v.id&&r.modelHash===m.digest&&configMatches(r.thresholds,config));
  if(cached)return {run:cached,cached:true};
  localGeneration++;if(remoteEnabled)localStorage.setItem(pendingKey(),'1');
  const started=performance.now(),rows=await inferRows(v.rows,m,config),id=crypto.randomUUID(),created=new Date().toISOString();
  rows.forEach(r=>{r.run_id=id;r.prediction_time_utc=created;r.dataset_version_id=v.id;});
  const run={id,datasetId:d.id,versionId:v.id,name:d.name,created,modelName:m.name,modelVersion:m.version,modelHash:m.digest,thresholds:{...config},rows,elapsedMs:performance.now()-started};
  state.runs.unshift(run);return {run,cached:false};
}
async function runBatch({go=true}={}){
  if(!version()?.rows.length)throw new Error('Chọn tập hồ sơ có dữ liệu trước khi dự báo.');
  const d=dataset(),v=version(),config=configuration(),m=model();
  if(!m)throw new Error('Chưa tải được mô hình.');
  let run=activeRun();
  if(!run){run=await busy('Đang dự báo tập hồ sơ',async()=>{const result=await ensureRun(d,v,m,config);if(!result.cached)await persist();return result.run;});}
  renderAll();if(go){location.hash='predict';batchTab(true);}notify(`Đã có kết quả ${fmt(run.rows.length)} hồ sơ · ${run.modelName}`);
}
async function upload(event){
  const file=event.target.files?.[0];if(!file)return;event.target.value='';
  if(file.size>4*1024*1024)throw new Error('Tệp tối đa 4 MiB.');
  const data=new FormData();data.append('file',file);
  const result=await busy('Đang kiểm tra và lưu tệp',async()=>{
    const result=await api('import',data);
    await addDataset(file.name,result.rows,{imputation:result.imputation});
    return result;
  });
  location.hash='datasets';
  renderImputationReport(result.imputation);
  const changes=Object.entries(result.normalization||{}).filter(([,count])=>count);
  if(changes.length)notify(`Đã chuẩn hóa mã UCI: ${changes.map(([key,count])=>`${key}: ${count}`).join(', ')}.`);
}
async function loadSample(){
  await busy('Đang tải dữ liệu mẫu UCI',async()=>{
    const result=await api('sample');
    await addDataset('Hồ sơ mẫu UCI',result.rows);
  });
  location.hash='overview';
}
function inputFields(container,prefix,row={}){
  const names={PAY_0:'Trễ hạn tháng gần nhất',LIMIT_BAL:'Hạn mức tín dụng (TWD)',SEX:'Giới tính',EDUCATION:'Trình độ học vấn',MARRIAGE:'Tình trạng hôn nhân',AGE:'Tuổi'};
  const hints={SEX:'1: Nam · 2: Nữ',EDUCATION:'1: Sau ĐH · 2: ĐH · 3: THPT · 4: Khác',MARRIAGE:'1: Đã kết hôn · 2: Độc thân · 3: Khác'};
  const groups=[['Thông tin khách hàng',features.slice(0,5)],['Trạng thái trả nợ 6 tháng · mã −2 đến 8',features.filter(f=>f.startsWith('PAY_')&&!f.includes('AMT'))],['Dư nợ sao kê 6 tháng · TWD',features.filter(f=>f.startsWith('BILL_AMT'))],['Tiền thanh toán 6 tháng · TWD',features.filter(f=>f.startsWith('PAY_AMT'))]];
  let html=`<div class="field-id"><label for="${prefix}-ID">Mã khách hàng (ID)<input id="${prefix}-ID" name="ID" maxlength="128" required placeholder="VD: KH-001" value="${escapeHTML(row.ID||'')}"></label></div>`;
  groups.forEach(([title,keys])=>{html+=`<fieldset><legend>${title}</legend><div class="field-grid">`;keys.forEach(key=>{const categorical=['SEX','EDUCATION','MARRIAGE'].includes(key);let control;if(categorical){const options=key==='SEX'?[[1,'Nam'],[2,'Nữ']]:key==='EDUCATION'?[[1,'Sau đại học'],[2,'Đại học'],[3,'THPT'],[4,'Khác']]:[[1,'Đã kết hôn'],[2,'Độc thân'],[3,'Khác']];control=`<select id="${prefix}-${key}" name="${key}" ${imputableFeatures.includes(key)?'':'required'}><option value="">Chọn…</option>${options.map(([v,t])=>`<option value="${v}" ${Number(row[key])===v?'selected':''}>${v} · ${t}</option>`).join('')}</select>`;}else{const min=key==='AGE'?18:key==='LIMIT_BAL'?1:key.startsWith('PAY_AMT')?0:key.startsWith('PAY_')?-2:null,max=key==='AGE'?100:key==='LIMIT_BAL'?10000000:key.startsWith('PAY_')&&!key.includes('AMT')?8:null;control=`<input id="${prefix}-${key}" name="${key}" type="number" ${imputableFeatures.includes(key)?'':'required'} step="${key==='AGE'||(key.startsWith('PAY_')&&!key.includes('AMT'))?'1':'any'}" ${min!=null?`min="${min}"`:''} ${max!=null?`max="${max}"`:''} value="${escapeHTML(row[key]??'')}" placeholder="${key}">`;}html+=`<label for="${prefix}-${key}">${names[key]||key}${control}<small>${key}${imputableFeatures.includes(key)?' · Có thể để trống: điền từ thống kê train':' · Bắt buộc'}${hints[key]?` · ${hints[key]}`:''}</small></label>`;});html+='</div></fieldset>';});$(container).innerHTML=html;
}
function clearSingle(event) {
  event.preventDefault();
  clearProfileContext();
  $('single-form').querySelectorAll('input, select, textarea').forEach(field=>{
    if(field.dataset)delete field.dataset.imputedValue;
    if(field.type==='checkbox'||field.type==='radio')field.checked=false;
    else field.value='';
    field.setCustomValidity('');field.removeAttribute('aria-invalid');
  });
  invalidateSingle();clearDraft();$('alert').hidden=true;$('alert').textContent='';
  $('result-status').textContent='Chưa dự báo';$('single-ID')?.focus();
  notify('Đã xóa toàn bộ thông tin nhập và kết quả dự báo.');
}
function formRow(prefix){const row={ID:$(`${prefix}-ID`).value.trim()};features.forEach(f=>{const field=$(`${prefix}-${f}`),value=field.value;row[f]=value.trim()===''||field.dataset?.imputedValue===value?null:Number(value);});return row;}
function markImputed(report){
  for(const entry of report?.rows||[])for(const name of entry.fields){
    if(!imputableFeatures.includes(name))continue;
    const field=$(`single-${name}`);field.value=String(entry.values[name]);field.dataset.imputedValue=field.value;
  }
}
function showDatasetProfile(row){
  $('profile-detail-title').textContent=`Hồ sơ ${row.ID}`;
  const keys=['ID',...features];
  if([0,1].includes(row['default.payment.next.month']))keys.push('default.payment.next.month');
  $('profile-detail-content').innerHTML=keys.map(key=>
    `<div><dt>${escapeHTML(key)}</dt><dd>${escapeHTML(row[key]??'—')}</dd></div>`).join('');
  $('profile-detail-dialog').showModal();
}
function clearProfileContext(){profileOrigin=null;$('profile-context').hidden=true;}
async function openProfileDetails(row){
  const inputs=Object.fromEntries(['ID',...features].map(key=>[key,row[key]]));
  profileOrigin={hash:location.hash||'#datasets',batch:!$('batch-panel').hidden,datasetId:selectedDataset,versionId:version()?.id,customerId:row.ID,runId:selectedRunId,dataPage,resultsPage,modelName:model()?.name,thresholds:model()?configuration():null};
  invalidateSingle();inputFields('single-fields','single',inputs);
  const actual=row['default.payment.next.month'];
  $('profile-source').textContent=`Hồ sơ ${row.ID} · ${dataset()?.name||'Tập dữ liệu'} · Phiên bản ${version()?.revision??'—'}${[0,1].includes(actual)?` · Nhãn thực tế nguồn: ${actual}`:''}`;
  $('profile-context').hidden=false;
  location.hash='predict';navigate();batchTab(false);
  await predictSingle({preventDefault(){}});
}
function returnToProfiles(){
  if(!profileOrigin)return;
  const origin=profileOrigin;clearProfileContext();
  selectedDataset=origin.datasetId;selectedVersion=origin.versionId;selectedCustomer=origin.customerId;selectedRunId=origin.runId;dataPage=origin.dataPage;resultsPage=origin.resultsPage;
  if(origin.modelName)$('model-choice').value=origin.modelName;
  if(origin.thresholds){$('decision-basis').value=origin.thresholds.basis;['decision','low','high'].forEach(k=>$(k).value=origin.thresholds[k]*100);}
  location.hash=origin.hash;navigate();batchTab(origin.batch);renderAll();
}
function draftKey(){
  return `creditrisk-single-draft:${currentAccount?.id||'demo'}:${workspaceAccount||currentAccount?.id||localStorage.getItem('creditrisk-workspace-key')||'local'}`;
}
function clearDraft(){try{localStorage.removeItem(draftKey());}catch{}$('draft-status').textContent='';}
function saveDraft(m){
  try{
    localStorage.setItem(draftKey(),JSON.stringify({row:singleInputs,result:singleResult,config:singleConfig,model:m.name,digest:m.digest}));
    $('draft-status').textContent='Đã lưu nháp trên thiết bị này.';
  }catch{$('draft-status').textContent='Trình duyệt không lưu được bản nháp.';}
}
function restoreDraft(){
  try{
    const draft=JSON.parse(localStorage.getItem(draftKey()));
    if(!draft?.row)return;
    inputFields('single-fields','single',draft.row);markImputed(draft.result?.imputation);
    const savedModel=models.find(m=>m.name===draft.model&&m.digest===draft.digest);
    if(!savedModel){$('draft-status').textContent='Đã khôi phục dữ liệu nhập. Hãy dự báo lại với mô hình hiện tại.';return;}
    $('model-choice').value=savedModel.name;
    $('decision-basis').value=draft.config.basis;
    ['decision','low','high'].forEach(k=>$(k).value=draft.config[k]*100);
    ({row:singleInputs,result:singleResult,config:singleConfig}=draft);
    renderSingle(savedModel,singleConfig);
    $('draft-status').textContent='Đã khôi phục bản nháp trên thiết bị này.';
  }catch{clearDraft();}
}
async function predictSingle(event){
  event.preventDefault();
  const generation=singleGeneration,row=formRow('single'),config=configuration(),m=model();
  const result=await busy('Đang chấm điểm hồ sơ',()=>api('predict',{rows:[row],model:m.name,thresholds:config}));
  if(generation!==singleGeneration)return;
  singleResult=result.rows[0];singleResult.imputation=result.imputation;singleInputs={...row};singleConfig=config;
  features.forEach(name=>{singleInputs[name]=singleResult[name]??row[name];});
  markImputed(result.imputation);
  renderSingle(m,config);
  if(!profileOrigin)saveDraft(m);
  await explainSingle();
}
function renderSingle(m,config){
  $('generate-insights').disabled=false;$('ai-insights').replaceChildren();
  if(singleResult.insights)renderInsights(singleResult.insights);
  const r=singleResult,tone=r.risk_level.toLowerCase();$('single-result').className='';$('single-result').innerHTML=`<div class="risk-result ${tone}"><div class="result-label">XÁC SUẤT VỠ NỢ · PD ĐÃ HIỆU CHỈNH</div><div class="pd-number">${pct(r.probability)}</div><span class="tag ${tone}">Rủi ro ${riskNames[r.risk_level].toLowerCase()}</span></div><div class="result-meta"><div><span>Điểm thô</span><strong>${r.raw_score.toFixed(4)}</strong></div><div><span>Ngưỡng nhãn · ${escapeHTML(config.basis)}</span><strong>${config.decision.toFixed(4)}</strong></div><div><span>Nhãn cảnh báo</span><strong>${r.default_label} · ${r.default_label?'Cảnh báo':'Không cảnh báo'}</strong></div><div><span>Mô hình</span><strong>${escapeHTML(m.name)}</strong></div></div><p class="fine-print">Nhóm rủi ro dựa trên PD (Thấp dưới ${pct(config.low)}, Trung bình từ ${pct(config.low)} đến dưới ${pct(config.high)}, Cao từ ${pct(config.high)}). Nhãn cảnh báo dùng ngưỡng riêng, nên hồ sơ nhóm Trung bình vẫn có thể được cảnh báo.</p>`;
  if(r.imputation?.filled_cells)$('single-result').innerHTML+=imputationSummary(r.imputation);
  $('result-status').textContent=r.default_label?'Nhãn 1 · Cảnh báo':'Nhãn 0';$('result-status').className=`tag ${tone}`;['save-single','export-single','explain-single','transfer-single'].forEach(id=>$(id).disabled=false);$('explanation').hidden=true;
}
async function saveSingle(){
  if(!singleResult)throw new Error('Chạy dự báo trước khi lưu.');
  const row={...singleInputs},result=singleResult,config={...singleConfig},m=model();
  await busy('Đang lưu hồ sơ chính thức',async()=>{
    const previousDatasets=state.datasets.slice();
    const id=await addDataset(`Hồ sơ ${row.ID}`,[row],{save:null,imputation:result.imputation});
    const v=version(),d=dataset();
    if(state.runs.some(r=>r.datasetId===id&&r.versionId===v.id&&r.modelHash===m.digest&&configMatches(r.thresholds,config)))return;
    const created=new Date().toISOString(),runId=crypto.randomUUID();
    const run={id:runId,datasetId:id,versionId:v.id,name:d.name,created,modelName:m.name,modelVersion:m.version,modelHash:m.digest,thresholds:config,rows:[{...result,run_id:runId,prediction_time_utc:created,dataset_version_id:v.id}]};
    state.runs.unshift(run);
    try{await persist();}catch(error){state.runs=state.runs.filter(r=>r!==run);state.datasets=previousDatasets;selectDataset(previousDatasets.find(d=>!d.deleted)?.id);throw error;}
  });
  renderAll();$('save-single').disabled=true;notify('Đã lưu hồ sơ và kết quả vào tập chính thức.');
}
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);}
async function exportRows(rows,config){if(!rows.length)throw new Error('Chưa có kết quả để xuất. Hãy chạy dự báo hoặc kiểm tra bộ lọc.');const m=model();if(rows.some(r=>r.model_sha256!==m.digest))throw new Error('Kết quả thuộc model khác. Hãy chọn lại model hoặc chạy dự báo.');const blob=await busy('Đang tạo báo cáo Excel',()=>api('export',{rows,model:m.name,thresholds:config}));download(blob,`ket_qua_${({'Random Forest':'RF','Logistic Regression':'LR','XGBoost':'XGb'})[m.name]||'model'}.xlsx`);notify('Đã xuất dữ liệu, insight và dashboard vào Excel.');}
async function exportCurrent(){const onBatch=location.hash==='#predict'&&!$('batch-panel').hidden,run=activeRun();await exportRows(onBatch?filteredRows():run?.rows||[],run?.thresholds||configuration());}
function openRun(run){selectedRunId=run.id;selectedDataset=run.datasetId;selectedVersion=run.versionId;selectedCustomer=null;$('model-choice').value=run.modelName;setModelInfo();$('decision-basis').value=run.thresholds.basis;['decision','low','high'].forEach(k=>$(k).value=run.thresholds[k]*100);resetFilters();invalidateSingle();renderAll();batchTab(true);location.hash='predict';}
function resetFilters(){['result-search','risk-filter','warning-filter'].forEach(id=>$(id).value='');const values={'min-pd':0,'max-pd':100,'min-age':18,'max-age':100,'min-limit':0,'max-limit':10000000,'min-delay':''};Object.entries(values).forEach(([k,v])=>$(k).value=v);resultsPage=0;renderResults();}
function openEditor(edit){if(!version())throw new Error('Chọn tập hồ sơ trước.');const row=edit?version().rows.find(r=>r.ID===selectedCustomer):{};if(edit&&!row)throw new Error('Chọn một dòng để chỉnh sửa.');editId=edit?row.ID:null;inputFields('edit-fields','edit',row);$('edit-title').textContent=edit?'Cập nhật hồ sơ':'Bổ sung hồ sơ';$('edit-copy').checked=false;$('edit-copy-name').value='';$('edit-dialog').showModal();}
async function revise(rows,copyName){if(!dataset())throw new Error('Chưa chọn tập hồ sơ.');if(copyName){await addDataset(copyName,rows);return;}const d=dataset(),v={id:crypto.randomUUID(),revision:d.versions.at(-1).revision+1,created:new Date().toISOString(),rows};await versionHash(v);d.versions.push(v);await persist();selectDataset(d.id,v.id);}
async function saveEdit(event){event.preventDefault();const row=formRow('edit'),existing=version().rows.find(r=>r.ID===row.ID);if(existing&&row.ID!==editId&&!confirm(`ID ${row.ID} đã tồn tại. Cập nhật hồ sơ này?`))return;const copy=$('edit-copy').checked,copyName=$('edit-copy-name').value.trim();if(copy&&!copyName)throw new Error('Nhập tên bản sao.');const valid=await busy('Đang kiểm tra hồ sơ',()=>api('predict',{rows:[row],model:model().name,thresholds:configuration()}));const canonical=Object.fromEntries(Object.entries(valid.rows[0]).filter(([k])=>k==='ID'||features.includes(k)));const rows=version().rows.filter(r=>r.ID!==editId&&r.ID!==row.ID).map(r=>({...r}));rows.push({...existing,...canonical});await revise(rows,copy?copyName:null);$('edit-dialog').close();notify('Đã lưu phiên bản mới; cần chạy dự báo lại.');}
async function deleteCustomer(){if(selectedCustomer==null)throw new Error('Chọn dòng cần xóa.');if(!confirm(`Xóa hồ sơ ${selectedCustomer} khỏi phiên bản mới? Lịch sử và phiên bản cũ vẫn được giữ.`))return;await revise(version().rows.filter(r=>r.ID!==selectedCustomer));notify('Đã tạo phiên bản mới; kết quả cũ vẫn được giữ.');}

function transferSingle(){
  if(!singleInputs)throw new Error('Chạy dự báo đơn lẻ trước.');
  if(!workingDatasets().length)throw new Error('Tạo hoặc tải lên tập dữ liệu hàng loạt trước.');
  $('transfer-target').replaceChildren(...workingDatasets().map(d=>new Option(`${d.name} · ${d.versions.at(-1).rows.length} hồ sơ`,d.id)));
  $('transfer-target').value=state.datasets.find(d=>d.id===selectedDataset&&!d.deleted)?.id||state.datasets.find(d=>!d.deleted).id;
  $('transfer-copy').checked=false;$('transfer-copy-name').value='';
  $('transfer-dialog').showModal();
}
async function confirmTransfer(event){
  event.preventDefault();
  const target=state.datasets.find(d=>d.id===$('transfer-target').value);
  if(!target||target.deleted||!singleInputs)throw new Error('Chọn tập dữ liệu nhận hồ sơ.');
  const latest=target.versions.at(-1);
  if(latest.rows.some(r=>String(r.ID)===String(singleInputs.ID)))throw new Error('ID đã tồn tại trong tập dữ liệu nhận. Hãy đổi ID hoặc sửa hồ sơ ở Quản lý dữ liệu.');
  if(latest.rows.length>=30000)throw new Error('Tập dữ liệu đã đạt giới hạn 30.000 hồ sơ.');
  const copy=$('transfer-copy').checked,name=$('transfer-copy-name').value.trim();
  if(copy&&!name)throw new Error('Nhập tên bản sao.');
  const rows=[...structuredClone(latest.rows),structuredClone(singleInputs)];
  if(copy)await addDataset(name,rows);
  else{selectedDataset=target.id;selectedVersion=latest.id;await revise(rows);}
  $('transfer-dialog').close();notify('Đã chuyển đầu vào. Hồ sơ chưa có điểm số trong tập nhận. Hãy chạy dự báo riêng cho tập này.');
}
async function renameDataset(){
  const d=dataset();if(!d)throw new Error('Chọn tập dữ liệu trước.');
  const name=prompt('Tên tập dữ liệu:',d.name)?.trim();if(!name)return;
  if(name.length>255)throw new Error('Tên tối đa 255 ký tự.');
  d.name=name;await persist();renderAll();
}
async function deleteDataset(){
  const d=dataset();if(!d)throw new Error('Chọn tập dữ liệu trước.');
  if(!confirm(`Xóa tập dữ liệu ${d.name}? Kết quả lịch sử vẫn được giữ và có thể mở lại.`))return;
  d.deleted=true;await persist();selectDataset(state.datasets.find(item=>!item.deleted)?.id);notify('Đã xóa tập dữ liệu khỏi danh sách làm việc.');
}
function featureLabel(feature){
  const name=feature.split('__').at(-1);
  const labels={LIMIT_BAL:'Hạn mức tín dụng',AGE:'Tuổi',SEX:'Giới tính',EDUCATION:'Trình độ học vấn',MARRIAGE:'Tình trạng hôn nhân',PAY_0:'Trạng thái trả nợ tháng gần nhất',PAY_1:'Trạng thái trả nợ tháng gần nhất',DELAY_MONTHS_COUNT:'Số tháng có trả nợ trễ',MAX_DELAY_MONTHS:'Mức trễ hạn lớn nhất',AVG_BILL_AMT:'Dư nợ sao kê trung bình 6 tháng',BILL_TREND:'Chênh lệch dư nợ tháng gần nhất so với trung bình'};
  if(labels[name])return labels[name];
  const match=name.match(/^(UTILIZATION_|PAY_RATIO_|BILL_AMT|PAY_AMT|PAY_)([1-6])$/);
  if(match)return `${({'UTILIZATION_':'Tỷ lệ sử dụng hạn mức tháng','PAY_RATIO_':'Tỷ lệ thanh toán so với dư nợ kỳ trước · tháng','BILL_AMT':'Dư nợ sao kê tháng','PAY_AMT':'Tiền thanh toán tháng','PAY_':'Trạng thái trả nợ tháng'})[match[1]]} ${match[2]}`;
  return name;
}
function imputationSummary(report){
  const fields=[...new Set(report.rows.flatMap(row=>row.fields))];
  return `<div class="notice imputation-summary"><p>Đã điền ${fmt(report.filled_cells)} giá trị thiếu trong ${fmt(report.filled_rows)} hồ sơ từ thống kê tập train (median/mode): ${fields.map(name=>escapeHTML(`${featureLabel(name)} (${name})`)).join(', ')}. Đây là giá trị ước lượng, cần xác minh trước khi ra quyết định.</p></div>`;
}
function renderImputationReport(report){
  displayedImputationReport=report;
  const box=$('dataset-imputation');box.hidden=!report?.filled_cells;
  $('download-imputation-report').hidden=box.hidden;
  if(box.hidden){box.replaceChildren();return;}
  box.innerHTML=imputationSummary(report)+`<details><summary>Xem các giá trị đã điền (${fmt(report.filled_rows)} hồ sơ)</summary><p>Hiển thị tối đa 25 hồ sơ; tải báo cáo JSON để xem đầy đủ.</p>${report.rows.slice(0,25).map(row=>`<p><strong>${escapeHTML(row.ID)}</strong>: ${row.fields.map(name=>`${escapeHTML(name)} = ${escapeHTML(row.values[name])}`).join(', ')}</p>`).join('')}</details>`;
}
async function explainSingle(){
  if(!singleInputs)return;
  const generation=singleGeneration,inputs=singleInputs,m=model(),box=$('explanation');
  box.hidden=false;
  box.textContent='Đang tải giải thích SHAP…';
  $('explain-single').disabled=true;
  $('explain-single').hidden=true;
  try{
    const result=await api('explain',{rows:[inputs],model:m.name});
    if(generation!==singleGeneration||inputs!==singleInputs||m!==model())return;
    const max=Math.max(...result.rows.filter(r=>Number.isFinite(r.contribution)).map(r=>Math.abs(r.contribution)),.00001);
    box.innerHTML=`<h3>Vì sao mô hình đưa ra kết quả này?</h3><p>${escapeHTML(result.scale)} · ${result.rows.length} yếu tố có độ lớn đóng góp cao nhất. Đỏ (+): tăng điểm rủi ro; xanh (−): giảm điểm. Các giá trị SHAP giải thích điểm mô hình trước hiệu chỉnh, không phải phần trăm PD và không chứng minh quan hệ nhân quả.</p>${singleResult?.imputation?.filled_cells?'<p>Hồ sơ có dữ liệu được điền từ tập train. Giải thích này dựa trên đầu vào sau khi điền.</p>':''}${result.rows.map(r=>{const valid=Number.isFinite(r.contribution);const width=valid?Math.abs(r.contribution)/max*50:0;const value=valid?`${r.contribution>=0?'+':''}${r.contribution.toFixed(4)}`:'Không có dữ liệu';return `<div class="contribution ${r.contribution<0?'negative':'positive'}"><div><span>${escapeHTML(featureLabel(r.feature))}<small>${escapeHTML(r.feature)}</small></span><strong><small>${valid?(r.contribution>=0?'Tăng điểm':'Giảm điểm'):value}</small></strong></div><svg class="shap-bar" viewBox="0 0 100 8" preserveAspectRatio="none" role="img" aria-label="Đóng góp SHAP: ${value}" ${chartData('Đặc trưng',featureLabel(r.feature),'Đóng góp SHAP',value,valid?(r.contribution<0?'Giảm điểm':'Tăng điểm'):'')}><rect class="shap-track" width="100" height="8" rx="2"/><rect class="shap-value" x="${r.contribution<0?50-width:50}" width="${width}" height="8"/><path class="shap-zero" d="M50 0V8"/></svg></div>`;}).join('')}`;
  }catch{
    if(generation!==singleGeneration||inputs!==singleInputs||m!==model())return;
    box.textContent='Chưa tải được giải thích SHAP. Kết quả dự báo đã có.';
    $('explain-single').disabled=false;
    $('explain-single').hidden=false;
  }
}
function renderInsights(result){
  const box=$('ai-insights');
  if(result.status!=='ok'){box.textContent=result.message;return;}
  box.innerHTML=`<h3>Insight hỗ trợ chuyên viên</h3><p class="fine-print">Bản diễn giải do ${escapeHTML(result.provider)} · ${escapeHTML(result.model)} tạo. Cần chuyên viên kiểm chứng; không phải quyết định phê duyệt hoặc từ chối tín dụng.</p>${result.insights.map(item=>`<article class="ai-insight"><p>${escapeHTML(item.text)}</p><small>Bằng chứng: ${item.features.map(name=>{const evidence=result.evidence.find(row=>row.feature===name);return escapeHTML(`${featureLabel(name)} = ${fmt(evidence.value)} · SHAP ${evidence.contribution>=0?'+':''}${evidence.contribution.toFixed(4)}`);}).join('; ')}</small></article>`).join('')}<h4>Gợi ý bước kiểm tra tiếp</h4><ul>${result.checks.map(check=>`<li>${escapeHTML(check.text)}</li>`).join('')}</ul>`;
}
async function generateInsights(){
  if(!singleResult||!singleInputs)return;
  if(singleResult.insights?.status==='ok'){renderInsights(singleResult.insights);return;}
  const generation=singleGeneration,snapshot=singleResult,m=model(),row={...singleInputs},config={...singleConfig};
  for(const entry of snapshot.imputation?.rows||[])for(const name of entry.fields)if(imputableFeatures.includes(name))row[name]=null;
  const button=$('generate-insights'),box=$('ai-insights');button.disabled=true;box.textContent='Đang phân tích bằng chứng SHAP bằng AI…';
  try{
    const result=await api('insights',{rows:[row],model:m.name,thresholds:config});
    if(generation!==singleGeneration||snapshot!==singleResult)return;
    renderInsights(result);
    if(result.status==='ok'){snapshot.insights=result;if(!profileOrigin)saveDraft(m);}
  }catch{
    if(generation===singleGeneration&&snapshot===singleResult)box.textContent='Chưa tải được insight AI. Kết quả dự báo và SHAP vẫn sử dụng được.';
  }finally{if(generation===singleGeneration&&snapshot===singleResult)button.disabled=false;}
}
$('generate-insights').addEventListener('click',guarded(generateInsights));
async function compareModels(){
  if(!version()?.rows.length)throw new Error('Chọn tập hồ sơ trước.');
  const d=dataset(),v=version();
  await busy('Đang đối chiếu mô hình',async()=>{
    let changed=false;
    try{
      for(const m of models){
        const result=await ensureRun(d,v,m,performanceConfig(m));
        changed=changed||!result.cached;
        renderModels();
      }
    }finally{
      if(changed){$('busy-detail').textContent='Đang lưu kết quả và lịch sử…';await persist();}
    }
  });
  renderModels();notify('Đã có đầu ra của các mô hình; kết quả và lịch sử được giữ riêng.');
}
function backup(){download(new Blob([JSON.stringify({format:'creditrisk-ai-backup-v1',...state})],{type:'application/json'}),`creditrisk_sao_luu_${new Date().toISOString().slice(0,10)}.json`);}
async function restore(event){const file=event.target.files?.[0];if(!file)return;event.target.value='';if(file.size>100*1024*1024)throw new Error('Bản sao lưu tối đa 100 MB.');const data=JSON.parse(await file.text());if(data.format!=='creditrisk-ai-backup-v1'||!Array.isArray(data.datasets)||!Array.isArray(data.runs)||data.datasets.some(d=>!d.id||typeof d.name!=='string'||!Array.isArray(d.versions)||!d.versions.length||d.versions.some(v=>!v.id||!Array.isArray(v.rows)||v.rows.length>30000))||data.runs.some(r=>!r.id||!Array.isArray(r.rows)||!r.thresholds))throw new Error('Tệp không đúng định dạng sao lưu CreditRisk AI.');if(!confirm('Khôi phục sẽ thay thế dữ liệu đang lưu trên trình duyệt này. Tiếp tục?'))return;const snapshot={datasets:data.datasets,runs:data.runs};await indexDatasets(snapshot);state=snapshot;await persist();selectDataset(workingDatasets()[0]?.id);notify('Đã khôi phục dữ liệu và lịch sử.');}

$('close-profile-detail').addEventListener('click',()=>$('profile-detail-dialog').close());
document.querySelectorAll('[data-action="upload"]').forEach(el=>el.addEventListener('click',()=>$('upload').click()));
document.querySelectorAll('[data-action="export"]').forEach(el=>el.addEventListener('click',guarded(exportCurrent)));
document.querySelectorAll('[data-action="sample"]').forEach(el=>el.addEventListener('click',guarded(loadSample)));
$('sample-top').addEventListener('click',guarded(loadSample));$('upload').addEventListener('change',guarded(upload));
$('back-to-profiles').addEventListener('click',guarded(returnToProfiles));
$('single-form').addEventListener('submit',guarded(predictSingle));$('single-form').addEventListener('input',event=>{if(event.target.dataset)delete event.target.dataset.imputedValue;invalidateSingle();if(!profileOrigin)clearDraft();});$('single-form').addEventListener('reset',clearSingle);
$('fill-sample').addEventListener('click',guarded(async()=>{const sample=await api('sample');clearProfileContext();inputFields('single-fields','single',sample.rows[0]);invalidateSingle();clearDraft();}));
$('save-single').addEventListener('click',guarded(saveSingle));$('export-single').addEventListener('click',guarded(()=>exportRows([singleResult],singleConfig)));$('explain-single').addEventListener('click',guarded(explainSingle));$('transfer-single').addEventListener('click',guarded(transferSingle));
$('download-imputation-report').addEventListener('click',()=>{const report=displayedImputationReport;if(report)download(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}),'bao_cao_dien_thieu.json');});
document.querySelectorAll('[data-page="predict"]').forEach(link=>link.addEventListener('click',()=>{batchTab(false);if(location.hash==='#predict')navigate();}));
document.querySelectorAll('[data-predict-mode]').forEach(link=>link.addEventListener('click',()=>{batchTab(link.dataset.predictMode==='batch');}));
$('tab-single').addEventListener('click',()=>batchTab(false));$('tab-batch').addEventListener('click',()=>batchTab(true));
document.querySelectorAll('.dataset-select').forEach(el=>el.addEventListener('change',()=>selectDataset(el.value)));
$('version-choice').addEventListener('change',()=>selectDataset(selectedDataset,$('version-choice').value));
$('model-choice').addEventListener('change',guarded(async()=>{
  const hadSingle=singleInputs!==null;
  selectedRunId=null;$('decision').value=$('decision-basis').value==='raw'?model().threshold*100:50;
  invalidateSingle();renderAll();
  if(hadSingle)await predictSingle({preventDefault(){}});

}));
['decision','low','high','decision-basis'].forEach(id=>$(id).addEventListener('change',guarded(()=>{selectedRunId=null;if(id==='decision-basis')$('decision').value=$('decision-basis').value==='raw'?model().threshold*100:50;configuration();invalidateSingle();if(!profileOrigin)clearDraft();renderAll();})));
['run-batch','predict-dataset'].forEach(id=>$(id).addEventListener('click',guarded(()=>runBatch())));$('analyze-selected').addEventListener('click',guarded(()=>runBatch({go:false})));
['result-search','risk-filter','warning-filter','min-pd','max-pd','min-age','max-age','min-limit','max-limit','min-delay'].forEach(id=>$(id).addEventListener('input',()=>{if(/^(min|max)-(pd|age|limit)$/.test(id)){const peer=id.startsWith('min-')?id.replace('min-','max-'):id.replace('max-','min-');if(id.startsWith('min-')?Number($(id).value)>Number($(peer).value):Number($(id).value)<Number($(peer).value))$(peer).value=$(id).value;}resultsPage=0;renderResults();}));
$('reset-thresholds').addEventListener('click',()=>{
  selectedRunId=null;$('decision-basis').value='raw';$('decision').value=model().threshold*100;
  $('low').value=20;$('high').value=50;
  invalidateSingle();if(!profileOrigin)clearDraft();renderAll();
});
$('reset-filters').addEventListener('click',resetFilters);$('chart-mode').addEventListener('change',renderOverview);$('dataset-search').addEventListener('input',renderDatasets);$('history-search').addEventListener('input',renderHistory);
$('add-customer').addEventListener('click',guarded(()=>openEditor(false)));$('edit-customer').addEventListener('click',guarded(()=>openEditor(true)));$('edit-form').addEventListener('submit',guarded(saveEdit));['close-edit','cancel-edit'].forEach(id=>$(id).addEventListener('click',()=>$('edit-dialog').close()));
$('transfer-form').addEventListener('submit',guarded(confirmTransfer));
['close-transfer','cancel-transfer'].forEach(id=>$(id).addEventListener('click',()=>$('transfer-dialog').close()));
$('rename-dataset').addEventListener('click',guarded(renameDataset));$('delete-dataset').addEventListener('click',guarded(deleteDataset));
$('delete-customer').addEventListener('click',guarded(deleteCustomer));$('goto-models').addEventListener('click',()=>location.hash='models');$('compare-models').addEventListener('click',guarded(compareModels));
['backup','history-backup'].forEach(id=>$(id).addEventListener('click',backup));$('restore').addEventListener('click',()=>$('restore-file').click());$('restore-file').addEventListener('change',guarded(restore));
$('menu-toggle').addEventListener('click',()=>{const open=$('sidebar').classList.toggle('open');$('menu-toggle').setAttribute('aria-expanded',String(open));});
document.addEventListener('keydown',event=>{if(event.key==='Escape'){$('sidebar').classList.remove('open');$('menu-toggle').setAttribute('aria-expanded','false');}});
window.addEventListener('hashchange',navigate);
window.addEventListener('unhandledrejection',event=>{showError(event.reason);event.preventDefault();});

$('workspace-settings').addEventListener('click',()=>{
  $('workspace-key').value=workspaceKey();
  $('storage-description').textContent=remoteEnabled?'MongoDB Atlas đã được cấu hình. Dữ liệu được lưu cục bộ và đồng bộ vào kho riêng theo mã.':'Hiện lưu riêng trong trình duyệt. Cấu hình MONGODB_URI trên Vercel để bật đồng bộ MongoDB Atlas.';
  $('storage-dialog').showModal();
});
$('retry-sync').addEventListener('click',guarded(connectCloud));
$('backup-pending').addEventListener('click',backup);
$('open-cloud-version').addEventListener('click',guarded(openCloudVersion));
$('close-storage').addEventListener('click',()=>$('storage-dialog').close());
$('copy-workspace-key').addEventListener('click',guarded(async()=>{await navigator.clipboard.writeText($('workspace-key').value);notify('Đã sao chép mã kho. Giữ riêng mã này.');}));
$('storage-form').addEventListener('submit',guarded(async event=>{
  event.preventDefault();const key=$('workspace-key').value.trim();if(!/^[0-9a-f]{64}$/.test(key))throw new Error('Mã kho phải gồm 64 ký tự 0–9, a–f.');
  if(!remoteEnabled)throw new Error('Chưa có kết nối MongoDB Atlas. Dữ liệu vẫn lưu trong trình duyệt hiện tại.');
  const result=await api('workspace',undefined,{headers:{Authorization:`Bearer ${key}`}});
  if(!confirm('Mở kho này sẽ thay dữ liệu cục bộ hiện tại. Bạn đã sao lưu JSON chưa?'))return;
  localStorage.setItem('creditrisk-workspace-key',key);localStorage.removeItem('creditrisk-cloud-pending');cloudRevision=result.revision;
  if(result.state)await indexDatasets(result.state);
  clearDraft();invalidateSingle();inputFields('single-fields','single');
  state=result.state||{datasets:[],runs:[]};await persist();selectDataset(workingDatasets()[0]?.id);$('storage-dialog').close();notify('Đã mở kho dữ liệu riêng.');
}));

async function initialize(){
  navigate();
  const auth=await api('auth/session');currentAccount=auth.user;csrfToken=auth.csrf;
  if(auth.enabled&&!currentAccount){location.assign('/login');return;}
  if(currentAccount?.must_change_password){location.assign('/change-password');return;}
  if(currentAccount){
    $('sign-in-link').hidden=true;
    workspaceAccount=currentAccount.role==='admin'?new URLSearchParams(location.search).get('account_id'):null;
    $('workspace-settings').hidden=true;
    const banner=$('account-banner');banner.hidden=false;
    const name=document.createElement('strong');name.textContent=`${currentAccount.name} · ${currentAccount.role==='admin'?'Quản trị viên':'Chuyên viên phân tích'}`;banner.append(name);
    if(workspaceAccount){const scope=document.createElement('span');scope.textContent='Đang quản lý dữ liệu: '+workspaceAccount;banner.append(scope);}
    if(currentAccount.role==='admin'){const link=document.createElement('a');link.href='/admin';link.className='button secondary';link.textContent='Admin Console';banner.append(link);}
    const change=document.createElement('a');change.href='/change-password';change.className='button secondary';change.textContent='Đổi mật khẩu';banner.append(change);
    const logout=$('logout');logout.hidden=false;logout.addEventListener('click',guarded(async()=>{await api('auth/logout',{});location.assign('/login');}));
  }
  await openStorage();const [meta,health]=await Promise.all([api('models'),api('health')]);models=meta.models;features=meta.features;if(!models.length)throw new Error('Chưa tải được model thật. Kiểm tra bước build trên Vercel.');$('model-choice').replaceChildren(...models.map(m=>new Option(m.name,m.name)));if(meta.default_model)$('model-choice').value=meta.default_model;$('model-choice').disabled=false;$('decision').value=model().threshold*100;$('connection').innerHTML='<span class="status-dot"></span> API dự báo đã kết nối';$('app-version').textContent=`v${health.version} · Dữ liệu riêng trên trình duyệt`;remoteEnabled=health.storage==='mongodb';inputFields('single-fields','single');restoreDraft();selectedDataset=state.datasets.find(d=>!d.deleted)?.id;selectedVersion=dataset()?.versions.at(-1)?.id;renderAll();if(remoteEnabled)void connectCloud();
  if(singleResult&&location.hash==='#predict')void explainSingle();
}
document.querySelectorAll('[role="tab"]').forEach(tab=>tab.addEventListener('keydown',event=>{
  const tabs=[...tab.closest('[role="tablist"]').querySelectorAll('[role="tab"]:not([hidden])')];let index=tabs.indexOf(tab);
  if(event.key==='ArrowRight')index=(index+1)%tabs.length;
  else if(event.key==='ArrowLeft')index=(index+tabs.length-1)%tabs.length;
  else if(event.key==='Home')index=0;
  else if(event.key==='End')index=tabs.length-1;else return;
  event.preventDefault();tabs[index].click();tabs[index].focus();
}));
document.querySelectorAll('.more-actions').forEach(details=>{
  details.addEventListener('keydown',event=>{if(event.key==='Escape'){details.open=false;details.querySelector('summary').focus();}});
  details.addEventListener('click',event=>{if(event.target.closest('button:not(:disabled)'))details.open=false;});
  document.addEventListener('click',event=>{if(!details.contains(event.target))details.open=false;});
});

initialize().catch(error=>{$('connection').textContent='Chưa kết nối được API';showError(error);});
