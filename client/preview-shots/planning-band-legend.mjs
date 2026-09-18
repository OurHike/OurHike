// The planning band's sentence (#1585): the legend, open over the band's
// camera, saying what this zoom draws.
//
// The other half of planning-band.mjs, and its own frame because the two
// cannot share one: on a phone the legend sheet covers the lower two thirds
// of the map, so a frame with it open shows the sentence and hides the pins,
// and one with it closed shows the pins and no sentence. The first preview
// round (2026-09-18) photographed the first and called it the second.
//
// WHAT THIS FRAME IS EVIDENCE FOR. Below the seam the legend used to say
// "Waypoints appear from a closer zoom." on every rectangle; in the band it
// says "Shelters, water and resupply towns show at this zoom; the rest appear
// from a closer zoom." - the second half kept so a hiker who learned one form
// reads the other. The rows beneath keep their plain in-view counts with no
// "N of M fit" fractions, because down here "drawn" would measure the band's
// type gate and not the collision engine (chrome/Legend.tsx). Resupply's row
// still reads as hidden - the toggle is the walking map's - while the band
// draws the towns regardless, which is the decision lib/waypointVisibility.ts
// records.
//
// Same camera and seeding as planning-band.mjs, for its reasons; public
// ground, nobody's data, no fix.
export const caption =
  'The legend in the planning band (#1585), over the same Hudson Highlands camera at zoom 8.2: "Shelters, water and resupply towns show at this zoom; the rest appear from a closer zoom." above the rows, which keep plain in-view counts with no fit fraction; resupply’s row still reads as hidden while the band draws the towns'
export const alt =
  'The legend sheet open over the lower part of the map screen, opening with the sentence that shelters, water and resupply towns show at this zoom and the rest appear from a closer zoom, then rows for shelter, water, campsite, resupply, crossing, viewpoint, parking, privy and trailhead with counts, some struck through as hidden, and the closure and serious-warning rows beneath'

/** The waypoint source landing plus the legend's own counts want the same
 *  settle planning-band.mjs gives them. */
export const wait = 6000

export default async function drive(page) {
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-74.56, 41.15], zoom: 8.2 }),
    )
  })
  await page.reload({ waitUntil: 'load' })
  await page.getByRole('tab', { name: 'Map' }).click()

  // Guarded the way in-view.mjs guards its door: a build where the button
  // has not mounted by the wait still photographs the map rather than
  // failing the recipe.
  const legend = page.getByRole('button', { name: 'Legend' })
  await legend.waitFor({ timeout: 15000 }).catch(() => {})
  if ((await legend.count()) > 0) await legend.click()
}
