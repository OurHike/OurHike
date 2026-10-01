// "Listen here", last on a waypoint's opened card (#1718 - Tag podcast
// episodes to the places they talk about, and show them last on each place's
// card; the maintainer's frame P1).
//
// NO EXISTING RECIPE REACHES THIS SECTION. waypoint-photo.mjs stops at the
// photograph and waypoint-conditions.mjs at the "Say something back" band;
// "Listen here" is under "About this place", the last thing on the card, so
// this drive opens the card and scrolls to the end of it.
//
// WHY A NAMED SHELTER, when the waypoint recipes search a category. An episode
// is tagged to one POI id, so the drive has to open that POI's card: the
// fixture tags an invented episode to Fingerboard Shelter's published id, and
// the drive searches for it by name. A rename upstream keeps the id and loses
// the search, which is the honest frame below rather than a wrong one.
//
// THREE HONEST FRAMES, named in the caption because photograph-preview.mjs
// reads it before the drive runs (#1058): the opened card ending in "Listen
// here" with the fixture episode; the opened card with no such section,
// where the kept list has not been read yet; and the search panel saying
// nothing is here, where the build has no POI artifacts at all.
//
// Nobody's data is in the frame: no account, no notes seeded, no location
// fix, an invented episode, and a shelter - a structure ATC publishes the
// location of, not one of the dispersed sites SOURCE_SURVEY.md §3b is about.
import { seedPodcastEpisodes } from './fixtures/podcasts.mjs'

export const caption =
  'A waypoint card ending in “Listen here”: an episode tagged to Fingerboard Shelter, last, under “About this place” (#1718)'
export const alt =
  'Either the bottom of the opened card for Fingerboard Shelter: the "About this place" section with its coordinates and source, then a "Listen here" section holding one invented episode with its show, title and length, a play circle, a download circle and a Listen button; or the same card without the section; or, where this build has no waypoint data, the search panel reading "Nothing here by that name."'

// The POI artifacts are several megabytes and are hashed before they are
// trusted (waypoint-photo.mjs's settle).
export const wait = 5000

export default async function drive(page) {
  // The route and the kept copy both have to be in place when the app wakes,
  // and nothing else in this drive reloads.
  await seedPodcastEpisodes(page)
  await page.reload()

  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('button', { name: 'Search' }).click()
  await page
    .getByRole('searchbox', { name: 'Search the downloaded map' })
    .fill('Fingerboard Shelter')

  const result = page
    .getByRole('button')
    .filter({ hasText: /Fingerboard Shelter/ })
    .first()
  await result.waitFor({ timeout: 20000 }).catch(() => {})
  if ((await result.count()) === 0) return
  await result.click()

  const expand = page.getByTestId('poi-card-expand')
  await expand.waitFor({ timeout: 15000 }).catch(() => {})
  if ((await expand.count()) === 0) return
  await expand.click()

  const listen = page.getByTestId('poi-card-listen')
  await listen.waitFor({ timeout: 15000 }).catch(() => {})
  if ((await listen.count()) === 0) return
  await listen.evaluate((element) => element.scrollIntoView({ block: 'end' }))
}
