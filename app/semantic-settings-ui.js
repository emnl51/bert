(() => {
  const $ = id => document.getElementById(id);
  async function install() {
    for (let index = 0; index < 30 && !$('aiSettingsCard'); index += 1) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    const anchor = $('aiSettingsCard');
    if (!anchor || $('semanticSettingsCard')) return;
    const card = document.createElement('div');
    card.id = 'semanticSettingsCard';
    card.className = 'card';
    card.style.marginBottom = '14px';
    card.innerHTML = `<div class="section-title" style="margin-top:0"><div><h2>Semantic re-ranking</h2><div class="hint">Optional multilingual similarity for already eligible jobs. It never overrides role, working-time, language or CV gates.</div></div></div><div class="form-grid"><div class="field"><label><input id="semanticEnabled" type="checkbox"> Enable local Ollama embeddings</label><div class="hint">Failure automatically falls back to deterministic ranking.</div></div><div class="field"><label for="semanticModel">Embedding model</label><input id="semanticModel" value="nomic-embed-text"></div><div class="field"><label for="semanticWeight">Ranking weight (0–20%)</label><input id="semanticWeight" type="number" min="0" max="20" value="15"></div></div><button class="btn" id="saveSemanticSettings">Save semantic settings</button><span id="semanticSettingsStatus" class="status"></span>`;
    anchor.insertAdjacentElement('afterend', card);
    let settings = {};
    try {
      settings = await api('/api/intelligence/settings');
      $('semanticEnabled').checked = !!settings.semantic_rerank_enabled;
      $('semanticModel').value = settings.semantic_model || 'nomic-embed-text';
      $('semanticWeight').value = settings.semantic_weight ?? 15;
    } catch (_) {}
    $('saveSemanticSettings').onclick = async () => {
      const status = $('semanticSettingsStatus');
      try {
        settings = await api('/api/intelligence/settings');
        await api('/api/intelligence/settings', {
          method: 'PUT',
          body: JSON.stringify({
            ollama_enabled: !!settings.ollama_enabled,
            ollama_url: settings.ollama_url,
            ollama_model: settings.ollama_model,
            ollama_timeout_seconds: settings.ollama_timeout_seconds,
            semantic_rerank_enabled: $('semanticEnabled').checked,
            semantic_model: $('semanticModel').value.trim() || 'nomic-embed-text',
            semantic_weight: Number($('semanticWeight').value) || 0
          })
        });
        status.textContent = 'Saved'; status.className = 'status ok';
      } catch (error) {
        status.textContent = error.message; status.className = 'status error';
      }
    };
  }
  install();
})();
