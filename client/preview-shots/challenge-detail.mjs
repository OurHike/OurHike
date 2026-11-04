// One challenge (#1780, frame #5): the ATC's list, open.
//
// WHAT THIS SHOT IS EVIDENCE FOR. The pine header - org, trail and window,
// the name, the draft banner (one line, not a chip - #1961), the ATC's own
// summary line, 3 of 25 and the bar - and the strip laying every place on
// the list along the trail in mile order, Springer to Katahdin, the earned
// ones filled. Under it the pills in the ATC's own order (Learn · Experience
// · Protect · Mystery, then Done) and the Learn rows, numbered as the ATC's
// paper list numbers them: a place with its published mile, "done" where the
// day's walk earned it, Earn it where a hand tag is allowed, the towns saying
// they are off the trail, and no sub-line at all under an at-home item.
// Under the list, the one status line.
//
// The Triple Crown row (under Experience) lists its three peaks, each its
// own Earn it (review, 2026-09-30), and Leave this challenge asks before it
// leaves.
//
// THE CLOCK IS INSIDE THE WINDOW, fixed by `before` the way the camp card's
// recipe fixes its evening: the ATC's 2027 draft opens May 13, and on any
// earlier day the page offers no Earn it at all and says "Opens May 13" -
// which is right, and is not what this shot is for.
//
// SEEDED, AND SAID SO: fixtures/challenges.mjs.
import { EVENING, openChallenges, seedChallenges } from './fixtures/challenges.mjs'

export async function before(page) {
  await page.clock.setFixedTime(EVENING)
}

export const caption =
  'One challenge: the ATC’s list in the ATC’s sections, numbered, with one status line (#1780, #1961, seeded hiker)'
export const alt =
  'A challenge screen with a dark green header reading A.T. Summer Bucket List, a one-line draft banner, 3 of 25 for the drawing, a progress bar and a line of yellow diamonds, then the pills Learn, Experience, Protect, Mystery and Done, and numbered rows of the Learn items'

export default async function drive(page) {
  await seedChallenges(page)
  await openChallenges(page)
  await page.getByRole('button', { name: /A\.T\. Summer Bucket List/ }).click()
  await page.getByRole('heading', { name: 'A.T. Summer Bucket List' }).waitFor()
}
