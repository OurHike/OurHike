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
// where until this change the red line showed through between the stripes -
// the maintainer's choice from five rendered treatments: "I think I like
// option E the best". The band is white because the field day sheet's paper
// is white (map/style.ts's MAP_BACKDROP.light); on night_hike it would be
// ink, the same image built on that sheet's paper (map/closureTape.ts).
// Blaze colors stay OFF here, the shipped default, so every line under the
// tape is the same red as the tape's stripes - which is the case the band
// exists for.
//
// The same seeding as network-above-the-seam.mjs: a remembered camera and a
// reload, and no location fix, no account, nobody's reports.
export const caption =
  'Bear Mountain and Doodletown on a phone, z13, Blaze colors off (the default): OPRHP’s long-term closed trails drawn as barrier tape on an opaque band of the sheet’s paper over the red lines (#1575, the maintainer’s option E), where until this change the red line showed through between the stripes. Seven closed runs of 1.1 to 1.9 km sit in this frame, placed by measuring the pinned release’s network overview, with the A.T. crossing it over Bear Mountain'
export const alt =
  'The map screen over Bear Mountain State Park at zoom 13: every trail a solid red line inside a thin dark casing, the Appalachian Trail the widest, and along several trails a wide band of red diagonal stripes on a white ground laid over the line, the barrier tape marking a closed trail'

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
