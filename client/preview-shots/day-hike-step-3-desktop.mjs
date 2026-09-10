// Step 3 of the planning spine on a laptop (#1373, frame 16b): the review
// of the route you chose, read in the rail beside the route it describes.
//
// WHY THIS IS A SECOND RECIPE AND NOT A SECOND WAIT IN THE FIRST ONE - the
// argument day-hike-builder-desktop.mjs makes for step 2, one step further
// along. The runner captures a recipe at one viewport, and above desktop.css's
// 900px breakpoint step 3 is a different screen rather than the same one
// reflowed: on a phone the review is a sheet over the canvas
// (MapScreen's `routeSheet` slot, `.day-hike-card` at `bottom: 0`), and on
// a desktop the shell hands the same card to the builder-panel slot, so it
// is a 348px column down the left with the map filling everything right of
// it - the rail step 2 just wore, continuing.
//
// WHAT THIS SHOT IS EVIDENCE FOR. That step 3 can be read against the route
// it describes without either giving up room, which is what the handoff's
// desktop frame asks for and what the phone's sheet cannot do: at 85% of the
// canvas the sheet covers most of the route it is summarising. And that the
// map is never covered on a desktop - WEBSITE.md §6's rule, which the review
// card was the last of the builder's surfaces to break.
//
// WHAT TO LOOK FOR: the rail on the LEFT holding the three-stop rail with
// Details lit, the name field, the figures, the water and stop rows, and
// "‹ Route" / "Save this day hike" at its foot; the map to the right with
// the route cased dark and nothing over it; no rounded top edge or shadow
// on the card, because nothing is under it to be over. The close button is
// still in the card's own top-right corner - desktop.css keeps the card
// positioned for exactly that, and test/desktopLayout.test.ts pins it.
//
// Driven through the builder exactly as day-hike-step-3.mjs is - the same
// `walkInHarriman`, reused rather than copied - so it has that recipe's two
// honest frames where the graph does not arrive, and a third where it does.
//
// Nobody's data is in the frame by construction: no account, no saved
// hikes seeded, no location fix, and the walk is a ring of taps around a
// shelter chosen by name.
import { walkInHarriman } from './day-hike-builder.mjs'

export const caption =
  'Step 3 on a laptop — the review in the rail, read against the route it describes, with the map uncovered (#1373, frame 16b)'
export const alt =
  'Either step 3 of the planning spine in a wide browser window: a narrow column down the left opening with a three-stop rail reading Day hike ✓, Route ✓ and Details with Details lit, a Name field, the date, a figures line with miles and legs, then Water on route and Shelters & campsites rows where this build holds waypoints near the walk, the legs with their blazes, the ways off, and a foot with "‹ Route" and "Save this day hike"; the map filling the whole right of the window with the route cased dark and nothing drawn over it - or, where no walk could be built, the empty builder or step 1 with its refusal sentence'

// The wide layout, which is the entire subject.
export const desktop = true

// The routing artifact is 7.5 MB and is hashed before it is trusted - the
// same settle the phone recipe explains.
export const wait = 6000

export default async function drive(page) {
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

  // The card in the rail: Save is its last button, and the rail is what
  // this recipe photographs. Waiting on the button proves the review is
  // up; the layout is desktop.css's, under its own test.
  await page.getByRole('button', { name: 'Save this day hike' }).waitFor()
}
