// The blaze card (#1962, features/CHALLENGES_BLAZE_CARD.md, frame
// features/design/blaze-card/Card.dc.html): the ATC's list as a card of
// tiles in the ATC's four sections, the seeded hiker's earned items white.
//
// WHAT THIS SHOT IS EVIDENCE FOR. The card sits in the pine header under the
// finish line, where the diamond strip used to be: Learn, Experience,
// Protect and Mystery as rows of 26 px tiles, each tile its item's glyph,
// the earned ones white blazes, the three sealed mystery items dashed. Under
// the card, "Bigger tiles". The fixture carries 33 of the 100 items
// (fixtures/challenges.mjs says which), so the card is shorter than a
// hiker's.
//
// SEEDED, AND SAID SO: fixtures/challenges.mjs; the clock is inside the
// window the way challenge-detail.mjs fixes it.
import { EVENING, openChallenges, seedChallenges } from './fixtures/challenges.mjs'

export async function before(page) {
  await page.clock.setFixedTime(EVENING)
}

export const caption =
  'The card in the challenge’s header: tiles in the ATC’s sections, earned ones white (#1962, seeded hiker)'
export const alt =
  'A challenge screen whose dark green header holds a card of small tiles in four labelled rows, Learn, Experience, Protect and Mystery, a few tiles white where the rest are dark green, and a Bigger tiles button under it'

export default async function drive(page) {
  await seedChallenges(page)
  await openChallenges(page)
  await page.getByRole('button', { name: /A\.T\. Summer Bucket List/ }).click()
  await page.getByTestId('blaze-card').waitFor()
}
