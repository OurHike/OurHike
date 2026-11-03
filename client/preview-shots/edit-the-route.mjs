// Editing a saved walk: the camera on the route rather than on the corridor
// (#1404).
//
// WHAT THIS IS EVIDENCE FOR. "Edit the route" on a saved card loaded the
// walk's legs into step 2 and drew the line, and left the camera wherever the
// map already was - which, for a hiker arriving from the Plan tab, is the
// whole corridor. The walk they came to edit was then a mark a few tens of
// pixels long somewhere in the frame, and on a laptop often not in the frame
// at all.
//
// It was not found by looking at it, which is why a shot is worth adding
// rather than assumed. `e2e/data/desktopMap.spec.ts` sweeps the pointer over
// the map hunting for the drawn route, because chrome/RouteHover.tsx only
// prints its plate when the pointer is over the line. Measured 2026-09-11
// against release 2026-09-10 on the fixture walk Ramapo-Dunderberg to
// Timp-Torne (2.85 mi), 1280x800: a 17-by-17 sweep of the map's box on the
// camera the builder opened on raised the plate 0, 0, 0 and once 1 times, and
// a denser 16 px grid of 1,974 points raised it zero. There was nothing under
// the frame to find. Seeded onto the walk at z14, the same sweep raised it 20
// times.
//
// So the frame this photographs is the one that could not be photographed
// before: step 2 with the route it is editing actually in it.
//
// TWO HONEST FRAMES, ONE RECIPE - the shape day-hike-card.mjs and
// day-hike-builder.mjs already ship, and the reason is the same. "Edit the
// route" is offered only while the card's own resolution is live, which needs
// this build's bucket to carry the junction graph's cell index. Where it
// does, the picture is the builder over the route. Where it does not, the
// card has no such door and the picture is the saved card itself with its
// cached figures - a true screen for that bucket, and the state day-hike-card
// .mjs already documents. The caption names both, because
// photograph-preview.mjs reads `caption` before the drive runs.
//
// NOBODY'S DATA, by construction: the same invented fixture day-hike-card.mjs
// seeds - an invented name, a grid coordinate pair, no account, no location
// fix, no reports and no photos.
//
// WHAT IT CANNOT SHOW, said here rather than discovered in review: the PHONE.
// #1404's sweep is the laptop project's, and the phone's builder covers the
// map at step 2 anyway (measured 8% of it reachable), so the same fix may be
// invisible at this width rather than absent. This recipe photographs the
// phone because that is the camera's default and the frame is still the
// right one - the route is in it either way - but the laptop is where the
// defect was measured and is not what this proves.

import { seedDayHikes } from './fixtures/dayHike.mjs'

export const caption =
  'Editing a saved walk — step 2 opens framed on the route, not on the corridor (#1404)'
export const alt =
  'Either the day-hike builder at step 2 with the saved walk’s route drawn and the camera fitted to it — the rail reading Day hike ✓, Route, Details with Route lit, the route order under it and the builder bar at the foot — or, where this build’s bucket carries no junction graph, the saved card itself with its cached figures and no Edit the route door'

// The cell index is fetched and hashed before the card can resolve, and the
// fit runs on the cell the walk sits in. The drive waits on the builder's own
// region rather than on a clock; this is the settle after it, so the camera
// move has finished easing.
export const wait = 6000

export default async function drive(page) {
  await seedDayHikes(page)

  await page.getByRole('tab', { name: 'Plan' }).click()
  await page.getByRole('button', { name: /Pine Meadow loop/ }).click()
  await page.getByRole('heading', { name: 'Legs' }).waitFor()

  // The door exists only where the card resolved against a live graph. Waited
  // on rather than counted immediately - the cell index is still landing when
  // the card opens - and its absence is the second honest frame rather than a
  // broken drive.
  const edit = page.getByRole('button', { name: 'Edit the route' })
  await edit.waitFor({ timeout: 20000 }).catch(() => {})
  if ((await edit.count()) === 0) return

  await edit.click()
  await page.getByRole('region', { name: 'Build a day hike' }).waitFor()
}
