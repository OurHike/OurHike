// Find a hike (#1284), with the Time sheet open over it.
//
// WHAT THIS SHOT IS EVIDENCE FOR. The search screen pushed from Today's
// shelf - the crumb back, the field, the facet chips - and one facet sheet
// at a time docked over it: the four time buckets each carrying the count
// it would leave, "2 – 4 hours" picked and its count in brand green beside
// the check, the caveat that a time is a walking duration at the hiker's
// pace and never an arrival, and the footer's Clear beside "Show N hikes"
// saying the number it is about to show. The Time chip behind the scrim
// wears the set styling while its sheet is up.
//
// WHAT IT IS NOT EVIDENCE FOR. "Near me": there is no fix in a preview run,
// so that chip cannot appear and must not be made to. The rule above the
// list therefore reads "Routes on this phone" rather than "Near you".

import { seedSuggestedHikes } from './fixtures/suggestedHikes.mjs'

export const caption = 'Find a hike — one facet sheet at a time (#1284)'
export const alt =
  'The Find a hike screen with its search field and facet chips, and the Time to complete sheet docked over it: four options with counts, 2 – 4 hours selected, a caveat about walking durations, and Clear beside Show hikes'

export default async function drive(page) {
  await seedSuggestedHikes(page)
  await page.getByRole('button', { name: /Find a hike/ }).click()
  await page.getByRole('heading', { name: 'Find a hike' }).waitFor()
  await page.getByRole('button', { name: 'Time ▾' }).click()
  await page.getByRole('dialog', { name: 'Time to complete' }).waitFor()
  await page.getByRole('button', { name: /2 – 4 hours/ }).click()
  await page.getByRole('button', { name: /Show \d+ hikes/ }).waitFor()
}
