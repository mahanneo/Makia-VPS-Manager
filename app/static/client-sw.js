const CACHE="makia-client-v161-wstunnel";
const SHELL=["/static/client.css","/static/client.js","/static/client-login.js","/static/client-icon.svg"];
self.addEventListener("install",event=>{event.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).catch(()=>{}));self.skipWaiting()});
self.addEventListener("activate",event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE&&k.startsWith("makia-client-")).map(k=>caches.delete(k)))));self.clients.claim()});
self.addEventListener("fetch",event=>{
  const u=new URL(event.request.url);
  if(event.request.method!=="GET"||u.origin!==self.location.origin)return;
  if(u.pathname.startsWith("/client/")){
    event.respondWith(fetch(event.request,{cache:"no-store"}));
    return;
  }
  if(SHELL.includes(u.pathname)){
    event.respondWith(caches.match(event.request).then(hit=>hit||fetch(event.request).then(r=>{const copy=r.clone();caches.open(CACHE).then(c=>c.put(event.request,copy));return r})));
  }
});
