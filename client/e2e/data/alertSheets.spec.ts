// The two safety sheets a mark on the map is supposed to answer — #1400, and
// the half of F12 that `e2e/data/mapSheets.spec.ts` cannot reach.
//
// WHY THIS IS NOT AN ORDINARY COVERAGE GAP. CLAUDE.md names four ways this app
// can hurt somebody and one of them is "in front of something dangerous".
// `chrome/ClosureSheet.tsx`'s own header says what it is for: "barrier tape
// with no answer invites the guess that the app knows a way round, and this
// exists to say it does not." That path had never been driven end to end, and
// the reason nobody noticed is the reason it could not be driven.
//
// THE REASON, MEASURED. `features/FLOW_TESTING.md` recorded these as a
// needle-in-a-haystack problem — "a closure is one pin rather than a line
// across the frame". It is not that. Measured against UA on 2026-09-11 and
// re-checked 2026-09-15, `conditions/closures.json` carries **0** closures and
// `conditions/reports.json` carries **0** reports. There is no needle in the
// haystack; there is no needle, and no camera derived from any mile would find
// one.
//
// SO THIS ASSERTS THE SHEET AND NOT THE DATA, LOUDLY. Both artifacts are
// replaced with `page.route` — #1400's option 3, and the move
// `e2e/data/newerData.spec.ts` already makes to simulate a publish. Nothing
// here is evidence that UA carries a closure, that a closure exists, or that
// the pipeline bakes one correctly. What it is evidence of is that a tapped
// mark opens the sheet built for it, that the sheet says what it is, and that
// one safety claim replaces another rather than stacking on it. Option 1 —
// wait for a real closure — remains the right answer for the MARKS, and #1400
// keeps that half.
//
// WHY THE FIXTURES CARRY NO MILE. `lib/closureProjection.ts` re-reads a
// closure's miles from its `start_lat`/`start_lon` pair against whichever
// release this phone holds, and `lib/seriousWarnings.ts`'s `placeAll` snaps a
// report's fix the same way — both through `mileOnTrail`, both tolerant to
// `MAX_OFF_TRAIL_MILES` (3). So every fixture below is positioned in LAT/LON
// at the camera this suite already seeds, and the app computes the miles. A
// hard-coded mile would be this file naming a number off one release, which is
// the thing `mapSheets.spec.ts` refuses to do for shelters and counts.
//
// RUNNING IT BY HAND IN THE SANDBOX, AND THE TRAP THAT COSTS AN HOUR. The
// data half needs `scripts/data-proxy.mjs`, and the build it serves must carry
// the proxy's own base:
//
//     VITE_DATA_BASE_URL=/data/environments/ua npm run build
//     node scripts/data-proxy.mjs dist 8787
//     FLOW_DATA=1 FLOW_DATA_ORIGIN=http://localhost:8787 npx playwright test \
//       e2e/data/alertSheets.spec.ts --project=phone
//
// `scripts/test.sh` REBUILDS `dist` WITHOUT THAT VARIABLE on its way past the
// hermetic half, so a run after it serves an app pointed at a bucket the
// sandbox's browser cannot reach - no trail, no marks, and every test here
// fails with "swept the whole frame and never opened", which reads exactly
// like the marks not drawing. Rebuild before re-running. CI never meets this:
// the runner reaches the bucket itself.
//
// A NEW FILE RATHER THAN MORE TESTS IN mapSheets.spec.ts, deliberately: that
// file is being rewritten for #1443 on another branch, and BRANCHING.md §2 is
// about not slicing two changes through one file. The sweep below is therefore
// a near-cousin of `tapTheTrail`'s rather than a shared helper — extracting one
// would have meant editing that file, which is the thing being avoided.

import { test, expect, type Page, type Locator } from '@playwright/test'
import {
  seedPreferences,
  seedCamera,
  ON_THE_TRAIL,
  ABOVE_THE_SEAM_ZOOM,
} from '../support/seed'

/** `lib/publishedConditions.ts`'s two keys — the wire contract this spec
 *  intercepts, not modules it imports, for the reason support/seed.ts gives
 *  about its own keys. */
const CLOSURES_KEY = 'conditions/closures.json'
const REPORTS_KEY = 'conditions/reports.json'

/**
 * How long a mark is allowed to take to arrive, swept for throughout.
 *
 * Same order as mapSheets.spec.ts's SKETCHES_BOUND_MS and for the same
 * underlying reason - the artifacts are large and the sandbox reads them
 * through a proxy - but spent sweeping rather than waiting, so the budget is
 * also the assertion. A mark that never draws fails here saying how many full
 * passes of the frame found nothing, which is a more useful failure than a
 * timeout on a legend section this file does not otherwise care about.
 *
 * 90 s RATHER THAN 120, AND THE TEST BUDGET IS 300 RATHER THAN 180, because
 * the last test sweeps TWICE. At 120 s inside a 180 s test the second sweep
 * could never reach its own deadline: Playwright would kill the test first
 * and report a timeout, throwing away the count-of-passes message that says
 * what actually went wrong. Two 90 s sweeps and their overhead fit inside 300
 * with room, so a failure here is always the informative one. Measured: a
 * mark that IS drawn is found in the first pass, in about 20 s.
 */
const MARKS_BOUND_MS = 90_000

/** Room for two full sweeps and their boot - see MARKS_BOUND_MS. */
test.describe.configure({ timeout: 300_000 })

/**
 * A point on the A.T. `metres` north-east of the camera's centre.
 *
 * Only ever used to make two marks land in DIFFERENT places, never to claim a
 * position: what this controls is "somewhere else, still in frame", not a
 * coordinate.
 *
 * HOW BIG THE FRAME ACTUALLY IS, measured rather than derived, because the
 * derivation was wrong and cost an afternoon. At this camera the app's own
 * scale bar reads 2,000 ft across about 100 CSS px, so roughly 6 m/px - and
 * the map region is 390x772, which makes the visible ground about
 * **2.4 km by 4.7 km**. A first attempt put the warning 2 km north-east, which
 * is outside the 1.2 km half-width: the pin was never drawn on screen at all
 * and the sweep's failure read as "the pin does not draw". Everything here
 * stays inside a few hundred metres.
 */
function nearTheCamera(metres: number): { lat: number; lon: number } {
  const [lon, lat] = ON_THE_TRAIL
  const degrees = metres / 111_320
  return { lat: lat + degrees, lon: lon + degrees / Math.cos((lat * Math.PI) / 180) }
}

function closuresDocument(closures: readonly unknown[]): string {
  return JSON.stringify({ generated_at: new Date().toISOString(), closures })
}

function reportsDocument(reports: readonly unknown[]): string {
  return JSON.stringify({ generated_at: new Date().toISOString(), reports })
}

/**
 * One closed stretch, spanning the camera's centre.
 *
 * `status: 'closed'` because `map/closureLayers.ts`'s `closureBands` drops an
 * `open` one, and the two ends are half a kilometre apart because the same
 * function drops anything spanning more than `MAX_BAND_MILES` (50) as a broad
 * advisory. Both of those are the app's rules, not this file's, and a fixture
 * that broke either would draw nothing and read as "tapping tape is broken".
 *
 * It runs NORTH-EAST of the camera centre while the warning sits south-west of
 * it, so the two marks never overlap and each sweep finds its own.
 */
const A_CLOSED_STRETCH = {
  id: 'fixture-closure',
  reason_type: 'storm_damage',
  note: 'A fixture, intercepted by e2e/data/alertSheets.spec.ts. Not published.',
  status: 'closed',
  // Ignored: closureProjection re-reads both from the geometry below.
  start_mile_marker: 0,
  end_mile_marker: 0,
  start_lat: nearTheCamera(0).lat,
  start_lon: nearTheCamera(0).lon,
  end_lat: nearTheCamera(600).lat,
  end_lon: nearTheCamera(600).lon,
}

/**
 * One escalated report, which is what a serious-warning pin is.
 *
 * `severity: 'serious'` is the whole of what makes it a pin —
 * `lib/seriousWarnings.ts`'s `isSeriousWarning` — and `verified_at` is the
 * moderator's stamp the sheet prints. Unlike the closure it is drawn at its
 * RAW lat/lon rather than snapped (`warningPins` in App.tsx: "a pin goes where
 * the report was written"), so it needs no trail under it — only the frame.
 *
 * Placed a few hundred metres off the closure's own end so neither mark
 * shadows the other: `map/closureLayers.ts`'s tap handler yields to a warning
 * pin before it reads the tape, and `map/atcUpdateLayers.ts`'s yields to both,
 * which is correct and would otherwise make one of these sweeps look broken.
 */
const AN_ESCALATED_REPORT = {
  id: 'fixture-warning',
  type: 'hazard',
  reporter_type: 'hiker',
  status: 'verified',
  severity: 'serious',
  lat: nearTheCamera(-500).lat,
  lon: nearTheCamera(-500).lon,
  mile: null,
  poi_id: null,
  note: 'A fixture, intercepted by e2e/data/alertSheets.spec.ts. Not published.',
  timestamp: new Date().toISOString(),
  verified_at: new Date().toISOString(),
}

/**
 * Serve these two artifacts instead of the bucket's, before anything boots.
 *
 * Every other artifact is left alone: the map still draws the real release's
 * trail lines, and it has to, because the marks are positioned against them.
 * That is the difference from newerData.spec.ts, which aborts the trail
 * artifacts outright — it is asserting a release comparison and does not care
 * what is drawn behind it, and this file cares about nothing else.
 */
async function serveConditions(
  page: Page,
  {
    closures = [],
    reports = [],
  }: { closures?: readonly unknown[]; reports?: readonly unknown[] },
): Promise<void> {
  await page.route(`**/${CLOSURES_KEY}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: closuresDocument(closures),
    }),
  )
  await page.route(`**/${REPORTS_KEY}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: reportsDocument(reports),
    }),
  )
}

/**
 * The same camera mapSheets.spec.ts seeds, and NO separate wait for the map.
 *
 * That file opens the legend first and waits for its "Trails in view" section,
 * because the thing it taps is a drawn trail SKETCH and the section is the
 * app's own statement that the sketches landed. This file taps neither. A
 * closure band and a warning pin are placed against the CENTERLINE INDEX -
 * `closureBands` and `placeAll` both go through `mileOnTrail` - which is a
 * different artifact arriving on a different clock, and the legend says
 * nothing about it. Measured here 2026-09-15: waiting on "Trails in view"
 * failed all four tests at 90 s while the marks themselves were already in the
 * legend's key, so it was waiting on the wrong thing and calling the wait a
 * failure.
 *
 * The legend's Closure and Serious warning rows are NOT the signal either,
 * which is worth writing down because they look like one: `withSafetyKey`
 * appends them "carrying no count at all", so they render on a phone holding
 * no closures whatsoever.
 *
 * So the sweep below does the waiting, against a deadline, and the sheet
 * OPENING is the observable that proves the sequence completed - which is what
 * CLAUDE.md asks for and is strictly better than a proxy for it.
 */
async function openMapOnTheTrail(page: Page): Promise<void> {
  await seedCamera(page, ON_THE_TRAIL, ABOVE_THE_SEAM_ZOOM)
  await seedPreferences(page)
  await page.goto('/')
  await page.getByRole('tab', { name: 'Map' }).click()
  await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
}

/** Clears the header's floating pills, which a tap meant for the canvas would
 *  otherwise hit — mapSheets.spec.ts's HEADER_ROWS, and its hour. */
// The sweep below runs to the twentieth row rather than mapSheets.spec.ts's
// eighteenth, and that is not a style difference: the map region measures
// 390x772 here, not 390x844 - the tab bar and the credits strip sit outside it -
// and the fixture warning pin landed at y=716, which is row 18.5. Stopping at
// 18 put the pin below the last row swept, and the failure read as "the pin is
// not drawn". The columns are a twentieth apart for the same reason: the pin is
// 44 px with a 22 px tap slop, and a 78 px column spacing steps over it.
const HEADER_ROWS = 7

async function frameOf(
  page: Page,
): Promise<{ x: number; y: number; width: number; height: number }> {
  const box = await page.getByRole('region', { name: 'Trail map' }).boundingBox()
  if (box === null) throw new Error('the map region has no box, so it never mounted')
  return box
}

/**
 * Sweep the frame until the named sheet opens, the way a finger does.
 *
 * A FIXED COORDINATE WOULD BE PINNING A PROJECTION. Where a mark lands on the
 * canvas is a function of the release's geometry, the seeded camera and
 * MapLibre's own fit; the map object is deliberately not on `window`, so
 * `queryRenderedFeatures` is not available from out here. Same reasoning, and
 * the same shape, as mapSheets.spec.ts's `tapTheTrail`.
 *
 * WHAT IT HAS TO STEP OVER. A tap landing on a waypoint pin opens a card that
 * then covers the canvas, so every later tap would hit the card and the sweep
 * would run out having tested nothing; a tap on the trail itself opens the line
 * sheet the same way. Both are closed and the sweep carries on — they are
 * exactly what this camera is looking at, so meeting them is expected rather
 * than a failure.
 */
interface Swept {
  sheet: Locator
  /** Where the tap that opened it landed, in page coordinates. Stable for as
   *  long as the camera does not move, which is what lets the stacking test
   *  re-tap a mark without sweeping over an open sheet. */
  at: { x: number; y: number }
}

async function sweepFor(page: Page, sheetName: string): Promise<Swept> {
  const box = await frameOf(page)
  const wanted = page.getByRole('dialog', { name: sheetName })
  /**
   * Close whatever else a tap opened, whichever sheet it was.
   *
   * ENUMERATING THE BLOCKERS DOES NOT WORK, which is worth recording because
   * it was the first thing tried. The list looked short - a waypoint card, a
   * trail-line sheet - and the sheet that actually stopped the sweep was
   * neither: "Appalachian Trail Conservancy trail update", raised by the notice
   * bands, of which the live UA bucket carries 56 along this very stretch. It
   * opened on the FIRST tap, stayed up, and every one of the next two thousand
   * taps hit the sheet rather than the canvas - which reads as "the pin is not
   * drawn" and is not.
   *
   * So anything that is not the sheet being swept for is closed by its own
   * close button. Escape does not do it: measured 2026-09-15, the notice sheet
   * was still open after one.
   */
  const clearOthers = async (): Promise<void> => {
    const open = page.getByRole('dialog')
    for (let index = (await open.count()) - 1; index >= 0; index -= 1) {
      const dialog = open.nth(index)
      if ((await dialog.getAttribute('aria-label')) === sheetName) continue
      const close = dialog.getByRole('button', { name: /^Close/ }).first()
      if ((await close.count()) > 0) await close.click()
    }
    // WAIT FOR IT TO ACTUALLY GO, then say what it was if it did not.
    //
    // The wait is load-bearing and was learned the hard way: clicking Close
    // and reading `count()` straight afterwards returns 0 before React has
    // re-rendered, so the sweep carried on tapping into a sheet that was
    // still up and found nothing at all - "never opened", on a mark that was
    // drawn. Two seconds rather than the 30-second default, so a dialog that
    // genuinely cannot be closed costs one tap's worth of time instead of
    // half the budget, and is then named rather than left as a bare count.
    try {
      await expect(page.getByRole('dialog')).toHaveCount(0, { timeout: 2_000 })
    } catch {
      const stuck = await page.getByRole('dialog').first().getAttribute('aria-label')
      throw new Error(
        `the sweep cannot close "${stuck}", so it can never reach the canvas again`,
      )
    }
  }

  let landed: { x: number; y: number } | null = null

  const tap = async (across: number, down: number): Promise<boolean> => {
    const at = {
      x: box.x + (box.width * across) / 20,
      y: box.y + (box.height * down) / 20,
    }
    await page.mouse.click(at.x, at.y)
    if ((await wanted.count()) > 0) {
      landed = at
      return true
    }
    if ((await page.getByRole('dialog').count()) > 0) await clearOthers()
    return false
  }

  // SWEEP UNTIL THE DEADLINE, NOT ONCE. The marks are drawn when the
  // centerline index lands, and a sweep that starts before it has nothing to
  // hit; re-sweeping is how this waits on the mark itself rather than on a
  // proxy for it. Each pass is ~60 taps and takes a few seconds, so this is
  // tens of attempts rather than a busy loop.
  const deadline = Date.now() + MARKS_BOUND_MS
  let passes = 0
  do {
    passes += 1
    for (const step of [2, 1]) {
      for (let down = HEADER_ROWS; down <= 19; down += step) {
        for (let across = 1; across <= 19; across += step) {
          if (await tap(across, down)) return { sheet: wanted, at: landed! }
        }
      }
    }
  } while (Date.now() < deadline)
  throw new Error(
    `swept the whole frame ${passes} time(s) over ${MARKS_BOUND_MS} ms and never opened "${sheetName}"`,
  )
}

test.describe('the sheet behind a closure band', () => {
  test('entrance: tapping the tape opens the closure sheet, which says what is closed and why', async ({
    page,
  }) => {
    await serveConditions(page, { closures: [A_CLOSED_STRETCH] })
    await openMapOnTheTrail(page)

    const { sheet } = await sweepFor(page, 'Trail closure')

    // The reason, in the app's own words for `storm_damage` — not the wire
    // value, which a hiker never sees.
    await expect(sheet).toContainText(/storm/i)
    // ClosureSheet's limit note, the sentence the whole sheet exists for: it
    // says what this app does NOT know, rather than implying a way round.
    await expect(sheet.getByRole('note')).toBeVisible()
  })

  test('exit: closing it leaves the map behind it, with nothing else opened', async ({
    page,
  }) => {
    await serveConditions(page, { closures: [A_CLOSED_STRETCH] })
    await openMapOnTheTrail(page)

    const { sheet } = await sweepFor(page, 'Trail closure')
    await sheet.getByRole('button', { name: /^Close$/ }).click()

    await expect(page.getByRole('dialog', { name: 'Trail closure' })).toHaveCount(0)
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
  })
})

test.describe('the sheet behind a serious-warning pin', () => {
  test('entrance: tapping the pin opens the warning sheet, which names itself as serious', async ({
    page,
  }) => {
    await serveConditions(page, { reports: [AN_ESCALATED_REPORT] })
    await openMapOnTheTrail(page)

    const { sheet } = await sweepFor(page, 'Serious warning')

    await expect(sheet).toContainText('Serious warning')
    await expect(sheet.getByRole('note')).toBeVisible()
  })
})

test.describe('two safety claims at once', () => {
  test('states: a warning opened over a closure REPLACES it, rather than stacking on it', async ({
    page,
  }) => {
    // alertSheetsPanel's stated rule, and the reason for it: "two safety
    // sheets stacked is two claims a hiker has to reconcile with a thumb."
    //
    // IT CANNOT BE TWO SWEEPS, which is what this test was until review
    // caught it. `sweepFor`'s own `clearOthers` closes any sheet that is not
    // the one being swept for, so sweeping for the warning with the closure
    // sheet open closes the closure ON THE FIRST TAP - and the final
    // "the closure is gone" then passed whether the panel replaced it or
    // stacked on it. A test that cannot fail is worse than no test, and this
    // one was carrying a `covered` row for `alertSheetsPanel.tsx`.
    //
    // So: find the warning by sweeping, note where it is, close it, open the
    // closure, and then tap the warning's own point ONCE. Nothing clears
    // anything between that tap and the assertion, so the closure is gone
    // only if the panel closed it.
    await serveConditions(page, {
      closures: [A_CLOSED_STRETCH],
      reports: [AN_ESCALATED_REPORT],
    })
    await openMapOnTheTrail(page)

    const warning = await sweepFor(page, 'Serious warning')
    await warning.sheet.getByRole('button', { name: /^Close$/ }).click()
    await expect(page.getByRole('dialog', { name: 'Serious warning' })).toHaveCount(0)

    const closure = await sweepFor(page, 'Trail closure')
    await expect(page.getByRole('dialog', { name: 'Trail closure' })).toHaveCount(1)

    // The pin has to still be reachable with the closure's sheet up, or the
    // tap below would land on the sheet and this would be vacuous a second
    // way. Asserted rather than assumed, and loudly, because a fixture moved
    // under a bottom sheet is a fixture problem and not a finding about the
    // app.
    const sheetBox = await closure.sheet.boundingBox()
    if (sheetBox !== null && warning.at.y >= sheetBox.y) {
      throw new Error(
        `the warning pin at y=${warning.at.y} is under the closure sheet (y=${sheetBox.y}), ` +
          'so this test cannot tap it - move the fixture, do not weaken the assertion',
      )
    }

    await page.mouse.click(warning.at.x, warning.at.y)

    await expect(page.getByRole('dialog', { name: 'Serious warning' })).toHaveCount(1)
    await expect(page.getByRole('dialog', { name: 'Trail closure' })).toHaveCount(0)
  })
})
