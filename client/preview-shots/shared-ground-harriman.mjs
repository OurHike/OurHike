// The A.T. and the Ramapo-Dunderberg on one treadway in Harriman, z14 - the
// 2,145 m stretch between Fingerboard and William Brien that the maintainer's
// screenshot of 2026-09-10 showed as one line painting over the other ("If 2
// trail lines overlap, could we show both somehow?"). map/sharedGround.ts
// draws a stretch the pipeline has paired (#1384) as two halves of one
// line: the A.T.'s white on one side of the chord, the R-D's red on the
// other, inside one dark casing.
//
// UNTIL A RELEASE CARRIES THE PAIRS THIS FRAME SHOWS THE OVERLAP AS IT WAS -
// the client half is guarded on the property's absence, and the pairing
// publishes with pipeline PR #1385 and the next UA vector publish. The
// recipe is the same camera either way, so the before and the after are one
// frame.
//
// A remembered camera and a reload, as hudson-highlands-desktop.mjs seeds
// its frame; no location fix, no account, nobody's reports.
export const caption =
  'Harriman at z14, the A.T. and the Ramapo-Dunderberg on one treadway between Fingerboard and William Brien: where a release carries the shared-ground pairs, one line with the A.T.’s white half on one side and the R-D’s red half on the other inside a single casing; on a release without them, the two lines as they overlapped before'
export const alt =
  'A phone map of Harriman State Park at hiking zoom with contour lines, and the Appalachian Trail running with the red Ramapo-Dunderberg Trail: on a release with the shared-ground pairs the two draw as one line split lengthwise, white on one side and red on the other, inside a thin dark casing'

/** Contours from the DEM worker and the network tiles from the bucket, at a
 *  hiking zoom over a park: the same window the Hudson frame needs. */
export const wait = 22000

export default async function drive(page) {
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-74.094, 41.2755], zoom: 14 }),
    )
  })
  await page.reload({ waitUntil: 'load' })
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()
}
