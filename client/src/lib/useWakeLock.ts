// Holding the screen awake, for the one feature that needs it (#1180).
//
// WHY THIS EXISTS, AND WHAT IT DOES NOT FIX.
//
// `useGeolocation`'s `keepAwake` stops THIS APP ending a recording when the
// tab hides. It cannot stop the PLATFORM ending one: a phone that locks
// suspends the page, `watchPosition` stops firing, and no amount of
// application code changes that in a web app. Reported from a real walk - the
// recording stopped when the phone went to sleep - and the copy on that screen
// had promised otherwise, which is the failure this hook and that rewrite
// exist to repair together.
//
// The Screen Wake Lock API is the part a web app can actually do: it stops the
// screen going dark ON ITS OWN, so the page stays alive and the watch keeps
// firing. It does NOT survive somebody pressing the power button, and it is
// not a background-location permission. Recording through a genuinely locked
// phone needs the native path FEATURES.md already names (Capacitor's
// geolocation plugin), and until that exists the screen has to say so.
//
// THE STATE IS RETURNED RATHER THAN SWALLOWED. A browser can refuse the lock -
// no support, or a battery-saver policy - and a tester whose screen is going
// to sleep anyway needs to know that before the walk rather than after it.
// Reporting 'held' when nothing was held would be the same lie in a smaller
// font.
//
// AND IT IS WITHDRAWN WHEN THE PLATFORM WITHDRAWS IT.
//
// A `WakeLockSentinel` is not a permanent grant. The platform fires `release`
// on it and drops the lock - on a battery-saver threshold crossed mid-walk, on
// the page hiding, on its own policy - and the first version of this hook
// listened for none of that. It set 'held' once and never took it back, so the
// screen could go on saying "the screen is being kept awake" for the rest of a
// walk during which nothing was held.
//
// That is the same failure as the pocket sentence this hook was written to
// repair, one layer down, and the third field walk is why it is being fixed
// now: 136 fixes arrived at a metronomic 5.7 s and then stopped dead for 272
// seconds, 45 seconds after the last screen tap, while the hiker stood still
// on purpose to collect exactly that stretch. A clean cliff at a steady
// cadence is a page that stopped being run, not a GPS that stopped answering.
// Whether the lock was refused, released, or never asked for is the question
// the trace could not answer, and this state - recorded per sample by
// lib/gpsTrace.ts - is half of the answer.

import { useEffect, useState } from 'react'

export type WakeLockState =
  /** Not asked for - nothing is recording. */
  | 'off'
  /** Asked for and granted: the screen will not sleep on its own. */
  | 'held'
  /** This browser has no Screen Wake Lock API. The screen will sleep. */
  | 'unsupported'
  /** Asked for and refused - a battery-saver policy, usually. */
  | 'refused'
  /**
   * Held, and then taken back by the platform.
   *
   * A separate state from 'refused' because it says something different
   * happened, and from 'held' because the screen must stop promising. Every
   * consumer treats anything that is not 'held' as "this screen will sleep",
   * so a new member needs no branch anywhere to be handled safely.
   */
  | 'released'

export function useWakeLock(active: boolean): WakeLockState {
  const [state, setState] = useState<WakeLockState>('off')

  useEffect(() => {
    if (!active) {
      setState('off')
      return
    }
    if (typeof navigator === 'undefined' || !('wakeLock' in navigator)) {
      setState('unsupported')
      return
    }

    // `cancelled` rather than an abort signal because the thing being raced is
    // a sentinel that may arrive AFTER the recording stopped - and one that
    // arrives to nobody would hold the screen on for the life of the tab.
    let cancelled = false
    let sentinel: WakeLockSentinel | null = null
    // WHY A TICKET AND NOT JUST `cancelled`. `acquire` runs on mount and again
    // from `reacquire` on every visibilitychange, so a hidden -> visible ->
    // hidden -> visible flap inside the time one `request` takes to resolve
    // leaves two in flight. Both pass the guard below, and each resolves with
    // its OWN sentinel - the platform grants a new one per request. Only one
    // can be `sentinel`, and the other is then held by nothing: cleanup and
    // the 'release' listener both only ever address whatever `sentinel` is
    // now. The counter makes the LAST request win, which is the right one -
    // it was asked for after the most recent time the page came back, so the
    // earlier one was requested before a hide the platform releases on.
    let generation = 0

    const acquire = async () => {
      if (cancelled || document.hidden) return
      const mine = ++generation
      try {
        const held = await navigator.wakeLock.request('screen')
        if (cancelled || mine !== generation) {
          void held.release().catch(() => {})
          return
        }
        // The other half, and the one the counter alone does not cover: this
        // request may have overtaken one that already landed. Storing the new
        // sentinel FIRST and releasing the old one after is deliberate - the
        // old sentinel's 'release' listener guards on `sentinel === held`, so
        // by releasing it second we stop it reporting 'released' for a screen
        // that is still being held by its replacement.
        const superseded = sentinel
        sentinel = held
        setState('held')
        if (superseded !== null && superseded !== held) {
          void superseded.release().catch(() => {})
        }
        // The platform can take it back at any time. Without this the state
        // stays 'held' forever and the screen keeps promising a lock that is
        // gone - see the header. `once` because a fresh sentinel arrives with
        // its own listener from the next `acquire`.
        // Guarded: a real WakeLockSentinel is an EventTarget, but a sentinel
        // that is not must not cost the lock we actually hold - falling into
        // the catch below would report 'refused' for a granted request, which
        // is a worse lie than missing the release.
        held.addEventListener?.(
          'release',
          () => {
            if (!cancelled && sentinel === held) setState('released')
          },
          { once: true },
        )
      } catch {
        // Refusal is a normal answer, not an error to surface as a crash: a
        // phone under 20% battery declines this on several platforms.
        // `mine === generation` for the same reason as above, one case over: a
        // superseded request that rejects must not report 'refused' over a
        // lock a later request has since been granted.
        if (!cancelled && mine === generation) setState('refused')
      }
    }

    // THE PART THAT IS EASY TO MISS. The platform releases the lock every time
    // the page hides, and does not give it back on return. Without this
    // listener the first glance at another app would end the wake lock for the
    // rest of the walk, silently - which is the same shape as the bug this
    // hook is fixing.
    const reacquire = () => {
      if (!document.hidden) void acquire()
    }

    document.addEventListener('visibilitychange', reacquire)
    void acquire()

    return () => {
      cancelled = true
      document.removeEventListener('visibilitychange', reacquire)
      void sentinel?.release().catch(() => {})
    }
  }, [active])

  return state
}
