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
// "Decide this later" on the size step rather than "Keep going", so the
// shot does not start a corridor download it has no use for; "Not now" on
// the location step, so no permission prompt is raised on a runner.
export const caption =
  'The map right after the entry steps (#1296): the whole corridor fitted to the screen at 100 mi, the A.T. one dark line from Georgia to Maine, no marks below the seam (#1292) — where it used to sit under the identity plate at 300 mi and read as an empty map'
export const alt =
  'The map screen as a new hiker first opens it after the three entry steps: the identity plate at the top, and below it the whole Appalachian Trail as a single dark line from Georgia to Maine fitted to the screen over the basemap, with no pins, dots or marks on it, a 100 mi scale bar and the elevation strip along the foot'

// First run is the subject, so it must not be skipped (scripts/screenshot.mjs).
export const entry = true

/** The trail line lands from the corridor-view sketch within a second or two
 *  of the map mounting (#1291); the basemap tiles take longer than that on a
 *  runner. */
export const wait = 6000

export default async function drive(page) {
  await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByRole('button', { name: 'Decide this later' }).click()
  await page.getByRole('button', { name: /not now/i }).click()
  await page.getByRole('tab', { name: 'Map' }).click()
}
