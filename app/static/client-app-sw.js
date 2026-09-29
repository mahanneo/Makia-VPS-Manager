const CACHE='makia-client-phase-a-v2';
const SHELL=[
  '/static/client-app.css',
  '/static/client-app.js',
  '/static/client-app-icon.svg'
];

self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)).catch(()=>{}));
  self.skipWaiting();
});

self.addEventListener('activate',event=>{
  event.waitUntil(
    caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('makia-client-')&&key!==CACHE).map(key=>caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener('fetch',event=>{
  const req=event.request;
  const url=new URL(req.url);
  if(req.method!=='GET'||url.origin!==location.origin) return;

  // Authenticated pages and login are always network-only. The service worker
  // never caches account/session/API responses.
  if(url.pathname.startsWith('/client-app/')){
    event.respondWith(fetch(req));
    return;
  }

  if(url.pathname.startsWith('/static/client-app')){
    event.respondWith(
      caches.match(req).then(hit=>hit||fetch(req).then(response=>{
        if(response && response.ok){
          const copy=response.clone();
          caches.open(CACHE).then(cache=>cache.put(req,copy)).catch(()=>{});
        }
        return response;
      }))
    );
  }
});