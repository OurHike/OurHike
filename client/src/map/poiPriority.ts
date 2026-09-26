// The one ordering of waypoint types by how much a hiker needs to see them.
//
// Split out of poiLayers.ts when sites gave it a second reader (#607). Two
// mechanisms consult it, and they have to agree:
//
//  - which pin survives a collision, as the layer's `symbol-sort-key`
//    (poiLayers.ts)
//  - which member carries a site's pin when the anchor is filtered off the map
//    (poiSites.ts)
//
// Those are the same question - "of these, which does a hiker most need" -
// asked once by MapLibre's placement and once by the site composition, so a
// second copy of the answer is a second thing to keep in step. It cannot live
// in either module: poiLayers.ts already imports poiSites.ts, and poiSites.ts
// needing the ordering would close the loop.

/**
 * Who wins a collision, best first.
 *
 * THE MAINTAINER'S ORDER SINCE 2026-09-26 (#1676): "Can we put a priority to
 * what gets displayed full size? Shelters/Campsites, Water, Trailheads,
 * Everything else." Given with the collision engine back on the pins, shown
 * against real frames of what wins and what falls back to a dot, so where two
 * pins cannot both be placed the one that stays is the one this list names
 * first, and the other is drawn as its dot.
 *
 * It was water first until then - "water, then somewhere to sleep, then
 * supplies", the order this note said WIREFRAMES.md's lanes use too - and the change is a
 * safety-adjacent one, so it is said plainly rather than tidied away: a spring
 * whose pin would overlap a shelter's or a campsite's is now the one drawn as
 * a dot. It is still on the map, at its own coordinate, in water's colour;
 * and the water that belongs to a shelter mostly never competes at all,
 * because it is folded onto the shelter's pin as a badge (poiSites.ts).
 *
 * @unvalidated How many water pins the reorder turns into dots has not been
 * counted. What would settle it: spike_poi_seam.py's placement model run with
 * both orders over the carry and walking zooms, water pins placed under each.
 *
 * "Everything else" keeps the order it already had among itself: towns, then
 * parking, then the tail.
 */
export const POI_PRIORITY: readonly string[] = [
  // "Shelters/Campsites" is one tier in the maintainer's list. The shelter
  // goes first within it because a roof is the stronger claim, and because a
  // tie in `symbol-sort-key` would leave the winner to whatever order the
  // features happen to sit in the source.
  'shelter',
  'campsite',
  'water',
  // A trailhead is where the way off the trail reaches a road (#1197), and
  // the maintainer put it next, ahead of parking and towns.
  //
  // NOTE THIS IS STILL NOT map/labelLadder.ts's ORDER. That ladder ranks
  // LABELS for somebody choosing where to start; this ranks PINS.
  'trailhead',
  'resupply',
  // Parking above the rest of the tail because it is a way off the trail:
  // the pin a hiker looks for when the weather turns or an ankle goes.
  'parking',
  'privy',
  // Last. Vistas are the densest layer ATC publishes - 1,223 of them, half
  // again as many as every other POI put together - so at any zoom where pins
  // collide, they are what would win by sheer count if nothing decided
  // otherwise.
  'viewpoint',
]

/**
 * Where a type sits in {@link POI_PRIORITY}, lowest first.
 *
 * A type the list does not name sorts last rather than first, which is the
 * same fall-through the layer's `symbol-sort-key` expression uses for its
 * default arm - so a category added to the pipeline before it is added here
 * loses a collision to every known type instead of winning against all of
 * them.
 */
export function poiPriorityRank(type: string): number {
  const rank = POI_PRIORITY.indexOf(type)
  return rank === -1 ? POI_PRIORITY.length : rank
}
