// When the reconciliation in lib/preferencesSync.ts actually runs (#891).
//
// Two moments, and they are the issue's own words: **pull on sign-in, push
// on change.**
//
//   - Signing in (or opening the app already signed in) is when the account
//     can have something this device does not. That is the one moment a
//     `GET` is worth spending.
//   - A local change is when this device has something the account does not.
//     That path spends no `GET` at all - see `pushPreferencesIfChanged`.
//
// A hook rather than more effects in App.tsx, and that is a deliberate
// choice about a specific file: App.tsx is this repository's merge-conflict
// chokepoint (#327 - 12 of the last 27 conflicts, more than the next six
// files combined). What lands there is one call.
//
// NOTHING HERE BLOCKS A RENDER OR A WRITE. The app has already read
// preferences from IndexedDB and drawn with them before this runs; a pull
// arrives afterwards and changes them, exactly as a hiker toggling something
// would.

import { useEffect, useRef } from 'react'
import { pushPreferencesIfChanged, syncPreferences } from './preferencesSync'
import type { UserPreferences } from './userPreferences'

/**
 * How long a burst of changes is allowed to settle before it is pushed.
 *
 * @unvalidated Picked, not measured. What it is protecting against is real
 * and observable - the legend's category toggles and the map-options
 * switches are tapped in runs, and each one is a `savePreferences` - but
 * nobody has timed how long a run of taps actually takes. What would settle
 * it is instrumenting the settings and legend surfaces for the gap between
 * consecutive preference writes and taking a high percentile of it. Being
 * wrong is cheap in both directions: too short spends extra requests on a
 * connection this app assumes is bad, too long delays a push that the next
 * launch would make anyway.
 */
export const PUSH_SETTLE_MS = 1_500

/**
 * Keep this device's preferences and the account's in step.
 *
 * @param preferences  the app's current preferences, as rendered.
 * @param signedIn     whether there is an account to sync with. A change
 *                     from false to true is what triggers the pull, so this
 *                     must reflect the session rather than a screen.
 * @param onAdopt      called with the account's preferences when the pull
 *                     decides they win. Not called otherwise - a push and an
 *                     idle launch both leave what is on screen alone. Must
 *                     be stable across renders.
 */
export function usePreferencesSync(
  preferences: UserPreferences,
  signedIn: boolean,
  onAdopt: (preferences: UserPreferences) => void,
): void {
  // Read inside the effects rather than depended upon, so a preference
  // changing does not re-run the sign-in pull.
  const latest = useRef(preferences)
  latest.current = preferences

  useEffect(() => {
    if (!signedIn) return
    let live = true

    void syncPreferences(latest.current).then((adopted) => {
      if (live && adopted !== null) onAdopt(adopted)
    })

    return () => {
      live = false
    }
  }, [signedIn, onAdopt])

  // The push half. Driven off the rendered `preferences` because that is
  // what changes when a hiker touches something - but what it actually sends
  // is whatever the store says is dirty, so this firing spuriously (a render
  // with a new object and the same values) costs nothing but a read of one
  // IndexedDB key.
  useEffect(() => {
    if (!signedIn) return

    const timer = setTimeout(() => {
      void pushPreferencesIfChanged(latest.current)
    }, PUSH_SETTLE_MS)

    return () => clearTimeout(timer)
  }, [preferences, signedIn])
}
