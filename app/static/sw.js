const CACHE='makia-shell-v0170';
const CORE=['/static/makia.svg','/static/manifest.webmanifest'];

self.addEventListener('install',event=>{
  event.waitUntil(
    caches.open(CACHE)
      .then(cache=>cache.addAll(CORE))
      .then(()=>self.skipWaiting())
  );
});

self.addEventListener('activate',event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k))))
      .then(()=>self.clients.claim())
  );
});

self.addEventListener('fetch',event=>{
  const req=event.request;
  const url=new URL(req.url);
  if(req.method!=='GET'||url.origin!==self.location.origin)return;
  if(url.pathname.startsWith('/api/')||url.pathname.startsWith('/sub/')||url.pathname.startsWith('/client/')||url.pathname==='/')return;

  if(url.pathname==='/static/app.js'||url.pathname==='/static/app.css'||url.pathname==='/static/manifest.webmanifest'){
    event.respondWith(
      fetch(req,{cache:'no-store'}).then(res=>{
        if(res.ok){
          const copy=res.clone();
          caches.open(CACHE).then(cache=>cache.put(req,copy));
        }
        return res;
      }).catch(()=>caches.match(req))
    );
    return;
  }

  if(url.pathname.startsWith('/static/')){
    event.respondWith(
      caches.match(req).then(hit=>hit||fetch(req).then(res=>{
        if(res.ok){
          const copy=res.clone();
          caches.open(CACHE).then(cache=>cache.put(req,copy));
        }
        return res;
      }))
    );
  }
});
