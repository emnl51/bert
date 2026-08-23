(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
  const stages = [
    ['to_apply', 'To Apply'], ['applied', 'Applied'], ['interview', 'Interview'],
    ['offer', 'Offer'], ['rejected', 'Rejected']
  ];
  const funnelStages = [['tracked', 'Tracked'], ['applied', 'Applied'], ['interview', 'Interview'], ['offer', 'Offer']];
  let profileNames = new Map();
  let view = localStorage.getItem('bert-applications-view') === 'list' ? 'list' : 'board';

  function profileId() {
    const value = $('applicationsProfile')?.value ?? '';
    return value ? Number(value) : null;
  }

  function installStyles() {
    if ($('application-workspace-style')) return;
    const style = document.createElement('style');
    style.id = 'application-workspace-style';
    style.textContent = `
      .app-workspace-toolbar{display:flex;align-items:end;justify-content:space-between;gap:12px;margin:22px 0 12px;flex-wrap:wrap}
      .app-workspace-controls{display:flex;align-items:end;gap:8px;flex-wrap:wrap}.app-workspace-controls .field{min-width:170px}
      .app-view-toggle{display:flex;padding:3px;border:1px solid var(--line);border-radius:10px;background:#fff}.app-view-toggle .btn{border:0;min-height:32px}.app-view-toggle .active{background:var(--accent2);color:var(--accent)}
      .application-board{display:grid;grid-template-columns:repeat(5,minmax(230px,1fr));gap:12px;overflow-x:auto;padding:2px 1px 12px;align-items:start}
      .application-column{background:#eef2f7;border:1px solid #dde3ec;border-radius:14px;padding:10px;min-height:230px}.application-column.drag-over{outline:3px solid rgba(37,99,235,.22);background:#e8efff}
      .application-column-header{display:flex;justify-content:space-between;align-items:center;padding:3px 4px 10px;font-weight:750}.application-count{display:inline-grid;place-items:center;min-width:24px;height:24px;border-radius:999px;background:#fff;color:var(--muted);font-size:11px}
      .application-column-body{display:grid;gap:9px}.application-card{background:#fff;border:1px solid #e1e7ef;border-radius:12px;padding:12px;box-shadow:0 3px 12px rgba(15,23,42,.045);cursor:grab}.application-card:active{cursor:grabbing}.application-card h3{font-size:14px;line-height:1.35;margin:0 0 4px}.application-card-company{font-size:12px;color:var(--muted)}.application-card-meta{display:flex;gap:5px;flex-wrap:wrap;margin:9px 0}.application-card-actions{display:flex;gap:6px;margin-top:10px;flex-wrap:wrap}
      .application-due{margin-top:8px;padding:6px 8px;border-radius:8px;background:#eef6ff;color:#2857a4;font-size:11px}.application-due.overdue{background:var(--badbg);color:var(--bad)}.application-due.today{background:var(--warnbg);color:var(--warn)}
      .application-empty{padding:24px 8px;text-align:center;color:var(--muted);font-size:12px}.application-analytics{margin-top:18px}.application-analytics-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.application-funnel{display:flex;gap:6px;align-items:stretch;overflow:auto}.funnel-step{flex:1;min-width:90px;padding:12px;background:#f7f9fc;border-radius:10px}.funnel-step b{display:block;font-size:21px;margin-top:4px}
      .application-dialog{width:min(680px,calc(100vw - 24px));max-height:90dvh;border:0;border-radius:16px;padding:0;box-shadow:0 30px 80px rgba(15,23,42,.25)}.application-dialog::backdrop{background:rgba(15,23,42,.55);backdrop-filter:blur(2px)}.application-dialog-body{padding:22px}.application-dialog-head{display:flex;justify-content:space-between;gap:12px;align-items:start;margin-bottom:18px}.application-dialog-head h2{margin:0;font-size:20px}.application-dialog-close{border:0;background:#eef2f7;border-radius:8px;width:34px;height:34px;cursor:pointer}.application-timeline{display:grid;gap:9px;margin-top:16px}.application-event{border-left:3px solid #cbd5e1;padding:7px 10px;background:#f8fafc;border-radius:0 8px 8px 0}.application-event b{display:block;font-size:12px}.application-event span{font-size:11px;color:var(--muted)}
      @media(max-width:1100px){.application-board{grid-template-columns:repeat(5,260px)}.application-analytics-grid{grid-template-columns:1fr}}
      @media(max-width:720px){.app-workspace-toolbar,.app-workspace-controls{display:grid;grid-template-columns:1fr;width:100%}.app-workspace-controls .field{min-width:0}.app-view-toggle{display:grid;grid-template-columns:1fr 1fr}.application-board{grid-template-columns:repeat(5,84vw)}.application-dialog-body{padding:16px}}
    `;
    document.head.appendChild(style);
  }

  function installWorkspace() {
    const section = $('applications');
    if (!section || $('applicationBoard')) return;
    installStyles();
    section.innerHTML = `
      <div class="grid">
        <div class="card"><div class="muted">To Apply</div><div id="aToApply" class="metric">—</div></div>
        <div class="card"><div class="muted">Applied</div><div id="aApplied" class="metric">—</div></div>
        <div class="card"><div class="muted">Interview</div><div id="aInterview" class="metric">—</div></div>
        <div class="card"><div class="muted">Offer</div><div id="aOffer" class="metric">—</div></div>
        <div class="card"><div class="muted">Due actions</div><div id="aDue" class="metric">—</div></div>
      </div>
      <div class="app-workspace-toolbar">
        <div><h2 style="margin:0">Application Workspace</h2><div class="hint">Move applications, plan follow-ups and keep every next step visible.</div></div>
        <div class="app-workspace-controls">
          <div class="field"><label for="applicationsProfile">Search profile</label><select id="applicationsProfile" class="compact-select"></select></div>
          <div class="field"><label for="appFilter">Stage</label><select id="appFilter" class="compact-select"><option value="all">All stages</option>${stages.map(([key,label]) => `<option value="${key}">${label}</option>`).join('')}</select></div>
          <div class="app-view-toggle" aria-label="Application view"><button id="applicationBoardButton" class="btn small" type="button">Board</button><button id="applicationListButton" class="btn small" type="button">List</button></div>
          <button class="btn primary" type="button" id="addManualJobButton">Add job</button>
        </div>
      </div>
      <div id="applicationBoard" class="application-board"></div>
      <div id="applicationList" class="table-wrap" hidden><table><thead><tr><th>Role</th><th>Company</th><th>Fit</th><th>Stage</th><th>Next action</th><th>Updated</th><th></th></tr></thead><tbody id="applicationsBody"></tbody></table></div>
      <div class="application-analytics application-analytics-grid">
        <div class="card"><h3 style="margin-top:0">Application funnel</h3><div id="applicationFunnel" class="application-funnel"></div></div>
        <div class="card"><h3 style="margin-top:0">Source progression</h3><div id="applicationSources" class="hint">No application data yet.</div></div>
      </div>
      <dialog id="applicationDialog" class="application-dialog"><div class="application-dialog-body">
        <div class="application-dialog-head"><div><h2 id="applicationDialogTitle">Application</h2><div id="applicationDialogSubtitle" class="hint"></div></div><button class="application-dialog-close" type="button" aria-label="Close">×</button></div>
        <form id="applicationForm" class="form-grid">
          <input id="applicationJobKey" type="hidden">
          <div class="field"><label for="applicationStatus">Stage</label><select id="applicationStatus">${stages.map(([key,label]) => `<option value="${key}">${label}</option>`).join('')}</select></div>
          <div class="field"><label for="applicationAppliedAt">Applied date</label><input id="applicationAppliedAt" type="date"></div>
          <div class="field full"><label for="applicationNextAction">Next action</label><input id="applicationNextAction" maxlength="300" placeholder="Follow up, prepare interview, send documents…"></div>
          <div class="field"><label for="applicationNextActionAt">Next action date</label><input id="applicationNextActionAt" type="date"></div>
          <div class="field"><label for="applicationContact">Contact</label><input id="applicationContact" maxlength="200" placeholder="Recruiter or hiring manager"></div>
          <div class="field full"><label for="applicationNotes">Notes</label><textarea id="applicationNotes" maxlength="4000"></textarea></div>
          <div class="actions full"><button class="btn primary" type="submit">Save application</button><button id="careerOpsExportButton" class="btn" type="button">Export for career-ops</button><a id="applicationOpenJob" class="btn" target="_blank" rel="noopener">Open job</a></div>
        </form>
        <div class="section-title"><h3 style="margin:0">Activity</h3></div><div id="applicationTimeline" class="application-timeline"></div>
      </div></dialog>
      <dialog id="manualJobDialog" class="application-dialog"><div class="application-dialog-body">
        <div class="application-dialog-head"><div><h2>Add a job</h2><div class="hint">Paste a public vacancy into Bert and review the fields before saving.</div></div><button class="application-dialog-close" type="button" aria-label="Close">×</button></div>
        <form id="manualJobForm" class="form-grid">
          <div class="field full"><label for="manualJobTitle">Position</label><input id="manualJobTitle" required maxlength="300"></div>
          <div class="field"><label for="manualJobCompany">Company</label><input id="manualJobCompany" maxlength="300"></div>
          <div class="field"><label for="manualJobLocation">Location</label><input id="manualJobLocation" maxlength="300"></div>
          <div class="field full"><label for="manualJobUrl">Job URL</label><input id="manualJobUrl" type="url" required maxlength="2000" placeholder="https://…"></div>
          <div class="field"><label for="manualJobPublished">Published date</label><input id="manualJobPublished" type="date"></div>
          <div class="field"><label><input id="manualJobRemote" type="checkbox" style="width:auto"> Remote position</label></div>
          <div class="field full"><label for="manualJobDescription">Original job description</label><textarea id="manualJobDescription" maxlength="50000" style="min-height:220px" required></textarea><div class="hint">Public vacancy text only. Do not paste private correspondence or credentials.</div></div>
          <div class="actions full"><button class="btn primary" type="submit">Save and track</button><button class="btn" type="button" data-close>Cancel</button></div>
        </form>
      </div></dialog>`;

    $('applicationsProfile').addEventListener('change', () => {
      const selected = profileId();
      if (selected) {
        window.activeProfileId = selected;
        localStorage.setItem('jobtrack-profile', String(selected));
      }
      window.loadApplications();
    });
    $('appFilter').addEventListener('change', window.loadApplications);
    $('applicationBoardButton').onclick = () => setView('board');
    $('applicationListButton').onclick = () => setView('list');
    $('addManualJobButton').onclick = () => $('manualJobDialog').showModal();
    section.querySelectorAll('.application-dialog-close,[data-close]').forEach(button => {
      button.onclick = () => button.closest('dialog').close();
    });
    $('applicationForm').addEventListener('submit', saveApplicationForm);
    $('manualJobForm').addEventListener('submit', saveManualJob);
    $('careerOpsExportButton').onclick = exportCareerOps;
    setView(view, false);
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

  function setView(next, reload = true) {
    view = next;
    localStorage.setItem('bert-applications-view', view);
    if ($('applicationBoard')) $('applicationBoard').hidden = view !== 'board';
    if ($('applicationList')) $('applicationList').hidden = view !== 'list';
    $('applicationBoardButton')?.classList.toggle('active', view === 'board');
    $('applicationListButton')?.classList.toggle('active', view === 'list');
    if (reload && appCache) renderApplications(appCache);
  }

  function dueState(value) {
    if (!value) return null;
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const due = new Date(`${String(value).slice(0, 10)}T00:00:00`);
    const days = Math.round((due - today) / 86400000);
    if (days < 0) return ['overdue', `${Math.abs(days)}d overdue`];
    if (days === 0) return ['today', 'Due today'];
    return ['', `Due in ${days}d`];
  }

  function card(application) {
    const key = encodeURIComponent(application.job_key);
    const due = dueState(application.next_action_at);
    const profile = application.profile_id ? profileNames.get(application.profile_id) : '';
    return `<article class="application-card" draggable="true" data-job-key="${key}">
      <h3>${esc(application.title)}</h3><div class="application-card-company">${esc(application.company || 'Company unknown')} · ${esc(application.location || 'Location unknown')}</div>
      <div class="application-card-meta"><span class="pill">${Number(application.overall_score || 0)} fit</span><span class="lang ${esc(application.language_label)}">${esc(langLabel(application.language_label))}</span>${profile ? `<span class="pill">${esc(profile)}</span>` : ''}</div>
      ${application.next_action ? `<div class="application-due ${due ? due[0] : ''}"><b>${esc(application.next_action)}</b>${due ? ` · ${esc(due[1])}` : ''}</div>` : '<div class="hint">No next action planned</div>'}
      <div class="application-card-actions"><button class="btn small" type="button" onclick="openApplicationDialog('${key}')">Details</button><a class="btn small" href="${esc(application.url)}" target="_blank" rel="noopener">Open job</a></div>
    </article>`;
  }

  function renderApplications(applications) {
    const selectedStage = $('appFilter')?.value || 'all';
    const visible = selectedStage === 'all' ? applications : applications.filter(item => item.status === selectedStage);
    const board = $('applicationBoard');
    if (board) {
      board.innerHTML = stages.map(([status, label]) => {
        const items = visible.filter(item => item.status === status);
        return `<section class="application-column" data-status="${status}"><div class="application-column-header"><span>${label}</span><span class="application-count">${items.length}</span></div><div class="application-column-body">${items.length ? items.map(card).join('') : '<div class="application-empty">No applications</div>'}</div></section>`;
      }).join('');
      board.querySelectorAll('.application-card').forEach(node => node.addEventListener('dragstart', event => event.dataTransfer.setData('text/plain', node.dataset.jobKey)));
      board.querySelectorAll('.application-column').forEach(column => {
        column.addEventListener('dragover', event => { event.preventDefault(); column.classList.add('drag-over'); });
        column.addEventListener('dragleave', () => column.classList.remove('drag-over'));
        column.addEventListener('drop', async event => {
          event.preventDefault(); column.classList.remove('drag-over');
          const key = event.dataTransfer.getData('text/plain');
          if (key) await window.changeAppStatus(key, column.dataset.status);
        });
      });
    }
    const body = $('applicationsBody');
    if (body) body.innerHTML = visible.length ? visible.map(application => {
      const key = encodeURIComponent(application.job_key); const due = dueState(application.next_action_at);
      return `<tr><td><b>${esc(application.title)}</b><div class="hint">${esc(application.location)}</div></td><td>${esc(application.company)}</td><td><b>${Number(application.overall_score || 0)}</b></td><td><span class="stage ${esc(application.status)}">${esc(stageLabel(application.status))}</span></td><td>${application.next_action ? `${esc(application.next_action)}${due ? `<div class="hint">${esc(due[1])}</div>` : ''}` : '<span class="muted">Not planned</span>'}</td><td>${dt(application.updated_at)}</td><td><button class="btn small" onclick="openApplicationDialog('${key}')">Details</button></td></tr>`;
    }).join('') : '<tr><td colspan="7" class="muted">No applications for this selection.</td></tr>';
  }

  function renderAnalytics(data) {
    if ($('aDue')) $('aDue').textContent = data.due_actions || 0;
    if ($('applicationFunnel')) $('applicationFunnel').innerHTML = funnelStages.map(([status, label]) => `<div class="funnel-step"><span class="muted">${label}</span><b>${Number(data.funnel?.[status] || 0)}</b></div>`).join('');
    if ($('applicationSources')) $('applicationSources').innerHTML = data.sources?.length ? `<div class="table-wrap"><table><thead><tr><th>Source</th><th>Tracked</th><th>Interview+</th><th>Offers</th></tr></thead><tbody>${data.sources.map(source => `<tr><td>${esc(source.source)}</td><td>${Number(source.tracked)}</td><td>${Number(source.progressed)}</td><td>${Number(source.offers)}</td></tr>`).join('')}</tbody></table></div>` : 'No application data yet.';
  }

  window.loadApplications = async function loadApplicationsWorkspace() {
    installWorkspace();
    if (!$('applicationsProfile')?.options.length) await loadApplicationProfiles();
    const params = new URLSearchParams({status: 'all', limit: '500'});
    const selectedProfile = profileId();
    if (selectedProfile) params.set('profile_id', String(selectedProfile));
    const [data, analytics] = await Promise.all([
      api('/api/applications?' + params), api('/api/application-analytics?' + params)
    ]);
    appCache = data.applications;
    if ($('aToApply')) $('aToApply').textContent = data.stats.to_apply;
    if ($('aApplied')) $('aApplied').textContent = data.stats.applied;
    if ($('aInterview')) $('aInterview').textContent = data.stats.interview;
    if ($('aOffer')) $('aOffer').textContent = data.stats.offer;
    renderApplications(appCache); renderAnalytics(analytics);
  };

  window.updateApp = async function updateApplicationWorkspace(encodedKey, patch) {
    const application = findApp(encodedKey); if (!application) return;
    const body = {
      status: patch.status ?? application.status,
      notes: patch.notes === undefined ? application.notes : patch.notes,
      applied_at: patch.applied_at === undefined ? application.applied_at : patch.applied_at,
      next_action: patch.next_action === undefined ? application.next_action : patch.next_action,
      next_action_at: patch.next_action_at === undefined ? application.next_action_at : patch.next_action_at,
      contact_name: patch.contact_name === undefined ? application.contact_name : patch.contact_name
    };
    await api(`/api/applications/${encodeURIComponent(application.job_key)}`, {method: 'PUT', body: JSON.stringify(body)});
    await Promise.all([window.loadApplications(), loadOverview(), loadJobs()]);
  };

  window.changeAppStatus = async function changeApplicationStatus(key, status) {
    try { await window.updateApp(key, {status}); toast(`Application moved to ${stageLabel(status)}`); }
    catch (error) { toast(error.message, true); await window.loadApplications(); }
  };

  window.openApplicationDialog = async function openApplicationDialog(encodedKey) {
    const application = findApp(encodedKey); if (!application) return;
    $('applicationJobKey').value = encodedKey; $('applicationDialogTitle').textContent = application.title;
    $('applicationDialogSubtitle').textContent = `${application.company || 'Company unknown'} · ${application.location || 'Location unknown'}`;
    $('applicationStatus').value = application.status; $('applicationAppliedAt').value = dateOnly(application.applied_at);
    $('applicationNextAction').value = application.next_action || ''; $('applicationNextActionAt').value = dateOnly(application.next_action_at);
    $('applicationContact').value = application.contact_name || ''; $('applicationNotes').value = application.notes || '';
    $('applicationOpenJob').href = application.url; $('applicationTimeline').innerHTML = '<div class="muted">Loading activity…</div>';
    $('applicationDialog').showModal();
    try {
      const data = await api(`/api/applications/${encodeURIComponent(application.job_key)}/events`);
      $('applicationTimeline').innerHTML = data.events.length ? data.events.map(event => `<div class="application-event"><b>${esc(event.detail || event.event_type)}</b><span>${dt(event.created_at)}</span></div>`).join('') : '<div class="muted">No activity recorded yet.</div>';
    } catch (error) { $('applicationTimeline').innerHTML = `<div class="error">${esc(error.message)}</div>`; }
  };

  async function saveApplicationForm(event) {
    event.preventDefault();
    try {
      await window.updateApp($('applicationJobKey').value, {
        status: $('applicationStatus').value, applied_at: $('applicationAppliedAt').value,
        next_action: $('applicationNextAction').value, next_action_at: $('applicationNextActionAt').value,
        contact_name: $('applicationContact').value, notes: $('applicationNotes').value
      });
      $('applicationDialog').close(); toast('Application updated');
    } catch (error) { toast(error.message, true); }
  }

  async function saveManualJob(event) {
    event.preventDefault();
    let selectedProfile = profileId();
    if (!selectedProfile) selectedProfile = Number(localStorage.getItem('jobtrack-profile')) || window.activeProfileId;
    if (!selectedProfile) return toast('Choose a search profile before adding a job.', true);
    const button = event.submitter; button.disabled = true;
    try {
      await api('/api/jobs/manual', {method: 'POST', body: JSON.stringify({
        title: $('manualJobTitle').value, company: $('manualJobCompany').value,
        location: $('manualJobLocation').value, url: $('manualJobUrl').value,
        description: $('manualJobDescription').value, published_at: $('manualJobPublished').value,
        remote: $('manualJobRemote').checked, profile_id: selectedProfile
      })});
      event.target.reset(); $('manualJobDialog').close(); toast('Job added to the application workspace');
      await Promise.all([window.loadApplications(), loadOverview(), loadJobs()]);
    } catch (error) { toast(error.message, true); } finally { button.disabled = false; }
  }

  function exportCareerOps() {
    const application = findApp($('applicationJobKey').value); if (!application) return;
    const link = document.createElement('a');
    link.href = `/api/applications/${encodeURIComponent(application.job_key)}/career-ops`;
    link.download = 'career-ops-job.md'; document.body.appendChild(link); link.click(); link.remove();
  }

  installWorkspace();
})();
