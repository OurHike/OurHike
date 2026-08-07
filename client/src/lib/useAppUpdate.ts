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
// WHAT "SAFE TO RELOAD" MEANT, AND WHY IT WAS ONLY HALF TRUE (#311)
//
// This file used to say a reload was safe under someone because the app shell
// is the only thing the service worker holds - the downloaded map, the POIs,
// the outbox and the preferences all live in IndexedDB
// (map/pmtilesSource.ts, lib/trailData.ts, lib/outbox.ts), which a worker swap
// does not touch. That is true, and it is a claim about STORAGE. React state
// is not storage, and a reload takes all of it:
//
//   - the note someone is part way through typing into a report;
//   - an open POI card, an open legend, a search in progress;
//   - a download status that is session-only by design (DownloadCard.tsx).
//
// The concrete worst case is a hiker standing at a junction, reading the fork
// they have just panned to, when an hour-old deploy lands. Nothing they lose
// is recoverable and nothing warned them.
//
// So the reload now waits for a moment when it costs nothing: the page has to
// be HIDDEN, and the shell has to say nothing is at stake (`hold`). The next
// time the phone comes out of the pocket it is simply the new build, and
// nobody watched it happen. The camera is kept across it separately
// (lib/cameraMemory.ts), because a reload while hidden still forgets the view.
//
// The cost, stated plainly: a page that is never hidden and never idle never
// updates. On a phone that is a non-case - the screen locks - and on a desktop
// the new bundle is already cached and lands on the next navigation. Waiting
// is the cheaper failure than interrupting someone mid-decision.
//
// Written against the standard ServiceWorker API rather than
// vite-plugin-pwa's `virtual:pwa-register`: that module only exists when the
// plugin runs, and the plugin is skipped under Vitest (see vite.config.ts), so
// importing it - even dynamically - breaks the whole test suite at
// transform time.

import { useEffect, useRef } from 'react'

/** Long enough to be invisible, short enough that a phone left open overnight
 *  wakes up on the current build. */
export const UPDATE_CHECK_MS = 60 * 60 * 1000

export interface AppUpdateOptions {
  /**
   * Whether something on screen would be destroyed by a reload right now -
   * a half-written report, an open window (#311).
   *
   * A hold rather than a list of conditions, because what is at stake is the
   * shell's knowledge and this hook has no business enumerating screens. It
   * is read at the moment a reload is considered, not captured when the
   * listeners are attached, so putting a form away releases the hold without
   * re-registering anything.
   */
  hold?: boolean
}

export function useAppUpdate(
  intervalMs: number = UPDATE_CHECK_MS,
  { hold = false }: AppUpdateOptions = {},
): void {
  // Both live in refs so that a change in either re-evaluates the pending
  // reload WITHOUT re-running the effect below - which would re-read
  // `controller`, re-attach every listener and restart the hourly timer each
  // time a hiker opened a dialog.
  const holdRef = useRef(hold)
  holdRef.current = hold
  /** Set once a new worker has taken control and never cleared: the old
   *  bundle stays stale until the page actually reloads. */
  const pending = useRef(false)
  /** Re-checked on visibility changes and on every release of the hold. */
  const reloadIfIdle = useRef<() => void>(() => {})

  useEffect(() => {
    if (!('serviceWorker' in navigator)) return

    // Whether this page is already under a worker's control decides what a
    // controller change means. On a first-ever visit the worker claims an
    // uncontrolled page, which is not an update and must not reload - that
    // would bounce every new visitor once for nothing.
    const wasControlled = navigator.serviceWorker.controller !== null
    let reloading = false

    /**
     * Reload, but only into an empty room.
     *
     * Hidden AND nothing held. Both halves are needed and they catch
     * different things: hidden covers the hiker who is walking with the
     * screen off, the hold covers the one who is standing still with a report
     * half typed and the phone in their hand. A page that is hidden with a
     * draft open is still holding something worth keeping.
     */
    const reloadIfIdleNow = () => {
      if (!pending.current || reloading) return
      if (holdRef.current) return
      if (document.visibilityState !== 'hidden') return
      reloading = true
      window.location.reload()
    }
    reloadIfIdle.current = reloadIfIdleNow

    const onControllerChange = () => {
      // Not an update: on a first-ever visit the worker claims an
      // uncontrolled page, and reloading would bounce every new visitor once
      // for nothing.
      if (!wasControlled) return
      pending.current = true
      reloadIfIdleNow()
    }

    navigator.serviceWorker.addEventListener('controllerchange', onControllerChange)
    document.addEventListener('visibilitychange', reloadIfIdleNow)

    // A PWA can stay open for days. Without an explicit check the browser only
    // looks for a new worker on navigation, which a standalone app may not do
    // for a very long time.
    // Swallowing the rejection is the whole point, not laziness.
    // registration.update() re-fetches the worker script, so it rejects
    // whenever there is no signal - which for this app is not an edge case but
    // the normal condition for days at a time. Left unhandled it raised an
    // `unhandledrejection` every hour on exactly the hike this app is for,
    // which is noise in any error reporting we add later and, in a browser
    // that surfaces them, noise at the hiker. There is nothing to do about it
    // either way: the next tick tries again, and the running app is fine
    // meanwhile.
    //
    // And not attempted at all while the browser says there is no network.
    // The fetch was going to fail; what it costs anyway is a cold cellular
    // radio woken once an hour for the length of a hike, on the battery that
    // gets someone to the next town. `navigator.onLine` saying true proves
    // nothing (lib/useOnline.ts), but saying FALSE is definitive - that is
    // the reading this guard acts on, and the only one it can trust.
    const check = () => {
      if (!navigator.onLine) return
      void navigator.serviceWorker
        .getRegistration()
        .then((registration) => registration?.update())
        .catch(() => {})
    }

    check()
    const timer = setInterval(check, intervalMs)

    return () => {
      clearInterval(timer)
      navigator.serviceWorker.removeEventListener('controllerchange', onControllerChange)
      document.removeEventListener('visibilitychange', reloadIfIdleNow)
    }
  }, [intervalMs])

  // The hold being RELEASED is the other way a reload becomes possible, and it
  // fires no event of its own - submitting a report or closing a window is
  // just a render. Without this the update would sit until the next visibility
  // change, which on a phone left face-up on a table is never.
  useEffect(() => {
    if (!hold) reloadIfIdle.current()
  }, [hold])
}
