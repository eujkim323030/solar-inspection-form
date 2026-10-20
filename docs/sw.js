// 한 번 열면 인터넷 없는 현장에서도 열리도록 캐시. 배포할 때마다 VERSION을 올린다.
const VERSION = 'suggeom-v11';
const BG = ['p04', 'p05', 'p06', 'p07', 'p08', 'p09', 'p10', 'p11', 'p12', 'p14', 'p15', 'p16', 'p17', 'p18', 'p19', 'p20'].map(p => `bg/${p}.png`);
const CORE = ['./', 'index.html', 'manifest.webmanifest', 'icon-180.png', 'icon-192.png', 'icon-512.png', 'fields.json', 'template.pdf', ...BG];
const CDN = ['https://cdnjs.cloudflare.com/ajax/libs/pdf-lib/1.17.1/pdf-lib.min.js'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSION)
    .then(c => c.addAll(CORE).then(() => Promise.all(CDN.map(u => c.add(new Request(u, { mode: 'no-cors' })).catch(() => {})))))
    .then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

// 캐시를 먼저 보여주고 뒤에서 새 버전으로 갱신 (글꼴·PDF 도구 CDN 포함)
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(caches.open(VERSION).then(async cache => {
    const hit = await cache.match(e.request, { ignoreSearch: e.request.mode === 'navigate' });
    const net = fetch(e.request).then(res => {
      if (res.ok || res.type === 'opaque') cache.put(e.request, res.clone());
      return res;
    }).catch(() => hit);
    return hit || net;
  }));
});
