(() => {
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const reasonOptions = [
    ['wrong_role','Wrong role / function'],['german_level','German requirement too high'],['seniority','Wrong seniority'],
    ['employment_type','Wrong employment type'],['location','Wrong location'],['company','Not interested in company'],['other','Other']
  ];

  function injectStyles(){
    const st=document.createElement('style'); st.textContent=`
      .review-toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:end;margin-bottom:14px}.review-toolbar .field{min-width:150px}
      .job-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:14px}.job-card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:var(--shadow);display:flex;flex-direction:column;gap:12px}
      .job-head{display:flex;justify-content:space-between;gap:12px}.job-title{font-weight:800;font-size:16px;line-height:1.25}.job-company{color:var(--muted);margin-top:4px}.fit-row{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.fit-box{background:#f7f9fc;border:1px solid var(--line);border-radius:10px;padding:8px}.fit-box b{display:block;font-size:18px}.fit-box span{font-size:11px;color:var(--muted)}
      .fit-high b{color:var(--good)}.fit-mid b{color:var(--warn)}.fit-low b{color:var(--bad)}.review-actions{display:flex;gap:6px;flex-wrap:wrap}.review-actions button{flex:1;min-width:90px}
      .btn.suitable{background:var(--goodbg);color:var(--good);border-color:#a8d9bc}.btn.unsuitable{background:var(--badbg);color:var(--bad);border-color:#efb2ab}.btn.maybe2{background:var(--warnbg);color:var(--warn);border-color:#e5c567}
      .job-meta{font-size:12px;color:var(--muted);display:flex;gap:10px;flex-wrap:wrap}.why-list{font-size:12px;color:var(--muted);max-height:52px;overflow:hidden}.learning-rule{display:grid;grid-template-columns:90px 1fr 80px 90px auto;gap:10px;align-items:center;padding:10px 12px;border-bottom:1px solid var(--line)}
      .rule-term{font-weight:700}.feedback-note{font-size:12px;color:var(--muted)}.reject-box{display:grid;grid-template-columns:1fr;gap:7px;padding:10px;background:#fff8f7;border:1px solid #f4cbc7;border-radius:10px}.reject-box textarea{min-height:54px;border:1px solid var(--line);border-radius:8px;padding:8px;resize:vertical}.reject-box select{padding:8px}
      @media(max-width:700px){.job-grid{grid-template-columns:1fr}.learning-rule{grid-template-columns:1fr 1fr}.fit-row{grid-template-columns:repeat(3,1fr)}}`;
    document.head.appendChild(st);
  }

  function fitClass(n){return n>=75?'fit-high':n>=50?'fit-mid':'fit-low'}
  function installOverview(){
    const section=$('overview'); if(!section)return;
    const wrap=document.createElement('div');
    wrap.innerHTML=`<div class="section-title"><div><h2>Job Review Queue</h2><div class="hint">Review jobs, track applications and teach JobTrack what is not relevant.</div></div></div>
      <div class="review-toolbar">
        <div class="field"><label>Decision</label><select id="reviewDecision"><option value="active">Active</option><option value="unreviewed">Unreviewed</option><option value="apply">Suitable</option><option value="maybe">Maybe</option><option value="skip">Not suitable</option><option value="all">All</option></select></div>
        <div class="field"><label>Language</label><select id="reviewLanguage"><option value="preferred">Recommended</option><option value="english_first">English-first</option><option value="german_growth">German-growth</option><option value="stretch">B2 stretch</option><option value="unclear">Unclear</option><option value="all">All</option></select></div>
        <div class="field"><label>Min fit</label><input id="reviewMin" type="number" value="35" min="0" max="100"></div>
        <button class="btn" id="reviewReload">Refresh jobs</button>
      </div><div id="jobReviewGrid" class="job-grid"></div>`;
    const oldTitle=[...section.querySelectorAll('.section-title')].find(x=>x.textContent.includes('Latest matches'));
    const oldTable=oldTitle?.nextElementSibling;
    if(oldTitle) oldTitle.remove(); if(oldTable?.classList.contains('table-wrap')) oldTable.remove();
    section.appendChild(wrap);
    ['reviewDecision','reviewLanguage','reviewMin'].forEach(id=>$(id).addEventListener('change',loadReviewJobs));
    $('reviewReload').addEventListener('click',loadReviewJobs);
  }

  function installLearning(){
    const nav=document.querySelector('.nav'); const main=document.querySelector('.main'); if(!nav||!main||$('learning'))return;
    const b=document.createElement('button');b.dataset.tab='learning';b.textContent='Learning';nav.appendChild(b);
    const s=document.createElement('section');s.id='learning';s.className='section';s.innerHTML=`
      <div class="section-title"><div><h2>Search Learning</h2><div class="hint">Rules learned from Not suitable feedback. Disable or delete a rule if the system learned the wrong preference.</div></div><button class="btn" onclick="loadLearning()">Refresh</button></div>
      <div class="grid"><div class="card"><div class="muted">Feedback events</div><div id="lfTotal" class="metric">—</div></div><div class="card"><div class="muted">Not suitable</div><div id="lfBad" class="metric">—</div></div><div class="card"><div class="muted">Active learned rules</div><div id="lfRules" class="metric">—</div></div></div>
      <div class="section-title"><h2>Learned rules</h2></div><div class="card" style="padding:0"><div id="learnedRules"></div></div>
      <div class="section-title"><h2>Recent feedback</h2></div><div class="table-wrap"><table><thead><tr><th>Job</th><th>Decision</th><th>Reason</th><th>When</th></tr></thead><tbody id="feedbackBody"></tbody></table></div>`;
    main.appendChild(s);
    b.addEventListener('click',()=>setTimeout(loadLearning,0));
  }

  async function loadReviewJobs(){
    const q=new URLSearchParams({limit:'150',min_score:$('reviewMin')?.value||'35',min_language_score:'0',decision:$('reviewDecision')?.value||'active',language:$('reviewLanguage')?.value||'preferred'});
    const d=await api('/api/jobs?'+q); const grid=$('jobReviewGrid'); if(!grid)return;
    grid.innerHTML=d.jobs.length?d.jobs.map((j,i)=>`<article class="job-card">
      <div class="job-head"><div><a class="job-title" href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a><div class="job-company">${esc(j.company)} · ${esc(j.location)}</div></div><span class="pill">${esc((j.language_label||'unclear').replaceAll('_',' '))}</span></div>
      <div class="fit-row"><div class="fit-box ${fitClass(j.overall_score||j.score)}"><b>${j.overall_score??j.score}</b><span>Overall fit</span></div><div class="fit-box ${fitClass(j.score)}"><b>${j.score}</b><span>Job fit</span></div><div class="fit-box ${fitClass(j.language_score||0)}"><b>${j.language_score??'—'}</b><span>Language fit</span></div></div>
      <div class="job-meta"><span>${esc(j.source)}</span><span>Review: ${esc(j.decision||'unreviewed')}</span><span>Application: ${esc(j.application_status||'not started')}</span></div>
      <div class="why-list">${(j.reasons||[]).slice(0,6).map(x=>`<span class="pill">${esc(x)}</span>`).join('')}</div>
      <div class="review-actions"><button class="btn suitable" onclick='reviewJob(${JSON.stringify(j.job_key)},"suitable")'>Suitable</button><button class="btn maybe2" onclick='reviewJob(${JSON.stringify(j.job_key)},"maybe")'>Maybe</button><button class="btn unsuitable" onclick="toggleReject(${i})">Not suitable</button></div>
      <div class="reject-box" id="reject-${i}" hidden><select id="reject-reason-${i}">${reasonOptions.map(x=>`<option value="${x[0]}">${x[1]}</option>`).join('')}</select><textarea id="reject-note-${i}" placeholder="Optional note: what exactly made this irrelevant?"></textarea><label class="hint"><input id="reject-learn-${i}" type="checkbox" checked> Update search learning from this decision</label><button class="btn unsuitable" onclick='submitNotSuitable(${JSON.stringify(j.job_key)},${i})'>Save as not suitable</button></div>
    </article>`).join(''):'<div class="card muted">No jobs match the current filters.</div>';
  }

  window.reviewJob=async function(jobKey,suitability,reason='',note='',learn=true){
    await api(`/api/jobs/${encodeURIComponent(jobKey)}/feedback`,{method:'POST',body:JSON.stringify({suitability,reason,note,learn})}); toast(suitability==='suitable'?'Added to To Apply':'Feedback saved'); await loadReviewJobs(); if(window.loadOverview)loadOverview();
  }
  window.toggleReject=function(i){const box=$(`reject-${i}`);box.hidden=!box.hidden;}
  window.submitNotSuitable=async function(jobKey,i){const reason=$(`reject-reason-${i}`).value;const note=$(`reject-note-${i}`).value;const learn=$(`reject-learn-${i}`).checked;await reviewJob(jobKey,'not_suitable',reason,note,learn);}

  window.loadLearning=async function(){
    const d=await api('/api/learning'); $('lfTotal').textContent=d.stats.feedback_total;$('lfBad').textContent=d.stats.not_suitable;$('lfRules').textContent=d.stats.active_rules;
    $('learnedRules').innerHTML=d.rules.length?d.rules.map(r=>`<div class="learning-rule"><span class="pill">${esc(r.scope)}</span><span class="rule-term">${esc(r.term)}</span><span>${r.weight}</span><span>${r.evidence_count} signals</span><span><button class="btn small" onclick="toggleRule(${r.id},${!r.enabled})">${r.enabled?'Disable':'Enable'}</button> <button class="btn small danger" onclick="removeRule(${r.id})">Delete</button></span></div>`).join(''):'<div class="muted" style="padding:16px">No learned rules yet.</div>';
    $('feedbackBody').innerHTML=d.feedback.map(f=>`<tr><td>${esc(f.title)}<div class="muted">${esc(f.company)}</div></td><td>${esc(f.suitability)}</td><td>${esc(f.reason||'—')}</td><td>${esc((f.created_at||'').slice(0,16).replace('T',' '))}</td></tr>`).join('');
  }
  window.toggleRule=async function(id,enabled){await api(`/api/learning/rules/${id}`,{method:'PUT',body:JSON.stringify({enabled})});loadLearning();}
  window.removeRule=async function(id){if(!confirm('Delete this learned rule?'))return;await api(`/api/learning/rules/${id}`,{method:'DELETE'});loadLearning();}

  injectStyles(); installOverview(); installLearning(); loadReviewJobs().catch(e=>toast(e.message,true));
})();
