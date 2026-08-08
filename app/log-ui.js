(() => {
  const $=id=>document.getElementById(id);
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let timer=null, paused=false;

  function install(){
    const nav=document.querySelector('.nav'), main=document.querySelector('.main');
    if(!nav||!main) return setTimeout(install,100);
    if($('logs')) return;
    const btn=document.createElement('button'); btn.dataset.tab='logs'; btn.textContent='Logs'; nav.appendChild(btn);
    btn.addEventListener('click',()=>{
      document.querySelectorAll('.nav button').forEach(b=>b.classList.remove('active')); btn.classList.add('active');
      document.querySelectorAll('.section').forEach(s=>s.classList.remove('active')); $('logs').classList.add('active'); $('pageTitle').textContent='Logs'; loadLogs();
      try{localStorage.setItem('jobtrack-tab','logs')}catch(_){ }
    });
    const section=document.createElement('section'); section.id='logs'; section.className='section'; section.innerHTML=`
      <div class="section-title"><div><h2>Live Application Logs</h2><div class="hint">In-memory JobTrack/Uvicorn logs. Secrets are redacted. Container restart clears this buffer.</div></div><div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn" id="logPause">Pause</button><button class="btn" onclick="loadLogs()">Refresh</button><button class="btn" onclick="exportWebLogs()">Export TXT</button><button class="btn danger" onclick="clearWebLogs()">Clear view</button></div></div>
      <div class="grid" id="logMetrics"></div>
      <div class="card" style="margin-top:14px">
        <div style="display:flex;gap:10px;align-items:end;flex-wrap:wrap">
          <label>Minimum level<br><select id="logLevel"><option value="">All</option><option>INFO</option><option>WARNING</option><option>ERROR</option><option>CRITICAL</option></select></label>
          <label>Logger<br><input id="logLogger" placeholder="jobtrack.jobspy / uvicorn.access" style="min-width:220px"></label>
          <label>Search<br><input id="logQuery" placeholder="403, timeout, linkedin, provider…" style="min-width:260px"></label>
          <label>Rows<br><select id="logLimit"><option>100</option><option selected>300</option><option>500</option><option>1000</option><option>2000</option></select></label>
          <label style="display:flex;gap:6px;align-items:center"><input id="logAuto" type="checkbox" checked> Auto refresh (2s)</label>
          <button class="btn" onclick="loadLogs()">Apply</button>
        </div>
      </div>
      <div class="card" style="margin-top:14px;padding:0;overflow:hidden"><div id="logOutput" class="mono" style="background:#0b1220;color:#e5e7eb;padding:14px;min-height:420px;max-height:65vh;overflow:auto;white-space:pre-wrap;font-size:12px;line-height:1.5">Loading…</div></div>`;
    main.appendChild(section);
    ['logQuery','logLogger'].forEach(id=>$(id).addEventListener('keydown',e=>{if(e.key==='Enter')loadLogs()}));
    $('logPause').onclick=()=>{paused=!paused;$('logPause').textContent=paused?'Resume':'Pause';$('logRefreshState')&&($('logRefreshState').textContent=paused?'Paused':'2 sec')};
    timer=setInterval(()=>{if(!paused&&$('logs')?.classList.contains('active')&&$('logAuto')?.checked) loadLogs(true)},2000);
    try{if(localStorage.getItem('jobtrack-tab')==='logs')setTimeout(()=>btn.click(),120)}catch(_){ }
  }

  window.loadLogs=async function(silent=false){
    if(paused&&silent)return;
    try{
      const level=$('logLevel')?.value||'', q=$('logQuery')?.value||'', logger=$('logLogger')?.value||'', limit=$('logLimit')?.value||300;
      const d=await api(`/api/logs?limit=${encodeURIComponent(limit)}&level=${encodeURIComponent(level)}&q=${encodeURIComponent(q)}&logger_name=${encodeURIComponent(logger)}`);
      const s=d.stats||{}, lv=s.levels||{};
      $('logMetrics').innerHTML=`<div class="card"><div class="muted">Buffered</div><div class="metric">${s.stored||0}</div></div><div class="card"><div class="muted">Warnings</div><div class="metric">${lv.WARNING||0}</div></div><div class="card"><div class="muted">Errors</div><div class="metric">${(lv.ERROR||0)+(lv.CRITICAL||0)}</div></div><div class="card"><div class="muted">Capacity</div><div class="metric">${s.capacity||0}</div></div>`;
      const rows=d.logs||[], out=$('logOutput'), atBottom=out.scrollHeight-out.scrollTop-out.clientHeight<80;
      out.innerHTML=rows.length?rows.map(r=>{const color=r.level==='ERROR'||r.level==='CRITICAL'?'#fca5a5':r.level==='WARNING'?'#fde68a':r.level==='INFO'?'#bfdbfe':'#d1d5db';return `<span style="color:#64748b">${esc(new Date(r.timestamp).toLocaleString())}</span> <b style="color:${color}">${esc(r.level.padEnd(8))}</b> <span style="color:#a7f3d0">${esc(r.logger)}</span>  ${esc(r.message)}`}).join('\n'):'No matching logs.';
      if(atBottom)out.scrollTop=out.scrollHeight;
    }catch(e){if(!silent)toast(e.message,true)}
  };

  window.clearWebLogs=async function(){
    if(!confirm('Clear the in-memory web log buffer? This does not delete Docker/server logs or search history.')) return;
    try{const d=await api('/api/logs',{method:'DELETE'});toast(`Cleared ${d.cleared||0} log entries.`);await loadLogs();}catch(e){toast(e.message,true)}
  };

  window.exportWebLogs=function(){
    const level=$('logLevel')?.value||'', q=$('logQuery')?.value||'', logger=$('logLogger')?.value||'', limit=$('logLimit')?.value||1000;
    window.location=`/api/logs/export?limit=${encodeURIComponent(limit)}&level=${encodeURIComponent(level)}&q=${encodeURIComponent(q)}&logger_name=${encodeURIComponent(logger)}`;
  };
  install();
})();
