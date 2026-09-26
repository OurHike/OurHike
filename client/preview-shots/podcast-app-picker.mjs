// "Which app do you listen in?" - the podcast card's first-tap ask (#1690 -
// Let a hiker pick their podcast app once, the maintainer's frame 2).
//
// WHAT THIS SHOT IS EVIDENCE FOR. Tapping Listen on a card with no app picked
// opens the list inside the card: Spotify, Apple Podcasts, Pocket Casts,
// Overcast and YouTube Music, each beside its own icon, and the line saying
// the pick is kept on this phone and changed in More → Settings. The tap
// reaches nothing outside the app - no link is followed until an app is
// picked, and nothing is picked here.
//
// WHAT IT IS NOT EVIDENCE FOR. The card after a pick, which
// today-long-hike-podcasts.mjs photographs.
import { reachTheCard } from './hike-detail-podcasts.mjs'

export const caption = 'The podcast card asking which app you listen in, once (#1690)'
export const alt =
  'The podcast card at the bottom of the Wapiti to Docs Knob detail screen, showing the heading "Which app do you listen in?" over a list of five podcast apps with their icons - Spotify, Apple Podcasts, Pocket Casts, Overcast and YouTube Music - and a line saying the choice is kept on this phone and can be changed in More, then Settings'

export default async function drive(page) {
  const card = await reachTheCard(page)
  await card
    .getByRole('button', { name: /^Listen to .* in your podcast app$/ })
    .first()
    .click()
  await card.getByText('Which app do you listen in?').waitFor()
  await card.evaluate((element) => element.scrollIntoView({ block: 'end' }))
}
