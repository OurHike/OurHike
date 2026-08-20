// Flushing the outbox when there is finally signal to flush it with.
//
// The outbox has always queued correctly (lib/outbox.ts) and nothing ever
// emptied it - `flushOutbox` had no production caller at all (#231). This is
// that caller, plus the two conditions worth checking before spending a
// request, plus the guard that stops two flushes overlapping.

import { useEffect } from 'react'
import { flushOutbox, hasWorkThatNeedsNoAccount, type FlushResult } from './outbox'
import {
  accessToken,
  sendOutboxItem,
  permanentFailureReason,
  API_CONFIGURED,
} from './api'

/**
 * The in-flight flush, if one is running.
 *
 * `flushOutbox` reads the whole queue, sends each item, then writes back what
 * failed. Two overlapping calls therefore both read the same queue and both
 * send everything in it - filing every report twice. Its own docstring
 * promises "flushing twice cannot file the same report twice", which holds for
 * flushes that follow one another and not for flushes that overlap. Coming
 * back into signal is exactly when overlap happens: the `online` event and a
 * screen mounting can land in the same tick.
 *
 * Module-level rather than a ref, because the thing being protected is the
 * queue in IndexedDB - one per device, not one per component.
 */
let inFlight: Promise<FlushResult | null> | null = null

async function run(): Promise<FlushResult | null> {
  // Nothing to send to. Not an error - a build with no backend configured is
  // a real state (see api.ts), and one a hiker cannot do anything about.
  if (!API_CONFIGURED) return null

  // Signed out. Almost every item would be refused and stay queued, which is
  // the correct outcome, so this only avoids spending requests to reach it: a
  // report written before signing in waits for an account rather than being
  // lost, and goes the moment one exists.
  //
  // **Almost, since #848.** The app-failure report is the one write that
  // takes no account, because a hiker whose app just failed may never have
  // signed in and asking them to fix that first gets the priority backwards.
  // Unconditionally returning here left exactly that report waiting for an
  // account it does not need. So a queue holding one is flushed anyway - and
  // the reports and photo actions beside it still cost nothing to skip, since
  // `authedFetch` refuses on a missing token before spending a request.
  if ((await accessToken()) === null && !(await hasWorkThatNeedsNoAccount())) return null

  // The one place transport knowledge (which HTTP statuses are hopeless)
  // meets storage (what to do with a report that will never be accepted).
  // Neither module imports the other; this introduces them. Since
  // #577/#579 the send dispatches on what the item carries - a report or a
  // photo action - through one seam, so the queue stays one queue.
  return flushOutbox(sendOutboxItem, permanentFailureReason)
}

/**
 * Sends whatever is queued, or reports that it could not try.
 *
 * Never rejects: a failed send leaves its item queued (`flushOutbox`), and a
 * flush is background work that must not surface as an error over a map
 * someone is navigating by.
 */
export async function syncOutbox(): Promise<FlushResult | null> {
  if (inFlight !== null) return inFlight

  const started = run()
    .catch(() => null)
    .finally(() => {
      inFlight = null
    })

  inFlight = started
  return started
}

/**
 * Flushes when `enabled` becomes true - i.e. when the phone has signal.
 *
 * Deliberately not on a timer. Out here the app spends most of its life with
 * no connection, and a poll would wake the radio for nothing on a battery
 * that has to last to the next town.
 *
 * `onSynced` fires only when a flush actually ran, so a caller can record a
 * real sync time without mistaking "could not try" for "nothing to send". It
 * must be referentially stable, or this re-runs on every render.
 */
export function useOutboxSync(
  enabled: boolean,
  onSynced: (result: FlushResult) => void,
): void {
  useEffect(() => {
    if (!enabled) return

    let cancelled = false
    void syncOutbox().then((result) => {
      // Unmounted while in flight. The send itself is not cancelled - those
      // reports are gone from the queue and genuinely sent - only the report
      // back to a component that is no longer listening.
      if (result !== null && !cancelled) onSynced(result)
    })

    return () => {
      cancelled = true
    }
  }, [enabled, onSynced])
}
