'use strict';
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
let workspace, selected = 'reprogramming', activeTab = 'evidence', chemistryRun = null;
const runCache = new Map();
const labels = {title:'Blueprint name',area:'Research area',query:'Default search',question:'Research question',who:'Who / population / species',what:'What / mechanism / intervention',where:'Where / tissue / cell state',when:'When / time horizon',why:'Why / causal hypothesis',how:'How / computational approach',falsifier:'What would disprove the hypothesis?',desired_changes:'Desired changes / competing objectives'};
const busy = new Set(['queued','running']);
let refreshing = false;

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function safeLink(title, url) {
  const link = el('a', title);
  try { const parsed = new URL(url, location.origin); if (['http:', 'https:'].includes(parsed.protocol)) link.href = parsed.href; } catch {}
  link.target = '_blank'; link.rel = 'noreferrer'; return link;
}
function badge(text, cls = '') { return el('span', text, `tag ${cls}`); }
function notice(message, error = false) { $('#notice').textContent = message; $('#notice').hidden = false; $('#notice').className = error ? 'error' : ''; }
function task(fn) { return async (event) => { try { await fn(event); } catch (error) { notice(error.message, true); } }; }
async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
  return result;
}
function current() { return workspace.blueprints.find(b => b.id === selected); }
function switchTab(tab) {
  activeTab = tab;
  $$('.view').forEach(view => { view.hidden = view.id !== tab; });
  $$('[data-tab]').forEach(button => { button.classList.toggle('active', button.dataset.tab === tab); button.setAttribute('aria-current',button.dataset.tab === tab ? 'page' : 'false'); });
}
async function getRun(id, status) {
  const cached = runCache.get(id);
  if (cached && !busy.has(cached.status) && (!status || status === cached.status)) return cached;
  const run = await api(`/api/run/${id}`); runCache.set(id, run); return run;
}
function areaNavigation() {
  $('#areas').replaceChildren();
  workspace.blueprints.forEach((blueprint, index) => {
    const button = el('button');
    button.append(el('span',String(index+1).padStart(2,'0'),'area-number'),el('span',blueprint.title));
    button.classList.toggle('active', blueprint.id === selected);
    button.setAttribute('aria-current',blueprint.id === selected ? 'page' : 'false');
    button.addEventListener('click',task(async () => { selected = blueprint.id; chemistryRun = null; await renderArea(); }));
    $('#areas').append(button);
  });
}
function renderBlueprint() {
  const blueprint = current();
  $('#blueprint-fields').replaceChildren();
  for (const [field, label] of Object.entries(labels)) {
    const wrapper = el('label', label, ['question','desired_changes','falsifier'].includes(field) ? 'full' : '');
    const input = el(['title','area','query'].includes(field) ? 'input' : 'textarea');
    input.name = field; input.value = blueprint[field] || ''; input.maxLength = 4000;
    if (input.tagName === 'TEXTAREA') input.rows = 3;
    if (field === 'title') input.required = true;
    wrapper.append(input); $('#blueprint-fields').append(wrapper);
  }
}
function renderFindings() {
  const container = $('#findings'); container.replaceChildren();
  const findings = workspace.findings.filter(f => f.blueprint_id === selected)
    .sort((a, b) => (a.priority ?? 100) - (b.priority ?? 100));
  for (const finding of findings) {
    const article = el('article', null, 'finding');
    article.append(badge(`${finding.design} · ${finding.date}`),el('h3',finding.title),el('p',finding.claim),el('p',finding.boundary,'boundary'),safeLink('Primary source',finding.url));
    container.append(article);
  }
  if (!findings.length) container.append(el('div','No reviewed starting point for this area yet.','empty'));
}
function renderNotes() {
  const notes = workspace.notes.filter(n => n.blueprint_id === selected);
  $('#notes-count').textContent = `${notes.length} recorded`;
  $('#notes').replaceChildren();
  for (const note of notes) {
    const article = el('article',null,'note');
    const meta = el('div',null,'row'); meta.append(badge(note.kind,'unreviewed'),badge(note.direction),badge(note.review_status));
    article.append(meta,el('h3',note.title || 'Observation'),el('p',note.claim));
    if (note.url) article.append(safeLink('Source',note.url));
    article.append(el('p',`Population: ${note.species || 'Unknown'} · Confounders: ${note.confounders || 'Not assessed'}`),el('small',`${note.origin.replace('user supplied','manually entered')} · ${note.recorded_utc.slice(0,10)}`));
    $('#notes').append(article);
  }
  if (!notes.length) $('#notes').append(el('p','No observations recorded.','empty'));
}
let currentHits = [], currentProviders = [];
function renderRecords() {
  const kind = $('#source-filter').value, filter = $('#record-filter').value.toLowerCase();
  const unique = new Map();
  for (const h of currentHits) {
    const category = ['brave','exa'].includes(h.provider) ? 'web' : h.provider === 'trials' ? 'trials' : 'literature';
    if ((kind !== 'all' && kind !== category) || !h.title.toLowerCase().includes(filter)) continue;
    const key = h.duplicate_key;
    if (!unique.has(key)) unique.set(key, {...h, providers:[h.provider]});
    else {
      const merged = unique.get(key);
      if (!merged.providers.includes(h.provider)) merged.providers.push(h.provider);
      if (h.is_retracted === true || h.is_retracted === 'Y') merged.is_retracted = true;
      if (!merged.abstract && h.abstract) merged.abstract = h.abstract;
      merged.publication_types = [...new Set([...(merged.publication_types || []),...(h.publication_types || [])])];
    }
  }
  $('#evidence-count').textContent = unique.size;
  $('#records').replaceChildren();
  $('#provider-status').replaceChildren(...currentProviders.map(p => badge(`${p.provider}: ${p.status === 'ok' ? `${p.count} records` : p.error}`,p.status)));
  for (const h of unique.values()) {
    const row = el('article',null,'record');
    const source = el('div',null,'source'); source.append(el('div',h.providers.join(' + ')),el('div',h.date));
    const body = el('div'); const title = el('h3'); title.append(safeLink(h.title,h.url)); body.append(title,el('p',h.evidence_type));
    if (h.publication_types?.length) body.append(badge(h.publication_types.join(' / ')));
    if (h.status) body.append(badge(h.status),el('p',`${(h.phases || []).join(', ') || 'Phase not specified'} · Results posted: ${h.has_results ? 'Yes' : 'No'}`));
    if (h.is_retracted === true || h.is_retracted === 'Y') body.append(badge('RETRACTED','error'));
    if (h.abstract || h.snippet) { const details = el('details'); details.append(el('summary',h.abstract ? 'Abstract' : 'Search excerpt'),el('p',(h.abstract || h.snippet).replace(/<[^>]*>/g,''))); body.append(details); }
    const add = el('button','Add claim');
    add.addEventListener('click',() => { const form = $('#note-form'); form.elements.title.value = h.title; form.elements.url.value = h.url; form.elements.kind.value = (h.publication_types || []).some(t => /preprint/i.test(t)) ? 'preprint' : ['brave','exa','trials'].includes(h.provider) ? 'other' : 'paper'; $('#note-details').open = true; $('#note-details').scrollIntoView({behavior:'smooth',block:'center'}); form.elements.claim.focus(); });
    row.append(source,body,add); $('#records').append(row);
  }
  if (!unique.size) $('#records').append(el('div','No matching source records.','empty'));
}
async function renderResults() {
  const areaAtStart = selected;
  const searches = workspace.runs.filter(r => r.blueprint_id === selected && r.kind === 'search').slice(0,6);
  const runs = await Promise.all(searches.map(r => getRun(r.id,r.status)));
  if (selected !== areaAtStart) return;
  currentHits = runs.flatMap(r => r.result?.hits || []);
  currentProviders = runs[0]?.result?.providers || [];
  renderRecords();
  if (!chemistryRun) {
    const latest = workspace.runs.find(r => r.blueprint_id === selected && r.kind !== 'search' && ['complete','partial'].includes(r.status));
    if (latest) {
      const loaded = await getRun(latest.id,latest.status);
      if (selected !== areaAtStart) return;
      chemistryRun = loaded;
    }
  }
  if (selected !== areaAtStart) return;
  renderChemistry();
}
function setReference(row) {
  $('#reference-smiles').value = row.smiles;
  $('#reference-visual').replaceChildren();
  if (row.image) { const img = el('img'); img.src = row.image; img.alt = row.label; $('#reference-visual').append(img); }
  else $('#reference-visual').append(el('span',row.label || 'No depiction'));
}
function renderChemistry() {
  const picker = $('#chemistry-run'); picker.replaceChildren();
  for (const run of workspace.runs.filter(r => r.blueprint_id === selected && r.kind !== 'search' && ['complete','partial'].includes(r.status))) {
    const option = el('option',`${run.kind} · ${new Date(run.created_utc).toLocaleTimeString()} · ${run.id.slice(0,6)}`);
    option.value = run.id; option.selected = run.id === chemistryRun?.id; picker.append(option);
  }
  picker.disabled = picker.options.length === 0;
  const result = chemistryRun?.result;
  $('#molecule-results').replaceChildren(); $('#conformer-results').replaceChildren();
  if (!result) { $('#chemistry-note').textContent = 'No computation selected.'; return; }
  const constraints = chemistryRun.kind === 'variants' ? `Run constraints: MW <= ${chemistryRun.parameters.max_mw}; TPSA <= ${chemistryRun.parameters.max_tpsa}; no PAINS alerts.` : '';
  $('#chemistry-note').textContent = [result.identity_note,result.interpretation,result.enumeration,constraints,result.message].filter(Boolean).join(' ');
  const molecules = result.molecules || [];
  if (!$('#reference-smiles').value && molecules[0]) setReference(molecules[0]);
  const grid = el('div',null,'molecule-grid');
  for (const row of molecules) {
    if ($('#passing-only').checked && row.passes_constraints === false) continue;
    const card = el('article',null,'molecule-card');
    if (row.image) { const img = el('img'); img.src = row.image; img.alt = `${row.label} chemical structure`; img.loading = 'lazy'; card.append(img); }
    card.append(el('h3',row.label));
    if (row.cid) card.append(safeLink(`PubChem CID ${row.cid}`,row.url));
    if (row.passes_constraints !== undefined) card.append(badge(row.passes_constraints ? 'Within property constraints' : 'Outside property constraints', row.passes_constraints ? 'ok' : 'partial'));
    if (row.novelty) card.append(badge('Unmeasured · novelty unverified','unreviewed'));
    if (row.mw !== undefined) {
      const dl = el('dl');
      for (const [key,label] of [['mw','MW'],['logp','cLogP'],['tpsa','TPSA'],['hbd','H-bond donors'],['hba','H-bond acceptors'],['similarity','Morgan similarity']]) {
        if (row[key] !== undefined) { dl.append(el('dt',label),el('dd',String(row[key]))); }
      }
      card.append(dl);
      if (row.delta) card.append(el('p',`Delta MW ${row.delta.mw > 0 ? '+' : ''}${row.delta.mw}; TPSA ${row.delta.tpsa > 0 ? '+' : ''}${row.delta.tpsa}`,'method-note'));
      card.append(el('p',`PAINS alerts: ${row.pains?.length || 0} · Unspecified stereo: ${row.unspecified_stereo || 0}`,'method-note'));
    } else card.append(el('p',row.status || 'Descriptors unavailable','method-note'));
    const actions = el('div',null,'row');
    const ref = el('button','Set reference'); ref.addEventListener('click',() => setReference(row));
    const variant = el('button','Set variant'); variant.addEventListener('click',() => { $('#candidate-smiles').value = row.smiles; notice('Variant selected for comparison.'); });
    actions.append(ref,variant); card.append(actions); grid.append(card);
  }
  $('#molecule-results').append(grid);
  for (const compound of result.compounds || []) {
    const section = el('div'); section.append(el('h3',`Conformer result: ${compound.status}`),el('p',`${compound.conformers_converged || 0}/${compound.conformers_generated || 0} conformers converged. Energies refer only to this molecular representation.`,'method-note'));
    const table = el('table');
    const head = el('tr'); ['Conformer','Converged','Relative kcal/mol','Optimizer code'].forEach(s => head.append(el('th',s))); table.append(head);
    for (const c of compound.conformers || []) { const tr = el('tr'); [c.id,c.converged ? 'Yes':'No',c.relative_energy_kcal_mol === null ? 'Excluded':c.relative_energy_kcal_mol.toFixed(3),c.optimizer_status].forEach(s => tr.append(el('td',String(s)))); table.append(tr); }
    const wrap = el('div',null,'table-wrap'); wrap.append(table); section.append(wrap);
    if (compound.sdf_file) section.append(safeLink('Download all conformers (SDF)',`/api/artifact/${chemistryRun.id}/conformers/${compound.sdf_file}`));
    $('#conformer-results').append(section);
  }
}
function renderRuns() {
  const runs = workspace.runs.filter(r => r.blueprint_id === selected);
  $('#run-count').textContent = runs.length;
  const container = $('#run-list'); container.replaceChildren();
  if (!runs.length) { container.append(el('p','No runs in this blueprint.','empty')); return; }
  const wrap = el('div',null,'table-wrap'), table = el('table'), header = el('tr');
  ['Started','Operation','Status','Result',''].forEach(s => header.append(el('th',s))); table.append(header);
  for (const run of runs) {
    const row = el('tr'); row.append(el('td',new Date(run.created_utc).toLocaleString()),el('td',run.kind));
    const status = el('td'); status.append(badge(run.status,run.status)); row.append(status,el('td',run.summary || run.error || 'Pending'));
    const cell = el('td'), open = el('button','Inspect');
    open.addEventListener('click',task(async () => {
      const full = await getRun(run.id,run.status); const detail = el('div',null,'run-detail');
      detail.append(el('h3',`${full.kind} · ${full.id.slice(0,12)}`));
      const links = el('div',null,'row'); links.append(safeLink('Run JSON',`/api/artifact/${run.id}/run.json`));
      if (full.result) links.append(safeLink('Results',`/api/artifact/${run.id}/result.json`),safeLink('Manifest',`/api/artifact/${run.id}/manifest.json`));
      if (full.kind !== 'search' && full.result) { const show = el('button','Open molecule results'); show.addEventListener('click',() => { chemistryRun = full; if (full.result.molecules?.[0]) setReference(full.result.molecules[0]); renderChemistry(); switchTab('molecules'); }); links.append(show); }
      detail.append(links,el('pre',JSON.stringify({parameters:full.parameters,status:full.status,error:full.error,providers:full.result?.providers},null,2)));
      $('#run-detail').replaceChildren(detail);
    }));
    cell.append(open); row.append(cell); table.append(row);
  }
  wrap.append(table); container.append(wrap);
}
async function renderArea() {
  areaNavigation(); const b = current();
  $('#area-category').textContent = b.area; $('#area-title').textContent = b.title; $('#area-question').textContent = b.question;
  $('#query').value = b.query || ''; $('#reference-smiles').value = ''; $('#candidate-smiles').value = '';
  $('#reference-visual').replaceChildren(el('span','No structure selected'));
  $('#run-detail').replaceChildren(); $('#notice').hidden = true;
  renderBlueprint(); renderFindings(); renderNotes(); renderRuns(); await renderResults();
}
async function refresh() {
  workspace = await api('/api/state');
  const active = workspace.runs.filter(r => busy.has(r.status));
  $('#connection').textContent = active.length ? `${active.length} active run${active.length === 1 ? '' : 's'}` : 'Ready';
  renderNotes(); renderRuns(); await renderResults();
}
async function submitJob(params) {
  const run = await api('/api/jobs',{...params,blueprint_id:selected});
  notice(`${run.kind} run queued. ${run.id.slice(0,12)}`);
  await refresh();
}
$$('[data-tab]').forEach(button => button.addEventListener('click',() => switchTab(button.dataset.tab)));
$('#source-filter').addEventListener('change',renderRecords); $('#record-filter').addEventListener('input',renderRecords);
$('#passing-only').addEventListener('change',renderChemistry);
$('#chemistry-run').addEventListener('change',task(async event => {
  const area = selected, loaded = await getRun(event.target.value);
  if (selected !== area) return;
  chemistryRun = loaded;
  if (loaded.result?.molecules?.[0]) setReference(loaded.result.molecules[0]);
  renderChemistry();
}));
$('#search-form').addEventListener('submit',task(async event => { event.preventDefault(); await submitJob({kind:'search',query:$('#query').value,limit:Number($('#limit').value),providers:$$('#providers input:checked').map(n => n.value)}); }));
$('#compound-form').addEventListener('submit',task(async event => { event.preventDefault(); chemistryRun = null; $('#reference-smiles').value = ''; await submitJob({kind:event.submitter.value,name:$('#compound-name').value,threshold:Number($('#threshold').value)}); }));
$('#variant-form').addEventListener('submit',task(async event => { event.preventDefault(); await submitJob({kind:'variants',smiles:$('#reference-smiles').value,max_mw:Number($('#max-mw').value),max_tpsa:Number($('#max-tpsa').value)}); }));
$('#compare-form').addEventListener('submit',task(async event => { event.preventDefault(); await submitJob({kind:'compare',smiles:$('#reference-smiles').value,candidate:$('#candidate-smiles').value}); }));
$('#conformer-form').addEventListener('submit',task(async event => { event.preventDefault(); await submitJob({kind:'conformers',smiles:$('#reference-smiles').value,conformers:Number($('#conformer-count').value),seed:Number($('#seed').value)}); }));
$('#blueprint-form').addEventListener('submit',task(async event => { event.preventDefault(); const saved = await api('/api/blueprints',{...Object.fromEntries(new FormData(event.target)),id:selected}); await refresh(); areaNavigation(); $('#area-title').textContent = saved.title; $('#area-question').textContent = saved.question; $('#area-category').textContent = saved.area; $('#query').value = saved.query; notice('Blueprint saved.'); }));
$('#note-form').addEventListener('submit',task(async event => { event.preventDefault(); await api('/api/notes',{...Object.fromEntries(new FormData(event.target)),blueprint_id:selected}); event.target.reset(); await refresh(); notice('Observation saved with its source type and review status.'); }));
$('#new-blueprint').addEventListener('click',task(async () => { const item = await api('/api/blueprints',{title:'Untitled research blueprint',area:'Open exploration'}); workspace = await api('/api/state'); selected = item.id; chemistryRun = null; await renderArea(); switchTab('blueprint'); $('#blueprint-form [name=title]').select(); }));
$('#export').addEventListener('click',task(async () => { const data = await api(`/api/export/${selected}`); const url = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})); const a = el('a'); a.href = url; a.download = `regen-${selected}-dossier.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url),1000); notice('Dossier exported with blueprint, source notes, runs and a Markdown draft.'); }));

async function init() {
  workspace = await api('/api/state');
  if (!workspace.blueprints.some(b => b.id === selected)) selected = workspace.blueprints[0].id;
  $('#compute-status').textContent = workspace.rdkit_available ? 'RDKit available · CPU' : 'RDKit unavailable';
  for (const provider of workspace.providers) {
    const label = el('label'), input = el('input'); input.type = 'checkbox'; input.value = provider.id;
    input.checked = ['pubmed','europepmc','trials'].includes(provider.id);
    input.disabled = provider.key_required && !provider.key_configured;
    label.append(input,document.createTextNode(provider.name));
    if (provider.key_configured) label.append(el('small','key set'));
    if (input.disabled) label.append(el('small','key missing'));
    $('#providers').append(label);
  }
  await renderArea(); $('#connection').textContent = 'Ready';
  setInterval(task(async () => {
    if (refreshing || !workspace.runs.some(r => busy.has(r.status))) return;
    refreshing = true;
    try {
      const previous = new Set(workspace.runs.filter(r => busy.has(r.status)).map(r => r.id));
      await refresh();
      const finished = workspace.runs.filter(r => previous.has(r.id) && !busy.has(r.status));
      for (const run of finished) {
        if (run.blueprint_id !== selected) continue;
        notice(`${run.kind}: ${run.summary || run.error || run.status}`,run.status === 'failed');
        if (run.kind !== 'search' && ['complete','partial'].includes(run.status)) {
          const loaded = await getRun(run.id,run.status);
          if (run.blueprint_id !== selected) continue;
          chemistryRun = loaded;
          if (['compound','neighbors'].includes(run.kind) && chemistryRun.result?.molecules?.[0]) setReference(chemistryRun.result.molecules[0]);
          renderChemistry();
        }
      }
    } finally { refreshing = false; }
  }),2000);
}
init().catch(error => notice(error.message,true));
