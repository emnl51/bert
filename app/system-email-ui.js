(() => {
  const $=id=>document.getElementById(id), nav=document.querySelector('.nav'), main=document.querySelector('.main');
  if(!nav||!main||$('systemEmail')) return;
  const button=document.createElement('button');button.dataset.tab='systemEmail';button.textContent='System Email';nav.appendChild(button);
  const section=document.createElement('section');section.id='systemEmail';section.className='section';section.innerHTML=`
    <div class="section-title"><div><h2>System email</h2><div class="hint">Used for account activation and security messages. These settings are separate from each user's job notifications.</div></div><button class="btn" type="button" onclick="loadSystemEmailSettings()">Refresh</button></div>
    <div class="card"><div id="systemEmailState" class="warning" style="display:none"></div><div class="form-grid">
      <div class="field full"><label>Public base URL</label><input id="system_public_base_url" type="url" placeholder="https://bert.example.com"><div class="hint">Activation links start with this externally reachable HTTPS address.</div></div>
      <div class="field"><label>Activation link lifetime (hours)</label><input id="system_registration_lifetime" type="number" min="1" max="168" value="24"></div>
      <div class="field"><label>SMTP host</label><input id="system_smtp_host" placeholder="smtp.gmail.com"></div>
      <div class="field"><label>Port</label><input id="system_smtp_port" type="number" min="1" max="65535" value="587"></div>
      <div class="field"><label>Username</label><input id="system_smtp_username" autocomplete="username"></div>
      <div class="field"><label>Password</label><input id="system_smtp_password" type="password" autocomplete="new-password" placeholder="Leave blank to keep current password"><div id="systemSmtpSecret" class="hint"></div></div>
      <div class="field"><label>From address</label><input id="system_email_from" type="email" placeholder="bert@example.com"></div>
      <div class="field"><label><input id="system_smtp_use_tls" type="checkbox" style="width:auto" checked> Use STARTTLS</label><div class="hint">Use port 587 for Gmail and most STARTTLS providers.</div></div>
    </div><div class="actions"><button class="btn primary" type="button" onclick="saveSystemEmailSettings()">Save system email</button><span id="systemEmailStatus" class="status"></span></div></div>
    <div class="card" style="margin-top:14px"><h3 style="margin-top:0">Send test</h3><div class="inline"><div class="field"><label>Test recipient</label><input id="system_test_email" type="email" placeholder="you@example.com"></div><button class="btn" type="button" onclick="testSystemEmail()">Send test email</button></div><div class="hint">Save the configuration first. The test uses the same SMTP path as account activation emails.</div></div>
    <div class="card" style="margin-top:14px"><b>Secret handling</b><div class="hint">The SMTP password is encrypted in SQLite with APP_SECRET_KEY and is never returned to this browser after saving. Existing environment values remain fallback defaults until replaced here.</div></div>`;
  main.appendChild(section);

  window.loadSystemEmailSettings=async function(){
    try{
      const data=await api('/api/admin/system-email');
      $('system_public_base_url').value=data.public_base_url||'';$('system_registration_lifetime').value=data.registration_lifetime_hours||24;
      $('system_smtp_host').value=data.system_smtp_host||'';$('system_smtp_port').value=data.system_smtp_port||587;
      $('system_smtp_username').value=data.system_smtp_username||'';$('system_email_from').value=data.system_email_from||'';
      $('system_smtp_use_tls').checked=Boolean(data.system_smtp_use_tls);$('system_smtp_password').value='';
      $('systemSmtpSecret').textContent=data.system_smtp_password==='configured'?'Password configured. Enter a new value only to replace it.':'No password configured.';
      $('systemEmailState').style.display=data.configured?'none':'block';$('systemEmailState').textContent=data.configured?'':'System email is not configured. Complete the public URL, SMTP host and From address.';
    }catch(error){toast(error.message,true)}
  };
  window.saveSystemEmailSettings=async function(){
    try{
      const body={public_base_url:$('system_public_base_url').value.trim(),registration_lifetime_hours:+$('system_registration_lifetime').value||24,system_smtp_host:$('system_smtp_host').value.trim(),system_smtp_port:+$('system_smtp_port').value||587,system_smtp_username:$('system_smtp_username').value.trim(),system_smtp_password:$('system_smtp_password').value,system_smtp_use_tls:$('system_smtp_use_tls').checked,system_email_from:$('system_email_from').value.trim()};
      await api('/api/admin/system-email',{method:'PUT',body:JSON.stringify(body)});$('systemEmailStatus').textContent='Saved';$('systemEmailStatus').className='status ok';toast('System email settings saved');await loadSystemEmailSettings();
    }catch(error){$('systemEmailStatus').textContent=error.message;$('systemEmailStatus').className='status error';toast(error.message,true)}
  };
  window.testSystemEmail=async function(){
    const email=$('system_test_email').value.trim();if(!email){toast('Enter a test recipient',true);return}
    try{await api('/api/admin/system-email/test',{method:'POST',body:JSON.stringify({email})});toast('System test email sent')}catch(error){toast(error.message,true)}
  };
  button.addEventListener('click',()=>{
    document.querySelectorAll('.nav button').forEach(item=>item.classList.remove('active'));button.classList.add('active');
    document.querySelectorAll('.section').forEach(item=>item.classList.remove('active'));section.classList.add('active');$('pageTitle').textContent='System Email';
    try{localStorage.setItem('jobtrack-tab','systemEmail')}catch(_){ }loadSystemEmailSettings();
  });
  try{if(localStorage.getItem('jobtrack-tab')==='systemEmail')setTimeout(()=>button.click(),120)}catch(_){ }
})();
