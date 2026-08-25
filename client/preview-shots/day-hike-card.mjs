// The finished day hike's card (#980, frame `1l`), opened from the Plan
// home's day-hikes row.
//
// THE SEED, AND WHY A DRIVE OF PURE TAPS CANNOT GET HERE. A hiker reaches
// this card by building a day hike, and building one needs the junction
// graph - which no preview holds until the pipeline first publishes
// `trail_graph.json`. So this drive plants ONE fixture hike in the store and
// reloads before tapping, which is the runner's own first-run trick applied
// one store over. The fixture is nobody's data: an invented name, a grid
// coordinate pair, no account, no location fix (the skill's
// never-photograph list, kept by construction).
//
// Touched with #1002 so the camera re-photographs the card now that per-leg
// miles print again, priced at the walked metres.
//
// TWO HONEST STATES, ONE RECIPE. Until the graph publishes, the card leans
// on the fixture's cached figures under the sentence saying exactly that -
// a state this card ships with and tests. Once `trail_graph.json` is live,
// the same recipe photographs the live resolution instead: whatever real
// trail claims the fixture's ends through the same projection a tap uses,
// with the ways-off block. Both frames are true; the camera does not care
// which one it gets.

export const caption = 'The finished day hike’s card'
export const alt = 'A saved day hike’s card, opened from the Plan tab'

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
            blaze_color: 'blue',
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

export default async function drive(page) {
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

  await page.getByRole('tab', { name: 'Plan' }).click()
  await page.getByRole('button', { name: /Pine Meadow loop/ }).click()
  // The card is up once its legs print - true in both of the states above.
  await page.getByText('Legs').waitFor()
}
