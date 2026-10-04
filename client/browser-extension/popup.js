"use strict";

const $=id=>document.getElementById(id);
let state={paired:false,connected:false,scope:"",proxy_port:0};
let accesses=[];

function send(action,payload={}){
  return new Promise((resolve,reject)=>{
    chrome.runtime.sendMessage({action,...payload},response=>{
      const last=chrome.runtime.lastError;
      if(last){reject(new Error(last.message));return}
      if(!response||!response.ok){reject(new Error(response&&response.error||"Makia extension error"));return}
      resolve(response.result||{});
    });
  });
}

function showError(error){
  const el=$("error");
  el.textContent=error?String(error.message||error):"";
  el.hidden=!error;
}

function bytes(n){
  n=Number(n||0);
  if(!n)return"0 B";
  const units=["B","KB","MB","GB","TB"];
  let i=0;
  while(n>=1024&&i<units.length-1){n/=1024;i++}
  return (i?n.toFixed(n>=10?1:2):Math.round(n))+" "+units[i];
}

function date(ts){
  if(!Number(ts))return"بدون انقضا";
  try{return new Intl.DateTimeFormat("fa-IR",{dateStyle:"medium"}).format(new Date(Number(ts)*1000))}
  catch(_e){return"—"}
}

function currentMode(){
  return document.querySelector('input[name="mode"]:checked')?.value||"browser";
}

function browserSupported(item){
  const engine=String(item.engine||"").toLowerCase();
  return !["wireguard","openvpn"].includes(engine);
}

function renderState(){
  $("pairView").hidden=!!state.paired;
  $("mainView").hidden=!state.paired;
  $("dot").classList.toggle("on",!!state.connected);
  $("statusText").textContent=state.connected
    ?(state.scope==="browser"?"Connected · Browser Only":"Connected · Device VPN")
    :"Disconnected";
  $("disconnectBtn").disabled=!state.connected;
}

function renderAccesses(){
  const list=$("accessList");
  list.textContent="";
  if(!accesses.length){
    const p=document.createElement("p");p.className="muted";p.textContent="دسترسی فعالی برای این حساب وجود ندارد.";list.appendChild(p);return;
  }
  for(const item of accesses){
    const row=document.createElement("div");row.className="access";
    const meta=document.createElement("div");
    const title=document.createElement("strong");title.textContent=item.label||item.name||"Makia Access";
    const small=document.createElement("small");small.textContent=(item.engine||"")+" · "+(item.protocol||"");
    meta.append(title,small);
    const btn=document.createElement("button");btn.className="primary";btn.textContent="Connect";
    const mode=currentMode();
    if(!item.available){btn.disabled=true;btn.title="این دسترسی در حال حاضر فعال نیست."}
    else if(mode==="browser"&&!browserSupported(item)){btn.disabled=true;btn.title="برای این پروتکل Device VPN را انتخاب کنید."}
    btn.addEventListener("click",()=>connectItem(item,btn));
    row.append(meta,btn);list.appendChild(row);
  }
}

async function load(){
  showError(null);
  try{
    state=await send("status");
    renderState();
    if(!state.paired)return;
    const [me,p]=await Promise.all([send("me"),send("protocols")]);
    $("accountName").textContent=me.display_name||me.username||"—";
    $("planName").textContent=me.plan_name||"اشتراک اختصاصی";
    $("usage").textContent=bytes(me.used_bytes)+(Number(me.quota_bytes||0)?" / "+bytes(me.quota_bytes):"");
    $("expiry").textContent=date(me.expire_at);
    accesses=Array.isArray(p.items)?p.items:[];
    renderAccesses();
  }catch(error){
    showError(error);
    if(/not paired|expired|authentication/i.test(String(error.message||error))){
      state={paired:false,connected:false};renderState();
    }
  }
}

async function connectItem(item,button){
  showError(null);
  button.disabled=true;
  try{
    const mode=currentMode();
    const result=await send("connect",{
      kind:item.delivery_kind,id:item.delivery_id,mode
    });
    state.connected=true;
    state.scope=mode;
    state.proxy_port=Number(result.proxy_port||0);
    renderState();
    if(result.uac)showError(new Error("در پنجره UAC اجازه اجرا را تأیید کنید؛ Device VPN بعد از تأیید فعال می‌شود."));
  }catch(error){showError(error)}
  finally{renderAccesses()}
}

$("pairBtn").addEventListener("click",async()=>{
  showError(null);$("pairBtn").disabled=true;
  try{
    await send("pair",{controller:$("controller").value.trim(),code:$("pairCode").value.trim()});
    $("pairCode").value="";
    await load();
  }catch(error){showError(error)}
  finally{$("pairBtn").disabled=false}
});

$("refreshBtn").addEventListener("click",load);
$("disconnectBtn").addEventListener("click",async()=>{
  showError(null);$("disconnectBtn").disabled=true;
  try{await send("disconnect");state.connected=false;state.scope="";state.proxy_port=0;renderState()}
  catch(error){showError(error)}
  finally{$("disconnectBtn").disabled=!state.connected}
});
$("logoutBtn").addEventListener("click",async()=>{
  showError(null);
  try{await send("logout");state={paired:false,connected:false};accesses=[];renderState()}
  catch(error){showError(error)}
});
document.querySelectorAll('input[name="mode"]').forEach(x=>x.addEventListener("change",renderAccesses));

load();
