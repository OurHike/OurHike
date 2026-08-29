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
  android: {
    /**
     * REQUIRED BY THE BACKGROUND-GEOLOCATION PLUGIN, and a real trade.
     *
     * Without it, `@capacitor-community/background-geolocation` stops
     * delivering location about five minutes after the app goes to the
     * background - its README says so, pointing at its own issue #89. Five
     * minutes is shorter than every walk #1182 exists to record, so the
     * plugin without this flag would fail in exactly the way that looks like
     * success on a short test.
     *
     * What it costs: the legacy bridge serves the WebView from
     * `http://localhost` rather than `https://localhost`. That is a
     * NON-SECURE origin, and the header above notes that Android is the shell
     * where service workers exist. `'serviceWorker' in navigator` is false on
     * a non-secure origin, so the Android shell now behaves like the iOS one -
     * the vite-plugin-pwa registration is a no-op and lib/useAppUpdate.ts with
     * it. Both were already guarded for iOS and both are already redundant in
     * a shell that ships its assets in the binary, which is why this is
     * acceptable rather than merely survivable.
     *
     * @unvalidated - no device build has been run since this was set. The
     * scheme change is read off Capacitor's documented behaviour for
     * `useLegacyBridge`, not observed here, and IndexedDB being keyed by
     * origin means an existing install's downloaded archive may not be
     * visible under the new scheme. What would settle it: install over a
     * previous build and see whether the trail data is still there.
     */
    useLegacyBridge: true,
  },
}

export default config
