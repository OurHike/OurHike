// The app's service worker (vite.config.ts builds it with Workbox's
// generateSW), registered here rather than by vite-plugin-pwa's own script so
// that a new version waits until the person says to use it.
//
// Before the adversarial review's third pass (P4, 2026-10-27) a new version
// took over the moment it arrived. The open page had been started from the
// old version, so its next on-demand load (MapLibre when a map first draws,
// supabase-js when sign-in is first used) asked for a file the new version
// had just removed from the cache and the new deployment no longer serves: a
// blank map or a failed sign-in until a reload. That is reasoned from how
// Workbox swaps versions, not seen on a phone. Now the old version keeps
// serving the old files until the page reloads, which it offers.

/** Calls `onReady` with a way to switch to the new version once one is waiting. */
export function watchForUpdates(onReady: (apply: () => void) => void): void {
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return
  const workers = navigator.serviceWorker
  const offer = (worker: ServiceWorker) =>
    onReady(() => {
      workers.addEventListener('controllerchange', () => window.location.reload(), {
        once: true,
      })
      // Workbox's generated worker skips waiting when it is sent this.
      worker.postMessage({ type: 'SKIP_WAITING' })
    })
  const register = () =>
    workers.register('./sw.js', { scope: './' }).then(
      (registration) => {
        // A controller means this is an update, not the first install.
        if (registration.waiting && workers.controller) offer(registration.waiting)
        registration.addEventListener('updatefound', () => {
          const worker = registration.installing
          worker?.addEventListener('statechange', () => {
            if (worker.state === 'installed' && workers.controller) offer(worker)
          })
        })
      },
      () => {
        // No worker (a private window, an old browser): the app works online as before.
      },
    )
  if (document.readyState === 'complete') void register()
  else window.addEventListener('load', () => void register(), { once: true })
}
