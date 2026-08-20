(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let profileNames = new Map();

  function profileId() {
    const value = $('applicationsProfile')?.value ?? '';
    return value ? Number(value) : null;
  }

  async function loadApplicationProfiles() {
    const response = await api('/api/profiles');
    const profiles = response.profiles.filter(profile => profile.enabled);
    profileNames = new Map(profiles.map(profile => [profile.id, profile.name]));
    const select = $('applicationsProfile');
    if (!select) return;
    const saved = Number(localStorage.getItem('jobtrack-profile')) || window.activeProfileId;
    const selected = profiles.some(profile => profile.id === saved) ? saved : '';
    select.innerHTML = '<option value="">All profiles</option>' + profiles.map(profile =>
      `<option value="${profile.id}" ${profile.id === selected ? 'selected' : ''}>${esc(profile.name)}</option>`
    ).join('');
  }

  function install() {
    const title = [...document.querySelectorAll('#applications .section-title')]
      .find(node => node.textContent.includes('Application Tracker'));
    if (!title || $('applicationsProfile')) return;
    const controls = title.querySelector('.compact-select')?.parentElement || title;
    controls.insertAdjacentHTML('beforeend', `
      <label class="muted" style="margin-left:8px">Search profile</label>
      <select id="applicationsProfile" class="compact-select" aria-label="Search profile"></select>
    `);
    $('applicationsProfile').addEventListener('change', () => {
      const id = profileId();
      if (id) {
        window.activeProfileId = id;
        try { localStorage.setItem('jobtrack-profile', String(id)); } catch (_) {}
      }
      window.loadApplications();
    });
  }

  window.loadApplications = async function loadApplicationsByProfile() {
    if (!$('applicationsProfile')) install();
    if (!$('applicationsProfile')?.options.length) await loadApplicationProfiles();
    const status = $('appFilter')?.value || 'all';
    const params = new URLSearchParams({ status, limit: '300' });
    const selectedProfileId = profileId();
    if (selectedProfileId) params.set('profile_id', String(selectedProfileId));
    const data = await api('/api/applications?' + params);
    appCache = data.applications;
    if ($('aToApply')) $('aToApply').textContent = data.stats.to_apply;
    if ($('aApplied')) $('aApplied').textContent = data.stats.applied;
    if ($('aInterview')) $('aInterview').textContent = data.stats.interview;
    if ($('aOffer')) $('aOffer').textContent = data.stats.offer;
    const body = $('applicationsBody');
    if (!body) return;
    body.innerHTML = appCache.length ? appCache.map(application => {
      const key = encodeURIComponent(application.job_key);
      const profile = application.profile_id
        ? (profileNames.get(application.profile_id) || 'Unavailable profile')
        : 'Unassigned legacy application';
      const profileHint = selectedProfileId ? '' : `<div class="hint">${esc(profile)}</div>`;
      return `<tr>
        <td><a href="${esc(application.url)}" target="_blank" rel="noopener">${esc(application.title)}</a><div class="hint">${esc(application.location)}</div>${profileHint}</td>
        <td>${esc(application.company)}</td>
        <td class="score-stack"><b>${application.overall_score}</b><div class="hint">Job ${application.score} · Lang ${application.language_score}</div></td>
        <td><span class="lang ${esc(application.language_label)}">${esc(langLabel(application.language_label))}</span></td>
        <td><select class="compact-select" onchange="changeAppStatus('${key}',this.value)"><option value="to_apply" ${application.status === 'to_apply' ? 'selected' : ''}>To Apply</option><option value="applied" ${application.status === 'applied' ? 'selected' : ''}>Applied</option><option value="interview" ${application.status === 'interview' ? 'selected' : ''}>Interview</option><option value="rejected" ${application.status === 'rejected' ? 'selected' : ''}>Rejected</option><option value="offer" ${application.status === 'offer' ? 'selected' : ''}>Offer</option></select><div style="margin-top:5px"><span class="stage ${esc(application.status)}">${esc(stageLabel(application.status))}</span></div></td>
        <td><input type="date" value="${esc(dateOnly(application.applied_at))}" style="min-width:135px;padding:6px" onchange="changeAppliedDate('${key}',this.value)"></td>
        <td class="notes-cell">${esc(shortNotes(application.notes)) || '<span class="muted">No notes</span>'}<div style="margin-top:5px"><button class="btn small" onclick="editNotes('${key}')">Edit notes</button></div></td>
        <td>${dt(application.updated_at)}</td><td><a class="btn small" href="${esc(application.url)}" target="_blank" rel="noopener">Open job</a></td>
      </tr>`;
    }).join('') : '<tr><td colspan="9" class="muted">No applications for this profile and stage.</td></tr>';
  };

  install();
})();
