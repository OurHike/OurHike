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
//
// 2026-09-10, re-photographed for #1373 (D10, inventory P20 and P31). TWO
// doors now, not three: "Export it" was wired to a handler that did nothing
// and no GPX/GeoJSON writer exists, so the door is gone until one does. And
// the note under the sections - "Some sections show distance alone" - is
// derived from the rows now rather than hard-coded off; the preview's
// download carries no elevation profile (#1313), so the note is what this
// frame shows, and it is the truth about that download.
import { seedLongHike, finishedStore } from './fixtures/longHike.mjs'

export const caption = 'A finished hike — still a hike, in Plan (#1317)'
export const alt =
  'A screen headed FINISHED HIKE with the hike name, a line carrying its dates, miles walked and 0 mi to go, its sections listed with their own figures and provenance, a note saying some sections show distance alone, and two doors reading Share it with someone and Start another long hike'

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
