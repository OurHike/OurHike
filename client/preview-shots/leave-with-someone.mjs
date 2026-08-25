// "Leave this with someone" (#1008, storyboard frame D6): the plain-text
// card, its typed fields, and the sentence that keeps "if I'm not back by"
// a field rather than a calculation.
//
// Same fixture seed as day-hike-card.mjs, then one tap further: the saved
// hike's card, then its primary action. Nothing typed into the fields on
// purpose - the empty state is the honest one to publish (typed lines are a
// person's plan, even an invented person's), and the preview block already
// shows the app-composed half of the card.

export const caption = 'Leave this with someone'
export const alt =
  'The leave-with-someone sheet: typed fields and the plain-text card preview'

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
  await page.reload({ waitUntil: 'load' })

  await page.getByRole('tab', { name: 'Plan' }).click()
  await page.getByRole('button', { name: /Pine Meadow loop/ }).click()
  await page.getByRole('button', { name: 'Leave this with someone' }).click()
  // The sheet is up once the card preview prints the app-composed line.
  await page.getByText(/on marked trails/).waitFor()
}
