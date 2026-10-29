// Served as /sw.js on UA and nowhere else, since #1887 moved UA's app from the
// root to /app/. ua.yml copies it to the root of the upload.
//
// WHY IT EXISTS. Before #1887 UA served the app at its root, and the app
// registers its service worker at its own base: /sw.js, scope /
// (client/vite.config.ts, VitePWA). With the site at the root that script
// would 404 - and a registration whose update fails is kept, not removed. The
// old worker would go on answering / and /app/ with the old app's cached
// shell, and the new app would never load to register its own. This is the
// script the old registration finds at /sw.js instead: the browser installs
// it as an update, in place of the old worker, on a tester's next visit.
//
// WHAT IT DOES, as a door to /app/ that stays:
//
//   - Until the new app is installed on this device (no /app/ precache yet),
//     a navigation to any old app address goes to the same address under
//     /app/. The old icon's start_url is `/`, so its next launch with signal
//     installs the new app - which is what keeps that icon working offline
//     afterwards. A tester who needs the site at / reaches it from then on.
//   - After that, a navigation is the network's, so / is the site; and when
//     there is no network, it goes to /app/, which the new app's own worker
//     answers. An old icon therefore opens the map offline, as it did.
//   - A window of the old app still on screen keeps working: its requests are
//     answered from the precache the old worker left, which is dropped once
//     the new app is installed. Nothing is reloaded under anyone - a report
//     half typed in the old app stays where it is (#311's rule, in
//     client/src/lib/useAppUpdate.ts, is the same one).
//
// It never unregisters, because the old icon has nothing else to open it
// offline. It touches no cache but `workbox-precache-v2-<origin>/`, and
// IndexedDB - the downloaded map - not at all.
//
// WHAT IT DOES NOT DO: register anywhere. Nothing on the site calls
// navigator.serviceWorker.register, so a browser that never ran UA's old root
// app never fetches this file. Proven against real builds in Chromium on
// 2026-10-24, online and offline, as #1887's pull request records; not yet
// seen on a tester's own phone or in WebKit.
const scope = self.registration.scope
const ROOT_PRECACHE = `-${scope}`
const APP_PRECACHE = `-${scope}app/`

const precaches = async () => (await caches.keys()).filter((name) => name.startsWith('workbox-precache'))

async function appInstalled() {
  return (await precaches()).some((name) => name.endsWith(APP_PRECACHE))
}

/** The same address under /app/: the old app's `/my/tread` is the new one's `/app/my/tread`. */
function underApp(url) {
  return new URL(`app${url.pathname}${url.search}${url.hash}`, scope).href
}

async function navigate(request) {
  const url = new URL(request.url)
  if (url.pathname.startsWith(new URL('app/', scope).pathname)) return fetch(request)
  if (!(await appInstalled())) return Response.redirect(underApp(url), 302)
  await Promise.all(
    (await precaches()).filter((name) => name.endsWith(ROOT_PRECACHE)).map((name) => caches.delete(name)),
  )
  try {
    return await fetch(request)
  } catch {
    return Response.redirect(underApp(url), 302)
  }
}

self.addEventListener('install', () => self.skipWaiting())

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.mode === 'navigate') {
    event.respondWith(navigate(request))
  } else {
    event.respondWith(caches.match(request).then((hit) => hit || fetch(request)))
  }
})
