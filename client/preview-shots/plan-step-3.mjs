// Step 3 of the planning spine for a long hike (#1373, frame 5b): the
// route's own head, the target control, and THE DAYS BEFORE THEY ARE KEPT -
// one DayRow per day the target makes, priced at the hiker's pace where
// the profile covers the ground - under the rail "Long hike ✓ · Route ✓ ·
// Details", with "‹ Route" and "Save this long hike" at the foot.
//
// The drive is the long hike's whole spine, step by step, and every wait
// past the mode switch is guarded: the corridor on the preview's bucket
// gives the entrance and the stop picker real waypoints to name, and a
// search that finds nothing leaves the picker as the frame. What the shot
// is evidence for is the sheet itself; which stops it names depends on the
// bucket, which is why they are searched rather than assumed.
//
// Nobody's data: the fixture's invented hike over the A.T.'s published mile
// axis (fixtures/longHike.mjs), no account, no location fix.
export const caption =
  'Step 3 for a long hike — the days laid out before they are kept, each priced, under the rail; Save is the last button (#1373, frame 5b)'
export const alt =
  'Either step 3 of the spine for a long hike: a sheet opening with the three-stop rail reading Long hike ✓, Route ✓ and Details with Details lit, the route\u2019s ends as a heading with its miles, day count and climb, the "How long is a day?" control with Walking hours and Miles, the days as rows - D1, D2 … each with an arrow to where it ends, its miles, ≈time and climb - an "All N days ›" door where there are more than four, and a foot with "‹ Route" and "Save this long hike"; or, where the drive could not name a start, the stop picker or the entrance sheet asking where from'

export const wait = 4000

import { seedLongHike } from './fixtures/longHike.mjs'

const SHELTER = 'Fingerboard Shelter'

export default async function drive(page) {
  // The kind is the mode (D6): a long hike, seeded with the fixture every
  // long-hike recipe shares rather than set up in the drive. The first
  // version of this recipe went through "A new long hike" and clicked
  // "Start this long hike" on a hike with no ends, which the screen
  // refuses (lib/hikeText.ts's setupRefusal: "A long hike needs two ends")
  // - the preview at 88891547 caught it as a disabled button. The fixture
  // is Springer → Katahdin with a section behind it, which is also the
  // honest state for step 3's head to print against.
  await seedLongHike(page)

  // Step 1, then the A.T. builder's entrance (frame 4c) by the map door.
  await page
    .getByRole('group', { name: 'Find or plan a hike' })
    .getByRole('button', { name: 'Plan a hike' })
    .click()
  await page.getByRole('heading', { name: 'Where do you want to go?' }).waitFor()
  await page.getByRole('button', { name: 'Pick on the map' }).click()
  await page.getByText('Where from?').waitFor()

  // A start by name, through the picker every stop field opens (frame 4d).
  const start = page.getByRole('button', { name: /Start/ }).first()
  await start.waitFor({ timeout: 5000 }).catch(() => {})
  if ((await start.count()) === 0) return
  await start.click()
  const search = page.getByLabel('Search for a stop')
  await search.waitFor({ timeout: 5000 }).catch(() => {})
  if ((await search.count()) === 0) return
  await search.fill(SHELTER)
  const hit = page.getByRole('button', { name: new RegExp(SHELTER) }).first()
  await hit.waitFor({ timeout: 15000 }).catch(() => {})
  if ((await hit.count()) === 0) return
  await hit.click()

  // The stretch, then the stops panel (step 2), then step 3.
  const use = page.getByRole('button', { name: 'Use this stretch' })
  await use.waitFor({ timeout: 10000 }).catch(() => {})
  if ((await use.count()) === 0) return
  await use.click()
  const on = page.getByRole('button', { name: 'Use this route' })
  await on.waitFor({ timeout: 10000 }).catch(() => {})
  if ((await on.count()) === 0) return
  await on.click()
  await page.getByRole('region', { name: 'The days' }).waitFor({ timeout: 10000 })
}
