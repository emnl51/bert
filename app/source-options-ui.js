(() => {
  async function install() {
    for (let index = 0; index < 30 && typeof window.openJobDetail !== 'function'; index += 1) {
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    if (typeof window.openJobDetail !== 'function' || window.openJobDetailShowsSources) return;
    const original = window.openJobDetail;
    window.openJobDetail = async function(jobKey, trigger) {
      await original(jobKey, trigger);
      try {
        const data = await api(`/api/jobs/${encodeURIComponent(jobKey)}/detail?profile_id=${encodeURIComponent(window.activeProfileId)}`);
        const options = (data.job.source_options || []).filter(option => /^https?:\/\//i.test(option.url || ''));
        if (options.length < 2) return;
        const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
        const section = document.createElement('section');
        section.className = 'job-detail-section';
        section.innerHTML = `<h3>Available sources</h3><div class="job-detail-actions">${options.map(option => `<a class="btn" href="${esc(option.url)}" target="_blank" rel="noopener noreferrer">${esc(option.source)} ↗</a>`).join('')}</div>`;
        document.getElementById('jobDetailBody')?.insertBefore(section, document.querySelector('#jobDetailBody > .job-detail-actions'));
      } catch (_) {}
    };
    window.openJobDetailShowsSources = true;
  }
  install();
})();
