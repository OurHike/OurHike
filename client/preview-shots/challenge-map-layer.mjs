// The Legend's "Challenge places" switch, turned on (#1780, frame #1).
//
// WHAT THIS SHOT IS EVIDENCE FOR. The row the legend lists only while a
// joined challenge is on the chosen trail - here the A.T., taken from the map
// - with its detail line and its switch on, and (with real data under it)
// the blaze-yellow diamonds at the list's places around McAfee Knob, hollow
// until tagged. The plate is unchanged: no count, no banner. The trail line
// keeps its own colour.
//
// WHEN IT SHOWS LESS. The canvas is paper in a sandbox with no downloaded
// map, so the frame is the legend alone there.
//
// SEEDED, AND SAID SO: fixtures/challenges.mjs. The camera is a window on
// McAfee Knob at a zoom above the pin seam - a public summit, nobody's fix.
import { seedChallenges } from './fixtures/challenges.mjs'

export const caption =
  'The map layer: Challenge places switched on in the Legend (#1780, seeded hiker)'
export const alt =
  'The map with the Legend sheet open, showing a Challenge places row with its switch on; with map data, yellow diamond pins near McAfee Knob'

export const wait = 6000

export async function before(page) {
  await page.addInitScript(() => {
    sessionStorage.setItem(
      'ourhike:camera',
      JSON.stringify({ center: [-80.03712, 37.39297], zoom: 11.5 }),
    )
  })
}

export default async function drive(page) {
  await seedChallenges(page, { takenTrail: 'AT' })
  await page.getByRole('tab', { name: 'Map' }).click()
  await page.getByRole('button', { name: 'Legend' }).click()
  const toggle = page.getByRole('switch', { name: /Challenge places/ })
  await toggle.waitFor()
  await toggle.click()
}
