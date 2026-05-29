const CACHE = 'nagger-v3-secure';
const STATIC = [
  '/', 
  '/index.html', 
  '/app.html', 
  '/settings.html', 
  '/manifest.json'
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
    e.waitUntil(
      caches.keys().then(keys => {
        return Promise.all(
          keys.map(k => {
            if (k !== CACHE) return caches.delete(k);
          })
        );
      })
    );
    self.clients.claim();
});

self.addEventListener('fetch', e => {
  // Never cache API requests, always hit the secure network
  if (e.request.url.includes('/api/')) {
      return;
  }
  
  // Cache-first for static assets
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});
