async function clearBrowserProxy() {
  await chrome.proxy.settings.clear({scope: "regular"});
  await chrome.storage.session.remove(["proxyAuth","proxyEndpoint"]);
  await chrome.storage.local.set({connected:false,activeLabel:"",proxyHost:"",proxyPort:0});
}

async function setBrowserProxy(proxy) {
  if (!proxy || proxy.scheme !== "https") throw new Error("Makia requires an HTTPS Browser Gateway");
  const host=String(proxy.host || "").trim();
  const port=Number(proxy.port || 0);
  if (!host || !Number.isInteger(port) || port < 1 || port > 65535) throw new Error("Invalid Browser Gateway");
  await chrome.storage.session.set({
    proxyAuth:{username:String(proxy.username||""),password:String(proxy.password||"")},
    proxyEndpoint:{host,port}
  });
  await chrome.proxy.settings.set({
    value:{
      mode:"fixed_servers",
      rules:{
        singleProxy:{scheme:"https",host,port},
        bypassList:["<local>","127.0.0.1","localhost","::1"]
      }
    },
    scope:"regular"
  });
  await chrome.storage.local.set({
    connected:true,
    activeLabel:"Makia Browser VPN",
    proxyHost:host,
    proxyPort:port
  });
}

chrome.webRequest.onAuthRequired.addListener(
  (details, callback) => {
    if (!details.isProxy) {
      callback({});
      return;
    }
    chrome.storage.session.get(["proxyAuth","proxyEndpoint"]).then(saved => {
      const auth=saved.proxyAuth || {};
      const endpoint=saved.proxyEndpoint || {};
      const challenger=details.challenger || {};
      const challengerHost=String(challenger.host || "").toLowerCase();
      const challengerPort=Number(challenger.port || 0);
      const expectedHost=String(endpoint.host || "").toLowerCase();
      const expectedPort=Number(endpoint.port || 0);
      if (!auth.username || !auth.password || !expectedHost || !expectedPort ||
          challengerHost !== expectedHost || challengerPort !== expectedPort) {
        callback({cancel:true});
        return;
      }
      callback({authCredentials:{username:auth.username,password:auth.password}});
    }).catch(() => callback({cancel:true}));
  },
  {urls:["<all_urls>"]},
  ["asyncBlocking"]
);

chrome.runtime.onInstalled.addListener(() => clearBrowserProxy().catch(() => {}));
chrome.runtime.onStartup.addListener(() => clearBrowserProxy().catch(() => {}));

chrome.runtime.onMessage.addListener((message,sender,sendResponse) => {
  (async () => {
    if (message && message.action === "connect") {
      await clearBrowserProxy();
      await setBrowserProxy(message.proxy);
      return {ok:true,result:{host:message.proxy.host,port:Number(message.proxy.port)}};
    }
    if (message && message.action === "disconnect") {
      await clearBrowserProxy();
      return {ok:true};
    }
    if (message && message.action === "status") {
      const state=await chrome.storage.local.get(["connected","activeLabel","proxyHost","proxyPort"]);
      return {ok:true,result:state};
    }
    throw new Error("Unknown extension action");
  })().then(sendResponse).catch(err => sendResponse({ok:false,error:String(err.message||err)}));
  return true;
});
