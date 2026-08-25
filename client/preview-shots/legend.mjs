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
export const caption = 'The legend'
export const alt = 'The legend sheet, open over the trail screen'

export default async function drive(page) {
  // The header's icon button. Its accessible name is the visually-hidden
  // span inside it (chrome/Header.tsx), which is what a screen reader — and
  // therefore this locator — sees.
  await page.getByRole('button', { name: 'Legend' }).click()
}
