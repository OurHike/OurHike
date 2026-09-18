// The badged trails at the A.T.'s prominence (#1586) under the default's
// vocabulary (#1588), on a phone at z7 over the Hudson valley and the
// Catskills - below the pin seam, where the network is the corridor-view
// sketch.
//
// WHAT THIS FRAME SHOWS. The Long Path from the George Washington Bridge to
// the Helderbergs and the A.T. from the Delaware Water Gap into New England,
// each a plain solid red line at one fine weight with its badge, over every
// other organization's trails as a lighter dashed red - the maintainer's
// pick, 2026-09-18, from two sheets of mock-ups rendered off this release's
// own lines: "light dashed red" for everything without a pill, and for the
// two badged trails "solid, no casing" ("the at and long path looks too
// different now") over #1586's cased line of the day before. Nothing is
// cased under the default; with "Blaze colors" on, the badged trails' sketch
// lines are cased and every line solid in its hue, the look this frame had
// on 2026-09-17.
//
// WHERE THE CAMERA POINTS, MEASURED. The pinned release's
// network_overview.geojson (2026-09-16-4, fetched 2026-09-17) puts the Long
// Path at -74.61..-73.90 by 40.85..43.23. MapLibre's world is 512 px times
// two to the zoom, so a 390 by 844 px phone at z7 spans 2.1 degrees of
// longitude and, at this latitude, about 3.4 of latitude: [-74.6, 42.4]
// holds the Long Path whole with the A.T.'s New York miles beside it. (The
// first version of this comment said 4.3 and 6.9 degrees, the 256 px tile's
// arithmetic; the frame CI photographed - Rome at the top, Paterson at the
// foot - is the correction.)
//
// Seeded as network-above-the-seam.mjs seeds its camera: a remembered view
// and a reload. No location fix, no account, nobody's reports, and nothing
// readable at this zoom but public ground.
export const caption =
  'The Hudson valley and the Catskills on a phone at z7, below the pin seam, nothing taken, blaze colours off: the Long Path and the A.T. each a plain solid red line at one fine weight with its badge - "solid, no casing", the maintainer’s pick over #1586’s cased line - and every other organization’s trail a lighter dashed red around them (#1588: "long trails are those named with pills showing", and the rest "light dashed")'
export const alt =
  'The map screen over New York State at zoom 7: two long solid red trail lines running north to south - the Long Path up the Hudson valley to the Helderbergs, the Appalachian Trail across the Hudson Highlands into New England - each with a paper badge naming it, over a pale basemap with city names and fainter dashed red threads for the other trails'

/** The sketch is one GeoJSON the app loads with the map, and the basemap
 *  tiles for a state-wide frame take a moment more than a park's. */
export const wait = 8000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract: { center: [lon, lat], zoom }, validated
  // field by field on load. Between the Long Path's south end and its
  // north end, at the zoom that holds both.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-74.6, 42.4], zoom: 7 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  // First run stays skipped across the reload: the runner installs that
  // through an init script on the context (scripts/screenshot.mjs's
  // skipFirstRun), which re-runs on every document rather than only the first.
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()
}
