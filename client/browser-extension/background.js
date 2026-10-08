// Browser-only HTTPS proxy. A configured proxy is NOT a verified VPN connection.
const IP_PROBES=[
  {url:"https://api.ipify.org?format=json",json:true},
  {url:"https://api4.ipify.org?format=json",json:true},
  {url:"https://checkip.amazonaws.com/",json:false}
];
const CONNECTION_KEYS=["connected","activeLabel","proxyHost","proxyPort","exitIp","directIp","verifiedAt","connectionError"];

function publicIp(value){
  const ip=String(value||"").trim();
  // The public IP probe is informational; only return plausibly formed IPs.
  if (ip.length<3||ip.length>45||!/^[0-9a-fA-F:.]+$/.test(ip)) return "";
  return ip;
}

async function fetchPublicIp(){
  let last=null;
  for(const item of IP_PROBES){
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),8000);
    try{
      const response=await fetch(item.url+(item.url.includes("?")?"&":"?")+"_="+Date.now(),{
        cache:"no-store",redirect:"error",signal:controller.signal
      });
      if(!response.ok) throw new Error("IP check HTTP "+response.status);
      const value=item.json?(await response.json()).ip:await response.text();
      const ip=publicIp(value);
      if(!ip) throw new Error("Invalid IP check response");
      return ip;
    }catch(e){last=e;}
    finally{clearTimeout(timer);}
  }
  throw new Error("IP verification unavailable: "+String(last&&last.message||"network error"));
}

async function clearPrivacyProtection(){
  try{await chrome.privacy.network.webRTCIPHandlingPolicy.clear({scope:"regular"});}catch(_){}
  try{await chrome.privacy.network.networkPredictionEnabled.clear({scope:"regular"});}catch(_){}
}
async function applyPrivacyProtection(){
  await chrome.privacy.network.webRTCIPHandlingPolicy.set({
    value:"disable_non_proxied_udp",scope:"regular"
  });
  await chrome.privacy.network.networkPredictionEnabled.set({
    value:false,scope:"regular"
  });
}
async function clearBrowserProxy(){
  await chrome.proxy.settings.clear({scope:"regular"});
  await clearPrivacyProtection();
  await chrome.storage.session.remove(["proxyAuth","proxyEndpoint"]);
  await chrome.storage.local.set({
    connected:false,activeLabel:"",proxyHost:"",proxyPort:0,
    exitIp:"",directIp:"",verifiedAt:0,connectionError:""
  });
}
async function effectiveProxy(expectedHost,expectedPort){
  const current=await chrome.proxy.settings.get({incognito:false});
  const proxy=current.value&&current.value.rules&&current.value.rules.singleProxy;
  return current.levelOfControl==="controlled_by_this_extension" &&
    current.value.mode==="fixed_servers" &&
    String(proxy&&proxy.scheme||"").toLowerCase()==="https" &&
    String(proxy&&proxy.host||"").toLowerCase()===String(expectedHost||"").toLowerCase() &&
    Number(proxy&&proxy.port||0)===Number(expectedPort);
}
async function disconnectWithError(message){
  try{await clearBrowserProxy();}catch(_){}
  await chrome.storage.local.set({connected:false,connectionError:String(message||"Proxy not verified")});
}
async function verifyBrowserProxy(){
  const s=await chrome.storage.local.get(CONNECTION_KEYS);
  if(!s.proxyHost||!s.proxyPort||!await effectiveProxy(s.proxyHost,s.proxyPort))
    throw new Error("Chrome/Edge did not apply the Makia proxy (another extension or policy may control it).");
  const exitIp=await fetchPublicIp();
  if(s.directIp&&exitIp===s.directIp)
    throw new Error("Public IP has not changed. Browser traffic is not verified through Makia.");
  await chrome.storage.local.set({
    connected:true,exitIp,verifiedAt:Date.now(),connectionError:""
  });
  return {exitIp,directIp:s.directIp||"",verifiedAt:Date.now()};
}
async function setBrowserProxy(proxy){
  if(!proxy||proxy.scheme!=="https")throw new Error("Makia requires an HTTPS Browser Gateway");
  const host=String(proxy.host||"").trim().toLowerCase();
  const port=Number(proxy.port||0);
  if(!/^[a-z0-9.-]+$/.test(host)||!Number.isInteger(port)||port<1||port>65535)
    throw new Error("Invalid Browser Gateway");
  if(chrome.extension&&chrome.extension.inIncognitoContext)
    throw new Error("The browser VPN must be activated in a regular browser window.");

  // Capture an optional direct baseline BEFORE changing the proxy.
  const directIp=await fetchPublicIp().catch(()=>"");
  await chrome.storage.session.set({
    proxyAuth:{username:String(proxy.username||""),password:String(proxy.password||"")},
    proxyEndpoint:{host,port}
  });
  await applyPrivacyProtection();
  await chrome.proxy.settings.set({
    value:{
      mode:"fixed_servers",
      rules:{singleProxy:{scheme:"https",host,port},
        bypassList:["<local>","127.0.0.1","localhost","::1"]}
    },
    scope:"regular"
  });
  await chrome.storage.local.set({
    connected:false,activeLabel:"Makia Browser VPN",
    proxyHost:host,proxyPort:port,directIp,exitIp:"",verifiedAt:0,connectionError:""
  });
  // Fail closed: never display "connected" until a real HTTPS request
  // succeeds through the installed proxy and an effective setting is observed.
  return verifyBrowserProxy();
}

chrome.webRequest.onAuthRequired.addListener(
  (details,callback)=>{
    if(!details.isProxy){callback({});return;}
    chrome.storage.session.get(["proxyAuth","proxyEndpoint"]).then(saved=>{
      const auth=saved.proxyAuth||{},endpoint=saved.proxyEndpoint||{};
      const challenger=details.challenger||{};
      const challengerHost=String(challenger.host||"").toLowerCase();
      const challengerPort=Number(challenger.port||0);
      const expectedHost=String(endpoint.host||"").toLowerCase();
      const expectedPort=Number(endpoint.port||0);
      if(!auth.username||!auth.password||!expectedHost||!expectedPort||
        challengerHost!==expectedHost||challengerPort!==expectedPort){
        callback({cancel:true});return;
      }
      callback({authCredentials:{username:auth.username,password:auth.password}});
    }).catch(()=>callback({cancel:true}));
  },
  {urls:["<all_urls>"]},["asyncBlocking"]
);

chrome.proxy.onProxyError.addListener(async details=>{
  const saved=await chrome.storage.local.get(["connected"]);
  if(saved.connected){
    await chrome.storage.local.set({
      connected:false,
      connectionError:"Browser proxy error: "+String(details.error||"Gateway unavailable")
    });
  }
});
chrome.runtime.onInstalled.addListener(()=>clearBrowserProxy().catch(()=>{}));
chrome.runtime.onStartup.addListener(()=>clearBrowserProxy().catch(()=>{}));

chrome.runtime.onMessage.addListener((message,sender,sendResponse)=>{
  (async()=>{
    if(message&&message.action==="connect"){
      await clearBrowserProxy();
      try{
        const verified=await setBrowserProxy(message.proxy);
        return {ok:true,result:verified};
      }catch(e){
        await disconnectWithError(e.message);
        throw e;
      }
    }
    if(message&&message.action==="disconnect"){
      await clearBrowserProxy();
      return {ok:true};
    }
    if(message&&message.action==="verify"){
      try{
        const verified=await verifyBrowserProxy();
        return {ok:true,result:verified};
      }catch(e){
        await disconnectWithError(e.message);
        throw e;
      }
    }
    if(message&&message.action==="status"){
      const s=await chrome.storage.local.get(CONNECTION_KEYS);
      if(s.connected&&!await effectiveProxy(s.proxyHost,s.proxyPort)){
        await chrome.storage.local.set({
          connected:false,connectionError:"Browser proxy is no longer controlled by Makia."
        });
        s.connected=false;
        s.connectionError="Browser proxy is no longer controlled by Makia.";
      }
      return {ok:true,result:s};
    }
    throw new Error("Unknown extension action");
  })().then(sendResponse).catch(e=>sendResponse({ok:false,error:String(e.message||e)}));
  return true;
});
