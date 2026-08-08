(() => {
  const labelMap = {
    english_first: 'English-first',
    german_growth: 'German-growth',
    stretch: 'B2 stretch',
    german_heavy: 'German-heavy',
    unclear: 'Language unclear',
  };

  const style = document.createElement('style');
  style.textContent = `
    .lang{display:inline-block;border-radius:999px;padding:3px 7px;font-size:11px;font-weight:700;margin-top:3px}
    .lang.english_first,.lang.german_growth{background:var(--goodbg);color:var(--good)}
    .lang.stretch{background:var(--warnbg);color:var(--warn)}
    .lang.german_heavy{background:var(--badbg);color:var(--bad)}
    .lang.unclear{background:#eef2f7;color:#475569}
    .score-stack{white-space:nowrap}.score-stack b{font-size:15px}.score-stack .hint{margin:1px 0}
    .language-profile{margin-top:20px}
  `;
  document.head.appendChild(style);

  const $ = id => document.getElementById(id);
  const langLabel = value => labelMap[value] || value;
  window.langLabel = langLabel;

  function injectUI() {
    const brand = document.querySelector('.brand');
    if (brand) brand.innerHTML = 'JobTrack<small>Berlin / Brandenburg · v4</small>';

    const latestTitle = [...document.querySelectorAll('#overview .section-title h2')].find(x => x.textContent.trim() === 'Latest matches');
    const controls = latestTitle?.parentElement?.querySelector('.inline');
    if (controls && !document.getElementById('jobsLanguage')) {
      const oldScoreLabel = [...controls.querySelectorAll('label')].find(x => x.textContent.trim() === 'Min score');
      if (oldScoreLabel) oldScoreLabel.textContent = 'Min overall';
      controls.insertAdjacentHTML('beforeend', `
        <label class="muted">Language</label>
        <select id="jobsLanguage" class="compact-select" onchange="loadJobs()">
          <option value="preferred">Recommended</option><option value="english_first">English-first</option>
          <option value="german_growth">German-growth</option><option value="stretch">B2 stretch</option>
          <option value="unclear">Language unclear</option><option value="german_heavy">German-heavy</option><option value="all">All</option>
        </select>
        <label class="muted">Min language</label>
        <input id="jobsMinLanguage" type="number" value="40" min="0" max="100" style="width:70px;padding:7px;border:1px solid var(--line);border-radius:7px" onchange="loadJobs()">
      `);
      const minOverall = document.getElementById('jobsMinScore');
      if (minOverall) { minOverall.max = '100'; minOverall.style.width = '70px'; }
    }

    const jobsHead = document.querySelector('#jobsBody')?.closest('table')?.querySelector('thead tr');
    if (jobsHead) jobsHead.innerHTML = '<th>Fit</th><th>Language</th><th>Role</th><th>Company</th><th>Location</th><th>Why</th><th>Decision</th><th>Source</th>';

    const appHead = document.querySelector('#applicationsBody')?.closest('table')?.querySelector('thead tr');
    if (appHead) appHead.innerHTML = '<th>Role</th><th>Company</th><th>Fit</th><th>Language</th><th>Stage</th><th>Applied date</th><th>Notes</th><th>Updated</th><th></th>';

    const searchCard = document.querySelector('#search .card');
    const scheduleHeading = searchCard ? [...searchCard.querySelectorAll('h3')].find(x => x.textContent.trim() === 'Schedule') : null;
    if (searchCard && scheduleHeading && !document.getElementById('current_german_level')) {
      const wrapper = document.createElement('div');
      wrapper.className = 'language-profile';
      wrapper.innerHTML = `
        <hr style="border:0;border-top:1px solid var(--line);margin:20px 0"><h3>Language profile</h3>
        <div class="form-grid">
          <div class="field"><label>Primary working language</label><select id="primary_working_language"><option value="English">English</option><option value="German">German</option></select></div>
          <div class="field"><label>Current German level</label><select id="current_german_level"><option value="a2">A2</option><option value="a2_b1">A2 → B1 (developing)</option><option value="b1">B1</option></select></div>
          <div class="field"><label>Maximum preferred German requirement</label><select id="max_german_requirement"><option value="a2">A2</option><option value="b1">B1</option><option value="b2">B2</option></select></div>
          <div class="field"><label>Minimum Language Fit</label><input id="min_language_score" type="number" min="0" max="100"></div>
          <div class="field"><label>Language weight in Overall Fit (%)</label><input id="language_weight" type="number" min="0" max="100"><div class="hint">Recommended: 35%. Job Fit keeps the larger share.</div></div>
          <div class="field"><label><input id="show_b2_stretch" type="checkbox" style="width:auto"> Show B2 stretch roles</label></div>
          <div class="field"><label><input id="hide_german_heavy" type="checkbox" style="width:auto"> Hide C1 / fluent / native German roles from notifications</label></div>
          <div class="field"><label><input id="prefer_german_growth" type="checkbox" style="width:auto"> Prefer German-growth opportunities</label></div>
          <div class="field full"><div class="hint"><b>Labels:</b> English-first = English working environment; German-growth = A2/B1 or German optional; Stretch = usually B2; German-heavy = C1/fluent/native; Unclear = no reliable language signal.</div></div>
        </div>`;
      searchCard.insertBefore(wrapper, scheduleHeading);
      const minScore = document.getElementById('min_score');
      if (minScore) { minScore.max = '100'; minScore.previousElementSibling.textContent = 'Minimum overall fit'; }
    }
  }

  window.loadJobs = async function loadJobsV4() {
    // review-ui replaces the legacy Latest matches table. When that happens,
    // refreshAll must refresh the modern review grid instead of dereferencing removed controls.
    const legacyBody = $('jobsBody');
    if (!legacyBody) {
      if (typeof window.loadReviewJobs === 'function') return window.loadReviewJobs();
      return;
    }
    const min = $('jobsMinScore')?.value || 0;
    const minLang = $('jobsMinLanguage')?.value || 0;
    const decision = $('jobsDecision')?.value || 'active';
    const language = $('jobsLanguage')?.value || 'preferred';
    const d = await api(`/api/jobs?limit=100&min_score=${encodeURIComponent(min)}&min_language_score=${encodeURIComponent(minLang)}&decision=${encodeURIComponent(decision)}&language=${encodeURIComponent(language)}`);
    legacyBody.innerHTML = d.jobs.length ? d.jobs.map(j => `<tr>
      <td class="score-stack"><b>${j.overall_score}</b><div class="hint">Job ${j.score} · Lang ${j.language_score}</div></td>
      <td><span class="lang ${esc(j.language_label)}">${esc(langLabel(j.language_label))}</span><div class="hint">${(j.language_reasons||[]).slice(0,2).map(esc).join(' · ')}</div></td>
      <td><a href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a></td><td>${esc(j.company)}</td><td>${esc(j.location)}</td>
      <td>${(j.reasons||[]).slice(0,4).map(x=>`<span class="pill">${esc(x)}</span>`).join('')}</td><td>${decisionButtons(j)}</td><td>${esc(j.source)}</td></tr>`).join('') : '<tr><td colspan="8" class="muted">No matches for this filter.</td></tr>';
  };

  window.loadApplications = async function loadApplicationsV4() {
    const status = $('appFilter')?.value || 'all';
    const d = await api(`/api/applications?status=${encodeURIComponent(status)}&limit=300`);
    appCache = d.applications;
    if ($('aToApply')) $('aToApply').textContent=d.stats.to_apply;
    if ($('aApplied')) $('aApplied').textContent=d.stats.applied;
    if ($('aInterview')) $('aInterview').textContent=d.stats.interview;
    if ($('aOffer')) $('aOffer').textContent=d.stats.offer;
    const body = $('applicationsBody');
    if (!body) return;
    body.innerHTML = appCache.length ? appCache.map(a => { const key=encodeURIComponent(a.job_key); return `<tr>
      <td><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.title)}</a><div class="hint">${esc(a.location)}</div></td><td>${esc(a.company)}</td>
      <td class="score-stack"><b>${a.overall_score}</b><div class="hint">Job ${a.score} · Lang ${a.language_score}</div></td><td><span class="lang ${esc(a.language_label)}">${esc(langLabel(a.language_label))}</span></td>
      <td><select class="compact-select" onchange="changeAppStatus('${key}',this.value)"><option value="to_apply" ${a.status==='to_apply'?'selected':''}>To Apply</option><option value="applied" ${a.status==='applied'?'selected':''}>Applied</option><option value="interview" ${a.status==='interview'?'selected':''}>Interview</option><option value="rejected" ${a.status==='rejected'?'selected':''}>Rejected</option><option value="offer" ${a.status==='offer'?'selected':''}>Offer</option></select><div style="margin-top:5px"><span class="stage ${esc(a.status)}">${esc(stageLabel(a.status))}</span></div></td>
      <td><input type="date" value="${esc(dateOnly(a.applied_at))}" style="min-width:135px;padding:6px" onchange="changeAppliedDate('${key}',this.value)"></td><td class="notes-cell">${esc(shortNotes(a.notes))||'<span class="muted">No notes</span>'}<div style="margin-top:5px"><button class="btn small" onclick="editNotes('${key}')">Edit notes</button></div></td><td>${dt(a.updated_at)}</td><td><a class="btn small" href="${esc(a.url)}" target="_blank" rel="noopener">Open job</a></td></tr>`; }).join('') : '<tr><td colspan="9" class="muted">No applications in this stage.</td></tr>';
  };

  window.loadSettings = async function loadSettingsV4() {
    const s = await api('/api/settings'); settingsCache = s;
    ['target_location','location_terms','min_score','max_digest_jobs','timezone','schedule_frequency','schedule_day','schedule_hour','schedule_minute','schedule_interval_hours','primary_working_language','current_german_level','max_german_requirement','min_language_score','language_weight'].forEach(k=>{if($(k))$(k).value=s[k]??''});
    ['show_b2_stretch','hide_german_heavy','prefer_german_growth'].forEach(k=>{if($(k))$(k).checked=String(s[k]).toLowerCase()==='true'});
    ['telegram_chat_id','smtp_host','smtp_port','smtp_username','email_from','email_to'].forEach(k=>{if($(k))$(k).value=s[k]??''});
    if ($('smtp_use_tls')) $('smtp_use_tls').checked=String(s.smtp_use_tls).toLowerCase()==='true';
    if ($('telegramSecret')) $('telegramSecret').textContent=s.telegram_bot_token==='configured'?'Token configured. Enter a new value only to replace it.':'No token saved.';
    if ($('smtpSecret')) $('smtpSecret').textContent=s.smtp_password==='configured'?'Password configured. Enter a new value only to replace it.':'No password saved.';
    if ($('jobsMinScore')) $('jobsMinScore').value=s.min_score||35;
    if($('jobsMinLanguage'))$('jobsMinLanguage').value=s.min_language_score||40;
    if (typeof toggleScheduleFields === 'function') toggleScheduleFields();
  };

  window.saveSettings = async function saveSettingsV4() {
    try {
      const body={target_location:$('target_location').value,location_terms:$('location_terms').value,min_score:+$('min_score').value,max_digest_jobs:+$('max_digest_jobs').value,timezone:$('timezone').value,schedule_frequency:$('schedule_frequency').value,schedule_day:$('schedule_day').value,schedule_hour:+$('schedule_hour').value,schedule_minute:+$('schedule_minute').value,schedule_interval_hours:+$('schedule_interval_hours').value,primary_working_language:$('primary_working_language').value,current_german_level:$('current_german_level').value,max_german_requirement:$('max_german_requirement').value,min_language_score:+$('min_language_score').value,language_weight:+$('language_weight').value,show_b2_stretch:$('show_b2_stretch').checked,hide_german_heavy:$('hide_german_heavy').checked,prefer_german_growth:$('prefer_german_growth').checked};
      await api('/api/settings',{method:'PUT',body:JSON.stringify(body)});if($('settingsStatus')){$('settingsStatus').textContent='Saved';$('settingsStatus').className='status ok'};if($('jobsMinScore'))$('jobsMinScore').value=body.min_score;if($('jobsMinLanguage'))$('jobsMinLanguage').value=body.min_language_score;toast('Search and language settings saved');await Promise.all([loadOverview(),loadJobs()]);
    } catch(e) { toast(e.message,true); }
  };

  injectUI();
  Promise.all([loadSettings(), loadJobs(), loadApplications()]).catch(e => toast(e.message,true));
})();
