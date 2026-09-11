// A fixture for the saved day-hike card (#980, frame `1l`), factored out of
// day-hike-card.mjs so a Playwright spec can seed the same real hike profile
// rather than re-deriving one - one home per fixture, same as
// preview-shots/fixtures/longHike.mjs.
//
// NOBODY'S DATA. An invented name, a grid coordinate pair, no account, no
// location fix - the skill's never-photograph list, kept by construction.
//
// THREE HONEST STATES, ONE FIXTURE. Until the trail graph publishes, a card
// opened on this fixture leans on its own saved-time figures under the
// sentence saying exactly that - the state this repo's own agent sandbox and
// CI's dev server both land on, since neither can reach a graph (see
// day-hike-card.mjs's header and features/FLOW_TESTING.md). Once
// `trail_graph.json` is live, the same seed resolves live instead: whatever
// real trail claims the fixture's ends through the same projection a tap
// uses. Once `trail_graph_elevation.json` is live too, that resolution also
// carries a climb and a time. All three are true of this one fixture; which
// one a given environment reaches is what it reaches.

export const DAY_HIKES = {
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
            // Both organizations designate this tread; the leg wears one
            // name and credits the other (#1115). Invented, like every
            // other figure in this fixture - nobody's data.
            concurrent_sources: ['nynjtc_long_path'],
          },
        ],
      },
      looped: true,
      recorded: 'planned',
    },
  ],
  openId: null,
}

/** Seed the fixture into idb-keyval's `ourhike:day-hikes` key, then reload -
 *  the store is read once at mount, which has already happened by the time
 *  a drive or a spec calls this. */
export async function seedDayHikes(page, store = DAY_HIKES) {
  await page.evaluate(
    ({ store: seeded }) =>
      new Promise((done, fail) => {
        const open = indexedDB.open('keyval-store')
        open.onupgradeneeded = () => open.result.createObjectStore('keyval')
        open.onerror = () => fail(open.error)
        open.onsuccess = () => {
          const write = open.result
            .transaction('keyval', 'readwrite')
            .objectStore('keyval')
            .put(seeded, 'ourhike:day-hikes')
          write.onsuccess = () => done()
          write.onerror = () => fail(write.error)
        }
      }),
    { store },
  )
  await page.reload({ waitUntil: 'load' })
}
