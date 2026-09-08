// Find a hike (#1284): the results, with the applied filters as chips.
//
// WHAT THIS SHOT IS EVIDENCE FOR. The results view a sheet's "Show N hikes"
// pushes: the count as the title, the sort control, the applied filters as
// removable chips with "+ filter" after them, the first result promoted to a
// full-bleed card and the rest as rows, and the footer naming transit as the
// publisher listed it. The drive applies two facets - by transit, then under
// two hours - so two chips are on the row and the count is the one both
// leave: four of the nine fixtures, enough for a hero and three rows.
//
// WHAT IT IS NOT EVIDENCE FOR. "Nearest first": with no fix and no place
// picked there is nothing to measure from, so the control offers shortest
// and easiest and the title reads "shortest first". A photo on the hero:
// the fixtures carry none, so the hero shows the sunken block.

import { seedSuggestedHikes } from './fixtures/suggestedHikes.mjs'

export const caption = 'Find a hike — results with removable filter chips (#1284)'
export const alt =
  'The results screen titled 4 hikes with a shortest first sort control, two applied filter chips reading Under 2 h and By transit with a plus filter chip after them, a full-bleed first result and three rows beneath it'

export default async function drive(page) {
  await seedSuggestedHikes(page)
  await page.getByRole('button', { name: /Find a hike/ }).click()
  await page.getByRole('heading', { name: 'Find a hike' }).waitFor()

  await page.getByRole('button', { name: 'Transit ▾' }).click()
  await page.getByRole('button', { name: /Reachable by public transport/ }).click()
  await page.getByRole('button', { name: /Show \d+ hikes/ }).click()

  await page.getByRole('button', { name: '+ filter' }).click()
  await page.getByRole('button', { name: 'Time ▾' }).click()
  await page.getByRole('button', { name: /Under 2 hours/ }).click()
  await page.getByRole('button', { name: /Show \d+ hikes?/ }).click()

  await page.getByRole('button', { name: /By transit/ }).waitFor()
}
