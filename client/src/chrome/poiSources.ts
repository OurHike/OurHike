// Who said this POI is there, in words a hiker can weigh.
//
// Kept out of PoiCard.tsx so that file exports only a component (React Fast
// Refresh breaks on modules that mix the two), same as legendLabels.ts.
//
// The ids are the pipeline's own `source` values (pipeline/lib/poi_schema.py's
// `unify_poi`, wired up in export_poi.py). They are stable - a POI id is built
// from one, and a Report references that id - so this map is not chasing a
// moving target.
//
// The wording is doing real work rather than decorating. "Where did this claim
// come from" is the question behind OurHikeValues.md #4, and the two ATC
// sources are NOT interchangeable: shelters and campsites are the ATC's own
// facility data about a thing they maintain, while an "A.T. Community" is a
// town that applied for a designation - a proxy for resupply, which is exactly
// why the pipeline files it at low confidence. Saying "the ATC" for both would
// flatten the one distinction this line exists to make.

export const SOURCE_LABELS: Record<string, string> = {
  atc_shelters: 'the Appalachian Trail Conservancy’s shelter data',
  atc_campsites: 'the Appalachian Trail Conservancy’s campsite data',
  atc_communities: 'the Appalachian Trail Conservancy’s list of A.T. Community towns',
  opentrail_at: 'opentrail.org, tagged by hikers',
}

/**
 * A source id as a sentence fragment, or null when there is nothing to say.
 *
 * An unknown id comes back as itself rather than as null: a release that adds
 * a source should show a hiker something, the same call the map makes when it
 * draws an unknown POI type as a neutral pin instead of nothing. A raw id is a
 * poor label and still tells someone more than silence does.
 */
export function sourceLabel(source: string | undefined): string | null {
  if (source === undefined || source.trim() === '') return null
  return SOURCE_LABELS[source] ?? source
}
