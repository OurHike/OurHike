// Decision 31's map shot for the `national` region box, its contiguous part
// west of the `eastern` box: the West, at zoom 2.9 (fixtures/regionCamera.mjs
// says what the set is for).
//
// THE REGION IS THE CODE'S. region_boxes() in
// pipeline/dbt/macros/lands_outside_its_region.sql holds the western and
// nationwide trail layers to `national` (lat 18 to 72, lon -180 to -64):
// USFS's and BLM's nationwide trails, COTREX, Utah's and Washington's state
// layers, the Pacific Crest, Continental Divide and Arizona trails, the Ice
// Age Trail, the national historic trails (the macro's `regions` map lists
// each). That box is the fifty states, which no one frame can hold at a zoom
// worth reading, so it is shot in the parts its sources land in: this one,
// map-region-national-alaska.mjs, map-region-national-hawaii.mjs and
// map-region-national-caribbean.mjs. The eastern box is its own recipe.
//
// THIS FRAME is the lower 48 west of the eastern box's edge at lon -90: at z2.9
// a 390 px phone spans 36.8 degrees of longitude, so from -125.9 to -89.1
// around a centre of -107.5 (Reasoned: 274.2 degrees across 390 px at z0,
// halved per zoom), the Pacific coast to the Mississippi.
//
// WHAT IT CAN SHOW. At this zoom the other organizations' trails draw from the
// network sketch (map/style.ts's NETWORK_SKETCH_MAX_ZOOM), whatever the bucket
// the preview reads holds; the question is whether a state with two
// nationwide sources over it (colorado-network.mjs's finding, at z7) still
// reads as threads at the scale a hiker picks a region from.
//
// SAFE TO TAKE AGAIN, WHATEVER THE DATA BECOMES (.claude/skills/pr-screenshot/
// SKILL.md's four rules). No waypoint draws below POI_PIN_MIN_ZOOM, 7
// (map/poiLayerIds.ts), so no campsite of any kind is on the map at 2.9, and
// src/test/regionMapShots.test.ts fails this recipe if its zoom reaches the
// seam. The drive never signs in, never presses locate, and opens nobody's
// report or photo; a published serious warning draws at every zoom
// (map/warningLayers.ts) as a pin with no words and no reporter.

import { openMapAt } from './fixtures/regionCamera.mjs'

/** The box this frame shows, by its name in region_boxes(). */
export const region = 'national'
export const camera = { center: [-107.5, 40], zoom: 2.9 }

export const caption =
  'Region `national`, the West, zoom 2.9 — the lower 48 west of the eastern box, where the build holds the nationwide and western trail layers (USFS, BLM, COTREX, Utah, Washington, the Pacific Crest and Continental Divide trails, the national historic trails; dbt/macros/lands_outside_its_region.sql). What to look for: whether two nationwide sources over one state still read as threads at the scale a hiker picks a region from. No waypoint draws below zoom 7, so no campsite can be in this frame.'
export const alt =
  'The map screen over the western United States at zoom 2.9, from the Pacific coast to the Mississippi, with trails as thin coloured threads across the mountain states and no waypoint pins.'

/** A region's worth of sketch at a coarse zoom reads several files before the first line draws. */
export const wait = 6000

export default async function drive(page) {
  await openMapAt(page, camera)
}
