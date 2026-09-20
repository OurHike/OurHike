// Every waypoint, at the zoom a resupply carry fits (#1585).
//
// WHAT THIS FRAME IS EVIDENCE FOR, and it is two things that have to be seen
// together. A thru-hiker walking twenty miles a day plans one resupply at a
// time - five or six days, 100-120 trail miles - and measured on the
// calibrated mile axis that section fits a 390x700 phone at a median z8.26,
// with nine in ten 120-mile windows fitting at z7.61 or nearer. The pin seam
// was z9. So the screen a hiker plans a carry from had no waypoint on it at
// all, and this camera is that screen with the seam moved to 7 - the
// maintainer's number, set on 2026-09-20 against two drawn frames, and low
// enough to clear every carry rather than the median half of them.
//
// THE OTHER THING IS WHAT IS NOT MISSING. A first build of #1585 put the
// shelters, water and towns on this screen and left the campsites, privies,
// parking, crossings, viewpoints and trailheads off it - a type gate below
// the seam. The maintainer's rule, 2026-09-18: "Don't auto hide the POIs
// ever. It's a safety thing, hikers need to know that info." So what this
// frame has to show is every category the hiker has switched on, drawn. That
// rule survived the seam moving: it is about WHICH categories the map may
// decide for a hiker, and the seam decides only WHERE waypoints begin.
//
// What the frame should hold, as of 2026-09-20: shelters, water, campsites
// and privies, with the privies and campsites RIDING their shelters' pins as
// badges rather than stacking beside them - the nesting came back the same
// day ("You need to nest the Shelters, Campsites, Privies & Water as we did
// before this PR"). The trail line draws OVER the pins now, and each pin
// stands on its point rather than being centred on it, so the line passes
// under the artwork instead of through it.
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
// WHEN IT SHOWS LESS. A bare line means either the camera settled under z7
// and the seam did its job, or the waypoints had not landed by the wait -
// the honest state on a slow bucket rather than a broken recipe. The legend
// is shut in this frame, so which of the two it is has to be read off the
// zoom rather than off a control; the waypoint gate lives in the legend's
// Showing picker now ("None" at the far end of it), not over the map. Both
// ranks share one floor, so dots without pins is no longer a state this
// frame can be in - if it ever is, the two floors have drifted apart.
export const caption =
  'Every waypoint at the zoom a resupply carry fits (#1585): the A.T. through the Hudson Highlands at zoom 7.8, just above the z7 seam — shelters and campsites as pins with their privies and water riding them as badges, the trail line drawing over the top, and no category the map decided to leave off'
export const alt =
  'The map screen over the Hudson Highlands at zoom 7.8: the Appalachian Trail as a red line drawn over the waypoints along it, with dark-green shelter pins standing on their points, each wearing a small strip of badges for the privy, water and campsite that belong to the same place, and no control floating over the map'

/** Vector tiles from the bucket plus the waypoint source landing take longer
 *  than chrome. */
export const wait = 6000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract: { center: [lon, lat], zoom }, read back
  // with every field validated, and null on anything that does not convince.
  // 7.8 rather than 7 itself: a camera parked exactly on the floor would
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
