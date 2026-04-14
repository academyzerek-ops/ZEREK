const CACHE_NAME = 'zerek-v4-threads-dark';

self.addEventListener('install', function(e) {
  self.skipWaiting();
});

self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE_NAME; })
            .map(function(k) { return caches.delete(k); })
      );
    }).then(function() { return clients.claim(); })
  );
});

self.addEventListener('fetch', function(e) {
  /* Network-first for HTML, network-only for API to avoid stale data */
  var req = e.request;
  var url = new URL(req.url);
  if (req.method !== 'GET') return;
  if (url.hostname.indexOf('railway.app') !== -1) return; /* don't intercept API */

  e.respondWith(
    fetch(req).then(function(resp) {
      /* Cache GET responses for offline fallback */
      if (resp && resp.ok) {
        var copy = resp.clone();
        caches.open(CACHE_NAME).then(function(c) { c.put(req, copy); });
      }
      return resp;
    }).catch(function() {
      return caches.match(req);
    })
  );
});
