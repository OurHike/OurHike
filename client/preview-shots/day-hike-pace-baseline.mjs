// A walking time, and what it was adjusted from (#851, #1350).
//
// WHAT THIS SHOT IS EVIDENCE FOR - one thing, and it needs the fixture below
// read beside it, because the claim is about a RELATIONSHIP between two lines
// rather than about either one.
//
// Every "Ready to walk" row prints an approximate walking time, and under it
// the line saying whose estimate that is: the top row reads `≈4h 20m` over
// `was ≈3h · 1.4x standard`. The
// figure alone is what shipped, on this screen and on two others - and a
// hiker who set their pace optimistic in week one had no way to tell that the
// number they were picking tomorrow's walk on was not Naismith's own. #851's
// decision, the maintainer's, is that the two never travel apart.
//
// THE SEEDED PACE IS WHAT MAKES IT VISIBLE, and it is the other half of the
// evidence. `ourhike:pace` below is 1.9 mph against the standard 3.107, which
// is a real setting a slow walker would choose and inside the control's own
// 1-4 range. At the STANDARD pace `relativeLine` is null by design and none
// of these rows carries a second line at all - a caveat on every line reads
// exactly like a caveat on none - so a shot of a default install would be
// evidence of nothing.
//
// WHY THE FIGURES ARE ON THE RECORD rather than routed. `cachedEstimate`
// prices a saved hike from `figures.miles` and `figures.climb`, both stored,
// so this screen needs neither the junction graph nor the elevation artifact
// - which is the whole reason it can be photographed in a preview build at
// all (an empty VITE_DATA_BASE_URL, #1024). The builder's own panel carries
// the same fix and cannot be shown here for exactly that reason: its figure
// comes from a live route.
//
// Fixtures are nobody's data: invented names, a grid of coordinates walking
// north, no account, no location fix (the skill's never-photograph list, kept
// by construction).

export const caption = 'A walking time with the pace it was adjusted from underneath'
export const alt =
  'Saved day hikes, each row reading a distance and an approximate walking time, with a smaller line beneath giving the standard time and the multiple'

const NAMES = [
  'Pine Meadow loop',
  'Seven Hills, out and back',
  'Claudius Smith Den',
  'Island Pond loop',
  'Ramapo Torne',
]

const DAY_HIKES = {
  hikes: NAMES.map((name, at) => ({
    id: `preview-fixture-${at}`,
    name,
    date: at % 2 === 0 ? `2026-09-${String(14 + at).padStart(2, '0')}` : null,
    segments: [
      [
        { coord: [-74.1 + at * 0.004, 41.2 + at * 0.004], poiId: null },
        { coord: [-74.09 + at * 0.004, 41.2 + at * 0.004], poiId: null },
      ],
    ],
    figures: {
      miles: 3 + at * 0.9,
      legs: [
        {
          name: 'Pine Meadow Trail',
          source: 'oprhp_trails',
          blaze_color: 'Blue',
          miles: 3 + at * 0.9,
        },
      ],
      // The cached climb is what lets the row be priced at all - a record
      // saved without one prints no time, which is the honest state and the
      // one the existing day-hike-list shot happens to photograph.
      climb: { gainFt: 700 + at * 260, lossFt: 700 + at * 260 },
    },
    looped: at % 2 === 0,
    recorded: 'planned',
  })),
  openId: null,
}

/**
 * 1.9 mph on the flat - a slow walker's own setting, inside the control's own
 * 1-4 range, and far enough from the standard 3.107 that the ratio rounds to
 * something worth printing.
 *
 * What the rows come out at, computed through `paceEstimate` rather than
 * guessed - and IN THE ORDER THE SCREEN PUTS THEM, which is the list's own
 * `recent` sort and not the order they are written below:
 *
 *   Ramapo Torne          6.6 mi   ≈4h 20m   was ≈3h     · 1.4x standard
 *   Claudius Smith Den    4.8 mi   ≈3h 10m   was ≈2h 10m · 1.5x standard
 *   Pine Meadow loop      3.0 mi   ≈1h 55m   was ≈1h 20m · 1.5x standard
 *   Seven Hills           3.9 mi   ≈2h 30m   was ≈1h 45m · 1.5x standard
 *   Island Pond loop      5.7 mi   ≈3h 45m   was ≈2h 35m · 1.5x standard
 *
 * Written down so a reviewer can check the picture against arithmetic rather
 * than against a claim - which is also how the sort was caught: the first
 * version of this header named the wrong top row.
 */
const PACE = {
  flatPaceMph: 1.9,
  ascentMetersPerHour: 600,
  descentMinutesPer1000m: 0,
}

export default async function drive(page) {
  await page.evaluate(
    ({ store, pace }) =>
      new Promise((done, fail) => {
        // The pace is localStorage rather than IndexedDB, matching lib/pace.ts:
        // it is read while a sheet renders, and an async read would mean a
        // frame with the wrong number on it.
        localStorage.setItem('ourhike:pace', JSON.stringify(pace))
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
    { store: DAY_HIKES, pace: PACE },
  )
  // Both stores are read once at mount, which has already happened - reload so
  // the app wakes up owning them, exactly as a phone reopening would.
  await page.reload({ waitUntil: 'load' })

  await page.getByRole('tab', { name: 'Plan' }).click()
  await page.getByRole('button', { name: `All ${NAMES.length} ›` }).click()
  await page.getByText('Ready to walk').waitFor()
  // The shot is not up until a baseline has actually printed: this waits on
  // the line the change adds, so a run where the pace failed to seed fails
  // here rather than publishing a picture of the old screen.
  await page
    .getByText(/standard/)
    .first()
    .waitFor()
}
