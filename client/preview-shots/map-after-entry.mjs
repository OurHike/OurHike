// The first map a hiker opens after the entry steps (#1296).
//
// Nothing else photographs this screen: every other recipe skips first run,
// and the standing trail-screen shot opens on a corridor that was fitted
// with no card in front of it. This one walks the entry cards the way a new
// hiker does (five since the review of #1374) and then taps Map - which is
// the frame the maintainer reported as "nothing at all shows when first
// opening the app", and what it showed
// was the whole corridor squeezed into the top fifth of the screen under the
// identity plate at a 300 mi scale, where the entry card's framing had left
// it. App.tsx re-fits the corridor when the steps end; this is that fix's
// camera.
//
// "Decide this later" on the size step rather than "Download", so the
// shot does not start a corridor download it has no use for; "Not now" on
// the location step, so no permission prompt is raised on a runner. The
// mode card (#1374 review) and the place card (#1373, frame 1b) are both
// skipped: a kept place would move this camera off the whole-corridor frame
// the caption describes, and the skipped mode is Day hike, which is what the
// shell would have assigned before the card existed.
export const caption =
  'The map right after the entry steps (#1296): the whole corridor fitted to the screen at 100 mi, nothing taken yet (#1306) so the A.T. is a fine solid dark line from Georgia to Maine (its sketch has no casing to edge a white line with; the dot rhythm is gone since 2026-09-10) at the same weight as the other organizations’ trails around its New York miles, no waypoints below the seam (#1292) and the A.T.’s one badge naming it (#1283; placed at the opening camera since the review of #1374) — where it used to sit under the identity plate at 300 mi and read as an empty map'
export const alt =
  'The map screen as a new hiker first opens it after the entry cards: the identity plate at the top, and below it the whole Appalachian Trail as a single fine dark line from Georgia to Maine fitted to the screen over the basemap, with the other organizations’ trails as fine threads of the same weight around its New York miles, no pins, one paper badge reading “Appalachian National Scenic Trail” with the ATC mark on the line, a 100 mi scale bar, and no elevation strip along the foot since nothing is taken (#1374 review)'

// First run is the subject, so it must not be skipped (scripts/screenshot.mjs).
export const entry = true

/** The trail line lands from the corridor-view sketch within a second or two
 *  of the map mounting (#1291); the basemap tiles take longer than that on a
 *  runner, and the network overview's tile cut longer still - between 6 and
 *  10 s after the map mounts in the agent sandbox (trail-screen.mjs has the
 *  frames), so 6 s caught its first dots by a hair. The same upper bound as
 *  the trail screen, for the same file. */
export const wait = 10000

export default async function drive(page) {
  await page.getByRole('button', { name: 'Get set up' }).click()
  // Two skips, one card each: the mode card, then the place card. Named in
  // full rather than /^Skip/, which the camera caught matching the first of
  // them twice when the mode card arrived (the preview at 05e9506a).
  await page.getByRole('button', { name: /^Skip — day hike for now/ }).click()
  await page.getByRole('button', { name: /^Skip — I.ll set this later/ }).click()
  await page.getByRole('button', { name: 'Decide this later' }).click()
  await page.getByRole('button', { name: /not now/i }).click()
  await page.getByRole('tab', { name: 'Map' }).click()
}
