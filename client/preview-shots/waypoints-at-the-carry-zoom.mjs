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
// What the frame should hold, as of 2026-09-26 (#1676): pins where there is
// room and small coloured dots everywhere else - the two ranks of #597, back
// after eight days with the collision engine off, when this frame drew 7,123
// full-size pins on top of each other. Where two pins would overlap, the one
// the maintainer's order ranks first keeps its pin: shelters and campsites,
// then water, then trailheads, then the rest. The privies and campsites
// still RIDE their shelters' pins as badges (the nesting, 2026-09-20). The
// trail line draws OVER the pins, and each pin stands on its point rather
// than being centred on it, so the line passes under the artwork instead of
// through it.
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
// ranks share one floor, so a frame of dots with no pins at all means the
// two floors have drifted apart; a frame of pins with no dots between them
// means the collision engine is off again.
export const caption =
  'Every waypoint at the zoom a resupply carry fits, as a pin or a dot (#1676), in the slim pin (#1682): the A.T. through the Hudson Highlands at zoom 7.8, just above the z7 seam — pins where there is room, shelters and campsites first in full colour, parking, privies and vistas pale, unverified waypoints hollow, small coloured dots for the waypoints that lost their pin to a neighbour, the trail line drawing over the top, and no category the map decided to leave off'
export const alt =
  'The map screen over the Hudson Highlands at zoom 7.8: the Appalachian Trail as a red line drawn over the waypoints along it, a few dozen pins spaced apart with map paper between them, and small coloured dots along the trails for every waypoint that did not take a pin'

/** Vector tiles from the bucket plus the waypoint source landing take longer
 *  than chrome.
 *
 * 22000, as the Hudson Highlands desktop recipes wait, since #1676's first
 * preview (built from 698274a7): at the old wait all three waypoint recipes
 * photographed the map mid-load - the carry frame with its dots drawn but no
 * pin and no trail line, the Brooklyn and Shenandoah frames with neither. The trail
 * line is not something #1676 touches, so the frame was early rather than
 * wrong. Measured in the agent sandbox the same day, through
 * scripts/data-proxy.mjs: at 6 s `main` and #1676's branch were both still
 * blank at the carry camera, and at 15-20 s both had drawn everything. */
export const wait = 22000

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
