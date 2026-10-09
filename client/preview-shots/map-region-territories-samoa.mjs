// Decision 31's map shot for the `us_and_territories` region box, its South
// Pacific part: American Samoa, at zoom 6.5 (fixtures/regionCamera.mjs says
// what the set is for; map-region-territories-marianas.mjs what the box holds).
//
// THE REGION IS THE CODE'S. pipeline/dbt/macros/lands_outside_its_region.sql's
// header measured NPS's trails from lat -14.37 to 65.85 and lon -170.77 to
// 145.73: lat -14.37 and lon -170.77 are both American Samoa's (Reasoned from
// the islands' coordinates, not from the rows), and no box narrower than
// `us_and_territories` (lat -20 to 72, any longitude) holds them. The
// `national` box stops at lat 18, so this frame is entirely that box's own
// ground.
//
// THIS FRAME: at z6.5 a 390 px phone spans 3.0 degrees of longitude, so from
// -171.7 to -168.7 around a centre of -170.2 (Reasoned: 274.2 degrees across
// 390 px at z0, halved per zoom): Tutuila to the west, the Manu'a islands to
// the east. Past NETWORK_SKETCH_MAX_ZOOM (5, map/style.ts) the trails draw from
// the network tiles. An empty frame is an answer too: it says the island's
// trails are loaded and no publish has carried them.
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
export const camera = { center: [-170.2, -14.3], zoom: 6.5 }

export const caption =
  'Region `us_and_territories`, American Samoa, zoom 6.5 — one corner of NPS’s trails’ measured extent, lat −14.37 and lon −170.77, which only the widest region box holds (dbt/macros/lands_outside_its_region.sql). Past zoom 5 the trails draw from the network tiles; an empty frame means no publish has carried them. No waypoint draws below zoom 7, so no campsite can be in this frame.'
export const alt =
  'The map screen over American Samoa at zoom 6.5, Tutuila at the left and the Manu’a islands at the right in open ocean, with any trails drawn as thin coloured threads and no waypoint pins.'

/** The network tiles at a coarse zoom read a leaf directory or two before the first line draws. */
export const wait = 6000

export default async function drive(page) {
  await openMapAt(page, camera)
}
