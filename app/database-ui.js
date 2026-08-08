(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[c]));

  function install(){
    const nav=document.querySelector('.nav'); const main=document.querySelector('.main');
    if(!nav||!main) return setTimeout(install,100);
    if($('database')) return;
    const btn=document.createElement('button'); btn.dataset.tab='database'; btn.textContent='Database'; nav.appendChild(btn);
    btn.addEventListener('click',()=>{document.querySelectorAll('.nav button').forEach(b=>b.classList.remove('active'));btn.classList.add('active');document.querySelectorAll('.section').forEach(s=>s.classList.remove('active'));$('database').classList.add('active');$('pageTitle').textContent='Database';loadDatabaseStatus();});
    const section=document.createElement('section'); section.id='database'; section.className='section'; section.innerHTML=`
      <div class="warning"><b>Destructive actions.</b> Every reset can permanently remove data. Backups are enabled by default, and Factory Reset always creates one.</div>
      <div class="grid" id="dbMetrics"></div>
      <div class="section-title"><div><h2>Reset options</h2><div class="hint">Configuration such as sources, API settings, profiles and schedules is preserved unless you choose Factory Reset.</div></div></div>
      <div class="two">
        <div class="card"><h3>Jobs & Applications</h3><p class="muted">Deletes stored jobs, decisions, application tracker records and job-linked analysis/feedback.</p><button class="btn danger" onclick="resetDb('jobs')">Reset jobs</button></div>
        <div class="card"><h3>Run History & Analytics</h3><p class="muted">Deletes search run history, source funnel analytics and per-search-job run records.</p><button class="btn danger" onclick="resetDb('runs')">Reset runs</button></div>
        <div class="card"><h3>Learning Data</h3><p class="muted">Deletes learned negative/positive rules and feedback history without deleting jobs.</p><button class="btn danger" onclick="resetDb('learning')">Reset learning</button></div>
        <div class="card"><h3>AI / Intelligence</h3><p class="muted">Deletes stored CV/job intelligence analyses. Candidate profiles remain.</p><button class="btn danger" onclick="resetDb('intelligence')">Reset intelligence</button></div>
        <div class="card"><h3>All Operational Data</h3><p class="muted">Clears jobs, applications, run history, analytics, learning and intelligence while preserving configuration.</p><button class="btn danger" onclick="resetDb('operational')">Reset operational data</button></div>
        <div class="card" style="border-color:#fecaca"><h3 style="color:#b42318">Factory Reset</h3><p class="muted">Clears the entire database including sources, API settings, profiles, candidates, schedules and history, then recreates defaults.</p><button class="btn danger" onclick="resetDb('factory')">Factory reset</button></div>
      </div>
      <div class="card" style="margin-top:16px"><h3 style="margin-top:0">Database details</h3><div id="dbDetails" class="mono muted">Loading…</div></div>`;
    main.appendChild(section);
  }

  window.loadDatabaseStatus=async function(){
    try{
      const d=await api('/api/database/status'); const c=d.counts||{};
      const sum=names=>names.reduce((n,k)=>n+(Number(c[k])||0),0);
      if($('dbMetrics')) $('dbMetrics').innerHTML=`<div class="card"><div class="muted">Jobs</div><div class="metric">${Number(c.jobs||0)}</div></div><div class="card"><div class="muted">Applications</div><div class="metric">${Number(c.applications||0)}</div></div><div class="card"><div class="muted">Runs</div><div class="metric">${sum(['search_runs','search_job_runs'])}</div></div><div class="card"><div class="muted">DB tables</div><div class="metric">${Number(d.tables||0)}</div></div>`;
      if($('dbDetails')) $('dbDetails').innerHTML=`Path: ${esc(d.database_path)}<br>${Object.entries(c).sort().map(([k,v])=>`${esc(k)}: ${v}`).join('<br>')}`;
      return d;
    }catch(e){toast(e.message,true);throw e}
  };

  function clearStaleOperationalViews(scope){
    if(!['jobs','operational','factory'].includes(scope)) return;
    const review=$('jobReviewGrid'); if(review) review.innerHTML='<div class="card muted">No jobs loaded.</div>';
    const jobs=$('jobsBody'); if(jobs) jobs.innerHTML='<tr><td colspan="8" class="muted">No jobs loaded.</td></tr>';
    const apps=$('applicationsBody'); if(apps) apps.innerHTML='<tr><td colspan="9" class="muted">No applications.</td></tr>';
    ['mJobs','mReviewed','mToApply','mInterviews','mOffers','aToApply','aApplied','aInterview','aOffer'].forEach(id=>{if($(id))$(id).textContent='0'});
  }

  async function callIf(name){
    const fn=window[name];
    if(typeof fn!=='function') return;
    try{return await fn()}catch(e){console.warn(`Post-reset refresh failed: ${name}`,e)}
  }

  async function refreshAfterReset(scope){
    if(scope==='factory'){
      window.activeProfileId=null;
      try{localStorage.removeItem('jobtrack-profile')}catch(_){ }
    }
    // Do not call the legacy refreshAll here. Newer UI modules replace some legacy DOM controls.
    // Refresh each modern surface independently so one optional panel cannot block the others.
    const tasks=['loadOverview','loadApplications','loadRuns','loadSources','loadSettings','loadProfiles','loadSearchJobs','loadDatabaseStatus'];
    for(const name of tasks) await callIf(name);
    if(typeof window.loadReviewProfiles==='function') await callIf('loadReviewProfiles');
    if(typeof window.loadReviewJobs==='function') await callIf('loadReviewJobs');
    if($('learning')?.classList.contains('active')) await callIf('loadLearning');
    if(typeof window.loadSourceAnalytics==='function') await callIf('loadSourceAnalytics');
  }

  window.resetDb=async function(scope){
    const factory=scope==='factory';
    const warning=factory?'This will erase ALL JobTrack database content and restore defaults.':'This will permanently delete the selected database records.';
    if(!confirm(`${warning}\n\nA database backup will be created first. Continue?`)) return;
    const phrase=factory?'FACTORY RESET JOBTRACK':'RESET JOBTRACK';
    const typed=prompt(`Type exactly:\n${phrase}`,'');
    if(typed!==phrase){toast('Reset cancelled: confirmation text did not match.',true);return;}
    try{
      const result=await api('/api/database/reset',{method:'POST',body:JSON.stringify({scope,confirmation:typed,create_backup:true})});
      if(!result.verified) throw new Error('Reset returned without verification.');
      if(['jobs','operational','factory'].includes(scope) && Number(result.after?.jobs||0)!==0) throw new Error(`Reset verification failed: ${result.after.jobs} jobs remain.`);
      clearStaleOperationalViews(scope);
      toast(`Reset complete and verified: ${result.rows_deleted} rows deleted. Backup: ${result.backup_path}`);
      await refreshAfterReset(scope);
      if(factory) alert('Factory reset completed. Default profiles/sources/schedule were recreated. Review settings before the next search.');
    }catch(e){toast(e.message,true)}
  };

  install();
})();
