// The other standing shot (see README.md, and STANDING in
// scripts/photograph-preview.mjs): the map screen, photographed on every
// pull request.
//
// This had no drive until #1054 - the app used to open here on its own. The
// redesign made Today the opening tab (today.mjs is that shot now), so the
// map is one tap away and this recipe takes it. What the shot shows since
// the same change: the floating identity plate over the canvas and the
// next-up band along the foot, in place of the old full-width header bands.
export const caption = 'The map screen'
export const alt =
  'The map screen: a floating identity plate over the canvas, and the next-up band along the foot'

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Map' }).click()
}
