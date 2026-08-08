(() => {
  const $=id=>document.getElementById(id);
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let timer=null;

  function install(){
    const nav=document.querySelector('.nav'), main=document.querySelector('.main');
    if(!nav||!main) return setTimeout(install,100);
    if($('logs')) return;
    const btn=document.createElement('button'); btn.dataset.tab='logs'; btn.textContent='Logs'; nav.appendChild(btn);
    btn.addEventListener('click',()=>{
      document.querySelectorAll('.nav button').forEach(b=>b.classList.remove('active')); btn.classList.add('active');
      document.querySelectorAll('.section').forEach(s=>s.classList.remove('active')); $('logs').classList.add('active'); $('pageTitle').textContent='Logs'; loadLogs();
    });
    const section=document.createElement('section'); section.id='logs'; section.className='section'; section.innerHTML=`
      <div class="section-title"><div><h2>Application Logs</h2><div class="hint">Live in-memory application and Uvicorn logs. Secrets are redacted before display.</div></div><div style="display:flex;gap:8px"><button class="btn" onclick="loadLogs()">Refresh</button><button class="btn danger" onclick="clearWebLogs()">Clear view</button></div></div>
      <div class="grid" id="logMetrics"></div>
      <div class="card" style="margin-top:14px">
        <div style="display:flex;gap:10px;align-items:end;flex-wrap:wrap">
          <label>Minimum level<br><select id="logLevel"><option value="">All</option><option>INFO</option><option>WARNING</option><option>ERROR</option><option>CRITICAL</option></select></label>
          <label>Search<br><input id="logQuery" placeholder="JobSpy, Jooble, timeout…" style="min-width:260px"></label>
          <label>Rows<br><select id="logLimit"><option>100</option><option selected>300</option><option>500</option><option>1000</option></select></label>
          <label style="display:flex;gap:6px;align-items:center"><input id="logAuto" type="checkbox" checked> Auto refresh (5s)</label>
          <button class="btn" onclick="loadLogs()">Apply</button>
        </div>
      </div>
      <div class="card" style="margin-top:14px;padding:0;overflow:hidden"><div id="logOutput" class="mono" style="background:#111827;color:#e5e7eb;padding:14px;max-height:65vh;overflow:auto;white-space:pre-wrap;font-size:12px;line-height:1.5">Loading…</div></div>`;
    main.appendChild(section);
    $('logQuery').addEventListener('keydown',e=>{if(e.key==='Enter')loadLogs()});
    timer=setInterval(()=>{if($('logs')?.classList.contains('active')&&$('logAuto')?.checked) loadLogs(true)},5000);
  }

  window.loadLogs=async function(silent=false){
    try{
      const level=$('logLevel')?.value||'', q=$('logQuery')?.value||'', limit=$('logLimit')?.value||300;
      const d=await api(`/api/logs?limit=${encodeURIComponent(limit)}&level=${encodeURIComponent(level)}&q=${encodeURIComponent(q)}`);
      const s=d.stats||{}, lv=s.levels||{};
      $('logMetrics').innerHTML=`<div class="card"><div class="muted">Stored</div><div class="metric">${s.stored||0}</div></div><div class="card"><div class="muted">Warnings</div><div class="metric">${lv.WARNING||0}</div></div><div class="card"><div class="muted">Errors</div><div class="metric">${(lv.ERROR||0)+(lv.CRITICAL||0)}</div></div><div class="card"><div class="muted">Capacity</div><div class="metric">${s.capacity||0}</div></div>`;
      const rows=d.logs||[];
      $('logOutput').innerHTML=rows.length?rows.map(r=>`<span style="opacity:.65">${esc(new Date(r.timestamp).toLocaleString())}</span> <b>${esc(r.level.padEnd(7))}</b> <span style="opacity:.7">${esc(r.logger)}</span>  ${esc(r.message)}`).join('\n'):'No matching logs.';
      const out=$('logOutput'); out.scrollTop=out.scrollHeight;
    }catch(e){if(!silent)toast(e.message,true)}
  };

  window.clearWebLogs=async function(){
    if(!confirm('Clear the in-memory web log buffer? This does not delete Docker/server logs.')) return;
    try{const d=await api('/api/logs',{method:'DELETE'});toast(`Cleared ${d.cleared||0} log entries.`);await loadLogs();}catch(e){toast(e.message,true)}
  };
  install();
})();
