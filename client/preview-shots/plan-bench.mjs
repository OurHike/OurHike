// The plan bench on a laptop (#971, WIREFRAMES.md frame 3a) — the Plan tab's
// wide layout and the one gesture it exists for.
//
// WHAT TO LOOK FOR, because the point of this frame is a COMPOSITION and a
// composition is easy to skim past:
//
//   1. THREE PANES, not one column widened. The tree on the left (the hike,
//      the trip, its resupply sections), the timeline on the right, and the
//      day rows in it. There is no middle pane in this shot and that is
//      correct rather than missing — the map is a slot the app shell fills,
//      and the preview build's Plan tab has no map to lend it, so the bench
//      draws two panes instead of a framed empty box. Wiring the third is
//      one prop in App.tsx and is named in the pull request.
//   2. THE SELECTION, read back on the strip below the panes — "Day 2 · Lost
//      Mountain Shelter → Thomas Knob Shelter" — with the way to that day's
//      actions beside it. The picked row and the picked section both carry a
//      four-pixel blaze-orange inside edge; that is one selection marked in
//      two panes, and in the third when the shell lends a map.
//   3. THE STRIP BENEATH THEM, which is where the whole section's elevation
//      goes: the chart rests on the plan's own miles rather than the phone's
//      ten-mile window, with the plan's day boundaries drawn on it — solid
//      where one may be dragged, dashed and dimmed where it may not.
//
// TWO TRUE FRAMES, and which one this is depends on whether the build has a
// data source. Measured in the sandbox on 2026-08-27, against a local
// `npm run build` with no VITE_DATA_BASE_URL: the strip prints the refusal —
// "This download has no elevation profile, so there is nothing to drag a day
// boundary along" — because the profile is an artifact of the release and
// there is no release to read. That frame is worth having: it is what a fork's
// pull request and an old download both look like, and the screen says which
// absence it is rather than drawing an empty axis.
//
// With a data source — which pr-preview.yml supplies for a branch on this
// repository — the chart is there and the boundaries are on it, which is the
// frame this recipe is really for. A SESSION IN THE SANDBOX CANNOT VERIFY
// THAT ONE: Chromium there reaches no external host, so the only build it can
// photograph is the dataless one. If the CI frame still shows the refusal
// line, that is a finding about the preview's data source (#1024, #1093) and
// not about this screen.
//
// The drag itself is a pointer gesture and does not photograph. It is
// exercised in screens/Plan.test.tsx and chrome/ElevationChart.test.tsx
// instead; what a picture can honestly carry is that the handles are there
// and which of them are live.
//
// Fixtures are nobody's data: real A.T. place names off the published
// centerline, no account, no location fix, no campsite anywhere near a
// readable zoom (the skill's never-photograph list, kept by construction —
// this screen draws no map at all).

export const caption =
  'The plan bench — three panes, one selection, boundaries on the chart'
export const alt =
  'The Plan tab on a wide screen: a section tree on the left, a day timeline on the right, and the whole section’s elevation profile pinned beneath them with the plan’s day boundaries drawn on it'

// The wide layout, not the phone. Above desktop.css's 900px breakpoint, which
// is the only width at which any of this exists.
export const desktop = true

const DAY = (id, date) => ({ id, date, pinned: false, generated: true })

/**
 * Damascus → Atkins, three walking days and no zero.
 *
 * NO ZERO, deliberately: a zero's two boundaries sit on the same mile, and
 * lib/planBench.ts fixes both of them (a hiker cannot see which of two
 * coincident lines they are taking, and moving either turns a rest day into a
 * walking day). A fixture with one in it would photograph a chart whose
 * middle handles were all dashed, which is the opposite of what this frame is
 * evidence for.
 */
const TRIPS = {
  trips: [
    {
      id: 'preview-fixture-bench',
      name: 'Damascus → Atkins',
      plan: {
        target: { walkingHours: 7 },
        stops: [
          { mile: 470.8, name: 'Damascus', resupply: true },
          { mile: 486.2, name: 'Lost Mountain Shelter', resupply: false },
          { mile: 503.3, name: 'Thomas Knob Shelter', resupply: false },
          { mile: 516.1, name: 'Atkins', resupply: true },
        ],
        days: [
          DAY('preview-bench-1', '2026-05-12'),
          DAY('preview-bench-2', '2026-05-13'),
          DAY('preview-bench-3', '2026-05-14'),
        ],
      },
    },
  ],
  openId: 'preview-fixture-bench',
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
  // the app wakes up owning the fixture, exactly as a laptop reopening would.
  await page.reload({ waitUntil: 'load' })

  await page.getByRole('tab', { name: 'Plan' }).click()
  // One trip and nothing else opens straight onto its timeline rather than
  // the home.
  await page.getByText('Damascus → Lost Mountain Shelter').first().waitFor()

  // Pick a day, because an unselected bench photographs its own invitation
  // rather than the thing it invites. This is the middle day, so the caption
  // reads a stretch with a boundary either side of it on the chart.
  await page.getByText('Lost Mountain Shelter → Thomas Knob Shelter').first().click()
  await page.getByRole('button', { name: 'Day actions…' }).waitFor()
}
