// Decision 31's map shot for the `national` region box, its Caribbean part:
// Puerto Rico and the U.S. Virgin Islands, at zoom 6.5
// (fixtures/regionCamera.mjs says what the set is for;
// map-region-national-west.mjs why the box is shot in parts).
//
// THE REGION IS THE CODE'S. pipeline/dbt/macros/lands_outside_its_region.sql's
// header names the trail here: USFS's in Puerto Rico, at lat 18.27, inside the
// `national` box (lat 18 to 72, lon -180 to -64) with the nationwide layer it
// belongs to. The islands straddle that box's southern edge, which is why the
// same header gives NWS's alerts the wider `us_and_territories` box: an alert
// on Puerto Rico's south coast reaches below lat 18. This frame's centre, lat
// 18.2, is inside `national`, which is the box it is filed under.
//
// THIS FRAME: at z6.5 a 390 px phone spans 3.0 degrees of longitude, so from
// -67.4 to -64.4 around a centre of -65.9 (Reasoned: 274.2 degrees across
// 390 px at z0, halved per zoom), Mona Passage to St. Croix. Past
// NETWORK_SKETCH_MAX_ZOOM (5, map/style.ts) the other organizations' trails
// draw from the network tiles. An empty frame is an answer too.
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
export const region = 'national'
export const camera = { center: [-65.9, 18.2], zoom: 6.5 }

export const caption =
  'Region `national`, Puerto Rico and the U.S. Virgin Islands, zoom 6.5 — USFS’s trails in Puerto Rico sit inside the national box at lat 18.27, and NWS’s alerts here reach below its edge at lat 18 (dbt/macros/lands_outside_its_region.sql). Past zoom 5 the trails draw from the network tiles; an empty frame means no publish has carried them. No waypoint draws below zoom 7, so no campsite can be in this frame.'
export const alt =
  'The map screen over Puerto Rico and the U.S. Virgin Islands at zoom 6.5, Puerto Rico filling the left of the frame and St. Thomas, St. John and St. Croix to the right, with any trails drawn as thin coloured threads and no waypoint pins.'

/** The network tiles at a coarse zoom read a leaf directory or two before the first line draws. */
export const wait = 6000

export default async function drive(page) {
  await openMapAt(page, camera)
}
