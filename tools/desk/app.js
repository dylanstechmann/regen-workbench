'use strict';
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
let workspace, selected = 'reprogramming', activeTab = 'evidence', chemistryRun = null, selectedCampaignId = null;
let runPage = 0, runPageSize = 50, historyRuns = [], historyTotal = 0;
const runCache = new Map();
let experimentRecords = [];
let modelArtifactState = null;
const trajectoryCache = new Map();
const sweepMetricOptions = [
  ['median_prospective_forecast_rmse','Forward forecast RMSE'],
  ['median_prospective_forecast_baseline_rmse','Last-reading baseline RMSE'],
  ['median_prospective_forecast_coverage_95','Approx. 95% interval coverage'],
  ['median_prospective_forecast_interval_width_95','Approx. 95% interval width'],
  ['median_cross_replicate_holdout_fixture_scale_rmse','Leave-one-seed-out balance residual (not forecast)'],
  ['median_temporal_holdout_fixture_scale_rmse','Same-run balance residual (not forecast)'],
  ['median_design_condition_number','Balance-regression condition number'],
];
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
    $('#model-bench-comparison').hidden = true;
    status.replaceChildren(badge('Reports have not been loaded','unreviewed'));
    $('#model-bench-count').textContent = '';
    return;
  }
  const verified = (state.bundles || []).filter(bundle => bundle.verified === true);
  $('#model-bench-count').textContent = verified.length ? String(verified.length) : '';
  status.replaceChildren(badge(state.available ? `${verified.length} hash-matched bundles` : 'Sibling artifact folder not mounted',state.available ? 'complete' : 'unreviewed'),el('span',state.message || ''));
  renderModelBenchComparison(verified);
  if (!state.bundles?.length) {
    container.append(el('p',state.available
      ? 'No recognized receipt-bearing reports are available yet. Generate an evidence, simulation, identifiability, design-sweep, or transport-verification bundle in artificial-womb-models/artifacts, then refresh.'
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
      const stateModel = summary.noise_aware_state_model || {};
      const forecast = stateModel.prospective_forecast || {};
      const stateFit = stateModel.full_series_fit || {};
      if (forecast.prediction_interval_available === false && forecast.prediction_interval_reason) {
        card.append(el('p',`Forecast uncertainty: ${forecast.prediction_interval_reason}`,'boundary'));
      }
      card.append(el('p',`Forward forecast: ${forecast.estimable ? `${forecast.n_training_readings} prefix readings trained through time ${modelNumber(forecast.split_time)}; ${forecast.n_scored_readings} later readings scored · RMSE ${modelNumber(forecast.fixture_scale_rmse)} vs last-reading baseline ${modelNumber(forecast.baseline_last_observation_rmse)} · 95% interval coverage ${modelNumber(forecast.coverage_95)}` : (forecast.reason || 'not estimable')}.`,'model-bench-metric'));
      card.append(el('p',`Noise-aware state fit: ${stateFit.estimable ? `powered input ${modelNumber(stateFit.parameters?.powered_input)} · conversion ${modelNumber(stateFit.parameters?.conversion)} · assumed sensor noise SD ${modelNumber(stateFit.sensor_noise_sd_assumed)}` : (stateFit.reason || 'not estimable')}. ${early.estimable ? `Legacy balance fit: rank ${early.rank}, condition ${modelNumber(early.normalized_design_condition_number)}.` : ''} The balance residual uses endpoint readings inside its predictors, so it is a same-run consistency diagnostic, not a forecast.`,'boundary'));
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
      card.append(el('p',`The primary forecast trains on scheduled, unbiased readings through 70% of elapsed dimensionless duration, propagates the fitted state forward without later readings, and compares with a last-reading baseline. The older balance residual uses endpoint readings in its predictors and is shown only as a consistency diagnostic. Seeded runs share one generated fixture, so these are software sensitivity results. ${faultBoundary} ${timingBoundary}`,'boundary'));
      const fields = el('div',null,'model-bench-sweep-controls');
      const faultSelect = el('select'); faultSelect.setAttribute('aria-label','Filter monitor-fault profile');
      [...new Set(designSummaries.map(item=>item.monitor_fault_profile || 'not reported'))].forEach(value=>{const option=el('option',value);option.value=value;faultSelect.append(option);});
      const timingSelect = el('select'); timingSelect.setAttribute('aria-label','Filter event-timing profile');
      [...new Set(designSummaries.map(item=>item.event_timing_profile || 'not reported'))].forEach(value=>{const option=el('option',value);option.value=value;timingSelect.append(option);});
      const metricSelect = el('select'); metricSelect.setAttribute('aria-label','Sweep metric');
      sweepMetricOptions.forEach(([value,label])=>{const option=el('option',label);option.value=value;metricSelect.append(option);});
      for (const [label,control] of [['Monitor-fault profile',faultSelect],['Event timing',timingSelect],['Metric',metricSelect]]) { const wrapper=el('label',label);wrapper.append(control);fields.append(wrapper); }
      card.append(fields);
      const matrixContainer = el('div',null,'model-bench-sweep-matrix');
      const drawMatrix = () => {
        const filtered=designSummaries.filter(item=>(item.monitor_fault_profile || 'not reported')===faultSelect.value&&(item.event_timing_profile || 'not reported')===timingSelect.value);
        const byCell=new Map(filtered.map(item=>[`${item.cadence_factor_requested}|${item.noise_multiplier_requested}`,item]));
        const cadences=[...new Set(filtered.map(item=>item.cadence_factor_requested))].sort((a,b)=>a-b);
        const noises=[...new Set(filtered.map(item=>item.noise_multiplier_requested))].sort((a,b)=>a-b);
        const metric=metricSelect.value, values=filtered.map(item=>item[metric]).filter(value=>typeof value==='number'&&Number.isFinite(value));
        const low=values.length?Math.min(...values):0, high=values.length?Math.max(...values):0;
        const table=el('table',null,'model-bench-sweep-table'), header=el('tr');header.append(el('th','Cadence × baseline step'));
        noises.forEach(noise=>header.append(el('th',`${modelNumber(noise)}× noise`)));table.append(header);
        for(const cadence of cadences){const row=el('tr');row.append(el('th',`${modelNumber(cadence)}× cadence · step ${modelNumber(filtered.find(item=>item.cadence_factor_requested===cadence)?.actual_output_step)}`));for(const noise of noises){const item=byCell.get(`${cadence}|${noise}`),cell=el('td');if(!item){cell.textContent='—';}else{const value=item[metric];cell.textContent=`${modelNumber(value)}\n${item.prospective_forecast_estimable_replicates ?? item.cross_replicate_holdout_estimable_replicates ?? item.temporal_holdout_estimable_replicates ?? '—'} / ${item.replicates ?? '—'} estimable`;if(typeof value==='number'&&Number.isFinite(value)){const t=high===low?0.5:(value-low)/(high-low);cell.style.backgroundColor=`hsl(${125-115*t} 36% 91%)`;}}row.append(cell);}table.append(row);}
        matrixContainer.replaceChildren(table);
      };
      for(const select of [faultSelect,timingSelect,metricSelect])select.addEventListener('change',drawMatrix);
      drawMatrix();card.append(matrixContainer);
    } else if (bundle.bundle_kind === 'dimensionless_transport_theory' || bundle.bundle_kind === 'dimensionless_mechanics_theory') {
      const outputs=summary.outputs || {}, alternative=summary.alternative_model || {};
      const context=summary.stage_context || {};
      card.append(el('p',`${summary.result_kind || 'Dimensionless theory fixture'} · context tags ${context.species || 'unspecified'} / ${context.stage_track || 'unspecified'} / ${context.interval_label || 'unassigned'}. These tags organize questions and do not calibrate the equations to a biological system.`));
      card.append(el('p',`Fixture outputs: ${Object.entries(outputs).map(([key,value])=>`${key.replaceAll('_',' ')} ${modelNumber(value)}`).join(' · ') || 'report contains no scalar output fields'}`,'model-bench-metric'));
      card.append(el('p',`Alternative: ${alternative.name || 'reported comparator'} · ${alternative.equation || 'equation recorded in report'} · ${alternative.comparison_scope || 'theoretical comparison only'}`,'boundary'));
      const assumptions=el('details',null,'model-bench-limitations');assumptions.append(el('summary','Model assumptions'));const list=el('ul');(summary.assumptions || []).slice(0,12).forEach(item=>list.append(el('li',String(item).slice(0,1200))));assumptions.append(list);card.append(assumptions);
    } else if (bundle.bundle_kind === 'dimensionless_transport_numerical_verification') {
      card.append(el('p',`${summary.n_refinement_levels ?? '—'} forward-Euler step sizes · ${summary.n_total_timepoints ?? '—'} total timepoints compared with a closed-form two-state reference.`));
      const method=(summary.reference_method || 'Reference method not recorded').replace(/[.!?]+$/,'');
      card.append(el('p',`${method}. All errors and time values are dimensionless numerical diagnostics for this fixture.`,'boundary'));
      const table=el('table',null,'model-bench-verification-table'),header=el('tr');
      for(const label of ['Step factor','Requested step','Actual max step','Max state error','State RMSE','Observed order'])header.append(el('th',label));
      const thead=el('thead');thead.append(header);const body=el('tbody');
      for(const item of summary.convergence || []){
        const row=el('tr');
        for(const value of [modelNumber(item.refinement_factor),modelNumber(item.requested_step),modelNumber(item.actual_max_step),modelNumber(item.max_abs_state_error),modelNumber(item.state_rmse),modelNumber(item.observed_order)])row.append(el('td',value));
        body.append(row);
      }
      table.append(thead,body);card.append(table);
    } else if (bundle.bundle_kind === 'dimensionless_transport_parameter_matrix_numerical_verification') {
      const method=(summary.reference_method || 'Reference method not recorded').replace(/[.!?]+$/,'');
      card.append(el('p',`${summary.n_scenarios ?? '—'} deterministic rate regimes · ${summary.n_refinement_levels ?? '—'} refinement levels · ${summary.n_total_timepoints ?? '—'} total dimensionless timepoints.`));
      card.append(el('p',`${method}. Each curve compares forward Euler with the same closed-form two-state reference; profiles are software stress cases, not biological parameter estimates.`,'boundary'));
      const table=el('table',null,'model-bench-verification-table'),header=el('tr');
      for(const label of ['Regime','Exchange','Transfer','Loss','Requested step','Stability product','Finest max error'])header.append(el('th',label));
      const thead=el('thead');thead.append(header);const body=el('tbody');
      for(const item of summary.scenarios || []){
        const row=el('tr'),rates=item.rates || {};
        for(const value of [item.name,modelNumber(rates.boundary_exchange),modelNumber(rates.intercompartment_transport),modelNumber(rates.loss),modelNumber(item.requested_step),modelNumber(item.stability_product),modelNumber(item.finest_max_abs_state_error)])row.append(el('td',value));
        body.append(row);
      }
      table.append(thead,body);card.append(table);
    } else if (bundle.bundle_kind === 'dimensionless_mechanics_numerical_verification') {
      const method=(summary.reference_method || 'Reference method not recorded').replace(/[.!?]+$/,'');
      const errors=summary.errors || {};
      card.append(el('p',`${summary.n_timepoints ?? '—'} timepoints · ${summary.n_load_boundaries ?? '—'} load boundaries compared with a closed-form reference.`));
      card.append(el('p',`${method}. Maximum scaled error ${modelNumber(summary.maximum_scaled_error)} against tolerance ${modelNumber(summary.relative_tolerance)}; ${summary.verification_passed ? 'verification passed' : 'verification status unavailable'}. All values are dimensionless software diagnostics.`,'boundary'));
      const table=el('table',null,'model-bench-verification-table'),header=el('tr');
      for(const label of ['Maximum absolute error','RMSE','Maximum boundary error'])header.append(el('th',label));
      const row=el('tr');
      for(const value of [modelNumber(errors.max_absolute),modelNumber(errors.rmse),modelNumber(errors.max_boundary_absolute)])row.append(el('td',value));
      const thead=el('thead');thead.append(header);const body=el('tbody');body.append(row);
      table.append(thead,body);card.append(table);
    }
    if (Array.isArray(summary.limitations) && summary.limitations.length) {
      const limits=el('details',null,'model-bench-limitations');
      limits.append(el('summary','Limits recorded by this report'));
      const list=el('ul');
      summary.limitations.slice(0,12).forEach(item=>list.append(el('li',String(item).slice(0,2000))));
      limits.append(list); card.append(limits);
    }
    const links = el('div',null,'row model-bench-links');
    const labelsByFile = {"REPORT.md":"Readable report","observability_report.json":"Fit summary","simulation_summary.json":"Simulation summary","evidence_report.json":"Evidence map JSON","design_sweep_report.json":"Sweep summary JSON","transport_report.json":"Transport theory JSON","mechanics_report.json":"Mechanics theory JSON","numerical_verification_report.json":"Numerical verification JSON","mechanics_verification_report.json":"Mechanics verification JSON","transport_matrix_report.json":"Transport regime matrix JSON","transport_matrix_convergence.csv":"Transport regime convergence table","transport_matrix_scenario_configs.json":"Exact regime configurations","transport_configured_baseline_finest_errors.csv":"Baseline pointwise errors","transport_zero_dynamics_finest_errors.csv":"Zero-dynamics pointwise errors","transport_exchange_only_finest_errors.csv":"Exchange-only pointwise errors","transport_transfer_only_finest_errors.csv":"Transfer-only pointwise errors","transport_unequal_coupled_finest_errors.csv":"Unequal-rate pointwise errors","transport_high_mixing_finest_errors.csv":"High-mixing pointwise errors","transport_near_degenerate_finest_errors.csv":"Near-degenerate pointwise errors","transport_convergence.csv":"Transport error curve","finest_step_trajectory.csv":"Finest-step pointwise errors","mechanics_pointwise_errors.csv":"Mechanics pointwise errors","mechanics_boundary_errors.csv":"Mechanics boundary errors","transport_trajectory.csv":"Transport trajectory","well_mixed_reference.csv":"Single-compartment reference","mechanics_trajectory.csv":"Mechanics trajectory","elastic_reference.csv":"Elastic reference","sweep_plan.json":"Sweep design plan","design_sweep.csv":"Replicate table","design_summaries.csv":"Design summary table","trajectory.csv":"Trajectory","interval_design.csv":"Design intervals","claims.csv":"Claims table","stage_map.csv":"Stage map","requirements.csv":"Requirements"};
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
function renderModelBenchComparison(verified) {
  const panel = $('#model-bench-comparison');
  panel.replaceChildren();
  panel.hidden = true;
  const sweeps = verified.filter(bundle => bundle.bundle_kind === 'synthetic_exchange_design_sweep');
  if (sweeps.length < 2) return;
  panel.hidden = false;
  const title = el('h3','Compare compatible design sweeps');
  title.id = 'model-bench-comparison-title';
  panel.append(title,el('p','Select two receipt-verified reports to compare matching dimensionless design conditions. Input hashes and complete coordinates must match; implementation-hash changes are called out. The difference is B−A between reported medians, with no pooling, model ranking, or biological inference.','boundary'));
  const fields = el('div',null,'model-bench-sweep-controls model-bench-comparison-controls');
  const selectA = el('select'); selectA.setAttribute('aria-label','First design-sweep bundle');
  const selectB = el('select'); selectB.setAttribute('aria-label','Second design-sweep bundle');
  const compatiblePair = (()=>{
    const coordinateSet=bundle=>{
      const rows=bundle.summary?.design_summaries;
      if(!Array.isArray(rows)||!rows.length)return null;
      const keys=rows.map(row=>JSON.stringify([row.cadence_factor_requested,row.noise_multiplier_requested,
        row.monitor_fault_profile,row.event_timing_profile ?? null]));
      return new Set(keys).size===keys.length ? new Set(keys) : null;
    };
    for(let i=0;i<sweeps.length;i++)for(let j=i+1;j<sweeps.length;j++){
      if(sweeps[i].input_sha256!==sweeps[j].input_sha256)continue;
      const left=coordinateSet(sweeps[i]),right=coordinateSet(sweeps[j]);
      if(left&&right&&left.size===right.size&&[...left].every(key=>right.has(key)))return [i,j];
    }
    return null;
  })();
  const initialIndexes=compatiblePair || [0,1];
  for (const [select,index] of [[selectA,initialIndexes[0]],[selectB,initialIndexes[1]]]) {
    sweeps.forEach((bundle,i)=>{const option=el('option',`${bundle.bundle_id} · ${bundle.package_version || 'version not recorded'}`);option.value=bundle.bundle_id;select.append(option);});
    select.selectedIndex = Math.min(index,sweeps.length-1);
  }
  const metric = el('select'); metric.setAttribute('aria-label','Comparison metric');
  sweepMetricOptions.forEach(([value,label])=>{const option=el('option',label);option.value=value;metric.append(option);});
  for (const [label,control] of [['Report A',selectA],['Report B',selectB],['Metric',metric]]) {const wrapper=el('label',label);wrapper.append(control);fields.append(wrapper);}
  const resultPanel=el('div',null,'model-bench-comparison-result');
  panel.append(fields,resultPanel);
  let requestNumber=0;
  const draw=async()=>{
    const thisRequest=++requestNumber;
    resultPanel.replaceChildren(el('p','Rechecking receipts and design coordinates…','boundary'));
    const query=new URLSearchParams({bundle_a:selectA.value,bundle_b:selectB.value,metric:metric.value});
    try {
      const result=await api(`/api/ectogenesis/model-comparison?${query}`);
      if(thisRequest!==requestNumber)return;
      resultPanel.replaceChildren();
      if (!result.compatible) {resultPanel.append(el('p',result.reason || 'These reports cannot be compared.','boundary'));return;}
      const versions=`Report A ${result.bundle_a.bundle_id} (${result.bundle_a.package_version || 'version not recorded'}, ${result.bundle_a.n_synthetic_runs} seeded runs); Report B ${result.bundle_b.bundle_id} (${result.bundle_b.package_version || 'version not recorded'}, ${result.bundle_b.n_synthetic_runs} seeded runs).`;
      resultPanel.append(el('p',`${versions} Implementation hashes ${result.implementation_hashes_match ? 'match' : 'differ'}. Input SHA-256: ${result.input_sha256}.`,'model-bench-id'));
      const table=el('table',null,'model-bench-comparison-table'),head=el('tr');
      for(const label of ['Design condition',`A · ${result.metric_label}`,'A estimable / total',`B · ${result.metric_label}`,'B estimable / total','B − A'])head.append(el('th',label));
      const thead=el('thead');thead.append(head);const body=el('tbody');
      for(const row of result.rows){
        const c=row.coordinate, timing=c.event_timing_profile || 'timing not reported';
        const condition=`${c.monitor_fault_profile} · ${timing} · ${modelNumber(c.cadence_factor_requested)}× cadence · ${modelNumber(c.noise_multiplier_requested)}× noise`;
        const tr=el('tr');
        for(const value of [condition,modelNumber(row.value_a),`${row.estimable_a ?? '—'} / ${row.replicates_a ?? '—'}`,modelNumber(row.value_b),`${row.estimable_b ?? '—'} / ${row.replicates_b ?? '—'}`,modelNumber(row.delta_b_minus_a)])tr.append(el('td',value));
        body.append(tr);
      }
      table.append(thead,body);
      const download=el('button','Download comparison JSON');download.type='button';
      download.addEventListener('click',()=>{
        const record={schema_version:1,generated_at:new Date().toISOString(),application:'regen-workbench ResearchDesk',comparison:result};
        const objectUrl=URL.createObjectURL(new Blob([JSON.stringify(record,null,2)],{type:'application/json'}));
        const link=el('a');link.href=objectUrl;
        link.download=`${result.bundle_a.bundle_id}_vs_${result.bundle_b.bundle_id}_${result.metric}.json`;
        link.click();setTimeout(()=>URL.revokeObjectURL(objectUrl),1000);
      });
      resultPanel.append(table,download,el('p',result.interpretation,'boundary'));
    } catch(error) { if(thisRequest===requestNumber)resultPanel.replaceChildren(el('p',error.message || 'Comparison could not be loaded.','boundary')); }
  };
  for(const control of [selectA,selectB,metric])control.addEventListener('change',draw);
  draw();
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
function renderExperiments(records = experimentRecords) {
  const container = $('#experiment-records');
  if (!container) return;
  experimentRecords = records;
  $('#experiment-count').textContent = records.length || '';
  container.replaceChildren();
  if (!records.length) {
    container.append(el('p','No experiment manifests were found under studies/.','empty'));
    return;
  }
  for (const study of records) {
    const card = el('article',null,'experiment-card');
    const heading = el('div',null,'experiment-heading');
    heading.append(el('div',null),badge(study.validation_status,study.validation_status));
    heading.firstChild.append(el('h3',study.title),el('small',`ID ${study.experiment_id} · ${study.manifest_path}`));
    card.append(heading);
    if (study.validation_status !== 'valid') {
      card.append(el('p',study.validation_error || 'Manifest could not be validated.','boundary'));
      container.append(card); continue;
    }
    card.append(el('p',study.question),el('p',study.model_system),el('p',study.claim_boundary,'boundary'));
    const units = study.design?.donor_structure || {};
    const unitSummary = el('p',`Independent donor counts · disease: ${units.disease_donor_count ?? 'unknown'} · healthy: ${units.healthy_donor_count ?? 'unknown'} · observation-level IDs: ${units.observation_level_ids_available ? 'available' : 'unavailable'}`,'experiment-units');
    card.append(unitSummary);
    if (study.developmental_context) {
      const context=study.developmental_context;
      const developmental=el('div',null,'experiment-developmental-context');
      developmental.append(el('h4','Species and developmental context'),el('p',`${context.species.replaceAll('_',' ')} · ${context.stage_track.replaceAll('_',' ')} · ${context.interval_label} · ${context.interval_kind.replaceAll('_',' ')}`),el('p',context.notes,'boundary'));
      card.append(developmental);
    }
    const assays = el('div',null,'experiment-assays');
    assays.append(el('h4','Assay inventory'));
    if (study.assays?.length) {
      const table = el('table'), header = el('tr');
      ['Status','Assay','Endpoint','Unit','Experimental unit','Source n'].forEach(label => header.append(el('th',label)));
      table.append(header);
      for (const assay of study.assays) {
        const row = el('tr');
        const assayStatus = assay.status || 'measured';
        const statusCell = el('td'); statusCell.append(badge(assayStatus,assayStatus === 'measured' ? 'complete' : 'unreviewed'));
        row.append(statusCell);
        [assay.name,assay.endpoint,assay.unit,assay.experimental_unit,assay.source_n].forEach(value => row.append(el('td',value)));
        table.append(row);
        if (assay.notes) {
          const notes = el('tr'), cell = el('td',assay.notes,'boundary'); cell.colSpan = 6;
          notes.append(cell); table.append(notes);
        }
      }
      assays.append(table);
    } else assays.append(el('p','No assay entries.','empty'));
    card.append(assays);
    const outcomes = el('div',null,'experiment-outcomes');
    outcomes.append(el('h4','Function, identity, viability, genome stability, adverse effects, and durability'));
    for (const endpoint of study.validation_endpoints || []) {
      const row = el('div',null,'experiment-outcome');
      row.append(el('strong',endpoint.role.replaceAll('_',' ')),badge(endpoint.status,endpoint.status === 'measured' ? 'complete' : 'unreviewed'));
      if (endpoint.rationale) row.append(el('span',endpoint.rationale));
      if (endpoint.assay_id) row.append(badge(`assay ${endpoint.assay_id}`));
      outcomes.append(row);
    }
    card.append(outcomes);
    const evidence = el('div',null,'experiment-evidence');
    evidence.append(el('h4','Analysis and limitations'));
    if (study.analysis_history?.length) {
      const history=el('div',null,'experiment-analysis-history');
      history.append(el('h4','Analysis run history'));
      const current=study.current_analysis_by_kind || {};
      for (const run of study.analysis_history) {
        const row=el('section',null,'experiment-analysis-run');
        row.append(el('div',null,`${run.kind.replaceAll('_',' ')} · ${run.registered_utc}`),badge(run.status,run.status === 'receipt_verified' ? 'complete' : 'unreviewed'),el('small',`Bundle ${run.bundle_id}`));
        if (current[run.kind] === run.bundle_id) row.append(badge('Current','complete'));
        const outputs=el('div',null,'row experiment-analysis-outputs');
        const artifactById=new Map((study.artifacts || []).map(artifact=>[artifact.id,artifact]));
        for (const id of run.artifact_ids || []) {
          const artifact=artifactById.get(id);
          if (artifact?.previewable) outputs.append(safeLink(artifact.id,`/api/experiment/artifact?experiment_id=${encodeURIComponent(study.experiment_id)}&artifact_id=${encodeURIComponent(id)}`));
        }
        row.append(outputs);history.append(row);
      }
      evidence.append(history);
    }
    const validation = study.modeling?.donor_validation || {};
    evidence.append(badge(`Donor validation: ${validation.status || 'not assessed'}`,validation.status === 'passed' ? 'complete' : 'unreviewed'));
    if (validation.reason) evidence.append(el('p',validation.reason));
    if (validation.success_criterion) evidence.append(el('p',`Prespecified criterion: ${validation.success_criterion}`));
    if (study.modeling?.falsifier) evidence.append(el('p',`Falsifier: ${study.modeling.falsifier}`));
    if (study.summary?.interpretation) evidence.append(el('p',study.summary.interpretation,'boundary'));
    if (study.summary?.tool === 'organoid-phenotyping') {
      const receipt = study.summary;
      const intake = el('div',null,'experiment-evidence');
      intake.append(el('h4','Organoid image-analysis receipt'));
      intake.append(el('p',`Frames indexed: ${receipt.n_manifest_rows ?? 'unknown'} · measured masks: ${receipt.n_measured_frames ?? 'unknown'} · pending annotation: ${receipt.n_pending_annotation_frames ?? 'unknown'} · missing: ${receipt.n_missing_frames ?? 'unknown'} · failed: ${receipt.n_failed_frames ?? 'unknown'}`));
      const tracking = receipt.object_tracking || {};
      intake.append(el('p',`Object tracks: ${tracking.n_tracked_object_trajectories ?? 0} trajectories from ${tracking.status || 'no track map'}. No tracked growth is inferred without reviewed object identities.`,'boundary'));
      evidence.append(intake);
    }
    for (const pilot of study.annotation_pilots || []) {
      const plan = el('div',null,'experiment-evidence');
      plan.append(el('h4','Manual annotation pilot plan'));
      plan.append(el('p',`${pilot.n_unique_frames ?? 'unknown'} selected frames · ${pilot.n_total_tasks ?? 'unknown'} assignments, including ${pilot.n_round2_concealed_repeat_tasks ?? 'unknown'} concealed repeats · ${pilot.n_development_source_groups_represented ?? 'unknown'} development source groups · ${pilot.timepoint_h ?? 'unknown'} h`));
      plan.append(el('p',`Final-test source group excluded: ${pilot.final_test_group_excluded ? 'yes' : 'no'}. This is a worklist only; no masks or biological results have been generated. The full-resolution images remain in the sibling annotation pack.`,'boundary'));
      if (pilot.blinding_limit) plan.append(el('p',pilot.blinding_limit,'boundary'));
      evidence.append(plan);
    }
    for (const review of study.annotation_reviews || []) {
      const audit = el('div',null,'experiment-evidence');
      audit.append(el('h4','Manual mask agreement review'));
      audit.append(el('p',`${review.n_annotated_tasks} tasks annotated · ${review.n_repeat_pairs_scored} concealed repeat pairs scored · ${review.n_repeat_pairs_with_distinct_annotator_ids} pairs used different annotator IDs`));
      audit.append(el('p','Foreground Dice describes segmentation agreement only. It does not establish mask correctness, tissue function, treatment response, or a biological effect. Manual masks still require review.','boundary'));
      evidence.append(audit);
    }
    if (study.summary?.monotone_dose_response_check?.length) {
      const checks = study.summary.monotone_dose_response_check.map(check => `week ${check.week}: ${check.nondecreasing ? 'nondecreasing' : 'not nondecreasing'}`).join(' · ');
      evidence.append(el('p',`Monotonicity check: ${checks}`));
    }
    if (study.summary?.summaries?.length) {
      const measured = el('div',null,'experiment-evidence');
      measured.append(el('h4','Locally recomputed group summaries'));
      measured.append(badge('Descriptive; source workbook values have no vessel IDs','unreviewed'));
      const table = el('table'), header = el('tr');
      ['Group','Week','Source values','Mean','SD'].forEach(label => header.append(el('th',label)));
      table.append(header);
      for (const item of study.summary.summaries) {
        const row = el('tr');
        [item.group,`week ${item.week}`,item.n_source_values,item.mean,item.sd].forEach(value => row.append(el('td',value)));
        table.append(row);
      }
      measured.append(table);
      const author = study.summary.author_reported_model;
      if (author) {
        measured.append(badge(`Author-reported ${author.method || 'analysis'} · not locally refit`,'unreviewed'));
        const comparisons = [];
        if (author.ratio_p_value !== undefined) comparisons.push(`ratio p=${author.ratio_p_value}`);
        if (author.week_p_value !== undefined) comparisons.push(`week p=${author.week_p_value}`);
        const pair = author.reported_pairwise_comparison;
        if (pair) comparisons.push(`${pair.left} vs ${pair.right}, adjusted p=${pair.adjusted_p_value}`);
        if (comparisons.length) measured.append(el('p',comparisons.join(' · ')));
      }
      evidence.append(measured);
    }
    if (study.limitations?.length) {
      const list = el('ul'); study.limitations.forEach(limitation => list.append(el('li',limitation)));
      evidence.append(list);
    }
    card.append(evidence);
    for (const dataTable of study.tables || []) {
      const details = el('details',null,'experiment-table-details');
      details.append(el('summary',`Linked observation table · ${dataTable.total_rows} rows${dataTable.truncated ? ' (first 100 shown)' : ''}`));
      details.append(el('p',`Declared artifact: ${dataTable.artifact_id}. Blank identifiers are shown as “Not reported”; rows remain observations, not independent donors.`,'boundary'));
      const table = el('table'), header = el('tr');
      dataTable.columns.forEach(column => header.append(el('th',column)));
      table.append(header);
      for (const values of dataTable.rows) {
        const row = el('tr');
        dataTable.columns.forEach(column => row.append(el('td',values[column])));
        table.append(row);
      }
      details.append(table); card.append(details);
    }
    const calibration = study.calibration || {};
    if (study.environmental_conditions?.length) {
      const conditions=el('div',null,'experiment-environment');conditions.append(el('h4','Environmental measurements and assumptions'));
      for (const condition of study.environmental_conditions) conditions.append(el('p',`${condition.domain} · ${condition.name}: ${typeof condition.value === 'object' ? JSON.stringify(condition.value) : condition.value} ${condition.unit} · ${condition.status} · source ${condition.source_artifact_id}`));
      card.append(conditions);
    }
    card.append(el('p',`Calibration: ${calibration.status || 'not assessed'} · ${calibration.notes || ''}`,'experiment-calibration'));
    const links = el('div',null,'row experiment-artifacts');
    for (const artifact of study.artifacts || []) {
      if (artifact.previewable && ['raw_assay_data','analysis_output','analysis_code','calibration_record'].includes(artifact.kind)) {
        const link = safeLink(`${artifact.kind.replaceAll('_',' ')} · ${artifact.id}`,`/api/experiment/artifact?experiment_id=${encodeURIComponent(study.experiment_id)}&artifact_id=${encodeURIComponent(artifact.id)}`);
        links.append(link);
      } else if (artifact.uri) links.append(safeLink(artifact.kind.replaceAll('_',' ')+' · source',artifact.uri));
    }
    card.append(links);
    container.append(card);
  }
}
async function refreshExperiments() {
  const button = $('#refresh-experiments');
  if (button) button.disabled = true;
  try {
    const result = await api('/api/experiments');
    renderExperiments(result.experiments || []);
  } finally { if (button) button.disabled = false; }
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
  if (!experimentRecords.length) await refreshExperiments();
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
  const container = $('#campaign-evidence'); container.className='evidence-matrix';container.replaceChildren();
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
const evidenceRecordFields = [
  ['source_type','Source type'],['source_title','Source title'],['source_url','Source URL'],['license','License'],
  ['species','Species / population'],['stage_track','Stage or model track'],['developmental_interval','Developmental interval'],
  ['model_system','Model system'],['comparator','Comparator'],['outcome','Outcome'],['measure','Measure / endpoint'],
  ['value','Reported value'],['unit','Unit / denominator'],['independent_unit','Independent unit'],['sample_size','Reported n'],
  ['follow_up','Follow-up / timepoint'],['status','Source status'],['direction','Interpretation direction'],
  ['dataset_sha256','Dataset SHA-256'],['notes','Design details and limitations'],
];
function renderEvidenceRecords(records=[]) {
  const container=$('#campaign-evidence-records');container.replaceChildren();
  const heading=el('div',null,'evidence-record-heading');heading.append(el('h3','Source-linked observations'),el('p','Keep each source, species, stage, outcome, comparator, reported sample size and independent unit as its own record. Values remain source-reported; this form does not combine them.','boundary'));
  const add=el('button','Add source observation');add.type='button';add.addEventListener('click',()=>renderEvidenceRecords([...collectCampaignEvidenceRecords(),{}]));heading.append(add);container.append(heading);
  const axes=workspace.campaign_frameworks?.[selected] || [];
  for(const record of records){
    const fieldset=el('fieldset',null,'evidence-record');fieldset.dataset.recordId=record.record_id || '';
    const legend=el('legend','Source observation');fieldset.append(legend);
    const axisLabel=el('label','Evidence question');const axis=el('select');axis.dataset.recordField='axis_id';
    for(const item of axes){const option=el('option',item.label);option.value=item.id;axis.append(option);}axis.value=record.axis_id || axes[0]?.id || '';axisLabel.append(axis);fieldset.append(axisLabel);
    const grid=el('div',null,'evidence-record-grid');
    for(const [field,label] of evidenceRecordFields){
      const wrapper=el('label',label);let control;
      if(field==='source_type'){control=el('select');for(const value of ['publication','preprint','dataset','trial_registry','patent','protocol','other']){const option=el('option',value.replaceAll('_',' '));option.value=value;control.append(option);}}
      else if(field==='status'){control=el('select');for(const value of ['not assessed','source reports positive signal','source reports mixed signal','source reports no signal','conflicting sources']){const option=el('option',value);option.value=value;control.append(option);}}
      else if(field==='direction'){control=el('select');for(const value of ['unclear','supports','contradicts','mixed']){const option=el('option',value);option.value=value;control.append(option);}}
      else if(field==='notes'){control=el('textarea');control.rows=2;}
      else{control=el('input');control.type=field==='source_url'?'url':'text';}
      control.dataset.recordField=field;control.maxLength=(field==='notes'||field==='source_url')?3000:800;control.value=record[field] || (field==='status'?'not assessed':field==='direction'?'unclear':field==='source_type'?'publication':'');wrapper.append(control);grid.append(wrapper);
    }
    fieldset.append(grid);const remove=el('button','Remove source observation');remove.type='button';remove.addEventListener('click',()=>{const remaining=collectCampaignEvidenceRecords();remaining.splice([...container.querySelectorAll('.evidence-record')].indexOf(fieldset),1);renderEvidenceRecords(remaining);});fieldset.append(remove);container.append(fieldset);
  }
}
function collectCampaignEvidenceRecords() {
  return [...$('#campaign-evidence-records').querySelectorAll('.evidence-record')].map(fieldset=>{
    const record={record_id:fieldset.dataset.recordId};
    for(const control of fieldset.querySelectorAll('[data-record-field]'))record[control.dataset.recordField]=control.value.trim();
    return record;
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
  form.elements.experiment_ids.value=(campaign?.experiment_ids || []).join('\n');
  form.elements.model_bundle_ids.value=(campaign?.model_bundle_ids || []).join('\n');
  const starterPicker = $('#campaign-starter'); starterPicker.replaceChildren(el('option','Blank campaign'));
  starterPicker.options[0].value = '';
  for (const starter of workspace.campaign_starters?.[selected] || []) { const option = el('option',starter.title); option.value = starter.id; starterPicker.append(option); }
  starterPicker.value = campaign?.starter_id || '';
  renderEvidenceAxes(campaign);
  renderEvidenceRecords(campaign?.evidence_records || []);
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
  const splitIds=value=>String(value || '').split(/\r?\n/).map(item=>item.trim()).filter(Boolean);
  const saved = await api('/api/campaigns',{...values,experiment_ids:splitIds(values.experiment_ids),model_bundle_ids:splitIds(values.model_bundle_ids),evidence:collectCampaignEvidence(),evidence_records:collectCampaignEvidenceRecords(),id:selectedCampaignId || '',blueprint_id:selected});
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
$('#refresh-experiments').addEventListener('click',task(refreshExperiments));
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
