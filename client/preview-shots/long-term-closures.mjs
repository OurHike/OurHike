// Long-term closed trails at Bear Mountain and Doodletown, on a phone at
// z13 (#1575, option E): barrier tape on an opaque band of the sheet's paper
// over the red trail lines. The one photographed screen that reaches a
// closure at a zoom the tape can be read at - hudson-highlands-desktop.mjs's
// frame holds no closed line, and the opening camera (trail-screen.mjs) is
// two thousand miles wide.
//
// WHERE THE CAMERA POINTS, MEASURED RATHER THAN GUESSED. The pinned release's
// network_overview.geojson (2026-09-16-4, fetched from the bucket on
// 2026-09-17) holds 201 features, 7 of them `trail_status: closed`, in 15
// line runs. Summed by the 0.05-degree cell their centres fall in, 25.3 km of
// that closed length sits in the cell centred on -74.00, 41.30 - Bear
// Mountain State Park's Doodletown side, where OPRHP marks trail after trail
// closed - against 7.5 km in the next densest cell, on the Genesee Valley
// Greenway. The seven longest runs here are 1.1 to 1.9 km, and the A.T.
// crosses the frame over Bear Mountain. The overview is what draws BELOW the
// seam; at z13 the tape comes from the network tiles' own closed lines
// (NEARBY_LONG_TERM_CLOSURE_LAYER_ID), which carry the same OPRHP status on
// the same ground, so the overview's closed features say where to look.
//
// WHAT TO LOOK FOR: over each closed trail, red diagonals on a white band
// inside a dark outline, where until #1575 the red line showed through
// between the stripes - the maintainer's choice from five rendered
// treatments: "I think I like option E the best". The band is white because
// the field day sheet's paper is white (map/style.ts's MAP_BACKDROP.light) -
// and, since 2026-09-18, it is
// that same white on night_hike too (closureTapeGround), the maintainer having
// read stripes on ink as no closure at all; long-term-closures-night.mjs is
// this frame under the dark scheme. Only red light keeps its ink.
// Blaze colors stay OFF here, the shipped default, so every line under the
// tape is the same red as the tape's stripes - which is the case the band
// exists for.
//
// The same seeding as network-above-the-seam.mjs: a remembered camera and a
// reload, and no location fix, no account, nobody's reports.
// AMENDED 2026-09-18 (#1588): the lines under the tape are the default's new
// vocabulary - the park's trails dashed and thinner, the A.T. a plain solid
// red with no casing - so the tape reads against a quieter ground than the
// solid cased lines it was chosen over.
// AMENDED 2026-09-20 (#1598 and #1597), and both changes are in this frame.
// The band carries a hard dark outline and 41% of its length in red rather
// than 28% - the maintainer's pick from four treatments after "the closures
// are not easily visible".
//
// THIS FRAME IS WHY THE BAND IS 14 PX AND NOT 17. The first cut widened it
// too, and what CI photographed here was ropes: a dozen closed trails at
// once, at the densest closure cell in the release, with the lines under
// them gone. The maintainer took the navigation weight back on 2026-09-21
// and kept the outline and the overview cadence, which are what fix the
// zoom that was actually broken. So this frame is the check on the OTHER
// direction - a closure must be unmistakable AND must not be the subject of
// a map about trails. And the lines under it are no longer a tint: every trail
// here is the A.T.'s own red, so the tape's job of being unmistakable for a
// trail line is harder than it was, which is what makes this frame worth
// reading rather than only the overview one.
// long-term-closures-overview.mjs is the same closures from the opening
// camera, which is the zoom the complaint was actually about.
export const caption =
  'Bear Mountain and Doodletown on a phone, z13, Blaze colors off (the default): OPRHP’s long-term closed trails drawn as barrier tape on an opaque band of the sheet’s paper (#1575, the maintainer’s option E) over the lines — and since #1598 the band is 14 px with 41% of its length red, inside a hard dark outline — 17 px and 51% for one day, until this frame showed a dozen closed trails drawn as ropes. The lines beneath are the park’s trails dashed and the A.T. solid, both in the one red since #1597 took the tint off them, so the tape is the one heavy mark on this frame without a second hue helping it. Seven closed runs of 1.1 to 1.9 km sit in this frame, placed by measuring the pinned release’s network overview, with the A.T. crossing it over Bear Mountain'
export const alt =
  'The map screen over Bear Mountain State Park at zoom 13: the Appalachian Trail a plain solid red line, the park’s trails thinner red dashed lines, and along several of them a wide band of red diagonal stripes on a white ground inside a dark outline, laid over the line, the barrier tape marking a closed trail'

/** Vector tiles from the bucket plus generated contours over a park at z13,
 *  the same allowance hudson-highlands-desktop.mjs makes. */
export const wait = 22000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract, as network-above-the-seam.mjs seeds it:
  // the centre of the densest cell of closed lines the release carries.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-74.005, 41.308], zoom: 13 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  // First run stays skipped across the reload: the runner installs that
  // through an init script on the context (scripts/screenshot.mjs's
  // skipFirstRun), which re-runs on every document rather than only the first.
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()
}
