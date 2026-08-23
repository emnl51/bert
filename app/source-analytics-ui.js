(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function ensurePanel(){
    const runs = $('runs');
    if(!runs || $('sourceAnalyticsPanel')) return;
    const wrap = document.createElement('div');
    wrap.id='sourceAnalyticsPanel';
    wrap.innerHTML = `
      <div class="section-title"><div><h2>Source Analytics</h2><div class="hint">Source quality across recent runs: fetched → unique → Job Fit → Language Fit → recommended → new.</div></div><button class="btn" onclick="loadSourceAnalytics()">Refresh analytics</button></div>
      <div class="table-wrap"><table><thead><tr><th>Source</th><th>Runs</th><th>Fetched</th><th>Unique</th><th>Job Fit</th><th>Language Fit</th><th>Recommended</th><th>New</th><th>Provider filters</th><th>Quality</th></tr></thead><tbody id="sourceAnalyticsBody"></tbody></table></div>`;
    runs.prepend(wrap);
  }

  window.loadSourceAnalytics = async function(){
    ensurePanel();
    const body=$('sourceAnalyticsBody'); if(!body) return;
    try{
      const d=await api('/api/source-analytics?last_runs=20');
      const rows=d.summary||[];
      body.innerHTML=rows.length?rows.map(r=>{const filters=Number(r.provider_raw)>0?`<b>${r.provider_raw} → ${r.provider_accepted}</b><div class="hint">duplicate ${r.provider_duplicates} · inactive ${r.filtered_inactive} · old ${r.filtered_stale} · work time ${r.filtered_arrangement} · outside area ${r.filtered_location}</div>`:'<span class="muted">—</span>';return `<tr><td><b>${esc(r.source)}</b></td><td>${r.runs}</td><td>${r.fetched}</td><td>${r.unique_jobs}</td><td>${r.job_fit}</td><td>${r.language_fit}</td><td>${r.recommended}</td><td>${r.new_matches}</td><td>${filters}</td><td><b>${r.quality_pct}%</b><div class="hint">new ${r.new_yield_pct}% · dedupe ${r.dedupe_pct}%</div></td></tr>`}).join(''):'<tr><td colspan="10" class="muted">No source analytics yet. Run a search first.</td></tr>';
    }catch(e){ body.innerHTML=`<tr><td colspan="10" class="error">${esc(e.message)}</td></tr>`; }
  };

  const boot=()=>{ensurePanel(); loadSourceAnalytics();};
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',boot); else boot();
})();
