// A tagged place (#1780, frame #4b): McAfee Knob, tagged from the day's walk.
//
// WHAT THIS SHOT IS EVIDENCE FOR. No stamp and no animation: the place's
// name and the moment it was tagged over the photo slot, "Your line" - ten
// miles either side with the hiker's walked miles filled and the list's
// places as diamonds - and the one-line register field that stays on the
// phone. The photo slot is the chrome here because the seeded hiker added no
// photo of their own and the ATC's draft carries no club photo; the moment
// line has a date and a time and no weather, which the phone never kept
// against a tag.
//
// And "Remove this tag" beside Done, for the hiker who pressed Tag all after
// walking past the junction without going up (review, 2026-09-30).
//
// SEEDED, AND SAID SO: fixtures/challenges.mjs. No walked miles are seeded,
// so the line draws only its track.
import { openChallenges, seedChallenges } from './fixtures/challenges.mjs'

export const caption =
  'A tagged place: McAfee Knob, its moment, your line, a private register line (#1780, seeded)'
export const alt =
  'A full-screen sheet headed by a dark panel reading A.T. Summer Bucket List and McAfee Knob Summit with a date and time, then a Your line strip with yellow diamonds, a One line for the register field reading Stays on this phone, and Done and Remove this tag buttons'

export default async function drive(page) {
  await seedChallenges(page)
  await openChallenges(page)
  await page.getByRole('button', { name: /A\.T\. Summer Bucket List/ }).click()
  await page.getByRole('button', { name: /Take the McAfee Knob shuttle/ }).click()
  await page.getByRole('dialog').waitFor()
}
