// The planning band (#1585): the A.T.'s shelters, water and towns below the
// pin seam, at the zoom a hundred-mile resupply carry fits a phone.
//
// WHAT THIS FRAME IS EVIDENCE FOR. Until #1585 the map drew no waypoint
// below z9 and the legend said "Waypoints appear from a closer zoom." A
// thru-hiker planning the five or six days to the next town looks at
// 100-120 trail miles, which on a phone is a z8 screen - measured on the
// calibrated mile axis, the median 110-mile window fits at z8.26
// (map/poiLayers.ts's POI_PLANNING_MIN_ZOOM has the table). This camera is
// that screen over the Delaware Water Gap to Bear Mountain carry - New
// Jersey's whole A.T. and the Hudson Highlands, 111 trail miles that fit at
// z7.7 - held at z8.2 so the band's pins are in the frame as well as its
// dots: shelters, water and A.T. Community towns, the three types the band
// draws, the pins collision-placed and the losers dots beneath them.
//
// WHAT MUST NOT BE IN IT, and is not by construction: the other
// organizations' waypoints. Harriman's OPRHP trailheads and parking share
// the source and draw from the seam up; the band is scoped to the A.T.
// export (lib/trailData.ts's StoredPoi.network), so at this camera they are
// absent, and that absence is half of what the frame shows. Public ground
// throughout - no campsite readable at this zoom, nobody's report, nobody's
// fix (the four things SKILL.md says must never appear).
//
// THE LEGEND STAYS CLOSED HERE, and that is the correction from the first
// preview round (2026-09-18): opened, its sheet covers the lower two thirds
// of a phone and hid the very pins the frame exists to show. The band's
// other half - the legend's own sentence for it - is planning-band-legend.mjs,
// the same camera with the sheet open, so the two frames read as one change.
//
// The camera is seeded through lib/cameraMemory.ts's session-storage key,
// as basemap-ground-network.mjs does and for its reasons: the app restores
// a remembered view on load, validates the shape field by field, and a
// reload is what that memory is for.
//
// WHEN IT SHOWS LESS. A frame with the line and dots but no pins means the
// camera settled below POI_PLANNING_PIN_MIN_ZOOM; a frame with nothing on
// the line means the waypoints had not landed by the wait - the honest
// state on a slow bucket, not a broken recipe.
export const caption =
  'The planning band (#1585): the A.T. from the Delaware Water Gap to the Hudson Highlands at zoom 8.2, below the pin seam — shelters, water and A.T. Community towns drawn as pins where they fit and as dots where they do not, nothing else and none of the other organizations’ waypoints; the header’s In view door counting those three types. planning-band-legend.mjs is the same camera with the legend open.'
export const alt =
  'The map screen over northern New Jersey and the Hudson Highlands at zoom 8.2: the A.T. as a white line inside a dark casing running from the lower left to the upper right, with small dark-green shelter pins, blue water pins and brown town pins along it and smaller dots between them where pins did not fit, no other waypoint categories, and the header reading In view with a count'

/** Vector tiles from the bucket plus the waypoint source landing take longer
 *  than chrome. */
export const wait = 6000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract: { center: [lon, lat], zoom }, read back
  // with every field validated, and null on anything that does not convince.
  // The centre is the carry's own bounding-box centre from #1585's
  // measurement; the zoom is the band's pin floor plus a little, so the
  // frame is the band with pins and not its dots-only lower half.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-74.56, 41.15], zoom: 8.2 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  // First run stays skipped across the reload: the runner installs that
  // through an init script on the CONTEXT (scripts/screenshot.mjs's
  // skipFirstRun), which re-runs on every document rather than only the first.
  await page.getByRole('tab', { name: 'Map' }).click()
}
