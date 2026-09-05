(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);

  function install() {
    const list = $('sjListView');
    if (!list || $('matchingDiagnostics')) return false;
    const card = document.createElement('details');
    card.id = 'matchingDiagnostics';
    card.className = 'card';
    card.style.marginBottom = '14px';
    card.innerHTML = `
      <summary style="cursor:pointer;font-weight:800">Why was a job missed?</summary>
      <div class="hint" style="margin:8px 0 14px">Paste a public vacancy URL. Bert fetches available details, replays every matching gate and can retain the example as a regression benchmark.</div>
      <div class="form-grid">
        <div class="field"><label for="mdSearchJob">Search job</label><select id="mdSearchJob"></select></div>
        <div class="field"><label for="mdUrl">Public job URL</label><input id="mdUrl" type="url" placeholder="https://company.example/jobs/123"></div>
        <div class="field"><label for="mdTitle">Title (optional)</label><input id="mdTitle" placeholder="Filled from the page when possible"></div>
        <div class="field"><label for="mdCompany">Company (optional)</label><input id="mdCompany"></div>
        <div class="field"><label for="mdLocation">Location (optional)</label><input id="mdLocation"></div>
        <div class="field full"><label for="mdDescription">Description (optional)</label><textarea id="mdDescription" placeholder="Paste the text if the source blocks automatic detail retrieval"></textarea></div>
      </div>
      <div class="actions">
        <button class="btn primary" type="button" id="mdAnalyze">Analyze matching</button>
        <label><input id="mdSave" type="checkbox"> Keep as benchmark</label>
        <select id="mdExpected" aria-label="Expected benchmark decision"><option value="true">Should match</option><option value="false">Should not match</option></select>
        <button class="btn" type="button" id="mdRunBenchmarks">Run saved benchmarks</button>
        <button class="btn" type="button" id="mdQuality">Source & query quality</button>
        <span id="mdStatus" class="status"></span>
      </div>
      <div id="mdResult" style="margin-top:14px"></div>`;
    const summary = list.querySelector('.sj-summary');
    (summary?.parentNode || list).insertBefore(card, summary?.nextSibling || list.firstChild);
    $('mdAnalyze').onclick = analyze;
    $('mdRunBenchmarks').onclick = runBenchmarks;
    $('mdQuality').onclick = loadQuality;
    refreshJobs();
    return true;
  }

  async function refreshJobs() {
    try {
      const data = await api('/api/search-jobs');
      $('mdSearchJob').innerHTML = (data.search_jobs || []).map(job =>
        `<option value="${job.id}">${esc(job.name)} · ${esc(job.profile_name)}</option>`
      ).join('');
    } catch (error) {
      if ($('mdStatus')) $('mdStatus').textContent = error.message;
    }
  }

  function stageMarkup(stage) {
    const tone = stage.passed ? 'ok' : 'error';
    return `<div style="padding:9px 0;border-bottom:1px solid var(--line)"><b class="${tone}">${stage.passed ? 'PASS' : 'STOP'} · ${esc(stage.stage)}</b><div class="hint">${esc(stage.detail || '')}${stage.score !== undefined ? ` · ${stage.score}/${stage.threshold}` : ''}</div></div>`;
  }

  async function analyze() {
    const id = Number($('mdSearchJob').value);
    if (!id || !$('mdUrl').value.trim()) return;
    $('mdStatus').textContent = 'Analyzing…';
    $('mdResult').innerHTML = '';
    try {
      const result = await api(`/api/search-jobs/${id}/diagnose`, {
        method: 'POST',
        body: JSON.stringify({
          url: $('mdUrl').value.trim(), title: $('mdTitle').value.trim(),
          company: $('mdCompany').value.trim(), location: $('mdLocation').value.trim(),
          description: $('mdDescription').value.trim(), fetch_details: true,
          save_benchmark: $('mdSave').checked, expected_relevant: $('mdExpected').value === 'true'
        })
      });
      $('mdStatus').textContent = result.eligible ? 'Recommended' : `Stopped at ${result.first_failure}`;
      $('mdStatus').className = `status ${result.eligible ? 'ok' : 'error'}`;
      const facts = result.facts || {};
      $('mdResult').innerHTML = `
        <div class="sj-summary"><div class="card"><span class="muted">Decision</span><strong>${result.eligible ? 'Match' : 'Excluded'}</strong></div><div class="card"><span class="muted">Overall fit</span><strong>${result.scores.overall}</strong></div><div class="card"><span class="muted">Working time</span><strong style="font-size:16px">${esc(facts.employment_type || 'unknown')}</strong></div></div>
        <div class="card" style="box-shadow:none"><b>${esc(result.summary)}</b>${result.detail_fetch_error ? `<div class="warning" style="margin-top:10px">Detail fetch: ${esc(result.detail_fetch_error)}</div>` : ''}<div style="margin-top:10px">${(result.stages || []).map(stageMarkup).join('')}</div></div>`;
    } catch (error) {
      $('mdStatus').textContent = error.message;
      $('mdStatus').className = 'status error';
    }
  }

  async function runBenchmarks() {
    const id = Number($('mdSearchJob').value);
    if (!id) return;
    $('mdStatus').textContent = 'Running benchmarks…';
    try {
      const result = await api(`/api/search-jobs/${id}/benchmarks/run`, {method: 'POST', body: '{}'});
      const pct = value => value == null ? '—' : `${Math.round(value * 100)}%`;
      $('mdStatus').textContent = `${result.total} examples · precision ${pct(result.precision)} · recall ${pct(result.recall)} · ${result.failures.length} failures`;
      $('mdStatus').className = `status ${result.failures.length ? 'warning' : 'ok'}`;
    } catch (error) {
      $('mdStatus').textContent = error.message;
      $('mdStatus').className = 'status error';
    }
  }

  async function loadQuality() {
    const id = Number($('mdSearchJob').value);
    if (!id) return;
    try {
      const result = await api(`/api/search-jobs/${id}/quality`);
      const rows = (label, items) => `<h3>${label}</h3><div class="table-wrap"><table><thead><tr><th>Name</th><th>Fetched</th><th>Recommended</th><th>New</th><th>Yield</th><th>Status</th></tr></thead><tbody>${items.map(item => `<tr><td>${esc(item.source || item.query)}</td><td>${item.fetched}</td><td>${item.recommended}</td><td>${item.new_matches}</td><td>${item.quality_pct}%</td><td>${esc((item.status || '').replaceAll('_', ' '))}</td></tr>`).join('') || '<tr><td colspan="6">No completed runs yet.</td></tr>'}</tbody></table></div>`;
      $('mdResult').innerHTML = rows('Source quality', result.sources || []) + rows('Query quality', result.queries || []);
      $('mdStatus').textContent = 'Quality report loaded';
      $('mdStatus').className = 'status ok';
    } catch (error) {
      $('mdStatus').textContent = error.message;
      $('mdStatus').className = 'status error';
    }
  }

  if (!install()) {
    let attempts = 0;
    const timer = setInterval(() => { if (install() || ++attempts > 30) clearInterval(timer); }, 100);
  }
})();
