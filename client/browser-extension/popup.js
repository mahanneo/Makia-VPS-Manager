const $ = id => document.getElementById(id);
const EXT_HEADER = {"X-Makia-Extension":"1"};
let state = {controller:"",token:"",deviceKey:"",account:null,gateway:null};

function normalizeController(value){
  const u=new URL(String(value||"").trim());
  if(u.protocol!=="https:") throw new Error("آدرس پنل باید HTTPS باشد.");
  if(u.username||u.password||u.search||u.hash) throw new Error("آدرس پنل معتبر نیست.");
  return u.origin;
}

async function api(path,options={}){
  const headers=Object.assign({},EXT_HEADER,options.headers||{});
  if(state.token) headers.Authorization="Bearer "+state.token;
  if(options.body&&!headers["Content-Type"]) headers["Content-Type"]="application/json";
  const response=await fetch(state.controller+path,Object.assign({},options,{headers}));
  let data={}; try{data=await response.json();}catch(_){}
  if(!response.ok) throw new Error(data.detail||data.error||("HTTP "+response.status));
  return data;
}

async function loadStorage(){
  const saved=await chrome.storage.local.get(["controller","token","deviceKey","account"]);
  state=Object.assign(state,saved);
}

async function saveAuth(){
  await chrome.storage.local.set({
    controller:state.controller,
    token:state.token,
    deviceKey:state.deviceKey,
    account:state.account
  });
}

function bytes(n){
  n=Number(n||0);
  if(!n) return "0 B";
  const units=["B","KB","MB","GB","TB"]; let i=0;
  while(n>=1024&&i<units.length-1){n/=1024;i++;}
  return (i?n.toFixed(n>=10?1:2):Math.round(n))+" "+units[i];
}

function setError(id,msg){$(id).textContent=msg||"";}

async function render(){
  const logged=!!state.token;
  $("setupView").classList.toggle("hidden",logged);
  $("appView").classList.toggle("hidden",!logged);
  if(!logged) return;

  const stored=await chrome.storage.local.get(["connected","gatewayHost","gatewayPort","proxyError"]);
  $("statusDot").className="dot "+(stored.connected?"on":"off");
  $("connectionState").textContent=stored.connected?"متصل":"قطع";
  $("activeLabel").textContent=stored.connected?"Makia Browser VPN":"Browser VPN";
  $("disconnectBtn").classList.toggle("hidden",!stored.connected);
  $("connectBtn").classList.toggle("hidden",!!stored.connected);

  const a=state.account||{};
  const quota=Number(a.quota_bytes||0),used=Number(a.used_bytes||0);
  $("accountMeta").textContent=(a.display_name||a.username||"Makia")+(quota?" · "+bytes(used)+" / "+bytes(quota):"");

  const gateway=state.gateway||{};
  if(gateway.available){
    $("gatewayMeta").textContent=(gateway.host||"Makia")+" : "+Number(gateway.port||0)+" · HTTPS";
    $("connectBtn").disabled=false;
  }else{
    $("gatewayMeta").textContent=gateway.reason||"Browser Gateway آماده نیست";
    $("connectBtn").disabled=true;
  }
  setError("appError",stored.proxyError||"");
}

async function refresh(){
  setError("appError","");
  try{
    state.account=await api("/client/extension/me");
    const status=await api("/client/extension/browser-status");
    state.gateway=status.gateway||null;
    await chrome.storage.local.set({account:state.account});
  }catch(e){
    if(/401|authentication|session/i.test(String(e.message||e))) await logout(false);
    else setError("appError",e.message);
  }
  await render();
}

async function login(){
  setError("setupError","");
  $("loginBtn").disabled=true;
  try{
    state.controller=normalizeController($("controller").value);
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

async function connect(){
  setError("appError","");
  $("connectBtn").disabled=true;
  $("connectBtn").textContent="در حال اتصال…";
  try{
    const response=await chrome.runtime.sendMessage({action:"connect"});
    if(!response||!response.ok) throw new Error((response&&response.error)||"اتصال ناموفق بود");
    await refresh();
  }catch(e){setError("appError",e.message);}
  finally{
    $("connectBtn").textContent="اتصال";
    if(state.gateway&&state.gateway.available) $("connectBtn").disabled=false;
  }
}

async function disconnect(){
  setError("appError","");
  const response=await chrome.runtime.sendMessage({action:"disconnect"});
  if(!response||!response.ok) setError("appError",(response&&response.error)||"قطع اتصال ناموفق بود");
  await refresh();
}

async function logout(callServer=true){
  try{await chrome.runtime.sendMessage({action:"disconnect"});}catch(_){}
  try{if(callServer&&state.token) await api("/client/extension/logout",{method:"POST"});}catch(_){}
  const keep={controller:state.controller,deviceKey:state.deviceKey};
  await chrome.storage.local.clear();
  await chrome.storage.session.clear();
  await chrome.storage.local.set(keep);
  state={controller:keep.controller,deviceKey:keep.deviceKey,token:"",account:null,gateway:null};
  $("controller").value=keep.controller||"";
  await render();
}

$("loginBtn").addEventListener("click",login);
$("refreshBtn").addEventListener("click",refresh);
$("connectBtn").addEventListener("click",connect);
$("disconnectBtn").addEventListener("click",disconnect);
$("logoutBtn").addEventListener("click",()=>logout(true));

chrome.storage.onChanged.addListener((changes,area)=>{
  if(area==="local"&&(changes.connected||changes.proxyError)) render().catch(()=>{});
});

(async()=>{
  await loadStorage();
  $("controller").value=state.controller||"";
  if(state.token) await refresh();
  await render();
})();
