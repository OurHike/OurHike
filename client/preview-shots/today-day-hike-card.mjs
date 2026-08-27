// A saved hike opened from TODAY, which is where a tap used to do nothing.
//
// WHAT THIS SHOT IS EVIDENCE FOR - one thing, and it is the same thing
// day-hike-list.mjs photographs one tab over, which is why it is a separate
// recipe rather than a second frame of that one: that a card opened from the
// Today shelf DOCKS TO THE SCREEN a hiker is looking at. #1054 put "Your day
// hikes" on the Today tab and wired its rows to the same store pointer the
// Plan tab's rows write, but nothing on Today rendered that pointer - the tap
// stored `openId`, started the geometry fetch the card needs, and put nothing
// on screen at all.
//
// So the picture worth having is the card over the JOURNAL, and the two
// things a jsdom test cannot check about it are both in frame: that it is
// there, and that it is docked to the bottom of the pane rather than to the
// bottom of a scrolled column. `.today` is bounded to the pane's own height
// and App.css makes that pane the containing block; neither fact is visible
// to a test that does no layout.
//
// WHAT IT IS NOT EVIDENCE FOR. The desktop half of the same fix - the card
// docked in the journal COLUMN beside the map, which desktop.css anchors -
// is not in this frame: the runner shoots a 390x844 phone, where that layout
// does not apply. desktopLayout.test.ts pins the anchoring as text and
// App.dayHike.test.tsx pins the wiring; say so rather than reading this shot
// as covering both.
//
// SECOND, AND ADDED WITH #1112: that the legs row no longer piles up on
// itself. It used to be a grid whose two trailing columns could not break, so
// a long steward name overflowed the card - the trail name squeezed to a
// stack under the mileage, the organization cut off at the edge. The row is a
// wrapping flex line now, and this shot is where that is visible.
//
// WHICH ROW WRAPS DEPENDS ON WHERE THIS RUNS, and only CI can show the
// defect. `orgLabelFrom` falls back to the raw source key when no steward
// matches, so a build with no data source prints `oprhp_trails` - 12
// characters, fits anywhere, and photographs a row that was never broken. CI
// resolves the real export and prints "New York State Office of Parks,
// Recreation and Historic Preservation" instead, at 68 characters, which is
// the row that used to collide. This recipe cannot seed its way past that:
// `loadTrailData` returns early when the phone holds no trail lines, so a
// stewards record planted in the store is never even read.
//
// So the fixture carries TWO legs on purpose, one per organization - 68
// characters against 36 - and in CI they photograph as the row that has to
// wrap and the row that still fits, side by side. That pairing is the whole
// argument for wrapping the name rather than truncating it. In a sandbox both
// print short keys and the frame says nothing about #1112; judge that half on
// the preview comment, not locally.
//
// The card's own contents are day-hike-card.mjs's subject and its header has
// the three honest states the figures can be in - a preview without
// `trail_graph.json` photographs the cached figures under the sentence saying
// exactly that, which is correct rather than a missing feature.
//
// The fixture is nobody's data: an invented hike name, grid coordinates, no
// account, no location fix (the skill's never-photograph list, kept by
// construction).
export const caption = 'A saved hike, opened from Today'
export const alt =
  'The Today journal with a saved day hike’s card docked to the bottom of the screen over it'

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
            miles: 4.1,
          },
          {
            name: 'Long Path',
            source: 'nynjtc_long_path',
            blaze_color: 'aqua',
            miles: 2.3,
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

  // No tab click: Today is the tab the app opens on (today.mjs's whole
  // premise), and the shelf is on it. Tapping the row from where a hiker
  // actually meets it is the point of this recipe.
  await page.getByRole('button', { name: /Pine Meadow loop/ }).click()
  // The card is up once its legs heading prints - true in every state the
  // figures can be in. The HEADING and not the bare text, for
  // day-hike-card.mjs's reason: once the graph resolves, the figures line
  // reads "6.4 mi · 2 legs" and a bare `getByText('Legs')` matches both,
  // which is a strict-mode violation rather than a wait.
  await page.getByRole('heading', { name: 'Legs' }).waitFor()
}
