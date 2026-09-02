// The day-hike builder on a laptop - the layout that did not exist until
// #1194.
//
// WHY THIS IS A SECOND RECIPE AND NOT A SECOND WAIT IN THE FIRST ONE. The
// runner captures a recipe at one viewport, and `desktop` is the flag that
// picks which (see first-run-desktop.mjs, which added it). The phone and the
// wide layout are genuinely different screens here rather than one screen
// reflowing: on a phone the panel is a band across the top with the map
// below; above desktop.css's 900px breakpoint it is a 348px rail down the
// left with the map filling everything right of it, and its details body has
// no collapsed state at all.
//
// WHAT THIS SHOT IS EVIDENCE FOR, which is the first of #1194's three
// complaints. Before it, `desktop.css` had no rule for the builder of any
// kind: above 900px the wide layout still wore the phone's bottom sheet, so
// a 27" display showed a letterboxed map with a sheet across the foot of it
// that could take 60% of the canvas. Every other wide surface in this app had
// already been given its room - the tab bar became a sidebar, the legend
// became a persistent panel, the elevation chart became interactive - and
// this one had been missed. The picture to compare against is the phone
// recipe beside it: same panel, same controls, a map with the whole right of
// the window.
//
// WHAT TO LOOK FOR: the rail is on the LEFT and holds everything at once (no
// "Details" button - there is nothing to collapse), the label toggles are a
// two-column grid rather than the phone's scrolling row, and the builder's
// buttons are still along the bottom of the map rather than in the rail. That
// last one is the instruction this change was built to, and it is the easiest
// to lose in a redesign: the bar is where a thumb reaches.
//
// Nobody's data is in the frame by construction: no account, no saved hikes
// seeded, no location fix, and the map is wherever the app opens itself.

export const caption =
  'The day-hike builder on a laptop - a left rail, and the map gets the rest (#1194)'
export const alt =
  'Either the day-hike builder in a wide browser window - a narrow panel down the left headed "Your route" with Distance, Climb and Walking figures, the route order beneath them and a two-column grid of map-label toggles at its foot, the map filling the whole right of the window, and the builder bar with Cancel and its actions along the bottom of the map - or, where this build has no junction graph, the "What are you planning?" sheet with the day-hike door withheld and a sentence naming what is missing'

// The wide layout, which is the entire subject.
export const desktop = true

// The routing artifact is 7.5 MB and is hashed before it is trusted - the
// same settle the phone recipe beside this one explains.
export const wait = 6000

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Plan' }).click()
  await page.getByRole('button', { name: 'Start on the map' }).click()
  await page.getByRole('dialog', { name: 'What are you planning?' }).waitFor()

  // A BUTTON only while the network is ready; withheld, it is a div with the
  // same name. Which frame this build can reach is what this locator tests -
  // see the phone recipe for the two-honest-frames argument.
  const door = page.getByRole('button', { name: /A day hike/ })
  await door.waitFor({ timeout: 20000 }).catch(() => {})
  if ((await door.count()) === 0) return

  await door.click()
  await page.getByRole('region', { name: 'Build a day hike' }).waitFor()

  // No Details click here, unlike the phone: desktop.css keeps the rail's
  // body open and hides the toggle, so the label row is already in frame.
  // Waiting on the route order proves that rather than assuming it.
  await page.getByRole('region', { name: 'Your route' }).waitFor()
  await page.getByText('Route order · tap the map to add').waitFor()
}
