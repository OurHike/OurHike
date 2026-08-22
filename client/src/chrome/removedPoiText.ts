// The words a removed place is described with, in one place.
//
// Kept out of RemovedPoiCard.tsx so that file exports only a component — React
// Fast Refresh breaks on modules that mix the two, which is the same reason
// poiSources.ts and legendLabels.ts exist beside PoiCard.tsx rather than
// inside it.
//
// THE SENTENCE IS DERIVED FROM THE ROW, WHICH IS THE WHOLE POINT
//
// features/POI_IDENTITY.md §4 and #831 are both explicit that this copy
// "cannot hard-code 'no longer in ATC's data'". Measured against the ledger
// 2026-08-22, the 93 retired rows come from TWO sources — `atc_csi` and
// `opentrail_at` — and opentrail.org is not the ATC at all, so a hard-coded
// sentence would be a false statement about a share of every tombstone the
// app will ever draw. It goes through `sourceLabel`, the same map the live
// card's provenance line reads, so the two cannot describe one source in two
// voices.

import { longDate } from '../lib/atcNoticeText'
import { sourceLabel } from './poiSources'
import type { Tombstone } from '../lib/poiIdentity'

/** The retirement stamp as a hiker reads it, or the raw value if it is not a date.
 *
 *  `retired` is a release date (`YYYY-MM-DD`) written by the pipeline, so the
 *  unparseable branch is not expected — it is here because rendering
 *  `Invalid Date` on the card that exists to explain a disappearance would be
 *  the second confusing thing in a row. */
export function retiredWhen(retired: string): string {
  const parsed = new Date(`${retired}T00:00:00Z`)
  return Number.isNaN(parsed.getTime()) ? retired : longDate(parsed)
}

/** What happened to this place, in one sentence built from its own row. */
export function whatHappened(tombstone: Tombstone): string {
  const source = sourceLabel(tombstone.source)
  const when = retiredWhen(tombstone.retired)
  return source === null
    ? `This place was removed from the trail data on ${when}.`
    : `This place is no longer in ${source}, as of ${when}.`
}
