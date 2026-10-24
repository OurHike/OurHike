// Served as /sw.js on UA and nowhere else (#1887 - UA serves the app alone,
// so a change to ourhike.org cannot be checked anywhere between its PR
// preview and production). ua.yml copies it to the root of the upload.
//
// WHY IT EXISTS. Until #1887 UA served the app at its root, and the app
// registers its service worker at its own base: /sw.js, scope /
// (client/vite.config.ts, VitePWA). UA now serves the marketing site at the
// root and the app at /app/, as production does, so the old registration's
// script would 404 - and a registration whose update fails is kept, not
// removed. That worker would go on answering / and /app/ with the old app's
// cached shell for as long as the phone keeps it, and the new app at /app/
// would never load to register its own. This is the script the old
// registration finds at /sw.js instead: the browser installs it as an
// update, and it removes itself.
//
// WHAT IT TOUCHES: its own registration, and the precache workbox keeps under
// the root scope's name, `workbox-precache-v2-<origin>/`. The app at /app/
// registers /app/sw.js with scope /app/ and a precache of its own whose name
// ends in `/app/`, which the filter below does not match. IndexedDB - the
// downloaded map, POIs, outbox and preferences - is not touched here, nor by
// any worker swap (client/vite.config.ts's registerType note says why).
//
// WHAT IT DOES NOT DO: register anywhere. Nothing on the site calls
// navigator.serviceWorker.register, so a browser that never ran UA's old root
// app never fetches this file. Proven against real builds in a browser on
// 2026-10-24 - a root-app install, then this layout - as #1887's pull request
// records; not yet seen on a tester's own phone.
self.addEventListener('install', () => self.skipWaiting())

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const scope = self.registration.scope
      const names = await caches.keys()
      await Promise.all(
        names
          .filter((name) => name.startsWith('workbox-precache') && name.endsWith(`-${scope}`))
          .map((name) => caches.delete(name)),
      )
      await self.registration.unregister()
      // Reload whatever the old worker was answering, so it is fetched from
      // the network: the site at /, the new app at /app/.
      const windows = await self.clients.matchAll({ type: 'window' })
      await Promise.all(windows.map((client) => client.navigate(client.url)))
    })(),
  )
})
