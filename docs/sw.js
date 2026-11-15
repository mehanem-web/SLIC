// Keeps the form working with no signal. The version changes whenever the page does.
const CACHE = "slic-68725ddff8";
const SHELL = ["./", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== location.origin) return;
  e.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(req, { ignoreSearch: true });
    const fresh = fetch(req).then((res) => { if (res && res.ok) cache.put(req, res.clone()); return res; });
    if (!cached) return fresh;
    // With a saved copy on the tablet: use the network if it answers quickly, otherwise the saved copy.
    return Promise.race([fresh.catch(() => cached), new Promise((done) => setTimeout(() => done(cached), 2500))]);
  })());
});
