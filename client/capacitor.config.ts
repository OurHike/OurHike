import type { CapacitorConfig } from '@capacitor/cli'

// The native shells around the PWA (#101 — Wrap the PWA with Capacitor).
//
// The posture, stated once: everything stays on the web APIs the app already
// uses. Geolocation is navigator.geolocation.watchPosition
// (lib/useGeolocation.ts, and MapLibre's GeolocateControl runs a second one
// internally that no plugin swap could reach); the offline archive is
// IndexedDB end-to-end via idb-keyval (lib/archiveStore.ts,
// map/pmtilesSource.ts — nothing in src/ touches Cache Storage). Both work
// inside WKWebView and Android WebView, so a Capacitor plugin would be a
// second implementation of a thing that already works, not a wrapper detail.
// The issue flags web-APIs-vs-plugins as the decision worth making early;
// this config is that decision being made, and the shells are built to
// keep it true.
//
// What the WebViews serve from, because two behaviours hang off it:
//   iOS     capacitor://localhost — `'serviceWorker' in navigator` is false
//           there, so the vite-plugin-pwa registration script (guarded, see
//           dist/registerSW.js) and lib/useAppUpdate.ts are both no-ops by
//           construction. Nothing to disable: the app shell ships in the
//           binary, which is what the precache existed to guarantee.
//   Android https://localhost — service workers exist there, so registration
//           is attempted and the precache is redundant-but-harmless (a few MB
//           beside a 1.18 GB archive). Whether it fully works in the shell is
//           untested until #103 has a device; either way assets are local.
const config: CapacitorConfig = {
  // Reverse-DNS of ourhike.org — the domain this project actually registered
  // (site/CNAME; LAUNCH_CHECKLIST.md records that the ourhike.app name #566
  // assumed was NOT the one bought). @unvalidated as a naming decision: no
  // maintainer has confirmed it, and it becomes near-irreversible the moment
  // a TestFlight or Play listing exists (#102, #103) — confirm it before
  // either. Until then it costs nothing to change.
  appId: 'org.ourhike.app',
  // Matches the PWA manifest's name/short_name in vite.config.ts.
  appName: 'OurHike',
  // `vite build` output. The shells need the default base path: pages.yml
  // deploys the web app under /app/ via VITE_BASE_PATH, and a dist built
  // that way references /app/assets/... which no WebView serves — so the
  // build that gets synced here is a plain `npm run build`, never the
  // pages.yml one. client/README.md § Native shells has the full command.
  webDir: 'dist',
  // Behind the WebView until first paint, and behind any overscroll after
  // it. --paper-100, the app's own page surface (design-system
  // tokens/colors.css) — the dark theme gets paper for a frame instead of
  // its own ink, which is the cheaper half of a static value; white would
  // be wrong in both.
  backgroundColor: '#f7f3e9',
}

export default config
