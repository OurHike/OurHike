// The Today shelf (#1284): routes somebody published, and the way to the
// rest of them.
//
// WHAT THIS SHOT IS EVIDENCE FOR. That the section renders in the Today
// column with its rule, three cards on a rail that bleeds to the screen
// edges, the Find-a-hike row with its count, and the provenance note - and
// that a card with no published transit shows no bus, while a card with one
// shows the line and the walk. The third card is cut by the edge on
// purpose: that is how the rail says it scrolls.
//
// WHAT IT IS NOT EVIDENCE FOR. The nearest-first pick. The preview has no
// fix (the runner writes `onboarding_completed` alone and never requests
// location - a real fix is one of the four things a shot may never contain),
// so the shelf shows the first three published, which is the honest frame
// for a phone with no fix. The photos: the fixtures carry none, so every
// card shows the sunken block a route without one gets.
//
// Day mode is switched on so the section leads; in the other two modes it
// sits last, below the fold of a phone.

import { seedSuggestedHikes } from './fixtures/suggestedHikes.mjs'

export const caption = 'Today — the suggested-hikes shelf (#1284)'
export const alt =
  'The Today column in day mode with a Suggested hikes rule, three route cards on a horizontal rail showing name, distance and time, a difficulty badge, a transit line where one was published and who wrote the route, then a Find a hike row reading 6 more'

export default async function drive(page) {
  await seedSuggestedHikes(page)
  await page.getByRole('radio', { name: 'Day hike' }).click()
  await page.getByRole('button', { name: /Find a hike/ }).waitFor()
}
