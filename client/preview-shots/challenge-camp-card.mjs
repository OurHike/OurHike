// Today's camp card (#1780, frame #3): "From today's walk".
//
// WHAT THIS SHOT IS EVIDENCE FOR. The one question a challenge asks, at the
// top of Today once the day is over: the places the day's walked miles
// passed and the hiker has not tagged, each with its mile, then Tag all and
// Not tonight. Here that is McAfee Knob Summit as a peak of Virginia's
// Triple Crown - the seeded hiker already tagged the shuttle item there -
// and, with waypoint data under it, Campbell Shelter for "any shelter".
// Nothing about what was not passed, and no count of it.
//
// HOW IT GETS THERE. The page clock is fixed at 7:30 pm on 14 July 2027 (in
// the recipe's `before`), because the card waits for the day to be over and
// the seeded hiker called no day and logged no walk; the day's walk is
// lib/passedToday.ts's own record, miles 710 to 716.
//
// SEEDED, AND SAID SO: fixtures/challenges.mjs.
import { EVENING, PASSED_MCAFEE, seedChallenges } from './fixtures/challenges.mjs'

export const caption =
  'Today’s camp card: what the day’s walk passed, Tag all or Not tonight (#1780, seeded day)'
export const alt =
  'The Today screen with a dark green card at the top reading From today’s walk, You passed places on your challenges. Tag them?, a row for the McAfee Knob item with its mile marker, and Tag all and Not tonight buttons'

export async function before(page) {
  await page.clock.setFixedTime(EVENING)
}

export default async function drive(page) {
  await seedChallenges(page, { passedToday: PASSED_MCAFEE })
  await page.getByRole('tab', { name: 'Today' }).click()
  await page.getByText('From today’s walk').waitFor()
}
