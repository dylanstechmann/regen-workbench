'use strict';
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
let workspace, selected = 'reprogramming', activeTab = 'evidence', chemistryRun = null, selectedCampaignId = null;
let runPage = 0, runPageSize = 50, historyRuns = [], historyTotal = 0;
const runCache = new Map();
let modelArtifactState = null;
const trajectoryCache = new Map();
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
function modelNumber(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value.toPrecision(4) : 'not reported';
}
function parseModelTrajectory(text) {
  const lines = text.split(/\r?\n/);
  const header = (lines.shift() || '').split(',');
  const indexes = Object.fromEntries(['dimensionless_time','power_source','sensor_sampled','sensor_reading']
    .map(name => [name,header.indexOf(name)]));
  if (Object.values(indexes).some(index => index < 0)) throw new Error('Trajectory is missing required plot columns.');
  const rows = [];
  let previous = -Infinity;
  for (const line of lines) {
    if (!line) continue;
    if (rows.length >= 50402) throw new Error('Trajectory exceeds the plot row limit.');
    const columns = line.split(',');
    const time = Number(columns[indexes.dimensionless_time]);
    const power = columns[indexes.power_source];
    const sampledText = columns[indexes.sensor_sampled];
    const readingText = columns[indexes.sensor_reading];
    const reading = readingText === '' ? null : Number(readingText);
    if (!Number.isFinite(time) || time <= previous || !['wall','backup','none'].includes(power)
        || !['True','False'].includes(sampledText)
        || (reading !== null && (!Number.isFinite(reading) || Math.abs(reading) > 1e12))) {
      throw new Error('Trajectory contains an invalid dimensionless time, power label, or reading.');
    }
    const sampled = sampledText === 'True';
    if (!sampled && reading !== null) throw new Error('An unscheduled trajectory row contains a reading.');
    rows.push({time,power,sampled,reading});
    previous = time;
  }
  if (rows.length < 2) throw new Error('Trajectory does not contain enough rows to plot.');
  return rows;
}
function drawModelTrajectory(canvas, rows) {
  const cardWidth = canvas.closest('.model-bench-card')?.clientWidth || canvas.clientWidth || 760;
  const width = Math.max(480, Math.floor(cardWidth - 36)), height = 260;
  const scale = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = Math.round(width * scale); canvas.height = Math.round(height * scale);
  canvas.style.height = `${height}px`;
  canvas.setAttribute('aria-label','Dimensionless synthetic sensor readings over time. Shaded intervals indicate backup power or no power.');
  const context = canvas.getContext('2d');
  context.setTransform(scale,0,0,scale,0,0);
  context.fillStyle = '#fff'; context.fillRect(0,0,width,height);
  const margin = {left:58,right:16,top:16,bottom:38};
  const plotWidth = width-margin.left-margin.right, plotHeight = height-margin.top-margin.bottom;
  const readings = rows.filter(row => row.sampled && row.reading !== null).map(row => row.reading);
  if (!readings.length) throw new Error('This fixture has no usable sensor readings to plot.');
  let low = Infinity, high = -Infinity;
  for (const value of readings) { low=Math.min(low,value); high=Math.max(high,value); }
  if (low === high) { low -= 0.5; high += 0.5; }
  const firstTime = rows[0].time, lastTime = rows[rows.length-1].time;
  const x = time => margin.left+(time-firstTime)/(lastTime-firstTime)*plotWidth;
  const y = value => margin.top+(high-value)/(high-low)*plotHeight;
  for (let index=0; index<rows.length-1; index++) {
    const row=rows[index], next=rows[index+1];
    if (row.power === 'wall') continue;
    context.fillStyle = row.power === 'none' ? 'rgba(177,75,61,.12)' : 'rgba(51,116,160,.12)';
    context.fillRect(x(row.time),margin.top,Math.max(1,x(next.time)-x(row.time)),plotHeight);
  }
  context.strokeStyle='#dce2e0'; context.lineWidth=1;
  context.font='10px Segoe UI, Arial, sans-serif'; context.fillStyle='#67736f';
  for (let tick=0;tick<=4;tick++) {
    const fraction=tick/4, yy=margin.top+fraction*plotHeight;
    context.beginPath(); context.moveTo(margin.left,yy); context.lineTo(width-margin.right,yy); context.stroke();
    context.fillText((high-fraction*(high-low)).toPrecision(3),4,yy+3);
  }
  context.strokeStyle='#426e5d'; context.lineWidth=1.8; context.beginPath();
  let active=false;
  for (const row of rows) {
    if (!row.sampled) continue;
    if (row.reading === null) { active=false; continue; }
    if (!active) { context.moveTo(x(row.time),y(row.reading)); active=true; }
    else context.lineTo(x(row.time),y(row.reading));
  }
  context.stroke();
  context.fillStyle='#146b55';
  for (const row of rows) {
    if (!row.sampled || row.reading === null) continue;
    context.beginPath(); context.arc(x(row.time),y(row.reading),2.2,0,Math.PI*2); context.fill();
  }
  context.fillStyle='#67736f'; context.textAlign='left'; context.fillText(modelNumber(firstTime),margin.left,height-12);
  context.textAlign='right'; context.fillText(modelNumber(lastTime),width-margin.right,height-12);
  context.textAlign='center'; context.fillText('dimensionless time',margin.left+plotWidth/2,height-2);
  context.save(); context.translate(13,margin.top+plotHeight/2); context.rotate(-Math.PI/2);
  context.fillText('sensor reading (dimensionless)',0,0); context.restore();
  return {scheduled:rows.filter(row=>row.sampled).length,usable:readings.length,missing:rows.filter(row=>row.sampled&&row.reading===null).length};
}
async function showModelTrajectory(bundleId, section, button) {
  if (!section.hidden) { section.hidden=true; button.textContent='Show synthetic trajectory'; return; }
  button.disabled=true;
  try {
    let rows=trajectoryCache.get(bundleId);
    if (!rows) {
      const response=await fetch(`/api/ectogenesis/model-artifact/${encodeURIComponent(bundleId)}/trajectory.csv`);
      if (!response.ok) throw new Error(`Trajectory could not be loaded (${response.status}).`);
      const csv=await response.text();
      if (csv.length>12_000_000) throw new Error('Trajectory exceeds the 12 MB display limit.');
      rows=parseModelTrajectory(csv); trajectoryCache.set(bundleId,rows);
    }
    section.replaceChildren();
    const canvas=el('canvas',null,'model-bench-chart');
    const summary=drawModelTrajectory(canvas,rows);
    section.append(canvas,el('p',`${summary.usable} of ${summary.scheduled} scheduled readings were usable · ${summary.missing} gaps. Values and time are dimensionless; light blue marks backup power and light red marks no power.`,'boundary'));
    section.hidden=false; button.textContent='Hide synthetic trajectory';
  } finally { button.disabled=false; }
}
function renderModelBench() {
  const state = modelArtifactState, status = $('#model-bench-status'), container = $('#model-bench-cards');
  container.replaceChildren();
  if (!state) {
    status.replaceChildren(badge('Reports have not been loaded','unreviewed'));
    $('#model-bench-count').textContent = '';
    return;
  }
  const verified = (state.bundles || []).filter(bundle => bundle.verified === true);
  $('#model-bench-count').textContent = verified.length ? String(verified.length) : '';
  status.replaceChildren(badge(state.available ? `${verified.length} hash-matched bundles` : 'Sibling artifact folder not mounted',state.available ? 'complete' : 'unreviewed'),el('span',state.message || ''));
  if (!state.bundles?.length) {
    container.append(el('p',state.available
      ? 'No recognized receipt-bearing reports are available yet. Generate an evidence, simulation, identifiability, or design-sweep bundle in artificial-womb-models/artifacts, then refresh.'
      : (state.message || 'The sibling artifact folder is not mounted.'),'empty'));
    return;
  }
  for (const bundle of state.bundles) {
    const card = el('article',null,'model-bench-card');
    const heading = el('div',null,'model-bench-card-heading');
    heading.append(el('h3',bundle.label || 'Local bundle'),badge(bundle.verified ? 'Receipt hashes match files' : 'Needs review',bundle.verified ? 'complete' : 'unreviewed'));
    card.append(heading,el('p',`Bundle: ${bundle.bundle_id}`,'model-bench-id'));
    if (!bundle.verified) {
      card.append(el('p',bundle.error || 'The bundle did not pass the receipt check. Files are not exposed in this view.','boundary'));
      container.append(card);
      continue;
    }
    const summary = bundle.summary || {};
    if (bundle.bundle_kind === 'reviewed_evidence_map') {
      card.append(el('p',`${summary.source_count ?? '—'} sources · ${summary.claim_count ?? '—'} claims · ${summary.requirement_count ?? '—'} requirements`));
      if (summary.reviewed_on) card.append(el('p',`Ledger review date: ${summary.reviewed_on}. Review and update it before relying on a source card.`,'boundary'));
    } else if (bundle.bundle_kind === 'synthetic_exchange_software_fixture') {
      const residuals = Object.values(summary.balances || {}).filter(value => typeof value === 'number' && Number.isFinite(value));
      const maxResidual = residuals.length ? Math.max(...residuals) : null;
      card.append(el('p',`${summary.n_monitor_samples ?? '—'} scheduled monitor samples · ${summary.fault_metrics?.fault_intervals?.length ?? 0} modeled fault intervals`));
      card.append(el('p',`Largest accounting residual: ${modelNumber(maxResidual)}`,'model-bench-metric'));
      card.append(el('p','Accounting consistency is a property of this fixture; it is not a physiological validation.','boundary'));
      if ((bundle.outputs || []).includes('trajectory.csv')) {
        const plotButton=el('button','Show synthetic trajectory'); plotButton.type='button';
        const plotSection=el('section',null,'model-bench-plot'); plotSection.hidden=true;
        plotButton.addEventListener('click',task(()=>showModelTrajectory(bundle.bundle_id,plotSection,plotButton)));
        card.append(plotButton,plotSection);
      }
    } else if (bundle.bundle_kind === 'synthetic_exchange_observability_diagnostic') {
      const fit = summary.full_series_fit || {}, early = summary.early_series_fit || {};
      const estimates = fit.parameter_estimates || {};
      card.append(el('p',`${summary.n_usable_readings ?? '—'} usable readings · design rank ${fit.rank ?? 'unresolved'} · condition ${modelNumber(fit.normalized_design_condition_number)}`));
      card.append(el('p',`Full-run fixture-rate estimates · powered input ${modelNumber(estimates.powered_input)} · conversion ${modelNumber(estimates.conversion)}`,'model-bench-metric'));
      card.append(el('p',`First 70% window: ${early.estimable ? `rank ${early.rank}; condition ${modelNumber(early.normalized_design_condition_number)}` : (early.reason || 'not identified')}. Later-window observations are from the same generated run.`,'boundary'));
    } else if (bundle.bundle_kind === 'synthetic_exchange_design_sweep') {
      card.append(el('p',`${summary.n_synthetic_runs ?? '—'} seeded fixture runs across ${summary.n_designs ?? '—'} design conditions.`));
      const designSummaries = Array.isArray(summary.design_summaries) ? summary.design_summaries : [];
      const profiles = new Set(designSummaries.map(item=>item.monitor_fault_profile));
      const timingProfiles = new Set(designSummaries.map(item=>item.event_timing_profile).filter(value=>typeof value==='string'));
      const reportsTiming = designSummaries.some(item=>typeof item.event_timing_profile==='string');
      const faultBoundary = profiles.has('injected monitor faults removed')
        ? 'The fault-free profile removes injected monitor bias/dropout intervals while retaining wall outages and power-loss-related missing readings.'
        : 'This source fixture has no configured monitor-fault contrast; modeled wall outages and power-loss-related missing readings remain in scope.';
      const timingBoundary = !reportsTiming
        ? 'This report predates the event-timing comparison field, so its timing profile is not recorded.'
        : timingProfiles.has('time-reflected event timing')
          ? 'The reflected schedule preserves event durations and maps intervals across the fixture midpoint; it tests timing sensitivity for this fixture, not a realistic outage distribution.'
          : 'No event-timing contrast was needed because the source fixture contains no outage or monitor-fault intervals.';
      card.append(el('p',`Generator-known rates score fits only after estimation. Replicates share one fixture and event schedule within each design. A temporal holdout trains on each run's first 70% of usable intervals and scores later intervals from that same run. Leave-one-seed-out fits train on other runs of the same design and score the omitted run; both are synthetic diagnostics, not independent experimental validation. ${faultBoundary} ${timingBoundary}`,'boundary'));
      const table = el('table',null,'model-bench-sweep-table'), header = el('tr');
      ['Requested cadence × noise','Fault profile','Event timing','Actual step · noise SD','Estimable runs','Same-run holdout fits','Same-run RMSE med / P90','Leave-one-seed-out fits','Cross-run RMSE med / P90','Condition med / P90','Input abs error med / P90','Conversion abs error med / P90'].forEach(label => header.append(el('th',label)));
      table.append(header);
      for (const design of designSummaries.slice(0,36)) {
        const row = el('tr');
        row.append(el('td',`${modelNumber(design.cadence_factor_requested)}× cadence · ${modelNumber(design.noise_multiplier_requested)}× noise`));
        row.append(el('td',design.monitor_fault_profile || 'not reported'));
        row.append(el('td',design.event_timing_profile || 'not reported'));
        row.append(el('td',`${modelNumber(design.actual_output_step)} · ${modelNumber(design.actual_noise_sd)}`));
        row.append(el('td',`${design.estimable_replicates ?? '—'} / ${design.replicates ?? '—'}`));
        row.append(el('td',`${design.temporal_holdout_estimable_replicates ?? '—'} / ${design.replicates ?? '—'}`));
        row.append(el('td',`${modelNumber(design.median_temporal_holdout_fixture_scale_rmse)} / ${modelNumber(design.p90_temporal_holdout_fixture_scale_rmse)}`));
        row.append(el('td',`${design.cross_replicate_holdout_estimable_replicates ?? '—'} / ${design.replicates ?? '—'}`));
        row.append(el('td',`${modelNumber(design.median_cross_replicate_holdout_fixture_scale_rmse)} / ${modelNumber(design.p90_cross_replicate_holdout_fixture_scale_rmse)}`));
        row.append(el('td',`${modelNumber(design.median_design_condition_number)} / ${modelNumber(design.p90_design_condition_number)}`));
        row.append(el('td',`${modelNumber(design.median_absolute_error_powered_input)} / ${modelNumber(design.p90_absolute_error_powered_input)}`));
        row.append(el('td',`${modelNumber(design.median_absolute_error_conversion)} / ${modelNumber(design.p90_absolute_error_conversion)}`));
        table.append(row);
      }
      const tableWrap = el('div',null,'table-wrap model-bench-sweep-wrap');
      tableWrap.append(table); card.append(tableWrap);
    }
    if (Array.isArray(summary.limitations) && summary.limitations.length) {
      const limits=el('details',null,'model-bench-limitations');
      limits.append(el('summary','Limits recorded by this report'));
      const list=el('ul');
      summary.limitations.slice(0,12).forEach(item=>list.append(el('li',String(item).slice(0,2000))));
      limits.append(list); card.append(limits);
    }
    const links = el('div',null,'row model-bench-links');
    const labelsByFile = {"REPORT.md":"Readable report","observability_report.json":"Fit summary","simulation_summary.json":"Simulation summary","evidence_report.json":"Evidence map JSON","design_sweep_report.json":"Sweep summary JSON","sweep_plan.json":"Sweep design plan","design_sweep.csv":"Replicate table","design_summaries.csv":"Design summary table","trajectory.csv":"Trajectory","interval_design.csv":"Design intervals","claims.csv":"Claims table","stage_map.csv":"Stage map","requirements.csv":"Requirements"};
    for (const filename of bundle.outputs || []) {
      if (!labelsByFile[filename]) continue;
      links.append(safeLink(labelsByFile[filename],`/api/ectogenesis/model-artifact/${encodeURIComponent(bundle.bundle_id)}/${encodeURIComponent(filename)}`));
    }
    card.append(links);
    const provenance = el('details',null,'model-bench-provenance');
    provenance.append(el('summary','Receipt, runtime and implementation provenance'),el('pre',JSON.stringify({package_version:bundle.package_version,python_version:bundle.python_version,input_sha256:bundle.input_sha256,implementation_sha256:bundle.implementation_sha256,outputs:bundle.outputs},null,2)));
    card.append(provenance);
    container.append(card);
  }
}
async function refreshModelBench() {
  if (selected !== 'ectogenesis') return;
  const button = $('#refresh-model-bench');
  button.disabled = true;
  try {
    const areaAtStart = selected;
    const result = await api('/api/ectogenesis/models');
    if (areaAtStart !== selected) return;
    modelArtifactState = result;
    renderModelBench();
  } finally { button.disabled = false; }
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
  $('#provider-status').replaceChildren(...currentProviders.map(p => badge(`${p.run_label} / ${p.provider}: ${p.status === 'ok' ? `${p.count} records` : p.error}`,p.status)));
  for (const h of unique.values()) {
    const row = el('article',null,'record');
    const source = el('div',null,'source'); source.append(el('div',h.providers.join(' + ')),el('div',h.date),el('small',h.run_label || ''));
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
  currentHits = [];
  currentProviders = [];
  for (const run of runs) {
    const query = run.parameters?.query || '';
    const runLabel = `${new Date(run.created_utc).toLocaleString()} · ${query.slice(0,72)}`;
    currentProviders.push(...(run.result?.providers || []).map(provider => ({...provider, run_id:run.id, query, run_label:runLabel})));
    currentHits.push(...(run.result?.hits || []).map(hit => ({...hit, run_id:run.id, query, run_label:runLabel})));
  }
  renderRecords();
  if (!chemistryRun) {
    const latest = workspace.runs.find(r => r.blueprint_id === selected && !['search','docking'].includes(r.kind) && ['complete','partial'].includes(r.status));
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
  for (const run of workspace.runs.filter(r => r.blueprint_id === selected && !['search','docking'].includes(r.kind) && ['complete','partial'].includes(r.status))) {
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
  const runs = historyRuns;
  $('#run-count').textContent = historyTotal;
  const container = $('#run-list'); container.replaceChildren();
  if (!historyTotal) { container.append(el('p','No runs in this blueprint.','empty')); $('#run-pagination').replaceChildren(); return; }
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
      if (full.artifacts?.submission) links.append(safeLink('Submission snapshot',`/api/artifact/${run.id}/submission.json`));
      if (full.artifacts?.manifest) links.append(safeLink('Manifest',`/api/artifact/${run.id}/manifest.json`));
      if (full.result && full.artifacts?.result) links.append(safeLink('Results',`/api/artifact/${run.id}/result.json`));
      if (full.kind === 'docking' && full.result) {
        links.append(safeLink('Docked poses',full.result.output_artifact));
        for (const file of full.result.input_artifacts || []) links.append(safeLink('Prepared input',file));
      }
      if (!['search','docking'].includes(full.kind) && full.result) { const show = el('button','Open molecule results'); show.addEventListener('click',() => { chemistryRun = full; if (full.result.molecules?.[0]) setReference(full.result.molecules[0]); renderChemistry(); switchTab('molecules'); }); links.append(show); }
      detail.append(links,el('pre',JSON.stringify({parameters:full.parameters,status:full.status,error:full.error,submission_sha256:full.submission_sha256,providers:full.result?.providers,metrics:full.result?.metrics,interpretation:full.result?.interpretation},null,2)));
      $('#run-detail').replaceChildren(detail);
    }));
    cell.append(open); row.append(cell); table.append(row);
  }
  wrap.append(table); container.append(wrap);
  const pagination = $('#run-pagination'); pagination.replaceChildren();
  const pages = Math.max(1,Math.ceil(historyTotal / runPageSize));
  const previous = el('button','Previous'); previous.disabled = runPage === 0; previous.addEventListener('click',task(async () => { await loadRunPage(runPage - 1); }));
  const next = el('button','Next'); next.disabled = runPage + 1 >= pages; next.addEventListener('click',task(async () => { await loadRunPage(runPage + 1); }));
  pagination.append(previous,el('span',`Page ${runPage + 1} of ${pages} · ${historyTotal} runs`),next);
}
async function loadRunPage(page = runPage) {
  const areaAtStart = selected;
  const params = new URLSearchParams({blueprint_id:selected,offset:String(page * runPageSize),limit:String(runPageSize)});
  const result = await api(`/api/runs?${params}`);
  if (selected !== areaAtStart) return;
  runPage = page; historyRuns = result.runs; historyTotal = result.total;
  renderRuns();
}
async function renderArea() {
  areaNavigation(); const b = current();
  $('#model-bench-tab').hidden = selected !== 'ectogenesis';
  if (selected !== 'ectogenesis' && activeTab === 'model-bench') switchTab('evidence');
  $('#area-category').textContent = b.area; $('#area-title').textContent = b.title; $('#area-question').textContent = b.question;
  $('#query').value = b.query || ''; $('#reference-smiles').value = ''; $('#candidate-smiles').value = '';
  $('#reference-visual').replaceChildren(el('span','No structure selected'));
  $('#run-detail').replaceChildren(); $('#notice').hidden = true;
  selectedCampaignId = null; $('#link-campaign').checked = false;
  renderBlueprint(); renderFindings(); renderNotes(); renderCampaign(); await loadRunPage(0); await renderResults();
  if (selected === 'ectogenesis' && activeTab === 'model-bench') {
    renderModelBench();
    await refreshModelBench();
  }
}
async function refresh() {
  workspace = await api('/api/state');
  const active = workspace.runs.filter(r => busy.has(r.status));
  $('#connection').textContent = active.length ? `${active.length} active run${active.length === 1 ? '' : 's'}` : 'Ready';
  renderNotes(); renderCampaignRuns(); await loadRunPage(runPage); await renderResults();
}
async function submitJob(params) {
  const {campaign_id:explicitCampaignId, ...jobParams} = params;
  const campaignId = explicitCampaignId || ($('#link-campaign').checked ? selectedCampaignId : null);
  const run = await api('/api/jobs',{...jobParams,blueprint_id:selected,...(campaignId ? {campaign_id:campaignId} : {})});
  notice(`${run.kind} run queued. ${run.id.slice(0,12)}`);
  await refresh();
}

function campaignById() { return workspace.campaigns.find(c => c.id === selectedCampaignId && c.blueprint_id === selected) || null; }
function updateCampaignLink() {
  const campaign = campaignById(), toggle = $('#link-campaign');
  toggle.disabled = !campaign;
  if (!campaign) toggle.checked = false;
  $('#campaign-link-target').textContent = campaign ? campaign.title : 'Select a saved campaign to link runs';
}
function renderEvidenceAxes(campaign, preset = []) {
  const container = $('#campaign-evidence'); container.replaceChildren();
  const axes = workspace.campaign_frameworks?.[selected] || [];
  const saved = new Map([...(campaign?.evidence || []), ...preset].map(item => [item.axis_id,item]));
  for (const axis of axes) {
    const value = saved.get(axis.id) || {};
    const fieldset = el('fieldset',null,'evidence-axis'); fieldset.append(el('legend',axis.label),el('small',axis.prompt));
    const fields = el('div',null,'evidence-fields');
    for (const [field,label] of [['status','Source direction'],['value','Reported value'],['unit','Unit / denominator'],['comparator','Comparator'],['timepoint','Timepoint'],['source_url','Source URL'],['notes','Interpretation / limitations']]) {
      const wrapper = el('label',label);
      let input;
      if (field === 'status') {
        input = el('select');
        for (const option of ['not assessed','source reports positive signal','source reports mixed signal','source reports no signal','conflicting sources']) {
          const choice = el('option',option); choice.value = option; input.append(choice);
        }
      } else if (field === 'notes') {
        input = el('textarea'); input.rows = 2; input.maxLength = 3000;
      } else {
        input = el('input'); input.type = field === 'source_url' ? 'url' : 'text'; input.maxLength = 3000;
      }
      input.id = `evidence_${axis.id}_${field}`; input.dataset.axis = axis.id; input.dataset.field = field; input.value = value[field] || (field === 'status' ? 'not assessed' : '');
      wrapper.append(input); fields.append(wrapper);
    }
    fieldset.append(fields); container.append(fieldset);
  }
}
function collectCampaignEvidence() {
  return (workspace.campaign_frameworks?.[selected] || []).map(axis => {
    const entry = {axis_id:axis.id};
    for (const field of ['status','value','unit','comparator','timepoint','source_url','notes']) entry[field] = $(`#evidence_${axis.id}_${field}`).value.trim();
    return entry;
  });
}
function renderCampaign() {
  const campaigns = workspace.campaigns.filter(c => c.blueprint_id === selected);
  if (selectedCampaignId && !campaigns.some(c => c.id === selectedCampaignId)) selectedCampaignId = null;
  $('#campaign-count').textContent = campaigns.length || '';
  const picker = $('#campaign-select'); picker.replaceChildren();
  const blank = el('option','New campaign'); blank.value = ''; picker.append(blank);
  for (const campaign of campaigns) { const option = el('option',campaign.title); option.value = campaign.id; picker.append(option); }
  picker.value = selectedCampaignId || '';
  const campaign = campaignById(), form = $('#campaign-form');
  for (const name of ['title','target','species','tissue','hypothesis','endpoint','falsifier','evidence_stage','study_design','reference_url','receptor','structure_notes','starter_id']) form.elements[name].value = campaign?.[name] || '';
  const starterPicker = $('#campaign-starter'); starterPicker.replaceChildren(el('option','Blank campaign'));
  starterPicker.options[0].value = '';
  for (const starter of workspace.campaign_starters?.[selected] || []) { const option = el('option',starter.title); option.value = starter.id; starterPicker.append(option); }
  starterPicker.value = campaign?.starter_id || '';
  renderEvidenceAxes(campaign);
  for (const [axis,index] of [['x',0],['y',1],['z',2]]) {
    form.elements[`center_${axis}`].value = campaign?.center?.[index] ?? 0;
    form.elements[`size_${axis}`].value = campaign?.size?.[index] ?? 20;
  }
  const tools = workspace.docking_tools || {};
  const engine = $('#docking-form').elements.engine;
  engine.querySelector('[value="vina"]').disabled = !tools.vina;
  engine.querySelector('[value="gnina"]').disabled = !tools.gnina;
  if (!tools.vina && tools.gnina) engine.value = 'gnina';
  else if (tools.vina && engine.selectedOptions[0]?.disabled) engine.value = 'vina';
  $('#docking-status').textContent = `Vina ${tools.vina ? 'available' : 'unavailable'} · GNINA ${tools.gnina ? 'available' : 'unavailable'}`;
  $('#docking-form button[type="submit"]').disabled = !campaign || (!tools.vina && !tools.gnina);
  updateCampaignLink();
  renderCampaignRuns();
}
async function saveCampaign() {
  const form = $('#campaign-form');
  const values = Object.fromEntries(new FormData(form));
  const saved = await api('/api/campaigns',{...values,evidence:collectCampaignEvidence(),id:selectedCampaignId || '',blueprint_id:selected});
  workspace = await api('/api/state');
  selectedCampaignId = saved.id;
  renderCampaign();
  notice('Campaign saved.');
  return saved;
}
function renderCampaignRuns() {
  const container = $('#campaign-runs');
  if (!container) return;
  const runs = workspace.runs.filter(r => r.campaign_id === selectedCampaignId);
  container.replaceChildren();
  if (!selectedCampaignId || !runs.length) { container.append(el('p',selectedCampaignId ? 'No runs linked to this campaign.' : 'Save a campaign to start attaching runs.','empty')); return; }
  const wrap = el('div',null,'table-wrap'), table = el('table'), header = el('tr');
  ['Started','Operation','Status','Result'].forEach(label => header.append(el('th',label))); table.append(header);
  for (const run of runs) {
    const row = el('tr'); row.append(el('td',new Date(run.created_utc).toLocaleString()),el('td',run.kind),el('td',run.status),el('td',run.summary || run.error || 'Pending')); table.append(row);
  }
  wrap.append(table); container.append(wrap);
}
$$('[data-tab]').forEach(button => button.addEventListener('click',task(async () => {
  switchTab(button.dataset.tab);
  if (button.dataset.tab === 'model-bench') await refreshModelBench();
})));
$('#source-filter').addEventListener('change',renderRecords); $('#record-filter').addEventListener('input',renderRecords);
$('#passing-only').addEventListener('change',renderChemistry);
$('#refresh-model-bench').addEventListener('click',task(refreshModelBench));
$('#chemistry-run').addEventListener('change',task(async event => {
  const area = selected, loaded = await getRun(event.target.value);
  if (selected !== area) return;
  chemistryRun = loaded;
  if (loaded.result?.molecules?.[0]) setReference(loaded.result.molecules[0]);
  renderChemistry();
}));
$('#search-form').addEventListener('submit',task(async event => { event.preventDefault(); await submitJob({kind:'search',query:$('#query').value,limit:Number($('#limit').value),providers:$$('#providers input:checked').map(n => n.value)}); }));
$('#campaign-select').addEventListener('change',task(async event => { selectedCampaignId = event.target.value || null; $('#link-campaign').checked = false; renderCampaign(); }));
$('#new-campaign').addEventListener('click',() => { selectedCampaignId = null; renderCampaign(); $('#campaign-form [name=title]').focus(); });
$('#campaign-starter').addEventListener('change',event => {
  const starter = (workspace.campaign_starters?.[selected] || []).find(item => item.id === event.target.value);
  if (!starter) return;
  selectedCampaignId = null; $('#link-campaign').checked = false;
  renderCampaign();
  const form = $('#campaign-form');
  for (const name of ['title','target','species','tissue','hypothesis','endpoint','falsifier','evidence_stage','study_design','reference_url','structure_notes']) form.elements[name].value = starter[name] || '';
  form.elements.starter_id.value = starter.id;
  renderEvidenceAxes(null,starter.evidence || []);
  $('#campaign-starter').value = starter.id;
  updateCampaignLink();
  notice('Reference campaign loaded. Verify its source methods and adapt the hypothesis before saving.');
});
$('#link-campaign').addEventListener('change',() => {
  if ($('#link-campaign').checked && !campaignById()) $('#link-campaign').checked = false;
});
$('#campaign-form').addEventListener('submit',task(async event => { event.preventDefault(); await saveCampaign(); }));
$('#docking-form').addEventListener('submit',task(async event => {
  event.preventDefault();
  if (!campaignById()) throw new Error('Save a target campaign before docking.');
  const values = Object.fromEntries(new FormData(event.target));
  await saveCampaign();
  await submitJob({kind:'docking',campaign_id:selectedCampaignId,...values,exhaustiveness:Number(values.exhaustiveness),num_modes:Number(values.num_modes),cpu:Number(values.cpu),seed:Number(values.seed)});
}));
$('#compound-form').addEventListener('submit',task(async event => { event.preventDefault(); chemistryRun = null; $('#reference-smiles').value = ''; await submitJob({kind:event.submitter.value,name:$('#compound-name').value,threshold:Number($('#threshold').value)}); }));
$('#variant-form').addEventListener('submit',task(async event => { event.preventDefault(); await submitJob({kind:'variants',smiles:$('#reference-smiles').value,max_mw:Number($('#max-mw').value),max_tpsa:Number($('#max-tpsa').value)}); }));
$('#compare-form').addEventListener('submit',task(async event => { event.preventDefault(); await submitJob({kind:'compare',smiles:$('#reference-smiles').value,candidate:$('#candidate-smiles').value}); }));
$('#conformer-form').addEventListener('submit',task(async event => { event.preventDefault(); await submitJob({kind:'conformers',smiles:$('#reference-smiles').value,conformers:Number($('#conformer-count').value),seed:Number($('#seed').value)}); }));
$('#blueprint-form').addEventListener('submit',task(async event => { event.preventDefault(); const saved = await api('/api/blueprints',{...Object.fromEntries(new FormData(event.target)),id:selected}); await refresh(); areaNavigation(); $('#area-title').textContent = saved.title; $('#area-question').textContent = saved.question; $('#area-category').textContent = saved.area; $('#query').value = saved.query; notice('Blueprint saved.'); }));
$('#note-form').addEventListener('submit',task(async event => { event.preventDefault(); await api('/api/notes',{...Object.fromEntries(new FormData(event.target)),blueprint_id:selected}); event.target.reset(); await refresh(); notice('Observation saved with its source type and review status.'); }));
$('#new-blueprint').addEventListener('click',task(async () => { const item = await api('/api/blueprints',{title:'Untitled research blueprint',area:'Open exploration'}); workspace = await api('/api/state'); selected = item.id; chemistryRun = null; await renderArea(); switchTab('blueprint'); $('#blueprint-form [name=title]').select(); }));
$('#export').addEventListener('click',task(async () => {
  const includeNotes = $('#include-notes').checked;
  const response = await fetch(`/api/export/${encodeURIComponent(selected)}.zip?include_notes=${includeNotes ? '1' : '0'}`);
  if (!response.ok) { const detail = await response.json(); throw new Error(detail.error || `Export failed (${response.status})`); }
  const url = URL.createObjectURL(await response.blob()), a = el('a'); a.href = url; a.download = `regen-${selected}-dossier.zip`; a.click();
  setTimeout(() => URL.revokeObjectURL(url),1000);
  notice(includeNotes ? 'Dossier archive downloaded with manual notes included.' : 'Dossier archive downloaded. Manual notes were excluded.');
}));

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
        if (!['search','docking'].includes(run.kind) && ['complete','partial'].includes(run.status)) {
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
