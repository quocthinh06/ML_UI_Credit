'use strict';

const $ = id => document.getElementById(id);
const fmt = n => Number(n || 0).toLocaleString('vi-VN', {maximumFractionDigits: 2});
const pct = n => n == null || !Number.isFinite(Number(n)) ? '—' : `${(Number(n) * 100).toFixed(2)}%`;
const date = s => new Date(s).toLocaleString('vi-VN');
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
let resultsPage = 0, dataPage = 0, comparison = [], toastTimer;
let remoteEnabled = false, cloudRevision = 0;
let currentAccount = null, csrfToken = null, workspaceAccount = null;
const PAGE_SIZE = 25;

function cloudPath() { return workspaceAccount ? 'workspace?account_id='+encodeURIComponent(workspaceAccount) : 'workspace'; }
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
  try { return await fn(); } finally { $('busy').hidden = true; document.querySelector('.workspace').inert = false; $('sidebar').inert = false; }
}
async function api(path, data, options = {}) {
  let headers = csrfToken ? {'X-CSRF-Token':csrfToken} : {}, body;
  if (data instanceof FormData) body = data;
  else if (data !== undefined) {
    headers['Content-Type'] = 'application/json'; body = JSON.stringify(data);
    if (body.length > 100000 && 'CompressionStream' in window) {
      body = await new Response(new Blob([body]).stream().pipeThrough(new CompressionStream('gzip'))).blob();
      headers['Content-Encoding'] = 'gzip';
    }
  }
  const response = await fetch(`/api/${path}`, {method: data === undefined ? 'GET' : 'POST', body,
    ...options, headers:{...headers,...options.headers}});
  if (!response.ok) {
    if (response.status === 401 && currentAccount) { location.assign('/login'); throw new Error('Phiên đăng nhập đã hết hạn.'); }
    const type = response.headers.get('Content-Type') || '';
    const error = type.includes('json') ? (await response.json()).error : `Máy chủ trả lỗi ${response.status}. Vui lòng thử lại.`;
    throw new Error(error || 'Không thể xử lý yêu cầu.');
  }
  return response.headers.get('Content-Type')?.includes('json') ? response.json() : response.blob();
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
  if (saved) state = saved;
}
async function persist() {
  try {
    await new Promise((resolve, reject) => {
      const tx = database.transaction('app', 'readwrite'); tx.objectStore('app').put(state, 'state');
      tx.oncomplete = resolve; tx.onerror = () => reject(tx.error); tx.onabort = () => reject(tx.error);
    });
  } catch { throw new Error('Không lưu được dữ liệu vào trình duyệt. Có thể đã hết dung lượng; hãy sao lưu JSON và thử lại.'); }
  if (remoteEnabled) {
    localStorage.setItem(pendingKey(), '1');
    try {
      const result = await api(cloudPath(), {state, revision:cloudRevision},
        {method:'PUT',headers:{Authorization:`Bearer ${workspaceKey()}`}});
      cloudRevision = result.revision; localStorage.removeItem(pendingKey());
      $('connection').innerHTML = '<span class="status-dot"></span> API & MongoDB đã đồng bộ';
    } catch(error) { $('connection').textContent = 'Đã lưu cục bộ · chưa đồng bộ'; showError(error); }
  }
}

async function connectCloud() {
  const result = await api(cloudPath(), undefined, {headers:{Authorization:`Bearer ${workspaceKey()}`}});
  cloudRevision = result.revision;
  if (result.state) {
    const pending = localStorage.getItem(pendingKey()) && state.datasets.length;
    if (!pending || !confirm('Có thay đổi cục bộ chưa đồng bộ. Giữ bản cục bộ và thay thế bản trên kho? Chọn Hủy để mở bản trên kho.')) {
      state = result.state;
      await new Promise((resolve,reject)=>{const tx=database.transaction('app','readwrite');tx.objectStore('app').put(state,'state');tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});
      localStorage.removeItem(pendingKey());
    } else await persist();
  } else if (state.datasets.length) await persist();
  document.querySelector('.sidebar-footer').lastChild.textContent = ' MongoDB Atlas · kho riêng';
  $('app-version').textContent = $('app-version').textContent.replace('Dữ liệu riêng trên trình duyệt','MongoDB Atlas · kho riêng');
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
  return state.runs.find(r => r.versionId === version()?.id && r.modelHash === model()?.digest && configMatches(r.thresholds, config));
}
function selectDataset(id, vid) { selectedDataset = id; selectedVersion = vid || dataset()?.versions.at(-1)?.id; selectedCustomer = null; resultsPage = dataPage = 0; renderAll(); }
function navigate() {
  const page = location.hash.slice(1) || 'overview';
  const current = ['overview','datasets','predict','history','models'].includes(page) ? page : 'overview';
  document.querySelectorAll('.page').forEach(el => el.hidden = el.id !== `page-${current}`);
  document.querySelectorAll('[data-page]').forEach(el => { el.classList.toggle('active', el.dataset.page === current); if (el.dataset.page === current) el.setAttribute('aria-current','page'); else el.removeAttribute('aria-current'); });
  $('sidebar').classList.remove('open'); $('menu-toggle').setAttribute('aria-expanded','false');
  document.title = `${({overview:'Tổng quan',datasets:'Quản lý dữ liệu',predict:'Dự báo rủi ro',history:'Kết quả & Lịch sử',models:'Hiệu năng mô hình'})[current]} · CreditRisk AI`;
}
function batchTab(show) { $('single-panel').hidden = show; $('batch-panel').hidden = !show; $('tab-single').classList.toggle('active', !show); $('tab-batch').classList.toggle('active', show); $('tab-single').setAttribute('aria-selected', String(!show)); $('tab-batch').setAttribute('aria-selected', String(show)); }
function setModelInfo() {
  if (!model()) return;
  $('model-meta').textContent = `${model().version} · τ = ${model().threshold.toFixed(4)}`;
  $('predict-model-title').textContent = `Mô hình dự báo: ${model().name}`;
  $('predict-model-detail').textContent = `${model().version} · CV AUC: ${model().cv_auc?.toFixed(4) ?? '—'} · Test AUC: ${model().test_auc?.toFixed(4) ?? '—'}`;
}
function invalidateSingle() {
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
    if (select) { tr.className = 'selectable'; tr.tabIndex = 0; tr.setAttribute('aria-label', `Chọn hồ sơ ${row.ID ?? row.name}`); tr.addEventListener('click', () => select(row)); tr.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(row); } }); }
    if (selected?.(row)) tr.classList.add('selected');
    if (action) { const td = tr.insertCell(); const button = document.createElement('button'); button.className = 'button secondary compact'; button.textContent = action.label; button.addEventListener('click', guarded(() => action.run(row))); td.append(button); }
  }); wrap.append(el);
}
function pagination(id, count, page, change) {
  const foot = $(id); foot.replaceChildren(); const total = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const text = document.createElement('span'); text.textContent = `${fmt(count)} hồ sơ · Trang ${page + 1}/${total}`; foot.append(text);
  const actions = document.createElement('div'); actions.className = 'actions';
  [['Trước',-1],['Sau',1]].forEach(([label, step]) => { const button = document.createElement('button'); button.textContent = label; button.className = 'button secondary compact'; button.disabled = page + step < 0 || page + step >= total; button.addEventListener('click', () => change(page + step)); actions.append(button); }); foot.append(actions);
}
function selectors() {
  document.querySelectorAll('.dataset-select').forEach(select => {
    select.replaceChildren(); if (!state.datasets.length) select.add(new Option('Chưa có tập hồ sơ', ''));
    state.datasets.forEach(d => select.add(new Option(`${d.name} · v${d.versions.at(-1).revision}`, d.id)));
    select.value = selectedDataset || ''; select.disabled = !state.datasets.length;
  });
  $('version-choice').replaceChildren(); dataset()?.versions.slice().reverse().forEach(v => $('version-choice').add(new Option(`Phiên bản ${v.revision} · ${date(v.created)}`, v.id)));
  if (version()) $('version-choice').value = version().id;
}
function historyRows(runs) { return runs.map(r => ({...r, model: `${r.modelName} · ${r.modelVersion}`, count:r.rows.length, warnings:r.rows.filter(row=>row.default_label === 1).length, config:`${r.thresholds.basis} ≥ ${r.thresholds.decision.toFixed(4)}`})); }
function renderHistory() {
  const columns = [['name','Tập hồ sơ'],['created','Thời điểm chạy'],['model','Model / phiên bản'],['count','Số hồ sơ'],['warnings','Cảnh báo'],['config','Ngưỡng nhãn']];
  const query = $('history-search').value.toLowerCase();
  table('history-table', columns, historyRows(state.runs.filter(r => `${r.name} ${r.modelName}`.toLowerCase().includes(query))), {action:{label:'Xem kết quả',run:openRun}});
  table('recent-runs', columns.slice(0,5), historyRows(state.runs.slice(0,5)), {action:{label:'Xem chi tiết',run:openRun}});
}
function renderDatasets() {
  const query = $('dataset-search').value.toLowerCase();
  const rows = state.datasets.filter(d => d.name.toLowerCase().includes(query)).map(d => { const v = d.versions.at(-1), run = state.runs.find(r => r.datasetId === d.id && r.modelHash === model()?.digest); return {...d, count:v.rows.length, revision:v.revision, created:v.created, status: !run ? 'Chưa dự báo' : run.versionId === v.id ? 'Đã dự báo' : 'Cần dự báo lại'}; });
  table('datasets-table', [['name','Tên tập hồ sơ'],['count','Số hồ sơ'],['revision','Phiên bản'],['created','Cập nhật'],['status','Trạng thái model đang chọn']], rows, {action:{label:'Xem hồ sơ',run:r=>selectDataset(r.id)},selected:r=>r.id===selectedDataset});
  const v = version(); $('data-title').textContent = dataset()?.name || 'Nội dung tập hồ sơ';
  $('data-caption').textContent = v ? `Phiên bản ${v.revision} · ${fmt(v.rows.length)} dòng · ${Object.keys(v.rows[0] || {}).length} cột · Chọn dòng để chỉnh sửa` : 'Chọn một tập hồ sơ để xem.';
  const data = v?.rows || [], columns = data.length ? Object.keys(data[0]).map(c=>[c,c]) : [];
  if (dataPage >= Math.ceil(data.length / PAGE_SIZE)) dataPage = 0;
  table('data-table', columns, data.slice(dataPage * PAGE_SIZE, (dataPage + 1) * PAGE_SIZE), {select:r=>{selectedCustomer=r.ID;renderDatasets();}, selected:r=>r.ID===selectedCustomer});
  pagination('data-footer', data.length, dataPage, page=>{dataPage=page;renderDatasets();});
  ['predict-dataset','add-customer','clone-dataset'].forEach(id=>$(id).disabled=!v);
  ['edit-customer','delete-customer'].forEach(id=>$(id).disabled=!v || selectedCustomer==null);
}
function filteredRows() {
  const run = activeRun(); if (!run) return [];
  const q=$('result-search').value.toLowerCase(), risk=$('risk-filter').value, warning=$('warning-filter').value;
  return run.rows.filter(r => String(r.ID).toLowerCase().includes(q) && (!risk || r.risk_level===risk) &&
    r.probability>=Number($('min-pd').value)/100 && r.probability<=Number($('max-pd').value)/100 &&
    r.AGE>=Number($('min-age').value) && r.AGE<=Number($('max-age').value) &&
    r.LIMIT_BAL>=Number($('min-limit').value) && r.LIMIT_BAL<=Number($('max-limit').value) &&
    r.PAY_0>=Number($('min-delay').value) && (warning==='' || r.default_label===Number(warning)));
}
function renderResults() {
  const run=activeRun(), rows=filteredRows();
  $('results-caption').textContent=run ? `${run.modelName} · ${run.modelVersion} · ${date(run.created)} · ${fmt(rows.length)}/${fmt(run.rows.length)} hồ sơ sau lọc` : 'Chưa có kết quả phù hợp với dữ liệu, model và ngưỡng hiện tại. Hãy chạy dự báo.';
  const order=['ID','raw_score','probability','default_label','risk_level','AGE','LIMIT_BAL',...features.filter(f=>!['AGE','LIMIT_BAL'].includes(f))];
  const titles={ID:'Mã hồ sơ',raw_score:'Điểm thô',probability:'PD hiệu chỉnh',default_label:'Cảnh báo (0/1)',risk_level:'Mức rủi ro',AGE:'Tuổi',LIMIT_BAL:'Hạn mức (TWD)'};
  if (resultsPage>=Math.ceil(rows.length/PAGE_SIZE)) resultsPage=0;
  table('results-table',order.map(c=>[c,titles[c]||c]),rows.slice(resultsPage*PAGE_SIZE,(resultsPage+1)*PAGE_SIZE));
  pagination('results-footer',rows.length,resultsPage,page=>{resultsPage=page;renderResults();});
}

function stats(rows) { const labelled=rows.filter(r=>r['default.payment.next.month']===0||r['default.payment.next.month']===1); return {rows:rows.length,mean:rows.length?rows.reduce((s,r)=>s+r.probability,0)/rows.length:null,high:rows.filter(r=>r.risk_level==='High').length,warnings:rows.filter(r=>r.default_label===1).length,labelled,actual:labelled.length?labelled.reduce((s,r)=>s+r['default.payment.next.month'],0)/labelled.length:null}; }
function barChart(title, subtitle, labels, values, {percent=false, colors, axis='Số hồ sơ'}={}) {
  const width=520,height=240,left=42,top=22,bottom=65,plotH=height-top-bottom,plotW=width-left-12,max=percent?1:Math.max(1,Math.ceil(Math.max(...values.filter(Number.isFinite),1)/4))*4;
  let svg=`<svg class="chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHTML(title)}">`;
  for(let i=0;i<=4;i++){const y=top+plotH-i*plotH/4;svg+=`<line class="grid" x1="${left}" x2="${width-12}" y1="${y}" y2="${y}"/><text x="${left-7}" y="${y+4}" text-anchor="end">${escapeHTML(percent?`${Math.round(max*i/4*100)}%`:fmt(max*i/4))}</text>`;}
  const band=plotW/Math.max(labels.length,1),barW=Math.min(64,band*.65);
  labels.forEach((label,i)=>{const v=Number.isFinite(values[i])?values[i]:0,x=left+band*i+(band-barW)/2,h=v/max*plotH;svg+=`<rect x="${x}" y="${top+plotH-h}" width="${barW}" height="${h}" rx="3" fill="${colors?.[i]||'#2563eb'}"><title>${escapeHTML(label)}: ${escapeHTML(percent?pct(v):fmt(v))}</title></rect><text class="number" x="${x+barW/2}" y="${top+plotH-h-7}" text-anchor="middle">${escapeHTML(percent?pct(v):fmt(v))}</text><text x="${x+barW/2}" y="${top+plotH+18}" text-anchor="middle"${labels.length>9?' transform="rotate(-32 '+(x+barW/2)+' '+(top+plotH+18)+')"':''}>${escapeHTML(label)}</text>`;});
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
  return `<article class="panel chart-card"><h3>ROC · điểm thô</h3><p class="chart-subtitle">AUC ${metrics(rows).AUC.toFixed(4)} · Nhãn hợp lệ ${known.length}</p><svg class="chart" viewBox="0 0 520 240" role="img" aria-label="Đường ROC"><path d="M45 25V195H475" fill="none" stroke="#d8e0ed"/><path d="M45 195L475 25" stroke="#b9c8dc" stroke-dasharray="5"/><polyline points="${points.join(' ')}" fill="none" stroke="#2563eb" stroke-width="2.5"/><text x="45" y="214">0</text><text x="475" y="214">1</text><text x="23" y="30">1</text><text x="180" y="236">False positive rate</text><text x="45" y="13">True positive rate</text></svg></article>`;
}
function renderOverview() {
  const latest=state.datasets.map(d=>{const v=d.versions.at(-1);return {d,v,run:state.runs.find(r=>r.datasetId===d.id&&r.modelHash===model()?.digest&&r.versionId===v.id)};});
  const total=latest.reduce((s,x)=>s+x.v.rows.length,0),high=latest.reduce((s,x)=>s+(x.run?.rows.filter(r=>r.risk_level==='High').length||0),0),stale=latest.filter(x=>!x.run).reduce((s,x)=>s+x.v.rows.length,0);
  $('portfolio-metrics').innerHTML=[['Hồ sơ danh mục',total,'Theo phiên bản mới nhất','overview',''],['Hồ sơ rủi ro cao',high,'Theo model đang chọn','shield','danger'],['Hồ sơ cần dự báo',stale,'Chưa có kết quả trên bản mới','predict','warning'],['Tập dữ liệu đã lưu',state.datasets.length,'Lưu riêng trên thiết bị này','database','teal']].map(([title,value,note,ico,tone])=>`<article class="metric ${tone}"><div class="metric-label">${title}</div><div class="metric-icon">${icon(ico)}</div><div class="metric-value">${fmt(value)}</div><p class="metric-note">${note}</p></article>`).join('');
  const run=activeRun();$('dashboard-empty').hidden=!!run;$('dashboard-content').hidden=!run;
  $('overview-context').textContent=version()?`${fmt(version().rows.length)} hồ sơ · ${model()?.name||'Chưa có model'} · Phiên bản ${version().revision}`:'Chưa có dữ liệu';
  if(!run)return;
  const rows=run.rows,s=stats(rows),mode=$('chart-mode').value;
  $('dashboard-caption').textContent=`${dataset()?.name} · ${run.modelName} · ${fmt(rows.length)} dòng · ${Object.keys(rows[0]||{}).length} cột`;
  $('insight-text').textContent=`PD trung bình ${pct(s.mean)}. ${fmt(s.warnings)}/${fmt(rows.length)} hồ sơ cảnh báo theo ngưỡng ${run.thresholds.decision} (${run.thresholds.basis}); ${fmt(s.high)} hồ sơ thuộc nhóm rủi ro cao. ${s.labelled.length?`Tỷ lệ vỡ nợ thực tế ${pct(s.actual)} trên ${fmt(s.labelled.length)} nhãn hợp lệ.`:'Chưa có nhãn thực tế để đánh giá chất lượng dự báo.'}`;
  let charts=[];
  if(mode==='risk'){
    charts.push(barChart('Phân nhóm rủi ro từ PD','risk_level · Số hồ sơ theo nhóm',['Thấp','Trung bình','Cao'],['Low','Medium','High'].map(k=>rows.filter(r=>r.risk_level===k).length),{colors:['#087f83','#d49727','#bd2946']}));
    const pd=Array(10).fill(0);rows.forEach(r=>pd[Math.min(9,Math.floor(r.probability*10))]++);
    charts.push(barChart('Phân bố PD đã hiệu chỉnh','probability · Khoảng xác suất vỡ nợ',pd.map((_,i)=>`${i*10}–${(i+1)*10}%`),pd));
    const ages=[[18,29],[30,39],[40,49],[50,59],[60,100]],means=ages.map(([lo,hi])=>{const group=rows.filter(r=>r.AGE>=lo&&r.AGE<=hi);return group.length?stats(group).mean:0;});
    charts.push(barChart('PD trung bình theo tuổi','AGE · Nhóm không có hồ sơ hiển thị 0',['18–29','30–39','40–49','50–59','60+'],means,{percent:true,axis:'PD (%)',colors:Array(5).fill('#087f83')}));
    charts.push(barChart('Nhãn cảnh báo theo ngưỡng đã lưu','default_label · Cảnh báo hỗ trợ chuyên viên',['Nhãn 0','Nhãn 1'],[rows.length-s.warnings,s.warnings],{colors:['#087f83','#bd2946']}));
  }else if(mode==='data'){
    [['AGE','Phân bố tuổi'],['LIMIT_BAL','Phân bố hạn mức (TWD)']].forEach(([key,title])=>{const [labels,values]=histogram(rows,key,6);charts.push(barChart(title,key,labels,values));});
    [['EDUCATION','Trình độ học vấn'],['PAY_0','Trạng thái trả nợ gần nhất']].forEach(([key,title])=>{const counts=new Map();rows.forEach(r=>counts.set(r[key],(counts.get(r[key])||0)+1));const labels=[...counts.keys()].sort((a,b)=>a-b);charts.push(barChart(title,`${key} · Mã UCI`,labels,labels.map(k=>counts.get(k)),{colors:labels.map(()=>'#087f83')}));});
  }else{
    const m=metrics(rows);
    if(!m){$('charts').innerHTML='<div class="panel empty"><h2>Chưa có nhãn thực tế hợp lệ</h2><p>Thêm cột default.payment.next.month với nhãn 0/1 để đánh giá model.</p></div>';return;}
    charts.push(barChart('Ma trận nhầm lẫn · thực tế / dự báo','0: không vỡ nợ · 1: vỡ nợ',['TN (0/0)','FP (0/1)','FN (1/0)','TP (1/1)'],[m.tn,m.fp,m.fn,m.tp]));
    charts.push(rocChart(rows));const keys=['Accuracy','Precision','Recall','F1'];charts.push(barChart('Chỉ số trên nhãn hợp lệ',`${fmt(m.labelled)} hồ sơ có nhãn thực tế`,keys,keys.map(k=>m[k]),{percent:true,axis:'Tỷ lệ (%)'}));
    charts.push(barChart('Phân bố nhãn thực tế','default.payment.next.month',['Không vỡ nợ','Vỡ nợ'],[m.tn+m.fp,m.fn+m.tp],{colors:['#087f83','#bd2946']}));
  }
  $('charts').innerHTML=charts.join('');
}
function renderModels() {
  table('model-table',[['name','Mô hình'],['version','Phiên bản'],['cv_auc','CV AUC gốc'],['test_auc','Test AUC gốc'],['threshold','Ngưỡng điểm thô']],models.map(m=>({...m,cv_auc:m.cv_auc?.toFixed(4),test_auc:m.test_auc?.toFixed(4),threshold:m.threshold.toFixed(4)})));
  table('comparison-table',[['name','Mô hình'],['labelled','Nhãn hợp lệ'],['Accuracy','Accuracy'],['Precision','Precision'],['Recall','Recall'],['F1','F1'],['AUC','AUC']],comparison);
}
function renderAll() { selectors();setModelInfo();renderDatasets();renderResults();renderOverview();renderHistory();renderModels(); }

async function addDataset(name,rows){const id=crypto.randomUUID(),vid=crypto.randomUUID();state.datasets.unshift({id,name,versions:[{id:vid,revision:1,created:new Date().toISOString(),rows}]});await persist();selectDataset(id,vid);return id;}
async function inferRows(rows,selected=model(),config=configuration()) {
  const output=[];
  for(let i=0;i<rows.length;i+=500){$('busy-detail').textContent=`${selected.name} · ${fmt(Math.min(i+500,rows.length))}/${fmt(rows.length)} hồ sơ`;$('busy-progress').value=Math.round((i/rows.length)*100);const result=await api('predict',{rows:rows.slice(i,i+500),model:selected.name,thresholds:config});output.push(...result.rows);}
  return output;
}
async function runBatch({go=true}={}){
  if(!version()?.rows.length)throw new Error('Chọn tập hồ sơ có dữ liệu trước khi dự báo.');
  const d=dataset(),v=version(),config=configuration(),m=model();
  if(!m)throw new Error('Chưa tải được mô hình.');
  let run=activeRun();
  if(!run){run=await busy('Đang dự báo tập hồ sơ',async()=>{const rows=await inferRows(v.rows,m,config),id=crypto.randomUUID(),created=new Date().toISOString();rows.forEach(r=>{r.run_id=id;r.prediction_time_utc=created;r.dataset_version_id=v.id;});const record={id,datasetId:d.id,versionId:v.id,name:d.name,created,modelName:m.name,modelVersion:m.version,modelHash:m.digest,thresholds:config,rows};state.runs.unshift(record);await persist();return record;});}
  renderAll();if(go){location.hash='predict';batchTab(true);}notify(`Đã có kết quả ${fmt(run.rows.length)} hồ sơ · ${run.modelName}`);
}
async function upload(event){const file=event.target.files?.[0];if(!file)return;event.target.value='';if(file.size>4*1024*1024)throw new Error('Tệp tối đa 4 MB khi tải lên Vercel.');const data=new FormData();data.append('file',file);const result=await busy('Đang kiểm tra tệp',()=>api('import',data));await addDataset(file.name,result.rows);await runBatch();const changes=Object.entries(result.normalization||{}).filter(([,v])=>v);if(changes.length)notify(`Đã chuẩn hóa theo notebook: ${changes.map(([k,v])=>`${k}: ${v}`).join(', ')}`);}
async function loadSample(){const result=await busy('Đang tải dữ liệu mẫu UCI',()=>api('sample'));await addDataset('Hồ sơ mẫu UCI',result.rows);await runBatch({go:false});location.hash='overview';}
function inputFields(container,prefix,row={}){
  const names={LIMIT_BAL:'Hạn mức tín dụng (TWD)',SEX:'Giới tính',EDUCATION:'Trình độ học vấn',MARRIAGE:'Tình trạng hôn nhân',AGE:'Tuổi'};
  const hints={SEX:'1: Nam · 2: Nữ',EDUCATION:'1: Sau ĐH · 2: ĐH · 3: THPT · 4: Khác',MARRIAGE:'1: Đã kết hôn · 2: Độc thân · 3: Khác'};
  const groups=[['Thông tin khách hàng',features.slice(0,5)],['Trạng thái trả nợ 6 tháng · mã −2 đến 8',features.filter(f=>f.startsWith('PAY_')&&!f.includes('AMT'))],['Dư nợ sao kê 6 tháng · TWD',features.filter(f=>f.startsWith('BILL_AMT'))],['Tiền thanh toán 6 tháng · TWD',features.filter(f=>f.startsWith('PAY_AMT'))]];
  let html=`<div class="field-id"><label for="${prefix}-ID">Mã khách hàng (ID)<input id="${prefix}-ID" name="ID" maxlength="128" required placeholder="VD: KH-001" value="${escapeHTML(row.ID||'')}"></label></div>`;
  groups.forEach(([title,keys])=>{html+=`<fieldset><legend>${title}</legend><div class="field-grid">`;keys.forEach(key=>{const categorical=['SEX','EDUCATION','MARRIAGE'].includes(key);let control;if(categorical){const options=key==='SEX'?[[1,'Nam'],[2,'Nữ']]:key==='EDUCATION'?[[1,'Sau đại học'],[2,'Đại học'],[3,'THPT'],[4,'Khác']]:[[1,'Đã kết hôn'],[2,'Độc thân'],[3,'Khác']];control=`<select id="${prefix}-${key}" name="${key}" required><option value="">Chọn…</option>${options.map(([v,t])=>`<option value="${v}" ${Number(row[key])===v?'selected':''}>${v} · ${t}</option>`).join('')}</select>`;}else{const min=key==='AGE'?18:key==='LIMIT_BAL'?1:key.startsWith('PAY_AMT')?0:key.startsWith('PAY_')?-2:null,max=key==='AGE'?100:key==='LIMIT_BAL'?10000000:key.startsWith('PAY_')&&!key.includes('AMT')?8:null;control=`<input id="${prefix}-${key}" name="${key}" type="number" required step="${key==='AGE'||(key.startsWith('PAY_')&&!key.includes('AMT'))?'1':'any'}" ${min!=null?`min="${min}"`:''} ${max!=null?`max="${max}"`:''} value="${escapeHTML(row[key]??'')}" placeholder="${key}">`;}html+=`<label for="${prefix}-${key}">${names[key]||key}${control}<small>${key}${hints[key]?` · ${hints[key]}`:''}</small></label>`;});html+='</div></fieldset>';});$(container).innerHTML=html;
}
function formRow(prefix){const row={ID:$(`${prefix}-ID`).value.trim()};features.forEach(f=>row[f]=Number($(`${prefix}-${f}`).value));return row;}
async function predictSingle(event){event.preventDefault();const row=formRow('single'),config=configuration(),m=model();const result=await busy('Đang chấm điểm hồ sơ',()=>api('predict',{rows:[row],model:m.name,thresholds:config}));singleResult=result.rows[0];singleInputs=row;singleConfig=config;
  const r=singleResult,tone=r.risk_level.toLowerCase();$('single-result').className='';$('single-result').innerHTML=`<div class="risk-result ${tone}"><div class="result-label">XÁC SUẤT VỠ NỢ · PD ĐÃ HIỆU CHỈNH</div><div class="pd-number">${pct(r.probability)}</div><span class="tag ${tone}">Rủi ro ${riskNames[r.risk_level].toLowerCase()}</span></div><div class="result-meta"><div><span>Điểm thô</span><strong>${r.raw_score.toFixed(4)}</strong></div><div><span>Ngưỡng nhãn · ${escapeHTML(config.basis)}</span><strong>${config.decision.toFixed(4)}</strong></div><div><span>Nhãn cảnh báo</span><strong>${r.default_label} · ${r.default_label?'Cảnh báo':'Không cảnh báo'}</strong></div><div><span>Mô hình</span><strong>${escapeHTML(m.name)}</strong></div></div>`;
  $('result-status').textContent=r.default_label?'Nhãn 1 · Cảnh báo':'Nhãn 0';$('result-status').className=`tag ${tone}`;['save-single','export-single','explain-single','transfer-single'].forEach(id=>$(id).disabled=false);$('explanation').hidden=true;
}
async function saveSingle(){if(!singleResult)throw new Error('Chạy dự báo trước khi lưu.');const id=await addDataset(`Hồ sơ ${singleInputs.ID}`,[{...singleInputs}]);const created=new Date().toISOString(),runId=crypto.randomUUID();state.runs.unshift({id:runId,datasetId:id,versionId:version().id,name:dataset().name,created,modelName:model().name,modelVersion:model().version,modelHash:model().digest,thresholds:{...singleConfig},rows:[{...singleResult,run_id:runId,prediction_time_utc:created,dataset_version_id:version().id}]});await persist();renderAll();$('save-single').disabled=true;notify('Đã lưu hồ sơ và kết quả vào trình duyệt.');}
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);}
async function exportRows(rows,config){if(!rows.length)throw new Error('Chưa có kết quả để xuất. Hãy chạy dự báo hoặc kiểm tra bộ lọc.');const m=model();if(rows.some(r=>r.model_sha256!==m.digest))throw new Error('Kết quả thuộc model khác. Hãy chọn lại model hoặc chạy dự báo.');const blob=await busy('Đang tạo báo cáo Excel',()=>api('export',{rows,model:m.name,thresholds:config}));download(blob,`ket_qua_${({'Random Forest':'RF','Logistic Regression':'LR','XGBoost':'XGb'})[m.name]||'model'}.xlsx`);notify('Đã xuất dữ liệu, insight và dashboard vào Excel.');}
async function exportCurrent(){const onBatch=location.hash==='#predict'&&!$('batch-panel').hidden,run=activeRun();await exportRows(onBatch?filteredRows():run?.rows||[],run?.thresholds||configuration());}
function openRun(run){selectedDataset=run.datasetId;selectedVersion=run.versionId;selectedCustomer=null;$('model-choice').value=run.modelName;setModelInfo();$('decision-basis').value=run.thresholds.basis;['decision','low','high'].forEach(k=>$(k).value=run.thresholds[k]*100);resetFilters();invalidateSingle();renderAll();batchTab(true);location.hash='predict';}
function resetFilters(){['result-search','risk-filter','warning-filter'].forEach(id=>$(id).value='');const values={'min-pd':0,'max-pd':100,'min-age':18,'max-age':100,'min-limit':0,'max-limit':10000000,'min-delay':-2};Object.entries(values).forEach(([k,v])=>$(k).value=v);resultsPage=0;renderResults();}
function openEditor(edit){if(!version())throw new Error('Chọn tập hồ sơ trước.');const row=edit?version().rows.find(r=>r.ID===selectedCustomer):{};if(edit&&!row)throw new Error('Chọn một dòng để chỉnh sửa.');editId=edit?row.ID:null;inputFields('edit-fields','edit',row);$('edit-title').textContent=edit?'Cập nhật hồ sơ':'Bổ sung hồ sơ';$('edit-copy').checked=false;$('edit-copy-name').value='';$('edit-dialog').showModal();}
async function revise(rows,copyName){if(!dataset())throw new Error('Chưa chọn tập hồ sơ.');if(copyName){await addDataset(copyName,rows);return;}const d=dataset(),v={id:crypto.randomUUID(),revision:d.versions.at(-1).revision+1,created:new Date().toISOString(),rows};d.versions.push(v);await persist();selectDataset(d.id,v.id);}
async function saveEdit(event){event.preventDefault();const row=formRow('edit'),existing=version().rows.find(r=>r.ID===row.ID);if(existing&&row.ID!==editId&&!confirm(`ID ${row.ID} đã tồn tại. Cập nhật hồ sơ này?`))return;const copy=$('edit-copy').checked,copyName=$('edit-copy-name').value.trim();if(copy&&!copyName)throw new Error('Nhập tên bản sao.');const valid=await busy('Đang kiểm tra hồ sơ',()=>api('predict',{rows:[row],model:model().name,thresholds:configuration()}));const canonical=Object.fromEntries(Object.entries(valid.rows[0]).filter(([k])=>k==='ID'||features.includes(k)));const rows=version().rows.filter(r=>r.ID!==editId&&r.ID!==row.ID).map(r=>({...r}));rows.push({...existing,...canonical});await revise(rows,copy?copyName:null);$('edit-dialog').close();notify('Đã lưu phiên bản mới; cần chạy dự báo lại.');}
async function deleteCustomer(){if(selectedCustomer==null)throw new Error('Chọn dòng cần xóa.');if(!confirm(`Xóa hồ sơ ${selectedCustomer} khỏi phiên bản mới? Lịch sử và phiên bản cũ vẫn được giữ.`))return;await revise(version().rows.filter(r=>r.ID!==selectedCustomer));notify('Đã tạo phiên bản mới; kết quả cũ vẫn được giữ.');}
async function cloneDataset(){if(!version())throw new Error('Chọn tập hồ sơ trước.');const name=prompt('Tên tập hồ sơ mới:',`${dataset().name} · bản sao`);if(!name?.trim())return;await addDataset(name.trim(),structuredClone(version().rows));notify('Đã lưu thành tập hồ sơ mới.');}
async function transferSingle(){if(!singleInputs)throw new Error('Chạy dự báo đơn lẻ trước.');if(!version())throw new Error('Chọn dataset nhận dữ liệu.');const existing=version().rows.some(r=>r.ID===singleInputs.ID);if(!confirm(existing?`ID ${singleInputs.ID} đã tồn tại. Cập nhật trên phiên bản mới?`:'Chuyển đầu vào vào phiên bản mới của dataset đã chọn?'))return;await revise([...version().rows.filter(r=>r.ID!==singleInputs.ID),{...singleInputs}]);notify('Đã chuyển đầu vào. Dataset cần chạy dự báo lại.');}
async function explainSingle(){if(!singleInputs)throw new Error('Chạy dự báo trước khi giải thích.');const result=await busy('Đang phân tích đóng góp đặc trưng',()=>api('explain',{rows:[singleInputs],model:model().name}));const max=Math.max(...result.rows.map(r=>Math.abs(r.contribution)),.00001);$('explanation').innerHTML=`<h3>Đóng góp đặc trưng</h3><p>${escapeHTML(result.scale)}</p>${result.rows.map(r=>`<div class="contribution ${r.contribution<0?'negative':''}"><div><span>${escapeHTML(r.feature)}</span><strong>${r.contribution>=0?'+':''}${r.contribution.toFixed(4)}</strong></div><meter min="0" max="${max}" value="${Math.abs(r.contribution)}">${r.contribution}</meter></div>`).join('')}`;$('explanation').hidden=false;}
async function compareModels(){if(!version()?.rows.length)throw new Error('Chọn tập hồ sơ trước.');if(!version().rows.some(r=>[0,1].includes(r['default.payment.next.month'])))throw new Error('Tệp cần nhãn thực tế 0/1 để so sánh.');const config=configuration();comparison=await busy('Đang đối chiếu mô hình',async()=>{const results=[];for(const m of models){const rows=await inferRows(version().rows,m,config),values=metrics(rows);results.push({name:m.name,...Object.fromEntries(Object.entries(values).map(([k,v])=>[k,typeof v==='number'&&k!=='labelled'?v.toFixed(4):v]))});}return results;});renderModels();}
function backup(){download(new Blob([JSON.stringify({format:'creditrisk-ai-backup-v1',...state})],{type:'application/json'}),`creditrisk_sao_luu_${new Date().toISOString().slice(0,10)}.json`);}
async function restore(event){const file=event.target.files?.[0];if(!file)return;event.target.value='';if(file.size>100*1024*1024)throw new Error('Bản sao lưu tối đa 100 MB.');const data=JSON.parse(await file.text());if(data.format!=='creditrisk-ai-backup-v1'||!Array.isArray(data.datasets)||!Array.isArray(data.runs)||data.datasets.some(d=>!d.id||typeof d.name!=='string'||!Array.isArray(d.versions)||!d.versions.length||d.versions.some(v=>!v.id||!Array.isArray(v.rows)||v.rows.length>30000))||data.runs.some(r=>!r.id||!Array.isArray(r.rows)||!r.thresholds))throw new Error('Tệp không đúng định dạng sao lưu CreditRisk AI.');if(!confirm('Khôi phục sẽ thay thế dữ liệu đang lưu trên trình duyệt này. Tiếp tục?'))return;state={datasets:data.datasets,runs:data.runs};await persist();selectDataset(state.datasets[0]?.id);notify('Đã khôi phục dữ liệu và lịch sử.');}

document.querySelectorAll('[data-action="upload"]').forEach(el=>el.addEventListener('click',()=>$('upload').click()));
document.querySelectorAll('[data-action="export"]').forEach(el=>el.addEventListener('click',guarded(exportCurrent)));
document.querySelectorAll('[data-action="sample"]').forEach(el=>el.addEventListener('click',guarded(loadSample)));
$('sample-top').addEventListener('click',guarded(loadSample));$('upload').addEventListener('change',guarded(upload));
$('single-form').addEventListener('submit',guarded(predictSingle));$('single-form').addEventListener('input',invalidateSingle);$('single-form').addEventListener('reset',()=>setTimeout(invalidateSingle,0));
$('fill-sample').addEventListener('click',guarded(async()=>{const sample=await api('sample');inputFields('single-fields','single',sample.rows[0]);invalidateSingle();}));
$('save-single').addEventListener('click',guarded(saveSingle));$('export-single').addEventListener('click',guarded(()=>exportRows([singleResult],singleConfig)));$('explain-single').addEventListener('click',guarded(explainSingle));$('transfer-single').addEventListener('click',guarded(transferSingle));
$('tab-single').addEventListener('click',()=>batchTab(false));$('tab-batch').addEventListener('click',()=>batchTab(true));
document.querySelectorAll('.dataset-select').forEach(el=>el.addEventListener('change',()=>selectDataset(el.value)));
$('version-choice').addEventListener('change',()=>selectDataset(selectedDataset,$('version-choice').value));
$('model-choice').addEventListener('change',guarded(async()=>{$('decision').value=$('decision-basis').value==='raw'?model().threshold*100:50;invalidateSingle();comparison=[];renderAll();if(version()?.rows.length)await runBatch({go:false});}));
['decision','low','high','decision-basis'].forEach(id=>$(id).addEventListener('change',guarded(()=>{if(id==='decision-basis')$('decision').value=$('decision-basis').value==='raw'?model().threshold*100:50;configuration();invalidateSingle();renderAll();})));
['run-batch','predict-dataset'].forEach(id=>$(id).addEventListener('click',guarded(()=>runBatch())));$('analyze-selected').addEventListener('click',guarded(()=>runBatch({go:false})));
['result-search','risk-filter','warning-filter','min-pd','max-pd','min-age','max-age','min-limit','max-limit','min-delay'].forEach(id=>$(id).addEventListener('input',()=>{resultsPage=0;renderResults();}));
$('reset-filters').addEventListener('click',resetFilters);$('chart-mode').addEventListener('change',renderOverview);$('dataset-search').addEventListener('input',renderDatasets);$('history-search').addEventListener('input',renderHistory);
$('add-customer').addEventListener('click',guarded(()=>openEditor(false)));$('edit-customer').addEventListener('click',guarded(()=>openEditor(true)));$('edit-form').addEventListener('submit',guarded(saveEdit));['close-edit','cancel-edit'].forEach(id=>$(id).addEventListener('click',()=>$('edit-dialog').close()));
$('clone-dataset').addEventListener('click',guarded(cloneDataset));$('delete-customer').addEventListener('click',guarded(deleteCustomer));$('goto-models').addEventListener('click',()=>location.hash='models');$('compare-models').addEventListener('click',guarded(compareModels));
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
$('close-storage').addEventListener('click',()=>$('storage-dialog').close());
$('copy-workspace-key').addEventListener('click',guarded(async()=>{await navigator.clipboard.writeText($('workspace-key').value);notify('Đã sao chép mã kho. Giữ riêng mã này.');}));
$('storage-form').addEventListener('submit',guarded(async event=>{
  event.preventDefault();const key=$('workspace-key').value.trim();if(!/^[0-9a-f]{64}$/.test(key))throw new Error('Mã kho phải gồm 64 ký tự 0–9, a–f.');
  if(!remoteEnabled)throw new Error('Chưa có kết nối MongoDB Atlas. Dữ liệu vẫn lưu trong trình duyệt hiện tại.');
  const result=await api('workspace',undefined,{headers:{Authorization:`Bearer ${key}`}});
  if(!confirm('Mở kho này sẽ thay dữ liệu cục bộ hiện tại. Bạn đã sao lưu JSON chưa?'))return;
  localStorage.setItem('creditrisk-workspace-key',key);localStorage.removeItem('creditrisk-cloud-pending');cloudRevision=result.revision;
  state=result.state||{datasets:[],runs:[]};await persist();selectDataset(state.datasets[0]?.id);$('storage-dialog').close();notify('Đã mở kho dữ liệu riêng.');
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
    const logout=document.createElement('button');logout.className='button secondary';logout.textContent='Đăng xuất';logout.addEventListener('click',guarded(async()=>{await api('auth/logout',{});location.assign('/login');}));banner.append(logout);
  }
  await openStorage();const [meta,health]=await Promise.all([api('models'),api('health')]);models=meta.models;features=meta.features;if(!models.length)throw new Error('Chưa tải được model thật. Kiểm tra bước build trên Vercel.');$('model-choice').replaceChildren(...models.map(m=>new Option(m.name,m.name)));if(meta.default_model)$('model-choice').value=meta.default_model;$('model-choice').disabled=false;$('decision').value=model().threshold*100;$('connection').innerHTML='<span class="status-dot"></span> API dự báo đã kết nối';$('app-version').textContent=`v${health.version} · Dữ liệu riêng trên trình duyệt`;remoteEnabled=health.storage==='mongodb';if(remoteEnabled){try{await connectCloud();}catch(error){showError(error);}}inputFields('single-fields','single');selectedDataset=state.datasets[0]?.id;selectedVersion=dataset()?.versions.at(-1)?.id;renderAll();
}
initialize().catch(error=>{$('connection').textContent='Chưa kết nối được API';showError(error);});
