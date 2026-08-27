// The legend sheet — and the worked example of pointing the camera.
//
// A recipe exports a caption and, when the screen is not the one the app
// opens on, a default-export drive that takes a Playwright page the rest of
// the way. The runner (scripts/photograph-preview.mjs) has already loaded
// the built app, skipped first run (export `entry = true` to keep it), and
// let it settle; the drive does only the taps a hiker would.
//
// CI photographs every recipe a pull request adds or changes and leads the
// preview comment with it, so changing a screen and pointing the camera at
// it are the same pull request — .claude/skills/pr-screenshot/SKILL.md.
// Re-pointed 2026-08-25: the blaze rows came off the top of this panel, so
// the shot this recipe already reached is the evidence for their removal —
// what the caption has to say is which absence to look for, since a reviewer
// cannot see a row that is not there without being told it used to be.
//
// Re-pointed again 2026-08-26 (#1047): the panel gained an Alerts switch
// under the grid, beside "Verified?" and the drought row. This time the shot
// is evidence for something PRESENT, so the drive scrolls it into frame
// rather than stopping at the top of the sheet — the switch sits below the
// controls a phone-height sheet shows at rest, and a photograph of the grid
// says nothing about a control under the fold.
//
// Re-pointed again 2026-08-27 (#1051): the closure and serious-warning rows
// reach a hiker for the first time. They had rendered in Legend.test.tsx and
// nowhere else for as long as they had existed, so this is the first
// photograph of either — which makes the shot the whole evidence, and makes
// the row rather than the switch what the camera has to reach. Both sit at
// the foot of the grid, immediately above the switch the last re-pointing
// framed, so this scrolls further down the same sheet rather than anywhere
// new. What the caption has to name is what is NOT on them: no number.
export const caption =
  'The legend — the closure and serious-warning rows, on screen at last (#1051)'
export const alt =
  'The legend sheet over the trail screen, scrolled to the foot of the waypoint grid: two full-width rows below the two-column grid, a barrier-tape swatch labelled Closure and a hollow red triangle labelled Serious warning, each tagged Alerts and neither carrying a count, with the Verified? and Alerts switches below them'

export default async function drive(page) {
  // The map first: the app opens on Today since #1054, and the legend's
  // button floats over the map screen.
  await page.getByRole('tab', { name: 'Map' }).click()

  // The header's icon button. Its accessible name is the visually-hidden
  // span inside it (chrome/Header.tsx), which is what a screen reader — and
  // therefore this locator — sees.
  await page.getByRole('button', { name: 'Legend' }).click()

  // The lower of the two new rows, brought into view by the thing that IS the
  // change rather than by a pixel offset into the sheet: the grid above it is
  // every hideable category (#723), so how far down these rows sit moves
  // whenever that list does. `scrollIntoViewIfNeeded` also waits for the
  // element, so this is the settle as well as the scroll.
  //
  // The LOWER of the two on purpose. They are stacked and each spans the grid,
  // so reaching the second brings the first with it, and it sits directly above
  // the Alerts switch that names the tag both rows carry — one scroll, and the
  // row and the switch it points at are in the same frame.
  //
  // By its accessible name, which the row carries as an `aria-label` because a
  // safety row is not a button (chrome/Legend.tsx). An exact name rather than a
  // regex: `/warning/i` would also match the wrong-way row if one is ever added
  // beside it, and this shot has one job.
  await page.getByRole('listitem', { name: 'Serious warning' }).scrollIntoViewIfNeeded()
}
