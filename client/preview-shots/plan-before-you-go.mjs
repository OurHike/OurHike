// The "Before you go" row on the Plan tab (#1689): the door to the Ten
// Essentials page, just above the room's own primary action.
//
// WHAT THIS SHOT IS EVIDENCE FOR. That the row is there, in the hike's room,
// and reads "N of 10 packed · gear at REI". The maintainer chose this spot
// over a row under More (poll, 2026-09-26, frame A of the mock). The same
// row sits in the day room and the sections room. PlanHome.test.tsx holds
// all three; this frame shows one.
//
// Scrolled to the row, because the hike room is long enough that the row is
// below the first screen on a phone.
//
// Nobody's data: the fixture hike plan-hike-room.mjs seeds, an invented
// hiker, no account, no location fix. Nothing is ticked, so the row reads
// "0 of 10 packed".
import { seedLongHike } from './fixtures/longHike.mjs'

export const caption =
  'The “Before you go” row on the hike’s Plan screen, the door to the Ten Essentials page (#1689, frame A)'
export const alt =
  'The Plan tab for the hike Springer → Katahdin, scrolled to a section headed "Before you go" with one row, "Pack the Ten Essentials, 0 of 10 packed, gear at REI", above the "Plan a section" button.'

export default async function drive(page) {
  await seedLongHike(page)
  await page.getByRole('tab', { name: 'Plan' }).click()
  await page.getByRole('heading', { level: 1, name: 'Springer → Katahdin' }).waitFor()
  const row = page.getByRole('button', { name: /Pack the Ten Essentials/ })
  await row.scrollIntoViewIfNeeded()
  await row.waitFor()
}
