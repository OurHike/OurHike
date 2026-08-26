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
export const caption = 'The legend — the Alerts switch under the grid (#1047)'
export const alt =
  'The legend sheet over the trail screen, scrolled to the switches under the waypoint grid: Showing, Verified?, and an Alerts checkbox with a line under it saying what is ahead of you is still called out at the top'

export default async function drive(page) {
  // The header's icon button. Its accessible name is the visually-hidden
  // span inside it (chrome/Header.tsx), which is what a screen reader — and
  // therefore this locator — sees.
  await page.getByRole('button', { name: 'Legend' }).click()

  // The switch itself, brought into view by the thing that IS it rather than
  // by a pixel offset into the sheet: the grid above it is every hideable
  // category (#723), so how far down this row sits moves whenever that list
  // does. `scrollIntoViewIfNeeded` also waits for the element, so this is the
  // settle as well as the scroll.
  await page.getByRole('checkbox', { name: /alerts/i }).scrollIntoViewIfNeeded()
}
