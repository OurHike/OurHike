// One ordering for every label on the map, so they compete on one scale
// (#1194).
//
// THE PROBLEM THIS FIXES IS NOT "TOO FEW LABELS". It is that the labels this
// map draws were each given a priority by whoever built their layer, on a
// scale of their own, and MapLibre then placed them against each other as
// though those scales were comparable. Before this file:
//
//   - map/poiPriority.ts ranks waypoint PINS 0-8, water first.
//   - map/trailLabels.ts ranks trail NAMES 0-1, chosen system first, and its
//     header explains at length that it had to invert map/style.ts's line
//     ordering to do it.
//   - the live sheet's own labels (peaks, water, places) carry no sort key at
//     all, so MapLibre orders them by feature index - which is to say, by
//     whatever order the vector tile happened to encode.
//
// Three scales all starting at zero means a trail name and a shelter pin both
// claim "rank 0, place me first", and which one actually survives is decided
// by layer order rather than by anybody's judgement about what a hiker needs.
//
// THE LADDER IS THE DESIGN HANDOFF'S, WITH ONE RUNG THAT HAS NO DATA
//
// The handoff's central claim about complaint #2 - "locations were hard to
// find" - is that a hiker choosing where to START a walk needs different
// labels from a hiker already walking, and that the map should say so. Roads
// and parking are how somebody gets to a trail, so they outrank a spring.
//
// That is the opposite of map/poiPriority.ts's ordering, and both are right
// about their own question. poiPriority.ts orders PINS for a hiker on the
// trail (water first - "the pin a hiker looks for when the weather turns");
// this orders LABELS while a walk is being planned. They are deliberately not
// unified, and the difference is the whole reason this is a second file
// rather than an edit to that one.
//
// One rung of the handoff's ladder is still absent because nothing publishes
// it, written down here rather than silently skipped so the next reader knows
// where the ladder is incomplete rather than where it disagrees with the
// handoff. It was two until #1197:
//
//   - TRAILHEADS ARE NO LONGER ONE OF THEM (#1197). This said the pipeline
//     published eight types and `trailhead` was not among them, which was
//     true when the ladder was written and is the rung it most wanted: "roads
//     exist specifically so a user can find a start point", and the start
//     point itself was the thing missing from the map. There is a ninth type
//     now, and OPRHP's 287 trailheads ship in `nearby_poi.geojson` - so the
//     top rung is filled by the class it was reserved for.
//   - JUNCTIONS. pipeline/build_trail_graph.py splits every line at every
//     crossing, so junctions exist as graph NODES and route the walk, but
//     nothing publishes them as features and no layer draws them.
//
// The junction rung is named on #1194 rather than fudged, and #1213 is where
// it would be filled. A rung with no data draws nothing whether or not it has
// a number here.

/**
 * The rungs, lowest number first - and lower WINS.
 *
 * MapLibre's `symbol-sort-key` places lower values first, and a symbol that
 * cannot be placed is dropped, so "lower is better" is the direction of the
 * whole scale. map/trailLabels.ts's header is the standing warning about
 * this: `line-sort-key` runs the other way, and copying one into the other
 * silently gives the most important thing the worst claim on space.
 *
 * SPACED BY TENS, on purpose. A rung is a band rather than a value, so a
 * layer can rank WITHIN its tier - `poiLabelSortKey` puts a chosen stop above
 * an unchosen shelter without either leaving its rung - and a rung inserted
 * later does not renumber the ones below it.
 */
export const LABEL_TIER = {
  /** Tier 1: how a hiker gets to the trail at all. Parking, road names. */
  gateway: 10,
  /** Tier 2: the walk itself. A chosen stop's name, the mile numbers. */
  route: 20,
  /** Tier 3: names of trails the walk uses. */
  routeTrail: 30,
  /** Tier 4: peaks, overlooks, and waypoints the walk does not stop at. */
  landmark: 40,
  /** Tier 5: junctions. No data - see this file's header. */
  junction: 50,
  /** Tier 6: names of trails the walk does not use. */
  otherTrail: 60,
  /** Tier 7: everything else with a name. */
  rest: 70,
} as const

export type LabelTier = keyof typeof LABEL_TIER

/**
 * The zoom each tier starts drawing at.
 *
 * THE HANDOFF'S THREE ZOOM STEPS ARE NOT PORTED AS A CONTROL, and this is the
 * one place its prototype and a real map engine genuinely disagree. The
 * prototype has `zoom: 1 | 2 | 3` and `+`/`-` buttons that step it, because
 * it draws its own map and had to invent a notion of scale. MapLibre has a
 * continuous zoom that a hiker already pinches, and its own note says to use
 * the engine's placement rather than reimplement the placer.
 *
 * So the three tiers become three zoom thresholds on one continuous axis, and
 * the `+`/`-` buttons become the map's existing zoom. A hiker zooming in gets
 * the handoff's "park -> route -> section" progression without a second,
 * competing idea of zoom on the screen.
 *
 * The numbers are POI_PIN_MIN_ZOOM (9) and the two steps above it, which is
 * not a coincidence: pins and their names should arrive together, and
 * map/trailLabels.ts already borrowed the same constant for the same reason.
 *
 * `@unvalidated` as display choices, inheriting TRAIL_LABEL_MIN_ZOOM's
 * caveat exactly: picked to match thresholds this map already uses, not
 * measured against how a hiker actually zooms while planning.
 */
export const TIER_MIN_ZOOM: Record<LabelTier, number> = {
  gateway: 9,
  route: 9,
  routeTrail: 9,
  landmark: 11,
  junction: 13,
  otherTrail: 11,
  rest: 13,
}

/**
 * What the on-map legend says the current zoom is showing.
 *
 * The handoff surfaces its three steps to the hiker as "Zoom: park/route/
 * section" with a line describing each. That part ports unchanged - it is a
 * readout, not a control - and reading it off the live zoom means it cannot
 * disagree with what is actually drawn.
 */
export type ZoomBand = 'park' | 'route' | 'section'

export function zoomBand(zoom: number): ZoomBand {
  if (zoom < TIER_MIN_ZOOM.landmark) return 'park'
  if (zoom < TIER_MIN_ZOOM.junction) return 'route'
  return 'section'
}

export const ZOOM_BAND_TEXT: Record<ZoomBand, string> = {
  park: 'Trailheads, parking, roads and your route',
  route: 'Adds trail names, peaks, shelters and campsites',
  section: 'Adds water and the finer sheet',
}
