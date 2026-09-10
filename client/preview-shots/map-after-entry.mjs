// The first map a hiker opens after the entry steps (#1296).
//
// Nothing else photographs this screen: every other recipe skips first run,
// and the standing trail-screen shot opens on a corridor that was fitted
// with no card in front of it. This one walks the three steps the way a new
// hiker does and then taps Map - which is the frame the maintainer reported
// as "nothing at all shows when first opening the app", and what it showed
// was the whole corridor squeezed into the top fifth of the screen under the
// identity plate at a 300 mi scale, where the entry card's framing had left
// it. App.tsx re-fits the corridor when the steps end; this is that fix's
// camera.
//
// "Decide this later" on the size step rather than "Download", so the
// shot does not start a corridor download it has no use for; "Not now" on
// the location step, so no permission prompt is raised on a runner. The
// second card, where the hiker hikes (#1373, frame 1b), is skipped: a kept
// place would move this camera off the whole-corridor frame the caption
// describes.
export const caption =
  'The map right after the entry steps (#1296): the whole corridor fitted to the screen at 100 mi, nothing taken yet (#1306) so the A.T. is a fine dotted dark line from Georgia to Maine at the same weight as the other organizations’ dotted trails around its New York miles, no waypoints below the seam (#1292) and the A.T.’s one badge naming it (#1283; placed at the opening camera since the review of #1374) — where it used to sit under the identity plate at 300 mi and read as an empty map'
export const alt =
  'The map screen as a new hiker first opens it after the three entry steps: the identity plate at the top, and below it the whole Appalachian Trail as a single fine dotted dark line from Georgia to Maine fitted to the screen over the basemap, with the other organizations’ trails as dotted threads of the same weight around its New York miles, no pins, one paper badge reading “Appalachian National Scenic Trail” with the ATC mark on the line, a 100 mi scale bar, and no elevation strip along the foot since nothing is taken (#1374 review)'

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
  await page.getByRole('button', { name: /^Skip/ }).click()
  await page.getByRole('button', { name: 'Decide this later' }).click()
  await page.getByRole('button', { name: /not now/i }).click()
  await page.getByRole('tab', { name: 'Map' }).click()
}
