// Stepping away from a long hike (#1317).
//
// WHAT THIS SHOT IS EVIDENCE FOR. That every door names its consequence
// rather than only its verb - "The day stays; the ones after it shift by
// one", "Keeps the mile you stopped at", "Closes the hike and keeps every
// section in it" - and that the one destructive door carries the danger
// colour on its NAME while its note carries the reassurance, because both
// are true at once. A sheet of bare verbs would make forgetting a hike look
// like taking a zero, which is the failure this copy exists to prevent.
import { seedLongHike } from './fixtures/longHike.mjs'

export const caption = 'Stepping away — every door named by what it does (#1317)'
export const alt =
  'A bottom sheet titled "Step away from this hike" listing a zero, a town night, pausing, turning around and finishing, each with a sentence saying what happens to the record, and a final "Forget this hike" in the danger colour noting that every section stays in Plan'

export default async function drive(page) {
  await seedLongHike(page)
  await page.getByRole('tab', { name: 'More' }).click()
  await page.getByRole('button', { name: /^You/ }).click()
  await page.getByRole('button', { name: 'Springer → Katahdin' }).click()
  await page.getByRole('dialog', { name: 'Step away from this hike' }).waitFor()
}
