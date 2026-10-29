// Preferences follow the account (#891, features/ACCOUNT_SYNC.md phase A).
//
// `GET /preferences/me` and `PUT /preferences/me` have been implemented,
// strictly validated and covered by two backend test files since well before
// anything called them. Until this module there was no caller: a hiker who
// signed in on a second device got the default theme, the default units, no
// trail name and an onboarding flow they had already finished.
//
// PHASE A GOES FIRST BECAUSE BEING WRONG HERE IS CHEAP. Every phase after it
// inherits this machinery - the token, the base URL, the conflict rule, the
// offline no-op, the sign-out - and preferences are the one payload in the
// whole feature where losing the older of two edits costs a toggle a hiker
// can flip again rather than four days of planning.
//
// NO WRITE WAITS ON THE NETWORK. Preferences save to IndexedDB exactly as
// they did before this file existed; the sync is a reconciliation on top. An
// offline device, an unconfigured build and a signed-out hiker are all
// no-ops - `syncPreferences` returns rather than throws for every one of
// them, because none of them is a fault a hiker can act on and a settings
// screen that reported them would be reporting the ordinary state of this
// app.
//
// THE BLOB SYNCS WHOLESALE, which is the router's design and not a shortcut
// taken here (`models/preferences.py`: "a client-owned blob that syncs
// wholesale, not a table anything here queries relationally"). The honest
// consequence is that a conflict is resolved for the WHOLE blob, so a hiker
// who changes the theme on one device and the units on another loses one of
// them. That is the cost this phase accepts by going first, and it is not
// hidden: it is why the conflict rule below is the shape it is.

import { fetchSyncedPreferences, pushPreferences, type SyncedPreferences } from './api'
import {
  adoptPreferences,
  CONSENT_KEYS,
  type ConsentKey,
  normalisePreferences,
  preferencesSyncState,
  recordPreferencesPush,
  type PreferencesSyncState,
} from './preferences'
import type { UserPreferences } from './userPreferences'

/** What a reconciliation decided to do. `idle` is the ordinary answer on a
 *  launch where nobody changed anything anywhere. */
export type SyncPlan = 'push' | 'pull' | 'idle'

/** What one attempt came to. */
export interface SyncOutcome {
  /** The preferences to switch to, or null when nothing on screen changes. */
  adopted: UserPreferences | null
  /**
   * The account answered, and every consent answer given on this device has
   * reached it. Only then are the consent answers on screen the account's
   * word, which is what usage measurement waits for before it sends
   * (lib/useUsageMeasurement.ts `consentSettled`). An attempt with no signal
   * is not one: settling on it let a phone that launched offline send the
   * moment signal returned, before the "off" given on another phone arrived
   * (#1903's second review).
   */
  reached: boolean
}

const NOT_REACHED: SyncOutcome = { adopted: null, reached: false }

/**
 * The conflict rule, as a function of two facts and nothing else.
 *
 * Pure and exported so the rule can be argued with directly. The order of
 * the branches IS the rule:
 *
 *  1. **No row on the server** -> push. There is nothing to overwrite, and
 *     until some device establishes the row every other device's first sync
 *     has nothing to adopt.
 *  2. **This device has never synced** -> pull, even if it has local
 *     changes. Signing in is a hiker asking for their account's settings,
 *     and whatever an install accumulated before it had an account is not a
 *     claim on that account. This is the exact case #891 opens with, and
 *     getting it the other way round would mean a hiker who onboards on a
 *     new phone and then signs in overwrites their own account with the
 *     defaults they just clicked through.
 *  3. **This device has changed something** -> push. Including when the
 *     server also moved: that is the one case the bookkeeping genuinely
 *     cannot separate, and it resolves toward the device in the hiker's
 *     hand, which is the one whose settings they can see being wrong.
 *  4. **The server moved and we did not** -> pull.
 *  5. **Neither moved** -> idle, and no request is spent.
 *
 * Note what is NOT here: any comparison of a local clock against a server
 * clock. `preferences.ts`'s `dirty` docstring has the reasoning.
 */
export function planPreferencesSync(
  remoteUpdatedAt: string | null,
  state: Pick<PreferencesSyncState, 'dirty' | 'syncedAt'>,
): SyncPlan {
  if (remoteUpdatedAt === null) return 'push'
  if (state.syncedAt === null) return 'pull'
  if (state.dirty) return 'push'
  if (remoteUpdatedAt !== state.syncedAt) return 'pull'
  return 'idle'
}

/** The blob a `SyncedPreferences` carries, without the server's own field
 *  and made safe for this build to use. */
function adoptable(remote: SyncedPreferences): UserPreferences {
  const { updated_at: _updatedAt, ...blob } = remote
  return normalisePreferences(blob)
}

/**
 * What a push may carry: every preference, and a consent answer only when it
 * was given on this device (`PreferencesSyncState.consentTouched`). A key left
 * out keeps the account's value - the router merges with `exclude_unset`.
 * Creating the account's row is the exception: there is no answer there to
 * keep, and leaving one out would write the default "on" in its place.
 */
function forPush(
  local: UserPreferences,
  touched: readonly ConsentKey[],
  creating: boolean,
): UserPreferences {
  const blob: Partial<UserPreferences> = { ...local }
  if (!creating)
    for (const key of CONSENT_KEYS) if (!touched.includes(key)) delete blob[key]
  return blob as UserPreferences
}

/**
 * Push, then take the account's word for every consent answer this device did
 * not give. Returns what to adopt, or null when nothing on screen changes.
 */
async function pushAndSettle(
  local: UserPreferences,
  state: PreferencesSyncState,
  creating: boolean,
): Promise<UserPreferences | null> {
  const pushed = await pushPreferences(forPush(local, state.consentTouched, creating))
  await recordPreferencesPush(pushed.updated_at)
  const account = adoptable(pushed)
  const theirs = CONSENT_KEYS.filter(
    (key) => !state.consentTouched.includes(key) && account[key] !== local[key],
  )
  if (creating || theirs.length === 0) return null
  const settled: UserPreferences = { ...local }
  for (const key of theirs) Object.assign(settled, { [key]: account[key] })
  return adoptPreferences(settled, pushed.updated_at)
}

/**
 * The three states that are not faults, BY NAME rather than by class.
 *
 * A build with no backend, a hiker who is signed out and a device with no
 * signal are the ordinary conditions this app is designed around. `TypeError`
 * is what `fetch` rejects with when the request never reached anything; the
 * check is deliberately broad, because the ways a phone loses signal
 * mid-request are many and the right response to all of them is the same -
 * leave the bookkeeping alone and try again next launch. A genuine
 * programming `TypeError` would be misread as no-signal here, and that costs
 * a skipped sync rather than anything a hiker notices.
 *
 * Matched on `name` and not with `instanceof`, which is the part worth
 * explaining. `api.ts` sets `name` on both of its error classes precisely so
 * they can be identified, and reading it means this module imports two
 * functions from that file and no values - so a test that partially mocks
 * `./lib/api` cannot make the CLASSIFICATION of an error throw a second
 * error inside the handler for the first. That is not hypothetical: it is
 * what the ten `App.*.test.tsx` files that mock the API module did to the
 * first version of this file.
 */
const SILENT_FAILURES = new Set([
  'ApiNotConfiguredError',
  'NotSignedInError',
  'TypeError',
])

function isOrdinarySilence(error: unknown): boolean {
  return error instanceof Error && SILENT_FAILURES.has(error.name)
}

/**
 * What happens to a failure that is NOT one of the three silences.
 *
 * A 422 here is the client sending a key the schema forbids - wholesale, for
 * every hiker, on their first sync. That was #242, and it must not be
 * invisible a second time.
 *
 * **Logged rather than thrown, and the first draft of this file got that
 * wrong.** Every caller of this module is a background effect, so a throw
 * became `void promise` with nothing to catch it: an unhandled rejection,
 * which is quieter than a log rather than louder, while looking from the
 * code like the error was being taken seriously. It also cannot help the
 * person it would need to reach - a hiker can do nothing about a schema
 * mismatch, and there is no surface in phase A that could tell them
 * (features/ACCOUNT_SYNC.md phase D is where saying anything belongs).
 *
 * The reader who CAN act on it is whoever is looking at a console or a
 * bug report, so the message names the guard that should have caught this
 * before it shipped.
 */
function reportSyncFailure(error: unknown): void {
  console.error(
    'Preferences sync failed for a reason that is not offline, signed out or unconfigured. ' +
      'A 422 here means the client blob and backend/app/schemas/preferences.py disagree, ' +
      'which backend/tests/test_preferences_contract.py exists to catch first (#242).',
    error,
  )
}

/**
 * Reconcile this device with the account, and return what to adopt.
 *
 * Returns the preferences the app should switch to, or null when there is
 * nothing to adopt - which covers a push, an idle launch, and every one of
 * the no-op conditions above. Null is deliberately not distinguishable from
 * "nothing changed" by the caller: no surface in phase A reports sync state,
 * and #894 is where saying so out loud belongs.
 *
 * **This never rejects.** Its only callers are background effects, so a
 * rejection here would be an unhandled one - see `reportSyncFailure`, which
 * is where anything that is not one of the three silences goes instead.
 */
export async function syncPreferences(
  local: UserPreferences,
): Promise<UserPreferences | null> {
  return (await reconcilePreferences(local)).adopted
}

/**
 * `syncPreferences`, saying also whether the account answered - which
 * lib/usePreferencesSync.ts needs and the null of "nothing to adopt" cannot
 * carry. Never rejects, for the same reason.
 */
export async function reconcilePreferences(local: UserPreferences): Promise<SyncOutcome> {
  try {
    const remote = await fetchSyncedPreferences()
    const state = await preferencesSyncState()
    const plan = planPreferencesSync(remote?.updated_at ?? null, state)

    if (plan === 'idle') return { adopted: null, reached: true }
    if (plan === 'pull') {
      // `remote` cannot be null on this branch - `planPreferencesSync` answers
      // 'push' for a missing row - but the compiler does not know the rule,
      // and asserting it here would be a claim rather than a check.
      if (remote === null) return NOT_REACHED
      // The account wins, except for a consent answer given on this device
      // since the last sync: that is the hiker's newest word, and it goes up.
      const merged: UserPreferences = adoptable(remote)
      for (const key of state.consentTouched) Object.assign(merged, { [key]: local[key] })
      const adopted = await adoptPreferences(merged, remote.updated_at)
      if (state.consentTouched.length > 0) {
        const pushed = await pushPreferences(
          forPush(adopted, state.consentTouched, false),
        )
        await recordPreferencesPush(pushed.updated_at)
      }
      return { adopted, reached: true }
    }

    return { adopted: await pushAndSettle(local, state, remote === null), reached: true }
  } catch (error) {
    if (!isOrdinarySilence(error)) reportSyncFailure(error)
  }
  return NOT_REACHED
}

/**
 * Push, but only if this device has something to push.
 *
 * The "push on change" half, and it deliberately spends no `GET`. A hiker
 * flipping four waypoint categories in the legend would otherwise cost four
 * round trips to ask a question whose answer this device already has
 * written down.
 *
 * The dirty flag is read from the store rather than taken as an argument,
 * because `savePreferences` is what sets it and this must not be able to
 * disagree with it.
 */
export async function pushPreferencesIfChanged(
  local: UserPreferences,
): Promise<UserPreferences | null> {
  return (await pushIfChanged(local)).adopted
}

/** `pushPreferencesIfChanged`, saying also whether the push reached the account. */
export async function pushIfChanged(local: UserPreferences): Promise<SyncOutcome> {
  const state = await preferencesSyncState()
  // Never before this device's first reconciliation: that is `syncPreferences`'
  // job, and its rule is that a first sign-in ADOPTS the account. A change
  // made before it, pushed by this timer, could beat the pull and write a
  // fresh install's defaults over the account (#1903's review).
  if (!state.dirty || state.syncedAt === null) return NOT_REACHED

  try {
    return { adopted: await pushAndSettle(local, state, false), reached: true }
  } catch (error) {
    // Still dirty either way, deliberately. The next launch or the next
    // change tries again, which is what makes an offline stretch cost
    // nothing - and what makes a schema mismatch retry rather than lose the
    // hiker's setting while somebody fixes it.
    if (!isOrdinarySilence(error)) reportSyncFailure(error)
    return NOT_REACHED
  }
}
