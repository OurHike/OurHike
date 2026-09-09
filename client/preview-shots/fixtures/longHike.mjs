// Fixtures for the long-hike recipes (#1317): one hike with two sections on
// it, seeded into the trip store the app reads (lib/trips.ts, under
// `ourhike:trips`), plus the mode that makes it lead.
//
// NOBODY'S DATA. An invented hike over invented ends on the A.T.'s published
// mile axis, with no photos and no account: a photo is a data surface with a
// credit and a licence (features/POI_PHOTOS.md), and a recipe that pointed
// at somebody's walk would publish it on every future pull request.
//
// THE DATES ARE RELATIVE, AND THAT IS THE CORRECTION. They were pinned
// first, on the reasoning that a recipe shot in March and one shot in
// September should produce the same frame - and it was wrong, because
// nothing pins the APP's clock. Today's card renders for the day dated
// today, so a fixture dated to 2026-09-08 photographs a card in September
// and no card at all in March, which is the one thing this shot exists to
// show. So the days are laid around the browser's own today at seed time:
// the printed date moves between runs and the frame does not, and the frame
// is what the shot is evidence about.
//
// Not a recipe: the runner treats every top-level `preview-shots/*.mjs` as
// one, so shared fixtures live one directory down where that pattern does
// not reach.

/** An ISO day `offset` days from `from`. */
function day(from, offset) {
  const at = new Date(from.getTime() + offset * 86_400_000)
  return at.toISOString().slice(0, 10)
}

function planDay(id, date, walked) {
  return { id, date, pinned: false, generated: true, walked }
}

/**
 * Springer to Katahdin, eight days in, with one section behind it.
 *
 * The day lengths are the ones a hiker in Georgia actually walks - eleven
 * and twelve miles rather than a twenty-six-mile day, which is what the
 * first version of this fixture produced by putting one day between two
 * stops that were a resupply apart. A shot is copy AND figures, and an
 * implausible figure in one is a reviewer's time spent working out whether
 * the app computed it wrong.
 */
export function tripStore(today = new Date()) {
  return {
    openId: null,
    activeHikeId: 'fixture-hike',
    groups: [],
    trips: [
      {
        id: 'fixture-section-walked',
        name: 'Springer → Neels Gap',
        plan: {
          target: { miles: 12 },
          stops: [
            { mile: 0, name: 'Springer Mountain', resupply: false },
            { mile: 15.8, name: 'Gooch Mountain Shelter', resupply: false },
            { mile: 31.7, name: 'Neels Gap', resupply: true },
          ],
          days: [
            planDay('fixture-day-1', day(today, -8), true),
            planDay('fixture-day-2', day(today, -7), true),
          ],
        },
      },
      {
        id: 'fixture-section-walking',
        name: 'Neels Gap → Dicks Creek Gap',
        plan: {
          target: { miles: 11 },
          stops: [
            { mile: 31.7, name: 'Neels Gap', resupply: false },
            { mile: 42.9, name: 'Low Gap Shelter', resupply: false },
            { mile: 54.4, name: 'Tray Mountain Shelter', resupply: false },
            { mile: 69.6, name: 'Dicks Creek Gap', resupply: true },
          ],
          days: [
            planDay('fixture-day-3', day(today, -1), true),
            planDay('fixture-day-4', day(today, 0), false),
            planDay('fixture-day-5', day(today, 1), false),
          ],
          // See finishedStore: it walks every one of these, because a hike
          // marked finished whose days are not walked prints what is left
          // under the word FINISHED - which is the screen being right.
        },
      },
    ],
    hikes: [
      {
        id: 'fixture-hike',
        name: 'Springer → Katahdin',
        type: 'thru',
        trailId: 'AT',
        points: [
          { name: 'Springer Mountain', mile: 0 },
          { name: 'Katahdin', mile: 2197.4 },
        ],
        status: 'walking',
        tripIds: ['fixture-section-walked', 'fixture-section-walking'],
      },
    ],
  }
}

/**
 * A hike that is genuinely finished, with NO active pointer - which is how
 * its record is reachable: tapping Long hike with nothing active opens the
 * pick sheet, and picking a finished hike lands on its record rather than on
 * a Today screen with nothing planned.
 *
 * ITS ENDS ARE THE GROUND THE SECTIONS ACTUALLY COVER, and that is a
 * correction worth keeping. The first version marked the Springer-to-Katahdin
 * hike finished while its two sections covered 42.9 of 2,197.4 miles, and
 * the record printed "2,154.5 mi to go" under the word FINISHED. The screen
 * was right and the fixture was wrong: `leftMi` is what the walking actually
 * covers, and a status flag does not get to overrule it - a display that
 * printed 0 because a flag said finished would be exactly the display
 * outrunning its source that CLAUDE.md forbids. So this is a section hike
 * that really was walked end to end.
 *
 * Its `finishedOn` is after its last dated day, for the same reason: the
 * first version dated the finish four weeks BEFORE the walking and the
 * header printed "1 Sept 2026 – 12 Aug 2026", which reads as a rendering
 * fault and is a fixture that could not happen.
 */
export function finishedStore(today = new Date()) {
  const base = tripStore(today)
  return {
    ...base,
    activeHikeId: null,
    trips: base.trips.map((trip) => ({
      ...trip,
      plan: {
        ...trip.plan,
        days: trip.plan.days.map((entry) => ({ ...entry, walked: true })),
      },
    })),
    hikes: [
      {
        ...base.hikes[0],
        name: 'Springer → Dicks Creek Gap',
        type: 'section',
        points: [
          { name: 'Springer Mountain', mile: 0 },
          { name: 'Dicks Creek Gap', mile: 69.6 },
        ],
        status: 'finished',
        finishedOn: day(today, 1),
      },
    ],
  }
}

/** Seed the store and the mode, then reload so the app wakes up owning
 *  both - day-hike-list.mjs's move, with a second key. */
export async function seedLongHike(page, build = tripStore) {
  await page.evaluate(
    ({ store: seeded }) =>
      new Promise((done, fail) => {
        const open = indexedDB.open('keyval-store')
        open.onupgradeneeded = () => open.result.createObjectStore('keyval')
        open.onerror = () => fail(open.error)
        open.onsuccess = () => {
          const shelf = open.result
            .transaction('keyval', 'readwrite')
            .objectStore('keyval')
          shelf.put(seeded, 'ourhike:trips')
          const write = shelf.put('long', 'ourhike:hiker-mode')
          write.onsuccess = () => done()
          write.onerror = () => fail(write.error)
        }
      }),
    { store: build() },
  )
  await page.reload({ waitUntil: 'load' })
  // The mode switch, not the hike's name: a FINISHED hike with no active
  // pointer leads no screen, so its name is nowhere until the pick sheet
  // opens. Waiting on it here made a failure look like the recipe's drive
  // rather than the seed's own landing.
  await page.getByRole('radio', { name: 'Long hike' }).waitFor()
}
