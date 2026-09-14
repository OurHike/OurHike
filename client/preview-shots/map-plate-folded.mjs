// The Map tab after the hiker's first pan: the plate folded (#1374, the room
// audit of 2026-09-10).
//
// THE SCREEN THIS CHANGE IS ABOUT. Every phone screen was rendered at 375x667
// and 390x844 and the chrome around the map measured: the plate was 112px
// with its status strip, the new-notice banner 61px whenever ATC had posted
// in the last 72 hours, the tab bar 105px wrapped to three rows. The
// maintainer chose, from mocked options, that the plate folds to its eyebrow
// and mono line after the first pan or zoom and opens again on a tap
// (MapScreen.tsx owns the state, Header.tsx draws it), and that the banner
// becomes a dot on the legend button with the count on the legend's row.
// trail-screen.mjs photographs the plate OPEN, before any gesture; this frame
// is the same screen one pan later, which is the state a hiker walks with.
//
// A DRAG RATHER THAN A ZOOM, because a drag is one gesture MapLibre reports
// with an `originalEvent` on the phone and the desktop alike, and the fold
// keys on exactly that (MapView.tsx's `fromGesture`). The distance is short
// on purpose: the frame is about the chrome, not about where the map went.
//
// The dot is in this frame only when the build's data holds a notice touched
// in the last 72 hours - the same data-dependence the banner had - so the
// caption promises the fold and says the dot is conditional.
//
// Nobody's data is in the frame: no account, no notes, no location fix, and
// the opening camera is trail lines only (#1292).

export const caption =
  'The Map tab one pan later — the plate folded to its eyebrow and position line, the status strip a tap away, one bottom row of chrome with the mode chip at its left, and, where ATC has posted in the last 72 hours, a dot on the legend button in place of the banner row (#1374, room audit 2026-09-10)'
export const alt =
  'The whole-corridor map with a slim dark plate at the top-left carrying only “No trail taken” and “Location is off”, the legend and search buttons beside it, no status line under the plate and no notice banner under the map, and a single bottom row reading Day hike with a caret, then Today, Map, Plan and More'

/** The corridor overview lands 6–10 s after the Map tap in the sandbox
 *  (trail-screen.mjs's own note); this drive waits for that, then pans. */
export const wait = 6000

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Map' }).click()
  const canvas = page.getByRole('region', { name: /trail map/i })
  await canvas.waitFor()
  // Let the opening frame settle before touching it, so the pan is the
  // hiker's first gesture on a map that has already framed itself.
  await page.waitForTimeout(4000)
  const box = await canvas.boundingBox()
  if (box === null) return
  const x = box.x + box.width / 2
  const y = box.y + box.height / 2
  await page.mouse.move(x, y)
  await page.mouse.down()
  await page.mouse.move(x - 30, y + 40, { steps: 6 })
  await page.mouse.up()
}
