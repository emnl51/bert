(() => {
  const $ = id => document.getElementById(id);
  const NAV = {
    overview:['⌂','Overview'], applications:['✓','Applications'], search:['⌕','Search & Schedule'],
    sources:['◫','Sources'], keywords:['#','Keywords'], notifications:['↗','Notifications'],
    runs:['↻','Run History'], database:['DB','Database'], logs:['>_','Logs'], updates:['↑','Updates']
  };

  function installStyles(){
    if($('jobtrack-v16-style')) return;
    const style=document.createElement('style'); style.id='jobtrack-v16-style'; style.textContent=`
      :root{--jt-sidebar:252px;--jt-sidebar-mini:78px;--jt-mobile-top:64px;--jt-radius:14px;--jt-bg:#f5f7fb;--jt-card:#fff;--jt-border:#e2e8f0;--jt-ink:#0f172a;--jt-soft:#64748b;--jt-blue:#2563eb;--jt-blue-dark:#1d4ed8}
      html{scroll-behavior:smooth}body{background:radial-gradient(circle at 85% -10%,#eaf1ff 0,transparent 28%),linear-gradient(180deg,#f8fafc 0,#f4f7fb 100%);overflow-x:hidden}
      body.jt-menu-open{overflow:hidden}.app{grid-template-columns:var(--jt-sidebar) minmax(0,1fr);transition:grid-template-columns .2s ease;min-height:100dvh}.app.jt-collapsed{grid-template-columns:var(--jt-sidebar-mini) minmax(0,1fr)}
      .side{width:auto;min-width:0;height:100dvh;position:sticky;top:0;padding:18px 12px;background:linear-gradient(180deg,#0b1220 0%,#111827 58%,#172033 100%);z-index:40;display:flex;flex-direction:column;overflow:hidden;box-shadow:8px 0 28px rgba(15,23,42,.07)}
      .brand{padding:4px 10px 20px;font-size:20px;white-space:nowrap;overflow:hidden}.brand small{opacity:.65}.jt-brand-row{display:flex;align-items:center;justify-content:space-between;gap:8px}.jt-collapse{width:34px;height:34px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.06);color:#cbd5e1;border-radius:9px;cursor:pointer;flex:none;font-size:17px}
      .nav{display:flex;flex-direction:column;gap:3px;overflow-y:auto;overflow-x:hidden;padding:2px 0 12px;scrollbar-width:thin}.nav button{display:flex;align-items:center;gap:11px;width:100%;min-height:44px;padding:9px 11px;margin:0;border-radius:10px;white-space:nowrap;font-weight:650;transition:.15s ease;color:#cbd5e1}.nav button:hover{background:rgba(255,255,255,.07);transform:none}.nav button.active{background:linear-gradient(90deg,rgba(37,99,235,.38),rgba(37,99,235,.10));color:#fff;box-shadow:inset 3px 0 0 #60a5fa}.jt-nav-icon{width:22px;text-align:center;font-size:14px;flex:none;color:#94a3b8}.nav button.active .jt-nav-icon{color:#bfdbfe}.jt-nav-label{overflow:hidden;text-overflow:ellipsis}
      .app.jt-collapsed .brand .jt-brand-text,.app.jt-collapsed .brand small,.app.jt-collapsed .jt-nav-label{display:none}.app.jt-collapsed .brand{padding-left:9px}.app.jt-collapsed .jt-brand-row{justify-content:center}.app.jt-collapsed .nav button{justify-content:center;padding-inline:8px}.app.jt-collapsed .jt-nav-icon{font-size:15px}.app.jt-collapsed .jt-collapse{transform:rotate(180deg)}
      .main{max-width:none;width:100%;min-width:0;padding:24px clamp(18px,2.5vw,38px) 50px}.top{min-height:62px;position:sticky;top:0;z-index:20;margin:-10px 0 20px;padding:10px 0;background:rgba(248,250,252,.86);backdrop-filter:blur(14px);display:flex;gap:14px}.top h1{font-size:clamp(21px,2vw,27px);letter-spacing:-.035em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.top-actions{display:flex;gap:8px;align-items:center}.jt-mobile-menu{display:none;width:42px;height:42px;border:1px solid var(--jt-border);background:white;border-radius:10px;font-size:20px;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 3px 10px rgba(15,23,42,.05)}
      .card{border-radius:var(--jt-radius);border-color:var(--jt-border);box-shadow:0 8px 28px rgba(15,23,42,.045);padding:clamp(14px,1.8vw,20px)}.grid{grid-template-columns:repeat(4,minmax(0,1fr));gap:13px}.metric{font-size:clamp(23px,2.2vw,30px)}.section-title{margin:26px 0 11px}.section-title h2{font-size:19px;letter-spacing:-.015em}
      .btn{min-height:38px;border-radius:9px;transition:transform .12s ease,box-shadow .12s ease,background .12s ease}.btn:hover{transform:translateY(-1px);box-shadow:0 5px 14px rgba(15,23,42,.08)}.btn.primary{background:linear-gradient(135deg,var(--jt-blue),var(--jt-blue-dark))}.btn.small{min-height:31px}.field input,.field select,.field textarea,select,input[type=date]{min-height:40px;border-color:#cbd5e1}.field input:focus,.field select:focus,.field textarea:focus,select:focus,input:focus{outline:3px solid rgba(37,99,235,.11);border-color:#60a5fa}
      .table-wrap{max-width:100%;overflow:auto;border-radius:var(--jt-radius);-webkit-overflow-scrolling:touch}.table-wrap table{min-width:860px}.table-wrap th{top:0;z-index:2}.table-wrap td,.table-wrap th{padding:11px 12px}.actions{flex-wrap:wrap}.inline{flex-wrap:wrap}.form-grid,.two{min-width:0}.source-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
      .jt-sidebar-overlay{display:none;position:fixed;inset:0;background:rgba(15,23,42,.48);backdrop-filter:blur(2px);z-index:35}.toast{max-width:min(430px,calc(100vw - 28px));right:14px;bottom:14px}
      .jt-mobile-table{display:none}
      @media(max-width:1280px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}.source-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.main{padding-inline:22px}}
      @media(max-width:980px){
        .app,.app.jt-collapsed{display:block}.side{position:fixed;left:0;top:0;bottom:0;width:min(310px,86vw);height:100dvh;transform:translateX(-102%);transition:transform .22s ease;z-index:50;padding-top:18px}.side.jt-open{transform:translateX(0)}.jt-sidebar-overlay.jt-open{display:block}.jt-collapse{display:none}.brand .jt-brand-text,.app.jt-collapsed .brand .jt-brand-text,.brand small,.app.jt-collapsed .brand small,.jt-nav-label,.app.jt-collapsed .jt-nav-label{display:block}.nav button,.app.jt-collapsed .nav button{justify-content:flex-start;padding:10px 12px}.main{padding:14px 18px 42px}.top{top:0;margin:-2px -2px 16px;padding:9px 2px;min-height:58px}.jt-mobile-menu{display:inline-flex}.top-actions .btn{padding-inline:10px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.form-grid,.two{grid-template-columns:1fr 1fr}.source-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
      }
      @media(max-width:720px){
        .main{padding:10px 12px 34px}.top{gap:8px}.top h1{font-size:21px;flex:1}.top-actions{gap:6px}.top-actions .btn{min-height:40px;font-size:12px;padding:7px 9px}.grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.card{padding:14px;border-radius:12px}.metric{font-size:23px}.form-grid,.two,.source-grid{grid-template-columns:1fr}.inline{display:grid;grid-template-columns:1fr;width:100%;align-items:stretch}.inline .field{width:100%}.inline>button{width:100%}.actions{display:grid;grid-template-columns:1fr}.actions .btn{width:100%}.section-title{align-items:flex-start;flex-direction:column}.section-title>select,.section-title>.inline{width:100%}
        .table-wrap{border:0;background:transparent;overflow:visible}.table-wrap table{display:block;min-width:0;width:100%}.table-wrap thead{display:none}.table-wrap tbody{display:grid;gap:10px;width:100%}.table-wrap tr{display:block;background:#fff;border:1px solid var(--jt-border);border-radius:12px;padding:6px 12px;box-shadow:0 5px 18px rgba(15,23,42,.04)}.table-wrap td{display:grid;grid-template-columns:minmax(92px,36%) minmax(0,1fr);gap:10px;width:100%;padding:8px 0;border-bottom:1px solid #edf0f5;white-space:normal;overflow-wrap:anywhere}.table-wrap td:last-child{border-bottom:0}.table-wrap td::before{content:attr(data-label);font-size:10px;text-transform:uppercase;letter-spacing:.055em;color:#64748b;font-weight:800;padding-top:2px}.table-wrap td[colspan]{display:block;text-align:center}.table-wrap td[colspan]::before{display:none}.decision{min-width:0}.notes-cell{max-width:none}.compact-select{width:100%;min-width:0}.source-toolbar{flex-direction:column;align-items:stretch}.source-toolbar .field{max-width:none!important}.source-toolbar .btn{width:100%}.jt-modal-backdrop{padding:10px}.jt-modal{border-radius:14px;padding:17px;max-height:94dvh}.jt-fields{grid-template-columns:1fr}.jt-fields .full{grid-column:auto}
      }
      @media(max-width:430px){.grid{grid-template-columns:1fr}.top-actions .btn:not(.primary){display:none}.main{padding-inline:10px}.card{padding:13px}.top h1{font-size:19px}.brand{font-size:19px}}
      @media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important;animation:none!important}}
    `; document.head.appendChild(style);
  }

  function decorateNav(){
    document.querySelectorAll('.nav button[data-tab]').forEach(btn=>{
      const key=btn.dataset.tab; const meta=NAV[key]||['•',btn.textContent.trim()];
      if(!btn.querySelector('.jt-nav-icon')) btn.innerHTML=`<span class="jt-nav-icon" aria-hidden="true">${meta[0]}</span><span class="jt-nav-label">${meta[1]}</span>`;
      btn.setAttribute('title',meta[1]);
    });
  }

  function annotateTables(root=document){
    root.querySelectorAll?.('.table-wrap table').forEach(table=>{
      const headers=[...table.querySelectorAll('thead th')].map(th=>th.textContent.trim());
      table.querySelectorAll('tbody tr').forEach(tr=>[...tr.children].forEach((td,i)=>{
        if(td.tagName==='TD'&&!td.hasAttribute('data-label')) td.setAttribute('data-label',headers[i]||'');
      }));
    });
  }

  function setMenu(open){
    document.querySelector('.side')?.classList.toggle('jt-open',open);
    $('.jtSidebarOverlay')?.classList.toggle('jt-open',open);
    document.body.classList.toggle('jt-menu-open',open);
    $('.jtMobileMenu')?.setAttribute('aria-expanded',String(open));
  }

  function installShell(){
    const app=document.querySelector('.app'), side=document.querySelector('.side'), top=document.querySelector('.top'), brand=document.querySelector('.brand');
    if(!app||!side||!top||!brand) return setTimeout(installShell,80);
    installStyles();
    brand.innerHTML='<div class="jt-brand-row"><div><span class="jt-brand-text">JobTrack</span><small>Smart Job Search · v16</small></div><button class="jt-collapse" type="button" title="Collapse sidebar" aria-label="Collapse sidebar">‹</button></div>';
    const mobile=document.createElement('button'); mobile.id='jtMobileMenu'; mobile.className='jt-mobile-menu'; mobile.type='button'; mobile.setAttribute('aria-label','Open navigation'); mobile.setAttribute('aria-expanded','false'); mobile.textContent='☰'; top.insertBefore(mobile,top.firstChild);
    const overlay=document.createElement('div'); overlay.id='jtSidebarOverlay'; overlay.className='jt-sidebar-overlay'; document.body.appendChild(overlay);
    try{if(localStorage.getItem('jobtrack-sidebar-collapsed')==='1')app.classList.add('jt-collapsed')}catch(_){ }
    brand.querySelector('.jt-collapse').onclick=()=>{app.classList.toggle('jt-collapsed');try{localStorage.setItem('jobtrack-sidebar-collapsed',app.classList.contains('jt-collapsed')?'1':'0')}catch(_){}};
    mobile.onclick=()=>setMenu(!side.classList.contains('jt-open')); overlay.onclick=()=>setMenu(false);
    document.addEventListener('keydown',e=>{if(e.key==='Escape')setMenu(false)});
    side.addEventListener('click',e=>{if(e.target.closest('.nav button')&&window.innerWidth<=980)setMenu(false)});
    decorateNav(); annotateTables();
    const observer=new MutationObserver(muts=>{decorateNav();for(const m of muts){m.addedNodes.forEach(n=>{if(n.nodeType===1) annotateTables(n)})}annotateTables()});
    observer.observe(document.body,{childList:true,subtree:true});
    window.addEventListener('resize',()=>{if(window.innerWidth>980)setMenu(false)});
  }
  installShell();
})();
