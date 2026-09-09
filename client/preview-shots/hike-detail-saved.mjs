// The same route after the hiker has saved it and logged a walk (#1290).
//
// WHAT THIS SHOT IS EVIDENCE FOR. ONE RECORD, MANY DATES - the maintainer's
// own framing, and the reason this recipe exists beside hike-detail.mjs. The
// drive presses the button twice: the first press saves the publisher's
// route into the hiker's own day hikes, the second logs today as a walk of
// THAT record rather than minting a second copy of it. What the shot shows
// afterwards is the state that proves it:
//
//  - "You walked this on <today>." - the walked line, which appears only
//    once a date is on the record. Saving a plan is not walking it, so the
//    save alone leaves this line off and the button reading "Log a walk".
//  - "Log another walk" - the button's third state, offered only once there
//    is a walk for a second one to be another of.
//  - "Open on map" - which appears only now, because what the map draws is
//    a record in the hiker's own hikes. Before the save there is nothing to
//    draw, and a control that cannot do its job is not offered.
//
// And what is deliberately absent, which is the other half of the evidence:
// no streak, no total, no comparison with the last time, no congratulation.
// A screen about walking is exactly where gamification creeps in (#982,
// value #1), and the count is here only so the sentence can be short.
//
// WHAT IT IS NOT EVIDENCE FOR. The map itself: "Open on map" is
// photographed as an offer, not followed - the preview has no fix and no
// downloaded trail data, so the route would resolve against nothing.

import { seedSuggestedHikes } from './fixtures/suggestedHikes.mjs'

export const caption = 'A route saved once, walked twice — one record, many dates (#1290)'
export const alt =
  'The Wapiti to Docs Knob detail screen after saving and logging a walk: a line reading You walked this on today’s date, a Log another walk button beside an Open on map button, and no streak, total or comparison anywhere on the screen'

export default async function drive(page) {
  await seedSuggestedHikes(page)
  await page.getByRole('button', { name: /Find a hike/ }).click()
  await page.getByRole('heading', { name: 'Find a hike' }).waitFor()

  await page.getByRole('button', { name: /Wapiti to Docs Knob/ }).click()
  await page.getByRole('heading', { name: 'Wapiti to Docs Knob' }).waitFor()

  // Save, then log. Each press is awaited on the label the NEXT state
  // shows, so the second click cannot land on the first render - the
  // store is written and read back between them.
  await page.getByRole('button', { name: 'Save to my hikes' }).click()
  await page.getByRole('button', { name: 'Log a walk' }).click()
  await page.getByText(/^You walked this on /).waitFor()
  await page.getByRole('button', { name: 'Open on map' }).waitFor()
}
