// What's left (#791), reached from the hike's own room (#1373, frame 8b).
//
// WHAT THIS SHOT IS EVIDENCE FOR. Two things. That the screen opens with
// TWO FIGURES - walked and to go - and nothing else at its head: no
// percentage, no pace anybody could be behind, which is OurHikeValues.md #1
// and what WhatsLeft.test.tsx's standing guard holds. And that it is one tap
// from the Plan tab now: "What's left ›" sits beside "This hike, end to end"
// in the hike room (plan-hike-room.mjs is that frame), where it used to be
// at the foot of the hike zoom, two taps down and past every section row.
//
// WHAT TO LOOK FOR under the figures: "in N pieces", the gap cards with
// BOTH ends of each gap offered (flip-floppers are the design, not an edge
// case), and at the foot "Change the plan from here ›" - the way back into
// the open section's days, where the cascade lives (frame 7). No "Export
// GPX" beside it, though the frame draws one: no writer exists, and a door
// is a claim.
//
// Nobody's data: the same fixture hike plan-hike-room.mjs seeds - an
// invented hiker, no account, no location fix, so "Nearest me" is absent
// rather than dead.
import { seedLongHike } from './fixtures/longHike.mjs'

export const caption =
  'What’s left, one tap from the hike room — two figures at the head, the gaps under them, the way back into the plan at the foot (#1373, frame 8b)'
export const alt =
  'A screen headed "What’s left" with two figures, Walked and To go, each with its miles; a line reading "in N pieces"; a day-count control reading "I have 5 days"; gap cards each naming both ends with "North from …" and "South from …" rows; and a door at the foot reading "Change the plan from here"'

export default async function drive(page) {
  await seedLongHike(page)
  await page.getByRole('tab', { name: 'Plan' }).click()
  await page.getByRole('heading', { level: 1, name: 'Springer → Katahdin' }).waitFor()
  await page.getByRole('button', { name: /What’s left/ }).click()
  await page.getByRole('heading', { name: 'What’s left' }).waitFor()
}
