// The legend's "Trails in view" block, over Harriman (#1283).
//
// legend.mjs reaches the same panel and cannot be the evidence for this
// change: its drive scrolls the sheet to the "Showing" control at the foot,
// and the block this pull request adds sits at the TOP of the panel, above
// the pin grid, so re-pointing that recipe would trade one claim for the
// other. A second recipe reaching the same panel at rest is what README.md's
// "reuse one by touching it" allows when the two shots carry different
// evidence - and it is retired back into legend.mjs the day the block is not
// the change under review.
//
// Harriman at z12 rather than the opening camera, deliberately. The block
// lists the named trails the map is drawing, and below the seam the network
// is the overview sketch, which publishes no `name` - so at the opening
// camera the block would show the A.T. alone, which is true and is not the
// picture. Over the park the full lines draw from the tiles, and the rows
// are the A.T. (solid, `taken`) over a column of dotted rows in their own
// blaze hues: Long Path, Ramapo-Dunderberg, Arden-Surebridge and the rest
// of what crosses one z12 frame. The same frame and the same seeding as
// network-above-the-seam.mjs, for its reasons.
//
// WHAT THIS SHOWS AND WHEN IT SHOWS LESS. The rows are measured off what the
// map actually drew (map/trailsInView.ts), so until a publish has carried
// nearby_trails.pmtiles to the bucket this preview reads, the block holds
// the A.T. alone - which is the honest state a phone on an older release is
// in, and the same "has publish-vector-data.yml run since the merge"
// question network-above-the-seam.mjs's frame already asks. The panel
// blanks the canvas behind it under this camera (#1138), so the map half of
// the change is that recipe's frame, not this one's.
export const caption =
  'The legend over Harriman at zoom 12 — the "Trails in view" block above the pin grid (#1283): the A.T. solid and marked taken, every other trail on screen a dotted row in its own blaze hue; the A.T. alone until nearby_trails.pmtiles is in the bucket this preview reads'
export const alt =
  'The legend sheet over the map screen, opening with a "Trails in view" heading over a column of rows: a solid dark line swatch beside "Appalachian National Scenic Trail" with "taken" on the right, then dotted swatches in aqua, red and blue beside the names of the park’s other trails, above the waypoint category grid'

/** Vector tiles from the bucket plus generated contours over a park both take
 *  longer than chrome. */
export const wait = 6000

export default async function drive(page) {
  // lib/cameraMemory.ts's contract, as network-above-the-seam.mjs seeds it:
  // Lake Tiorati, where the A.T., the Ramapo-Dunderberg and the Long Path's
  // feeder trails all sit inside one z12 frame.
  await page.evaluate(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-74.09, 41.25], zoom: 12 }),
    )
  })
  await page.reload({ waitUntil: 'load' })

  await page.getByRole('tab', { name: 'Map' }).click()

  // The rows are read off the settled frame, so the map has to have drawn
  // the trails before the panel can list them: wait for the A.T.'s badge
  // source to fill, which is the same measurement the rows come from - or
  // for the map to settle, on a build with no data to draw.
  await page.waitForTimeout(wait)

  // The header's icon button, by its visually-hidden name (chrome/Header.tsx).
  await page.getByRole('button', { name: 'Legend' }).click()

  // The block is at the top of the sheet, which opens scrolled to the top;
  // waiting for the heading is the settle.
  await page.getByRole('heading', { name: 'Trails in view' }).waitFor()
}
