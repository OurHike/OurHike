// Plan's card for a joined challenge (#1780, frame #6).
//
// WHAT THIS SHOT IS EVIDENCE FOR. Under the day list: "Challenge places on
// this route" - each ATC place on the planned section with the day it falls
// on and its mile - and the amber line saying every place of Virginia's Triple
// Crown is on this route. The plan itself is untouched: the same days, miles
// and targets as without the card.
//
// SEEDED, AND SAID SO: fixtures/challenges.mjs - an invented section plan at
// real A.T. miles, and the seeded hiker who joined the ATC's draft.
import { planStore, seedChallenges } from './fixtures/challenges.mjs'

export const caption = 'Plan: the ATC’s places on this route, by day (#1780, seeded plan)'
export const alt =
  'The Plan tab with a section plan’s days, and beneath them a card titled Challenge places on this route listing Dragons Tooth Peak, McAfee Knob and Tinker Cliffs with day numbers and mile markers'

export default async function drive(page) {
  await seedChallenges(page, { trips: planStore() })
  await page.getByRole('tab', { name: 'Plan' }).click()
  // Plan opens on the hike's room; the day list - and the card under it -
  // is the section's, one tap in.
  await page
    .getByRole('button', { name: /^Pearisburg → Daleville\s*\d/ })
    .first()
    .click()
  const card = page.getByRole('heading', { name: 'Challenge places on this route' })
  await card.waitFor()
  await card.scrollIntoViewIfNeeded()
}
