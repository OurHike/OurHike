// "On the A.T. Summer Bucket List" on McAfee Knob Summit's card (#1780,
// frames #2 and #2c).
//
// WHAT THIS SHOT IS EVIDENCE FOR. The section above "About this place": the
// two items at this place - the shuttle hike and the Triple Crown - each
// credited to its list and its club, the draft label, "done" on the one the
// seeded hiker's walk already tagged and Tag it on the other, and the line
// saying what leaves the phone.
//
// WHEN IT SHOWS LESS. The card is reached by searching the downloaded
// waypoints, as waypoint-photo.mjs reaches one. A build with no waypoint data
// (this sandbox) finds nothing, and the frame is the search panel - which is
// the honest answer, said here rather than discovered.
//
// SEEDED, AND SAID SO: fixtures/challenges.mjs.
import { seedChallenges } from './fixtures/challenges.mjs'

export const caption =
  'A place card’s challenge section: McAfee Knob Summit on the ATC’s draft list (#1780, seeded hiker)'
export const alt =
  'A waypoint card for McAfee Knob Summit, opened, with a section headed On the A.T. Summer Bucket List listing two items with a draft label, one marked done and one with a Tag it button; or, where the build has no waypoint data, the search panel'

export const wait = 5000

export default async function drive(page) {
  await seedChallenges(page)
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('button', { name: 'Search' }).click()
  await page
    .getByRole('searchbox', { name: 'Search the downloaded map' })
    .fill('McAfee Knob Summit')
  const hit = page
    .getByRole('button')
    .filter({ hasText: /McAfee Knob Summit/ })
    .first()
  await hit.waitFor({ timeout: 20000 }).catch(() => {})
  if ((await hit.count()) === 0) return
  await hit.click()
  const expand = page.getByTestId('poi-card-expand')
  await expand.waitFor({ timeout: 15000 }).catch(() => {})
  if ((await expand.count()) === 0) return
  await expand.click()
  const section = page.getByRole('region', { name: 'Challenges' })
  await section.waitFor({ timeout: 15000 }).catch(() => {})
  if ((await section.count()) > 0) await section.scrollIntoViewIfNeeded()
}
