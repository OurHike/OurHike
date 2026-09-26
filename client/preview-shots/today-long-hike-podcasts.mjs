// The podcast card on Today, on a long hike (#1683 - Offer podcast episodes
// picked for the hike, with a one-tap Spotify save and an in-app player).
//
// WHAT THIS SHOT IS EVIDENCE FOR. Frame 3 of the mock the maintainer chose on
// 2026-09-26: a "For today's stretch" card directly under "Today on your
// hike", titled with the leg it was matched to. The fixture's episode is
// tagged Neels Gap to Dicks Creek Gap (A.T. mi 31.7-69.6) and today's leg is
// Low Gap to Tray Mountain (mi 42.9-54.4), so the card is here because the
// two overlap - matched on this phone, with no GPS fix and nothing sent
// anywhere.
//
// WHAT IT IS NOT EVIDENCE FOR. Anything after a tap, for the reason
// hike-detail-podcasts.mjs gives, or the Save button in a build with no
// VITE_SPOTIFY_CLIENT_ID (it reads "Open in Spotify ↗" there).
import { seedLongHike } from './fixtures/longHike.mjs'
import { seedPodcastEpisodes } from './fixtures/podcasts.mjs'

export const caption =
  'Today, on a long hike — the episode picked for today’s stretch (#1683)'
export const alt =
  'The Today screen in long-hike mode, scrolled to the card headed "Today on your hike" for Low Gap Shelter to Tray Mountain Shelter, with a card directly below it reading "For today’s stretch" and "Picked for Low Gap Shelter → Tray Mountain Shelter", listing one invented episode with a round play icon and a Save button carrying the Spotify icon beside its title'

export default async function drive(page) {
  await seedPodcastEpisodes(page)
  await seedLongHike(page)
  const card = page.getByRole('region', { name: /^Picked for / })
  await card.waitFor()
  await card.evaluate((element) => element.scrollIntoView({ block: 'end' }))
}
