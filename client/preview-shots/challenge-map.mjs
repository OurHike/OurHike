// "Where your trail karma is" (#1965, features/CHALLENGES_BLAZE_CARD.md slice
// 5, frame features/design/blaze-card/Line.dc.html): the challenge's second
// view, from the Card / Where pair above the card.
//
// WHAT THIS SHOT IS EVIDENCE FOR. The seeded hiker's four earned items under
// the state each landed in - Georgia, Virginia - with where and when, the
// trivia quiz under "Not on the trail", the places still on the card as
// chips with their states and no count, and the strip of fourteen states with
// gold marks. The map above them draws only when the release carries
// challenge_map.json: CI's preview fetches whatever the preview's data has,
// and until a publish after #1965's merge that is nothing, so this shot shows
// the list alone - which is the honest fallback, not a fault.
//
// SEEDED, AND SAID SO: fixtures/challenges.mjs; the clock inside the window.
import { EVENING, openChallenges, seedChallenges } from './fixtures/challenges.mjs'

export async function before(page) {
  await page.clock.setFixedTime(EVENING)
}

export const caption =
  'Where your trail karma is: earned items by state, the strip of states, the places still on the card (#1965, seeded hiker)'
export const alt =
  'A challenge screen titled Where your trail karma is, with a sentence saying how many were earned on the trail and at home, a dark strip of fourteen state columns with gold marks, then rows grouped under Georgia and Virginia, a Not on the trail chip and Also on your card chips'

export default async function drive(page) {
  await seedChallenges(page)
  await openChallenges(page)
  await page.getByRole('button', { name: /A\.T\. Summer Bucket List/ }).click()
  await page.getByRole('button', { name: 'Where', exact: true }).click()
  await page.getByRole('heading', { name: /Where your trail karma is/ }).waitFor()
}
