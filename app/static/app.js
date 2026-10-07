// Historical compatibility: the stored theme key "glass" remains supported; Glass Aurora is rendered by the current shell.
// Legacy CI marker retained intentionally: glass-status-hero legacy.
const content=document.querySelector('#content'),title=document.querySelector('#pageTitle'),modalRoot=document.querySelector('#modalRoot');let activeView='dashboard';
const pageContext=document.querySelector('#pageContext');
function htmlEsc(v){return String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]))}
function dataEnc(v){return encodeURIComponent(String(v??''))}
function dataDec(v){try{return decodeURIComponent(String(v??''))}catch{return String(v??'')}}
function formEl(id){const el=document.getElementById(id);if(!el)throw new Error('Form control '+id+' is not available');return el}
function formValue(id,fallback=''){const el=document.getElementById(id);return el?el.value:fallback}
function formChecked(id){const el=document.getElementById(id);return Boolean(el&&el.checked)}
function setFieldValue(id,value){const el=document.getElementById(id);if(el)el.value=value}

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
  const anchor=kind==='wireguard'?'wireguard':kind==='openvpn'?'openvpn':kind==='ssh'?'ssh':kind==='outline'?'outline':'xray';
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
        '<div class="pro-directory-toolbar"><div class="pro-filter-tabs" id="accessSegments"><button class="active" data-filter-value="all">همه</button><button data-filter-value="xray">Xray</button><button data-filter-value="ssh">SSH</button><button data-filter-value="wireguard">WireGuard</button><button data-filter-value="openvpn">OpenVPN</button><button data-filter-value="outline">Outline</button></div><div class="pro-search-wrap"><span>⌕</span><input id="accessSearch" placeholder="جستجو نام کاربر یا پروتکل..."></div></div>',
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
  if(a.kind==='xray'||a.kind==='outline'){
    const used=fmtBytes(a.used_bytes||0),quota=a.quota_bytes?fmtBytes(a.quota_bytes):'∞';
    return used+' / '+quota;
  }
  if(a.kind==='wireguard')return fmtBytes(Number(a.rx||0)+Number(a.tx||0));
  if(a.kind==='ssh')return Number(a.online||0)+' / '+Number(a.connection_limit||1)+' session';
  return 'PKI';
}
function accessExpiryText(a){
  if(a.kind==='ssh')return a.expire_date||'بدون انقضا';
  if(a.kind==='xray'||a.kind==='outline')return a.expire_at?new Date(a.expire_at*1000).toLocaleDateString():'بدون انقضا';
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
  const shareLabel=a.kind==='ssh'?'NPV / QR':a.kind==='xray'?'QR / Share':a.kind==='wireguard'?'QR / Share':a.kind==='outline'?'Access Key / QR':'';
  let manage='';
  if(a.kind==='ssh'){
    manage='<button class="primary" data-action="manage-access" data-id="'+dataEnc(a.id)+'">'+htmlEsc(tr('ویرایش کاربر','Edit user'))+'</button><button class="ghost" data-action="account-disconnect" data-user="'+key+'">'+htmlEsc(tr('قطع اتصال','Disconnect'))+'</button>';
  }else if(a.kind==='xray'){
    manage='<button class="primary" data-action="manage-access" data-id="'+dataEnc(a.id)+'">'+htmlEsc(tr('Policy / تنظیمات','Policy / settings'))+'</button><button class="ghost" data-action="access-diagnostics" data-kind="xray" data-key="'+key+'" data-name="'+name+'">Diagnostics</button>';
  }else if(a.kind==='wireguard'){
    const enabled=a.enabled!==false;
    manage='<button class="'+(enabled?'soft':'primary')+'" data-action="wg-toggle" data-key="'+key+'" data-enabled="'+(enabled?'0':'1')+'">'+htmlEsc(enabled?tr('غیرفعال کردن','Disable'):tr('فعال کردن','Enable'))+'</button><button class="ghost" data-action="wg-reissue" data-key="'+key+'">'+htmlEsc(tr('تعویض کلید','Reissue'))+'</button><button class="ghost" data-action="access-diagnostics" data-kind="wireguard" data-key="'+key+'" data-name="'+name+'">Diagnostics</button>';
  }else if(a.kind==='outline'){
    const quotaGb=Math.round(Number(a.quota_bytes||0)/1073741824*100)/100;
    manage='<button class="primary" data-action="outline-renew" data-key="'+key+'">+30D</button><button class="ghost" data-action="outline-quota" data-key="'+key+'" data-name="'+name+'" data-quota="'+quotaGb+'">'+htmlEsc(tr('حجم','Quota'))+'</button><button class="ghost" data-action="outline-reissue" data-key="'+key+'" data-name="'+name+'">'+htmlEsc(tr('تعویض کلید','Reissue'))+'</button><button class="ghost" data-action="access-diagnostics" data-kind="outline" data-key="'+key+'" data-name="'+name+'">Diagnostics</button>';
  }else if(a.kind==='openvpn'){
    manage='<button class="primary" data-action="nav" data-view="openvpn">'+htmlEsc(tr('مدیریت OpenVPN','Manage OpenVPN'))+'</button><button class="ghost" data-action="openvpn-wstunnel-client" data-name="'+name+'">WStunnel 443</button><button class="ghost" data-action="access-diagnostics" data-kind="openvpn" data-key="'+key+'" data-name="'+name+'">Diagnostics</button>';
  }else if(a.kind==='openvpn_wstunnel'){
    manage='<button class="primary" data-action="nav" data-view="protocols">WStunnel 443</button><button class="ghost" data-action="openvpn-wstunnel-client" data-name="'+name+'">'+htmlEsc(tr('بازسازی بسته','Rebuild package'))+'</button>';
  }else{
    manage='<button class="primary" data-action="nav" data-view="'+kind+'">'+htmlEsc(tr('مدیریت پروتکل','Manage protocol'))+'</button><button class="ghost" data-action="access-diagnostics" data-kind="'+kind+'" data-key="'+key+'" data-name="'+name+'">Diagnostics</button>';
  }
  const nativeLabel=['openvpn','openvpn_wstunnel'].includes(a.kind)?'دانلود فایل OVPN':a.kind==='wireguard'?'دانلود Config':a.kind==='outline'?'Access Key':'Native config';
  const deliveryButtons=a.can_export?[
    canShare&&shareLabel?'<button class="ghost" data-action="access-share" data-kind="'+kind+'" data-key="'+key+'" data-name="'+name+'">'+shareLabel+'</button>':'',
    '<button class="ghost" data-action="native-export" data-kind="'+kind+'" data-key="'+key+'">'+nativeLabel+'</button>',
    '<button class="primary" data-action="client-portal" data-kind="'+kind+'" data-key="'+key+'" data-name="'+name+'">'+htmlEsc(tr('لینک اختصاصی کاربر','Client portal link'))+'</button>',
    '<button class="ghost" data-action="protected-export" data-kind="'+kind+'" data-key="'+key+'" data-name="'+name+'">'+htmlEsc(tr('بسته رمزدار','Protected ZIP'))+'</button>',
    '<button class="ghost" data-action="client-guide" data-kind="'+(a.kind==='openvpn_wstunnel'?'openvpn':kind)+'">'+htmlEsc(tr('راهنمای اتصال','Connection guide'))+'</button>'
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
    outline:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M8 8h8v8H8zM5 12h3m8 0h3M12 5v3m0 8v3"/></svg>',
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
  if(kind==='openvpn_wstunnel')return Boolean(s.openvpn_wstunnel?.ready);
  if(kind==='outline')return Boolean(s.outline?.installed&&s.outline?.api_ok);
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
      ['openvpn','OpenVPN','PKI با TCP/UDP قابل تنظیم','Certificate · OVPN · TCP/UDP'],
      ['openvpn_wstunnel','WStunnel 443','OpenVPN داخل WebSocket/TLS','HTTPS/443 · Restricted networks'],
      ['outline','Outline','Shadowsocks مدیریت‌شده','Access Key · QR · Data Limit']
    ];
    body='<div class="provision-intro"><span class="pro-kicker">CHOOSE PROTOCOL</span><h4>نوع دسترسی را انتخاب کن</h4><p>فقط تنظیمات ضروری نمایش داده می‌شود؛ گزینه‌های تخصصی داخل بخش پیشرفته باقی می‌مانند.</p></div><div class="wizard-protocols pro-protocol-picker">'+cards.map(x=>{
      const ready=wizardProtocolReady(x[0]);
      const setupAction=x[0]==='openvpn_wstunnel'?'openvpn-wstunnel-setup':'protocol-setup';
      const glyph=x[0]==='openvpn_wstunnel'?'wstunnel':x[0];
      return '<button class="wizard-protocol pro-protocol-card '+(ready?'ready':'not-ready')+'" data-action="'+(ready?'wizard-protocol':setupAction)+'" data-kind="'+x[0]+'"><span class="protocol-card-icon '+x[0]+'">'+protocolGlyph(glyph)+'</span><div class="protocol-card-copy"><b>'+x[1]+'</b><small>'+x[2]+'</small><em>'+x[3]+'</em></div><i>'+(ready?'آماده':'نیاز به راه‌اندازی')+'</i></button>';
    }).join('')+'</div>';
  }else if(s.step===2){
    body=wizardIdentityFields(s);
  }else if(s.step===3){
    body=wizardPolicyFields(s);
  }else{
    body=wizardReview(s);
  }
  const protocolLabel=s.protocol?({ssh:'SSH',xray:'Xray / V2Ray',wireguard:'WireGuard',openvpn:'OpenVPN',openvpn_wstunnel:'WStunnel 443',outline:'Outline'}[s.protocol]||s.protocol):'انتخاب پروتکل';
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
  if(s.protocol==='openvpn_wstunnel') return [
    '<div class="wizard-section-title"><span class="pro-kicker">WSTUNNEL 443</span><h4>دسترسی مقاوم روی HTTPS/443</h4><p>برای این کاربر Certificate مستقل OpenVPN ساخته می‌شود و Transport از مسیر WSS روی Nginx/443 عبور می‌کند.</p></div>',
    '<div class="wizard-form two"><label>نام Client<input id="wizName" value="'+htmlEsc(s.name)+'"></label><label>Public endpoint<input value="'+htmlEsc(s.endpoint)+'" readonly></label></div>',
    '<div class="wizard-note"><b>Policy owner</b><span>پس از ساخت، این Artifact را به Client Account همان کاربر Bind کن تا Expiry، Quota، Device Limit و Concurrent Limit روی همان Subscription اعمال شوند.</span></div>'
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
  if(s.protocol==='openvpn_wstunnel') return '<div class="wizard-review-hint"><div class="review-icon">✓</div><h4>WStunnel 443 آماده است</h4><p>Certificate و بسته WStunnel/OpenVPN ساخته می‌شود. Policyهای کاربر از Client Platform و Binding همان Artifact اعمال می‌شوند.</p></div>';
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
    }else if(s.protocol==='openvpn_wstunnel'){
      r=await api('/api/protocols/openvpn/wstunnel/clients',{method:'POST',body:JSON.stringify({name:s.name,local_port:11941})});
      kind='openvpn_wstunnel';key=s.name;
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
    const isOutline=kind==='outline';
    const directTitle=isSsh?'NPV Tunnel / NapsternetV Import':isXray?'Xray Share Center':isOutline?'Outline Access Key / QR':'WireGuard QR';
    const directHelp=isSsh
      ?'در NPV Tunnel از Scan QR یا Import from Clipboard استفاده کن. لینک npvt-ssh شامل Host/User/Password همین اکانت است.'
      :isXray?'QR را در v2rayNG / Hiddify / NPV یا کلاینت سازگار اسکن کن؛ Copy Link نیز همان Share URI را می‌دهد.'
      :isOutline?'QR یا ss:// Access Key را در Outline Client یا کلاینت سازگار وارد کن.'
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
        '<div class="wizard-note"><b>Security</b><span>'+htmlEsc(isOutline?tr('QR و Access Key محرمانه‌اند؛ Quota و Expiry روی سرور اعمال می‌شوند و Outline محدودیت IP ساختگی ندارد.','QR and Access Key are secrets; server-side quota and expiry are enforced. Makia does not claim a fake Outline IP limit.'):tr('QR و Share Link حاوی Credential اتصال هستند؛ فقط برای همان کاربر ارسال شوند. Policyهای پشتیبانی‌شده روی سرور اعمال می‌شوند.','QR and share links contain credentials; send them only to the intended client. Supported policies remain server-enforced.'))+'</span></div>',
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
  const [rows,accessRows,operator]=await Promise.all([api('/api/accounts'),api('/api/access'),api('/api/settings/operator')]);
  if(renderToken!==window.__viewRenderToken||!['accounts','ssh'].includes(activeView))return;
  accountCache=rows;accessCache=accessRows;window.__operatorSettings=operator;
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
async function suggestUsername(){try{const d=await api('/api/accounts/new-defaults');setFieldValue('cUser',d.username||'')}catch(e){alert(e.message)}}
function clearAccountForm(){setFieldValue('cUser','');setFieldValue('cPass','');setFieldValue('cPlan','');setFieldValue('cNote','');setFieldValue('cLimit',1);setFieldValue('cDevice',1);setExpiryPreset('cExpire',30)}
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
    return '<div class="row account-row"><div><label class="check-user"><input class="account-check" type="checkbox" value="'+htmlEsc(a.username)+'"><div><b>'+htmlEsc(a.username)+'</b><div class="chips">'+statusFor(a)+'<span class="status-chip">Sessions '+Number(a.online||0)+'/'+Number(a.connection_limit||1)+'</span><span class="status-chip">Devices '+Number((a.online_ips||[]).length)+'/'+Number(a.device_limit||1)+'</span></div></div></label></div><div><b>'+htmlEsc(a.plan||'—')+'</b><div class="muted">'+htmlEsc(a.expire_date||'بدون انقضا')+(a.days_left!==null?' · '+a.days_left+'d':'')+'</div></div><div><b>'+htmlEsc((a.online_ips||[]).length?(a.online_ips||[]).join(', '):'بدون IP فعال')+'</b><div class="muted">'+htmlEsc(a.note||'بدون یادداشت')+'</div></div><div class="pro-row-actions"><button class="pro-more" data-action="access-detail" data-id="'+dataEnc('ssh:'+a.username)+'" aria-label="جزئیات '+dataEnc(a.username)+'">•••</button></div></div>';
  }).join(''):'<div class="empty">نتیجه‌ای پیدا نشد.</div>';
}
async function bulkExtendPreset(days){const usernames=selectedAccounts();if(!usernames.length){alert('حداقل یک کاربر را انتخاب کنید.');return}try{const r=await api('/api/accounts/bulk',{method:'POST',body:JSON.stringify({usernames,action:'extend',days})});if(r.failed?.length)alert('برخی عملیات ناموفق بود: '+r.failed.length);toast('تمدید انجام شد');await accounts()}catch(e){alert(e.message)}}
async function bulkAccounts(action){const usernames=selectedAccounts();if(!usernames.length){alert('حداقل یک کاربر را انتخاب کنید.');return}if(action==='disconnect'&&!confirm('اتصال کاربران انتخاب‌شده قطع شود؟'))return;try{const r=await api('/api/accounts/bulk',{method:'POST',body:JSON.stringify({usernames,action,days:0})});if(r.failed?.length)alert('برخی عملیات ناموفق بود: '+r.failed.length);await accounts()}catch(e){alert(e.message)}}
async function bulkExtend(){const usernames=selectedAccounts();if(!usernames.length){alert('حداقل یک کاربر را انتخاب کنید.');return}const days=Number(prompt('چند روز به تاریخ فعلی اضافه شود؟','30'));if(!days||days<1)return;try{const r=await api('/api/accounts/bulk',{method:'POST',body:JSON.stringify({usernames,action:'extend',days})});if(r.failed?.length)alert('برخی عملیات ناموفق بود: '+r.failed.length);await accounts()}catch(e){alert(e.message)}}
async function createAccount(){
  const p={username:formValue('cUser','').trim(),password:formValue('cPass','')||null,password_mode:'manual',expire_date:formValue('cExpire','')||null,plan:formValue('cPlan',''),note:formValue('cNote',''),connection_limit:Number(formValue('cLimit','1')||1),device_limit:Number(formValue('cDevice','1')||1),quota_mb:0,renewal_days:0};
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
async function saveAccount(u){try{const expire=formValue('eExpire','');const p={password:formValue('ePass','')||null,expire_date:expire||null,clear_expire:!expire,plan:formValue('ePlan',''),note:formValue('eNote',''),connection_limit:Number(formValue('eLimit','1')||1),device_limit:Number(formValue('eDevice','1')||1),quota_mb:0,renewal_days:0,enabled:formValue('eEnabled','1')==='1'};await api('/api/accounts/'+encodeURIComponent(u),{method:'PUT',body:JSON.stringify(p)});const secret=p.password;closeModal();if(secret)toast('رمز کاربر تغییر کرد؛ Artifact تحویل هم بروزرسانی شد.');await currentView()}catch(e){alert(e.message)}}
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
  title.textContent=tr('نودها','Nodes');setPageContext('MULTI-VPS FLEET');
  const rows=await api('/api/nodes');if(renderToken!==window.__viewRenderToken||activeView!=='nodes')return;
  const now=Date.now();
  const online=rows.filter(n=>n.last_seen_at&&now-Date.parse(n.last_seen_at)<180000).length;
  const cards=rows.map(n=>{
    let services={};try{services=JSON.parse(n.services_json||'{}')}catch(e){}
    const stale=!n.last_seen_at||now-Date.parse(n.last_seen_at)>=180000;
    const svc=Object.entries(services).map(([k,v])=>'<span class="'+(v?'up':'down')+'">'+htmlEsc(k)+' '+(v?'✓':'!')+'</span>').join('');
    return '<article class="ops-card"><div class="ops-card-head"><div><span class="pro-kicker">'+htmlEsc(n.region||'NODE')+'</span><h3>'+htmlEsc(n.name)+'</h3><small class="muted">'+htmlEsc(n.hostname||tr('منتظر Heartbeat','Waiting for heartbeat'))+'</small></div><span class="status-chip '+(!stale?'ok':'bad')+'">'+(!stale?tr('آنلاین','ONLINE'):tr('آفلاین','OFFLINE'))+'</span></div>'+
      '<div class="plan-facts"><span>CPU<b>'+htmlEsc(n.cpu??'-')+'%</b></span><span>RAM<b>'+htmlEsc(n.memory??'-')+'%</b></span><span>Disk<b>'+htmlEsc(n.disk??'-')+'%</b></span><span>'+htmlEsc(tr('کاربر','Users'))+'<b>'+Number(n.users||0)+'</b></span><span>'+htmlEsc(tr('فعال اخیر','Recent active'))+'<b>'+Number(n.online_users||0)+'</b></span><span>'+htmlEsc(tr('ترافیک NIC','NIC traffic'))+'<b>'+fmtBytes(n.traffic_bytes||0)+'</b></span></div>'+
      '<div class="node-service-chips">'+svc+'</div><div class="muted" style="margin-top:9px">'+htmlEsc(n.public_ip||'—')+' · '+htmlEsc(relativeSeen(n.last_seen_at))+' · v'+htmlEsc(n.version||'-')+'</div>'+
      '<div class="toolbar" style="margin-top:12px"><button class="danger" data-action="node-revoke" data-id="'+Number(n.id)+'">'+htmlEsc(tr('لغو نود','Revoke'))+'</button></div></article>';
  }).join('');
  content.innerHTML=[
    '<section class="pro-page-head"><div><span class="pro-kicker">MULTI-VPS FLEET</span><h1>'+htmlEsc(tr('داشبورد چند سرور','Multi-VPS Dashboard'))+'</h1><p>'+htmlEsc(tr('Heartbeat، منابع، سرویس‌ها، تعداد کاربر و ترافیک Nodeها در یک صفحه.','Heartbeat, resources, service health, client counts and traffic across nodes.'))+'</p></div><div class="pro-head-actions"><button class="primary" data-action="node-create">＋ '+htmlEsc(tr('افزودن نود','Add Node'))+'</button></div></section>',
    '<section class="pro-stat-strip"><div><span>'+htmlEsc(tr('کل نودها','Total nodes'))+'</span><b>'+rows.length+'</b></div><div><span>'+htmlEsc(tr('آنلاین','Online'))+'</span><b>'+online+'</b></div><div><span>'+htmlEsc(tr('آفلاین','Offline'))+'</span><b>'+(rows.length-online)+'</b></div><div><span>'+htmlEsc(tr('کاربر مدیریت‌شده','Managed clients'))+'</span><b>'+rows.reduce((a,n)=>a+Number(n.users||0),0)+'</b></div></section>',
    '<div class="notice">'+htmlEsc(tr('برای Nodeهای خارج از شبکه محلی، Controller را فقط از HTTPS در دسترس قرار بده.','Expose the controller to remote nodes over HTTPS only.'))+'</div>',
    '<section class="ops-card-grid">'+(cards||'<div class="empty">'+htmlEsc(tr('هنوز نودی ثبت نشده است.','No nodes enrolled yet.'))+'</div>')+'</section>'
  ].join('');
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
  window.__protocolData=stack;window.__operatorSettings=operator;accessCache=rows;
  const peers=rows.filter(x=>x.kind==='wireguard'),service=stack.wireguard||{},defs=operator.defaults||{};
  const active=peers.filter(p=>p.enabled!==false).length;
  const connected=peers.filter(p=>p.enabled&&p.handshake_age!==null&&p.handshake_age!==undefined&&p.handshake_age<180).length;
  const rx=peers.reduce((n,p)=>n+Number(p.rx||0),0),tx=peers.reduce((n,p)=>n+Number(p.tx||0),0);
  const peerRows=peers.map(p=>{
    const key=dataEnc(p.key),enabled=p.enabled!==false;
    return '<div class="row protocol-list-row"><div><b>'+htmlEsc(p.name)+'</b><div class="muted">'+htmlEsc(p.address||'WireGuard peer')+'</div></div><div><span class="status-chip '+(enabled?'ok':'bad')+'">'+(enabled?'فعال':'غیرفعال')+'</span><div class="muted">'+(p.handshake_age==null?'بدون Handshake':Math.floor(Number(p.handshake_age)/60)+' دقیقه پیش')+'</div></div><div><b>↓ '+fmtBytes(p.rx||0)+' · ↑ '+fmtBytes(p.tx||0)+'</b><div class="muted" dir="ltr">'+htmlEsc(p.endpoint||'—')+'</div></div><div class="pro-row-actions"><button class="pro-more" data-action="access-detail" data-id="'+dataEnc('wireguard:'+p.key)+'" aria-label="جزئیات '+dataEnc(p.name)+'">•••</button></div></div>';
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
  const [stack,clients]=await Promise.all([api('/api/protocols'),api('/api/protocol-clients?engine=xray')]);
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
  const [stack,clients,accessRows,operator]=await Promise.all([api('/api/protocols'),api('/api/protocol-clients?engine=xray'),api('/api/access'),api('/api/settings/operator')]);
  if(renderToken!==window.__viewRenderToken||activeView!=='xray')return;
  window.__protocolData=stack;window.__protocolClients=clients;window.__operatorSettings=operator;accessCache=accessRows;
  const engine=stack.xray||{},managed=clients.filter(x=>String(x.engine||'xray').toLowerCase()==='xray'),rows=accessRows.filter(x=>x.kind==='xray');
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
      'wstunnel-openvpn':'<button class="ghost" data-action="openvpn-wstunnel-setup">Configure 443</button><button class="soft" data-action="openvpn-wstunnel-client" data-name="">New user</button>',
      wstunnel:'<button class="ghost" data-action="wstunnel-setup">Configure WG</button>'
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
    '<section class="panel protocol-modes-panel"><div class="panel-head"><div><h3>Connection Modes</h3><span>IKEV2 · WIREGUARD · UDP · TCP · STEALTH · WSTUNNEL 443</span></div></div><div class="protocol-mode-grid">'+(protocolModeCards||'<div class="empty">Mode data unavailable.</div>')+'</div><div class="port-safe-note">WStunnel 443 جدید OpenVPN را داخل WebSocket/TLS از همان HTTPS/443 پنل عبور می‌دهد؛ WStunnel WG قدیمی همچنان Mode جداگانه است.</div></section>',
    '<section class="panel port-plan-panel"><div class="panel-head"><div><h3>TCP Port Ownership</h3><span>REAL LISTENER PREFLIGHT</span></div></div><div class="port-plan-grid">'+((modesData.port_plan?.rows||[]).map(r=>'<article><span>'+htmlEsc(r.service)+'</span><b>TCP/'+Number(r.port||0)+'</b><small class="'+(r.occupied?'warn-text':'ok-text')+'">'+(r.occupied?('Owned: '+htmlEsc(r.owner||'host service')):'Free now')+'</small></article>').join('')||'<div class="empty">Port plan unavailable.</div>')+'</div>'+((modesData.port_plan?.blockers?.openvpn_tcp||[]).length?'<div class="wizard-note danger-note"><b>OpenVPN TCP blockers</b><span>'+htmlEsc(modesData.port_plan.blockers.openvpn_tcp.join(' · '))+'</span></div>':'')+((modesData.port_plan?.blockers?.stealth||[]).length?'<div class="wizard-note danger-note"><b>Stealth blockers</b><span>'+htmlEsc(modesData.port_plan.blockers.stealth.join(' · '))+'</span></div>':'')+'<div class="port-safe-note">'+htmlEsc(modesData.port_plan?.note||'TCP/443 has one owner; UDP/443 may coexist independently.')+'</div></section>',
    '<section class="panel port-management-panel"><div class="panel-head"><div><h3>لیست پورت‌های فعال</h3><span>TRANSPORT-AWARE ALLOCATION</span></div></div><div class="port-table-head"><span>پروتکل</span><span>پورت</span><span>نوع اتصال</span><span>وضعیت</span><span>عملیات</span></div><div class="port-table-body">'+(portRows||'<div class="empty">پورت مدیریت‌شده‌ای پیدا نشد.</div>')+'</div><div class="port-safe-note">✓ بررسی تداخل پورت‌ها بر اساس Transport انجام می‌شود؛ TCP/443 و UDP/443 می‌توانند هم‌زمان فعال باشند.</div></section>',
    '<section class="split-grid"><div class="panel"><div class="panel-head"><div><h3>Engineها</h3><span>INSTALL / RUNTIME</span></div></div><div class="service-control-list">'+engineRows+'</div></div><div class="panel"><div class="panel-head"><div><h3>Xray Inbounds</h3><span>'+Number((x.inbounds||[]).length)+' DETECTED</span></div></div><div class="engine-inbounds">'+((x.inbounds||[]).length?(x.inbounds||[]).map(i=>'<div class="engine-inbound"><div><b>'+htmlEsc(String(i.protocol||'').toUpperCase())+'</b><span>'+htmlEsc(i.tag||'Inbound')+'</span></div><div><b>:'+Number(i.port||0)+'</b><span>'+Number(i.clients||0)+' users</span></div></div>').join(''):'<div class="empty compact">Inbound وجود ندارد.</div>')+'</div></div></section>',
    '<section class="panel"><div class="panel-head"><div><h3>Client Policy Snapshot</h3><span>'+clients.length+' XRAY RECORDS</span></div><button class="ghost" data-action="nav" data-view="xray">مدیریت کاربران Xray</button></div><div class="protocol-policy-mini">'+(clients.length?clients.slice(0,8).map(pc=>'<div><div><b>'+htmlEsc(pc.name)+'</b><span>'+htmlEsc(String(pc.protocol||'').toUpperCase())+'</span></div><strong class="'+(pc.enabled&&!pc.expired?'ok-text':'bad-text')+'">'+(pc.enabled&&!pc.expired?'Active':'Attention')+'</strong></div>').join(''):'<div class="empty compact">Client ثبت نشده است.</div>')+'</div></section>'
  ].join('');
}
function createXrayTunnel(){modalRoot.innerHTML=`<div class="modal-backdrop" onclick="if(event.target===this)closeModal()"><div class="modal"><div class="modal-head"><div><div class="eyebrow">XRAY TUNNEL</div><h3>Port Forward / Dokodemo</h3></div><button class="close-btn" onclick="closeModal()">×</button></div><div class="form-grid"><label>Name<input id="tnName" value="tunnel01"></label><label>Listen port<input id="tnListen" type="number" min="1" max="65535" value="8443"></label><label>Target host<input id="tnHost" placeholder="10.0.0.2 or example.com"></label><label>Target port<input id="tnPort" type="number" min="1" max="65535" value="443"></label><label>Network<select id="tnNetwork"><option value="tcp,udp">TCP + UDP</option><option value="tcp">TCP</option><option value="udp">UDP</option></select></label></div><div class="notice">Config قبل از Apply توسط Xray validate می‌شود و در خطا Rollback انجام می‌شود.</div><div class="toolbar"><button class="primary" onclick="submitXrayTunnel()">Create Tunnel</button><button class="ghost" onclick="closeModal()">Cancel</button></div></div></div>`}
async function submitXrayTunnel(){const payload={name:formValue('tnName','').trim(),listen_port:Number(formValue('tnListen','0')),target_host:formValue('tnHost','').trim(),target_port:Number(formValue('tnPort','0')),network:formValue('tnNetwork','tcp')};if(!payload.name||!payload.target_host||!payload.listen_port||!payload.target_port){alert('فیلدهای اصلی را کامل کنید.');return}try{const r=await api('/api/protocols/xray/tunnels',{method:'POST',body:JSON.stringify(payload)});closeModal();toast('Tunnel '+r.listen_port+' → '+r.target_host+':'+r.target_port+' created');await protocols()}catch(e){alert(e.message)}}


function protocolModeDescription(id){
  return {
    ikev2:'IPsec/IKEv2 با StrongSwan؛ مناسب Clientهای Native سیستم‌عامل.',
    wireguard:'WireGuard سریع با Peer، QR، Handshake و Traffic واقعی.',
    udp:'OpenVPN روی UDP؛ حالت کم‌تاخیر با Port قابل انتخاب.',
    tcp:'OpenVPN روی TCP؛ برای شبکه‌هایی که UDP مشکل دارد.',
    stealth:'OpenVPN پشت TLS/Stunnel؛ نیازمند Certificate معتبر.',
    'wstunnel-openvpn':'OpenVPN داخل WebSocket/TLS روی HTTPS TCP/443؛ مناسب شبکه‌های محدود و مشابه WStunnel در Windscribe.',
    wstunnel:'WireGuard داخل WSS/WebSocket؛ Mode قدیمی Makia و جدا از OpenVPN WStunnel.'
  }[id]||'';
}

async function openChangeProtocol(){
  let data=window.__protocolModes;
  if(!data||!Array.isArray(data.modes)){
    data=await api('/api/protocols/modes');
    window.__protocolModes=data;
  }
  const order=['ikev2','wireguard','udp','tcp','stealth','wstunnel-openvpn','wstunnel'];
  const byId=Object.fromEntries((data.modes||[]).map(x=>[x.id,x]));
  const rows=order.map(id=>{
    const m=byId[id]||{id,label:id.toUpperCase(),ports:[],transport:'',ready:false,status:{}};
    const port=(m.ports||[]).filter(Boolean).join(' / ')||'Setup';
    const iconKind=(id==='udp'||id==='tcp')?'openvpn':id==='wstunnel-openvpn'?'wstunnel':id;
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
      '<div class="change-protocol-foot"><span>Listener خام TCP/443 فقط یک Owner دارد. WStunnel 443 جدید Listener جدا نمی‌سازد؛ از مسیر WebSocket مخفی داخل Nginx/HTTPS موجود عبور می‌کند و با پنل روی 443 هم‌زیست است.</span><button class="ghost" data-action="modal-close">Cancel</button></div>',
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
  if(mode==='wstunnel-openvpn'){await setupOpenVPNWStunnel();return}
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
async function setupOpenVPNWStunnel(){
  const domain=prompt('OpenVPN WStunnel 443 domain',window.PANEL_DOMAIN||location.hostname);if(!domain)return;
  if(!confirm('OpenVPN از طریق WebSocket/TLS روی HTTPS TCP/443 فعال شود؟ Nginx همان پورت 443 را نگه می‌دارد و Makia فقط یک مسیر WebSocket امن اضافه می‌کند.'))return;
  try{
    const r=await api('/api/protocols/openvpn/wstunnel/bootstrap',{method:'POST',body:JSON.stringify({domain,public_port:443,bridge_port:10445,backend_port:11940,path_prefix:''})});
    configModal('OpenVPN WStunnel 443',r.client_command+'\n\nPublic: wss://'+domain+':443\nOpenVPN backend: loopback/'+r.status.target_port,'makia-openvpn-wstunnel.txt');
    toast('OpenVPN WStunnel 443 ready');
    await protocols();
  }catch(e){alert('OpenVPN WStunnel 443: '+e.message)}
}

async function createOpenVPNWStunnelProfile(name){
  if(!name){name=prompt('OpenVPN client name','');if(!name)return}
  try{
    const r=await api('/api/protocols/openvpn/wstunnel/clients',{method:'POST',body:JSON.stringify({name,local_port:11941})});
    configModal('WStunnel 443 · '+name,r.config,name+'-wstunnel.ovpn','openvpn_wstunnel',name);
    toast('WStunnel 443 package created for '+name);
  }catch(e){alert('WStunnel profile: '+e.message)}
}

async function setupWStunnel(){
  const domain=prompt('WStunnel WSS domain',window.PANEL_DOMAIN||'');if(!domain)return;
  const port=Number(prompt('Public WStunnel TCP port','8444'));if(!port)return;
  try{const r=await api('/api/protocols/wstunnel/bootstrap',{method:'POST',body:JSON.stringify({domain,port,path_prefix:''})});configModal('WStunnel client command',r.client_command+'\n\nWireGuard Endpoint: '+r.wireguard_endpoint,'makia-wstunnel-client.txt');toast('WStunnel listener ready')}catch(e){alert('WStunnel: '+e.message)}
}

async function installProtocol(component){if(!confirm('Install '+component+' and required packages?'))return;try{await api('/api/protocols/install',{method:'POST',body:JSON.stringify({component})});toast(component+' installed');await protocols()}catch(e){alert(e.message)}}
function showXrayInbounds(){document.querySelector('.protocol-grid')?.nextElementSibling?.scrollIntoView({behavior:'smooth'})}
async function createXrayInbound(){const defs=await api('/api/accounts/new-defaults').catch(()=>({username:'user001'}));modalRoot.innerHTML=`<div class="modal-backdrop" onclick="if(event.target===this)closeModal()"><div class="modal"><div class="modal-head"><div><div class="eyebrow">XRAY CLIENT + INBOUND</div><h3>ساخت دسترسی Xray</h3></div><button class="close-btn" onclick="closeModal()">×</button></div><div class="form-grid"><label>Protocol<select id="xiProtocol" onchange="syncXrayForm()"><option value="vless">VLESS</option><option value="vmess">VMess</option><option value="trojan">Trojan</option><option value="shadowsocks">Shadowsocks</option><option value="hysteria2">Hysteria2</option><option value="http">HTTP Proxy</option><option value="socks">SOCKS5</option></select></label><label>Transport<select id="xiTransport" onchange="syncXrayForm()"><option value="tcp">RAW / TCP</option><option value="ws">WebSocket</option><option value="grpc">gRPC</option><option value="httpupgrade">HTTPUpgrade</option><option value="xhttp">XHTTP</option><option value="kcp">mKCP</option></select></label><label>Security<select id="xiSecurity" onchange="syncXrayForm()"><option value="none">None</option><option value="tls">TLS</option><option value="reality">REALITY</option></select></label><label>Port<input id="xiPort" type="number" min="1" max="65535" value="2087"></label><label>Client name<input id="xiName" value="${htmlEsc(defs.username||'user001')}"></label><label>Public domain / IP<input id="xiEndpoint" value="${window.PANEL_DOMAIN||location.hostname}"></label><label id="xiPathWrap">Path / Service<input id="xiPath" value="/makia"></label><label id="xiSniWrap">Domain / SNI<input id="xiSni" value="${window.PANEL_DOMAIN||''}" placeholder="vpn.example.com"></label><label id="xiRealityWrap">REALITY target<input id="xiRealityDest" value="www.cloudflare.com:443" placeholder="www.example.com:443"></label><label>Traffic quota (GB)<input id="xiQuota" type="number" min="0" step="1" value="50"><div class="password-tools quota-tools"><button class="soft" onclick="setFieldValue('xiQuota',0)">∞</button><button class="soft" onclick="setFieldValue('xiQuota',10)">10</button><button class="soft" onclick="setFieldValue('xiQuota',20)">20</button><button class="soft recommended" onclick="setFieldValue('xiQuota',50)">50</button><button class="soft" onclick="setFieldValue('xiQuota',100)">100</button><button class="soft" onclick="setFieldValue('xiQuota',200)">200</button><button class="soft" onclick="setFieldValue('xiQuota',500)">500</button></div><span class="muted">0 = Unlimited</span></label><label>Expiry days<input id="xiDays" type="number" min="0" max="3650" value="30"><div class="password-tools duration-tools"><button class="soft" onclick="setFieldValue('xiDays',1)">1D</button><button class="soft" onclick="setFieldValue('xiDays',3)">3D</button><button class="soft" onclick="setFieldValue('xiDays',7)">7D</button><button class="soft" onclick="setFieldValue('xiDays',15)">15D</button><button class="soft recommended" onclick="setFieldValue('xiDays',30)">30D</button><button class="soft" onclick="setFieldValue('xiDays',60)">60D</button><button class="soft" onclick="setFieldValue('xiDays',90)">90D</button><button class="soft" onclick="setFieldValue('xiDays',0)">∞</button></div></label><label>Traffic reset cycle<input id="xiResetDays" type="number" min="0" max="3650" value="30"><div class="password-tools"><button class="soft" onclick="setFieldValue('xiResetDays',0)">Never</button><button class="soft" onclick="setFieldValue('xiResetDays',7)">7D</button><button class="soft recommended" onclick="setFieldValue('xiResetDays',30)">30D</button><button class="soft" onclick="setFieldValue('xiResetDays',60)">60D</button><button class="soft" onclick="setFieldValue('xiResetDays',90)">90D</button></div><span class="muted">حجم مصرفی در شروع هر دوره صفر می‌شود.</span></label><label>IP / Device limit<input id="xiIpLimit" type="number" min="1" max="50" value="1"><div class="password-tools"><button class="soft recommended" onclick="setFieldValue('xiIpLimit',1)">1</button><button class="soft" onclick="setFieldValue('xiIpLimit',2)">2</button><button class="soft" onclick="setFieldValue('xiIpLimit',3)">3</button><button class="soft" onclick="setFieldValue('xiIpLimit',5)">5</button><button class="soft" onclick="setFieldValue('xiIpLimit',10)">10</button></div><span class="muted">با Online-IP API هسته Xray مانیتور و توسط Policy Worker enforce می‌شود؛ روی Coreهای فاقد این API فقط وضعیت Unavailable نشان داده می‌شود.</span></label></div><div id="xiCompatNote" class="notice"></div><div class="toolbar"><button class="primary" onclick="submitXrayInbound()">Create, Validate & Restart</button><button class="ghost" onclick="closeModal()">Cancel</button></div></div></div>`;syncXrayForm()}
function syncXrayForm(){
  const protocolEl=formEl('xiProtocol'),transportEl=formEl('xiTransport'),securityEl=formEl('xiSecurity');
  const pathWrap=formEl('xiPathWrap'),sniWrap=formEl('xiSniWrap'),realityWrap=formEl('xiRealityWrap');
  const quotaEl=formEl('xiQuota'),resetEl=formEl('xiResetDays'),noteEl=formEl('xiCompatNote');
  const p=protocolEl.value;
  if(p==='hysteria2'){transportEl.value='tcp';securityEl.value='tls';transportEl.disabled=true;securityEl.disabled=true}
  else if(['http','socks'].includes(p)){transportEl.value='tcp';securityEl.value='none';transportEl.disabled=true;securityEl.disabled=true}
  else{transportEl.disabled=false;securityEl.disabled=false}
  const t=p==='hysteria2'?'hysteria':transportEl.value,s=p==='hysteria2'?'tls':securityEl.value;
  const pathNeeded=['ws','grpc','httpupgrade','xhttp'].includes(t)&&!['http','socks'].includes(p);
  pathWrap.style.display=pathNeeded?'block':'none';
  sniWrap.style.display=(s==='tls'||s==='reality')&&!['http','socks'].includes(p)?'block':'none';
  realityWrap.style.display=s==='reality'?'block':'none';
  const accountingLimited=['shadowsocks','http','socks'].includes(p);
  quotaEl.disabled=accountingLimited;
  resetEl.disabled=accountingLimited;
  if(accountingLimited){quotaEl.value=0;resetEl.value=0}
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
  noteEl.textContent=note;
}
async function submitXrayInbound(){const payload={protocol:formValue('xiProtocol','vless'),transport:formValue('xiTransport','tcp'),security:formValue('xiSecurity','none'),port:Number(formValue('xiPort','0')),name:formValue('xiName','').trim(),endpoint:formValue('xiEndpoint','').trim(),path_value:formValue('xiPath','/')||'/',server_name:formValue('xiSni','').trim(),reality_dest:formValue('xiRealityDest','').trim(),quota_gb:Number(formValue('xiQuota','0')||0),expire_days:Number(formValue('xiDays','0')||0),ip_limit:Number(formValue('xiIpLimit','1')||1),reset_days:Number(formValue('xiResetDays','0')||0)};if(!payload.name||!payload.endpoint||!payload.port){alert('فیلدهای اصلی را کامل کنید.');return}try{const r=await api('/api/protocols/xray/quick-inbound',{method:'POST',body:JSON.stringify(payload)});xrayCredentialModal(r)}catch(e){alert(e.message)}}
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
    window.__xrayBuilderUsedPorts=used;
    let port=Number(defaults.xray_port||2087);
    while(used.has(port)&&port<65535)port++;
    modalRoot.innerHTML=[
      '<div class="modal-backdrop"><div class="modal xray-builder-modal">',
        '<div class="wizard-head"><div><div class="eyebrow">XRAY INBOUND CENTER</div><h3>ساخت Inbound حرفه‌ای</h3><p>ساختار Inbound → Client → Transport → Security → Sniffing → Sockopt</p></div><button class="close-btn" data-action="modal-close">×</button></div>',
        '<div class="xray-builder-grid">',
          '<section class="xray-builder-section xray-preset-section"><div class="section-title"><b>Iran Network Presets</b><span>Recommended · Alternative · Compatibility · Experimental</span></div><div class="wizard-note"><b>Preset = شروع سریع، نه تضمین اتصال</b><span>شرایط فیلترینگ، ISP، دیتاسنتر و Client تغییر می‌کند. هر Preset فقط ترکیب معتبر Core را اعمال می‌کند و قبل از Commit با Xray validate می‌شود.</span></div><div id="xbPresetGrid" class="xray-preset-grid"></div></section>',
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
    renderXrayInboundPresets();
    p.addEventListener('change',syncXrayInboundBuilder);
    document.getElementById('xbTransport').addEventListener('change',syncXrayInboundBuilder);
    document.getElementById('xbSecurity').addEventListener('change',syncXrayInboundBuilder);
    syncXrayInboundBuilder();
  }catch(e){alert('Xray Inbound Center: '+e.message)}
}

function xbValue(id,fallback=''){const el=document.getElementById(id);return el?el.value:fallback}
function xbChecked(id){const el=document.getElementById(id);return !!(el&&el.checked)}
function xbSet(id,value){const el=document.getElementById(id);if(el&&value!==undefined&&value!==null)el.value=String(value)}
function xbPresetTierLabel(tier){
  return ({recommended:'Recommended',alternative:'Alternative',compatibility:'Compatibility',experimental:'Experimental'})[tier]||String(tier||'Preset');
}
function renderXrayInboundPresets(){
  const root=document.getElementById('xbPresetGrid');if(!root||!xrayBuilderCaps)return;
  const presets=xrayBuilderCaps.presets||[];
  root.innerHTML=presets.map(p=>{
    const req=[];
    if(p.requires_domain)req.push('TLS domain');
    if(p.requires_udp)req.push('UDP');
    const meta=[String(p.protocol||'').toUpperCase(),String(p.transport||'').toUpperCase(),String(p.security||'').toUpperCase()].filter(Boolean).join(' · ');
    const portInfo=p.suggested_port
      ? ('Port '+Number(p.suggested_port)+' ready')
      : ((p.port_state||[]).length?'Preset ports busy':'Port checked on create');
    return '<button type="button" class="xray-preset-card tier-'+htmlEsc(p.tier||'alternative')+'" data-action="xray-inbound-preset" data-preset="'+dataEnc(p.id)+'">'+
      '<span class="preset-tier">'+htmlEsc(xbPresetTierLabel(p.tier))+'</span>'+
      '<b>'+htmlEsc(p.label||p.id)+'</b><small>'+htmlEsc(meta)+'</small>'+
      '<p>'+htmlEsc(p.summary||'')+'</p>'+
      '<span class="preset-port">'+htmlEsc(portInfo)+'</span>'+
      (req.length?'<em>'+htmlEsc(req.join(' · '))+'</em>':'')+
      '</button>';
  }).join('');
}
function xrayPresetPort(preset){
  if(Number(preset?.suggested_port||0)>0)return Number(preset.suggested_port);
  const used=window.__xrayBuilderUsedPorts instanceof Set?window.__xrayBuilderUsedPorts:new Set();
  for(const raw of (preset.ports||[])){const port=Number(raw);if(port>0&&!used.has(port))return port}
  return Number(xbValue('xbPort','2087'));
}
function applyXrayInboundPreset(presetId){
  const preset=(xrayBuilderCaps?.presets||[]).find(x=>x.id===presetId);
  if(!preset){alert('Preset پیدا نشد.');return}
  const protocol=document.getElementById('xbProtocol');
  if(!protocol||!xrayBuilderCaps?.protocols?.[preset.protocol]){alert('این Preset با Core فعلی سازگار نیست.');return}
  protocol.value=preset.protocol;
  syncXrayInboundBuilder();
  const transport=document.getElementById('xbTransport'),security=document.getElementById('xbSecurity');
  if(transport&&(xrayBuilderCaps.protocols[preset.protocol].transports||[]).includes(preset.transport))transport.value=preset.transport;
  if(security&&(xrayBuilderCaps.protocols[preset.protocol].security||[]).includes(preset.security))security.value=preset.security;
  syncXrayInboundBuilder();

  const endpoint=xbValue('xbEndpoint','').trim();
  const endpointIsIp=/^\d{1,3}(?:\.\d{1,3}){3}$/.test(endpoint)||endpoint.includes(':');
  const sni=preset.sni==='$endpoint'?endpoint:preset.sni;
  xbSet('xbPort',xrayPresetPort(preset));
  xbSet('xbRemark','IR-'+String(preset.id||'preset').replace(/^ir-/,'').replace(/[^a-z0-9]+/gi,'-').slice(0,54)+'-'+xbValue('xbPort',''));
  xbSet('xbFlow',preset.flow||'');
  xbSet('xbPath',preset.path||'/');
  xbSet('xbServiceName',String(preset.path||'makia').replace(/^\//,''));
  xbSet('xbHost',endpointIsIp?'':endpoint);
  xbSet('xbSni',sni||'');
  xbSet('xbRealityDest',preset.reality_dest||'');
  xbSet('xbXhttpMode',preset.xhttp_mode||'auto');
  if(preset.protocol==='hysteria2')xbSet('xbHyIdle','60');

  const cards=document.querySelectorAll('.xray-preset-card');
  cards.forEach(el=>el.classList.toggle('selected',dataDec(el.dataset.preset||'')===preset.id));
  const note=document.getElementById('xbCompatNote');
  if(note){
    let warning=preset.note||'';
    if(preset.requires_domain&&endpointIsIp)warning='این Preset TLS domain می‌خواهد؛ Endpoint فعلی IP است. ابتدا دامنه و Certificate معتبر تنظیم کن. '+warning;
    note.innerHTML='<b>'+htmlEsc(xbPresetTierLabel(preset.tier))+' · '+htmlEsc(preset.label)+'</b><span>'+htmlEsc(warning)+'</span>';
  }
}

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

function protocolClientRow(c){const quota=Number(c.quota_bytes||0),used=Number(c.usage?.total||0),p=quota?Math.min(100,(used/quota)*100):0;const expiry=c.expire_at?new Date(c.expire_at*1000).toLocaleDateString():'∞';const state=!c.enabled?('Disabled'+(c.disabled_reason?' · '+c.disabled_reason:'')):(c.expired?'Expired':'Active');const sub=location.origin+'/sub/'+c.subscription_id;const ipCount=Number(c.online_ip_count||0),ipState=c.ip_violation?'bad':(ipCount?'ok':'');const accounting=c.accounting_supported!==false;return `<div class="protocol-client-row"><div><div class="client-main"><b>${c.name}</b><span class="protocol-pill">${c.protocol.toUpperCase()}</span><span class="status-chip ${c.enabled&&!c.expired?'ok':'bad'}">${state}</span>${c.ip_violation?'<span class="status-chip bad">IP LIMIT</span>':''}</div><div class="muted">${c.inbound_tag}</div></div><div>${accounting?`<b>${fmtBytes(used)} / ${quota?fmtBytes(quota):'Unlimited'}</b><div class="usage-track"><i style="width:${p}%"></i></div><div class="muted">↑ ${fmtBytes(c.usage?.uplink||0)} · ↓ ${fmtBytes(c.usage?.downlink||0)} · Reset ${c.reset_days?c.reset_days+'d':'manual'}</div>`:'<span class="status-chip warn">Accounting unavailable</span><div class="muted">این پروتکل در این نسخه counter مستقل per-client ندارد.</div>'}</div><div><b>${expiry}</b><div class="muted">${c.days_left===null?'No expiry':c.days_left+' days left'}</div><div class="chips"><button class="status-chip ${ipState}" onclick="showClientIPs(${c.id})">IPs ${ipCount}/${c.ip_limit}</button></div></div><div class="pro-row-actions"><button class="pro-more" data-action="access-detail" data-id="${dataEnc('xray:'+c.id)}" aria-label="جزئیات ${dataEnc(c.name)}">•••</button></div></div>`}

function showClientIPs(id){const c=(window.__protocolClients||[]).find(x=>x.id===id);if(!c)return;const rows=c.online?.ips||[];modalRoot.innerHTML=`<div class="modal-backdrop"><div class="modal"><div class="modal-head"><div><div class="eyebrow">XRAY ONLINE STATS</div><h3>Live IPs · ${c.name}</h3></div><button class="close-btn" onclick="closeModal()">×</button></div><div class="notice">${c.online?.available?'داده از Xray online-stats API خوانده شده است.':'این Xray Core یا Topology هنوز Online-IP API قابل استفاده ارائه نکرده است.'}</div><div class="ip-list">${rows.length?rows.map(x=>`<div><b>${x.ip}</b><span>${x.last_seen?new Date(x.last_seen*1000).toLocaleString():'-'}</span></div>`).join(''):'<div class="empty">IP آنلاین ثبت نشده است.</div>'}</div></div></div>`}

function editProtocolClient(id){
  const c=(window.__protocolClients||[]).find(x=>x.id===id);if(!c)return;
  const accounting=c.accounting_supported!==false;
  modalRoot.innerHTML=`<div class="modal-backdrop"><div class="modal"><div class="modal-head"><div><div class="eyebrow">CLIENT POLICY</div><h3>${c.name}</h3></div><button class="close-btn" onclick="closeModal()">×</button></div>
  <div class="policy-summary"><div><span>Protocol</span><b>${c.protocol.toUpperCase()}</b></div><div><span>Used</span><b>${fmtBytes(c.usage?.total||0)}</b></div><div><span>Online IPs</span><b>${c.online_ip_count||0} / ${c.ip_limit||1}</b></div><div><span>Reset</span><b>${c.reset_days?c.reset_days+'d':'Manual'}</b></div></div>
  <div class="form-grid">
    <label>Traffic quota (GB)<input id="pcQuota" type="number" min="0" step="1" value="${c.quota_bytes?(c.quota_bytes/1073741824).toFixed(2):0}" ${accounting?'':'disabled'}><div class="password-tools quota-tools"><button class="soft" onclick="setFieldValue('pcQuota',0)" ${accounting?'':'disabled'}>∞</button><button class="soft" onclick="setFieldValue('pcQuota',10)" ${accounting?'':'disabled'}>10</button><button class="soft" onclick="setFieldValue('pcQuota',20)" ${accounting?'':'disabled'}>20</button><button class="soft recommended" onclick="setFieldValue('pcQuota',50)" ${accounting?'':'disabled'}>50</button><button class="soft" onclick="setFieldValue('pcQuota',100)" ${accounting?'':'disabled'}>100</button><button class="soft" onclick="setFieldValue('pcQuota',200)" ${accounting?'':'disabled'}>200</button></div><span class="muted">${accounting?'0 = Unlimited':'Accounting برای این protocol در دسترس نیست.'}</span></label>
    <label>Expiry from today (days)<input id="pcDays" type="number" min="0" max="3650" value="${c.days_left??0}"><div class="password-tools duration-tools"><button class="soft" onclick="setFieldValue('pcDays',1)">1</button><button class="soft" onclick="setFieldValue('pcDays',3)">3</button><button class="soft" onclick="setFieldValue('pcDays',7)">7</button><button class="soft" onclick="setFieldValue('pcDays',15)">15</button><button class="soft recommended" onclick="setFieldValue('pcDays',30)">30</button><button class="soft" onclick="setFieldValue('pcDays',60)">60</button><button class="soft" onclick="setFieldValue('pcDays',90)">90</button><button class="soft" onclick="setFieldValue('pcDays',0)">∞</button></div></label>
    <label>Device / IP limit<input id="pcIp" type="number" min="1" max="50" value="${c.ip_limit||1}"><div class="password-tools"><button class="soft recommended" onclick="setFieldValue('pcIp',1)">1</button><button class="soft" onclick="setFieldValue('pcIp',2)">2</button><button class="soft" onclick="setFieldValue('pcIp',3)">3</button><button class="soft" onclick="setFieldValue('pcIp',5)">5</button><button class="soft" onclick="setFieldValue('pcIp',10)">10</button></div></label>
    <label>Traffic reset cycle<input id="pcReset" type="number" min="0" max="3650" value="${c.reset_days||0}" ${accounting?'':'disabled'}><div class="password-tools"><button class="soft" onclick="setFieldValue('pcReset',0)" ${accounting?'':'disabled'}>Never</button><button class="soft" onclick="setFieldValue('pcReset',7)" ${accounting?'':'disabled'}>7</button><button class="soft recommended" onclick="setFieldValue('pcReset',30)" ${accounting?'':'disabled'}>30</button><button class="soft" onclick="setFieldValue('pcReset',60)" ${accounting?'':'disabled'}>60</button><button class="soft" onclick="setFieldValue('pcReset',90)" ${accounting?'':'disabled'}>90</button></div></label>
    <label>Status<select id="pcEnabled"><option value="1" ${c.enabled?'selected':''}>Active</option><option value="0" ${!c.enabled?'selected':''}>Disabled</option></select><span class="muted">${c.disabled_reason?'Reason: '+c.disabled_reason:'Enable/disable updates the live engine when supported.'}</span></label>
  </div>
  <div class="toolbar" style="margin-top:16px"><button class="primary" onclick="saveProtocolClient(${c.id})">Save policy</button>${accounting?'<button class="ghost" onclick="resetProtocolTraffic('+c.id+')">Reset traffic</button>':''}<button class="ghost" onclick="closeModal()">Cancel</button></div></div></div>`;
}
async function saveProtocolClient(id){try{await api('/api/protocol-clients/'+id,{method:'PUT',body:JSON.stringify({quota_gb:Number(formValue('pcQuota','0')||0),expire_days:Number(formValue('pcDays','0')||0),ip_limit:Number(formValue('pcIp','1')||1),reset_days:Number(formValue('pcReset','0')||0),enabled:formValue('pcEnabled','1')==='1'})});closeModal();toast('Policy updated');await currentView()}catch(e){alert(e.message)}}
async function resetProtocolTraffic(id){if(!confirm('Traffic counter این Client صفر شود؟'))return;try{await api('/api/protocol-clients/'+id+'/reset-traffic',{method:'POST'});toast('Traffic reset');await currentView()}catch(e){alert(e.message)}}
async function openXrayAdvanced(){try{const r=await api('/api/protocols/xray/config');modalRoot.innerHTML=`<div class="modal-backdrop"><div class="modal config-modal"><div class="modal-head"><div><div class="eyebrow">ADVANCED XRAY</div><h3>Validated JSON Configuration</h3><div class="muted">${r.path}</div></div><button class="close-btn" onclick="closeModal()">×</button></div><textarea id="xrayAdvancedText" class="config-output" spellcheck="false"></textarea><div class="notice">برای Routing، Outbounds، Fallbacks، TUN، HTTP/SOCKS و تنظیمات پیشرفته. قبل از Apply با خود Xray تست می‌شود، Backup گرفته می‌شود و در Failure رول‌بک انجام می‌شود.</div><div class="toolbar"><button class="ghost" onclick="validateXrayAdvanced()">Validate</button><button class="primary" onclick="applyXrayAdvanced()">Validate & Apply</button><button class="ghost" onclick="downloadText('xray-config.json',formValue('xrayAdvancedText',''))">Export JSON</button></div></div></div>`;setFieldValue('xrayAdvancedText',JSON.stringify(r.config,null,2))}catch(e){alert(e.message)}}
function parseAdvancedXray(){try{return JSON.parse(formValue('xrayAdvancedText',''))}catch(e){throw new Error('JSON نامعتبر: '+e.message)}}
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
async function createWireGuardPeer(){const d=window.__operatorSettings?.defaults||{};const defs=await api('/api/accounts/new-defaults').catch(()=>({username:'user001'}));const name=prompt('Peer name',defs.username||'user001');if(!name)return;const endpoint=prompt('Public domain or server IP',window.PANEL_DOMAIN||location.hostname);if(!endpoint)return;const dns=prompt('Client DNS',d.wireguard_dns||'1.1.1.1')||'1.1.1.1';try{const r=await api('/api/protocols/wireguard/peers',{method:'POST',body:JSON.stringify({name,endpoint,dns,mtu:Number(d.wireguard_mtu||1280),keepalive:Number(d.wireguard_keepalive??15),allowed_ips:d.wireguard_allowed_ips||'0.0.0.0/0'})});configModal('WireGuard · '+name,r.config,name+'.conf','wireguard',name);if(r.diagnostics&&!r.diagnostics.ok)toast('Config ساخته شد؛ WireGuard Diagnostics نیاز به بررسی دارد')}catch(e){alert(e.message)}}
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
async function createOpenVPNClient(){const defs=await api('/api/accounts/new-defaults').catch(()=>({username:'user001'}));const name=prompt('Client name',defs.username||'user001');if(!name)return;const endpoint=prompt('Public domain or server IP',window.PANEL_DOMAIN||location.hostname);if(!endpoint)return;const port=Number(prompt('OpenVPN port',String(window.__operatorSettings?.defaults?.openvpn_port||1194)))||1194;const proto=(prompt('Protocol: udp or tcp',window.__operatorSettings?.defaults?.openvpn_proto||'udp')||'udp').toLowerCase();try{const r=await api('/api/protocols/openvpn/clients',{method:'POST',body:JSON.stringify({name,endpoint,port,proto})});configModal('OpenVPN · '+name,r.config,name+'.ovpn','openvpn',name);if(r.diagnostics?.warnings?.length)toast('OpenVPN ساخته شد؛ Domain Diagnostics هشدار دارد')}catch(e){alert(e.message)}}
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

async function saveGeneral(){try{const r=await api('/api/settings/general',{method:'PUT',body:JSON.stringify({language:formValue('generalLang','fa'),panel_domain:formValue('generalDomain','').trim(),theme:formValue('generalTheme','dark'),density:formValue('generalDensity','comfortable')})});window.PANEL_DOMAIN=r.panel_domain||'';toast('Settings saved');if(r.language!==window.MAKIA_LANG||r.theme!==window.MAKIA_THEME||r.density!==window.MAKIA_DENSITY){setTimeout(()=>location.reload(),450);return}await settings()}catch(e){alert(e.message)}}
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
async function applyDomain(){const domain=formValue('generalDomain','').trim();if(!domain){alert('دامنه را وارد کنید.');return}if(!confirm('Nginx server_name روی '+domain+' تنظیم شود؟'))return;try{await api('/api/settings/domain/apply',{method:'POST',body:JSON.stringify({domain})});window.PANEL_DOMAIN=domain;toast('Domain applied to Nginx');await settings()}catch(e){alert(e.message)}}
async function issueCertificate(){const domain=formValue('generalDomain','').trim(),email=formValue('tlsEmail','').trim();if(!domain||!email){alert('دامنه و ایمیل لازم است.');return}if(!confirm('برای '+domain+' گواهی Let\'s Encrypt صادر شود؟'))return;try{const r=await api('/api/settings/domain/certificate',{method:'POST',body:JSON.stringify({domain,email})});toast(r.certificate?'HTTPS enabled':'Certificate command completed');setTimeout(()=>location.href='https://'+domain,1000)}catch(e){alert(e.message)}}
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
async function enable2FA(){try{await api('/api/admin/2fa/enable',{method:'POST',body:JSON.stringify({code:formValue('twoCode','')})});closeModal();alert('2FA فعال شد.');await settings()}catch(e){alert(e.message)}}
async function disable2FA(){const password=prompt('رمز فعلی مدیر:');if(password===null)return;const code=prompt('کد ۶ رقمی Authenticator:');if(code===null)return;try{await api('/api/admin/2fa/disable',{method:'POST',body:JSON.stringify({password,code})});alert('2FA غیرفعال شد.');await settings()}catch(e){alert(e.message)}}
async function changePass(){try{await api('/api/admin/password',{method:'POST',body:JSON.stringify({current_password:formValue('oldP',''),new_password:formValue('newP','')})});alert('رمز مدیر تغییر کرد.')}catch(e){alert(e.message)}}
function toast(msg){let t=document.getElementById('makiaToast');if(!t){t=document.createElement('div');t.id='makiaToast';t.className='toast';document.body.appendChild(t)}t.textContent=msg;t.classList.add('show');clearTimeout(window.__toastTimer);window.__toastTimer=setTimeout(()=>t.classList.remove('show'),2200)}
const commandItems=[['Dashboard','dashboard'],['Clients','access'],['Plans','plans'],['Expiry Center','expiry'],['Inbounds','inbounds'],['SSH / NPV','ssh'],['Xray / V2Ray','xray'],['Outline','outline'],['WireGuard','wireguard'],['OpenVPN','openvpn'],['Connectivity Lab','connectivity'],['Telegram Proxy','telegramproxy'],['DNS Center','dnscenter'],['Diagnostics Center','diagnostics'],['Operations / DR','operations'],['Network / Ports','protocols'],['Live Sessions','sessions'],['Nodes','nodes'],['Services','services'],['Backups','backups'],['Logs','audit'],['Update','updates'],['Settings','settings'],['Client Guides','guides'],['Security','security'],['Support','support']];

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
  if(kind==='outline'){
    closeModal();
    if(!wizardProtocolReady('outline')){await switchView('outline');setTimeout(setupOutline,50);return}
    await switchView('outline');setTimeout(openOutlineKeyCreate,50);return;
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
  if(action==='mtproxy-configure'){await configureTelegramProxy(false);return}
  if(action==='mtproxy-rotate'){await configureTelegramProxy(true);return}
  if(action==='dns-configure'){await configureDnsCenter();return}
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
  if(action==='xray-inbound-preset'){applyXrayInboundPreset(dataDec(btn.dataset.preset));return}
  if(action==='outline-quota'){await setOutlineQuota(dataDec(btn.dataset.key),dataDec(btn.dataset.name),Number(btn.dataset.quota||0));return}
  if(action==='outline-renew'){await bulkManaged([{kind:'outline',key:dataDec(btn.dataset.key)}],'renew',30,0);return}
  if(action==='outline-reissue'){await reissueOutlineClient(dataDec(btn.dataset.key),dataDec(btn.dataset.name));return}
  if(action==='outline-delete-key'){await deleteOutlineKey(dataDec(btn.dataset.key));return}
  if(action==='access-diagnostics'){await openAccessDiagnostics(btn.dataset.kind,dataDec(btn.dataset.key),dataDec(btn.dataset.name));return}
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
  if(action==='openvpn-wstunnel-setup'){await setupOpenVPNWStunnel();return}
  if(action==='openvpn-wstunnel-client'){await createOpenVPNWStunnelProfile(btn.dataset.name||'');return}
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
  if(action==='client-open-portal'){window.open(location.origin+'/client/','_blank','noopener');return}
  if(action==='client-copy-portal'){copyText(location.origin+'/client/');toast(tr('لینک Client Portal کپی شد','Client Portal link copied'));return}
  if(action==='client-copy-link'){copyText(clientPortalUrl(dataDec(btn.dataset.user)));toast(tr('لینک ورود کاربر کپی شد','Client login link copied'));return}
  if(action==='client-openvpn-policy-enable'){
    if(!confirm(tr('فعال‌سازی کنترل Client برای OpenVPN یک Restart کنترل‌شده OpenVPN انجام می‌دهد و ممکن است اتصال‌های OpenVPN فعلی برای چند ثانیه قطع و دوباره برقرار شوند. ادامه می‌دهی؟','Enabling OpenVPN Client policy performs a controlled OpenVPN restart and may briefly interrupt current OpenVPN sessions. Continue?')))return;
    btn.disabled=true;
    try{
      const r=await api('/api/client-platform/openvpn-policy/enable',{method:'POST'});
      toast(r.ready?tr('کنترل OpenVPN آماده شد','OpenVPN Client policy is ready'):tr('تنظیم انجام شد؛ وضعیت را دوباره بررسی کن','Configured; recheck status'));
      await clientPlatformCenter();
    }finally{btn.disabled=false}
    return;
  }
  if(action==='client-platform-toggle'){
    const next=btn.dataset.enabled==='1';
    if(!confirm(next?tr('Client Portal برای کاربران فعال شود؟','Enable Client Portal for users?'):tr('Client Portal غیرفعال شود؟ اتصال‌های VPN فعلی قطع نمی‌شوند.','Disable Client Portal? Existing VPN connections will not be disconnected.')))return;
    await api('/api/client-platform/settings',{method:'POST',body:JSON.stringify({enabled:next})});
    toast(next?tr('Client Portal فعال شد','Client Portal enabled'):tr('Client Portal غیرفعال شد','Client Portal disabled'));
    await clientPlatformCenter();return;
  }
  if(action==='client-account-new'){openClientAccountCreate();return}
  if(action==='client-account-create'){await createClientAccount();return}
  if(action==='client-account-open'){await openClientAccountManage(Number(btn.dataset.id));return}
  if(action==='client-account-save'){await saveClientAccount(Number(btn.dataset.id));return}
  if(action==='client-password-generate'){
    const r=await api('/api/accounts/generate-secret?mode=strong');
    const el=document.getElementById(btn.dataset.target);if(el){el.value=r.secret||'';el.type='text';el.focus()}return;
  }
  if(action==='client-password-rotate'){await rotateClientPassword(Number(btn.dataset.id),dataDec(btn.dataset.user));return}
  if(action==='client-binding-add'){await bindClientAccess(Number(btn.dataset.account));return}
  if(action==='client-binding-remove'){await removeClientBinding(Number(btn.dataset.account),btn.dataset.type,Number(btn.dataset.id));return}
  if(action==='client-device-revoke-admin'){
    if(!confirm(tr('این دستگاه لغو شود؟ Sessionهای همان دستگاه هم باطل می‌شوند.','Revoke this device and its sessions?')))return;
    await api('/api/client-platform/accounts/'+Number(btn.dataset.account)+'/devices/'+Number(btn.dataset.device)+'/revoke',{method:'POST'});
    toast(tr('دستگاه لغو شد','Device revoked'));await openClientAccountManage(Number(btn.dataset.account));return;
  }
  if(action==='client-devices-revoke-all'){
    if(!confirm(tr('همه دستگاه‌های این حساب لغو شوند؟ کاربر باید دوباره دستگاه ثبت کند.','Revoke all devices for this account? The user must register a device again.')))return;
    await api('/api/client-platform/accounts/'+Number(btn.dataset.account)+'/devices/revoke-all',{method:'POST'});
    toast(tr('همه دستگاه‌ها لغو شدند','All devices revoked'));await openClientAccountManage(Number(btn.dataset.account));return;
  }
  if(action==='client-sessions-revoke-all'){
    if(!confirm(tr('همه Sessionهای فعال این حساب خارج شوند؟','Revoke all active sessions for this account?')))return;
    await api('/api/client-platform/accounts/'+Number(btn.dataset.account)+'/sessions/revoke-all',{method:'POST'});
    toast(tr('همه Sessionها باطل شدند','All sessions revoked'));return;
  }
  if(action==='client-account-delete'){
    const user=dataDec(btn.dataset.user);
    if(!confirm(tr('حساب Client '+user+' حذف شود؟ پروتکل‌ها و Credentialهای اصلی حذف نمی‌شوند.','Delete client account '+user+'? Original protocol credentials will remain untouched.')))return;
    await api('/api/client-platform/accounts/'+Number(btn.dataset.id),{method:'DELETE'});
    closeModal();toast(tr('حساب Client حذف شد؛ Runtime دست‌نخورده ماند','Client account deleted; runtime remained untouched'));await clientPlatformCenter();return;
  }
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


function networkState(ok,labelOk,labelBad){
  return '<span class="status-chip '+(ok?'ok':'bad')+'">'+htmlEsc(ok?labelOk:labelBad)+'</span>';
}

async function telegramProxyCenter(renderToken=window.__viewRenderToken){
  title.textContent=tr('پروکسی تلگرام','Telegram Proxy');setPageContext('TELEGRAM MTPROXY');
  content.innerHTML='<div class="loading-state"><span class="spinner"></span><b>'+htmlEsc(tr('در حال بررسی MTProxy…','Checking MTProxy…'))+'</b></div>';
  const r=await api('/api/network/mtproxy');
  if(renderToken!==window.__viewRenderToken||activeView!=='telegramproxy')return;
  const health=Boolean(r.installed&&r.configured&&r.service_active&&r.listener&&(!r.firewall_active||r.firewall_allowed));
  const install=r.installed?'':[
    '<section class="network-tool-card install-card">',
      '<div><span class="pro-kicker">ROOT INSTALL REQUIRED</span><h3>'+htmlEsc(tr('نصب MTProxy مدرن (mtg)','Install maintained Telegram MTProxy (mtg)'))+'</h3>',
      '<p>'+htmlEsc(tr('نصب از داخل Web Service انجام نمی‌شود. دستور زیر Installer پین‌شده Makia را اجرا می‌کند.','Host installation is intentionally outside the web service. Run the pinned Makia installer below.'))+'</p></div>',
      '<textarea id="mtInstallCommand" readonly>'+htmlEsc(r.install_command||'sudo makia-install-mtproxy')+'</textarea>',
      '<button class="primary" data-action="copy-target" data-target="mtInstallCommand">'+htmlEsc(tr('کپی دستور نصب','Copy install command'))+'</button>',
    '</section>'
  ].join('');
  const delivery=(r.configured?[
    '<section class="network-tool-card delivery-card">',
      '<div class="tool-card-head"><div><span class="pro-kicker">USER DELIVERY</span><h3>'+htmlEsc(tr('لینک آماده Telegram','Telegram connection link'))+'</h3></div>'+networkState(health,tr('آماده','READY'),tr('نیازمند بررسی','CHECK'))+'</div>',
      '<div class="network-delivery-grid">',
        (r.qr?'<div class="network-qr"><img src="'+htmlEsc(r.qr)+'" alt="Telegram Proxy QR"></div>':''),
        '<div class="network-link-stack">',
          '<label>t.me link<textarea id="mtHttpsLink" readonly>'+htmlEsc(r.https_link||'')+'</textarea></label>',
          '<label>tg:// link<textarea id="mtTgLink" readonly>'+htmlEsc(r.tg_link||'')+'</textarea></label>',
          '<div class="toolbar"><button class="primary" data-action="copy-target" data-target="mtHttpsLink">'+htmlEsc(tr('کپی لینک برای کاربر','Copy user link'))+'</button><button class="ghost" data-action="copy-target" data-target="mtTgLink">tg://</button>'+(r.https_link?'<a class="ghost link-btn" href="'+htmlEsc(r.https_link)+'" target="_blank" rel="noopener noreferrer">'+htmlEsc(tr('باز کردن در Telegram','Open in Telegram'))+'</a>':'')+'</div>',
        '</div>',
      '</div>',
      '<div class="notice">'+htmlEsc(tr('Secret تحویلی با FakeTLS secret نسخه mtg ساخته می‌شود. اپراتور Proxy به محتوای چت‌های Telegram دسترسی ندارد.','The delivered secret uses mtg FakeTLS format. A proxy operator cannot read Telegram chat contents.'))+'</div>',
    '</section>'
  ].join(''):'');
  content.innerHTML=[
    '<div class="pro-page network-tools-page">',
      '<section class="pro-page-head"><div><span class="pro-kicker">TELEGRAM MTPROXY</span><h1>'+htmlEsc(tr('پروکسی اختصاصی Telegram','Private Telegram Proxy'))+'</h1><p>'+htmlEsc(tr('MTProto Proxy واقعی با Secret، لینک مستقیم، QR و Port collision detection.','Real MTProto proxy with secret, direct links, QR and port collision detection.'))+'</p></div><div class="pro-head-actions"><button class="ghost" data-action="refresh">'+htmlEsc(tr('بروزرسانی','Refresh'))+'</button></div></section>',
      '<section class="network-health-grid">',
        '<div><span>Installed</span><b>'+networkState(Boolean(r.installed),'YES','NO')+'</b></div>',
        '<div><span>Configured</span><b>'+networkState(Boolean(r.configured),'YES','NO')+'</b></div>',
        '<div><span>Service</span><b>'+networkState(Boolean(r.service_active),'ACTIVE','DOWN')+'</b></div>',
        '<div><span>Listener</span><b>'+networkState(Boolean(r.listener),'TCP/'+htmlEsc(String(r.port||'')),'OFFLINE')+'</b></div>',
      '</section>',
      (r.configured&&r.firewall_active&&!r.firewall_allowed?'<div class="notice">'+htmlEsc(tr('Proxy ذخیره و فعال است، اما UFW اجازه Port فعلی را نشان نمی‌دهد. تنظیم Proxy حذف نشده؛ Firewall را بررسی کن.','Proxy configuration is preserved and the service is active, but UFW does not show an allow rule for the current port. The proxy was not deleted; check the firewall rule.'))+'</div>':''),
      install,
      (r.installed?[
        '<section class="network-tool-card">',
          '<div class="tool-card-head"><div><span class="pro-kicker">CONFIGURATION</span><h3>'+htmlEsc(tr('تنظیم Proxy','Proxy configuration'))+'</h3></div><small>'+htmlEsc(tr('Port از ابتدا خودکار انتخاب می‌شود و در Retry فقط وقتی لازم باشد تغییر می‌کند.','The port is automatic from the start and changes on retry only when required.'))+'</small></div>',
          '<div class="wizard-form two">',
            '<label>'+htmlEsc(tr('دامنه FakeTLS پروکسی','Proxy FakeTLS hostname'))+'<input id="mtHost" dir="ltr" value="'+htmlEsc(r.configured?r.host:'')+'" placeholder="proxy.example.com"></label>',
            '<label>'+htmlEsc(tr('Port پروکسی','Proxy port'))+'<input id="mtPortDisplay" type="text" dir="ltr" readonly value="'+htmlEsc(r.port?String(r.port):'AUTO')+'"><span class="muted">'+htmlEsc(tr('انتخاب Port کاملاً خودکار است؛ Makia از Portهای آزاد High-TCP استفاده می‌کند و 443 را پیش‌فرض نمی‌گیرد.','Port selection is fully automatic. Makia uses a free high TCP port and does not prefer 443.'))+'</span></label>',
          '</div>',
          '<div class="toolbar"><button class="primary" data-action="mtproxy-configure">'+htmlEsc(tr('ذخیره و راه‌اندازی','Save & start'))+'</button><button class="danger" data-action="mtproxy-rotate">'+htmlEsc(tr('تعویض Secret','Rotate secret'))+'</button></div>',
          '<div class="notice">'+htmlEsc(tr('تعویض Secret لینک قبلی کاربران را باطل می‌کند.','Rotating the secret invalidates previously issued proxy links.'))+'</div>',
        '</section>'
      ].join(''):''),
      delivery,
    '</div>'
  ].join('');
}

async function configureTelegramProxy(rotate=false){
  const host=(document.getElementById('mtHost')?.value||'').trim();
  const port=0;
  if(!host){alert(tr('دامنه DNS پروکسی را وارد کن.','Enter the proxy DNS hostname.'));return}
  if(/^\[?[0-9a-f:.]+\]?$/i.test(host)){alert(tr('برای FakeTLS باید دامنه DNS وارد شود؛ IP خام قابل قبول نیست.','FakeTLS requires a DNS hostname; a raw IP is not accepted.'));return}
  if(rotate&&!confirm(tr('Secret قبلی باطل شود؟','Invalidate the previous secret?')))return;
  try{
    const r=await api('/api/network/mtproxy/configure',{method:'POST',body:JSON.stringify({host,port,rotate_secret:Boolean(rotate)})});
    if(r.firewall_warning){
      alert(tr('Proxy ذخیره و سرویس فعال شد، اما Rule فایروال اعمال نشد:\n','Proxy was saved and the service is active, but the firewall rule could not be applied:\n')+r.firewall_warning);
    }else{
      toast(r.port_adjusted?tr('Proxy ساخته شد؛ Port آزاد جایگزین شد.','Proxy saved; a free port was selected.'):tr('Proxy آماده است.','Proxy is ready.'));
    }
    await telegramProxyCenter();
  }catch(e){alert('MTProxy: '+e.message)}
}

async function dnsCenter(renderToken=window.__viewRenderToken){
  title.textContent=tr('مرکز DNS','DNS Center');setPageContext('PRIVATE DNS');
  content.innerHTML='<div class="loading-state"><span class="spinner"></span><b>'+htmlEsc(tr('در حال بررسی Resolver…','Checking resolver…'))+'</b></div>';
  const r=await api('/api/network/dns');
  if(renderToken!==window.__viewRenderToken||activeView!=='dnscenter')return;
  const install=r.installed?'':[
    '<section class="network-tool-card install-card">',
      '<div><span class="pro-kicker">ROOT INSTALL REQUIRED</span><h3>'+htmlEsc(tr('نصب Unbound Resolver','Install Unbound resolver'))+'</h3>',
      '<p>'+htmlEsc(tr('نصب اولیه Local-only است و Open Resolver ساخته نمی‌شود.','The initial install is local-only and never creates an open resolver.'))+'</p></div>',
      '<textarea id="dnsInstallCommand" readonly>'+htmlEsc(r.install_command||'sudo makia-install-dns')+'</textarea>',
      '<button class="primary" data-action="copy-target" data-target="dnsInstallCommand">'+htmlEsc(tr('کپی دستور نصب','Copy install command'))+'</button>',
    '</section>'
  ].join('');
  const remoteAddresses=[...new Set([r.wireguard_address,r.public_address].filter(Boolean))];
  const addresses=remoteAddresses.map((x,i)=>'<div class="network-copy-row"><span class="dns-address" id="dnsAddress'+i+'">'+htmlEsc(x)+'</span><button class="ghost" data-action="copy-target" data-target="dnsAddress'+i+'">'+htmlEsc(tr('کپی','Copy'))+'</button></div>').join('');
  const dnsDeliveryLines=[];
  if(r.wireguard_address)dnsDeliveryLines.push('WireGuard DNS: '+r.wireguard_address);
  if(r.public_address)dnsDeliveryLines.push('Public DNS: '+r.public_address);
  if(r.mode==='public'&&(r.allowed_cidrs||[]).length)dnsDeliveryLines.push('Allowed source: '+(r.allowed_cidrs||[]).join(', '));
  dnsDeliveryLines.push('Upstream: '+String(r.upstream_label||r.upstream||''));
  const dnsDeliveryText=dnsDeliveryLines.join('\n');
  const upstreamOptions=(r.upstreams||[]).map(x=>'<option value="'+htmlEsc(x.id)+'" '+(x.id===r.upstream?'selected':'')+'>'+htmlEsc(x.label)+'</option>').join('');
  content.innerHTML=[
    '<div class="pro-page network-tools-page">',
      '<section class="pro-page-head"><div><span class="pro-kicker">SECURE RESOLVER</span><h1>'+htmlEsc(tr('DNS خصوصی / کم‌تاخیر','Private / low-latency DNS'))+'</h1><p>'+htmlEsc(tr('Unbound cache + DNS-over-TLS upstream، بدون ساخت Open Resolver عمومی.','Unbound cache with DNS-over-TLS upstreams, without exposing an open resolver.'))+'</p></div><div class="pro-head-actions"><button class="ghost" data-action="refresh">'+htmlEsc(tr('بروزرسانی','Refresh'))+'</button></div></section>',
      '<div class="iran-boundary"><b>'+htmlEsc(tr('واقعیت فنی:','Technical note:'))+'</b><span>'+htmlEsc(r.warning||'DNS does not equal game ping.')+'</span></div>',
      '<section class="network-health-grid">',
        '<div><span>Installed</span><b>'+networkState(Boolean(r.installed),'YES','NO')+'</b></div>',
        '<div><span>Service</span><b>'+networkState(Boolean(r.service_active),'ACTIVE','DOWN')+'</b></div>',
        '<div><span>Mode</span><strong>'+htmlEsc(String(r.mode||'private').toUpperCase())+'</strong></div>',
        '<div><span>Resolver query</span><strong>'+(r.query_ok===false?'<span class="state-bad">FAILED</span>':((r.query_ms===null||r.query_ms===undefined)?'—':Number(r.query_ms)+' ms'))+'</strong></div>',
      '</section>',
      (r.service_active&&r.query_ok===false?'<div class="notice">'+htmlEsc(tr('Unbound فعال است اما Query محلی جواب نمی‌دهد. Makia در Repair بعدی تنظیم DoT و CA bundle را بازسازی می‌کند.','Unbound is active but the localhost query is failing. Makia repair will rebuild the DoT/CA-bundle configuration.'))+(r.runtime_error?'<div class="network-delivery-note" dir="ltr">'+htmlEsc(r.runtime_error)+'</div>':'')+'</div>':''),
      install,
      (r.installed?[
        '<section class="network-tool-card">',
          '<div class="tool-card-head"><div><span class="pro-kicker">RESOLVER POLICY</span><h3>'+htmlEsc(tr('تنظیم DNS','DNS configuration'))+'</h3></div></div>',
          '<div class="wizard-form two">',
            '<label>'+htmlEsc(tr('حالت دسترسی','Access mode'))+'<select id="dnsMode"><option value="private" '+(r.mode!=='public'?'selected':'')+'>'+htmlEsc(tr('Private / VPN only','Private / VPN only'))+'</option><option value="public" '+(r.mode==='public'?'selected':'')+'>'+htmlEsc(tr('Public + IP allowlist','Public + IP allowlist'))+'</option></select></label>',
            '<label>Upstream<select id="dnsUpstream">'+upstreamOptions+'</select></label>',
            '<label>'+htmlEsc(tr('Public IPv4 همین VPS','This VPS public IPv4'))+'<input id="dnsPublic" dir="ltr" value="'+htmlEsc(r.public_address||'')+'" placeholder="203.0.113.10"></label>',
            '<label>'+htmlEsc(tr('IP/CIDR مجاز کاربران','Allowed client IP/CIDR'))+'<textarea id="dnsAllowed" dir="ltr" placeholder="198.51.100.25/32">'+htmlEsc((r.allowed_cidrs||[]).join('\n'))+'</textarea></label>',
          '</div>',
          '<div class="notice">'+htmlEsc(tr('حالت Public بدون Allowlist عمداً Block می‌شود تا سرور شما Open Resolver و ابزار DDoS نشود.','Public mode is blocked without an allowlist so the VPS cannot become an open DNS resolver or amplification source.'))+'</div>',
          '<div class="toolbar"><button class="primary" data-action="dns-configure">'+htmlEsc(tr('Validate & Apply','Validate & Apply'))+'</button></div>',
        '</section>',
        '<section class="network-tool-card">',
          '<div class="tool-card-head"><div><span class="pro-kicker">CLIENT DELIVERY</span><h3>'+htmlEsc(tr('آدرس‌های قابل استفاده','Usable resolver addresses'))+'</h3></div></div>',
          '<div class="dns-address-list">'+(addresses||'<div class="network-delivery-note">'+htmlEsc(tr('فعلاً فقط Localhost فعال است و چیزی برای تحویل مستقیم به کاربر راه‌دور وجود ندارد. برای کاربران WireGuard از DNS داخلی WireGuard استفاده کن؛ برای Public DNS باید IP/CIDR همان کاربر را Allowlist کنی.','Only localhost is active, so there is no remote client address to deliver yet. WireGuard users can use the WireGuard resolver; public DNS requires the client IP/CIDR to be allowlisted first.'))+'</div>')+'</div>',
          (dnsDeliveryText?'<label>'+htmlEsc(tr('متن آماده تحویل به کاربر','Ready-to-send client DNS'))+'<textarea id="dnsUserDelivery" class="network-user-text" readonly>'+htmlEsc(dnsDeliveryText)+'</textarea></label><div class="toolbar"><button class="primary" data-action="copy-target" data-target="dnsUserDelivery">'+htmlEsc(tr('کپی اطلاعات DNS کاربر','Copy client DNS details'))+'</button></div>':''),
          (r.mode==='public'?'<div class="network-delivery-note">'+htmlEsc(tr('قبل از ارسال Public DNS، IP یا CIDR اینترنت کاربر باید در Allowlist بالا ثبت شده باشد.','Before sharing public DNS, the client Internet IP/CIDR must be present in the allowlist above.'))+'</div>':''),
          '<p class="muted">'+htmlEsc(tr('این Resolver می‌تواند زمان Lookup و Cache را بهتر کند؛ Ping سرور بازی یا رفع محدودیت جغرافیایی را تضمین نمی‌کند. برای Smart-DNS واقعی باید Upstream مخصوص آن سرویس جداگانه داشته باشی.','This resolver can improve lookup/cache behavior; it does not guarantee lower game-server RTT or geo-unblocking. True Smart DNS requires a specialized upstream service.'))+'</p>',
        '</section>'
      ].join(''):''),
    '</div>'
  ].join('');
}

async function configureDnsCenter(){
  const mode=document.getElementById('dnsMode')?.value||'private';
  const upstream=document.getElementById('dnsUpstream')?.value||'cloudflare';
  const public_address=(document.getElementById('dnsPublic')?.value||'').trim();
  const allowed_cidrs=(document.getElementById('dnsAllowed')?.value||'').split(/[\n,]+/).map(x=>x.trim()).filter(Boolean);
  try{
    await api('/api/network/dns/configure',{method:'POST',body:JSON.stringify({mode,upstream,public_address,allowed_cidrs})});
    toast(tr('DNS اعمال شد.','DNS applied.'));
    await dnsCenter();
  }catch(e){alert('DNS: '+e.message)}
}

function applyLanguageShell(){
  const fa={dashboard:'داشبورد',inbounds:'Inboundها',access:'کاربران',plans:'پلن‌ها',expiry:'مرکز تمدید',ssh:'SSH / NPV',xray:'Xray / V2Ray',outline:'Outline',wireguard:'WireGuard',openvpn:'OpenVPN',sessions:'اتصال‌های زنده',services:'سرویس‌ها',protocols:'شبکه و پورت‌ها',nodes:'نودها',connectivity:'Connectivity Lab',telegramproxy:'پروکسی تلگرام',dnscenter:'DNS برای کاربران',diagnostics:'مرکز عیب‌یابی',operations:'عملیات و انتقال',backups:'بکاپ',audit:'لاگ‌ها',updates:'بروزرسانی',settings:'تنظیمات',support:'پشتیبانی'};
  const en={dashboard:'Dashboard',inbounds:'Inbounds',access:'Clients',plans:'Plans',expiry:'Expiry Center',ssh:'SSH / NPV',xray:'Xray / V2Ray',outline:'Outline',wireguard:'WireGuard',openvpn:'OpenVPN',sessions:'Live Sessions',services:'Services',protocols:'Network / Ports',nodes:'Nodes',connectivity:'Connectivity Lab',telegramproxy:'Telegram Proxy',dnscenter:'Client DNS',diagnostics:'Diagnostics Center',operations:'Operations / DR',backups:'Backup',audit:'Logs',updates:'Update',settings:'Settings',support:'Support'};
  const dict=window.MAKIA_LANG==='en'?en:fa;
  document.documentElement.lang=window.MAKIA_LANG==='en'?'en':'fa';
  document.documentElement.dir=window.MAKIA_LANG==='en'?'ltr':'rtl';
  document.querySelectorAll('nav.pro-nav button[data-view]').forEach(b=>{const label=dict[b.dataset.view];const t=b.querySelector('b');if(label&&t)t.textContent=label});
}

let planCache=[];

async function plansCenter(renderToken=window.__viewRenderToken){
  title.textContent=tr('پلن‌ها','Plans');setPageContext('PLAN TEMPLATES');
  content.innerHTML='<div class="loading-state"><span class="spinner"></span><b>'+htmlEsc(tr('در حال بارگذاری پلن‌ها…','Loading plans…'))+'</b></div>';
  const rows=await api('/api/plans');if(renderToken!==window.__viewRenderToken||activeView!=='plans')return;
  planCache=rows;
  const cards=rows.map(p=>{
    const cfg=p.config||{},kind=String(p.protocol_kind||'').toLowerCase(),proto=kind.toUpperCase();
    const policy=kind==='wireguard'||kind==='openvpn'
      ?'<div class="plan-facts"><span><b>'+htmlEsc(tr('قالب تنظیمات اتصال','Connection template'))+'</b></span><span>'+htmlEsc(tr('بدون Quota/Expiry صوری','No fake quota/expiry'))+'</span></div>'
      :kind==='ssh'
        ?'<div class="plan-facts"><span>'+htmlEsc(tr('مدت','Duration'))+' <b>'+(Number(cfg.expire_days||0)||'∞')+(cfg.expire_days?'d':'')+'</b></span><span>'+htmlEsc(tr('دستگاه','Devices'))+' <b>'+Number(cfg.device_limit||1)+'</b></span><span>'+htmlEsc(tr('بدون سهمیه ترافیک صوری','No fake traffic quota'))+'</span></div>'
        :'<div class="plan-facts"><span>'+htmlEsc(tr('مدت','Duration'))+' <b>'+(Number(cfg.expire_days||0)||'∞')+(cfg.expire_days?'d':'')+'</b></span><span>'+htmlEsc(tr('حجم','Quota'))+' <b>'+(Number(cfg.quota_gb||0)||'∞')+(cfg.quota_gb?'GB':'')+'</b></span>'+(kind==='outline'?'':'<span>'+htmlEsc(tr('IP','IP limit'))+' <b>'+Number(cfg.ip_limit||1)+'</b></span>')+'</div>';
    return '<article class="ops-card plan-card"><div class="ops-card-head"><div><span class="pro-kicker">'+htmlEsc(proto)+'</span><h3>'+htmlEsc(p.name)+'</h3></div><span class="status-chip '+(p.active?'ok':'warn')+'">'+(p.active?tr('فعال','ACTIVE'):tr('غیرفعال','INACTIVE'))+'</span></div>'+
      policy+
      (p.price_label?'<p class="muted">'+htmlEsc(p.price_label)+'</p>':'')+
      '<div class="toolbar"><button class="primary" onclick="useServicePlan('+Number(p.id)+')">'+htmlEsc(tr('ساخت کاربر با این پلن','Create from plan'))+'</button><button class="ghost" onclick="editServicePlan('+Number(p.id)+')">'+htmlEsc(tr('ویرایش','Edit'))+'</button><button class="danger" onclick="deleteServicePlan('+Number(p.id)+')">'+htmlEsc(tr('حذف','Delete'))+'</button></div></article>';
  }).join('');
  content.innerHTML=[
    '<section class="pro-page-head"><div><span class="pro-kicker">SMART PLANS</span><h1>'+htmlEsc(tr('پلن‌ها و قالب‌ها','Plans & Templates'))+'</h1><p>'+htmlEsc(tr('ساخت سریع کاربر با تنظیمات از پیش تعریف‌شده و بدون تکرار فرم‌ها.','Create users quickly from reusable, validated protocol templates.'))+'</p></div><div class="pro-head-actions"><button class="primary" onclick="editServicePlan(0)">＋ '+htmlEsc(tr('پلن جدید','New plan'))+'</button></div></section>',
    '<section class="ops-card-grid">'+(cards||'<div class="empty">'+htmlEsc(tr('هنوز پلنی ساخته نشده است.','No plans yet.'))+'</div>')+'</section>'
  ].join('');
}

function editServicePlan(id){
  const p=planCache.find(x=>Number(x.id)===Number(id))||{name:'',protocol_kind:'xray',config:{expire_days:30,quota_gb:50,ip_limit:1,reset_days:30},price_label:'',active:true};
  const cfg=p.config||{};
  modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">PLAN TEMPLATE</div><h3>'+htmlEsc(id?tr('ویرایش پلن','Edit plan'):tr('پلن جدید','New plan'))+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div>'+
    '<div class="form-grid two"><label>'+htmlEsc(tr('نام پلن','Plan name'))+'<input id="plName" value="'+htmlEsc(p.name||'')+'"></label><label>'+htmlEsc(tr('پروتکل','Protocol'))+'<select id="plKind" onchange="syncPlanPolicyFields()"><option value="ssh">SSH / NPV</option><option value="xray">Xray / V2Ray</option><option value="wireguard">WireGuard</option><option value="openvpn">OpenVPN</option><option value="outline">Outline</option></select></label>'+
    '<label data-plan-policy="expiry">'+htmlEsc(tr('مدت روز','Expiry days'))+'<input id="plDays" type="number" min="0" max="3650" value="'+Number(cfg.expire_days||0)+'"></label><label data-plan-policy="quota">'+htmlEsc(tr('حجم GB','Quota GB'))+'<input id="plQuota" type="number" min="0" value="'+Number(cfg.quota_gb||0)+'"></label>'+
    '<label data-plan-policy="limit">'+htmlEsc(tr('محدودیت IP/Device','IP / Device limit'))+'<input id="plLimit" type="number" min="1" max="50" value="'+Number(cfg.ip_limit||cfg.device_limit||1)+'"></label><label data-plan-policy="reset">'+htmlEsc(tr('بازنشانی ترافیک','Traffic reset days'))+'<input id="plReset" type="number" min="0" value="'+Number(cfg.reset_days||0)+'"></label>'+
    '<label>'+htmlEsc(tr('قیمت/برچسب','Price / label'))+'<input id="plPrice" value="'+htmlEsc(p.price_label||'')+'"></label><label class="check-row"><input id="plActive" type="checkbox" '+(p.active!==false?'checked':'')+'> '+htmlEsc(tr('فعال','Active'))+'</label></div>'+
    '<details class="pro-advanced"><summary>'+htmlEsc(tr('تنظیمات تخصصی پروتکل','Protocol-specific options'))+'</summary><textarea id="plExtra" class="config-output small" spellcheck="false"></textarea></details>'+
    '<div class="wizard-footer"><button class="ghost" data-action="modal-close">'+htmlEsc(tr('انصراف','Cancel'))+'</button><button class="primary" onclick="saveServicePlan('+Number(id||0)+')">'+htmlEsc(tr('ذخیره','Save'))+'</button></div></div></div>';
  document.getElementById('plKind').value=p.protocol_kind||'xray';
  const extra={...cfg};['expire_days','quota_gb','ip_limit','device_limit','reset_days'].forEach(k=>delete extra[k]);
  document.getElementById('plExtra').value=JSON.stringify(extra,null,2);
  syncPlanPolicyFields();
}
function syncPlanPolicyFields(){
  const kind=document.getElementById('plKind')?.value||'xray';
  const visible={expiry:!['wireguard','openvpn'].includes(kind),quota:['xray','outline'].includes(kind),limit:['ssh','xray'].includes(kind),reset:kind==='xray'};
  document.querySelectorAll('[data-plan-policy]').forEach(el=>{el.style.display=visible[el.dataset.planPolicy]?'':'none'});
}
async function saveServicePlan(id){
  let extra={};try{extra=JSON.parse(formValue('plExtra','{}')||'{}')}catch(e){alert('JSON: '+e.message);return}
  const kind=formValue('plKind','');
  const config={...extra};
  if(!['wireguard','openvpn'].includes(kind))config.expire_days=Number(formValue('plDays','0')||0);
  if(['xray','outline'].includes(kind))config.quota_gb=Number(formValue('plQuota','0')||0);
  if(kind==='ssh')config.device_limit=Number(formValue('plLimit','1')||1);
  if(kind==='xray'){config.ip_limit=Number(formValue('plLimit','1')||1);config.reset_days=Number(formValue('plReset','0')||0)}
  const payload={name:formValue('plName','').trim(),protocol_kind:kind,config,price_label:formValue('plPrice','').trim(),active:formChecked('plActive')};
  if(!payload.name){alert(tr('نام پلن لازم است','Plan name is required'));return}
  try{
    await api('/api/plans'+(id?'/'+id:''),{method:id?'PUT':'POST',body:JSON.stringify(payload)});
    closeModal();toast(tr('پلن ذخیره شد','Plan saved'));await plansCenter();
  }catch(e){alert(e.message)}
}
async function deleteServicePlan(id){
  if(!confirm(tr('این پلن حذف شود؟','Delete this plan?')))return;
  try{await api('/api/plans/'+id,{method:'DELETE'});await plansCenter()}catch(e){alert(e.message)}
}
async function useServicePlan(id){
  const p=planCache.find(x=>Number(x.id)===Number(id));if(!p)return;
  const cfg=p.config||{},kind=p.protocol_kind;
  const suggested=(await api('/api/accounts/new-defaults').catch(()=>({username:'user001'}))).username||'user001';
  modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">QUICK CREATE · '+htmlEsc(String(kind).toUpperCase())+'</div><h3>'+htmlEsc(p.name)+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div>'+
    '<div class="form-grid two"><label>'+htmlEsc(tr('نام کاربر','Client name'))+'<input id="qpName" value="'+htmlEsc(suggested)+'"></label><label>'+htmlEsc(tr('دامنه/IP اتصال','Endpoint'))+'<input id="qpEndpoint" dir="ltr" value="'+htmlEsc(window.PANEL_DOMAIN||location.hostname)+'"></label>'+
    '<label>'+htmlEsc(tr('Port اختیاری','Optional port'))+'<input id="qpPort" type="number" min="1" max="65535" value="'+Number(cfg.port||0)+'"></label><label>'+htmlEsc(tr('رمز اختیاری SSH','SSH password (optional)'))+'<input id="qpPassword" type="text" placeholder="'+htmlEsc(tr('خالی = تولید خودکار','blank = generate'))+'"></label></div>'+
    '<div class="wizard-note"><b>'+htmlEsc(tr('تنظیمات پلن','Plan settings'))+'</b><span>'+htmlEsc(JSON.stringify(cfg))+'</span></div>'+
    '<div class="wizard-footer"><button class="ghost" data-action="modal-close">'+htmlEsc(tr('انصراف','Cancel'))+'</button><button class="primary" onclick="createFromPlan('+Number(id)+')">'+htmlEsc(tr('ساخت و تحویل','Create & deliver'))+'</button></div></div></div>';
}
async function createFromPlan(id){
  const p=planCache.find(x=>Number(x.id)===Number(id));if(!p)return;
  const cfg=p.config||{},name=formValue('qpName','').trim(),endpoint=formValue('qpEndpoint','').trim(),port=Number(formValue('qpPort',String(cfg.port||0))||cfg.port||0),kind=p.protocol_kind;
  if(!name||!endpoint){alert(tr('نام و Endpoint لازم است','Name and endpoint are required'));return}
  try{
    let result=null,key=name;
    if(kind==='ssh'){
      const secret=formValue('qpPassword','')||(await api('/api/accounts/generate-secret?mode=pin6')).secret;
      const exp=Number(cfg.expire_days||0)?new Date(Date.now()+Number(cfg.expire_days)*86400000).toISOString().slice(0,10):null;
      result=await api('/api/accounts',{method:'POST',body:JSON.stringify({username:name,endpoint,endpoint_mode:'auto',password:secret,password_mode:'manual',expire_date:exp,plan:p.name,note:'',connection_limit:Number(cfg.connection_limit||1),device_limit:Number(cfg.device_limit||1),quota_mb:Number(cfg.quota_gb||0)*1024,renewal_days:Number(cfg.expire_days||0)})});
      result.password=result.password||secret;
    }else if(kind==='outline'){
      result=await api('/api/protocols/outline/keys',{method:'POST',body:JSON.stringify({name,quota_gb:Number(cfg.quota_gb||0),expire_days:Number(cfg.expire_days||0)})});
      key=String(result.client_id);
    }else if(kind==='wireguard'){
      result=await api('/api/protocols/wireguard/peers',{method:'POST',body:JSON.stringify({name,endpoint,endpoint_mode:'auto',dns:cfg.dns||'1.1.1.1',mtu:Number(cfg.mtu||1280),keepalive:Number(cfg.keepalive??15),allowed_ips:cfg.allowed_ips||'0.0.0.0/0'})});
    }else if(kind==='openvpn'){
      result=await api('/api/protocols/openvpn/clients',{method:'POST',body:JSON.stringify({name,endpoint,endpoint_mode:'auto',port:port||Number(cfg.port||1194),proto:cfg.proto||'udp'})});
    }else if(kind==='xray'){
      const protocol=cfg.protocol||cfg.xray_protocol||'vless',transport=cfg.transport||'tcp',security=cfg.security||'none';
      result=await api('/api/protocols/xray/inbounds',{method:'POST',body:JSON.stringify({protocol,port:port||Number(cfg.port||2087),remark:cfg.remark||p.name+'-'+name,name,endpoint,endpoint_mode:'auto',listen:cfg.listen||'0.0.0.0',transport,security,flow:cfg.flow||'',credential:'',shadowsocks_method:cfg.shadowsocks_method||'aes-128-gcm',quota_gb:Number(cfg.quota_gb||0),expire_days:Number(cfg.expire_days||0),ip_limit:Number(cfg.ip_limit||1),reset_days:Number(cfg.reset_days||0),options:cfg.options||{}})});
      key=String(result.client_id);
    }
    closeModal();toast(tr('دسترسی ساخته شد','Access created'));
    if(kind==='xray'||kind==='outline')await openClientPortal(kind,key,name);else await switchView('access');
  }catch(e){alert(e.message)}
}

async function expiryCenter(renderToken=window.__viewRenderToken){
  title.textContent=tr('مرکز تمدید','Expiry Center');setPageContext('EXPIRY & RENEWAL');
  const data=await api('/api/expiry?days=30');if(renderToken!==window.__viewRenderToken||activeView!=='expiry')return;
  const rows=data.rows||[];
  content.innerHTML=[
    '<section class="pro-page-head"><div><span class="pro-kicker">EXPIRY CENTER</span><h1>'+htmlEsc(tr('تمدید و انقضا','Renewals & Expiry'))+'</h1><p>'+htmlEsc(tr('کاربرهای منقضی یا نزدیک انقضا را یکجا مدیریت کن.','Manage expired and soon-to-expire access in one place.'))+'</p></div><div class="pro-head-actions"><button class="ghost" onclick="renewSelected(7)">+7D</button><button class="primary" onclick="renewSelected(30)">+30D</button><button class="ghost" onclick="renewSelected(90)">+90D</button></div></section>',
    '<section class="pro-stat-strip"><div><span>'+htmlEsc(tr('۳۰ روز آینده','Next 30 days'))+'</span><b>'+Number(data.count||0)+'</b></div><div><span>'+htmlEsc(tr('منقضی','Expired'))+'</span><b>'+Number(data.expired||0)+'</b></div><div><span>'+htmlEsc(tr('قابل تمدید','Renewable'))+'</span><b>'+rows.filter(x=>x.renew_supported).length+'</b></div></section>',
    '<section class="panel"><div class="panel-head"><div><h3>'+htmlEsc(tr('لیست انقضا','Expiry list'))+'</h3><span>SSH · XRAY · OUTLINE</span></div><button class="ghost" onclick="toggleExpiryAll()">'+htmlEsc(tr('انتخاب همه','Select all'))+'</button></div><div class="table">'+(rows.length?rows.map(x=>'<div class="row ops-row"><div><label class="check-user"><input class="expiry-check" type="checkbox" data-kind="'+htmlEsc(x.kind)+'" data-key="'+dataEnc(x.key)+'" '+(x.renew_supported?'':'disabled')+'><div><b>'+htmlEsc(x.name)+'</b><span class="muted">'+htmlEsc(String(x.protocol||x.kind).toUpperCase())+'</span></div></label></div><div><span class="status-chip '+(x.expired?'bad':x.days_left<=3?'warn':'ok')+'">'+(x.expired?tr('منقضی','Expired'):x.days_left+'d')+'</span></div><div class="muted">'+(x.renew_supported?tr('تمدید Backend واقعی','Real backend renewal'):tr('تمدید خودکار پشتیبانی نمی‌شود','No managed renewal'))+'</div><div><button class="primary" '+(x.renew_supported?'onclick="renewOne(\''+htmlEsc(x.kind)+'\',\''+dataEnc(x.key)+'\',30)"':'disabled')+'>+30D</button></div></div>').join(''):'<div class="empty">'+htmlEsc(tr('موردی وجود ندارد.','Nothing expiring in this window.'))+'</div>')+'</div></section>'
  ].join('');
}
function toggleExpiryAll(){const xs=[...document.querySelectorAll('.expiry-check:not(:disabled)')],v=xs.some(x=>!x.checked);xs.forEach(x=>x.checked=v)}
async function renewOne(kind,key,days){return bulkManaged([{kind,key:dataDec(key)}],'renew',days)}
async function renewSelected(days){
  const items=[...document.querySelectorAll('.expiry-check:checked')].map(x=>({kind:x.dataset.kind,key:dataDec(x.dataset.key)}));
  if(!items.length){alert(tr('حداقل یک کاربر را انتخاب کنید','Select at least one access'));return}
  const add=Number(prompt(tr('چند GB حجم اضافه شود؟ 0 = بدون تغییر','Additional GB? 0 = unchanged'),'0')||0);
  await bulkManaged(items,'renew',days,add);
}
async function bulkManaged(items,action,days=0,quota_add_gb=0){
  try{
    const r=await api('/api/access/bulk',{method:'POST',body:JSON.stringify({items,action,days,quota_add_gb})});
    if(r.failed?.length)alert(tr('بعضی عملیات ناموفق بود: ','Some operations failed: ')+r.failed.map(x=>x.name||x.key).join(', '));
    toast(tr('عملیات انجام شد','Operation complete'));await currentView();
  }catch(e){alert(e.message)}
}

async function outlineWorkspace(renderToken=window.__viewRenderToken){
  title.textContent='Outline';setPageContext('OUTLINE SERVER');
  const [status,keys]=await Promise.all([api('/api/protocols/outline/status'),api('/api/protocols/outline/keys').catch(()=>[])]);
  if(renderToken!==window.__viewRenderToken||activeView!=='outline')return;
  const ready=Boolean(status.api_ok);
  const managedCount=keys.filter(k=>k.managed).length;
  const keyRows=keys.length?keys.map(k=>{
    const m=k.managed||null,clientId=m?String(m.id):'',name=m?.name||k.name||('Key '+k.id);
    const expiry=m?accessExpiryText({expire_at:Number(k.expire_at||m.expire_at||0)}):tr('خارج از Makia','External');
    const quota=Number(k.quota_bytes||m?.quota_bytes||0),used=Number(k.usage_bytes||0);
    const usage=m?(fmtBytes(used)+' / '+(quota?fmtBytes(quota):'∞')):fmtBytes(used);
    return '<div class="row"><div><b>'+htmlEsc(name)+'</b><div class="muted">ID '+htmlEsc(k.id)+' · '+(m?tr('Managed','Managed'):tr('External','External'))+'</div></div><div><b>'+htmlEsc(usage)+'</b><div class="muted">'+htmlEsc(expiry)+'</div></div><div><span class="status-chip '+(m&&m.enabled!==false?'ok':m?'warn':'')+'">'+(m?(m.enabled!==false?'ACTIVE':'DISABLED'):'OUTLINE')+'</span></div><div class="pro-row-actions">'+
      (m?'<button class="pro-more" data-action="access-detail" data-id="'+dataEnc('outline:'+clientId)+'" aria-label="جزئیات '+dataEnc(name)+'">•••</button>':'<button class="danger" data-action="outline-delete-key" data-key="'+dataEnc(String(k.id))+'">'+htmlEsc(tr('حذف','Delete'))+'</button>')+
      '</div></div>';
  }).join(''):'<div class="empty">'+htmlEsc(tr('کلیدی وجود ندارد.','No keys.'))+'</div>';
  content.innerHTML=[
    '<section class="protocol-page-header"><div class="protocol-page-title">'+protocolGlyph('outline')+'<div><span class="pro-kicker">OUTLINE SERVER</span><h2>Outline</h2><p>'+htmlEsc(tr('Management API واقعی، Traffic Metrics، Quota، Expiry و تحویل امن Access Key.','Real Management API, traffic metrics, quota, expiry and secure Access Key delivery.'))+'</p></div></div><div class="protocol-header-actions"><button class="ghost" onclick="setupOutline()">'+(ready?htmlEsc(tr('وضعیت نصب','Setup status')):htmlEsc(tr('راه‌اندازی','Setup')))+'</button><button class="primary" '+(ready?'onclick="openOutlineKeyCreate()"':'disabled')+'>＋ '+htmlEsc(tr('Access Key جدید','New Access Key'))+'</button></div></section>',
    '<section class="protocol-stat-grid"><div class="protocol-stat"><span class="icon">◈</span><div><span>Management API</span><b>'+(ready?'READY':'SETUP')+'</b></div></div><div class="protocol-stat"><span class="icon">♙</span><div><span>'+htmlEsc(tr('Managed','Managed'))+'</span><b>'+managedCount+'</b></div></div><div class="protocol-stat"><span class="icon">▣</span><div><span>Container</span><b>'+(status.container_active?'RUNNING':'STOPPED')+'</b></div></div></section>',
    (!ready?'<div class="notice">'+htmlEsc(status.error||tr('Outline هنوز روی VPS آماده نیست. Setup را بزن و دستور Root را اجرا کن.','Outline is not ready on this VPS. Open Setup and run the root command.'))+'</div>':''),
    '<section class="panel"><div class="panel-head"><div><h3>'+htmlEsc(tr('Access Keyها','Access Keys'))+'</h3><span>TRAFFIC · QUOTA · EXPIRY · DELIVERY</span></div><button class="ghost" data-action="refresh">'+htmlEsc(tr('بروزرسانی','Refresh'))+'</button></div><div class="table">'+keyRows+'</div></section>'
  ].join('');
}
async function setupOutline(){
  const host=prompt(tr('Hostname اختیاری برای Outline','Optional Outline hostname'),window.PANEL_DOMAIN||'')??'';if(host===null)return;
  const port=Number(prompt(tr('Port دسترسی Outline (0 = خودکار)','Outline access-key port (0 = automatic)'),'0')||0);
  const prep='sudo MAKIA_ENABLE_OUTLINE=1 makia-upgrade';
  try{
    const r=await api('/api/protocols/outline/install',{method:'POST',body:JSON.stringify({hostname:host,keys_port:port})});
    if(r.already_ready){toast('Outline READY');await outlineWorkspace();return}
    const dependency=Boolean(r.requires_dependency||r.status?.docker===false);
    modalRoot.innerHTML=[
      '<div class="modal-backdrop"><div class="modal outline-setup-modal">',
      '<div class="wizard-head"><div><div class="eyebrow">ROOT SETUP</div><h3>Outline Server</h3><p>'+htmlEsc(tr('نصب Host dependency و Outline باید در Shell روت انجام شود.','Host dependency and Outline installation must run in a root shell.'))+'</p></div><button class="close-btn" data-action="modal-close">×</button></div>',
      '<div class="protocol-stat-grid compact"><div class="protocol-stat"><span class="icon">▣</span><div><span>Docker</span><b>'+(dependency?'REQUIRED':'READY')+'</b></div></div><div class="protocol-stat"><span class="icon">◈</span><div><span>Management API</span><b>'+(r.status?.api_ok?'READY':'PENDING')+'</b></div></div></div>',
      dependency?'<div class="wizard-note warn"><b>'+htmlEsc(tr('مرحله ۱ · آماده‌سازی VPS','Step 1 · Prepare VPS'))+'</b><span>'+htmlEsc(tr('این دستور Docker را از مسیر Root نصب/فعال می‌کند و سرویس وب هیچ APTای اجرا نمی‌کند.','This root command prepares Docker; the web service never runs APT.'))+'</span></div><textarea id="outlineDependencyCmd" class="config-output small" readonly></textarea><div class="wizard-footer compact"><button class="primary" data-action="copy-target" data-target="outlineDependencyCmd">'+htmlEsc(tr('کپی دستور مرحله ۱','Copy step 1'))+'</button></div>':'',
      '<div class="wizard-note"><b>'+htmlEsc(dependency?tr('مرحله ۲ · نصب Outline','Step 2 · Install Outline'):tr('نصب Outline','Install Outline'))+'</b><span>'+htmlEsc(r.note||'')+'</span></div>',
      '<textarea id="outlineInstallCmd" class="config-output small" readonly></textarea>',
      '<div class="wizard-footer"><button class="primary" data-action="copy-target" data-target="outlineInstallCmd">'+htmlEsc(tr('کپی دستور نصب','Copy install command'))+'</button><button class="ghost" data-action="refresh">'+htmlEsc(tr('بعد از اجرا، بروزرسانی وضعیت','Refresh after running'))+'</button><button class="ghost" data-action="modal-close">'+htmlEsc(tr('بستن','Close'))+'</button></div>',
      '</div></div>'
    ].join('');
    if(dependency){const dep=document.getElementById('outlineDependencyCmd');if(dep)dep.value=r.dependency_command||prep}
    document.getElementById('outlineInstallCmd').value=r.command||'sudo makia-install-outline';
  }catch(e){
    const msg=String(e?.message||'');
    if(/docker host dependency|MAKIA_ENABLE_OUTLINE/i.test(msg)){
      modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal outline-setup-modal"><div class="wizard-head"><div><div class="eyebrow">HOST PREPARATION</div><h3>'+htmlEsc(tr('Docker برای Outline آماده نیست','Docker is not ready for Outline'))+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="wizard-note warn"><b>'+htmlEsc(tr('این خطا نیاز به نصب Root دارد','Root preparation required'))+'</b><span>'+htmlEsc(tr('دستور زیر را در SSH سرور اجرا کن، سپس دوباره Setup را باز کن.','Run this command in the VPS SSH shell, then reopen Setup.'))+'</span></div><textarea id="outlineDependencyCmd" class="config-output small" readonly></textarea><div class="wizard-footer"><button class="primary" data-action="copy-target" data-target="outlineDependencyCmd">'+htmlEsc(tr('کپی دستور','Copy command'))+'</button><button class="ghost" data-action="modal-close">'+htmlEsc(tr('بستن','Close'))+'</button></div></div></div>';
      document.getElementById('outlineDependencyCmd').value=prep;
      return;
    }
    alert(e.message)
  }
}
async function openOutlineKeyCreate(){
  const defs=await api('/api/accounts/new-defaults').catch(()=>({username:'user001'}));
  modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">OUTLINE ACCESS KEY</div><h3>'+htmlEsc(tr('ساخت کاربر Outline','Create Outline client'))+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="form-grid two"><label>'+htmlEsc(tr('نام','Name'))+'<input id="olName" value="'+htmlEsc(defs.username||'user001')+'"></label><label>'+htmlEsc(tr('حجم GB','Quota GB'))+'<input id="olQuota" type="number" min="0" value="50"></label><label>'+htmlEsc(tr('مدت روز','Expiry days'))+'<input id="olDays" type="number" min="0" value="30"></label></div><div class="wizard-footer"><button class="ghost" data-action="modal-close">'+htmlEsc(tr('انصراف','Cancel'))+'</button><button class="primary" onclick="createOutlineKey()">'+htmlEsc(tr('ساخت','Create'))+'</button></div></div></div>';
}
async function createOutlineKey(){
  const nameEl=document.getElementById('olName');
  const quotaEl=document.getElementById('olQuota');
  const daysEl=document.getElementById('olDays');
  const name=(nameEl?.value||'').trim();
  const quota=Number(quotaEl?.value||0);
  const days=Number(daysEl?.value||0);
  if(!name){alert(tr('نام کاربر Outline را وارد کنید','Enter an Outline client name'));return}
  if(!Number.isFinite(quota)||quota<0){alert(tr('حجم نامعتبر است','Invalid quota'));return}
  if(!Number.isFinite(days)||days<0){alert(tr('مدت نامعتبر است','Invalid expiry'));return}
  try{
    const r=await api('/api/protocols/outline/keys',{method:'POST',body:JSON.stringify({name,quota_gb:quota,expire_days:days})});
    closeModal();
    toast(tr('کلید Outline ساخته شد','Outline key created'));
    await openClientPortal('outline',String(r.client_id),name);
  }catch(e){alert(e.message)}
}
async function deleteOutlineKey(id){if(!confirm(tr('این کلید Outline حذف شود؟','Delete this Outline key?')))return;try{await api('/api/protocols/outline/keys/'+encodeURIComponent(dataDec(id)),{method:'DELETE'});await outlineWorkspace()}catch(e){alert(e.message)}}

async function setOutlineQuota(key,name,current){
  const raw=prompt(tr('حجم جدید بر حسب GB؛ 0 = نامحدود','New quota in GB; 0 = unlimited'),String(current||0));if(raw===null)return;
  const quota=Number(raw);if(!Number.isFinite(quota)||quota<0){alert(tr('حجم نامعتبر است','Invalid quota'));return}
  try{await api('/api/protocols/outline/clients/'+encodeURIComponent(key)+'/quota',{method:'PUT',body:JSON.stringify({quota_gb:quota})});toast(tr('Quota اعمال شد','Quota updated'));await outlineWorkspace()}catch(e){alert(e.message)}
}
async function reissueOutlineClient(key,name){
  if(!confirm(tr('Access Key قبلی پس از تعویض دیگر معتبر نخواهد بود. ادامه؟','The previous Access Key will be retired after rotation. Continue?')))return;
  try{const r=await api('/api/protocols/outline/clients/'+encodeURIComponent(key)+'/reissue',{method:'POST'});toast(tr('Access Key جدید صادر شد','Access Key reissued'));await outlineWorkspace();await openAccessShare('outline',key,name);if(r.cleanup_warning)alert(r.cleanup_warning)}catch(e){alert(e.message)}
}
async function openAccessDiagnostics(kind,key,name){
  try{
    const r=await api('/api/diagnostics/access/'+encodeURIComponent(kind)+'/'+encodeURIComponent(key));
    modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">ACCESS DIAGNOSTICS</div><h3>'+htmlEsc(name||key)+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="diagnostic-score '+(r.ok?'pass':'fail')+'"><b>'+(r.ok?'PASS':'CHECK')+'</b><span>'+htmlEsc(String(kind).toUpperCase())+'</span></div><div class="diagnostic-list">'+(r.checks||[]).map(x=>'<div><i class="'+(x.ok?'ok':'bad')+'">'+(x.ok?'✓':'!')+'</i><div><b>'+htmlEsc(x.name)+'</b><span>'+htmlEsc(x.detail||'')+'</span></div></div>').join('')+'</div><div class="wizard-footer"><button class="ghost" data-action="modal-close">'+htmlEsc(tr('بستن','Close'))+'</button></div></div></div>';
  }catch(e){alert(e.message)}
}

async function diagnosticsCenter(renderToken=window.__viewRenderToken){
  title.textContent=tr('مرکز عیب‌یابی','Diagnostics Center');setPageContext('DIAGNOSTICS CENTER');
  const [self,accessRows]=await Promise.all([api('/api/diagnostics/self-test'),api('/api/access')]);
  if(renderToken!==window.__viewRenderToken||activeView!=='diagnostics')return;
  const opts=accessRows.map(x=>'<option value="'+dataEnc(x.kind+'|'+x.key)+'">'+htmlEsc(x.name+' · '+String(x.protocol).toUpperCase())+'</option>').join('');
  content.innerHTML=[
    '<section class="pro-page-head"><div><span class="pro-kicker">DIAGNOSTICS</span><h1>'+htmlEsc(tr('مرکز عیب‌یابی','Diagnostics Center'))+'</h1><p>'+htmlEsc(tr('از Artifact تا سرویس، Listener، DNS و Runtime یک کاربر را مرحله‌به‌مرحله بررسی کن.','Trace one access from encrypted artifact through runtime, listener and DNS.'))+'</p></div><div class="pro-head-actions"><button class="primary" onclick="runSelfTest()">'+htmlEsc(tr('Self-Test کامل','Full Self-Test'))+'</button></div></section>',
    '<section class="diagnostic-score '+(self.ok?'pass':'fail')+'"><b>'+(self.ok?'PASS':'FAIL')+'</b><span>'+htmlEsc(self.summary||'')+'</span></section>',
    '<section class="panel"><div class="panel-head"><div><h3>'+htmlEsc(tr('عیب‌یابی یک کاربر','Diagnose an access'))+'</h3><span>ARTIFACT → POLICY → ENDPOINT → RUNTIME</span></div></div><div class="form-grid two"><label>'+htmlEsc(tr('کاربر','Access'))+'<select id="diagAccess">'+opts+'</select></label><label>&nbsp;<button class="primary full-field-btn" onclick="diagnoseSelectedAccess()">'+htmlEsc(tr('شروع تشخیص','Run diagnostics'))+'</button></label></div><div id="diagAccessResult"></div></section>'
  ].join('');
}
async function diagnoseSelectedAccess(){
  const raw=dataDec(document.getElementById('diagAccess').value),[kind,...rest]=raw.split('|'),key=rest.join('|');
  try{
    const r=await api('/api/diagnostics/access/'+encodeURIComponent(kind)+'/'+encodeURIComponent(key));
    document.getElementById('diagAccessResult').innerHTML='<div class="diagnostic-list">'+(r.checks||[]).map(x=>'<div><i class="'+(x.ok?'ok':'bad')+'">'+(x.ok?'✓':'!')+'</i><div><b>'+htmlEsc(x.name)+'</b><span>'+htmlEsc(x.detail||'')+'</span></div></div>').join('')+'</div>';
  }catch(e){alert(e.message)}
}

async function operationsCenter(renderToken=window.__viewRenderToken){
  title.textContent=tr('عملیات و انتقال','Operations / DR');setPageContext('OPERATIONS & DISASTER RECOVERY');
  const [dr,backup,cf,tg,notifications]=await Promise.all([
    api('/api/disaster-recovery/summary'),api('/api/backups/schedule'),api('/api/integrations/cloudflare'),api('/api/integrations/telegram'),api('/api/notifications')
  ]);
  if(renderToken!==window.__viewRenderToken||activeView!=='operations')return;
  const bstat=backup.status||{};
  content.innerHTML=[
    '<section class="pro-page-head"><div><span class="pro-kicker">OPERATIONS CONTROL</span><h1>'+htmlEsc(tr('عملیات، بکاپ و Disaster Recovery','Operations, Backup & Disaster Recovery'))+'</h1><p>'+htmlEsc(tr('مسیر عملیاتی از بکاپ رمزدار تا Restore، DNS cutover، اعلان و UAT.','Operational path from encrypted backup through restore, DNS cutover, alerts and UAT.'))+'</p></div><div class="pro-head-actions"><button class="primary" data-action="nav" data-view="backups">'+htmlEsc(tr('Backup Center','Backup Center'))+'</button></div></section>',
    '<section class="ops-card-grid">'+
      '<article class="ops-card"><div class="ops-card-head"><h3>'+htmlEsc(tr('Scheduled Backup','Scheduled Backup'))+'</h3><span class="status-chip '+(backup.enabled?'ok':'warn')+'">'+(backup.enabled?'ON':'OFF')+'</span></div><p>'+htmlEsc(tr('Full Migration رمزدار با نگهداری محلی و SCP اختیاری.','Encrypted Full Migration with local retention and optional SCP copy.'))+'</p><div class="toolbar"><button class="primary" onclick="configureBackupSchedule()">'+htmlEsc(tr('تنظیم','Configure'))+'</button><button class="ghost" onclick="runScheduledBackupNow()">'+htmlEsc(tr('اجرای الان','Run now'))+'</button></div><small class="muted">'+htmlEsc(bstat.name||bstat.error||tr('هنوز اجرا نشده','Not run yet'))+'</small></article>'+
      '<article class="ops-card"><div class="ops-card-head"><h3>Cloudflare DNS</h3><span class="status-chip '+(cf.configured?'ok':'warn')+'">'+(cf.configured?'READY':'SETUP')+'</span></div><p>'+htmlEsc(cf.record_name||tr('A record برای cutover سریع VPS','A record for fast VPS cutover'))+'</p><div class="toolbar"><button class="primary" onclick="configureCloudflare()">'+htmlEsc(tr('تنظیم','Configure'))+'</button><button class="ghost" onclick="testCloudflare()">'+htmlEsc(tr('تست','Test'))+'</button><button class="ghost" onclick="cloudflareCutover()">'+htmlEsc(tr('Cutover','Cutover'))+'</button></div></article>'+
      '<article class="ops-card"><div class="ops-card-head"><h3>Telegram</h3><span class="status-chip '+(tg.configured?'ok':'warn')+'">'+(tg.configured?'READY':'SETUP')+'</span></div><p>'+htmlEsc(tr('هشدار سرویس، انقضا، بکاپ و Bot امن.','Service, expiry and backup alerts plus secure admin bot.'))+'</p><div class="toolbar"><button class="primary" onclick="configureTelegram()">'+htmlEsc(tr('تنظیم','Configure'))+'</button><button class="ghost" onclick="testTelegram()">'+htmlEsc(tr('ارسال تست','Send test'))+'</button></div></article>'+
      '<article class="ops-card"><div class="ops-card-head"><h3>'+htmlEsc(tr('Disaster Recovery','Disaster Recovery'))+'</h3><span class="status-chip '+(dr.readiness?.ready?'ok':'warn')+'">'+(dr.readiness?.ready?'READY':'CHECK')+'</span></div><p>'+htmlEsc(tr('Preflight → Backup → Restore → Runtime → DNS → UAT','Preflight → Backup → Restore → Runtime → DNS → UAT'))+'</p><button class="primary" onclick="openDRWizard()">'+htmlEsc(tr('باز کردن Wizard','Open wizard'))+'</button></article>'+
    '</section>',
    '<section class="pro-stat-strip"><div><span>'+htmlEsc(tr('انقضا ≤۷روز','Expiry ≤7d'))+'</span><b>'+Number(notifications.summary?.expiring_7d||0)+'</b></div><div><span>'+htmlEsc(tr('منقضی','Expired'))+'</span><b>'+Number(notifications.summary?.expired||0)+'</b></div><div><span>'+htmlEsc(tr('Node آفلاین','Offline nodes'))+'</span><b>'+Number(notifications.summary?.nodes_offline||0)+'</b></div><div><span>'+htmlEsc(tr('آخرین Full Backup','Latest full backup'))+'</span><b>'+(dr.latest_full_backup?'✓':'—')+'</b></div></section>'
  ].join('');
}
function configureBackupSchedule(){
  api('/api/backups/schedule').then(s=>{
    const r=s.remote||{};
    modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">BACKUP AUTOMATION</div><h3>'+htmlEsc(tr('بکاپ زمان‌بندی‌شده','Scheduled backup'))+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="form-grid two"><label class="check-row"><input id="bsEnabled" type="checkbox" '+(s.enabled?'checked':'')+'> '+htmlEsc(tr('فعال','Enabled'))+'</label><label>'+htmlEsc(tr('هر چند ساعت','Every N hours'))+'<input id="bsFreq" type="number" min="1" max="168" value="'+Number(s.frequency_hours||24)+'"></label><label>'+htmlEsc(tr('تعداد بکاپ محلی','Keep local'))+'<input id="bsKeep" type="number" min="1" max="50" value="'+Number(s.keep_local||7)+'"></label><label>'+htmlEsc(tr('رمز Full Backup','Full backup password'))+'<input id="bsPass" type="password" placeholder="'+(s.has_password?tr('خالی = بدون تغییر','blank = unchanged'):'')+'"></label><label class="check-row"><input id="bsRemote" type="checkbox" '+(r.enabled?'checked':'')+'> '+htmlEsc(tr('ارسال SCP به VPS دیگر','Remote SCP copy'))+'</label><div class="wizard-note"><b>SSH host key verification</b><span>'+htmlEsc(tr('قبل از فعال‌سازی، کلید Host مقصد را در known_hosts سرور ثبت کن. اتصال ناشناس رد می‌شود.','Pre-register the destination host key in server known_hosts. Unknown hosts are rejected.'))+'</span></div><label>Host<input id="bsHost" dir="ltr" value="'+htmlEsc(r.host||'')+'"></label><label>User<input id="bsUser" dir="ltr" value="'+htmlEsc(r.user||'')+'"></label><label>Remote path<input id="bsPath" dir="ltr" value="'+htmlEsc(r.path||'/var/backups/makia')+'"></label><label>SSH Port<input id="bsPort" type="number" value="'+Number(r.port||22)+'"></label><label>SSH key path<input id="bsKey" dir="ltr" value="'+htmlEsc(r.key_path||'')+'" placeholder="/root/.ssh/id_ed25519"></label></div><div class="wizard-footer"><button class="primary" onclick="saveBackupSchedule()">'+htmlEsc(tr('ذخیره','Save'))+'</button></div></div></div>';
  }).catch(e=>alert(e.message))
}
async function saveBackupSchedule(){
  const payload={
    enabled:formChecked('bsEnabled'),frequency_hours:Number(formValue('bsFreq','24')||24),
    keep_local:Number(formValue('bsKeep','7')||7),password:formValue('bsPass',''),
    remote_enabled:formChecked('bsRemote'),remote_host:formValue('bsHost','').trim(),
    remote_user:formValue('bsUser','').trim(),remote_path:formValue('bsPath','').trim(),
    remote_port:Number(formValue('bsPort','22')||22),remote_key_path:formValue('bsKey','').trim()
  };
  try{await api('/api/backups/schedule',{method:'PUT',body:JSON.stringify(payload)});closeModal();await operationsCenter()}catch(e){alert(e.message)}
}
async function runScheduledBackupNow(){if(!confirm(tr('Full Migration Backup رمزدار الان ساخته شود؟','Create an encrypted Full Migration Backup now?')))return;try{const r=await api('/api/backups/schedule/run',{method:'POST'});toast('Backup: '+r.name);await operationsCenter()}catch(e){alert(e.message)}}
function configureCloudflare(){api('/api/integrations/cloudflare').then(s=>{modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">CLOUDFLARE DNS</div><h3>'+htmlEsc(tr('اتصال Cloudflare','Cloudflare integration'))+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="form-grid two"><label>API Token<input id="cfToken" type="password" placeholder="'+(s.configured?tr('خالی = بدون تغییر','blank = unchanged'):'')+'"></label><label>Zone ID<input id="cfZone" dir="ltr" value="'+htmlEsc(s.zone_id||'')+'"></label><label>A Record<input id="cfName" dir="ltr" value="'+htmlEsc(s.record_name||window.PANEL_DOMAIN||'')+'"></label><label>TTL<input id="cfTtl" type="number" min="60" value="'+Number(s.ttl||60)+'"></label></div><div class="wizard-note"><b>DNS only</b><span>'+htmlEsc(tr('Makia برای Endpointهای VPN/SSH رکورد را عمداً Proxy نمی‌کند.','Makia intentionally keeps VPN/SSH endpoints DNS-only, not proxied.'))+'</span></div><div class="wizard-footer"><button class="primary" onclick="saveCloudflare()">'+htmlEsc(tr('ذخیره','Save'))+'</button></div></div></div>'}).catch(e=>alert(e.message))}
async function saveCloudflare(){try{await api('/api/integrations/cloudflare',{method:'PUT',body:JSON.stringify({api_token:formValue('cfToken',''),zone_id:formValue('cfZone',''),record_name:formValue('cfName',''),ttl:Number(formValue('cfTtl','60')||60)})});closeModal();await operationsCenter()}catch(e){alert(e.message)}}
async function testCloudflare(){try{const r=await api('/api/integrations/cloudflare/test',{method:'POST'});alert(JSON.stringify(r,null,2))}catch(e){alert(e.message)}}
async function cloudflareCutover(){const ip=prompt(tr('IP جدید VPS','New VPS IPv4'),'');if(!ip)return;if(!confirm(tr('A Record به IP جدید تغییر کند؟','Change A record to the new IP?')))return;try{const r=await api('/api/integrations/cloudflare/cutover',{method:'POST',body:JSON.stringify({ipv4:ip})});alert((r.propagated?'DNS propagated':'DNS updated; propagation pending')+'\n'+JSON.stringify(r.record,null,2))}catch(e){alert(e.message)}}
function configureTelegram(){api('/api/integrations/telegram').then(s=>{modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal"><div class="wizard-head"><div><div class="eyebrow">TELEGRAM ADMIN</div><h3>'+htmlEsc(tr('Telegram Bot و هشدارها','Telegram bot & alerts'))+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div><div class="form-grid two"><label>Bot Token<input id="tgToken" type="password" placeholder="'+(s.configured?tr('خالی = بدون تغییر','blank = unchanged'):'')+'"></label><label>Chat ID<input id="tgChat" dir="ltr" value="'+htmlEsc(s.chat_id||'')+'"></label><label class="check-row"><input id="tgWebhook" type="checkbox" '+(s.webhook_enabled?'checked':'')+'> '+htmlEsc(tr('فعال‌سازی webhook /status /expiry /backup (فقط وضعیت)','Enable webhook commands /status /expiry /backup (status only)'))+'</label></div><div class="wizard-footer"><button class="primary" onclick="saveTelegram()">'+htmlEsc(tr('ذخیره','Save'))+'</button></div></div></div>'}).catch(e=>alert(e.message))}
async function saveTelegram(){try{await api('/api/integrations/telegram',{method:'PUT',body:JSON.stringify({bot_token:formValue('tgToken',''),chat_id:formValue('tgChat',''),enable_webhook:formChecked('tgWebhook')})});closeModal();await operationsCenter()}catch(e){alert(e.message)}}
async function testTelegram(){try{await api('/api/integrations/telegram/test',{method:'POST'});toast(tr('پیام تست ارسال شد','Test message sent'))}catch(e){alert(e.message)}}
async function openDRWizard(){
  try{
    const r=await api('/api/disaster-recovery/summary'),ready=r.readiness||{},backup=r.latest_full_backup;
    modalRoot.innerHTML='<div class="modal-backdrop"><div class="modal dr-wizard"><div class="wizard-head"><div><div class="eyebrow">DISASTER RECOVERY WIZARD</div><h3>'+htmlEsc(tr('انتقال به VPS جدید','Migrate to a new VPS'))+'</h3></div><button class="close-btn" data-action="modal-close">×</button></div>'+
      '<div class="dr-steps">'+[
        [tr('۱. Preflight','1. Preflight'),ready.ready,ready.ready?tr('سرور برای Backup آماده است','Source is backup-ready'):JSON.stringify(ready.blockers||[])],
        [tr('۲. Full Backup','2. Full backup'),Boolean(backup),backup?backup.name:tr('Full Backup بساز','Create a Full Migration Backup')],
        [tr('۳. مقصد','3. Destination'),true,'sudo makia-upgrade / install RC7'],
        [tr('۴. Restore','4. Restore'),false,tr('Upload → Verify → Restore از Backup Center','Upload → Verify → Restore in Backup Center')],
        [tr('۵. Runtime','5. Runtime'),false,'Xray · WG · OpenVPN · Outline · HTTPS'],
        [tr('۶. DNS Cutover','6. DNS cutover'),Boolean(r.cloudflare?.configured),r.cloudflare?.record_name||tr('Cloudflare را تنظیم کن','Configure Cloudflare')],
        [tr('۷. UAT','7. UAT'),false,tr('Client واقعی و داخل ایران','Real client and Iran field test')]
      ].map(x=>'<div class="dr-step"><i class="'+(x[1]?'ok':'pending')+'">'+(x[1]?'✓':'•')+'</i><div><b>'+htmlEsc(x[0])+'</b><span>'+htmlEsc(String(x[2]||''))+'</span></div></div>').join('')+'</div>'+
      '<div class="wizard-footer"><button class="ghost" data-action="nav" data-view="backups">'+htmlEsc(tr('Backup Center','Backup Center'))+'</button><button class="primary" onclick="cloudflareCutover()">'+htmlEsc(tr('DNS Cutover','DNS Cutover'))+'</button></div></div></div>';
  }catch(e){alert(e.message)}
}


let clientPlatformCache=[];

function clientDateValue(ts){
  if(!Number(ts))return '';
  const d=new Date(Number(ts)*1000);
  const y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,'0'),day=String(d.getDate()).padStart(2,'0');
  return y+'-'+m+'-'+day;
}
function clientExpireTs(value){
  if(!value)return 0;
  const n=Math.floor(new Date(value+'T23:59:59').getTime()/1000);
  return Number.isFinite(n)?n:0;
}
function clientExpiryLabel(ts){
  if(!Number(ts))return tr('بدون انقضا','No expiry');
  try{return new Intl.DateTimeFormat(isFa()?'fa-IR':'en-US',{dateStyle:'medium'}).format(new Date(Number(ts)*1000))}
  catch{return new Date(Number(ts)*1000).toLocaleDateString()}
}
function clientPortalUrl(username=''){
  const base=location.origin+'/client/login';
  return username?base+'?u='+encodeURIComponent(username):location.origin+'/client/';
}
function clientAccountState(a){
  if(!a.enabled)return '<span class="status-chip bad">'+htmlEsc(tr('غیرفعال','Disabled'))+'</span>';
  if(Number(a.expire_at||0)&&Number(a.expire_at)<Math.floor(Date.now()/1000))return '<span class="status-chip bad">'+htmlEsc(tr('منقضی','Expired'))+'</span>';
  return '<span class="status-chip ok">'+htmlEsc(tr('فعال','Active'))+'</span>';
}

async function clientPlatformCenter(renderToken=window.__viewRenderToken){
  title.textContent=tr('اپ کاربران','Client Platform');setPageContext('CLIENT PLATFORM');
  content.innerHTML='<div class="loading-state"><span class="spinner"></span><b>'+htmlEsc(tr('در حال همگام‌سازی Client Platform…','Synchronizing Client Platform…'))+'</b></div>';
  const [status,accountsList]=await Promise.all([
    api('/api/client-platform/status'),api('/api/client-platform/accounts')
  ]);
  if(renderToken!==window.__viewRenderToken||activeView!=='clientplatform')return;
  clientPlatformCache=accountsList||[];
  const enabled=Boolean(status.enabled);
  const portal=location.origin+(status.portal_path||'/client/');
  const totalQuota=clientPlatformCache.reduce((n,a)=>n+Number(a.quota_bytes||0),0);
  const totalUsed=clientPlatformCache.reduce((n,a)=>n+Number(a.used_bytes||0),0);
  const rows=clientPlatformCache.map(a=>{
    const link=clientPortalUrl(a.username);
    return '<div class="cp-account-row">'+
      '<div class="cp-user-cell"><span class="cp-avatar">'+htmlEsc(String(a.username||'?').slice(0,1).toUpperCase())+'</span><div><b>'+htmlEsc(a.display_name||a.username)+'</b><small dir="ltr">'+htmlEsc(a.username)+'</small></div></div>'+
      '<div><span class="cp-cell-label">'+htmlEsc(tr('پلن','Plan'))+'</span><b>'+htmlEsc(a.plan_name||'—')+'</b><small>'+htmlEsc(clientExpiryLabel(a.expire_at))+'</small></div>'+
      '<div><span class="cp-cell-label">'+htmlEsc(tr('دستگاه','Devices'))+'</span><b>'+Number(a.active_devices||0)+' / '+Number(a.device_limit||1)+'</b><small>'+htmlEsc(tr('همزمان','Concurrent'))+' '+Number(a.concurrent_device_limit||1)+'</small></div>'+
      '<div><span class="cp-cell-label">'+htmlEsc(tr('دسترسی‌ها','Access'))+'</span><b>'+Number(a.bindings||0)+'</b><small>'+fmtBytes(Number(a.used_bytes||0))+(Number(a.quota_bytes||0)?' / '+fmtBytes(Number(a.quota_bytes||0)):'')+'</small></div>'+
      '<div class="cp-state-cell">'+clientAccountState(a)+'</div>'+
      '<div class="cp-row-actions"><button class="ghost" data-action="client-copy-link" data-user="'+dataEnc(a.username)+'">'+htmlEsc(tr('کپی لینک','Copy link'))+'</button><button class="primary" data-action="client-account-open" data-id="'+Number(a.id)+'">'+htmlEsc(tr('مدیریت','Manage'))+'</button></div>'+
    '</div>';
  }).join('');
  const override=status.enable_source==='env_on'||status.enable_source==='env_off';
  content.innerHTML=[
    '<div class="pro-page client-platform-page">',
      '<section class="pro-page-head"><div><span class="pro-kicker">MAKIA CLIENT</span><h1>'+htmlEsc(tr('اپ کاربران','Client Platform'))+'</h1><p>'+htmlEsc(tr('حساب، دستگاه، اشتراک و تحویل امن پروتکل‌ها؛ بدون تغییر Credential کاربران فعلی.','Accounts, devices, subscriptions and secure delivery without rotating existing credentials.'))+'</p></div><div class="pro-head-actions"><button class="ghost" data-action="client-open-portal">'+htmlEsc(tr('باز کردن اپ کاربران','Open client app'))+'</button><button class="primary" data-action="client-account-new">＋ '+htmlEsc(tr('حساب جدید','New client'))+'</button></div></section>',
      '<section class="cp-rollout-card '+(enabled?'is-on':'is-off')+'"><div><span class="pro-kicker">ROLLOUT CONTROL</span><h3>'+htmlEsc(enabled?tr('Client Portal فعال است','Client Portal is enabled'):tr('Client Portal غیرفعال است','Client Portal is disabled'))+'</h3><p>'+htmlEsc(override?tr('وضعیت توسط Environment Override قفل شده است.','State is locked by an environment override.'):tr('این کلید فقط Portal کاربران را کنترل می‌کند و سرویس‌های VPN فعلی را Restart یا Rotate نمی‌کند.','This switch controls only the client portal and does not restart or rotate active VPN services.'))+'</p></div><div class="cp-rollout-actions"><code>'+htmlEsc(portal)+'</code><button class="ghost" data-action="client-copy-portal">'+htmlEsc(tr('کپی','Copy'))+'</button><button class="'+(enabled?'danger':'primary')+'" data-action="client-platform-toggle" data-enabled="'+(enabled?'0':'1')+'" '+(status.admin_toggle_available?'':'disabled')+'>'+(enabled?htmlEsc(tr('غیرفعال کردن','Disable')):htmlEsc(tr('فعال کردن','Enable')))+'</button></div></section>',
      '<section class="pro-stat-strip cp-stats"><div><span>'+htmlEsc(tr('حساب‌ها','Accounts'))+'</span><b>'+Number(status.account_count||0)+'</b></div><div><span>'+htmlEsc(tr('فعال','Active'))+'</span><b>'+Number(status.active_accounts||0)+'</b></div><div><span>'+htmlEsc(tr('دستگاه ثبت‌شده','Registered devices'))+'</span><b>'+Number(status.registered_devices||0)+'</b></div><div><span>'+htmlEsc(tr('دسترسی‌های Bind شده','Bound access'))+'</span><b>'+Number(status.bindings||0)+'</b></div></section>',
      '<section class="cp-safety-note"><b>'+htmlEsc(tr('مرز Enforcement','Enforcement boundary'))+'</b><span>'+htmlEsc(tr('محدودیت دستگاه Web/PWA روی خود Portal اعمال می‌شود. محدودیت زمان و حجم برای پروتکل‌هایی که Hard Policy دارند در Runtime سرور هم اعمال می‌شود. قفل سخت‌افزاری واقعی دستگاه در Native Agent مرحله بعد است.','Web/PWA device limits protect the portal itself. Expiry/quota are also enforced in server runtime where a hard policy adapter is available. Hardware-backed device lock comes with the native agent.'))+'</span></section>',
      '<section class="cp-enforcement-grid">'+Object.entries(status.enforcement||{}).map(([name,e])=>'<article class="cp-enforcement-card"><div><b>'+htmlEsc(name.toUpperCase())+'</b><span class="status-chip '+(e.mode==='hard'?'ok':e.mode==='setup_required'?'warn':'muted')+'">'+htmlEsc(e.mode==='hard'?tr('کنترل فعال','Hard policy'):e.mode==='setup_required'?tr('نیاز به راه‌اندازی','Setup required'):tr('تحویل پروفایل','Delivery'))+'</span></div><small>'+htmlEsc((e.expiry?tr('انقضا ✓','Expiry ✓'):tr('انقضا —','Expiry —'))+' · '+(e.quota?tr('حجم ✓','Quota ✓'):tr('حجم —','Quota —'))+' · '+(e.device?tr('دستگاه ✓','Device ✓'):tr('دستگاه Portal','Portal device')))+'</small>'+(name==='openvpn'&&e.mode==='setup_required'?'<button class="ghost" data-action="client-openvpn-policy-enable">'+htmlEsc(tr('فعال‌سازی کنترل OpenVPN','Enable OpenVPN policy'))+'</button>':'')+(name==='openvpn'&&e.policy_conflict?'<em>'+htmlEsc(e.policy_conflict)+'</em>':'')+'</article>').join('')+'</section>',
      '<section class="pro-directory cp-directory"><div class="pro-directory-toolbar"><div><h3>'+htmlEsc(tr('حساب‌های Client','Client accounts'))+'</h3><small>'+clientPlatformCache.length+' ACCOUNT · '+fmtBytes(totalUsed)+(totalQuota?' / '+fmtBytes(totalQuota):'')+'</small></div><div class="pro-search-wrap"><span>⌕</span><input id="clientPlatformSearch" placeholder="'+htmlEsc(tr('جستجو نام، پلن یا یوزرنیم…','Search name, plan or username…'))+'"></div></div>',
      '<div class="cp-account-head"><span>'+htmlEsc(tr('کاربر','Client'))+'</span><span>'+htmlEsc(tr('پلن / انقضا','Plan / expiry'))+'</span><span>'+htmlEsc(tr('دستگاه','Devices'))+'</span><span>'+htmlEsc(tr('مصرف / دسترسی','Usage / access'))+'</span><span>'+htmlEsc(tr('وضعیت','Status'))+'</span><span></span></div>',
      '<div id="clientPlatformRows">'+(rows||'<div class="empty">'+htmlEsc(tr('هنوز حساب Client ساخته نشده است.','No client account has been created yet.'))+'</div>')+'</div></section>',
    '</div>'
  ].join('');
  const search=document.getElementById('clientPlatformSearch');
  search?.addEventListener('input',()=>{
    const q=(search.value||'').trim().toLowerCase();
    document.querySelectorAll('#clientPlatformRows .cp-account-row').forEach((row,i)=>{
      const a=clientPlatformCache[i],hay=((a?.username||'')+' '+(a?.display_name||'')+' '+(a?.plan_name||'')).toLowerCase();
      row.hidden=Boolean(q&&!hay.includes(q));
    });
  });
}

function openClientAccountCreate(){
  modalRoot.innerHTML=[
    '<div class="modal-backdrop"><div class="modal cp-modal">',
      '<div class="modal-head"><div><span class="pro-kicker">NEW CLIENT</span><h3>'+htmlEsc(tr('ساخت حساب Client','Create client account'))+'</h3><p>'+htmlEsc(tr('این عملیات فقط حساب Client می‌سازد؛ هیچ پروتکل فعالی تغییر نمی‌کند.','This creates only a client account; no active protocol is changed.'))+'</p></div><button class="close-btn" data-action="modal-close">×</button></div>',
      '<div class="cp-form-grid">',
        '<label><span>'+htmlEsc(tr('نام کاربری','Username'))+'</span><input id="cpUser" dir="ltr" maxlength="64" autocomplete="off"></label>',
        '<label><span>'+htmlEsc(tr('نام نمایشی','Display name'))+'</span><input id="cpDisplay" maxlength="120"></label>',
        '<label class="cp-span-2"><span>'+htmlEsc(tr('رمز عبور','Password'))+'</span><div class="cp-inline"><input id="cpPass" dir="ltr" type="text" maxlength="128" autocomplete="new-password"><button class="ghost" data-action="client-password-generate" data-target="cpPass">'+htmlEsc(tr('ساخت رمز قوی','Generate'))+'</button></div></label>',
        '<label><span>'+htmlEsc(tr('پلن','Plan'))+'</span><input id="cpPlan" maxlength="120" placeholder="30 Days"></label>',
        '<label><span>'+htmlEsc(tr('انقضا','Expiry'))+'</span><input id="cpExpire" type="date"></label>',
        '<label><span>'+htmlEsc(tr('حجم کل GB','Quota GB'))+'</span><input id="cpQuota" type="number" min="0" step="1" value="0"></label>',
        '<label><span>'+htmlEsc(tr('تعداد دستگاه','Device limit'))+'</span><input id="cpDevices" type="number" min="1" max="20" value="1"></label>',
        '<label><span>'+htmlEsc(tr('دستگاه همزمان','Concurrent devices'))+'</span><input id="cpConcurrent" type="number" min="1" max="20" value="1"></label>',
      '</div>',
      '<div class="wizard-note"><b>'+htmlEsc(tr('پیشنهاد','Recommended'))+'</b><span>'+htmlEsc(tr('برای فروش تک‌دستگاه: Device limit = 1 و Concurrent = 1. رمز عبور حداقل ۸ کاراکتر باشد.','For a single-device plan use Device limit = 1 and Concurrent = 1. Password must be at least 8 characters.'))+'</span></div>',
      '<div class="wizard-footer"><button class="ghost" data-action="modal-close">'+htmlEsc(tr('انصراف','Cancel'))+'</button><button class="primary" data-action="client-account-create">'+htmlEsc(tr('ساخت حساب','Create account'))+'</button></div>',
    '</div></div>'
  ].join('');
  const d=new Date();d.setDate(d.getDate()+30);const exp=document.getElementById('cpExpire');if(exp)exp.value=d.toISOString().slice(0,10);
}

async function createClientAccount(){
  const username=document.getElementById('cpUser')?.value.trim()||'';
  const password=document.getElementById('cpPass')?.value||'';
  const display_name=document.getElementById('cpDisplay')?.value.trim()||'';
  const plan_name=document.getElementById('cpPlan')?.value.trim()||'';
  const device_limit=Number(document.getElementById('cpDevices')?.value||1);
  const concurrent_device_limit=Number(document.getElementById('cpConcurrent')?.value||1);
  const quota_gb=Number(document.getElementById('cpQuota')?.value||0);
  const expire_at=clientExpireTs(document.getElementById('cpExpire')?.value||'');
  if(username.length<3)throw new Error(tr('نام کاربری حداقل ۳ کاراکتر باشد.','Username must be at least 3 characters.'));
  if(password.length<8)throw new Error(tr('رمز عبور حداقل ۸ کاراکتر باشد.','Password must be at least 8 characters.'));
  const item=await api('/api/client-platform/accounts',{method:'POST',body:JSON.stringify({username,password,display_name,plan_name,expire_at,quota_gb,device_limit,concurrent_device_limit,enabled:true})});
  window.__lastClientCredential={username,password,url:clientPortalUrl(username)};
  showClientOnboarding(item,username,password);
}

function showClientOnboarding(item,username,password){
  modalRoot.innerHTML=[
    '<div class="modal-backdrop"><div class="modal cp-modal cp-onboarding">',
      '<div class="modal-head"><div><span class="pro-kicker">READY</span><h3>'+htmlEsc(tr('حساب Client آماده است','Client account is ready'))+'</h3><p>'+htmlEsc(tr('این رمز را فقط یک‌بار و از مسیر امن به کاربر تحویل بده.','Deliver this password to the user once through a secure channel.'))+'</p></div><button class="close-btn" data-action="modal-close-refresh" data-view="clientplatform">×</button></div>',
      '<div class="cp-credential-box"><label>'+htmlEsc(tr('نام کاربری','Username'))+'<input id="cpReadyUser" readonly dir="ltr" value="'+htmlEsc(username)+'"></label><label>'+htmlEsc(tr('رمز عبور','Password'))+'<input id="cpReadyPass" readonly dir="ltr" value="'+htmlEsc(password)+'"></label><label class="cp-span-2">'+htmlEsc(tr('لینک ورود','Login link'))+'<input id="cpReadyUrl" readonly dir="ltr" value="'+htmlEsc(clientPortalUrl(username))+'"></label></div>',
      '<div class="wizard-footer"><button class="ghost" data-action="copy-target" data-target="cpReadyUrl">'+htmlEsc(tr('کپی لینک','Copy link'))+'</button><button class="ghost" data-action="copy-target" data-target="cpReadyUser">'+htmlEsc(tr('کپی یوزر','Copy username'))+'</button><button class="primary" data-action="copy-target" data-target="cpReadyPass">'+htmlEsc(tr('کپی رمز','Copy password'))+'</button><button class="primary" data-action="client-account-open" data-id="'+Number(item.id)+'">'+htmlEsc(tr('مدیریت حساب','Manage'))+'</button></div>',
    '</div></div>'
  ].join('');
}

async function openClientAccountManage(accountId){
  const [a,protocolsData,artifactsData]=await Promise.all([
    api('/api/client-platform/accounts/'+Number(accountId)),
    api('/api/client-platform/protocols'),
    api('/api/client-platform/artifacts')
  ]);
  const protocolBindings=a.bindings_detail||[],artifactBindings=a.artifact_bindings_detail||[];
  const boundProtocolIds=new Set(protocolBindings.map(x=>Number(x.protocol_client_id)));
  const boundArtifactIds=new Set(artifactBindings.map(x=>Number(x.artifact_id)));
  const protocols=(protocolsData.items||[]).filter(x=>!x.bound||Number(x.bound_account_id)===Number(a.id));
  const artifacts=(artifactsData.items||[]).filter(x=>['ssh','wireguard','openvpn','openvpn_wstunnel'].includes(String(x.kind||'').toLowerCase())&&(!x.bound||Number(x.bound_account_id)===Number(a.id)));
  const protocolOptions=protocols.map(x=>'<option value="p:'+Number(x.id)+'" '+(boundProtocolIds.has(Number(x.id))?'disabled':'')+'>'+htmlEsc((x.name||'')+' · '+String(x.protocol||x.engine||'').toUpperCase()+(x.bound?' · BOUND':''))+'</option>').join('');
  const artifactOptions=artifacts.map(x=>'<option value="a:'+Number(x.id)+'" '+(boundArtifactIds.has(Number(x.id))?'disabled':'')+'>'+htmlEsc((x.display_name||x.external_key||'')+' · '+String(x.kind||'').toUpperCase()+(x.bound?' · BOUND':''))+'</option>').join('');
  const bindings=[
    ...protocolBindings.map(x=>({type:'protocol',id:x.protocol_client_id,label:x.label||x.protocol_name,kind:x.protocol,enabled:x.protocol_enabled})),
    ...artifactBindings.map(x=>({type:'artifact',id:x.artifact_id,label:x.label||x.display_name,kind:x.kind,enabled:true}))
  ];
  const devices=(a.devices||[]).map(d=>'<div class="cp-device-row"><div><b>'+htmlEsc(d.label||'Web / PWA')+'</b><small>'+htmlEsc(d.platform||'web')+' · '+htmlEsc(d.last_ip||'')+' · ****'+htmlEsc(d.device_key_last4||'')+'</small></div><span class="status-chip '+(d.active?'ok':'bad')+'">'+htmlEsc(d.active?tr('فعال','Active'):tr('لغوشده','Revoked'))+'</span>'+(d.active?'<button class="danger" data-action="client-device-revoke-admin" data-account="'+Number(a.id)+'" data-device="'+Number(d.id)+'">'+htmlEsc(tr('لغو','Revoke'))+'</button>':'')+'</div>').join('');
  const bindingRows=bindings.map(b=>'<div class="cp-binding-row"><div><span class="cp-protocol-mark">'+htmlEsc(String(b.kind||'').slice(0,3).toUpperCase())+'</span><div><b>'+htmlEsc(b.label||'Access')+'</b><small>'+htmlEsc(b.type==='protocol'?tr('Managed protocol','Managed protocol'):tr('Existing profile','Existing profile'))+'</small></div></div><button class="danger" data-action="client-binding-remove" data-account="'+Number(a.id)+'" data-type="'+b.type+'" data-id="'+Number(b.id)+'">'+htmlEsc(tr('حذف اتصال','Unbind'))+'</button></div>').join('');
  modalRoot.innerHTML=[
    '<div class="modal-backdrop detail-backdrop"><aside class="access-detail-drawer cp-manage-drawer">',
      '<header><div><span class="pro-kicker">CLIENT ACCOUNT</span><h3>'+htmlEsc(a.display_name||a.username)+'</h3><p dir="ltr">'+htmlEsc(a.username)+'</p></div><button class="close-btn" data-action="modal-close">×</button></header>',
      '<div class="access-detail-body">',
        '<section class="cp-manage-grid">',
          '<label><span>'+htmlEsc(tr('نام نمایشی','Display name'))+'</span><input id="cpmDisplay" value="'+htmlEsc(a.display_name||'')+'"></label>',
          '<label><span>'+htmlEsc(tr('پلن','Plan'))+'</span><input id="cpmPlan" value="'+htmlEsc(a.plan_name||'')+'"></label>',
          '<label><span>'+htmlEsc(tr('انقضا','Expiry'))+'</span><input id="cpmExpire" type="date" value="'+htmlEsc(clientDateValue(a.expire_at))+'"></label>',
          '<label><span>'+htmlEsc(tr('حجم GB','Quota GB'))+'</span><input id="cpmQuota" type="number" min="0" step=".1" value="'+(Number(a.quota_bytes||0)/1073741824).toFixed(2).replace(/\.00$/,'')+'"></label>',
          '<label><span>'+htmlEsc(tr('Device limit','Device limit'))+'</span><input id="cpmDevices" type="number" min="1" max="20" value="'+Number(a.device_limit||1)+'"></label>',
          '<label><span>'+htmlEsc(tr('Concurrent','Concurrent'))+'</span><input id="cpmConcurrent" type="number" min="1" max="20" value="'+Number(a.concurrent_device_limit||1)+'"></label>',
        '</section>',
        '<div class="cp-account-control"><label class="switch-label"><input id="cpmEnabled" type="checkbox" '+(a.enabled?'checked':'')+'><span>'+htmlEsc(tr('حساب فعال','Account enabled'))+'</span></label><button class="primary" data-action="client-account-save" data-id="'+Number(a.id)+'">'+htmlEsc(tr('ذخیره تنظیمات','Save settings'))+'</button></div>',
        '<section class="detail-section"><div class="detail-section-head"><div><h4>'+htmlEsc(tr('اتصال دسترسی‌ها','Access bindings'))+'</h4><p>'+htmlEsc(tr('Credential موجود را بدون ساخت مجدد به این حساب متصل کن.','Bind existing credentials without recreating them.'))+'</p></div></div><div class="cp-bind-add"><select id="cpBindSelect"><option value="">'+htmlEsc(tr('انتخاب دسترسی…','Select access…'))+'</option><optgroup label="Xray / Outline">'+protocolOptions+'</optgroup><optgroup label="SSH / WireGuard / OpenVPN / WStunnel 443">'+artifactOptions+'</optgroup></select><input id="cpBindLabel" placeholder="'+htmlEsc(tr('نام نمایشی اختیاری','Optional label'))+'"><button class="primary" data-action="client-binding-add" data-account="'+Number(a.id)+'">'+htmlEsc(tr('Bind','Bind'))+'</button></div><div class="cp-binding-list">'+(bindingRows||'<div class="empty compact">'+htmlEsc(tr('هنوز دسترسی Bind نشده است.','No access is bound yet.'))+'</div>')+'</div></section>',
        '<section class="detail-section"><div class="detail-section-head"><div><h4>'+htmlEsc(tr('دستگاه‌ها','Devices'))+'</h4><p>'+htmlEsc(tr('لغو دستگاه، Sessionهای همان دستگاه را هم باطل می‌کند.','Revoking a device also invalidates its sessions.'))+'</p></div><button class="ghost" data-action="client-devices-revoke-all" data-account="'+Number(a.id)+'">'+htmlEsc(tr('لغو همه دستگاه‌ها','Revoke all'))+'</button></div><div class="cp-device-list">'+(devices||'<div class="empty compact">'+htmlEsc(tr('دستگاهی ثبت نشده است.','No registered device.'))+'</div>')+'</div></section>',
        '<section class="detail-section"><div class="detail-section-head"><div><h4>'+htmlEsc(tr('رمز و Session','Password & sessions'))+'</h4><p>'+htmlEsc(tr('تعویض رمز همه Sessionهای فعلی را باطل می‌کند.','Changing the password revokes all current sessions.'))+'</p></div></div><div class="cp-password-row"><input id="cpmPassword" type="text" dir="ltr" placeholder="'+htmlEsc(tr('رمز جدید حداقل ۸ کاراکتر','New password, minimum 8 characters'))+'"><button class="ghost" data-action="client-password-generate" data-target="cpmPassword">'+htmlEsc(tr('ساخت رمز','Generate'))+'</button><button class="primary" data-action="client-password-rotate" data-id="'+Number(a.id)+'" data-user="'+dataEnc(a.username)+'">'+htmlEsc(tr('تعویض رمز','Rotate password'))+'</button><button class="danger" data-action="client-sessions-revoke-all" data-account="'+Number(a.id)+'">'+htmlEsc(tr('خروج همه Sessionها','Revoke sessions'))+'</button></div></section>',
      '</div>',
      '<footer><button class="danger" data-action="client-account-delete" data-id="'+Number(a.id)+'" data-user="'+dataEnc(a.username)+'">'+htmlEsc(tr('حذف حساب Client','Delete client account'))+'</button><button class="ghost" data-action="client-copy-link" data-user="'+dataEnc(a.username)+'">'+htmlEsc(tr('کپی لینک ورود','Copy login link'))+'</button><button class="ghost" data-action="modal-close">'+htmlEsc(tr('بستن','Close'))+'</button></footer>',
    '</aside></div>'
  ].join('');
}

async function saveClientAccount(accountId){
  const payload={
    display_name:document.getElementById('cpmDisplay')?.value.trim()||'',
    plan_name:document.getElementById('cpmPlan')?.value.trim()||'',
    expire_at:clientExpireTs(document.getElementById('cpmExpire')?.value||''),
    quota_gb:Number(document.getElementById('cpmQuota')?.value||0),
    device_limit:Number(document.getElementById('cpmDevices')?.value||1),
    concurrent_device_limit:Number(document.getElementById('cpmConcurrent')?.value||1),
    enabled:Boolean(document.getElementById('cpmEnabled')?.checked)
  };
  await api('/api/client-platform/accounts/'+Number(accountId),{method:'PUT',body:JSON.stringify(payload)});
  toast(tr('حساب Client بروزرسانی شد','Client account updated'));
  await openClientAccountManage(accountId);
}
async function bindClientAccess(accountId){
  const raw=document.getElementById('cpBindSelect')?.value||'';
  if(!raw)throw new Error(tr('یک دسترسی انتخاب کن.','Select an access.'));
  const [type,idText]=raw.split(':'),id=Number(idText),label=document.getElementById('cpBindLabel')?.value.trim()||'';
  if(type==='p')await api('/api/client-platform/accounts/'+Number(accountId)+'/bindings',{method:'POST',body:JSON.stringify({protocol_client_id:id,label,priority:100,enabled:true})});
  else if(type==='a')await api('/api/client-platform/accounts/'+Number(accountId)+'/artifact-bindings',{method:'POST',body:JSON.stringify({artifact_id:id,label,priority:100,enabled:true})});
  else throw new Error('invalid binding');
  toast(tr('دسترسی به حساب متصل شد','Access bound to account'));
  await openClientAccountManage(accountId);
}
async function removeClientBinding(accountId,type,id){
  if(!confirm(tr('این Bind حذف شود؟ Credential اصلی و Runtime حذف نمی‌شوند.','Remove this binding? The original credential and runtime will remain untouched.')))return;
  const url=type==='protocol'?'/api/client-platform/accounts/'+accountId+'/bindings/'+id:'/api/client-platform/accounts/'+accountId+'/artifact-bindings/'+id;
  await api(url,{method:'DELETE'});toast(tr('Bind حذف شد','Binding removed'));await openClientAccountManage(accountId);
}
async function rotateClientPassword(accountId,username){
  const password=document.getElementById('cpmPassword')?.value||'';
  if(password.length<8)throw new Error(tr('رمز جدید حداقل ۸ کاراکتر باشد.','New password must be at least 8 characters.'));
  await api('/api/client-platform/accounts/'+accountId+'/password',{method:'POST',body:JSON.stringify({password})});
  window.__lastClientCredential={username,password,url:clientPortalUrl(username)};
  alert(tr('رمز تغییر کرد و همه Sessionهای قبلی باطل شدند. رمز جدید را اکنون به کاربر تحویل بده.','Password changed and all old sessions were revoked. Deliver the new password to the user now.'));
  const el=document.getElementById('cpmPassword');if(el)el.value='';
}

const views={dashboard,clientplatform:clientPlatformCenter,inbounds:inboundsWorkspace,access,plans:plansCenter,expiry:expiryCenter,ssh:accounts,xray:xrayWorkspace,outline:outlineWorkspace,wireguard,openvpn:openvpnWorkspace,accounts,sessions,services,protocols,guides,nodes,security,connectivity:connectivityLab,telegramproxy:telegramProxyCenter,dnscenter:dnsCenter,diagnostics:diagnosticsCenter,operations:operationsCenter,backups,audit:auditView,updates,settings,support:supportCenter};
window.__viewRenderToken=0;
function currentView(){const token=++window.__viewRenderToken;return(views[activeView]||dashboard)(token)}
function switchView(v){
  activeView=v;
  setPageContext(v==='dashboard'?'OVERVIEW':v==='clientplatform'?'CLIENT PLATFORM':v==='inbounds'?'INBOUNDS':v==='access'?'CLIENTS':v==='ssh'?'SSH CLIENTS':v==='xray'?'XRAY CLIENTS':v==='wireguard'?'WIREGUARD PEERS':v==='openvpn'?'OPENVPN CLIENTS':v==='connectivity'?'CONNECTIVITY LAB':v==='telegramproxy'?'TELEGRAM MTPROXY':v==='dnscenter'?'PRIVATE DNS':v==='settings'?'SETTINGS':'MAKIA CONTROL CENTER');
  document.querySelectorAll('nav button[data-view]').forEach(x=>x.classList.toggle('active',x.dataset.view===v));
  document.querySelectorAll('.pro-nav-group').forEach(g=>{
    const name=g.dataset.groupRoot;
    const shouldOpen=(name==='protocols'&&['ssh','xray','wireguard','openvpn','outline','inbounds','telegramproxy','dnscenter'].includes(v))||(name==='infra'&&['services','protocols','sessions','nodes','connectivity','diagnostics','operations'].includes(v))||(name==='system'&&['audit','backups','updates'].includes(v));
    if(shouldOpen)g.classList.add('open');
  });
  document.body.classList.remove('menu-open');
  document.querySelector('.mobile-menu-toggle')?.setAttribute('aria-expanded','false');
  return currentView();
}
document.querySelectorAll('nav button[data-view]').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.view)));
applyLanguageShell();localizeVisibleUi(document);ensureSessionContext().catch(()=>{});switchView('dashboard');
if('serviceWorker' in navigator){window.addEventListener('load',()=>navigator.serviceWorker.register('/static/sw.js').catch(()=>{}));}
