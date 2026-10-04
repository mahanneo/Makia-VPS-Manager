const HOST = "com.makia.browser_host";

async function clearBrowserProxy() {
  await chrome.proxy.settings.clear({scope: "regular"});
  await chrome.storage.local.set({connected: false, activeLabel: "", proxyPort: 0});
}

async function setBrowserProxy(port) {
  await chrome.proxy.settings.set({
    value: {
      mode: "fixed_servers",
      rules: {
        singleProxy: {scheme: "socks5", host: "127.0.0.1", port: Number(port)},
        bypassList: ["<local>", "127.0.0.1", "localhost"]
      }
    },
    scope: "regular"
  });
}

function nativeMessage(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendNativeMessage(HOST, message, response => {
      const err = chrome.runtime.lastError;
      if (err) return reject(new Error(err.message || "Makia native host is unavailable"));
      if (!response || response.ok === false) return reject(new Error((response && response.error) || "Makia native host failed"));
      resolve(response);
    });
  });
}

async function resetBrowserTunnel() {
  await clearBrowserProxy();
  try { await nativeMessage({action: "disconnect", mode: "browser"}); } catch (_) {}
}

chrome.runtime.onInstalled.addListener(() => resetBrowserTunnel().catch(() => {}));
chrome.runtime.onStartup.addListener(() => resetBrowserTunnel().catch(() => {}));

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    if (message && message.action === "native-status") {
      return {ok: true, result: await nativeMessage({action: "status", mode: "browser"})};
    }
    if (message && message.action === "connect") {
      await clearBrowserProxy();
      const result = await nativeMessage({
        action: "connect",
        mode: "browser",
        controller: message.controller,
        ticket: message.ticket
      });
      if (!result.proxy_port) throw new Error("Makia browser proxy port was not returned");
      await setBrowserProxy(result.proxy_port);
      await chrome.storage.local.set({
        connected: true,
        activeLabel: String(message.label || ""),
        proxyPort: Number(result.proxy_port)
      });
      return {ok: true, result};
    }
    if (message && message.action === "disconnect") {
      await clearBrowserProxy();
      let result = {ok: true, stopped: false};
      try { result = await nativeMessage({action: "disconnect", mode: "browser"}); } catch (_) {}
      return {ok: true, result};
    }
    throw new Error("Unknown extension action");
  })().then(sendResponse).catch(err => sendResponse({ok: false, error: String(err.message || err)}));
  return true;
});
