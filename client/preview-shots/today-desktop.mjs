// Today on a laptop (#1054, and #1373's frame 16a): the journal beside the
// map, and a row of it tapped.
//
// WHAT THIS SHOT IS EVIDENCE FOR. Two things the phone's Today cannot show
// because they need the width. First, that the Today tab above desktop.css's
// 900px breakpoint is not its own screen: the map branch renders, with the
// journal docked as a column between the sidebar and the canvas - the
// planning station #1054 built. Second, and the reason this recipe exists
// now, that a tap on a journal row MOVES THE MAP INSTEAD OF REPLACING THE
// LIST. Until #1373 the row's handler switched to the Map tab on every
// width, which on a desktop unmounted the journal the row was tapped in (the
// inventory's C5): the card opened and the column that opened it was gone.
// Now the desktop's Today keeps its tab, the waypoint's card opens over the
// map beside the journal, and the row that opened it is still there to tap
// the next one.
//
// WHAT TO LOOK FOR: the sidebar, then the journal column headed by the
// pine chrome with the mode readout, then the map with a waypoint card open
// on it - all three at once. The Today tab is the selected one in the
// sidebar. That is the whole change.
//
// THE FIX IS A FIXTURE. The journal has rows only where the phone is - it
// lists what a hiker will meet from where they stand - so the browser
// answers with a made-up point on public trail geometry (Bear Mountain's
// summit, which the A.T. crosses) for a fictional hiker, the arrangement
// following-a-day-hike.mjs already uses. Nobody's location is in the frame.
// Where the release's waypoints put no journal row within reach of that
// point, the frame is honest about it: the journal's own empty column beside
// the map, and no card. The caption names both.
//
// Nobody's data otherwise: no account, no saved hikes, no reports or photos.

/** A made-up point on the fixture's own grid: Bear Mountain's summit. */
const FIX = { longitude: -73.9888, latitude: 41.3125 }

export const caption =
  'Today on a laptop — the journal beside the map, and a row of it tapped: the card opens over the map and the column stays (#1054, #1373 frame 16a)'
export const alt =
  'Either a wide browser window with the OurHike sidebar down the left, Today selected, a journal column beside it headed by a pine chrome band reading Today with the mode readout and a list of waypoint rows, and the map filling the right with a waypoint card open over it - or the same journal column with no rows within reach of the fixture point, and the map beside it with nothing over it'

// The wide layout, which is the entire subject.
export const desktop = true

export default async function drive(page) {
  await page.context().grantPermissions(['geolocation'])
  await page.context().setGeolocation(FIX)

  // Location through the SWITCH rather than through the store, for the
  // reason following-a-day-hike.mjs gives: the runner's skip-first-run init
  // script rewrites the preferences record on every navigation, so a seeded
  // `location_permission_requested` is gone by the time the app reads it.
  // The switch is also the door a hiker uses. On a desktop More is a screen
  // over the map like the phone's, so the drive is the phone's.
  await page.getByRole('tab', { name: 'More' }).click()
  await page.getByRole('button', { name: /safety & privacy/i }).click()
  const useMyLocation = page.getByRole('checkbox', { name: 'Use my location' })
  if (!(await useMyLocation.isChecked())) await useMyLocation.check()

  // Back to Today, which above the breakpoint is the map screen with the
  // journal docked beside it. The region is the wait, for the reason
  // long-hike-window-desktop.mjs gives: a click cannot spend a CI runner's
  // software-rendered map build usefully, a waitFor can.
  await page.getByRole('tab', { name: 'Today' }).click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()
  await page.locator('.map-screen__journal .today').waitFor()

  // A row, where the release puts one within reach of the fixture point.
  // Its absence is the honest second frame the caption names.
  const row = page.locator('.map-screen__journal .poi-row--opens').first()
  await row.waitFor({ timeout: 20000 }).catch(() => {})
  if ((await row.count()) === 0) return

  await row.click()
  // The card, over the map beside the journal - and the journal still there
  // is what the frame is evidence for.
  await page.getByRole('dialog', { name: 'Waypoint' }).waitFor()
  await page.locator('.map-screen__journal .today').waitFor()
}
