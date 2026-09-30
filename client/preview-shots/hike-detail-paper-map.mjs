// A published route's record naming the paper map its park is on (#1574 -
// A hiker on NYNJTC ground has nowhere to buy the paper map for where they
// are).
//
// WHAT THIS SHOT IS EVIDENCE FOR. The footer of a NYNJTC-published hike in
// Harriman now reads "The park is on sheets 118 and 119 of the New York-New
// Jersey Trail Conference’s" over a link, "Harriman-Bear Mountain Trails Map
// ›", to that product on their own store - and under it the sentence saying
// it is their map on their store and OurHike takes no cut. The join is by
// name: the route's park ("Harriman State Park", the publisher's own word)
// against the parks NYNJTC's own sheet index lists ("Southern Harriman State
// Park" on 118, "Northern Harriman State Park" on 119) - lib/paperMaps.ts.
//
// A SEPARATE RECIPE FROM hike-detail.mjs, deliberately. That shot's route is
// an OurHike pick in an invented forest, and it is evidence for four other
// things; giving it a park on a real sheet would change what it shows. This
// one seeds a single NYNJTC route whose park is on a sheet, so the frame is
// about the one line that is new.
//
// WHAT IT IS NOT EVIDENCE FOR. The real hike list, or NYNJTC's real store
// page: the route is invented (its prose, its publisher's page URL, its
// figures), and only the map product - its title, its sheets, its URL - is
// NYNJTC's, as pipeline/reference/nynjtc_paper_maps.json records it.
//
// Nothing here reaches an account, a hiker's own report, a dispersed
// campsite or a real location fix; the start is a made-up pin on public
// state parkland.

import { seedStewards } from './fixtures/stewards.mjs'
import { seedSuggestedHikes } from './fixtures/suggestedHikes.mjs'

const PINE_MEADOW = {
  id: 'nynjtc_hike_finder:118',
  name: 'Pine Meadow Lake loop',
  miles: 6.4,
  climb: null,
  difficulty: 'moderate',
  author: { kind: 'club', name: 'New York-New Jersey Trail Conference' },
  segments: [
    [
      { coord: [-74.09, 41.17], poiId: null },
      { coord: [-74.075, 41.18], poiId: null },
    ],
  ],
  routeProvenance: 'generated',
  routeGrade: 'strong',
  routeType: 'Loop',
  park: 'Harriman State Park',
}

const PINE_MEADOW_DETAIL = {
  id: 'nynjtc_hike_finder:118',
  url: 'https://example.org/hike/pine-meadow-lake-loop',
  publishedMiles: 6.6,
  overview: [
    'A lake loop on old roads and a rocky ridge, with the lake in view for most of the second half.',
  ],
  description: [
    'From the lot, follow the red-on-white blazes uphill past the stone bridge.',
    'At the lake, turn right and keep the water on your left all the way round.',
    'The last mile back is the road you came in on.',
  ],
  publication: {
    submittedBy: 'D. Chazin',
    submittedOn: '2018-06-09',
    verifiedOn: '2025-04-20',
  },
  start: { lat: 41.17, lon: -74.09, basis: 'marker' },
  routeType: 'Loop',
  park: 'Harriman State Park',
  trails: ['Pine Meadow Trail', 'Kakiat Trail'],
}

const DOCUMENT = { generated_at: '2026-09-17T12:00:00Z', hikes: [PINE_MEADOW] }

export const caption = 'A published route’s record, naming its paper map (#1574)'
export const alt =
  'The Pine Meadow Lake loop record: the title over New York-New Jersey Trail Conference, the figures, a Moderate badge with Loop · Harriman State Park, the save button, the Getting there card, the overview, the turn-by-turn, and a footer whose last lines read "The park is on sheets 118 and 119 of the New York-New Jersey Trail Conference’s" over a "Harriman-Bear Mountain Trails Map ›" link and a note that it is their map on their store and OurHike takes no cut'

export default async function drive(page) {
  // Stewards first, hikes second: the hikes fixture reloads the page once
  // and waits for the shelf, so both seeds are read on that one launch.
  await seedStewards(page)
  await seedSuggestedHikes(page, DOCUMENT, PINE_MEADOW_DETAIL)
  await page.getByRole('button', { name: /Find a hike/ }).click()
  await page.getByRole('heading', { name: 'Find a hike' }).waitFor()

  await page.getByRole('button', { name: /Pine Meadow Lake loop/ }).click()
  await page.getByRole('heading', { name: 'Pine Meadow Lake loop' }).waitFor()

  // The line the shot is about, which cannot render until the prose (and
  // its park) has arrived and the stewards have loaded - waiting on it is
  // waiting on both.
  const link = page.getByRole('link', { name: 'Harriman-Bear Mountain Trails Map ›' })
  await link.waitFor()
  await link.scrollIntoViewIfNeeded()
}
