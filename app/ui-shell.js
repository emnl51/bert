(() => {
  const $ = id => document.getElementById(id);
  const SHELL = window.APP_SHELL || {};
  const USER_HIDDEN_TABS = new Set(['sources','search','keywords','runs','users','systemEmail','database','logs','updates']);
  const NAV = {
    overview:['⌂','Control Panel'], searchJobs:['▤','Jobs'], jobReview:['✓','Job Review'],
    applications:['→','Applications'], intelligence:['◇','Intelligence'], candidates:['◎','Candidate Profiles'],
    learning:['+','Learning'], profiles:['◉','Search Profiles'], interface:['◐','Interface'], sources:['◫','Sources'],
    search:['⌕','Global Search'], keywords:['#','Ranking Rules'], notifications:['↗','Notifications'],
    runs:['↻','Run History'], users:['◎','Users'], systemEmail:['@','System Email'], database:['DB','Database'], logs:['>_','Logs'], updates:['↑','Updates']
  };
  const GROUPS = [
    {key:'controlPanel',label:'Control Panel',icon:'⌂',primary:'overview',tabs:[]},
    {key:'jobs',label:'Jobs',icon:'▤',primary:'searchJobs',tabs:['applications']},
    {key:'jobReview',label:'Job Review',icon:'✓',primary:'jobReview',tabs:['intelligence','candidates','learning']},
    {key:'settings',label:'Settings',icon:'⚙',primary:null,tabs:['profiles','interface','sources','search','keywords','notifications']},
    {key:'administration',label:'Administration',icon:'▦',primary:null,tabs:['runs','users','systemEmail','database','logs','updates']},
  ];
  const PAGE_CONTEXT = {
    overview:'Your search activity, applications and next steps at a glance.',
    searchJobs:'Manage automated searches, schedules and connected profiles.',
    jobReview:'Review opportunities and train matching for each search profile.',
    applications:'Follow every application from first interest to final decision.',
    intelligence:'Understand candidate fit, job requirements and recommendations.',
    candidates:'Keep your experience, skills and application documents organized.',
    learning:'See how your feedback improves future job recommendations.',
    profiles:'Define the roles, locations and working arrangements you want.',
    interface:'Choose the language and appearance used in this browser.',
    sources:'Choose where new opportunities are discovered.',
    search:'Adjust shared search preferences and automated schedules.',
    keywords:'Refine positive ranking signals and excluded terms.',
    notifications:'Control how you receive job and application updates.',
    runs:'Inspect completed searches and provider activity.',
    users:'Manage workspace accounts and access.',
    systemEmail:'Configure account invitations and system email delivery.',
    database:'Create backups and manage your application database.',
    logs:'Review application events and operational diagnostics.',
    updates:'Check your installed release and safely deploy available updates.'
  };
  const TURKISH = {
    'Dashboard':'Ana panel','Overview':'Genel bakış','Control Panel':'Kontrol paneli','Jobs':'İş ilanları','Job Review':'İlan inceleme','Applications':'Başvurular',
    'Intelligence':'Akıllı analiz','Candidate Profiles':'Aday profilleri','Learning':'Öğrenme','Search Profiles':'Arama profilleri',
    'Search profiles':'Arama profilleri','Sources':'Kaynaklar','Global Search':'Genel arama','Ranking Rules':'Sıralama kuralları',
    'Notifications':'Bildirimler','Run History':'Çalışma geçmişi','Users':'Kullanıcılar','System Email':'Sistem e-postası',
    'Database':'Veritabanı','Logs':'Kayıtlar','Updates':'Güncellemeler','Settings':'Ayarlar','Administration':'Yönetim','Interface':'Arayüz',
    'Administrator':'Yönetici','Your workspace':'Çalışma alanınız','Your job search workspace':'İş arama çalışma alanınız',
    'Keep profiles, opportunities and applications moving in one place.':'Profilleri, fırsatları ve başvuruları tek yerden yönetin.',
    'Review jobs':'İlanları incele','Job Review Queue':'İlan inceleme listesi','Search profile':'Arama profili','Decision':'Karar',
    'Language requirement':'Dil gereksinimi','Ad language':'İlan dili','Min fit':'En düşük uyum','Refresh jobs':'İlanları yenile',
    'Active':'Aktif','Unreviewed':'İncelenmedi','Suitable':'Uygun','Maybe':'Belki','Not suitable':'Uygun değil','All':'Tümü',
    'Recommended':'Önerilen','English-first':'Öncelikle İngilizce','German-growth':'Almanca geliştirmeye uygun',
    'B2 stretch':'B2 gelişim fırsatı','Unclear':'Belirsiz','Profile preference':'Profil tercihi','German (DE)':'Almanca (DE)',
    'English (EN)':'İngilizce (EN)','Mixed (DE/EN)':'Karışık (DE/EN)','Unknown':'Bilinmiyor','Overall fit':'Genel uyum',
    'Job fit':'İş uyumu','Language fit':'Dil uyumu','Strong profile match':'Profilinizle güçlü eşleşme',
    'Provider search phrases':'Sağlayıcı arama ifadeleri','Target positions and roles':'Hedef pozisyonlar ve roller',
    'Working arrangements':'Çalışma biçimleri','Advanced scoring keywords (JSON)':'Gelişmiş puanlama anahtar kelimeleri (JSON)',
    'One phrase per line. These are provider queries, not scoring rules.':'Her satıra bir ifade. Bunlar sağlayıcı sorgularıdır, puanlama kuralı değildir.',
    'One role per line. Used for role matching and bilingual expansion.':'Her satıra bir rol. Rol eşleştirme ve iki dilli genişletme için kullanılır.',
    'One format per line. Part-time hours are also recognized automatically.':'Her satıra bir çalışma biçimi. Yarı zamanlı saatler otomatik tanınır.',
    'Guided profile builder':'Rehberli profil oluşturucu','Choose your real target roles, working arrangements and language ability; the guide creates ready-to-use job-board searches.':'Gerçek hedef rollerinizi, çalışma biçiminizi ve dil seviyenizi seçin; kılavuz ilan siteleri için hazır arama ifadeleri oluşturur.',
    'Start with a profile example':'Örnek profille başlayın','Choose an example':'Örnek seçin','Example actions':'Örnek işlemleri','Use profile example':'Örnek profili kullan',
    'Technical support · part-time':'Teknik destek · yarı zamanlı','Engineering · full-time':'Mühendislik · tam zamanlı','Technical office · minijob':'Teknik ofis · minijob',
    '1. Which positions match your experience?':'1. Deneyiminize hangi pozisyonlar uyuyor?','2. Which working arrangements are acceptable?':'2. Hangi çalışma biçimlerini kabul ediyorsunuz?',
    'Quality / inspection':'Kalite / kontrol','Production / manufacturing':'Üretim / imalat','Production planning':'Üretim planlama','Process engineering':'Proses mühendisliği',
    'Technical office / administration':'Teknik ofis / idari işler','Procurement / purchasing':'Satın alma / tedarik','Logistics / supply chain':'Lojistik / tedarik zinciri',
    'Full-time / Vollzeit':'Tam zamanlı / Vollzeit','Part-time / Teilzeit':'Yarı zamanlı / Teilzeit','Working student / Werkstudent':'Öğrenci işi / Werkstudent',
    'Currently enrolled at a university':'Hâlen üniversite öğrencisiyim','Preferred weekly hours':'Tercih edilen haftalık saat','Availability':'Uygun çalışma zamanı',
    'Any suitable time':'Uygun herhangi bir zaman','Afternoons / after 14:00':'Öğleden sonra / 14.00 sonrası','Flexible working hours':'Esnek çalışma saatleri',
    'Current German ability':'Mevcut Almanca seviyeniz','Current English ability':'Mevcut İngilizce seviyeniz',
    '3. Which languages should job-board searches use?':'3. İlan sitelerinde hangi dillerde arama yapılsın?','German job titles':'Almanca pozisyon adları','English job titles':'İngilizce pozisyon adları',
    '4. Preview provider-ready search phrases':'4. İlan sitelerine hazır arama ifadelerini önizleyin','Apply guide to profile':'Kılavuzu profile uygula','Check profile targeting':'Profil hedeflerini kontrol et',
    'Choose a role and working arrangement to preview search phrases.':'Arama ifadelerini görmek için rol ve çalışma biçimi seçin.',
    'Choose at least one target role.':'En az bir hedef rol seçin.','Choose at least one eligible working arrangement.':'En az bir uygun çalışma biçimi seçin.',
    'Choose German or English provider queries.':'Almanca veya İngilizce arama dili seçin.','Working-student searches require current university enrollment.':'Werkstudent aramaları için güncel üniversite öğrenciliği gerekir.',
    'Create separate full-time and part-time profiles for more precise matches.':'Daha isabetli eşleşmeler için tam ve yarı zamanlı profilleri ayırın.',
    'Some providers only run the first 6–8 queries; role families are interleaved automatically.':'Bazı kaynaklar yalnızca ilk 6–8 sorguyu çalıştırır; rol aileleri otomatik dengelenir.',
    'New profile':'Yeni profil','Edit search profile':'Arama profilini düzenle','New search profile':'Yeni arama profili',
    'Name':'Ad','Slug':'Kısa ad','Primary location':'Ana konum','Location terms':'Konum terimleri',
    'Minimum Overall Fit':'En düşük genel uyum','Minimum Language Fit':'En düşük dil uyumu','Language weight %':'Dil ağırlığı %',
    'Current German':'Mevcut Almanca','Maximum preferred German':'Tercih edilen en yüksek Almanca','Preferred ad languages':'Tercih edilen ilan dilleri',
    'German':'Almanca','English':'İngilizce','Mixed':'Karışık','Enabled':'Etkin','Disabled':'Devre dışı','Default profile':'Varsayılan profil',
    'Show B2 stretch':'B2 fırsatlarını göster','Hide German-heavy':'İleri Almanca isteyenleri gizle','Prefer German-growth':'Almanca gelişimini tercih et',
    'Save profile':'Profili kaydet','Close':'Kapat','Edit':'Düzenle','Delete':'Sil','Use in review':'İncelemede kullan',
    'Run now':'Şimdi çalıştır','Duplicate':'Çoğalt','Save':'Kaydet','Refresh':'Yenile','Find a page…':'Sayfa ara…',
    'No matching pages':'Eşleşen sayfa yok','Theme':'Tema','System theme':'Sistem teması','Light theme':'Açık tema','Dark theme':'Koyu tema','Language':'Dil','Interface settings':'Arayüz ayarları','Personalize language and appearance for this browser.':'Bu tarayıcı için dil ve görünümü kişiselleştirin.','Appearance':'Görünüm','Follow this device':'Bu cihazı takip et','Always use light colors':'Her zaman açık renkleri kullan','Always use dark colors':'Her zaman koyu renkleri kullan','Interface language':'Arayüz dili','Changes are saved automatically in this browser.':'Değişiklikler bu tarayıcıya otomatik kaydedilir.','Profile Learning':'Profil öğrenmesi','Positive events':'Olumlu geri bildirim',
    'Active boosts':'Aktif güçlendirmeler','Active penalties':'Aktif cezalar','Learned preference rules':'Öğrenilmiş tercih kuralları',
    'Recent review feedback':'Son inceleme geri bildirimleri','Your search activity, applications and next steps at a glance.':'Aramalarınız, başvurularınız ve sonraki adımlar bir bakışta.',
    'Manage automated searches, schedules and connected profiles.':'Otomatik aramaları, zamanlamaları ve bağlı profilleri yönetin.',
    'Review opportunities and train matching for each search profile.':'Fırsatları inceleyin ve her profil için eşleştirmeyi geliştirin.',
    'Follow every application from first interest to final decision.':'Her başvuruyu ilk ilgiden nihai karara kadar takip edin.',
    'Define the roles, locations and working arrangements you want.':'İstediğiniz rolleri, konumları ve çalışma biçimlerini belirleyin.',
    'Application Workspace':'Başvuru çalışma alanı','Move applications, plan follow-ups and keep every next step visible.':'Başvuruları ilerletin, takipleri planlayın ve sonraki adımları görünür tutun.',
    'To Apply':'Başvurulacak','Applied':'Başvuruldu','Interview':'Mülakat','Offer':'Teklif','Rejected':'Reddedildi','Due actions':'Bekleyen işlemler',
    'Stage':'Aşama','All stages':'Tüm aşamalar','Board':'Pano','List':'Liste','Add job':'İlan ekle','No applications':'Başvuru yok',
    'Application funnel':'Başvuru hunisi','Source progression':'Kaynak ilerlemesi','Tracked':'Takip edilen','Interview+':'Mülakat+','Offers':'Teklifler',
    'Applied date':'Başvuru tarihi','Next action':'Sonraki işlem','Next action date':'Sonraki işlem tarihi','Contact':'İletişim kişisi','Notes':'Notlar',
    'Save application':'Başvuruyu kaydet','Export for career-ops':'career-ops için dışa aktar','Open job':'İlanı aç','Activity':'Etkinlik',
    'Add a job':'İlan ekle','Paste a public vacancy into Bert and review the fields before saving.':'Herkese açık bir ilanı Bert’e yapıştırın ve kaydetmeden önce alanları kontrol edin.',
    'Position':'Pozisyon','Company':'Şirket','Location':'Konum','Job URL':'İlan bağlantısı','Published date':'Yayın tarihi','Remote position':'Uzaktan çalışma',
    'Original job description':'Orijinal ilan açıklaması','Public vacancy text only. Do not paste private correspondence or credentials.':'Yalnızca herkese açık ilan metni. Özel yazışma veya kimlik bilgisi eklemeyin.',
    'Save and track':'Kaydet ve takip et','Cancel':'İptal','Details':'Ayrıntılar','No next action planned':'Sonraki işlem planlanmadı','No application data yet.':'Henüz başvuru verisi yok.'
  };
  let interfaceLanguage='en';try{interfaceLanguage=localStorage.getItem('bert-interface-language')==='tr'?'tr':'en'}catch(_){}
  const THEME_KEY='bert-theme';
  let themePreference='system';
  try{const savedTheme=localStorage.getItem(THEME_KEY);if(['light','dark','system'].includes(savedTheme))themePreference=savedTheme}catch(_){}
  const systemTheme=window.matchMedia?.('(prefers-color-scheme:dark)');

  function applyTheme(preference=themePreference){
    themePreference=['light','dark','system'].includes(preference)?preference:'system';
    const resolved=themePreference==='system'?(systemTheme?.matches?'dark':'light'):themePreference;
    document.documentElement.dataset.theme=resolved;
    document.documentElement.style.colorScheme=resolved;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content',resolved==='dark'?'#0b1220':'#f6f7fb');
    $('jtThemeSelect')?.setAttribute('data-resolved-theme',resolved);
  }
  applyTheme();
  systemTheme?.addEventListener?.('change',()=>{if(themePreference==='system')applyTheme('system')});

  function translateInterface(root=document.body){
    if(interfaceLanguage!=='tr'||!root)return;
    const translateNode=node=>{const raw=node.nodeValue,trimmed=raw.trim(),translated=TURKISH[trimmed];if(translated)node.nodeValue=raw.replace(trimmed,translated)};
    if(root.nodeType===3){translateNode(root);return}
    if(root.nodeType!==1&&root.nodeType!==9)return;
    if(root.matches?.('script,style,textarea,[data-no-translate]'))return;
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let node;
    while((node=walker.nextNode()))if(!node.parentElement?.closest('script,style,textarea,[data-no-translate]'))translateNode(node);
    if(root.matches?.('[placeholder]')&&TURKISH[root.getAttribute('placeholder')])root.setAttribute('placeholder',TURKISH[root.getAttribute('placeholder')]);
    root.querySelectorAll?.('[placeholder]').forEach(element=>{const value=element.getAttribute('placeholder');if(TURKISH[value])element.setAttribute('placeholder',TURKISH[value])});
    document.documentElement.lang='tr';
  }

  function installStyles(){
    if($('jobtrack-v16-style')) return;
    const style=document.createElement('style'); style.id='jobtrack-v16-style'; style.textContent=`
      :root{--jt-sidebar:244px;--jt-sidebar-mini:72px;--jt-mobile-top:64px;--jt-radius:14px;--jt-bg:#f5f7fb;--jt-card:#fff;--jt-border:#e2e8f0;--jt-ink:#0f172a;--jt-soft:#64748b;--jt-blue:#2563eb;--jt-blue-dark:#1d4ed8}
      html{scroll-behavior:smooth}body{background:radial-gradient(circle at 85% -10%,#eaf1ff 0,transparent 28%),linear-gradient(180deg,#f8fafc 0,#f4f7fb 100%);overflow-x:hidden}
      body.jt-menu-open{overflow:hidden}.app{grid-template-columns:var(--jt-sidebar) minmax(0,1fr);transition:grid-template-columns .2s ease;min-height:100dvh}.app.jt-collapsed{grid-template-columns:var(--jt-sidebar-mini) minmax(0,1fr)}
      .side{width:auto;min-width:0;height:100dvh;position:sticky;top:0;padding:16px 11px 12px;background:#101827;z-index:40;display:flex;flex-direction:column;overflow:hidden;border-right:1px solid rgba(148,163,184,.1)}
      .brand{padding:4px 9px 17px;font-size:19px;white-space:nowrap;overflow:hidden}.brand small{opacity:.58}.jt-brand-row{display:flex;align-items:center;justify-content:space-between;gap:8px}.jt-collapse{width:34px;height:34px;border:0;background:transparent;color:#94a3b8;border-radius:9px;cursor:pointer;flex:none;font-size:17px}.jt-collapse:hover{background:rgba(255,255,255,.06);color:#fff}
      .nav{display:flex;flex-direction:column;gap:5px;overflow-y:auto;overflow-x:hidden;padding:0 1px 12px;scrollbar-width:thin}.nav button{display:flex;align-items:center;gap:10px;width:100%;min-height:38px;padding:7px 10px;margin:0;border:0;border-radius:9px;background:transparent;white-space:nowrap;font-size:13px;font-weight:560;transition:background .14s ease,color .14s ease;color:#aeb9ca}.nav button:hover{background:rgba(255,255,255,.065);color:#f8fafc;transform:none}.nav button.active{background:rgba(89,119,214,.2);color:#fff;box-shadow:inset 2px 0 0 #8ca7ff}.jt-nav-icon,.jt-group-icon{width:20px;text-align:center;font-size:13px;flex:none;color:#7f8da3}.nav button.active .jt-nav-icon{color:#b9c8ff}.jt-nav-label,.jt-group-label{min-width:0;overflow:hidden;text-overflow:ellipsis}
      .jt-nav-group{display:grid;gap:2px}.jt-nav-primary-row{display:flex;align-items:center;gap:2px}.jt-nav-primary-row>button[data-tab]{min-width:0;flex:1;font-weight:680}.jt-nav-group-toggle{font-weight:680!important}.jt-nav-expander{width:30px!important;min-width:30px!important;padding:0!important;justify-content:center!important;color:#77869d!important}.jt-nav-chevron{display:block;font-size:13px;transition:transform .16s ease}.jt-nav-group.is-open .jt-nav-chevron{transform:rotate(90deg)}
      .jt-nav-group-panel{display:none;gap:1px;margin:1px 0 5px 30px;padding-left:9px;border-left:1px solid rgba(148,163,184,.16)}.jt-nav-group.is-open>.jt-nav-group-panel{display:grid}.jt-nav-group-panel>button{min-height:34px;padding:6px 9px;font-size:12px;font-weight:520;border-radius:8px}.jt-nav-group-panel .jt-nav-icon{width:17px;font-size:11px}
      .app.jt-collapsed .brand .jt-brand-text,.app.jt-collapsed .brand small,.app.jt-collapsed .jt-nav-label,.app.jt-collapsed .jt-group-label{display:none}.app.jt-collapsed .brand{padding-left:9px}.app.jt-collapsed .jt-brand-row{justify-content:center}.app.jt-collapsed .nav button{justify-content:center;padding-inline:8px}.app.jt-collapsed .jt-nav-icon,.app.jt-collapsed .jt-group-icon{font-size:15px}.app.jt-collapsed .jt-collapse{transform:rotate(180deg)}
      .app.jt-collapsed .jt-nav-expander,.app.jt-collapsed .jt-nav-group-panel{display:none!important}.app.jt-collapsed .nav{gap:5px}.app.jt-collapsed .jt-nav-group{gap:1px}
      .main{max-width:none;width:100%;min-width:0;padding:24px clamp(18px,2.5vw,38px) 50px}.top{min-height:62px;position:sticky;top:0;z-index:20;margin:-10px 0 20px;padding:10px 0;background:rgba(248,250,252,.86);backdrop-filter:blur(14px);display:flex;gap:14px}.top h1{font-size:clamp(21px,2vw,27px);letter-spacing:-.035em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.top-actions{display:flex;gap:8px;align-items:center}.jt-mobile-menu{display:none;width:42px;height:42px;border:1px solid var(--jt-border);background:white;border-radius:10px;font-size:20px;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 3px 10px rgba(15,23,42,.05)}
      .card{border-radius:var(--jt-radius);border-color:var(--jt-border);box-shadow:0 8px 28px rgba(15,23,42,.045);padding:clamp(14px,1.8vw,20px)}.grid{grid-template-columns:repeat(4,minmax(0,1fr));gap:13px}.metric{font-size:clamp(23px,2.2vw,30px)}.section-title{margin:26px 0 11px}.section-title h2{font-size:19px;letter-spacing:-.015em}
      .btn{min-height:38px;border-radius:9px;transition:transform .12s ease,box-shadow .12s ease,background .12s ease}.btn:hover{transform:translateY(-1px);box-shadow:0 5px 14px rgba(15,23,42,.08)}.btn.primary{background:linear-gradient(135deg,var(--jt-blue),var(--jt-blue-dark))}.btn.small{min-height:31px}.field input,.field select,.field textarea,select,input[type=date]{min-height:40px;border-color:#cbd5e1}.field input:focus,.field select:focus,.field textarea:focus,select:focus,input:focus{outline:3px solid rgba(37,99,235,.11);border-color:#60a5fa}
      .table-wrap{max-width:100%;overflow:auto;border-radius:var(--jt-radius);-webkit-overflow-scrolling:touch}.table-wrap table{min-width:860px}.table-wrap th{top:0;z-index:2}.table-wrap td,.table-wrap th{padding:11px 12px}.actions{flex-wrap:wrap}.inline{flex-wrap:wrap}.form-grid,.two{min-width:0}.source-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
      .jt-sidebar-overlay{display:none;position:fixed;inset:0;background:rgba(15,23,42,.48);backdrop-filter:blur(2px);z-index:35}.toast{max-width:min(430px,calc(100vw - 28px));right:14px;bottom:14px}
      .jt-mobile-table{display:none}
      :root{--jt-radius:16px;--jt-bg:#f3f6fb;--jt-blue:#315eea;--jt-blue-dark:#2448c4}
      body{background:#f4f6fb}.side{border-right:1px solid rgba(148,163,184,.08)}
      .brand{padding:3px 9px 18px}.brand .jt-brand-text{font-size:19px;letter-spacing:-.035em}.brand small{margin-top:5px;font-size:10px;letter-spacing:.035em}
      .jt-sidebar-search{position:relative;margin:0 2px 16px}.jt-sidebar-search input{width:100%;height:40px;border:1px solid rgba(148,163,184,.18);border-radius:11px;background:rgba(255,255,255,.055);padding:0 38px 0 35px;color:#e6edf8;font-size:12px;outline:none}.jt-sidebar-search input::placeholder{color:#8390a7}.jt-sidebar-search input:focus{border-color:rgba(110,152,255,.72);background:rgba(255,255,255,.08);box-shadow:0 0 0 3px rgba(84,125,238,.14)}.jt-search-icon{position:absolute;left:12px;top:10px;color:#91a0b8;font-size:15px;pointer-events:none}.jt-search-shortcut{position:absolute;right:10px;top:10px;color:#8d9ab0;font-size:10px;border:1px solid rgba(148,163,184,.2);border-radius:4px;padding:1px 5px;pointer-events:none}
      .nav{flex:1;padding-bottom:14px}.nav button[hidden],.jt-nav-group[hidden],.jt-nav-empty[hidden]{display:none!important}.nav button.active{background:rgba(84,123,233,.18);box-shadow:inset 2px 0 0 #85a2ff}.jt-nav-group.has-active>.jt-nav-primary-row>button[data-tab],.jt-nav-group.has-active>.jt-nav-group-toggle{color:#f5f8ff}.jt-nav-empty{padding:15px 10px;color:#9aa7bc;font-size:12px}
      .jt-sidebar-footer{display:flex;align-items:center;gap:10px;margin-top:auto;padding:13px 8px 3px;border-top:1px solid rgba(148,163,184,.12)}.jt-user-avatar{display:grid;place-items:center;width:32px;height:32px;border-radius:50%;background:rgba(85,125,235,.15);color:#c1d1ff;font-size:12px;font-weight:750}.jt-user-copy{min-width:0}.jt-user-label{display:block;color:#e7edf7;font-size:12px;font-weight:680}.jt-user-meta{display:block;margin-top:2px;color:#7f8da3;font-size:10px}
      .app.jt-collapsed .jt-sidebar-search,.app.jt-collapsed .jt-user-copy{display:none}.app.jt-collapsed .jt-sidebar-footer{justify-content:center;padding-inline:0}
      .main{padding:27px clamp(24px,3.3vw,48px) 56px}.top{min-height:78px;margin:-10px 0 24px;padding:13px 0;background:rgba(244,246,251,.88);border-bottom:1px solid rgba(210,218,229,.72)}.jt-page-heading{min-width:0;flex:1}.jt-breadcrumb{margin-bottom:4px;color:#67758c;font-size:11px;font-weight:650;letter-spacing:.025em}.top h1{font-size:clamp(22px,2.1vw,29px)}.jt-page-description{margin-top:4px;color:#738097;font-size:12px}.top-actions .btn{min-height:39px;padding-inline:13px}.top-actions .btn.primary{box-shadow:0 5px 14px rgba(49,94,234,.2)}
      .section.active{animation:jt-section-enter .17s ease-out}@keyframes jt-section-enter{from{opacity:.7;transform:translateY(3px)}to{opacity:1;transform:translateY(0)}}.card{border-color:#e1e7f0;box-shadow:0 4px 18px rgba(25,40,70,.045)}.grid{gap:15px}.grid>.card{position:relative;overflow:hidden}.grid>.card::before{content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:#d4dcee}.grid>.card:nth-child(4n + 1)::before{background:#5579e8}.grid>.card:nth-child(4n + 2)::before{background:#6a8caa}.grid>.card:nth-child(4n + 3)::before{background:#618f83}.grid>.card:nth-child(4n)::before{background:#907da9}.grid>.card>.muted{font-size:11px;font-weight:680;letter-spacing:.02em}.metric{margin-top:8px;letter-spacing:-.035em}.section-title{margin-top:30px}.table-wrap{border-color:#e1e7f0;box-shadow:0 4px 18px rgba(25,40,70,.04)}.table-wrap th{background:#f8fafd;font-size:10px;letter-spacing:.065em}.table-wrap tbody tr:hover{background:#fafcff}
      .jt-overview-welcome{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:20px;padding:20px 22px;background:linear-gradient(115deg,#fff 0%,#f3f6ff 100%);border:1px solid #e1e7f0;border-radius:16px}.jt-overview-welcome h2{margin:0 0 5px;font-size:18px;letter-spacing:-.025em}.jt-overview-welcome p{margin:0;color:#69778b;font-size:12px}.jt-quick-actions{display:flex;flex-wrap:wrap;gap:8px}.jt-quick-action{min-height:36px;font-size:12px}
      @media(max-width:1280px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}.source-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.main{padding-inline:22px}}
      @media(max-width:980px){
        .app,.app.jt-collapsed{display:block}.side{position:fixed;left:0;top:0;bottom:0;width:min(310px,86vw);height:100dvh;transform:translateX(-102%);transition:transform .22s ease;z-index:50;padding-top:18px}.side.jt-open{transform:translateX(0)}.jt-sidebar-overlay.jt-open{display:block}.jt-collapse{display:none}.brand .jt-brand-text,.app.jt-collapsed .brand .jt-brand-text,.brand small,.app.jt-collapsed .brand small,.jt-nav-label,.app.jt-collapsed .jt-nav-label{display:block}.nav button,.app.jt-collapsed .nav button{justify-content:flex-start;padding:10px 12px}.main{padding:14px 18px 42px}.top{top:0;margin:-2px -2px 16px;padding:9px 2px;min-height:58px}.jt-mobile-menu{display:inline-flex}.top-actions .btn{padding-inline:10px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.form-grid,.two{grid-template-columns:1fr 1fr}.source-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
      }
      @media(max-width:980px){.jt-sidebar-search,.app.jt-collapsed .jt-sidebar-search{display:block}.jt-user-copy,.app.jt-collapsed .jt-user-copy{display:block}.jt-page-description{display:none}.main{padding-inline:18px}.top{min-height:66px}.jt-overview-welcome{align-items:flex-start;flex-direction:column}.jt-quick-actions{width:100%}}
      @media(max-width:720px){
        .main{padding:10px 12px 34px}.top{gap:8px}.top h1{font-size:21px;flex:1}.top-actions{gap:6px}.top-actions .btn{min-height:40px;font-size:12px;padding:7px 9px}.grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.card{padding:14px;border-radius:12px}.metric{font-size:23px}.form-grid,.two,.source-grid{grid-template-columns:1fr}.inline{display:grid;grid-template-columns:1fr;width:100%;align-items:stretch}.inline .field{width:100%}.inline>button{width:100%}.actions{display:grid;grid-template-columns:1fr}.actions .btn{width:100%}.section-title{align-items:flex-start;flex-direction:column}.section-title>select,.section-title>.inline{width:100%}
        .table-wrap{border:0;background:transparent;overflow:visible}.table-wrap table{display:block;min-width:0;width:100%}.table-wrap thead{display:none}.table-wrap tbody{display:grid;gap:10px;width:100%}.table-wrap tr{display:block;background:#fff;border:1px solid var(--jt-border);border-radius:12px;padding:6px 12px;box-shadow:0 5px 18px rgba(15,23,42,.04)}.table-wrap td{display:grid;grid-template-columns:minmax(92px,36%) minmax(0,1fr);gap:10px;width:100%;padding:8px 0;border-bottom:1px solid #edf0f5;white-space:normal;overflow-wrap:anywhere}.table-wrap td:last-child{border-bottom:0}.table-wrap td::before{content:attr(data-label);font-size:10px;text-transform:uppercase;letter-spacing:.055em;color:#64748b;font-weight:800;padding-top:2px}.table-wrap td[colspan]{display:block;text-align:center}.table-wrap td[colspan]::before{display:none}.decision{min-width:0}.notes-cell{max-width:none}.compact-select{width:100%;min-width:0}.source-toolbar{flex-direction:column;align-items:stretch}.source-toolbar .field{max-width:none!important}.source-toolbar .btn{width:100%}.jt-modal-backdrop{padding:10px}.jt-modal{border-radius:14px;padding:17px;max-height:94dvh}.jt-fields{grid-template-columns:1fr}.jt-fields .full{grid-column:auto}
      }
      @media(max-width:430px){.grid{grid-template-columns:1fr}.top-actions .btn:not(.primary){display:none}.main{padding-inline:10px}.card{padding:13px}.top h1{font-size:19px}.brand{font-size:19px}}
      @media(max-width:720px){.jt-breadcrumb{font-size:10px}.top h1{font-size:20px}.jt-overview-welcome{padding:16px}.jt-quick-actions{display:grid;grid-template-columns:1fr 1fr}.jt-quick-action{width:100%}.top-actions .btn{padding-inline:8px}.jt-sidebar-footer{padding-bottom:8px}}

      :root{color-scheme:light;--bg:#f6f7fb;--card:#ffffff;--text:#111827;--muted:#526174;--line:#d5dce7;--accent:#254fce;--accent-solid:#315eea;--accent2:#e9efff;--on-accent:#ffffff;--surface-soft:#f5f7fa;--focus:#6d28d9;--good:#12683f;--goodbg:#e6f6ed;--bad:#a51d15;--badbg:#fff0ef;--warn:#765000;--warnbg:#fff5d8;--shadow:0 4px 18px rgba(15,23,42,.06);--jt-bg:var(--bg);--jt-card:var(--card);--jt-border:var(--line);--jt-ink:var(--text);--jt-soft:var(--muted);--jt-blue:var(--accent-solid);--jt-blue-dark:#2448c4}
      html[data-theme="dark"]{color-scheme:dark;--bg:#090e16;--card:#141c28;--text:#f1f5f9;--muted:#b5c0d0;--line:#3a475b;--accent:#a9bcff;--accent-solid:#4f6fdb;--accent2:#202e50;--on-accent:#ffffff;--surface-soft:#1c2635;--focus:#d8b4fe;--good:#82e2af;--goodbg:#153b2a;--bad:#ffaaa3;--badbg:#462329;--warn:#ffd27a;--warnbg:#41331a;--shadow:0 8px 28px rgba(0,0,0,.34);--jt-blue:var(--accent-solid);--jt-blue-dark:#3f5fc4}
      body{background:var(--bg);color:var(--text)}.main{color:var(--text)}.card,.table-wrap,.review-toolbar,.profile-guide,.profile-guide-preview,.profile-guide-option,.profile-dialog,.jt-modal,.application-dialog,.application-card,.application-column,.source-card,.sj-form-card,.sj-rule-box,.job-card{background:var(--card);color:var(--text);border-color:var(--line)}
      .top{background:color-mix(in srgb,var(--bg) 88%,transparent);border-color:var(--line)}.top h1,.section-title h2,h1,h2,h3,.source-title,.job-title,.profile-card strong{color:var(--text)}.muted,.hint,.source-meta,.jt-page-description,.jt-breadcrumb{color:var(--muted)}
      .btn{background:var(--card);color:var(--text);border-color:var(--line)}.btn.primary,.btn.suitable{background:var(--accent-solid);border-color:var(--accent-solid);color:var(--on-accent)}.btn.danger,.btn.unsuitable{color:var(--bad)}
      input,select,textarea,.field input,.field select,.field textarea,input[type="date"]{background:var(--card);color:var(--text);border-color:var(--line)}input::placeholder,textarea::placeholder{color:var(--muted)}
      :where(a,button,input,select,textarea,[tabindex]):focus-visible{outline:3px solid var(--focus)!important;outline-offset:2px!important;box-shadow:none!important}.btn,.nav button,.jt-mobile-menu,.jt-collapse{min-height:44px}.btn.small{min-height:36px}
      th,.table-wrap th{background:var(--surface-soft);color:var(--muted);border-color:var(--line)}td,tr,.table-wrap td{border-color:var(--line)}.table-wrap tbody tr:hover{background:var(--surface-soft)}.pill,.stage,.lang.unclear{background:var(--surface-soft);color:var(--muted);border-color:var(--line)}
      .jt-overview-welcome{background:var(--card);border-color:var(--line)}.jt-overview-welcome p{color:var(--muted)}.grid>.card::before{background:var(--accent)}.warning{background:var(--warnbg);color:var(--warn);border-color:color-mix(in srgb,var(--warn) 45%,var(--line))}
      .jt-interface-settings{max-width:760px}.jt-interface-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.jt-setting-block{display:grid;gap:7px}.jt-setting-block label{font-weight:720}.jt-setting-block select{width:100%;min-height:44px}.jt-theme-preview{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:4px}.jt-theme-swatch{height:54px;border:1px solid var(--line);border-radius:10px;background:var(--surface-soft);padding:7px}.jt-theme-swatch::before{content:'';display:block;width:55%;height:7px;border-radius:4px;background:var(--muted);box-shadow:0 13px 0 color-mix(in srgb,var(--muted) 45%,transparent)}.jt-theme-swatch.active{border-color:var(--accent);box-shadow:0 0 0 2px color-mix(in srgb,var(--accent) 18%,transparent)}.jt-theme-swatch[data-theme-option="dark"]{background:#121925}.jt-theme-swatch[data-theme-option="dark"]::before{background:#d7dfed;box-shadow:0 13px 0 #66758d}.jt-theme-swatch[data-theme-option="system"]{background:linear-gradient(90deg,#f7f8fb 0 50%,#121925 50%)}
      .jt-skip-link{position:fixed;left:14px;top:10px;z-index:200;transform:translateY(-160%);padding:10px 14px;border-radius:9px;background:var(--accent);color:#fff;font-weight:700}.jt-skip-link:focus{transform:translateY(0)}body.jt-dialog-open{overflow:hidden}
      html[data-theme="dark"] .side{background:#0a111c;border-color:#2a3649}html[data-theme="dark"] .nav button{color:#c2ccda}html[data-theme="dark"] .nav button:hover,html[data-theme="dark"] .nav button.active{color:#fff}html[data-theme="dark"] .jt-nav-group-title{color:#91a0b5}html[data-theme="dark"] .jt-sidebar-search input{background:#111b2a;color:#f1f5f9;border-color:#38465a}html[data-theme="dark"] .jt-sidebar-search input::placeholder{color:#9aa8bb}
      html[data-theme="dark"] .job-insight.role,html[data-theme="dark"] .intel-ai-note,html[data-theme="dark"] .profile-guide{background:var(--accent2);color:var(--text)}html[data-theme="dark"] .reject-box,html[data-theme="dark"] .detected-box,html[data-theme="dark"] .sj-callout,html[data-theme="dark"] .source-hero,html[data-theme="dark"] .source-toolbar,html[data-theme="dark"] .sj-hero,html[data-theme="dark"] .sj-summary,html[data-theme="dark"] .fit-row,html[data-theme="dark"] .fit-box,html[data-theme="dark"] .intel-evidence-row,html[data-theme="dark"] .application-column-header,html[data-theme="dark"] .application-event,html[data-theme="dark"] .application-empty,html[data-theme="dark"] .job-detail-fact{background:var(--surface-soft);border-color:var(--line);color:var(--text)}
      html[data-theme="dark"] :where(.job-company,.job-meta,.job-language-reasons,.why-list,.source-meta,.sj-name-meta,.application-card-meta,.application-card-company,.intel-meta){color:var(--muted)}html[data-theme="dark"] hr{border-color:var(--line)!important}html[data-theme="dark"] a{color:var(--accent)}html[data-theme="dark"] .btn:hover{border-color:#61718a;background:#1d2939}html[data-theme="dark"] .btn.primary:hover,html[data-theme="dark"] .btn.suitable:hover{background:#5c7be2;border-color:#5c7be2;color:#fff}
      @media(max-width:720px){.table-wrap tr{background:var(--card);border-color:var(--line)}.table-wrap td{border-color:var(--line)}.jt-interface-grid{grid-template-columns:1fr}}
      @media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important;animation:none!important}}
    `; document.head.appendChild(style);
  }

  function decorateNav(){
    document.querySelectorAll('.nav button[data-tab]').forEach(btn=>{
      const key=btn.dataset.tab; const meta=NAV[key]||['•',btn.textContent.trim()];
      if(!btn.querySelector('.jt-nav-icon')) btn.innerHTML=`<span class="jt-nav-icon" aria-hidden="true">${meta[0]}</span><span class="jt-nav-label">${meta[1]}</span>`;
      btn.setAttribute('title',meta[1]);
    });
  }

  function setGroupExpanded(group,expanded){
    if(!group)return;
    group.classList.toggle('is-open',expanded);
    group.querySelector(':scope > .jt-nav-primary-row > .jt-nav-expander, :scope > .jt-nav-group-toggle')?.setAttribute('aria-expanded',String(expanded));
  }

  function groupNavigation(){
    const nav=document.querySelector('.nav'); if(!nav||nav.querySelector('.jt-nav-group')) return;
    const buttons=new Map([...nav.querySelectorAll(':scope > button[data-tab]')].map(btn=>[btn.dataset.tab,btn]));
    const active=[...buttons.values()].find(btn=>btn.classList.contains('active'));
    nav.replaceChildren();
    for(const group of GROUPS){
      const primary=group.primary?buttons.get(group.primary):null;
      const items=group.tabs.map(tab=>buttons.get(tab)).filter(Boolean);
      if(!primary&&!items.length)continue;
      const wrap=document.createElement('div');wrap.className='jt-nav-group';wrap.dataset.group=group.key;
      const panel=document.createElement('div');panel.id=`jt-nav-${group.key}`;panel.className='jt-nav-group-panel';
      items.forEach(btn=>panel.appendChild(btn));
      if(primary){
        primary.classList.add('jt-nav-primary');
        const row=document.createElement('div');row.className='jt-nav-primary-row';row.appendChild(primary);
        if(items.length){
          const expander=document.createElement('button');expander.type='button';expander.className='jt-nav-expander';expander.setAttribute('aria-controls',panel.id);expander.setAttribute('aria-label',`Toggle ${group.label} submenu`);expander.innerHTML='<span class="jt-nav-chevron" aria-hidden="true">›</span>';
          expander.addEventListener('click',()=>setGroupExpanded(wrap,!wrap.classList.contains('is-open')));
          row.appendChild(expander);
        }
        wrap.appendChild(row);
      }else{
        const toggle=document.createElement('button');toggle.type='button';toggle.className='jt-nav-group-toggle';toggle.setAttribute('aria-controls',panel.id);toggle.innerHTML=`<span class="jt-group-icon" aria-hidden="true">${group.icon}</span><span class="jt-group-label">${group.label}</span><span class="jt-nav-chevron" aria-hidden="true">›</span>`;
        toggle.addEventListener('click',()=>{const app=document.querySelector('.app');if(app?.classList.contains('jt-collapsed')){app.classList.remove('jt-collapsed');try{localStorage.setItem('jobtrack-sidebar-collapsed','0')}catch(_){}}setGroupExpanded(wrap,!wrap.classList.contains('is-open'))});
        wrap.appendChild(toggle);
      }
      if(items.length)wrap.appendChild(panel);
      const containsActive=primary===active||items.includes(active);wrap.classList.toggle('has-active',containsActive);setGroupExpanded(wrap,containsActive);
      nav.appendChild(wrap);
    }
  }

  function revealGroup(tab){
    const btn=document.querySelector(`.nav button[data-tab="${tab}"]`), group=btn?.closest('.jt-nav-group'); if(!group) return;
    document.querySelectorAll('.jt-nav-group').forEach(node=>{const active=node===group;node.classList.toggle('has-active',active);if(active)setGroupExpanded(node,true)});
  }

  function updatePageContext(tab){
    const group=GROUPS.find(item=>item.primary===tab||item.tabs.includes(tab));
    if($('jtBreadcrumb'))$('jtBreadcrumb').textContent=`${String(SHELL.appName||'Bert')} / ${group?.label||'Workspace'}`;
    if($('jtPageDescription'))$('jtPageDescription').textContent=PAGE_CONTEXT[tab]||'Manage your job search workspace.';
  }

  function installNavigationSearch(side){
    const nav=side.querySelector('.nav');if(!nav||$('jtNavigationSearch'))return;
    const search=document.createElement('label');search.className='jt-sidebar-search';
    search.innerHTML='<span class="jt-search-icon" aria-hidden="true">⌕</span><input id="jtNavigationSearch" type="search" placeholder="Find a page…" aria-label="Search navigation"><span class="jt-search-shortcut" aria-hidden="true">/</span>';
    side.insertBefore(search,nav);
    const empty=document.createElement('div');empty.className='jt-nav-empty';empty.textContent='No matching pages';empty.hidden=true;nav.appendChild(empty);
    search.querySelector('input').addEventListener('input',event=>{
      const query=event.target.value.trim().toLowerCase();let matches=0;
      nav.querySelectorAll('.jt-nav-group').forEach(group=>{
        const groupLabel=(GROUPS.find(item=>item.key===group.dataset.group)?.label||'').toLowerCase();let visible=0;
        group.querySelectorAll('button[data-tab]').forEach(button=>{const show=!query||groupLabel.includes(query)||button.textContent.toLowerCase().includes(query);button.hidden=!show;if(show){visible++;matches++}});
        group.hidden=!visible;
        if(query&&visible)setGroupExpanded(group,true);
        if(!query){const active=Boolean(group.querySelector('button[data-tab].active'));group.classList.toggle('has-active',active);setGroupExpanded(group,active)}
      });
      empty.hidden=!query||matches>0;
    });
  }

  function installInterfaceSettings(nav,main){
    if($('interface'))return;
    const button=document.createElement('button');button.dataset.tab='interface';button.textContent='Interface';nav.appendChild(button);
    const section=document.createElement('section');section.id='interface';section.className='section';section.innerHTML=`
      <div class="section-title"><div><h2>Interface settings</h2><div class="hint">Personalize language and appearance for this browser.</div></div></div>
      <div class="card jt-interface-settings"><div class="jt-interface-grid">
        <div class="jt-setting-block"><label for="jtThemeSelect">Appearance</label><select id="jtThemeSelect"><option value="system">System theme</option><option value="light">Light theme</option><option value="dark">Dark theme</option></select><div class="jt-theme-preview" aria-hidden="true"><div class="jt-theme-swatch" data-theme-option="system" title="Follow this device"></div><div class="jt-theme-swatch" data-theme-option="light" title="Always use light colors"></div><div class="jt-theme-swatch" data-theme-option="dark" title="Always use dark colors"></div></div></div>
        <div class="jt-setting-block"><label for="jtInterfaceLanguage">Interface language</label><select id="jtInterfaceLanguage"><option value="en">English</option><option value="tr">Türkçe</option></select><div class="hint">Changes are saved automatically in this browser.</div></div>
      </div></div>`;
    main.appendChild(section);
    const theme=$('jtThemeSelect');theme.value=themePreference;theme.addEventListener('change',event=>{try{localStorage.setItem(THEME_KEY,event.target.value)}catch(_){}applyTheme(event.target.value);document.querySelectorAll('.jt-theme-swatch').forEach(swatch=>swatch.classList.toggle('active',swatch.dataset.themeOption===event.target.value))});
    document.querySelectorAll('.jt-theme-swatch').forEach(swatch=>swatch.classList.toggle('active',swatch.dataset.themeOption===themePreference));
    const language=$('jtInterfaceLanguage');language.value=interfaceLanguage;language.addEventListener('change',event=>{try{localStorage.setItem('bert-interface-language',event.target.value)}catch(_){}location.reload()});
    button.addEventListener('click',()=>{document.querySelectorAll('.section').forEach(node=>node.classList.remove('active'));document.querySelectorAll('.nav button[data-tab]').forEach(node=>node.classList.remove('active'));section.classList.add('active');button.classList.add('active');if($('pageTitle'))$('pageTitle').textContent='Interface';revealGroup('interface');updatePageContext('interface');try{localStorage.setItem('jobtrack-tab','interface')}catch(_){}});
  }

  function installOverviewShortcuts(){
    const overview=$('overview');if(!overview||$('jtOverviewWelcome'))return;
    const welcome=document.createElement('div');welcome.id='jtOverviewWelcome';welcome.className='jt-overview-welcome';
    const shortcuts=[['jobReview','Review jobs'],['applications','Applications'],['profiles','Search profiles']].filter(([tab])=>document.querySelector(`.nav button[data-tab="${tab}"]`));
    welcome.innerHTML='<div><h2>Your job search workspace</h2><p>Keep profiles, opportunities and applications moving in one place.</p></div><div class="jt-quick-actions"></div>';
    shortcuts.forEach(([tab,label],index)=>{const button=document.createElement('button');button.type='button';button.className=`btn jt-quick-action${index===0?' primary':''}`;button.textContent=label;button.onclick=()=>document.querySelector(`.nav button[data-tab="${tab}"]`)?.click();welcome.querySelector('.jt-quick-actions').appendChild(button)});
    overview.insertBefore(welcome,overview.firstChild);
  }

  function annotateTables(root=document){
    root.querySelectorAll?.('.table-wrap table').forEach(table=>{
      const headers=[...table.querySelectorAll('thead th')].map(th=>th.textContent.trim());
      table.querySelectorAll('tbody tr').forEach(tr=>[...tr.children].forEach((td,i)=>{
        if(td.tagName==='TD'&&!td.hasAttribute('data-label')) td.setAttribute('data-label',headers[i]||'');
      }));
    });
  }

  function setMenu(open){
    document.querySelector('.side')?.classList.toggle('jt-open',open);
    $('.jtSidebarOverlay')?.classList.toggle('jt-open',open);
    document.body.classList.toggle('jt-menu-open',open);
    $('.jtMobileMenu')?.setAttribute('aria-expanded',String(open));
  }

  function installShell(){
    const app=document.querySelector('.app'), side=document.querySelector('.side'), top=document.querySelector('.top'), brand=document.querySelector('.brand');
    if(!app||!side||!top||!brand) return setTimeout(installShell,80);
    installStyles();
    if(!document.querySelector('meta[name="theme-color"]')){const meta=document.createElement('meta');meta.name='theme-color';document.head.appendChild(meta)}
    if(!$('jtMainContent'))app.querySelector('.main')?.setAttribute('id','jtMainContent');
    if(!document.querySelector('.jt-skip-link')){const skip=document.createElement('a');skip.className='jt-skip-link';skip.href='#jtMainContent';skip.textContent='Skip to content';document.body.prepend(skip)}
    const toastRegion=$('toast');if(toastRegion){toastRegion.setAttribute('role','status');toastRegion.setAttribute('aria-live','polite')}
    if(!SHELL.isAdmin){
      document.querySelectorAll('.nav button[data-tab]').forEach(btn=>{if(USER_HIDDEN_TABS.has(btn.dataset.tab))btn.remove()});
      document.querySelector('[onclick="runNow()"]')?.remove();
    }
    brand.innerHTML='<div class="jt-brand-row"><div><span class="jt-brand-text"></span><small></small></div><button class="jt-collapse" type="button" title="Collapse sidebar" aria-label="Collapse sidebar">‹</button></div>';
    brand.querySelector('.jt-brand-text').textContent=String(SHELL.appName||'JobTrack');
    brand.querySelector('small').textContent=`Smart Job Search · v${String(SHELL.version||'16')}`;
    const pageTitle=$('pageTitle');if(pageTitle){const heading=document.createElement('div');heading.className='jt-page-heading';heading.innerHTML='<div id="jtBreadcrumb" class="jt-breadcrumb"></div>';pageTitle.before(heading);heading.appendChild(pageTitle);const description=document.createElement('div');description.id='jtPageDescription';description.className='jt-page-description';heading.appendChild(description)}
    const mobile=document.createElement('button'); mobile.id='jtMobileMenu'; mobile.className='jt-mobile-menu'; mobile.type='button'; mobile.setAttribute('aria-label','Open navigation'); mobile.setAttribute('aria-expanded','false'); mobile.textContent='☰'; top.insertBefore(mobile,top.firstChild);
    const overlay=document.createElement('div'); overlay.id='jtSidebarOverlay'; overlay.className='jt-sidebar-overlay'; document.body.appendChild(overlay);
    try{if(localStorage.getItem('jobtrack-sidebar-collapsed')==='1')app.classList.add('jt-collapsed')}catch(_){ }
    brand.querySelector('.jt-collapse').onclick=()=>{app.classList.toggle('jt-collapsed');try{localStorage.setItem('jobtrack-sidebar-collapsed',app.classList.contains('jt-collapsed')?'1':'0')}catch(_){}};
    mobile.onclick=()=>setMenu(!side.classList.contains('jt-open')); overlay.onclick=()=>setMenu(false);
    document.addEventListener('keydown',e=>{if(e.key==='Escape'){if(document.activeElement===$('jtNavigationSearch')&&$('jtNavigationSearch').value){$('jtNavigationSearch').value='';$('jtNavigationSearch').dispatchEvent(new Event('input'))}else setMenu(false)}if(e.key==='/'&&!e.ctrlKey&&!e.metaKey&&!e.altKey&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)){e.preventDefault();if(window.innerWidth<=980)setMenu(true);$('jtNavigationSearch')?.focus()}});
    side.addEventListener('click',e=>{if(e.target.closest('.nav button[data-tab]')&&window.innerWidth<=980)setMenu(false)});
    installInterfaceSettings(side.querySelector('.nav'),main);groupNavigation();decorateNav();installNavigationSearch(side);annotateTables();installOverviewShortcuts();
    const footer=document.createElement('div');footer.className='jt-sidebar-footer';footer.innerHTML='<div class="jt-user-avatar" aria-hidden="true"></div><div class="jt-user-copy"><span class="jt-user-label"></span><span class="jt-user-meta"></span></div>';footer.querySelector('.jt-user-avatar').textContent=SHELL.isAdmin?'A':'U';footer.querySelector('.jt-user-label').textContent=SHELL.isAdmin?'Administrator':'Your workspace';footer.querySelector('.jt-user-meta').textContent=`Version ${String(SHELL.version||'16')}`;side.appendChild(footer);applyTheme(themePreference);
    updatePageContext(document.querySelector('.nav button[data-tab].active')?.dataset.tab||'overview');
    side.addEventListener('click',e=>{const btn=e.target.closest('.nav button[data-tab]');if(!btn)return;revealGroup(btn.dataset.tab);updatePageContext(btn.dataset.tab);try{localStorage.setItem('jobtrack-tab',btn.dataset.tab)}catch(_){}setTimeout(()=>{if($('pageTitle'))$('pageTitle').textContent=(NAV[btn.dataset.tab]||[])[1]||btn.textContent.trim()},0)});
    try{const saved=localStorage.getItem('jobtrack-tab');const savedButton=saved?document.querySelector(`.nav button[data-tab="${saved}"]`):null;if(savedButton&&!savedButton.classList.contains('active'))savedButton.click()}catch(_){}
    translateInterface();
    const observer=new MutationObserver(muts=>{decorateNav();for(const m of muts){m.addedNodes.forEach(n=>{if(n.nodeType===1)annotateTables(n);translateInterface(n)})}annotateTables()});
    observer.observe(document.body,{childList:true,subtree:true});
    window.addEventListener('resize',()=>{if(window.innerWidth>980)setMenu(false)});
  }
  installShell();
})();
