// Makia RC7 growth/automation views. Loaded before app.js; functions resolve shared helpers at runtime.
(function(){
  const H=v=>window.htmlEsc?htmlEsc(v):String(v??'');
  const T=(fa,en)=>window.tr?tr(fa,en):en;

  window.growthPlansView=async function(renderToken=window.__viewRenderToken){
    title.textContent=T('پلن‌ها','Plans');setPageContext('PLANS & TEMPLATES');
    const plans=await api('/api/plans');
    if(renderToken!==window.__viewRenderToken||activeView!=='plans')return;
    const rows=plans.map(p=>'<article class="growth-card"><div><span class="pro-kicker">'+H((p.protocol||'any').toUpperCase())+'</span><h3>'+H(p.name)+'</h3><p>'+H(p.expire_days+'d · '+(p.quota_bytes?fmtBytes(p.quota_bytes):T('نامحدود','Unlimited'))+' · '+p.ip_limit+' IP')+'</p></div><div class="growth-card-actions"><button class="ghost" data-growth-action="plan-edit" data-id="'+p.id+'">'+H(T('ویرایش','Edit'))+'</button><button class="danger" data-growth-action="plan-delete" data-id="'+p.id+'">'+H(T('حذف','Delete'))+'</button></div></article>').join('');
    content.innerHTML='<div class="pro-page growth-page"><section class="pro-page-head"><div><span class="pro-kicker">PLANS / TEMPLATES</span><h1>'+H(T('پلن‌های سرویس','Service plans'))+'</h1><p>'+H(T('پلن‌های آماده برای حجم، مدت، محدودیت IP و تنظیمات پروتکل.','Reusable templates for quota, duration, IP limits and protocol defaults.'))+'</p></div><div class="pro-head-actions"><button class="primary" data-growth-action="plan-new">＋ '+H(T('پلن جدید','New plan'))+'</button></div></section><section class="growth-grid">'+(rows||'<div class="empty">'+H(T('هنوز پلنی ساخته نشده است.','No plans yet.'))+'</div>')+'</section><section class="panel"><div class="panel-head"><div><h3>'+H(T('روش استفاده','How it works'))+'</h3><span>FAST PROVISIONING</span></div></div><div class="guide-flow"><div><b>1</b><span>'+H(T('پلن را یک‌بار تعریف کن.','Define a plan once.'))+'</span></div><div><b>2</b><span>'+H(T('در ساخت یا تمدید همان Policy را استفاده کن.','Reuse the policy for create/renew.'))+'</span></div><div><b>3</b><span>'+H(T('مقادیر هر کاربر همچنان قابل تغییر هستند.','Per-client values remain overridable.'))+'</span></div></div></section></div>';
  };

  window.openGrowthPlanEditor=function(plan){
    const p=plan||{name:'',protocol:'xray',quota_bytes:50*1024**3,expire_days:30,ip_limit:1,reset_days:30,price:0,active:1,config:{}};
    modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">SERVICE PLAN</div><h3>'+H(plan?T('ویرایش پلن','Edit plan'):T('پلن جدید','New plan'))+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="form-grid two"><label>'+H(T('نام','Name'))+'<input id="planName" value="'+H(p.name||'')+'"></label><label>'+H(T('پروتکل','Protocol'))+'<select id="planProtocol">'+['xray','outline','wireguard','openvpn','ssh'].map(x=>'<option value="'+x+'" '+(p.protocol===x?'selected':'')+'>'+x.toUpperCase()+'</option>').join('')+'</select></label><label>'+H(T('حجم GB','Quota GB'))+'<input id="planQuota" type="number" min="0" value="'+(Number(p.quota_bytes||0)/1024**3)+'"></label><label>'+H(T('مدت روز','Expiry days'))+'<input id="planDays" type="number" min="0" max="3650" value="'+Number(p.expire_days||0)+'"></label><label>'+H(T('محدودیت IP','IP limit'))+'<input id="planIp" type="number" min="1" max="50" value="'+Number(p.ip_limit||1)+'"></label><label>'+H(T('Reset روز','Reset days'))+'<input id="planReset" type="number" min="0" max="3650" value="'+Number(p.reset_days||0)+'"></label><label>'+H(T('قیمت اختیاری','Optional price'))+'<input id="planPrice" type="number" min="0" value="'+Number(p.price||0)+'"></label><label class="check-row"><input id="planActive" type="checkbox" '+(p.active?'checked':'')+'> '+H(T('فعال','Active'))+'</label></div><label>'+H(T('تنظیمات اضافی JSON','Extra settings JSON'))+'<textarea id="planConfig" class="config-output small">'+H(JSON.stringify(p.config||{},null,2))+'</textarea></label><div class="wizard-footer"><button class="ghost" data-action="modal-close">'+H(T('انصراف','Cancel'))+'</button><button class="primary" data-growth-action="plan-save" data-id="'+(p.id||0)+'">'+H(T('ذخیره','Save'))+'</button></div></div></div>';
  };

  async function savePlan(id){
    let config={};try{config=JSON.parse(document.getElementById('planConfig').value||'{}')}catch(e){alert('JSON: '+e.message);return}
    const payload={name:planName.value.trim(),protocol:planProtocol.value,quota_gb:Number(planQuota.value||0),expire_days:Number(planDays.value||0),ip_limit:Number(planIp.value||1),reset_days:Number(planReset.value||0),price:Number(planPrice.value||0),active:planActive.checked,config};
    if(!payload.name){alert(T('نام پلن لازم است','Plan name is required'));return}
    await api(id?'/api/plans/'+id:'/api/plans',{method:id?'PUT':'POST',body:JSON.stringify(payload)});
    closeModal();toast(T('پلن ذخیره شد','Plan saved'));await growthPlansView();
  }

  window.growthExpiryView=async function(renderToken=window.__viewRenderToken){
    title.textContent=T('انقضا و تمدید','Expiry & Renew');setPageContext('EXPIRY CENTER');
    const data=await api('/api/expiry-center');
    if(renderToken!==window.__viewRenderToken||activeView!=='expiry')return;
    const section=(label,rows,cls)=>'<section class="panel expiry-section"><div class="panel-head"><div><h3>'+H(label)+'</h3><span>'+rows.length+'</span></div></div><div class="expiry-list">'+(rows.length?rows.map(x=>'<div class="expiry-row '+cls+'"><div><b>'+H(x.name)+'</b><span>'+H(String(x.protocol||x.kind).toUpperCase())+'</span></div><div><b>'+H(String(x.days_left))+'d</b><span>'+new Date(x.expire_at*1000).toLocaleDateString()+'</span></div><div class="toolbar"><button class="primary" data-growth-action="quick-renew" data-target="'+encodeURIComponent(x.target)+'">+30d / +50GB</button><button class="ghost" data-growth-action="renew-custom" data-target="'+encodeURIComponent(x.target)+'">'+H(T('دلخواه','Custom'))+'</button></div></div>').join(''):'<div class="empty">'+H(T('موردی وجود ندارد.','Nothing here.'))+'</div>')+'</div></section>';
    content.innerHTML='<div class="pro-page"><section class="pro-page-head"><div><span class="pro-kicker">EXPIRY CENTER</span><h1>'+H(T('تمدید و انقضا','Renewals & expiry'))+'</h1><p>'+H(T('منقضی‌ها، امروز و هفت روز آینده را یکجا ببین و سریع تمدید کن.','See expired, today and next-7-day clients and renew fast.'))+'</p></div><div class="pro-head-actions"><button class="ghost" data-action="nav" data-view="access">'+H(T('همه کاربران','All clients'))+'</button></div></section><div class="expiry-columns">'+section(T('منقضی‌شده','Expired'),data.expired||[],'bad')+section(T('امروز','Today'),data.today||[],'warn')+section(T('۷ روز آینده','Next 7 days'),data.soon||[],'soon')+'</div></div>';
  };

  async function renewTarget(target,days,gb,custom){
    if(custom){days=Number(prompt(T('چند روز اضافه شود؟','Days to add?'),'30')||0);gb=Number(prompt(T('چند GB اضافه شود؟','GB to add?'),'50')||0)}
    if(!days&&!gb)return;
    await api('/api/clients/'+encodeURIComponent(target)+'/renew',{method:'POST',body:JSON.stringify({add_days:days||0,add_gb:gb||0,enable:true,reset_traffic:false})});
    toast(T('تمدید انجام شد','Renewal completed'));await currentView();
  }

  window.growthAutomationView=async function(renderToken=window.__viewRenderToken){
    title.textContent=T('اتوماسیون','Automation');setPageContext('AUTOMATION & INTEGRATIONS');
    const [schedules,cf,tg,notes]=await Promise.all([api('/api/backup-schedules'),api('/api/integrations/cloudflare'),api('/api/integrations/telegram'),api('/api/notifications')]);
    if(renderToken!==window.__viewRenderToken||activeView!=='automation')return;
    const srows=schedules.map(s=>'<div class="automation-row"><div><b>'+H(s.name)+'</b><span>'+H(s.frequency+' @ '+String(s.hour).padStart(2,'0')+':00 · keep '+s.keep_last+' · '+s.remote_type)+'</span></div><span class="status-chip '+(s.last_status==='pass'?'ok':s.last_status==='fail'?'bad':'')+'">'+H(s.last_status||'NEW')+'</span><div class="toolbar"><button class="primary" data-growth-action="schedule-run" data-id="'+s.id+'">'+H(T('اجرا','Run now'))+'</button><button class="danger" data-growth-action="schedule-delete" data-id="'+s.id+'">'+H(T('حذف','Delete'))+'</button></div></div>').join('');
    content.innerHTML='<div class="pro-page"><section class="pro-page-head"><div><span class="pro-kicker">AUTOMATION</span><h1>'+H(T('اتوماسیون و اتصال‌ها','Automation & integrations'))+'</h1><p>'+H(T('بکاپ زمان‌بندی‌شده، مقصد راه‌دور، Cloudflare و Telegram.','Scheduled backups, remote target, Cloudflare and Telegram.'))+'</p></div><div class="pro-head-actions"><button class="primary" data-growth-action="schedule-new">＋ '+H(T('بکاپ زمان‌بندی‌شده','Backup schedule'))+'</button></div></section><section class="panel"><div class="panel-head"><div><h3>'+H(T('بکاپ‌های خودکار','Scheduled backups'))+'</h3><span>ENCRYPTED / VERIFIED</span></div></div><div class="automation-list">'+(srows||'<div class="empty">'+H(T('برنامه‌ای تعریف نشده.','No schedule configured.'))+'</div>')+'</div></section><div class="split-grid"><section class="panel integration-card"><div class="panel-head"><div><h3>Cloudflare DNS</h3><span>'+H(cf.configured?'CONNECTED':'NOT CONFIGURED')+'</span></div></div><p>'+H(T('برای مهاجرت VPS، رکورد A را DNS-only به IP جدید تغییر می‌دهد.','For VPS migration, updates the A record to the new IP in DNS-only mode.'))+'</p><div class="settings-form-grid"><label>Hostname<input id="cfHost" value="'+H(cf.hostname||window.PANEL_DOMAIN||'')+'"></label><label>API Token<input id="cfToken" type="password" placeholder="'+(cf.configured?'•••• existing token':'Cloudflare API token')+'"></label><label>TTL<input id="cfTtl" type="number" value="'+Number(cf.ttl||120)+'"></label></div><div class="settings-actions"><button class="primary" data-growth-action="cloudflare-save">'+H(T('ذخیره و بررسی','Save & verify'))+'</button></div>'+(cf.status?'<div class="wizard-note"><b>'+H(cf.status.name||'')+'</b><span>'+H((cf.status.content||'—')+' · '+(cf.status.proxied?'PROXIED':'DNS ONLY'))+'</span></div>':'')+'</section><section class="panel integration-card"><div class="panel-head"><div><h3>Telegram</h3><span>'+H(tg.configured?'CONNECTED':'NOT CONFIGURED')+'</span></div></div><p>'+H(T('هشدار مدیر و Bot محدود برای status، expiry، user و backup.','Admin alerts and restricted bot commands for status, expiry, user and backup.'))+'</p><div class="settings-form-grid"><label>Bot Token<input id="tgToken" type="password" placeholder="'+(tg.configured?'••••'+H(tg.token_last4||''):'123:ABC')+'"></label><label>Chat ID<input id="tgChat" value="'+H(tg.chat_id||'')+'"></label><label class="check-row"><input id="tgAlerts" type="checkbox" '+(tg.enabled?'checked':'')+'> Alerts</label><label class="check-row"><input id="tgBot" type="checkbox" '+(tg.bot_enabled?'checked':'')+'> Bot commands</label></div><div class="settings-actions"><button class="primary" data-growth-action="telegram-save">'+H(T('ذخیره','Save'))+'</button><button class="ghost" data-growth-action="telegram-test">Test</button></div></section></div><section class="panel"><div class="panel-head"><div><h3>'+H(T('اعلان‌های اخیر','Recent notifications'))+'</h3><span>'+notes.length+'</span></div></div><div class="notification-list">'+notes.slice(0,20).map(n=>'<div class="notification-row '+H(n.level)+'"><div><b>'+H(n.title)+'</b><span>'+H(n.message)+'</span></div><small>'+H(n.created_at)+'</small></div>').join('')+'</div></section></div>';
  };

  function openScheduleEditor(){
    modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">SCHEDULED BACKUP</div><h3>'+H(T('بکاپ خودکار','Automated backup'))+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="form-grid two"><label>'+H(T('نام','Name'))+'<input id="schName" value="Daily Migration"></label><label>'+H(T('تناوب','Frequency'))+'<select id="schFreq"><option value="daily">Daily</option><option value="weekly">Weekly (Monday)</option></select></label><label>'+H(T('ساعت','Hour'))+'<input id="schHour" type="number" min="0" max="23" value="4"></label><label>Keep last<input id="schKeep" type="number" min="1" max="90" value="7"></label><label>'+H(T('رمز بکاپ','Backup password'))+'<input id="schPass" type="password" minlength="10"></label><label>'+H(T('مقصد','Destination'))+'<select id="schRemote"><option value="local">Local copy</option><option value="sftp">SFTP / another VPS</option></select></label></div><details class="pro-advanced" open><summary>SFTP</summary><div class="form-grid two"><label>Host<input id="schHost"></label><label>User<input id="schUser"></label><label>Port<input id="schPort" type="number" value="22"></label><label>Remote path<input id="schPath" value="~/makia-backups"></label><label>Identity file on this VPS<input id="schIdentity" value="/root/.ssh/id_ed25519"></label></div></details><div class="wizard-footer"><button class="primary" data-growth-action="schedule-save">'+H(T('ذخیره','Save'))+'</button><button class="ghost" data-action="modal-close">'+H(T('انصراف','Cancel'))+'</button></div></div></div>';
  }
  async function saveSchedule(){
    const remote_type=schRemote.value;
    const remote=remote_type==='sftp'?{host:schHost.value.trim(),user:schUser.value.trim(),port:Number(schPort.value||22),path:schPath.value.trim(),identity_file:schIdentity.value.trim()}:{path:'/var/backups/makia-remote'};
    await api('/api/backup-schedules',{method:'POST',body:JSON.stringify({name:schName.value.trim(),frequency:schFreq.value,hour:Number(schHour.value),keep_last:Number(schKeep.value),password:schPass.value,remote_type,remote,enabled:true})});
    closeModal();toast(T('زمان‌بندی ذخیره شد','Schedule saved'));await growthAutomationView();
  }

  window.growthMigrationView=async function(renderToken=window.__viewRenderToken){
    title.textContent=T('مهاجرت VPS','VPS Migration');setPageContext('DISASTER RECOVERY');
    const m=await api('/api/migration/wizard');
    if(renderToken!==window.__viewRenderToken||activeView!=='migration')return;
    const r=m.readiness||{},cf=m.cloudflare||{},b=m.latest_backup;
    const step=(n,t,ok,d,a)=>'<article class="migration-step '+(ok?'ok':'warn')+'"><span>'+n+'</span><div><b>'+H(t)+'</b><p>'+H(d||'')+'</p></div>'+(a||'')+'</article>';
    content.innerHTML='<div class="pro-page"><section class="pro-page-head"><div><span class="pro-kicker">DISASTER RECOVERY</span><h1>'+H(T('مهاجرت و بازیابی VPS','VPS migration & recovery'))+'</h1><p>Backup → Restore → Runtime Verify → DNS Cutover → UAT</p></div></section><div class="migration-step-list">'+step(1,T('Preflight','Preflight'),Boolean(m.self_test?.ok),m.self_test?.ok?T('سلامت پایه PASS','Base health PASS'):T('Self-Test نیازمند بررسی است','Self-Test needs attention'),'<button class="ghost" data-action="self-test">Self-Test</button>')+step(2,'Full Migration Backup',Boolean(b),b?b.name:T('بکاپ کامل هنوز موجود نیست','No full migration backup yet'),'<button class="primary" data-action="nav" data-view="backups">'+H(T('ساخت بکاپ','Create backup'))+'</button>')+step(3,T('Domain readiness','Domain readiness'),Boolean(r.domain_configured),r.panel_domain||T('دامنه تنظیم نشده','No domain configured'),'')+step(4,T('Config portability','Config portability'),Boolean(r.same_config_cutover_ready),r.ip_based?(String(r.ip_based)+' IP-based config(s) need re-export'):T('کانفیگ‌ها Domain-based هستند','Configs are domain-based'),'')+step(5,'Cloudflare',Boolean(cf.configured),cf.configured?(cf.hostname||'Configured'):T('اختیاری؛ هنوز تنظیم نشده','Optional; not configured'),'<button class="ghost" data-action="nav" data-view="automation">Cloudflare</button>')+step(6,T('Restore on new VPS','Restore on new VPS'),false,T('روی VPS جدید RC7 را نصب کن، Bundle را Verify و Restore کن.','Install RC7 on the new VPS, verify the bundle and restore it.'),'<button class="ghost" data-action="nav" data-view="backups">'+H(T('Restore Wizard','Restore Wizard'))+'</button>')+step(7,T('DNS cutover','DNS cutover'),Boolean(cf.configured),T('فقط بعد از Runtime Verification رکورد A را تغییر بده.','Change the A record only after runtime verification.'),cf.configured?'<button class="primary" data-growth-action="cloudflare-cutover">'+H(T('تغییر IP','Cut over IP'))+'</button>':'')+'</div><div class="wizard-note danger-note"><b>'+H(T('کانفیگ‌های IP-based','IP-based configs'))+'</b><span>'+H(T('کانفیگ دارای IP قدیمی ممکن است نیاز به Re-export داشته باشد.','Configs embedding the old IP may require re-export.'))+'</span></div></div>';
  };

  window.growthDiagnosticsView=async function(renderToken=window.__viewRenderToken){
    title.textContent=T('عیب‌یابی کاربران','Client Diagnostics');setPageContext('CLIENT DIAGNOSTICS');
    const clients=await api('/api/access');
    if(renderToken!==window.__viewRenderToken||activeView!=='diagnostics')return;
    content.innerHTML='<div class="pro-page"><section class="pro-page-head"><div><span class="pro-kicker">DIAGNOSTICS</span><h1>'+H(T('عیب‌یابی اتصال کاربر','Client connection diagnostics'))+'</h1><p>'+H(T('Database، Expiry، Quota، Runtime، Listener، DNS، Handshake و Delivery را یکجا بررسی کن.','Check database, expiry, quota, runtime, listener, DNS, handshake and delivery in one place.'))+'</p></div></section><section class="panel"><div class="settings-form-grid two"><label>'+H(T('دسترسی','Access'))+'<select id="diagClient">'+clients.map(x=>'<option value="'+H(x.kind+':'+x.key)+'">'+H(x.name+' · '+String(x.protocol||x.kind).toUpperCase())+'</option>').join('')+'</select></label><div class="settings-actions"><button class="primary" data-growth-action="diagnostic-run">'+H(T('اجرای عیب‌یابی','Run diagnostics'))+'</button></div></div><div id="diagResult"></div></section></div>';
  };
  async function runClientDiagnostic(){
    const raw=document.getElementById('diagClient')?.value||'';if(!raw||!raw.includes(':'))return;
    const i=raw.indexOf(':'),kind=raw.slice(0,i),key=raw.slice(i+1);
    const r=await api('/api/diagnostics/access/'+encodeURIComponent(kind)+'/'+encodeURIComponent(key));
    document.getElementById('diagResult').innerHTML='<div class="diagnostic-grid">'+(r.checks||[]).map(x=>'<div class="diagnostic-row"><span class="'+(x.ok?'ok-dot':'bad-dot')+'"></span><div><b>'+H(x.name)+'</b><small>'+H(x.detail)+'</small></div><strong class="'+(x.ok?'ok-text':'bad-text')+'">'+(x.ok?'PASS':'FAIL')+'</strong></div>').join('')+'</div>';
  }

  window.growthOutlineView=async function(renderToken=window.__viewRenderToken){
    title.textContent='Outline';setPageContext('OUTLINE / SHADOWSOCKS');
    const [status,clients]=await Promise.all([api('/api/protocols/outline'),api('/api/protocol-clients')]);
    if(renderToken!==window.__viewRenderToken||activeView!=='outline')return;
    const filtered=clients.filter(x=>x.protocol==='outline');
    const rows=filtered.map(x=>'<div class="protocol-client-row"><div><b>'+H(x.name)+'</b><span>Outline · AES-256-GCM</span></div><div><b>'+H(x.expire_at?new Date(x.expire_at*1000).toLocaleDateString():T('بدون انقضا','No expiry'))+'</b><span>'+(x.quota_bytes?fmtBytes(x.quota_bytes):'∞')+'</span></div><button class="ghost" data-action="client-portal" data-kind="xray" data-key="'+encodeURIComponent(String(x.id))+'" data-name="'+encodeURIComponent(x.name)+'">'+H(T('لینک کاربر','Client link'))+'</button></div>').join('');
    content.innerHTML='<div class="pro-page"><section class="pro-page-head"><div><span class="pro-kicker">OUTLINE COMPATIBLE</span><h1>Outline</h1><p>'+H(T('کلید Static Shadowsocks سازگار با Outline Client؛ Backend واقعی Xray Core با AES-256-GCM.','Outline Client-compatible static Shadowsocks keys backed by Xray Core with AES-256-GCM.'))+'</p></div><div class="pro-head-actions"><button class="primary" data-growth-action="outline-new">＋ '+H(T('کاربر Outline','Outline client'))+'</button></div></section><div class="wizard-note"><b>'+H(T('شفافیت فنی','Technical note'))+'</b><span>'+H(T('این قابلیت کلید استاندارد ss:// برای Outline Client می‌سازد و API رسمی Outline Manager را جعل نمی‌کند.','This creates standard ss:// static keys for Outline Client and does not pretend to implement the official Outline Manager API.'))+'</span></div><section class="panel"><div class="panel-head"><div><h3>'+H(T('کاربران Outline','Outline clients'))+'</h3><span>'+filtered.length+'</span></div></div><div class="protocol-client-list">'+(rows||'<div class="empty">'+H(T('هنوز کاربری نیست.','No clients yet.'))+'</div>')+'</div></section></div>';
  };
  function openOutlineCreate(){
    modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">OUTLINE STATIC KEY</div><h3>'+H(T('ساخت کاربر Outline','Create Outline client'))+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="form-grid two"><label>'+H(T('نام','Name'))+'<input id="olName" value="outline01"></label><label>Port<input id="olPort" type="number" min="1" max="65535" value="8388"></label><label>Endpoint<input id="olEndpoint" value="'+H(window.PANEL_DOMAIN||location.hostname)+'"></label><label>Endpoint mode<select id="olMode"><option value="domain">Domain</option><option value="ip">IP</option></select></label><label>Quota GB<input id="olQuota" type="number" min="0" value="50"></label><label>Expiry days<input id="olDays" type="number" min="0" value="30"></label><label>IP limit<input id="olIp" type="number" min="1" max="50" value="1"></label></div><div class="wizard-footer"><button class="primary" data-growth-action="outline-save">'+H(T('ساخت','Create'))+'</button><button class="ghost" data-action="modal-close">'+H(T('انصراف','Cancel'))+'</button></div></div></div>';
  }
  async function saveOutline(){
    const p={name:olName.value.trim(),port:Number(olPort.value),endpoint:olEndpoint.value.trim(),endpoint_mode:olMode.value,quota_gb:Number(olQuota.value||0),expire_days:Number(olDays.value||0),ip_limit:Number(olIp.value||1)};
    const r=await api('/api/protocols/outline/clients',{method:'POST',body:JSON.stringify(p)});
    xrayCredentialModal(r);
  }

  function selectedBulkTargets(){
    return [...document.querySelectorAll('.access-select:checked')].map(x=>x.dataset.target).filter(Boolean);
  }
  async function runBulk(action,days=0,gb=0){
    const targets=selectedBulkTargets();
    if(!targets.length){alert(T('حداقل یک کاربر را انتخاب کنید.','Select at least one client.'));return}
    if(action==='renew'){
      if(!days)days=Number(prompt(T('چند روز اضافه شود؟','Days to add?'),'30')||0);
      if(!gb)gb=Number(prompt(T('چند GB اضافه شود؟','GB to add?'),'50')||0);
    }
    const result=await api('/api/clients/bulk',{method:'POST',body:JSON.stringify({targets,action,add_days:days,add_gb:gb})});
    toast(String((result.ok||[]).length)+' '+T('کاربر بروزرسانی شد','clients updated'));
    if((result.failed||[]).length)alert((result.failed||[]).map(x=>x.target+': '+x.error).join('\n'));
    await access();
  }

  window.MAKIA_GROWTH_VIEWS={
    plans:growthPlansView,expiry:growthExpiryView,automation:growthAutomationView,
    migration:growthMigrationView,diagnostics:growthDiagnosticsView,outline:growthOutlineView
  };

  document.addEventListener('click',async function(e){
    const btn=e.target.closest('[data-growth-action]');if(!btn)return;
    e.preventDefault();e.stopImmediatePropagation();
    const a=btn.dataset.growthAction;
    try{
      if(a==='bulk-renew'){await runBulk('renew',30,50);return}
      if(a==='bulk-enable'){await runBulk('enable');return}
      if(a==='bulk-disable'){await runBulk('disable');return}
      if(a==='bulk-reset'){await runBulk('reset_traffic');return}
      if(a==='plan-new'){openGrowthPlanEditor();return}
      if(a==='plan-edit'){const p=(await api('/api/plans')).find(x=>Number(x.id)===Number(btn.dataset.id));if(p)openGrowthPlanEditor(p);return}
      if(a==='plan-save'){await savePlan(Number(btn.dataset.id||0));return}
      if(a==='plan-delete'){if(confirm(T('پلن حذف شود؟','Delete plan?'))){await api('/api/plans/'+btn.dataset.id,{method:'DELETE'});await growthPlansView()}return}
      if(a==='quick-renew'){await renewTarget(decodeURIComponent(btn.dataset.target),30,50,false);return}
      if(a==='renew-custom'){await renewTarget(decodeURIComponent(btn.dataset.target),0,0,true);return}
      if(a==='schedule-new'){openScheduleEditor();return}
      if(a==='schedule-save'){await saveSchedule();return}
      if(a==='schedule-run'){await api('/api/backup-schedules/'+btn.dataset.id+'/run',{method:'POST'});toast(T('بکاپ اجرا شد','Backup completed'));await growthAutomationView();return}
      if(a==='schedule-delete'){if(confirm(T('زمان‌بندی حذف شود؟','Delete schedule?'))){await api('/api/backup-schedules/'+btn.dataset.id,{method:'DELETE'});await growthAutomationView()}return}
      if(a==='cloudflare-save'){await api('/api/integrations/cloudflare',{method:'PUT',body:JSON.stringify({token:cfToken.value,hostname:cfHost.value.trim(),ttl:Number(cfTtl.value||120)})});toast('Cloudflare OK');await growthAutomationView();return}
      if(a==='cloudflare-cutover'){const ip=prompt(T('IP جدید VPS','New VPS IPv4'),'');if(ip&&confirm(T('رکورد A به '+ip+' تغییر کند؟','Change A record to '+ip+'?'))){await api('/api/integrations/cloudflare/cutover',{method:'POST',body:JSON.stringify({ip})});toast('DNS updated');await growthMigrationView()}return}
      if(a==='telegram-save'){await api('/api/integrations/telegram',{method:'PUT',body:JSON.stringify({bot_token:tgToken.value,chat_id:tgChat.value.trim(),enabled:tgAlerts.checked,bot_enabled:tgBot.checked})});toast('Telegram saved');await growthAutomationView();return}
      if(a==='telegram-test'){await api('/api/integrations/telegram/test',{method:'POST'});toast('Telegram test sent');return}
      if(a==='diagnostic-run'){await runClientDiagnostic();return}
      if(a==='outline-new'){openOutlineCreate();return}
      if(a==='outline-save'){await saveOutline();return}
    }catch(err){alert(err?.message||String(err))}
  },true);
})();
