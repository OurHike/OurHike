// A notice from an organization, whichever organization that is (#1083).
//
// features/ORG_NOTICES.md is the design. Its one-line summary of the problem:
// almost all of the delivery machinery already generalizes, and exactly one
// thing does not - WHERE A NOTICE IS. The ATC says it in miles from Springer.
// Nobody else can, and pretending otherwise is the failure mode that document
// exists to prevent.
//
// WHAT THIS MODULE IS FOR, AND WHAT IT DELIBERATELY LEAVES ALONE
//
// The surfaces that need a mile - the banner's "2.6 mi ahead", the bands, the
// points on the map - keep taking `AtcUpdate` and are untouched by this file.
// That is not laziness: `at_miles` is still the only arm of the union that
// carries a mile, so code that needs one is code that only ever runs on ATC's
// rows, and giving it a nullable mile would turn a compile-time fact into a
// runtime check.
//
// What generalizes here is everything that needs no mile: the list a hiker
// reads, the "something new was posted" banner, the id a drawn band is keyed
// on, and above all THE ORGANIZATION'S NAME - which is read off the row's
// `source_key` through lib/stewards.ts and never written in a component.
// ORG_NOTICES.md §6: "a string in a component is how the app ends up telling a
// hiker that NYNJTC's closure is ATC's word."
//
// WHY THE ROW TYPE IS AN ALIAS RATHER THAN A NEW INTERFACE
//
// `OrgNotice` in lib/publishedConditions.ts is already exactly the row
// ORG_NOTICES.md §2 specifies, because `pipeline/export_nynjtc_alerts.py`
// already publishes it - `notice_id`, `source_key`, `category` nullable,
// `locality`, and the `place` union. Declaring a second identical interface
// here would be two names for one shape, and the day they drift is the day a
// renderer reads one and the pipeline writes the other.
//
// ATC's artifact is the older one and does NOT carry `source_key` or `place`:
// `pipeline/export_atc_updates.py` still writes `atc_id` and two mile columns.
// So `atcUpdateAsNotice` below adapts it, and that adapter is the whole of the
// asymmetry. When ATC's exporter grows the two fields, the adapter becomes the
// identity function and this comment is how the next person knows to delete it.

import type { AtcUpdate } from './atcUpdates'
import type { OrgNotice } from './publishedConditions'
import { orgLabelFrom, type Stewards } from './stewards'

/**
 * One notice, from any organization, as the surfaces that need no mile see it.
 *
 * See the module comment for why this is an alias. The name is the one worth
 * reading in a signature - `TrailNotice` says what a caller may assume, where
 * `OrgNotice` reads as "not the ATC's", which is exactly the single-tenant
 * habit this issue is undoing.
 */
export type TrailNotice = OrgNotice

/**
 * The registry key for ATC's notices, which is the join `source_key` carries.
 *
 * `pipeline/sources.json`'s ninth-from-last entry, verbatim. It is a REGISTRY
 * KEY and not an abbreviation, which is the point: `lib/stewards.ts`'s
 * `orgLabelFrom` resolves a key to an organization's own name through the
 * published `stewards.json`, so a row that carries one can be attributed
 * without any component knowing who the ATC are.
 *
 * This replaces `ATC_BAND_ID_PREFIX = 'atc:'`, which was the same idea written
 * as an abbreviation nothing could resolve.
 */
export const ATC_SOURCE_KEY = 'atc_trail_updates'

/**
 * ATC's row, seen as a notice.
 *
 * Every field maps across without a judgement except two, and both are worth
 * stating:
 *
 * - `locality` takes `states`, joined. ORG_NOTICES.md §2 replaces `states`
 *   with `locality` precisely because "NC, TN" and "Harriman-Bear Mountain"
 *   answer the same question in two organizations' vocabularies, and neither
 *   is the other's.
 * - `review_state` defaults to `reviewed` when absent, matching
 *   `isReviewedByAPerson`: artifacts baked before #963 carry no such field and
 *   every row in one of those was reviewed by definition.
 */
export function atcUpdateAsNotice(update: AtcUpdate): TrailNotice {
  return {
    notice_id: `${ATC_SOURCE_KEY}:${update.atc_id}`,
    source_key: ATC_SOURCE_KEY,
    title: update.title,
    category: update.category,
    locality: update.states.join(', '),
    place: {
      kind: 'at_miles',
      start: update.start_mile_marker,
      end: update.end_mile_marker,
    },
    obstructs_trail: update.obstructs_trail,
    updated_at: update.updated_at,
    source_url: update.source_url,
    review_state: update.review_state ?? 'reviewed',
  }
}

/** Whether this notice is drawable at all, which today means "is it ATC's".
 *  Written as a question about the PLACE rather than about the publisher, so
 *  the day a reviewed `org_terms` table exists this reads correctly without
 *  being edited. */
export function isPlacedOnTheTrail(notice: TrailNotice): boolean {
  return notice.place.kind === 'at_miles'
}

/**
 * Every notice the app holds, newest first.
 *
 * ONE FLAT LIST, and the ordering is a maintainer's call (2026-08-27) rather
 * than something derived here, so the argument it overrules is worth recording
 * beside it. This surface used to sort by `start_mile_marker` and said why, in
 * its own comment:
 *
 *   "Not by date, and not by severity. Date would put a notice edited
 *    yesterday above one two miles ahead... Mile is the one ordering that is
 *    a fact about the trail rather than a judgement about the notices."
 *
 * That argument was written when every row had a mile. It no longer holds as
 * stated: NYNJTC publishes 18 alerts and not one of them carries a mile, so
 * mile order cannot rank the list at all - it can only rank a subset and leave
 * the rest in an arbitrary order that LOOKS like distance along the trail.
 *
 * What replaces it does the same job a different way. Recency is also a fact
 * rather than a ranking - it is the organization's own `updated_at`, not this
 * app's judgement about which notice matters more - and the "not the one two
 * miles ahead" worry is answered by `withinExtent` below, which scopes the
 * list to where the hiker is looking instead of by how the remainder is
 * sorted.
 */
export function orderedNotices(notices: readonly TrailNotice[]): TrailNotice[] {
  return [...notices].sort((a, b) => noticeTime(b) - noticeTime(a))
}

/**
 * How recently an organization must have touched a notice for it to be shown
 * wherever the map is pointed.
 *
 * Twenty-four hours. The maintainer's rule is that something posted today is
 * shown regardless of extent, and "today" has to become a duration because a
 * calendar day is a fact about a timezone rather than about a notice - a
 * hiker in Georgia at 00:30 would otherwise watch this morning's alert leave
 * the list at midnight while it is still the freshest thing anybody published.
 *
 * @unvalidated Picked to make "today" mean something everywhere rather than
 * measured against how often these organizations post. What would settle it:
 * the interval between consecutive edits on both feeds - NYNJTC's 18 alerts
 * span 2024-01-11 to 2026-06-16, which suggests a day is generous for them and
 * says nothing about ATC's.
 */
export const ALWAYS_SHOWN_WINDOW_MS = 24 * 60 * 60 * 1000

/** The stretch of trail the map is currently showing, in miles from the
 *  southern terminus - `lib/viewportMiles.ts`'s answer, or null when there is
 *  no centerline, no viewport, or no trail in view. */
export interface MileExtent {
  startMile: number
  endMile: number
}

/** What the list shows, and what it is holding back. */
export interface ScopedNotices {
  /** In view, or exempt from the scoping. Ordered newest first. */
  shown: TrailNotice[]
  /** How many the extent scoped out. NEVER silently dropped - the list prints
   *  this number and offers to show them, because a notice the app is holding
   *  and does not mention is the failure #1083 is about. */
  hidden: number
}

/**
 * The notices worth showing for where the hiker is looking.
 *
 * The maintainer's rule (2026-08-27): scope the list to the selected extent.
 * A thru-hiker in Connecticut scrolling past nine Georgia notices to reach the
 * one nine miles ahead is the problem, and mile order alone never solved it.
 *
 * THREE THINGS ARE NEVER SCOPED OUT, and each is a different reason:
 *
 * 1. **A notice with no mile.** Every NYNJTC row today. Filtering something on
 *    a criterion it cannot answer does not exclude it fairly, it excludes it
 *    always - and a notice that reaches no screen is the exact failure this
 *    whole change exists to undo.
 * 2. **A notice the map is drawing.** If a hiker can see the mark, the list
 *    has to be able to explain it. A list that omits what is on screen is
 *    worse than one that shows too much.
 * 3. **Anything touched in the last 24 hours.** The maintainer's "or today".
 *    A closure posted this morning is the one thing a hiker wants whether or
 *    not their map happens to be pointed at it.
 *
 * With no extent - no centerline loaded, or a viewport holding no trail -
 * nothing is scoped. Showing everything is the conservative direction, and it
 * is what the screen did before this rule existed.
 */
export function scopedNotices(
  notices: readonly TrailNotice[],
  extent: MileExtent | null,
  drawnIds: ReadonlySet<string>,
  now: Date,
): ScopedNotices {
  const ordered = orderedNotices(notices)
  if (extent === null) return { shown: ordered, hidden: 0 }

  const low = Math.min(extent.startMile, extent.endMile)
  const high = Math.max(extent.startMile, extent.endMile)

  const shown: TrailNotice[] = []
  let hidden = 0

  for (const notice of ordered) {
    if (notice.place.kind !== 'at_miles') {
      shown.push(notice)
      continue
    }
    if (drawnIds.has(noticeBandId(notice))) {
      shown.push(notice)
      continue
    }
    const at = noticeUpdatedAt(notice)
    if (at !== null && now.getTime() - at.getTime() <= ALWAYS_SHOWN_WINDOW_MS) {
      shown.push(notice)
      continue
    }

    const { start, end } = notice.place
    const overlaps = Math.min(start, end) <= high && Math.max(start, end) >= low
    if (overlaps) shown.push(notice)
    else hidden += 1
  }

  return { shown, hidden }
}

/** Milliseconds, or 0 for a stamp this build cannot read. Sorting an
 *  unreadable date to the bottom is the conservative direction: it cannot
 *  claim to be the newest thing an organization has posted. */
function noticeTime(notice: TrailNotice): number {
  const at = new Date(notice.updated_at).getTime()
  return Number.isNaN(at) ? 0 : at
}

/** The parsed `updated_at`, or null when the organization's stamp is
 *  unreadable - which renders as no date rather than as today. */
export function noticeUpdatedAt(notice: TrailNotice): Date | null {
  const at = new Date(notice.updated_at)
  return Number.isNaN(at.getTime()) ? null : at
}

/**
 * The id a drawn band is keyed on.
 *
 * `notice_id` and nothing else, which is the generalization of
 * `ATC_BAND_ID_PREFIX` rather than a replacement for it: the pipeline already
 * namespaces NYNJTC's ids as `<source key>:<slug>`, so the prefix scheme the
 * client invented for ATC is the scheme the pipeline settled on, one
 * vocabulary further along.
 */
export function noticeBandId(notice: TrailNotice): string {
  return notice.notice_id
}

/**
 * How an organization is named on a notice, from the published registry.
 *
 * Returns a function so a list renders N rows against one Map rather than N
 * scans. `orgLabelFrom` already answers exactly this question for graph edges
 * (#978) and answers it in the three honesty tiers that matter: the steward's
 * own name where one claims the key, the raw key where none does, and
 * "Unattributed" for no key at all.
 *
 * THE RAW-KEY CASE IS NOT A BUG TO PAPER OVER. A card reading
 * `atc_trail_updates` says "this app has a key it cannot name", which is true;
 * a prettified guess would say something nobody stands behind. It happens for
 * real when a phone holds a notice artifact and a stewards artifact from
 * different releases.
 */
export function noticeOrgLabel(stewards: Stewards): (notice: TrailNotice) => string {
  const label = orgLabelFrom(stewards)
  return (notice) => label(notice.source_key || null)
}

// ---------------------------------------------------------------------------
// "Something new was posted", per organization.
// ---------------------------------------------------------------------------

/**
 * How long an edit counts as "new" for the banner.
 *
 * Three days, carried over unchanged from `NEW_ATC_ALERT_WINDOW_MS` in the
 * single-tenant module this replaced, along with the reasoning: long enough to
 * survive a weekend without a phone, and short of features/
 * ATC_TRAIL_UPDATES.md's own weekly review cadence, so an ordinary gap between
 * reviews does not leave the banner lit for a notice nobody would call fresh.
 *
 * ONE WINDOW FOR EVERY ORGANIZATION, which is worth stating because it is a
 * choice rather than a simplification. A per-org window would let one
 * publisher's notices stay "new" longer than another's on the same screen,
 * and the banner's count spans organizations - so the same three days is what
 * makes the number mean one thing.
 *
 * @unvalidated The three days is ATC's cadence reasoned about, not a
 * measurement of what hikers do. NYNJTC's own posting rhythm has never been
 * measured against it - their 18 alerts span 2024-01-11 to 2026-06-16, which
 * is far slower, so the window is if anything generous for them. What would
 * settle it: how often a hiker opens the app, which #93's field testing is the
 * only thing that can answer.
 */
export const NEW_NOTICE_WINDOW_MS = 72 * 60 * 60 * 1000

/**
 * Where a hiker's "I have seen these" watermark lives, PER ORGANIZATION.
 *
 * THE BUG THIS EXISTS TO PREVENT, stated plainly because it was live the
 * moment a second publisher rendered: there was one key,
 * `ourhike:atc-alerts-silenced-through`, so a hiker dismissing the ATC's
 * banner would have silenced NYNJTC's too - for notices they had never been
 * shown. A watermark is a record of what somebody has SEEN, and one hiker
 * cannot have seen an organization's notices by dismissing another's.
 *
 * Still localStorage and still deliberately not lib/userPreferences.ts: which
 * alerts a hiker has already seen on THIS phone is not a fact an account
 * should carry to a second one.
 */
export function noticeSilenceKey(sourceKey: string): string {
  return `ourhike:notices-silenced-through:${sourceKey}`
}

/** The key the single-tenant watermark used, kept only so an existing hiker's
 *  dismissal survives the change - see `readNoticeSilence`. Nothing writes it. */
export const LEGACY_ATC_SILENCE_KEY = 'ourhike:atc-alerts-silenced-through'

/** Guarded because merely reading `window.localStorage` throws in a hardened
 *  embedder or private browsing, before any get or set runs. */
function storage(): Storage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

function readStamp(key: string): Date | null {
  try {
    const raw = storage()?.getItem(key)
    if (raw === null || raw === undefined) return null
    const parsed = new Date(raw)
    return Number.isNaN(parsed.getTime()) ? null : parsed
  } catch {
    return null
  }
}

/**
 * The newest edit this hiker has already silenced for one organization.
 *
 * READS THE OLD SINGLE-TENANT KEY AS A FALLBACK, for ATC only. A hiker who
 * dismissed the banner yesterday and updates the app today should not be told
 * about the same three notices again - that is the banner crying wolf on its
 * first run after an upgrade, which is exactly how a warning surface teaches
 * people to ignore it. The fallback is read-only and never written back: it
 * ages out of relevance on its own as ATC posts anything newer.
 *
 * Null when nothing is silenced, and null when the marker is unreadable -
 * indistinguishable, and treated as the safe case: nothing is silenced that
 * this build cannot prove is.
 */
export function readNoticeSilence(sourceKey: string): Date | null {
  const own = readStamp(noticeSilenceKey(sourceKey))
  if (own !== null) return own
  return sourceKey === ATC_SOURCE_KEY ? readStamp(LEGACY_ATC_SILENCE_KEY) : null
}

/** Silences every edit at or before `through`, for one organization only.
 *  Best-effort and silent on failure, like every other write in
 *  lib/storageHealth.ts - losing this costs the banner reappearing a beat
 *  early, never any data. */
export function writeNoticeSilence(sourceKey: string, through: Date): void {
  try {
    storage()?.setItem(noticeSilenceKey(sourceKey), through.toISOString())
  } catch {
    // See the docstring.
  }
}

/** What the banner has to say, or null for nothing to say. */
export interface NewNotices {
  /** How many notices, across every organization. */
  count: number
  /** The organizations with at least one, in the order they were first seen -
   *  which is the order the caller handed them over, so a caller wanting ATC
   *  named first hands ATC's rows first. */
  sourceKeys: string[]
  /** The newest edit per organization, which is what a dismissal is recorded
   *  against. One watermark per key, never one shared - see
   *  `noticeSilenceKey`. */
  newestBySource: Map<string, Date>
}

/**
 * The notices touched inside the window that this hiker has not silenced.
 *
 * Generalized from `atcAlertsSince` with the arithmetic unchanged: an edit
 * after `now` (clock skew, not a real case any of these organizations
 * produces) is not counted yet rather than counted forever, and an edit at or
 * before the watermark has already been shown.
 *
 * What is new is that the watermark is looked up PER ROW rather than passed as
 * one value, because two organizations' watermarks are two different facts.
 */
export function newNoticesSince(
  notices: readonly TrailNotice[],
  now: Date,
  silencedThrough: (sourceKey: string) => Date | null,
): NewNotices | null {
  const watermarks = new Map<string, Date | null>()
  const newestBySource = new Map<string, Date>()
  const sourceKeys: string[] = []
  let count = 0

  for (const notice of notices) {
    const at = noticeUpdatedAt(notice)
    if (at === null) continue
    if (at.getTime() > now.getTime()) continue
    if (now.getTime() - at.getTime() > NEW_NOTICE_WINDOW_MS) continue

    const key = notice.source_key
    if (!watermarks.has(key)) watermarks.set(key, silencedThrough(key))
    const mark = watermarks.get(key) ?? null
    if (mark !== null && at.getTime() <= mark.getTime()) continue

    count += 1
    if (!newestBySource.has(key)) sourceKeys.push(key)
    const seen = newestBySource.get(key)
    if (seen === undefined || at.getTime() > seen.getTime()) {
      newestBySource.set(key, at)
    }
  }

  return count === 0 ? null : { count, sourceKeys, newestBySource }
}

/**
 * Silence everything the banner is currently counting, for every organization
 * it is counting for.
 *
 * One dismissal, N watermarks. That is the whole of the merged banner's
 * honesty: what a hiker dismisses is what they were shown, and they were shown
 * a count that spans organizations.
 */
export function silenceNewNotices(newNotices: NewNotices): void {
  for (const [sourceKey, newest] of newNotices.newestBySource) {
    writeNoticeSilence(sourceKey, newest)
  }
}

/**
 * What the "new notices" banner says, with every organization named.
 *
 * Composed here rather than in chrome/MapScreen.tsx, because naming an
 * organization means resolving a `source_key` through the published registry
 * and features/ORG_NOTICES.md §6 puts that everywhere except a component.
 *
 * ONE PUBLISHER KEEPS TODAY'S SENTENCE, shape and separator both - `ATC · 2
 * new alerts issued` becomes `Appalachian Trail Conservancy · 2 new notices
 * issued`, which is the same line with the abbreviation resolved. That is
 * features/ATC_TRAIL_UPDATES.md's "an ATC update must be visibly ATC's" still
 * holding in the case where it can, rather than being generalized away.
 *
 * THREE OR MORE STOPS NAMING THEM, and that is a deliberate ceiling rather
 * than a layout convenience. A banner is around 40 characters of a hiker's
 * attention in direct sun; four organization names in full is a paragraph, and
 * a warning surface that becomes a paragraph is the "feed" features/
 * ORG_NOTICES.md §9 names as the thing to avoid. The list has the names.
 *
 * @unvalidated The 3-organization ceiling is picked, not measured - the survey
 * found four orgs that publish and only two ship today, so nothing has ever
 * rendered the third branch. What would settle it: the first release carrying
 * three notice sources, read on a phone in daylight.
 */
export function newNoticeLabel(newNotices: NewNotices, stewards: Stewards): string {
  const label = orgLabelFrom(stewards)
  const names = newNotices.sourceKeys.map((key) => label(key))
  const { count } = newNotices

  if (names.length === 1) {
    return count === 1
      ? `${names[0]} · New notice issued`
      : `${names[0]} · ${count} new notices issued`
  }

  const who = names.length === 2 ? names.join(' and ') : `${names.length} organizations`
  return `${count} new trail notices · ${who}`
}
