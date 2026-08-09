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
import { DATA_CONFIGURED, dataUrl } from './config'

/** The keys `pipeline/publish.py` uploads them under. Must match exactly: a
 *  key in that bucket is a URL deployed clients already request, and cannot be
 *  renamed afterwards (pipeline/R2_LAYOUT.md). */
export const PUBLISHED_CLOSURES_KEY = 'conditions/closures.json'
export const PUBLISHED_REPORTS_KEY = 'conditions/reports.json'

export interface PublishedConditions<T> {
  /** When the bake ran. Rendered to the hiker; see lib/conditionState.ts. */
  generatedAt: Date
  items: T[]
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
  field: 'closures' | 'reports',
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

    return { generatedAt, items: items as T[] }
  } catch {
    // Includes the abort case, which is not an error worth distinguishing:
    // a cancelled read has no baseline to offer either.
    return null
  }
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
