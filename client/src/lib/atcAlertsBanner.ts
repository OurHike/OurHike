// Whether to tell a hiker the ATC has posted something recently, and the
// hiker's own answer to that - separate from chrome/AtcNoticeList.tsx, which
// is every notice the app holds, always browsable through the legend,
// whether or not any of it is new (#687).
//
// WHY A WATERMARK, NOT A SET OF IDS. Tracking "has this hiker seen atc_id X"
// for a handful of slugs that ATC itself edits, retitles and occasionally
// removes would need its own reconciliation the moment a notice's shape
// changes - and ATC's history already shows that (Iron Mtn Gap held five
// edited ranges under one slug across a few months,
// features/ATC_TRAIL_UPDATES.md). A single "silenced through this
// timestamp" mark needs none of that: silencing sets it to the newest edit
// currently counted as new, and the banner returns the moment ATC publishes
// something after it - never because a notice already seen was merely
// reworded or reordered.

import type { AtcUpdate } from './atcUpdates'
import { atcUpdatedAt } from './atcNoticeText'

/** How long an ATC edit counts as "new" for the banner - three days, long
 *  enough to survive a weekend without a phone and short of
 *  features/ATC_TRAIL_UPDATES.md's own weekly review cadence, so an ordinary
 *  gap between reviews does not leave the banner lit for a notice nobody
 *  would call fresh. */
export const NEW_ATC_ALERT_WINDOW_MS = 72 * 60 * 60 * 1000

/** The updates ATC touched inside the window that the hiker has not
 *  silenced. */
export interface NewAtcAlerts {
  count: number
  /** The newest edit among them - what a silence action is recorded
   *  against (writeAtcAlertSilence below). */
  newestAt: Date
}

/**
 * What the bottom banner has to say, or null for nothing to say.
 *
 * `silencedThrough` is the hiker's own watermark (readAtcAlertSilence
 * below); an edit at or before it has already been shown and silenced,
 * however many times ATC has touched the page since this build last read
 * it. An edit that is somehow after `now` (clock skew, not a real case ATC
 * produces) is not counted yet rather than counted forever - it becomes new
 * once `now` actually reaches it.
 */
export function atcAlertsSince(
  updates: readonly AtcUpdate[],
  now: Date,
  silencedThrough: Date | null,
): NewAtcAlerts | null {
  let count = 0
  let newestAt: Date | null = null

  for (const update of updates) {
    const at = atcUpdatedAt(update)
    if (at === null) continue
    if (at.getTime() > now.getTime()) continue
    if (now.getTime() - at.getTime() > NEW_ATC_ALERT_WINDOW_MS) continue
    if (silencedThrough !== null && at.getTime() <= silencedThrough.getTime()) continue

    count += 1
    if (newestAt === null || at.getTime() > newestAt.getTime()) newestAt = at
  }

  return newestAt === null ? null : { count, newestAt }
}

/** Where the silence watermark lives - localStorage, like every other
 *  best-effort local-only marker (lib/storageHealth.ts), and deliberately
 *  not lib/userPreferences.ts: that model syncs to an account
 *  (backend/app/schemas/preferences.py mirrors it field for field), and
 *  which alerts a hiker has already seen on THIS phone is not a fact an
 *  account should carry to a second one. */
export const ATC_ALERT_SILENCE_KEY = 'ourhike:atc-alerts-silenced-through'

/** Guarded because merely reading `window.localStorage` throws in a
 *  hardened embedder or private browsing, before any get or set runs. */
function storage(): Storage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

/** The newest ATC edit the hiker has already silenced, or null if none has
 *  been (or the marker is unreadable - indistinguishable, and treated as
 *  the safe case: nothing is silenced that this build cannot prove is). */
export function readAtcAlertSilence(): Date | null {
  try {
    const raw = storage()?.getItem(ATC_ALERT_SILENCE_KEY)
    if (raw === null || raw === undefined) return null
    const parsed = new Date(raw)
    return Number.isNaN(parsed.getTime()) ? null : parsed
  } catch {
    return null
  }
}

/** Silences every edit at or before `through`. Best-effort and silent on
 *  failure, like every other write in lib/storageHealth.ts - losing this
 *  costs the banner reappearing a beat early, never any data. */
export function writeAtcAlertSilence(through: Date): void {
  try {
    storage()?.setItem(ATC_ALERT_SILENCE_KEY, through.toISOString())
  } catch {
    // See the docstring.
  }
}
