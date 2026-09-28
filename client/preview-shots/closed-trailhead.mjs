// A trailhead whose every trail within 100 m is closed, drawn as the dark pin
// with a white x and opened to its peek (#1695). The maintainer: "If a
// trailhead has all trails closed with an x, show an x as the trailhead icon
// too." Picked by poll on 2026-09-28 from three drawn over this same ground:
// this pin, the trailhead's own purple with an x, and the closure's bare x.
//
// WHERE THE CAMERA POINTS, MEASURED RATHER THAN GUESSED. Run against the UA
// release 2026-09-24-2 on 2026-09-28, pipeline/export_nearby_poi.py's
// mark_closed_trailheads marks four trailheads statewide, and three of them
// are here, on Storm King's Route 9W side: OPRHP facilities 10073 (named
// "Wilkonson Memorial"), 10079 and 10165. The fourth is on the Genesee Valley
// Greenway, with no name to search for. At Storm King the only line within
// 100 m of each is a short closed connector, while the park's trails further
// out are open - which is the case to judge the rule on.
//
// THIS FRAME IS ONLY THE X ONCE THE DATA CARRIES IT. The pin reads
// `trails_closed` off nearby_poi.geojson, which the bucket holds only after
// publish-vector-data runs from a build with this change in it. Before that,
// the camera finds an ordinary purple trailhead pin and a peek with no closed
// line: a true picture of the data it was given, and the caption says both.
//
// Search reaches the trailhead by name, the same drive as
// waypoint-quick-answers.mjs. No location fix, no account, nobody's reports.
export const caption =
  'Storm King State Park on a phone: the Wilkonson Memorial trailhead’s peek (#1695). Where the data carries trails_closed, the trailhead is a dark pin with a white x in place of the signpost, and the peek says “Every trail within 328 ft of this trailhead is closed.” Until publish-vector-data has run with this change, the same trailhead is an ordinary purple pin with no such line: the shot shows what the bucket holds.'
export const alt =
  'The map over Storm King State Park with a waypoint card open for the Wilkonson Memorial trailhead. Either its pin is dark with a white x and the card carries a boxed line saying every trail within 328 feet is closed; or, before the data is republished, it is an ordinary purple trailhead pin and card. Or, where this build has no waypoint data, the search panel reading “Nothing here by that name.”'

/** Vector tiles and the network waypoints over a park at z15. */
export const wait = 12000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract, as long-term-closures.mjs seeds it: the
  // three marked trailheads sit within a kilometre of this point.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-73.979, 41.444], zoom: 15 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()

  await page.getByRole('button', { name: 'Search' }).click()
  await page
    .getByRole('searchbox', { name: 'Search the downloaded map' })
    .fill('Wilkonson')

  // Whether a result arrives is the test for which frame this build can
  // reach; waited on because the artifacts may still be landing.
  const first = page
    .getByRole('button')
    .filter({ hasText: /Wilkonson/ })
    .first()
  await first.waitFor({ timeout: 20000 }).catch(() => {})
  if ((await first.count()) === 0) return

  await first.click()
  await page
    .getByTestId('poi-card-peek-conditions')
    .waitFor({ timeout: 15000 })
    .catch(() => {})
}
