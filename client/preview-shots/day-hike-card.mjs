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
// miles print again, priced at the walked metres. Touched again with #1011,
// which puts the ± elevation, the ≈ walking time and the estimate note on
// this same card.
//
// THREE HONEST STATES, ONE RECIPE, and the third arrived with #1011. Until
// the graph publishes, the card leans on the fixture's cached figures under
// the sentence saying exactly that - a state this card ships with and tests.
// Once `trail_graph.json` is live, the same recipe photographs the live
// resolution instead: whatever real trail claims the fixture's ends through
// the same projection a tap uses, with the ways-off block. Once
// `trail_graph_elevation.json` is live TOO, that resolution also carries a
// climb and a time.
//
// The card never prints a climb over the cached figures, deliberately (see
// screens/DayHikeCard.tsx), so the first state photographs without one and
// that is the correct picture rather than a missing feature. All three frames
// are true; the camera does not care which one it gets.

// Touched by #1008 so the camera re-takes the card it changed: the date
// field, the gap rows, and the "Leave this with someone" primary all landed
// on this screen (leave-with-someone.mjs photographs that sheet itself).
//
// Touched again by #1042, which adds the moving-time sentence to the note
// under the figures. That sentence rides the THIRD state above, so a preview
// without `trail_graph_elevation.json` photographs the first state and shows
// none of it - correctly. Say so rather than reading the shot as a missing
// feature: DayHikeCard.test.tsx is where that sentence is actually pinned,
// and the camera is here for the states it can reach.
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
  // The card is up once its legs heading prints - true in all three states
  // above. The HEADING and not the bare text, which was this drive's own
  // latent break: once the graph resolves, the figures line reads "6.4 mi ·
  // 2 legs" and `getByText('Legs')` matches that AND the heading, which is a
  // strict-mode violation rather than a wait. Nothing had reached that state
  // to find out until #1041 drove this flow against a fixture data bucket.
  await page.getByRole('heading', { name: 'Legs' }).waitFor()
}
