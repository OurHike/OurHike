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
  normalisePreferences,
  preferencesSyncState,
  recordPreferencesPush,
  type PreferencesSyncState,
} from './preferences'
import type { UserPreferences } from './userPreferences'

/** What a reconciliation decided to do. `idle` is the ordinary answer on a
 *  launch where nobody changed anything anywhere. */
export type SyncPlan = 'push' | 'pull' | 'idle'

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
  state: PreferencesSyncState,
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
  try {
    const remote = await fetchSyncedPreferences()
    const state = await preferencesSyncState()
    const plan = planPreferencesSync(remote?.updated_at ?? null, state)

    if (plan === 'idle') return null
    if (plan === 'pull') {
      // `remote` cannot be null on this branch - `planPreferencesSync` answers
      // 'push' for a missing row - but the compiler does not know the rule,
      // and asserting it here would be a claim rather than a check.
      if (remote === null) return null
      return await adoptPreferences(adoptable(remote), remote.updated_at)
    }

    const pushed = await pushPreferences(local)
    await recordPreferencesPush(pushed.updated_at)
  } catch (error) {
    if (!isOrdinarySilence(error)) reportSyncFailure(error)
  }
  return null
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
export async function pushPreferencesIfChanged(local: UserPreferences): Promise<void> {
  const state = await preferencesSyncState()
  if (!state.dirty) return

  try {
    const pushed = await pushPreferences(local)
    await recordPreferencesPush(pushed.updated_at)
  } catch (error) {
    // Still dirty either way, deliberately. The next launch or the next
    // change tries again, which is what makes an offline stretch cost
    // nothing - and what makes a schema mismatch retry rather than lose the
    // hiker's setting while somebody fixes it.
    if (!isOrdinarySilence(error)) reportSyncFailure(error)
  }
}
