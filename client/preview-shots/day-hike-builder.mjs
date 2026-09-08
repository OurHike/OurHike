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
// 2026-09-08: THE BUILDER WITH A WALK IN IT (#1212). Both builder recipes
// stopped at "Tap a trail to walk it", so the route order, the stop rows, the
// mile marks and the selection casing had all shipped on unit tests alone -
// and #1200 is the standing argument for why that is not enough: it shipped
// a first cut that made the map SMALLER with a fully green suite, and only
// the camera caught it.
//
// A drive cannot aim a canvas click at a trail from the opening view - the
// lon/lat under a pixel depends on where the camera is. What it CAN do is
// move the camera somewhere known: selecting a search result centres the map
// on that waypoint at SEARCH_RESULT_ZOOM (App.tsx), and while the builder is
// open the same selection files a shelter as a stop rather than opening its
// card (`handleSelectPoi` -> `toggleDayHikeStop`). So `walkInHarriman` below
// searches for a named shelter beside the A.T. in Harriman, which lands the
// stop AND puts the shelter under the canvas centre, zooms in two steps so
// MAX_OFF_NETWORK_FEET is tens of pixels rather than six, and taps a ring of
// sixteen points around the pin. The trail passes the pin, so the ring
// crosses it twice; a tap that misses every line is refused and costs
// nothing, and the accepted ones are a walk along that trail. The wait is
// on the panel's own summary and the stop row's own text, not on a clock.
//
// The geometry is what decides the tolerance. At the search zoom (14) one
// pixel is 7.2 m at Harriman's latitude and 150 ft is six pixels, which no
// blind tap lands; two zoom steps in, a pixel is 1.8 m and the tolerance is
// 25 px, against ring taps 23 px apart - so any crossing has a tap inside
// the tolerance. Derived, not measured; the first CI frame is the test.
//
// THREE HONEST FRAMES now, and the caption names all of them: the builder
// with a route and a stop row; the builder waiting for its first tap, where
// the search found no such shelter or every tap was refused; and the
// withheld door where this build has no graph.
//
// THE WALK IS UNVERIFIED, and this is the record of why. Measured
// 2026-09-08 on #1268's preview, the first run of this drive: both builder
// frames were the withheld door. The bucket's trail_graph.json is
// 78,595,556 bytes against the 32 MiB launch budget #1255 set after #1254's
// frozen first page, so the app declines it - the desktop frame says so in
// #1255's own words, and the phone's read "has not downloaded yet, and it
// needs a connection". Nothing about the camera changed that; the door is
// withheld for every hiker on that release too. `walkInHarriman` never ran,
// because the drive returns before it when the door is a div. What would
// settle it is a preview whose graph loads: #1257's stage 3 cuts the graph
// per cell, and #1231 is the decision that would shrink it. Until one of
// those lands, the ring's arithmetic below is derived and not measured.

export const caption =
  'The day-hike builder with a walk in it: the route order, a stop row, the mile marks (#1194, #1212)'
export const alt =
  'Either the redesigned day-hike builder holding a walk - a panel across the top of the screen headed "Your route" with Distance, Climb and Walking figures, an expanded body listing the route order with a stop row for Fingerboard Shelter, the map in the middle with the route cased dark and its mile marks, and the builder bar with Cancel, Undo and Draw instead along the bottom - or the same builder still waiting for its first tap, where the search found no such shelter or no tap landed on a trail; or, where this build has no junction graph, the "What are you planning?" sheet with the day-hike door withheld and a sentence naming what is missing'

// The routing artifact is 7.5 MB and is hashed before it is trusted, so the
// door can take a moment to appear on a cold preview. The drive waits on the
// door itself rather than on a clock; this is the settle after it.
export const wait = 6000

/**
 * A shelter beside the A.T. in Harriman-Bear Mountain, by name.
 *
 * Named rather than searched by category, unlike waypoint-quick-answers.mjs,
 * because this recipe needs the camera somewhere the network graph has trail
 * on both sides of the pin - and a first-result shelter could be anywhere
 * from Georgia to Maine, on a stretch where only the A.T. is published. If
 * ATC renames or retires this row the search finds nothing, and the frame
 * is the honest empty builder rather than a broken drive.
 */
const SHELTER = 'Fingerboard Shelter'

/** Zoom steps in from SEARCH_RESULT_ZOOM (14): two, for the arithmetic in
 *  the header - 1.8 m per pixel, a 25 px tolerance. */
const ZOOM_STEPS = 2

/** The ring of taps around the pin: its radius in pixels and how many taps.
 *  Sixteen at 64 px are 23 px apart, inside the tolerance either side. The
 *  radius clears the pin's own icon, so a tap is a map tap rather than a
 *  second toggle of the stop. */
const RING_RADIUS_PX = 64
const RING_TAPS = 16

/** MapLibre's keyboard handler zooms on `=` / `+` while the canvas has focus;
 *  the ease is about 300 ms a step, and nothing in the DOM says when it has
 *  settled, so this is the one clock in the drive. */
const ZOOM_SETTLE_MS = 1200

/**
 * Put a walk into an open builder: the stop, the camera, the taps.
 *
 * Resolves true when the panel reports legs. Every wait is guarded, and every
 * early return leaves a frame the caption names.
 */
export async function walkInHarriman(page) {
  await page.getByRole('button', { name: 'Search' }).click()
  await page.getByRole('searchbox', { name: 'Search the downloaded map' }).fill(SHELTER)

  const result = page.getByRole('button').filter({ hasText: SHELTER }).first()
  await result.waitFor({ timeout: 20000 }).catch(() => {})
  if ((await result.count()) === 0) return false

  // Selecting it files the stop and jumps the camera. The summary proves the
  // stop landed before anything trusts where the camera is.
  await result.click()
  const oneShelter = page.getByText(/1 shelter/)
  await oneShelter.waitFor({ timeout: 10000 }).catch(() => {})

  const canvas = page.locator('.maplibregl-canvas')
  await canvas.focus()
  for (let step = 0; step < ZOOM_STEPS; step += 1) {
    await page.keyboard.press('=')
  }
  await page.waitForTimeout(ZOOM_SETTLE_MS)

  const box = await canvas.boundingBox()
  if (box === null) return false
  const centre = { x: box.x + box.width / 2, y: box.y + box.height / 2 }

  const ring = async () => {
    for (let i = 0; i < RING_TAPS; i += 1) {
      const angle = (i / RING_TAPS) * 2 * Math.PI
      await page.mouse.click(
        centre.x + RING_RADIUS_PX * Math.cos(angle),
        centre.y + RING_RADIUS_PX * Math.sin(angle),
      )
      // Spaced so two neighbours never read as a double-click, which MapLibre
      // would answer with a zoom rather than a tap.
      await page.waitForTimeout(200)
    }
  }

  // The panel's summary reads "N legs" the moment two taps have routed. A
  // second ring only where the first produced nothing: the 17 MB geometry
  // may still have been landing, and App.tsx refuses every tap until it has
  // (day-hike-builder's header, "What it cannot show").
  const legs = page.getByText(/\d+ legs?/)
  await ring()
  await legs.waitFor({ timeout: 8000 }).catch(() => {})
  if ((await legs.count()) === 0) {
    await ring()
    await legs.waitFor({ timeout: 8000 }).catch(() => {})
  }

  // A ring tap that landed on the pin's LABEL toggled the stop back off -
  // poiIdAt asks the symbol layer, and a label is part of the symbol. Filing
  // it again is the same search, which also re-centres on a camera that has
  // not moved.
  if ((await legs.count()) > 0 && (await oneShelter.count()) === 0) {
    await page.getByRole('button', { name: 'Search' }).click()
    await page.getByRole('searchbox', { name: 'Search the downloaded map' }).fill(SHELTER)
    await result.waitFor({ timeout: 10000 }).catch(() => {})
    if ((await result.count()) > 0) await result.click()
    await oneShelter.waitFor({ timeout: 5000 }).catch(() => {})
  }

  return (await legs.count()) > 0
}

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

  await page.getByRole('region', { name: 'Your route' }).waitFor()

  // The walk goes in BEFORE the panel opens: collapsed is the state where
  // the map is biggest, which is the state the ring of taps wants.
  const walked = await walkInHarriman(page)

  // #1194's panel, opened. It renders collapsed by default - which IS the
  // redesign, the state where the map is biggest - but a collapsed panel and
  // the old bar-only screen look alike in a still, and the point of the shot
  // is what the panel now holds. So the camera opens it.
  //
  // Waited on by the thing being photographed rather than by the button that
  // was clicked: the stop row's own text where the walk landed, the empty
  // prompt where it did not.
  await page.getByRole('button', { name: 'Details' }).click()
  if (walked) {
    await page
      .getByText(/Shelter · mile/)
      .waitFor({ timeout: 10000 })
      .catch(() => {})
  } else {
    await page.getByText('Route order · tap the map to add').waitFor()
  }
}
