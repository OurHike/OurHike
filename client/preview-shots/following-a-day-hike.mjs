// Following a saved day hike (#1041, storyboard frames D9-D11) - the map
// while a walk is being followed: the header reading the walk's own distances
// instead of a Springer mile, and the next turn in the lower third.
//
// THE SEED, AND WHY IT IS THE ONE day-hike-card.mjs ALREADY USES. Reaching
// this screen means owning a saved day hike the graph can still place, and a
// drive of pure taps cannot build one - the builder needs `trail_graph.json`,
// which no preview holds until the pipeline first publishes it. So this
// plants the same fixture hike that recipe does, over the same invented grid
// coordinates: nobody's data, no account, and the one location fix on screen
// is a made-up point on the same grid rather than anybody's real position
// (the skill's never-photograph list, kept by construction).
//
// WHAT IT PHOTOGRAPHS TODAY, STATED RATHER THAN HOPED FOR - AND THE OLD
// ANSWER HERE WAS WRONG.
//
// This header used to say the preview build carries an empty
// VITE_DATA_BASE_URL (#1024, measured 2026-08-25), so the graph never
// arrives, the fixture cannot be resolved, and the card offers no Follow door
// at all. `day-hike-builder.mjs` re-measured that on 2026-08-27 and neither
// half survived: a deployed preview DOES carry a data source, and the bucket
// answers 200 for `trail_graph.json`, `trail_graph_geometry.json` and
// `trail_graph_elevation.json` with a sha256 for each in `latest.json`. What
// was actually stopping the camera was the camera's own origin - screenshot.
// mjs served from `127.0.0.1` on an OS-picked port, against a CORS allowlist
// holding exact origins - and that is fixed.
//
// AND THE FOLLOW DOOR IS STILL NOT THERE, FOR A SECOND REASON THAT IS THIS
// RECIPE'S OWN. Measured on run 1201 of pr-preview (2026-08-27, PR #1119):
// `day-hike-builder.mjs` photographed the builder bar over a live map in the
// same run, so the graph plainly arrives - and this recipe still landed on
// the card, under the card's own sentence, "This phone's current trail map
// can't place this walk, so these are the figures from the day it was
// saved."
//
// The fixture's ends are INVENTED grid coordinates, and `resolveDayHike`
// needs each of them within `MAX_OFF_NETWORK_FEET` (150 ft) of a published
// line. Against a fixture bucket, where the network is the same invented
// grid, they land on it; against the real one they land in the woods between
// real trails. So the two halves of this recipe's seed pull against each
// other: the coordinates were chosen to be nobody's data, and being nobody's
// data is exactly what stops the live network claiming them.
//
// What would settle it is a fixture on the PUBLISHED Pine Meadow line -
// which is public trail geometry and nobody's personal data, so it costs the
// never-photograph list nothing. It is not done here because it cannot be
// checked from an agent sandbox: Chromium here reaches no external host, so
// picking coordinates off the live artifact and confirming they resolve is
// work for a session that can see the bucket.
//
// #1045 ADDED AN ELEVATION RIBBON TO THAT FRAME, AND IT NEEDS ONE MORE
// ARTIFACT THAN THE BUCKET HAS. A followed walk now draws its own profile -
// miles from the hiker's first step - from `trail_graph_profile.json`, which
// `pipeline/export_network_profile.py` publishes and which no release has
// carried yet. Until `publish-vector-data.yml` runs from a `main` holding
// that exporter, the bucket 404s it and the frame has no ribbon on it. That
// is not a fault in this recipe and not a missing feature: it is #1041's
// honest state, which #1045 keeps deliberately - a walk this phone has no
// shape for gets no ribbon rather than the A.T.'s borrowed.
//
// So the drive takes the door WHEN IT IS THERE and stops on the card when it
// is not, and the frame is true either way. It is the same "several honest
// states, one recipe" shape day-hike-card.mjs already ships.
//
// The alt below is unchanged deliberately. It already describes the two
// states this recipe can actually reach, and adding "with an elevation
// ribbon" to a sentence a screen-reader user gets INSTEAD of the picture
// would describe a band that is not in either frame today - which is the
// failure #1058 rewrote this caption to stop.

// THE CAPTION NAMES BOTH FRAMES, because a static string cannot know which
// one landed (#1058). photograph-preview.mjs reads `caption` and `alt` off
// the module (scripts/photograph-preview.mjs:188-190) before the drive runs,
// so they cannot be decided by what the drive reached - and the drive reaches
// the followed map only where the graph resolved the fixture.
//
// It used to say "Following a saved day hike ... with the next turn in the
// lower third" unconditionally, over a picture of the CARD - the same frame
// day-hike-card.mjs publishes, under a caption describing a screen the
// reviewer was not being shown. CLAUDE.md's own words for that: it "looks
// like evidence and is not". The alt matters most of the two, because a
// screen-reader user gets that sentence and no picture to correct it with.
export const caption = 'Following a day hike, or the card it starts from'
export const alt =
  'Either the map screen while a saved day hike is being followed, with the next turn in the lower third, or - where this build has no trail network to resolve the hike against - the saved hike card that carries the Follow door'

/** The same fixture the finished-hike card's recipe plants. */
const DAY_HIKES = {
  hikes: [
    {
      id: 'preview-fixture-1',
      name: 'Pine Meadow loop',
      date: '2026-08-29',
      segments: [
        [
          { coord: [-74.095, 41.25], poiId: null },
          { coord: [-74.085, 41.25], poiId: null },
        ],
      ],
      figures: {
        miles: 6.4,
        legs: [
          {
            name: 'Pine Meadow Trail',
            source: 'oprhp_trails',
            blaze_color: 'Blue',
            miles: 6.4,
          },
        ],
      },
      looped: true,
      recorded: 'planned',
    },
  ],
  openId: null,
}

/** Between the fixture's two ends. Invented, like they are. */
const FIX = { longitude: -74.09, latitude: 41.25 }

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
  await page.getByRole('button', { name: /Pine Meadow loop/ }).click()
  // The card is up once its legs heading prints - true whether or not the
  // graph came. The HEADING and not the bare text: the live resolution also
  // prints "6.4 mi · 2 legs" in the figures line, and `getByText('Legs')`
  // matches both of those, which is a strict-mode violation rather than a
  // wait. Found by driving this against a fixture data bucket, which is the
  // state this recipe exists for.
  await page.getByRole('heading', { name: 'Legs' }).waitFor()

  const follow = page.getByRole('button', { name: 'Follow this hike on the map' })
  // Present only where the graph resolved the fixture. Where it did not, the
  // card IS the frame, and it is the true one for a build the bucket did not
  // answer - see the header, and the caption, which says so rather than
  // leaving the picture to be read as the followed map (#1058).
  //
  // Not thrown, deliberately. A throw lands an error row in the preview
  // comment (photograph-preview.mjs:338-339), and filling that row with an
  // expected, filed condition is how a row that should mean "this recipe
  // broke" stops being read.
  if ((await follow.count()) === 0) return
  await follow.click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()
}
