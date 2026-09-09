// Planning a section without leaving the page (#1344).
//
// WHAT THIS SHOT IS EVIDENCE FOR. That the hike room's primary no longer
// throws a hiker at the map. It used to run `sweepForBuilder`, whose first
// act is `setActiveTab('map')`; the ask was "Plan the next section should be
// 'Plan a section', and that content should live on the same page", and this
// is that page, with the panel in the column where the primary was.
//
// WHAT TO LOOK FOR: the band still says "you're planning / Springer →
// Katahdin" and the Plan tab is still the selected one — the hiker has not
// gone anywhere. Under the sections, a blaze-bordered panel with From and To
// rows, and "Draw it on the map instead" as an explicit door rather than the
// default.
//
// WHAT IT IS NOT: a second route builder. Both ends are named with the route
// builder's OWN stop picker, and once they are named this same slot becomes
// `PlanTargetSheet` — the form that already turns two ends into a plan
// (planDaysVia + buildPlan). Nothing here lays out a day or prices a leg;
// chrome/SectionPlanner.tsx's header has the full argument.
import { seedLongHike } from './fixtures/longHike.mjs'

export const caption = 'Planning a section, on the page you were already on (#1344)'
export const alt =
  'The Plan tab headed "you’re planning / Springer → Katahdin" with a quietly outlined panel in the column reading "A section on this hike", a From row and a To row each offering "Choose a place", and a pill button reading "Draw it on the map instead" below them'

export default async function drive(page) {
  await seedLongHike(page)
  await page.getByRole('tab', { name: 'Plan' }).click()
  // Wait for the room before reaching for its primary - the same reason
  // long-hike-window-desktop.mjs waits, one screen along.
  await page.getByRole('heading', { level: 1, name: 'Springer → Katahdin' }).waitFor()
  await page.getByRole('button', { name: 'Plan a section' }).click()
  await page.getByRole('button', { name: /Draw it on the map instead/ }).waitFor()
}
