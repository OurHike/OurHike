// `places.json` as bytes on the phone (#1371, #1373).
//
// The same road `suggested_hikes.json` rides (lib/suggestedHikesData.ts):
// fetched from the bucket when there is signal, kept in IndexedDB through
// lib/conditionsCache.ts so the search answers with none, validated on BOTH
// ways through because a stored document is no more trustworthy than a
// fetched one.
//
// NEVER FATAL. An unreachable bucket, a 404 from a release that predates the
// artifact, a malformed document - all yield "nothing to search yet", and the
// first-run field says so in words. This is a source of places, not a second
// thing to be offline from.

import { DATA_CONFIGURED, PLACES_KEY, dataUrl } from './config'
import { recallPublished, rememberPublished } from './conditionsCache'
import { validatePlaces, type PlacesDocument } from './places'

/** The kept copy, or null when nothing has been kept. */
export async function recallPlaces(): Promise<PlacesDocument | null> {
  const cached = await recallPublished(PLACES_KEY)
  return cached === null ? null : validatePlaces(cached.document)
}

/**
 * Ask the bucket, keep what it says, hand back the places - or null when
 * nothing usable came back, in which case the caller keeps what it had. A
 * 404 must not clear the kept copy: a bucket that stopped carrying the
 * artifact is not evidence the places it carried stopped existing.
 */
export async function fetchPlaces(signal?: AbortSignal): Promise<PlacesDocument | null> {
  if (!DATA_CONFIGURED) return null
  try {
    const response = await fetch(dataUrl(PLACES_KEY), { signal })
    if (!response.ok) return null
    const document: unknown = await response.json()
    if (typeof document !== 'object' || document === null) return null
    const places = validatePlaces(document)
    await rememberPublished(PLACES_KEY, document as Record<string, unknown>)
    return places
  } catch {
    return null
  }
}
