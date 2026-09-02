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
 * This is a safety ordering, not a visual one. When two pins cannot both be
 * placed, the one that stays is the one a hiker most needs: water, then
 * somewhere to sleep, then supplies. WIREFRAMES.md's lanes make the same call
 * in the same order.
 */
export const POI_PRIORITY: readonly string[] = [
  'water',
  'shelter',
  'campsite',
  'resupply',
  // Parking above the rest of the tail because it is the way off the trail:
  // the pin a hiker looks for when the weather turns or an ankle goes, which
  // is the same argument water and shelter win on.
  'parking',
  // A trailhead is the same argument again and one step further along it: it
  // is where the way off the trail actually reaches a road (#1197). Below
  // parking rather than above it only because a lot is where a car is, and a
  // car is what a hiker in trouble is trying to reach.
  //
  // NOTE THIS IS NOT map/labelLadder.ts's ORDER, and the difference is
  // deliberate on both sides. That ladder ranks LABELS for somebody choosing
  // where to start, so a trailhead sits at its top rung. This ranks PINS for
  // somebody already walking, where water and a roof outrank the way in.
  'trailhead',
  'privy',
  'crossing',
  // Last, and the ordering earns its keep here for the first time. Vistas are
  // the densest layer ATC publishes - 1,223 of them, half again as many as
  // every other POI put together - so at any zoom where pins collide, they
  // are what would win by sheer count if nothing decided otherwise. A hiker
  // losing a spring to an overlook is the exact trade this list exists to
  // refuse.
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
