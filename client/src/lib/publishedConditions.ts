// Closures as published bytes, rather than as an answer from a server.
//
// features/CONDITIONS_DELIVERY.md is the design. The short version: closures
// are public, unauthenticated and read-mostly, which is the same shape as the
// map data this app already downloads from R2 - so `pipeline/export_conditions.py`
// bakes the verified ones into an artifact daily and this reads it.
//
// WHY THIS EXISTS AT ALL, given `fetchClosures` already works. Because that
// one needs the backend to be up. Today an unreachable backend means a hiker
// sees NO closure warnings and nothing saying why (#249, and the reason #429
// exists) - "nothing is closed here" and "we could not ask" render identically.
// A published baseline turns the worst case from *no warnings* into *day-old
// warnings, labelled as day-old*, which is strictly safer and is
// OurHikeValues.md #4 rather than a nicety.
//
// NEVER FATAL, deliberately, and copied from lib/dataManifest.ts's posture: an
// unreachable bucket, a malformed document, or a data release published before
// this artifact existed all yield `null`, and the caller falls back to exactly
// what it did before. This is a source of safety information, not a second
// thing to be offline from.
//
// The shape matches the backend's `ClosureOut` exactly - see the export
// script's docstring for why - so a live read can replace a baseline one
// without conversion.

import type { ClosureSummary } from './api'
import { DATA_CONFIGURED, dataUrl } from './config'

/** The key `pipeline/publish.py` uploads it under. Must match exactly: a key
 *  in that bucket is a URL deployed clients already request, and cannot be
 *  renamed afterwards (pipeline/R2_LAYOUT.md). */
export const PUBLISHED_CLOSURES_KEY = 'conditions/closures.json'

export interface PublishedClosures {
  /** When the bake ran. Rendered to the hiker; see lib/closureState.ts. */
  generatedAt: Date
  closures: ClosureSummary[]
}

interface RawDocument {
  generated_at?: unknown
  closures?: unknown
}

/**
 * Read the published baseline, or `null` if there isn't a usable one.
 *
 * A document with no `generated_at` is refused rather than defaulted, and that
 * is the one strict thing here. The timestamp is what the UI turns into "as of
 * <date>"; without it the app would show day-old closures with no indication
 * of age, which is the exact failure this whole path exists to remove. Missing
 * data is recoverable, silently-stale data is not.
 */
export async function fetchPublishedClosures(
  signal?: AbortSignal,
): Promise<PublishedClosures | null> {
  if (!DATA_CONFIGURED) return null

  try {
    const response = await fetch(dataUrl(PUBLISHED_CLOSURES_KEY), { signal })
    if (!response.ok) return null

    const document = (await response.json()) as RawDocument
    if (typeof document?.generated_at !== 'string') return null
    if (!Array.isArray(document.closures)) return null

    const generatedAt = new Date(document.generated_at)
    if (Number.isNaN(generatedAt.getTime())) return null

    return { generatedAt, closures: document.closures as ClosureSummary[] }
  } catch {
    // Includes the abort case, which is not an error worth distinguishing:
    // a cancelled read has no baseline to offer either.
    return null
  }
}
