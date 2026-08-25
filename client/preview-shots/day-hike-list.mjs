// Your day hikes (#1008, storyboard frame D7) - the list that did not
// exist, with a card opened over it.
//
// TWO THINGS THIS SHOT IS EVIDENCE FOR, and neither can be asserted in
// jsdom, which does no layout:
//
//   1. The split shelves and the sort chips, on a list long enough to be a
//      list rather than a row.
//   2. That a card opened from a row DOCKS TO THE SCREEN, not to the bottom
//      of the list. `.plan` is the containing block for `.day-hike-card` and
//      grows with its content, so before `plan--bounded` a tap on the first
//      row of a twenty-hike list opened a card a screenful below the fold and
//      read as a tap that did nothing.
//
// Fixtures are nobody's data: invented names, a grid of coordinates walking
// north, no account, no location fix (the skill's never-photograph list, kept
// by construction). Enough of them to overflow a phone, because the defect
// this photographs only appears once the list is longer than the screen.

export const caption = 'Your day hikes, with one opened'
export const alt =
  'The saved day-hike list, split into ready-to-walk and walked, with a hike’s card open over it'

const NAMES = [
  'Pine Meadow loop',
  'Seven Hills, out and back',
  'Bear Mountain over Perkins',
  'Claudius Smith Den',
  'Reeves Meadow to the lake',
  'Diamond Mountain',
  'Almost Perpendicular',
  'Tuxedo to Southfields',
  'Island Pond loop',
  'Stony Brook and back',
  'Ramapo Torne',
  'Cobus Mountain',
]

const DAY_HIKES = {
  hikes: NAMES.map((name, at) => ({
    id: `preview-fixture-${at}`,
    name,
    // A few dated, the rest not - an undated day hike is a first-class
    // state and the list has to show it as one.
    date: at % 3 === 0 ? `2026-09-${String(12 + (at % 15)).padStart(2, '0')}` : null,
    segments: [
      [
        { coord: [-74.1 + at * 0.004, 41.2 + at * 0.004], poiId: null },
        { coord: [-74.09 + at * 0.004, 41.2 + at * 0.004], poiId: null },
      ],
    ],
    figures: {
      miles: 3 + (at % 7) * 0.8,
      legs: [
        {
          name: 'Pine Meadow Trail',
          source: 'oprhp_trails',
          blaze_color: 'blue',
          miles: 3 + (at % 7) * 0.8,
        },
      ],
    },
    looped: at % 2 === 0,
    // The last two are walked, so the second shelf has something on it -
    // nothing in the client marks a hike walked yet (#982 builds that), so
    // a fixture is the only way to photograph the split.
    recorded: at >= NAMES.length - 2 ? 'walked' : 'planned',
  })),
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
  // the app wakes up owning the fixtures, exactly as a phone reopening would.
  await page.reload({ waitUntil: 'load' })

  await page.getByRole('tab', { name: 'Plan' }).click()
  await page.getByRole('button', { name: `All ${NAMES.length} ›` }).click()
  // The list is up once its first shelf prints.
  await page.getByText('Ready to walk').waitFor()

  // A row from the TOP of a list taller than the screen: the card it opens
  // has to be on screen, which is the half of this shot no test can make.
  await page
    .getByRole('button', { name: /Pine Meadow loop/ })
    .first()
    .click()
  await page.getByText('Leave this with someone').waitFor()
}
