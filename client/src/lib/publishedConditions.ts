// Closures and reports as published bytes, rather than as answers from a
// server.
//
// features/CONDITIONS_DELIVERY.md is the design. The short version: both are
// public, unauthenticated and read-mostly, which is the same shape as the map
// data this app already downloads from R2 - so `pipeline/export_conditions.py`
// bakes the verified public rows into artifacts daily and this reads them.
//
// WHY THIS EXISTS AT ALL, given `fetchClosures` and `fetchReports` already
// work. Because those need the backend to be up. Today an unreachable backend
// means a hiker sees NO closure warnings, NO warning pins, and nothing saying
// why (#249, and the reason #429 exists) - "nothing is reported here" and "we
// could not ask" render identically. A published baseline turns the worst case
// from *no warnings* into *day-old warnings, labelled as day-old*, which is
// strictly safer and is OurHikeValues.md #4 rather than a nicety.
//
// NEVER FATAL, deliberately, and copied from lib/dataManifest.ts's posture: an
// unreachable bucket, a malformed document, or a data release published before
// these artifacts existed all yield `null`, and the caller falls back to
// exactly what it did before. This is a source of safety information, not a
// second thing to be offline from.
//
// The shapes match the anonymous responses of the live endpoints - see the
// export script's docstring for why - so a live read can replace a baseline
// one without conversion. The one asymmetry is report photos (#436): the live
// tier answers `photo_url` with a short-lived presigned URL, so the baked
// artifact simply omits the field, and a baseline report renders without its
// photo rather than with a broken one.

import type { ClosureSummary, ReportSummary } from './api'
import type { AtcUpdate } from './atcUpdates'
import type { NoteSummary } from './fieldNotes'
import { DATA_CONFIGURED, dataUrl } from './config'

/** The keys `pipeline/publish.py` uploads them under. Must match exactly: a
 *  key in that bucket is a URL deployed clients already request, and cannot be
 *  renamed afterwards (pipeline/R2_LAYOUT.md). */
export const PUBLISHED_CLOSURES_KEY = 'conditions/closures.json'
export const PUBLISHED_REPORTS_KEY = 'conditions/reports.json'
export const PUBLISHED_ATC_UPDATES_KEY = 'conditions/atc_updates.json'
export const PUBLISHED_DROUGHT_KEY = 'conditions/drought.json'
export const PUBLISHED_NOTES_KEY = 'conditions/notes.json'

export interface PublishedConditions<T> {
  /** When the bake ran. Rendered to the hiker; see lib/conditionState.ts. */
  generatedAt: Date
  items: T[]
  /**
   * When a person last checked the source against what it publishes, for the
   * one artifact where that is a different date from the bake's.
   *
   * `undefined` for closures and reports, and that is not an omission: those
   * are baked straight out of the database, so the bake's own clock is the
   * only age there is. ATC's updates come from a file a human reviewed
   * (features/ATC_TRAIL_UPDATES.md), and a daily bake of a three-month-old
   * review would otherwise render as "conditions as of 2h ago" - fresh
   * bytes carrying a stale claim, which is the exact failure the
   * `generated_at` stamp exists to prevent.
   */
  reviewedAt?: Date
  /**
   * The week an artifact describes, when that is not the week it was baked.
   *
   * The drought bands are the case, and they are `reviewedAt`'s problem in a
   * different costume: the U.S. Drought Monitor publishes one map per week,
   * on a Thursday, for the Tuesday-to-Monday week just gone. Baking that
   * hourly is right - it is how the new release is picked up within an hour -
   * but it means `generatedAt` moves twenty-four times a day while the claim
   * underneath does not move at all. A hiker told "drought as of 20 minutes
   * ago" would be reading the bake's clock as if it were NDMC's.
   *
   * `undefined` everywhere else, for the same reason `reviewedAt` is: a
   * closure is true as of the bake and has no other week to belong to.
   */
  validWeek?: { start: Date; end: Date }
}

/**
 * Read one published baseline, or `null` if there isn't a usable one.
 *
 * A document with no `generated_at` is refused rather than defaulted, and that
 * is the one strict thing here. The timestamp is what the UI turns into "as of
 * <date>"; without it the app would show day-old conditions with no indication
 * of age, which is the exact failure this whole path exists to remove. Missing
 * data is recoverable, silently-stale data is not.
 *
 * `field` names the payload inside the document - each artifact says what it
 * holds ("closures", "reports") the way the live endpoints' paths do, and
 * validating it by name means a reports document served where closures were
 * expected reads as "no usable baseline" rather than as an empty trail.
 */
async function fetchPublished<T>(
  key: string,
  field: 'closures' | 'reports' | 'atc_updates' | 'drought' | 'notes',
  signal?: AbortSignal,
): Promise<PublishedConditions<T> | null> {
  if (!DATA_CONFIGURED) return null

  try {
    const response = await fetch(dataUrl(key), { signal })
    if (!response.ok) return null

    const document = (await response.json()) as Record<string, unknown>
    if (typeof document?.generated_at !== 'string') return null
    const items = document[field]
    if (!Array.isArray(items)) return null

    const generatedAt = new Date(document.generated_at)
    if (Number.isNaN(generatedAt.getTime())) return null

    const reviewedAt = parseReviewedAt(document.reviewed_at)
    const validWeek = parseValidWeek(document.valid_start, document.valid_end)
    return {
      generatedAt,
      items: items as T[],
      ...(reviewedAt ? { reviewedAt } : {}),
      ...(validWeek ? { validWeek } : {}),
    }
  } catch {
    // Includes the abort case, which is not an error worth distinguishing:
    // a cancelled read has no baseline to offer either.
    return null
  }
}

/** `reviewed_at`, or undefined when the document has none or it is unusable.
 *
 *  Lenient where `generated_at` is strict, because the two carry different
 *  weight. A document with no `generated_at` is refused outright - it would
 *  show day-old conditions with no indication of age. A missing `reviewed_at`
 *  costs a line of provenance on a sheet, not the age of the data, so an
 *  artifact baked before this field existed still reads. */
function parseReviewedAt(value: unknown): Date | undefined {
  if (typeof value !== 'string') return undefined
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? undefined : parsed
}

/** The week an artifact describes, or undefined when it does not name one.
 *
 *  Lenient like `reviewedAt` and for the same reason - an artifact baked
 *  before this field existed still reads - but stricter in one way: BOTH ends
 *  have to parse. A half-dated week would render as "the week of 11 August to
 *  Invalid Date", and no date at all is a better thing to show than that.
 *
 *  The dates arrive as bare `YYYY-MM-DD`, which `new Date()` reads as UTC
 *  midnight rather than local. That is deliberate and matches the `...Z`
 *  stamping the pipeline uses everywhere else: a hiker in Georgia and one in
 *  Maine should read the same week off the same artifact. */
function parseValidWeek(
  start: unknown,
  end: unknown,
): { start: Date; end: Date } | undefined {
  if (typeof start !== 'string' || typeof end !== 'string') return undefined
  const from = new Date(start)
  const to = new Date(end)
  if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) return undefined
  return { start: from, end: to }
}

export async function fetchPublishedClosures(
  signal?: AbortSignal,
): Promise<PublishedConditions<ClosureSummary> | null> {
  return fetchPublished(PUBLISHED_CLOSURES_KEY, 'closures', signal)
}

export async function fetchPublishedReports(
  signal?: AbortSignal,
): Promise<PublishedConditions<ReportSummary> | null> {
  return fetchPublished(PUBLISHED_REPORTS_KEY, 'reports', signal)
}

/**
 * Field notes as published bytes (features/FIELD_NOTES.md §6): the roll-up's
 * input for every POI, most recent few per place, baked by
 * pipeline/export_conditions.py alongside closures and reports. Same
 * baseline-under-live contract as reports: the live `GET /field-notes` read
 * wins whenever it lands, and this is what a hiker has when the backend is
 * unreachable - day-old word from the trail, labelled as day-old.
 */
export async function fetchPublishedFieldNotes(
  signal?: AbortSignal,
): Promise<PublishedConditions<NoteSummary> | null> {
  return fetchPublished(PUBLISHED_NOTES_KEY, 'notes', signal)
}

/**
 * The ATC's own trail updates, or null if there isn't a usable set.
 *
 * The one artifact here with no live counterpart, and it never gets one: a
 * hiker report has a backend endpoint behind it, and an ATC notice has ATC's
 * website. So this is not a *baseline* for anything - it is the only tier
 * there is, which is why `lib/atcUpdates.ts` states its own age rather than
 * borrowing the closures caveat.
 *
 * `null` covers the case that matters most on this key: a 404, which is what
 * the bucket serves while nobody has reviewed `reference/atc_updates.json`.
 * The pipeline deliberately publishes nothing rather than an empty document
 * in that state (`pipeline/export_atc_updates.py`), because "we have not
 * looked" and "ATC reports nothing" are different claims and only one of
 * them is safe to draw as an empty map.
 */
export async function fetchPublishedAtcUpdates(
  signal?: AbortSignal,
): Promise<PublishedConditions<AtcUpdate> | null> {
  return fetchPublished(PUBLISHED_ATC_UPDATES_KEY, 'atc_updates', signal)
}

/** One published drought band, exactly as `pipeline/export_drought.py` writes
 *  it. `trail_miles` is the mileage at EXACTLY this class - NDMC's polygons
 *  are mutually exclusive, and the export refuses a release where they are
 *  not - so these add up rather than nesting. */
export interface PublishedDroughtBand {
  type: 'Feature'
  geometry: unknown
  properties: { dm: number; label: string; trail_miles: number }
}

/**
 * This week's drought bands, or null if there isn't a usable set.
 *
 * Like the ATC notices and unlike closures, this is the only tier there is -
 * there is no live endpoint behind it, so nothing overrides it and nothing
 * falls back to it.
 *
 * The distinction `null` carries here is the one the pipeline went out of its
 * way to preserve: a 404 means we could not ask, while a document holding an
 * EMPTY band list means NDMC has looked and there is no drought on the trail.
 * Both draw an empty map and only one of them is good news, which is why the
 * export publishes the empty set rather than skipping the file
 * (`pipeline/export_drought.py`).
 */
export async function fetchPublishedDrought(
  signal?: AbortSignal,
): Promise<PublishedConditions<PublishedDroughtBand> | null> {
  return fetchPublished(PUBLISHED_DROUGHT_KEY, 'drought', signal)
}
