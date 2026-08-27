// Frame `1j`'s bar - the day-hike builder, waiting for its first tap (#1093,
// #978, features/HIKE_PLANNING.md "The day hike on a network").
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

export const caption = 'The day-hike builder in draw mode, or the door it opens from'
export const alt =
  'Either the day-hike builder bar over the map in draw mode - "Drag to draw. We\'ll put it on the trails and tell you what moved." with Cancel, a "Tap instead" way back, and the row saying roads are drawn and never routed on - or, where this build has no junction graph, the "What are you planning?" sheet with the day-hike door withheld and a sentence naming what is missing'

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

  // ON INTO DRAW MODE, because that is what changed. Three of this branch's
  // decisions land on this bar and only one of them survives a canvas the
  // drive cannot aim at: frame `1k`'s freehand door (#983), the way back from
  // it, and the row that used to promise roads as a LATER feature and now
  // says what is true about them (#931). The resting "Tap a trail to walk it"
  // frame is the one this recipe already published; this is the frame with
  // the change in it.
  //
  // The prompt line is what proves the mode flipped - the button's own label
  // changes too, but waiting on the sentence waits on the thing being
  // photographed rather than on the thing that was clicked.
  await page.getByRole('button', { name: 'Draw instead' }).click()
  await page.getByText(/Drag to draw/).waitFor()
}
