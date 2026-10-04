const $ = id => document.getElementById(id);
const EXT_HEADER = {"X-Makia-Extension": "1"};
let state = {controller:"", token:"", deviceKey:"", account:null, profiles:[]};

function normalizeController(value){
  const u = new URL(String(value || "").trim());
  if (u.protocol !== "https:") throw new Error("آدرس پنل باید HTTPS باشد.");
  if (u.username || u.password || u.search || u.hash) throw new Error("آدرس پنل معتبر نیست.");
  return u.origin;
}
function api(path, options={}){
  const headers = Object.assign({}, EXT_HEADER, options.headers || {});
  if (state.token) headers.Authorization = "Bearer " + state.token;
  if (options.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  return fetch(state.controller + path, Object.assign({}, options, {headers})).then(async r => {
    let data = {};
    try { data = await r.json(); } catch (_) {}
    if (!r.ok) throw new Error(data.detail || data.error || ("HTTP " + r.status));
    return data;
  });
}
async function ensureOriginPermission(origin){
  const pattern = origin + "/*";
  const has = await chrome.permissions.contains({origins:[pattern]});
  if (has) return true;
  return chrome.permissions.request({origins:[pattern]});
}
async function loadStorage(){
  const saved = await chrome.storage.local.get(["controller","token","deviceKey","account"]);
  state = Object.assign(state, saved);
}
async function saveAuth(){
  await chrome.storage.local.set({controller:state.controller, token:state.token, deviceKey:state.deviceKey, account:state.account});
}
function setError(id,msg){ $(id).textContent = msg || ""; }
function bytes(n){
  n = Number(n || 0);
  if (!n) return "0 B";
  const u = ["B","KB","MB","GB","TB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return (i ? n.toFixed(n >= 10 ? 1 : 2) : Math.round(n)) + " " + u[i];
}
function browserSupported(item){
  const engine = String(item.engine || "").toLowerCase();
  return !["wireguard","openvpn"].includes(engine) && item.available !== false;
}
function render(){
  const logged = !!state.token;
  $("setupView").classList.toggle("hidden", logged);
  $("appView").classList.toggle("hidden", !logged);
  if (!logged) return;
  chrome.storage.local.get(["connected","activeLabel"]).then(s => {
    $("statusDot").className = "dot " + (s.connected ? "on" : "off");
    $("connectionState").textContent = s.connected ? "متصل" : "قطع";
    $("activeLabel").textContent = s.connected ? (s.activeLabel || "Makia VPN") : "Browser VPN";
    $("disconnectBtn").classList.toggle("hidden", !s.connected);
  });
  const a = state.account || {};
  const quota = Number(a.quota_bytes || 0);
  const used = Number(a.used_bytes || 0);
  $("accountMeta").textContent = (a.display_name || a.username || "Makia") + (quota ? " · " + bytes(used) + " / " + bytes(quota) : "");
  $("profiles").innerHTML = "";
  if (!state.profiles.length) {
    $("profiles").innerHTML = '<div class="profile"><div><strong>دسترسی فعالی وجود ندارد</strong><small>از مدیر سرویس بخواهید یک پروفایل به حساب شما متصل کند.</small></div></div>';
    return;
  }
  for (const item of state.profiles) {
    const row = document.createElement("div"); row.className = "profile";
    const info = document.createElement("div");
    const title = document.createElement("strong"); title.textContent = item.label || item.name || item.protocol || "Makia";
    const sub = document.createElement("small"); sub.textContent = [item.protocol,item.engine].filter(Boolean).join(" · ");
    const badge = document.createElement("span"); badge.className = "badge";
    const supported = browserSupported(item);
    badge.textContent = supported ? "Browser VPN" : "فقط Full Device / Import";
    info.append(title,sub,badge);
    const btn = document.createElement("button"); btn.textContent = "اتصال"; btn.disabled = !supported;
    btn.addEventListener("click", () => connectItem(item,btn));
    row.append(info,btn); $("profiles").append(row);
  }
}
async function refresh(){
  setError("appError","");
  try {
    state.account = await api("/client/extension/me");
    const p = await api("/client/extension/protocols");
    state.profiles = p.items || [];
    await chrome.storage.local.set({account:state.account});
    render();
  } catch (e) {
    if (/401|authentication|session/i.test(String(e.message || e))) await logout(false);
    setError("appError",e.message);
  }
}
async function login(){
  setError("setupError","");
  $("loginBtn").disabled = true;
  try {
    const origin = normalizeController($("controller").value);
    if (!await ensureOriginPermission(origin)) throw new Error("اجازه دسترسی افزونه به پنل داده نشد.");
    state.controller = origin;
    const data = await api("/client/extension/login",{
      method:"POST",
      body:JSON.stringify({
        username:$("username").value,
        password:$("password").value,
        device_key:state.deviceKey || "",
        device_label:"Chrome / Edge · Makia Browser VPN"
      })
    });
    state.token = data.token;
    state.deviceKey = data.device_key || state.deviceKey || "";
    state.account = data.account;
    $("password").value = "";
    await saveAuth();
    await refresh();
    render();
  } catch (e) { setError("setupError",e.message); }
  finally { $("loginBtn").disabled = false; }
}
async function connectItem(item,btn){
  setError("appError","");
  btn.disabled = true; btn.textContent = "...";
  try {
    const t = await api("/client/extension/connect/" + encodeURIComponent(item.delivery_kind) + "/" + Number(item.delivery_id) + "/ticket",{method:"POST"});
    const response = await chrome.runtime.sendMessage({action:"connect",controller:t.controller,ticket:t.ticket,label:item.label || item.name || item.protocol || "Makia"});
    if (!response || !response.ok) throw new Error((response && response.error) || "اتصال ناموفق بود");
    render();
  } catch (e) { setError("appError",e.message); }
  finally { btn.disabled = !browserSupported(item); btn.textContent = "اتصال"; }
}
async function disconnect(){
  setError("appError","");
  const r = await chrome.runtime.sendMessage({action:"disconnect"});
  if (!r || !r.ok) setError("appError",(r && r.error) || "قطع اتصال ناموفق بود");
  render();
}
async function logout(callServer=true){
  try { if (callServer && state.token) await api("/client/extension/logout",{method:"POST"}); } catch (_) {}
  try { await chrome.runtime.sendMessage({action:"disconnect"}); } catch (_) {}
  const keep = {controller:state.controller, deviceKey:state.deviceKey};
  await chrome.storage.local.clear();
  await chrome.storage.local.set(keep);
  state = {controller:keep.controller, deviceKey:keep.deviceKey, token:"", account:null, profiles:[]};
  $("controller").value = keep.controller || "";
  render();
}
$("loginBtn").addEventListener("click",login);
$("refreshBtn").addEventListener("click",refresh);
$("disconnectBtn").addEventListener("click",disconnect);
$("logoutBtn").addEventListener("click",() => logout(true));
(async () => {
  await loadStorage();
  $("controller").value = state.controller || "";
  if (state.token) await refresh();
  render();
})();
