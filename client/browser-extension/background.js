const EXT_HEADER = {"X-Makia-Extension": "1"};
const REFRESH_ALARM = "makia-browser-gateway-refresh";

async function getAuthState() {
  return chrome.storage.local.get(["controller","token","connected","gatewayHost","gatewayPort","credentialExpiresAt"]);
}

async function api(path, options={}) {
  const state = await getAuthState();
  if (!state.controller || !state.token) throw new Error("Makia login required");
  const headers = Object.assign({}, EXT_HEADER, options.headers || {}, {
    Authorization: "Bearer " + state.token
  });
  if (options.body && !headers["Content-Type"]) headers["Content-Type"]="application/json";
  const response = await fetch(state.controller + path, Object.assign({}, options, {headers}));
  let data = {};
  try { data = await response.json(); } catch (_) {}
  if (!response.ok) throw new Error(data.detail || data.error || ("HTTP " + response.status));
  return data;
}

async function clearProxyState(force=false) {
  const ownedState = await chrome.storage.local.get(["makiaProxyOwned"]);
  if (force || ownedState.makiaProxyOwned) {
    try { await chrome.proxy.settings.clear({scope:"regular"}); } catch (_) {}
  }
  try { await chrome.storage.session.remove(["proxyUsername","proxyPassword"]); } catch (_) {}
  await chrome.storage.local.set({
    connected:false,
    makiaProxyOwned:false,
    gatewayHost:"",
    gatewayPort:0,
    credentialExpiresAt:0,
    proxyError:""
  });
  try { await chrome.alarms.clear(REFRESH_ALARM); } catch (_) {}
}

async function setSecureProxy(gateway) {
  if (!gateway || gateway.scheme !== "https" || !gateway.host || !gateway.port) {
    throw new Error("Invalid Makia Browser Gateway configuration");
  }
  const current = await chrome.proxy.settings.get({incognito:false});
  if (["not_controllable","controlled_by_other_extensions"].includes(String(current.levelOfControl || ""))) {
    throw new Error("Chrome proxy settings are controlled by another policy or extension");
  }
  await chrome.proxy.settings.set({
    value:{
      mode:"fixed_servers",
      rules:{
        singleProxy:{
          scheme:"https",
          host:String(gateway.host),
          port:Number(gateway.port)
        },
        bypassList:[
          "<local>",
          "localhost",
          "127.0.0.0/8",
          "[::1]",
          "10.0.0.0/8",
          "172.16.0.0/12",
          "192.168.0.0/16"
        ]
      }
    },
    scope:"regular"
  });
  await chrome.storage.local.set({makiaProxyOwned:true});
}

async function issueGatewaySession() {
  const data = await api("/client/extension/browser-session",{method:"POST"});
  if (!data.gateway || !data.gateway.available) {
    throw new Error((data.gateway && data.gateway.reason) || "Makia Browser Gateway is unavailable");
  }
  if (!data.proxy || !data.proxy.username || !data.proxy.password) {
    throw new Error("Makia proxy credentials were not returned");
  }
  await chrome.storage.session.set({
    proxyUsername:String(data.proxy.username),
    proxyPassword:String(data.proxy.password)
  });
  await chrome.storage.local.set({
    connected:true,
    gatewayHost:String(data.gateway.host),
    gatewayPort:Number(data.gateway.port),
    credentialExpiresAt:Number(data.proxy.expires_at || 0),
    proxyError:""
  });
  try {
    await setSecureProxy(data.gateway);
  } catch (err) {
    await chrome.storage.session.remove(["proxyUsername","proxyPassword"]);
    await chrome.storage.local.set({
      connected:false,
      gatewayHost:"",
      gatewayPort:0,
      credentialExpiresAt:0
    });
    throw err;
  }
  await chrome.alarms.create(REFRESH_ALARM,{periodInMinutes:10});
  return data;
}

async function disconnect(callServer=true) {
  if (callServer) {
    try { await api("/client/extension/browser-disconnect",{method:"POST"}); } catch (_) {}
  }
  await clearProxyState();
}

async function ensureCredentialsFresh() {
  const state = await getAuthState();
  if (!state.connected) throw new Error("Makia Browser VPN is disconnected");
  const creds = await chrome.storage.session.get(["proxyUsername","proxyPassword"]);
  const now = Math.floor(Date.now()/1000);
  if (creds.proxyUsername && creds.proxyPassword && Number(state.credentialExpiresAt || 0) > now + 60) {
    return creds;
  }
  await issueGatewaySession();
  return chrome.storage.session.get(["proxyUsername","proxyPassword"]);
}

chrome.webRequest.onAuthRequired.addListener(
  (details, callback) => {
    (async () => {
      if (!details.isProxy) return {};
      const state = await getAuthState();
      const challenger = details.challenger || {};
      if (!state.connected) return {};
      if (String(challenger.host || "").toLowerCase() !== String(state.gatewayHost || "").toLowerCase()) return {};
      if (Number(challenger.port || 0) !== Number(state.gatewayPort || 0)) return {};
      const creds = await ensureCredentialsFresh();
      if (!creds.proxyUsername || !creds.proxyPassword) return {cancel:true};
      return {
        authCredentials:{
          username:String(creds.proxyUsername),
          password:String(creds.proxyPassword)
        }
      };
    })().then(callback).catch(async err => {
      await chrome.storage.local.set({proxyError:String(err.message || err)});
      callback({cancel:true});
    });
  },
  {urls:["<all_urls>"]},
  ["asyncBlocking"]
);

chrome.proxy.onProxyError.addListener(details => {
  chrome.storage.local.set({proxyError:String((details && details.error) || "Proxy connection failed")}).catch(()=>{});
});

chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm && alarm.name === REFRESH_ALARM) {
    issueGatewaySession().catch(async err => {
      await chrome.storage.local.set({proxyError:String(err.message || err)});
      await clearProxyState();
    });
  }
});

chrome.runtime.onInstalled.addListener(details => {
  const upgrading = details && details.reason === "update";
  clearProxyState(upgrading).catch(()=>{});
});

chrome.runtime.onStartup.addListener(() => {
  (async () => {
    const state = await getAuthState();
    if (state.connected && state.controller && state.token) {
      try { await issueGatewaySession(); }
      catch (err) {
        await clearProxyState();
        await chrome.storage.local.set({proxyError:String(err.message || err)});
      }
    } else {
      await clearProxyState();
    }
  })().catch(()=>{});
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    if (!message || !message.action) throw new Error("Unknown extension action");
    if (message.action === "connect") {
      const data = await issueGatewaySession();
      return {ok:true,gateway:data.gateway,expires_at:data.proxy.expires_at};
    }
    if (message.action === "disconnect") {
      await disconnect(true);
      return {ok:true};
    }
    if (message.action === "status") {
      const state = await getAuthState();
      return {ok:true,state};
    }
    throw new Error("Unknown extension action");
  })().then(sendResponse).catch(err => sendResponse({ok:false,error:String(err.message || err)}));
  return true;
});
