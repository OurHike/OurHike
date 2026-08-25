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
export const caption = 'The legend — no blaze rows above the pin grid'
export const alt =
  'The legend sheet over the trail screen, opening at the grid of waypoint categories with no blaze colour rows above it'

export default async function drive(page) {
  // The header's icon button. Its accessible name is the visually-hidden
  // span inside it (chrome/Header.tsx), which is what a screen reader — and
  // therefore this locator — sees.
  await page.getByRole('button', { name: 'Legend' }).click()
}
