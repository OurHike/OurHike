// A finished hike, as it lives in Plan afterwards (#1317).
//
// WHAT THIS SHOT IS EVIDENCE FOR. That "finished" here does not mean
// archived, greyed, or gone from where it used to be: the hike keeps its
// name, its dates, its sections and their provenance, and the closing line
// says it never leaves the list unless it is forgotten. Also that "0 mi to
// go" reads as a zero rather than as "unknown", which is the rule a finished
// hike is the test of.
//
// THE DRIVE IS HOW A HIKER ACTUALLY GETS BACK TO ONE: the pick sheet, where
// a finished hike sits beside the walking ones, and picking it lands here
// rather than on a Today screen with nothing planned.
import { seedLongHike, finishedStore } from './fixtures/longHike.mjs'

export const caption = 'A finished hike — still a hike, in Plan (#1317)'
export const alt =
  'A screen headed FINISHED HIKE with the hike name, a line carrying its dates, miles walked and 0 mi to go, its sections listed with their own figures and provenance, and three doors reading Share it with someone, Export it and Start another long hike'

export default async function drive(page) {
  await seedLongHike(page, finishedStore)
  await page.getByRole('radio', { name: 'Long hike' }).click()
  const sheet = page.getByRole('dialog', { name: 'Which long hike?' })
  await sheet.waitFor()
  // Scoped to the sheet: the Plan tab behind it lists the same hike, and an
  // unscoped query would click whichever the DOM ordered first.
  await sheet.getByRole('button', { name: /Springer → Dicks Creek Gap/ }).click()
  await page.getByText(/A finished hike is still a hike/).waitFor()
}
