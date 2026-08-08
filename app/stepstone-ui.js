(() => {
  const $ = id => document.getElementById(id);

  const numberPrompt = (label, value, min, max, allowFloat=false) => {
    const raw = prompt(label, String(value));
    if(raw === null) return null;
    const n = allowFloat ? Number.parseFloat(raw) : Number.parseInt(raw, 10);
    if(!Number.isFinite(n)) throw new Error(`${label}: enter a number`);
    return Math.max(min, Math.min(max, n));
  };

  async function createStepStone(){
    try{
      const name = prompt('Display name', 'StepStone Germany');
      if(name === null) return;
      const maxTerms = numberPrompt('Maximum search terms per run (1-10)', 3, 1, 10);
      if(maxTerms === null) return;
      const pages = numberPrompt('Pages per search term (1-3)', 1, 1, 3);
      if(pages === null) return;
      const results = numberPrompt('Maximum results per search term (1-75)', 25, 1, 75);
      if(results === null) return;
      const timeout = numberPrompt('Request timeout in seconds (10-90)', 30, 10, 90);
      if(timeout === null) return;
      const delay = numberPrompt('Delay between requests in seconds (0-5)', 1, 0, 5, true);
      if(delay === null) return;
      const enabled = confirm('Enable StepStone automatic fetching now?\n\nThis provider is experimental. It uses normal public search pages and does not bypass blocking.\n\nOK = Enable, Cancel = Save disabled');
      await api('/api/sources', {method:'POST', body:JSON.stringify({
        name: name || 'StepStone Germany',
        source_type: 'stepstone',
        enabled,
        config: {
          max_search_terms: maxTerms,
          pages_per_term: pages,
          results_per_term: results,
          timeout_seconds: timeout,
          request_delay_seconds: delay,
        },
        secrets: {},
      })});
      toast(`StepStone saved${enabled ? ' and enabled' : ' (disabled)'}`);
      if(window.loadSources) await window.loadSources();
      if(window.loadOverview) await window.loadOverview();
    }catch(e){ toast(e.message, true); }
  }

  async function editStepStone(source){
    try{
      const cfg = source.config || {};
      const maxTerms = numberPrompt('Maximum search terms per run (1-10)', cfg.max_search_terms || 3, 1, 10);
      if(maxTerms === null) return;
      const pages = numberPrompt('Pages per search term (1-3)', cfg.pages_per_term || 1, 1, 3);
      if(pages === null) return;
      const results = numberPrompt('Maximum results per search term (1-75)', cfg.results_per_term || 25, 1, 75);
      if(results === null) return;
      const timeout = numberPrompt('Request timeout in seconds (10-90)', cfg.timeout_seconds || 30, 10, 90);
      if(timeout === null) return;
      const delay = numberPrompt('Delay between requests in seconds (0-5)', cfg.request_delay_seconds ?? 1, 0, 5, true);
      if(delay === null) return;
      await api(`/api/sources/${source.id}`, {method:'PUT', body:JSON.stringify({
        name: source.name,
        source_type: 'stepstone',
        enabled: source.enabled,
        config: {
          ...cfg,
          max_search_terms: maxTerms,
          pages_per_term: pages,
          results_per_term: results,
          timeout_seconds: timeout,
          request_delay_seconds: delay,
        },
        secrets: {},
      })});
      toast('StepStone settings updated');
      if(window.loadSources) await window.loadSources();
    }catch(e){ toast(e.message, true); }
  }

  function install(){
    if(typeof window.addCatalogSource !== 'function' || typeof window.editSource !== 'function') return setTimeout(install, 100);
    if(window.addCatalogSource.__stepstoneWrapped) return;

    const originalAdd = window.addCatalogSource;
    const wrappedAdd = function(key){
      if(key === 'stepstone') return createStepStone();
      return originalAdd.apply(this, arguments);
    };
    wrappedAdd.__stepstoneWrapped = true;
    window.addCatalogSource = wrappedAdd;

    const originalEdit = window.editSource;
    const wrappedEdit = async function(id){
      try{
        const d = await api('/api/sources');
        const source = (d.sources || []).find(x => x.id === id);
        if(source?.source_type === 'stepstone') return editStepStone(source);
      }catch(e){ return toast(e.message, true); }
      return originalEdit.apply(this, arguments);
    };
    wrappedEdit.__stepstoneWrapped = true;
    window.editSource = wrappedEdit;
  }

  install();
})();
