// When the trip reconciliation runs (#892), and when it does not.
//
// Phase A's `lib/usePreferencesSync.ts` shape, with one difference that
// comes from what trips are: **a pull, on sign-in, and after a local change
// - but never a push-only path.** Preferences can be pushed blind, because
// one blob replaced wholesale cannot be a conflict with itself. A trip can,
// so every exchange has to be an exchange: this device offers what it did
// and takes back what the server decided, in one call.
//
// A hook rather than more effects in App.tsx, and for the reason phase A
// gives: App.tsx is this repository's merge-conflict chokepoint (#327).
// What lands there is one call.

import { useEffect, useRef } from 'react'
import { syncTripsWithAccount } from './tripsSync'
import type { TripStore } from './trips'

/**
 * How long a burst of edits is allowed to settle before it is synced.
 *
 * @unvalidated Picked, not measured, and longer than phase A's 1.5s on
 * purpose: a preference is one tap, while editing a plan is a sustained
 * activity - dragging a day boundary, renaming a stop, adding a resupply -
 * and syncing mid-edit would spend a request on a plan the hiker is still
 * changing. What would settle it is instrumenting the Plan tab for the gap
 * between consecutive `saveTrips` calls during a real editing session and
 * taking a high percentile. Being wrong is cheap in both directions: too
 * short spends requests, too long delays a sync the next launch would make.
 */
export const TRIP_SETTLE_MS = 4_000

/**
 * Keep this device's trips and the account's in step.
 *
 * @param trips     the store as rendered. Only used to notice that it moved.
 * @param signedIn  whether there is an account to sync with.
 * @param onAdopt   called with the merged store when the exchange changed
 *                  something. Must be stable across renders.
 */
export function useTripsSync(
  trips: TripStore,
  signedIn: boolean,
  onAdopt: (store: TripStore) => void,
): void {
  const adopt = useRef(onAdopt)
  adopt.current = onAdopt

  // Sign-in, and opening the app already signed in. The one moment the
  // account can be holding something this device has never seen.
  useEffect(() => {
    if (!signedIn) return
    let live = true

    void syncTripsWithAccount().then((merged) => {
      if (live && merged !== null) adopt.current(merged)
    })

    return () => {
      live = false
    }
  }, [signedIn])

  // And after the hiker changes something here. `syncTripsWithAccount` reads
  // the ledger itself, so this firing on a render that changed nothing costs
  // one IndexedDB read and sends an empty exchange.
  useEffect(() => {
    if (!signedIn) return

    const timer = setTimeout(() => {
      void syncTripsWithAccount().then((merged) => {
        if (merged !== null) adopt.current(merged)
      })
    }, TRIP_SETTLE_MS)

    return () => clearTimeout(timer)
  }, [trips, signedIn])
}
