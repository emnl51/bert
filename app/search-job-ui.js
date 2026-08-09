(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
  const splitTerms = value => [...new Set(String(value || '').split(/[\n,]+/).map(x => x.trim().toLowerCase()).filter(Boolean))];
  let state = {search_jobs: [], profiles: [], sources: [], candidates: [], assignments: []};

  const style = document.createElement('style');
  style.textContent = `
    .sj-hero{display:flex;justify-content:space-between;align-items:flex-start;gap:18px;margin-bottom:18px}.sj-hero h2{font-size:24px;margin:0 0 4px}.sj-toolbar{display:grid;grid-template-columns:minmax(220px,1.4fr) minmax(160px,.7fr) minmax(160px,.7fr);gap:10px;margin-bottom:14px}.sj-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-bottom:14px}.sj-summary .card{padding:14px 16px}.sj-summary strong{display:block;font-size:22px;margin-top:2px}.sj-list-table{min-width:1050px}.sj-name-button{appearance:none;border:0;background:transparent;padding:0;color:var(--text);font:inherit;font-weight:800;text-align:left;cursor:pointer}.sj-name-button:hover{color:var(--accent)}.sj-name-meta,.sj-last-run{font-size:12px;color:var(--muted);margin-top:3px}.sj-rule-stack{display:flex;gap:5px;flex-wrap:wrap}.sj-status{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.04em}.sj-status::before{content:'';width:7px;height:7px;border-radius:50%;background:#94a3b8}.sj-status.on::before{background:#22c55e}.sj-row-actions{display:flex;gap:6px;justify-content:flex-end}.sj-empty{padding:38px;text-align:center}.sj-run-table{margin-top:14px}
    .sj-editor-head{display:flex;justify-content:space-between;align-items:center;gap:14px;margin-bottom:16px}.sj-editor-title{display:flex;align-items:center;gap:11px;min-width:0}.sj-editor-title h2{margin:0;font-size:23px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sj-editor-actions{display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end}.sj-editor-layout{display:grid;grid-template-columns:210px minmax(0,1fr);gap:16px;align-items:start}.sj-editor-nav{position:sticky;top:78px;padding:10px}.sj-editor-nav a{display:block;padding:9px 10px;border-radius:8px;color:#475569;font-weight:650}.sj-editor-nav a:hover{background:#f1f5f9;color:var(--accent)}.sj-editor-content{display:grid;gap:14px}.sj-form-card{scroll-margin-top:86px}.sj-form-card h3{margin:0 0 4px;font-size:17px}.sj-form-card>.hint{margin-bottom:15px}.sj-inherit{display:flex;align-items:center;gap:8px;margin-top:8px;font-weight:650}.sj-inherit input{width:auto}.sj-textarea{min-height:112px!important}.sj-rule-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.sj-rule-box{border:1px solid var(--line);border-radius:11px;padding:13px;background:#fbfcfe}.sj-rule-box.danger{background:#fffafa;border-color:#f0d3d0}.sj-rule-box.good{background:#f8fcfa;border-color:#cde8d9}.sj-rule-box h4{margin:0 0 3px}.sj-profile-preview{font-size:12px;color:var(--muted);margin:6px 0 9px;min-height:34px}.sj-source-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:8px}.sj-source-option{display:flex;gap:9px;align-items:flex-start;padding:10px;border:1px solid var(--line);border-radius:9px;background:#fff}.sj-source-option input{width:auto;margin-top:3px}.sj-channel{border:1px solid var(--line);border-radius:11px;padding:14px}.sj-channel+.sj-channel{margin-top:10px}.sj-channel-title{display:flex;align-items:center;gap:8px;margin-bottom:12px}.sj-channel-title input{width:auto}.sj-callout{padding:11px 12px;border:1px solid #c7d7fe;background:#f4f7ff;border-radius:10px;color:#36508a;font-size:12px;margin-bottom:12px}.sj-danger-note{padding:10px 12px;border-left:3px solid var(--bad);background:#fff7f6;color:#7f1d1d;font-size:12px;margin-top:9px}.sj-editor-footer{display:flex;justify-content:flex-end;gap:8px;position:sticky;bottom:10px;padding:12px;border:1px solid var(--line);border-radius:12px;background:rgba(255,255,255,.94);backdrop-filter:blur(10px);box-shadow:0 10px 30px rgba(15,23,42,.12)}
    @media(max-width:980px){.sj-editor-layout{grid-template-columns:1fr}.sj-editor-nav{position:sticky;top:64px;z-index:8;display:flex;overflow:auto;gap:4px;padding:7px}.sj-editor-nav a{white-space:nowrap}.sj-rule-grid{grid-template-columns:1fr}}
    @media(max-width:720px){.sj-hero,.sj-editor-head{display:grid}.sj-hero .btn,.sj-editor-actions .btn{width:100%}.sj-toolbar{grid-template-columns:1fr}.sj-summary{grid-template-columns:1fr 1fr}.sj-editor-actions{display:grid;grid-template-columns:1fr 1fr}.sj-editor-title h2{font-size:20px}.sj-source-grid{grid-template-columns:1fr}.sj-editor-footer{display:grid;grid-template-columns:1fr 1fr;bottom:4px}.sj-editor-footer .btn{width:100%}}
    @media(max-width:430px){.sj-summary{grid-template-columns:1fr}.sj-editor-actions{grid-template-columns:1fr}.sj-editor-footer{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);

  function install() {
    const nav = document.querySelector('.nav');
    const main = document.querySelector('.main');
    if (!nav || !main || $('searchJobs')) return;
    const button = document.createElement('button');
    button.dataset.tab = 'searchJobs';
    button.textContent = 'Jobs';
    nav.insertBefore(button, nav.querySelector('[data-tab="profiles"]') || nav.firstChild);
    const section = document.createElement('section');
    section.id = 'searchJobs';
    section.className = 'section';
    section.innerHTML = `
      <div id="sjListView">
        <div class="sj-hero"><div><h2>Jobs</h2><div class="muted">Create and manage independent job-search automations from one place.</div></div><button class="btn primary" type="button" onclick="openSearchJob()">New job</button></div>
        <div class="sj-summary"><div class="card"><span class="muted">Total jobs</span><strong id="sjTotal">—</strong></div><div class="card"><span class="muted">Active</span><strong id="sjActive">—</strong></div><div class="card"><span class="muted">Last matches</span><strong id="sjMatches">—</strong></div></div>
        <div class="sj-toolbar"><div class="field"><label for="sjFilter">Find a job</label><input id="sjFilter" type="search" placeholder="Name, profile or location"></div><div class="field"><label for="sjStateFilter">Status</label><select id="sjStateFilter"><option value="all">All</option><option value="active">Active</option><option value="inactive">Inactive</option></select></div><div class="field"><label for="sjSort">Sort by</label><select id="sjSort"><option value="updated">Recently updated</option><option value="name">Name</option><option value="next">Next run</option></select></div></div>
        <div class="table-wrap"><table class="sj-list-table"><thead><tr><th>Job</th><th>Profile</th><th>Schedule</th><th>Rules</th><th>Last run</th><th>Status</th><th></th></tr></thead><tbody id="sjRows"></tbody></table></div>
        <div class="section-title"><div><h2>Recent job runs</h2><div class="hint">The newest executions across all jobs.</div></div><button class="btn" type="button" onclick="loadSearchJobRuns()">Refresh</button></div>
        <div class="table-wrap sj-run-table"><table><thead><tr><th>Job</th><th>Status</th><th>Fetched</th><th>Matches</th><th>Filtered</th><th>Notifications</th><th>Started</th></tr></thead><tbody id="sjRuns"></tbody></table></div>
      </div>
      <div id="sjEditorView" hidden>
        <div class="sj-editor-head"><div class="sj-editor-title"><button class="btn" type="button" onclick="closeSearchJob()" aria-label="Back to jobs">←</button><div><h2 id="sjEditorTitle">New job</h2><div id="sjEditorSubtitle" class="hint">All settings are saved together.</div></div></div><div class="sj-editor-actions"><button id="sjRunButton" class="btn" type="button" onclick="runEditedSearchJob()">Run now</button><button id="sjDuplicateButton" class="btn" type="button" onclick="duplicateEditedSearchJob()">Duplicate</button><button id="sjDeleteButton" class="btn danger" type="button" onclick="removeEditedSearchJob()">Delete</button><button class="btn primary" type="button" onclick="saveSearchJob()">Save job</button></div></div>
        <input id="sjId" type="hidden">
        <div class="sj-editor-layout">
          <nav class="card sj-editor-nav" aria-label="Job settings sections"><a href="#sjGeneral">General</a><a href="#sjSearch">Search</a><a href="#sjFilters">Filters</a><a href="#sjSourcesCard">Sources</a><a href="#sjNotifications">Notifications</a><a href="#sjSchedule">Schedule</a></nav>
          <div class="sj-editor-content">
            <article id="sjGeneral" class="card sj-form-card"><h3>General</h3><div class="hint">Name the job and choose the profile that supplies its base values.</div><div class="form-grid"><div class="field"><label for="sjName">Job name</label><input id="sjName" placeholder="Part-time Process Engineer"></div><div class="field"><label for="sjProfile">Search profile</label><select id="sjProfile"></select></div><div class="field"><label for="sjCandidate">Candidate profile</label><select id="sjCandidate"><option value="">No candidate assignment</option></select><div class="hint">Optional CV Match intelligence for eligible results.</div></div><div class="field"><label>Status</label><label class="sj-inherit"><input id="sjEnabled" type="checkbox" checked> Active and scheduled</label></div></div></article>
            <article id="sjSearch" class="card sj-form-card"><h3>Search</h3><div class="hint">Inherit profile defaults or replace them only for this job.</div><div class="sj-callout">Inherited values update automatically when the selected profile changes. Custom values stay isolated to this job.</div><label class="sj-inherit"><input id="sjLocationInherit" type="checkbox" checked> Use profile location</label><div id="sjLocationPreview" class="sj-profile-preview"></div><div class="form-grid"><div class="field"><label for="sjLocation">Primary location</label><input id="sjLocation" value="Berlin"></div><div class="field"><label for="sjLocationTerms">Location terms</label><textarea id="sjLocationTerms" placeholder="berlin, potsdam, hennigsdorf"></textarea></div></div><label class="sj-inherit"><input id="sjSearchInherit" type="checkbox" checked> Use profile search keywords</label><div id="sjSearchPreview" class="sj-profile-preview"></div><div class="field"><label for="sjSearchTerms">Search keywords</label><textarea id="sjSearchTerms" class="sj-textarea" placeholder="teilzeit process engineer&#10;part time quality engineer"></textarea><div class="hint">One phrase per line. These are provider queries, not scoring rules.</div></div></article>
            <article id="sjFilters" class="card sj-form-card"><h3>Filters and scoring</h3><div class="hint">Profile rules are inherited unless you explicitly replace a section.</div><div class="form-grid"><div class="field"><label for="sjMin">Minimum Overall Fit</label><input id="sjMin" type="number" min="0" max="100"><label class="sj-inherit"><input id="sjMinInherit" type="checkbox" checked> Inherit profile threshold</label></div><div class="field"><label for="sjLangMin">Minimum Language Fit</label><input id="sjLangMin" type="number" min="0" max="100"><label class="sj-inherit"><input id="sjLangMinInherit" type="checkbox" checked> Inherit profile threshold</label></div><div class="field"><label for="sjCvMin">Minimum CV Match</label><input id="sjCvMin" type="number" min="0" max="100" value="58"><div class="hint">Applied only when a candidate profile is assigned.</div></div><div class="field"><label for="sjMax">Maximum results per notification</label><input id="sjMax" type="number" min="1" max="100" value="20"></div></div><div class="sj-rule-grid" style="margin-top:14px"><div class="sj-rule-box good"><h4>Allowlist</h4><div class="hint">A match can only add points. It never forces inclusion.</div><label class="sj-inherit"><input id="sjAllowInherit" type="checkbox" checked> Use profile allowlist</label><div id="sjAllowPreview" class="sj-profile-preview"></div><div class="field"><label for="sjAllowlist">Job-specific allowlist</label><textarea id="sjAllowlist" class="sj-textarea" placeholder="automotive&#10;process engineer&#10;IATF 16949"></textarea></div><div class="field"><label for="sjAllowBoost">Points per matching term</label><input id="sjAllowBoost" type="number" min="0" max="100" value="15"></div></div><div class="sj-rule-box danger"><h4>Blacklist</h4><div class="hint">Any match excludes the vacancy from this job.</div><label class="sj-inherit"><input id="sjBlockInherit" type="checkbox" checked> Use profile blacklist</label><div id="sjBlockPreview" class="sj-profile-preview"></div><div class="field"><label for="sjBlocklist">Job-specific blacklist</label><textarea id="sjBlocklist" class="sj-textarea" placeholder="software developer&#10;nurse&#10;driver"></textarea></div><div class="sj-danger-note">Blacklist terms are hard filters. Matching vacancies are not scored, stored for this profile, or notified.</div></div></div></article>
            <article id="sjSourcesCard" class="card sj-form-card"><h3>Sources</h3><div class="hint">Choose none to use every enabled automatic source.</div><div id="sjSources" class="sj-source-grid"></div></article>
            <article id="sjNotifications" class="card sj-form-card"><h3>Notifications</h3><div class="hint">Blank override fields use the global notification settings.</div><div class="sj-channel"><label class="sj-channel-title"><input id="sjTelegram" type="checkbox"> <b>Telegram</b></label><div class="form-grid"><div class="field"><label for="sjChat">Chat ID override</label><input id="sjChat" placeholder="Use global value"></div><div class="field"><label for="sjToken">Bot token override</label><input id="sjToken" type="password" placeholder="Leave blank to keep current/global"></div></div></div><div class="sj-channel"><label class="sj-channel-title"><input id="sjEmail" type="checkbox"> <b>Email</b></label><div class="form-grid"><div class="field"><label for="sjEmailTo">Recipient override</label><input id="sjEmailTo" placeholder="Use global value"></div><div class="field"><label for="sjEmailFrom">Sender override</label><input id="sjEmailFrom" placeholder="Use global value"></div><div class="field"><label for="sjSmtpHost">SMTP host override</label><input id="sjSmtpHost" placeholder="Use global value"></div><div class="field"><label for="sjSmtpPort">SMTP port</label><input id="sjSmtpPort" type="number" min="1" max="65535" placeholder="587"></div><div class="field"><label for="sjSmtpUser">SMTP username override</label><input id="sjSmtpUser"></div><div class="field"><label for="sjSmtpPass">SMTP password override</label><input id="sjSmtpPass" type="password" placeholder="Leave blank to keep current/global"></div><div class="field full"><label class="sj-inherit"><input id="sjSmtpTls" type="checkbox" checked> Use STARTTLS</label></div></div></div></article>
            <article id="sjSchedule" class="card sj-form-card"><h3>Schedule</h3><div class="hint">Manual jobs can still be started with Run now.</div><div class="form-grid"><div class="field"><label for="sjFreq">Frequency</label><select id="sjFreq"><option value="weekly">Weekly</option><option value="daily">Daily</option><option value="interval">Every N hours</option><option value="disabled">Manual only</option></select></div><div class="field sj-weekly"><label for="sjDay">Day of week</label><select id="sjDay"><option value="mon">Monday</option><option value="tue">Tuesday</option><option value="wed">Wednesday</option><option value="thu">Thursday</option><option value="fri">Friday</option><option value="sat">Saturday</option><option value="sun">Sunday</option></select></div><div class="field sj-time"><label for="sjHour">Hour</label><input id="sjHour" type="number" min="0" max="23" value="8"></div><div class="field sj-time"><label for="sjMinute">Minute</label><input id="sjMinute" type="number" min="0" max="59" value="0"></div><div class="field sj-interval"><label for="sjInterval">Interval hours</label><input id="sjInterval" type="number" min="1" max="168" value="12"></div></div></article>
            <div class="sj-editor-footer"><button class="btn" type="button" onclick="closeSearchJob()">Cancel</button><button class="btn primary" type="button" onclick="saveSearchJob()">Save job</button></div>
          </div>
        </div>
      </div>`;
    main.appendChild(section);
    button.addEventListener('click', () => {
      document.querySelectorAll('.section').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.nav button[data-tab]').forEach(x => x.classList.remove('active'));
      section.classList.add('active');
      button.classList.add('active');
      if ($('pageTitle')) $('pageTitle').textContent = 'Jobs';
      closeSearchJob(false);
      loadSearchJobs();
    });
    ['sjFilter', 'sjStateFilter', 'sjSort'].forEach(id => $(id).addEventListener(id === 'sjFilter' ? 'input' : 'change', renderSearchJobs));
    ['sjProfile', 'sjLocationInherit', 'sjSearchInherit', 'sjMinInherit', 'sjLangMinInherit', 'sjAllowInherit', 'sjBlockInherit'].forEach(id => $(id).addEventListener('change', updateInheritedControls));
    $('sjFreq').addEventListener('change', updateScheduleControls);
  }

  function selectedProfile() {
    return state.profiles.find(profile => profile.id === Number($('sjProfile')?.value));
  }

  function profileTerms(kind) {
    return Object.keys((selectedProfile()?.keywords || {})[kind] || {});
  }

  function previewTerms(terms, emptyText) {
    if (!terms.length) return emptyText;
    return `${terms.length} inherited · ${terms.slice(0, 5).join(', ')}${terms.length > 5 ? '…' : ''}`;
  }

  function updateInheritedControls() {
    const profile = selectedProfile();
    if (!profile) return;
    const locationInherited = $('sjLocationInherit').checked;
    $('sjLocation').disabled = locationInherited;
    $('sjLocationTerms').disabled = locationInherited;
    $('sjLocationPreview').textContent = locationInherited ? `${profile.target_location} · ${(profile.location_terms || []).join(', ')}` : 'Using job-specific location values.';
    const searchInherited = $('sjSearchInherit').checked;
    $('sjSearchTerms').disabled = searchInherited;
    $('sjSearchPreview').textContent = searchInherited ? previewTerms(profileTerms('search'), 'The profile has no search keywords.') : 'Using job-specific provider queries.';
    $('sjMin').disabled = $('sjMinInherit').checked;
    $('sjLangMin').disabled = $('sjLangMinInherit').checked;
    if ($('sjMinInherit').checked) $('sjMin').value = profile.min_score ?? 35;
    if ($('sjLangMinInherit').checked) $('sjLangMin').value = profile.min_language_score ?? 40;
    const allowInherited = $('sjAllowInherit').checked;
    $('sjAllowlist').disabled = allowInherited;
    $('sjAllowBoost').disabled = allowInherited;
    $('sjAllowPreview').textContent = allowInherited ? previewTerms(profileTerms('allowlist'), 'The profile allowlist is empty.') : 'Using job-specific positive terms.';
    const blockInherited = $('sjBlockInherit').checked;
    $('sjBlocklist').disabled = blockInherited;
    $('sjBlockPreview').textContent = blockInherited ? previewTerms(profileTerms('blocklist'), 'The profile blacklist is empty.') : 'Using job-specific hard exclusions.';
  }

  function updateScheduleControls() {
    const frequency = $('sjFreq').value;
    document.querySelectorAll('.sj-weekly').forEach(x => x.hidden = frequency !== 'weekly');
    document.querySelectorAll('.sj-time').forEach(x => x.hidden = !['weekly', 'daily'].includes(frequency));
    document.querySelectorAll('.sj-interval').forEach(x => x.hidden = frequency !== 'interval');
  }

  function formatSchedule(job) {
    if (!job.enabled) return 'Paused';
    if (job.frequency === 'interval') return `Every ${job.interval_hours}h`;
    if (job.frequency === 'daily') return `Daily ${String(job.hour).padStart(2, '0')}:${String(job.minute).padStart(2, '0')}`;
    if (job.frequency === 'disabled') return 'Manual only';
    return `${String(job.day_of_week || 'mon').toUpperCase()} ${String(job.hour).padStart(2, '0')}:${String(job.minute).padStart(2, '0')}`;
  }

  function formatDate(value) {
    if (!value) return '—';
    try { return new Date(value).toLocaleString(); } catch (_) { return value; }
  }

  function assignedCandidate(jobId) {
    const assignment = state.assignments.find(x => x.search_job_id === jobId && x.enabled);
    return state.candidates.find(x => x.id === assignment?.candidate_profile_id);
  }

  function effectiveRuleCount(job, kind) {
    const override = kind === 'allowlist' ? job.allowlist_terms : job.blocklist_terms;
    if (override !== null && override !== undefined) return {count: override.length, inherited: false};
    const profile = state.profiles.find(x => x.id === job.profile_id);
    return {count: Object.keys((profile?.keywords || {})[kind] || {}).length, inherited: true};
  }

  function renderSearchJobs() {
    const query = String($('sjFilter')?.value || '').trim().toLowerCase();
    const status = $('sjStateFilter')?.value || 'all';
    const sort = $('sjSort')?.value || 'updated';
    let jobs = state.search_jobs.filter(job => {
      const haystack = `${job.name} ${job.profile_name} ${job.target_location}`.toLowerCase();
      return (!query || haystack.includes(query)) && (status === 'all' || (status === 'active' ? job.enabled : !job.enabled));
    });
    jobs = [...jobs].sort((a, b) => {
      if (sort === 'name') return a.name.localeCompare(b.name);
      if (sort === 'next') return String(a.next_run || 'z').localeCompare(String(b.next_run || 'z'));
      return String(b.updated_at || '').localeCompare(String(a.updated_at || ''));
    });
    const body = $('sjRows');
    if (!body) return;
    body.innerHTML = jobs.length ? jobs.map(job => {
      const allow = effectiveRuleCount(job, 'allowlist');
      const block = effectiveRuleCount(job, 'blocklist');
      const candidate = assignedCandidate(job.id);
      return `<tr><td><button class="sj-name-button" type="button" onclick="openSearchJob(${job.id})">${esc(job.name)}</button><div class="sj-name-meta">${esc(job.target_location)}${candidate ? ` · ${esc(candidate.name)}` : ''}</div></td><td>${esc(job.profile_name)}<div class="hint">${job.search_terms?.length ? `${job.search_terms.length} custom queries` : 'Profile queries'}</div></td><td>${esc(formatSchedule(job))}<div class="hint">Next: ${esc(formatDate(job.next_run))}</div></td><td><div class="sj-rule-stack"><span class="pill">+ ${allow.count} ${allow.inherited ? 'inherited' : 'custom'}</span><span class="pill">× ${block.count} ${block.inherited ? 'inherited' : 'custom'}</span></div></td><td>${esc(job.last_run_status || 'Never')}<div class="sj-last-run">${job.last_match_count || 0} matches · ${esc(formatDate(job.last_run_at))}</div></td><td><button class="btn small" type="button" onclick="toggleSearchJob(${job.id},${!job.enabled})"><span class="sj-status ${job.enabled ? 'on' : ''}">${job.enabled ? 'Active' : 'Paused'}</span></button></td><td><div class="sj-row-actions"><button class="btn small" type="button" onclick="runSearchJob(${job.id})">Run</button><button class="btn small" type="button" onclick="openSearchJob(${job.id})">Edit</button></div></td></tr>`;
    }).join('') : '<tr><td colspan="7"><div class="sj-empty muted">No jobs match these filters.</div></td></tr>';
  }

  window.loadSearchJobRuns = async function() {
    const data = await api('/api/search-job-runs');
    const body = $('sjRuns');
    if (!body) return;
    body.innerHTML = (data.runs || []).slice(0, 20).map(run => { const filtered = Object.entries(run.filter_counts || {}).filter(([,count]) => count).map(([reason,count]) => `${reason}: ${count}`).join(' · ') || '—'; return `<tr><td>${esc(run.search_job_name)}</td><td>${esc(run.status)}</td><td>${run.fetched}</td><td>${run.matches}</td><td class="hint">${esc(filtered)}</td><td>${esc((run.notification_channels || []).join(', ') || '—')}</td><td>${esc(formatDate(run.started_at))}</td></tr>`; }).join('') || '<tr><td colspan="7" class="muted">No job runs yet.</td></tr>';
  };

  window.loadSearchJobs = async function() {
    const [jobsData, candidatesData] = await Promise.all([api('/api/search-jobs'), api('/api/candidates')]);
    state = {...jobsData, candidates: candidatesData.candidates || [], assignments: candidatesData.assignments || []};
    if ($('sjTotal')) $('sjTotal').textContent = state.search_jobs.length;
    if ($('sjActive')) $('sjActive').textContent = state.search_jobs.filter(x => x.enabled).length;
    if ($('sjMatches')) $('sjMatches').textContent = state.search_jobs.reduce((sum, x) => sum + (x.last_match_count || 0), 0);
    renderSearchJobs();
    await loadSearchJobRuns();
    return state;
  };

  function populateEditor(job, duplicate = false) {
    const editing = Boolean(job && !duplicate);
    const candidate = editing ? assignedCandidate(job.id) : null;
    $('sjId').value = editing ? job.id : '';
    $('sjEditorTitle').textContent = editing ? job.name : (duplicate ? `Copy of ${job.name}` : 'New job');
    $('sjEditorSubtitle').textContent = editing ? `${job.profile_name} · updated ${formatDate(job.updated_at)}` : 'All settings are saved together.';
    $('sjName').value = duplicate ? `${job.name} copy` : (job?.name || '');
    $('sjProfile').innerHTML = state.profiles.map(profile => `<option value="${profile.id}">${esc(profile.name)}${profile.is_default ? ' · default' : ''}</option>`).join('');
    $('sjProfile').value = job?.profile_id || state.profiles.find(x => x.is_default)?.id || state.profiles[0]?.id || '';
    $('sjCandidate').innerHTML = '<option value="">No candidate assignment</option>' + state.candidates.map(item => `<option value="${item.id}">${esc(item.name)}</option>`).join('');
    $('sjCandidate').value = candidate?.id || '';
    $('sjEnabled').checked = job?.enabled ?? true;
    $('sjLocationInherit').checked = job ? Boolean(job.inherit_location) : true;
    $('sjLocation').value = job?.target_location || selectedProfile()?.target_location || 'Berlin';
    $('sjLocationTerms').value = (job?.location_terms || []).join('\n');
    $('sjSearchInherit').checked = !job?.search_terms?.length;
    $('sjSearchTerms').value = (job?.search_terms || []).join('\n');
    $('sjMinInherit').checked = job?.min_score_override === null || job?.min_score_override === undefined;
    $('sjMin').value = job?.min_score_override ?? selectedProfile()?.min_score ?? 35;
    $('sjLangMinInherit').checked = job?.min_language_score_override === null || job?.min_language_score_override === undefined;
    $('sjLangMin').value = job?.min_language_score_override ?? selectedProfile()?.min_language_score ?? 40;
    $('sjCvMin').value = job?.min_cv_match ?? 58;
    $('sjMax').value = job?.max_results ?? 20;
    $('sjAllowInherit').checked = job?.allowlist_terms === null || job?.allowlist_terms === undefined;
    $('sjAllowlist').value = (job?.allowlist_terms || []).join('\n');
    $('sjAllowBoost').value = job?.allowlist_boost ?? 15;
    $('sjBlockInherit').checked = job?.blocklist_terms === null || job?.blocklist_terms === undefined;
    $('sjBlocklist').value = (job?.blocklist_terms || []).join('\n');
    $('sjSources').innerHTML = state.sources.map(source => `<label class="sj-source-option"><input class="sj-source" type="checkbox" value="${source.id}" ${(job?.source_ids || []).includes(source.id) ? 'checked' : ''}><span><b>${esc(source.name)}</b><span class="hint">${esc(source.source_type)}${source.enabled ? '' : ' · disabled'}</span></span></label>`).join('') || '<div class="muted">No sources are configured.</div>';
    $('sjTelegram').checked = job?.notify_telegram ?? false;
    $('sjEmail').checked = job?.notify_email ?? false;
    const notification = job?.notification || {};
    $('sjChat').value = notification.telegram_chat_id || '';
    $('sjToken').value = '';
    $('sjEmailTo').value = notification.email_to || '';
    $('sjEmailFrom').value = notification.email_from || '';
    $('sjSmtpHost').value = notification.smtp_host || '';
    $('sjSmtpPort').value = notification.smtp_port || '';
    $('sjSmtpUser').value = notification.smtp_username || '';
    $('sjSmtpPass').value = '';
    $('sjSmtpTls').checked = notification.smtp_use_tls ?? true;
    $('sjFreq').value = job?.frequency || 'weekly';
    $('sjDay').value = job?.day_of_week || 'mon';
    $('sjHour').value = job?.hour ?? 8;
    $('sjMinute').value = job?.minute ?? 0;
    $('sjInterval').value = job?.interval_hours ?? 12;
    $('sjRunButton').hidden = !editing;
    $('sjDuplicateButton').hidden = !editing;
    $('sjDeleteButton').hidden = !editing;
    updateInheritedControls();
    updateScheduleControls();
  }

  window.openSearchJob = async function(id, duplicate = false) {
    if (!state.profiles.length) await loadSearchJobs();
    const job = id ? state.search_jobs.find(x => x.id === id) : null;
    if (id && !job) return toast('Job not found', true);
    populateEditor(job, duplicate);
    $('sjListView').hidden = true;
    $('sjEditorView').hidden = false;
    if ($('pageTitle')) $('pageTitle').textContent = job && !duplicate ? job.name : 'New job';
    window.scrollTo({top: 0, behavior: 'smooth'});
  };

  window.closeSearchJob = function(showList = true) {
    if (!$('sjListView') || !$('sjEditorView')) return;
    $('sjEditorView').hidden = true;
    $('sjListView').hidden = false;
    if (showList && $('pageTitle')) $('pageTitle').textContent = 'Jobs';
  };

  function editorPayload() {
    const profile = selectedProfile();
    const inheritLocation = $('sjLocationInherit').checked;
    return {
      name: $('sjName').value.trim(),
      enabled: $('sjEnabled').checked,
      profile_id: Number($('sjProfile').value),
      inherit_location: inheritLocation,
      target_location: inheritLocation ? (profile?.target_location || 'Berlin') : ($('sjLocation').value.trim() || 'Berlin'),
      location_terms: inheritLocation ? [] : splitTerms($('sjLocationTerms').value),
      search_terms: $('sjSearchInherit').checked ? [] : splitTerms($('sjSearchTerms').value),
      allowlist_terms: $('sjAllowInherit').checked ? null : splitTerms($('sjAllowlist').value),
      blocklist_terms: $('sjBlockInherit').checked ? null : splitTerms($('sjBlocklist').value),
      allowlist_boost: Number($('sjAllowBoost').value) || 0,
      source_ids: [...document.querySelectorAll('.sj-source:checked')].map(x => Number(x.value)),
      frequency: $('sjFreq').value,
      day_of_week: $('sjDay').value,
      hour: Number($('sjHour').value) || 0,
      minute: Number($('sjMinute').value) || 0,
      interval_hours: Number($('sjInterval').value) || 12,
      min_score_override: $('sjMinInherit').checked ? null : Number($('sjMin').value),
      min_language_score_override: $('sjLangMinInherit').checked ? null : Number($('sjLangMin').value),
      min_cv_match: Number($('sjCvMin').value) || 0,
      max_results: Number($('sjMax').value) || 20,
      notify_telegram: $('sjTelegram').checked,
      notify_email: $('sjEmail').checked,
      notification: {
        telegram_chat_id: $('sjChat').value.trim(), email_to: $('sjEmailTo').value.trim(),
        email_from: $('sjEmailFrom').value.trim(), smtp_host: $('sjSmtpHost').value.trim(),
        smtp_port: $('sjSmtpPort').value ? Number($('sjSmtpPort').value) : '',
        smtp_username: $('sjSmtpUser').value.trim(), smtp_use_tls: $('sjSmtpTls').checked,
      },
      secrets: {telegram_bot_token: $('sjToken').value, smtp_password: $('sjSmtpPass').value},
    };
  }

  function payloadFromJob(job, changes = {}) {
    return {
      name: job.name, enabled: job.enabled, profile_id: job.profile_id,
      inherit_location: job.inherit_location, target_location: job.target_location,
      location_terms: job.location_terms || [], search_terms: job.search_terms || [],
      allowlist_terms: job.allowlist_terms, blocklist_terms: job.blocklist_terms,
      allowlist_boost: job.allowlist_boost ?? 15, source_ids: job.source_ids || [],
      frequency: job.frequency, day_of_week: job.day_of_week, hour: job.hour, minute: job.minute,
      interval_hours: job.interval_hours, min_score_override: job.min_score_override,
      min_language_score_override: job.min_language_score_override, max_results: job.max_results,
      min_cv_match: job.min_cv_match ?? 58,
      notify_telegram: job.notify_telegram, notify_email: job.notify_email,
      notification: job.notification || {}, secrets: job.secrets || {}, ...changes,
    };
  }

  window.saveSearchJob = async function() {
    const payload = editorPayload();
    if (!payload.name) return toast('Job name is required', true);
    if (!payload.profile_id) return toast('Select a search profile', true);
    if (!payload.search_terms.length && !profileTerms('search').length) return toast('Add search keywords to the job or selected profile', true);
    const currentId = Number($('sjId').value) || null;
    try {
      const result = await api(currentId ? `/api/search-jobs/${currentId}` : '/api/search-jobs', {method: currentId ? 'PUT' : 'POST', body: JSON.stringify(payload)});
      const jobId = currentId || result.id;
      await api(`/api/search-jobs/${jobId}/candidate`, {method: 'PUT', body: JSON.stringify({candidate_profile_id: $('sjCandidate').value ? Number($('sjCandidate').value) : null, enabled: Boolean($('sjCandidate').value)})});
      toast('Job saved');
      await loadSearchJobs();
      await openSearchJob(jobId);
    } catch (error) { toast(error.message, true); }
  };

  window.toggleSearchJob = async function(id, enabled) {
    const job = state.search_jobs.find(x => x.id === id);
    if (!job) return;
    try { await api(`/api/search-jobs/${id}`, {method: 'PUT', body: JSON.stringify(payloadFromJob(job, {enabled}))}); await loadSearchJobs(); toast(enabled ? 'Job activated' : 'Job paused'); } catch (error) { toast(error.message, true); }
  };

  window.runSearchJob = async function(id) {
    toast('Job search started');
    try { const result = await api(`/api/search-jobs/${id}/run`, {method: 'POST'}); toast(`${result.matches} new matches from ${result.unique_fetched ?? result.fetched} unique vacancies`); await loadSearchJobs(); } catch (error) { toast(error.message, true); }
  };

  window.runEditedSearchJob = () => runSearchJob(Number($('sjId').value));
  window.duplicateEditedSearchJob = () => openSearchJob(Number($('sjId').value), true);
  window.removeEditedSearchJob = async function() {
    const id = Number($('sjId').value);
    if (!id || !confirm('Delete this job and its run history?')) return;
    try { await api(`/api/search-jobs/${id}`, {method: 'DELETE'}); toast('Job deleted'); closeSearchJob(); await loadSearchJobs(); } catch (error) { toast(error.message, true); }
  };

  install();
  loadSearchJobs().catch(() => {});
})();
