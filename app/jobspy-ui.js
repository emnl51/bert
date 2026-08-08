(() => {
  function selectedSites(raw){
    return String(raw||'').split(',').map(x=>x.trim().toLowerCase()).filter(x=>['linkedin','indeed','google','glassdoor'].includes(x));
  }

  async function configureJobSpy(){
    const current = await api('/api/jobspy/source');
    const src = current.source || {};
    const cfg = src.config || {};
    const name = prompt('Display name', src.name || 'JobSpy Multi-board');
    if(name===null) return;
    const sitesRaw = prompt('Sites (comma separated): linkedin, indeed, google, glassdoor', (cfg.sites || ['linkedin','indeed','google']).join(','));
    if(sitesRaw===null) return;
    const sites = selectedSites(sitesRaw);
    if(!sites.length){ toast('Select at least one supported JobSpy site', true); return; }
    const results = Number(prompt('Results per search term (1-100)', cfg.results_per_term || 20));
    const hours = Number(prompt('Only jobs newer than N hours', cfg.hours_old || 168));
    const maxTerms = Number(prompt('Maximum search terms per run (1-20)', cfg.max_search_terms || 6));
    const fetchDesc = confirm('Fetch full LinkedIn descriptions? This is slower and increases blocking risk.\n\nOK = Yes, Cancel = No');
    const enable = confirm('Enable JobSpy automatic scraping now?\n\nRecommended: first save disabled, then enable after a successful source test.\n\nOK = Enable, Cancel = Save disabled');
    await api('/api/jobspy/source', {method:'PUT', body:JSON.stringify({
      name:name || 'JobSpy Multi-board', enabled:enable, sites,
      results_per_term:Number.isFinite(results)?Math.max(1,Math.min(100,results)):20,
      hours_old:Number.isFinite(hours)?Math.max(1,Math.min(720,hours)):168,
      max_search_terms:Number.isFinite(maxTerms)?Math.max(1,Math.min(20,maxTerms)):6,
      linkedin_fetch_description:fetchDesc
    })});
    toast(`JobSpy saved${enable?' and enabled':' (disabled)'}`);
    if(window.loadSources) await window.loadSources();
    if(window.loadOverview) await window.loadOverview();
  }

  const install = () => {
    const original = window.addCatalogSource;
    if(typeof original !== 'function') return setTimeout(install, 100);
    if(original.__jobspyWrapped) return;
    const wrapped = function(key){
      if(key === 'jobspy') return configureJobSpy();
      return original.apply(this, arguments);
    };
    wrapped.__jobspyWrapped = true;
    window.addCatalogSource = wrapped;
  };
  install();
})();
