// Every waypoint, at the zoom a resupply carry fits (#1585).
//
// WHAT THIS FRAME IS EVIDENCE FOR, and it is two things that have to be seen
// together. A thru-hiker walking twenty miles a day plans one resupply at a
// time - five or six days, 100-120 trail miles - and measured on the
// calibrated mile axis that section fits a 390x700 phone at a median z8.26,
// with nine in ten 120-mile windows fitting at z7.61 or nearer. The pin seam
// was z9. So the screen a hiker plans a carry from had no waypoint on it at
// all, and this camera is that screen with the seam moved to 7.5.
//
// THE OTHER THING IS WHAT IS NOT MISSING. A first build of #1585 put the
// shelters, water and towns on this screen and left the campsites, privies,
// parking, crossings, viewpoints and trailheads off it - a type gate below
// the seam. The maintainer's rule, 2026-09-18: "Don't auto hide the POIs
// ever. It's a safety thing, hikers need to know that info." So what this
// frame has to show is every category the hiker has switched on, drawn: the
// four a fresh install shows (shelter, water, campsite, privy), as pins where
// the collision engine places them and as dots where it does not, and never
// as nothing. A frame with only two or three kinds of mark on it is this
// change having regressed.
//
// Harriman and the Hudson Highlands, where the A.T. runs through public land
// thick enough that all four categories are in one frame. Public ground
// throughout - no campsite readable at this zoom, nobody's report, nobody's
// fix (the four things SKILL.md says must never appear).
//
// The camera is seeded through lib/cameraMemory.ts's session-storage key, as
// basemap-ground-network.mjs does and for its reasons: the app restores a
// remembered view on load, validates the shape field by field, and a reload
// is what that memory is for.
//
// WHEN IT SHOWS LESS. Dots with no pins means the camera settled under z7.5;
// a bare line means the waypoints had not landed by the wait, which is the
// honest state on a slow bucket rather than a broken recipe.
export const caption =
  'Every waypoint at the zoom a resupply carry fits (#1585): the A.T. through the Hudson Highlands at zoom 7.8, below the old z9 seam and above the new 7.5 one — shelters, water, campsites and privies all drawn, as pins where they fit and as dots where they do not, with no category hidden by the map'
export const alt =
  'The map screen over the Hudson Highlands at zoom 7.8: the Appalachian Trail as a white line inside a dark casing, with dark-green shelter pins, blue water pins, green campsite pins and purple privy marks along it, and smaller coloured dots between them where a pin did not fit'

/** Vector tiles from the bucket plus the waypoint source landing take longer
 *  than chrome. */
export const wait = 6000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract: { center: [lon, lat], zoom }, read back
  // with every field validated, and null on anything that does not convince.
  // 7.8 rather than 7.5 itself: a camera parked exactly on the floor would
  // photograph the one frame where a rounding error decides whether this
  // shot has pins in it at all.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-74.09, 41.25], zoom: 7.8 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  // First run stays skipped across the reload: the runner installs that
  // through an init script on the CONTEXT (scripts/screenshot.mjs's
  // skipFirstRun), which re-runs on every document rather than only the first.
  await page.getByRole('tab', { name: 'Map' }).click()
}
