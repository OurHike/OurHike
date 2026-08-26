// The trips-room timeline, and which of its rows may call itself a rest
// (#1031).
//
// WHAT THIS SHOT IS EVIDENCE FOR - one thing, and it is an absence, so the
// fixture below is the other half of the evidence and has to be read beside
// the picture. TWO of the seeded days carry `rest: true`:
//
//   - day 2, Lost Mountain → Wise Shelter, 4.2 mi - a nearo the hiker's own
//     rhythm placed. It prints "nearo · your rest day", and must.
//   - day 4, Thomas Knob → Old Orchard, 12.8 mi - the same flag, stranded on
//     a day a cascade re-planned underneath it. Before #1031 this row
//     printed the identical badge; here it prints none.
//
// So the picture is one badge on a timeline holding two flags, and a
// reviewer can check the claim against the store four inches above it. The
// stranded flag is dropped by `validatePlan` on the way in, which is where a
// plan written by an older build is met - the trip store runs every plan
// through it (lib/trips.ts).
//
// WHAT IT IS NOT EVIDENCE FOR: the ≈time and ↑ figures on each row, which
// need `elevation_profile.json` from the release. A preview build carries an
// empty VITE_DATA_BASE_URL (#1024), so the rows here print distance and the
// badge and nothing priced. That is the whole of what this change touches.
//
// AND THE BADGE THAT SURVIVES IS CLIPPED IN THIS SHOT, which is a second
// defect rather than a flaw in the fixture: `.plan__day` sets an exact
// height and hides its overflow, so a row whose title wraps to two lines
// cuts its bottom line off - measured here at 3 of 13 px. That is #1032, and
// it is not fixed on this branch. Read the shot for the ABSENCE on the
// 12.8-mile row, which is what this recipe is for; the sliver on the
// 4.2-mile row is #1032 showing through.
//
// Fixtures are nobody's data: real A.T. place names off the published
// centerline, no account, no location fix (the skill's never-photograph
// list, kept by construction).

export const caption = 'The timeline, with a rest badge only where a day is still a rest'
export const alt =
  'A trip timeline: the 4.2-mile day reads “nearo · your rest day”, the 12.8-mile day above it reads only its distance'

const DAY = (id, date, extra = {}) => ({
  id,
  date,
  pinned: false,
  generated: true,
  ...extra,
})

const TRIPS = {
  trips: [
    {
      id: 'preview-fixture-trip',
      name: 'Damascus → Atkins',
      plan: {
        target: { miles: 15 },
        rhythm: { everyDays: 2, kind: 'nearo' },
        stops: [
          { mile: 470.8, name: 'Damascus', resupply: true },
          { mile: 486.2, name: 'Lost Mountain Shelter', resupply: false },
          { mile: 490.4, name: 'Wise Shelter', resupply: false },
          { mile: 503.3, name: 'Thomas Knob Shelter', resupply: false },
          { mile: 516.1, name: 'Old Orchard Shelter', resupply: false },
          { mile: 525.7, name: 'Atkins', resupply: true },
        ],
        days: [
          DAY('preview-day-1', '2026-05-12'),
          // The nearo the rhythm placed - 4.2 mi, and a rest by any reading.
          DAY('preview-day-2', '2026-05-13', { rest: true, generated: false }),
          DAY('preview-day-3', '2026-05-14'),
          // The stranded one: 12.8 mi wearing the same flag, which is what a
          // pre-#1031 cascade left behind on a re-planned day.
          DAY('preview-day-4', '2026-05-15', { rest: true }),
          DAY('preview-day-5', '2026-05-16'),
        ],
      },
    },
  ],
  openId: 'preview-fixture-trip',
  hikes: [],
  groups: [],
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
            .put(store, 'ourhike:trips')
          write.onsuccess = () => done()
          write.onerror = () => fail(write.error)
        }
      }),
    { store: TRIPS },
  )
  // The store is read once at mount, which has already happened - reload so
  // the app wakes up owning the fixture, exactly as a phone reopening would.
  await page.reload({ waitUntil: 'load' })

  await page.getByRole('tab', { name: 'Plan' }).click()
  // One trip and nothing else opens straight onto its timeline rather than
  // the home, so the rows are up once the badge that survived prints.
  await page.getByText('nearo · your rest day').waitFor()
}
