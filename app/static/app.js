// Historical compatibility: the stored theme key "glass" remains supported; Glass Aurora is rendered by the current shell.
// Legacy CI marker retained intentionally: glass-status-hero legacy.
const content=document.querySelector('#content'),title=document.querySelector('#pageTitle'),modalRoot=document.querySelector('#modalRoot');let activeView='dashboard';
const pageContext=document.querySelector('#pageContext');
function htmlEsc(v){return String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]))}
function dataEnc(v){return encodeURIComponent(String(v??''))}
function dataDec(v){try{return decodeURIComponent(String(v??''))}catch{return String(v??'')}}
function isFa(){return String(window.MAKIA_LANG||'fa').toLowerCase()!=='en'}
function tr(fa,en){return isFa()?fa:en}
const MAKIA_UI_TEXT={
  'Dashboard':'داشبورد','Clients':'کاربران','Client':'کاربر','Create access':'ساخت دسترسی',
  'Create Access':'ساخت دسترسی','Access Management':'مدیریت دسترسی','ACCESS MANAGEMENT':'مدیریت دسترسی',
  'Main':'اصلی','Protocols':'پروتکل‌ها','Protocol management':'مدیریت پروتکل‌ها','Inbounds':'Inboundها',
  'Infrastructure':'زیرساخت','Server & Network':'سرور و شبکه','System':'سیستم','Maintenance':'نگهداری',
  'Services':'سرویس‌ها','Network / Ports':'شبکه و پورت‌ها','Live Sessions':'اتصال‌های زنده','Nodes':'نودها',
  'Logs':'لاگ‌ها','Backups':'بکاپ‌ها','Backup':'بکاپ','Update':'بروزرسانی','Settings':'تنظیمات','Support':'پشتیبانی',
  'Server online':'سرور آنلاین','ONLINE':'آنلاین','Administrator':'مدیر','Refresh':'بروزرسانی',
  'Search panel...':'جستجو در پنل...','Open menu':'باز کردن منو','Close menu':'بستن منو','Sign out':'خروج',
  'Active':'فعال','ACTIVE':'فعال','Disabled':'غیرفعال','DISABLED':'غیرفعال','Expired':'منقضی',
  'Running':'در حال اجرا','Attention':'نیازمند بررسی','Status':'وضعیت','Endpoint':'آدرس اتصال',
  'Usage':'مصرف','Used':'مصرف','Quota':'حجم کل','Unlimited':'نامحدود','Expiry':'انقضا','Expires':'انقضا',
  'IP limit':'محدودیت IP','Device / IP limit':'محدودیت دستگاه / IP',
  'Management':'مدیریت','Delivery':'تحویل','Close':'بستن','Done':'تمام','Cancel':'انصراف','Save':'ذخیره',
  'Copy':'کپی','Copied':'کپی شد','Copy link':'کپی لینک','Copy config':'کپی تنظیمات',
  'Download':'دانلود','Download raw':'دانلود فایل خام','Native file':'فایل اصلی','Native config':'تنظیمات اصلی',
  'Protected ZIP':'بسته رمزدار','Connection guide':'راهنمای اتصال','Client portal link':'لینک اختصاصی کاربر',
  'QR / Share':'QR / اشتراک','Profile file':'فایل پروفایل','Config':'تنظیمات','Self-Test':'تست سلامت',
  'Health check':'بررسی سلامت','Total clients':'کل کاربران','Needs attention':'نیازمند توجه',
  'Live connections':'اتصال زنده','All access':'همه دسترسی‌ها','Protocol':'پروتکل',
  'User':'کاربر','Search':'جستجو','Search Makia…  (Ctrl+K)':'جستجو در Makia…  (Ctrl+K)',
  'System history':'تاریخچه سیستم','Clients by protocol':'کاربران بر اساس پروتکل',
  'Memory':'حافظه','Disk':'دیسک','Uptime':'زمان فعالیت','Traffic recorded':'ترافیک ثبت‌شده',
  'Panel endpoint':'آدرس پنل','Server ready':'سرور آماده','Check required':'نیازمند بررسی',
  'Install':'نصب','Repair & Restart':'تعمیر و راه‌اندازی مجدد','Validate':'اعتبارسنجی',
  'Validate & Apply':'اعتبارسنجی و اعمال','Validate & Create':'اعتبارسنجی و ساخت',
  'New Inbound':'Inbound جدید','ADD XRAY CLIENT':'افزودن کاربر Xray','Create client':'ساخت کاربر',
  'ACCESS PROFILE':'پروفایل دسترسی','CLIENT ACCESS':'دسترسی کاربر','CLIENT SELF-SERVICE LINK':'لینک اختصاصی کاربر',
  'Private':'محرمانه','Open client page':'باز کردن صفحه کاربر','Download connection file':'دانلود فایل اتصال',
  'Download QR code':'دانلود QR','Full connection guide':'راهنمای کامل اتصال',
  'QUICK SCAN':'اسکن سریع','Connection QR':'QR اتصال','MANUAL IMPORT':'ورود دستی',
  'Connection link / configuration':'لینک / تنظیمات اتصال','QUICK GUIDE':'راهنمای سریع',
  'How do I connect?':'چطور وصل شوم؟','Server Ready':'سرور آماده'
};
Object.assign(MAKIA_UI_TEXT,{
  'Overview of system status, Xray, resources and access':'نمای کلی وضعیت سیستم، Xray، منابع و دسترسی‌ها',
  'نمای کلی وضعیت سیستم، Xray، منابع و دسترسی‌ها':'نمای کلی وضعیت سیستم، Xray، منابع و دسترسی‌ها',
  'Instant CPU usage':'مصرف لحظه‌ای پردازنده','مصرف لحظه‌ای پردازنده':'مصرف لحظه‌ای پردازنده',
  'System memory usage':'مصرف حافظه سیستم','مصرف حافظه سیستم':'مصرف حافظه سیستم',
  'Used storage space':'فضای ذخیره‌سازی استفاده‌شده','فضای ذخیره‌سازی استفاده‌شده':'فضای ذخیره‌سازی استفاده‌شده',
  'System history':'تاریخچه سیستم','CPU and Memory over the last 24 hours':'CPU و حافظه در ۲۴ ساعت گذشته',
  'Clients by protocol':'کاربران بر اساس پروتکل','Managed access':'دسترسی مدیریت‌شده',
  'All':'همه','Search user or protocol...':'جستجو نام کاربر یا پروتکل...',
  'No expiry':'بدون انقضا','Without expiry':'بدون انقضا','Certificate':'گواهی',
  'Edit settings':'ویرایش تنظیمات','Operational settings for this access':'تنظیمات عملیاتی این دسترسی',
  'Deliver to client':'تحویل به کاربر','Use these tools only when delivering the configuration.':'فقط هنگام تحویل کانفیگ به کاربر از این ابزارها استفاده کنید.',
  'Revoke access':'لغو دسترسی','Connection file':'فایل اتصال','Download OVPN file':'دانلود فایل OVPN',
  'Download config':'دانلود تنظیمات','Choose connection path':'انتخاب مسیر اتصال','Details':'مشخصات',
  'Client information':'اطلاعات کاربر','Policy':'سیاست','Limits and network':'محدودیت و شبکه',
  'Review':'تأیید','Create and deliver':'ساخت و تحویل','Fast lightweight access':'دسترسی سریع و سبک',
  'Multiple profiles and advanced management':'پروفایل‌های چندگانه و مدیریت پیشرفته',
  'Fast native tunnel':'تونل بومی سریع','PKI with configurable TCP/UDP':'PKI با TCP/UDP قابل تنظیم',
  'Choose access type':'نوع دسترسی را انتخاب کنید','Ready':'آماده','Setup required':'نیاز به راه‌اندازی',
  'Choose protocol':'انتخاب پروتکل','Username':'نام کاربری','Generate':'تولید','Advanced settings':'تنظیمات پیشرفته',
  'Internal note':'یادداشت داخلی','Customer / order name':'نام مشتری / سفارش',
  'Peer name':'نام Peer','Network settings':'تنظیمات شبکه','Client name':'نام کاربر',
  'Public VPS IPv4':'IPv4 عمومی VPS','Expiration date':'تاریخ انقضا','7 days':'۷ روز','30 days':'۳۰ روز',
  '60 days':'۶۰ روز','90 days':'۹۰ روز','Connection limit':'محدودیت اتصال','Concurrent sessions':'نشست همزمان',
  'Manual Inbound / Client creation':'ساخت دستی Inbound / Client','Network and limits':'شبکه و محدودیت',
  'Domain required':'نیاز به دامنه','Use simple preset':'استفاده از Preset ساده',
  'Secure delivery package':'بسته تحویل امن','Package PIN':'PIN بسته',
  'Client/user name is required.':'نام کاربر لازم است.','Password/PIN must be at least 4 characters.':'رمز/PIN باید حداقل ۴ کاراکتر باشد.',
  'Domain or public IP is required.':'دامنه یا IP عمومی لازم است.','Enter a valid port.':'Port معتبر وارد کنید.',
  'Creating…':'در حال ساخت…','Create and prepare':'ساخت و آماده‌سازی',
  'Profile created on server and delivery packages are ready.':'پروفایل روی سرور ساخته شده و بسته‌های تحویل آماده‌اند.',
  'Protected ZIP downloaded':'بسته رمزدار دانلود شد','Native file downloaded':'فایل اصلی دانلود شد',
  'QR downloaded':'QR دانلود شد','Subscription QR downloaded':'QR اشتراک دانلود شد',
  'SSH users':'کاربران SSH','SSH and NPV user and connection-policy management':'مدیریت کاربران SSH / NPV و سیاست‌های اتصال',
  'Advanced settings':'تنظیمات پیشرفته','Update / Refresh':'بروزرسانی',
  'Domain / SNI':'دامنه / SNI','Public IPv4':'IPv4 عمومی','Server address':'آدرس سرور',
  'Password':'رمز عبور','Package password':'رمز بسته','Traffic quota':'سقف ترافیک',
  'Traffic reset':'بازنشانی ترافیک','Never':'هرگز','Manual':'دستی','Enabled':'فعال','Inactive':'غیرفعال',
  'Online IPs':'IPهای آنلاین','Days left':'روز باقی‌مانده','No expiry':'بدون انقضا',
  'Traffic accounting':'حسابداری ترافیک','Accounting unavailable':'حسابداری در دسترس نیست',
  'Connection mode':'حالت اتصال','Language':'زبان','Theme':'پوسته','Density':'تراکم',
  'General':'عمومی','Domain & TLS':'دامنه و TLS','Security':'امنیت','API Access':'دسترسی API',
  'Session':'نشست','Sessions':'نشست‌ها','Status':'وضعیت','Version':'نسخه'
});
function localizeString(value){
  const raw=String(value??''),trim=raw.trim();if(!trim)return raw;
  if(isFa()){
    const out=MAKIA_UI_TEXT[trim];if(!out)return raw;
    return raw.replace(trim,out);
  }
  const pair=Object.entries(MAKIA_UI_TEXT).find(([,fa])=>fa===trim);
  if(!pair)return raw;
  return raw.replace(trim,pair[0]);
}
function localizeVisibleUi(root=document){
  const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
  const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);
  for(const node of nodes){
    const p=node.parentElement;if(!p||['SCRIPT','STYLE','TEXTAREA','PRE','CODE'].includes(p.tagName))continue;
    const next=localizeString(node.nodeValue);if(next!==node.nodeValue)node.nodeValue=next;
  }
  const scope=root.querySelectorAll?root:document;
  scope.querySelectorAll?.('[placeholder],[title],[aria-label]').forEach(el=>{
    for(const attr of ['placeholder','title','aria-label']){
      const v=el.getAttribute(attr);if(!v)continue;
      const next=localizeString(v);if(next!==v)el.setAttribute(attr,next);
    }
  });
}
let __localizeScheduled=false;
function scheduleUiLocalization(){
  if(__localizeScheduled)return;__localizeScheduled=true;
  queueMicrotask(()=>{__localizeScheduled=false;localizeVisibleUi(document)});
}
new MutationObserver(scheduleUiLocalization).observe(document.documentElement,{subtree:true,childList:true});

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
async function dashboard(renderToken=window.__viewRenderToken){
  title.textContent='داشبورد';setPageContext('OVERVIEW');
  content.innerHTML='<div class="loading-state"><span class="spinner"></span><b>در حال دریافت وضعیت سرور…</b></div>';
  const [d,hist,accessRows,stack]=await Promise.all([
    api('/api/overview'),api('/api/metrics/history?hours=24'),api('/api/access'),api('/api/protocols')
  ]);
  if(renderToken!==window.__viewRenderToken||activeView!=='dashboard')return;
  const m=d.metrics||{},services=d.services||[],x=stack.xray||{};
  const running=services.filter(s=>s.active).length;
  const counts={
    ssh:accessRows.filter(a=>a.kind==='ssh').length,
    xray:accessRows.filter(a=>a.kind==='xray').length,
    wireguard:accessRows.filter(a=>a.kind==='wireguard').length,
    openvpn:accessRows.filter(a=>a.kind==='openvpn').length
  };
  const maxCount=Math.max(1,...Object.values(counts));
  const traffic=Number(m.network?.sent||0)+Number(m.network?.recv||0);
  const activeClients=accessRows.filter(a=>a.status==='active').length;
  const endpoint=window.PANEL_DOMAIN||location.hostname;
  const vital=(icon,label,value,unit,detail,percent,footL,footR)=>'<article class="sx-vital"><div class="sx-vital-head"><span>'+icon+'</span><b>'+htmlEsc(label)+'</b></div><div class="sx-vital-value"><b>'+htmlEsc(value)+'</b><span>'+htmlEsc(unit||'')+'</span></div><div class="sx-vital-detail">'+htmlEsc(detail)+'</div><div class="sx-meter"><i style="width:'+pct(percent)+'%"></i></div><div class="sx-vital-foot"><span>'+htmlEsc(footL||'')+'</span><span>'+htmlEsc(footR||'')+'</span></div></article>';
  const proto=(label,count)=>'<div class="sx-protocol-row"><div><b>'+label+'</b><span>'+count+' client</span></div><em>'+Math.round((count/Math.max(1,accessRows.length))*100)+'%</em><div class="sx-protocol-bar"><i style="width:'+Math.round(count/maxCount*100)+'%"></i></div></div>';
  content.innerHTML=[
    '<div class="sx-page">',
      '<section class="sx-page-head"><div><h1>داشبورد</h1><p>نمای کلی وضعیت سیستم، Xray، منابع و دسترسی‌ها</p></div><div class="sx-head-actions"><span class="sx-state-pill '+(x.service_active?'':'warn')+'"><i></i>Xray · '+(x.service_active?'Running':'Attention')+(x.version?' · '+htmlEsc(x.version):'')+'</span><button class="primary" data-shell-action="create-access">＋ ساخت کاربر</button></div></section>',
      '<section class="sx-actionbar"><button class="primary" data-action="service-action" data-service="'+dataEnc('xray')+'" data-service-action="restart">↻ Restart Xray</button><button data-action="nav" data-view="audit">▤ Logs</button><button data-action="xray-advanced">⌘ Config</button><span class="sx-sep"></span><button data-action="nav" data-view="backups">↺ Backup</button><button data-action="nav" data-view="updates">⇧ Update</button><button data-action="self-test">Self-Test</button><button data-action="refresh">Refresh</button><span class="sx-version">Makia v'+htmlEsc(window.MAKIA_VERSION||'')+'</span></section>',
      '<section class="sx-vitals">',
        vital('◴','CPU',Number(m.cpu||0).toFixed(1),'%','مصرف لحظه‌ای پردازنده',Number(m.cpu||0),'24h metrics',''),
        vital('▥','Memory',Number(m.memory||0).toFixed(1),'%','مصرف حافظه سیستم',Number(m.memory||0),'24h metrics',''),
        vital('▤','Disk',Number(m.disk||0).toFixed(1),'%','فضای ذخیره‌سازی استفاده‌شده',Number(m.disk||0),'Host storage',''),
        vital('◉','Services',String(running),'','از '+services.length+' سرویس مدیریت‌شده',services.length?running/services.length*100:0,'Running',running+'/'+services.length),
      '</section>',
      '<section class="sx-mid-grid">',
        '<article class="sx-card"><div class="sx-card-head"><div><h3>System history</h3><p>CPU و Memory در ۲۴ ساعت گذشته</p></div><span class="status-chip">'+(hist?.length||0)+' samples</span></div>'+svgHistory(hist)+'</article>',
        '<article class="sx-card"><div class="sx-card-head"><div><h3>Clients by protocol</h3><p>'+activeClients+' فعال از '+accessRows.length+' پروفایل</p></div><button class="ghost" data-action="nav" data-view="access">Clients</button></div><div class="sx-protocol-list">'+proto('Xray / V2Ray',counts.xray)+proto('SSH / NPV',counts.ssh)+proto('WireGuard',counts.wireguard)+proto('OpenVPN',counts.openvpn)+'</div></article>',
      '</section>',
      '<section class="sx-system-strip"><div class="sx-system-cell"><span>Uptime</span><b>'+htmlEsc(fmtUp(m.uptime_seconds||0))+'</b></div><div class="sx-system-cell"><span>Traffic recorded</span><b>'+htmlEsc(fmtBytes(traffic))+'</b></div><div class="sx-system-cell"><span>Live sessions</span><b>'+Number(d.online_sessions||0)+'</b></div><div class="sx-system-cell"><span>Panel endpoint</span><b>'+htmlEsc(endpoint)+'</b></div></section>',
    '</div>'
  ].join('');
}
let accountCache=[];
function setExpiryPreset(id,days){const el=document.getElementById(id);if(!el)return;if(Number(days)===0){el.value='';return}const base=new Date();base.setHours(12,0,0,0);base.setDate(base.getDate()+Number(days));el.value=base.toISOString().slice(0,10)}
function shiftExpiry(id,days){const el=document.getElementById(id);if(!el)return;const today=new Date();today.setHours(12,0,0,0);let base=today;if(el.value){const current=new Date(el.value+'T12:00:00');if(!Number.isNaN(current.getTime())&&current>today)base=current}base.setDate(base.getDate()+Number(days));el.value=base.toISOString().slice(0,10)}
function stepNumber(id,delta,min=1,max=50){const el=document.getElementById(id);if(!el)return;el.value=Math.max(min,Math.min(max,Number(el.value||min)+delta))}
let accessCache=[];
let provisionState=null;

async function access(renderToken=window.__viewRenderToken){
  title.textContent=tr('کاربران','Clients');setPageContext(tr('کاربران','CLIENTS'));
  content.innerHTML='<div class="loading-state"><span class="spinner"></span><b>'+htmlEsc(tr('در حال همگام‌سازی کاربران…','Synchronizing clients…'))+'</b></div>';
  const [rows,stack,sshRows,pcRows,operator]=await Promise.all([
    api('/api/access'),api('/api/protocols'),api('/api/accounts'),api('/api/protocol-clients'),api('/api/settings/operator')
  ]);
  if(renderToken!==window.__viewRenderToken||activeView!=='access')return;
  accessCache=rows;accountCache=sshRows;window.__protocolClients=pcRows;window.__protocolData=stack;window.__operatorSettings=operator;
  const active=rows.filter(x=>x.status==='active').length;
  const attention=rows.length-active;
  const online=rows.reduce((n,x)=>n+Number(x.online||0),0);
  content.innerHTML=[
    '<div class="pro-page">',
      '<section class="pro-page-head"><div><span class="pro-kicker">'+htmlEsc(tr('مدیریت دسترسی','ACCESS MANAGEMENT'))+'</span><h1>'+htmlEsc(tr('کاربران','Clients'))+'</h1><p>'+htmlEsc(tr('لیست یکپارچه دسترسی‌ها؛ جزئیات و ابزارهای تحویل فقط هنگام نیاز باز می‌شوند.','Unified access list; delivery and management tools open only when needed.'))+'</p></div><div class="pro-head-actions"><button class="ghost" data-action="self-test">'+htmlEsc(tr('بررسی سلامت','Health check'))+'</button><button class="primary" data-action="wizard-open">＋ '+htmlEsc(tr('ساخت دسترسی','Create access'))+'</button></div></section>',
      '<section class="pro-stat-strip"><div><span>'+htmlEsc(tr('کل کاربران','Total clients'))+'</span><b>'+rows.length+'</b></div><div><span>'+htmlEsc(tr('فعال','Active'))+'</span><b>'+active+'</b></div><div><span>'+htmlEsc(tr('نیازمند توجه','Needs attention'))+'</span><b>'+attention+'</b></div><div><span>'+htmlEsc(tr('اتصال زنده','Live connections'))+'</span><b>'+online+'</b></div></section>',
      '<section class="pro-directory">',
        '<div class="pro-directory-toolbar"><div class="pro-filter-tabs" id="accessSegments"><button class="active" data-filter-value="all">همه</button><button data-filter-value="xray">Xray</button><button data-filter-value="ssh">SSH</button><button data-filter-value="wireguard">WireGuard</button><button data-filter-value="openvpn">OpenVPN</button></div><div class="pro-search-wrap"><span>⌕</span><input id="accessSearch" placeholder="جستجو نام کاربر یا پروتکل..."></div></div>',
        '<div class="pro-user-table-head"><span>کاربر</span><span>پروتکل</span><span>وضعیت</span><span>مصرف / انقضا</span><span></span></div>',
        '<div id="accessRows" class="pro-user-list"></div>',
      '</section>',
    '</div>'
  ].join('');
  document.getElementById('accessSearch')?.addEventListener('input',renderAccessRows);
  document.getElementById('accessSegments')?.addEventListener('click',e=>{
    const b=e.target.closest('[data-filter-value]');if(!b)return;
    document.querySelectorAll('#accessSegments [data-filter-value]').forEach(x=>x.classList.toggle('active',x===b));
    window.__accessFilter=b.dataset.filterValue||'all';renderAccessRows();
  });
  window.__accessFilter='all';renderAccessRows();
}

function renderAccessRows(){
  const root=document.getElementById('accessRows');if(!root)return;
  const q=(document.getElementById('accessSearch')?.value||'').trim().toLowerCase();
  const filter=window.__accessFilter||'all';
  const rows=accessCache.filter(a=>{
    const hay=(String(a.name||'')+' '+String(a.protocol||'')+' '+String(a.plan||'')+' '+String(a.endpoint||'')).toLowerCase();
    return (!q||hay.includes(q))&&(filter==='all'||a.kind===filter);
  });
  root.innerHTML=rows.length?rows.map(accessCard).join(''):'<div class="empty pro-empty">کاربری مطابق فیلتر پیدا نشد.</div>';
}

function accessUsageText(a){
  if(a.kind==='xray'){
    const used=fmtBytes(a.used_bytes||0),quota=a.quota_bytes?fmtBytes(a.quota_bytes):'∞';
    return used+' / '+quota;
  }
  if(a.kind==='wireguard')return fmtBytes(Number(a.rx||0)+Number(a.tx||0));
  if(a.kind==='ssh')return Number(a.online||0)+' / '+Number(a.connection_limit||1)+' session';
  return 'PKI';
}
function accessExpiryText(a){
  if(a.kind==='ssh')return a.expire_date||'بدون انقضا';
  if(a.kind==='xray')return a.expire_at?new Date(a.expire_at*1000).toLocaleDateString():'بدون انقضا';
  if(a.kind==='wireguard')return a.address||'Peer';
  return 'Certificate';
}
function accessCard(a){
  const proto=String(a.protocol||a.kind||'').toUpperCase();
  const stateClass=a.status==='active'?'ok':a.status==='expired'?'bad':'warn';
  const label=dataEnc(a.name),id=dataEnc(a.id);
  return [
    '<article class="pro-user-row">',
      '<div class="pro-user-id"><span class="pro-user-avatar">'+htmlEsc(String(a.name||'?').slice(0,1).toUpperCase())+'</span><div><b>'+htmlEsc(a.name)+'</b><small>'+htmlEsc(a.endpoint||a.plan||'Managed access')+'</small></div></div>',
      '<div><span class="pro-protocol-badge '+htmlEsc(a.kind)+'">'+htmlEsc(proto)+'</span></div>',
      '<div><span class="status-chip '+stateClass+'">'+htmlEsc(a.status||'unknown')+'</span></div>',
      '<div class="pro-user-usage"><b>'+htmlEsc(accessUsageText(a))+'</b><small>'+htmlEsc(accessExpiryText(a))+'</small></div>',
      '<div class="pro-row-actions"><button class="pro-more" data-action="access-detail" data-id="'+id+'" aria-label="جزئیات '+label+'">•••</button></div>',
    '</article>'
  ].join('');
}



async function rotateClientPortal(kind,key,name){
  if(!confirm(tr('لینک فعلی فوراً از کار می‌افتد و لینک جدید ساخته می‌شود. ادامه می‌دهید؟','The current link will stop working immediately and a new link will be created. Continue?')))return;
  try{
    await api('/api/access/'+encodeURIComponent(kind)+'/'+encodeURIComponent(key)+'/portal/rotate',{method:'POST'});
    toast(tr('لینک جدید ساخته شد','New client link created'));
    await openClientPortal(kind,key,name);
  }catch(e){alert(tr('تغییر لینک: ','Rotate link: ')+e.message)}
}

async function openClientPortal(kind,key,name){
  try{
    const r=await api('/api/access/'+encodeURIComponent(kind)+'/'+encodeURIComponent(key)+'/portal');
    const url=String(r.url||'');
    if(!url)throw new Error(tr('لینک کاربر ساخته نشد','Client link could not be created'));
    modalRoot.innerHTML=[
      '<div class="modal-backdrop"><div class="modal client-portal-link-modal">',
      '<div class="wizard-head"><div><div class="eyebrow">'+htmlEsc(tr('لینک اختصاصی کاربر','CLIENT SELF-SERVICE LINK'))+'</div><h3>'+htmlEsc(name||key)+'</h3><p>'+htmlEsc(tr('این لینک را مستقیم برای کاربر بفرست؛ آموزش، فایل و QR در همان صفحه است.','Send this link directly to the client; guide, file and QR are available on the same page.'))+'</p></div><button class="close-btn" data-action="modal-close">×</button></div>',
      '<label>'+htmlEsc(tr('لینک اختصاصی','Private client link'))+'<textarea id="clientPortalUrl" class="config-output small" readonly></textarea></label>',
      '<div class="wizard-note"><b>'+htmlEsc(tr('محرمانه','Private'))+'</b><span>'+htmlEsc(tr('هر کسی این لینک را داشته باشد می‌تواند اطلاعات اتصال همان کاربر را ببیند. آن را مانند رمز عبور نگه دارید.','Anyone with this link can view this client’s connection data. Treat it like a password.'))+'</span></div>',
      '<div class="wizard-footer"><button class="ghost" data-action="copy-target" data-target="clientPortalUrl">'+htmlEsc(tr('کپی لینک','Copy link'))+'</button><a class="primary link-btn" href="'+htmlEsc(url)+'" target="_blank" rel="noopener noreferrer">'+htmlEsc(tr('باز کردن صفحه کاربر','Open client page'))+'</a><button class="ghost" data-action="client-portal-rotate" data-kind="'+htmlEsc(kind)+'" data-key="'+dataEnc(key)+'" data-name="'+dataEnc(name||key)+'">'+htmlEsc(tr('ساخت لینک جدید','Rotate link'))+'</button><button class="ghost" data-action="modal-close">'+htmlEsc(tr('بستن','Close'))+'</button></div>',
      '</div></div>'
    ].join('');
    document.getElementById('clientPortalUrl').value=url;
  }catch(e){alert(tr('لینک کاربر: ','Client link: ')+e.message)}
}

async function openAccessDetail(id){
  let a=accessCache.find(x=>String(x.id)===String(id));
  if(!a){
    try{
      accessCache=await api('/api/access');
      a=accessCache.find(x=>String(x.id)===String(id));
    }catch(e){
      alert('Access refresh: '+e.message);
      return;
    }
  }
  if(!a){alert('این دسترسی دیگر در سرور پیدا نشد. صفحه را بروزرسانی کنید.');return;}
  const kind=htmlEsc(a.kind),key=dataEnc(a.key),name=dataEnc(a.name);
  const delivery=window.__operatorSettings?.delivery||{};
  const canShare=a.can_export&&(a.kind!=='ssh'||delivery.npv_enabled!==false);
  const shareLabel=a.kind==='ssh'?'NPV / QR':a.kind==='xray'?'QR / Share':a.kind==='wireguard'?'QR / Share':'';
  const manage=(a.kind==='ssh'||a.kind==='xray')
    ? '<button class="primary" data-action="manage-access" data-id="'+dataEnc(a.id)+'">ویرایش تنظیمات</button>'
    : '<button class="primary" data-action="nav" data-view="'+kind+'">مدیریت '+htmlEsc(String(a.kind).toUpperCase())+'</button>';
  const nativeLabel=a.kind==='openvpn'?'دانلود فایل OVPN':a.kind==='wireguard'?'دانلود Config':'Native config';
  const deliveryButtons=a.can_export?[
    canShare&&shareLabel?'<button class="ghost" data-action="access-share" data-kind="'+kind+'" data-key="'+key+'" data-name="'+name+'">'+shareLabel+'</button>':'',
    '<button class="ghost" data-action="native-export" data-kind="'+kind+'" data-key="'+key+'">'+nativeLabel+'</button>',
    '<button class="primary" data-action="client-portal" data-kind="'+kind+'" data-key="'+key+'" data-name="'+name+'">'+htmlEsc(tr('لینک اختصاصی کاربر','Client portal link'))+'</button>',
    '<button class="ghost" data-action="protected-export" data-kind="'+kind+'" data-key="'+key+'" data-name="'+name+'">'+htmlEsc(tr('بسته رمزدار','Protected ZIP'))+'</button>',
    '<button class="ghost" data-action="client-guide" data-kind="'+kind+'">'+htmlEsc(tr('راهنمای اتصال','Connection guide'))+'</button>'
  ].join(''):'<span class="muted">برای این رکورد خروجی قابل تحویل موجود نیست.</span>';
  modalRoot.innerHTML=[
    '<div class="modal-backdrop detail-backdrop"><aside class="access-detail-drawer">',
      '<header><div><span class="pro-kicker">ACCESS PROFILE</span><h3>'+htmlEsc(a.name)+'</h3><p>'+htmlEsc(String(a.protocol||a.kind).toUpperCase())+'</p></div><button class="close-btn" data-action="modal-close">×</button></header>',
      '<div class="access-detail-body">',
        '<section class="access-detail-summary"><div><span>وضعیت</span><b>'+htmlEsc(a.status||'unknown')+'</b></div><div><span>Endpoint</span><b>'+htmlEsc(a.endpoint||'—')+'</b></div><div><span>مصرف</span><b>'+htmlEsc(accessUsageText(a))+'</b></div><div><span>انقضا / نوع</span><b>'+htmlEsc(accessExpiryText(a))+'</b></div></section>',
        '<section class="detail-section"><div class="detail-section-head"><div><h4>مدیریت</h4><p>تنظیمات عملیاتی این دسترسی</p></div></div><div class="detail-actions">'+manage+'</div></section>',
        '<section class="detail-section"><div class="detail-section-head"><div><h4>تحویل به کاربر</h4><p>فقط در زمان ارسال کانفیگ از این ابزارها استفاده کن.</p></div></div><div class="detail-actions">'+deliveryButtons+'</div></section>',
      '</div>',
      '<footer><button class="danger" data-action="revoke-access" data-kind="'+kind+'" data-key="'+key+'" data-name="'+name+'">لغو دسترسی</button><button class="ghost" data-action="modal-close">بستن</button></footer>',
    '</aside></div>'
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
  const initialEndpoint=window.PANEL_DOMAIN||location.hostname;
  const initialMode=/^\d{1,3}(?:\.\d{1,3}){3}$/.test(initialEndpoint)?'ip':'domain';
  const ovpn=window.__protocolData?.openvpn||{};
  const usedXrayPorts=new Set((window.__protocolData?.xray?.inbounds||[]).map(x=>Number(x.port)));
  let xrayPort=Number(d.xray_port||2087);
  while(usedXrayPorts.has(xrayPort)&&xrayPort<65535)xrayPort++;
  provisionState={
    step:protocol?2:1,protocol:protocol||'',name:defs.username||'user001',
    endpoint:initialEndpoint,endpointMode:initialMode,
    endpointValues:{ip:initialMode==='ip'?initialEndpoint:'',domain:initialMode==='domain'?initialEndpoint:''},
    password:'',passwordMode:d.ssh_password_mode||'pin6',
    expireDate:'',plan:'',note:'',sessions:Number(d.ssh_sessions||1),devices:Number(d.ssh_devices||1),
    xrayProtocol:d.xray_protocol||'vless',port:xrayPort,transport:'tcp',security:'reality',simpleMode:true,manualXray:false,path:d.xray_path||'/makia',
    sni:d.xray_sni||'www.microsoft.com',realityDest:d.xray_reality_target||'www.microsoft.com:443',
    quota:Number(d.xray_quota_gb??50),expireDays:Number(d.xray_expire_days??30),resetDays:Number(d.xray_reset_days??30),
    dns:d.wireguard_dns||'1.1.1.1',wgPort:Number(d.wireguard_port||443),wgMtu:Number(d.wireguard_mtu||1280),wgKeepalive:Number(d.wireguard_keepalive??15),wgAllowedIps:d.wireguard_allowed_ips||'0.0.0.0/0',wgCidr:d.wireguard_cidr||'10.66.66.1/24',ovpnProto:String(ovpn.proto||d.openvpn_proto||'udp').startsWith('tcp')?'tcp':'udp',ovpnPort:Number(ovpn.port||d.openvpn_port||1194),
    packagePassword:''
  };
  applySimpleXrayPreset(provisionState);
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

function protocolGlyph(kind){
  const glyphs={
    ssh:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="m7 9 3 3-3 3M12 15h5"/></svg>',
    xray:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 5l14 14M19 5 5 19"/><circle cx="12" cy="12" r="9"/></svg>',
    wireguard:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 4.5 6v5.5c0 4.7 3.1 7.8 7.5 9.5 4.4-1.7 7.5-4.8 7.5-9.5V6L12 3Z"/><path d="m9 13 2-4 1 3h3l-3 4"/></svg>',
    openvpn:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="9" r="5"/><path d="M9 13v7h6v-7M12 14v3"/></svg>',
    ikev2:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 12a8 8 0 1 1 2.3 5.7"/><path d="M4 17v-5h5"/><path d="M10 12h8M14 8v8"/></svg>',
    stealth:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6Z"/><circle cx="12" cy="12" r="2.5"/><path d="M5 19 19 5"/></svg>',
    wstunnel:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12h5l2-4 4 8 2-4h5"/><path d="M5 5h14v14H5z"/></svg>',
    inbound:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m0 0-4-4m4 4 4-4"/><path d="M5 19h14"/></svg>'
  };
  return '<span class="proto-glyph '+htmlEsc(kind)+'">'+(glyphs[kind]||glyphs.inbound)+'</span>';
}

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
  const steps=[['پروتکل','انتخاب مسیر اتصال'],['مشخصات','اطلاعات کاربر'],['سیاست','محدودیت و شبکه'],['تأیید','ساخت و تحویل']];
  let body='';
  if(s.step===1){
    const cards=[
      ['ssh','SSH','دسترسی سریع و سبک','Password / Session policy'],
      ['xray','Xray / V2Ray','پروفایل‌های چندگانه و مدیریت پیشرفته','VLESS · VMess · Trojan · Hysteria2'],
      ['wireguard','WireGuard','تونل Native سریع','Peer · QR · Handshake · Traffic'],
      ['openvpn','OpenVPN','PKI با TCP/UDP قابل تنظیم','Certificate · OVPN · TCP/UDP']
    ];
    body='<div class="provision-intro"><span class="pro-kicker">CHOOSE PROTOCOL</span><h4>نوع دسترسی را انتخاب کن</h4><p>فقط تنظیمات ضروری نمایش داده می‌شود؛ گزینه‌های تخصصی داخل بخش پیشرفته باقی می‌مانند.</p></div><div class="wizard-protocols pro-protocol-picker">'+cards.map(x=>{
      const ready=wizardProtocolReady(x[0]);
      return '<button class="wizard-protocol pro-protocol-card '+(ready?'ready':'not-ready')+'" data-action="'+(ready?'wizard-protocol':'protocol-setup')+'" data-kind="'+x[0]+'"><span class="protocol-card-icon '+x[0]+'">'+x[4]+'</span><div><b>'+x[1]+'</b><small>'+x[2]+'</small><em>'+x[3]+'</em></div><i>'+(ready?'آماده':'نیاز به راه‌اندازی')+'</i></button>';
    }).join('')+'</div>';
  }else if(s.step===2){
    body=wizardIdentityFields(s);
  }else if(s.step===3){
    body=wizardPolicyFields(s);
  }else{
    body=wizardReview(s);
  }
  const protocolLabel=s.protocol?({ssh:'SSH',xray:'Xray / V2Ray',wireguard:'WireGuard',openvpn:'OpenVPN'}[s.protocol]||s.protocol):'انتخاب پروتکل';
  const footer=s.step===1
    ? '<button class="ghost" data-action="modal-close">انصراف</button>'
    : '<button class="ghost" data-action="wizard-prev">مرحله قبل</button>'+(s.step<4?'<button class="primary" data-action="wizard-next">ادامه ←</button>':'<button class="primary action-lg" data-action="wizard-create">ساخت دسترسی</button>');
  modalRoot.innerHTML=[
    '<div class="modal-backdrop provision-backdrop"><aside class="provision-drawer">',
      '<header class="provision-header"><div><span class="pro-kicker">NEW ACCESS</span><h3>ساخت دسترسی جدید</h3><p>'+htmlEsc(protocolLabel)+'</p></div><button class="close-btn" data-action="modal-close">×</button></header>',
      '<div class="provision-progress">'+steps.map((x,i)=>'<div class="'+(s.step===i+1?'active':s.step>i+1?'done':'')+'"><i>'+(s.step>i+1?'✓':i+1)+'</i><span><b>'+x[0]+'</b><small>'+x[1]+'</small></span></div>').join('')+'</div>',
      '<div class="provision-scroll"><div class="wizard-body">'+body+'</div></div>',
      '<footer class="wizard-footer">'+footer+'</footer>',
    '</aside></div>'
  ].join('');
}
function wizardIdentityFields(s){
  if(s.protocol==='ssh') return [
    '<div class="wizard-section-title"><span class="pro-kicker">IDENTITY</span><h4>حساب SSH</h4><p>اطلاعات اصلی ورود را وارد کن. تنظیمات کمتر استفاده‌شده داخل «پیشرفته» قرار دارند.</p></div>',
    '<div class="wizard-form two"><label>نام کاربری<input id="wizName" value="'+htmlEsc(s.name)+'"></label>',
    '<label>رمز / PIN<div class="input-action"><input id="wizPassword" value="'+htmlEsc(s.password)+'"><button class="soft" data-action="wizard-secret" data-mode="pin6">تولید</button></div><div class="preset-row"><button data-action="wizard-secret" data-mode="pin6">PIN 6</button><button data-action="wizard-secret" data-mode="easy8">Easy 8</button><button data-action="wizard-secret" data-mode="strong">Strong</button></div></label>',
    wizardEndpointFields(s)+'</div>',
    '<details class="pro-advanced"><summary><span>تنظیمات پیشرفته</span><small>Plan و یادداشت داخلی</small></summary><div class="wizard-form two"><label>Plan<input id="wizPlan" value="'+htmlEsc(s.plan)+'" placeholder="VIP / Trial / 30D"></label><label>یادداشت داخلی<input id="wizNote" value="'+htmlEsc(s.note)+'" placeholder="نام مشتری / سفارش"></label></div></details>'
  ].join('');
  if(s.protocol==='xray') return [
    '<div class="wizard-section-title"><span class="pro-kicker">XRAY PROFILE</span><h4>پروفایل Xray</h4><p>Protocol و Endpoint را مشخص کن؛ Makia تنظیمات سازگار پایه را خودکار انتخاب می‌کند.</p></div>',
    '<div class="wizard-form two"><label>Protocol<select id="wizXrayProtocol">',
    ['vless','vmess','trojan','shadowsocks','hysteria2','http','socks'].map(x=>'<option value="'+x+'" '+(s.xrayProtocol===x?'selected':'')+'>'+x.toUpperCase()+'</option>').join(''),
    '</select></label><label>نام Client<input id="wizName" value="'+htmlEsc(s.name)+'"></label>',
    wizardEndpointFields(s),
    '<label>Port<input id="wizPort" type="number" min="1" max="65535" value="'+Number(s.port)+'"></label></div>',
    '<div class="pro-info-card"><div><b>Preset هوشمند</b><span>'+htmlEsc(s.xrayProtocol.toUpperCase())+' · '+htmlEsc(s.transport.toUpperCase())+' · '+htmlEsc(s.security.toUpperCase())+'</span></div><small>در مرحله بعد در صورت نیاز Transport، TLS/REALITY، حجم و IP Limit را تغییر بده.</small></div>'
  ].join('');
  if(s.protocol==='wireguard') return [
    '<div class="wizard-section-title"><span class="pro-kicker">WIREGUARD PEER</span><h4>Peer جدید</h4><p>برای هر دستگاه یک Peer مستقل بساز؛ تنظیمات شبکه پیش‌فرض برای اکثر کلاینت‌ها کافی است.</p></div>',
    '<div class="wizard-form two"><label>نام Peer<input id="wizName" value="'+htmlEsc(s.name)+'"></label>'+wizardEndpointFields(s)+'</div>',
    '<details class="pro-advanced"><summary><span>تنظیمات شبکه</span><small>DNS · MTU · Keepalive · Allowed IPs</small></summary><div class="wizard-form two"><label>DNS<input id="wizDns" value="'+htmlEsc(s.dns)+'"></label><label>MTU<input id="wizWgMtu" type="number" min="576" max="1500" value="'+Number(s.wgMtu||1280)+'"></label><label>Persistent Keepalive<input id="wizWgKeepalive" type="number" min="0" max="3600" value="'+Number(s.wgKeepalive??15)+'"></label><label>Allowed IPs<input id="wizWgAllowedIps" value="'+htmlEsc(s.wgAllowedIps||'0.0.0.0/0')+'"></label></div></details>'
  ].join('');
  return [
    '<div class="wizard-section-title"><span class="pro-kicker">OPENVPN CLIENT</span><h4>Client جدید</h4><p>برای این کاربر Certificate مستقل ساخته می‌شود.</p></div>',
    '<div class="wizard-form two"><label>نام Client<input id="wizName" value="'+htmlEsc(s.name)+'"></label>'+wizardEndpointFields(s),
    '<label>Port سرور<input id="wizOvpnPort" type="number" value="'+Number(s.ovpnPort)+'" readonly></label>',
    '<label>Transport<input value="'+htmlEsc(s.ovpnProto.toUpperCase())+'" readonly></label></div>'
  ].join('');
}
const XRAY_PROFILE_MATRIX={
  vless:{label:'VLESS',transports:['tcp','ws','grpc','httpupgrade','xhttp','kcp'],security:['reality','tls','none'],preset:['tcp','reality'],requiresDomain:false},
  vmess:{label:'VMess',transports:['tcp','ws','grpc','httpupgrade','xhttp','kcp'],security:['none','tls'],preset:['ws','none'],requiresDomain:false},
  trojan:{label:'Trojan',transports:['tcp','ws','grpc','httpupgrade','xhttp'],security:['tls'],preset:['tcp','tls'],requiresDomain:true},
  shadowsocks:{label:'Shadowsocks',transports:['tcp'],security:['none'],preset:['tcp','none'],requiresDomain:false},
  hysteria2:{label:'Hysteria2',transports:['hysteria'],security:['tls'],preset:['hysteria','tls'],requiresDomain:true},
  http:{label:'HTTP Proxy',transports:['tcp'],security:['none'],preset:['tcp','none'],requiresDomain:false},
  socks:{label:'SOCKS5',transports:['tcp'],security:['none'],preset:['tcp','none'],requiresDomain:false}
};
const XRAY_MANUAL_MATRIX={
  vless:{label:'VLESS',transports:['tcp','ws','grpc','httpupgrade','xhttp','kcp'],security:['none','tls','reality'],preset:['tcp','none']},
  vmess:{label:'VMess',transports:['tcp','ws','grpc','httpupgrade','xhttp','kcp'],security:['none','tls'],preset:['tcp','none']},
  trojan:{label:'Trojan',transports:['tcp','ws','grpc','httpupgrade','xhttp','kcp'],security:['none','tls'],preset:['tcp','none']},
  shadowsocks:{label:'Shadowsocks',transports:['tcp'],security:['none'],preset:['tcp','none']},
  hysteria2:{label:'Hysteria2',transports:['hysteria'],security:['tls'],preset:['hysteria','tls']},
  http:{label:'HTTP Proxy',transports:['tcp'],security:['none'],preset:['tcp','none']},
  socks:{label:'SOCKS5',transports:['tcp'],security:['none'],preset:['tcp','none']}
};

function xrayProfileSpec(protocol){return XRAY_PROFILE_MATRIX[protocol]||XRAY_PROFILE_MATRIX.vless}
function xrayManualSpec(protocol){return XRAY_MANUAL_MATRIX[protocol]||XRAY_MANUAL_MATRIX.vless}

function normalizeXrayProfile(s,forcePreset=false){
  const spec=s.manualXray?xrayManualSpec(s.xrayProtocol):xrayProfileSpec(s.xrayProtocol);
  if(forcePreset||!spec.transports.includes(s.transport))s.transport=spec.preset[0];
  if(forcePreset||!spec.security.includes(s.security))s.security=spec.preset[1];
  if(s.security==='reality'&&!['tcp','grpc','xhttp'].includes(s.transport))s.transport='tcp';
  if(s.security==='tls'&&s.endpointMode==='domain'&&s.endpoint&&!s.sni)s.sni=s.endpoint;
  if(s.xrayProtocol==='hysteria2'){s.transport='hysteria';s.security='tls'}
  return s;
}

function applySimpleXrayPreset(s){s.manualXray=false;return normalizeXrayProfile(s,true)}

function xrayPrerequisiteMessage(s){
  if(s.security==='tls'&&s.endpointMode!=='domain')return 'TLS به Domain/SNI و Certificate معتبر روی همین VPS نیاز دارد.';
  if(s.xrayProtocol==='hysteria2'&&s.endpointMode!=='domain')return 'Hysteria2 به Domain/SNI و Certificate معتبر نیاز دارد.';
  if(s.security==='reality'&&s.xrayProtocol!=='vless')return 'REALITY فقط برای VLESS قابل ساخت است.';
  if(s.security==='reality'&&!['tcp','grpc','xhttp'].includes(s.transport))return 'REALITY فقط با TCP/RAW، gRPC یا XHTTP قابل ساخت است.';
  return '';
}

function wizardEndpointFields(s){
  const mode=s.endpointMode==='ip'?'ip':'domain';
  return '<label>Endpoint type<select id="wizEndpointMode"><option value="domain" '+(mode==='domain'?'selected':'')+'>دامنه</option><option value="ip" '+(mode==='ip'?'selected':'')+'>IPv4 عمومی</option></select></label>'+
    '<label>'+(mode==='ip'?'Public IPv4':'Domain / hostname')+'<input id="wizEndpoint" dir="ltr" autocomplete="off" placeholder="'+(mode==='ip'?'IPv4 عمومی VPS':'vpn.example.com')+'" value="'+htmlEsc(s.endpoint)+'"><small>'+(mode==='domain'?(s.protocol==='xray'?'TLS ممکن است به SNI و گواهی معتبر نیاز داشته باشد.':s.protocol==='ssh'?'رکورد A باید مستقیم به VPS برسد؛ AAAA فقط با IPv6 سالم سرور.':'رکورد A باید مستقیم به VPS برسد؛ Proxy/CDN برای این پروتکل مناسب نیست.'):'IP عمومی سرور را وارد کن؛ خروجی کلاینت از همین IP استفاده می‌کند.')+'</small></label>';
}

function wizardPolicyFields(s){
  if(s.protocol==='ssh') return [
    '<div class="wizard-section-title"><span class="pro-kicker">ACCESS POLICY</span><h4>مدت و محدودیت</h4><p>فقط انقضا را تنظیم کن؛ محدودیت‌های نشست و دستگاه اختیاری‌اند.</p></div>',
    '<div class="wizard-form one"><label>تاریخ انقضا<input id="wizExpireDate" type="date" value="'+htmlEsc(s.expireDate)+'"><div class="preset-row"><button data-action="wizard-expiry" data-days="7">7 روز</button><button data-action="wizard-expiry" data-days="30">30 روز</button><button data-action="wizard-expiry" data-days="60">60 روز</button><button data-action="wizard-expiry" data-days="90">90 روز</button><button data-action="wizard-expiry" data-days="0">بدون انقضا</button></div></label></div>',
    '<details class="pro-advanced"><summary><span>محدودیت اتصال</span><small>Session و Device/IP limit</small></summary><div class="wizard-form two"><label>نشست همزمان<input id="wizSessions" type="number" min="1" max="50" value="'+Number(s.sessions)+'"></label><label>Device / IP Limit<input id="wizDevices" type="number" min="1" max="50" value="'+Number(s.devices)+'"></label></div></details>'
  ].join('');
  if(s.protocol==='xray'){
    normalizeXrayProfile(s,false);
    const spec=s.manualXray?xrayManualSpec(s.xrayProtocol):xrayProfileSpec(s.xrayProtocol),pre=xrayPrerequisiteMessage(s);
    const intro='<div class="wizard-section-title"><span class="pro-kicker">'+(s.manualXray?'XRAY MANUAL BUILDER':'NETWORK POLICY')+'</span><h4>'+(s.manualXray?'ساخت دستی Inbound / Client':'شبکه و محدودیت')+'</h4><p>'+(s.manualXray?'Protocol، Port، Transport و Security را خودت انتخاب می‌کنی؛ Makia فقط Collision را بررسی می‌کند و Xray Core 26.3.27 قبل از Apply کانفیگ را Validate می‌کند.':'Presetهای تست‌شده برای '+htmlEsc(spec.label)+' نمایش داده می‌شوند.')+'</p></div>';
    if(s.simpleMode)return intro+
      '<div class="recommended-profile"><div><span>پروفایل پیشنهادی</span><b>'+htmlEsc(spec.label.toUpperCase())+' / '+htmlEsc(s.transport.toUpperCase())+' / '+htmlEsc(s.security.toUpperCase())+'</b></div><span class="status-chip '+(pre?'warn':'ok')+'">'+(pre?'نیاز به Domain':'Recommended')+'</span></div>'+
      (pre?'<div class="wizard-note danger-note"><b>پیش‌نیاز</b><span>'+htmlEsc(pre)+'</span></div>':'')+
      '<div class="pro-info-card"><div><b>حالت ساده</b><span>Preset تست‌شده اعمال می‌شود.</span></div><small>برای انتخاب آزاد Port/Transport/Security و حتی VLESS/VMess بدون TLS/REALITY وارد Manual Builder شو.</small></div><button class="soft pro-advanced-open" data-action="wizard-xray-advanced">Manual / Expert Builder</button>';
    const transports=spec.transports.map(x=>'<option value="'+x+'" '+(s.transport===x?'selected':'')+'>'+x.toUpperCase()+'</option>').join('');
    const securities=spec.security.map(x=>'<option value="'+x+'" '+(s.security===x?'selected':'')+'>'+x.toUpperCase()+'</option>').join('');
    const fixedTransport=spec.transports.length===1?' disabled':'',fixedSecurity=spec.security.length===1?' disabled':'';
    return [intro,
      pre?'<div class="wizard-note danger-note"><b>پیش‌نیاز</b><span>'+htmlEsc(pre)+'</span></div>':'',
      '<div class="wizard-form two"><label>Transport<select id="wizTransport"'+fixedTransport+'>'+transports+'</select><small>'+htmlEsc(spec.transports.join(' · '))+'</small></label>',
      '<label>Security<select id="wizSecurity"'+fixedSecurity+'>'+securities+'</select><small>'+htmlEsc(spec.security.join(' · ').toUpperCase())+'</small></label>',
      '<label>Path / Service<input id="wizPath" value="'+htmlEsc(s.path)+'" '+(['tcp','kcp','hysteria'].includes(s.transport)?'disabled':'')+'><small>'+(s.transport==='kcp'?'mKCP جدید Seed قدیمی ندارد.':'WS / gRPC / XHTTP path or service')+'</small></label>',
      '<label>SNI / Domain<input id="wizSni" value="'+htmlEsc(s.sni)+'" '+(s.security==='none'?'disabled':'')+'></label>',
      (s.security==='reality'?'<label>REALITY target<input id="wizReality" value="'+htmlEsc(s.realityDest)+'"></label>':''),
      '<label>Quota GB<input id="wizQuota" type="number" min="0" value="'+Number(s.quota)+'"><small>0 = Unlimited</small></label>',
      '<label>Expiry days<input id="wizExpireDays" type="number" min="0" max="3650" value="'+Number(s.expireDays)+'"></label>',
      '<label>Device / IP Limit<input id="wizDevices" type="number" min="1" max="50" value="'+Number(s.devices)+'"></label>',
      '<label>Traffic reset days<input id="wizResetDays" type="number" min="0" max="3650" value="'+Number(s.resetDays)+'"></label></div>',
      (s.manualXray&&s.security==='none'&&s.endpointMode!=='ip'?'<div class="wizard-note danger-note"><b>بدون رمزگذاری Transport</b><span>این انتخاب عمداً TLS/REALITY ندارد. Makia آن را مسدود نمی‌کند؛ امنیت و مناسب‌بودن شبکه بر عهده مدیر است.</span></div>':''),
      '<div class="toolbar"><button class="soft" data-action="wizard-xray-simple">استفاده از Preset ساده</button><button class="ghost" data-action="xray-advanced">Advanced JSON — همه فیلدهای Core</button></div>'
    ].join('');
  }
  const labels={wireguard:'WireGuard',openvpn:'OpenVPN'};
  return '<div class="wizard-review-hint"><div class="review-icon">✓</div><h4>'+htmlEsc(labels[s.protocol]||s.protocol)+' آماده است</h4><p>تنظیمات سرور و Client آماده‌اند. مرحله بعد خلاصه نهایی و بسته تحویل را نشان می‌دهد.</p></div>';
}
function wizardReview(s){
  const summary=[];
  summary.push(['Protocol',s.protocol==='xray'?s.xrayProtocol.toUpperCase():s.protocol.toUpperCase()]);
  summary.push(['Name',s.name]);
  if(s.endpoint)summary.push(['Endpoint',s.endpoint]);
  if(s.protocol==='ssh'){summary.push(['Expire',s.expireDate||'بدون انقضا']);summary.push(['Sessions',s.sessions]);summary.push(['Devices',s.devices])}
  if(s.protocol==='xray'){summary.push(['Port',s.port]);summary.push(['Transport',s.transport.toUpperCase()]);summary.push(['Security',s.security.toUpperCase()]);summary.push(['Quota',s.simpleMode?'Unlimited':s.quota?String(s.quota)+' GB':'Unlimited'])}
  return [
    '<div class="wizard-section-title"><span class="pro-kicker">REVIEW</span><h4>تأیید نهایی</h4><p>قبل از ساخت، فقط اطلاعات کلیدی را بررسی کن.</p></div>',
    '<div class="review-grid pro-review-grid">'+summary.map(x=>'<div><span>'+htmlEsc(x[0])+'</span><b>'+htmlEsc(x[1])+'</b></div>').join('')+'</div>',
    '<div class="delivery-box pro-delivery-box"><div><b>بسته تحویل امن</b><span>بعد از ساخت، Native config، QR و ZIP رمزدار در دسترس خواهد بود.</span></div><label>PIN بسته<div class="input-action"><input id="wizPackagePassword" value="'+htmlEsc(s.packagePassword)+'" minlength="4"><button class="soft" data-action="wizard-package-pin">تولید</button></div></label></div>'
  ].join('');
}
function captureWizard(){
  const s=provisionState;if(!s)return;
  const val=id=>document.getElementById(id)?.value;
  if(val('wizName')!==undefined)s.name=val('wizName').trim();
  if(val('wizEndpoint')!==undefined)s.endpoint=val('wizEndpoint').trim();
  if(s.endpointValues)s.endpointValues[s.endpointMode]=s.endpoint;
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
    if(!s.endpoint)return 'دامنه یا IP عمومی لازم است.';
    const isIp=/^\d{1,3}(?:\.\d{1,3}){3}$/.test(s.endpoint);
    if(s.endpointMode==='ip'&&!isIp)return 'در حالت IP، آدرس IPv4 عمومی را وارد کن.';
    if(s.endpointMode==='domain'&&(isIp||!/^([a-z0-9-]+\.)+[a-z0-9-]+\.?$/i.test(s.endpoint)))return 'در حالت دامنه، یک hostname معتبر وارد کن.';
    if(s.protocol==='xray'&&(!s.port||s.port<1||s.port>65535))return 'Port معتبر وارد کن.';
  }
  if(s.step===3&&s.protocol==='xray'){
    normalizeXrayProfile(s,false);
    const pre=xrayPrerequisiteMessage(s);if(pre)return pre;
    const spec=s.manualXray?xrayManualSpec(s.xrayProtocol):xrayProfileSpec(s.xrayProtocol);
    if(!spec.transports.includes(s.transport)||!spec.security.includes(s.security))return 'این ترکیب توسط Builder قابل Export نیست؛ برای تنظیمات خارج از Builder از Advanced JSON استفاده کن.';
    if(s.security==='reality'&&!['tcp','grpc','xhttp'].includes(s.transport))return 'REALITY فقط با TCP/RAW، gRPC یا XHTTP فعال است.';
    if(!s.manualXray&&['vless','trojan'].includes(s.xrayProtocol)&&s.security==='none'){
      const ep=(s.endpoint||'').trim();
      const privateIp=/^(10\.|127\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(ep)||ep==='localhost'||ep.endsWith('.local');
      if(!privateIp)return 'Guided mode برای Endpoint عمومی TLS/REALITY می‌خواهد؛ Manual / Expert Builder را انتخاب کن تا none مجاز باشد.';
    }
  }
  return '';
}

async function wizardNext(){
  captureWizard();if(provisionState.step===2&&provisionState.protocol==='xray'&&provisionState.simpleMode)applySimpleXrayPreset(provisionState);
  const err=validateWizardStep();if(err){alert(err);return}
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
      r=await api('/api/accounts',{method:'POST',body:JSON.stringify({username:s.name,password:s.password,password_mode:'manual',endpoint:s.endpoint,endpoint_mode:s.endpointMode,expire_date:s.expireDate||null,plan:s.plan,note:s.note,connection_limit:s.sessions,device_limit:s.devices,quota_mb:0,renewal_days:0})});
      key=s.name;
    }else if(s.protocol==='xray'){
      r=await api('/api/protocols/xray/quick-inbound',{method:'POST',body:JSON.stringify({protocol:s.xrayProtocol,port:s.port,name:s.name,endpoint:s.endpoint,endpoint_mode:s.endpointMode,transport:s.transport,security:s.security,path_value:s.path,server_name:s.sni,reality_dest:s.realityDest,manual:Boolean(s.manualXray),quota_gb:s.simpleMode?0:s.quota,expire_days:s.simpleMode?0:s.expireDays,ip_limit:s.simpleMode?50:s.devices,reset_days:s.simpleMode?0:s.resetDays})});
      kind='xray';key=String(r.client_id);
    }else if(s.protocol==='wireguard'){
      r=await api('/api/protocols/wireguard/peers',{method:'POST',body:JSON.stringify({name:s.name,endpoint:s.endpoint,endpoint_mode:s.endpointMode,dns:s.dns,mtu:s.wgMtu,keepalive:s.wgKeepalive,allowed_ips:s.wgAllowedIps})});key=s.name;
    }else{
      r=await api('/api/protocols/openvpn/clients',{method:'POST',body:JSON.stringify({name:s.name,endpoint:s.endpoint,endpoint_mode:s.endpointMode,port:s.ovpnPort,proto:s.ovpnProto})});key=s.name;
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
      '<div class="delivery-actions"><button class="primary action-lg" data-action="client-portal" data-kind="'+htmlEsc(kind)+'" data-key="'+dataEnc(key)+'" data-name="'+dataEnc(name)+'">'+htmlEsc(tr('لینک اختصاصی کاربر','Client portal link'))+'</button>'+((kind==='xray'||kind==='wireguard'||(kind==='ssh'&&(window.__operatorSettings?.delivery?.npv_enabled!==false)))?'<button class="ghost action-lg" data-action="access-share" data-kind="'+htmlEsc(kind)+'" data-key="'+dataEnc(key)+'" data-name="'+dataEnc(name)+'">'+(kind==='ssh'?'NPV / QR':'QR / Share')+'</button>':'')+'<button class="ghost action-lg" data-action="protected-download-now" data-kind="'+htmlEsc(kind)+'" data-key="'+dataEnc(key)+'" data-name="'+dataEnc(name)+'" data-password="'+dataEnc(packagePassword)+'">'+htmlEsc(tr('بسته رمزدار','Protected ZIP'))+'</button>',
      '<button class="ghost action-lg" data-action="native-export" data-kind="'+htmlEsc(kind)+'" data-key="'+dataEnc(key)+'">'+htmlEsc(tr('فایل اتصال','Native file'))+'</button><button class="ghost action-lg" data-action="client-guide" data-kind="'+htmlEsc(kind)+'">'+htmlEsc(tr('راهنمای اتصال','Connection guide'))+'</button></div>',
      '<div class="wizard-note"><b>تحویل امن</b><span>فایل و PIN را در دو پیام/کانال جداگانه برای کاربر بفرست.</span></div>',
      '<button class="soft wide-btn" data-action="success-done">بازگشت به Access Center</button>',
    '</div></div>'
  ].join('');
}

async function openProtectedExport(kind,key,name){
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
  const endpoint=prompt('Endpoint برای Peer جدید (دامنه مستقیم یا IPv4)',window.PANEL_DOMAIN||location.hostname);
  if(!endpoint)return;
  try{
    const check=await api('/api/protocols/wireguard/diagnostics?endpoint='+encodeURIComponent(endpoint));
    if(!check.endpoint_ok){alert('Endpoint آماده نیست؛ Peer قدیمی حفظ شد:\n'+(check.warnings||[]).join('\n'));return}
    if(!confirm('Peer قدیمی '+name+' باطل و Key جدید ساخته شود؟ فایل جدید باید روی Client دوباره Import شود.'))return;
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
  title.textContent='کاربران SSH';setPageContext('SSH USER MANAGEMENT');
  content.innerHTML='<div class="loading-state"><span class="spinner"></span><b>در حال بارگذاری کاربران SSH…</b></div>';
  const rows=await api('/api/accounts');
  if(renderToken!==window.__viewRenderToken||!['accounts','ssh'].includes(activeView))return;
  accountCache=rows;
  const active=rows.filter(a=>a.enabled&&!a.expired).length;
  const inactive=rows.length-active;
  const online=rows.reduce((n,a)=>n+Number(a.online||0),0);
  content.innerHTML=[
    '<section class="protocol-page-header"><div class="protocol-page-title"><span class="protocol-page-icon ssh">SSH</span><div><h2>SSH</h2><p>مدیریت کاربران SSH / NPV و سیاست‌های اتصال</p></div></div><div class="protocol-header-actions"><button class="ghost" data-action="nav" data-view="settings">تنظیمات SSH</button><button class="primary" data-action="wizard-open" data-kind="ssh">＋ ایجاد کاربر جدید</button></div></section>',
    '<section class="protocol-stat-grid"><div class="protocol-stat"><span class="icon">♙</span><div><span>کل کاربران</span><b>'+rows.length+'</b></div></div><div class="protocol-stat green"><span class="icon">◔</span><div><span>کاربران فعال</span><b>'+active+'</b></div></div><div class="protocol-stat red"><span class="icon">♧</span><div><span>غیرفعال / منقضی</span><b>'+inactive+'</b></div></div></section>',
    '<section class="panel protocol-directory"><div class="panel-head account-tools"><div><h3>مدیریت کاربران SSH</h3><span id="accountCount">'+rows.length+' USERS · '+online+' ONLINE SESSION</span></div><div class="filterbar"><input id="accountSearch" placeholder="جستجو نام کاربری / پلن / یادداشت" oninput="renderAccountRows()"><select id="accountFilter" onchange="renderAccountRows()"><option value="all">همه</option><option value="online">آنلاین</option><option value="active">فعال</option><option value="expiring">≤ 7 روز</option><option value="expired">منقضی</option><option value="locked">غیرفعال</option></select></div></div>',
    '<div class="toolbar bulkbar"><button class="soft" onclick="toggleAllAccounts()">انتخاب همه</button><button class="ghost" onclick="bulkAccounts(\'lock\')">غیرفعال</button><button class="ghost" onclick="bulkAccounts(\'unlock\')">فعال</button><button class="ghost" onclick="bulkExtendPreset(7)">+7 روز</button><button class="ghost" onclick="bulkExtendPreset(30)">+30 روز</button><button class="ghost" onclick="bulkExtendPreset(90)">+90 روز</button><button class="danger" onclick="bulkAccounts(\'disconnect\')">قطع اتصال</button></div>',
    '<div id="accountRows" class="table"></div></section>'
  ].join('');
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
async function wireguard(renderToken=window.__viewRenderToken){
  title.textContent='WireGuard';setPageContext('WIREGUARD USER MANAGEMENT');
  content.innerHTML='<div class="loading-state"><span class="spinner"></span><b>در حال خواندن WireGuard…</b></div>';
  const [stack,rows,operator]=await Promise.all([api('/api/protocols'),api('/api/access'),api('/api/settings/operator')]);
  if(renderToken!==window.__viewRenderToken||activeView!=='wireguard')return;
  window.__protocolData=stack;window.__operatorSettings=operator;
  const peers=rows.filter(x=>x.kind==='wireguard'),service=stack.wireguard||{},defs=operator.defaults||{};
  const active=peers.filter(p=>p.enabled!==false).length;
  const connected=peers.filter(p=>p.enabled&&p.handshake_age!==null&&p.handshake_age!==undefined&&p.handshake_age<180).length;
  const rx=peers.reduce((n,p)=>n+Number(p.rx||0),0),tx=peers.reduce((n,p)=>n+Number(p.tx||0),0);
  const peerRows=peers.map(p=>{
    const key=dataEnc(p.key),enabled=p.enabled!==false;
    return '<div class="row protocol-list-row"><div><b>'+htmlEsc(p.name)+'</b><div class="muted">'+htmlEsc(p.address||'WireGuard peer')+'</div></div><div><span class="status-chip '+(enabled?'ok':'bad')+'">'+(enabled?'فعال':'غیرفعال')+'</span><div class="muted">'+(p.handshake_age==null?'بدون Handshake':Math.floor(Number(p.handshake_age)/60)+' دقیقه پیش')+'</div></div><div><b>↓ '+fmtBytes(p.rx||0)+' · ↑ '+fmtBytes(p.tx||0)+'</b><div class="muted" dir="ltr">'+htmlEsc(p.endpoint||'—')+'</div></div><div class="toolbar">'+
      (p.can_export?'<button class="ghost" data-action="access-share" data-kind="wireguard" data-key="'+key+'" data-name="'+dataEnc(p.name)+'">QR</button><button class="ghost" data-action="native-export" data-kind="wireguard" data-key="'+key+'">Config</button>':'')+
      '<button class="'+(enabled?'soft':'primary')+'" data-action="wg-toggle" data-key="'+key+'" data-enabled="'+(enabled?'0':'1')+'">'+(enabled?'خاموش':'روشن')+'</button><button class="danger" data-action="revoke-access" data-kind="wireguard" data-key="'+key+'" data-name="'+dataEnc(p.name)+'">حذف</button></div></div>';
  }).join('');
  content.innerHTML=[
    '<section class="wg-workspace-hero protocol-page-header pro-engine-hero"><div class="protocol-page-title">'+protocolGlyph('wireguard')+'<div><span class="pro-kicker">NATIVE VPN</span><h2>WireGuard</h2><p>Peer، QR، Handshake، ترافیک و تنظیمات سازگاری Client</p></div></div><div class="protocol-header-actions"><button class="ghost" data-action="wireguard-diagnostics">Diagnostics</button><button class="ghost" data-action="nav-settings" data-tab="vpn">Advanced settings</button><button class="primary" data-action="'+(service.config?'wizard-open':'protocol-setup')+'" data-kind="wireguard">'+(service.config?'＋ ساخت Peer':'راه‌اندازی WireGuard')+'</button></div></section>',
    '<section class="wg-workspace-metrics pro-engine-metrics"><div><span>Peers</span><b>'+peers.length+'</b><small>'+active+' active</small></div><div><span>Recent handshake</span><b>'+connected+'</b><small>last 3 minutes</small></div><div><span>Traffic</span><b>'+fmtBytes(rx+tx)+'</b><small>↓ '+fmtBytes(rx)+' · ↑ '+fmtBytes(tx)+'</small></div><div><span>Server</span><b>UDP / '+htmlEsc(String(service.port||defs.wireguard_port||'—'))+'</b><small>MTU '+htmlEsc(String(service.mtu||defs.wireguard_mtu||1280))+'</small></div></section>',
    '<section class="engine-feature-grid"><article><span class="feature-icon">QR</span><div><b>Native QR / Config</b><small>تحویل مستقیم فایل و QR هر Peer</small></div></article><article><span class="feature-icon">↻</span><div><b>Keepalive</b><small>'+Number(defs.wireguard_keepalive??15)+'s برای NAT traversal</small></div></article><article><span class="feature-icon">DNS</span><div><b>Client DNS</b><small>'+htmlEsc(defs.wireguard_dns||'1.1.1.1')+'</small></div></article><article><span class="feature-icon">⇄</span><div><b>Allowed IPs</b><small>'+htmlEsc(defs.wireguard_allowed_ips||'0.0.0.0/0')+'</small></div></article></section>',
    '<section class="panel protocol-directory"><div class="panel-head"><div><h3>Peerهای WireGuard</h3><span>HANDSHAKE · TRAFFIC · ENDPOINT · STATE</span></div><div class="toolbar"><button class="ghost" data-action="wireguard-diagnostics">بررسی Endpoint</button><button class="ghost" data-action="refresh">بروزرسانی</button></div></div><div class="neon-table-head"><span>Peer</span><span>وضعیت</span><span>ترافیک / Endpoint</span><span>عملیات</span></div><div class="table">'+(peerRows||'<div class="empty">هنوز Peer ساخته نشده است.</div>')+'</div></section>',
    '<details class="pro-advanced engine-advanced-summary"><summary><span>تنظیمات پیشرفته WireGuard</span><small>DNS · Port · MTU · Keepalive · Allowed IPs · Tunnel CIDR</small></summary><div class="engine-setting-summary"><div><span>DNS</span><b>'+htmlEsc(defs.wireguard_dns||'1.1.1.1')+'</b></div><div><span>Listen Port</span><b>'+Number(defs.wireguard_port||443)+'/UDP</b></div><div><span>MTU</span><b>'+Number(defs.wireguard_mtu||1280)+'</b></div><div><span>Keepalive</span><b>'+Number(defs.wireguard_keepalive??15)+'s</b></div><div><span>Allowed IPs</span><b>'+htmlEsc(defs.wireguard_allowed_ips||'0.0.0.0/0')+'</b></div><div><span>Tunnel CIDR</span><b>'+htmlEsc(defs.wireguard_cidr||'10.66.66.1/24')+'</b></div></div><div class="settings-actions"><button class="primary" data-action="nav-settings" data-tab="vpn">ویرایش در تنظیمات VPN</button></div></details>'
  ].join('');
}

async function toggleWireGuardPeer(key,enabled){
  if(!confirm((enabled?'فعال کردن':'غیرفعال کردن')+' همتای '+key+'؟'))return;
  try{await api('/api/access/wireguard/'+encodeURIComponent(key)+'/state',{method:'POST',body:JSON.stringify({enabled})});toast(enabled?'همتا فعال شد':'همتا غیرفعال شد');await currentView()}catch(e){alert(e.message)}
}

async function inboundsWorkspace(renderToken=window.__viewRenderToken){
  title.textContent='Inboundها';setPageContext('INBOUNDS');
  content.innerHTML='<div class="loading-state"><span class="spinner"></span><b>در حال خواندن Inboundها…</b></div>';
  const [stack,clients]=await Promise.all([api('/api/protocols'),api('/api/protocol-clients')]);
  if(renderToken!==window.__viewRenderToken||activeView!=='inbounds')return;
  window.__protocolData=stack;window.__protocolClients=clients;
  const engine=stack.xray||{},rows=engine.inbounds||[];
  const totalClients=rows.reduce((n,x)=>n+Number(x.clients||0),0);
  const protocols=[...new Set(rows.map(x=>String(x.protocol||'unknown').toUpperCase()))];
  const list=rows.map((ib,i)=>{
    const proto=String(ib.protocol||'unknown').toUpperCase();
    const listen=(ib.listen||'0.0.0.0')+':'+(ib.port??'—');
    const managed=clients.filter(c=>String(c.inbound_tag||'')===String(ib.tag||'')).length;
    return '<div class="sx-inbound-row"><div class="sx-inbound-icon">'+htmlEsc(proto.slice(0,2))+'</div>'+
      '<div class="sx-inbound-main"><b>'+htmlEsc(ib.tag||('inbound-'+(i+1)))+'</b><span>'+htmlEsc(proto)+' · '+htmlEsc(String(ib.transport||'raw').toUpperCase())+' · '+htmlEsc(String(ib.security||'none').toUpperCase())+'</span></div>'+
      '<div class="sx-inbound-cell"><span>Listen</span><b dir="ltr">'+htmlEsc(listen)+'</b></div>'+
      '<div class="sx-inbound-cell"><span>Port</span><b>'+htmlEsc(String(ib.port??'—'))+'</b></div>'+
      '<div class="sx-inbound-cell"><span>Clients</span><b>'+Number(ib.clients||0)+'</b></div>'+
      '<div class="sx-inbound-cell"><span>Managed</span><b>'+managed+'</b></div>'+
      '<div class="sx-inbound-actions"><button class="primary" data-action="xray-inbound-client" data-tag="'+dataEnc(ib.tag||'')+'" data-protocol="'+htmlEsc(String(ib.protocol||''))+'">+ Client</button><button class="ghost" data-action="nav" data-view="xray">Clients</button><button class="ghost" data-action="xray-diagnostics">Status</button><button class="ghost" data-action="xray-advanced">JSON</button></div></div>';
  }).join('');
  content.innerHTML=[
    '<div class="sx-page">',
      '<section class="sx-page-head"><div><h1>Inboundها</h1><p>ساختار Xray Inboundها، پورت‌ها و Clientهای متصل</p></div><div class="sx-head-actions"><span class="sx-state-pill '+(engine.service_active?'':'warn')+'"><i></i>'+(engine.service_active?'Xray Running':'Xray Attention')+'</span><button class="ghost" data-action="xray-diagnostics">Diagnostics</button><button class="primary" data-action="'+(engine.installed?'xray-inbound-builder':'protocol-setup')+'" data-kind="xray">'+(engine.installed?'＋ New Inbound':'Install Xray')+'</button></div></section>',
      '<section class="sx-summary-row"><div class="sx-summary"><span>Inbounds</span><b>'+rows.length+'</b><small>Xray runtime</small></div><div class="sx-summary"><span>Clients</span><b>'+totalClients+'</b><small>Core-reported</small></div><div class="sx-summary"><span>Protocols</span><b>'+protocols.length+'</b><small>'+htmlEsc(protocols.join(' · ')||'—')+'</small></div><div class="sx-summary"><span>Managed clients</span><b>'+clients.length+'</b><small>Makia policy records</small></div></section>',
      '<section class="sx-table-wrap"><div class="sx-table-toolbar"><div><h3>Inbound list</h3><small>PORT · PROTOCOL · CLIENTS</small></div><div class="sx-toolbar-right"><button class="ghost" data-action="xray-advanced">Advanced JSON</button><button class="ghost" data-action="refresh">Refresh</button></div></div><div class="sx-inbound-list">'+(list||'<div class="empty">Inbound قابل‌خواندن وجود ندارد. از افزودن Inbound یا Advanced JSON استفاده کنید.</div>')+'</div></section>',
    '</div>'
  ].join('');
}

async function xrayWorkspace(renderToken=window.__viewRenderToken){
  title.textContent='V2Ray / Xray';setPageContext('XRAY USER MANAGEMENT');
  content.innerHTML='<div class="loading-state"><span class="spinner"></span><b>در حال همگام‌سازی Xray…</b></div>';
  const [stack,clients,accessRows,operator]=await Promise.all([api('/api/protocols'),api('/api/protocol-clients'),api('/api/access'),api('/api/settings/operator')]);
  if(renderToken!==window.__viewRenderToken||activeView!=='xray')return;
  window.__protocolData=stack;window.__protocolClients=clients;window.__operatorSettings=operator;accessCache=accessRows;
  const engine=stack.xray||{},managed=clients,rows=accessRows.filter(x=>x.kind==='xray');
  const active=managed.filter(x=>x.enabled&&!x.expired).length;
  const inactive=managed.length-active;
  const used=managed.reduce((sum,x)=>sum+Number(x.usage?.total||0),0);
  content.innerHTML=[
    '<section class="wg-workspace-hero protocol-page-header"><div class="protocol-page-title"><span class="protocol-page-icon xray">V</span><div><h2>Xray / V2Ray</h2><p>Inbound → Client → Transport → Security · VLESS · VMess · Trojan · Shadowsocks · Hysteria2</p></div></div><div class="protocol-header-actions"><button class="ghost" data-action="xray-diagnostics">Diagnostics</button><button class="ghost" data-action="xray-advanced">تنظیمات Xray</button><button class="primary" data-action="'+(engine.installed?'xray-inbound-builder':'protocol-setup')+'" data-kind="xray">'+(engine.installed?'＋ New Inbound':'نصب Xray Core')+'</button></div></section>',
    '<section class="wg-workspace-metrics"><div><span>کل کاربران</span><b>'+managed.length+'</b></div><div><span>فعال</span><b>'+active+'</b></div><div><span>غیرفعال</span><b>'+inactive+'</b></div><div><span>مصرف کل</span><b>'+fmtBytes(used)+'</b></div></section>',
    '<section class="panel protocol-directory"><div class="panel-head"><div><h3>Clientهای مدیریت‌شده</h3><span>هر Client به یک Inbound متصل است · QUOTA · EXPIRY · IP LIMIT</span></div><div class="toolbar"><button class="ghost" data-action="nav" data-view="inbounds">مشاهده Inboundها</button><button class="ghost" data-action="refresh">بروزرسانی</button></div></div><div class="protocol-client-list">'+(managed.length?managed.map(protocolClientRow).join(''):'<div class="empty">هنوز Client ساخته نشده است. ابتدا یک Inbound بساز.</div>')+'</div></section>',
    '<section class="panel"><div class="panel-head"><div><h3>خروجی و اشتراک کاربران</h3><span>'+rows.length+' PROFILE</span></div><button class="ghost" data-action="client-guide" data-kind="xray">راهنمای اتصال</button></div><div class="access-cards">'+(rows.length?rows.map(accessCard).join(''):'<div class="empty compact">پروفایل قابل تحویل وجود ندارد.</div>')+'</div></section>'
  ].join('');
}
async function openvpnWorkspace(renderToken=window.__viewRenderToken){
  title.textContent='OpenVPN';setPageContext('OPENVPN USER MANAGEMENT');
  content.innerHTML='<div class="loading-state"><span class="spinner"></span><b>در حال همگام‌سازی OpenVPN…</b></div>';
  const [stack,rows,operator]=await Promise.all([api('/api/protocols'),api('/api/access'),api('/api/settings/operator')]);
  if(renderToken!==window.__viewRenderToken||activeView!=='openvpn')return;
  window.__protocolData=stack;window.__operatorSettings=operator;accessCache=rows;
  const engine=stack.openvpn||{},clients=rows.filter(x=>x.kind==='openvpn'),opt=engine.options||{};
  const active=engine.service_active?clients.length:0;
  const transport=String(opt.proto||engine.proto||'udp').startsWith('tcp')?'TCP':'UDP';
  const dns=(opt.dns||[]).join(' · ')||'1.1.1.1';
  content.innerHTML=[
    '<section class="protocol-page-header pro-engine-hero"><div class="protocol-page-title">'+protocolGlyph('openvpn')+'<div><span class="pro-kicker">CERTIFICATE VPN</span><h2>OpenVPN</h2><p>PKI، Client profile، TCP/UDP و سیاست‌های Server در یک Workspace</p></div></div><div class="protocol-header-actions"><button class="ghost" data-action="openvpn-diagnostics">Diagnostics</button><button class="ghost" data-action="openvpn-configure">Server settings</button><button class="primary" data-action="'+(engine.config?'wizard-open':'protocol-setup')+'" data-kind="openvpn">'+(engine.config?'＋ ایجاد کلاینت':'راه‌اندازی OpenVPN')+'</button></div></section>',
    '<section class="wg-workspace-metrics pro-engine-metrics"><div><span>Clients</span><b>'+clients.length+'</b><small>Certificates</small></div><div><span>Runtime</span><b class="'+(engine.service_active?'ok-text':'bad-text')+'">'+(engine.service_active?'ACTIVE':'DOWN')+'</b><small>openvpn-server@server</small></div><div><span>Transport</span><b>'+transport+' / '+htmlEsc(String(opt.port||engine.port||'—'))+'</b><small>IPv4 locked</small></div><div><span>DNS</span><b>'+htmlEsc(dns)+'</b><small>Pushed to clients</small></div></section>',
    '<section class="engine-feature-grid"><article><span class="feature-icon">↔</span><div><b>TCP / UDP Switch</b><small>تغییر امن Transport با Backup و Rollback</small></div></article><article><span class="feature-icon">⌁</span><div><b>DNS & Gateway</b><small>DNS push و Redirect Gateway قابل تنظیم</small></div></article><article><span class="feature-icon">♢</span><div><b>PKI Lifecycle</b><small>Certificate مستقل و Revoke واقعی</small></div></article><article><span class="feature-icon">✓</span><div><b>Fresh Exports</b><small>OVPN دانلودی با Runtime فعلی بازسازی می‌شود</small></div></article></section>',
    '<section class="panel protocol-directory"><div class="panel-head"><div><h3>کلاینت‌های OpenVPN</h3><span>PKI · OVPN · PROTECTED DELIVERY</span></div><div class="toolbar"><button class="ghost" data-action="openvpn-configure">تنظیمات پیشرفته</button><button class="ghost" data-action="refresh">بروزرسانی</button></div></div><div class="access-cards">'+(clients.length?clients.map(accessCard).join(''):'<div class="empty">Client ساخته نشده است.</div>')+'</div><div class="wizard-note"><b>Traffic accounting</b><span>Quota/Reset per-client برای OpenVPN تا زمانی که شمارش Runtime قابل اتکا اضافه نشود نمایش داده نمی‌شود؛ کنترل نمایشی و جعلی اضافه نشده است.</span></div></section>'
  ].join('');
}
async function protocols(renderToken=window.__viewRenderToken){
  title.textContent='مدیریت پورت‌ها';setPageContext('PORT & ENGINE MANAGEMENT');
  content.innerHTML='<div class="loading-state"><span class="spinner"></span><b>در حال بررسی پورت‌ها و Engineها…</b></div>';
  const [d,clients,matrix,modesData]=await Promise.all([
    api('/api/protocols'),api('/api/protocol-clients'),
    api('/api/protocols/endpoint-matrix').catch(()=>({rows:[],endpoint:'',all_ready:false})),
    api('/api/protocols/modes').catch(()=>({modes:[],constraints:{}}))
  ]);
  if(renderToken!==window.__viewRenderToken||activeView!=='protocols')return;
  window.__protocolData=d;window.__protocolClients=clients;window.__protocolModes=modesData;
  const x=d.xray||{},w=d.wireguard||{},o=d.openvpn||{},s=d.stunnel||{},ssh=d.ssh||{};
  const protocolModeCards=(modesData.modes||[]).map(m=>{
    const suggestionKey=m.id==='tcp'?'openvpn_tcp':m.id;
    const suggested=Number(modesData.port_plan?.suggested?.[suggestionKey]||0);
    const assigned=(m.ports||[]).filter(Boolean);
    const ports=assigned.length?assigned.join(', '):(suggested?('suggested '+suggested):'—');
    const actions={
      ikev2:'<button class="ghost" data-action="ikev2-setup">Configure</button><button class="soft" data-action="ikev2-user">New user</button><button class="soft" data-action="ikev2-users">Users</button>',
      wireguard:'<button class="ghost" data-action="nav" data-view="wireguard">Manage</button>',
      udp:'<button class="ghost" data-action="openvpn-mode" data-proto="udp">Use UDP</button>',
      tcp:'<button class="ghost" data-action="openvpn-tcp-fallback">Enable TCP fallback</button>',
      stealth:'<button class="ghost" data-action="stealth-setup">Configure</button>',
      wstunnel:'<button class="ghost" data-action="wstunnel-setup">Configure</button>'
    }[m.id]||'';
    return '<article class="protocol-mode-card '+(m.ready?'ready':'')+'"><div class="protocol-mode-top"><div class="protocol-mode-icon">'+protocolGlyph(m.id==='udp'||m.id==='tcp'?'openvpn':m.id)+'</div><div><b>'+htmlEsc(m.label)+'</b><span>'+htmlEsc(m.transport||'')+'</span></div><span class="status-chip '+(m.ready?'ok':'warn')+'">'+(m.ready?'READY':'SETUP')+'</span></div><div class="protocol-mode-meta"><span>Port</span><b>'+htmlEsc(ports)+'</b></div><div class="toolbar">'+actions+'</div></article>';
  }).join('');
  const fallbackPortRows=[
    {id:'ssh',label:'SSH',transport:'TCP',ports:[22],runtime:Boolean(ssh.service_active)},
    {id:'xray',label:'Xray',transport:'TCP/UDP by inbound',ports:(x.inbounds||[]).map(i=>i.port).filter(Boolean),runtime:Boolean(x.service_active)},
    {id:'wireguard',label:'WireGuard',transport:'UDP',ports:w.port?[w.port]:[],runtime:Boolean(w.service_active)},
    {id:'openvpn',label:'OpenVPN',transport:String(o.proto||'UDP').toUpperCase(),ports:o.port?[o.port]:[],runtime:Boolean(o.service_active)}
  ];
  const matrixRows=(matrix.rows||[]).length?matrix.rows:fallbackPortRows;
  const portRows=matrixRows.map(row=>{
    const ports=(row.ports||[]).length?(row.ports||[]).join(', '):'—';
    const view=row.id==='ssh'?'ssh':row.id==='xray'?'xray':row.id==='wireguard'?'wireguard':'openvpn';
    return '<div class="port-table-row"><div><b>'+htmlEsc(row.label)+'</b><span>'+htmlEsc(row.id==='xray'?'Xray inbounds':'Managed service')+'</span></div><div><b>'+htmlEsc(ports)+'</b></div><div><span class="transport-badge">'+htmlEsc(row.transport||'—')+'</span></div><div><span class="status-chip '+(row.runtime?'ok':'bad')+'">'+(row.runtime?'فعال':'غیرفعال')+'</span></div><div class="toolbar"><button class="ghost" data-action="nav" data-view="'+view+'">مدیریت</button></div></div>';
  }).join('');
  const engineRows=[
    ['SSH',ssh.installed,ssh.service_active,'ssh'],
    ['Xray Core',x.installed,x.service_active,'xray'],
    ['WireGuard',w.installed,w.service_active,'wireguard'],
    ['OpenVPN',o.installed,o.service_active,'openvpn'],
    ['Stunnel',s.installed,s.service_active,'services']
  ].map(e=>'<div class="service-control-row"><div class="service-logo-mini">'+htmlEsc(e[0].slice(0,1))+'</div><div><b>'+htmlEsc(e[0])+'</b><span>'+(e[1]?'نصب شده':'نصب نشده')+'</span></div><span class="status-chip '+(e[2]?'ok':e[1]?'warn':'bad')+'">'+(e[2]?'در حال اجرا':e[1]?'متوقف':'Missing')+'</span><button class="ghost" data-action="nav" data-view="'+e[3]+'">تنظیمات</button></div>').join('');
  content.innerHTML=[
    '<section class="protocol-page-header"><div class="protocol-page-title"><span class="protocol-page-icon xray">⌘</span><div><h2>مدیریت پورت‌ها</h2><p>نمایش پورت‌های فعال و کنترل Engineهای شبکه بدون تداخل TCP / UDP</p></div></div><div class="protocol-header-actions"><button class="primary" data-action="change-protocol">Change Protocol</button><button class="ghost" data-action="endpoint-matrix">بررسی Endpoint</button><button class="ghost" data-action="protocol-refresh">بروزرسانی</button></div></section>',
    '<section class="panel protocol-modes-panel"><div class="panel-head"><div><h3>Connection Modes</h3><span>IKEV2 · WIREGUARD · UDP · TCP · STEALTH · WSTUNNEL</span></div></div><div class="protocol-mode-grid">'+(protocolModeCards||'<div class="empty">Mode data unavailable.</div>')+'</div><div class="port-safe-note">هر Mode به Backend واقعی متصل است. OpenVPN UDP مستقل می‌ماند؛ TCP fallback جداست و Stealth فقط روی Listener عمومی جدا به آن وصل می‌شود.</div></section>',
    '<section class="panel port-plan-panel"><div class="panel-head"><div><h3>TCP Port Ownership</h3><span>REAL LISTENER PREFLIGHT</span></div></div><div class="port-plan-grid">'+((modesData.port_plan?.rows||[]).map(r=>'<article><span>'+htmlEsc(r.service)+'</span><b>TCP/'+Number(r.port||0)+'</b><small class="'+(r.occupied?'warn-text':'ok-text')+'">'+(r.occupied?('Owned: '+htmlEsc(r.owner||'host service')):'Free now')+'</small></article>').join('')||'<div class="empty">Port plan unavailable.</div>')+'</div>'+((modesData.port_plan?.blockers?.openvpn_tcp||[]).length?'<div class="wizard-note danger-note"><b>OpenVPN TCP blockers</b><span>'+htmlEsc(modesData.port_plan.blockers.openvpn_tcp.join(' · '))+'</span></div>':'')+((modesData.port_plan?.blockers?.stealth||[]).length?'<div class="wizard-note danger-note"><b>Stealth blockers</b><span>'+htmlEsc(modesData.port_plan.blockers.stealth.join(' · '))+'</span></div>':'')+'<div class="port-safe-note">'+htmlEsc(modesData.port_plan?.note||'TCP/443 has one owner; UDP/443 may coexist independently.')+'</div></section>',
    '<section class="panel port-management-panel"><div class="panel-head"><div><h3>لیست پورت‌های فعال</h3><span>TRANSPORT-AWARE ALLOCATION</span></div></div><div class="port-table-head"><span>پروتکل</span><span>پورت</span><span>نوع اتصال</span><span>وضعیت</span><span>عملیات</span></div><div class="port-table-body">'+(portRows||'<div class="empty">پورت مدیریت‌شده‌ای پیدا نشد.</div>')+'</div><div class="port-safe-note">✓ بررسی تداخل پورت‌ها بر اساس Transport انجام می‌شود؛ TCP/443 و UDP/443 می‌توانند هم‌زمان فعال باشند.</div></section>',
    '<section class="split-grid"><div class="panel"><div class="panel-head"><div><h3>Engineها</h3><span>INSTALL / RUNTIME</span></div></div><div class="service-control-list">'+engineRows+'</div></div><div class="panel"><div class="panel-head"><div><h3>Xray Inbounds</h3><span>'+Number((x.inbounds||[]).length)+' DETECTED</span></div></div><div class="engine-inbounds">'+((x.inbounds||[]).length?(x.inbounds||[]).map(i=>'<div class="engine-inbound"><div><b>'+htmlEsc(String(i.protocol||'').toUpperCase())+'</b><span>'+htmlEsc(i.tag||'Inbound')+'</span></div><div><b>:'+Number(i.port||0)+'</b><span>'+Number(i.clients||0)+' users</span></div></div>').join(''):'<div class="empty compact">Inbound وجود ندارد.</div>')+'</div></div></section>',
    '<section class="panel"><div class="panel-head"><div><h3>Client Policy Snapshot</h3><span>'+clients.length+' XRAY RECORDS</span></div><button class="ghost" data-action="nav" data-view="xray">مدیریت کاربران Xray</button></div><div class="protocol-policy-mini">'+(clients.length?clients.slice(0,8).map(pc=>'<div><div><b>'+htmlEsc(pc.name)+'</b><span>'+htmlEsc(String(pc.protocol||'').toUpperCase())+'</span></div><strong class="'+(pc.enabled&&!pc.expired?'ok-text':'bad-text')+'">'+(pc.enabled&&!pc.expired?'Active':'Attention')+'</strong></div>').join(''):'<div class="empty compact">Client ثبت نشده است.</div>')+'</div></section>'
  ].join('');
}
function createXrayTunnel(){modalRoot.innerHTML=`<div class="modal-backdrop" onclick="if(event.target===this)closeModal()"><div class="modal"><div class="modal-head"><div><div class="eyebrow">XRAY TUNNEL</div><h3>Port Forward / Dokodemo</h3></div><button class="close-btn" onclick="closeModal()">×</button></div><div class="form-grid"><label>Name<input id="tnName" value="tunnel01"></label><label>Listen port<input id="tnListen" type="number" min="1" max="65535" value="8443"></label><label>Target host<input id="tnHost" placeholder="10.0.0.2 or example.com"></label><label>Target port<input id="tnPort" type="number" min="1" max="65535" value="443"></label><label>Network<select id="tnNetwork"><option value="tcp,udp">TCP + UDP</option><option value="tcp">TCP</option><option value="udp">UDP</option></select></label></div><div class="notice">Config قبل از Apply توسط Xray validate می‌شود و در خطا Rollback انجام می‌شود.</div><div class="toolbar"><button class="primary" onclick="submitXrayTunnel()">Create Tunnel</button><button class="ghost" onclick="closeModal()">Cancel</button></div></div></div>`}
async function submitXrayTunnel(){const payload={name:tnName.value.trim(),listen_port:Number(tnListen.value),target_host:tnHost.value.trim(),target_port:Number(tnPort.value),network:tnNetwork.value};if(!payload.name||!payload.target_host||!payload.listen_port||!payload.target_port){alert('فیلدهای اصلی را کامل کنید.');return}try{const r=await api('/api/protocols/xray/tunnels',{method:'POST',body:JSON.stringify(payload)});closeModal();toast('Tunnel '+r.listen_port+' → '+r.target_host+':'+r.target_port+' created');await protocols()}catch(e){alert(e.message)}}


function protocolModeDescription(id){
  return {
    ikev2:'IPsec/IKEv2 با StrongSwan؛ مناسب Clientهای Native سیستم‌عامل.',
    wireguard:'WireGuard سریع با Peer، QR، Handshake و Traffic واقعی.',
    udp:'OpenVPN روی UDP؛ حالت کم‌تاخیر با Port قابل انتخاب.',
    tcp:'OpenVPN روی TCP؛ برای شبکه‌هایی که UDP مشکل دارد.',
    stealth:'OpenVPN پشت TLS/Stunnel؛ نیازمند Certificate معتبر.',
    wstunnel:'WireGuard داخل WSS/WebSocket؛ نیازمند Client WStunnel.'
  }[id]||'';
}

async function openChangeProtocol(){
  let data=window.__protocolModes;
  if(!data||!Array.isArray(data.modes)){
    data=await api('/api/protocols/modes');
    window.__protocolModes=data;
  }
  const order=['ikev2','wireguard','udp','tcp','stealth','wstunnel'];
  const byId=Object.fromEntries((data.modes||[]).map(x=>[x.id,x]));
  const rows=order.map(id=>{
    const m=byId[id]||{id,label:id.toUpperCase(),ports:[],transport:'',ready:false,status:{}};
    const port=(m.ports||[]).filter(Boolean).join(' / ')||'Setup';
    const iconKind=(id==='udp'||id==='tcp')?'openvpn':id;
    return '<button class="change-protocol-row '+(m.ready?'ready':'')+'" data-action="protocol-mode-select" data-mode="'+htmlEsc(id)+'">'+
      '<span class="change-protocol-icon">'+protocolGlyph(iconKind)+'</span>'+
      '<span class="change-protocol-copy"><b>'+htmlEsc(m.label)+'</b><small>'+htmlEsc(protocolModeDescription(id))+'</small></span>'+
      '<span class="change-protocol-port">'+htmlEsc(port)+'</span>'+
      '<span class="change-protocol-state '+(m.ready?'ok':'')+'">'+(m.ready?'READY':'SETUP')+'</span>'+
      '<span class="change-protocol-arrow">›</span>'+
    '</button>';
  }).join('');
  modalRoot.innerHTML=[
    '<div class="modal-backdrop change-protocol-backdrop"><div class="modal change-protocol-modal">',
      '<div class="change-protocol-head"><div class="change-protocol-mark">↻</div><div><span class="eyebrow">CONNECTION MODE</span><h3>Change Protocol</h3><p>پروتکل یا Transport موردنظر را انتخاب کن. هر گزینه به Backend واقعی Makia وصل است.</p></div><button class="close-btn" data-action="modal-close">×</button></div>',
      '<div class="change-protocol-list">'+rows+'</div>',
      '<div class="change-protocol-foot"><span>TCP/443 بین HTTPS، OpenVPN TCP، Stealth و WStunnel قابل اشتراک هم‌زمان نیست؛ Makia تداخل واقعی Port را Block می‌کند.</span><button class="ghost" data-action="modal-close">Cancel</button></div>',
    '</div></div>'
  ].join('');
}

async function selectProtocolMode(mode){
  const data=window.__protocolModes||{};
  const current=(data.modes||[]).find(x=>x.id===mode)||{};
  closeModal();
  if(mode==='ikev2'){
    if(current.ready)await openIKEv2Users(); else await setupIKEv2();
    return;
  }
  if(mode==='wireguard'){await switchView('wireguard');return}
  if(mode==='udp'){await switchOpenVPNMode('udp');return}
  if(mode==='tcp'){await ensureOpenVPNTCPFallback();return}
  if(mode==='stealth'){await setupStealth();return}
  if(mode==='wstunnel'){await setupWStunnel();return}
}

async function setupIKEv2(){
  const domain=prompt('IKEv2 domain (must already have valid HTTPS certificate)',window.PANEL_DOMAIN||'');if(!domain)return;
  const cidr=prompt('IKEv2 client CIDR','10.77.0.0/24')||'10.77.0.0/24';
  const dns=prompt('IKEv2 DNS','1.1.1.1')||'1.1.1.1';
  try{await api('/api/protocols/ikev2/bootstrap',{method:'POST',body:JSON.stringify({domain,cidr,dns})});toast('IKEv2 configured');await protocols()}catch(e){alert('IKEv2: '+e.message)}
}
async function createIKEv2User(){
  const name=prompt('IKEv2 username','user001');if(!name)return;
  const password=prompt('Password (leave empty to generate)','')||'';
  try{const r=await api('/api/protocols/ikev2/users',{method:'POST',body:JSON.stringify({name,password})});configModal('IKEv2 · '+name,r.profile,name+'-ikev2.txt')}catch(e){alert('IKEv2 user: '+e.message)}
}
async function openIKEv2Users(){
  try{
    const r=await api('/api/protocols/ikev2/users'),users=r.users||[];
    modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="modal-head"><div><div class="eyebrow">IKEV2 USERS</div><h3>StrongSwan users</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="service-control-list">'+(users.length?users.map(x=>'<div class="service-row"><div><b>'+htmlEsc(x.name)+'</b><span>EAP-MSCHAPv2</span></div><button class="danger" data-action="ikev2-user-delete" data-name="'+dataEnc(x.name)+'">Revoke</button></div>').join(''):'<div class="empty">هنوز کاربر IKEv2 ساخته نشده است.</div>')+'</div><div class="toolbar"><button class="primary" data-action="ikev2-user">New user</button><button class="ghost" data-action="modal-close">Close</button></div></div></div>';
  }catch(e){alert('IKEv2 users: '+e.message)}
}
async function revokeIKEv2User(name){
  if(!confirm('کاربر IKEv2 '+name+' لغو شود؟'))return;
  try{await api('/api/protocols/ikev2/users/'+encodeURIComponent(name),{method:'DELETE'});toast('IKEv2 user revoked');await openIKEv2Users()}catch(e){alert('IKEv2 revoke: '+e.message)}
}

async function switchOpenVPNMode(proto){
  const current=window.__protocolData?.openvpn||{},opts=current.options||{};
  const suggested=proto==='udp'?443:8443;
  const port=Number(prompt('OpenVPN '+proto.toUpperCase()+' port',String(current.port||suggested)));if(!port)return;
  const payload={port,proto,dns_servers:opts.dns_servers||['1.1.1.1','8.8.8.8'],keepalive_ping:Number(opts.keepalive_ping||10),keepalive_timeout:Number(opts.keepalive_timeout||120),redirect_gateway:opts.redirect_gateway!==false,client_to_client:Boolean(opts.client_to_client)};
  try{await api('/api/protocols/openvpn/configure',{method:'POST',body:JSON.stringify(payload)});toast('OpenVPN switched to '+proto.toUpperCase());await protocols()}catch(e){alert('OpenVPN '+proto.toUpperCase()+': '+e.message)}
}
async function ensureOpenVPNTCPFallback(){
  const current=window.__protocolModes?.modes?.find(x=>x.id==='tcp');
  const suggested=Number(current?.ports?.[0]||8443);
  const port=Number(prompt('OpenVPN TCP fallback port',String(suggested)));if(!port)return;
  try{
    await api('/api/protocols/openvpn/tcp-fallback',{method:'POST',body:JSON.stringify({port})});
    toast('OpenVPN TCP fallback active without changing UDP users');
    if(activeView==='protocols')await protocols(); else await currentView();
  }catch(e){alert('OpenVPN TCP fallback: '+e.message)}
}

async function setupStealth(){
  const domain=prompt('Stealth TLS domain',window.PANEL_DOMAIN||'');if(!domain)return;
  const port=Number(prompt('Public Stealth TLS port (443 only if HTTPS is not using it)','9443'));if(!port)return;
  try{const r=await api('/api/protocols/stealth/bootstrap',{method:'POST',body:JSON.stringify({domain,port})});configModal('Stealth TLS client',r.client_stunnel_config,'makia-stealth-stunnel.conf');toast('Stealth listener ready')}catch(e){alert('Stealth: '+e.message)}
}
async function setupWStunnel(){
  const domain=prompt('WStunnel WSS domain',window.PANEL_DOMAIN||'');if(!domain)return;
  const port=Number(prompt('Public WStunnel TCP port','8444'));if(!port)return;
  try{const r=await api('/api/protocols/wstunnel/bootstrap',{method:'POST',body:JSON.stringify({domain,port,path_prefix:''})});configModal('WStunnel client command',r.client_command+'\n\nWireGuard Endpoint: '+r.wireguard_endpoint,'makia-wstunnel-client.txt');toast('WStunnel listener ready')}catch(e){alert('WStunnel: '+e.message)}
}

async function installProtocol(component){if(!confirm('Install '+component+' and required packages?'))return;try{await api('/api/protocols/install',{method:'POST',body:JSON.stringify({component})});toast(component+' installed');await protocols()}catch(e){alert(e.message)}}
function showXrayInbounds(){document.querySelector('.protocol-grid')?.nextElementSibling?.scrollIntoView({behavior:'smooth'})}
function createXrayInbound(){modalRoot.innerHTML=`<div class="modal-backdrop" onclick="if(event.target===this)closeModal()"><div class="modal"><div class="modal-head"><div><div class="eyebrow">XRAY CLIENT + INBOUND</div><h3>ساخت دسترسی Xray</h3></div><button class="close-btn" onclick="closeModal()">×</button></div><div class="form-grid"><label>Protocol<select id="xiProtocol" onchange="syncXrayForm()"><option value="vless">VLESS</option><option value="vmess">VMess</option><option value="trojan">Trojan</option><option value="shadowsocks">Shadowsocks</option><option value="hysteria2">Hysteria2</option><option value="http">HTTP Proxy</option><option value="socks">SOCKS5</option></select></label><label>Transport<select id="xiTransport" onchange="syncXrayForm()"><option value="tcp">RAW / TCP</option><option value="ws">WebSocket</option><option value="grpc">gRPC</option><option value="httpupgrade">HTTPUpgrade</option><option value="xhttp">XHTTP</option><option value="kcp">mKCP</option></select></label><label>Security<select id="xiSecurity" onchange="syncXrayForm()"><option value="none">None</option><option value="tls">TLS</option><option value="reality">REALITY</option></select></label><label>Port<input id="xiPort" type="number" min="1" max="65535" value="2087"></label><label>Client name<input id="xiName" value="client01"></label><label>Public domain / IP<input id="xiEndpoint" value="${window.PANEL_DOMAIN||location.hostname}"></label><label id="xiPathWrap">Path / Service<input id="xiPath" value="/makia"></label><label id="xiSniWrap">Domain / SNI<input id="xiSni" value="${window.PANEL_DOMAIN||''}" placeholder="vpn.example.com"></label><label id="xiRealityWrap">REALITY target<input id="xiRealityDest" value="www.cloudflare.com:443" placeholder="www.example.com:443"></label><label>Traffic quota (GB)<input id="xiQuota" type="number" min="0" step="1" value="50"><div class="password-tools quota-tools"><button class="soft" onclick="xiQuota.value=0">∞</button><button class="soft" onclick="xiQuota.value=10">10</button><button class="soft" onclick="xiQuota.value=20">20</button><button class="soft recommended" onclick="xiQuota.value=50">50</button><button class="soft" onclick="xiQuota.value=100">100</button><button class="soft" onclick="xiQuota.value=200">200</button><button class="soft" onclick="xiQuota.value=500">500</button></div><span class="muted">0 = Unlimited</span></label><label>Expiry days<input id="xiDays" type="number" min="0" max="3650" value="30"><div class="password-tools duration-tools"><button class="soft" onclick="xiDays.value=1">1D</button><button class="soft" onclick="xiDays.value=3">3D</button><button class="soft" onclick="xiDays.value=7">7D</button><button class="soft" onclick="xiDays.value=15">15D</button><button class="soft recommended" onclick="xiDays.value=30">30D</button><button class="soft" onclick="xiDays.value=60">60D</button><button class="soft" onclick="xiDays.value=90">90D</button><button class="soft" onclick="xiDays.value=0">∞</button></div></label><label>Traffic reset cycle<input id="xiResetDays" type="number" min="0" max="3650" value="30"><div class="password-tools"><button class="soft" onclick="xiResetDays.value=0">Never</button><button class="soft" onclick="xiResetDays.value=7">7D</button><button class="soft recommended" onclick="xiResetDays.value=30">30D</button><button class="soft" onclick="xiResetDays.value=60">60D</button><button class="soft" onclick="xiResetDays.value=90">90D</button></div><span class="muted">حجم مصرفی در شروع هر دوره صفر می‌شود.</span></label><label>IP / Device limit<input id="xiIpLimit" type="number" min="1" max="50" value="1"><div class="password-tools"><button class="soft recommended" onclick="xiIpLimit.value=1">1</button><button class="soft" onclick="xiIpLimit.value=2">2</button><button class="soft" onclick="xiIpLimit.value=3">3</button><button class="soft" onclick="xiIpLimit.value=5">5</button><button class="soft" onclick="xiIpLimit.value=10">10</button></div><span class="muted">با Online-IP API هسته Xray مانیتور و توسط Policy Worker enforce می‌شود؛ روی Coreهای فاقد این API فقط وضعیت Unavailable نشان داده می‌شود.</span></label></div><div id="xiCompatNote" class="notice"></div><div class="toolbar"><button class="primary" onclick="submitXrayInbound()">Create, Validate & Restart</button><button class="ghost" onclick="closeModal()">Cancel</button></div></div></div>`;syncXrayForm()}
function syncXrayForm(){
  const p=xiProtocol.value;
  if(p==='hysteria2'){xiTransport.value='tcp';xiSecurity.value='tls';xiTransport.disabled=true;xiSecurity.disabled=true}
  else if(['http','socks'].includes(p)){xiTransport.value='tcp';xiSecurity.value='none';xiTransport.disabled=true;xiSecurity.disabled=true}
  else{xiTransport.disabled=false;xiSecurity.disabled=false}
  const t=p==='hysteria2'?'hysteria':xiTransport.value,s=p==='hysteria2'?'tls':xiSecurity.value;
  const pathNeeded=['ws','grpc','httpupgrade','xhttp'].includes(t)&&!['http','socks'].includes(p);
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
  else if(t==='kcp') note='mKCP روی Xray 26.3.27 بدون header/seed قدیمی ساخته می‌شود؛ گزینه‌های حذف‌شده‌ی Core در Guided mode نمایش داده نمی‌شوند.';
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
    '<div class="delivery-actions"><button class="primary" data-action="client-portal" data-kind="xray" data-key="'+dataEnc(String(r.client_id))+'" data-name="'+dataEnc(r.name)+'">'+htmlEsc(tr('لینک اختصاصی کاربر','Client portal link'))+'</button><button class="ghost" data-action="protected-export" data-kind="xray" data-key="'+dataEnc(String(r.client_id))+'" data-name="'+dataEnc(r.name)+'">'+htmlEsc(tr('بسته رمزدار','Protected ZIP'))+'</button><button class="ghost" data-action="native-export" data-kind="xray" data-key="'+dataEnc(String(r.client_id))+'">'+htmlEsc(tr('فایل پروفایل','Profile file'))+'</button><button class="ghost" data-action="copy-target" data-target="xrayShare">'+htmlEsc(tr('کپی لینک','Copy link'))+'</button><button class="ghost" data-action="client-guide" data-kind="xray">'+htmlEsc(tr('راهنمای اتصال','Connection guide'))+'</button></div>',
    '<div class="wizard-note"><b>Subscription ready</b><span>Profile/QR/Subscription metadata داخل بسته تحویل هم قرار می‌گیرد.</span></div></div></div>'
  ].join('');
  document.getElementById('xrayShare').value=r.share_link||'';
}

let xrayBuilderCaps=null;

async function openXrayInboundBuilder(){
  try{
    const [caps,defs,stack]=await Promise.all([
      api('/api/protocols/xray/inbound-capabilities'),
      api('/api/accounts/new-defaults').catch(()=>({username:'user001'})),
      api('/api/protocols')
    ]);
    xrayBuilderCaps=caps;
    const defaults=window.__operatorSettings?.defaults||{};
    const endpoint=window.PANEL_DOMAIN||location.hostname;
    const endpointMode=/^\d{1,3}(?:\.\d{1,3}){3}$/.test(endpoint)?'ip':'domain';
    const used=new Set((stack?.xray?.inbounds||[]).map(x=>Number(x.port)));
    let port=Number(defaults.xray_port||2087);
    while(used.has(port)&&port<65535)port++;
    modalRoot.innerHTML=[
      '<div class="modal-backdrop"><div class="modal xray-builder-modal">',
        '<div class="wizard-head"><div><div class="eyebrow">XRAY INBOUND CENTER</div><h3>ساخت Inbound حرفه‌ای</h3><p>ساختار Inbound → Client → Transport → Security → Sniffing → Sockopt</p></div><button class="close-btn" data-action="modal-close">×</button></div>',
        '<div class="xray-builder-grid">',
          '<section class="xray-builder-section"><div class="section-title"><b>1. Inbound</b><span>مشخصات سرویس</span></div><div class="form-grid two">',
            '<label>Remark / نام Inbound<input id="xbRemark" maxlength="80" value="Makia-'+port+'"></label>',
            '<label>Protocol<select id="xbProtocol"></select></label>',
            '<label>Listen<input id="xbListen" dir="ltr" value="0.0.0.0"><span class="muted">0.0.0.0 = همه Interfaceها</span></label>',
            '<label>Port<input id="xbPort" type="number" min="1" max="65535" value="'+port+'"></label>',
            '<label>Endpoint mode<select id="xbEndpointMode"><option value="domain" '+(endpointMode==='domain'?'selected':'')+'>Domain</option><option value="ip" '+(endpointMode==='ip'?'selected':'')+'>IP</option></select></label>',
            '<label>Client endpoint<input id="xbEndpoint" dir="ltr" value="'+htmlEsc(endpoint)+'"><span class="muted">در Share Link/QR استفاده می‌شود.</span></label>',
          '</div></section>',
          '<section class="xray-builder-section"><div class="section-title"><b>2. Client & limits</b><span>اولین Client این Inbound</span></div><div class="form-grid two">',
            '<label>Client / Email<input id="xbName" value="'+htmlEsc(defs.username||'user001')+'" maxlength="48"></label>',
            '<label>Credential (اختیاری)<input id="xbCredential" dir="ltr" placeholder="خالی = تولید خودکار"><span class="muted">برای VLESS/VMess باید UUID معتبر باشد.</span></label>',
            '<label>Traffic quota GB<input id="xbQuota" type="number" min="0" step="1" value="'+Number(defaults.xray_quota_gb??50)+'"><span class="muted">0 = Unlimited</span></label>',
            '<label>Expiry days<input id="xbDays" type="number" min="0" max="3650" value="'+Number(defaults.xray_expire_days??30)+'"><span class="muted">0 = بدون انقضا</span></label>',
            '<label>IP / Device limit<input id="xbIpLimit" type="number" min="1" max="50" value="'+Number(defaults.xray_ip_limit||1)+'"></label>',
            '<label>Traffic reset days<input id="xbReset" type="number" min="0" max="3650" value="'+Number(defaults.xray_reset_days??30)+'"><span class="muted">0 = دستی</span></label>',
            '<label id="xbFlowWrap">Flow<select id="xbFlow"><option value="">None</option><option value="xtls-rprx-vision">xtls-rprx-vision</option></select></label>',
            '<label id="xbSsMethodWrap">Shadowsocks method<select id="xbSsMethod"></select></label>',
          '</div></section>',
          '<section class="xray-builder-section"><div class="section-title"><b>3. Transport</b><span>Raw/TCP · WS · gRPC · HTTPUpgrade · XHTTP · mKCP · Hysteria</span></div><div class="form-grid two">',
            '<label>Transport<select id="xbTransport"></select></label>',
            '<label>Security<select id="xbSecurity"></select></label>',
          '</div><div id="xbTransportFields" class="form-grid two"></div></section>',
          '<section class="xray-builder-section"><div class="section-title"><b>4. Security</b><span>None / TLS / REALITY</span></div><div id="xbSecurityFields" class="form-grid two"></div><div id="xbSecurityNote" class="wizard-note"></div></section>',
          '<section class="xray-builder-section"><div class="section-title"><b>5. Sniffing</b><span>مثل Inboundهای حرفه‌ای 3x-ui</span></div><div class="form-grid two">',
            '<label class="check-row"><input id="xbSniffEnabled" type="checkbox" checked> Enable sniffing</label>',
            '<label>Dest override<input id="xbSniffDest" value="http,tls,quic" dir="ltr"></label>',
            '<label class="check-row"><input id="xbSniffRouteOnly" type="checkbox" checked> Route only</label>',
            '<label class="check-row"><input id="xbSniffMetadata" type="checkbox"> Metadata only</label>',
          '</div></section>',
          '<details class="xray-builder-section pro-advanced"><summary><span>6. Sockopt / Network advanced</span><small>TCP Fast Open · congestion · domain strategy · mark · interface · TProxy</small></summary><div class="form-grid two">',
            '<label class="check-row"><input id="xbTcpFastOpen" type="checkbox"> TCP Fast Open</label>',
            '<label class="check-row"><input id="xbTcpNoDelay" type="checkbox"> TCP NoDelay</label>',
            '<label>TCP congestion<select id="xbCongestion"><option value="">OS default</option><option value="bbr">BBR</option><option value="cubic">Cubic</option><option value="reno">Reno</option></select></label>',
            '<label>Domain strategy<select id="xbDomainStrategy"><option value="">Default</option><option>AsIs</option><option>UseIP</option><option>UseIPv4</option><option>ForceIP</option><option>ForceIPv4</option></select></label>',
            '<label>SO_MARK<input id="xbMark" type="number" min="0" value="0"></label>',
            '<label>Interface<input id="xbInterface" dir="ltr" placeholder="مثلاً eth0"></label>',
            '<label>TProxy<select id="xbTproxy"><option value="">Off/default</option><option value="off">off</option><option value="redirect">redirect</option><option value="tproxy">tproxy</option></select></label>',
          '</div></details>',
          '<details class="xray-builder-section pro-advanced"><summary><span>7. Core options JSON</span><small>برای گزینه‌های خاص Xray که در فرم نیستند</small></summary><div class="wizard-note"><b>Validated, not raw apply</b><span>این JSON فقط داخل streamSettings Merge می‌شود؛ method/security/TLS/REALITY از فیلدهای معتبر بالا کنترل می‌شوند و کل Config با خود Xray Core تست می‌شود.</span></div><textarea id="xbExtraStream" class="config-output small" spellcheck="false">{}</textarea></details>',
        '</div>',
        '<div id="xbCompatNote" class="wizard-note"><b>Compatibility</b><span>فقط ترکیب‌های معتبر برای Protocol انتخابی نمایش داده می‌شوند.</span></div>',
        '<div class="wizard-footer"><button class="ghost" data-action="modal-close">Cancel</button><button class="ghost" data-action="xray-advanced">Advanced JSON</button><button class="primary" data-action="xray-builder-create">Validate & Create</button></div>',
      '</div></div>'
    ].join('');
    const p=document.getElementById('xbProtocol');
    p.innerHTML=Object.keys(caps.protocols||{}).map(x=>'<option value="'+htmlEsc(x)+'">'+htmlEsc(x.toUpperCase())+'</option>').join('');
    const preferred=String(defaults.xray_protocol||'vless').toLowerCase();
    if(caps.protocols?.[preferred])p.value=preferred;
    document.getElementById('xbSsMethod').innerHTML=(caps.shadowsocks_methods||[]).map(x=>'<option value="'+htmlEsc(x)+'">'+htmlEsc(x)+'</option>').join('');
    p.addEventListener('change',syncXrayInboundBuilder);
    document.getElementById('xbTransport').addEventListener('change',syncXrayInboundBuilder);
    document.getElementById('xbSecurity').addEventListener('change',syncXrayInboundBuilder);
    syncXrayInboundBuilder();
  }catch(e){alert('Xray Inbound Center: '+e.message)}
}

function xbValue(id,fallback=''){const el=document.getElementById(id);return el?el.value:fallback}
function xbChecked(id){const el=document.getElementById(id);return !!(el&&el.checked)}

function syncXrayInboundBuilder(){
  if(!xrayBuilderCaps)return;
  const protocol=xbValue('xbProtocol','vless');
  const spec=xrayBuilderCaps.protocols?.[protocol]||{transports:['tcp'],security:['none']};
  const t=document.getElementById('xbTransport'),s=document.getElementById('xbSecurity');
  const oldT=t.value,oldS=s.value;
  t.innerHTML=(spec.transports||[]).map(x=>'<option value="'+htmlEsc(x)+'">'+htmlEsc(x==='tcp'?'TCP / RAW':x.toUpperCase())+'</option>').join('');
  if((spec.transports||[]).includes(oldT))t.value=oldT;
  s.innerHTML=(spec.security||[]).map(x=>'<option value="'+htmlEsc(x)+'">'+htmlEsc(x.toUpperCase())+'</option>').join('');
  if((spec.security||[]).includes(oldS))s.value=oldS;
  const transport=t.value,security=s.value;
  if(security==='reality'&&!['tcp','grpc','xhttp'].includes(transport)){
    const fallback=(spec.security||[]).includes('none')?'none':((spec.security||[]).includes('tls')?'tls':spec.security[0]);
    s.value=fallback;
  }
  const finalSecurity=s.value;
  const tf=document.getElementById('xbTransportFields');
  const commonPath='<label>Path / Service<input id="xbPath" dir="ltr" value="/makia"></label>';
  if(transport==='tcp'){
    tf.innerHTML=[
      '<label>RAW header<select id="xbHeaderType"><option value="none">None</option><option value="http">HTTP camouflage</option></select></label>',
      '<label class="check-row"><input id="xbAcceptProxy" type="checkbox"> Accept PROXY protocol</label>',
      '<label>HTTP Host<input id="xbHttpHost" dir="ltr" placeholder="example.com"></label>',
      '<label>HTTP Path<input id="xbHttpPath" dir="ltr" value="/"></label>'
    ].join('');
  }else if(transport==='ws'){
    tf.innerHTML=commonPath+'<label>Host<input id="xbHost" dir="ltr"></label><label>Heartbeat seconds<input id="xbHeartbeat" type="number" min="0" max="3600" value="0"></label><label class="check-row"><input id="xbAcceptProxy" type="checkbox"> Accept PROXY protocol</label><label>Headers JSON<textarea id="xbHeaders" spellcheck="false">{}</textarea></label>';
  }else if(transport==='grpc'){
    tf.innerHTML='<label>Service name<input id="xbServiceName" dir="ltr" value="makia"></label><label>Authority<input id="xbAuthority" dir="ltr"></label><label class="check-row"><input id="xbMultiMode" type="checkbox"> Multi mode</label>';
  }else if(transport==='httpupgrade'){
    tf.innerHTML=commonPath+'<label>Host<input id="xbHost" dir="ltr"></label><label class="check-row"><input id="xbAcceptProxy" type="checkbox"> Accept PROXY protocol</label><label>Headers JSON<textarea id="xbHeaders" spellcheck="false">{}</textarea></label>';
  }else if(transport==='xhttp'){
    tf.innerHTML=commonPath+'<label>Host<input id="xbHost" dir="ltr"></label><label>Mode<select id="xbXhttpMode">'+(xrayBuilderCaps.xhttp_modes||[]).map(x=>'<option value="'+htmlEsc(x)+'">'+htmlEsc(x)+'</option>').join('')+'</select></label><label>X Padding<input id="xbXPadding" dir="ltr" value="100-1000"></label>';
  }else if(transport==='kcp'){
    tf.innerHTML='<label>MTU<input id="xbKcpMtu" type="number" value="1350" min="576" max="1460"></label><label>TTI ms<input id="xbKcpTti" type="number" value="20" min="10" max="100"></label><label>Uplink capacity MB/s<input id="xbKcpUp" type="number" value="5" min="1"></label><label>Downlink capacity MB/s<input id="xbKcpDown" type="number" value="20" min="1"></label><label>CWND multiplier<input id="xbKcpCwnd" type="number" value="1" min="1"></label><label>Max sending window<input id="xbKcpWindow" type="number" value="2097152" min="576"></label>';
  }else if(transport==='hysteria'){
    tf.innerHTML='<label>UDP idle timeout<input id="xbHyIdle" type="number" value="60" min="2" max="600"></label>';
  }else tf.innerHTML='';

  const sf=document.getElementById('xbSecurityFields'),note=document.getElementById('xbSecurityNote');
  if(finalSecurity==='tls'){
    sf.innerHTML='<label>Server Name / SNI<input id="xbSni" dir="ltr" placeholder="vpn.example.com"></label><label>ALPN<input id="xbAlpn" dir="ltr" value="'+(transport==='hysteria'?'h3':'h2,http/1.1')+'"></label>';
    note.innerHTML='<b>TLS</b><span>Certificate همین SNI باید قبلاً در Settings → Domain & TLS موجود باشد. Makia همان Certificate واقعی را به Xray متصل می‌کند.</span>';
  }else if(finalSecurity==='reality'){
    sf.innerHTML='<label>Server Name / SNI<input id="xbSni" dir="ltr" value="www.microsoft.com"></label><label>REALITY target<input id="xbRealityDest" dir="ltr" value="www.microsoft.com:443"></label><label>Fingerprint<input id="xbFingerprint" value="chrome"></label><label>Short ID<input id="xbShortId" dir="ltr" placeholder="خالی = تولید خودکار"></label><label>Spider X<input id="xbSpiderX" dir="ltr" value="/"></label><label>xver<select id="xbXver"><option value="0">0</option><option value="1">1</option><option value="2">2</option></select></label>';
    note.innerHTML='<b>REALITY</b><span>Private/Public X25519 و Short ID در Backend ساخته می‌شوند؛ Private Key در Share Link قرار نمی‌گیرد.</span>';
  }else{
    sf.innerHTML='';
    note.innerHTML='<b>Security = NONE</b><span>هیچ TLS/REALITY اجباری نیست. این انتخاب عمداً Plain transport است و باید خودت مناسب بودنش برای شبکه را تعیین کنی.</span>';
  }
  const flowWrap=document.getElementById('xbFlowWrap');
  if(flowWrap)flowWrap.style.display=(protocol==='vless'&&((transport==='tcp'&&['tls','reality'].includes(finalSecurity))||transport==='xhttp'))?'':'none';
  if(flowWrap&&flowWrap.style.display==='none')document.getElementById('xbFlow').value='';
  const ss=document.getElementById('xbSsMethodWrap');
  if(ss)ss.style.display=protocol==='shadowsocks'?'':'none';
  const note2=document.getElementById('xbCompatNote');
  note2.innerHTML='<b>'+htmlEsc(protocol.toUpperCase())+'</b><span>'+htmlEsc(transport.toUpperCase())+' + '+htmlEsc(finalSecurity.toUpperCase())+' · Config قبل از Commit توسط Xray Core validate می‌شود و در Failure Rollback دارد.</span>';
}

function xrayBuilderJson(id){
  const raw=xbValue(id,'{}').trim()||'{}';
  try{
    const obj=JSON.parse(raw);
    if(!obj||Array.isArray(obj)||typeof obj!=='object')throw new Error('JSON object لازم است');
    return obj;
  }catch(e){throw new Error(id+': '+e.message)}
}

async function createXrayInboundBuilder(){
  try{
    const protocol=xbValue('xbProtocol'),transport=xbValue('xbTransport'),security=xbValue('xbSecurity');
    const options={
      path:xbValue('xbPath','/'),
      host:xbValue('xbHost',''),
      headers:document.getElementById('xbHeaders')?xrayBuilderJson('xbHeaders'):{},
      heartbeat_period:Number(xbValue('xbHeartbeat','0')||0),
      accept_proxy_protocol:xbChecked('xbAcceptProxy'),
      header_type:xbValue('xbHeaderType','none'),
      http_host:xbValue('xbHttpHost',''),
      http_path:xbValue('xbHttpPath','/'),
      service_name:xbValue('xbServiceName',''),
      authority:xbValue('xbAuthority',''),
      multi_mode:xbChecked('xbMultiMode'),
      xhttp_mode:xbValue('xbXhttpMode','auto'),
      x_padding_bytes:xbValue('xbXPadding',''),
      mtu:Number(xbValue('xbKcpMtu','1350')||1350),
      tti:Number(xbValue('xbKcpTti','20')||20),
      uplink_capacity:Number(xbValue('xbKcpUp','5')||5),
      downlink_capacity:Number(xbValue('xbKcpDown','20')||20),
      cwnd_multiplier:Number(xbValue('xbKcpCwnd','1')||1),
      max_sending_window:Number(xbValue('xbKcpWindow','2097152')||2097152),
      udp_idle_timeout:Number(xbValue('xbHyIdle','60')||60),
      server_name:xbValue('xbSni',''),
      alpn:xbValue('xbAlpn',''),
      reality_dest:xbValue('xbRealityDest',''),
      fingerprint:xbValue('xbFingerprint','chrome'),
      short_id:xbValue('xbShortId',''),
      spider_x:xbValue('xbSpiderX','/'),
      xver:Number(xbValue('xbXver','0')||0),
      sniffing_enabled:xbChecked('xbSniffEnabled'),
      sniffing_dest_override:xbValue('xbSniffDest','http,tls,quic'),
      sniffing_route_only:xbChecked('xbSniffRouteOnly'),
      sniffing_metadata_only:xbChecked('xbSniffMetadata'),
      tcp_fast_open:xbChecked('xbTcpFastOpen'),
      tcp_no_delay:xbChecked('xbTcpNoDelay'),
      tcp_congestion:xbValue('xbCongestion',''),
      domain_strategy:xbValue('xbDomainStrategy',''),
      mark:Number(xbValue('xbMark','0')||0),
      interface:xbValue('xbInterface',''),
      tproxy:xbValue('xbTproxy',''),
      extra_stream:xrayBuilderJson('xbExtraStream')
    };
    const payload={
      protocol,transport,security,
      remark:xbValue('xbRemark').trim(),listen:xbValue('xbListen','0.0.0.0').trim(),
      port:Number(xbValue('xbPort','0')),name:xbValue('xbName').trim(),
      endpoint:xbValue('xbEndpoint').trim(),endpoint_mode:xbValue('xbEndpointMode','auto'),
      credential:xbValue('xbCredential','').trim(),flow:xbValue('xbFlow',''),
      shadowsocks_method:xbValue('xbSsMethod','aes-128-gcm'),
      quota_gb:Number(xbValue('xbQuota','0')||0),expire_days:Number(xbValue('xbDays','0')||0),
      ip_limit:Number(xbValue('xbIpLimit','1')||1),reset_days:Number(xbValue('xbReset','0')||0),
      options
    };
    if(!payload.remark||!payload.name||!payload.endpoint||!payload.port){alert('Remark، Client، Endpoint و Port الزامی هستند.');return}
    if(!confirm('این Inbound با Xray Core اعتبارسنجی و سپس اعمال شود؟'))return;
    const btn=document.querySelector('[data-action="xray-builder-create"]');if(btn){btn.disabled=true;btn.textContent='Validating…'}
    const result=await api('/api/protocols/xray/inbounds',{method:'POST',body:JSON.stringify(payload)});
    xrayCredentialModal(result);
  }catch(e){alert('Xray Inbound: '+e.message)}
}


function openXrayInboundClient(tag,protocol){
  const allowed=['vless','vmess','trojan','hysteria2'].includes(String(protocol||'').toLowerCase());
  if(!allowed){alert('این Protocol در Makia فعلاً Client چندگانه قابل مدیریت ندارد؛ برای Shadowsocks/HTTP/SOCKS یک Inbound جدا بساز.');return}
  const endpoint=window.PANEL_DOMAIN||location.hostname;
  const endpointMode=/^\d{1,3}(?:\.\d{1,3}){3}$/.test(endpoint)?'ip':'domain';
  const defaults=window.__operatorSettings?.defaults||{};
  modalRoot.innerHTML=[
    '<div class="modal-backdrop"><div class="modal">',
      '<div class="wizard-head"><div><div class="eyebrow">ADD XRAY CLIENT</div><h3>'+htmlEsc(tag)+'</h3><p>'+htmlEsc(String(protocol).toUpperCase())+' · همین Inbound و Transport/Security حفظ می‌شود</p></div><button class="close-btn" data-action="modal-close">×</button></div>',
      '<div class="form-grid two">',
        '<label>Client / Email<input id="xacName" value="user'+Math.floor(Math.random()*9000+1000)+'" maxlength="48"></label>',
        '<label>Credential (اختیاری)<input id="xacCredential" dir="ltr" placeholder="خالی = تولید خودکار"></label>',
        '<label>Endpoint mode<select id="xacEndpointMode"><option value="domain" '+(endpointMode==='domain'?'selected':'')+'>Domain</option><option value="ip" '+(endpointMode==='ip'?'selected':'')+'>IP</option></select></label>',
        '<label>Client endpoint<input id="xacEndpoint" dir="ltr" value="'+htmlEsc(endpoint)+'"></label>',
        '<label>Flow<select id="xacFlow"><option value="">None</option><option value="xtls-rprx-vision">xtls-rprx-vision</option></select><span class="muted">فقط اگر Inbound VLESS + RAW + TLS/REALITY باشد قابل اعمال است.</span></label>',
        '<label>Traffic quota GB<input id="xacQuota" type="number" min="0" value="'+Number(defaults.xray_quota_gb??50)+'"></label>',
        '<label>Expiry days<input id="xacDays" type="number" min="0" max="3650" value="'+Number(defaults.xray_expire_days??30)+'"></label>',
        '<label>IP limit<input id="xacIp" type="number" min="1" max="50" value="'+Number(defaults.xray_ip_limit||1)+'"></label>',
        '<label>Reset days<input id="xacReset" type="number" min="0" max="3650" value="'+Number(defaults.xray_reset_days??30)+'"></label>',
      '</div>',
      '<div class="wizard-note"><b>Same inbound</b><span>Port، Transport، TLS/REALITY و Sniffing تغییر نمی‌کند. فقط Client جدید به همین Inbound اضافه می‌شود و Share/QR مستقل می‌گیرد.</span></div>',
      '<div class="wizard-footer"><button class="ghost" data-action="modal-close">Cancel</button><button class="primary" data-action="xray-inbound-client-create" data-tag="'+dataEnc(tag)+'">Create client</button></div>',
    '</div></div>'
  ].join('');
}

async function createXrayInboundClient(tag){
  const payload={
    name:xbValue('xacName').trim(),
    endpoint:xbValue('xacEndpoint').trim(),
    endpoint_mode:xbValue('xacEndpointMode','auto'),
    credential:xbValue('xacCredential','').trim(),
    flow:xbValue('xacFlow',''),
    quota_gb:Number(xbValue('xacQuota','0')||0),
    expire_days:Number(xbValue('xacDays','0')||0),
    ip_limit:Number(xbValue('xacIp','1')||1),
    reset_days:Number(xbValue('xacReset','0')||0)
  };
  if(!payload.name||!payload.endpoint){alert('Client و Endpoint الزامی هستند.');return}
  try{
    const result=await api('/api/protocols/xray/inbounds/'+encodeURIComponent(tag)+'/clients',{
      method:'POST',body:JSON.stringify(payload)
    });
    xrayCredentialModal(result);
  }catch(e){alert('Add Xray client: '+e.message)}
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

async function bootstrapWireGuard(){const d=window.__operatorSettings?.defaults||{};const port=Number(prompt('WireGuard UDP port',String(d.wireguard_port||443)));if(!port)return;const cidr=prompt('Server tunnel CIDR',d.wireguard_cidr||'10.66.66.1/24');if(!cidr)return;try{const r=await api('/api/protocols/wireguard/bootstrap',{method:'POST',body:JSON.stringify({port,cidr,mtu:Number(d.wireguard_mtu||1280)})});toast('WireGuard '+r.interface+' started');await protocols()}catch(e){alert(e.message)}}
async function createWireGuardPeer(){const d=window.__operatorSettings?.defaults||{};const name=prompt('Peer name','client01');if(!name)return;const endpoint=prompt('Public domain or server IP',window.PANEL_DOMAIN||location.hostname);if(!endpoint)return;const dns=prompt('Client DNS',d.wireguard_dns||'1.1.1.1')||'1.1.1.1';try{const r=await api('/api/protocols/wireguard/peers',{method:'POST',body:JSON.stringify({name,endpoint,dns,mtu:Number(d.wireguard_mtu||1280),keepalive:Number(d.wireguard_keepalive??15),allowed_ips:d.wireguard_allowed_ips||'0.0.0.0/0'})});configModal('WireGuard · '+name,r.config,name+'.conf','wireguard',name);if(r.diagnostics&&!r.diagnostics.ok)toast('Config ساخته شد؛ WireGuard Diagnostics نیاز به بررسی دارد')}catch(e){alert(e.message)}}
async function openWireGuardDiagnostics(target=''){
  try{
    const endpoint=target||prompt('Endpoint داخل فایل WireGuard کلاینت (دامنه یا IP)',window.PANEL_DOMAIN||location.hostname);
    if(!endpoint)return;
    const known=prompt('اگر اتصال با IP کار می‌کند، آن IPv4 را برای مقایسه با رکورد A وارد کنید (اختیاری)','')||'';
    const d=await api('/api/protocols/wireguard/diagnostics?endpoint='+encodeURIComponent(endpoint)+'&known_working_ipv4='+encodeURIComponent(known));
    const warnings=(d.warnings||[]).map(x=>'<div class="diagnostic-hint">• '+htmlEsc(x)+'</div>').join('');
    const peers=(d.peers||[]).map(p=>'<div class="wg-peer-runtime"><div><b>'+htmlEsc(p.name||'peer')+'</b><span>'+htmlEsc(p.allowed_ips||'')+'</span></div><div><b>'+(p.handshake_age===null?'Never':Math.max(0,Number(p.handshake_age))+'s ago')+'</b><span>RX '+fmtBytes(p.rx||0)+' · TX '+fmtBytes(p.tx||0)+'</span></div></div>').join('');
    modalRoot.innerHTML=[
      '<div class="modal-backdrop"><div class="modal diagnostics-modal">',
      '<div class="wizard-head"><div><div class="eyebrow">WIREGUARD RUNTIME DIAGNOSTICS</div><h3>wg0 · '+(d.runtime_ok?'Healthy':'Attention')+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div>',
      '<div class="xray-diagnostic-grid">',
        '<div><span>Service</span><b class="'+(d.service_active?'ok-text':'bad-text')+'">'+(d.service_active?'ACTIVE':'DOWN')+'</b></div>',
        '<div><span>Interface</span><b class="'+(d.interface_present?'ok-text':'bad-text')+'">'+(d.interface_present?'wg0 READY':'MISSING')+'</b></div>',
        '<div><span>UDP Listener</span><b class="'+(d.listener?'ok-text':'bad-text')+'">'+(d.listener?(':'+Number(d.port)):'MISSING')+'</b></div>',
        '<div><span>IP Forward</span><b class="'+(d.ip_forward?'ok-text':'bad-text')+'">'+(d.ip_forward?'ON':'OFF')+'</b></div>',
        '<div><span>NAT</span><b class="'+(d.nat===true?'ok-text':'bad-text')+'">'+(d.nat===true?'READY':'UNKNOWN / MISSING')+'</b></div>',
        '<div><span>Endpoint</span><b class="'+(d.endpoint_ok?'ok-text':'bad-text')+'">'+htmlEsc(d.endpoint||'-')+'</b></div>',
      '</div>',
      '<div class="domain-resolution-grid"><div><span>A / IPv4</span><code>'+htmlEsc((d.resolved_ipv4||[]).join(', ')||'none')+'</code></div><div><span>AAAA / IPv6</span><code>'+htmlEsc((d.resolved_ipv6||[]).join(', ')||'none')+'</code></div><div><span>VPS IPv4</span><code>'+htmlEsc((d.local_ipv4||[]).join(', ')||'unknown')+'</code></div><div><span>VPS IPv6</span><code>'+htmlEsc((d.local_ipv6||[]).join(', ')||'unknown')+'</code></div></div>',
      warnings?'<div class="diagnostic-hints">'+warnings+'</div>':'<div class="wizard-note success-note"><b>WireGuard runtime ready</b><span>Forwarding، NAT، UDP listener و Endpoint بررسی شدند.</span></div>',
      '<div class="journal-head"><b>Peer Handshakes</b><span>'+Number(d.recent_handshakes||0)+' recent</span></div><div class="wg-peer-list">'+(peers||'<div class="empty compact">Peer runtime ثبت نشده است.</div>')+'</div>',
      '<div class="wizard-note"><b>Domain note</b><span>دامنه باید DNS-only و مستقیم باشد. اگر AAAA با IPv6 عملیاتی VPS مطابقت ندارد، زیر دامنه A-only بسازید. تنظیم دامنه پنل فایل‌های قبلی کلاینت را تغییر نمی‌دهد؛ از Access Center > Endpoint خروجی و QR جدید بگیرید و در دستگاه دوباره Import کنید.</span></div>',
      '<div class="wizard-footer"><button class="ghost" data-action="modal-close">Close</button><button class="primary" data-action="wireguard-repair">Repair & Restart</button></div>',
      '</div></div>'
    ].join('');
  }catch(e){alert('WireGuard diagnostics: '+e.message)}
}
async function updateWireGuardEndpoint(key,current){
  const endpoint=prompt('Endpoint جدید برای '+key+' (دامنه مستقیم یا IPv4؛ Port و Key حفظ می‌شوند)',current||window.PANEL_DOMAIN||location.hostname);
  if(!endpoint)return;
  try{
    const known=/^\d{1,3}(?:\.\d{1,3}){3}$/.test(current||'')?current:'';
    const d=await api('/api/protocols/wireguard/diagnostics?endpoint='+encodeURIComponent(endpoint)+'&known_working_ipv4='+encodeURIComponent(known));
    if(!d.endpoint_ok){alert('Endpoint آماده نیست:\n'+(d.warnings||[]).join('\n'));return}
    if(!confirm('فایل و QR این Peer با Endpoint جدید ساخته می‌شود. پس از دریافت خروجی جدید، پروفایل را روی دستگاه کاربر دوباره Import کنید. ادامه؟'))return;
    await api('/api/access/wireguard/'+encodeURIComponent(key)+'/endpoint',{method:'POST',body:JSON.stringify({endpoint})});
    toast('Endpoint ذخیره شد؛ Native/QR جدید را به کاربر تحویل بدهید');await access();
  }catch(e){alert('WireGuard Endpoint: '+e.message)}
}
async function repairWireGuardRuntime(){
  if(!confirm('Makia از wg0.conf بکاپ می‌گیرد، IP forwarding، NAT و Forward rules را اصلاح می‌کند و WireGuard را Restart می‌کند. ادامه؟'))return;
  try{const r=await api('/api/protocols/wireguard/repair',{method:'POST'});toast(r?.diagnostics?.runtime_ok?'WireGuard repaired and healthy':'WireGuard repair completed');await openWireGuardDiagnostics()}catch(e){alert('WireGuard repair: '+e.message)}
}
async function openEndpointMatrix(){
  const initial=window.PANEL_DOMAIN||location.hostname;
  const endpoint=prompt('دامنه یا IP عمومی برای بررسی همه پروتکل‌ها',initial);
  if(!endpoint)return;
  try{
    const d=await api('/api/protocols/endpoint-matrix?endpoint='+encodeURIComponent(endpoint));
    const rows=(d.rows||[]).map(r=>'<div class="endpoint-row"><span class="endpoint-dot '+(r.ready?'ok':'bad')+'"></span><div><b>'+htmlEsc(r.label)+'</b><small>'+htmlEsc(r.transport||'')+'</small></div><div><b>'+htmlEsc((r.ports||[]).filter(Boolean).join(', ')||'-')+'</b><small>Ports</small></div><div><span class="status-chip '+(r.runtime?'ok':'bad')+'">'+(r.runtime?'Runtime':'Runtime fail')+'</span><span class="status-chip '+(r.endpoint_ok?'ok':'bad')+'">'+(r.endpoint_ok?'Endpoint':'DNS/IP fail')+'</span></div></div>').join('');
    modalRoot.innerHTML=[
      '<div class="modal-backdrop"><div class="modal diagnostics-modal endpoint-matrix-modal">',
      '<div class="wizard-head"><div><div class="eyebrow">IP / DOMAIN READINESS MATRIX</div><h3>'+htmlEsc(d.endpoint)+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div>',
      '<div class="diagnostic-score '+(d.all_ready?'':'fail')+'"><div><b>'+(d.all_ready?'Server-side ready':'Attention required')+'</b><span>SSH · Xray · WireGuard · OpenVPN</span></div><span>'+((d.resolved_ipv4||[]).join(', ')||'No IPv4')+'</span></div>',
      '<div class="endpoint-matrix">'+rows+'</div>',
      '<div class="wizard-note"><b>تفسیر نتیجه</b><span>'+htmlEsc(d.note||'')+'</span></div>',
      '<div class="wizard-footer"><button class="ghost" data-action="modal-close">Close</button><button class="ghost" data-action="wireguard-diagnostics">WireGuard</button><button class="ghost" data-action="openvpn-diagnostics">OpenVPN</button></div>',
      '</div></div>'
    ].join('');
  }catch(e){alert('Endpoint readiness: '+e.message)}
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
      '<div class="xray-diagnostic-grid"><div><span>Service</span><b class="'+(d.service_active?'ok-text':'bad-text')+'">'+(d.service_active?'ACTIVE':'DOWN')+'</b></div><div><span>Listener</span><b class="'+(d.listener?'ok-text':'bad-text')+'">'+(d.listener?'READY':'MISSING')+'</b></div><div><span>Transport</span><b>'+htmlEsc(String(d.proto||'-'))+' : '+htmlEsc(String(d.port||'-'))+'</b></div><div><span>DNS → VPS</span><b class="'+(d.dns_matches_server===false?'bad-text':'ok-text')+'">'+(d.endpoint_is_ip?'DIRECT IP':d.dns_matches_server===false?'MISMATCH':'OK / UNKNOWN')+'</b></div><div><span>FORWARD</span><b class="'+(d.forwarding?.forward_in===false||d.forwarding?.forward_out===false?'bad-text':'ok-text')+'">'+(d.forwarding?.forward_in===true&&d.forwarding?.forward_out===true?'READY':'UNKNOWN / MISSING')+'</b></div><div><span>NAT</span><b class="'+(d.forwarding?.nat===false?'bad-text':'ok-text')+'">'+(d.forwarding?.nat===true?'READY':'UNKNOWN / MISSING')+'</b></div></div>',
      '<div class="domain-resolution-grid"><div><span>A / IPv4</span><code>'+htmlEsc((d.resolved_ipv4||[]).join(', ')||'none')+'</code></div><div><span>AAAA / IPv6</span><code>'+htmlEsc((d.resolved_ipv6||[]).join(', ')||'none')+'</code></div><div><span>VPS IPv4</span><code>'+htmlEsc((d.local_ipv4||[]).join(', ')||'unknown')+'</code></div></div>',
      d.hybrid_available?'<div class="wizard-note success-note"><b>Domain + IP Smart Fallback</b><span>پروفایل جدید ابتدا '+htmlEsc(endpoint)+' را امتحان می‌کند و اگر مسیر دامنه/DNS روی Client جواب نداد، به '+htmlEsc(d.hybrid_fallback_ipv4||'IPv4 VPS')+' سوییچ می‌کند.</span></div>':'',
      warnings?'<div class="diagnostic-hints">'+warnings+'</div>':'<div class="wizard-note"><b>Domain endpoint ready</b><span>دامنه به IPv4 این VPS می‌رسد و Listener OpenVPN فعال است.</span></div>',
      '<div class="wizard-note"><b>SSL clarification</b><span>گواهی HTTPS پنل برای Nginx است. OpenVPN از CA/Certificate داخلی خودش استفاده می‌کند؛ Cloudflare/HTTP proxy معمولی نمی‌تواند UDP/TCP خام OpenVPN را Forward کند.</span></div>',
      '<div class="wizard-footer"><button class="ghost" data-action="modal-close">Close</button><button class="ghost" data-action="openvpn-repair">Repair IPv4 / Forwarding</button><button class="primary" data-action="client-guide" data-kind="openvpn">راهنمای کاربر</button></div>',
      '</div></div>'
    ].join('');
  }catch(e){alert('OpenVPN diagnostics: '+e.message)}
}
async function repairOpenVPNRuntime(){
  if(!confirm('OpenVPN IPv4 و قوانین FORWARD/NAT مدیریت‌شده اصلاح شوند؟ پیش از تغییر Backup گرفته می‌شود و در خطا Rollback انجام می‌شود. سرویس کوتاه Restart خواهد شد.'))return;
  try{await api('/api/protocols/openvpn/repair',{method:'POST'});toast('OpenVPN runtime repaired');await openOpenVPNDiagnostics()}catch(e){alert('OpenVPN repair: '+e.message)}
}

async function openOpenVPNConfigure(){
  try{
    const stack=await api('/api/protocols'),engine=stack.openvpn||{},o=engine.options||{};
    const proto=String(o.proto||engine.proto||'udp').startsWith('tcp')?'tcp':'udp';
    const dns=Array.isArray(o.dns)?o.dns:['1.1.1.1','8.8.8.8'];
    modalRoot.innerHTML=[
      '<div class="modal-backdrop"><div class="modal engine-config-modal">',
        '<div class="wizard-head"><div><div class="eyebrow">OPENVPN SERVER</div><h3>تنظیمات پیشرفته OpenVPN</h3><p>تغییرها با Backup، Restart و Runtime verification اعمال می‌شوند.</p></div><button class="close-btn" data-action="modal-close">×</button></div>',
        '<div class="engine-mode-switch"><label class="'+(proto==='udp'?'active':'')+'"><input type="radio" name="ovpnTransport" value="udp" '+(proto==='udp'?'checked':'')+'><span>UDP</span><small>Latency کمتر، انتخاب پیش‌فرض</small></label><label class="'+(proto==='tcp'?'active':'')+'"><input type="radio" name="ovpnTransport" value="tcp" '+(proto==='tcp'?'checked':'')+'><span>TCP</span><small>برای شبکه‌هایی که UDP محدود است</small></label></div>',
        '<div class="wizard-form two"><label>Listen Port<input id="ovpnCfgPort" type="number" min="1" max="65535" value="'+Number(o.port||engine.port||1194)+'"></label><label>Primary DNS<input id="ovpnCfgDns1" value="'+htmlEsc(dns[0]||'1.1.1.1')+'"></label><label>Secondary DNS<input id="ovpnCfgDns2" value="'+htmlEsc(dns[1]||'8.8.8.8')+'"></label><label>Ping interval<input id="ovpnCfgPing" type="number" min="1" max="3600" value="'+Number(o.keepalive_ping||10)+'"></label><label>Restart timeout<input id="ovpnCfgTimeout" type="number" min="10" max="7200" value="'+Number(o.keepalive_timeout||120)+'"></label></div>',
        '<div class="engine-toggle-list"><label><input id="ovpnCfgRedirect" type="checkbox" '+(o.redirect_gateway!==false?'checked':'')+'><div><b>Redirect Gateway</b><small>تمام اینترنت Client از VPN عبور کند.</small></div></label><label><input id="ovpnCfgClientToClient" type="checkbox" '+(o.client_to_client?'checked':'')+'><div><b>Client-to-client</b><small>کلاینت‌های VPN بتوانند یکدیگر را ببینند؛ پیش‌فرض خاموش.</small></div></label></div>',
        '<div class="wizard-note"><b>تغییر Transport / Port</b><span>پروفایل‌های OVPN بعدی و دانلود مجدد کاربران با Runtime جدید ساخته می‌شوند. سرویس چند ثانیه Restart می‌شود. TCP/443 با HTTPS همان IP تداخل دارد.</span></div>',
        '<div class="wizard-footer"><button class="ghost" data-action="modal-close">انصراف</button><button class="ghost" data-action="openvpn-repair">Repair Runtime</button><button class="primary" data-action="openvpn-configure-save">اعمال تنظیمات</button></div>',
      '</div></div>'
    ].join('');
    document.querySelectorAll('input[name="ovpnTransport"]').forEach(x=>x.addEventListener('change',()=>document.querySelectorAll('.engine-mode-switch label').forEach(l=>l.classList.toggle('active',l.contains(x)&&x.checked))));
  }catch(e){alert('OpenVPN settings: '+e.message)}
}
async function saveOpenVPNConfigure(){
  const payload={
    port:Number(document.getElementById('ovpnCfgPort')?.value||1194),
    proto:document.querySelector('input[name="ovpnTransport"]:checked')?.value||'udp',
    dns_servers:[document.getElementById('ovpnCfgDns1')?.value,document.getElementById('ovpnCfgDns2')?.value].filter(Boolean),
    keepalive_ping:Number(document.getElementById('ovpnCfgPing')?.value||10),
    keepalive_timeout:Number(document.getElementById('ovpnCfgTimeout')?.value||120),
    redirect_gateway:Boolean(document.getElementById('ovpnCfgRedirect')?.checked),
    client_to_client:Boolean(document.getElementById('ovpnCfgClientToClient')?.checked)
  };
  if(!confirm('OpenVPN با '+payload.proto.toUpperCase()+'/'+payload.port+' بازتنظیم و Restart شود؟'))return;
  try{
    await api('/api/protocols/openvpn/configure',{method:'POST',body:JSON.stringify(payload)});
    toast('OpenVPN server updated');closeModal();window.__protocolData=await api('/api/protocols');if(activeView==='openvpn')await openvpnWorkspace(window.__viewRenderToken);
  }catch(e){alert('OpenVPN configure: '+e.message)}
}

async function services(renderToken=window.__viewRenderToken){
  title.textContent='مدیریت سرویس‌ها';setPageContext('SERVICE MANAGEMENT');
  const [d,pstack]=await Promise.all([api('/api/overview'),api('/api/protocols').catch(()=>({}))]);
  if(renderToken!==window.__viewRenderToken||activeView!=='services')return;
  const rows=d.services||[],running=rows.filter(x=>x.active).length;
  const installed={xray:Boolean(pstack?.xray?.installed),'openvpn-server@server':Boolean(pstack?.openvpn?.installed),'wg-quick@wg0':Boolean(pstack?.wireguard?.installed)};
  const body=rows.map(s=>{
    const protocolKind=s.name==='xray'?'xray':s.name==='openvpn-server@server'?'openvpn':s.name==='wg-quick@wg0'?'wireguard':'';
    const missing=protocolKind&&installed[s.name]===false;
    return '<div class="service-control-row"><div class="service-logo-mini">'+htmlEsc((s.label||s.name||'?').slice(0,1))+'</div><div class="service-control-copy"><b>'+htmlEsc(s.label||s.name)+'</b><span>'+htmlEsc(s.name)+'</span></div><span class="status-chip '+(missing?'warn':s.active?'ok':'bad')+'">'+(missing?'نصب نشده':s.active?'در حال اجرا':'متوقف')+'</span><div class="service-switch '+(s.active?'on':'')+'"><i></i></div><div class="toolbar">'+
      (missing?'<button class="primary" data-action="protocol-setup" data-kind="'+protocolKind+'">راه‌اندازی</button>':'<button class="ghost" data-action="service-action" data-service="'+dataEnc(s.name)+'" data-service-action="start">Start</button><button class="ghost" data-action="service-action" data-service="'+dataEnc(s.name)+'" data-service-action="restart">Restart</button><button class="danger" data-action="service-action" data-service="'+dataEnc(s.name)+'" data-service-action="stop">Stop</button>')+
      '</div></div>';
  }).join('');
  content.innerHTML=[
    '<section class="protocol-page-header"><div class="protocol-page-title"><span class="protocol-page-icon xray">▣</span><div><h2>مدیریت سرویس‌ها</h2><p>کنترل وضعیت سرویس‌های اصلی سرور و Engineهای پروتکل</p></div></div><div class="protocol-header-actions"><span class="status-chip '+(running===rows.length?'ok':'warn')+'">'+running+'/'+rows.length+' فعال</span><button class="ghost" data-action="refresh">بروزرسانی</button></div></section>',
    '<section class="panel"><div class="panel-head"><div><h3>وضعیت سرویس‌های سیستم</h3><span>START · STOP · RESTART</span></div></div><div class="service-control-list">'+body+'</div></section>'
  ].join('');
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
  const [rows,ready]=await Promise.all([api('/api/backups'),api('/api/backups/migration-readiness').catch(()=>({}))]);
  if(renderToken!==window.__viewRenderToken||activeView!=='backups')return;
  const full=rows.filter(x=>x.type==='full_migration'),quick=rows.filter(x=>x.type!=='full_migration');
  const migrationState=ready.same_config_cutover_ready?'READY':ready.ip_based?'IP-BASED CLIENTS':'CHECK';
  let lastRestore=null;
  const restoreJob=localStorage.getItem('makiaRestoreJob')||'';
  if(restoreJob){try{lastRestore=await api('/api/backups/restore/'+encodeURIComponent(restoreJob)+'/status')}catch{}}
  const history=rows.map(b=>{
    const sha=String(b.sha256||'');
    const download=b.type==='full_migration'?'<button class="ghost" data-action="backup-download" data-name="'+dataEnc(b.name)+'">Download Backup</button>':'<span class="muted">Host-local only</span>';
    return '<div class="backup-history-row"><div><b>'+htmlEsc(b.name)+'</b><small>'+htmlEsc(b.type==='full_migration'?'Full Migration Backup':'Quick Backup')+'</small></div><div><b>'+new Date(Number(b.created_at||0)*1000).toLocaleString()+'</b><small>'+fmtBytes(b.size)+'</small></div><div><b>'+htmlEsc(b.version||'—')+'</b><small title="'+htmlEsc(sha)+'">SHA256 '+htmlEsc(sha?sha.slice(0,12)+'…':'—')+'</small></div><div><span class="status-chip '+(b.encrypted?'ok':'warn')+'">'+(b.encrypted?'AES-256 Encrypted':'Local 0600')+'</span><small>'+(b.restore_ready?'Restore ready':'Check required')+'</small></div><div>'+download+'</div></div>';
  }).join('');
  const restoreState=lastRestore?'<section class="panel restore-job-card"><div class="panel-head"><div><h3>Latest Restore Job</h3><span>'+htmlEsc(lastRestore.job_id||'')+'</span></div><span class="status-chip '+(lastRestore.state==='passed'?'ok':lastRestore.state==='failed'?'bad':'warn')+'">'+htmlEsc(String(lastRestore.state||'unknown').toUpperCase())+'</span></div><p>'+htmlEsc(lastRestore.message||'')+'</p>'+(lastRestore.cutover_instruction?'<div class="wizard-note"><b>DNS cutover</b><span>'+htmlEsc(lastRestore.cutover_instruction)+'</span></div>':'')+'</section>':'';
  content.innerHTML=viewIntro('DISASTER RECOVERY','مرکز بکاپ و مهاجرت','Quick Backup برای rollback محلی است؛ Full Migration Backup رمزگذاری‌شده برای انتقال کامل هویت، PKI، Keys و تنظیمات به VPS جایگزین.','<div class="view-intro-actions"><div class="view-intro-stat"><b>'+rows.length+'</b><span>BACKUPS</span></div><button class="ghost" data-action="backup-create">Quick Backup</button><button class="primary" data-action="portable-backup">Full Migration Backup</button><button class="ghost" data-action="migration-restore-open">Upload & Restore</button></div>')+
  '<section class="migration-readiness-grid"><article><span>Preflight Migration Check</span><b class="'+(ready.same_config_cutover_ready?'ok-text':'warn-text')+'">'+htmlEsc(migrationState)+'</b><small>'+Number(ready.domain_based||0)+' domain-based · '+Number(ready.ip_based||0)+' IP-based · '+Number(ready.unknown||0)+' unknown</small></article><article><span>Panel domain</span><b>'+htmlEsc(ready.panel_domain||'Not configured')+'</b><small>'+(ready.panel_domain?('Cloudflare A record: '+htmlEsc(ready.panel_domain)+' → NEW_VPS_IP'):'Configure a stable hostname before an incident')+'</small></article><article><span>Portable backups</span><b>'+full.length+'</b><small>'+quick.length+' host-local quick snapshot(s)</small></article></section>'+
  (Number(ready.ip_based||0)>0?'<div class="wizard-note danger-note"><b>IP-based configs cannot survive DNS-only cutover</b><span>'+Number(ready.ip_based)+' خروجی مستقیماً IP قدیمی را ذخیره کرده‌اند. تغییر A record آن‌ها را اصلاح نمی‌کند؛ قبل از حادثه Endpoint را Domain-based کن یا بعداً re-export انجام بده.</span></div>':'')+
  '<section class="panel migration-flow-panel"><div class="panel-head"><div><h3>Migration Wizard</h3><span>BACKUP → VERIFY → RESTORE → UAT</span></div></div><div class="guide-flow"><div><b>1</b><span>Preflight و Full Migration Backup با Password.</span></div><div><b>2</b><span>روی VPS جدید همان نسخه Makia را نصب کن و Upload & Restore را باز کن.</span></div><div><b>3</b><span>Integrity + Version + Components قبل از Commit بررسی می‌شوند؛ Restore در Job مستقل با rollback اجرا می‌شود.</span></div><div><b>4</b><span>پس از Runtime PASS، A/AAAA دامنه را به IP جدید تغییر بده و UAT واقعی Client را انجام بده.</span></div></div></section>'+
  restoreState+
  '<section class="panel backup-history-panel"><div class="panel-head"><div><h3>Backup History</h3><span>DATE · SIZE · VERSION · SHA256 · ENCRYPTION · READINESS</span></div></div><div class="backup-history-list">'+(history||'<div class="empty">هنوز بکاپی ساخته نشده است.</div>')+'</div></section>';
}

function openPortableBackup(){
  modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal export-modal"><div class="wizard-head"><div><div class="eyebrow">FULL VPS MIGRATION</div><h3>Encrypted disaster-recovery bundle</h3></div><button class="close-btn" data-action="modal-close">×</button></div><p>این Bundle شامل DB و .secret، SSH password hashes و authorized_keys، Xray/REALITY، WireGuard keys/peers، OpenVPN PKI، IKEv2، Stealth/Stunnel، WStunnel، Nginx و Let\'s Encrypt است. Payloadها SHA-256 دارند.</p><label class="single-label">Migration password<input id="migrationPassword" type="password" minlength="10" autocomplete="new-password"></label><div class="wizard-note"><b>Restore contract</b><span>روی VPS مقصد همان نسخه Makia را نصب کن، Bundle را Restore کن؛ Runtime شبکه برای Interface جدید بازسازی می‌شود و سپس DNS همان دامنه را به IP جدید تغییر بده.</span></div><div class="wizard-note"><b>Cloudflare</b><span>برای ترافیک خام VPN/SSH رکورد باید DNS only باشد. فقط وب پنل می‌تواند پشت Proxy سازگار قرار بگیرد.</span></div><div class="wizard-footer"><button class="ghost" data-action="modal-close">Cancel</button><button class="primary" data-action="portable-backup-download">Build Full Backup</button></div></div></div>';
}
async function downloadPortableBackup(){
  const password=document.getElementById('migrationPassword')?.value||'';
  if(password.length<10){alert('Migration password حداقل ۱۰ کاراکتر باشد.');return}
  try{await fetchDownload('/api/backups/portable',{method:'POST',headers:{'Content-Type':'application/json','X-Makia-Request':'1'},body:JSON.stringify({password})},'makia-full-migration.zip');toast('Full VPS migration bundle آماده شد')}
  catch(e){alert('Portable backup: '+e.message)}
}
function openMigrationRestore(){
  window.__migrationRestorePassword=null;
  modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal export-modal migration-restore-modal"><div class="wizard-head"><div><div class="eyebrow">RESTORE / MIGRATE</div><h3>Upload encrypted Full Migration Backup</h3></div><button class="close-btn" data-action="modal-close">×</button></div><p>Bundle ابتدا بدون تغییر Runtime از نظر AES password، SHA256 payloadها، Manifest و Version بررسی می‌شود. Restore فقط بعد از Preview و تأیید جداگانه شروع می‌شود.</p><label class="single-label">Encrypted backup<input id="migrationRestoreFile" type="file" accept=".zip,application/zip"></label><label class="single-label">Migration password<input id="migrationRestorePassword" type="password" minlength="10" autocomplete="current-password"></label><div class="wizard-note"><b>Safety</b><span>Password در مرحله Verify روی دیسک ذخیره نمی‌شود؛ فقط هنگام Restore Now با Permission 0600 ساخته می‌شود و Restore runner آن را پس از اجرا حذف می‌کند. Bundle روی دیسک رمزگذاری‌شده باقی می‌ماند.</span></div><div class="wizard-footer"><button class="ghost" data-action="modal-close">Cancel</button><button class="primary" data-action="migration-restore-verify">Verify & Preview</button></div></div></div>';
}
async function verifyMigrationRestore(){
  const input=document.getElementById('migrationRestoreFile'),password=document.getElementById('migrationRestorePassword')?.value||'';
  const file=input?.files?.[0];
  if(!file){alert('فایل Full Migration Backup را انتخاب کن.');return}
  if(password.length<10){alert('Migration password حداقل ۱۰ کاراکتر باشد.');return}
  const body=new FormData();body.append('bundle',file);body.append('password',password);
  const r=await fetch('/api/backups/restore/verify',{method:'POST',credentials:'same-origin',headers:{'X-Makia-Request':'1'},body});
  let j={};try{j=await r.json()}catch{}
  if(!r.ok)throw new Error(j?.detail||'Migration verification failed');
  window.__migrationRestore=j;
  window.__migrationRestorePassword=password;
  const components=Object.entries(j.components||{}).filter(x=>x[1]).map(x=>x[0]).join(', ')||'core data';
  modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal export-modal migration-restore-modal"><div class="wizard-head"><div><div class="eyebrow">RESTORE PREVIEW</div><h3>Integrity & compatibility PASS</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="migration-preview-grid"><div><span>Version</span><b>'+htmlEsc(j.bundle_version||'—')+'</b></div><div><span>Payloads</span><b>'+Number(j.payload_count||0)+'</b></div><div><span>SHA256</span><b title="'+htmlEsc(j.sha256||'')+'">'+htmlEsc(String(j.sha256||'').slice(0,16))+'…</b></div><div><span>Domain</span><b>'+htmlEsc(j.panel_domain||'—')+'</b></div></div><div class="wizard-note"><b>Components</b><span>'+htmlEsc(components)+'</span></div><div class="wizard-note"><b>Cutover after PASS</b><span>'+htmlEsc(j.cutover_instruction||'Update DNS only after restore verification.')+'</span></div><div class="wizard-note danger-note"><b>Commit changes this VPS</b><span>Restore سرویس‌ها را restart می‌کند. اگر Runtime validation شکست بخورد، Restore engine به Snapshot قبل از Restore برمی‌گردد.</span></div><div class="wizard-footer"><button class="ghost" data-action="modal-close">Cancel</button><button class="primary" data-action="migration-restore-apply" data-job="'+dataEnc(j.job_id)+'">Restore Now</button></div></div></div>';
}
async function applyMigrationRestore(jobId){
  if(!confirm('Restore روی این VPS اجرا شود؟ سرویس Makia حین عملیات restart می‌شود.'))return;
  const password=window.__migrationRestorePassword||'';
  if(password.length<10){alert('Migration password برای Commit در حافظه موجود نیست؛ Bundle را دوباره Verify کن.');return}
  const r=await api('/api/backups/restore/'+encodeURIComponent(jobId)+'/apply',{method:'POST',body:JSON.stringify({password})});
  window.__migrationRestorePassword=null;
  localStorage.setItem('makiaRestoreJob',jobId);
  modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">RESTORE JOB</div><h3>Restore started</h3></div></div><p>Job مستقل systemd شروع شد. پنل ممکن است هنگام Restart موقتاً در دسترس نباشد. بعد از برگشت پنل، Backup Center وضعیت PASS/FAIL و DNS cutover را نشان می‌دهد.</p><div class="wizard-note"><b>Job ID</b><span>'+htmlEsc(jobId)+'</span></div><div class="wizard-footer"><button class="primary" data-action="modal-close-refresh" data-view="backups">Check status</button></div></div></div>';
  return r;
}
async function downloadBackup(name){
  await fetchDownload('/api/backups/'+encodeURIComponent(name)+'/download',{},name);
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
    '<section class="guide-admin-grid">'+cards.map(x=>'<article class="guide-admin-card"><div class="guide-admin-head">'+protocolGlyph(x[0])+'<div><b>'+x[1]+'</b><small>'+x[2]+'</small></div></div><p>'+x[3]+'</p><div class="toolbar"><button class="primary" data-action="client-guide" data-kind="'+x[0]+'">راهنمای تصویری</button><button class="ghost" data-action="client-guide-copy" data-kind="'+x[0]+'">کپی لینک راهنما</button></div></article>').join('')+'</section>',
    '<section class="panel"><div class="panel-head"><div><h3>روش پیشنهادی تحویل</h3><span>LESS SUPPORT TICKETS</span></div></div><div class="guide-flow"><div><b>1</b><span>از Access Center QR/Link/File همان کاربر را بفرست.</span></div><div><b>2</b><span>لینک Guide همان پروتکل را همراه آن ارسال کن.</span></div><div><b>3</b><span>برای Xray، Client Page و Subscription روش ساده‌تر برای کاربر نهایی هستند.</span></div><div><b>4</b><span>در صورت خطا، کاربر فقط نام برنامه، سیستم‌عامل و متن Error را بفرستد؛ Credential را در گروه عمومی نفرستد.</span></div></div></section>'
  ].join('');
}

async function supportCenter(renderToken=window.__viewRenderToken){
  title.textContent='Help & Support';setPageContext('HELP & DIAGNOSTICS');
  content.innerHTML='<div class="loading-state"><span class="spinner"></span><b>در حال آماده‌سازی مرکز راهنما…</b></div>';
  const [requests,session,grants,self,stack]=await Promise.all([
    api('/api/support/requests').catch(()=>({items:[],support:{}})),
    ensureSessionContext(true).catch(()=>({remote_support:false})),
    api('/api/support/grants').catch(()=>({items:[]})),
    api('/api/diagnostics/self-test').catch(()=>({ok:false,critical:1,warnings:0,summary:'Unavailable'})),
    api('/api/protocols').catch(()=>({}))
  ]);
  if(renderToken!==window.__viewRenderToken||activeView!=='support')return;
  const support=requests.support||{},items=requests.items||[];
  const engines=[
    ['Xray',Boolean(stack.xray?.service_active),'xray'],
    ['WireGuard',Boolean(stack.wireguard?.service_active),'wireguard'],
    ['OpenVPN',Boolean(stack.openvpn?.service_active),'openvpn']
  ];
  const recent=items.slice(0,6).map(x=>'<div class="support-ticket-row"><div><b>#'+Number(x.id)+' · '+htmlEsc(x.subject)+'</b><span>'+htmlEsc(x.created_at||'')+'</span></div><span class="status-chip '+(x.delivery_status==='webhook'?'ok':'')+'">'+htmlEsc(x.delivery_status||'local')+'</span></div>').join('');
  const grantsHtml=(grants.items||[]).slice(0,5).map(g=>'<div class="support-grant-row"><div><b>…'+htmlEsc(g.token_last4)+'</b><small>'+htmlEsc(g.scope)+' · '+htmlEsc(new Date(Number(g.expires_at)*1000).toLocaleString())+'</small></div>'+(g.active?'<button class="danger" data-action="support-grant-revoke" data-id="'+Number(g.id)+'">لغو</button>':'<span class="status-chip">Closed</span>')+'</div>').join('');
  content.innerHTML=[
    '<div class="pro-page support-v26">',
      '<section class="pro-page-head"><div><span class="pro-kicker">HELP CENTER</span><h1>راهنما و پشتیبانی</h1><p>اول وضعیت سیستم را ببین، بعد راهنمای اتصال یا مسیر گزارش مشکل را انتخاب کن.</p></div><div class="pro-head-actions"><button class="ghost" data-action="self-test">اجرای Self-Test</button><button class="primary" data-action="nav" data-view="guides">راهنمای اتصال</button></div></section>',
      '<section class="support-health-strip"><article class="'+(self.ok?'ok':'warn')+'"><span>●</span><div><b>System check</b><small>'+htmlEsc(self.summary||'Unknown')+' · '+Number(self.critical||0)+' critical · '+Number(self.warnings||0)+' warning</small></div></article>'+engines.map(x=>'<article class="'+(x[1]?'ok':'warn')+'"><span>'+protocolGlyph(x[2])+'</span><div><b>'+x[0]+'</b><small>'+(x[1]?'Runtime active':'Needs attention')+'</small></div></article>').join('')+'</section>',
      '<section class="support-action-grid">',
        '<button data-action="nav" data-view="connectivity"><span class="support-action-icon">⌁</span><div><b>Connectivity Lab</b><small>Endpoint، Port، Runtime و تست آماده‌سازی شبکه</small></div><i>←</i></button>',
        '<button data-action="nav" data-view="guides"><span class="support-action-icon">?</span><div><b>راهنمای تصویری</b><small>مراحل Xray، WireGuard، OpenVPN و SSH/NPV</small></div><i>←</i></button>',
        '<button data-action="nav" data-view="updates"><span class="support-action-icon">↻</span><div><b>Update Center</b><small>نسخه نصب‌شده و بروزرسانی رسمی</small></div><i>←</i></button>',
        '<a href="https://github.com/mahanneo/Makia-VPS-Manager/issues" target="_blank" rel="noopener"><span class="support-action-icon">GH</span><div><b>GitHub Issues</b><small>گزارش Bug عمومی و قابل پیگیری</small></div><i>↗</i></a>',
      '</section>',
      (support.telegram_url?'<section class="support-channel"><div><span class="pro-kicker">DIRECT SUPPORT</span><h3>ارتباط مستقیم</h3><p>کانال پشتیبانی توسط Owner این نصب تنظیم شده است.</p></div><button class="primary" data-action="support-telegram" data-url="'+htmlEsc(support.telegram_url)+'">Telegram @'+htmlEsc(support.telegram_username||'support')+'</button></section>':''),
      '<details class="pro-advanced support-advanced"><summary><span>ارسال گزارش مشکل</span><small>ثبت Ticket همراه با توضیح خطا</small></summary><div class="support-report-form"><div class="wizard-form one"><label>موضوع<input id="supportSubject" maxlength="160" placeholder="مثلاً: OpenVPN روی TCP وصل نمی‌شود"></label><label>توضیحات<textarea id="supportMessage" rows="5" placeholder="سیستم‌عامل، Client، پروتکل و متن خطا را بنویس. Credential کامل را ارسال نکن."></textarea></label></div><div class="settings-actions"><button class="primary" data-action="support-submit">ثبت گزارش</button></div></div></details>',
      (!session.remote_support?'<details class="pro-advanced support-advanced"><summary><span>دسترسی موقت پشتیبانی</span><small>Advanced · فقط با رضایت مدیر</small></summary><div class="remote-support-create"><div><p>در صورت نیاز به بررسی مستقیم، یک کد یک‌بارمصرف با مدت و Scope محدود بساز.</p><div class="wizard-form two"><label>مدت<select id="supportGrantMinutes"><option value="15">15 دقیقه</option><option value="30" selected>30 دقیقه</option><option value="60">60 دقیقه</option><option value="120">120 دقیقه</option></select></label><label>Scope<select id="supportGrantScope"><option value="readonly" selected>Read-only</option><option value="operator">Operator</option></select></label></div><button class="primary" data-action="support-grant-create">ساخت کد یک‌بارمصرف</button></div><div class="support-grant-list">'+(grantsHtml||'<div class="empty compact">کد فعالی وجود ندارد.</div>')+'</div></div></details>':'<div class="wizard-note danger-note"><b>Remote Support فعال</b><span>این Session موقت است و عملیات هویتی حساس محدود شده‌اند.</span></div>'),
      (recent?'<details class="pro-advanced support-advanced"><summary><span>گزارش‌های اخیر</span><small>'+items.length+' مورد ثبت‌شده</small></summary><div class="support-ticket-list">'+recent+'</div></details>':''),
    '</div>'
  ].join('');
}

async function createRemoteSupportGrant(){
  const minutes=Number(document.getElementById('supportGrantMinutes')?.value||30),scope=document.getElementById('supportGrantScope')?.value||'operator';
  try{
    const r=await api('/api/support/grants',{method:'POST',body:JSON.stringify({minutes,scope})});
    modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">ONE-TIME REMOTE SUPPORT</div><h3>کد موقت آماده است</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="support-code-box" id="supportGrantCode">'+htmlEsc(r.code)+'</div><div class="wizard-note"><b>Login URL</b><span id="supportGrantUrl">'+htmlEsc(r.login_url)+'</span></div><div class="wizard-note"><b>Expiry</b><span>'+htmlEsc(new Date(r.expires_at*1000).toLocaleString())+' · '+htmlEsc(r.scope)+'</span></div><div class="wizard-footer"><button class="primary" data-action="copy-target" data-target="supportGrantCode">Copy Code</button><button class="ghost" data-action="copy-target" data-target="supportGrantUrl">Copy URL</button><button class="ghost" data-action="modal-close-refresh" data-view="support">Done</button></div></div></div>';
  }catch(e){alert('Remote Support: '+e.message)}
}
async function revokeRemoteSupportGrant(id){
  if(!confirm('این دسترسی پشتیبانی فوراً لغو شود؟'))return;
  try{await api('/api/support/grants/'+Number(id),{method:'DELETE'});toast('Remote Support revoked');await currentView()}catch(e){alert(e.message)}
}
async function submitSupportRequest(){
  const subject=(document.getElementById('supportSubject')?.value||'').trim(),message=(document.getElementById('supportMessage')?.value||'').trim();
  if(subject.length<3||message.length<3){alert('Subject و Message را کامل کنید.');return}
  try{
    const r=await api('/api/support/requests',{method:'POST',body:JSON.stringify({subject,message})});
    modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">SUPPORT REQUEST</div><h3>درخواست ثبت شد</h3></div><button class="close-btn" data-action="modal-close">×</button></div><textarea id="supportRequestText" class="config-output small" readonly></textarea><div class="wizard-note"><b>Delivery: '+htmlEsc(r.status||'local')+'</b><span>'+(r.delivered?'درخواست به Endpoint مرکزی هم ارسال شد.':'این متن را می‌توانی برای پشتیبانی ارسال کنی.')+'</span></div><div class="wizard-footer"><button class="primary" data-action="copy-target" data-target="supportRequestText">Copy Request</button>'+(r.support?.telegram_url?'<button class="ghost" data-action="support-telegram" data-url="'+htmlEsc(r.support.telegram_url)+'">Open Telegram</button>':'')+'<button class="ghost" data-action="modal-close-refresh" data-view="support">Done</button></div></div></div>';
    document.getElementById('supportRequestText').value=r.request_text||'';
  }catch(e){alert('Support: '+e.message)}
}

async function settings(renderToken=window.__viewRenderToken){
  title.textContent='Settings';setPageContext('PANEL CONFIGURATION');
  const [general,two,tokens,operator,backupRows,sec]=await Promise.all([
    api('/api/settings/general'),
    api('/api/admin/2fa/status').catch(()=>({enabled:false,configured:false,restricted:true})),
    api('/api/admin/tokens').catch(()=>[]),
    api('/api/settings/operator'),
    api('/api/backups').catch(()=>[]),
    api('/api/security').catch(()=>({ufw:{installed:false,active:false},fail2ban:{installed:false,active:false},ssh:{installed:true,active:true}}))
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
      '<label>Theme<select id="generalTheme"><option value="glass" '+(general.theme==='glass'?'selected':'')+'>Control Center</option><option value="midnight" '+(general.theme==='midnight'?'selected':'')+'>Midnight</option><option value="amoled" '+(general.theme==='amoled'?'selected':'')+'>AMOLED</option><option value="graphite" '+(general.theme==='graphite'?'selected':'')+'>Graphite</option></select></label>',
      '<label>Density<select id="generalDensity"><option value="comfortable" '+(general.density==='comfortable'?'selected':'')+'>Comfortable</option><option value="compact" '+(general.density==='compact'?'selected':'')+'>Compact</option></select></label>',
      '<label>Panel Domain<input id="generalDomain" value="'+htmlEsc(general.panel_domain||'')+'" placeholder="panel.example.com"></label></div>',
      '<div class="settings-actions"><button class="primary" data-action="settings-general-save">Save panel settings</button></div></div>',
      '<div class="settings-card-v2"><div class="settings-card-title"><div><b>Operational owners</b><span>فقط مسیرهایی که Backend واقعی دارند</span></div></div>',
      '<div class="settings-shortcuts"><button data-action="nav" data-view="protocols"><b>Protocol Hub</b><span>Xray/WG/OpenVPN engines</span></button><button data-action="nav" data-view="access"><b>Access Center</b><span>Client provisioning & delivery</span></button><button data-action="nav" data-view="updates"><b>Update Center</b><span>Release status</span></button><button data-action="self-test"><b>Self-Test</b><span>DB, crypto and services</span></button></div></div>'
    ].join('');
  }else if(tab==='domain'){
    body=[
      '<section class="settings-section-head"><div><div class="eyebrow">PUBLIC PANEL EDGE</div><h2>Panel Domain / Nginx / HTTPS</h2><p>Domain، Nginx و Let\'s Encrypt با validation و rollback واقعی مدیریت می‌شوند.</p></div></section>',
      '<div class="settings-card-v2"><div class="domain-health-v2"><div><span>Configured domain</span><b>'+htmlEsc(general.panel_domain||'IP Mode')+'</b></div><div><span>DNS IPv4</span><b class="'+(ds.dns_matches_server===false?'warn-text':'')+'">'+htmlEsc(ds.resolved_ipv4?.length?ds.resolved_ipv4.join(', '):'Not resolved')+'</b></div><div><span>DNS → this VPS</span><b class="'+(ds.dns_matches_server===false?'warn-text':ds.dns_matches_server===true?'ok-text':'')+'">'+(ds.dns_matches_server===true?'MATCH':ds.dns_matches_server===false?'MISMATCH':'UNVERIFIED')+'</b></div><div><span>Certificate</span><b class="'+(ds.certificate&&Number(ds.certificate_days_left??-1)>14?'ok-text':'warn-text')+'">'+(ds.certificate?('Installed'+(ds.certificate_days_left!==null&&ds.certificate_days_left!==undefined?' · '+Number(ds.certificate_days_left)+'d':'')):'Not installed')+'</b></div><div><span>Nginx</span><b class="'+(ds.nginx_active&&ds.nginx_config_ok?'ok-text':'warn-text')+'">'+(ds.nginx_active&&ds.nginx_config_ok?'ACTIVE / VALID':'CHECK REQUIRED')+'</b></div><div><span>Listeners</span><b>'+(ds.http_listener?'80✓':'80—')+' · '+(ds.https_listener?'443✓':'443—')+'</b></div><div><span>Certbot</span><b class="'+(ds.certbot_nginx_ready?'ok-text':'warn-text')+'">'+(ds.certbot_nginx_ready?'READY':ds.certbot_installed?'NGINX PLUGIN MISSING':'HOST PACKAGE MISSING')+'</b></div></div>',
      '<div class="settings-form-grid two"><label>Panel Domain<input id="domainName" value="'+htmlEsc(general.panel_domain||'')+'" placeholder="panel.example.com"></label><label>Let\'s Encrypt email<input id="tlsEmail" type="email" placeholder="admin@example.com"></label></div>',
      '<div class="wizard-note"><b>DNS gate</b><span>Issue / Renew ابتدا DNS را با IPv4 همین VPS تطبیق می‌دهد، Domain را روی Nginx اعمال می‌کند و فقط از Certbot ازپیش‌نصب‌شده استفاده می‌کند؛ نصب Package داخل Web Service انجام نمی‌شود. nginx -t و Listener 443 تأیید می‌شوند و در خطا تنظیم Nginx rollback می‌شود.</span></div>',
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
    const xspec=xrayProfileSpec(defs.xray_protocol||'vless'),xtransport=xspec.transports.includes(defs.xray_transport)?defs.xray_transport:xspec.preset[0],xsecurity=xspec.security.includes(defs.xray_security)?defs.xray_security:xspec.preset[1];
    body=[
      '<section class="settings-section-head"><div><div class="eyebrow">PROVISIONING DEFAULTS</div><h2>Xray Defaults</h2><p>Defaultهای واقعی ساخت Client برای VLESS / VMess / Trojan / Shadowsocks / Hysteria2.</p></div></section>',
      '<div class="settings-card-v2"><div class="settings-form-grid">',
      '<label>Protocol<select id="opXrayProtocol">'+['vless','vmess','trojan','shadowsocks','hysteria2','http','socks'].map(x=>'<option value="'+x+'" '+(defs.xray_protocol===x?'selected':'')+'>'+x.toUpperCase()+'</option>').join('')+'</select></label>',
      '<label>Port<input id="opXrayPort" type="number" min="1" max="65535" value="'+Number(defs.xray_port||2087)+'"></label>',
      '<label>Transport<select id="opXrayTransport">'+xspec.transports.map(x=>'<option value="'+x+'" '+(xtransport===x?'selected':'')+'>'+x.toUpperCase()+'</option>').join('')+'</select></label>',
      '<label>Security<select id="opXraySecurity">'+xspec.security.map(x=>'<option value="'+x+'" '+(xsecurity===x?'selected':'')+'>'+x.toUpperCase()+'</option>').join('')+'</select></label>',
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
    const certValid=Boolean(ds.certificate)&&Number(ds.certificate_days_left??-1)>=0;
    const httpsReady=location.protocol==='https:'&&certValid;
    const activeTokens=tokens.filter(t=>t.active).length;
    const posture=[
      ['HTTPS',httpsReady,httpsReady?'TLS فعال روی همین Session':certValid?'Certificate نصب است اما این Session هنوز HTTPS نیست':'گواهی معتبر نصب نشده است'],
      ['Admin 2FA',Boolean(two.enabled),two.enabled?'TOTP فعال':'فعال‌سازی توصیه می‌شود'],
      ['UFW Firewall',Boolean(sec.ufw?.active),sec.ufw?.active?'Firewall active':sec.ufw?.installed?'Installed / inactive':'Not installed'],
      ['Fail2ban',Boolean(sec.fail2ban?.active),sec.fail2ban?.active?'Brute-force protection active':sec.fail2ban?.installed?'Installed / inactive':'Not installed'],
      ['OpenSSH',Boolean(sec.ssh?.active),sec.ssh?.active?'SSH daemon active':'SSH service needs attention'],
      ['API exposure',activeTokens===0,activeTokens?activeTokens+' active token':'No active token']
    ];
    const healthy=posture.filter(x=>x[1]).length;
    body=[
      '<section class="settings-section-head security-head-v26"><div><div class="eyebrow">ADMIN SECURITY</div><h2>Admin Security</h2><p>وضعیت ورود مدیر، HTTPS، Firewall، 2FA و Tokenها در یک نمای عملیاتی.</p></div><div class="security-posture-score '+(healthy>=5?'good':healthy>=3?'warn':'bad')+'"><b>'+healthy+'/'+posture.length+'</b><span>controls ready</span></div></section>',
      (!httpsReady?'<div class="security-critical-banner"><b>پنل در حال حاضر Secure نیست</b><span>اسکرین‌شات Host با HTTP/IP باز شده است. برای استفاده عمومی Domain + HTTPS را فعال کن.</span><button class="primary" data-action="settings-tab" data-tab="domain">تنظیم HTTPS</button></div>':''),
      '<div class="security-posture-grid">'+posture.map(x=>'<article class="'+(x[1]?'ok':'warn')+'"><i>'+(x[1]?'✓':'!')+'</i><div><b>'+x[0]+'</b><small>'+htmlEsc(x[2])+'</small></div></article>').join('')+'</div>',
      '<div class="settings-card-v2"><div class="settings-card-title"><div><b>Admin session</b><span>Signed session lifetime</span></div><span class="status-chip">'+Math.round(Number(operator.session_max_age_minutes||720)/60*10)/10+'h</span></div><div class="settings-form-grid two"><label>Session max age (minutes)<input id="opSessionMinutes" type="number" min="5" max="43200" value="'+Number(operator.session_max_age_minutes||720)+'"></label><div class="settings-inline-note"><b>Shorter is safer</b><span>برای پنل عمومی Session کوتاه‌تر و 2FA توصیه می‌شود.</span></div></div><div class="settings-actions"><button class="primary" data-action="settings-operator-save">ذخیره Session Policy</button></div></div>',
      '<div class="settings-card-v2"><div class="settings-card-title"><div><b>Administrator password</b><span>حداقل 12 کاراکتر و ترجیحاً یکتا</span></div></div><div class="settings-form-grid two"><label>رمز فعلی<input id="oldP" type="password" autocomplete="current-password"></label><label>رمز جدید<input id="newP" type="password" minlength="12" autocomplete="new-password"></label></div><div class="security-password-hint"><span>پیشنهاد:</span> حروف بزرگ/کوچک + عدد + نماد و عدم استفاده مجدد از رمزهای قبلی.</div><div class="settings-actions"><button class="primary" data-action="settings-password-change">تغییر رمز مدیر</button></div></div>',
      '<div class="settings-card-v2"><div class="settings-card-title"><div><b>Two-Factor Authentication</b><span>TOTP authenticator</span></div><span class="status-chip '+(two.enabled?'ok':'warn')+'">'+(two.enabled?'Enabled':'Recommended')+'</span></div><div class="security-feature-row"><div><b>'+(two.enabled?'2FA فعال است':'لایه دوم ورود را فعال کن')+'</b><span>'+(two.enabled?'برای ورود Password + کد ۶ رقمی لازم است.':'Google/Microsoft Authenticator، 1Password و سایر TOTP appها سازگارند.')+'</span></div><button class="'+(two.enabled?'danger':'primary')+'" data-action="'+(two.enabled?'settings-2fa-disable':'settings-2fa-setup')+'">'+(two.enabled?'غیرفعال‌سازی 2FA':'فعال‌سازی 2FA')+'</button></div></div>',
      '<div class="settings-card-v2"><div class="settings-card-title"><div><b>Security operations</b><span>ابزارهای سریع بررسی و سخت‌سازی</span></div></div><div class="settings-shortcuts"><button data-action="nav" data-view="security"><b>Host Security</b><span>UFW · Fail2ban · SSH</span></button><button data-action="self-test"><b>Self-Test</b><span>Crypto · DB · Services</span></button><button data-action="settings-tab" data-tab="api"><b>API Tokens</b><span>'+activeTokens+' active</span></button><button data-action="nav" data-view="audit"><b>Audit Logs</b><span>ردپای عملیات مدیر</span></button></div></div>'
    ].join('');
  }else if(tab==='api'){
    body=[
      '<section class="settings-section-head"><div><div class="eyebrow">AUTOMATION API</div><h2>Scoped API Tokens</h2><p>Tokenهای Read-only با Scope مشخص؛ مقدار کامل فقط هنگام ساخت نمایش داده می‌شود.</p></div><button class="primary" data-action="settings-api-new">＋ New Token</button></section>',
      '<div class="settings-card-v2"><div class="wizard-note"><b>HTTPS only</b><span>برای API مدیریتی از HTTPS استفاده کن. در دیتابیس فقط Hash Token ذخیره می‌شود.</span></div><div class="table">'+(tokens.length?tokens.map(t=>'<div class="row"><div><b>'+htmlEsc(t.name)+'</b><div class="muted">…'+htmlEsc(t.token_last4)+'</div></div><div class="muted">'+htmlEsc(t.scopes||'-')+'</div><div><span class="status-chip '+(t.active?'ok':'bad')+'">'+(t.active?'Active':'Revoked')+'</span></div><div class="toolbar">'+(t.active?'<button class="danger" data-action="settings-api-revoke" data-id="'+Number(t.id)+'">Revoke</button>':'')+'</div></div>').join(''):'<div class="empty">API Tokenای ساخته نشده است.</div>')+'</div></div>'
    ].join('');
  }else{
    const recent=backupRows.slice(0,5);
    body=[
      '<section class="settings-section-head"><div><div class="eyebrow">RECOVERY</div><h2>Backup / Migration</h2><p>Local Snapshot برای rollback؛ Full VPS Migration برای انتقال کاربران، credentialها، keys، PKI و تنظیمات به VPS جدید.</p></div><div class="toolbar"><button class="ghost" data-action="portable-backup">Full VPS Backup</button><button class="primary" data-action="backup-create">＋ Local Backup</button></div></section>',
      '<div class="settings-card-v2"><div class="domain-health-v2"><div><span>Backups</span><b>'+backupRows.length+'</b></div><div><span>Latest</span><b>'+(recent[0]?htmlEsc(recent[0].name):'None')+'</b></div><div><span>Storage</span><b>'+fmtBytes(backupRows.reduce((n,x)=>n+Number(x.size||0),0))+'</b></div><div><span>Restore</span><b class="warn-text">CLI / validated workflow only</b></div></div>',
      '<div class="settings-shortcuts"><button data-action="nav" data-view="backups"><b>Open Backup Center</b><span>View all real archives</span></button><button data-action="self-test"><b>Run Self-Test</b><span>Validate crypto, DB and services</span></button></div>',
      (recent.length?'<div class="recovery-list">'+recent.map(x=>'<div><b>'+htmlEsc(x.name)+'</b><span>'+fmtBytes(x.size||0)+'</span></div>').join('')+'</div>':'<div class="empty">هنوز Backup ساخته نشده است.</div>')+'</div>'
    ].join('');
  }

  content.innerHTML='<div class="sx-page"><section class="sx-page-head"><div><h1>تنظیمات</h1><p>تنظیمات پنل، امنیت، پروتکل‌ها و Recovery</p></div><div class="sx-head-actions"><span class="sx-state-pill"><i></i>v'+htmlEsc(window.MAKIA_VERSION||'')+'</span></div></section><div class="settings-tabs-sx">'+nav+'</div><div class="settings-content-v2">'+body+'</div></div>';
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
    xray_transport:readSettingValue('opXrayTransport',x.xray_transport||'tcp'),
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
const commandItems=[['Dashboard','dashboard'],['Clients','access'],['Inbounds','inbounds'],['SSH / NPV','ssh'],['Xray / V2Ray','xray'],['WireGuard','wireguard'],['OpenVPN','openvpn'],['Connectivity Lab','connectivity'],['Network / Ports','protocols'],['Live Sessions','sessions'],['Nodes','nodes'],['Services','services'],['Backups','backups'],['Logs','audit'],['Update','updates'],['Settings','settings'],['Client Guides','guides'],['Security','security'],['Support','support']];

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
  if(!wizardProtocolReady(kind)){await openProtocolSetup(kind);return}
  if(kind==='xray'){
    closeModal();
    await openXrayInboundBuilder();
    return;
  }
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
  if(action==='nav-settings'){closeModal();window.__settingsTab=btn.dataset.tab||'general';switchView('settings');return}
  if(action==='xray-inbound-builder'){await openXrayInboundBuilder();return}
  if(action==='xray-inbound-client'){openXrayInboundClient(dataDec(btn.dataset.tag),btn.dataset.protocol||'');return}
  if(action==='xray-inbound-client-create'){await createXrayInboundClient(dataDec(btn.dataset.tag));return}
  if(action==='xray-builder-create'){await createXrayInboundBuilder();return}
  if(action==='wizard-open'){await openProvisionWizard(btn.dataset.kind||null);return}
  if(action==='wizard-protocol'){await selectWizardProtocol(btn.dataset.kind);return}
  if(action==='wizard-xray-advanced'){captureWizard();provisionState.simpleMode=false;provisionState.manualXray=true;normalizeXrayProfile(provisionState,false);renderProvisionWizard();return}
  if(action==='wizard-xray-simple'){captureWizard();provisionState.simpleMode=true;provisionState.manualXray=false;applySimpleXrayPreset(provisionState);renderProvisionWizard();return}
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
  if(action==='client-portal'){await openClientPortal(btn.dataset.kind,dataDec(btn.dataset.key),dataDec(btn.dataset.name));return}
  if(action==='client-portal-rotate'){await rotateClientPortal(btn.dataset.kind,dataDec(btn.dataset.key),dataDec(btn.dataset.name));return}
  if(action==='qr-download'){await downloadAccessQr(btn.dataset.kind,dataDec(btn.dataset.key),dataDec(btn.dataset.name));return}
  if(action==='subscription-qr-download'){await downloadSubscriptionQr(dataDec(btn.dataset.key),dataDec(btn.dataset.name));return}
  if(action==='access-detail'){await openAccessDetail(dataDec(btn.dataset.id));return}
  if(action==='manage-access'){manageAccess(dataDec(btn.dataset.id));return}
  if(action==='revoke-access'){await revokeAccess(btn.dataset.kind,dataDec(btn.dataset.key),dataDec(btn.dataset.name));return}
  if(action==='wg-reissue'){await reissueWireGuard(dataDec(btn.dataset.key));return}
  if(action==='wg-toggle'){await toggleWireGuardPeer(dataDec(btn.dataset.key),btn.dataset.enabled==='1');return}
  if(action==='protocol-setup'){await openProtocolSetup(btn.dataset.kind);return}
  if(action==='protocol-install'){await performProtocolInstall(btn.dataset.kind);return}
  if(action==='change-protocol'){await openChangeProtocol();return}
  if(action==='protocol-mode-select'){await selectProtocolMode(btn.dataset.mode||'');return}
  if(action==='ikev2-setup'){await setupIKEv2();return}
  if(action==='ikev2-user'){await createIKEv2User();return}
  if(action==='ikev2-users'){await openIKEv2Users();return}
  if(action==='ikev2-user-delete'){await revokeIKEv2User(dataDec(btn.dataset.name));return}
  if(action==='openvpn-mode'){await switchOpenVPNMode(btn.dataset.proto||'udp');return}
  if(action==='openvpn-tcp-fallback'){await ensureOpenVPNTCPFallback();return}
  if(action==='stealth-setup'){await setupStealth();return}
  if(action==='wstunnel-setup'){await setupWStunnel();return}
  if(action==='protocol-bootstrap'){await performProtocolBootstrap(btn.dataset.kind,btn.dataset.installed==='1');return}
  if(action==='protocol-refresh'){await currentView();return}
  if(action==='endpoint-matrix'){await openEndpointMatrix();return}
  if(action==='wireguard-diagnostics'){await openWireGuardDiagnostics();return}
  if(action==='wg-endpoint-update'){await updateWireGuardEndpoint(dataDec(btn.dataset.key),btn.dataset.endpoint);return}
  if(action==='wireguard-repair'){await repairWireGuardRuntime();return}
  if(action==='openvpn-diagnostics'){await openOpenVPNDiagnostics();return}
  if(action==='openvpn-configure'){await openOpenVPNConfigure();return}
  if(action==='openvpn-configure-save'){await saveOpenVPNConfigure();return}
  if(action==='openvpn-repair'){await repairOpenVPNRuntime();return}
  if(action==='xray-diagnostics'){await openXrayDiagnostics();return}
  if(action==='xray-repair'){await repairXrayRuntime();return}
  if(action==='xray-advanced'){await openXrayAdvanced();return}
  if(action==='xray-tunnel'){createXrayTunnel();return}
  if(action==='client-guide'){openClientGuide(btn.dataset.kind||'xray');return}
  if(action==='client-guide-copy'){copyClientGuide(btn.dataset.kind||'xray');return}
  if(action==='self-test'){await runSelfTest();return}
  if(action==='success-done'){closeModal();switchView('access');return}
  if(action==='modal-close'){if(document.querySelector('.migration-restore-modal'))window.__migrationRestorePassword=null;closeModal();return}
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
  if(action==='backup-download'){await downloadBackup(dataDec(btn.dataset.name));return}
  if(action==='migration-restore-open'){openMigrationRestore();return}
  if(action==='migration-restore-verify'){await verifyMigrationRestore();return}
  if(action==='migration-restore-apply'){await applyMigrationRestore(dataDec(btn.dataset.job));return}
  if(action==='wg-compat-preset'){const values={opWgPort:443,opWgMtu:1280,opWgKeepalive:15,opWgAllowedIps:'0.0.0.0/0',opWgDns:'1.1.1.1'};for(const [id,v] of Object.entries(values)){const el=document.getElementById(id);if(el)el.value=v}toast('Compatibility preset applied; Save to persist');return}
  if(action==='support-grant-create'){await createRemoteSupportGrant();return}
  if(action==='support-grant-revoke'){await revokeRemoteSupportGrant(Number(btn.dataset.id));return}
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
    else if(a==='sidebar-open'){document.body.classList.add('menu-open');shell.setAttribute('aria-expanded','true')}
    else if(a==='sidebar-close'){document.body.classList.remove('menu-open');document.querySelector('.mobile-menu-toggle')?.setAttribute('aria-expanded','false')}
    else if(a==='sidebar-group'){
      shell.closest('.pro-nav-group')?.classList.toggle('open');
    }
    return;
  }
  const btn=e.target.closest('[data-action]');
  if(btn){e.preventDefault();Promise.resolve(handleMakiaAction(btn)).catch(err=>alert(err?.message||String(err)))}
});
document.addEventListener('change',e=>{
  if(e.target.id==='wizEndpointMode'&&provisionState){
    const next=e.target.value;
    captureWizard();
    provisionState.endpointMode=next;
    provisionState.endpoint=provisionState.endpointValues[next]||'';
    if(provisionState.protocol==='xray'&&provisionState.simpleMode)applySimpleXrayPreset(provisionState);
    renderProvisionWizard();
  }
  if(e.target.id==='wizXrayProtocol'&&provisionState){
    captureWizard();
    normalizeXrayProfile(provisionState,provisionState.simpleMode);
    renderProvisionWizard();
  }
  if((e.target.id==='wizTransport'||e.target.id==='wizSecurity')&&provisionState){
    captureWizard();
    normalizeXrayProfile(provisionState,false);
    renderProvisionWizard();
  }
  if(e.target.id==='opXrayProtocol'){
    const spec=xrayProfileSpec(e.target.value),t=document.getElementById('opXrayTransport'),s=document.getElementById('opXraySecurity');
    if(t)t.innerHTML=spec.transports.map(x=>'<option value="'+x+'">'+x.toUpperCase()+'</option>').join('');
    if(s)s.innerHTML=spec.security.map(x=>'<option value="'+x+'">'+x.toUpperCase()+'</option>').join('');
    if(t)t.value=spec.preset[0];if(s)s.value=spec.preset[1];
  }
});
document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openCommandPalette()}if(e.key==='Escape')closeModal()});


async function plansView(renderToken=window.__viewRenderToken){
  title.textContent=tr('پلن‌ها','Plans');setPageContext('PLANS / TEMPLATES');
  const rows=await api('/api/plans');if(renderToken!==window.__viewRenderToken||activeView!=='plans')return;
  const cards=rows.map(p=>'<article class="ops-card"><div class="ops-card-head"><div><span class="pro-kicker">'+htmlEsc(String(p.protocol||'').toUpperCase())+'</span><h3>'+htmlEsc(p.name)+'</h3></div><span class="status-chip '+(p.active?'ok':'warn')+'">'+(p.active?tr('فعال','Active'):tr('غیرفعال','Inactive'))+'</span></div><div class="ops-metrics"><div><span>'+tr('مدت','Days')+'</span><b>'+Number(p.days||0)+'</b></div><div><span>'+tr('حجم','Quota')+'</span><b>'+(Number(p.quota_gb||0)?Number(p.quota_gb)+' GB':tr('نامحدود','Unlimited'))+'</b></div><div><span>IP</span><b>'+Number(p.ip_limit||1)+'</b></div><div><span>'+tr('بازنشانی','Reset')+'</span><b>'+Number(p.reset_days||0)+'d</b></div></div><div class="toolbar"><button class="primary" data-action="plan-use" data-id="'+Number(p.id)+'">'+tr('استفاده از پلن','Use plan')+'</button><button class="ghost" data-action="plan-edit" data-id="'+Number(p.id)+'">'+tr('ویرایش','Edit')+'</button><button class="danger" data-action="plan-delete" data-id="'+Number(p.id)+'">'+tr('حذف','Delete')+'</button></div></article>').join('');
  content.innerHTML=viewIntro('PLANS / TEMPLATES',tr('پلن‌های آماده','Reusable plans'),tr('برای ساخت سریع SSH و Xray و Presetهای Outline. محدودیت زمان فقط جایی اعمال می‌شود که Backend واقعاً آن را enforce می‌کند.','Reusable presets for SSH, Xray and Outline. Time limits are only shown as enforced where the backend can truly enforce them.'),'<button class="primary" data-action="plan-new">＋ '+tr('پلن جدید','New plan')+'</button>')+
    '<div class="ops-grid">'+(cards||'<div class="empty">'+tr('هنوز پلنی ساخته نشده است.','No plans yet.')+'</div>')+'</div>'+
    '<div class="wizard-note"><b>'+tr('بدون قابلیت Fake','No fake enforcement')+'</b><span>'+tr('تمدید/انقضای خودکار فعلاً برای SSH و Xray enforce می‌شود. Outline از quota رسمی API پشتیبانی می‌کند؛ WireGuard/OpenVPN به‌عنوان پلن زمانی نمایش داده نمی‌شوند تا کنترل صوری ایجاد نشود.','Automatic renewal/expiry is enforced for SSH and Xray. Outline uses its official API quota; WireGuard/OpenVPN are not presented as time-enforced plans to avoid fake controls.')+'</span></div>';
}
async function openPlanEditor(id=0){
  let p={name:'',protocol:'xray',days:30,quota_gb:50,ip_limit:1,reset_days:30,defaults:{},active:true};
  if(id){const rows=await api('/api/plans');p=rows.find(x=>Number(x.id)===Number(id))||p}
  modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">PLAN TEMPLATE</div><h3>'+htmlEsc(id?tr('ویرایش پلن','Edit plan'):tr('پلن جدید','New plan'))+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="form-grid two"><label>'+tr('نام پلن','Plan name')+'<input id="planName" value="'+htmlEsc(p.name||'')+'"></label><label>'+tr('پروتکل','Protocol')+'<select id="planProtocol"><option value="ssh">SSH</option><option value="xray">Xray</option><option value="outline">Outline</option></select></label><label>'+tr('روز','Days')+'<input id="planDays" type="number" min="0" max="3650" value="'+Number(p.days||0)+'"></label><label>'+tr('حجم GB','Quota GB')+'<input id="planQuota" type="number" min="0" step="1" value="'+Number(p.quota_gb||0)+'"></label><label>'+tr('محدودیت IP','IP limit')+'<input id="planIp" type="number" min="1" max="50" value="'+Number(p.ip_limit||1)+'"></label><label>'+tr('چرخه Reset','Reset days')+'<input id="planReset" type="number" min="0" max="3650" value="'+Number(p.reset_days||0)+'"></label></div><label>'+tr('تنظیمات پیش‌فرض JSON','Defaults JSON')+'<textarea id="planDefaults" class="config-output small">'+htmlEsc(JSON.stringify(p.defaults||{},null,2))+'</textarea></label><label class="check-row"><input id="planActive" type="checkbox" '+(p.active?'checked':'')+'> '+tr('فعال','Active')+'</label><div class="wizard-footer"><button class="ghost" data-action="modal-close">'+tr('انصراف','Cancel')+'</button><button class="primary" data-action="plan-save" data-id="'+Number(id)+'">'+tr('ذخیره','Save')+'</button></div></div></div>';
  document.getElementById('planProtocol').value=p.protocol||'xray';
}
async function savePlan(id){
  let defaults={};try{defaults=JSON.parse(document.getElementById('planDefaults').value||'{}')}catch(e){alert(tr('JSON تنظیمات نامعتبر است','Defaults JSON is invalid'));return}
  const payload={name:document.getElementById('planName').value.trim(),protocol:document.getElementById('planProtocol').value,days:Number(document.getElementById('planDays').value||0),quota_gb:Number(document.getElementById('planQuota').value||0),ip_limit:Number(document.getElementById('planIp').value||1),reset_days:Number(document.getElementById('planReset').value||0),defaults,active:document.getElementById('planActive').checked};
  try{await api('/api/plans'+(id?'/'+id:''),{method:id?'PUT':'POST',body:JSON.stringify(payload)});closeModal();toast(tr('پلن ذخیره شد','Plan saved'));await plansView()}catch(e){alert(e.message)}
}
async function deletePlan(id){if(!confirm(tr('این پلن حذف شود؟','Delete this plan?')))return;try{await api('/api/plans/'+id,{method:'DELETE'});await plansView()}catch(e){alert(e.message)}}
async function usePlan(id){
  const rows=await api('/api/plans'),p=rows.find(x=>Number(x.id)===Number(id));if(!p)return;
  if(p.protocol==='ssh'){
    await openProvisionWizard('ssh');
    provisionState.plan=p.name;provisionState.expireDate=p.days?dateAfterDays(p.days):'';provisionState.devices=p.ip_limit||1;
    renderProvisionWizard();return;
  }
  if(p.protocol==='xray'){
    await openXrayInboundBuilder();
    const d=p.defaults||{};
    if(d.protocol&&document.getElementById('xbProtocol')){document.getElementById('xbProtocol').value=d.protocol;syncXrayInboundBuilder()}
    if(document.getElementById('xbDays'))document.getElementById('xbDays').value=Number(p.days||0);
    if(document.getElementById('xbQuota'))document.getElementById('xbQuota').value=Number(p.quota_gb||0);
    if(document.getElementById('xbIpLimit'))document.getElementById('xbIpLimit').value=Number(p.ip_limit||1);
    if(document.getElementById('xbReset'))document.getElementById('xbReset').value=Number(p.reset_days||0);
    return;
  }
  if(p.protocol==='outline'){await openOutlineCreate(p);return}
}
async function expiryView(renderToken=window.__viewRenderToken){
  title.textContent=tr('انقضا و تمدید','Expiry & Renew');setPageContext('EXPIRY CENTER');
  const data=await api('/api/expiry-center?days=30');if(renderToken!==window.__viewRenderToken||activeView!=='expiry')return;
  const rows=(data.items||[]).map(x=>'<div class="row expiry-row"><div><input type="checkbox" class="expiry-check" data-kind="'+htmlEsc(x.kind)+'" data-key="'+dataEnc(x.key)+'"><b>'+htmlEsc(x.name)+'</b><div class="muted">'+htmlEsc(String(x.protocol||x.kind).toUpperCase())+'</div></div><div><span class="status-chip '+(x.days_left<0?'bad':x.days_left<=3?'warn':'ok')+'">'+(x.days_left<0?tr('منقضی','Expired'):x.days_left===0?tr('امروز','Today'):x.days_left+' '+tr('روز','days'))+'</span></div><div>'+fmtBytes(x.quota_bytes||0)+'</div><div class="toolbar"><button class="primary" data-action="quick-renew" data-kind="'+htmlEsc(x.kind)+'" data-key="'+dataEnc(x.key)+'" data-name="'+dataEnc(x.name)+'">+30d</button></div></div>').join('');
  content.innerHTML=viewIntro('EXPIRY CENTER',tr('انقضا و تمدید سریع','Expiry & quick renew'),tr('کاربران SSH و Xray با انقضای واقعی Backend.','SSH and Xray clients with backend-enforced expiry.'),'<div class="view-intro-stat"><b>'+Number(data.soon||0)+'</b><span>'+tr('۷ روز آینده','NEXT 7 DAYS')+'</span></div>')+
  '<div class="panel"><div class="panel-head"><div><h3>'+tr('۳۰ روز آینده','Next 30 days')+'</h3><span>'+Number(data.expired||0)+' '+tr('منقضی','expired')+' · '+Number(data.today||0)+' '+tr('امروز','today')+'</span></div><div class="toolbar"><button class="ghost" data-action="expiry-select-all">'+tr('انتخاب همه','Select all')+'</button><button class="primary" data-action="bulk-renew">+30d '+tr('انتخاب‌شده‌ها','selected')+'</button></div></div><div class="table">'+(rows||'<div class="empty">'+tr('موردی برای انقضا در این بازه نیست.','Nothing expires in this window.')+'</div>')+'</div></div>';
}
async function quickRenew(kind,key,name){
  const days=Number(prompt(tr('چند روز اضافه شود؟','Days to add?'),'30'));if(!Number.isFinite(days)||days<0)return;
  const quota=Number(prompt(tr('چند GB حجم اضافه شود؟ 0 یعنی بدون تغییر','GB to add? 0 means unchanged'),'0'));if(!Number.isFinite(quota)||quota<0)return;
  try{await api('/api/renew',{method:'POST',body:JSON.stringify({kind,key,days,add_quota_gb:quota,reset_usage:false,enable:true})});toast(tr('تمدید انجام شد','Renewed'));await currentView()}catch(e){alert(e.message)}
}
async function bulkRenew(){
  const targets=[...document.querySelectorAll('.expiry-check:checked')].map(x=>({kind:x.dataset.kind,key:dataDec(x.dataset.key)}));if(!targets.length){alert(tr('حداقل یک کاربر انتخاب کن','Select at least one client'));return}
  const days=Number(prompt(tr('روز تمدید همه','Days to add to all'),'30'));if(!Number.isFinite(days)||days<0)return;
  const quota=Number(prompt(tr('GB اضافه برای همه','GB to add to all'),'0'));if(!Number.isFinite(quota)||quota<0)return;
  try{const r=await api('/api/renew/bulk',{method:'POST',body:JSON.stringify({targets,days,add_quota_gb:quota,reset_usage:false,enable:true})});toast((r.ok||[]).length+' '+tr('تمدید شد','renewed'));await expiryView()}catch(e){alert(e.message)}
}
async function outlineWorkspace(renderToken=window.__viewRenderToken){
  title.textContent='Outline';setPageContext('OUTLINE SERVER');
  const state=await api('/api/protocols/outline');if(renderToken!==window.__viewRenderToken||activeView!=='outline')return;
  const keys=(state.keys||[]).map(k=>'<div class="row"><div><b>'+htmlEsc(k.name||('Outline '+k.id))+'</b><div class="muted">ID '+htmlEsc(k.id||'')+'</div></div><div><b>'+htmlEsc(k.method||'Shadowsocks')+'</b><div class="muted">Port '+htmlEsc(k.port||'auto')+'</div></div><div><b>'+fmtBytes((k.dataLimit||{}).bytes||0)+'</b><div class="muted">'+tr('سقف رسمی API','Official API limit')+'</div></div><div class="toolbar"><button class="ghost" data-action="access-detail-by-key" data-kind="outline" data-key="'+dataEnc(k.id)+'">'+tr('جزئیات','Details')+'</button><button class="danger" data-action="outline-delete" data-id="'+dataEnc(k.id)+'">'+tr('حذف','Delete')+'</button></div></div>').join('');
  content.innerHTML=viewIntro('OUTLINE SERVER','Outline',tr('اتصال واقعی به Outline Server API رسمی؛ کلید Fake ساخته نمی‌شود.','Real integration with the official Outline Server API; no fake keys are generated.'),state.ready?'<button class="primary" data-action="outline-create">＋ '+tr('Access Key جدید','New access key')+'</button>':'<button class="primary" data-action="nav" data-view="operations">'+tr('تنظیم Outline API','Configure Outline API')+'</button>')+
  (state.ready?'<div class="panel"><div class="panel-head"><div><h3>Access Keys</h3><span>'+Number(state.count||0)+' '+tr('کلید','keys')+'</span></div><button class="ghost" data-action="refresh">'+tr('بروزرسانی','Refresh')+'</button></div><div class="table">'+(keys||'<div class="empty">'+tr('کلیدی وجود ندارد','No keys yet')+'</div>')+'</div></div>':'<div class="wizard-note danger-note"><b>SETUP</b><span>'+htmlEsc(state.error||tr('ابتدا API URL و SHA256 گواهی Outline Server را در Automation & Integrations وارد کن.','Configure the Outline Server API URL and certificate SHA256 in Automation & Integrations first.'))+'</span></div>');
}
async function openOutlineCreate(plan=null){
  modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">OUTLINE ACCESS KEY</div><h3>'+tr('ساخت کلید Outline','Create Outline key')+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="form-grid two"><label>'+tr('نام','Name')+'<input id="outlineName" value="client01"></label><label>'+tr('Port اختیاری','Optional port')+'<input id="outlinePort" type="number" min="0" max="65535" value="'+Number((plan?.defaults||{}).port||0)+'"></label><label>'+tr('حجم GB','Quota GB')+'<input id="outlineQuota" type="number" min="0" value="'+Number(plan?.quota_gb||0)+'"></label></div><div class="wizard-note"><b>'+tr('API واقعی Outline','Real Outline API')+'</b><span>'+tr('Makia کلید را از Outline Server می‌گیرد، سپس QR و Client Portal را از همان ss:// Access Key می‌سازد.','Makia creates the key through Outline Server, then builds QR and Client Portal from the returned ss:// access key.')+'</span></div><div class="wizard-footer"><button class="ghost" data-action="modal-close">'+tr('انصراف','Cancel')+'</button><button class="primary" data-action="outline-create-save">'+tr('ساخت','Create')+'</button></div></div></div>';
}
async function createOutlineKey(){
  const payload={name:document.getElementById('outlineName').value.trim(),port:Number(document.getElementById('outlinePort').value||0),quota_gb:Number(document.getElementById('outlineQuota').value||0)};
  try{const r=await api('/api/protocols/outline/keys',{method:'POST',body:JSON.stringify(payload)});closeModal();await openClientPortal('outline',String(r.id),payload.name)}catch(e){alert(e.message)}
}
async function deleteOutlineKey(id){if(!confirm(tr('این Outline Access Key حذف شود؟','Delete this Outline access key?')))return;try{await api('/api/protocols/outline/keys/'+encodeURIComponent(id),{method:'DELETE'});await outlineWorkspace()}catch(e){alert(e.message)}}
async function diagnosticsView(renderToken=window.__viewRenderToken){
  title.textContent=tr('عیب‌یابی کاربر','Client Diagnostics');setPageContext('CLIENT DIAGNOSTICS');
  const rows=await api('/api/access');if(renderToken!==window.__viewRenderToken||activeView!=='diagnostics')return;
  content.innerHTML=viewIntro('CLIENT DIAGNOSTICS',tr('عیب‌یابی یک‌کلیکی','One-click client diagnostics'),tr('Credential، Runtime، DNS، Port، Expiry و Quota را با داده واقعی همان پروتکل بررسی می‌کند.','Checks credential, runtime, DNS, port, expiry and quota using real protocol state.'),'<button class="ghost" data-action="self-test">'+tr('Self-Test سرور','Server Self-Test')+'</button>')+
  '<div class="panel"><div class="form-grid two"><label>'+tr('کاربر','Client')+'<select id="diagClient">'+rows.map(x=>'<option value="'+dataEnc(x.kind+':'+x.key)+'">'+htmlEsc(x.name+' · '+String(x.protocol||x.kind).toUpperCase())+'</option>').join('')+'</select></label><div class="form-action-align"><button class="primary" data-action="client-diagnose">'+tr('اجرای عیب‌یابی','Run diagnostics')+'</button></div></div><div id="diagResult" class="diagnostics-results"><div class="empty">'+tr('یک کاربر را انتخاب و تست را اجرا کن.','Select a client and run the test.')+'</div></div></div>';
}
async function runClientDiagnostics(){
  const raw=dataDec(document.getElementById('diagClient')?.value||''),idx=raw.indexOf(':');if(idx<1)return;
  const kind=raw.slice(0,idx),key=raw.slice(idx+1),root=document.getElementById('diagResult');root.innerHTML='<div class="loading-state"><span class="spinner"></span></div>';
  try{const d=await api('/api/diagnostics/access/'+encodeURIComponent(kind)+'/'+encodeURIComponent(key));root.innerHTML='<div class="diagnostic-score '+(d.ok?'':'fail')+'"><b>'+(d.ok?'PASS':'ATTENTION')+'</b><span>'+Number(d.critical)+' critical · '+Number(d.warnings)+' warning</span></div><div class="diagnostic-check-list">'+(d.checks||[]).map(x=>'<div class="diagnostic-check '+(x.ok?'ok':x.level==='warn'?'warn':'bad')+'"><span>'+(x.ok?'✓':'!')+'</span><div><b>'+htmlEsc(x.name)+'</b><small>'+htmlEsc(x.detail||'')+'</small></div></div>').join('')+'</div>'}catch(e){root.innerHTML='<div class="wizard-note danger-note">'+htmlEsc(e.message)+'</div>'}
}
async function operationsView(renderToken=window.__viewRenderToken){
  title.textContent=tr('اتوماسیون و اتصال‌ها','Automation & Integrations');setPageContext('AUTOMATION / INTEGRATIONS');
  const [i,n]=await Promise.all([api('/api/integrations'),api('/api/notifications?limit=8').catch(()=>[])]);
  if(renderToken!==window.__viewRenderToken||activeView!=='operations')return;
  const card=(name,status,desc,actions)=>'<article class="ops-card"><div class="ops-card-head"><div><h3>'+name+'</h3><span>'+desc+'</span></div><span class="status-chip '+(status?'ok':'warn')+'">'+(status?tr('آماده','READY'):'SETUP')+'</span></div><div class="toolbar">'+actions+'</div></article>';
  const cards=[
    card('Outline',i.outline.configured,tr('اتصال امن با Cert SHA256 به Outline Server API رسمی','Pinned-certificate connection to official Outline Server API'),'<button class="primary" data-action="integration-outline">'+tr('تنظیم','Configure')+'</button><button class="ghost" data-action="integration-test" data-kind="outline">Test</button>'),
    card('Cloudflare DNS',i.cloudflare.configured,tr('تعویض A record واقعی برای Migration؛ همیشه DNS-only برای VPN خام','Real A-record cutover for migration; raw VPN stays DNS-only'),'<button class="primary" data-action="integration-cloudflare">'+tr('تنظیم','Configure')+'</button><button class="ghost" data-action="integration-test" data-kind="cloudflare">Test</button>'),
    card('Telegram Alerts',i.telegram.configured&&i.telegram.enabled,tr('هشدار سرویس، منابع، Backup و Migration','Service, resource, backup and migration alerts'),'<button class="primary" data-action="integration-telegram">'+tr('تنظیم','Configure')+'</button><button class="ghost" data-action="integration-test" data-kind="telegram">Test</button>'),
    card(tr('بکاپ زمان‌بندی‌شده','Scheduled Backup'),i.backup_schedule.enabled,tr('Full Migration رمزگذاری‌شده + Retention + Remote SFTP','Encrypted Full Migration + retention + remote SFTP'),'<button class="primary" data-action="integration-backup">'+tr('تنظیم','Configure')+'</button>')
  ];
  content.innerHTML=viewIntro('AUTOMATION',tr('اتوماسیون و اتصال‌های خارجی','Automation & integrations'),tr('Secretها با کلید داخلی Makia رمزگذاری می‌شوند و در UI دوباره نمایش داده نمی‌شوند.','Secrets are encrypted with Makia internal crypto and are never redisplayed in full.'),'<button class="ghost" data-action="nav" data-view="backups">'+tr('Disaster Recovery','Disaster Recovery')+'</button>')+
    '<div class="ops-grid">'+cards.join('')+'</div><div class="panel"><div class="panel-head"><div><h3>'+tr('هشدارهای اخیر','Recent alerts')+'</h3><span>TELEGRAM / LOCAL</span></div></div><div class="table">'+((n||[]).map(x=>'<div class="row"><div><b>'+htmlEsc(x.title)+'</b><div class="muted">'+htmlEsc(x.detail||'')+'</div></div><span class="status-chip '+(x.level==='error'?'bad':x.level==='warn'?'warn':'ok')+'">'+htmlEsc(x.level)+'</span><span>'+htmlEsc(x.created_at||'')+'</span><span>'+((x.delivered)?'Telegram ✓':'Local')+'</span></div>').join('')||'<div class="empty">'+tr('هشداری ثبت نشده','No alerts recorded')+'</div>')+'</div></div>';
}
async function configureIntegration(kind){
  const current=await api('/api/integrations');
  if(kind==='outline'){
    const apiUrl=prompt('Outline apiUrl',current.outline.api_url||'');if(!apiUrl)return;const cert=prompt('Outline certSha256','');if(!cert)return;
    try{await api('/api/integrations/outline',{method:'PUT',body:JSON.stringify({api_url:apiUrl,cert_sha256:cert})});toast('Outline READY');await operationsView()}catch(e){alert(e.message)};return;
  }
  if(kind==='cloudflare'){
    const token=prompt('Cloudflare API Token','');if(!token)return;const zone=prompt('Zone (example.com)',current.cloudflare.zone||'');if(!zone)return;const hostname=prompt('DNS hostname',current.cloudflare.hostname||window.PANEL_DOMAIN||'');if(!hostname)return;
    try{await api('/api/integrations/cloudflare',{method:'PUT',body:JSON.stringify({api_token:token,zone,hostname})});toast('Cloudflare READY');await operationsView()}catch(e){alert(e.message)};return;
  }
  if(kind==='telegram'){
    const token=prompt('Telegram Bot Token','');if(!token)return;const chat=prompt('Telegram Chat ID',current.telegram.chat_id||'');if(!chat)return;
    try{await api('/api/integrations/telegram',{method:'PUT',body:JSON.stringify({bot_token:token,chat_id:chat,enabled:true})});toast('Telegram READY');await operationsView()}catch(e){alert(e.message)};return;
  }
  if(kind==='backup'){
    const b=current.backup_schedule||{},hour=Number(prompt(tr('ساعت UTC اجرای بکاپ (0-23)','Backup UTC hour (0-23)'),String(b.hour??4)));if(!Number.isFinite(hour))return;
    const keep=Number(prompt(tr('چند بکاپ نگه داشته شود؟','How many backups to keep?'),String(b.keep??7)));if(!Number.isFinite(keep))return;
    const password=prompt(b.password_set?tr('رمز جدید (خالی = حفظ رمز فعلی)','New password (blank = keep current)'):tr('رمز بکاپ حداقل ۱۰ کاراکتر','Backup password, min 10 chars'),'');if(password===null)return;
    const remote=confirm(tr('Remote SFTP فعال شود؟','Enable remote SFTP copy?'));
    let remote_host='',remote_user='',remote_path='/var/backups/makia',remote_key_path='/root/.ssh/id_ed25519',remote_port=22;
    if(remote){remote_host=prompt('Remote host',b.remote_host||'')||'';remote_user=prompt('Remote SSH user',b.remote_user||'root')||'';remote_path=prompt('Remote path',b.remote_path||'/var/backups/makia')||'';remote_key_path=prompt('SSH key path',b.remote_key_path||'/root/.ssh/id_ed25519')||'';remote_port=Number(prompt('SSH port',String(b.remote_port||22))||22)}
    try{await api('/api/integrations/backup-schedule',{method:'PUT',body:JSON.stringify({enabled:true,hour,keep,password,remote_enabled:remote,remote_host,remote_user,remote_path,remote_key_path,remote_port})});toast(tr('زمان‌بندی بکاپ ذخیره شد','Backup schedule saved'));await operationsView()}catch(e){alert(e.message)}
  }
}
async function testIntegration(kind){try{const r=await api('/api/integrations/'+kind+'/test',{method:'POST'});alert(JSON.stringify(r,null,2))}catch(e){alert(e.message)}}
async function openDisasterRecoveryWizard(){
  try{
    const [ready,intg,self]=await Promise.all([api('/api/backups/migration-readiness'),api('/api/integrations'),api('/api/diagnostics/self-test')]);
    modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal migration-wizard"><div class="wizard-head"><div><div class="eyebrow">DISASTER RECOVERY ASSISTANT</div><h3>'+tr('آمادگی انتقال VPS','VPS migration readiness')+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="migration-preview-grid"><div><span>Domain</span><b>'+htmlEsc(ready.panel_domain||'—')+'</b></div><div><span>Domain configs</span><b>'+Number(ready.domain_based||0)+'</b></div><div><span>IP configs</span><b class="'+(Number(ready.ip_based||0)?'warn-text':'ok-text')+'">'+Number(ready.ip_based||0)+'</b></div><div><span>Server Self-Test</span><b class="'+(self.ok?'ok-text':'bad-text')+'">'+htmlEsc(self.summary||'UNKNOWN')+'</b></div><div><span>Cloudflare</span><b class="'+(intg.cloudflare.configured?'ok-text':'warn-text')+'">'+(intg.cloudflare.configured?'READY':'SETUP')+'</b></div></div><div class="wizard-note"><b>'+tr('ترتیب امن','Safe order')+'</b><span>'+tr('۱) Full Migration Backup → ۲) Restore روی VPS جدید → ۳) Runtime PASS → ۴) تغییر DNS → ۵) تست Client.','1) Full Migration Backup → 2) restore new VPS → 3) runtime PASS → 4) DNS cutover → 5) client test.')+'</span></div>'+(Number(ready.ip_based||0)?'<div class="wizard-note danger-note"><b>'+tr('کانفیگ IP-based','IP-based configs')+'</b><span>'+tr('این کانفیگ‌ها بعد از تغییر IP بدون Re-export تضمین نمی‌شوند.','These configs cannot be guaranteed after the IP changes without re-export.')+'</span></div>':'')+'<div class="wizard-footer"><button class="primary" data-action="portable-backup">'+tr('ساخت Full Backup','Build Full Backup')+'</button>'+(intg.cloudflare.configured?'<button class="ghost" data-action="cloudflare-cutover">'+tr('DNS Cutover','DNS Cutover')+'</button>':'')+'<button class="ghost" data-action="migration-restore-open">'+tr('Restore Backup','Restore Backup')+'</button></div></div></div>';
  }catch(e){alert(e.message)}
}
async function cloudflareCutover(){
  const ip=prompt(tr('IPv4 جدید VPS','New VPS IPv4'),'');if(!ip)return;
  if(!confirm(tr('A record واقعی Cloudflare به '+ip+' تغییر کند؟ فقط بعد از PASS شدن Restore انجام بده.','Change the real Cloudflare A record to '+ip+'? Do this only after restore PASS.')))return;
  try{const r=await api('/api/integrations/cloudflare/cutover',{method:'POST',body:JSON.stringify({ipv4:ip,ttl:120})});alert(JSON.stringify(r,null,2))}catch(e){alert(e.message)}
}

async function connectivityLab(renderToken=window.__viewRenderToken){
  title.textContent='Connectivity Lab';setPageContext('CONNECTIVITY READINESS');
  content.innerHTML='<div class="loading-state"><span class="spinner"></span><b>در حال بررسی Runtime و Endpointها…</b></div>';
  const safe=async(url)=>{try{return await api(url)}catch(e){return {error:e.message||String(e)}}};
  const [stack,matrix,self,xray,wg,ovpn]=await Promise.all([
    safe('/api/protocols'),safe('/api/protocols/endpoint-matrix'),safe('/api/diagnostics/self-test'),
    safe('/api/protocols/xray/diagnostics'),safe('/api/protocols/wireguard/diagnostics'),safe('/api/protocols/openvpn/diagnostics')
  ]);
  if(renderToken!==window.__viewRenderToken||activeView!=='connectivity')return;
  const ssh=stack?.ssh||{};
  const state=(ok)=>'<span class="status-chip '+(ok?'ok':'warn')+'">'+(ok?'Server ready':'Check required')+'</span>';
  const field='<span class="field-badge">نیاز به تست از داخل ایران</span>';
  const cards=[
    ['SSH / NPV',Boolean(ssh.service_active),'TCP',ssh.port||22,'سرویس SSH و Policy Engine'],
    ['Xray / V2Ray',Boolean(xray.service_active&&xray.root_validation!==false&&xray.service_validation!==false),'TCP/UDP','Inbound-based','Core + config validation'],
    ['WireGuard',Boolean(wg.runtime_ok||wg.service_active),'UDP',wg.port||stack?.wireguard?.port||'—','Listener / NAT / Forward'],
    ['OpenVPN',Boolean(ovpn.service_active&&ovpn.listener),String(ovpn.proto||stack?.openvpn?.proto||'').toUpperCase()||'UDP',ovpn.port||stack?.openvpn?.port||'—','PKI + listener']
  ];
  const rows=(matrix.rows||[]).map(r=>'<div class="lab-port-row"><b>'+htmlEsc(r.label||r.id)+'</b><span>'+htmlEsc((r.ports||[]).join(', ')||'—')+'</span><span>'+htmlEsc(r.transport||'—')+'</span><span class="'+(r.runtime?'ok-text':'bad-text')+'">'+(r.runtime?'Active':'Inactive')+'</span></div>').join('');
  content.innerHTML=[
    '<div class="pro-page connectivity-page">',
      '<section class="pro-page-head"><div><span class="pro-kicker">NETWORK READINESS</span><h1>Connectivity Lab</h1><p>سلامت سمت سرور را دقیق بررسی می‌کند؛ نتیجه شبکه ایران فقط با Client واقعی داخل ایران معتبر است.</p></div><div class="pro-head-actions"><button class="ghost" data-action="endpoint-matrix">Endpoint Matrix</button><button class="primary" data-action="self-test">اجرای Self-Test</button></div></section>',
      '<div class="iran-boundary"><b>مهم:</b><span>Server Ready به معنی «تأیید اتصال از داخل ایران» نیست. فیلترینگ، اپراتور، شهر، IPv4/IPv6 و مسیر بین‌الملل می‌توانند نتیجه را تغییر دهند. Stable فقط بعد از Field Test واقعی علامت می‌خورد.</span></div>',
      '<section class="connectivity-grid">'+cards.map(x=>'<article class="connectivity-card"><div class="connectivity-title"><div><b>'+x[0]+'</b><small>'+x[4]+'</small></div>'+state(x[1])+'</div><div class="connectivity-meta"><div><span>Transport</span><b>'+htmlEsc(x[2])+'</b></div><div><span>Port</span><b>'+htmlEsc(String(x[3]))+'</b></div></div>'+field+'</article>').join('')+'</section>',
      '<section class="pro-directory"><div class="pro-directory-toolbar"><div><h3>Port / Runtime matrix</h3><small>Transport-aware server validation</small></div></div><div class="lab-port-head"><span>Service</span><span>Port</span><span>Transport</span><span>Runtime</span></div><div class="lab-port-list">'+(rows||'<div class="empty">Matrix data unavailable.</div>')+'</div></section>',
      '<section class="field-test-card"><div><span class="pro-kicker">IRAN FIELD GATE</span><h3>تست واقعی قبل از Stable</h3><p>برای هر پروتکل باید از حداقل یک اتصال Mobile و یک اتصال Fixed داخل ایران، اتصال واقعی، DNS، Handshake، دریافت اینترنت و Reconnect آزمایش شود.</p></div><ol><li>SSH/NPV: Login و قطع/وصل مجدد</li><li>Xray: VLESS/REALITY و سایر Profileهای مورد استفاده</li><li>WireGuard: Handshake + Route اینترنت</li><li>OpenVPN: TLS/PKI + Route اینترنت</li></ol></section>',
      '<div class="lab-self-summary"><span>Self-Test</span><b class="'+(self.ok?'ok-text':'bad-text')+'">'+htmlEsc(self.summary||'Unavailable')+'</b><small>'+(self.error?htmlEsc(self.error):Number(self.critical||0)+' critical · '+Number(self.warnings||0)+' warning')+'</small></div>',
    '</div>'
  ].join('');
}

function applyLanguageShell(){
  const fa={dashboard:'داشبورد',inbounds:'Inboundها',access:'کاربران',ssh:'SSH / NPV',xray:'Xray / V2Ray',wireguard:'WireGuard',openvpn:'OpenVPN',sessions:'اتصال‌های زنده',services:'سرویس‌ها',protocols:'شبکه و پورت‌ها',nodes:'نودها',connectivity:'Connectivity Lab',backups:'بکاپ',audit:'لاگ‌ها',updates:'بروزرسانی',settings:'تنظیمات',support:'پشتیبانی'};
  const en={dashboard:'Dashboard',inbounds:'Inbounds',access:'Clients',ssh:'SSH / NPV',xray:'Xray / V2Ray',wireguard:'WireGuard',openvpn:'OpenVPN',sessions:'Live Sessions',services:'Services',protocols:'Network / Ports',nodes:'Nodes',connectivity:'Connectivity Lab',backups:'Backup',audit:'Logs',updates:'Update',settings:'Settings',support:'Support'};
  const dict=window.MAKIA_LANG==='en'?en:fa;
  document.documentElement.lang=window.MAKIA_LANG==='en'?'en':'fa';
  document.documentElement.dir=window.MAKIA_LANG==='en'?'ltr':'rtl';
  document.querySelectorAll('nav.pro-nav button[data-view]').forEach(b=>{const label=dict[b.dataset.view];const t=b.querySelector('b');if(label&&t)t.textContent=label});
}
const views={dashboard,inbounds:inboundsWorkspace,access,ssh:accounts,xray:xrayWorkspace,wireguard,openvpn:openvpnWorkspace,accounts,sessions,services,protocols,guides,nodes,security,connectivity:connectivityLab,backups,audit:auditView,updates,settings,support:supportCenter};
window.__viewRenderToken=0;
function currentView(){const token=++window.__viewRenderToken;return(views[activeView]||dashboard)(token)}
function switchView(v){
  activeView=v;
  setPageContext(v==='dashboard'?'OVERVIEW':v==='inbounds'?'INBOUNDS':v==='access'?'CLIENTS':v==='ssh'?'SSH CLIENTS':v==='xray'?'XRAY CLIENTS':v==='wireguard'?'WIREGUARD PEERS':v==='openvpn'?'OPENVPN CLIENTS':v==='connectivity'?'CONNECTIVITY LAB':v==='settings'?'SETTINGS':'MAKIA CONTROL CENTER');
  document.querySelectorAll('nav button[data-view]').forEach(x=>x.classList.toggle('active',x.dataset.view===v));
  document.querySelectorAll('.pro-nav-group').forEach(g=>{
    const name=g.dataset.groupRoot;
    const shouldOpen=(name==='protocols'&&['ssh','xray','wireguard','openvpn','inbounds'].includes(v))||(name==='infra'&&['services','protocols','sessions','nodes','connectivity'].includes(v))||(name==='system'&&['audit','backups','updates'].includes(v));
    if(shouldOpen)g.classList.add('open');
  });
  document.body.classList.remove('menu-open');
  document.querySelector('.mobile-menu-toggle')?.setAttribute('aria-expanded','false');
  return currentView();
}
document.querySelectorAll('nav button[data-view]').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.view)));
applyLanguageShell();localizeVisibleUi(document);ensureSessionContext().catch(()=>{});switchView('dashboard');
if('serviceWorker' in navigator){window.addEventListener('load',()=>navigator.serviceWorker.register('/static/sw.js').catch(()=>{}));}
