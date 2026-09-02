// The day-hike builder on a phone (#1093, #978, #1194,
// features/HIKE_PLANNING.md "The day hike on a network").
//
// This is the screen #1093 changes, and until now nothing pointed a camera at
// it. The other four day-hike recipes photograph the Plan home, the finished
// card, the saved list and a walk under way; the builder itself - the surface
// a tap is answered on - had no shot.
//
// THE CAMERA CAN REACH IT NOW, AND FINDING OUT WHY IT COULD NOT TOOK TWO
// TRIES. `day-hike-card.mjs` and `following-a-day-hike.mjs` both say the
// builder is unreachable because "no preview holds `trail_graph.json`" and
// "the preview build carries an empty VITE_DATA_BASE_URL (#1024, measured
// 2026-08-25)". Measured again 2026-08-27 and neither half survives: this
// pull request's own deployed preview preloads
// `https://data.ourhike.org/trails_overview.geojson`, so the build DOES carry
// a data source, and that bucket answers 200 for `trail_graph.json`
// (7,475,349 bytes), `trail_graph_geometry.json` (17,285,133) and
// `trail_graph_elevation.json` (277,331), with `latest.json` naming a sha256
// for each.
//
// This recipe's own CI runs are what found the rest, over two rounds. Both
// photographed the withheld door under "the trail network has not downloaded
// yet, and it needs a connection" - a FETCH FAILURE, not a slow one - against
// a build that plainly had the bucket. The cause was the camera's own origin,
// and it had two halves: screenshot.mjs served from `127.0.0.1` rather than
// `localhost`, AND on a port the OS picked, where the bucket's CORS allowlist
// holds exact origins and only vite's own 4173 and 5173. Its `SHOT_HOST` note
// carries the measurement. So #1024's stated cause - an unset
// VITE_DATA_BASE_URL - was never the real one.
//
// TWO HONEST FRAMES, ONE RECIPE - the shape day-hike-card.mjs already ships.
// Where the graph arrives, the picture is the builder bar over the map. Where
// it does not (a fork's pull request gets no secrets, and a bucket can stop
// answering), PlanKindSheet withholds the door and names what is missing, and
// the picture is that refusal. Both are true screens; the caption names both,
// because photograph-preview.mjs reads `caption` off the module before the
// drive runs and a static string cannot know which one landed (#1058).
//
// WHAT IT CANNOT SHOW, said here so the pull request body does not have to
// pretend otherwise: #1093's new sentence - "OurHike hasn't got this area's
// trail lines yet" - appears only in ANSWER to a tap, during the window
// between the routing artifact landing and the 17 MB geometry one. A drive
// cannot aim a canvas click at a trail (the lon/lat under a fixed pixel
// depends on where the camera happens to be) and cannot hold a download open,
// so that frame is pinned in App.dayHike.test.tsx and not here. What this
// photographs is the surface it appears on.
//
// Nobody's data is in the frame by construction: no account, no saved hikes
// seeded, no location fix, and the map is wherever the app opens itself.

// #1194 REPOINTED THIS RECIPE at the panel rather than at draw mode.
//
// The three complaints that change answered are all about the surface this
// photographs: the map was too small, nothing was labelled, and the route was
// hard to pick out. The first is the one a still frame proves - the panel is
// a band at the TOP with the map below it and the buttons still at the foot,
// where before the bar alone could cover 60% of the canvas.
//
// Draw mode is no longer what this drives into. It was #983's frame and it is
// still pinned by chrome/DayHikePickBar.test.tsx; what it cannot show is the
// layout, because entering it replaces the bar's prompt and leaves the panel
// exactly as it was. The details toggle does the opposite - it is the control
// the redesign added, and opening it puts the route order, the climb figures
// and the label toggles in frame at once.
export const caption =
  'The day-hike builder: panel at the top, map in the middle, buttons at the bottom (#1194)'
export const alt =
  'Either the redesigned day-hike builder - a panel across the top of the screen headed "Your route" with Distance, Climb and Walking figures, an expanded body listing the route order and a scrolling row of map-label toggles, the map filling the middle, and the builder bar with Cancel, Undo and Draw instead along the bottom - or, where this build has no junction graph, the "What are you planning?" sheet with the day-hike door withheld and a sentence naming what is missing'

// The routing artifact is 7.5 MB and is hashed before it is trusted, so the
// door can take a moment to appear on a cold preview. The drive waits on the
// door itself rather than on a clock; this is the settle after it.
export const wait = 6000

export default async function drive(page) {
  await page.getByRole('tab', { name: 'Plan' }).click()
  // The empty state's primary, which is what a preview holding no saved plans
  // shows. It opens the fork rather than either builder.
  await page.getByRole('button', { name: 'Start on the map' }).click()
  await page.getByRole('dialog', { name: 'What are you planning?' }).waitFor()

  // The door is a BUTTON only while the network is ready; the withheld form
  // is a div with the same name, so this locator is the test for which frame
  // this build can reach. Waited on rather than counted immediately - the
  // graph is still being fetched and hashed when the sheet opens.
  const door = page.getByRole('button', { name: /A day hike/ })
  await door.waitFor({ timeout: 20000 }).catch(() => {})
  if ((await door.count()) === 0) return

  await door.click()
  await page.getByRole('region', { name: 'Build a day hike' }).waitFor()

  // #1194's panel, opened. It renders collapsed by default - which IS the
  // redesign, the state where the map is biggest - but a collapsed panel and
  // the old bar-only screen look alike in a still, and the point of the shot
  // is what the panel now holds. So the camera opens it.
  //
  // Waited on by its own heading rather than by the button that was clicked:
  // that waits on the thing being photographed instead of on the click.
  await page.getByRole('region', { name: 'Your route' }).waitFor()
  await page.getByRole('button', { name: 'Details' }).click()
  await page.getByText('Route order · tap the map to add').waitFor()
}
