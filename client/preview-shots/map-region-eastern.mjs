// Decision 31's map shot for the `eastern` region box: the A.T. states and the
// Northeast, at zoom 3.5 (fixtures/regionCamera.mjs says what the set is for).
//
// THE REGION IS THE CODE'S, NOT A GUESS. Every geometry mart holds each
// source's rows to one of three boxes, region_boxes() in
// pipeline/dbt/macros/lands_outside_its_region.sql, and `eastern` (lat 30 to
// 50, lon -90 to -66) is the box every source no other box names is held to:
// ATC's layers, OPRHP's, NYNJTC's, Mohonk's, DEC's, NJDEP's, PASDA's, CT
// DEEP's, NC MST's and MassGIS's (that file's header). This frame is the box,
// edge to edge: at z3.5 a 390 px phone spans 24.2 degrees of longitude, so
// from -90.1 to -65.9 (Reasoned from MapLibre's 512 px world at z0, 274.2
// degrees across 390 px at z0 halved per zoom). The portrait screen is taller
// than the box, so Florida and the Gulf coast, which the `national` box holds,
// show at its foot (Reasoned from the same arithmetic over the phone's height).
//
// WHAT IT CAN SHOW. Below z5 the other organizations' trails draw from the
// network sketch, network_overview.geojson (map/style.ts's
// NETWORK_SKETCH_MAX_ZOOM), and the A.T. from trails.geojson at every zoom; the
// frame draws whatever the bucket the preview reads holds, so a source no
// publish has carried draws nothing yet. The question it answers is whether
// the East reads as trails rather than a mat of colour, and whether anything
// lands outside the land it belongs to.
//
// SAFE TO TAKE AGAIN, WHATEVER THE DATA BECOMES (.claude/skills/pr-screenshot/
// SKILL.md's four rules). No waypoint draws below POI_PIN_MIN_ZOOM, 7
// (map/poiLayerIds.ts): pins and dots both floor there, so no campsite,
// dispersed or official, is on the map at all at 3.5, and
// src/test/regionMapShots.test.ts fails this recipe if its zoom ever reaches
// the seam. No account: the drive never signs in. No location fix: the
// runner's browser has none, and the drive never presses locate. Nobody's
// report or photo is opened; a published serious warning draws at every zoom
// (map/warningLayers.ts), as a pin with no words and no reporter, which is
// what every hiker's map shows.

import { openMapAt } from './fixtures/regionCamera.mjs'

/** The box this frame shows, by its name in region_boxes(). */
export const region = 'eastern'
/** Its centre is the box's: lon -78 between -90 and -66, lat 40 between 30 and 50. */
export const camera = { center: [-78, 40], zoom: 3.5 }

export const caption =
  'Region `eastern`, zoom 3.5 — the box decision 31’s map shots start from: every source the build holds to the A.T. states and the Northeast (lat 30–50, lon −90 to −66; dbt/macros/lands_outside_its_region.sql). Trails here draw from the network sketch and the A.T.’s own line, so what to look for is whether the East reads as threads rather than a mat of colour, and whether anything lands off the land it belongs to. No waypoint draws below zoom 7, so no campsite can be in this frame.'
export const alt =
  'The map screen over the eastern United States at zoom 3.5, from the Mississippi to the Atlantic and from Florida to southern Canada, with the Appalachian Trail as a line down the mountains and other trails as thin coloured threads, and no waypoint pins.'

/** A region's worth of sketch and tiles at a coarse zoom reads several files before the first line draws. */
export const wait = 6000

export default async function drive(page) {
  await openMapAt(page, camera)
}
