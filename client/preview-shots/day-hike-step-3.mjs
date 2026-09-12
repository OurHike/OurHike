// Step 3 of the planning spine for a day hike (#1373, frame 5a): the route
// you chose, read before it is saved, under the rail - "Day hike ✓ ·
// Route ✓ · Details" - with the name as a field, the date, the figures at
// the hiker's pace, and, where the published waypoints have any near the
// walk, "Water on route" and "Shelters & campsites" as waypoint rows; the
// foot is "‹ Route" and "Save this day hike" - Save the last button, never
// a step (D7).
//
// Driven through the builder exactly as day-hike-builder.mjs is - the same
// `walkInHarriman`, reused rather than copied - and then one tap further:
// "Use this route". So it has the same two honest frames that recipe has
// where the graph does not arrive (step 1's refusal sentence, or the empty
// builder), and a third where it does: step 3 itself. The caption names
// all three; photograph-preview.mjs reads it before the drive runs.
//
// Nobody's data is in the frame by construction: no account, no saved
// hikes seeded, no location fix, and the walk is a ring of taps around a
// shelter chosen by name.
//
// RE-PHOTOGRAPHED FOR THE MAP'S FLOOR (2026-09-12). The maintainer could not
// tap the map while planning on a phone: measured at 390x844 with a route in
// the builder, the panel took 292 px off the top and the bar sat over the
// map's bottom 321 px, leaving 159 px - 19% of the screen - that a finger
// could land on. screens/plan.css now spends a budget against a 75svh floor,
// so what this frame is evidence for is the map having three quarters of the
// screen with the panel and the bar both still legible and the way on still
// pinned where a thumb reaches it.
// Step 3 was the worse half: the review covered all but 83 px, 9.8%.
import { walkInHarriman } from './day-hike-builder.mjs'

export const caption =
  'Step 3 — the route you chose, read before it is saved: the rail, the name field, the figures, water and stops as rows, and Save as the last button (#1373, frame 5a)'
export const alt =
  'Either step 3 of the planning spine over the map: a sheet opening with a three-stop rail reading Day hike ✓, Route ✓ and Details with Details lit, a Name field, the date, a figures line with miles and legs, then Water on route and Shelters & campsites rows where this build holds waypoints near the walk, the legs with their blazes, the ways off, and a foot with "‹ Route" and "Save this day hike" - or, where no walk could be built, the empty builder or step 1 with its refusal sentence'

export const wait = 6000

/**
 * Through the spine to step 3: Plan, "Start on the map", step 1's map door,
 * the ring of taps in Harriman, and "Use this route". Exported so the
 * desktop recipe drives the same way rather than copying this - the two
 * shots differ only in viewport, and a drive copied twice drifts twice
 * (both had to be rewritten when step 1 gained its heading).
 *
 * Every wait that can fail returns rather than throwing: the frame at that
 * point - the empty builder, step 1's refusal - is the honest one.
 */
export async function reviewInHarriman(page) {
  await page.getByRole('tab', { name: 'Plan' }).click()
  await page.getByRole('button', { name: 'Start on the map' }).click()
  await page.getByRole('heading', { name: 'Where do you want to go?' }).waitFor()

  const door = page.getByRole('button', { name: 'Pick on the map' })
  await door.waitFor({ timeout: 20000 }).catch(() => {})
  if ((await door.count()) === 0) return

  await door.click()
  await page.getByRole('region', { name: 'Build a day hike' }).waitFor()
  if (!(await walkInHarriman(page))) return

  // The way on. Its absence means no route was made, and the builder is
  // the honest frame.
  const on = page.getByRole('button', { name: 'Use this route' })
  await on.waitFor({ timeout: 5000 }).catch(() => {})
  if ((await on.count()) === 0) return
  await on.click()
  await page.getByRole('button', { name: 'Save this day hike' }).waitFor()
}

export default async function drive(page) {
  await reviewInHarriman(page)
}
