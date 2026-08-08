(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

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
      $('dbMetrics').innerHTML=`<div class="card"><div class="muted">Jobs</div><div class="metric">${Number(c.jobs||0)}</div></div><div class="card"><div class="muted">Applications</div><div class="metric">${Number(c.applications||0)}</div></div><div class="card"><div class="muted">Runs</div><div class="metric">${sum(['search_runs','search_job_runs'])}</div></div><div class="card"><div class="muted">DB tables</div><div class="metric">${Number(d.tables||0)}</div></div>`;
      $('dbDetails').innerHTML=`Path: ${esc(d.database_path)}<br>${Object.entries(c).sort().map(([k,v])=>`${esc(k)}: ${v}`).join('<br>')}`;
    }catch(e){toast(e.message,true)}
  };

  window.resetDb=async function(scope){
    const factory=scope==='factory';
    const warning=factory?'This will erase ALL JobTrack database content and restore defaults.':'This will permanently delete the selected database records.';
    if(!confirm(`${warning}\n\nA database backup will be created first. Continue?`)) return;
    const phrase=factory?'FACTORY RESET JOBTRACK':'RESET JOBTRACK';
    const typed=prompt(`Type exactly:\n${phrase}`,'');
    if(typed!==phrase){toast('Reset cancelled: confirmation text did not match.',true);return;}
    try{
      const result=await api('/api/database/reset',{method:'POST',body:JSON.stringify({scope,confirmation:typed,create_backup:true})});
      toast(`Reset complete: ${result.rows_deleted} rows deleted. Backup: ${result.backup_path}`);
      await loadDatabaseStatus();
      if(window.refreshAll) await window.refreshAll();
      if(factory) alert('Factory reset completed. Default profiles/sources/schedule were recreated. Review settings before the next search.');
    }catch(e){toast(e.message,true)}
  };

  install();
})();
