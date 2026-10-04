"use strict";

const HOST="com.makia.client.browser";

function native(message){
  return new Promise((resolve,reject)=>{
    chrome.runtime.sendNativeMessage(HOST,message,response=>{
      const last=chrome.runtime.lastError;
      if(last){reject(new Error(last.message||"Makia Browser Host is unavailable"));return}
      if(!response){reject(new Error("No response from Makia Browser Host"));return}
      if(!response.ok){reject(new Error(response.error||"Makia Browser Host error"));return}
      resolve(response.result||{});
    });
  });
}

function proxyGet(){
  return new Promise(resolve=>chrome.proxy.settings.get({incognito:false},resolve));
}

function proxySet(details){
  return new Promise((resolve,reject)=>{
    chrome.proxy.settings.set(details,()=>{
      const last=chrome.runtime.lastError;
      if(last)reject(new Error(last.message));else resolve();
    });
  });
}

async function proxyClear(){
  const current=await proxyGet();
  if(current.levelOfControl!=="controlled_by_this_extension")return;
  return new Promise((resolve,reject)=>{
    chrome.proxy.settings.clear({scope:"regular"},()=>{
      const last=chrome.runtime.lastError;
      if(last)reject(new Error(last.message));else resolve();
    });
  });
}

async function applyBrowserProxy(port){
  const p=Number(port||0);
  if(!Number.isInteger(p)||p<1024||p>65535)throw new Error("Invalid local proxy port");
  const current=await proxyGet();
  if(!["controllable_by_this_extension","controlled_by_this_extension"].includes(current.levelOfControl)){
    throw new Error("Browser proxy is controlled by another extension or policy");
  }
  await proxySet({
    value:{
      mode:"fixed_servers",
      rules:{
        singleProxy:{scheme:"socks5",host:"127.0.0.1",port:p},
        bypassList:["<local>","localhost","127.0.0.1"]
      }
    },
    scope:"regular"
  });
}

function privacyGet(api){
  return new Promise(resolve=>api.get({},resolve));
}

function privacySet(api,value){
  return new Promise((resolve,reject)=>api.set({value},()=>{
    const last=chrome.runtime.lastError;
    if(last)reject(new Error(last.message));else resolve();
  }));
}

function privacyClear(api){
  return new Promise((resolve,reject)=>api.clear({},()=>{
    const last=chrome.runtime.lastError;
    if(last)reject(new Error(last.message));else resolve();
  }));
}

async function enableWebRtcLeakProtection(){
  const api=chrome.privacy&&chrome.privacy.network&&chrome.privacy.network.webRTCIPHandlingPolicy;
  if(!api)throw new Error("Browser WebRTC privacy control is unavailable");
  const current=await privacyGet(api);
  if(current.value==="disable_non_proxied_udp")return;
  if(!["controllable_by_this_extension","controlled_by_this_extension"].includes(current.levelOfControl)){
    throw new Error("WebRTC leak protection is controlled by another extension or policy");
  }
  await privacySet(api,"disable_non_proxied_udp");
}

async function clearWebRtcLeakProtection(){
  const api=chrome.privacy&&chrome.privacy.network&&chrome.privacy.network.webRTCIPHandlingPolicy;
  if(!api)return;
  const current=await privacyGet(api);
  if(current.levelOfControl==="controlled_by_this_extension")await privacyClear(api);
}

async function badge(status){
  const on=!!(status&&status.connected);
  await chrome.action.setBadgeText({text:on?"ON":""});
  await chrome.action.setTitle({title:on?"Makia VPN — Connected":"Makia VPN"});
}

async function status(){
  const s=await native({action:"status"});
  await badge(s);
  return s;
}

async function handle(message){
  const action=String(message&&message.action||"");
  if(action==="pair")return native({action:"pair",controller:message.controller,code:message.code});
  if(action==="me")return native({action:"me"});
  if(action==="protocols")return native({action:"protocols"});
  if(action==="status")return status();
  if(action==="connect"){
    const mode=message.mode==="device"?"device":"browser";
    const result=await native({
      action:"connect",kind:message.kind,id:Number(message.id),mode
    });
    if(mode==="browser"){
      try{
        if(!result.proxy_port)throw new Error("Local Browser Only proxy did not start");
        await enableWebRtcLeakProtection();
        await applyBrowserProxy(result.proxy_port);
      }catch(error){
        try{await native({action:"disconnect"})}catch(_e){}
        try{await proxyClear()}catch(_e){}
        try{await clearWebRtcLeakProtection()}catch(_e){}
        throw error;
      }
    }else{
      await proxyClear();
      await clearWebRtcLeakProtection();
    }
    await badge({connected:true});
    return result;
  }
  if(action==="disconnect"){
    const result=await native({action:"disconnect"});
    await proxyClear();
    await clearWebRtcLeakProtection();
    await badge({connected:false});
    return result;
  }
  if(action==="logout"){
    try{await native({action:"disconnect"})}catch(_e){}
    await proxyClear();
    await clearWebRtcLeakProtection();
    const result=await native({action:"logout"});
    await badge({connected:false});
    return result;
  }
  throw new Error("Unsupported extension action");
}

chrome.runtime.onMessage.addListener((message,_sender,sendResponse)=>{
  handle(message).then(result=>sendResponse({ok:true,result})).catch(error=>sendResponse({ok:false,error:error.message||String(error)}));
  return true;
});

async function restore(){
  try{
    const s=await native({action:"status"});
    if(s.connected&&s.scope==="browser"&&s.proxy_port){
      await applyBrowserProxy(s.proxy_port);
      await enableWebRtcLeakProtection();
    }else{
      await proxyClear();
      await clearWebRtcLeakProtection();
    }
    await badge(s);
  }catch(_e){
    await badge({connected:false});
  }
}

chrome.runtime.onStartup.addListener(restore);
chrome.runtime.onInstalled.addListener(restore);
