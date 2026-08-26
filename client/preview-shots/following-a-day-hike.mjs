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
// WHAT IT PHOTOGRAPHS TODAY, STATED RATHER THAN HOPED FOR. The preview build
// carries an empty VITE_DATA_BASE_URL (#1024 - measured 2026-08-25 in two
// deployed previews), so the graph does not arrive, the fixture cannot be
// resolved against it, and the card offers no Follow door at all - which is
// the honest behaviour, not a fault: following is a live position against a
// ROUTE, and a hike leaning on its stored cache has no route to be on.
//
// So the drive takes the door WHEN IT IS THERE and stops on the card when it
// is not, and the frame is true either way. It is the same "several honest
// states, one recipe" shape day-hike-card.mjs already ships, and it becomes
// the picture this change is about on the day #1024 lands.

export const caption = 'Following a saved day hike'
export const alt =
  'The map screen while a saved day hike is being followed, with the next turn in the lower third'

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
  // wait. Found by driving this against a fixture data bucket - the state no
  // preview has yet (#1024) and the one this recipe exists for.
  await page.getByRole('heading', { name: 'Legs' }).waitFor()

  const follow = page.getByRole('button', { name: 'Follow this hike on the map' })
  // Present only where the graph resolved the fixture. Where it did not, the
  // card IS the frame, and it is the true one for a build with no data
  // source - see the header.
  if ((await follow.count()) === 0) return
  await follow.click()
  await page.getByRole('region', { name: /trail map/i }).waitFor()
}
