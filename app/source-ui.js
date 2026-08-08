(() => {
  const $ = id => document.getElementById(id);
  const escS = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function installSourcePanel(){
    const section=$('sources');
    if(!section)return;
    section.innerHTML=`
      <div class="section-title"><div><h2>Configured sources</h2><div class="hint">API/feed sources run automatically. Search-only sources never scrape third-party sites.</div></div></div>
      <div id="sourcesList"></div>
      <div class="section-title"><div><h2>Source Catalog</h2><div class="hint">Add job boards, company ATS feeds and external search shortcuts.</div></div></div>
      <div id="catalogList" class="grid"></div>
      <div class="card" style="margin-top:16px"><h3 style="margin-top:0">Add custom RSS / Atom source</h3>
        <div class="form-grid"><div class="field"><label>Name</label><input id="rssName" placeholder="Company careers feed"></div>
        <div class="field"><label>Feed URL</label><input id="rssUrl" placeholder="https://example.com/jobs.xml"></div>
        <div class="field"><label>Default location (optional)</label><input id="rssLocation" placeholder="Berlin"></div></div>
        <div class="actions"><button class="btn primary" onclick="addRssSource()">Add source</button></div></div>`;
  }

  window.loadSources=async function(){
    const d=await api('/api/sources');
    $('sourcesList').innerHTML=d.sources.length?d.sources.map(s=>{
      const cfg=escS(JSON.stringify(s.config));
      const hasSecrets=Object.values(s.secrets||{}).some(x=>x==='configured');
      const searchOnly=s.source_type==='search_link';
      return `<div class="card source-card"><div><div class="source-title"><span class="dot ${s.enabled?'on':''}"></span>${escS(s.name)}</div><div class="source-meta">${escS(s.source_type)} · ${cfg}${hasSecrets?' · credentials configured':''}${searchOnly?' · manual search':''}</div></div><div class="source-actions">${searchOnly?'':`<button class="btn" onclick="toggleSource(${s.id},${!s.enabled})">${s.enabled?'Disable':'Enable'}</button>`}<button class="btn" onclick="testSource(${s.id})">${searchOnly?'Open search':'Test'}</button><button class="btn" onclick="editSource(${s.id})">Settings</button>${!['arbeitnow','adzuna'].includes(s.source_type)?`<button class="btn danger" onclick="deleteSource(${s.id})">Delete</button>`:''}</div></div>`
    }).join(''):'<div class="muted">No sources configured.</div>';
    await loadCatalog();
  }

  window.loadCatalog=async function(){
    const d=await api('/api/source-catalog');
    $('catalogList').innerHTML=d.catalog.map(c=>`<div class="card"><div class="source-title">${escS(c.name)}</div><div class="source-meta">${escS(c.mode)} · ${escS(c.source_type)}</div><p class="muted">${escS(c.description)}</p><button class="btn primary small" onclick="addCatalogSource('${escS(c.key)}')">${c.mode==='search-only'?'Add search shortcut':'Configure source'}</button></div>`).join('');
  }

  window.addCatalogSource=async function(key){
    const d=await api('/api/source-catalog'); const c=d.catalog.find(x=>x.key===key); if(!c)return;
    let config={},secrets={},enabled=true,name=c.name;
    if(c.source_type==='search_link'){config={url_template:c.url_template};enabled=false}
    else if(c.source_type==='jooble'){const apiKey=prompt('Jooble API key:','');if(apiKey===null||!apiKey.trim())return;const radius=prompt('Search radius km (0,4,8,16,26,40,80):','40');if(radius===null)return;config={radius:+radius||40,results_per_term:20};secrets={api_key:apiKey.trim()}}
    else if(c.source_type==='greenhouse'){const token=prompt('Greenhouse board token (boards.greenhouse.io/<token>):','');if(token===null||!token.trim())return;const company=prompt('Company display name (optional):','');if(company===null)return;config={board_token:token.trim(),company_name:company.trim()}}
    else if(c.source_type==='lever'){const site=prompt('Lever site/company slug:','');if(site===null||!site.trim())return;const company=prompt('Company display name (optional):','');if(company===null)return;config={site:site.trim(),company_name:company.trim()}}
    else if(c.source_type==='smartrecruiters'){const id=prompt('SmartRecruiters company identifier:','');if(id===null||!id.trim())return;const company=prompt('Company display name (optional):','');if(company===null)return;config={company_identifier:id.trim(),company_name:company.trim()}}
    else if(c.source_type==='rss'){const url=prompt('RSS / Atom feed URL:','');if(url===null||!url.trim())return;config={url:url.trim(),default_location:'Berlin'}}
    try{await api('/api/sources',{method:'POST',body:JSON.stringify({name,source_type:c.source_type,enabled,config,secrets})});toast(`${c.name} added`);await loadSources();await loadOverview()}catch(e){toast(e.message,true)}
  }

  window.editSource=async function(id){
    const d=await api('/api/sources');const s=d.sources.find(x=>x.id===id);if(!s)return;let config={...s.config},secrets={};
    if(s.source_type==='arbeitnow'){const pages=prompt('Pages to fetch per run (1-20):',String(config.pages||5));if(pages===null)return;config.pages=Math.max(1,Math.min(20,+pages||5))}
    else if(s.source_type==='adzuna'){const distance=prompt('Search radius in km (1-200):',String(config.distance_km||40));if(distance===null)return;const count=prompt('Results per search phrase (1-50):',String(config.results_per_term||50));if(count===null)return;const appId=prompt('Adzuna App ID (blank keeps current):','');if(appId===null)return;const key=prompt('Adzuna App Key (blank keeps current):','');if(key===null)return;config.distance_km=Math.max(1,Math.min(200,+distance||40));config.results_per_term=Math.max(1,Math.min(50,+count||50));secrets={app_id:appId,app_key:key}}
    else if(s.source_type==='rss'){const url=prompt('RSS / Atom URL:',config.url||'');if(url===null)return;const loc=prompt('Default location (optional):',config.default_location||'');if(loc===null)return;config.url=url;config.default_location=loc}
    else if(s.source_type==='search_link'){const url=prompt('Search URL template ({query}, {location}):',config.url_template||'');if(url===null)return;config.url_template=url}
    else if(s.source_type==='jooble'){const radius=prompt('Radius km:',String(config.radius||40));if(radius===null)return;const key=prompt('New Jooble API key (blank keeps current):','');if(key===null)return;config.radius=+radius||40;secrets={api_key:key}}
    else if(s.source_type==='greenhouse'){const token=prompt('Greenhouse board token:',config.board_token||'');if(token===null)return;config.board_token=token}
    else if(s.source_type==='lever'){const site=prompt('Lever site slug:',config.site||'');if(site===null)return;config.site=site}
    else if(s.source_type==='smartrecruiters'){const cid=prompt('SmartRecruiters company identifier:',config.company_identifier||'');if(cid===null)return;config.company_identifier=cid}
    await api(`/api/sources/${id}`,{method:'PUT',body:JSON.stringify({name:s.name,source_type:s.source_type,enabled:s.enabled,config,secrets})});toast('Source settings saved');loadSources();
  }

  window.testSource=async function(id){try{const d=await api(`/api/sources/${id}/test`,{method:'POST'});if(d.mode==='search-only'&&d.search_url){window.open(d.search_url,'_blank','noopener');toast('Search opened in a new tab')}else toast(`Source OK: ${d.count} jobs returned`)}catch(e){toast(e.message,true)}}

  installSourcePanel();
  loadSources().catch(e=>toast(e.message,true));
})();
