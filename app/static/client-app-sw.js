const CACHE='makia-client-phase-a-v1';
const SHELL=[
  '/client-app/login',
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
  if(url.pathname.startsWith('/client-app/api/')||url.pathname==='/client-app/'||url.pathname.startsWith('/client-app/logout')){
    event.respondWith(fetch(req));
    return;
  }
  event.respondWith(
    fetch(req).then(response=>{
      if(response && response.ok && (url.pathname.startsWith('/static/client-app')||url.pathname==='/client-app/login')){
        const copy=response.clone();
        caches.open(CACHE).then(cache=>cache.put(req,copy)).catch(()=>{});
      }
      return response;
    }).catch(()=>caches.match(req).then(hit=>hit||caches.match('/client-app/login')))
  );
});