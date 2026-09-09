// One published route's detail (#1290, wireframe `1g`).
//
// WHAT THIS SHOT IS EVIDENCE FOR. The screen the finder's cards now open,
// and specifically the four places it refuses to overstate:
//
//  - THE TWO FIGURES. "7.9 mi" is what this build measured on the trail
//    lines it holds; the line under it names that and prints the
//    publisher's own 8.5 mi beside it. On the routes shipping today the
//    two differ by up to a fifth, and one dressed as the other would be a
//    display outrunning its source.
//  - NO TIME. The fixture's climb is null, so the figures line reads
//    "no time - climb unmeasured" rather than pricing an unmeasured climb
//    as flat ground - which is what a time computed from zero would be.
//  - THE START, AND WHERE IT CAME FROM. The coordinates are read off the
//    centre of the map on the publisher's page rather than a placed pin,
//    and the card says exactly that before offering directions to them.
//  - THE LINE IS OURS. The footer says the route a map would draw is
//    OurHike's construction of their description, not a track anybody
//    walked with a GPS.
//
// It is also the shot for the widened difficulty ladder: "Moderate to
// Strenuous" is one of the two compound levels #1290 added, in the
// publisher's own spelling rather than rounded to a neighbour.
//
// WHAT IT IS NOT EVIDENCE FOR. A photo and its credit: the fixtures carry
// none (a recipe pointing at somebody's photograph would republish it on
// every future pull request), so the hero is the sunken block. The save
// button: nothing is saved here, so it reads "Save to my hikes" - the
// walked line and "Open on map" are hike-detail-saved.mjs. The whole
// turn-by-turn: two paragraphs show and the rest is behind the button,
// which is the folded state this screen opens in.

import { seedSuggestedHikes } from './fixtures/suggestedHikes.mjs'

export const caption =
  'A published route’s detail — two figures, from two parties (#1290)'
export const alt =
  'The Wapiti to Docs Knob detail screen: the title over Vernon Trails, a figures line reading 7.9 mi and no time because the climb is unmeasured, a line naming that measurement as this phone’s and 8.5 mi as the publisher’s, a Moderate to Strenuous badge, a note about the turnaround, a Save to my hikes button, a Getting there card whose coordinates say they were read from a map centre rather than a placed pin, the overview, the first two turn-by-turn paragraphs with a Read all 4 paragraphs button, and a footer crediting the publisher’s words'

export default async function drive(page) {
  await seedSuggestedHikes(page)
  await page.getByRole('button', { name: /Find a hike/ }).click()
  await page.getByRole('heading', { name: 'Find a hike' }).waitFor()

  await page.getByRole('button', { name: /Wapiti to Docs Knob/ }).click()
  await page.getByRole('heading', { name: 'Wapiti to Docs Knob' }).waitFor()
  await page.getByText(/measured on the trail lines this phone holds/).waitFor()
}
