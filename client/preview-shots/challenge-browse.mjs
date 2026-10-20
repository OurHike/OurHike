// Browse challenges (#1780, frame #5a, handoff revision 5).
//
// WHAT THIS SHOT IS EVIDENCE FOR. The three filters - Trail (opening on the
// trail the hiker chose, the A.T.), Club, Open now - and the list with no
// popularity sort and no hiker counts: with no plan on this phone there is
// no "On your plan" group, so both challenges sit under "Elsewhere on the
// A.T.", the ATC's labelled draft and joined, the invented record with Join.
// The footer counts what the trail filter shows, never who joined.
//
// SEEDED, AND SAID SO: fixtures/challenges.mjs.
import { openChallenges, seedChallenges } from './fixtures/challenges.mjs'

export const caption =
  'Browse challenges: Trail, Club, Open now; no popularity sort, no hiker counts (#1780, seeded)'
export const alt =
  'The Browse challenges screen with Trail, Club and Open now filters, then two challenge cards under an Elsewhere on the A.T. heading: the A.T. Summer Bucket List marked Joined with a draft label, and a preview club list with a Join button'

export default async function drive(page) {
  await seedChallenges(page)
  await openChallenges(page)
  await page.getByRole('button', { name: /Browse/ }).click()
  await page.getByRole('heading', { name: 'Browse challenges' }).waitFor()
}
