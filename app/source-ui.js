(() => {
  const $ = id => document.getElementById(id);
  const escS = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let catalogCache=[];
  let detectedCompany=null;

  const ATS_HINTS = [
    {key:'greenhouse', label:'Greenhouse', type:'greenhouse', mode:'api', hosts:['boards.greenhouse.io','job-boards.greenhouse.io','boards-api.greenhouse.io']},
    {key:'lever', label:'Lever', type:'lever', mode:'api', hosts:['jobs.lever.co']},
    {key:'smartrecruiters', label:'SmartRecruiters', type:'smartrecruiters', mode:'api', hosts:['jobs.smartrecruiters.com']},
    {key:'workday', label:'Workday', type:'search_link', mode:'manual', hostIncludes:['myworkdayjobs.com']},
    {key:'teamtailor', label:'Teamtailor', type:'search_link', mode:'manual', hostIncludes:['teamtailor.com']},
    {key:'recruitee', label:'Recruitee', type:'search_link', mode:'manual', hostIncludes:['recruitee.com']},
    {key:'successfactors', label:'SAP SuccessFactors', type:'search_link', mode:'manual', hostIncludes:['successfactors.com','successfactors.eu']},
    {key:'personio', label:'Personio', type:'search_link', mode:'manual', hosts:['jobs.personio.de','jobs.personio.com']},
    {key:'workable', label:'Workable', type:'search_link', mode:'manual', hosts:['apply.workable.com']},
    {key:'join', label:'JOIN', type:'search_link', mode:'manual', hosts:['join.com']},
  ];

  function injectDesign(){
    if(document.getElementById('jobtrack-v6-style')) return;
    const style=document.createElement('style'); style.id='jobtrack-v6-style'; style.textContent=`
      :root{--jt-blue:#2563eb;--jt-blue2:#eff6ff;--jt-green:#059669;--jt-amber:#d97706;--jt-red:#dc2626;--jt-ink:#0f172a;--jt-soft:#64748b}
      body{background:linear-gradient(180deg,#f8fafc 0,#f4f7fb 100%)}
      .side{background:linear-gradient(180deg,#0f172a 0%,#111827 70%,#172033 100%);border-right:1px solid rgba(255,255,255,.06)}
      .brand{font-size:20px;letter-spacing:-.02em}.brand small{font-size:11px;letter-spacing:.03em;text-transform:uppercase}
      .nav button{font-weight:600;padding:11px 12px}.nav button.active{background:linear-gradient(90deg,rgba(37,99,235,.35),rgba(37,99,235,.12));box-shadow:inset 3px 0 0 #60a5fa}
      .main{max-width:1600px}.top{position:sticky;top:0;z-index:5;background:rgba(248,250,252,.88);backdrop-filter:blur(12px);padding:14px 0;margin-top:-14px}
      .top h1{letter-spacing:-.03em}.card{border-color:#e2e8f0;box-shadow:0 8px 24px rgba(15,23,42,.045)}
      .metric{letter-spacing:-.035em}.btn{transition:.15s ease}.btn:hover{transform:translateY(-1px);box-shadow:0 4px 12px rgba(15,23,42,.08)}
      .btn.primary{background:linear-gradient(135deg,#2563eb,#1d4ed8)}
      .source-hero{background:linear-gradient(135deg,#0f172a 0%,#1e3a8a 100%);color:white;border:0;overflow:hidden;position:relative}
      .source-hero:after{content:'';position:absolute;width:260px;height:260px;border-radius:50%;right:-100px;top:-130px;background:rgba(96,165,250,.16)}
      .source-hero h2,.source-hero .hint{color:white}.source-hero .hint{opacity:.72}
      .source-hero input{background:rgba(255,255,255,.98);border:0;padding:12px 13px}
      .source-toolbar{display:flex;gap:10px;align-items:end}.source-toolbar .field{flex:1}.detected-box{margin-top:14px;padding:13px 14px;border-radius:10px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.16)}
      .source-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.source-grid .card{height:100%;display:flex;flex-direction:column}.source-grid .card .source-actions{margin-top:auto;padding-top:12px}
      .source-mode{display:inline-flex;align-items:center;border-radius:999px;padding:3px 8px;font-size:11px;font-weight:700;margin-left:5px}.source-mode.api{background:#dcfce7;color:#166534}.source-mode.feed{background:#e0f2fe;color:#075985}.source-mode.manual,.source-mode.search-only{background:#fef3c7;color:#92400e}
      .configured-source{border-left:3px solid #cbd5e1}.configured-source.enabled{border-left-color:#22c55e}.source-name-row{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
      .jt-modal-backdrop{position:fixed;inset:0;background:rgba(15,23,42,.55);backdrop-filter:blur(3px);z-index:1000;display:flex;align-items:center;justify-content:center;padding:20px}.jt-modal{width:min(620px,100%);max-height:90vh;overflow:auto;background:white;border-radius:16px;box-shadow:0 30px 80px rgba(15,23,42,.25);padding:22px}.jt-modal-head{display:flex;justify-content:space-between;align-items:start;gap:14px;margin-bottom:18px}.jt-modal-head h3{margin:0;font-size:20px}.jt-close{border:0;background:#f1f5f9;width:32px;height:32px;border-radius:8px;cursor:pointer;font-size:18px}.jt-fields{display:grid;grid-template-columns:1fr 1fr;gap:12px}.jt-fields .full{grid-column:1/-1}.jt-modal .actions{justify-content:flex-end}
      .empty-state{padding:28px;text-align:center;color:var(--muted);border:1px dashed #cbd5e1;border-radius:12px;background:#fafcff}
      .section-kicker{text-transform:uppercase;letter-spacing:.08em;font-size:10px;font-weight:800;color:#64748b;margin-bottom:3px}
      table tbody tr:hover{background:#fbfdff}th{position:sticky;top:0;z-index:1}
      @media(max-width:1200px){.source-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
      @media(max-width:760px){.source-grid{grid-template-columns:1fr}.source-toolbar{flex-direction:column;align-items:stretch}.jt-fields{grid-template-columns:1fr}.jt-fields .full{grid-column:auto}.top{position:static}}
    `; document.head.appendChild(style);

    const brand=document.querySelector('.brand'); if(brand) brand.innerHTML='JobTrack<small>Smart Job Search · v6</small>';
    const navLabels={overview:'Overview',applications:'Applications',search:'Search & Schedule',sources:'Sources',keywords:'Keywords',notifications:'Notifications',runs:'Run History'};
    document.querySelectorAll('.nav button[data-tab]').forEach(b=>{const k=b.dataset.tab;if(navLabels[k])b.textContent=navLabels[k]});
    try{const last=localStorage.getItem('jobtrack-tab');if(last){const btn=document.querySelector(`.nav button[data-tab="${last}"]`);if(btn)btn.click()}}catch(_){ }
    document.querySelectorAll('.nav button[data-tab]').forEach(b=>b.addEventListener('click',()=>{try{localStorage.setItem('jobtrack-tab',b.dataset.tab)}catch(_){}}));
  }

  function detectATS(raw){
    let u; try{u=new URL(raw.trim())}catch(_){return {ok:false,error:'Enter a valid https:// career URL.'}}
    const host=u.hostname.toLowerCase(); const parts=u.pathname.split('/').filter(Boolean);
    const hint=ATS_HINTS.find(h=>(h.hosts||[]).includes(host)||(h.hostIncludes||[]).some(x=>host.includes(x)));
    if(!hint) return {ok:true,key:'generic',label:'Company careers page',source_type:'search_link',mode:'manual',config:{url_template:u.toString()},note:'ATS not recognised. The URL can still be saved as a manual company careers shortcut.'};
    if(hint.key==='greenhouse'){
      let token=''; if(host==='boards-api.greenhouse.io'){const i=parts.indexOf('boards');token=i>=0?parts[i+1]||'':''} else token=parts[0]||'';
      if(!token)return {ok:false,error:'Greenhouse detected, but no board token was found in the URL.'};
      return {ok:true,...hint,source_type:'greenhouse',config:{board_token:token,company_name:''},note:'Public Greenhouse Job Board API can be monitored automatically.'};
    }
    if(hint.key==='lever'){
      const site=parts[0]||''; if(!site)return {ok:false,error:'Lever detected, but no company/site slug was found.'};
      return {ok:true,...hint,source_type:'lever',config:{site,company_name:''},note:'Public Lever postings can be monitored automatically.'};
    }
    if(hint.key==='smartrecruiters'){
      const company_identifier=parts[0]||''; if(!company_identifier)return {ok:false,error:'SmartRecruiters detected, but no company identifier was found.'};
      return {ok:true,...hint,source_type:'smartrecruiters',config:{company_identifier,company_name:''},note:'Public SmartRecruiters postings can be monitored automatically.'};
    }
    return {ok:true,...hint,source_type:'search_link',config:{url_template:u.toString()},note:`${hint.label} detected. Stored as a safe manual careers shortcut; JobTrack will not scrape it.`};
  }

  function showModal(title, subtitle, fields, onSave){
    const old=document.querySelector('.jt-modal-backdrop'); if(old)old.remove();
    const wrap=document.createElement('div');wrap.className='jt-modal-backdrop';
    wrap.innerHTML=`<div class="jt-modal"><div class="jt-modal-head"><div><div class="section-kicker">Source setup</div><h3>${escS(title)}</h3><div class="hint">${escS(subtitle||'')}</div></div><button class="jt-close" aria-label="Close">×</button></div><div class="jt-fields">${fields.map(f=>`<div class="field ${f.full?'full':''}"><label>${escS(f.label)}</label><input id="jt_${f.id}" type="${f.type||'text'}" value="${escS(f.value||'')}" placeholder="${escS(f.placeholder||'')}"><div class="hint">${escS(f.hint||'')}</div></div>`).join('')}</div><div class="actions"><button class="btn" id="jtCancel">Cancel</button><button class="btn primary" id="jtSave">Save source</button></div></div>`;
    document.body.appendChild(wrap);const close=()=>wrap.remove();wrap.querySelector('.jt-close').onclick=close;wrap.querySelector('#jtCancel').onclick=close;wrap.onclick=e=>{if(e.target===wrap)close()};
    wrap.querySelector('#jtSave').onclick=async()=>{const vals={};fields.forEach(f=>vals[f.id]=$(`jt_${f.id}`).value);try{await onSave(vals);close()}catch(e){toast(e.message,true)}};
  }

  function installSourcePanel(){
    const section=$('sources'); if(!section)return;
    section.innerHTML=`
      <div class="card source-hero"><div class="section-kicker" style="color:#bfdbfe">Target company monitor</div><h2 style="margin:2px 0 6px">Add a company careers page</h2><div class="hint">Paste a career URL. JobTrack detects Greenhouse, Lever and SmartRecruiters automatically; other ATS platforms are saved as safe shortcuts.</div>
        <div class="source-toolbar" style="margin-top:16px"><div class="field"><label style="color:white">Careers / jobs URL</label><input id="companyCareerUrl" placeholder="https://jobs.lever.co/company or https://boards.greenhouse.io/company"></div><div class="field" style="max-width:260px"><label style="color:white">Company name</label><input id="companyDisplayName" placeholder="e.g. Siemens"></div><button class="btn primary" style="background:white;color:#1d4ed8;border-color:white;padding:11px 16px" onclick="detectCompanySource()">Detect ATS</button></div>
        <div id="companyDetectResult"></div>
      </div>
      <div class="section-title"><div><div class="section-kicker">Active integrations</div><h2>Configured sources</h2><div class="hint">API/feed sources run automatically. Manual sources open the original job board or careers page.</div></div></div>
      <div id="sourcesList"></div>
      <div class="section-title"><div><div class="section-kicker">Integrations</div><h2>Source Catalog</h2><div class="hint">Job boards, company ATS feeds and external search shortcuts.</div></div></div>
      <div id="catalogList" class="source-grid"></div>
      <div class="card" style="margin-top:16px"><h3 style="margin-top:0">Custom RSS / Atom</h3><div class="form-grid"><div class="field"><label>Name</label><input id="rssName" placeholder="Company careers feed"></div><div class="field"><label>Feed URL</label><input id="rssUrl" placeholder="https://example.com/jobs.xml"></div><div class="field"><label>Default location</label><input id="rssLocation" placeholder="Berlin"></div></div><div class="actions"><button class="btn primary" onclick="addRssSource()">Add feed</button></div></div>`;
  }

  window.detectCompanySource=function(){
    const raw=$('companyCareerUrl').value;const name=$('companyDisplayName').value.trim();const r=detectATS(raw);detectedCompany=r.ok?{...r,name:name||r.label}:null;
    const box=$('companyDetectResult');
    if(!r.ok){box.innerHTML=`<div class="detected-box"><b>Could not detect</b><div style="margin-top:4px;opacity:.82">${escS(r.error)}</div></div>`;return}
    box.innerHTML=`<div class="detected-box"><div style="display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap"><div><b>${escS(r.label)}</b><span class="source-mode ${escS(r.mode)}">${r.mode==='api'?'AUTO API':'MANUAL'}</span><div style="margin-top:4px;opacity:.82">${escS(r.note)}</div></div><button class="btn" style="background:white" onclick="saveDetectedCompanySource()">Add to JobTrack</button></div></div>`;
  }

  window.saveDetectedCompanySource=async function(){
    if(!detectedCompany)return;const d=detectedCompany;const company=$('companyDisplayName').value.trim();if(company&&d.config)d.config.company_name=company;
    const payload={name:company||d.name||d.label,source_type:d.source_type,enabled:d.mode==='api',config:d.config||{},secrets:{}};
    await api('/api/sources',{method:'POST',body:JSON.stringify(payload)});toast(`${payload.name} added`);$('companyCareerUrl').value='';$('companyDisplayName').value='';$('companyDetectResult').innerHTML='';detectedCompany=null;await loadSources();await loadOverview();
  }

  window.loadSources=async function(){
    const d=await api('/api/sources');
    $('sourcesList').innerHTML=d.sources.length?d.sources.map(s=>{
      const hasSecrets=Object.values(s.secrets||{}).some(x=>x==='configured');const manual=s.source_type==='search_link';const mode=manual?'manual':s.source_type==='rss'?'feed':'api';
      let detail='';if(s.source_type==='greenhouse')detail=`board: ${escS(s.config.board_token||'—')}`;else if(s.source_type==='lever')detail=`site: ${escS(s.config.site||'—')}`;else if(s.source_type==='smartrecruiters')detail=`company: ${escS(s.config.company_identifier||'—')}`;else if(s.source_type==='rss')detail=escS(s.config.url||'');else if(manual)detail=escS(s.config.url_template||'');else detail=escS(JSON.stringify(s.config));
      return `<div class="card source-card configured-source ${s.enabled?'enabled':''}"><div><div class="source-name-row"><span class="dot ${s.enabled?'on':''}"></span><span class="source-title">${escS(s.name)}</span><span class="source-mode ${mode}">${mode==='api'?'AUTO':mode==='feed'?'FEED':'MANUAL'}</span></div><div class="source-meta">${escS(s.source_type)} · ${detail}${hasSecrets?' · credentials configured':''}</div></div><div class="source-actions">${manual?'':`<button class="btn" onclick="toggleSource(${s.id},${!s.enabled})">${s.enabled?'Disable':'Enable'}</button>`}<button class="btn" onclick="testSource(${s.id})">${manual?'Open':'Test'}</button><button class="btn" onclick="editSource(${s.id})">Settings</button>${!['arbeitnow','adzuna'].includes(s.source_type)?`<button class="btn danger" onclick="deleteSource(${s.id})">Delete</button>`:''}</div></div>`
    }).join(''):'<div class="empty-state"><b>No sources configured.</b><div>Add a target company or choose an integration from the catalog.</div></div>';
    await loadCatalog();
  }

  window.loadCatalog=async function(){
    const d=await api('/api/source-catalog');catalogCache=d.catalog||[];
    $('catalogList').innerHTML=catalogCache.map(c=>`<div class="card"><div><span class="source-title">${escS(c.name)}</span><span class="source-mode ${c.mode==='search-only'?'manual':c.mode}">${c.mode==='search-only'?'MANUAL':c.mode.toUpperCase()}</span></div><p class="muted" style="min-height:42px">${escS(c.description)}</p><div class="source-actions"><button class="btn primary small" onclick="addCatalogSource('${escS(c.key)}')">${c.mode==='search-only'?'Add shortcut':'Configure'}</button></div></div>`).join('');
  }

  window.addCatalogSource=function(key){
    const c=catalogCache.find(x=>x.key===key);if(!c)return;
    if(c.source_type==='kleinanzeigen') return showModal(c.name,c.description,[{id:'name',label:'Display name',value:'Kleinanzeigen Jobs'},{id:'location',label:'Location',value:'Berlin',hint:'The visible city name used in Kleinanzeigen URLs.'},{id:'location_id',label:'Kleinanzeigen location ID',value:'3331',hint:'Berlin is 3331. Copy another city ID from an exact Kleinanzeigen search URL.'},{id:'radius',label:'Radius (km)',value:'40',hint:'0–200 km'},{id:'terms',label:'Max profile search phrases',value:'6',hint:'1–20; queries keep their profile order.'},{id:'pages',label:'Pages per phrase',value:'1',hint:'1–5'},{id:'details',label:'Detail pages per run',value:'10',hint:'0 disables full-description enrichment.'}],async v=>{await api('/api/sources',{method:'POST',body:JSON.stringify({name:v.name||c.name,source_type:'kleinanzeigen',enabled:true,config:{location_name:v.location.trim(),location_id:v.location_id.trim(),radius_km:Math.max(0,Math.min(200,+v.radius||0)),max_search_terms:Math.max(1,Math.min(20,+v.terms||6)),pages_per_term:Math.max(1,Math.min(5,+v.pages||1)),detail_limit:Math.max(0,Math.min(50,+v.details||0)),request_delay_seconds:1},secrets:{}})});toast('Kleinanzeigen configured');await loadSources()});
    if(c.source_type==='search_link') return showModal(c.name,c.description,[{id:'name',label:'Display name',value:c.name},{id:'url',label:'Search URL template',value:c.url_template,full:true,hint:'Supports {query} and {location} placeholders.'}],async v=>{await api('/api/sources',{method:'POST',body:JSON.stringify({name:v.name||c.name,source_type:'search_link',enabled:false,config:{url_template:v.url},secrets:{}})});toast(`${c.name} added`);await loadSources()});
    if(c.source_type==='jooble') return showModal(c.name,c.description,[{id:'name',label:'Display name',value:c.name},{id:'key',label:'API key',type:'password',full:true},{id:'radius',label:'Radius (km)',value:'40'},{id:'count',label:'Results per query',value:'20'}],async v=>{await api('/api/sources',{method:'POST',body:JSON.stringify({name:v.name||c.name,source_type:'jooble',enabled:true,config:{radius:+v.radius||40,results_per_term:+v.count||20},secrets:{api_key:v.key}})});toast('Jooble configured');await loadSources()});
    if(['greenhouse','lever','smartrecruiters'].includes(c.source_type)){
      const idLabel=c.source_type==='greenhouse'?'Board token':c.source_type==='lever'?'Site/company slug':'Company identifier';const idKey=c.source_type==='greenhouse'?'board_token':c.source_type==='lever'?'site':'company_identifier';
      return showModal(c.name,c.description,[{id:'name',label:'Source name',value:c.name},{id:'company',label:'Company display name',placeholder:'Optional'},{id:'identifier',label:idLabel,full:true}],async v=>{const cfg={company_name:v.company};cfg[idKey]=v.identifier.trim();if(!cfg[idKey])throw new Error(`${idLabel} is required`);await api('/api/sources',{method:'POST',body:JSON.stringify({name:v.name||v.company||c.name,source_type:c.source_type,enabled:true,config:cfg,secrets:{}})});toast('Company source added');await loadSources()});
    }
    if(c.source_type==='rss') return showModal(c.name,c.description,[{id:'name',label:'Feed name',value:'Company careers feed'},{id:'url',label:'RSS / Atom URL',full:true},{id:'location',label:'Default location',value:'Berlin'}],async v=>{await api('/api/sources',{method:'POST',body:JSON.stringify({name:v.name,source_type:'rss',enabled:true,config:{url:v.url,default_location:v.location},secrets:{}})});toast('Feed added');await loadSources()});
  }

  window.editSource=async function(id){
    const d=await api('/api/sources');const s=d.sources.find(x=>x.id===id);if(!s)return;const config={...s.config};
    if(s.source_type==='arbeitnow')return showModal('Arbeitnow settings','Control how many API pages are fetched.',[{id:'pages',label:'Pages per run',value:String(config.pages||5),hint:'1–20'}],async v=>{config.pages=Math.max(1,Math.min(20,+v.pages||5));await saveExisting(s,config,{})});
    if(s.source_type==='adzuna')return showModal('Adzuna settings','Blank credentials keep the existing saved values.',[{id:'distance',label:'Radius km',value:String(config.distance_km||40)},{id:'count',label:'Results/query',value:String(config.results_per_term||50)},{id:'app_id',label:'New App ID',placeholder:'Leave blank to keep current'},{id:'app_key',label:'New App Key',type:'password',placeholder:'Leave blank to keep current'}],async v=>{config.distance_km=+v.distance||40;config.results_per_term=+v.count||50;await saveExisting(s,config,{app_id:v.app_id,app_key:v.app_key})});
    if(s.source_type==='kleinanzeigen')return showModal('Kleinanzeigen settings','Keep requests conservative to reduce rate-limit and layout-change failures.',[{id:'name',label:'Display name',value:s.name},{id:'location',label:'Location',value:config.location_name||'Berlin'},{id:'location_id',label:'Kleinanzeigen location ID',value:config.location_id||''},{id:'radius',label:'Radius (km)',value:String(config.radius_km??40)},{id:'terms',label:'Max profile search phrases',value:String(config.max_search_terms||6)},{id:'pages',label:'Pages per phrase',value:String(config.pages_per_term||1)},{id:'details',label:'Detail pages per run',value:String(config.detail_limit??10)}],async v=>{s.name=v.name||s.name;config.location_name=v.location.trim();config.location_id=v.location_id.trim();config.radius_km=Math.max(0,Math.min(200,+v.radius||0));config.max_search_terms=Math.max(1,Math.min(20,+v.terms||6));config.pages_per_term=Math.max(1,Math.min(5,+v.pages||1));config.detail_limit=Math.max(0,Math.min(50,+v.details||0));config.request_delay_seconds=1;await saveExisting(s,config,{})});
    if(s.source_type==='search_link')return showModal(`${s.name} settings`,'Manual/search shortcut.',[{id:'name',label:'Display name',value:s.name},{id:'url',label:'URL template',value:config.url_template||'',full:true}],async v=>{s.name=v.name||s.name;config.url_template=v.url;await saveExisting(s,config,{})});
    const map={rss:['url','RSS / Atom URL'],greenhouse:['board_token','Board token'],lever:['site','Lever site slug'],smartrecruiters:['company_identifier','Company identifier']};
    if(map[s.source_type]){const [key,label]=map[s.source_type];return showModal(`${s.name} settings`,'Update source configuration.',[{id:'name',label:'Display name',value:s.name},{id:'identifier',label,value:config[key]||'',full:true},{id:'company',label:'Company display name',value:config.company_name||''}],async v=>{s.name=v.name||s.name;config[key]=v.identifier;config.company_name=v.company;await saveExisting(s,config,{})})}
    if(s.source_type==='jooble')return showModal('Jooble settings','Blank API key keeps current value.',[{id:'radius',label:'Radius km',value:String(config.radius||40)},{id:'key',label:'New API key',type:'password',placeholder:'Leave blank to keep current'}],async v=>{config.radius=+v.radius||40;await saveExisting(s,config,{api_key:v.key})});
  }

  async function saveExisting(s,config,secrets){await api(`/api/sources/${s.id}`,{method:'PUT',body:JSON.stringify({name:s.name,source_type:s.source_type,enabled:s.enabled,config,secrets})});toast('Source settings saved');await loadSources()}

  window.testSource=async function(id){try{const d=await api(`/api/sources/${id}/test`,{method:'POST'});if(d.mode==='search-only'&&d.search_url){window.open(d.search_url,'_blank','noopener');toast('Opened in a new tab')}else toast(`Source OK · ${d.count} jobs returned`)}catch(e){toast(e.message,true)}}

  injectDesign();installSourcePanel();loadSources().catch(e=>toast(e.message,true));
})();
