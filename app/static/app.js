const content=document.querySelector('#content'),title=document.querySelector('#pageTitle'),modalRoot=document.querySelector('#modalRoot');let activeView='dashboard';
const pageContext=document.querySelector('#pageContext');
function htmlEsc(v){return String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]))}
function dataEnc(v){return encodeURIComponent(String(v??''))}
function dataDec(v){try{return decodeURIComponent(String(v??''))}catch{return String(v??'')}}
function setPageContext(v){if(pageContext)pageContext.textContent=v||'MAKIA CONTROL CENTER'}
function downloadBlob(blob,name){const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name||'download';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),800)}
function filenameFromHeaders(r,fallback){const cd=r.headers.get('content-disposition')||'';const m=cd.match(/filename="([^"]+)"/i);return m?.[1]||fallback||'download'}
async function fetchDownload(url,opts={},fallback='download'){const r=await fetch(url,{credentials:'same-origin',...opts});if(!r.ok){let msg='Download failed';try{const j=await r.json();msg=j?.detail||msg}catch{try{msg=await r.text()||msg}catch{}}throw new Error(msg)}const blob=await r.blob();downloadBlob(blob,filenameFromHeaders(r,fallback));return true}

async function api(url,opts={}){const r=await fetch(url,{headers:{'Content-Type':'application/json','X-Makia-Request':'1'},credentials:'same-origin',...opts});let j=null;try{j=await r.json()}catch{}if(!r.ok){const d=j?.detail;const msg=typeof d==='string'?d:(d?.message||d?.code||'خطا در انجام عملیات');const e=new Error(msg);e.detail=d;e.status=r.status;throw e}return j}
function fmtBytes(n){if(!n)return'0 B';const u=['B','KB','MB','GB','TB'];const i=Math.min(u.length-1,Math.floor(Math.log(n)/Math.log(1024)));return(n/1024**i).toFixed(i?1:0)+' '+u[i]}
function fmtUp(s){const d=Math.floor(s/86400),h=Math.floor((s%86400)/3600),m=Math.floor((s%3600)/60);return`${d}d ${h}h ${m}m`}
function pct(v){return Math.max(0,Math.min(100,Number(v)||0))}
function svgHistory(rows){if(!rows||rows.length<2)return'<div class="empty">برای نمودار ۲۴ ساعته هنوز داده کافی جمع نشده است.</div>';const w=900,h=220,p=18;const xs=rows.map((_,i)=>p+i*(w-2*p)/(rows.length-1));const path=(key,max=100)=>rows.map((r,i)=>(i?'L':'M')+xs[i].toFixed(1)+' '+(h-p-(Math.max(0,Math.min(max,Number(r[key])||0))/max)*(h-2*p)).toFixed(1)).join(' ');return `<svg class="history-chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><defs><linearGradient id="cpuG" x1="0" x2="1"><stop offset="0" stop-color="#35d6ff"/><stop offset="1" stop-color="#6c7cff"/></linearGradient><linearGradient id="memG" x1="0" x2="1"><stop offset="0" stop-color="#2dd4a7"/><stop offset="1" stop-color="#a855f7"/></linearGradient></defs><path d="${path('cpu')}" fill="none" stroke="url(#cpuG)" stroke-width="3"/><path d="${path('memory')}" fill="none" stroke="url(#memG)" stroke-width="3" opacity=".9"/></svg><div class="chart-legend"><span><i class="legend-dot cpu"></i>CPU</span><span><i class="legend-dot mem"></i>Memory</span><span>${rows.length} samples</span></div>`}

function healthScore(d){const m=d.metrics,s=d.services.filter(x=>x.active).length/Math.max(1,d.services.length)*100;return Math.round((100-pct(m.cpu))*.2+(100-pct(m.memory))*.25+(100-pct(m.disk))*.25+s*.3)}
function kpi(label,value,p,cls='',sub=''){return`<div class="kpi ${cls}"><div class="label"><span>${label}</span><span>${sub}</span></div><div class="value">${value}</div><div class="bar"><i style="width:${pct(p)}%"></i></div></div>`}
async function setPass(id,type){const el=document.getElementById(id);if(!el)return;const mode=type===4?'pin4':type===6?'pin6':type==='easy8'?'easy8':'strong';try{const r=await api('/api/accounts/generate-secret?mode='+mode);el.value=r.secret;el.type='text';el.focus()}catch(e){alert(e.message)}}
function setExpiryDays(id,days){const el=document.getElementById(id);if(!el)return;const d=new Date();d.setDate(d.getDate()+Number(days));el.value=d.toISOString().slice(0,10)}
function quotaLabel(mb){if(!mb)return'بدون سقف';return mb>=1024?(mb/1024).toFixed(mb%1024?1:0)+' GB':mb+' MB'}
function statusFor(a){if(!a.enabled)return'<span class="status-chip bad">Locked</span>';if(a.expired)return'<span class="status-chip bad">Expired</span>';if(a.days_left!==null&&a.days_left<=7)return'<span class="status-chip warn">'+a.days_left+' روز</span>';return'<span class="status-chip ok">Active</span>'}
function viewIntro(kicker,heading,desc,aside=''){
  return '<section class="view-intro"><div><div class="eyebrow">'+htmlEsc(kicker)+'</div><h2>'+htmlEsc(heading)+'</h2><p>'+htmlEsc(desc)+'</p></div>'+aside+'</section>';
}
function clientGuideUrl(kind){
  const anchor=kind==='wireguard'?'wireguard':kind==='openvpn'?'openvpn':kind==='ssh'?'ssh':'xray';
  return location.origin+'/help/connect#'+anchor;
}
function openClientGuide(kind){window.open(clientGuideUrl(kind),'_blank','noopener')}
function copyClientGuide(kind){copyText(clientGuideUrl(kind));toast('لینک راهنما کپی شد')}
window.__sessionContext=null;
async function ensureSessionContext(force=false){
  if(window.__sessionContext&&!force)return window.__sessionContext;
  window.__sessionContext=await api('/api/session/context');
  document.body.dataset.remoteSupport=window.__sessionContext?.remote_support?'1':'0';
  let banner=document.getElementById('remoteSupportBanner');
  if(window.__sessionContext?.remote_support){
    if(!banner){
      banner=document.createElement('div');banner.id='remoteSupportBanner';banner.className='remote-support-banner';
      banner.innerHTML='<b>REMOTE SUPPORT SESSION</b><span>دسترسی موقت '+htmlEsc(window.__sessionContext.support_scope||'readonly')+' فعال است و عملیات در Audit ثبت می‌شوند.</span><form method="post" action="/support/logout"><button type="submit">End session</button></form>';
      document.body.appendChild(banner);
    }
  }else if(banner){banner.remove()}
  return window.__sessionContext;
}
window.__licenseState=null;
async function ensureLicenseState(force=false){
  if(window.__licenseState&&!force)return window.__licenseState;
  window.__licenseState=await api('/api/license/status');
  syncLicenseShell();
  return window.__licenseState;
}
function hasLicenseFeature(feature){
  return Boolean((window.__licenseState?.features||[]).includes(feature));
}
function fullLicenseActive(){return window.__licenseState?.valid&&window.__licenseState?.tier!=='community'}
function syncLicenseShell(){
  const state=window.__licenseState;if(!state)return;
  document.body.dataset.licenseTier=state.tier||'community';
  const btn=document.querySelector('nav button[data-view="license"] b');
  if(btn)btn.textContent=(state.valid?'Full Access':'License & Support');
}
function lockedFeaturePanel(feature,titleText){
  const id=window.__licenseState?.installation_id||'';
  return [
    '<section class="license-lock-panel panel">',
      '<div class="license-lock-icon">◆</div>',
      '<div><div class="eyebrow">FULL ACCESS REQUIRED</div><h2>'+htmlEsc(titleText||'قابلیت حرفه‌ای')+'</h2>',
      '<p>این نصب در حالت Community است. ساخت و مدیریت SSH فعال است؛ این بخش بعد از فعال‌سازی License امضاشده باز می‌شود.</p>',
      '<div class="chips"><span class="status-chip">Installation '+htmlEsc(id)+'</span><span class="status-chip warn">Community</span></div></div>',
      '<button class="primary action-lg" data-action="nav" data-view="license">درخواست دسترسی کامل</button>',
    '</section>'
  ].join('');
}


async function dashboard(renderToken=window.__viewRenderToken){
  title.textContent='Overview';setPageContext('SYSTEMD CONTROL');
  content.innerHTML='<div class="loading-state"><span class="spinner"></span><b>در حال همگام‌سازی وضعیت سرور…</b></div>';
  const [d,hist,accessRows,stack]=await Promise.all([
    api('/api/overview'),api('/api/metrics/history?hours=24'),api('/api/access'),api('/api/protocols')
  ]);
  if(renderToken!==window.__viewRenderToken||activeView!=='dashboard')return;
  window.__licenseState=d.license||window.__licenseState;syncLicenseShell();
  const m=d.metrics,score=healthScore(d);
  const healthy=(d.services||[]).filter(x=>x.active).length,total=(d.services||[]).length;
  const activeAccess=accessRows.filter(x=>x.status==='active').length;
  const networkTotal=Number(m.network?.sent||0)+Number(m.network?.recv||0);
  const recent=(d.sessions||[]).slice(0,6);
  const ring=(label,value,cls='')=>'<div class="glass-ring '+cls+'" style="--ring:'+pct(value)+'"><div><b>'+Math.round(Number(value)||0)+'%</b><span>'+label+'</span></div></div>';
  const serviceCard=s=>'<button class="glass-service-card" data-action="nav" data-view="services"><span class="service-glyph">'+htmlEsc((s.label||s.name||'?').slice(0,1))+'</span><div><b>'+htmlEsc(s.label)+'</b><small>'+htmlEsc(s.name)+'</small></div><em class="'+(s.active?'running':'attention')+'">'+(s.active?'Running':'Attention')+'</em></button>';
  content.innerHTML=[
    '<section class="glass-status-hero">',
      '<div class="glass-status-score"><b>'+healthy+'/'+total+'</b><span>RUNNING</span></div>',
      '<div class="glass-status-copy"><div class="eyebrow">ALLOWLISTED SERVICES</div><h2>کنترل و سلامت سرور</h2><p>وضعیت زنده سرویس‌ها، منابع، ترافیک و دسترسی‌ها در یک نمای شیشه‌ای عملیاتی.</p></div>',
      '<div class="glass-status-actions"><span class="license-tier-chip '+(d.license?.valid?'full':'community')+'">'+(d.license?.valid?'FULL ACCESS':'COMMUNITY · SSH')+'</span><button class="primary action-lg" data-action="wizard-open">＋ ساخت دسترسی</button><button class="ghost action-lg" data-action="self-test">Self-Test</button></div>',
    '</section>',
    '<section class="glass-summary-grid">',
      '<article><span class="glass-summary-icon">U</span><div><small>کاربران فعال</small><b>'+activeAccess+'</b><em>از '+accessRows.length+' دسترسی</em></div></article>',
      '<article><span class="glass-summary-icon green">↗</span><div><small>ترافیک ثبت‌شده</small><b>'+fmtBytes(networkTotal)+'</b><em>Sent + Received</em></div></article>',
      '<article><span class="glass-summary-icon violet">S</span><div><small>سرویس‌های فعال</small><b>'+healthy+' / '+total+'</b><em>Running</em></div></article>',
      '<article><span class="glass-summary-icon amber">◇</span><div><small>وضعیت سرور</small><b>'+score+'%</b><em>Uptime '+fmtUp(m.uptime_seconds)+'</em></div></article>',
    '</section>',
    '<section class="glass-main-grid">',
      '<div class="panel glass-services-panel"><div class="panel-head"><div><h3>وضعیت سرویس‌ها</h3><span>LIVE SYSTEMD STATE</span></div><button class="ghost" data-action="nav" data-view="services">مدیریت</button></div><div class="glass-service-grid">'+(d.services||[]).map(serviceCard).join('')+'</div></div>',
      '<div class="panel glass-resource-panel"><div class="panel-head"><div><h3>مصرف منابع سرور</h3><span>REAL-TIME</span></div></div><div class="glass-rings">'+ring('CPU',m.cpu,'cyan')+ring('RAM',m.memory,'violet')+ring('Disk',m.disk,'green')+'</div><div class="glass-network-head"><span>ترافیک شبکه</span><b>'+fmtBytes(networkTotal)+'</b></div>'+svgHistory(hist)+'</div>',
    '</section>',
    '<section class="glass-secondary-grid">',
      '<div class="panel"><div class="panel-head"><div><h3>Access Center</h3><span>'+accessRows.length+' MANAGED</span></div><button class="ghost" data-action="nav" data-view="access">Open</button></div><div class="glass-access-strip"><div><b>'+accessRows.filter(x=>x.kind==='ssh').length+'</b><span>SSH</span></div><div><b>'+accessRows.filter(x=>x.kind==='xray').length+'</b><span>Xray</span></div><div><b>'+accessRows.filter(x=>x.kind==='wireguard').length+'</b><span>WireGuard</span></div><div><b>'+accessRows.filter(x=>x.kind==='openvpn').length+'</b><span>OpenVPN</span></div></div></div>',
      '<div class="panel"><div class="panel-head"><div><h3>Live Sessions</h3><span>'+d.online_sessions+' ACTIVE</span></div><button class="ghost" data-action="nav" data-view="sessions">View all</button></div><div class="session-cards">'+(recent.length?recent.map(x=>'<div><span class="avatar-mini">'+htmlEsc((x.username||'?').slice(0,1).toUpperCase())+'</span><div><b>'+htmlEsc(x.username)+'</b><small>'+htmlEsc(x.remote||'local')+'</small></div><time>'+htmlEsc(x.since||'')+'</time></div>').join(''):'<div class="empty compact">نشست فعالی وجود ندارد.</div>')+'</div></div>',
    '</section>'
  ].join('');
}

let accountCache=[];
function setExpiryPreset(id,days){const el=document.getElementById(id);if(!el)return;if(Number(days)===0){el.value='';return}const base=new Date();base.setHours(12,0,0,0);base.setDate(base.getDate()+Number(days));el.value=base.toISOString().slice(0,10)}
function shiftExpiry(id,days){const el=document.getElementById(id);if(!el)return;const today=new Date();today.setHours(12,0,0,0);let base=today;if(el.value){const current=new Date(el.value+'T12:00:00');if(!Number.isNaN(current.getTime())&&current>today)base=current}base.setDate(base.getDate()+Number(days));el.value=base.toISOString().slice(0,10)}
function stepNumber(id,delta,min=1,max=50){const el=document.getElementById(id);if(!el)return;el.value=Math.max(min,Math.min(max,Number(el.value||min)+delta))}
let accessCache=[];
let provisionState=null;

async function access(renderToken=window.__viewRenderToken){
  title.textContent='Access Center';setPageContext('IDENTITY & DELIVERY');
  content.innerHTML='<div class="loading-state"><span class="spinner"></span><b>در حال همگام‌سازی دسترسی‌ها…</b></div>';
  const license=await ensureLicenseState();
  const [rows,stack,sshRows,pcRows,operator]=await Promise.all([
    api('/api/access'),api('/api/protocols'),api('/api/accounts'),
    hasLicenseFeature('xray')?api('/api/protocol-clients'):Promise.resolve([]),
    api('/api/settings/operator')
  ]);
  if(renderToken!==window.__viewRenderToken||activeView!=='access')return;
  accessCache=rows;accountCache=sshRows;window.__protocolClients=pcRows;window.__protocolData=stack;window.__operatorSettings=operator;
  const counts={ssh:0,xray:0,wireguard:0,openvpn:0};rows.forEach(x=>{if(counts[x.kind]!==undefined)counts[x.kind]++});
  const active=rows.filter(x=>x.status==='active').length,legacy=rows.filter(x=>x.legacy).length;
  content.innerHTML=[
    '<section class="access-command">',
      '<div class="access-command-copy"><div class="eyebrow">UNIFIED ACCESS OPERATIONS</div><h2>مرکز دسترسی Makia</h2>',
      '<p>ساخت، سیاست‌گذاری، خروجی Native و تحویل رمزدار برای تمام دسترسی‌های واقعی سرور؛ بدون دکمه نمایشی.</p>',
      '<div class="hero-actions"><button class="primary action-lg" data-action="wizard-open">＋ ساخت دسترسی جدید</button>',
      '<button class="ghost action-lg" data-action="self-test">بررسی سلامت</button></div></div>',
      '<div class="access-command-stats"><div><b>'+rows.length+'</b><span>Total</span></div><div><b>'+active+'</b><span>Active</span></div><div><b>'+legacy+'</b><span>Legacy</span></div><div><b>'+(license.valid?'FULL':'SSH')+'</b><span>License</span></div></div>',
    '</section>',
    '<section class="protocol-launch-grid">',
      accessLaunchCard('ssh','SSH','Password / PIN · Expiry · Session / Device',counts.ssh,true),
      accessLaunchCard('xray','Xray','VLESS · VMess · Trojan · Shadowsocks · Hysteria2',counts.xray,Boolean(stack.xray?.installed)),
      accessLaunchCard('wireguard','WireGuard','Native .conf · QR · encrypted delivery',counts.wireguard,Boolean(stack.wireguard?.installed&&stack.wireguard?.config)),
      accessLaunchCard('openvpn','OpenVPN','Inline .ovpn · PKI · encrypted delivery',counts.openvpn,Boolean(stack.openvpn?.installed&&stack.openvpn?.config)),
    '</section>',
    '<section class="panel access-directory">',
      '<div class="panel-head directory-head"><div><h3>Directory</h3><span id="accessCount">'+rows.length+' PROFILES</span></div>',
      '<div class="directory-tools"><div class="segmented" id="accessSegments">',
        '<button class="active" data-filter-value="all">همه</button><button data-filter-value="ssh">SSH</button><button data-filter-value="xray">Xray</button><button data-filter-value="wireguard">WG</button><button data-filter-value="openvpn">OpenVPN</button>',
      '</div><input id="accessSearch" class="search-input" placeholder="جستجو نام، پلن یا پروتکل…"></div></div>',
      '<div class="directory-summary"><span><i class="legend-native"></i> Native export</span><span><i class="legend-protected"></i> Protected AES ZIP</span><span><i class="legend-legacy"></i> Legacy / reissue required</span></div>',
      '<div id="accessRows" class="access-cards"></div>',
    '</section>'
  ].join('');
  document.getElementById('accessSearch')?.addEventListener('input',renderAccessRows);
  document.getElementById('accessSegments')?.addEventListener('click',e=>{
    const b=e.target.closest('[data-filter-value]');if(!b)return;
    document.querySelectorAll('#accessSegments [data-filter-value]').forEach(x=>x.classList.toggle('active',x===b));
    window.__accessFilter=b.dataset.filterValue||'all';renderAccessRows();
  });
  window.__accessFilter='all';renderAccessRows();
}

function accessLaunchCard(kind,name,desc,count,ready){
  const feature={xray:'xray',wireguard:'wireguard',openvpn:'openvpn'}[kind];
  const unlocked=!feature||hasLicenseFeature(feature);
  let action='';
  if(!unlocked) action='<button class="launch-action locked" data-action="nav" data-view="license">◆ Full Access</button>';
  else if(kind==='ssh') action='<button class="launch-action" data-action="wizard-open" data-kind="ssh">Create</button>';
  else if(ready) action='<button class="launch-action" data-action="wizard-open" data-kind="'+kind+'">Create</button>';
  else action='<button class="launch-action setup" data-action="protocol-setup" data-kind="'+kind+'">Setup</button>';
  return '<article class="launch-card '+kind+(unlocked?'':' license-locked')+'"><div class="launch-top"><span class="access-protocol-icon">'+name.slice(0,1)+'</span><span class="launch-count">'+(unlocked?count:'◆')+'</span></div><h3>'+htmlEsc(name)+'</h3><p>'+htmlEsc(unlocked?desc:'نیازمند License Full امضاشده')+'</p>'+action+'</article>';
}

function renderAccessRows(){
  const root=document.getElementById('accessRows');if(!root)return;
  const q=(document.getElementById('accessSearch')?.value||'').trim().toLowerCase();
  const filter=window.__accessFilter||'all';
  const rows=accessCache.filter(a=>{
    const hay=(String(a.name||'')+' '+String(a.protocol||'')+' '+String(a.plan||'')).toLowerCase();
    return (!q||hay.includes(q))&&(filter==='all'||a.kind===filter);
  });
  const counter=document.getElementById('accessCount');if(counter)counter.textContent=rows.length+' / '+accessCache.length+' PROFILES';
  root.innerHTML=rows.length?rows.map(accessCard).join(''):'<div class="empty">دسترسی مطابق فیلتر پیدا نشد.</div>';
}

function accessCard(a){
  const kind=htmlEsc(a.kind),name=htmlEsc(a.name),proto=htmlEsc(String(a.protocol||a.kind).toUpperCase());
  const key=dataEnc(a.key),id=dataEnc(a.id),label=dataEnc(a.name);
  const stateClass=a.status==='active'?'ok':a.status==='expired'?'bad':'warn';
  let meta='',policy='';
  if(a.kind==='ssh'){
    meta=(a.expire_date||'بدون انقضا')+(a.plan?' · '+htmlEsc(a.plan):'');
    policy='Sessions '+Number(a.online||0)+'/'+Number(a.connection_limit||1)+' · Devices '+Number(a.device_limit||1);
  }else if(a.kind==='xray'){
    const quota=a.quota_bytes?fmtBytes(a.quota_bytes):'Unlimited';
    meta=a.expire_at?new Date(a.expire_at*1000).toLocaleDateString():'بدون انقضا';
    policy=fmtBytes(a.used_bytes||0)+' / '+quota+' · IP '+Number(a.online||0)+'/'+Number(a.device_limit||1);
  }else if(a.kind==='wireguard'){
    meta=htmlEsc(a.address||'WireGuard peer');policy='Native tunnel profile';
  }else{meta='Certificate profile';policy='OpenVPN PKI access'}
  const delivery=window.__operatorSettings?.delivery||{};
  const shareLabel=a.kind==='ssh'?'NPV Import':a.kind==='xray'?'QR / Share':a.kind==='wireguard'?'QR / Share':'';
  const shareAllowed=a.can_export&&shareLabel&&(a.kind!=='ssh'||delivery.npv_enabled!==false);
  const shareButton=shareAllowed?'<button class="icon-action shareish" data-action="access-share" data-kind="'+kind+'" data-key="'+key+'" data-name="'+label+'">'+shareLabel+'</button>':'';
  const guideButton='<button class="icon-action" data-action="client-guide" data-kind="'+kind+'">Guide</button>';
  const protectedButton=hasLicenseFeature('protected_delivery')?'<button class="icon-action primaryish" data-action="protected-export" data-kind="'+kind+'" data-key="'+key+'" data-name="'+label+'">Protected ZIP</button>':'';
  const exportAction=a.can_export
    ? shareButton+protectedButton+'<button class="icon-action" data-action="native-export" data-kind="'+kind+'" data-key="'+key+'">Native</button>'+guideButton
    : (a.kind==='wireguard'
      ? '<button class="icon-action warnish" data-action="wg-reissue" data-key="'+key+'">Reissue</button>'
      : '<button class="icon-action warnish" data-action="manage-access" data-id="'+id+'">Reset credential</button>');
  const manage=(a.kind==='ssh'||a.kind==='xray')?'<button class="more-action" data-action="manage-access" data-id="'+id+'">Manage</button>':'';
  return [
    '<article class="access-profile '+kind+'">',
      '<div class="profile-identity"><div class="profile-avatar">'+htmlEsc(String(a.name||'?').slice(0,1).toUpperCase())+'</div><div><div class="profile-name"><b>'+name+'</b><span class="protocol-pill">'+proto+'</span>',
      '<span class="status-chip '+stateClass+'">'+htmlEsc(a.status)+'</span>'+(a.legacy?'<span class="status-chip">Legacy</span>':'')+'</div><span>'+policy+'</span></div></div>',
      '<div class="profile-meta"><span>Expiry / Type</span><b>'+meta+'</b></div>',
      '<div class="profile-delivery">'+exportAction+'</div>',
      '<div class="profile-actions">'+manage+'<button class="more-action dangerish" data-action="revoke-access" data-kind="'+kind+'" data-key="'+key+'" data-name="'+label+'">Revoke</button></div>',
    '</article>'
  ].join('');
}

async function openProvisionWizard(protocol){
  if(!window.__protocolData) window.__protocolData=await api('/api/protocols');
  const [defs,operator]=await Promise.all([
    api('/api/accounts/new-defaults').catch(()=>({username:'user001'})),
    api('/api/settings/operator').catch(()=>({defaults:{},delivery:{}}))
  ]);
  window.__operatorSettings=operator;
  const d=operator.defaults||{};
  provisionState={
    step:protocol?2:1,protocol:protocol||'',name:defs.username||'user001',
    endpoint:window.PANEL_DOMAIN||location.hostname,password:'',passwordMode:d.ssh_password_mode||'pin6',
    expireDate:'',plan:'',note:'',sessions:Number(d.ssh_sessions||1),devices:Number(d.ssh_devices||1),
    xrayProtocol:d.xray_protocol||'vless',port:Number(d.xray_port||2087),transport:d.xray_transport||'xhttp',security:d.xray_security||'reality',path:d.xray_path||'/makia',
    sni:d.xray_sni||'www.microsoft.com',realityDest:d.xray_reality_target||'www.microsoft.com:443',
    quota:Number(d.xray_quota_gb??50),expireDays:Number(d.xray_expire_days??30),resetDays:Number(d.xray_reset_days??30),
    dns:d.wireguard_dns||'1.1.1.1',wgPort:Number(d.wireguard_port||443),wgMtu:Number(d.wireguard_mtu||1280),wgKeepalive:Number(d.wireguard_keepalive??15),wgAllowedIps:d.wireguard_allowed_ips||'0.0.0.0/0',wgCidr:d.wireguard_cidr||'10.66.66.1/24',ovpnProto:d.openvpn_proto||'udp',ovpnPort:Number(d.openvpn_port||1194),
    packagePassword:''
  };
  if(protocol==='ssh'){
    const mode=d.ssh_password_mode||'pin6';
    const sec=await api('/api/accounts/generate-secret?mode='+encodeURIComponent(mode)).catch(()=>({secret:''}));
    provisionState.password=sec.secret||'';
    const days=Number(d.ssh_expire_days??30);
    provisionState.expireDate=days?dateAfterDays(days):'';
  }
  renderProvisionWizard();
}

function dateAfterDays(days){const d=new Date();d.setHours(12,0,0,0);d.setDate(d.getDate()+Number(days));return d.toISOString().slice(0,10)}

function wizardProtocolReady(kind){
  const s=window.__protocolData||{};
  if(kind==='ssh')return true;
  if(kind==='xray')return Boolean(s.xray?.installed);
  if(kind==='wireguard')return Boolean(s.wireguard?.installed&&s.wireguard?.config);
  if(kind==='openvpn')return Boolean(s.openvpn?.installed&&s.openvpn?.config);
  return false;
}

function renderProvisionWizard(){
  const s=provisionState;if(!s)return;
  const steps=['Protocol','Identity','Policy','Review'];
  let body='';
  if(s.step===1){
    body='<div class="wizard-protocols">'+['ssh','xray','wireguard','openvpn'].map(k=>{
      const names={ssh:'SSH',xray:'Xray',wireguard:'WireGuard',openvpn:'OpenVPN'};
      const desc={ssh:'PIN / Password + Session policy',xray:'VLESS / VMess / Trojan / …',wireguard:'Native .conf + QR',openvpn:'Inline .ovpn profile'};
      const ready=wizardProtocolReady(k);
      return '<button class="wizard-protocol '+(ready?'ready':'not-ready')+'" data-action="'+(ready?'wizard-protocol':'protocol-setup')+'" data-kind="'+k+'"><span>'+names[k].slice(0,1)+'</span><div><b>'+names[k]+'</b><small>'+desc[k]+'</small></div><em>'+(ready?'READY':'SETUP')+'</em></button>';
    }).join('')+'</div>';
  }else if(s.step===2){
    body=wizardIdentityFields(s);
  }else if(s.step===3){
    body=wizardPolicyFields(s);
  }else{
    body=wizardReview(s);
  }
  const footer=s.step===1
    ? '<button class="ghost" data-action="modal-close">انصراف</button>'
    : '<button class="ghost" data-action="wizard-prev">قبلی</button>'+(s.step<4?'<button class="primary" data-action="wizard-next">ادامه</button>':'<button class="primary action-lg" data-action="wizard-create">ساخت و آماده‌سازی</button>');
  modalRoot.innerHTML=[
    '<div class="modal-backdrop wizard-backdrop"><div class="modal provision-wizard">',
      '<div class="wizard-head"><div><div class="eyebrow">SMART PROVISIONING</div><h3>ساخت دسترسی جدید</h3></div><button class="close-btn" data-action="modal-close">×</button></div>',
      '<div class="wizard-steps">'+steps.map((x,i)=>'<div class="'+(s.step===i+1?'active':s.step>i+1?'done':'')+'"><i>'+(s.step>i+1?'✓':i+1)+'</i><span>'+x+'</span></div>').join('')+'</div>',
      '<div class="wizard-body">'+body+'</div>',
      '<div class="wizard-footer">'+footer+'</div>',
    '</div></div>'
  ].join('');
}

function wizardIdentityFields(s){
  if(s.protocol==='ssh') return [
    '<div class="wizard-section-title"><h4>هویت کاربر</h4><p>اطلاعاتی که برای ورود SSH استفاده می‌شود.</p></div>',
    '<div class="wizard-form two"><label>Username<input id="wizName" value="'+htmlEsc(s.name)+'"></label>',
    '<label>Password / PIN<div class="input-action"><input id="wizPassword" value="'+htmlEsc(s.password)+'"><button class="soft" data-action="wizard-secret" data-mode="pin6">Generate</button></div>',
    '<div class="preset-row"><button data-action="wizard-secret" data-mode="pin4">PIN 4</button><button data-action="wizard-secret" data-mode="pin6">PIN 6</button><button data-action="wizard-secret" data-mode="easy8">Easy 8</button><button data-action="wizard-secret" data-mode="strong">Strong</button></div></label>',
    '<label>Plan<input id="wizPlan" value="'+htmlEsc(s.plan)+'" placeholder="VIP / Trial / 30D"></label>',
    '<label>Internal note<input id="wizNote" value="'+htmlEsc(s.note)+'" placeholder="نام مشتری / سفارش"></label></div>'
  ].join('');
  if(s.protocol==='xray') return [
    '<div class="wizard-section-title"><h4>پروفایل Xray</h4><p>Protocol و Endpoint عمومی را مشخص کن.</p></div>',
    '<div class="wizard-form two"><label>Protocol<select id="wizXrayProtocol">',
    ['vless','vmess','trojan','shadowsocks','hysteria2','http','socks'].map(x=>'<option value="'+x+'" '+(s.xrayProtocol===x?'selected':'')+'>'+x.toUpperCase()+'</option>').join(''),
    '</select></label><label>Client name<input id="wizName" value="'+htmlEsc(s.name)+'"></label>',
    '<label>Public domain / IP<input id="wizEndpoint" value="'+htmlEsc(s.endpoint)+'"></label>',
    '<label>Port<input id="wizPort" type="number" min="1" max="65535" value="'+Number(s.port)+'"></label></div>'
  ].join('');
  if(s.protocol==='wireguard') return [
    '<div class="wizard-section-title"><h4>WireGuard Peer</h4><p>برای هر دستگاه یک Peer مستقل بساز.</p></div>',
    '<div class="wizard-form two"><label>Peer name<input id="wizName" value="'+htmlEsc(s.name)+'"></label>',
    '<label>Public domain / IP<input id="wizEndpoint" value="'+htmlEsc(s.endpoint)+'"></label>',
    '<label>DNS<input id="wizDns" value="'+htmlEsc(s.dns)+'"></label>',
    '<label>MTU<input id="wizWgMtu" type="number" min="576" max="1500" value="'+Number(s.wgMtu||1280)+'"></label>',
    '<label>Persistent Keepalive<input id="wizWgKeepalive" type="number" min="0" max="3600" value="'+Number(s.wgKeepalive??15)+'"></label>',
    '<label>Allowed IPs<input id="wizWgAllowedIps" value="'+htmlEsc(s.wgAllowedIps||'0.0.0.0/0')+'"></label></div>',
    '<div class="wizard-note"><b>Compatibility</b><span>دامنه ثابت برای مهاجرت VPS مناسب‌تر است. UDP/443 + MTU 1280 + Keepalive 15 مشکلات رایج NAT/MTU را کاهش می‌دهد، اما در شبکه‌ای که خود WireGuard فیلتر است تضمین عبور نمی‌دهد.</span></div>'
  ].join('');
  return [
    '<div class="wizard-section-title"><h4>OpenVPN Client</h4><p>Certificate مستقل برای این Client ساخته می‌شود.</p></div>',
    '<div class="wizard-form two"><label>Client name<input id="wizName" value="'+htmlEsc(s.name)+'"></label>',
    '<label>Public domain / IP<input id="wizEndpoint" value="'+htmlEsc(s.endpoint)+'"></label>',
    '<label>Port<input id="wizOvpnPort" type="number" min="1" max="65535" value="'+Number(s.ovpnPort)+'"></label>',
    '<label>Transport<select id="wizOvpnProto"><option value="udp" '+(s.ovpnProto==='udp'?'selected':'')+'>UDP</option><option value="tcp" '+(s.ovpnProto==='tcp'?'selected':'')+'>TCP</option></select></label></div>'
  ].join('');
}

function wizardPolicyFields(s){
  if(s.protocol==='ssh') return [
    '<div class="wizard-section-title"><h4>Policy</h4><p>انقضا، نشست همزمان و تعداد IP/دستگاه را تنظیم کن.</p></div>',
    '<div class="wizard-form three"><label>Expire date<input id="wizExpireDate" type="date" value="'+htmlEsc(s.expireDate)+'"><div class="preset-row"><button data-action="wizard-expiry" data-days="7">7D</button><button data-action="wizard-expiry" data-days="30">30D</button><button data-action="wizard-expiry" data-days="60">60D</button><button data-action="wizard-expiry" data-days="90">90D</button><button data-action="wizard-expiry" data-days="0">∞</button></div></label>',
    '<label>Concurrent Sessions<input id="wizSessions" type="number" min="1" max="50" value="'+Number(s.sessions)+'"></label>',
    '<label>Device / IP Limit<input id="wizDevices" type="number" min="1" max="50" value="'+Number(s.devices)+'"></label></div>',
    '<div class="wizard-note"><b>Security</b><span>PIN 4 مجاز است، اما برای سرویس عمومی PIN 6 یا Strong توصیه می‌شود.</span></div>'
  ].join('');
  if(s.protocol==='xray') return [
    '<div class="wizard-section-title"><h4>Network & Limits</h4><p>Transport، Security و محدودیت‌های Client را تعیین کن.</p></div>',
    '<div class="wizard-form three"><label>Transport<select id="wizTransport">',
    ['tcp','ws','grpc','httpupgrade','xhttp','kcp'].map(x=>'<option value="'+x+'" '+(s.transport===x?'selected':'')+'>'+x.toUpperCase()+'</option>').join(''),
    '</select></label><label>Security<select id="wizSecurity"><option value="none" '+(s.security==='none'?'selected':'')+'>None</option><option value="tls" '+(s.security==='tls'?'selected':'')+'>TLS</option><option value="reality" '+(s.security==='reality'?'selected':'')+'>REALITY</option></select></label>',
    '<label>Path / Service<input id="wizPath" value="'+htmlEsc(s.path)+'"></label>',
    '<label>SNI / Domain<input id="wizSni" value="'+htmlEsc(s.sni)+'"></label>',
    '<label>REALITY target<input id="wizReality" value="'+htmlEsc(s.realityDest)+'"></label>',
    '<label>Quota GB<input id="wizQuota" type="number" min="0" value="'+Number(s.quota)+'"><small>0 = Unlimited</small></label>',
    '<label>Expiry days<input id="wizExpireDays" type="number" min="0" max="3650" value="'+Number(s.expireDays)+'"></label>',
    '<label>Device / IP Limit<input id="wizDevices" type="number" min="1" max="50" value="'+Number(s.devices)+'"></label>',
    '<label>Traffic reset days<input id="wizResetDays" type="number" min="0" max="3650" value="'+Number(s.resetDays)+'"></label></div>'
  ].join('');
  return '<div class="wizard-review-hint"><div class="review-icon">✓</div><h4>تنظیمات پایه آماده است</h4><p>برای '+htmlEsc(s.protocol)+' تنظیم اضافی لازم نیست. در مرحله بعد اطلاعات و رمز بسته تحویل را بررسی کن.</p></div>';
}

function wizardReview(s){
  const summary=[];
  summary.push(['Protocol',s.protocol==='xray'?s.xrayProtocol.toUpperCase():s.protocol.toUpperCase()]);
  summary.push(['Name',s.name]);
  if(s.endpoint)summary.push(['Endpoint',s.endpoint]);
  if(s.protocol==='ssh'){summary.push(['Expire',s.expireDate||'No expiry']);summary.push(['Sessions',s.sessions]);summary.push(['Devices',s.devices])}
  if(s.protocol==='xray'){summary.push(['Port',s.port]);summary.push(['Transport',s.transport]);summary.push(['Security',s.security]);summary.push(['Quota',s.quota?String(s.quota)+' GB':'Unlimited']);summary.push(['Days',s.expireDays||'Unlimited'])}
  return [
    '<div class="wizard-section-title"><h4>Review & Delivery</h4><p>قبل از ساخت، اطلاعات نهایی را کنترل کن.</p></div>',
    '<div class="review-grid">'+summary.map(x=>'<div><span>'+htmlEsc(x[0])+'</span><b>'+htmlEsc(x[1])+'</b></div>').join('')+'</div>',
    '<div class="delivery-box"><div><b>Protected delivery package</b><span>پس از ساخت می‌توانی Native file یا ZIP رمزدار AES-256 را دانلود کنی.</span></div>',
    '<label>Package PIN<div class="input-action"><input id="wizPackagePassword" value="'+htmlEsc(s.packagePassword)+'" minlength="4"><button class="soft" data-action="wizard-package-pin">Generate</button></div></label></div>'
  ].join('');
}

function captureWizard(){
  const s=provisionState;if(!s)return;
  const val=id=>document.getElementById(id)?.value;
  if(val('wizName')!==undefined)s.name=val('wizName').trim();
  if(val('wizEndpoint')!==undefined)s.endpoint=val('wizEndpoint').trim();
  if(val('wizPassword')!==undefined)s.password=val('wizPassword');
  if(val('wizPlan')!==undefined)s.plan=val('wizPlan');
  if(val('wizNote')!==undefined)s.note=val('wizNote');
  if(val('wizExpireDate')!==undefined)s.expireDate=val('wizExpireDate');
  if(val('wizSessions')!==undefined)s.sessions=Number(val('wizSessions')||1);
  if(val('wizDevices')!==undefined)s.devices=Number(val('wizDevices')||1);
  if(val('wizXrayProtocol')!==undefined)s.xrayProtocol=val('wizXrayProtocol');
  if(val('wizPort')!==undefined)s.port=Number(val('wizPort')||2087);
  if(val('wizTransport')!==undefined)s.transport=val('wizTransport');
  if(val('wizSecurity')!==undefined)s.security=val('wizSecurity');
  if(val('wizPath')!==undefined)s.path=val('wizPath');
  if(val('wizSni')!==undefined)s.sni=val('wizSni');
  if(val('wizReality')!==undefined)s.realityDest=val('wizReality');
  if(val('wizQuota')!==undefined)s.quota=Number(val('wizQuota')||0);
  if(val('wizExpireDays')!==undefined)s.expireDays=Number(val('wizExpireDays')||0);
  if(val('wizResetDays')!==undefined)s.resetDays=Number(val('wizResetDays')||0);
  if(val('wizDns')!==undefined)s.dns=val('wizDns');
  if(val('wizWgMtu')!==undefined)s.wgMtu=Number(val('wizWgMtu')||1280);
  if(val('wizWgKeepalive')!==undefined)s.wgKeepalive=Number(val('wizWgKeepalive')||0);
  if(val('wizWgAllowedIps')!==undefined)s.wgAllowedIps=val('wizWgAllowedIps');
  if(val('wizOvpnPort')!==undefined)s.ovpnPort=Number(val('wizOvpnPort')||1194);
  if(val('wizOvpnProto')!==undefined)s.ovpnProto=val('wizOvpnProto');
  if(val('wizPackagePassword')!==undefined)s.packagePassword=val('wizPackagePassword');
}

function validateWizardStep(){
  const s=provisionState;
  if(s.step===2){
    if(!s.name)return 'نام کاربر/Client لازم است.';
    if(s.protocol==='ssh'&&(!s.password||s.password.length<4))return 'Password/PIN حداقل ۴ کاراکتر باشد.';
    if(s.protocol!=='ssh'&&!s.endpoint)return 'دامنه یا IP عمومی لازم است.';
    if(s.protocol==='xray'&&(!s.port||s.port<1||s.port>65535))return 'Port معتبر وارد کن.';
  }
  if(s.step===3&&s.protocol==='xray'&&s.security==='reality'&&s.xrayProtocol!=='vless')return 'REALITY در Wizard فعلی Makia فقط برای VLESS فعال است.';
  if(s.step===3&&s.protocol==='xray'&&['vless','trojan'].includes(s.xrayProtocol)&&s.security==='none'){
    const ep=(s.endpoint||'').trim();
    const privateIp=/^(10\.|127\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(ep)||ep==='localhost'||ep.endsWith('.local');
    if(!privateIp)return 'برای '+s.xrayProtocol.toUpperCase()+' روی IP/دامنه عمومی، Security را روی REALITY یا TLS بگذار.';
  }
  return '';
}

async function wizardNext(){
  captureWizard();const err=validateWizardStep();if(err){alert(err);return}
  provisionState.step=Math.min(4,provisionState.step+1);
  if(provisionState.step===4&&!provisionState.packagePassword){
    const r=await api('/api/accounts/generate-secret?mode=pin6').catch(()=>({secret:''}));provisionState.packagePassword=r.secret||'';
  }
  renderProvisionWizard();
}
function wizardPrev(){captureWizard();provisionState.step=Math.max(1,provisionState.step-1);renderProvisionWizard()}

async function createProvisionedAccess(){
  captureWizard();const s=provisionState;if(!s)return;
  if(!s.packagePassword||s.packagePassword.length<4){alert('Package PIN حداقل ۴ کاراکتر باشد.');return}
  const createBtn=document.querySelector('[data-action="wizard-create"]');if(createBtn){createBtn.disabled=true;createBtn.textContent='در حال ساخت…'}
  try{
    let r,kind=s.protocol,key=s.name;
    if(s.protocol==='ssh'){
      r=await api('/api/accounts',{method:'POST',body:JSON.stringify({username:s.name,password:s.password,password_mode:'manual',expire_date:s.expireDate||null,plan:s.plan,note:s.note,connection_limit:s.sessions,device_limit:s.devices,quota_mb:0,renewal_days:0})});
      key=s.name;
    }else if(s.protocol==='xray'){
      r=await api('/api/protocols/xray/quick-inbound',{method:'POST',body:JSON.stringify({protocol:s.xrayProtocol,port:s.port,name:s.name,endpoint:s.endpoint,transport:s.transport,security:s.security,path_value:s.path,server_name:s.sni,reality_dest:s.realityDest,quota_gb:s.quota,expire_days:s.expireDays,ip_limit:s.devices,reset_days:s.resetDays})});
      kind='xray';key=String(r.client_id);
    }else if(s.protocol==='wireguard'){
      r=await api('/api/protocols/wireguard/peers',{method:'POST',body:JSON.stringify({name:s.name,endpoint:s.endpoint,dns:s.dns,mtu:s.wgMtu,keepalive:s.wgKeepalive,allowed_ips:s.wgAllowedIps})});key=s.name;
    }else{
      r=await api('/api/protocols/openvpn/clients',{method:'POST',body:JSON.stringify({name:s.name,endpoint:s.endpoint,port:s.ovpnPort,proto:s.ovpnProto})});key=s.name;
    }
    showProvisionSuccess(kind,key,s.name,s.packagePassword,s.protocol==='ssh'?s.password:null,r);
  }catch(e){alert(e.message);if(createBtn){createBtn.disabled=false;createBtn.textContent='ساخت و آماده‌سازی'}}
}

function showProvisionSuccess(kind,key,name,packagePassword,loginSecret,result){
  provisionState=null;
  modalRoot.innerHTML=[
    '<div class="modal-backdrop"><div class="modal provision-success">',
      '<div class="success-mark">✓</div><div class="eyebrow centered">ACCESS READY</div><h3>'+htmlEsc(name)+' آماده شد</h3>',
      '<p>پروفایل روی سرور ساخته شده و بسته‌های تحویل آماده دانلود هستند.</p>',
      '<div class="success-grid"><div><span>Protocol</span><b>'+htmlEsc(kind.toUpperCase())+'</b></div><div><span>Package PIN</span><b class="credential-secret">'+htmlEsc(packagePassword)+'</b></div>',
      (loginSecret?'<div><span>Login Password</span><b class="credential-secret">'+htmlEsc(loginSecret)+'</b></div>':'')+'</div>',
      '<div class="delivery-actions">'+((kind==='xray'||kind==='wireguard'||(kind==='ssh'&&(window.__operatorSettings?.delivery?.npv_enabled!==false)))?'<button class="primary action-lg" data-action="access-share" data-kind="'+htmlEsc(kind)+'" data-key="'+dataEnc(key)+'" data-name="'+dataEnc(name)+'">'+(kind==='ssh'?'NPV QR / Import':'QR / Share')+'</button>':'')+'<button class="primary action-lg" data-action="protected-download-now" data-kind="'+htmlEsc(kind)+'" data-key="'+dataEnc(key)+'" data-name="'+dataEnc(name)+'" data-password="'+dataEnc(packagePassword)+'">Protected ZIP</button>',
      '<button class="ghost action-lg" data-action="native-export" data-kind="'+htmlEsc(kind)+'" data-key="'+dataEnc(key)+'">Native file</button><button class="ghost action-lg" data-action="client-guide" data-kind="'+htmlEsc(kind)+'">راهنمای اتصال</button></div>',
      '<div class="wizard-note"><b>تحویل امن</b><span>فایل و PIN را در دو پیام/کانال جداگانه برای کاربر بفرست.</span></div>',
      '<button class="soft wide-btn" data-action="success-done">بازگشت به Access Center</button>',
    '</div></div>'
  ].join('');
}

async function openProtectedExport(kind,key,name){
  await ensureLicenseState();
  if(!hasLicenseFeature('protected_delivery')){switchView('license');return}
  const r=await api('/api/accounts/generate-secret?mode=pin6').catch(()=>({secret:''}));
  modalRoot.innerHTML=[
    '<div class="modal-backdrop"><div class="modal export-modal">',
      '<div class="wizard-head"><div><div class="eyebrow">ENCRYPTED DELIVERY</div><h3>Protected ZIP · '+htmlEsc(name)+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div>',
      '<div class="export-shield">◆</div><p>فایل‌های Client با AES-256 داخل ZIP رمزدار قرار می‌گیرند.</p>',
      '<label class="single-label">Package PIN / Password<input id="protectedPassword" value="'+htmlEsc(r.secret||'')+'" minlength="4"></label>',
      '<div class="wizard-note"><b>نکته</b><span>این رمز فقط برای باز کردن بسته است و با Password سرویس یکی نیست.</span></div>',
      '<div class="wizard-footer"><button class="ghost" data-action="modal-close">Cancel</button><button class="primary" data-action="protected-download-confirm" data-kind="'+htmlEsc(kind)+'" data-key="'+dataEnc(key)+'" data-name="'+dataEnc(name)+'">Download ZIP</button></div>',
    '</div></div>'
  ].join('');
}

async function performProtectedDownload(kind,key,name,password){
  if(!password||password.length<4){alert('رمز بسته حداقل ۴ کاراکتر باشد.');return}
  try{
    await fetchDownload('/api/access/'+encodeURIComponent(kind)+'/'+encodeURIComponent(key)+'/package',{
      method:'POST',headers:{'Content-Type':'application/json','X-Makia-Request':'1'},body:JSON.stringify({password})
    },'makia-'+kind+'-'+name+'.zip');
    toast('Protected ZIP دانلود شد');
  }catch(e){alert('Protected ZIP: '+e.message)}
}

async function downloadAccessNative(kind,key){
  try{await fetchDownload('/api/access/'+encodeURIComponent(kind)+'/'+encodeURIComponent(key)+'/native',{},'makia-'+kind+'-'+key);toast('Native file دانلود شد')}
  catch(e){alert('Native export: '+e.message)}
}

async function openAccessShare(kind,key,name){
  try{
    const r=await api('/api/access/'+encodeURIComponent(kind)+'/'+encodeURIComponent(key)+'/share');
    const isSsh=kind==='ssh',isXray=kind==='xray';
    const directTitle=isSsh?'NPV Tunnel / NapsternetV Import':isXray?'Xray Share Center':'WireGuard QR';
    const directHelp=isSsh
      ?'در NPV Tunnel از Scan QR یا Import from Clipboard استفاده کن. لینک npvt-ssh شامل Host/User/Password همین اکانت است.'
      :isXray?'QR را در v2rayNG / Hiddify / NPV یا کلاینت سازگار اسکن کن؛ Copy Link نیز همان Share URI را می‌دهد.'
      :'این QR همان WireGuard config است و در کلاینت رسمی WireGuard قابل اسکن است.';
    const qrVisible=window.__operatorSettings?.delivery?.show_qr!==false;
    const c=r.connection||{};
    const detailPairs=isXray?[
      ['Protocol',c.protocol],['Server',c.host],['Port',c.port],['Transport',c.transport],
      ['Security',c.security],['SNI',c.sni],['Path / Service',c.path],['Flow',c.flow],
      ['Fingerprint',c.fingerprint],['Cipher',c.cipher]
    ].filter(x=>x[1]!==undefined&&x[1]!==null&&String(x[1]).length):[];
    const details=detailPairs.length?'<div class="xray-share-details">'+detailPairs.map(x=>'<div><span>'+htmlEsc(String(x[0]))+'</span><b>'+htmlEsc(String(x[1]))+'</b></div>').join('')+'</div>':'';
    const reality=(c.reality_public_key||c.reality_short_id)?'<div class="share-advanced"><b>REALITY</b><span>Public Key</span><code>'+htmlEsc(c.reality_public_key||'-')+'</code><span>Short ID</span><code>'+htmlEsc(c.reality_short_id||'-')+'</code></div>':'';
    const subBlock=r.subscription_url?[
      '<div class="share-subscription">',
        '<div><b>Subscription URL</b><span>برای کلاینت‌هایی که Subscription را پشتیبانی می‌کنند.</span></div>',
        (qrVisible&&r.subscription_qr?'<img class="share-qr small" src="'+htmlEsc(r.subscription_qr)+'" alt="Subscription QR">':''),
        '<textarea id="shareSubscription" readonly></textarea>',
        '<div class="toolbar"><button class="ghost" data-action="copy-target" data-target="shareSubscription">Copy subscription</button>',
        (qrVisible&&r.subscription_qr?'<button class="ghost" data-action="subscription-qr-download" data-key="'+dataEnc(key)+'" data-name="'+dataEnc(name)+'">Download subscription QR</button>':''),
        (r.summary?.client_url?'<a class="ghost link-btn" target="_blank" rel="noopener" href="'+htmlEsc(r.summary.client_url)+'">Open client page</a>':''),
        '</div>',
      '</div>'
    ].join(''):'';
    modalRoot.innerHTML=[
      '<div class="modal-backdrop"><div class="modal share-modal">',
        '<div class="wizard-head"><div><div class="eyebrow">ONE-TAP DELIVERY</div><h3>'+htmlEsc(directTitle)+' · '+htmlEsc(name)+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div>',
        '<div class="share-layout">',
          (qrVisible?'<div class="share-qr-wrap"><img class="share-qr" src="'+htmlEsc(r.qr)+'" alt="Connection QR"><span>'+htmlEsc(String(r.share_type||kind).toUpperCase())+'</span></div>':''),
          '<div class="share-copy"><p>'+htmlEsc(directHelp)+'</p><label>Share / Import link<textarea id="shareText" readonly></textarea></label>',
          '<div class="toolbar"><button class="primary" data-action="copy-target" data-target="shareText">Copy Import Link</button><button class="ghost" data-action="qr-download" data-kind="'+htmlEsc(kind)+'" data-key="'+dataEnc(key)+'" data-name="'+dataEnc(name)+'">Download QR</button></div></div>',
        '</div>',
        details,reality,subBlock,
        '<div class="wizard-note"><b>Security</b><span>QR و Share Link حاوی Credential اتصال هستند؛ فقط برای همان کاربر ارسال شوند. محدودیت IP/Device، حجم و Expiry همچنان روی سرور اعمال می‌شود.</span></div>',
        '<div class="wizard-footer"><button class="ghost" data-action="modal-close">Done</button>'+(r.summary?.guide_url?'<a class="ghost link-btn" target="_blank" rel="noopener" href="'+htmlEsc(r.summary.guide_url)+'">راهنمای کاربر</a>':'')+'<button class="ghost" data-action="native-export" data-kind="'+htmlEsc(kind)+'" data-key="'+dataEnc(key)+'">Native config</button><button class="primary" data-action="protected-export" data-kind="'+htmlEsc(kind)+'" data-key="'+dataEnc(key)+'" data-name="'+dataEnc(name)+'">Protected ZIP</button></div>',
      '</div></div>'
    ].join('');
    document.getElementById('shareText').value=r.share_text||'';
    const sub=document.getElementById('shareSubscription');if(sub)sub.value=r.subscription_url||'';
  }catch(e){alert('Share / QR: '+e.message)}
}

async function downloadAccessQr(kind,key,name){
  try{await fetchDownload('/api/access/'+encodeURIComponent(kind)+'/'+encodeURIComponent(key)+'/qr.svg',{},'makia-'+kind+'-'+name+'-qr.svg');toast('QR دانلود شد')}
  catch(e){alert('QR export: '+e.message)}
}

async function downloadSubscriptionQr(key,name){
  try{await fetchDownload('/api/access/xray/'+encodeURIComponent(key)+'/subscription-qr.svg',{},'makia-xray-'+name+'-subscription-qr.svg');toast('Subscription QR دانلود شد')}
  catch(e){alert('Subscription QR: '+e.message)}
}

function manageAccess(id){
  const a=accessCache.find(x=>String(x.id)===String(id));if(!a)return;
  if(a.kind==='ssh'){const row=accountCache.find(x=>x.username===a.key);if(row)return editAccount(row)}
  if(a.kind==='xray'){const row=(window.__protocolClients||[]).find(x=>String(x.id)===String(a.key));if(row)return editProtocolClient(row.id)}
}

async function revokeAccess(kind,key,name){
  if(!confirm('دسترسی '+name+' لغو شود؟ این عملیات روی سرویس واقعی اعمال می‌شود.'))return;
  try{await api('/api/access/'+encodeURIComponent(kind)+'/'+encodeURIComponent(key),{method:'DELETE'});toast('Access revoked');await access()}catch(e){alert(e.message)}
}

async function reissueWireGuard(name){
  if(!confirm('Peer قدیمی '+name+' باطل و Key جدید ساخته شود؟'))return;
  const endpoint=window.PANEL_DOMAIN||location.hostname;
  try{
    await api('/api/access/wireguard/'+encodeURIComponent(name),{method:'DELETE'});
    const r=await api('/api/protocols/wireguard/peers',{method:'POST',body:JSON.stringify({name,endpoint,dns:'1.1.1.1'})});
    showProvisionSuccess('wireguard',name,name,(await api('/api/accounts/generate-secret?mode=pin6')).secret,null,r);
  }catch(e){alert(e.message)}
}

async function openProtocolSetup(kind){
  if(kind==='xray'){
    modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal setup-modal"><div class="wizard-head"><div><div class="eyebrow">ENGINE SETUP</div><h3>Install Xray Core</h3></div><button class="close-btn" data-action="modal-close">×</button></div><p>هسته Xray با Installer رسمی XTLS نصب و به systemd متصل می‌شود.</p><div class="wizard-note"><b>Real operation</b><span>این عملیات روی VPS package/service نصب می‌کند.</span></div><div class="wizard-footer"><button class="ghost" data-action="modal-close">Cancel</button><button class="primary" data-action="protocol-install" data-kind="xray">Install Xray</button></div></div></div>';
    return;
  }
  const installed=kind==='wireguard'?Boolean(window.__protocolData?.wireguard?.installed):Boolean(window.__protocolData?.openvpn?.installed);
  const d=window.__operatorSettings?.defaults||{};
  const fields=kind==='wireguard'
    ? '<label>UDP Port<input id="setupPort" type="number" value="'+Number(d.wireguard_port||443)+'"></label><label>Tunnel CIDR<input id="setupCidr" value="'+htmlEsc(d.wireguard_cidr||'10.66.66.1/24')+'"></label><label>MTU<input id="setupMtu" type="number" min="576" max="1500" value="'+Number(d.wireguard_mtu||1280)+'"></label>'
    : '<label>Port<input id="setupPort" type="number" value="1194"></label><label>Transport<select id="setupProto"><option value="udp">UDP</option><option value="tcp">TCP</option></select></label>';
  modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal setup-modal"><div class="wizard-head"><div><div class="eyebrow">PROTOCOL SETUP</div><h3>'+htmlEsc(kind==='wireguard'?'WireGuard':'OpenVPN')+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="wizard-form two">'+fields+'</div><div class="wizard-footer"><button class="ghost" data-action="modal-close">Cancel</button><button class="primary" data-action="protocol-bootstrap" data-kind="'+kind+'" data-installed="'+(installed?'1':'0')+'">'+(installed?'Bootstrap server':'Install & Bootstrap')+'</button></div></div></div>';
}

async function performProtocolInstall(kind){
  const btn=document.querySelector('[data-action="protocol-install"]');if(btn){btn.disabled=true;btn.textContent='Installing…'}
  try{await api('/api/protocols/install',{method:'POST',body:JSON.stringify({component:kind})});toast(kind+' installed');closeModal();window.__protocolData=await api('/api/protocols');await access()}
  catch(e){alert(e.message);if(btn){btn.disabled=false;btn.textContent='Install'}}
}

async function performProtocolBootstrap(kind,installed){
  const port=Number(document.getElementById('setupPort')?.value||0);if(!port){alert('Port معتبر وارد کن.');return}
  try{
    if(!installed)await api('/api/protocols/install',{method:'POST',body:JSON.stringify({component:kind})});
    if(kind==='wireguard'){
      const cidr=document.getElementById('setupCidr')?.value||'10.66.66.1/24',mtu=Number(document.getElementById('setupMtu')?.value||1280);
      await api('/api/protocols/wireguard/bootstrap',{method:'POST',body:JSON.stringify({port,cidr,mtu})});
    }else{
      const proto=document.getElementById('setupProto')?.value||'udp';
      await api('/api/protocols/openvpn/bootstrap',{method:'POST',body:JSON.stringify({port,proto})});
    }
    toast(kind+' ready');closeModal();window.__protocolData=await api('/api/protocols');await access();
  }catch(e){alert(e.message)}
}

async function runSelfTest(){
  try{
    const r=await api('/api/diagnostics/self-test');
    const checks=(r.checks||[]);
    modalRoot.innerHTML=[
      '<div class="modal-backdrop"><div class="modal diagnostics-modal"><div class="wizard-head"><div><div class="eyebrow">RUNTIME VERIFICATION</div><h3>Self-Test · '+htmlEsc(r.summary)+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div>',
      '<div class="diagnostic-score '+(r.ok?'pass':'fail')+'"><b>'+(r.ok?'PASS':'FAIL')+'</b><span>'+Number(r.critical||0)+' critical · '+Number(r.warnings||0)+' warnings</span></div>',
      '<div class="diagnostic-list">'+checks.map(x=>'<div><i class="'+(x.ok?'ok':'bad')+'">'+(x.ok?'✓':'!')+'</i><div><b>'+htmlEsc(x.name)+'</b><span>'+htmlEsc(x.detail)+'</span></div></div>').join('')+'</div>',
      '<div class="wizard-footer"><button class="primary" data-action="modal-close">Done</button></div></div></div>'
    ].join('');
  }catch(e){alert('Self-Test: '+e.message)}
}

async function accounts(renderToken=window.__viewRenderToken){
  title.textContent='Account Center';setPageContext('SSH POLICY');
  content.innerHTML='<div class="empty">در حال بارگذاری حساب‌ها…</div>';
  const [rows,defs]=await Promise.all([api('/api/accounts'),api('/api/accounts/new-defaults')]);
  if(renderToken!==window.__viewRenderToken||activeView!=='accounts')return;
  accountCache=rows;
  content.innerHTML=`
  <div class="account-hero panel">
    <div><div class="eyebrow">SSH ACCESS · REAL POLICY ENFORCEMENT</div><h2>مدیریت حرفه‌ای اکانت SSH</h2><p class="muted">Session Limit و Device/IP Limit دو سیاست جدا هستند و هر دو توسط Policy Enforcer اعمال می‌شوند. حجم برای SSH به‌عنوان محدودیت واقعی نمایش داده نمی‌شود؛ Traffic Quota واقعی در Protocol Clients اعمال می‌شود.</p></div>
    <div class="risk-card"><span>RECOMMENDED</span><b>PIN 6</b><small>PIN 4 اختیاری است؛ برای اینترنت عمومی PIN 6 بهتر است.</small></div>
  </div>
  <div class="panel">
    <div class="panel-head"><h3>ساخت اکانت</h3><span>FAST PROVISIONING</span></div>
    <div class="form-grid">
      <label>نام کاربری<div class="input-action"><input id="cUser" value="${defs.username||''}" placeholder="user001"><button class="soft" type="button" onclick="suggestUsername()">Auto</button></div></label>
      <label>رمز / PIN<div class="input-action"><input id="cPass" type="text" inputmode="text" placeholder="Generate or type"><button class="soft" type="button" onclick="toggleSecret('cPass')">👁</button></div>
        <div class="password-tools"><button class="soft" onclick="setPass('cPass',4)">PIN 4</button><button class="soft recommended" onclick="setPass('cPass',6)">PIN 6</button><button class="soft" onclick="setPass('cPass','easy8')">Easy 8</button><button class="soft" onclick="setPass('cPass','strong')">Strong</button></div>
      </label>
      <label>مدت / تاریخ پایان<input id="cExpire" type="date"><div class="password-tools duration-tools"><button class="soft" onclick="setExpiryPreset('cExpire',1)">1 روز</button><button class="soft" onclick="setExpiryPreset('cExpire',3)">3 روز</button><button class="soft" onclick="setExpiryPreset('cExpire',7)">7 روز</button><button class="soft" onclick="setExpiryPreset('cExpire',15)">15 روز</button><button class="soft recommended" onclick="setExpiryPreset('cExpire',30)">30 روز</button><button class="soft" onclick="setExpiryPreset('cExpire',60)">60 روز</button><button class="soft" onclick="setExpiryPreset('cExpire',90)">90 روز</button><button class="soft" onclick="setExpiryPreset('cExpire',0)">بدون انقضا</button></div></label>
      <label>پلن<input id="cPlan" placeholder="30D / VIP / Trial"></label>
      <label>تعداد اتصال همزمان<div class="number-stepper"><button class="soft" onclick="stepNumber('cLimit',-1)">−</button><input id="cLimit" type="number" min="1" max="50" value="1"><button class="soft" onclick="stepNumber('cLimit',1)">+</button></div><span class="muted">تعداد Sessionهای همزمان همین Username</span></label>
      <label>تعداد دستگاه / IP<div class="number-stepper"><button class="soft" onclick="stepNumber('cDevice',-1)">−</button><input id="cDevice" type="number" min="1" max="50" value="1"><button class="soft" onclick="stepNumber('cDevice',1)">+</button></div><span class="muted">تعداد IP مبدأ همزمان؛ مستقل از Session Limit</span></label>
    </div>
    <div class="form-grid two" style="margin-top:12px"><label>یادداشت داخلی<textarea id="cNote" placeholder="نام مشتری، سفارش، توضیح و..."></textarea></label>
      <div class="provision-preview"><span>POLICY ENGINE</span><b>Expiry + Session + Device/IP</b><small>انقضا باعث Lock حساب و قطع Session می‌شود. IP اضافه و Session اضافه نیز به‌صورت دوره‌ای قطع می‌شوند.</small></div>
    </div>
    <div class="toolbar" style="margin-top:16px"><button class="primary wide-btn" onclick="createAccount()">+ ساخت و نمایش اطلاعات</button><button class="ghost" onclick="clearAccountForm()">پاک کردن فرم</button></div>
  </div>
  <div class="panel">
    <div class="panel-head account-tools"><div><h3>کاربران مدیریت‌شده</h3><span id="accountCount">${rows.length} USERS</span></div>
      <div class="filterbar"><input id="accountSearch" placeholder="جستجو نام کاربری / پلن / یادداشت" oninput="renderAccountRows()"><select id="accountFilter" onchange="renderAccountRows()"><option value="all">همه</option><option value="online">آنلاین</option><option value="active">فعال</option><option value="expiring">≤ 7 روز</option><option value="expired">منقضی</option><option value="locked">قفل</option></select></div>
    </div>
    <div class="toolbar bulkbar"><button class="soft" onclick="toggleAllAccounts()">انتخاب همه</button><button class="ghost" onclick="bulkAccounts('lock')">قفل</button><button class="ghost" onclick="bulkAccounts('unlock')">بازکردن</button><button class="ghost" onclick="bulkExtendPreset(7)">+7 روز</button><button class="ghost" onclick="bulkExtendPreset(30)">+30 روز</button><button class="ghost" onclick="bulkExtendPreset(90)">+90 روز</button><button class="ghost" onclick="bulkExtend()">تمدید سفارشی</button><button class="danger" onclick="bulkAccounts('disconnect')">قطع اتصال</button></div>
    <div id="accountRows" class="table"></div>
  </div>`;
  setExpiryPreset('cExpire',30);
  await setPass('cPass',6);
  renderAccountRows();
}
function toggleSecret(id){const el=document.getElementById(id);if(el)el.type=el.type==='password'?'text':'password'}
async function suggestUsername(){try{const d=await api('/api/accounts/new-defaults');cUser.value=d.username||''}catch(e){alert(e.message)}}
function clearAccountForm(){if(document.getElementById('cUser'))cUser.value='';if(document.getElementById('cPass'))cPass.value='';if(document.getElementById('cPlan'))cPlan.value='';if(document.getElementById('cNote'))cNote.value='';if(document.getElementById('cLimit'))cLimit.value=1;if(document.getElementById('cDevice'))cDevice.value=1;setExpiryPreset('cExpire',30)}
function renderAccountRows(){
  const root=document.getElementById('accountRows');if(!root)return;
  const q=(document.getElementById('accountSearch')?.value||'').trim().toLowerCase();
  const f=document.getElementById('accountFilter')?.value||'all';
  const rows=accountCache.filter(a=>{
    const hay=(a.username+' '+(a.plan||'')+' '+(a.note||'')).toLowerCase();
    if(q&&!hay.includes(q))return false;
    if(f==='online'&&!(a.online>0))return false;
    if(f==='active'&&(!a.enabled||a.expired))return false;
    if(f==='expiring'&&!(a.days_left!==null&&a.days_left>=0&&a.days_left<=7))return false;
    if(f==='expired'&&!a.expired)return false;
    if(f==='locked'&&a.enabled)return false;
    return true;
  });
  document.getElementById('accountCount').textContent=rows.length+' / '+accountCache.length+' USERS';
  root.innerHTML=rows.length?rows.map(a=>{
    const u=dataEnc(a.username);
    return '<div class="row account-row"><div><label class="check-user"><input class="account-check" type="checkbox" value="'+htmlEsc(a.username)+'"><div><b>'+htmlEsc(a.username)+'</b><div class="chips">'+statusFor(a)+'<span class="status-chip">Sessions '+Number(a.online||0)+'/'+Number(a.connection_limit||1)+'</span><span class="status-chip">Devices '+Number((a.online_ips||[]).length)+'/'+Number(a.device_limit||1)+'</span></div></div></label></div><div><b>'+htmlEsc(a.plan||'—')+'</b><div class="muted">'+htmlEsc(a.expire_date||'بدون انقضا')+(a.days_left!==null?' · '+a.days_left+'d':'')+'</div></div><div><b>'+htmlEsc((a.online_ips||[]).length?(a.online_ips||[]).join(', '):'بدون IP فعال')+'</b><div class="muted">'+htmlEsc(a.note||'بدون یادداشت')+'</div></div><div class="toolbar"><button class="ghost" data-action="account-edit" data-user="'+u+'">ویرایش</button><button class="ghost" data-action="account-disconnect" data-user="'+u+'">قطع</button><button class="danger" data-action="account-delete" data-user="'+u+'">حذف</button></div></div>';
  }).join(''):'<div class="empty">نتیجه‌ای پیدا نشد.</div>';
}
async function bulkExtendPreset(days){const usernames=selectedAccounts();if(!usernames.length){alert('حداقل یک کاربر را انتخاب کنید.');return}try{const r=await api('/api/accounts/bulk',{method:'POST',body:JSON.stringify({usernames,action:'extend',days})});if(r.failed?.length)alert('برخی عملیات ناموفق بود: '+r.failed.length);toast('تمدید انجام شد');await accounts()}catch(e){alert(e.message)}}
async function bulkAccounts(action){const usernames=selectedAccounts();if(!usernames.length){alert('حداقل یک کاربر را انتخاب کنید.');return}if(action==='disconnect'&&!confirm('اتصال کاربران انتخاب‌شده قطع شود؟'))return;try{const r=await api('/api/accounts/bulk',{method:'POST',body:JSON.stringify({usernames,action,days:0})});if(r.failed?.length)alert('برخی عملیات ناموفق بود: '+r.failed.length);await accounts()}catch(e){alert(e.message)}}
async function bulkExtend(){const usernames=selectedAccounts();if(!usernames.length){alert('حداقل یک کاربر را انتخاب کنید.');return}const days=Number(prompt('چند روز به تاریخ فعلی اضافه شود؟','30'));if(!days||days<1)return;try{const r=await api('/api/accounts/bulk',{method:'POST',body:JSON.stringify({usernames,action:'extend',days})});if(r.failed?.length)alert('برخی عملیات ناموفق بود: '+r.failed.length);await accounts()}catch(e){alert(e.message)}}
async function createAccount(){
  const p={username:cUser.value.trim(),password:cPass.value||null,password_mode:'manual',expire_date:cExpire.value||null,plan:cPlan.value,note:cNote.value,connection_limit:Number(cLimit.value||1),device_limit:Number(cDevice.value||1),quota_mb:0,renewal_days:0};
  if(!p.username){alert('نام کاربری را وارد کنید.');return}
  if(!p.password||p.password.length<4){alert('PIN/Password حداقل ۴ کاراکتر باشد.');return}
  try{const r=await api('/api/accounts',{method:'POST',body:JSON.stringify(p)});credentialModal({...p,password:r.password||p.password});accountCache=await api('/api/accounts')}catch(e){alert(e.message)}
}
function editAccount(a){
  window.__editingSshUser=a.username;
  modalRoot.innerHTML=[
    '<div class="modal-backdrop"><div class="modal policy-modal">',
    '<div class="wizard-head"><div><div class="eyebrow">SSH ACCESS POLICY</div><h3>'+htmlEsc(a.username)+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div>',
    '<div class="wizard-form three">',
      '<label>رمز جدید / PIN<input id="ePass" type="text" placeholder="خالی = بدون تغییر"><div class="preset-row"><button data-action="edit-secret" data-mode="pin4">PIN 4</button><button data-action="edit-secret" data-mode="pin6">PIN 6</button><button data-action="edit-secret" data-mode="easy8">Easy 8</button><button data-action="edit-secret" data-mode="strong">Strong</button></div></label>',
      '<label>تاریخ پایان<input id="eExpire" type="date" value="'+htmlEsc(a.expire_date||'')+'"><div class="preset-row"><button data-action="edit-expiry" data-days="7">+7D</button><button data-action="edit-expiry" data-days="30">+30D</button><button data-action="edit-expiry" data-days="90">+90D</button><button data-action="edit-expiry" data-days="0">∞</button></div></label>',
      '<label>پلن<input id="ePlan" value="'+htmlEsc(a.plan||'')+'"></label>',
      '<label>Session Limit<input id="eLimit" type="number" min="1" max="50" value="'+Number(a.connection_limit||1)+'"></label>',
      '<label>Device/IP Limit<input id="eDevice" type="number" min="1" max="50" value="'+Number(a.device_limit||1)+'"></label>',
      '<label>وضعیت<select id="eEnabled"><option value="1" '+(a.enabled?'selected':'')+'>فعال</option><option value="0" '+(!a.enabled?'selected':'')+'>قفل</option></select></label>',
    '</div>',
    '<label class="single-label">یادداشت داخلی<textarea id="eNote"></textarea></label>',
    '<div class="policy-summary"><div><span>Online Sessions</span><b>'+Number(a.online||0)+' / '+Number(a.connection_limit||1)+'</b></div><div><span>Live IPs</span><b>'+Number((a.online_ips||[]).length)+' / '+Number(a.device_limit||1)+'</b></div><div><span>Expiry</span><b>'+htmlEsc(a.expire_date||'∞')+'</b></div><div><span>Plan</span><b>'+htmlEsc(a.plan||'—')+'</b></div></div>',
    '<div class="wizard-footer"><button class="danger" data-action="account-delete" data-user="'+dataEnc(a.username)+'">Delete</button><button class="ghost" data-action="account-disconnect" data-user="'+dataEnc(a.username)+'">Disconnect</button><button class="primary" data-action="account-save" data-user="'+dataEnc(a.username)+'">Save changes</button></div>',
    '</div></div>'
  ].join('');
  document.getElementById('eNote').value=a.note||'';
}
function copyText(text){navigator.clipboard?.writeText(text).then(()=>toast('کپی شد')).catch(()=>prompt('Copy:',text))}
function credentialModal(p){
  const host=window.PANEL_DOMAIN||location.hostname;
  window.__lastCredential={...p,host};
  modalRoot.innerHTML=[
    '<div class="modal-backdrop"><div class="modal provision-success">',
    '<div class="success-mark">✓</div><div class="eyebrow centered">SSH ACCESS READY</div><h3>'+htmlEsc(p.username)+'</h3>',
    '<div class="success-grid"><div><span>Server</span><b>'+htmlEsc(host)+'</b></div><div><span>Username</span><b>'+htmlEsc(p.username)+'</b></div><div><span>Password / PIN</span><b class="credential-secret">'+htmlEsc(p.password)+'</b></div><div><span>Expire</span><b>'+htmlEsc(p.expire_date||'No expiry')+'</b></div></div>',
    '<div class="delivery-actions"><button class="primary" data-action="protected-export" data-kind="ssh" data-key="'+dataEnc(p.username)+'" data-name="'+dataEnc(p.username)+'">Protected ZIP</button><button class="ghost" data-action="native-export" data-kind="ssh" data-key="'+dataEnc(p.username)+'">SSH config</button><button class="ghost" data-action="copy-last-credential">Copy details</button></div>',
    '<div class="wizard-note"><b>Encrypted storage</b><span>Credential export artifact با Secret داخلی همین سرور رمزگذاری شده است.</span></div>',
    '<button class="soft wide-btn" data-action="success-done">Done</button></div></div>'
  ].join('');
}
function closeModal(){modalRoot.innerHTML=''}
async function saveAccount(u){try{const p={password:ePass.value||null,expire_date:eExpire.value||null,clear_expire:!eExpire.value,plan:ePlan.value,note:eNote.value,connection_limit:Number(eLimit.value||1),device_limit:Number(eDevice.value||1),quota_mb:0,renewal_days:0,enabled:eEnabled.value==='1'};await api('/api/accounts/'+encodeURIComponent(u),{method:'PUT',body:JSON.stringify(p)});const secret=p.password;closeModal();if(secret)toast('رمز کاربر تغییر کرد؛ Artifact تحویل هم بروزرسانی شد.');await currentView()}catch(e){alert(e.message)}}
async function accountAction(u,a){if(a==='delete'&&!confirm('حذف کامل '+u+' ؟'))return;try{await api('/api/accounts/'+encodeURIComponent(u)+'/'+a,{method:'POST'});closeModal();await currentView()}catch(e){alert(e.message)}}
function selectedAccounts(){return [...document.querySelectorAll('.account-check:checked')].map(x=>x.value)}
function toggleAllAccounts(){const all=[...document.querySelectorAll('.account-check')],should=all.some(x=>!x.checked);all.forEach(x=>x.checked=should)}
async function sessions(renderToken=window.__viewRenderToken){
  title.textContent='Live Sessions';setPageContext('CONNECTION MONITOR');
  const rows=await api('/api/sessions');if(renderToken!==window.__viewRenderToken||activeView!=='sessions')return;
  content.innerHTML=viewIntro('LIVE CONNECTIONS','نشست‌های فعال','مشاهده اتصال‌های SSH زنده و قطع کنترل‌شده Sessionهای انتخابی.','<div class="view-intro-stat"><b>'+rows.length+'</b><span>ONLINE</span></div>')+
  '<div class="panel modern-list"><div class="panel-head"><h3>Active Sessions</h3><span>REAL HOST DATA</span></div><div class="table">'+(rows.length?rows.map(s=>'<div class="row"><div><i class="status-dot ok"></i><b>'+htmlEsc(s.username)+'</b><div class="muted">'+htmlEsc(s.tty||'-')+'</div></div><div class="muted">'+htmlEsc(s.remote||'local')+'</div><div class="muted">'+htmlEsc(s.since||'-')+'</div><div><button class="danger" data-action="session-disconnect" data-tty="'+dataEnc(s.tty||'')+'" data-user="'+dataEnc(s.username||'')+'">Disconnect</button></div></div>').join(''):'<div class="empty">نشست فعالی نیست.</div>')+'</div></div>';
}
async function disconnectSession(tty,user){if(!confirm('قطع اتصال '+user+' ؟'))return;try{await api('/api/sessions/disconnect',{method:'POST',body:JSON.stringify({tty,username:user})});await sessions()}catch(e){alert(e.message)}}
function relativeSeen(v){if(!v)return'Never';const t=Date.parse(v);if(Number.isNaN(t))return v;const s=Math.max(0,Math.floor((Date.now()-t)/1000));if(s<60)return s+'s ago';if(s<3600)return Math.floor(s/60)+'m ago';if(s<86400)return Math.floor(s/3600)+'h ago';return Math.floor(s/86400)+'d ago'}
async function nodes(renderToken=window.__viewRenderToken){
  await ensureLicenseState();
  if(!hasLicenseFeature('nodes')){title.textContent='Nodes';setPageContext('FULL ACCESS');content.innerHTML=lockedFeaturePanel('nodes','Multi-node Management');return}
  title.textContent='Nodes';setPageContext('FLEET CONTROL');
  const rows=await api('/api/nodes');if(renderToken!==window.__viewRenderToken||activeView!=='nodes')return;
  content.innerHTML=viewIntro('MULTI-NODE','مدیریت نودها','VPSهای متصل را با Token مستقل، Heartbeat و Telemetry مرکزی مدیریت کن.','<button class="primary action-lg" data-action="node-create">＋ Add Node</button>')+
  '<div class="panel modern-list"><div class="notice">برای Nodeهای خارج از شبکه محلی، Controller را فقط با HTTPS در دسترس قرار بده.</div><div class="table">'+(rows.length?rows.map(n=>'<div class="row"><div><b>'+htmlEsc(n.name)+'</b><div class="muted">'+htmlEsc(n.hostname||'Waiting for heartbeat')+'</div></div><div><span class="status-chip '+(n.last_seen_at?'ok':'warn')+'">'+htmlEsc(relativeSeen(n.last_seen_at))+'</span><div class="muted">token …'+htmlEsc(n.token_last4)+'</div></div><div><b>'+htmlEsc(n.cpu??'-')+'% / '+htmlEsc(n.memory??'-')+'%</b><div class="muted">CPU / RAM · Disk '+htmlEsc(n.disk??'-')+'%</div></div><div class="toolbar"><span class="status-chip">'+htmlEsc(n.version||'-')+'</span><button class="danger" data-action="node-revoke" data-id="'+Number(n.id)+'">Revoke</button></div></div>').join(''):'<div class="empty">هنوز Nodeای ثبت نشده است.</div>')+'</div></div>';
}
async function createNode(){
  const name=prompt('نام Node:','node-01');if(!name)return;
  try{
    const r=await api('/api/nodes',{method:'POST',body:JSON.stringify({name})});
    const cmd='MAKIA_CONTROLLER_URL='+location.origin+' MAKIA_NODE_TOKEN='+r.token+' bash <(curl -fsSL https://raw.githubusercontent.com/mahanneo/Makia-VPS-Manager/main/scripts/install-node-agent.sh)';
    window.__lastNodeCommand=cmd;
    modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">NODE ENROLLMENT</div><h3>Node token created</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="notice">Token فقط همین یک‌بار نمایش داده می‌شود.</div><div class="quick-card"><b style="word-break:break-all">'+htmlEsc(r.token)+'</b><span>Node token</span></div><textarea id="nodeInstallCommand" class="config-output small" readonly></textarea><div class="wizard-footer"><button class="primary" data-action="copy-target" data-target="nodeInstallCommand">Copy command</button><button class="ghost" data-action="modal-close-refresh" data-view="nodes">Done</button></div></div></div>';
    document.getElementById('nodeInstallCommand').value=cmd;
  }catch(e){alert(e.message)}
}
async function revokeNode(id){if(!confirm('دسترسی این Node لغو شود؟'))return;try{await api('/api/nodes/'+id+'/revoke',{method:'POST'});await nodes()}catch(e){alert(e.message)}}

function protocolState(installed,active){
  if(!installed)return'<span class="engine-state missing">Not installed</span>';
  return active?'<span class="engine-state running">Running</span>':'<span class="engine-state attention">Installed</span>';
}
function engineCard(icon,name,desc,status,meta,actions=''){
  return '<article class="engine-card"><div class="engine-card-head"><span class="engine-icon">'+htmlEsc(icon)+'</span>'+status+'</div><h3>'+htmlEsc(name)+'</h3><p>'+htmlEsc(desc)+'</p><div class="engine-meta">'+meta+'</div><div class="engine-actions">'+actions+'</div></article>';
}
async function protocols(renderToken=window.__viewRenderToken){
  await ensureLicenseState();
  if(!hasLicenseFeature('xray')&&!hasLicenseFeature('wireguard')&&!hasLicenseFeature('openvpn')){
    title.textContent='Protocols';setPageContext('LICENSED ENGINES');
    content.innerHTML=lockedFeaturePanel('protocols','Xray / WireGuard / OpenVPN');
    return;
  }
  title.textContent='Protocol Hub';setPageContext('ENGINE CONTROL');
  content.innerHTML='<div class="loading-state"><span class="spinner"></span><b>در حال بررسی Engineها…</b></div>';
  const [d,clients]=await Promise.all([api('/api/protocols'),api('/api/protocol-clients')]);
  if(renderToken!==window.__viewRenderToken||activeView!=='protocols')return;
  window.__protocolData=d;window.__protocolClients=clients;
  const x=d.xray,w=d.wireguard,o=d.openvpn,s=d.stunnel,ssh=d.ssh;
  const ready=(d.capabilities||[]).filter(x=>x.available).length,total=(d.capabilities||[]).length;
  const xActions=x.installed
    ? '<button class="engine-btn primaryish" data-action="nav" data-view="access">Manage Xray Access</button><button class="engine-btn" data-action="xray-diagnostics">Diagnostics</button>'+(!x.service_active?'<button class="engine-btn warnish" data-action="xray-repair">Repair & Restart</button>':'')+'<button class="engine-btn" data-action="xray-advanced">Advanced JSON</button><button class="engine-btn" data-action="xray-tunnel">Tunnel</button>'
    : '<button class="engine-btn primaryish" data-action="protocol-setup" data-kind="xray">Install Xray Core</button>';
  const wActions=!w.installed
    ? '<button class="engine-btn primaryish" data-action="protocol-setup" data-kind="wireguard">Install & Setup</button>'
    : (!w.config
      ? '<button class="engine-btn primaryish" data-action="protocol-setup" data-kind="wireguard">Bootstrap wg0</button>'
      : '<button class="engine-btn primaryish" data-action="nav" data-view="access">Manage Peers</button><button class="engine-btn" data-action="wireguard-diagnostics">Diagnostics</button><button class="engine-btn warnish" data-action="wireguard-repair">Repair Runtime</button>');
  const oActions=!o.installed
    ? '<button class="engine-btn primaryish" data-action="protocol-setup" data-kind="openvpn">Install & Setup</button>'
    : (!o.config
      ? '<button class="engine-btn primaryish" data-action="protocol-setup" data-kind="openvpn">Bootstrap Server</button>'
      : '<button class="engine-btn primaryish" data-action="nav" data-view="access">Manage Clients</button><button class="engine-btn" data-action="openvpn-diagnostics">Diagnostics</button><button class="engine-btn warnish" data-action="openvpn-repair">Repair Runtime</button>');
  const stActions=!s.installed
    ? '<button class="engine-btn" data-action="protocol-install" data-kind="stunnel">Install Stunnel</button>'
    : '<button class="engine-btn" data-action="nav" data-view="services">Service Control</button>';

  const capabilityHtml=(d.capabilities||[]).map(cap=>'<div class="capability-card '+(cap.available?'ready':'missing')+'"><div><b>'+htmlEsc(String(cap.id||'').toUpperCase())+'</b><span>'+htmlEsc(cap.engine||'')+'</span></div><em>'+htmlEsc(cap.available?(cap.mode==='advanced'?'ADVANCED':'READY'):'UNAVAILABLE')+'</em></div>').join('');
  const inboundHtml=(x.inbounds||[]).length?(x.inbounds||[]).map(i=>'<div class="engine-inbound"><div><b>'+htmlEsc(i.tag||'untagged')+'</b><span>'+htmlEsc(i.protocol||'unknown')+'</span></div><div><b>'+htmlEsc((i.listen||'0.0.0.0')+':'+(i.port??'-'))+'</b><span>'+Number(i.clients||0)+' clients</span></div></div>').join(''):'<div class="empty compact">Inbound قابل‌خواندن پیدا نشد.</div>';

  content.innerHTML=[
    '<section class="protocol-command"><div><div class="eyebrow">ENGINE & TRANSPORT CONTROL</div><h2>Protocol Hub</h2><p>Engineها، Server Bootstrap و تنظیمات پیشرفته اینجا مدیریت می‌شوند؛ ساخت Client فقط در Access Center انجام می‌شود.</p><div class="hero-actions"><button class="primary action-lg" data-action="nav" data-view="access">Open Access Center</button><button class="ghost action-lg" data-action="protocol-refresh">Refresh Engines</button></div></div>',
    '<div class="protocol-readiness"><b>'+ready+'/'+total+'</b><span>CAPABILITIES READY</span><button class="engine-btn connectivity-lab-btn" data-action="connectivity-lab">IP / Domain Lab</button></div></section>',
    '<section class="engine-grid">',
      engineCard('X','Xray Core','VLESS / VMess / Trojan / Shadowsocks / Hysteria2 / Proxy',protocolState(x.installed,x.config_path?x.runtime_ok:x.service_active),'<span>'+htmlEsc(x.version||'Version unavailable')+'</span><span>'+Number((x.inbounds||[]).length)+' inbounds</span><span>'+(x.config_path?(x.runtime_ok?'Runtime ready':'Runtime attention'):'No active config')+'</span>',xActions),
      engineCard('W','WireGuard','Kernel/userspace WireGuard with managed wg0 bootstrap',protocolState(w.installed,w.config?w.runtime_ok:w.service_active),'<span>'+Number((w.interfaces||[]).length)+' interfaces</span><span>'+Number(w.peers||0)+' peers</span><span>'+(w.config?(w.runtime_ok?'Runtime ready':'Runtime attention'):'Not bootstrapped')+'</span>',wActions),
      engineCard('O','OpenVPN','PKI-backed OpenVPN server and inline client profiles',protocolState(o.installed,o.config?o.runtime_ok:o.service_active),'<span>'+Number((o.servers||[]).length)+' server profiles</span><span>'+htmlEsc(String(o.proto||'PKI'))+(o.port?' · '+Number(o.port):'')+'</span><span>'+(o.config?(o.runtime_ok?'Runtime ready':'Runtime attention'):'Not bootstrapped')+'</span>',oActions),
      engineCard('S','OpenSSH','System SSH access with Makia expiry/session policy',protocolState(ssh.installed,ssh.service_active),'<span>Linux accounts</span><span>Policy worker</span>','<button class="engine-btn primaryish" data-action="nav" data-view="access">Manage SSH Access</button>'),
      engineCard('T','Stunnel','TLS wrapper for selected TCP services',protocolState(s.installed,s.service_active),'<span>Optional sidecar</span>',stActions),
    '</section>',
    '<section class="protocol-detail-grid"><div class="panel"><div class="panel-head"><div><h3>Capability Matrix</h3><span>'+ready+' READY</span></div></div><div class="capability-grid-v11">'+capabilityHtml+'</div></div>',
    '<div class="panel"><div class="panel-head"><div><h3>Xray Inbounds</h3><span>'+Number((x.inbounds||[]).length)+' DETECTED</span></div></div><div class="engine-inbounds">'+inboundHtml+'</div></div></section>',
    '<section class="panel"><div class="panel-head"><div><h3>Client Policy Snapshot</h3><span>'+clients.length+' XRAY RECORDS</span></div><button class="ghost" data-action="nav" data-view="access">Manage in Access Center</button></div><div class="protocol-policy-mini">'+
      (clients.length?clients.slice(0,8).map(pc=>'<div><div><b>'+htmlEsc(pc.name)+'</b><span>'+htmlEsc(String(pc.protocol||'').toUpperCase())+'</span></div><strong class="'+(pc.enabled&&!pc.expired?'ok-text':'bad-text')+'">'+(pc.enabled&&!pc.expired?'Active':'Attention')+'</strong></div>').join(''):'<div class="empty compact">هنوز Xray Client مدیریت‌شده وجود ندارد.</div>')+
    '</div></section>'
  ].join('');
}
function createXrayTunnel(){modalRoot.innerHTML=`<div class="modal-backdrop" onclick="if(event.target===this)closeModal()"><div class="modal"><div class="modal-head"><div><div class="eyebrow">XRAY TUNNEL</div><h3>Port Forward / Dokodemo</h3></div><button class="close-btn" onclick="closeModal()">×</button></div><div class="form-grid"><label>Name<input id="tnName" value="tunnel01"></label><label>Listen port<input id="tnListen" type="number" min="1" max="65535" value="8443"></label><label>Target host<input id="tnHost" placeholder="10.0.0.2 or example.com"></label><label>Target port<input id="tnPort" type="number" min="1" max="65535" value="443"></label><label>Network<select id="tnNetwork"><option value="tcp,udp">TCP + UDP</option><option value="tcp">TCP</option><option value="udp">UDP</option></select></label></div><div class="notice">Config قبل از Apply توسط Xray validate می‌شود و در خطا Rollback انجام می‌شود.</div><div class="toolbar"><button class="primary" onclick="submitXrayTunnel()">Create Tunnel</button><button class="ghost" onclick="closeModal()">Cancel</button></div></div></div>`}
async function submitXrayTunnel(){const payload={name:tnName.value.trim(),listen_port:Number(tnListen.value),target_host:tnHost.value.trim(),target_port:Number(tnPort.value),network:tnNetwork.value};if(!payload.name||!payload.target_host||!payload.listen_port||!payload.target_port){alert('فیلدهای اصلی را کامل کنید.');return}try{const r=await api('/api/protocols/xray/tunnels',{method:'POST',body:JSON.stringify(payload)});closeModal();toast('Tunnel '+r.listen_port+' → '+r.target_host+':'+r.target_port+' created');await protocols()}catch(e){alert(e.message)}}

async function installProtocol(component){if(!confirm('Install '+component+' and required packages?'))return;try{await api('/api/protocols/install',{method:'POST',body:JSON.stringify({component})});toast(component+' installed');await protocols()}catch(e){alert(e.message)}}
function showXrayInbounds(){document.querySelector('.protocol-grid')?.nextElementSibling?.scrollIntoView({behavior:'smooth'})}
function createXrayInbound(){modalRoot.innerHTML=`<div class="modal-backdrop" onclick="if(event.target===this)closeModal()"><div class="modal"><div class="modal-head"><div><div class="eyebrow">XRAY CLIENT + INBOUND</div><h3>ساخت دسترسی Xray</h3></div><button class="close-btn" onclick="closeModal()">×</button></div><div class="form-grid"><label>Protocol<select id="xiProtocol" onchange="syncXrayForm()"><option value="vless">VLESS</option><option value="vmess">VMess</option><option value="trojan">Trojan</option><option value="shadowsocks">Shadowsocks</option><option value="hysteria2">Hysteria2</option><option value="http">HTTP Proxy</option><option value="socks">SOCKS5</option></select></label><label>Transport<select id="xiTransport" onchange="syncXrayForm()"><option value="tcp">RAW / TCP</option><option value="ws">WebSocket</option><option value="grpc">gRPC</option><option value="httpupgrade">HTTPUpgrade</option><option value="xhttp">XHTTP</option><option value="kcp">mKCP</option></select></label><label>Security<select id="xiSecurity" onchange="syncXrayForm()"><option value="none">None</option><option value="tls">TLS</option><option value="reality">REALITY</option></select></label><label>Port<input id="xiPort" type="number" min="1" max="65535" value="2087"></label><label>Client name<input id="xiName" value="client01"></label><label>Public domain / IP<input id="xiEndpoint" value="${window.PANEL_DOMAIN||location.hostname}"></label><label id="xiPathWrap">Path / Service / Seed<input id="xiPath" value="/makia"></label><label id="xiSniWrap">Domain / SNI<input id="xiSni" value="${window.PANEL_DOMAIN||''}" placeholder="vpn.example.com"></label><label id="xiRealityWrap">REALITY target<input id="xiRealityDest" value="www.cloudflare.com:443" placeholder="www.example.com:443"></label><label>Traffic quota (GB)<input id="xiQuota" type="number" min="0" step="1" value="50"><div class="password-tools quota-tools"><button class="soft" onclick="xiQuota.value=0">∞</button><button class="soft" onclick="xiQuota.value=10">10</button><button class="soft" onclick="xiQuota.value=20">20</button><button class="soft recommended" onclick="xiQuota.value=50">50</button><button class="soft" onclick="xiQuota.value=100">100</button><button class="soft" onclick="xiQuota.value=200">200</button><button class="soft" onclick="xiQuota.value=500">500</button></div><span class="muted">0 = Unlimited</span></label><label>Expiry days<input id="xiDays" type="number" min="0" max="3650" value="30"><div class="password-tools duration-tools"><button class="soft" onclick="xiDays.value=1">1D</button><button class="soft" onclick="xiDays.value=3">3D</button><button class="soft" onclick="xiDays.value=7">7D</button><button class="soft" onclick="xiDays.value=15">15D</button><button class="soft recommended" onclick="xiDays.value=30">30D</button><button class="soft" onclick="xiDays.value=60">60D</button><button class="soft" onclick="xiDays.value=90">90D</button><button class="soft" onclick="xiDays.value=0">∞</button></div></label><label>Traffic reset cycle<input id="xiResetDays" type="number" min="0" max="3650" value="30"><div class="password-tools"><button class="soft" onclick="xiResetDays.value=0">Never</button><button class="soft" onclick="xiResetDays.value=7">7D</button><button class="soft recommended" onclick="xiResetDays.value=30">30D</button><button class="soft" onclick="xiResetDays.value=60">60D</button><button class="soft" onclick="xiResetDays.value=90">90D</button></div><span class="muted">حجم مصرفی در شروع هر دوره صفر می‌شود.</span></label><label>IP / Device limit<input id="xiIpLimit" type="number" min="1" max="50" value="1"><div class="password-tools"><button class="soft recommended" onclick="xiIpLimit.value=1">1</button><button class="soft" onclick="xiIpLimit.value=2">2</button><button class="soft" onclick="xiIpLimit.value=3">3</button><button class="soft" onclick="xiIpLimit.value=5">5</button><button class="soft" onclick="xiIpLimit.value=10">10</button></div><span class="muted">با Online-IP API هسته Xray مانیتور و توسط Policy Worker enforce می‌شود؛ روی Coreهای فاقد این API فقط وضعیت Unavailable نشان داده می‌شود.</span></label></div><div id="xiCompatNote" class="notice"></div><div class="toolbar"><button class="primary" onclick="submitXrayInbound()">Create, Validate & Restart</button><button class="ghost" onclick="closeModal()">Cancel</button></div></div></div>`;syncXrayForm()}
function syncXrayForm(){
  const p=xiProtocol.value;
  if(p==='hysteria2'){xiTransport.value='tcp';xiSecurity.value='tls';xiTransport.disabled=true;xiSecurity.disabled=true}
  else if(['http','socks'].includes(p)){xiTransport.value='tcp';xiSecurity.value='none';xiTransport.disabled=true;xiSecurity.disabled=true}
  else{xiTransport.disabled=false;xiSecurity.disabled=false}
  const t=p==='hysteria2'?'hysteria':xiTransport.value,s=p==='hysteria2'?'tls':xiSecurity.value;
  const pathNeeded=['ws','grpc','httpupgrade','xhttp','kcp'].includes(t)&&!['http','socks'].includes(p);
  xiPathWrap.style.display=pathNeeded?'block':'none';
  xiSniWrap.style.display=(s==='tls'||s==='reality')&&!['http','socks'].includes(p)?'block':'none';
  xiRealityWrap.style.display=s==='reality'?'block':'none';
  const accountingLimited=['shadowsocks','http','socks'].includes(p);
  xiQuota.disabled=accountingLimited;
  xiResetDays.disabled=accountingLimited;
  if(accountingLimited){xiQuota.value=0;xiResetDays.value=0}
  let note='';
  if(p==='hysteria2') note='Hysteria2 با TLS اجرا می‌شود و Certificate دامنه باید از Domain & TLS صادر شده باشد.';
  else if(p==='http') note='HTTP Proxy با Username/Password واقعی ساخته می‌شود. Per-client Xray traffic counter برای این نوع در این نسخه قابل اتکا نیست، بنابراین Quota غیرفعال است.';
  else if(p==='socks') note='SOCKS5 با Username/Password و UDP پشتیبانی می‌شود. Per-client traffic quota برای این نوع در این نسخه غیرفعال است.';
  else if(s==='reality'&&p!=='vless') note='REALITY در Makia فعلاً فقط برای VLESS فعال است.';
  else if(s==='reality'&&!['tcp','grpc','xhttp'].includes(t)) note='REALITY با این Transport مجاز نیست؛ RAW/TCP، gRPC یا XHTTP انتخاب کن.';
  else if(p==='shadowsocks'&&s!=='none') note='Shadowsocks Quick Profile با TLS/REALITY ترکیب نمی‌شود.';
  else if(p==='shadowsocks') note='Traffic quota مستقل برای Shadowsocks Quick Profile در این نسخه قابل enforce نیست.';
  else if(s==='tls') note='TLS نیاز به Certificate معتبر همان SNI در Settings → Domain & TLS دارد.';
  else if(s==='reality') note='Makia کلید X25519 و Short ID را سمت سرور تولید می‌کند.';
  else note='Config قبل از Apply توسط خود Xray validate می‌شود و در Failure نسخه قبلی Rollback می‌شود.';
  xiCompatNote.textContent=note;
}
async function submitXrayInbound(){const payload={protocol:xiProtocol.value,transport:xiTransport.value,security:xiSecurity.value,port:Number(xiPort.value),name:xiName.value.trim(),endpoint:xiEndpoint.value.trim(),path_value:xiPath.value||'/',server_name:xiSni.value.trim(),reality_dest:xiRealityDest.value.trim(),quota_gb:Number(xiQuota.value||0),expire_days:Number(xiDays.value||0),ip_limit:Number(xiIpLimit.value||1),reset_days:Number(xiResetDays.value||0)};if(!payload.name||!payload.endpoint||!payload.port){alert('فیلدهای اصلی را کامل کنید.');return}try{const r=await api('/api/protocols/xray/quick-inbound',{method:'POST',body:JSON.stringify(payload)});xrayCredentialModal(r)}catch(e){alert(e.message)}}
function xrayCredentialModal(r){
  window.__lastXrayShare=r.share_link||'';
  modalRoot.innerHTML=[
    '<div class="modal-backdrop"><div class="modal credential-modal">',
    '<div class="wizard-head"><div><div class="eyebrow">XRAY PROFILE READY</div><h3>'+htmlEsc(String(r.protocol||'').toUpperCase())+' · '+htmlEsc(r.name)+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div>',
    '<div class="xray-share"><img src="'+htmlEsc(r.qr||'')+'" alt="QR"><div><div class="credential-grid compact"><div><span>Transport</span><b>'+htmlEsc(r.transport||'-')+'</b></div><div><span>Security</span><b>'+htmlEsc(r.security||'none')+'</b></div><div><span>Port</span><b>'+Number(r.port||0)+'</b></div><div><span>Quota</span><b>'+(r.quota_bytes?fmtBytes(r.quota_bytes):'Unlimited')+'</b></div></div><span>Share link</span><textarea id="xrayShare" readonly></textarea></div></div>',
    '<div class="delivery-actions"><button class="primary" data-action="protected-export" data-kind="xray" data-key="'+dataEnc(String(r.client_id))+'" data-name="'+dataEnc(r.name)+'">Protected ZIP</button><button class="ghost" data-action="native-export" data-kind="xray" data-key="'+dataEnc(String(r.client_id))+'">Profile file</button><button class="ghost" data-action="copy-target" data-target="xrayShare">Copy link</button><button class="ghost" data-action="client-guide" data-kind="xray">راهنمای اتصال</button></div>',
    '<div class="wizard-note"><b>Subscription ready</b><span>Profile/QR/Subscription metadata داخل بسته تحویل هم قرار می‌گیرد.</span></div></div></div>'
  ].join('');
  document.getElementById('xrayShare').value=r.share_link||'';
}
function protocolClientRow(c){const quota=Number(c.quota_bytes||0),used=Number(c.usage?.total||0),p=quota?Math.min(100,(used/quota)*100):0;const expiry=c.expire_at?new Date(c.expire_at*1000).toLocaleDateString():'∞';const state=!c.enabled?('Disabled'+(c.disabled_reason?' · '+c.disabled_reason:'')):(c.expired?'Expired':'Active');const sub=location.origin+'/sub/'+c.subscription_id;const ipCount=Number(c.online_ip_count||0),ipState=c.ip_violation?'bad':(ipCount?'ok':'');const accounting=c.accounting_supported!==false;return `<div class="protocol-client-row"><div><div class="client-main"><b>${c.name}</b><span class="protocol-pill">${c.protocol.toUpperCase()}</span><span class="status-chip ${c.enabled&&!c.expired?'ok':'bad'}">${state}</span>${c.ip_violation?'<span class="status-chip bad">IP LIMIT</span>':''}</div><div class="muted">${c.inbound_tag}</div></div><div>${accounting?`<b>${fmtBytes(used)} / ${quota?fmtBytes(quota):'Unlimited'}</b><div class="usage-track"><i style="width:${p}%"></i></div><div class="muted">↑ ${fmtBytes(c.usage?.uplink||0)} · ↓ ${fmtBytes(c.usage?.downlink||0)} · Reset ${c.reset_days?c.reset_days+'d':'manual'}</div>`:'<span class="status-chip warn">Accounting unavailable</span><div class="muted">این پروتکل در این نسخه counter مستقل per-client ندارد.</div>'}</div><div><b>${expiry}</b><div class="muted">${c.days_left===null?'No expiry':c.days_left+' days left'}</div><div class="chips"><button class="status-chip ${ipState}" onclick="showClientIPs(${c.id})">IPs ${ipCount}/${c.ip_limit}</button></div></div><div class="toolbar"><button class="ghost" onclick="copyText('${sub}')">Subscription</button><button class="ghost" onclick="editProtocolClient(${c.id})">Policy</button>${accounting?'<button class="soft" onclick="resetProtocolTraffic('+c.id+')">Reset</button>':''}</div></div>`}

function showClientIPs(id){const c=(window.__protocolClients||[]).find(x=>x.id===id);if(!c)return;const rows=c.online?.ips||[];modalRoot.innerHTML=`<div class="modal-backdrop"><div class="modal"><div class="modal-head"><div><div class="eyebrow">XRAY ONLINE STATS</div><h3>Live IPs · ${c.name}</h3></div><button class="close-btn" onclick="closeModal()">×</button></div><div class="notice">${c.online?.available?'داده از Xray online-stats API خوانده شده است.':'این Xray Core یا Topology هنوز Online-IP API قابل استفاده ارائه نکرده است.'}</div><div class="ip-list">${rows.length?rows.map(x=>`<div><b>${x.ip}</b><span>${x.last_seen?new Date(x.last_seen*1000).toLocaleString():'-'}</span></div>`).join(''):'<div class="empty">IP آنلاین ثبت نشده است.</div>'}</div></div></div>`}

function editProtocolClient(id){
  const c=(window.__protocolClients||[]).find(x=>x.id===id);if(!c)return;
  const accounting=c.accounting_supported!==false;
  modalRoot.innerHTML=`<div class="modal-backdrop"><div class="modal"><div class="modal-head"><div><div class="eyebrow">CLIENT POLICY</div><h3>${c.name}</h3></div><button class="close-btn" onclick="closeModal()">×</button></div>
  <div class="policy-summary"><div><span>Protocol</span><b>${c.protocol.toUpperCase()}</b></div><div><span>Used</span><b>${fmtBytes(c.usage?.total||0)}</b></div><div><span>Online IPs</span><b>${c.online_ip_count||0} / ${c.ip_limit||1}</b></div><div><span>Reset</span><b>${c.reset_days?c.reset_days+'d':'Manual'}</b></div></div>
  <div class="form-grid">
    <label>Traffic quota (GB)<input id="pcQuota" type="number" min="0" step="1" value="${c.quota_bytes?(c.quota_bytes/1073741824).toFixed(2):0}" ${accounting?'':'disabled'}><div class="password-tools quota-tools"><button class="soft" onclick="pcQuota.value=0" ${accounting?'':'disabled'}>∞</button><button class="soft" onclick="pcQuota.value=10" ${accounting?'':'disabled'}>10</button><button class="soft" onclick="pcQuota.value=20" ${accounting?'':'disabled'}>20</button><button class="soft recommended" onclick="pcQuota.value=50" ${accounting?'':'disabled'}>50</button><button class="soft" onclick="pcQuota.value=100" ${accounting?'':'disabled'}>100</button><button class="soft" onclick="pcQuota.value=200" ${accounting?'':'disabled'}>200</button></div><span class="muted">${accounting?'0 = Unlimited':'Accounting برای این protocol در دسترس نیست.'}</span></label>
    <label>Expiry from today (days)<input id="pcDays" type="number" min="0" max="3650" value="${c.days_left??0}"><div class="password-tools duration-tools"><button class="soft" onclick="pcDays.value=1">1</button><button class="soft" onclick="pcDays.value=3">3</button><button class="soft" onclick="pcDays.value=7">7</button><button class="soft" onclick="pcDays.value=15">15</button><button class="soft recommended" onclick="pcDays.value=30">30</button><button class="soft" onclick="pcDays.value=60">60</button><button class="soft" onclick="pcDays.value=90">90</button><button class="soft" onclick="pcDays.value=0">∞</button></div></label>
    <label>Device / IP limit<input id="pcIp" type="number" min="1" max="50" value="${c.ip_limit||1}"><div class="password-tools"><button class="soft recommended" onclick="pcIp.value=1">1</button><button class="soft" onclick="pcIp.value=2">2</button><button class="soft" onclick="pcIp.value=3">3</button><button class="soft" onclick="pcIp.value=5">5</button><button class="soft" onclick="pcIp.value=10">10</button></div></label>
    <label>Traffic reset cycle<input id="pcReset" type="number" min="0" max="3650" value="${c.reset_days||0}" ${accounting?'':'disabled'}><div class="password-tools"><button class="soft" onclick="pcReset.value=0" ${accounting?'':'disabled'}>Never</button><button class="soft" onclick="pcReset.value=7" ${accounting?'':'disabled'}>7</button><button class="soft recommended" onclick="pcReset.value=30" ${accounting?'':'disabled'}>30</button><button class="soft" onclick="pcReset.value=60" ${accounting?'':'disabled'}>60</button><button class="soft" onclick="pcReset.value=90" ${accounting?'':'disabled'}>90</button></div></label>
    <label>Status<select id="pcEnabled"><option value="1" ${c.enabled?'selected':''}>Active</option><option value="0" ${!c.enabled?'selected':''}>Disabled</option></select><span class="muted">${c.disabled_reason?'Reason: '+c.disabled_reason:'Enable/disable updates the live engine when supported.'}</span></label>
  </div>
  <div class="toolbar" style="margin-top:16px"><button class="primary" onclick="saveProtocolClient(${c.id})">Save policy</button>${accounting?'<button class="ghost" onclick="resetProtocolTraffic('+c.id+')">Reset traffic</button>':''}<button class="ghost" onclick="closeModal()">Cancel</button></div></div></div>`;
}
async function saveProtocolClient(id){try{await api('/api/protocol-clients/'+id,{method:'PUT',body:JSON.stringify({quota_gb:Number(pcQuota.value||0),expire_days:Number(pcDays.value||0),ip_limit:Number(pcIp.value||1),reset_days:Number(pcReset.value||0),enabled:pcEnabled.value==='1'})});closeModal();toast('Policy updated');await currentView()}catch(e){alert(e.message)}}
async function resetProtocolTraffic(id){if(!confirm('Traffic counter این Client صفر شود؟'))return;try{await api('/api/protocol-clients/'+id+'/reset-traffic',{method:'POST'});toast('Traffic reset');await currentView()}catch(e){alert(e.message)}}
async function openXrayAdvanced(){try{const r=await api('/api/protocols/xray/config');modalRoot.innerHTML=`<div class="modal-backdrop"><div class="modal config-modal"><div class="modal-head"><div><div class="eyebrow">ADVANCED XRAY</div><h3>Validated JSON Configuration</h3><div class="muted">${r.path}</div></div><button class="close-btn" onclick="closeModal()">×</button></div><textarea id="xrayAdvancedText" class="config-output" spellcheck="false"></textarea><div class="notice">برای Routing، Outbounds، Fallbacks، TUN، HTTP/SOCKS و تنظیمات پیشرفته. قبل از Apply با خود Xray تست می‌شود، Backup گرفته می‌شود و در Failure رول‌بک انجام می‌شود.</div><div class="toolbar"><button class="ghost" onclick="validateXrayAdvanced()">Validate</button><button class="primary" onclick="applyXrayAdvanced()">Validate & Apply</button><button class="ghost" onclick="downloadText('xray-config.json',xrayAdvancedText.value)">Export JSON</button></div></div></div>`;xrayAdvancedText.value=JSON.stringify(r.config,null,2)}catch(e){alert(e.message)}}
function parseAdvancedXray(){try{return JSON.parse(xrayAdvancedText.value)}catch(e){throw new Error('JSON نامعتبر: '+e.message)}}
async function validateXrayAdvanced(){try{const config=parseAdvancedXray();await api('/api/protocols/xray/config/validate',{method:'POST',body:JSON.stringify({config})});toast('Xray config valid ✓')}catch(e){alert(e.message)}}
async function applyXrayAdvanced(){if(!confirm('Config اعتبارسنجی، Backup و سپس روی Xray اعمال شود؟'))return;try{const config=parseAdvancedXray();const r=await api('/api/protocols/xray/config',{method:'PUT',body:JSON.stringify({config})});toast('Xray config applied');closeModal();await protocols()}catch(e){alert(e.message)}}
async function openXrayDiagnostics(){
  try{
    const d=await api('/api/protocols/xray/diagnostics');
    const hints=(d.hints||[]).map(x=>'<div class="diagnostic-hint">• '+htmlEsc(x)+'</div>').join('');
    const journal=String(d.journal||'').trim();
    modalRoot.innerHTML=[
      '<div class="modal-backdrop"><div class="modal diagnostics-modal xray-diagnostics-modal">',
      '<div class="wizard-head"><div><div class="eyebrow">XRAY RUNTIME DIAGNOSTICS</div><h3>Xray Core · '+(d.service_active?'Running':'Attention')+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div>',
      '<div class="xray-diagnostic-grid">',
        '<div><span>Version</span><b>'+htmlEsc(d.version||'Unknown')+'</b><em class="'+(d.validated_version?'ok-text':'warn-text')+'">'+(d.validated_version?'CI validated':'Version differs')+'</em></div>',
        '<div><span>systemd user</span><b>'+htmlEsc(d.service_user||'root')+'</b><em>'+htmlEsc(d.config_mode||'-')+'</em></div>',
        '<div><span>Root config test</span><b class="'+(d.root_validation?'ok-text':'bad-text')+'">'+(d.root_validation?'PASS':'FAIL')+'</b></div>',
        '<div><span>Service-user test</span><b class="'+(d.service_validation?'ok-text':'bad-text')+'">'+(d.service_validation?'PASS':'FAIL')+'</b></div>',
        '<div><span>Cert renewal hook</span><b class="'+(d.cert_sync_hook?'ok-text':'warn-text')+'">'+(d.cert_sync_hook?'READY':'MISSING')+'</b></div>',
      '</div>',
      (d.root_error?'<div class="wizard-note danger-note"><b>Root validation</b><span>'+htmlEsc(d.root_error)+'</span></div>':''),
      (d.service_error?'<div class="wizard-note danger-note"><b>Service-user validation</b><span>'+htmlEsc(d.service_error)+'</span></div>':''),
      (hints?'<div class="diagnostic-hints">'+hints+'</div>':''),
      '<div class="journal-head"><b>آخرین لاگ Xray</b><span>journalctl -u xray</span></div>',
      '<pre class="journal-box">'+htmlEsc(journal||'Journal output available نیست.')+'</pre>',
      '<div class="wizard-footer"><button class="ghost" data-action="modal-close">Close</button><button class="ghost" data-action="client-guide" data-kind="xray">راهنمای کاربران</button><button class="primary" data-action="xray-repair">Repair & Restart</button></div>',
      '</div></div>'
    ].join('');
  }catch(e){alert('Xray diagnostics: '+e.message)}
}
async function repairXrayRuntime(){
  if(!confirm('Makia از کانفیگ Xray بکاپ می‌گیرد، دسترسی فایل‌ها و TLS را اصلاح می‌کند، با همان کاربر systemd اعتبارسنجی می‌کند و سپس Xray را Restart می‌کند. ادامه؟'))return;
  try{
    const r=await api('/api/protocols/xray/repair',{method:'POST'});
    toast(r?.diagnostics?.service_active?'Xray repaired and running':'Xray repair completed');
    await openXrayDiagnostics();
  }catch(e){alert('Xray repair: '+e.message)}
}

async function bootstrapWireGuard(){const port=Number(prompt('WireGuard UDP port','51820'));if(!port)return;const cidr=prompt('Server tunnel CIDR','10.66.66.1/24');if(!cidr)return;try{const r=await api('/api/protocols/wireguard/bootstrap',{method:'POST',body:JSON.stringify({port,cidr})});toast('WireGuard '+r.interface+' started');await protocols()}catch(e){alert(e.message)}}
async function createWireGuardPeer(){const d=window.__operatorSettings?.defaults||{};const name=prompt('Peer name','client01');if(!name)return;const endpoint=prompt('Public domain or server IP',window.PANEL_DOMAIN||location.hostname);if(!endpoint)return;const dns=prompt('Client DNS',d.wireguard_dns||'1.1.1.1')||'1.1.1.1';try{const r=await api('/api/protocols/wireguard/peers',{method:'POST',body:JSON.stringify({name,endpoint,dns,mtu:Number(d.wireguard_mtu||1280),keepalive:Number(d.wireguard_keepalive??15),allowed_ips:d.wireguard_allowed_ips||'0.0.0.0/0'})});configModal('WireGuard · '+name,r.config,name+'.conf','wireguard',name);if(r.fallback_ipv4)toast('Domain profile ساخته شد؛ Protected ZIP شامل IP fallback هم هست')}catch(e){alert(e.message)}}
async function openWireGuardDiagnostics(){
  try{
    const endpoint=window.PANEL_DOMAIN||location.hostname;
    const d=await api('/api/protocols/wireguard/diagnostics?endpoint='+encodeURIComponent(endpoint));
    const ep=d.endpoint||{},warnings=(d.warnings||[]).map(x=>'<div class="diagnostic-hint">• '+htmlEsc(x)+'</div>').join('');
    modalRoot.innerHTML=[
      '<div class="modal-backdrop"><div class="modal diagnostics-modal wireguard-diagnostics-modal">',
      '<div class="wizard-head"><div><div class="eyebrow">WIREGUARD RUNTIME DIAGNOSTICS</div><h3>'+htmlEsc(endpoint)+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div>',
      '<div class="xray-diagnostic-grid">',
        '<div><span>Service</span><b class="'+(d.service_active?'ok-text':'bad-text')+'">'+(d.service_active?'ACTIVE':'DOWN')+'</b></div>',
        '<div><span>Kernel interface</span><b class="'+(d.interface_active?'ok-text':'bad-text')+'">'+(d.interface_active?'wg0 READY':'MISSING')+'</b></div>',
        '<div><span>UDP listener</span><b class="'+(d.listener?'ok-text':'bad-text')+'">'+(d.listener?('UDP/'+htmlEsc(d.port)):'MISSING')+'</b></div>',
        '<div><span>IPv4 forwarding</span><b class="'+(d.ip_forward?'ok-text':'bad-text')+'">'+(d.ip_forward?'ENABLED':'DISABLED')+'</b></div>',
        '<div><span>NAT / MASQ</span><b class="'+(d.nat_rule?'ok-text':'bad-text')+'">'+(d.nat_rule?'READY':'MISSING')+'</b></div>',
        '<div><span>FORWARD rules</span><b class="'+(d.forward_in_rule&&d.forward_out_rule?'ok-text':'bad-text')+'">'+(d.forward_in_rule&&d.forward_out_rule?'READY':'MISSING')+'</b></div>',
        '<div><span>Peers</span><b>'+Number(d.peer_count||0)+'</b><em>'+Number(d.recent_handshakes||0)+' recent handshake</em></div>',
        '<div><span>DNS → VPS</span><b class="'+(ep.dns_matches_server===false?'bad-text':'ok-text')+'">'+(ep.endpoint_is_ip?'DIRECT IP':ep.dns_matches_server===false?'MISMATCH':'DIRECT / OK')+'</b></div>',
      '</div>',
      '<div class="domain-resolution-grid"><div><span>A / IPv4</span><code>'+htmlEsc((ep.resolved_ipv4||[]).join(', ')||'none')+'</code></div><div><span>AAAA / IPv6</span><code>'+htmlEsc((ep.resolved_ipv6||[]).join(', ')||'none')+'</code></div><div><span>VPS IPv4</span><code>'+htmlEsc((ep.local_ipv4||[]).join(', ')||'unknown')+'</code></div></div>',
      warnings?'<div class="diagnostic-hints">'+warnings+'</div>':'<div class="wizard-note success-note"><b>WireGuard runtime ready</b><span>Listener، Forwarding، NAT و Endpoint مستقیم آماده‌اند.</span></div>',
      '<div class="wizard-note"><b>Domain rule</b><span>WireGuard یک UDP tunnel خام است؛ دامنه باید رکورد A مستقیم/DNS-only به VPS داشته باشد. Proxy/CDN HTTP جایگزین Forward کردن WireGuard نیست.</span></div>',
      '<div class="wizard-footer"><button class="ghost" data-action="modal-close">Close</button><button class="ghost" data-action="client-guide" data-kind="wireguard">راهنمای کاربر</button><button class="primary" data-action="wireguard-repair">Repair & Restart</button></div>',
      '</div></div>'
    ].join('');
  }catch(e){alert('WireGuard diagnostics: '+e.message)}
}
async function repairWireGuardRuntime(){
  if(!confirm('Makia از wg0.conf بکاپ می‌گیرد، IP forwarding و NAT/FORWARD را به حالت idempotent اصلاح می‌کند و WireGuard را Restart می‌کند. Peerها و کلیدها حفظ می‌شوند. ادامه؟'))return;
  try{const r=await api('/api/protocols/wireguard/repair',{method:'POST'});toast(r?.diagnostics?.runtime_ok?'WireGuard repaired and healthy':'WireGuard repair completed');await openWireGuardDiagnostics()}catch(e){alert('WireGuard repair: '+e.message)}
}
function connectivityStatusCard(name,d){
  if(!d)return '<article class="connectivity-card muted-card"><div><b>'+htmlEsc(name)+'</b><span>Not installed / not configured</span></div><em>SKIP</em></article>';
  const warnings=(d.warnings||[]).slice(0,3);
  return '<article class="connectivity-card '+(d.ok?'pass':'fail')+'"><div><b>'+htmlEsc(name)+'</b><span>'+(d.ok?'Server-side readiness PASS':'Attention required')+'</span>'+(warnings.length?'<small>'+warnings.map(htmlEsc).join(' · ')+'</small>':'')+'</div><em>'+(d.ok?'PASS':'CHECK')+'</em></article>';
}
async function runConnectivityLab(endpoint){
  const target=(endpoint||document.getElementById('connectivityEndpoint')?.value||window.PANEL_DOMAIN||location.hostname).trim();
  if(!target){alert('Domain یا IP را وارد کنید.');return}
  try{
    const d=await api('/api/protocols/connectivity?endpoint='+encodeURIComponent(target));
    const ep=(d.wireguard?.endpoint)||(d.openvpn)||d.ssh||d.xray||{};
    modalRoot.innerHTML=[
      '<div class="modal-backdrop"><div class="modal diagnostics-modal connectivity-modal">',
      '<div class="wizard-head"><div><div class="eyebrow">IP / DOMAIN CONNECTIVITY LAB</div><h3>'+htmlEsc(target)+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div>',
      '<div class="connectivity-summary"><b>'+Number(d.passed||0)+' / '+Number(d.checked||0)+'</b><span>SERVER-SIDE READINESS</span></div>',
      '<div class="connectivity-grid">'+connectivityStatusCard('SSH',d.ssh)+connectivityStatusCard('WireGuard',d.wireguard)+connectivityStatusCard('OpenVPN',d.openvpn)+connectivityStatusCard('Xray',d.xray)+'</div>',
      '<div class="domain-resolution-grid"><div><span>A / IPv4</span><code>'+htmlEsc((ep.resolved_ipv4||[]).join(', ')||'none')+'</code></div><div><span>AAAA / IPv6</span><code>'+htmlEsc((ep.resolved_ipv6||[]).join(', ')||'none')+'</code></div><div><span>VPS IPv4</span><code>'+htmlEsc((ep.local_ipv4||[]).join(', ')||'unknown')+'</code></div></div>',
      '<div class="wizard-note"><b>What this proves</b><span>این تست DNS، Listener، Service، IPv4 routing/NAT و Runtime محلی را بررسی می‌کند. تأیید ۱۰۰٪ مسیر اینترنت اپراتور/ISP فقط با اتصال واقعی از یک Client بیرونی ممکن است.</span></div>',
      '<div class="wizard-footer"><button class="ghost" data-action="connectivity-edit" data-endpoint="'+dataEnc(target)+'">Test another endpoint</button><button class="primary" data-action="modal-close">Done</button></div>',
      '</div></div>'
    ].join('');
  }catch(e){alert('Connectivity lab: '+e.message)}
}
function openConnectivityLab(endpoint=''){
  const value=endpoint||window.PANEL_DOMAIN||location.hostname;
  modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal connectivity-modal"><div class="wizard-head"><div><div class="eyebrow">PROTOCOL CONNECTIVITY LAB</div><h3>IP / Domain readiness</h3></div><button class="close-btn" data-action="modal-close">×</button></div><label class="single-label">Public domain or VPS IP<input id="connectivityEndpoint" value="'+htmlEsc(value)+'" placeholder="vpn.example.com or 203.0.113.10"></label><div class="wizard-note"><b>Scope</b><span>SSH، WireGuard، OpenVPN و همه Xray Inboundهای فعال روی همین Endpoint بررسی می‌شوند.</span></div><div class="wizard-footer"><button class="ghost" data-action="modal-close">Cancel</button><button class="primary" data-action="connectivity-run">Run checks</button></div></div></div>';
}

async function bootstrapOpenVPN(){const port=Number(prompt('OpenVPN port','1194'));if(!port)return;const proto=(prompt('Protocol: udp or tcp','udp')||'udp').toLowerCase();try{await api('/api/protocols/openvpn/bootstrap',{method:'POST',body:JSON.stringify({port,proto})});toast('OpenVPN server started');await protocols()}catch(e){alert(e.message)}}
async function createOpenVPNClient(){const name=prompt('Client name','client01');if(!name)return;const endpoint=prompt('Public domain or server IP',window.PANEL_DOMAIN||location.hostname);if(!endpoint)return;const port=Number(prompt('OpenVPN port',String(window.__operatorSettings?.defaults?.openvpn_port||1194)))||1194;const proto=(prompt('Protocol: udp or tcp',window.__operatorSettings?.defaults?.openvpn_proto||'udp')||'udp').toLowerCase();try{const r=await api('/api/protocols/openvpn/clients',{method:'POST',body:JSON.stringify({name,endpoint,port,proto})});configModal('OpenVPN · '+name,r.config,name+'.ovpn','openvpn',name);if(r.diagnostics?.warnings?.length)toast('OpenVPN ساخته شد؛ Domain Diagnostics هشدار دارد')}catch(e){alert(e.message)}}
function configModal(titleText,textData,fileName,kind=null,key=null){
  window.__lastConfigFilename=fileName||'config.txt';
  const secure=kind&&key?'<button class="primary" data-action="protected-export" data-kind="'+htmlEsc(kind)+'" data-key="'+dataEnc(key)+'" data-name="'+dataEnc(key)+'">Protected ZIP</button><button class="ghost" data-action="native-export" data-kind="'+htmlEsc(kind)+'" data-key="'+dataEnc(key)+'">Native file</button>':'';
  modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal config-modal"><div class="wizard-head"><div><div class="eyebrow">CLIENT CONFIG</div><h3>'+htmlEsc(titleText)+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div><textarea id="configOutput" class="config-output" readonly></textarea><div class="wizard-note"><b>Delivery</b><span>Protected ZIP برای تحویل امن توصیه می‌شود.</span></div><div class="wizard-footer">'+secure+'<button class="ghost" data-action="copy-target" data-target="configOutput">Copy config</button><button class="ghost" data-action="download-text-target" data-target="configOutput">Download raw</button></div></div></div>';
  document.getElementById('configOutput').value=textData;
}
function downloadText(name,text){const blob=new Blob([text],{type:'text/plain;charset=utf-8'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),500)}
async function openOpenVPNDiagnostics(){
  try{
    const endpoint=window.PANEL_DOMAIN||location.hostname;
    const d=await api('/api/protocols/openvpn/diagnostics?endpoint='+encodeURIComponent(endpoint));
    const warnings=(d.warnings||[]).map(x=>'<div class="diagnostic-hint">• '+htmlEsc(x)+'</div>').join('');
    modalRoot.innerHTML=[
      '<div class="modal-backdrop"><div class="modal diagnostics-modal openvpn-diagnostics-modal">',
      '<div class="wizard-head"><div><div class="eyebrow">OPENVPN DOMAIN DIAGNOSTICS</div><h3>'+htmlEsc(endpoint)+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div>',
      '<div class="xray-diagnostic-grid"><div><span>Service</span><b class="'+(d.service_active?'ok-text':'bad-text')+'">'+(d.service_active?'ACTIVE':'DOWN')+'</b></div><div><span>Listener</span><b class="'+(d.listener?'ok-text':'bad-text')+'">'+(d.listener?'READY':'MISSING')+'</b></div><div><span>Transport</span><b>'+htmlEsc(String(d.proto||'-'))+' : '+htmlEsc(String(d.port||'-'))+'</b></div><div><span>DNS → VPS</span><b class="'+(d.dns_matches_server===false?'bad-text':'ok-text')+'">'+(d.endpoint_is_ip?'DIRECT IP':d.dns_matches_server===false?'MISMATCH':'OK / UNKNOWN')+'</b></div></div>',
      '<div class="domain-resolution-grid"><div><span>A / IPv4</span><code>'+htmlEsc((d.resolved_ipv4||[]).join(', ')||'none')+'</code></div><div><span>AAAA / IPv6</span><code>'+htmlEsc((d.resolved_ipv6||[]).join(', ')||'none')+'</code></div><div><span>VPS IPv4</span><code>'+htmlEsc((d.local_ipv4||[]).join(', ')||'unknown')+'</code></div></div>',
      d.hybrid_available?'<div class="wizard-note success-note"><b>Domain + IP Smart Fallback</b><span>پروفایل جدید ابتدا '+htmlEsc(endpoint)+' را امتحان می‌کند و اگر مسیر دامنه/DNS روی Client جواب نداد، به '+htmlEsc(d.hybrid_fallback_ipv4||'IPv4 VPS')+' سوییچ می‌کند.</span></div>':'',
      warnings?'<div class="diagnostic-hints">'+warnings+'</div>':'<div class="wizard-note"><b>Domain endpoint ready</b><span>دامنه به IPv4 این VPS می‌رسد و Listener OpenVPN فعال است.</span></div>',
      '<div class="wizard-note"><b>SSL clarification</b><span>گواهی HTTPS پنل برای Nginx است. OpenVPN از CA/Certificate داخلی خودش استفاده می‌کند؛ Cloudflare/HTTP proxy معمولی نمی‌تواند UDP/TCP خام OpenVPN را Forward کند.</span></div>',
      '<div class="wizard-footer"><button class="ghost" data-action="modal-close">Close</button><button class="ghost" data-action="openvpn-repair">Normalize IPv4</button><button class="primary" data-action="client-guide" data-kind="openvpn">راهنمای کاربر</button></div>',
      '</div></div>'
    ].join('');
  }catch(e){alert('OpenVPN diagnostics: '+e.message)}
}
async function repairOpenVPNRuntime(){
  if(!confirm('OpenVPN server.conf به udp4/tcp4 و IPv4 listener نرمال شود؟ قبل از تغییر Backup گرفته می‌شود و در Failure rollback خواهد شد.'))return;
  try{await api('/api/protocols/openvpn/repair',{method:'POST'});toast('OpenVPN IPv4 runtime normalized');await openOpenVPNDiagnostics()}catch(e){alert('OpenVPN repair: '+e.message)}
}

async function services(renderToken=window.__viewRenderToken){
  title.textContent='Services';setPageContext('SYSTEMD CONTROL');
  await ensureLicenseState();
  const [d,pstack]=await Promise.all([api('/api/overview'),api('/api/protocols').catch(()=>({}))]);
  if(renderToken!==window.__viewRenderToken||activeView!=='services')return;
  const running=(d.services||[]).filter(x=>x.active).length;
  const installed={
    xray:Boolean(pstack?.xray?.installed),
    'openvpn-server@server':Boolean(pstack?.openvpn?.installed),
    'wg-quick@wg0':Boolean(pstack?.wireguard?.installed)
  };
  const row=s=>{
    const protocolKind=s.name==='xray'?'xray':s.name==='openvpn-server@server'?'openvpn':s.name==='wg-quick@wg0'?'wireguard':'';
    const missing=protocolKind&&installed[s.name]===false;
    const licensed=!protocolKind||hasLicenseFeature(protocolKind);
    const runtimeData=protocolKind?pstack?.[protocolKind]:null;
    const runtimeAttention=Boolean(protocolKind&&!missing&&runtimeData?.config&&runtimeData?.runtime_ok===false);
    let extra='';
    if(protocolKind&&!licensed){
      extra='<button class="soft warnish" data-action="nav" data-view="license">◆ Full Access</button>';
    }else if(s.name==='xray'){
      extra=missing
        ? '<button class="soft" data-action="protocol-setup" data-kind="xray">Install Xray</button>'
        : '<button class="ghost" data-action="xray-diagnostics">Diagnose</button>'+((!s.active||runtimeAttention)?'<button class="soft warnish" data-action="xray-repair">Repair</button>':'');
    }else if(s.name==='openvpn-server@server'){
      extra=missing
        ? '<button class="soft" data-action="protocol-setup" data-kind="openvpn">Setup OpenVPN</button>'
        : '<button class="ghost" data-action="openvpn-diagnostics">Domain</button>'+((!s.active||runtimeAttention)?'<button class="soft warnish" data-action="openvpn-repair">Repair</button>':'');
    }else if(s.name==='wg-quick@wg0'){
      extra=missing
        ? '<button class="soft" data-action="protocol-setup" data-kind="wireguard">Setup WireGuard</button>'
        : '<button class="ghost" data-action="wireguard-diagnostics">Diagnose</button>'+((!s.active||runtimeAttention)?'<button class="soft warnish" data-action="wireguard-repair">Repair</button>':'');
    }
    const controls=(missing||!licensed)?'':[
      '<button class="ghost" data-action="service-action" data-service="'+dataEnc(s.name)+'" data-service-action="start">Start</button>',
      '<button class="primary" data-action="service-action" data-service="'+dataEnc(s.name)+'" data-service-action="restart">Restart</button>',
      '<button class="danger" data-action="service-action" data-service="'+dataEnc(s.name)+'" data-service-action="stop">Stop</button>'
    ].join('');
    const stateLabel=!licensed?'License locked':missing?'Not installed':runtimeAttention?'Runtime attention':s.active?'Running':'Attention';
    const stateClass=!licensed?'warn':missing?'warn':runtimeAttention?'bad':s.active?'ok':'bad';
    return '<div class="row"><div><i class="status-dot '+(s.active&&!runtimeAttention?'ok':'bad')+'"></i><b>'+htmlEsc(s.label)+'</b><div class="muted">'+htmlEsc(s.name)+'</div></div><div class="muted">'+htmlEsc(s.state)+'</div><div><span class="status-chip '+stateClass+'">'+stateLabel+'</span></div><div class="toolbar">'+extra+controls+'</div></div>';
  };
  content.innerHTML=viewIntro('ALLOWLISTED SERVICES','کنترل سرویس‌ها','Start/Stop/Restart فقط برای سرویس‌های نصب‌شده و Allowlist شده نمایش داده می‌شود؛ Xray، WireGuard و OpenVPN Diagnostics سلامت Runtime واقعی را جدا از صرفاً Running بودن systemd بررسی می‌کنند.','<div class="view-intro-stat"><b>'+running+'/'+d.services.length+'</b><span>RUNNING</span></div>')+
  '<div class="panel modern-list"><div class="table">'+d.services.map(row).join('')+'</div></div>';
}

async function svc(n,a){try{await api('/api/services/'+n+'/'+a,{method:'POST'});await services()}catch(e){alert(e.message)}}
async function security(renderToken=window.__viewRenderToken){
  title.textContent='Security Center';setPageContext('DEFENSE LAYER');
  const [sec,two]=await Promise.all([api('/api/security'),api('/api/admin/2fa/status')]);
  if(renderToken!==window.__viewRenderToken||activeView!=='security')return;
  const card=(name,x)=>'<div class="security-control"><div><b>'+htmlEsc(name)+'</b><span>'+htmlEsc(x.installed?(x.active?'Active':'Installed / attention'):'Not installed')+'</span></div><i class="'+(x.active?'ok':'warn')+'">'+(x.active?'✓':'!')+'</i></div>';
  const score=[sec.ufw.active,sec.fail2ban.active,sec.ssh.active,two.enabled].filter(Boolean).length;
  content.innerHTML=viewIntro('DEFENSE LAYER','وضعیت امنیت','کنترل‌های اصلی Host و ورود مدیر را یکجا بررسی کن.','<div class="view-intro-stat"><b>'+score+'/4</b><span>CONTROLS</span></div>')+
  '<div class="panel"><div class="security-control-grid">'+card('UFW Firewall',sec.ufw)+card('Fail2ban',sec.fail2ban)+card('OpenSSH',sec.ssh)+'<div class="security-control"><div><b>Admin 2FA</b><span>'+(two.enabled?'Authenticator enabled':'Setup recommended')+'</span></div><i class="'+(two.enabled?'ok':'warn')+'">'+(two.enabled?'✓':'!')+'</i></div></div><div class="wizard-note"><b>SSH PIN</b><span>PIN چهاررقمی برای کاربران اختیاری است؛ Fail2ban و محدودسازی شبکه برای سرویس عمومی توصیه می‌شود.</span></div><div class="toolbar" style="margin-top:14px"><button class="primary" data-action="nav" data-view="settings">'+(two.enabled?'Manage 2FA':'Enable 2FA')+'</button><button class="ghost" data-action="self-test">Run Self-Test</button></div></div>';
}
async function backups(renderToken=window.__viewRenderToken){
  title.textContent='Backups';setPageContext('RECOVERY');
  await ensureLicenseState();
  const rows=await api('/api/backups');if(renderToken!==window.__viewRenderToken||activeView!=='backups')return;
  const total=rows.reduce((n,b)=>n+Number(b.size||0),0);
  content.innerHTML=viewIntro('RECOVERY POINTS','مرکز بکاپ','Snapshot محلی برای rollback و Portable Migration Bundle رمزگذاری‌شده برای انتقال VPS.','<div class="view-intro-actions"><div class="view-intro-stat"><b>'+rows.length+'</b><span>LOCAL BACKUPS</span></div>'+(hasLicenseFeature('portable_migration')?'<button class="ghost" data-action="portable-backup">Portable Migration</button>':'<button class="ghost" data-action="nav" data-view="license">◆ Portable Migration</button>')+'<button class="primary" data-action="backup-create">＋ Local Backup</button></div>')+
  '<div class="panel modern-list"><div class="panel-head"><div><h3>Archive</h3><span>'+fmtBytes(total)+' TOTAL</span></div></div><div class="table">'+(rows.length?rows.map(b=>'<div class="row backup-row"><div><b>'+htmlEsc(b.name)+'</b><div class="muted">Makia data snapshot</div></div><div><b>'+fmtBytes(b.size)+'</b><div class="muted">archive size</div></div><div class="muted">'+new Date(b.created_at*1000).toLocaleString()+'</div><div><span class="status-chip">Host-local 0600</span></div></div>').join(''):'<div class="empty">هنوز بکاپی ساخته نشده.</div>')+'</div></div>';
}
function openPortableBackup(){
  modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal export-modal"><div class="wizard-head"><div><div class="eyebrow">PORTABLE MIGRATION</div><h3>Encrypted VPS migration bundle</h3></div><button class="close-btn" data-action="modal-close">×</button></div><p>این بسته شامل data/.secret، Xray/REALITY، WireGuard keys، OpenVPN PKI، Nginx/Let\'s Encrypt و hash حساب‌های SSH مدیریت‌شده است.</p><label class="single-label">Migration password<input id="migrationPassword" type="password" minlength="10" autocomplete="new-password"></label><div class="wizard-note"><b>Cutover</b><span>روی VPS مقصد ابتدا Makia را نصب کن، سپس با makia-restore-portable bundle را Restore کن و در پایان DNS همان دامنه را به IP جدید تغییر بده.</span></div><div class="wizard-footer"><button class="ghost" data-action="modal-close">Cancel</button><button class="primary" data-action="portable-backup-download">Build & Download</button></div></div></div>';
}
async function downloadPortableBackup(){
  const password=document.getElementById('migrationPassword')?.value||'';
  if(password.length<10){alert('Migration password حداقل ۱۰ کاراکتر باشد.');return}
  try{await fetchDownload('/api/backups/portable',{method:'POST',headers:{'Content-Type':'application/json','X-Makia-Request':'1'},body:JSON.stringify({password})},'makia-portable-migration.zip');toast('Portable migration bundle آماده شد')}
  catch(e){alert('Portable backup: '+e.message)}
}
async function makeBackup(){try{await api('/api/backups',{method:'POST'});toast('Backup created');if(activeView==='settings')await currentView();else await backups()}catch(e){alert(e.message)}}
async function auditView(renderToken=window.__viewRenderToken){
  title.textContent='Audit Logs';setPageContext('ACCOUNTING & TRACE');
  const rows=await api('/api/audit');if(renderToken!==window.__viewRenderToken||activeView!=='audit')return;
  content.innerHTML=viewIntro('AUDIT TRAIL','گزارش رویدادها','عملیات مدیریتی، تغییرات، Exportها و دسترسی‌ها در ردپای قابل بررسی ثبت می‌شوند.','<div class="view-intro-stat"><b>'+rows.length+'</b><span>RECENT</span></div>')+
  '<div class="panel modern-list"><div class="table">'+(rows.length?rows.map(x=>'<div class="row audit-row"><div><b>'+htmlEsc(x.action)+'</b><div class="muted">'+htmlEsc(x.actor)+'</div></div><div class="muted">'+htmlEsc(x.target||'-')+'</div><div class="muted">'+htmlEsc(new Date(x.created_at).toLocaleString())+'</div><div class="muted">'+htmlEsc(x.ip||'-')+'</div></div>').join(''):'<div class="empty">رویدادی ثبت نشده است.</div>')+'</div></div>';
}
async function updates(renderToken=window.__viewRenderToken){title.textContent='Update Center';setPageContext('RELEASE MANAGEMENT');content.innerHTML='<div class="empty">در حال بررسی نسخه…</div>';let s;try{s=await api('/api/update/status')}catch(e){s={current:window.MAKIA_VERSION,latest:null,error:e.message}}if(renderToken!==window.__viewRenderToken||activeView!=='updates')return;const available=s.update_available;content.innerHTML=`<div class="panel update-hero"><div><div class="eyebrow">RELEASE CHANNEL · MAIN</div><h2>${available?'نسخه جدید آماده است':'Makia به‌روز است'}</h2><p class="muted">${s.error?'بررسی آنلاین نسخه ناموفق بود: '+s.error:'نسخه نصب‌شده با VERSION مخزن اصلی مقایسه شد.'}</p></div><div class="version-stack"><span>Installed</span><b>v${s.current||window.MAKIA_VERSION}</b><span>Latest</span><b class="${available?'accent':''}">${s.latest?'v'+s.latest:'Unavailable'}</b></div></div><div class="two-col"><div class="panel"><div class="panel-head"><h3>Safe update workflow</h3><span>CLI VERIFIED PATH</span></div><div class="timeline"><div><b>1</b><span>Pre-update backup</span></div><div><b>2</b><span>Download main</span></div><div><b>3</b><span>Dependencies + service files</span></div><div><b>4</b><span>Restart + health check</span></div></div><div class="command-box">sudo makia-upgrade <button class="soft" onclick="copyText('sudo makia-upgrade')">Copy</button></div></div><div class="panel"><div class="panel-head"><h3>Release status</h3><span>${available?'ACTION AVAILABLE':'NO ACTION'}</span></div><div class="quick-grid"><div class="quick-card"><b>${s.current||'-'}</b><span>Current</span></div><div class="quick-card"><b>${s.latest||'-'}</b><span>Latest on GitHub</span></div></div><div class="notice">مسیر امن فعلی CLI است. v0.15 از Release Archive خصوصی و Bearer Token از فایل root-only /etc/makia-vps-manager/makia.env هم پشتیبانی می‌کند؛ بنابراین بعد از مهاجرت می‌توان مخزن را Private کرد.</div></div></div>`}
async function guides(renderToken=window.__viewRenderToken){
  title.textContent='Client Guides';setPageContext('DELIVERY EDUCATION');
  if(renderToken!==window.__viewRenderToken||activeView!=='guides')return;
  const cards=[
    ['xray','Xray','VLESS / VMess / Trojan / Shadowsocks / Hysteria2','QR مستقیم، Import from Clipboard و Subscription برای v2rayNG / Hiddify / NekoBox و کلاینت‌های سازگار.'],
    ['wireguard','WireGuard','.conf / QR','Import فایل Native یا اسکن QR با برنامه رسمی WireGuard.'],
    ['openvpn','OpenVPN','.ovpn','Import فایل OVPN با OpenVPN Connect روی موبایل و دسکتاپ.'],
    ['ssh','SSH / NPV','npvt-ssh / Credentials','Import لینک/QR در NPV Tunnel سازگار یا ورود دستی SSH با Server/User/Password.']
  ];
  content.innerHTML=[
    viewIntro('CLIENT ONBOARDING','راهنمای اتصال کاربران','این صفحه لینک عمومی و قابل‌ارسال راهنماها را می‌سازد؛ Credential کاربران داخل لینک راهنما قرار نمی‌گیرد.','<a class="primary link-btn" target="_blank" rel="noopener" href="/help/connect">باز کردن راهنمای عمومی</a>'),
    '<section class="guide-admin-grid">'+cards.map(x=>'<article class="guide-admin-card"><div class="guide-admin-head"><span>'+x[1].slice(0,1)+'</span><div><b>'+x[1]+'</b><small>'+x[2]+'</small></div></div><p>'+x[3]+'</p><div class="toolbar"><button class="primary" data-action="client-guide" data-kind="'+x[0]+'">Open guide</button><button class="ghost" data-action="client-guide-copy" data-kind="'+x[0]+'">Copy guide link</button></div></article>').join('')+'</section>',
    '<section class="panel"><div class="panel-head"><div><h3>روش پیشنهادی تحویل</h3><span>LESS SUPPORT TICKETS</span></div></div><div class="guide-flow"><div><b>1</b><span>از Access Center QR/Link/File همان کاربر را بفرست.</span></div><div><b>2</b><span>لینک Guide همان پروتکل را همراه آن ارسال کن.</span></div><div><b>3</b><span>برای Xray، Client Page و Subscription روش ساده‌تر برای کاربر نهایی هستند.</span></div><div><b>4</b><span>در صورت خطا، کاربر فقط نام برنامه، سیستم‌عامل و متن Error را بفرستد؛ Credential را در گروه عمومی نفرستد.</span></div></div></section>'
  ].join('');
}

async function licenseSupport(renderToken=window.__viewRenderToken){
  title.textContent='License & Support';setPageContext('ENTITLEMENT & SUPPORT');
  content.innerHTML='<div class="loading-state"><span class="spinner"></span><b>در حال بررسی مجوز…</b></div>';
  const [state,requests,session,grants]=await Promise.all([
    ensureLicenseState(true),
    api('/api/support/requests').catch(()=>({items:[],support:{}})),
    ensureSessionContext(true).catch(()=>({remote_support:false})),
    api('/api/support/grants').catch(()=>({items:[]}))
  ]);
  if(renderToken!==window.__viewRenderToken||activeView!=='license')return;
  const support=state.support||requests.support||{},expires=state.expires_at?new Date(state.expires_at*1000).toLocaleString():'بدون تاریخ انقضا';
  const featureLabels={xray:'Xray',wireguard:'WireGuard',openvpn:'OpenVPN',protected_delivery:'Protected ZIP',subscriptions:'Subscriptions',backups:'Backups',portable_migration:'Portable Migration',nodes:'Nodes',advanced_services:'Advanced Services',ssh:'SSH',security:'Security',domain:'Domain',updates:'Updates',support:'Support'};
  const feats=(state.features||[]).map(x=>'<span class="status-chip '+(state.valid?'ok':'')+'">'+htmlEsc(featureLabels[x]||x)+'</span>').join('');
  const rows=(requests.items||[]).slice(0,8).map(x=>'<div class="support-ticket-row"><div><b>#'+Number(x.id)+' · '+htmlEsc(x.subject)+'</b><span>'+htmlEsc(x.created_at||'')+'</span></div><span class="status-chip '+(x.delivery_status==='webhook'?'ok':'')+'">'+htmlEsc(x.delivery_status||'local')+'</span></div>').join('');
  content.innerHTML=[
    '<section class="license-hero '+(state.valid?'full':'community')+'">',
      '<div><div class="eyebrow">SIGNED ED25519 ENTITLEMENT</div><h2>'+(state.valid?'Full Access فعال است':'Community · SSH Only')+'</h2>',
      '<p>'+(state.valid?'این License با کلید امضای مالک پروژه تأیید شده است.':'در حالت Community فقط عملیات اصلی SSH باز است. برای Xray، WireGuard، OpenVPN و امکانات حرفه‌ای باید Activation Code معتبر وارد شود.')+'</p></div>',
      '<div class="license-install-id"><span>INSTALLATION ID</span><b id="installId">'+htmlEsc(state.installation_id)+'</b><button class="ghost" data-action="copy-target" data-target="installId">Copy</button></div>',
    '</section>',
    '<section class="license-grid">',
      '<div class="panel"><div class="panel-head"><div><h3>وضعیت License</h3><span>'+(state.valid?'VERIFIED':'COMMUNITY')+'</span></div></div>',
        '<div class="license-facts"><div><span>Tier</span><b>'+htmlEsc(state.tier||'community')+'</b></div><div><span>Customer</span><b>'+htmlEsc(state.customer||'-')+'</b></div><div><span>License ID</span><b>'+htmlEsc(state.license_id||'-')+'</b></div><div><span>Expiry</span><b>'+htmlEsc(expires)+'</b></div></div>',
        (state.online_required?'<div class="wizard-note"><b>Online entitlement · '+htmlEsc(state.online_status||'pending')+'</b><span>'+(state.lease_expires_at?('Lease تا '+htmlEsc(new Date(state.lease_expires_at*1000).toLocaleString())):'در انتظار Sync')+(state.lease_sync_error?' · '+htmlEsc(state.lease_sync_error):'')+'</span></div><div class="toolbar"><button class="ghost" data-action="license-sync">Sync License</button></div>':''),
        '<div class="chips license-features">'+feats+'</div>',
        (state.error?'<div class="wizard-note danger-note"><b>License error</b><span>'+htmlEsc(state.error)+'</span></div>':''),
      '</div>',
      '<div class="panel"><div class="panel-head"><div><h3>فعال‌سازی Full Access</h3><span>OFFLINE SIGNED CODE</span></div></div>',
        '<label class="single-label">Activation Code<textarea id="licenseCode" class="config-output small" placeholder="MKL1...."></textarea></label>',
        '<div class="wizard-note"><b>امنیت</b><span>Private signing key روی این VPS یا داخل GitHub قرار نمی‌گیرد. فقط Public Key برای Verify داخل پنل است.</span></div>',
        '<div class="toolbar"><button class="primary" data-action="license-activate">Activate</button>'+(state.valid?'<button class="danger" data-action="license-remove">Remove License</button>':'')+'</div>',
      '</div>',
    '</section>',
    (!session.remote_support?'<section class="panel remote-support-panel"><div class="panel-head"><div><h3>Remote Support موقت</h3><span>CONSENT · ONE-TIME CODE</span></div></div><div class="remote-support-create"><div><p>فقط در زمان نیاز یک کد موقت بساز. کد پس از اولین Login مصرف می‌شود و Session حداکثر تا زمان انتخاب‌شده فعال می‌ماند.</p><div class="form-grid two"><label>مدت<select id="supportGrantMinutes"><option value="15">15 دقیقه</option><option value="30" selected>30 دقیقه</option><option value="60">60 دقیقه</option><option value="120">120 دقیقه</option></select></label><label>Scope<select id="supportGrantScope"><option value="readonly">Read-only</option><option value="operator" selected>Operator</option></select></label></div><button class="primary" data-action="support-grant-create">ساخت کد موقت</button></div><div class="support-grant-list">'+((grants.items||[]).slice(0,5).map(g=>'<div><span>…'+htmlEsc(g.token_last4)+'</span><b>'+htmlEsc(g.scope)+'</b><small>'+htmlEsc(new Date(Number(g.expires_at)*1000).toLocaleString())+'</small>'+(g.active?'<button class="danger" data-action="support-grant-revoke" data-id="'+Number(g.id)+'">Revoke</button>':'<em>Closed</em>')+'</div>').join('')||'<div class="empty compact">کد فعالی وجود ندارد.</div>')+'</div></div></section>':'<section class="wizard-note danger-note"><b>Remote Support Session</b><span>این Login موقت است. تنظیمات هویتی حساس مانند 2FA، API Token و حذف License برای Remote Support مسدود هستند.</span></section>'),
    '<section class="license-grid">',
      '<div class="panel"><div class="panel-head"><div><h3>درخواست دسترسی / پشتیبانی</h3><span>SUPPORT REQUEST</span></div></div>',
        '<div class="form-grid two"><label>Subject<input id="supportSubject" maxlength="160" value="درخواست دسترسی Full"></label><label>Installation ID<input value="'+htmlEsc(state.installation_id)+'" readonly></label></div>',
        '<label class="single-label">Message<textarea id="supportMessage" rows="6" placeholder="توضیح درخواست یا مشکل…"></textarea></label>',
        '<div class="toolbar"><button class="primary" data-action="support-submit">ثبت درخواست</button>'+(support.telegram_url?'<button class="ghost" data-action="support-telegram" data-url="'+htmlEsc(support.telegram_url)+'">Telegram @'+htmlEsc(support.telegram_username)+'</button>':'')+'</div>',
        '<div class="wizard-note"><b>Ticket delivery</b><span>'+(support.webhook_enabled?'Webhook مرکزی فعال است؛ Ticket علاوه بر ثبت محلی ارسال می‌شود.':'Webhook مرکزی تنظیم نشده؛ درخواست محلی ثبت می‌شود و متن آماده برای Telegram/ارسال دستی تولید می‌گردد.')+'</span></div>',
      '</div>',
      '<div class="panel"><div class="panel-head"><div><h3>درخواست‌های اخیر</h3><span>LOCAL HISTORY</span></div></div><div class="support-ticket-list">'+(rows||'<div class="empty compact">درخواستی ثبت نشده.</div>')+'</div></div>',
    '</section>'
  ].join('');
}

async function createRemoteSupportGrant(){
  const minutes=Number(document.getElementById('supportGrantMinutes')?.value||30),scope=document.getElementById('supportGrantScope')?.value||'operator';
  try{
    const r=await api('/api/support/grants',{method:'POST',body:JSON.stringify({minutes,scope})});
    modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">ONE-TIME REMOTE SUPPORT</div><h3>کد موقت آماده است</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="support-code-box" id="supportGrantCode">'+htmlEsc(r.code)+'</div><div class="wizard-note"><b>Login URL</b><span id="supportGrantUrl">'+htmlEsc(r.login_url)+'</span></div><div class="wizard-note"><b>Expiry</b><span>'+htmlEsc(new Date(r.expires_at*1000).toLocaleString())+' · '+htmlEsc(r.scope)+'</span></div><div class="wizard-footer"><button class="primary" data-action="copy-target" data-target="supportGrantCode">Copy Code</button><button class="ghost" data-action="copy-target" data-target="supportGrantUrl">Copy URL</button><button class="ghost" data-action="modal-close-refresh" data-view="license">Done</button></div></div></div>';
  }catch(e){alert('Remote Support: '+e.message)}
}
async function revokeRemoteSupportGrant(id){
  if(!confirm('این دسترسی پشتیبانی فوراً لغو شود؟'))return;
  try{await api('/api/support/grants/'+Number(id),{method:'DELETE'});toast('Remote Support revoked');await currentView()}catch(e){alert(e.message)}
}
async function syncLicenseNow(){
  try{window.__licenseState=await api('/api/license/sync',{method:'POST'});toast('License sync completed');syncLicenseShell();await currentView()}catch(e){alert('License sync: '+e.message)}
}

async function activateLicense(){
  const code=(document.getElementById('licenseCode')?.value||'').trim();if(!code){alert('Activation Code را وارد کنید.');return}
  try{window.__licenseState=await api('/api/license/activate',{method:'POST',body:JSON.stringify({code})});toast('Full Access فعال شد');syncLicenseShell();await currentView()}catch(e){alert('License: '+e.message)}
}
async function removeLicense(){
  if(!confirm('License از این نصب حذف شود و پنل به Community / SSH Only برگردد؟'))return;
  try{window.__licenseState=await api('/api/license',{method:'DELETE'});toast('Community mode فعال شد');syncLicenseShell();await currentView()}catch(e){alert(e.message)}
}
async function submitSupportRequest(){
  const subject=(document.getElementById('supportSubject')?.value||'').trim(),message=(document.getElementById('supportMessage')?.value||'').trim();
  if(subject.length<3||message.length<3){alert('Subject و Message را کامل کنید.');return}
  try{
    const r=await api('/api/support/requests',{method:'POST',body:JSON.stringify({subject,message})});
    modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">SUPPORT REQUEST</div><h3>درخواست ثبت شد</h3></div><button class="close-btn" data-action="modal-close">×</button></div><textarea id="supportRequestText" class="config-output small" readonly></textarea><div class="wizard-note"><b>Delivery: '+htmlEsc(r.status||'local')+'</b><span>'+(r.delivered?'درخواست به Endpoint مرکزی هم ارسال شد.':'این متن را می‌توانی برای پشتیبانی ارسال کنی.')+'</span></div><div class="wizard-footer"><button class="primary" data-action="copy-target" data-target="supportRequestText">Copy Request</button>'+(r.support?.telegram_url?'<button class="ghost" data-action="support-telegram" data-url="'+htmlEsc(r.support.telegram_url)+'">Open Telegram</button>':'')+'<button class="ghost" data-action="modal-close-refresh" data-view="license">Done</button></div></div></div>';
    document.getElementById('supportRequestText').value=r.request_text||'';
  }catch(e){alert('Support: '+e.message)}
}

async function settings(renderToken=window.__viewRenderToken){
  title.textContent='Settings';setPageContext('PANEL CONFIGURATION');
  const [general,two,tokens,operator,backupRows]=await Promise.all([
    api('/api/settings/general'),
    api('/api/admin/2fa/status').catch(()=>({enabled:false,configured:false,restricted:true})),
    api('/api/admin/tokens').catch(()=>[]),
    api('/api/settings/operator'),
    api('/api/backups').catch(()=>[])
  ]);
  if(renderToken!==window.__viewRenderToken||activeView!=='settings')return;
  window.PANEL_DOMAIN=general.panel_domain||'';window.__operatorSettings=operator;
  window.__settingsTab=window.__settingsTab||'general';
  const tab=window.__settingsTab,ds=general.domain_status||{},delivery=operator.delivery||{},defs=operator.defaults||{},sub=operator.subscription||{};
  const tabs=[
    ['general','◫','Panel General'],['domain','⌁','Domain / Nginx / HTTPS'],['ssh','⌘','SSH Defaults'],
    ['xray','✦','Xray Defaults'],['vpn','◈','WG / OpenVPN'],['delivery','◇','Delivery / NPV'],
    ['subscription','◎','Subscription'],['security','◆','Admin Security'],['api','↔','API Tokens'],['recovery','⟳','Backup / Recovery']
  ];
  const nav=tabs.map(x=>'<button class="'+(tab===x[0]?'active':'')+'" data-action="settings-tab" data-tab="'+x[0]+'"><i>'+x[1]+'</i><span>'+x[2]+'</span></button>').join('');
  let body='';

  if(tab==='general'){
    body=[
      '<section class="settings-section-head"><div><div class="eyebrow">PANEL EXPERIENCE</div><h2>Panel General</h2><p>زبان، Theme، Density و هویت عمومی پنل؛ فارسی RTL و English LTR از Shell مشترک اعمال می‌شوند.</p></div><span class="settings-version">v'+htmlEsc(window.MAKIA_VERSION)+'</span></section>',
      '<div class="settings-card-v2"><div class="settings-card-title"><div><b>Interface</b><span>Language, theme and layout density</span></div></div>',
      '<div class="settings-form-grid"><label>Language<select id="generalLang"><option value="fa" '+(general.language==='fa'?'selected':'')+'>فارسی</option><option value="en" '+(general.language==='en'?'selected':'')+'>English</option></select></label>',
      '<label>Theme<select id="generalTheme"><option value="glass" '+(general.theme==='glass'?'selected':'')+'>Glass Aurora</option><option value="midnight" '+(general.theme==='midnight'?'selected':'')+'>Midnight</option><option value="amoled" '+(general.theme==='amoled'?'selected':'')+'>AMOLED</option><option value="graphite" '+(general.theme==='graphite'?'selected':'')+'>Graphite</option></select></label>',
      '<label>Density<select id="generalDensity"><option value="comfortable" '+(general.density==='comfortable'?'selected':'')+'>Comfortable</option><option value="compact" '+(general.density==='compact'?'selected':'')+'>Compact</option></select></label>',
      '<label>Panel Domain<input id="generalDomain" value="'+htmlEsc(general.panel_domain||'')+'" placeholder="panel.example.com"></label></div>',
      '<div class="settings-actions"><button class="primary" data-action="settings-general-save">Save panel settings</button></div></div>',
      '<div class="settings-card-v2"><div class="settings-card-title"><div><b>Operational owners</b><span>فقط مسیرهایی که Backend واقعی دارند</span></div></div>',
      '<div class="settings-shortcuts"><button data-action="nav" data-view="protocols"><b>Protocol Hub</b><span>Xray/WG/OpenVPN engines</span></button><button data-action="nav" data-view="access"><b>Access Center</b><span>Client provisioning & delivery</span></button><button data-action="nav" data-view="updates"><b>Update Center</b><span>Release status</span></button><button data-action="self-test"><b>Self-Test</b><span>DB, crypto and services</span></button></div></div>'
    ].join('');
  }else if(tab==='domain'){
    body=[
      '<section class="settings-section-head"><div><div class="eyebrow">PUBLIC PANEL EDGE</div><h2>Panel Domain / Nginx / HTTPS</h2><p>Domain، Nginx و Let\'s Encrypt با validation و rollback واقعی مدیریت می‌شوند.</p></div></section>',
      '<div class="settings-card-v2"><div class="domain-health-v2"><div><span>Configured domain</span><b>'+htmlEsc(general.panel_domain||'IP Mode')+'</b></div><div><span>DNS IPv4</span><b>'+htmlEsc(ds.resolved_ipv4?.length?ds.resolved_ipv4.join(', '):'Not resolved')+'</b></div><div><span>Certificate</span><b class="'+(ds.certificate&&Number(ds.certificate_days_left??99)>14?'ok-text':'warn-text')+'">'+(ds.certificate?('Installed'+(ds.certificate_days_left!==null&&ds.certificate_days_left!==undefined?' · '+Number(ds.certificate_days_left)+'d':'')):'Not installed')+'</b></div><div><span>Certbot</span><b>'+(ds.certbot_installed?'Ready':'Will install on demand')+'</b></div></div>',
      '<div class="settings-form-grid two"><label>Panel Domain<input id="domainName" value="'+htmlEsc(general.panel_domain||'')+'" placeholder="panel.example.com"></label><label>Let\'s Encrypt email<input id="tlsEmail" type="email" placeholder="admin@example.com"></label></div>',
      '<div class="wizard-note"><b>DNS gate</b><span>قبل از صدور HTTPS، رکورد A دامنه باید به همین VPS اشاره کند. Apply Nginx قبل از reload با nginx -t بررسی و در خطا rollback می‌شود.</span></div>',
      '<div class="settings-actions"><button class="ghost" data-action="settings-domain-apply">Apply domain to Nginx</button><button class="primary" data-action="settings-cert-issue">Issue / Renew HTTPS</button></div></div>'
    ].join('');
  }else if(tab==='ssh'){
    body=[
      '<section class="settings-section-head"><div><div class="eyebrow">PROVISIONING DEFAULTS</div><h2>SSH Defaults</h2><p>سیاست پیش‌فرض کاربر جدید SSH؛ Wizard عمومی و مستقیم هر دو از همین مقادیر استفاده می‌کنند.</p></div></section>',
      '<div class="settings-card-v2"><div class="settings-form-grid">',
      '<label>Password mode<select id="opSshPassword"><option value="pin4" '+(defs.ssh_password_mode==='pin4'?'selected':'')+'>PIN 4</option><option value="pin6" '+(defs.ssh_password_mode==='pin6'?'selected':'')+'>PIN 6</option><option value="easy8" '+(defs.ssh_password_mode==='easy8'?'selected':'')+'>Easy 8</option><option value="strong" '+(defs.ssh_password_mode==='strong'?'selected':'')+'>Strong</option></select></label>',
      '<label>Expiry days<input id="opSshDays" type="number" min="0" max="3650" value="'+Number(defs.ssh_expire_days??30)+'"><small>0 = no expiry</small></label><label>Concurrent sessions<input id="opSshSessions" type="number" min="1" max="50" value="'+Number(defs.ssh_sessions||1)+'"></label><label>Device / IP limit<input id="opSshDevices" type="number" min="1" max="50" value="'+Number(defs.ssh_devices||1)+'"></label></div>',
      '<div class="settings-actions"><button class="primary" data-action="settings-operator-save">Save SSH defaults</button></div></div>'
    ].join('');
  }else if(tab==='xray'){
    body=[
      '<section class="settings-section-head"><div><div class="eyebrow">PROVISIONING DEFAULTS</div><h2>Xray Defaults</h2><p>Defaultهای واقعی ساخت Client برای VLESS / VMess / Trojan / Shadowsocks / Hysteria2.</p></div></section>',
      '<div class="settings-card-v2"><div class="settings-form-grid">',
      '<label>Protocol<select id="opXrayProtocol">'+['vless','vmess','trojan','shadowsocks','hysteria2','http','socks'].map(x=>'<option value="'+x+'" '+(defs.xray_protocol===x?'selected':'')+'>'+x.toUpperCase()+'</option>').join('')+'</select></label>',
      '<label>Port<input id="opXrayPort" type="number" min="1" max="65535" value="'+Number(defs.xray_port||2087)+'"></label>',
      '<label>Transport<select id="opXrayTransport">'+['tcp','ws','grpc','httpupgrade','xhttp','kcp'].map(x=>'<option value="'+x+'" '+(defs.xray_transport===x?'selected':'')+'>'+x.toUpperCase()+'</option>').join('')+'</select></label>',
      '<label>Security<select id="opXraySecurity"><option value="reality" '+(defs.xray_security==='reality'?'selected':'')+'>REALITY</option><option value="tls" '+(defs.xray_security==='tls'?'selected':'')+'>TLS</option><option value="none" '+(defs.xray_security==='none'?'selected':'')+'>None</option></select></label>',
      '<label>Path / Service<input id="opXrayPath" value="'+htmlEsc(defs.xray_path||'/makia')+'"></label><label>SNI<input id="opXraySni" value="'+htmlEsc(defs.xray_sni||'www.microsoft.com')+'"></label><label>REALITY target<input id="opXrayTarget" value="'+htmlEsc(defs.xray_reality_target||'www.microsoft.com:443')+'"></label>',
      '<label>Quota GB<input id="opXrayQuota" type="number" min="0" value="'+Number(defs.xray_quota_gb??50)+'"></label><label>Expiry days<input id="opXrayDays" type="number" min="0" max="3650" value="'+Number(defs.xray_expire_days??30)+'"></label><label>IP limit<input id="opXrayIp" type="number" min="1" max="50" value="'+Number(defs.xray_ip_limit||1)+'"></label><label>Traffic reset days<input id="opXrayReset" type="number" min="0" max="3650" value="'+Number(defs.xray_reset_days??30)+'"></label></div>',
      '<div class="wizard-note"><b>Full Xray Core mode</b><span>Wizard بالا یک subset امن و ساختاریافته است. برای هر inbound/outbound/routing/fallback یا transport دیگری که Xray Core نصب‌شده پشتیبانی می‌کند از Advanced JSON استفاده کن؛ قبل از Apply با خود Xray validate و در خطا rollback می‌شود.</span></div>',
      '<div class="settings-actions"><button class="ghost" data-action="xray-diagnostics">Diagnostics</button><button class="ghost" data-action="xray-repair">Repair runtime</button><button class="ghost" data-action="xray-advanced">Advanced JSON</button><button class="primary" data-action="settings-operator-save">Save Xray defaults</button></div></div>'
    ].join('');
  }else if(tab==='vpn'){
    body=[
      '<section class="settings-section-head"><div><div class="eyebrow">PROVISIONING DEFAULTS</div><h2>WireGuard / OpenVPN Defaults</h2><p>تنظیمات پیش‌فرض Client برای Engineهای واقعی نصب‌شده روی Host.</p></div></section>',
      '<div class="settings-card-v2"><div class="settings-card-title"><div><b>WireGuard compatibility</b><span>Real client/server defaults</span></div><button class="soft" data-action="wg-compat-preset">Compatibility preset</button></div><div class="settings-form-grid"><label>DNS<input id="opWgDns" value="'+htmlEsc(defs.wireguard_dns||'1.1.1.1')+'"></label><label>UDP Listen Port<input id="opWgPort" type="number" min="1" max="65535" value="'+Number(defs.wireguard_port||443)+'"></label><label>MTU<input id="opWgMtu" type="number" min="576" max="1500" value="'+Number(defs.wireguard_mtu||1280)+'"></label><label>Keepalive seconds<input id="opWgKeepalive" type="number" min="0" max="3600" value="'+Number(defs.wireguard_keepalive??15)+'"></label><label>Allowed IPs<input id="opWgAllowedIps" value="'+htmlEsc(defs.wireguard_allowed_ips||'0.0.0.0/0')+'"></label><label>Tunnel CIDR<input id="opWgCidr" value="'+htmlEsc(defs.wireguard_cidr||'10.66.66.1/24')+'"></label></div><div class="wizard-note"><b>Important</b><span>Port 443/UDP و MTU پایین‌تر فقط سازگاری NAT/MTU را بهتر می‌کنند. اگر WireGuard protocol-level blocking وجود داشته باشد، از Xray/REALITY استفاده کن. برای مهاجرت بدون تعویض config کاربران، Endpoint را دامنه ثابت پنل قرار بده.</span></div></div>',
      '<div class="settings-card-v2"><div class="settings-card-title"><div><b>OpenVPN</b><span>Client defaults</span></div></div><div class="settings-form-grid"><label>OpenVPN port<input id="opOvpnPort" type="number" min="1" max="65535" value="'+Number(defs.openvpn_port||1194)+'"></label><label>OpenVPN transport<select id="opOvpnProto"><option value="udp" '+(defs.openvpn_proto==='udp'?'selected':'')+'>UDP</option><option value="tcp" '+(defs.openvpn_proto==='tcp'?'selected':'')+'>TCP</option></select></label></div>',
      '<div class="wizard-note"><b>Domain mode</b><span>OpenVPN از TLS/PKI داخلی خودش استفاده می‌کند؛ HTTPS پنل تونل OpenVPN نیست. برای Domain، رکورد A باید مستقیم و DNS-only به VPS اشاره کند. پروفایل‌های جدید روی udp4/tcp4 ساخته می‌شوند تا AAAA اشتباه باعث شکست اتصال نشود.</span></div><div class="settings-actions"><button class="ghost" data-action="openvpn-diagnostics">Domain Diagnostics</button><button class="ghost" data-action="openvpn-repair">Normalize IPv4 runtime</button><button class="primary" data-action="settings-operator-save">Save VPN defaults</button></div></div>'
    ].join('');
  }else if(tab==='delivery'){
    body=[
      '<section class="settings-section-head"><div><div class="eyebrow">CLIENT DELIVERY</div><h2>Delivery / NPV Tunnel Defaults</h2><p>QR، Profile remarks و خروجی مستقیم SSH برای NPV Tunnel / NapsternetV.</p></div></section>',
      '<div class="settings-card-v2"><div class="settings-card-title"><div><b>Share Center</b><span>Xray QR, WireGuard QR and SSH → NPV quick import</span></div></div>',
      '<div class="settings-form-grid"><label>Profile prefix<input id="opProfilePrefix" value="'+htmlEsc(delivery.profile_prefix||'Makia')+'" maxlength="40"></label>',
      '<label>Show QR in panel<select id="opShowQr"><option value="1" '+(delivery.show_qr!==false?'selected':'')+'>Enabled</option><option value="0" '+(delivery.show_qr===false?'selected':'')+'>Hidden</option></select></label>',
      '<label>NPV SSH quick import<select id="opNpvEnabled"><option value="1" '+(delivery.npv_enabled!==false?'selected':'')+'>Enabled</option><option value="0" '+(delivery.npv_enabled===false?'selected':'')+'>Disabled</option></select></label>',
      '<label>NPV DNS tunnel mode<select id="opNpvDns"><option value="UDP" '+(delivery.npv_dns_mode==='UDP'?'selected':'')+'>UDP</option><option value="TCP" '+(delivery.npv_dns_mode==='TCP'?'selected':'')+'>TCP</option></select></label>',
      '<label>UDPGW Port<input id="opNpvUdpPort" type="number" min="1" max="65535" value="'+Number(delivery.npv_udpgw_port||7300)+'"></label>',
      '<label>Transparent DNS<select id="opNpvTransparent"><option value="0" '+(!delivery.npv_transparent_dns?'selected':'')+'>Off</option><option value="1" '+(delivery.npv_transparent_dns?'selected':'')+'>On</option></select></label></div>',
      '<div class="wizard-note"><b>NPV import contract</b><span>Makia لینک npvt-ssh و QR می‌سازد. فایل proprietary رمزگذاری‌شده .npv4 بدون فرمت رسمی تولید یا جعل نمی‌شود. Transparent DNS فقط با UDPGW واقعی فعال شود.</span></div>',
      '<div class="settings-actions"><button class="primary" data-action="settings-operator-save">Save delivery settings</button></div></div>'
    ].join('');
  }else if(tab==='subscription'){
    body=[
      '<section class="settings-section-head"><div><div class="eyebrow">XRAY DELIVERY</div><h2>Subscription Settings</h2><p>دسترسی Subscription و Client Page عمومیِ مبتنی بر Secret ID را کنترل کن.</p></div></section>',
      '<div class="settings-card-v2"><div class="settings-form-grid">',
      '<label>Subscription endpoint<select id="opSubscriptionEnabled"><option value="1" '+(sub.enabled!==false?'selected':'')+'>Enabled</option><option value="0" '+(sub.enabled===false?'selected':'')+'>Disabled</option></select></label>',
      '<label>Public client page<select id="opClientPageEnabled"><option value="1" '+(sub.client_page_enabled!==false?'selected':'')+'>Enabled</option><option value="0" '+(sub.client_page_enabled===false?'selected':'')+'>Disabled</option></select></label>',
      '<label>Default subscription format<select id="opSubscriptionFormat"><option value="base64" '+(sub.default_format!=='raw'?'selected':'')+'>Base64</option><option value="raw" '+(sub.default_format==='raw'?'selected':'')+'>Raw URI</option></select></label></div>',
      '<div class="wizard-note"><b>Credential surface</b><span>Subscription ID مانند Secret URL در نظر گرفته می‌شود. Share Center مدیریتی همچنان Authentication می‌خواهد؛ Client Page فقط داده همان Client را نمایش می‌دهد.</span></div>',
      '<div class="settings-actions"><button class="primary" data-action="settings-operator-save">Save subscription settings</button></div></div>'
    ].join('');
  }else if(tab==='security'){
    body=[
      '<section class="settings-section-head"><div><div class="eyebrow">ADMIN SECURITY</div><h2>Admin Security</h2><p>'+(two.restricted?'این بخش هویتی فقط برای مدیر محلی قابل تغییر است.':'Session lifetime، رمز عبور مدیر و TOTP واقعی.')+'</p></div></section>',
      '<div class="settings-card-v2"><div class="settings-card-title"><div><b>Admin session</b><span>Signed cookie lifetime</span></div></div><div class="settings-form-grid two"><label>Session max age (minutes)<input id="opSessionMinutes" type="number" min="5" max="43200" value="'+Number(operator.session_max_age_minutes||720)+'"></label><div class="settings-inline-note"><b>'+Math.round(Number(operator.session_max_age_minutes||720)/60*10)/10+' hours</b><span>روی login بعدی اعمال می‌شود.</span></div></div><div class="settings-actions"><button class="primary" data-action="settings-operator-save">Save session policy</button></div></div>',
      '<div class="settings-card-v2"><div class="settings-card-title"><div><b>Administrator password</b><span>Minimum 12 characters</span></div></div><div class="settings-form-grid two"><label>Current password<input id="oldP" type="password"></label><label>New password<input id="newP" type="password" minlength="12"></label></div><div class="settings-actions"><button class="primary" data-action="settings-password-change">Change password</button></div></div>',
      '<div class="settings-card-v2"><div class="settings-card-title"><div><b>Two-Factor Authentication</b><span>TOTP authenticator</span></div><span class="status-chip '+(two.enabled?'ok':'warn')+'">'+(two.enabled?'Enabled':'Optional')+'</span></div><div class="security-feature-row"><div><b>'+(two.enabled?'2FA is active':'Add a second factor')+'</b><span>'+(two.enabled?'Password + 6-digit TOTP is required at login.':'Google Authenticator, Microsoft Authenticator or compatible TOTP app.')+'</span></div><button class="'+(two.enabled?'danger':'primary')+'" data-action="'+(two.enabled?'settings-2fa-disable':'settings-2fa-setup')+'">'+(two.enabled?'Disable 2FA':'Enable 2FA')+'</button></div></div>'
    ].join('');
  }else if(tab==='api'){
    body=[
      '<section class="settings-section-head"><div><div class="eyebrow">AUTOMATION API</div><h2>Scoped API Tokens</h2><p>Tokenهای Read-only با Scope مشخص؛ مقدار کامل فقط هنگام ساخت نمایش داده می‌شود.</p></div><button class="primary" data-action="settings-api-new">＋ New Token</button></section>',
      '<div class="settings-card-v2"><div class="wizard-note"><b>HTTPS only</b><span>برای API مدیریتی از HTTPS استفاده کن. در دیتابیس فقط Hash Token ذخیره می‌شود.</span></div><div class="table">'+(tokens.length?tokens.map(t=>'<div class="row"><div><b>'+htmlEsc(t.name)+'</b><div class="muted">…'+htmlEsc(t.token_last4)+'</div></div><div class="muted">'+htmlEsc(t.scopes||'-')+'</div><div><span class="status-chip '+(t.active?'ok':'bad')+'">'+(t.active?'Active':'Revoked')+'</span></div><div class="toolbar">'+(t.active?'<button class="danger" data-action="settings-api-revoke" data-id="'+Number(t.id)+'">Revoke</button>':'')+'</div></div>').join(''):'<div class="empty">API Tokenای ساخته نشده است.</div>')+'</div></div>'
    ].join('');
  }else{
    const recent=backupRows.slice(0,5);
    body=[
      '<section class="settings-section-head"><div><div class="eyebrow">RECOVERY</div><h2>Backup / Migration</h2><p>Local Snapshot برای rollback؛ Portable Migration برای انتقال credentialها و keys به VPS جدید.</p></div><div class="toolbar"><button class="ghost" data-action="portable-backup">Portable Migration</button><button class="primary" data-action="backup-create">＋ Local Backup</button></div></section>',
      '<div class="settings-card-v2"><div class="domain-health-v2"><div><span>Backups</span><b>'+backupRows.length+'</b></div><div><span>Latest</span><b>'+(recent[0]?htmlEsc(recent[0].name):'None')+'</b></div><div><span>Storage</span><b>'+fmtBytes(backupRows.reduce((n,x)=>n+Number(x.size||0),0))+'</b></div><div><span>Restore</span><b class="warn-text">CLI / validated workflow only</b></div></div>',
      '<div class="settings-shortcuts"><button data-action="nav" data-view="backups"><b>Open Backup Center</b><span>View all real archives</span></button><button data-action="self-test"><b>Run Self-Test</b><span>Validate crypto, DB and services</span></button></div>',
      (recent.length?'<div class="recovery-list">'+recent.map(x=>'<div><b>'+htmlEsc(x.name)+'</b><span>'+fmtBytes(x.size||0)+'</span></div>').join('')+'</div>':'<div class="empty">هنوز Backup ساخته نشده است.</div>')+'</div>'
    ].join('');
  }

  content.innerHTML='<div class="settings-shell-v2"><aside class="settings-nav-v2"><div class="settings-nav-title"><b>Settings V2</b><span>REAL BACKEND ONLY</span></div>'+nav+'</aside><div class="settings-content-v2">'+body+'</div></div>';
}

async function saveGeneral(){try{const r=await api('/api/settings/general',{method:'PUT',body:JSON.stringify({language:generalLang.value,panel_domain:generalDomain.value.trim(),theme:generalTheme.value,density:generalDensity.value})});window.PANEL_DOMAIN=r.panel_domain||'';toast('Settings saved');if(r.language!==window.MAKIA_LANG||r.theme!==window.MAKIA_THEME||r.density!==window.MAKIA_DENSITY){setTimeout(()=>location.reload(),450);return}await settings()}catch(e){alert(e.message)}}
function readSettingValue(id,fallback){
  const el=document.getElementById(id);if(!el)return fallback;
  if(el.type==='number')return Number(el.value);
  return el.value;
}
function operatorPayloadFromUi(){
  const o=window.__operatorSettings||{},d=o.delivery||{},x=o.defaults||{},sub=o.subscription||{};
  return {
    session_max_age_minutes:readSettingValue('opSessionMinutes',Number(o.session_max_age_minutes||720)),
    profile_prefix:readSettingValue('opProfilePrefix',d.profile_prefix||'Makia'),
    npv_enabled:readSettingValue('opNpvEnabled',d.npv_enabled!==false?'1':'0')==='1',
    npv_dns_mode:readSettingValue('opNpvDns',d.npv_dns_mode||'UDP'),
    npv_udpgw_port:readSettingValue('opNpvUdpPort',Number(d.npv_udpgw_port||7300)),
    npv_transparent_dns:readSettingValue('opNpvTransparent',d.npv_transparent_dns?'1':'0')==='1',
    show_qr:readSettingValue('opShowQr',d.show_qr!==false?'1':'0')==='1',
    ssh_password_mode:readSettingValue('opSshPassword',x.ssh_password_mode||'pin6'),
    ssh_expire_days:readSettingValue('opSshDays',Number(x.ssh_expire_days??30)),
    ssh_sessions:readSettingValue('opSshSessions',Number(x.ssh_sessions||1)),
    ssh_devices:readSettingValue('opSshDevices',Number(x.ssh_devices||1)),
    xray_protocol:readSettingValue('opXrayProtocol',x.xray_protocol||'vless'),
    xray_port:readSettingValue('opXrayPort',Number(x.xray_port||2087)),
    xray_transport:readSettingValue('opXrayTransport',x.xray_transport||'xhttp'),
    xray_security:readSettingValue('opXraySecurity',x.xray_security||'reality'),
    xray_path:readSettingValue('opXrayPath',x.xray_path||'/makia'),
    xray_sni:readSettingValue('opXraySni',x.xray_sni||'www.microsoft.com'),
    xray_reality_target:readSettingValue('opXrayTarget',x.xray_reality_target||'www.microsoft.com:443'),
    xray_quota_gb:readSettingValue('opXrayQuota',Number(x.xray_quota_gb??50)),
    xray_expire_days:readSettingValue('opXrayDays',Number(x.xray_expire_days??30)),
    xray_ip_limit:readSettingValue('opXrayIp',Number(x.xray_ip_limit||1)),
    xray_reset_days:readSettingValue('opXrayReset',Number(x.xray_reset_days??30)),
    wireguard_dns:readSettingValue('opWgDns',x.wireguard_dns||'1.1.1.1'),
    wireguard_port:readSettingValue('opWgPort',Number(x.wireguard_port||443)),
    wireguard_mtu:readSettingValue('opWgMtu',Number(x.wireguard_mtu||1280)),
    wireguard_keepalive:readSettingValue('opWgKeepalive',Number(x.wireguard_keepalive??15)),
    wireguard_allowed_ips:readSettingValue('opWgAllowedIps',x.wireguard_allowed_ips||'0.0.0.0/0'),
    wireguard_cidr:readSettingValue('opWgCidr',x.wireguard_cidr||'10.66.66.1/24'),
    openvpn_port:readSettingValue('opOvpnPort',Number(x.openvpn_port||1194)),
    openvpn_proto:readSettingValue('opOvpnProto',x.openvpn_proto||'udp'),
    subscription_enabled:readSettingValue('opSubscriptionEnabled',sub.enabled!==false?'1':'0')==='1',
    subscription_client_page_enabled:readSettingValue('opClientPageEnabled',sub.client_page_enabled!==false?'1':'0')==='1',
    subscription_default_format:readSettingValue('opSubscriptionFormat',sub.default_format||'base64')
  };
}
async function saveOperatorSettings(){
  try{window.__operatorSettings=await api('/api/settings/operator',{method:'PUT',body:JSON.stringify(operatorPayloadFromUi())});toast('Operational settings saved');await currentView()}catch(e){alert(e.message)}
}
async function applySettingsDomain(){
  const domain=(document.getElementById('domainName')?.value||'').trim();if(!domain){alert('دامنه را وارد کنید.');return}
  if(!confirm('Nginx server_name روی '+domain+' تنظیم شود؟'))return;
  try{await api('/api/settings/domain/apply',{method:'POST',body:JSON.stringify({domain})});window.PANEL_DOMAIN=domain;toast('Domain applied to Nginx');await currentView()}catch(e){alert(e.message)}
}
async function issueSettingsCertificate(){
  const domain=(document.getElementById('domainName')?.value||'').trim(),email=(document.getElementById('tlsEmail')?.value||'').trim();
  if(!domain||!email){alert('دامنه و ایمیل لازم است.');return}
  if(!confirm('برای '+domain+' گواهی Let\'s Encrypt صادر شود؟'))return;
  try{const r=await api('/api/settings/domain/certificate',{method:'POST',body:JSON.stringify({domain,email})});toast(r.certificate?'HTTPS enabled':'Certificate command completed');setTimeout(()=>location.href='https://'+domain,900)}catch(e){alert(e.message)}
}
async function applyDomain(){const domain=generalDomain.value.trim();if(!domain){alert('دامنه را وارد کنید.');return}if(!confirm('Nginx server_name روی '+domain+' تنظیم شود؟'))return;try{await api('/api/settings/domain/apply',{method:'POST',body:JSON.stringify({domain})});window.PANEL_DOMAIN=domain;toast('Domain applied to Nginx');await settings()}catch(e){alert(e.message)}}
async function issueCertificate(){const domain=generalDomain.value.trim(),email=tlsEmail.value.trim();if(!domain||!email){alert('دامنه و ایمیل لازم است.');return}if(!confirm('برای '+domain+' گواهی Let\'s Encrypt صادر شود؟'))return;try{const r=await api('/api/settings/domain/certificate',{method:'POST',body:JSON.stringify({domain,email})});toast(r.certificate?'HTTPS enabled':'Certificate command completed');setTimeout(()=>location.href='https://'+domain,1000)}catch(e){alert(e.message)}}
function createApiToken(){modalRoot.innerHTML=`<div class="modal-backdrop" onclick="if(event.target===this)closeModal()"><div class="modal"><div class="modal-head"><div><div class="eyebrow">SCOPED AUTOMATION ACCESS</div><h3>New API Token</h3></div><button class="close-btn" onclick="closeModal()">×</button></div><div class="form-grid two"><label>Token name<input id="apiTokenName" value="automation" maxlength="80"></label></div><div class="scope-grid"><label><input type="checkbox" class="api-scope" value="status:read" checked> <span><b>Status</b><small>Server health and metrics</small></span></label><label><input type="checkbox" class="api-scope" value="accounts:read"> <span><b>Accounts</b><small>SSH account read access</small></span></label><label><input type="checkbox" class="api-scope" value="protocols:read"> <span><b>Protocol Clients</b><small>Quota, expiry and protocol status</small></span></label><label><input type="checkbox" class="api-scope" value="nodes:read"> <span><b>Nodes</b><small>Multi-node status read access</small></span></label></div><div class="notice">حداقل یک Scope لازم است. Token را فقط روی HTTPS استفاده کن؛ مقدار کامل فقط یک‌بار نمایش داده می‌شود.</div><div class="toolbar"><button class="primary" onclick="submitApiToken()">Create Token</button><button class="ghost" onclick="closeModal()">Cancel</button></div></div></div>`}
async function submitApiToken(){
  const name=document.getElementById('apiTokenName').value.trim(),scopes=[...document.querySelectorAll('.api-scope:checked')].map(x=>x.value);
  if(!name){alert('نام Token را وارد کنید.');return}if(!scopes.length){alert('حداقل یک Scope را انتخاب کنید.');return}
  try{
    const r=await api('/api/admin/tokens',{method:'POST',body:JSON.stringify({name,scopes})});
    modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">API ACCESS</div><h3>API Token Created</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="notice">این Token فقط همین یک‌بار نمایش داده می‌شود.</div><textarea id="newApiTokenValue" class="config-output small" readonly></textarea><div class="chips">'+r.scopes.map(x=>'<span class="status-chip">'+htmlEsc(x)+'</span>').join('')+'</div><div class="wizard-footer"><button class="primary" data-action="copy-target" data-target="newApiTokenValue">Copy token</button><button class="ghost" data-action="modal-close-refresh" data-view="settings">Done</button></div></div></div>';
    document.getElementById('newApiTokenValue').value=r.token;
  }catch(e){alert(e.message)}
}
async function revokeApiToken(id){if(!confirm('این API Token لغو شود؟'))return;try{await api('/api/admin/tokens/'+id+'/revoke',{method:'POST'});await settings()}catch(e){alert(e.message)}}
async function setup2FA(){try{const r=await api('/api/admin/2fa/setup',{method:'POST'});modalRoot.innerHTML=`<div class="modal-backdrop"><div class="modal"><div class="modal-head"><h3>Enable 2FA</h3><button class="close-btn" onclick="closeModal()">×</button></div><div style="text-align:center"><img src="${r.qr}" alt="2FA QR" style="width:220px;max-width:80%;background:white;padding:10px;border-radius:16px"></div><div class="notice">QR را با Google Authenticator / Microsoft Authenticator / 1Password اسکن کنید. اگر اسکن نشد، Secret را دستی وارد کنید.</div><div class="quick-card"><b style="word-break:break-all">${r.secret}</b><span>Manual secret</span></div><div class="form-grid two" style="margin-top:12px"><label>کد ۶ رقمی<input id="twoCode" inputmode="numeric" maxlength="6"></label></div><div class="toolbar" style="margin-top:14px"><button class="primary" onclick="enable2FA()">Verify & Enable</button><button class="ghost" onclick="copyText('${r.secret}')">Copy secret</button></div></div></div>`}catch(e){alert(e.message)}}
async function enable2FA(){try{await api('/api/admin/2fa/enable',{method:'POST',body:JSON.stringify({code:twoCode.value})});closeModal();alert('2FA فعال شد.');await settings()}catch(e){alert(e.message)}}
async function disable2FA(){const password=prompt('رمز فعلی مدیر:');if(password===null)return;const code=prompt('کد ۶ رقمی Authenticator:');if(code===null)return;try{await api('/api/admin/2fa/disable',{method:'POST',body:JSON.stringify({password,code})});alert('2FA غیرفعال شد.');await settings()}catch(e){alert(e.message)}}
async function changePass(){try{await api('/api/admin/password',{method:'POST',body:JSON.stringify({current_password:oldP.value,new_password:newP.value})});alert('رمز مدیر تغییر کرد.')}catch(e){alert(e.message)}}
function toast(msg){let t=document.getElementById('makiaToast');if(!t){t=document.createElement('div');t.id='makiaToast';t.className='toast';document.body.appendChild(t)}t.textContent=msg;t.classList.add('show');clearTimeout(window.__toastTimer);window.__toastTimer=setTimeout(()=>t.classList.remove('show'),2200)}
const commandItems=[['Overview','dashboard'],['Access Center','access'],['Live Sessions','sessions'],['Protocols','protocols'],['Client Guides','guides'],['Nodes','nodes'],['Services','services'],['Security','security'],['Backups','backups'],['Audit Logs','audit'],['Update Center','updates'],['Settings / 2FA / API Tokens','settings'],['License & Support','license']];

function openCommandPalette(){
  modalRoot.innerHTML='<div class="modal-backdrop command-backdrop"><div class="command-modal"><input id="commandSearch" autofocus placeholder="Search Makia…  (Ctrl+K)"><div id="commandList"></div></div></div>';
  const input=document.getElementById('commandSearch');
  input?.addEventListener('input',()=>renderCommands(input.value));
  setTimeout(()=>{input?.focus();renderCommands('')},0);
}
function renderCommands(q=''){
  const root=document.getElementById('commandList');if(!root)return;
  const s=q.toLowerCase();
  root.innerHTML=commandItems.filter(x=>x[0].toLowerCase().includes(s)).map(x=>'<button data-action="nav" data-view="'+htmlEsc(x[1])+'"><span>'+htmlEsc(x[0])+'</span><kbd>↵</kbd></button>').join('');
}

async function selectWizardProtocol(kind){
  if(!provisionState)return;
  await ensureLicenseState();
  const feature={xray:'xray',wireguard:'wireguard',openvpn:'openvpn'}[kind];
  if(feature&&!hasLicenseFeature(feature)){closeModal();switchView('license');return}
  if(!wizardProtocolReady(kind)){await openProtocolSetup(kind);return}
  provisionState.protocol=kind;provisionState.step=2;
  if(kind==='ssh'){
    const d=window.__operatorSettings?.defaults||{},mode=d.ssh_password_mode||'pin6';
    const sec=await api('/api/accounts/generate-secret?mode='+encodeURIComponent(mode)).catch(()=>({secret:''}));
    provisionState.password=sec.secret||'';
    const days=Number(d.ssh_expire_days??30);provisionState.expireDate=days?dateAfterDays(days):'';
  }
  renderProvisionWizard();
}

async function handleMakiaAction(btn){
  const action=btn.dataset.action;if(!action)return;
  if(action==='nav'){closeModal();switchView(btn.dataset.view);return}
  if(action==='wizard-open'){await openProvisionWizard(btn.dataset.kind||null);return}
  if(action==='wizard-protocol'){await selectWizardProtocol(btn.dataset.kind);return}
  if(action==='wizard-next'){await wizardNext();return}
  if(action==='wizard-prev'){wizardPrev();return}
  if(action==='wizard-create'){await createProvisionedAccess();return}
  if(action==='wizard-secret'){
    const mode=btn.dataset.mode||'pin6',r=await api('/api/accounts/generate-secret?mode='+encodeURIComponent(mode));
    if(provisionState)provisionState.password=r.secret||'';const el=document.getElementById('wizPassword');if(el)el.value=r.secret||'';return;
  }
  if(action==='wizard-expiry'){
    const days=Number(btn.dataset.days||0),value=days?dateAfterDays(days):'';
    if(provisionState)provisionState.expireDate=value;const el=document.getElementById('wizExpireDate');if(el)el.value=value;return;
  }
  if(action==='wizard-package-pin'){
    const r=await api('/api/accounts/generate-secret?mode=pin6');if(provisionState)provisionState.packagePassword=r.secret||'';
    const el=document.getElementById('wizPackagePassword');if(el)el.value=r.secret||'';return;
  }
  if(action==='protected-export'){await openProtectedExport(btn.dataset.kind,dataDec(btn.dataset.key),dataDec(btn.dataset.name));return}
  if(action==='protected-download-confirm'){
    const password=document.getElementById('protectedPassword')?.value||'';
    await performProtectedDownload(btn.dataset.kind,dataDec(btn.dataset.key),dataDec(btn.dataset.name),password);return;
  }
  if(action==='protected-download-now'){
    await performProtectedDownload(btn.dataset.kind,dataDec(btn.dataset.key),dataDec(btn.dataset.name),dataDec(btn.dataset.password));return;
  }
  if(action==='native-export'){await downloadAccessNative(btn.dataset.kind,dataDec(btn.dataset.key));return}
  if(action==='access-share'){await openAccessShare(btn.dataset.kind,dataDec(btn.dataset.key),dataDec(btn.dataset.name));return}
  if(action==='qr-download'){await downloadAccessQr(btn.dataset.kind,dataDec(btn.dataset.key),dataDec(btn.dataset.name));return}
  if(action==='subscription-qr-download'){await downloadSubscriptionQr(dataDec(btn.dataset.key),dataDec(btn.dataset.name));return}
  if(action==='manage-access'){manageAccess(dataDec(btn.dataset.id));return}
  if(action==='revoke-access'){await revokeAccess(btn.dataset.kind,dataDec(btn.dataset.key),dataDec(btn.dataset.name));return}
  if(action==='wg-reissue'){await reissueWireGuard(dataDec(btn.dataset.key));return}
  if(action==='protocol-setup'){await openProtocolSetup(btn.dataset.kind);return}
  if(action==='protocol-install'){await performProtocolInstall(btn.dataset.kind);return}
  if(action==='protocol-bootstrap'){await performProtocolBootstrap(btn.dataset.kind,btn.dataset.installed==='1');return}
  if(action==='protocol-refresh'){await currentView();return}
  if(action==='connectivity-lab'){openConnectivityLab();return}
  if(action==='connectivity-run'){await runConnectivityLab();return}
  if(action==='connectivity-edit'){openConnectivityLab(dataDec(btn.dataset.endpoint));return}
  if(action==='wireguard-diagnostics'){await openWireGuardDiagnostics();return}
  if(action==='wireguard-repair'){await repairWireGuardRuntime();return}
  if(action==='openvpn-diagnostics'){await openOpenVPNDiagnostics();return}
  if(action==='openvpn-repair'){await repairOpenVPNRuntime();return}
  if(action==='xray-diagnostics'){await openXrayDiagnostics();return}
  if(action==='xray-repair'){await repairXrayRuntime();return}
  if(action==='xray-advanced'){await openXrayAdvanced();return}
  if(action==='xray-tunnel'){createXrayTunnel();return}
  if(action==='client-guide'){openClientGuide(btn.dataset.kind||'xray');return}
  if(action==='client-guide-copy'){copyClientGuide(btn.dataset.kind||'xray');return}
  if(action==='self-test'){await runSelfTest();return}
  if(action==='success-done'){closeModal();switchView('access');return}
  if(action==='modal-close'){closeModal();return}
  if(action==='modal-close-refresh'){const v=btn.dataset.view;closeModal();if(v&&views[v])await views[v]();return}
  if(action==='copy-target'){const el=document.getElementById(btn.dataset.target);if(el)copyText('value' in el?el.value:el.textContent||'');return}
  if(action==='copy-last-credential'){
    const p=window.__lastCredential||{};copyText('Makia SSH Account\nServer: '+(p.host||'')+'\nUsername: '+(p.username||'')+'\nPassword: '+(p.password||'')+'\nExpire: '+(p.expire_date||'No expiry'));return;
  }
  if(action==='download-text-target'){
    const el=document.getElementById(btn.dataset.target);if(el)downloadText(window.__lastConfigFilename||'config.txt',el.value||el.textContent||'');return;
  }
  if(action==='account-edit'){const u=dataDec(btn.dataset.user),row=accountCache.find(x=>x.username===u);if(row)editAccount(row);return}
  if(action==='account-save'){await saveAccount(dataDec(btn.dataset.user));return}
  if(action==='edit-secret'){const r=await api('/api/accounts/generate-secret?mode='+encodeURIComponent(btn.dataset.mode||'pin6'));const el=document.getElementById('ePass');if(el)el.value=r.secret||'';return}
  if(action==='edit-expiry'){const days=Number(btn.dataset.days||0),el=document.getElementById('eExpire');if(el)el.value=days?dateAfterDays(days):'';return}
  if(action==='account-disconnect'){await accountAction(dataDec(btn.dataset.user),'disconnect');return}
  if(action==='account-delete'){await accountAction(dataDec(btn.dataset.user),'delete');return}
  if(action==='session-disconnect'){await disconnectSession(dataDec(btn.dataset.tty),dataDec(btn.dataset.user));return}
  if(action==='node-create'){await createNode();return}
  if(action==='node-revoke'){await revokeNode(Number(btn.dataset.id));return}
  if(action==='service-action'){await svc(dataDec(btn.dataset.service),btn.dataset.serviceAction);return}
  if(action==='backup-create'){await makeBackup();return}
  if(action==='portable-backup'){openPortableBackup();return}
  if(action==='portable-backup-download'){await downloadPortableBackup();return}
  if(action==='wg-compat-preset'){const values={opWgPort:443,opWgMtu:1280,opWgKeepalive:15,opWgAllowedIps:'0.0.0.0/0',opWgDns:'1.1.1.1'};for(const [id,v] of Object.entries(values)){const el=document.getElementById(id);if(el)el.value=v}toast('Compatibility preset applied; Save to persist');return}
  if(action==='license-sync'){await syncLicenseNow();return}
  if(action==='support-grant-create'){await createRemoteSupportGrant();return}
  if(action==='support-grant-revoke'){await revokeRemoteSupportGrant(Number(btn.dataset.id));return}
  if(action==='license-activate'){await activateLicense();return}
  if(action==='license-remove'){await removeLicense();return}
  if(action==='support-submit'){await submitSupportRequest();return}
  if(action==='support-telegram'){window.open(btn.dataset.url,'_blank','noopener');return}
  if(action==='settings-tab'){window.__settingsTab=btn.dataset.tab||'general';await currentView();return}
  if(action==='settings-general-save'){await saveGeneral();return}
  if(action==='settings-domain-apply'){await applySettingsDomain();return}
  if(action==='settings-cert-issue'){await issueSettingsCertificate();return}
  if(action==='settings-operator-save'){await saveOperatorSettings();return}
  if(action==='settings-password-change'){await changePass();return}
  if(action==='settings-2fa-setup'){await setup2FA();return}
  if(action==='settings-2fa-disable'){await disable2FA();return}
  if(action==='settings-api-new'){createApiToken();return}
  if(action==='settings-api-revoke'){await revokeApiToken(Number(btn.dataset.id));return}
  if(action==='refresh'){await currentView();return}
}

document.addEventListener('click',e=>{
  const shell=e.target.closest('[data-shell-action]');
  if(shell){
    const a=shell.dataset.shellAction;
    if(a==='command')openCommandPalette();
    else if(a==='refresh')currentView();
    else if(a==='create-access')openProvisionWizard();
    return;
  }
  const btn=e.target.closest('[data-action]');
  if(btn){e.preventDefault();Promise.resolve(handleMakiaAction(btn)).catch(err=>alert(err?.message||String(err)))}
});
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openCommandPalette()}if(e.key==='Escape')closeModal()});

function applyLanguageShell(){
  const fa={dashboard:'نمای کلی',access:'مرکز دسترسی',accounts:'کاربران SSH',sessions:'اتصال‌های زنده',services:'سرویس‌ها',protocols:'پروتکل‌ها',guides:'راهنمای اتصال',nodes:'نودها',security:'امنیت',backups:'بکاپ‌ها',audit:'گزارش رویدادها',updates:'بروزرسانی',settings:'تنظیمات',license:'مجوز و پشتیبانی'};
  const en={dashboard:'Overview',access:'Access Center',accounts:'SSH Accounts',sessions:'Live Sessions',services:'Services',protocols:'Protocols',guides:'Client Guides',nodes:'Nodes',security:'Security',backups:'Backups',audit:'Audit Logs',updates:'Update Center',settings:'Settings',license:'License & Support'};
  const dict=window.MAKIA_LANG==='en'?en:fa;document.documentElement.lang=window.MAKIA_LANG==='en'?'en':'fa';document.documentElement.dir=window.MAKIA_LANG==='en'?'ltr':'rtl';
  document.querySelectorAll('nav button[data-view]').forEach(b=>{const label=dict[b.dataset.view];const t=b.querySelector('b');if(label&&t)t.textContent=label});
}
const views={dashboard,access,accounts,sessions,services,protocols,guides,nodes,security,backups,audit:auditView,updates,settings,license:licenseSupport};
window.__viewRenderToken=0;
function currentView(){const token=++window.__viewRenderToken;return(views[activeView]||dashboard)(token)}
function switchView(v){activeView=v;setPageContext(v==='dashboard'?'OPERATIONS COCKPIT':v==='access'?'IDENTITY & DELIVERY':v==='guides'?'DELIVERY EDUCATION':'MAKIA CONTROL CENTER');document.querySelectorAll('nav button[data-view]').forEach(x=>x.classList.toggle('active',x.dataset.view===v));return currentView()}
document.querySelectorAll('nav button[data-view]').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.view)));
applyLanguageShell();ensureSessionContext().catch(()=>{});ensureLicenseState().catch(()=>{});switchView('dashboard');
if('serviceWorker' in navigator){window.addEventListener('load',()=>navigator.serviceWorker.register('/static/sw.js').catch(()=>{}));}
