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
import type { UserPreferences } from './userPreferences'

// The reconciliation itself arrives behind import(), on the first sign-in a
// launch has: nothing in it draws the first frame, and #1903's consent rules
// made it 411 bytes the launch budget did not have (features/LAUNCH_BUDGET.md
// §3). Imported once and shared. A chunk that never arrives syncs nothing,
// which every caller already treats as an ordinary failed sync - and the
// next call asks again rather than replaying the failure.
let loading: Promise<typeof import('./preferencesSync')> | null = null
function reconciliation(): Promise<typeof import('./preferencesSync')> {
  loading ??= import('./preferencesSync').catch((error: unknown) => {
    loading = null
    throw error
  })
  return loading
}

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
 * @param onSettled    called after EVERY attempt, including the ones that
 *                     adopt nothing, with whether it reached the account
 *                     (`SyncOutcome.reached`). #894's panel reads the sync
 *                     bookkeeping out of IndexedDB, which no React state
 *                     watches - so a successful push would clear "not sent
 *                     yet" with nothing on screen noticing, and the panel
 *                     would go on saying it until something else
 *                     re-rendered. Optional, and must be stable across renders.
 * @param online       whether the device has signal. A pull that could not
 *                     reach the account is tried again when this turns true,
 *                     once per sign-in: a launch with no signal - the
 *                     ordinary launch on a trail - otherwise never heard the
 *                     account's answers until the next launch (#1903's
 *                     second review). Defaults to true.
 */
export function usePreferencesSync(
  preferences: UserPreferences,
  signedIn: boolean,
  onAdopt: (preferences: UserPreferences) => void,
  onSettled?: (reached: boolean) => void,
  online = true,
): void {
  // Read inside the effects rather than depended upon, so a preference
  // changing does not re-run the sign-in pull.
  const latest = useRef(preferences)
  latest.current = preferences
  const settled = useRef(onSettled)
  settled.current = onSettled
  // Whether this sign-in's pull has reached the account. Until it has, each
  // return of signal tries it again; after, a dropped and returned signal
  // spends nothing.
  const reached = useRef(false)

  useEffect(() => {
    if (!signedIn) {
      reached.current = false
      return
    }
    if (reached.current || !online) return
    let live = true

    void reconciliation()
      .then(({ reconcilePreferences }) => reconcilePreferences(latest.current))
      .catch(() => ({ adopted: null, reached: false }))
      .then((outcome) => {
        if (!live) return
        if (outcome.reached) reached.current = true
        if (outcome.adopted !== null) onAdopt(outcome.adopted)
        settled.current?.(outcome.reached)
      })

    return () => {
      live = false
    }
  }, [signedIn, onAdopt, online])

  // The push half. Driven off the rendered `preferences` because that is
  // what changes when a hiker touches something - but what it actually sends
  // is whatever the store says is dirty, so this firing spuriously (a render
  // with a new object and the same values) costs nothing but a read of one
  // IndexedDB key.
  useEffect(() => {
    if (!signedIn) return

    const timer = setTimeout(() => {
      void reconciliation()
        .then(({ pushIfChanged }) => pushIfChanged(latest.current))
        .catch(() => ({ adopted: null, reached: false }))
        .then((outcome) => {
          // A consent answer this device did not give, and the account holds
          // differently, comes back with the push (lib/preferencesSync.ts).
          if (outcome.adopted !== null) onAdopt(outcome.adopted)
          settled.current?.(outcome.reached)
        })
    }, PUSH_SETTLE_MS)

    return () => clearTimeout(timer)
  }, [preferences, signedIn, onAdopt])
}
