(() => {
  const $ = id => document.getElementById(id);
  let pollTimer = null;

  function install() {
    if ($('updates')) return;
    const nav = document.querySelector('.nav');
    if (!nav) return setTimeout(install, 80);

    const button = document.createElement('button');
    button.dataset.tab = 'updates';
    button.textContent = 'Updates';
    nav.appendChild(button);

    const section = document.createElement('section');
    section.id = 'updates';
    section.className = 'section';
    section.innerHTML = `
      <div class="section-title"><div><h2>Server updates</h2><div class="hint">Track the deployed Git commit and safely update the server from this page.</div></div></div>
      <div id="updateNotice"></div>
      <div class="grid">
        <div class="card"><div class="muted">Installed version</div><div id="updateInstalledVersion" class="metric" style="font-size:20px">—</div><div id="updateLocalCommit" class="hint mono">—</div></div>
        <div class="card"><div class="muted">Available version</div><div id="updateRemoteVersion" class="metric" style="font-size:20px">—</div><div id="updateRemoteCommit" class="hint mono">—</div></div>
        <div class="card"><div class="muted">Update status</div><div id="updateState" class="metric" style="font-size:20px">—</div><div id="updateCheckedAt" class="hint">—</div></div>
        <div class="card"><div class="muted">Commits behind</div><div id="updateBehind" class="metric">—</div><div class="hint">Only fast-forward updates from the configured main branch are allowed.</div></div>
      </div>
      <div class="card" style="margin-top:14px">
        <div class="section-title" style="margin-top:0"><div><h2>Deployment</h2><div id="updateMessage" class="hint">Loading update status…</div></div></div>
        <div class="actions">
          <button id="checkUpdateBtn" class="btn" type="button">Check for updates</button>
          <button id="applyUpdateBtn" class="btn primary" type="button" disabled>Apply update</button>
        </div>
        <div class="hint" style="margin-top:12px">Before deployment, Bert creates a SQLite backup. The updater then performs a fast-forward pull, rebuilds only the Bert service and verifies its health.</div>
      </div>
      <div class="card" style="margin-top:14px"><h3 style="margin-top:0">Recent updater log</h3><pre id="updateLog" class="mono" style="white-space:pre-wrap;max-height:320px;overflow:auto;margin-bottom:0">No update activity yet.</pre></div>`;
    document.querySelector('.main').appendChild(section);

    button.addEventListener('click', () => {
      document.querySelectorAll('.nav button').forEach(item => item.classList.remove('active'));
      document.querySelectorAll('.section').forEach(item => item.classList.remove('active'));
      button.classList.add('active');
      section.classList.add('active');
      $('pageTitle').textContent = 'Updates';
      loadUpdateStatus();
    });
    $('checkUpdateBtn').addEventListener('click', checkForUpdates);
    $('applyUpdateBtn').addEventListener('click', applyUpdate);
  }

  function shortSha(value) {
    return value ? String(value).slice(0, 8) : '—';
  }

  function render(data) {
    const configured = data.configured !== false;
    const busy = ['checking', 'backing_up', 'updating_code', 'building', 'restarting', 'verifying'].includes(data.state);
    $('updateInstalledVersion').textContent = data.local_version || '—';
    $('updateRemoteVersion').textContent = data.remote_version || '—';
    $('updateLocalCommit').textContent = `${shortSha(data.local_sha)}${data.local_subject ? ` · ${data.local_subject}` : ''}`;
    $('updateRemoteCommit').textContent = `${shortSha(data.remote_sha)}${data.remote_subject ? ` · ${data.remote_subject}` : ''}`;
    $('updateState').textContent = String(data.state || 'unknown').replaceAll('_', ' ');
    $('updateBehind').textContent = Number.isInteger(data.commits_behind) ? data.commits_behind : '—';
    $('updateCheckedAt').textContent = data.checked_at ? `Checked ${dt(data.checked_at)}` : 'Not checked yet';
    $('updateMessage').textContent = data.message || '—';
    $('updateLog').textContent = (data.log || []).join('\n') || 'No update activity yet.';
    $('checkUpdateBtn').disabled = !configured || busy;
    $('applyUpdateBtn').disabled = !configured || busy || !data.update_available || data.safe_to_update === false;
    $('applyUpdateBtn').textContent = busy ? 'Update in progress…' : 'Apply update';
    $('updateNotice').innerHTML = configured ? '' : '<div class="warning">The host update agent is disabled. Complete the server setup described in <span class="mono">deploy/README.md</span>.</div>';
    clearTimeout(pollTimer);
    if (busy) pollTimer = setTimeout(loadUpdateStatus, 3000);
  }

  async function loadUpdateStatus() {
    try {
      render(await api('/api/update/status'));
    } catch (error) {
      $('updateMessage').textContent = error.message;
      clearTimeout(pollTimer);
      pollTimer = setTimeout(loadUpdateStatus, 5000);
    }
  }

  async function checkForUpdates() {
    $('checkUpdateBtn').disabled = true;
    try {
      render(await api('/api/update/check', {method: 'POST', headers: {'X-JobTrack-Action': 'update'}}));
      toast('Update check completed.');
    } catch (error) {
      toast(error.message, true);
      await loadUpdateStatus();
    }
  }

  async function applyUpdate() {
    if (!confirm('Create a database backup and deploy the available update? Bert will restart and may be unavailable briefly.')) return;
    $('applyUpdateBtn').disabled = true;
    try {
      render(await api('/api/update/apply', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-JobTrack-Action': 'update'},
        body: JSON.stringify({confirmation: 'APPLY UPDATE'})
      }));
      toast('Update started. This page will reconnect after Bert restarts.');
      clearTimeout(pollTimer);
      pollTimer = setTimeout(loadUpdateStatus, 3000);
    } catch (error) {
      toast(error.message, true);
      pollTimer = setTimeout(loadUpdateStatus, 5000);
    }
  }

  window.loadUpdateStatus = loadUpdateStatus;
  install();
})();
