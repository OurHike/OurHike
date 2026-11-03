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
//
//    SINCE #1473 THOSE TWO FIGURES COME FROM TWO OBJECTS. The 7.9 is on
//    the shelf record; the publisher's 8.5 arrives with the prose, fetched
//    when this screen opened. So this shot is now also the evidence that
//    the split's fetch path renders - and the reason the drive below waits
//    on the publisher's half rather than on the phone's own, which is
//    printed before anything has been fetched and would photograph a
//    half-arrived screen.
//  - NO TIME. The fixture's climb is null, so the figures line reads
//    "no time - climb unmeasured" rather than pricing an unmeasured climb
//    as flat ground - which is what a time computed from zero would be.
//  - THE START, AND WHERE IT CAME FROM. The coordinates are read off the
//    centre of the map on the publisher's page rather than a placed pin,
//    and the card says exactly that before offering directions to them.
//  - THE LINE IS OURS. The footer says the route a map would draw is
//    OurHike's construction of their description, not a track anybody
//    walked with a GPS.
//  - THE FOOTER STILL LINKS TO THEIR PAGE. Since #1578 that link is drawn
//    only for a URL that is a web page (lib/safeLink.ts), and opens beside
//    the app rather than navigating it away. The fixture's URL is the
//    publisher's own https: one, so "Read it on their page ›" is the
//    evidence that the gate lets a real page through.
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
  // The PUBLISHER's half, not this phone's. "measured on the trail lines
  // this phone holds" is printed from the shelf record alone and is on
  // screen before the detail has been read, so waiting on it would let the
  // camera fire mid-fetch and photograph a screen with no prose on it.
  // "says 8.5 mi" cannot appear until suggested_hikes_detail_7909.json has
  // arrived and merged, which is the sequence this shot is evidence for.
  await page.getByText(/says 8\.5 mi/).waitFor()
  await page.getByText(/Park at the pull-off/).waitFor()
}
