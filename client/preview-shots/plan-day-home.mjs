// The Plan tab's day-hikes home (#1008, storyboard frame D1): the mode
// band, the switch chip to the trips room, the saved-hike shelf with its
// All N › door, and the one action.
//
// Seeds the same fixture store day-hike-card.mjs plants - an invented name,
// grid coordinates, no account, no location fix (the skill's
// never-photograph list, kept by construction) - and simply stops on the
// home instead of opening the row. With one day hike and no trips, the tab
// opens on the day room by itself, which is the defaulting rule under test
// in PlanHome.test.tsx photographed working.
//
// 2026-08-25: re-photographed on purpose. This band's legibility changed and
// nothing else in the pull request reaches it - the eyebrow went from 0.75
// to 0.85 opacity (4.01:1 to 4.72:1 at night), the switch chip took a 44px
// hit area, and its focus ring stopped being drawn in the same colour as the
// band behind it (measured 1.00:1, on the only control between the two
// rooms). `photograph-preview.mjs` shoots the recipes a pull request adds or
// CHANGES, so a contrast fix with no recipe touched ships with no picture of
// the thing it fixed.

export const caption = 'The day-hikes home, with its mode band'
export const alt = 'The Plan tab in day-hike mode: forest band, switch chip, saved hikes'

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
  // The home is up once the band names the room.
  await page.getByRole('heading', { name: 'Day hikes' }).waitFor()
}
