// Decision 31's map shot for the `national` region box, its Alaska part, at
// zoom 2.7 (fixtures/regionCamera.mjs says what the set is for;
// map-region-national-west.mjs why the box is shot in parts).
//
// THE REGION IS THE CODE'S. region_boxes() in
// pipeline/dbt/macros/lands_outside_its_region.sql holds `alaska_trails` (the
// Alaska Trails organization's own layer) and `blm_iditarod_nht` to the
// `national` box (lat 18 to 72, lon -180 to -64), as it does the nationwide
// USFS and NPS layers that reach the Chugach and the Tongass.
//
// WHY ALASKA NEEDS A FRAME OF ITS OWN. The app opens on the lower 48
// (App.tsx's UNITED_STATES_BOUNDS), and that constant's comment measured the
// trade: framing Alaska would shrink the rest of the country to a thumbnail,
// so its vertices "fall off the edge". The standing trail-screen.mjs shot
// therefore never shows any of it. At z2.7 a 390 px phone spans 42.2 degrees
// of longitude, so from -172.1 to -129.9 around a centre of -151 (Reasoned:
// 274.2 degrees across 390 px at z0, halved per zoom): the mainland and the
// southeast panhandle, the Aleutians' far end aside.
//
// WHAT IT CAN SHOW: whatever the bucket the preview reads holds, drawn from
// the network sketch at this zoom (map/style.ts's NETWORK_SKETCH_MAX_ZOOM). An
// empty Alaska is an answer too: it means no publish has carried its lines.
//
// SAFE TO TAKE AGAIN, WHATEVER THE DATA BECOMES (.claude/skills/pr-screenshot/
// SKILL.md's four rules). No waypoint draws below POI_PIN_MIN_ZOOM, 7
// (map/poiLayerIds.ts), so no campsite of any kind is on the map at 2.7, and
// src/test/regionMapShots.test.ts fails this recipe if its zoom reaches the
// seam. The drive never signs in, never presses locate, and opens nobody's
// report or photo; a published serious warning draws at every zoom
// (map/warningLayers.ts) as a pin with no words and no reporter.

import { openMapAt } from './fixtures/regionCamera.mjs'

/** The box this frame shows, by its name in region_boxes(). */
export const region = 'national'
export const camera = { center: [-151, 62], zoom: 2.7 }

export const caption =
  'Region `national`, Alaska, zoom 2.7 — ground the app’s opening camera leaves off its edge (App.tsx’s UNITED_STATES_BOUNDS), so no standing shot shows it. The build holds Alaska Trails’ own layer and the Iditarod National Historic Trail to this box, beside the nationwide USFS and NPS layers (dbt/macros/lands_outside_its_region.sql). An empty Alaska is an answer: no publish has carried its lines. No waypoint draws below zoom 7, so no campsite can be in this frame.'
export const alt =
  'The map screen over Alaska at zoom 2.7, from the Bering Sea to the southeast panhandle, with any trails drawn as thin coloured threads and no waypoint pins.'

/** A region's worth of sketch at a coarse zoom reads several files before the first line draws. */
export const wait = 6000

export default async function drive(page) {
  await openMapAt(page, camera)
}
