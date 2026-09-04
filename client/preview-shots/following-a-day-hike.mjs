// Following a saved day hike (#1041, storyboard frames D9-D11) - the map
// while a walk is being followed: the header reading the walk's own distances
// instead of a Springer mile, and the next turn in the lower third.
//
// THE SEED, AND WHY A DRIVE OF PURE TAPS CANNOT REACH THIS. Getting here means
// owning a saved day hike the graph can still place, and building one by
// tapping needs the junction graph plus canvas clicks aimed at particular
// trails, which a drive cannot do - the lon/lat under a fixed pixel depends on
// where the camera happens to be. So this plants a fixture hike in the store
// and reloads, the runner's own first-run trick applied one store over.
//
// #1150 REPLACED THAT FIXTURE, AND THE OLD ONE IS WHY THIS RECIPE HAD NEVER
// ONCE PHOTOGRAPHED THE SCREEN IT IS NAMED FOR. Every run published the saved
// hike card instead, under the card's own sentence: "This phone's current
// trail map can't place this walk, so these are the figures from the day it
// was saved."
//
// Two wrong explanations were recorded for that before the real one, and both
// are named here so nobody re-derives them. The first was "the preview build
// has no data source" (#1024); day-hike-builder.mjs re-measured that on
// 2026-08-27 and the bucket answers 200 for every graph artifact - what was
// actually stopping the camera was its own origin, screenshot.mjs served from
// 127.0.0.1 on an OS-picked port against a CORS allowlist holding exact
// origins, and that is fixed. The second was "so the Follow door should be
// there now"; pr-preview run 1201 disproved it in the same run that
// photographed the builder bar over a live map.
//
// THE REAL REASON WAS THE SEED, AND IT IS MEASURED BOTH WAYS. `resolveDayHike`
// needs each end within `MAX_OFF_NETWORK_FEET` = 150 ft of a published line.
// Measured against `trail_graph.json` + `trail_graph_geometry.json` as
// published on 2026-09-04, by point-to-segment distance over every edge whose
// bounding box is within 0.02 deg:
//
//   | point                            | nearest published tread            |
//   |----------------------------------|------------------------------------|
//   | OLD end A  [-74.095,   41.25   ] | 449.2 ft - Red Cross (Red)         |
//   | OLD end B  [-74.085,   41.25   ] |  38.3 ft - Red Cross (Red)         |
//   | OLD fix    [-74.09,    41.25   ] | 171.2 ft - Red Cross (Red)         |
//   | NEW end A  [-73.96567, 41.28166] |   1.6 ft - Ramapo-Dunderberg (Blue)|
//   | NEW end B  [-74.0002,  41.27722] |   0.5 ft - Ramapo-Dunderberg (Blue)|
//   | NEW fix    [-73.9888,  41.27444] |   0.8 ft - 1777 (Red)              |
//
// One end failing is enough - `resolveDayHike` refuses the hike whole - so the
// old first end at three times the tolerance could never resolve, however
// close its sibling happened to land. #1150 measured 446.8 ft for it against
// the 2026-08-27 artifacts; 449.2 ft here is the same finding re-taken against
// a later release, not a different one.
//
// The old fixture's NAME was invented too. There is no "Pine Meadow Trail"
// anywhere in the published Harriman data - the nearest real trail to all
// three old points is the Red Cross.
//
// WHY A REAL TRAIL COSTS THE NEVER-PHOTOGRAPH LIST NOTHING, because this is
// the tension that produced the old fixture and it is a false one. The seed
// was invented to be nobody's data, and being nobody's data is exactly what
// stopped the live network claiming it. But a trail's published centerline is
// PUBLIC GEOMETRY - the app draws it for every hiker - and the list forbids a
// real location fix (somebody's position), a signed-in account, anybody's
// reports or photos, and a dispersed campsite at readable zoom. A tap on a
// published trail line is none of those, and the fix below is a fictional
// hiker at a real, public place, which is what every other recipe's fix
// already is.
//
// WHAT THE WALK ACTUALLY IS, re-derived against the same two artifacts on
// 2026-09-04, by running the client's OWN `resolveDayHike` over
// `trail_graph.json` + `trail_graph_geometry.json` as published: 2.85 mi of
// tread over seven legs, against 1.82 mi straight-line. Both ends sit on the
// Ramapo-Dunderberg and the middle crosses Timp-Torne, an unnamed OPRHP
// segment and 1777, so the route has real turns in it - which is the point,
// since the frame this recipe exists for is the next-turn card in the lower
// third.
//
// The same run refuses the OLD fixture outright (`resolveDayHike` returns
// null), which is this recipe's whole history in one line.
//
// The fix is a vertex of the 1777 edge, so it lands ON the routed walk rather
// than near it and the follow state should be `on-route`.
//
// NO `climb` IN THE CACHED FIGURES, and that is the honest answer rather than
// a gap. `DayHikeFigures.climb` distinguishes absent ("the app never knew")
// from null ("the app asked and the graph had no answer"), and nothing here
// measured this walk's ascent - so it is absent. Inventing one to fill the
// field would be a flat-ground claim about real ground.
//
// THE ELEVATION RIBBON #1045 ADDED SHOULD NOW DRAW. This header used to say
// the frame had no ribbon because `trail_graph_profile.json` was in no
// release; it is published as of 2026-09-04 (3,317,565 bytes decoded), so the
// artifact that was missing is there. Stated as an expectation rather than a
// fact: a preview run is the only place this can be confirmed, and this pull
// request's own is the first that could.

// THE CAPTION STILL NAMES BOTH FRAMES, because a static string cannot know
// which one landed (#1058). photograph-preview.mjs reads `caption` and `alt`
// off the module (scripts/photograph-preview.mjs:188-190) before the drive
// runs, so they cannot be decided by what the drive reached.
//
// Kept at two even though the fixture now resolves, because the second frame
// is still reachable for a reason that has nothing to do with the seed: a
// fork's pull request gets no secrets and a bucket can stop answering. What
// changed is which frame is expected, not which are possible - and a caption
// that promised the followed map over a picture of the card would be the
// failure #1058 rewrote it to stop, whichever reason produced the card.
export const caption = 'Following a day hike, or the card it starts from'
export const alt =
  'Either the map screen while a saved day hike is being followed, with the next turn in the lower third, or - where this build could not reach the trail network to resolve the hike against - the saved hike card that carries the Follow door'

/**
 * A walk on published tread (#1150), replacing the invented grid coordinates
 * day-hike-card.mjs still plants.
 *
 * THE TWO RECIPES NO LONGER SHARE A FIXTURE, and that is deliberate rather
 * than drift. The card's three honest states include the cached-figures one,
 * which it photographs and tests on purpose, and its fixture's
 * `concurrent_sources` is what puts "Two organizations keep this loop
 * walkable" in that frame. Moving it onto tread that resolves live would
 * change what THAT recipe photographs, which is not this issue's to decide.
 *
 * Every figure below is re-derived, not invented - see the header.
 */
const DAY_HIKES = {
  hikes: [
    {
      id: 'preview-fixture-followed-1',
      name: 'Ramapo-Dunderberg to Timp-Torne',
      date: '2026-08-29',
      segments: [
        [
          { coord: [-73.96567, 41.28166], poiId: null },
          { coord: [-74.0002, 41.27722], poiId: null },
        ],
      ],
      // What the graph routes between those two ends, cached the way a phone
      // that once resolved this walk would have cached it. Printed only where
      // the graph CANNOT be reached - see the caption - so their job is to be
      // honest in that frame rather than to be what the live resolution shows.
      figures: {
        miles: 2.85,
        legs: [
          {
            name: 'Ramapo-Dunderberg',
            source: 'oprhp_trails',
            blaze_color: 'Blue',
            miles: 0.07,
          },
          {
            name: 'Timp-Torne',
            source: 'oprhp_trails',
            blaze_color: 'Blue',
            miles: 0.88,
          },
          // Unnamed in the published data, and left that way. A leg name is
          // `string | null` precisely so a segment nobody named can say so.
          { name: null, source: 'oprhp_trails', blaze_color: 'Unknown', miles: 0.51 },
          // Two rows, not one, because that is what the resolver produces:
          // these are separate published designations that happen to share a
          // name, so #1115's merge does not fold them. Cached as it comes
          // rather than tidied, since the whole job of this block is to be
          // what a phone that once resolved this walk would have stored.
          { name: '1777', source: 'oprhp_trails', blaze_color: 'Red', miles: 0.63 },
          { name: '1777', source: 'oprhp_trails', blaze_color: 'Red', miles: 0.07 },
          {
            name: 'Ramapo - Dunderberg',
            source: 'oprhp_trails',
            blaze_color: 'Red',
            miles: 0.34,
          },
          {
            name: 'Ramapo-Dunderberg',
            source: 'oprhp_trails',
            blaze_color: 'Blue',
            miles: 0.35,
          },
        ],
      },
      // NOT a loop. It was `true` while the fixture was invented, and it is a
      // point-to-point walk between two published vertices - #1150 names this
      // as one of the three things that had to move with the coordinates.
      looped: false,
      recorded: 'planned',
    },
  ],
  openId: null,
}

/** A vertex of the 1777 edge the walk crosses, so the fix lands ON the route
 *  rather than beside it. Public trail geometry, and a fictional hiker. */
const FIX = { longitude: -73.9888, latitude: 41.27444 }

export default async function drive(page) {
  // A made-up point on the fixture's own grid. The switch below is what the
  // app reads; this is what the browser answers with once it does.
  await page.context().grantPermissions(['geolocation'])
  await page.context().setGeolocation(FIX)

  await page.evaluate(
    ({ store }) =>
      new Promise((done, fail) => {
        const open = indexedDB.open('keyval-store')
        open.onupgradeneeded = () => open.result.createObjectStore('keyval')
        open.onerror = () => fail(open.error)
        open.onsuccess = () => {
          const write = open.result
            .transaction('keyval', 'readwrite')
            .objectStore('keyval')
            .put(store, 'ourhike:day-hikes')
          write.onsuccess = () => done()
          write.onerror = () => fail(write.error)
        }
      }),
    { store: DAY_HIKES },
  )
  // The store is read once at mount, which has already happened - reload so
  // the app wakes up owning the fixture, exactly as a phone reopening would.
  await page.reload({ waitUntil: 'load' })

  // Location through the SWITCH rather than through the store, and that is
  // not a stylistic choice: the runner's skip-first-run script is an init
  // script, so it rewrites the preferences record on every navigation and a
  // seeded `location_permission_requested` is gone by the time the app reads
  // it. The switch is also the door a hiker uses, which makes this drive one
  // a person could repeat.
  // Through More's destination rows since #1054 - the tab is "More" again
  // and Safety & privacy is a sub-page behind a row, not an inner tab.
  await page.getByRole('tab', { name: 'More' }).click()
  await page.getByRole('button', { name: /^Safety & privacy/ }).click()
  await page.getByRole('checkbox', { name: 'Use my location' }).check()

  await page.getByRole('tab', { name: 'Plan' }).click()
  await page.getByRole('button', { name: /Ramapo-Dunderberg to Timp-Torne/ }).click()
  // The card is up once its legs heading prints - true whether or not the
  // graph came. The HEADING and not the bare text: the live resolution also
  // prints "6.4 mi · 2 legs" in the figures line, and `getByText('Legs')`
  // matches both of those, which is a strict-mode violation rather than a
  // wait. Found by driving this against a fixture data bucket, which is the
  // state this recipe exists for.
  await page.getByRole('heading', { name: 'Legs' }).waitFor()

  const follow = page.getByRole('button', { name: 'Follow this hike on the map' })
  // Present only where the graph resolved the fixture, which since #1150 is
  // every build that can reach the bucket at all: the fixture's ends are
  // published vertices rather than invented grid points, so the tolerance is
  // no longer what decides this - reaching the data is. Where a build cannot
  // (a fork's pull request gets no secrets, and a bucket can stop answering),
  // the card IS the frame and it is the true one - see the caption, which
  // says so rather than leaving the picture to be read as the followed map
  // (#1058).
  //
  // Not thrown, deliberately. A throw lands an error row in the preview
  // comment (photograph-preview.mjs:338-339), and filling that row with an
  // expected, filed condition is how a row that should mean "this recipe
  // broke" stops being read.
  if ((await follow.count()) === 0) return
  await follow.click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()
}
