// Decision 31's map shot for the `national` region box, its Hawaii part, at
// zoom 5.5 (fixtures/regionCamera.mjs says what the set is for;
// map-region-national-west.mjs why the box is shot in parts).
//
// THE REGION IS THE CODE'S. region_boxes() in
// pipeline/dbt/macros/lands_outside_its_region.sql holds the Ala Kahakai
// National Historic Trail's four NPS layers (nps_ala_kahakai_kohala_hema,
// nps_ala_kahakai_alanui_aupuni, nps_ala_kahakai_kaawaloa and
// nps_ala_kahakai_kiholo_puako, the macro's `regions` map) to the `national`
// box (lat 18 to 72, lon -180 to -64), beside the nationwide layers that
// reach the islands.
//
// THIS FRAME is the main islands: at z5.5 a 390 px phone spans 6.1 degrees of
// longitude, so from -160.5 to -154.5 around a centre of -157.5 (Reasoned:
// 274.2 degrees across 390 px at z0, halved per zoom), Kauai to the Big
// Island. z5.5 is past NETWORK_SKETCH_MAX_ZOOM (5, map/style.ts), so the
// other organizations' trails draw from the network tiles here, not the
// sketch. An empty frame is an answer too: no publish has carried them.
//
// SAFE TO TAKE AGAIN, WHATEVER THE DATA BECOMES (.claude/skills/pr-screenshot/
// SKILL.md's four rules). No waypoint draws below POI_PIN_MIN_ZOOM, 7
// (map/poiLayerIds.ts), so no campsite of any kind is on the map at 5.5, and
// src/test/regionMapShots.test.ts fails this recipe if its zoom reaches the
// seam. The drive never signs in, never presses locate, and opens nobody's
// report or photo; a published serious warning draws at every zoom
// (map/warningLayers.ts) as a pin with no words and no reporter.

import { openMapAt } from './fixtures/regionCamera.mjs'

/** The box this frame shows, by its name in region_boxes(). */
export const region = 'national'
export const camera = { center: [-157.5, 20.6], zoom: 5.5 }

export const caption =
  'Region `national`, Hawaii, zoom 5.5 — Kauai to the Big Island, where the build holds the Ala Kahakai National Historic Trail’s four NPS layers (dbt/macros/lands_outside_its_region.sql). Past zoom 5 the trails draw from the network tiles rather than the sketch; an empty frame means no publish has carried them. No waypoint draws below zoom 7, so no campsite can be in this frame.'
export const alt =
  'The map screen over the main Hawaiian islands at zoom 5.5, Kauai at the left and the Big Island at the right, with any trails drawn as thin coloured threads and no waypoint pins.'

/** The network tiles at a coarse zoom read a leaf directory or two before the first line draws. */
export const wait = 6000

export default async function drive(page) {
  await openMapAt(page, camera)
}
