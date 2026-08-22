// Everything of yours, in one file — the export half of #895
// (features/ACCOUNT_SYNC.md phase E).
//
// WHY THIS DEVICE'S HALF IS IN HERE AND NOT LEFT TO THE SERVER
//
// `GET /profiles/me/export` returns everything the ACCOUNT holds, and that is
// deliberately less than everything the hiker has: photos never sync (phase C
// is unbuilt), walked miles and pace do not sync at all, and a trip made with
// syncing turned off has never been sent. An export that shipped only the
// server's answer would be short by exactly the things a hiker would most
// miss, and would look complete while being wrong.
//
// So the archive has two named halves — `this_device` and `your_account` —
// and the names are the point. A hiker comparing them can see what syncing
// has actually achieved, which is the same question #894's panel answers on
// screen. Merging them into one flat list would destroy that and would have
// to silently pick a winner where the two disagree.
//
// WHY IT STILL WORKS WITH NO BACKEND
//
// `your_account` is null when the export call fails for any of the ordinary
// reasons this app has — no backend configured, signed out, no signal — and
// the file says which. A hiker on a mountain who taps "Take my data" gets
// their device's half rather than an error, because their device's half is
// the part they cannot get anywhere else.

import { get } from 'idb-keyval'

import { ApiNotConfiguredError, NotSignedInError, fetchAccountExport } from './api'
import { PACE_STORAGE_KEY } from './pace'
import { PLAN_KEY, loadPlan } from './plan'
import { PLANNED_HIKE_KEY, loadPlannedHike } from './plannedHike'
import { loadPreferences } from './preferences'
import { OUTBOX_KEY } from './outbox'
import { loadTrips } from './trips'
import { WALKED_STORAGE_KEY, readWalked } from './walkedMiles'

/** What the account half could not be fetched for, in a hiker's words.
 *
 *  Three sentences rather than an error object, because this string goes
 *  into the file itself and is read by somebody with no console open. */
export type AccountUnavailable = string

export interface AccountArchive {
  exported_at: string
  format: string
  this_device: Record<string, unknown>
  your_account: unknown | null
  /** Null when the account half is present. */
  your_account_is_missing_because: AccountUnavailable | null
}

/** The version stamp a future reader needs to know what they are holding.
 *
 *  Not a semver: nothing consumes this file programmatically yet, and
 *  claiming a version contract we do not have would be the stronger
 *  plausible sentence over the weaker true one. It says what it is. */
export const ARCHIVE_FORMAT = 'ourhike-account-archive-1'

function unavailableBecause(error: unknown): AccountUnavailable {
  if (error instanceof ApiNotConfiguredError) {
    return 'This build has no server configured, so there is no account half to fetch.'
  }
  if (error instanceof NotSignedInError) {
    return 'You are not signed in, so nothing here has an account to be held in.'
  }
  return (
    'Your account could not be reached. Everything on this phone is below; try ' +
    'again on a better connection to get the account half too.'
  )
}

/**
 * Read the local half straight out of IndexedDB, by the same keys the app writes.
 *
 * Through each module's own loader where one exists, so the archive gets the
 * validated shape rather than whatever happens to be on disk — a corrupt
 * trips document reads as an empty store in the app (`loadTrips` falls back),
 * and an archive that disagreed with the app about what the hiker has would
 * be worse than one that matches it.
 *
 * The two raw `get` calls are for stores with no loader to borrow. They are
 * exported by key from their own modules rather than spelled here, so a key
 * that changes cannot leave this file quietly reading nothing.
 */
async function deviceHalf(): Promise<Record<string, unknown>> {
  const [trips, plannedHike, plan, preferences, outbox, pace] = await Promise.all([
    loadTrips(),
    loadPlannedHike(),
    loadPlan(),
    loadPreferences(),
    get(OUTBOX_KEY),
    get(PACE_STORAGE_KEY),
  ])

  return {
    trips: trips.trips,
    planned_hike: plannedHike,
    plan,
    preferences,
    // Reports and notes written offline that have not reached the server
    // yet. Ordinary to have, and the one part of a hiker's data that exists
    // in neither half if this is left out.
    not_yet_sent: outbox ?? null,
    pace: pace ?? null,
    walked_miles: readWalked(),
    // Named so a reader knows the two lines above came from this device's
    // own storage rather than from an account.
    read_from: {
      trips: 'ourhike:trips',
      planned_hike: PLANNED_HIKE_KEY,
      plan: PLAN_KEY,
      outbox: OUTBOX_KEY,
      pace: PACE_STORAGE_KEY,
      walked_miles: WALKED_STORAGE_KEY,
    },
  }
}

/**
 * Build the whole archive. Never rejects.
 *
 * The account half failing is an ordinary condition here in a way it is not
 * for a sync: a hiker asked for their data and is entitled to get what we
 * can give them, with a sentence about the rest, rather than an error that
 * loses the half we had in hand.
 */
export async function buildAccountArchive(
  now: Date = new Date(),
): Promise<AccountArchive> {
  const this_device = await deviceHalf()

  let your_account: unknown | null = null
  let missing: AccountUnavailable | null = null
  try {
    your_account = await fetchAccountExport()
  } catch (error) {
    missing = unavailableBecause(error)
  }

  return {
    exported_at: now.toISOString(),
    format: ARCHIVE_FORMAT,
    this_device,
    your_account,
    your_account_is_missing_because: missing,
  }
}

/** `ourhike-2026-08-22.json` — dated, because a hiker exports more than once. */
export function archiveFilename(now: Date = new Date()): string {
  return `ourhike-${now.toISOString().slice(0, 10)}.json`
}

/**
 * Hand the archive to the browser as a download.
 *
 * Separated from `buildAccountArchive` so the building is testable without a
 * DOM and so the one part that cannot be tested in jsdom — whether the
 * browser actually saves the file — is the only part not covered.
 *
 * `URL.revokeObjectURL` is deferred rather than immediate: revoking in the
 * same tick as the click races the browser's own read of the blob in Safari,
 * and the failure is a silently empty file rather than an error.
 */
export function downloadArchive(archive: AccountArchive, now: Date = new Date()): void {
  const blob = new Blob([JSON.stringify(archive, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = archiveFilename(now)
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
