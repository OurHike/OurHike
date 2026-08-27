// The other standing shot (see README.md, and STANDING in
// scripts/photograph-preview.mjs): the map screen, photographed on every
// pull request.
//
// This had no drive until #1054 - the app used to open here on its own. The
// redesign made Today the opening tab (today.mjs is that shot now), so the
// map is one tap away and this recipe takes it. What the shot shows since
// the same change: the floating identity plate over the canvas and the
// next-up band along the foot, in place of the old full-width header bands.
//
// Re-pointed 2026-08-27 (#1071) rather than copied, per README.md: the screen
// this pull request changes is THIS one - the ATC point notice is drawn on
// this canvas - and a second recipe reaching the same screen would be the
// gallery .claude/skills/pr-screenshot/SKILL.md warns against.
//
// WHAT THIS SHOT CANNOT SHOW, and the reason it is pointed here anyway. The
// preview build carries an empty `VITE_DATA_BASE_URL` (#1024), so no release
// artifacts arrive, so there are no ATC notices on the canvas to photograph -
// the shot is the map screen with no mark on it, which is evidence that the
// app still comes up and nothing more. It is the right camera position for the
// day #1024 is fixed. Until then the evidence for the mark itself is measured
// off the rendered image in map/atcNoticeMark.test.ts, and the pull request's
// `## Screenshot` section says so rather than letting this stand in for it.
export const caption = 'The map screen'
export const alt =
  'The map screen: a floating identity plate over the canvas, and the next-up band along the foot'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Map' }).click()
}
