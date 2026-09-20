// How crowded the ground around a waypoint is, so the pins can be given air
// where they need it and nowhere else (#1536).
//
// THE PROBLEM, measured. `icon-allow-overlap: false` packs pins until nothing
// more fits and has no notion of ENOUGH. On the densest z12 screen in New York
// City - Red Hook to Prospect Park - that is 63 pins covering 30% of a
// 390x700 phone, sitting a median 51 px apart when a pin is 36 px wide.
// features/POI_VISIBILITY.md's own table calls ~16 pins a full column.
//
// WHY THIS IS NOT A ZOOM RULE, which is the obvious fix and was measured
// before being rejected. A blanket `icon-padding: 24` costs the Appalachian
// Trail half its pins at z9 - 20 down to 10 on the corridor's own densest
// screen - and z9 is the seam features/POI_VISIBILITY.md sized to fit a day's
// hike. There is no zoom band that is crowded in the city and empty on the
// trail, because the two are crowded at DIFFERENT zooms.
//
// WHY THIS IS NOT A LIST OF CITY SOURCES EITHER. `['match', ['get','source'],
// ['nyc_drinking_fountains', ...], 24, 2]` needs no measurement and no
// artifact, and it encodes "New York" where the truth is "dense" - so the next
// dense city is a code change, and the comment explaining it could only say
// that somebody complained about these two layers.
//
// WHAT IT IS INSTEAD: a per-feature count, and the reason it can be is that
// `icon-padding` is `property-type: data-driven` in the maplibre-gl 6.7 this
// app ships (checked against the style spec, not assumed). A per-feature
// padding needs no second symbol layer, which map/poiLayers.ts's header would
// not permit and for good reason.
//
// WHY IT IS COMPUTED HERE AND NOT IN THE PIPELINE. pipeline/lib/poi_sites.py's
// header argues at length against computing things on a phone, and every word
// of it is about GROUPING: "no id that survives a pan, re-clusters at every
// zoom, answers 'how many' when the question at a shelter is 'is there a
// privy'." None of that applies to a scalar. This makes no mark, carries no
// id, and is computed once over the whole loaded set from fixed coordinates -
// so it is identical after a pan and after a zoom.
//
// It also gets one thing the pipeline could not: poiFeatureCollection rebuilds
// when the hidden set changes, so the count is over the waypoints the hiker
// can actually SEE. A pipeline figure would count categories they had turned
// off and give air against pins that are not there.

import type { MapPoint } from '../lib/legendContents'

/**
 * How far out a waypoint counts its neighbours, in metres.
 *
 * DERIVED from the two maps this has to tell apart, measured 2026-09-17
 * against release 2026-09-16-4 with the folds the pipeline actually publishes
 * applied, over the Appalachian Trail's own 563 marks and New York City's
 * 2,477:
 *
 * | radius | A.T. max | city median |
 * |--------|---------:|------------:|
 * | 300 m  |        5 |           2 |
 * | 500 m  |        5 |           4 |
 * | 800 m  |        5 |      **10** |
 *
 * 800 m is the smallest radius tried at which the city's MEDIAN clears the
 * trail's MAXIMUM. Below it the two overlap, and a signal that overlaps is a
 * signal that would quietly take pins off the Appalachian Trail.
 *
 * It is also the ground one pin competes over: an 800 m radius at z12 is
 * 55 px, an area that holds about SIX 40 px collision boxes. So "more than a
 * handful of waypoints within this radius" is the same statement as "these
 * cannot all be pins at a planning zoom", which is the question worth asking.
 */
export const CROWDING_RADIUS_M = 800

/**
 * The count at or below which a waypoint is drawn exactly as it is today.
 *
 * CLEAR OF TWO MEASURED FLOORS, and it is the whole of this feature's safety
 * argument.
 *
 * The first is the trail itself. Over all 563 marks ATC publishes on the
 * Appalachian Trail - shelters, campsites, privies and opentrail's water, with
 * export_poi.py's own site folding applied - the neighbour count at
 * {@link CROWDING_RADIUS_M} runs median 1, p90 2, p99 4, MAXIMUM 5 (measured
 * 2026-09-17 against release 2026-09-16-4). So every A.T. waypoint sits under
 * this anchor with three neighbours to spare and is padded at exactly
 * {@link BASE_PADDING_PX}.
 *
 * The second is geometry. An 800 m radius at z12 is 55 px, and that circle
 * holds about six 40 px collision boxes - so ground with more waypoints than
 * this in it could not draw them all as pins whatever this file did.
 *
 * Eight is the smallest round number clear of both.
 *
 * WHAT THIS DOES NOT SAY, because the first draft of this comment said it and
 * it was wrong. It is not "nothing in poi_*.geojson changes". Those files also
 * carry 185 OSM drinking-water points that reach the corridor through #1016's
 * widened gate - near SOME organisation's trail, not near the A.T. - and one
 * cluster of them in Chenango County, New York, runs to 24 neighbours: 165 km
 * from the Appalachian Trail and denser than anything on it. The worst z14
 * screen in the whole corridor file is that cluster, 18 marks, every one OSM
 * water and not one of them ATC's, and this ramp takes it from 4 pins to 2.
 *
 * That is the feature working rather than a regression. Nineteen drinking-water
 * nodes inside 800 m is crowded ground by any reading, and giving it air is
 * what this is for - the rule is about density, not about which file a
 * waypoint arrived in.
 *
 * Ground that gets denser than today degrades a pixel at a time rather than
 * falling off a cliff: a mark at 9 neighbours pads at 6 px, not 36.
 */
export const QUIET_NEIGHBOURS = 8

/**
 * Where the full allowance applies.
 *
 * REASONED: twice {@link QUIET_NEIGHBOURS}, so the rule reads "twice as
 * crowded as the busiest ground this map has any right to expect". Measured
 * against New York City's own distribution - median 10, p90 21, max 42 - it
 * lands around the 80th percentile, so the crowdedest fifth of the city's
 * marks get the full box and the rest ride up the ramp. The factor of two is
 * the argument; the percentile is the check on it.
 */
export const CROWDED_NEIGHBOURS = QUIET_NEIGHBOURS * 2

/**
 * Where a staleness ring stops being drawn at all (2026-09-20).
 *
 * ITS OWN NUMBER RATHER THAN {@link CROWDED_NEIGHBOURS}, because the two
 * answer different questions. Padding asks "how much air should this mark
 * reserve", and degrading a pixel at a time up to 16 is right for that. The
 * ring asks "can a rim around this mark still be READ", and the answer stops
 * being yes much sooner, because a ring is 44 px across and two marks 44 px
 * apart already overlap.
 *
 * MEASURED, on the frame the maintainer sent on 2026-09-20: the A.T. through
 * New York City, where the map draws the city's municipal water points. At
 * the previous ramp - full ring at 8 neighbours, gone at 16 - New York's own
 * distribution (median 10, p90 21, max 42, the figures CROWDED_NEIGHBOURS was
 * set against) left the MEDIAN city mark still drawing three quarters of its
 * ring. Hundreds of those at 75% stack into flat colour, which is what that
 * frame is: the rings are the wall, not the pins.
 *
 * 10 puts the median city mark at zero and leaves the corridor untouched: the
 * A.T.'s own neighbour counts run median 1, p90 2, max 5 (poiCrowding's
 * measurement above), so no waypoint on the trail this app is about ever
 * reaches the 8 where the fade even begins.
 *
 * WHAT IS LOST, said plainly because it is a safety-adjacent display: on
 * ground this crowded a hiker no longer sees at a glance how fresh a report
 * is. They lose the rim, not the fact - the pin is still drawn, and the card
 * behind it still carries the staleness in words. A rim nobody can separate
 * from its neighbours was not carrying that fact either.
 */
export const RING_GONE_NEIGHBOURS = 10

/** What every pin reserves today, and what a quiet one goes on reserving:
 *  `icon-padding` as map/poiLayers.ts has always set it. */
export const BASE_PADDING_PX = 2

/**
 * The padding a fully crowded waypoint reserves.
 *
 * DERIVED from features/POI_VISIBILITY.md's own figure rather than tuned to a
 * pin count. That doc's arithmetic is that about 16 pins fit down the column
 * at a hiking zoom. A symbol reserves a square of `(38 + 2 * padding) * scale`
 * px, and at z12 the icon-size ramp is at 0.95 - so at 36 px of padding a
 * saturated 390x700 screen holds floor(390/104.5) * floor(700/104.5) = 3 * 6 =
 * 18 boxes. Eighteen is that doc's ~16 within rounding, and that is the whole
 * derivation: the crowded box is the box at which a screen that fills up holds
 * about what POI_VISIBILITY.md calls a full column.
 *
 * Measured end to end against the real worst screen - the published records
 * through the pipeline's fold and this ramp - it lands at 32 pins rather than
 * 18, because a real screen is not a perfect grid and because most city marks
 * sit partway up the ramp and reserve less. 638 marks at 63 pins covering 30%
 * of the screen become 374 marks at 32 pins covering 15%.
 *
 * The mockup features/mockups/city-water-density.html shows 24 and was
 * approved at 24, and the difference is not a change of mind: that page
 * applied one flat padding to every mark on the screen, which is precisely
 * what {@link QUIET_NEIGHBOURS}'s measurement forbids. A ramp that leaves the
 * Appalachian Trail alone has to spend more at its top to reach the same
 * place, and 36 is where it reaches it.
 */
export const CROWDED_PADDING_PX = 36

/** Where the count rides on a drawn feature, for the layer's expression. */
export const CROWDING_PROPERTY = 'crowding'

/**
 * `icon-padding`, as a function of the count above.
 *
 * `coalesce` to {@link QUIET_NEIGHBOURS} rather than to 0, and the direction
 * matters: a feature built by an older code path that never set the property
 * lands at the quiet end and is padded exactly as it is today, instead of
 * being treated as the emptiest possible ground and padded the same way - the
 * two happen to agree here, and saying which one is meant is what stops the
 * next edit to the ramp's low end changing the fallback by accident.
 */
export const POI_ICON_PADDING_EXPRESSION: unknown[] = [
  'interpolate',
  ['linear'],
  ['coalesce', ['get', CROWDING_PROPERTY], QUIET_NEIGHBOURS],
  QUIET_NEIGHBOURS,
  BASE_PADDING_PX,
  CROWDED_NEIGHBOURS,
  CROWDED_PADDING_PX,
]

/**
 * How many other drawn marks sit within {@link CROWDING_RADIUS_M} of each,
 * keyed by waypoint id.
 *
 * Bucketed rather than compared pair by pair: the drawn set is a few thousand
 * marks and the corridor runs 2,190 miles, so an all-pairs pass is millions of
 * comparisons on the main thread every time the legend is tapped. A grid whose
 * cell is the radius means each mark reads the nine cells around it, and the
 * marks in them are the only ones that can be within range.
 *
 * Latitude-only cell sizing on purpose: a degree of longitude is 18% narrower
 * in Maine than in Georgia, so a cell sized in degrees of longitude would be
 * the wrong shape at one end of the corridor. Sizing both axes by the latitude
 * degree makes cells that are too WIDE in longitude, never too narrow - a cell
 * that is too wide costs a few extra distance checks, and one that is too
 * narrow silently misses a neighbour.
 */
export function crowdingByPoi(drawn: readonly MapPoint[]): Map<string, number> {
  const cell = CROWDING_RADIUS_M / METRES_PER_DEGREE
  const grid = new Map<string, MapPoint[]>()
  for (const poi of drawn) {
    const key = cellKey(Math.floor(poi.lon / cell), Math.floor(poi.lat / cell))
    const bucket = grid.get(key)
    if (bucket === undefined) grid.set(key, [poi])
    else bucket.push(poi)
  }

  const counts = new Map<string, number>()
  for (const poi of drawn) {
    const gx = Math.floor(poi.lon / cell)
    const gy = Math.floor(poi.lat / cell)
    // Starts at -1 because the nine cells include this waypoint's own.
    let near = -1
    for (let dx = -1; dx <= 1; dx += 1) {
      for (let dy = -1; dy <= 1; dy += 1) {
        const bucket = grid.get(cellKey(gx + dx, gy + dy))
        if (bucket === undefined) continue
        for (const other of bucket) {
          if (metresBetween(poi, other) <= CROWDING_RADIUS_M) near += 1
        }
      }
    }
    counts.set(poi.id, Math.max(0, near))
  }
  return counts
}

const METRES_PER_DEGREE = 111_320

function cellKey(x: number, y: number): string {
  return `${x},${y}`
}

/**
 * Flat-earth metres, which is the right approximation at this radius: over
 * 800 m the error against a great circle is under a millimetre, and the
 * result is compared against a threshold whose own provenance is a
 * distribution.
 */
function metresBetween(a: MapPoint, b: MapPoint): number {
  const midLat = ((a.lat + b.lat) / 2) * (Math.PI / 180)
  const dx = (a.lon - b.lon) * METRES_PER_DEGREE * Math.cos(midLat)
  const dy = (a.lat - b.lat) * METRES_PER_DEGREE
  return Math.hypot(dx, dy)
}
