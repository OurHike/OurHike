// The badged trails at the A.T.'s prominence (#1586), on a phone at z7 over
// the Hudson valley and the Catskills - below the pin seam, where the
// network is the corridor-view sketch and what changed is the casing under
// its through-routes.
//
// WHAT CHANGED IN THIS FRAME. Until this change the untaken A.T. was the
// only cased line on the opening camera: a 1.5 px red line inside a 3.5 px
// dark casing from Georgia to Maine. The Long Path beside it, though it wore
// a badge, was a bare red thread - twice the haze's width and no wider than
// a park loop at the seam - which is what the maintainer read off the
// trail-screen shot: "its weird that the AT is more prominent than the
// LongPath" (2026-09-17), and, asked which trails: "Long trails are those
// named with pills showing. Right now the AT and LP" (2026-09-18). Now the
// sketch carries the same casing under its through-routes
// (map/style.ts's NETWORK_OVERVIEW_CASING_LAYER_ID, filtered to
// PRIMARY_TRAIL_SOURCES) and hands off at the through-route width at the
// seam. In this frame that is the Long Path from the George Washington
// Bridge to the Helderbergs and the A.T. from the Delaware Water Gap into
// Vermont - two dark-edged red lines at one weight, each wearing its badge.
// Everything else - the Highlands Trail, the Northville-Placid Trail at the
// top edge, the park clusters - draws as before: a bare thread, at 3 px
// where the exporter named it a long-distance trail (#1307) and 1.5 px
// elsewhere. That is the maintainer's definition, not an omission.
//
// WHERE THE CAMERA POINTS, MEASURED. The pinned release's
// network_overview.geojson (2026-09-16-4, fetched 2026-09-17) puts the Long
// Path at -74.61..-73.90 by 40.85..43.23. A 390 px phone at z7 spans 4.3
// degrees of longitude and, at this latitude, about 6.9 of latitude, so
// [-74.6, 42.4] holds it whole with the A.T.'s New York and New England
// miles beside it.
//
// Seeded as network-above-the-seam.mjs seeds its camera: a remembered view
// and a reload. No location fix, no account, nobody's reports, and nothing
// readable at this zoom but public ground.
export const caption =
  'The Hudson valley and the Catskills on a phone at z7, below the pin seam, nothing taken: the Long Path drawn exactly as the untaken A.T. is - a red line inside a dark casing at one weight, badged (#1586) - where until this change the A.T. was the only cased line and the Long Path a bare thread beside it. The other organizations’ trails stay bare threads, the long-distance names among them a little heavier (#1307): "long trails are those named with pills showing"'
export const alt =
  'The map screen over New York State at zoom 7: two long red trail lines, each inside a thin dark casing, running north to south - the Long Path up the Hudson valley to the Helderbergs, the Appalachian Trail across the Hudson Highlands into New England - each with a paper badge naming it, over a pale basemap with city names and fine red threads for the other trails'

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
