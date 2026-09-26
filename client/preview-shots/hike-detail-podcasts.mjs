// The podcast card on a hike's detail screen (#1683 - Offer podcast episodes
// picked for the hike, with a one-tap Spotify save and an in-app player).
//
// WHAT THIS SHOT IS EVIDENCE FOR. Frame 1 of the mock the maintainer chose on
// 2026-09-26, as the app draws it: the card sits BELOW the provenance footer,
// the last thing on the screen ("should be the last thing you see"), under a
// "Listen before you go" rule in the screen's own style, with each episode's
// show, title and length, its two icons beside the title (the maintainer's
// pick after the first build, poll 2026-09-26), and the line under the list
// that says what the icons do and that the first save connects Spotify once.
//
// WHAT IT IS NOT EVIDENCE FOR. Anything after a tap. Play frames Spotify's
// player and Save leaves for Spotify's sign-in, and a recipe doing either
// would reach Spotify from CI on every future pull request. The Save button
// itself is drawn only in a build given VITE_SPOTIFY_CLIENT_ID; where the
// repository variable is unset, this frame shows "Open in Spotify ↗" in its
// place, which is also a true picture of that build.
import { seedPodcastEpisodes } from './fixtures/podcasts.mjs'
import { seedSuggestedHikes } from './fixtures/suggestedHikes.mjs'

export const caption =
  'Podcast episodes picked for a hike, the last thing on its detail screen (#1683)'
export const alt =
  'The bottom of the Wapiti to Docs Knob detail screen: the provenance footer, then a "Listen before you go" rule over a card headed "Picked for this hike", listing two invented episodes with their show, title and length, each with a round play icon and a round plus icon beside the title, and a line under the list saying the play icon plays it here, the plus saves it to Spotify, and the first time asks to connect once'

export default async function drive(page) {
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
}
