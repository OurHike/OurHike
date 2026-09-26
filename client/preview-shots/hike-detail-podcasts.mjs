// The podcast card on a hike's detail screen, before the hiker has picked a
// podcast app (#1683, #1690).
//
// WHAT THIS SHOT IS EVIDENCE FOR. The card sits BELOW the provenance footer,
// the last thing on the screen ("should be the last thing you see", the
// maintainer, 2026-09-26), under a "Listen before you go" rule in the
// screen's own style. Each episode shows its show, title and length, with
// three controls beside the title: ▶ (Spotify's player, for everyone), a ↓
// circle, and a plain "Listen" - no app's name or icon, because nobody has
// picked one yet and the card assumes none (#1690's frame 1A). The line under
// the list says Listen or ↓ asks which app, once.
//
// WHAT IT IS NOT EVIDENCE FOR. Anything after a tap: podcast-app-picker.mjs
// is the ask, and today-long-hike-podcasts.mjs is a card after a pick. Play
// frames Spotify's player, which a recipe must not do - it would reach
// Spotify from CI on every future pull request.
import { seedPodcastEpisodes } from './fixtures/podcasts.mjs'
import { seedSuggestedHikes } from './fixtures/suggestedHikes.mjs'

export const caption =
  'Podcast episodes picked for a hike, last on its detail screen, before an app is picked (#1683, #1690)'
export const alt =
  'The bottom of the Wapiti to Docs Knob detail screen: the provenance footer, then a "Listen before you go" rule over a card headed "Picked for this hike", listing two invented episodes with their show, title and length, each with a play circle, a download circle and a plain Listen button beside the title, and a line under the list saying Listen or the download arrow asks which podcast app you use, once'

/** Open Wapiti's detail and bring the podcast card into view. Shared with
 *  podcast-app-picker.mjs, which goes one tap further. */
export async function reachTheCard(page) {
  // Before seedSuggestedHikes, which reloads: the route and the kept copy
  // both have to be in place when the app wakes.
  await seedPodcastEpisodes(page)
  await seedSuggestedHikes(page)
  await page.getByRole('button', { name: /Find a hike/ }).click()
  await page.getByRole('heading', { name: 'Find a hike' }).waitFor()

  await page.getByRole('button', { name: /Wapiti to Docs Knob/ }).click()
  await page.getByRole('heading', { name: 'Wapiti to Docs Knob' }).waitFor()
  // The prose arrives on its own object (#1473) and lengthens the screen
  // above the card, so the scroll waits for it.
  await page.getByText(/says 8\.5 mi/).waitFor()

  const card = page.getByRole('region', { name: 'Picked for this hike' })
  await card.waitFor()
  await card.evaluate((element) => element.scrollIntoView({ block: 'end' }))
  return card
}

export default async function drive(page) {
  await reachTheCard(page)
}
