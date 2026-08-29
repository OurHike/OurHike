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

    const acquire = async () => {
      if (cancelled || document.hidden) return
      try {
        const held = await navigator.wakeLock.request('screen')
        if (cancelled) {
          void held.release().catch(() => {})
          return
        }
        sentinel = held
        setState('held')
      } catch {
        // Refusal is a normal answer, not an error to surface as a crash: a
        // phone under 20% battery declines this on several platforms.
        if (!cancelled) setState('refused')
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
