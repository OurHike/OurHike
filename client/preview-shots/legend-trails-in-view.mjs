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
//
// NO LONGER TAKEN IN THE DRIVE (#1352), and that is this recipe's own
// finding. Its drive used to tap the A.T.'s row and wait for `taken` to come
// back, which was #1306's legend half. Since the state merge that tap opens
// the "Which long hike?" sheet instead, so the wait would have hung for its
// full fifteen seconds and failed - the recipe caught the change before CI
// did. What replaces it is stronger evidence, not weaker: the drive seeds an
// active A.T. hike (the same fixture today-long-hike.mjs uses) and taps
// nothing at all, so the row reads `taken` BECAUSE the hiker is on that
// hike. That is precisely what #1352 changed - one state, read in two places
// - and a tap could not have shown it.
import { seedLongHike } from './fixtures/longHike.mjs'

// WHAT THE FRAME ACTUALLY HOLDS, checked against the photographed PNG
// (2026-09-09): two rows, not a column of them - the A.T. marked `taken`,
// and "Fingerboard Shelter Side Trail" SOLID in its blue blaze rather than
// dotted. That is right and is worth the caption saying so rather than
// glossing it: a side trail of the chosen system draws at full strength on
// purpose (map/nearbyTrails.ts's CHOSEN_SYSTEM_SOURCES holds `side_trails`
// beside `centerline`, and that file argues the decision at length). So the
// frame shows the taken system whole - through-route and spur - which is a
// better illustration than the dotted column the caption used to promise
// and this preview's bucket cannot yet draw.
export const caption =
  'The legend over Harriman at zoom 12 — the "Trails in view" block above the pin grid (#1283), with an active A.T. hike seeded and NOTHING TAPPED: since #1352 the row reads "taken" because the hiker is on that hike, which is the whole of the change in one word. Beside it the A.T.’s own Fingerboard Shelter side trail draws solid rather than dotted, because a spur of the taken system is part of it (map/nearbyTrails.ts). The other organizations’ trails are absent, not ghosted — this preview’s bucket has no nearby_trails.pmtiles yet'
export const alt =
  'The legend sheet over the map screen, opening with a "Trails in view" heading over two rows: a solid white line swatch inside its dark casing beside "Appalachian National Scenic Trail" with "taken" on the right, and a solid blue swatch beside "Fingerboard Shelter Side Trail", above the waypoint category grid'

/** Vector tiles from the bucket plus generated contours over a park both take
 *  longer than chrome. */
export const wait = 6000

export default async function drive(page) {
  // The hike first, because it is what makes the A.T. taken at all now. Its
  // reload lands on the entry screen; the camera write below survives it in
  // sessionStorage either way, but seeding in this order keeps each step's
  // failure legible.
  await seedLongHike(page)

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

  // `taken` with no tap behind it. Left as a wait rather than dropped: on a
  // build whose bucket has no nearby_trails.pmtiles the rows still hold the
  // A.T., so this settles the frame in both of the states the paragraph
  // above describes.
  await page.getByText('taken', { exact: true }).waitFor({ timeout: 15000 })
}
