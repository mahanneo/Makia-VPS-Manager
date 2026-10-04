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

function proxySet(details){
  return new Promise((resolve,reject)=>{
    chrome.proxy.settings.set(details,()=>{
      const last=chrome.runtime.lastError;
      if(last)reject(new Error(last.message));else resolve();
    });
  });
}

function proxyClear(){
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
    await proxyClear();
    const result=await native({
      action:"connect",kind:message.kind,id:Number(message.id),mode
    });
    if(mode==="browser"){
      if(!result.proxy_port)throw new Error("Local Browser Only proxy did not start");
      await applyBrowserProxy(result.proxy_port);
    }
    await badge({connected:true});
    return result;
  }
  if(action==="disconnect"){
    await proxyClear();
    const result=await native({action:"disconnect"});
    await badge({connected:false});
    return result;
  }
  if(action==="logout"){
    await proxyClear();
    try{await native({action:"disconnect"})}catch(_e){}
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
    if(s.connected&&s.scope==="browser"&&s.proxy_port)await applyBrowserProxy(s.proxy_port);
    else if(!s.connected)await proxyClear();
    await badge(s);
  }catch(_e){
    await badge({connected:false});
  }
}

chrome.runtime.onStartup.addListener(restore);
chrome.runtime.onInstalled.addListener(restore);
