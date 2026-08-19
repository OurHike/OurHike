// What the line-detail sheet says about the line a hiker tapped (#134).
//
// WIREFRAMES.md §3's blaze rules are the requirement: "tapping any line
// opens a sheet naming the blaze and its source, and says plainly when it's
// unknown." For a spur, features/SPUR_TRAILS.md §3 adds the facts the sheet
// exists for - where it goes, how far there and back, and where it joins
// the AT:
//
//   Blue blaze · spur
//   To Rocky Run Shelter — 0.2 mi each way
//   ≈20m there and back
//   Joins the AT at mi 1,043.2
//
// Built here rather than in the component for the same reason PoiCard's
// detail is resolved in the shell: the map knows what is drawn, and the app
// is what knows a line's spur record, its destination's name and the units
// the hiker chose. Everything the sheet renders is a string decided in this
// file, so the decisions are testable without a canvas.
//
// Three decisions carried over from #111 rather than relitigated (the
// issue's own list):
// - NO destination line at all when nothing resolved - not "Unknown
//   destination", which reads as a data error rather than the ordinary
//   situation it is for ~12% of spurs.
// - NO length threshold at either end. The median spur is 385 ft and the
//   longest 4.53 miles; suppressing either end's numbers buys nothing.
// - The round trip is ONE figure, not two legs - splitting it needs the
//   spur's own elevation profile, which does not exist.

import { describeSpur, type SpurRecord } from './spurDestination'
import type { StoredPoi } from './trailData'
import type { UnitSystem } from './units'

/** The tapped feature's published properties, as map/lineTaps.ts reports
 *  them. Redeclared here rather than imported so this module stays free of
 *  the map layer - the same direction poiTaps keeps. */
export interface TappedLineFacts {
  id: string | null
  source: string | null
  name: string | null
  blazeColor: string | null
}

export interface LineDetail {
  /** "Blue blaze · spur", "White blaze · Appalachian Trail", "Blaze not
   *  recorded · side trail" - the sheet's heading. */
  heading: string
  /** ATC's own name for the line, where they gave one. */
  name: string | null
  /** "To Rocky Run Shelter — 0.2 mi each way", or the distance alone when
   *  no destination was confidently resolved, or null with no length. */
  destinationLine: string | null
  /** "≈20m there and back", or null with no length. */
  roundTripLine: string | null
  /** "Joins the AT at mi 1,043.2", or null when the pipeline could not
   *  tell the spur's ends apart or the release predates the field (#136). */
  junctionLine: string | null
  /** "From the Appalachian Trail Conservancy’s …" - the provenance line,
   *  same shape as PoiCard's. */
  sourceLine: string | null
}

/**
 * Sources drawn at the through-route width (map/style.ts's
 * PRIMARY_TRAIL_SOURCES). Restated rather than imported for the reason
 * TappedLineFacts is: this module must not pull the map style in. The two
 * lists are pinned to each other by lineDetail.test.ts.
 */
export const THROUGH_ROUTE_SOURCES: readonly string[] = ['centerline']

/**
 * How each blaze_color is named. The pipeline's contract (lib/blaze.ts)
 * says "None" is CONFIRMED unblazed while "Unknown" is a value that failed
 * to decode - different claims, and the sheet keeps them apart: WIREFRAMES
 * requires saying plainly when the blaze is unknown, and "Unblazed" would
 * be a confident statement nobody made.
 */
function blazeLabel(blazeColor: string | null): string {
  if (blazeColor === null || blazeColor === 'Unknown') return 'Blaze not recorded'
  if (blazeColor === 'None') return 'Unblazed'
  if (blazeColor === 'Other') return 'Other blaze'
  return `${blazeColor} blaze`
}

/**
 * Where the line's data comes from, in the words the waypoint card already
 * uses for its sources. Both feeds are ATC's - the same FeatureServer family
 * chrome/poiSources.ts names - and an unfamiliar future source shows its raw
 * id rather than nothing, the same call sourceLabel() makes.
 */
function lineSourceLabel(source: string | null): string | null {
  if (source === null) return null
  if (source === 'centerline')
    return 'the Appalachian Trail Conservancy’s trail centerline'
  if (source === 'side_trails')
    return 'the Appalachian Trail Conservancy’s side trails data'
  return source
}

/** A mile marker, grouped with one decimal - the same rendering PoiCard and
 *  the position line give a mile, so three surfaces show one number. Mile
 *  markers do not convert (lib/units.ts's opening rule): `mi 1,043.2` is a
 *  shared coordinate, not a distance. */
function formatMileMarker(mile: number): string {
  return mile.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
}

/**
 * Everything the sheet can say about one tapped line.
 *
 * Every field is independently nullable because the underlying facts are
 * independently missing, and each absent fact costs its own line rather
 * than the sheet - the same shape describeSpur() keeps.
 */
export function buildLineDetail(
  line: TappedLineFacts,
  spurs: Record<string, SpurRecord>,
  pois: readonly StoredPoi[],
  units: UnitSystem = 'imperial',
  trailName = 'Appalachian Trail',
): LineDetail {
  const throughRoute = line.source !== null && THROUGH_ROUTE_SOURCES.includes(line.source)
  const spur = line.id !== null ? spurs[line.id] : undefined

  // The kind, for the heading: the through-route is named as the trail it
  // is; a side trail with a spur record is what SPUR_TRAILS.md calls a
  // spur; the rest are side trails - Access approaches, alternate routes -
  // that ATC classifies as something else.
  const kind = throughRoute ? trailName : spur !== undefined ? 'spur' : 'side trail'

  const detail = describeSpur(spur, units)
  const destination =
    detail.destinationPoiId === null
      ? undefined
      : pois.find((poi) => poi.id === detail.destinationPoiId)

  // "To X — 0.2 mi each way" only when a destination was confidently
  // resolved AND this phone's POI store can actually name it - a release
  // downloaded before the destination's layer shipped has the id and not
  // the name, and "To atc_shelters:abc-123" is worse than the distance
  // alone.
  const destinationLine =
    detail.distanceLabel === null
      ? null
      : destination === undefined
        ? detail.distanceLabel
        : `To ${destination.name} — ${detail.distanceLabel}`

  const junctionMile = spur?.junction_mile
  const junctionLine =
    typeof junctionMile === 'number' && Number.isFinite(junctionMile)
      ? `Joins the AT at mi ${formatMileMarker(junctionMile)}`
      : null

  const source = lineSourceLabel(line.source)

  return {
    heading: `${blazeLabel(line.blazeColor)} · ${kind}`,
    // The through-route's name is already the heading; repeating ATC's
    // formal name under it ("Appalachian National Scenic Trail") would be
    // the same fact twice in adjacent lines.
    name: throughRoute ? null : (spur?.name ?? line.name),
    destinationLine,
    roundTripLine: detail.roundTripLabel,
    junctionLine,
    sourceLine: source === null ? null : `From ${source}.`,
  }
}
