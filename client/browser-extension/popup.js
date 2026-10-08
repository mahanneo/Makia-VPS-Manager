const $ = id => document.getElementById(id);
const EXT_HEADER={"X-Makia-Extension":"1"};
let state={controller:"",token:"",deviceKey:"",account:null,gateway:null};

function normalizeController(value){
  const u=new URL(String(value||"").trim());
  if(u.protocol!=="https:") throw new Error("آدرس پنل باید HTTPS باشد.");
  if(u.username||u.password||u.search||u.hash) throw new Error("آدرس پنل معتبر نیست.");
  return u.origin;
}
function api(path,options={}){
  const headers=Object.assign({},EXT_HEADER,options.headers||{});
  if(state.token) headers.Authorization="Bearer "+state.token;
  if(options.body&&!headers["Content-Type"]) headers["Content-Type"]="application/json";
  return fetch(state.controller+path,Object.assign({},options,{headers})).then(async r=>{
    let data={}; try{data=await r.json();}catch(_){}
    if(!r.ok) throw new Error(data.detail||data.error||("HTTP "+r.status));
    return data;
  });
}
async function ensureOriginPermission(origin){
  const pattern=origin+"/*";
  const has=await chrome.permissions.contains({origins:[pattern]});
  if(has) return true;
  return chrome.permissions.request({origins:[pattern]});
}
async function loadStorage(){
  const saved=await chrome.storage.local.get(["controller","token","deviceKey","account"]);
  state=Object.assign(state,saved);
}
async function saveAuth(){
  await chrome.storage.local.set({controller:state.controller,token:state.token,deviceKey:state.deviceKey,account:state.account});
}
function setError(id,msg){$(id).textContent=msg||"";}
function bytes(n){
  n=Number(n||0); if(!n) return "0 B";
  const u=["B","KB","MB","GB","TB"]; let i=0;
  while(n>=1024&&i<u.length-1){n/=1024;i++;}
  return (i?n.toFixed(n>=10?1:2):Math.round(n))+" "+u[i];
}
async function render(){
  const logged=!!state.token;
  $("setupView").classList.toggle("hidden",logged);
  $("appView").classList.toggle("hidden",!logged);
  if(!logged) return;

  const status=await chrome.runtime.sendMessage({action:"status"});
  const connection=status&&status.ok?status.result:{connected:false,connectionError:"وضعیت Proxy قابل بررسی نیست"};
  $("statusDot").className="dot "+(connection.connected?"on":"off");
  $("connectionState").textContent=connection.connected?"متصل · تأیید شد":"قطع";
  $("activeLabel").textContent=connection.connected?"Makia Browser VPN":"Browser VPN";
  $("disconnectBtn").classList.toggle("hidden",!connection.connected);
  $("verifyBtn").classList.toggle("hidden",!connection.connected);
  $("exitIp").textContent=connection.connected&&connection.exitIp?connection.exitIp:"هنوز تأیید نشده";
  $("verificationState").textContent=connection.connected&&connection.verifiedAt?
    "IP خروجی از اتصال HTTPS واقعی بررسی شد. آخرین تست: "+new Date(connection.verifiedAt).toLocaleTimeString("fa-IR"):
    "صرف نمایش وضعیت متصل، تغییر IP را تضمین نمی‌کند.";
  if(connection.connectionError&&!$("appError").textContent) setError("appError",connection.connectionError);

  const a=state.account||{};
  const quota=Number(a.quota_bytes||0),used=Number(a.used_bytes||0);
  $("accountMeta").textContent=(a.display_name||a.username||"Makia")+(quota?" · "+bytes(used)+" / "+bytes(quota):"");

  const g=state.gateway||{};
  $("gatewayHost").textContent=(g.gateway&&g.gateway.host)?g.gateway.host:"—";
  $("gatewayState").textContent=g.available?"آماده اتصال":"در دسترس نیست";
  $("connectBtn").disabled=!g.available||!!connection.connected;
  $("connectBtn").textContent=connection.connected?"متصل":"اتصال";
}
async function refresh(){
  setError("appError","");
  try{
    state.account=await api("/client/extension/me");
    state.gateway=await api("/client/extension/browser-gateway");
    await chrome.storage.local.set({account:state.account});
    await render();
  }catch(e){
    if(/401|authentication|session/i.test(String(e.message||e))) await logout(false);
    setError("appError",e.message);
  }
}
async function login(){
  setError("setupError","");
  $("loginBtn").disabled=true;
  try{
    const origin=normalizeController($("controller").value);
    if(!await ensureOriginPermission(origin)) throw new Error("اجازه دسترسی افزونه به پنل داده نشد.");
    state.controller=origin;
    const data=await api("/client/extension/login",{
      method:"POST",
      body:JSON.stringify({
        username:$("username").value,
        password:$("password").value,
        device_key:state.deviceKey||"",
        device_label:"Chrome / Edge · Makia Browser VPN"
      })
    });
    state.token=data.token;
    state.deviceKey=data.device_key||state.deviceKey||"";
    state.account=data.account;
    $("password").value="";
    await saveAuth();
    await refresh();
  }catch(e){setError("setupError",e.message);}
  finally{$("loginBtn").disabled=false;}
}
async function connectGateway(){
  setError("appError","");
  $("connectBtn").disabled=true;
  $("connectBtn").textContent="در حال اتصال…";
  try{
    const data=await api("/client/extension/browser-gateway/credential",{method:"POST"});
    const response=await chrome.runtime.sendMessage({action:"connect",proxy:data.proxy});
    if(!response||!response.ok) throw new Error((response&&response.error)||"اتصال ناموفق بود");
    await refresh();
  }catch(e){
    setError("appError",e.message);
    await render();
  }
}
async function verifyGateway(){
  setError("appError","");
  $("verifyBtn").disabled=true;
  try{
    const result=await chrome.runtime.sendMessage({action:"verify"});
    if(!result||!result.ok) throw new Error((result&&result.error)||"تست IP خروجی ناموفق بود");
  }catch(e){setError("appError",String(e.message||e));}
  finally{$("verifyBtn").disabled=false;await render();}
}
async function disconnect(){
  setError("appError","");
  const r=await chrome.runtime.sendMessage({action:"disconnect"});
  if(!r||!r.ok) setError("appError",(r&&r.error)||"قطع اتصال ناموفق بود");
  await refresh();
}
async function logout(callServer=true){
  try{if(callServer&&state.token) await api("/client/extension/logout",{method:"POST"});}catch(_){}
  try{await chrome.runtime.sendMessage({action:"disconnect"});}catch(_){}
  const keep={controller:state.controller,deviceKey:state.deviceKey};
  await chrome.storage.local.clear();
  await chrome.storage.local.set(keep);
  state={controller:keep.controller,deviceKey:keep.deviceKey,token:"",account:null,gateway:null};
  $("controller").value=keep.controller||"";
  await render();
}
$("loginBtn").addEventListener("click",login);
$("refreshBtn").addEventListener("click",refresh);
$("connectBtn").addEventListener("click",connectGateway);
$("disconnectBtn").addEventListener("click",disconnect);
$("verifyBtn").addEventListener("click",verifyGateway);
$("logoutBtn").addEventListener("click",()=>logout(true));
(async()=>{
  await loadStorage();
  $("controller").value=state.controller||"";
  if(state.token) await refresh();
  await render();
})();
