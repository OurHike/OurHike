// Making sure a running app picks up a new version.
//
// This app previously shipped `registerType: 'prompt'` with nothing to supply
// the prompt, so a new build installed, moved to `waiting`, and stayed there
// while the old bundle kept being served. Every deploy looked like it had not
// happened, and the only way out was clearing site data through Chrome's
// settings - which is not a thing to ask of someone who just wants a map.
//
// vite.config.ts now uses `autoUpdate`, so the new worker skips waiting and
// claims open pages. This handles the half that plugin cannot: noticing a new
// version while the app is already open, and reloading once the new worker is
// actually in charge.
//
// Safe to reload under someone because the app shell is the only thing the
// service worker holds. The downloaded map, the POIs, the outbox and the
// preferences all live in IndexedDB (map/pmtilesSource.ts, lib/trailData.ts,
// lib/outbox.ts), which a worker swap does not touch. Nobody loses their map
// to an update.
//
// Written against the standard ServiceWorker API rather than
// vite-plugin-pwa's `virtual:pwa-register`: that module only exists when the
// plugin runs, and the plugin is skipped under Vitest (see vite.config.ts), so
// importing it - even dynamically - breaks the whole test suite at
// transform time.

import { useEffect } from 'react'

/** Long enough to be invisible, short enough that a phone left open overnight
 *  wakes up on the current build. */
export const UPDATE_CHECK_MS = 60 * 60 * 1000

export function useAppUpdate(intervalMs: number = UPDATE_CHECK_MS): void {
  useEffect(() => {
    if (!('serviceWorker' in navigator)) return

    // Whether this page is already under a worker's control decides what a
    // controller change means. On a first-ever visit the worker claims an
    // uncontrolled page, which is not an update and must not reload - that
    // would bounce every new visitor once for nothing.
    const wasControlled = navigator.serviceWorker.controller !== null
    let reloading = false

    const onControllerChange = () => {
      if (!wasControlled || reloading) return
      reloading = true
      window.location.reload()
    }

    navigator.serviceWorker.addEventListener('controllerchange', onControllerChange)

    // A PWA can stay open for days. Without an explicit check the browser only
    // looks for a new worker on navigation, which a standalone app may not do
    // for a very long time.
    const check = () => {
      void navigator.serviceWorker.getRegistration().then((registration) => {
        void registration?.update()
      })
    }

    check()
    const timer = setInterval(check, intervalMs)

    return () => {
      clearInterval(timer)
      navigator.serviceWorker.removeEventListener('controllerchange', onControllerChange)
    }
  }, [intervalMs])
}
