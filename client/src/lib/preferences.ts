// Persistence for UserPreferences.
//
// Preferences live on the phone first and sync to an account only if there
// ever is one (features/IDENTITY_AND_PRIVACY.md), so IndexedDB is the store
// of record rather than a cache of the server's copy.
//
// Reads merge over DEFAULT_PREFERENCES rather than trusting what was stored.
// A build that adds a key would otherwise read `undefined` for it on every
// phone that saved preferences before the key existed, and an undefined
// `wrong_way_alert_enabled` is a safety default silently turning itself off.
//
// THE SYNC BOOKKEEPING LIVES HERE TOO (#891), in a SECOND key rather than
// inside the blob. That is not tidiness: the blob is PUT wholesale at a
// schema with `extra="forbid"`, so a bookkeeping field folded into it would
// be a 422 for every hiker on their first sync - which is exactly what #242
// was. The rule that keeps it true is that nothing may join
// `PREFERENCE_KEYS` without joining the backend schema in the same change,
// and backend/tests/test_preferences_contract.py is what enforces it.
//
// lib/preferencesSync.ts owns the reconciliation. This owns the store, so
// there is one module that knows what an IndexedDB key for preferences is
// called.

import {
  BACKGROUND_SOURCES,
  DEFAULT_PREFERENCES,
  HIKING_DETAIL_LEVEL_VALUES,
  MAP_STYLE_VALUES,
  MAX_BACKGROUND_ZOOM_VALUES,
  REPORTER_TYPE_VALUES,
  THEME_VALUES,
  UNIT_SYSTEM_VALUES,
  type UserPreferences,
} from './userPreferences'
import { get, set } from 'idb-keyval'

export const PREFERENCES_KEY = 'ourhike:preferences'

/** Where the sync bookkeeping lives - beside the blob, never inside it. See
 *  this module's header for why that is a correctness rule and not a layout
 *  preference. */
export const PREFERENCES_SYNC_KEY = 'ourhike:preferences:sync'

/**
 * Merging over the defaults fixes a MISSING key, but not a key holding a value
 * this build no longer knows.
 *
 * `background_source` was the first through this door - it used to offer
 * `usgs_topo_live` and `osm_styled_live`, neither of which was ever built,
 * and both of which could be sitting in IndexedDB on a phone that ran an
 * earlier build. Left alone, that value survives the merge (it is present,
 * so there is nothing to fill in), reaches buildMapStyle, matches no
 * background, and draws no background - the exact black-map class of bug
 * MAP_OPTIONS.md spent a section on, arriving by a different road. Theme,
 * map style and the hiking level each then re-derived the same conclusion
 * as their own hand-rolled function, which is how `unit_system` and
 * `max_background_zoom` ended up with no guard at all - the argument covers
 * every enum-typed key, so since #175 the table below does too.
 *
 * An unrecognised value is treated as absent rather than trusted, and the
 * phone falls back to the default it would have had if it had never stored
 * anything. `null` counts as unrecognised except where the model itself is
 * nullable - `reporter_type`'s null is an answer ("hasn't said"), not a
 * corrupt value, and dropping it would re-ask a question the hiker declined.
 */
const KNOWN_ENUM_VALUES: {
  [K in keyof UserPreferences]?: { allowed: readonly unknown[]; nullable?: true }
} = {
  theme: { allowed: THEME_VALUES },
  unit_system: { allowed: UNIT_SYSTEM_VALUES },
  background_source: { allowed: BACKGROUND_SOURCES },
  max_background_zoom: { allowed: MAX_BACKGROUND_ZOOM_VALUES },
  hiking_detail_level: { allowed: HIKING_DETAIL_LEVEL_VALUES },
  map_style: { allowed: MAP_STYLE_VALUES },
  reporter_type: { allowed: REPORTER_TYPE_VALUES, nullable: true },
}

function dropUnknownEnumValues(
  stored: Partial<UserPreferences>,
): Partial<UserPreferences> {
  const repaired = { ...stored }
  for (const [key, rule] of Object.entries(KNOWN_ENUM_VALUES)) {
    const value = repaired[key as keyof UserPreferences]
    if (value === undefined) continue
    if (value === null && rule.nullable) continue
    if (rule.allowed.includes(value)) continue
    delete repaired[key as keyof UserPreferences]
  }
  return repaired
}

/**
 * A stored-or-received blob made safe to use, whatever wrote it.
 *
 * Exported because the account is a SECOND writer of this shape (#891) and
 * needs exactly the same treatment as IndexedDB: a synced blob can come from
 * a build newer than this one, or from a build old enough to predate a key,
 * and `GET /preferences/me` hands it back verbatim apart from its own
 * `background_source` repair. Trusting it because it arrived over TLS would
 * be trusting the wrong property.
 */
export function normalisePreferences(
  stored: Partial<UserPreferences> | undefined,
): UserPreferences {
  return {
    ...DEFAULT_PREFERENCES,
    ...dropUnknownEnumValues(stored ?? {}),
  }
}

export async function loadPreferences(): Promise<UserPreferences> {
  return normalisePreferences(
    (await get(PREFERENCES_KEY)) as Partial<UserPreferences> | undefined,
  )
}

/** What this device knows about its own sync with the account (#891). */
export interface PreferencesSyncState {
  /**
   * This device has changed preferences since its last successful sync.
   *
   * A flag rather than a timestamp, and that is the decision worth reading.
   * "Last write wins on `updated_at`" is the rule, and the obvious reading of
   * it - stamp the local edit, compare it against the server's stamp -
   * compares a phone's clock against a server's. A phone whose clock is a day
   * fast would win every conflict it ever had, silently, and a phone a day
   * slow would lose every one. Neither is detectable from here.
   *
   * So nothing local is ever compared to anything remote. The server's
   * `updated_at` is compared only against ITSELF (`syncedAt` below), which
   * answers "did somebody else move this" without a second clock, and this
   * flag answers "did we". Every case the pair cannot separate - both moved -
   * resolves toward the device the hiker is holding.
   */
  dirty: boolean
  /**
   * The server's `updated_at` at the last successful sync, verbatim, or null
   * when this device has never synced.
   *
   * Null is load-bearing rather than an empty value: it is what makes a first
   * sign-in ADOPT the account instead of overwriting it with whatever this
   * install happened to accumulate before it had one. See
   * `planPreferencesSync`.
   */
  syncedAt: string | null
}

const NEVER_SYNCED: PreferencesSyncState = { dirty: false, syncedAt: null }

export async function preferencesSyncState(): Promise<PreferencesSyncState> {
  const stored = (await get(PREFERENCES_SYNC_KEY)) as
    Partial<PreferencesSyncState> | undefined
  if (stored === undefined) return NEVER_SYNCED
  return {
    dirty: stored.dirty === true,
    syncedAt: typeof stored.syncedAt === 'string' ? stored.syncedAt : null,
  }
}

/**
 * Save a change made ON THIS DEVICE.
 *
 * Marks the blob dirty in the same call, so a preference cannot be changed
 * without the sync knowing. Every local write in the app goes through here;
 * the account's own writes go through `adoptPreferences` instead, which is
 * the whole reason there are two functions rather than a flag.
 */
export async function savePreferences(
  preferences: UserPreferences,
): Promise<UserPreferences> {
  await set(PREFERENCES_KEY, preferences)
  // After the blob, never before. A crash between the two leaves a saved
  // preference that has not been marked for sync, which costs one push; the
  // other order leaves a device claiming to have changed something it did
  // not, and pushing it over the account.
  const state = await preferencesSyncState()
  await set(PREFERENCES_SYNC_KEY, { ...state, dirty: true })
  return preferences
}

/**
 * Save what the ACCOUNT says, and record that this device is level with it.
 *
 * Not `savePreferences`, because adopting is the opposite of a local change:
 * marking it dirty would have this device push straight back what it just
 * pulled, on every launch, for ever.
 */
export async function adoptPreferences(
  preferences: UserPreferences,
  syncedAt: string,
): Promise<UserPreferences> {
  await set(PREFERENCES_KEY, preferences)
  await set(PREFERENCES_SYNC_KEY, { dirty: false, syncedAt })
  return preferences
}

/** Record a successful push: this device is level with the account again. */
export async function recordPreferencesPush(syncedAt: string): Promise<void> {
  await set(PREFERENCES_SYNC_KEY, { dirty: false, syncedAt })
}

/**
 * Forget the sync bookkeeping, keeping the preferences themselves.
 *
 * What sign-out does. The blob stays - it is the phone's, and a hiker who
 * signs out should not watch their theme revert - but `syncedAt` is a claim
 * about an account this device no longer has, and leaving it would make the
 * NEXT sign-in, possibly by a different person on a shared handset, look
 * like a device that had already synced. That is precisely the case
 * `planPreferencesSync` treats as "the account does not get to win".
 */
export async function forgetPreferencesSync(): Promise<void> {
  await set(PREFERENCES_SYNC_KEY, NEVER_SYNCED)
}
