// Decision 31's map shot for the `us_and_territories` region box, its western
// Pacific part: Guam and the Northern Mariana Islands, at zoom 6.5
// (fixtures/regionCamera.mjs says what the set is for).
//
// THE REGION IS THE CODE'S. region_boxes() in
// pipeline/dbt/macros/lands_outside_its_region.sql gives a layer that reaches
// the territories `us_and_territories` (lat -20 to 72, any longitude), and its
// header says why NPS's trails need it: measured from lat -14.37 to 65.85 and
// lon -170.77 to 145.73, American Samoa to the Marianas. The same box holds
// every generated places and elevation source (pipeline/ELT.md, "Region boxes
// from vertices") and NPS's campgrounds. Its own ground is what `national`
// (lat 18 to 72, lon -180 to -64) leaves out, and this frame is that ground
// in the western Pacific, at lon 145, far outside the national box.
// map-region-territories-samoa.mjs is its part in the South Pacific.
//
// THIS FRAME: at z6.5 a 390 px phone spans 3.0 degrees of longitude, so from
// 143.9 to 146.9 around a centre of 145.4, and the portrait screen about lat
// 12 to 17 (Reasoned: 274.2 degrees across 390 px at z0, halved per zoom, and
// the same arithmetic over the phone's height): Guam at the foot, Rota, Tinian
// and Saipan above it. Past NETWORK_SKETCH_MAX_ZOOM (5, map/style.ts) the
// trails draw from the network tiles. An empty frame is an answer too: it
// says the islands' trails are loaded and no publish has carried them.
//
// SAFE TO TAKE AGAIN, WHATEVER THE DATA BECOMES (.claude/skills/pr-screenshot/
// SKILL.md's four rules). No waypoint draws below POI_PIN_MIN_ZOOM, 7
// (map/poiLayerIds.ts), so no campsite of any kind is on the map at 6.5, half
// a zoom short of the seam, and src/test/regionMapShots.test.ts fails this
// recipe if its zoom ever reaches it. The drive never signs in, never presses
// locate, and opens nobody's report or photo; a published serious warning
// draws at every zoom (map/warningLayers.ts) as a pin with no words and no
// reporter.

import { openMapAt } from './fixtures/regionCamera.mjs'

/** The box this frame shows, by its name in region_boxes(). */
export const region = 'us_and_territories'
export const camera = { center: [145.4, 14.5], zoom: 6.5 }

export const caption =
  'Region `us_and_territories`, Guam and the Northern Mariana Islands, zoom 6.5 — ground outside the national box, which the build holds NPS’s trails to because they reach from American Samoa to the Marianas (lon 145.73; dbt/macros/lands_outside_its_region.sql). Past zoom 5 the trails draw from the network tiles; an empty frame means no publish has carried them. No waypoint draws below zoom 7, so no campsite can be in this frame.'
export const alt =
  'The map screen over the Mariana Islands at zoom 6.5, Guam near the foot of the frame and Rota, Tinian and Saipan above it in open ocean, with any trails drawn as thin coloured threads and no waypoint pins.'

/** The network tiles at a coarse zoom read a leaf directory or two before the first line draws. */
export const wait = 6000

export default async function drive(page) {
  await openMapAt(page, camera)
}
