// More → Challenges (#1780, frame #2b): the challenges a hiker joined.
//
// WHAT THIS SHOT IS EVIDENCE FOR. The ATC's A.T. Summer Bucket List on the
// chrome card a challenge with a finish line gets - its org and closing date
// in the eyebrow, the DRAFT label the maintainer made the condition of
// publishing it (poll, 2026-09-30), "3 of 25 for the drawing" and the 6 px
// bar - three, not four, because the seeded Triple Crown is one peak in and
// counts only when all three are - then the Browse row with how many more
// are on offer. The mock's
// "11 wk" countdown is deliberately absent (VOLUNTEERING.md §5 rule 2).
//
// SEEDED, AND SAID SO: fixtures/challenges.mjs - the ATC items are the
// published list's own, the hiker and their four tags are nobody's.
import { openChallenges, seedChallenges } from './fixtures/challenges.mjs'

export const caption =
  'More → Challenges: the ATC’s list, labelled draft, 3 of 25 (#1780, seeded hiker)'
export const alt =
  'The Your challenges screen: a dark green card reading ATC until Sep 1, A.T. Summer Bucket List, a Draft not yet confirmed by the ATC label, 3 of 25 for the drawing and an orange progress bar, then a dashed row reading 1 more on trails near you, Browse'

export default async function drive(page) {
  await seedChallenges(page)
  await openChallenges(page)
}
