// When the day-hike reconciliation runs (#976), and when it does not.
//
// lib/useTripsSync.ts's shape, unchanged, because the reasons are unchanged:
// **a pull, on sign-in, and after a local change - never a push-only path.**
// A day hike edited on two devices can conflict, so every exchange has to be
// an exchange - this device offers what it did and takes back what the
// server decided, in one call.
//
// A hook rather than more effects in App.tsx, and for the reason that file's
// siblings give: App.tsx is this repository's merge-conflict chokepoint
// (#327). What lands there is one call.

import { useEffect, useRef } from 'react'
import { syncDayHikesWithAccount } from './dayHikesSync'
import type { DayHikeStore } from './dayHikes'

/**
 * How long a burst of edits is allowed to settle before it is synced.
 *
 * @unvalidated Inherited from `TRIP_SETTLE_MS` rather than measured here,
 * and the reasoning transfers: building a day hike is a sustained activity -
 * tap, tap, undo, close the loop - and syncing mid-burst would spend a
 * request on a hike the hiker is still changing. What would settle it is the
 * same instrumentation that would settle the trips value: the gap between
 * consecutive saves in a real session, at a high percentile. Being wrong is
 * cheap in both directions - too short spends requests, too long delays a
 * sync the next launch would make.
 */
export const DAY_HIKE_SETTLE_MS = 4_000

/**
 * Keep this device's day hikes and the account's in step.
 *
 * @param hikes     the store as rendered. Only used to notice that it moved.
 * @param signedIn  whether there is an account to sync with.
 * @param onAdopt   called with the merged store when the exchange changed
 *                  something. Must be stable across renders.
 * @param onSettled called after EVERY exchange, including the ones that
 *                  adopt nothing - see `usePreferencesSync` for why a status
 *                  panel needs to hear about a push as much as about a pull.
 */
export function useDayHikesSync(
  hikes: DayHikeStore,
  signedIn: boolean,
  onAdopt: (store: DayHikeStore) => void,
  onSettled?: () => void,
): void {
  const adopt = useRef(onAdopt)
  adopt.current = onAdopt
  const settled = useRef(onSettled)
  settled.current = onSettled

  // Sign-in, and opening the app already signed in. The one moment the
  // account can be holding something this device has never seen.
  useEffect(() => {
    if (!signedIn) return
    let live = true

    void syncDayHikesWithAccount().then((merged) => {
      if (!live) return
      if (merged !== null) adopt.current(merged)
      settled.current?.()
    })

    return () => {
      live = false
    }
  }, [signedIn])

  // And after the hiker changes something here. `syncDayHikesWithAccount`
  // reads the ledger itself, so this firing on a render that changed nothing
  // costs one IndexedDB read and sends an empty exchange.
  useEffect(() => {
    if (!signedIn) return

    const timer = setTimeout(() => {
      void syncDayHikesWithAccount().then((merged) => {
        if (merged !== null) adopt.current(merged)
        settled.current?.()
      })
    }, DAY_HIKE_SETTLE_MS)

    return () => clearTimeout(timer)
  }, [hikes, signedIn])
}
