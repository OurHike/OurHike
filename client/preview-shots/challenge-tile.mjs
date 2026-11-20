// A tile, opened (#1963, frame features/design/blaze-card/Tile.dc.html):
// McAfee Knob from the list, read in full - the glyph where a photo will
// be (slice 7), the item's number and place, the moment the seeded hiker's
// walk earned it, one-tap "Take it back", "Also here" naming the Triple
// Crown, the register line, and the honor-system line.
//
// SEEDED, AND SAID SO: fixtures/challenges.mjs; the clock inside the window
// as challenge-detail.mjs fixes it.
import { EVENING, openChallenges, seedChallenges } from './fixtures/challenges.mjs'

export async function before(page) {
  await page.clock.setFixedTime(EVENING)
}

export const caption =
  'A tile, opened: the item in full, its place, earned from the walk, Take it back (#1963, seeded hiker)'
export const alt =
  'A full-screen sheet with a dark green top holding a white tile glyph, the item title Take the McAfee Knob shuttle, its place and mile and the moment it was earned, then Earned, a Take it back button, an Also here card naming the Triple Crown, and a register line'

export default async function drive(page) {
  await seedChallenges(page)
  await openChallenges(page)
  await page.getByRole('button', { name: /A\.T\. Summer Bucket List/ }).click()
  await page.getByRole('button', { name: 'Experience', exact: true }).click()
  await page
    .getByRole('button', { name: /Take the McAfee Knob shuttle/ })
    .filter({ hasNot: page.locator('.blaze-tile') })
    .first()
    .click()
  await page.getByRole('dialog', { name: /Take the McAfee Knob shuttle/ }).waitFor()
}
