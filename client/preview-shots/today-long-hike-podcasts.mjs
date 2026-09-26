// The podcast card on Today, on a long hike, for a hiker who picked Apple
// Podcasts (#1683, #1690).
//
// WHAT THIS SHOT IS EVIDENCE FOR. A "For today's stretch" card directly under
// "Today on your hike", titled with the leg it was matched to. The fixture's
// episode is tagged Neels Gap to Dicks Creek Gap (A.T. mi 31.7-69.6) and
// today's leg is Low Gap to Tray Mountain (mi 42.9-54.4), so the card is here
// because the two overlap - matched on this phone, with no GPS fix and
// nothing sent anywhere. The pick is Apple Podcasts, so the episode shows ▶,
// a ↓ circle, and "Listen on Apple Podcasts" beside Apple's icon, both
// linking to the episode's (invented) Apple Podcasts page; the line under
// the list says ↓ opens it in Apple Podcasts to download there.
//
// WHAT IT IS NOT EVIDENCE FOR. Anything after a tap, for the reason
// hike-detail-podcasts.mjs gives.
import { seedLongHike } from './fixtures/longHike.mjs'
import { pickPodcastApp, seedPodcastEpisodes } from './fixtures/podcasts.mjs'

export const caption =
  'Today, on a long hike — the episode picked for today’s stretch, in Apple Podcasts (#1683, #1690)'
export const alt =
  'The Today screen in long-hike mode, scrolled to the card headed "Today on your hike" for Low Gap Shelter to Tray Mountain Shelter, with a card directly below it reading "For today’s stretch" and "Picked for Low Gap Shelter → Tray Mountain Shelter", listing one invented episode with a play circle, a download circle and a Listen on Apple Podcasts button beside its title'

export default async function drive(page) {
  await seedPodcastEpisodes(page)
  await pickPodcastApp(page, 'apple_podcasts')
  await seedLongHike(page)
  const card = page.getByRole('region', { name: /^Picked for / })
  await card.waitFor()
  await card.evaluate((element) => element.scrollIntoView({ block: 'end' }))
}
