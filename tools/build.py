"""Build the site in docs/ from src/. Run from the repository root:  python tools/build.py"""
import hashlib, json, os
from PIL import Image, ImageDraw, ImageFont

OUT = "docs"
page = open("src/form.html", encoding="utf-8").read()
checklist = json.load(open("src/checklist.json", encoding="utf-8"))
parts = json.load(open("src/workbook-template.json", encoding="utf-8"))

def emb(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/").replace("<!--", "\\u003c!--")
def inline(path):
    return "<script>\n" + open(path, encoding="utf-8").read().replace("</script", "<\\/script") + "\n</script>"

page = page.replace("/*CHECKLIST*/", emb(checklist)).replace("/*PARTS*/", emb(parts))
for tag, lib in (('<script src="https://cdn.jsdelivr.net/npm/fflate@0.8.2/umd/index.js"></script>', "vendor/fflate-0.8.2.js"),
                 ('<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>', "vendor/jspdf-2.5.1.umd.min.js")):
    assert page.count(tag) == 1, tag
    page = page.replace(tag, inline(lib))
head = '''<meta name="robots" content="noindex, nofollow">
<meta name="theme-color" content="#15202b">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icon-192.png">
<link rel="apple-touch-icon" href="icon-192.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
'''
at = page.find("<title>")
page = page[:at] + head + page[at:]
sw = '''<script>
if ("serviceWorker" in navigator && /^https:|^http:\\/\\/(localhost|127\\.)/.test(location.href)) {
  window.addEventListener("load", function () { navigator.serviceWorker.register("sw.js").catch(function () {}); });
}
</script>
</body>'''
at = page.rfind("</body>")
assert at > 0
page = page[:at] + sw + page[at + len("</body>"):]

os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(page)
open(os.path.join(OUT, "manifest.webmanifest"), "w").write(json.dumps({
    "name": "Site Lead Installation Check", "short_name": "SLIC", "start_url": "./", "scope": "./", "display": "standalone",
    "background_color": "#edf0f3", "theme_color": "#15202b",
    "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}]}, indent=1))
ver = hashlib.sha1(page.encode("utf-8")).hexdigest()[:10]
open(os.path.join(OUT, "sw.js"), "w").write('''// Keeps the form working with no signal. The version changes whenever the page does.
const CACHE = "slic-%s";
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
''' % ver)
from PIL import Image, ImageDraw, ImageFont
for size in (192, 512):
    im = Image.new("RGB", (size, size), (21, 32, 43)); d = ImageDraw.Draw(im)
    try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(size * 0.27))
    except Exception: font = ImageFont.load_default()
    box = d.textbbox((0, 0), "SLIC", font=font); w, h = box[2] - box[0], box[3] - box[1]
    d.text(((size - w) / 2 - box[0], (size - h) / 2 - box[1] - size * 0.04), "SLIC", fill=(255, 255, 255), font=font)
    d.rectangle([size * 0.22, size * 0.68, size * 0.78, size * 0.72], fill=(116, 172, 255))
    im.save(os.path.join(OUT, "icon-%d.png" % size))
print("built", OUT, len(page), "bytes")
