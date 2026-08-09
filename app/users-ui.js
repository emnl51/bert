(() => {
  const nav=document.querySelector('.nav'), main=document.querySelector('.main');
  if(!nav||!main||document.getElementById('users')) return;
  const button=document.createElement('button');button.dataset.tab='users';button.textContent='Users';nav.appendChild(button);
  const section=document.createElement('section');section.id='users';section.className='section';section.innerHTML=`
    <div class="section-title"><div><h2>User management</h2><div class="hint">New users register from the public sign-in page and verify their email before activation.</div></div><button class="btn" type="button" onclick="loadUsers()">Refresh</button></div>
    <div class="table-wrap"><table><thead><tr><th>User</th><th>Role</th><th>Status</th><th>Verified</th><th>Last sign in</th><th>Sessions</th><th>Actions</th></tr></thead><tbody id="usersBody"></tbody></table></div>
    <div class="section-title"><h2>Registration requests</h2></div>
    <div class="table-wrap"><table><thead><tr><th>Email</th><th>State</th><th>Requested</th><th>Expires</th><th>Actions</th></tr></thead><tbody id="registrationsBody"></tbody></table></div>`;
  main.appendChild(section);

  window.loadUsers=async function(){
    try{
      const data=await api('/api/admin/users');
      const users=data.users||[], registrations=data.registrations||[];
      document.getElementById('usersBody').innerHTML=users.length?users.map(user=>`<tr><td><strong>${esc(user.full_name)}</strong><br><span class="muted">${esc(user.email)}</span></td><td>${esc(user.role)}</td><td>${esc(user.status)}</td><td>${dt(user.email_verified_at)}</td><td>${dt(user.last_login_at)}</td><td>${user.active_sessions}</td><td><div class="actions" style="margin:0"><button class="btn small" onclick="setAccountStatus(${user.id},'${user.status==='active'?'disabled':'active'}')">${user.status==='active'?'Disable':'Enable'}</button><button class="btn small" onclick="revokeAccountSessions(${user.id})">Sign out all</button></div></td></tr>`).join(''):'<tr><td colspan="7" class="muted">No registered users.</td></tr>';
      document.getElementById('registrationsBody').innerHTML=registrations.length?registrations.map(item=>`<tr><td>${esc(item.email)}</td><td>${esc(item.state)}</td><td>${dt(item.created_at)}</td><td>${dt(item.expires_at)}</td><td>${item.state==='pending'?`<button class="btn small danger" onclick="revokeRegistration(${item.id})">Revoke</button>`:'—'}</td></tr>`).join(''):'<tr><td colspan="5" class="muted">No registration requests.</td></tr>';
    }catch(error){toast(error.message,true)}
  };
  window.setAccountStatus=async function(id,status){try{await api(`/api/admin/users/${id}/status`,{method:'PUT',body:JSON.stringify({status})});toast(`User ${status}`);await loadUsers()}catch(error){toast(error.message,true)}};
  window.revokeAccountSessions=async function(id){try{await api(`/api/admin/users/${id}/revoke-sessions`,{method:'POST'});toast('User sessions revoked');await loadUsers()}catch(error){toast(error.message,true)}};
  window.revokeRegistration=async function(id){try{await api(`/api/admin/registrations/${id}/revoke`,{method:'POST'});toast('Registration revoked');await loadUsers()}catch(error){toast(error.message,true)}};
  button.addEventListener('click',()=>{
    document.querySelectorAll('.nav button').forEach(item=>item.classList.remove('active'));button.classList.add('active');
    document.querySelectorAll('.section').forEach(item=>item.classList.remove('active'));section.classList.add('active');
    document.getElementById('pageTitle').textContent='Users';
    try{localStorage.setItem('jobtrack-tab','users')}catch(_){ }
    loadUsers();
  });
  try{if(localStorage.getItem('jobtrack-tab')==='users')setTimeout(()=>button.click(),120)}catch(_){ }
})();
