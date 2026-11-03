// One challenge (#1780, frame #5): the ATC's list, open.
//
// WHAT THIS SHOT IS EVIDENCE FOR. The pine header - org, trail and window,
// the name, the DRAFT label, the ATC's own summary line, 3 of 25 and the bar
// - and the strip laying every place on the list along the trail in mile
// order, Springer to Katahdin, the tagged ones filled. Under it the filter
// pills (On the trail · Learn · Anywhere · Protect · Mystery) and the "On
// the trail" rows: each place with its published mile, "done" where the
// day's walk tagged it, Tag it where a hand tag is allowed, and the two towns
// saying they are off the trail and tagged by hand.
//
// The Triple Crown row lists its three peaks, each its own Tag it (review,
// 2026-09-30), and Leave this challenge asks before it leaves.
//
// THE CLOCK IS INSIDE THE WINDOW, fixed by `before` the way the camp card's
// recipe fixes its evening: the ATC's 2027 draft opens May 15, and on any
// earlier day the page offers no Tag it at all and says "Opens May 15" -
// which is right, and is not what this shot is for.
//
// SEEDED, AND SAID SO: fixtures/challenges.mjs.
import { EVENING, openChallenges, seedChallenges } from './fixtures/challenges.mjs'

export async function before(page) {
  await page.clock.setFixedTime(EVENING)
}

export const caption =
  'One challenge: the ATC’s list, its places along the trail, On the trail (#1780, seeded hiker)'
export const alt =
  'A challenge screen with a dark green header reading A.T. Summer Bucket List, a draft label, 3 of 25 for the drawing, a progress bar and a line of yellow diamonds, then filter pills and rows of places with their mile markers'

export default async function drive(page) {
  await seedChallenges(page)
  await openChallenges(page)
  await page.getByRole('button', { name: /A\.T\. Summer Bucket List/ }).click()
  await page.getByRole('heading', { name: 'A.T. Summer Bucket List' }).waitFor()
}
