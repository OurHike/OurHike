// Today with the season at the bottom (#1964, frame
// features/design/blaze-card/Home.dc.html): the seeded hiker has joined the
// ATC's list, so the last thing on Today is the strip - the mini card, how
// much trail karma, the states, "25 enters the drawing" - under everything about
// today. Scrolled to the foot, which is the point.
//
// SEEDED, AND SAID SO: fixtures/challenges.mjs; the clock inside the window.
import { EVENING, seedChallenges } from './fixtures/challenges.mjs'

export async function before(page) {
  await page.clock.setFixedTime(EVENING)
}

export const caption =
  'Today, once joined: the season strip is the last thing on the page (#1964, seeded hiker)'
export const alt =
  'The foot of the Today screen with an eyebrow reading Your summer on the A.T. and a dark green strip holding a tiny card of tiles, 4 trail karma, the states, and the list’s name and finish line'

export default async function drive(page) {
  await seedChallenges(page)
  await page.getByRole('tab', { name: 'Today' }).click()
  const strip = page.locator('.season__strip')
  await strip.waitFor()
  await strip.scrollIntoViewIfNeeded()
}
