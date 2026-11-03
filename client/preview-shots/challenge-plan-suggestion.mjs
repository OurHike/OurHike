// Plan's suggestion when no joined challenge touches the route (#1780, frame
// #6b, handoff revision 6).
//
// WHAT THIS SHOT IS EVIDENCE FOR. One suggestion and never more: a dashed
// "Challenge on your route" card under the day list, the ATC's list labelled
// draft, its first three places on this plan by day and "+N more on this
// hike", then Join and Hide. Suggested is not joined - no pins, no camp card,
// nothing queued until Join.
//
// SEEDED, AND SAID SO: fixtures/challenges.mjs - the same invented plan, and
// a hiker who has joined nothing.
import { UNJOINED_STATE, planStore, seedChallenges } from './fixtures/challenges.mjs'

export const caption =
  'Plan: one challenge suggested for this route, with Join and Hide (#1780, seeded plan)'
export const alt =
  'The Plan tab with a dashed card under the day list reading Challenge on your route, A.T. Summer Bucket List with a draft label, three places by day, a plus more line, and Join and Hide buttons'

export default async function drive(page) {
  await seedChallenges(page, { state: UNJOINED_STATE, trips: planStore() })
  await page.getByRole('tab', { name: 'Plan' }).click()
  // Plan opens on the hike's room; the day list - and the card under it -
  // is the section's, one tap in.
  await page
    .getByRole('button', { name: /^Pearisburg → Daleville\s*\d/ })
    .first()
    .click()
  const card = page.getByText('Challenge on your route')
  await card.waitFor()
  await card.scrollIntoViewIfNeeded()
}
