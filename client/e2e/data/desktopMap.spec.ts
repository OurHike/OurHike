// The two surfaces that exist only on a laptop AND only with published data —
// the elevation chart across the foot of the map, and the figure that follows
// the pointer over a route being built.
//
// WHY BOTH HALVES ARE NEEDED. e2e/desktopSpine.spec.ts drives the layout forks
// that are pure chrome; these two are behind a second door as well. The chart
// wants `elevation_profile.json` and a trail the hiker has chosen; the hover
// plate wants a routed day-hike draft, which wants the junction graph. Neither
// can be reached on a phone at all — `chrome/MapScreen.tsx` renders the chart
// under `isDesktop` and the plate comes from a hook that answers null without a
// fine pointer — so they are the clearest case in the suite for a second
// project existing.
//
// TAGGED `@desktop`, so the phone project greps them out.
//
// A FINE POINTER IS PART OF THE FIXTURE. `chrome/useRouteHover.ts` checks
// `(pointer: fine)` and gives up otherwise, which is correct — a thumb has no
// hover — and is why playwright.config.ts's desktop project sets
// `isMobile: false, hasTouch: false` rather than only widening the viewport.
// Measured 2026-09-11: that context reports `pointer: fine` true.

import { test, expect, type Page } from '@playwright/test'
// Untyped on purpose: a shot fixture is plain JavaScript, and its shape is the
// app's contract with IndexedDB rather than a type this spec restates.
import { seedLongHike } from '../../preview-shots/fixtures/longHike.mjs'
import { seedPreferences, seedHikerMode, seedCamera } from '../support/seed'
import { expectMapReach } from '../support/layout'
import {
  editTheSavedRoute,
  SAVED_WALK_CENTER,
  SAVED_WALK_ZOOM,
} from '../support/savedWalk'

/** The graph and the profile both arrive over the network, and the drives here
 *  wait on doors rather than timers — but the doors themselves are network
 *  bound. Same constant and same reason as e2e/data/longSpine.spec.ts.
 *
 *  The slowest door here does NOT use this: "Edit the route" waits on the
 *  junction graph resolving a saved walk, and support/savedWalk.ts owns both
 *  that drive and its own larger budget, with the measurement saying why
 *  60_000 was never one. */
const NETWORK_BOUND_MS = 60_000

/** How long the pointer keeps sweeping for the drawn route before giving up.
 *
 *  20_000 rather than the 60_000 this started at, and the cut is the point:
 *  with the camera seeded onto the walk a sweep finds the line on its first
 *  pass (measured: 20 of 289 points raise the plate), so the bound is only
 *  covering a line that draws late. The 60_000 was there to re-sweep the same
 *  coordinates over and over, which `hoverTheRoute` explains was never a
 *  wait on anything. A route that does not draw should fail in seconds. */
const SWEEP_BOUND_MS = 20_000

/** Room for support/savedWalk.ts's GRAPH_READY_MS and SWEEP_BOUND_MS on top of
 *  it, both larger than playwright.config.ts's data-mode per-test ceiling. */
test.describe.configure({ timeout: 300_000 })

test.describe('the elevation chart across the desk', { tag: '@desktop' }, () => {
  test('states: with nothing taken the map keeps its whole height', async ({ page }) => {
    // THE RESTING VIEW IS NOT A CHART OF SOMEBODY ELSE'S TRAIL. App.tsx's
    // `desktopChart` withholds it until a trail is chosen — "the desk's resting
    // view of the whole trail was a picture of a trail nobody had chosen under
    // a Today that said nothing was planned". Asserted first, because a chart
    // that always drew would pass the positive test below and still be wrong.
    await seedPreferences(page)
    await page.goto('/')
    await page.getByRole('tab', { name: 'Map' }).click()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
    await expect(page.getByText(/^No trail taken$/i)).toBeVisible()

    await expect(
      page.getByRole('application', { name: /Elevation profile/ }),
    ).toHaveCount(0)
  })

  test('entrance and states: a hike makes it draw, and it says what it can be used for', async ({
    page,
  }) => {
    // TAKEN BY THE HIKE RATHER THAN BY A TAP (#1352), which is also how
    // preview-shots/network-above-the-seam.mjs reaches the taken state: being
    // on a hike IS choosing its trail, so no legend row has to be pressed.
    await seedPreferences(page)
    await seedHikerMode(page, 'long')
    await page.goto('/')
    await seedLongHike(page)
    await page.getByRole('tab', { name: 'Map' }).click()

    const chart = page.getByRole('application', { name: /Elevation profile/ })
    await expect(chart).toBeVisible({ timeout: NETWORK_BOUND_MS })

    // THE KEYBOARD IS IN THE LABEL, not only in a mouse gesture. A chart whose
    // only way in is a drag is a chart a keyboard cannot read, and the
    // accessible name is where that promise is made.
    await expect(chart).toHaveAccessibleName(/Arrow keys move the cursor/)
    await expect(chart).toHaveAccessibleName(/Escape clears/)

    // The span it covers and the invitation, both in the app's own words. No
    // figure is named: the corridor's length and its extremes move with the
    // release.
    const plot = page.locator('.elevation-chart')
    await expect(plot.getByText(/^mi [\d.,]+ – [\d.,]+$/)).toBeVisible()
    await expect(plot.getByText('Drag to measure a stretch')).toBeVisible()
  })

  test('states: the pointer gets a read-out, and it carries a mile with its height', async ({
    page,
  }) => {
    await seedPreferences(page)
    await seedHikerMode(page, 'long')
    await page.goto('/')
    await seedLongHike(page)
    await page.getByRole('tab', { name: 'Map' }).click()
    const plot = page.locator('.elevation-chart')
    await expect(plot).toBeVisible({ timeout: NETWORK_BOUND_MS })

    // NOTHING BEFORE THE POINTER ARRIVES. The read-out is an answer to a
    // question the hiker asked by pointing, so it must not be sitting there
    // claiming a mile nobody chose.
    await expect(plot.getByText(/^mi [\d.,]+ · [-\d.,]+ ft$/)).toHaveCount(0)

    const box = await plot.boundingBox()
    if (box === null) throw new Error('the chart has no box, so it never mounted')
    await page.mouse.move(box.x + box.width / 2, box.y + box.height * 0.6)

    // BOTH FIGURES OR NEITHER. A height with no mile cannot be checked against
    // the map, and a mile with no height is not why anybody hovered — the
    // read-out is the pair, which is what the shape of this assertion pins.
    await expect(plot.getByText(/^mi [\d.,]+ · [-\d.,]+ ft$/)).toBeVisible()
  })
})

test.describe('the figure that follows the pointer', { tag: '@desktop' }, () => {
  /**
   * Put the camera on the walk, then sweep the frame for the drawn line.
   *
   * THE SWEEP IS NOT THE INTERESTING HALF — THE CAMERA IS, and the first two
   * versions of this helper got that backwards. It swept the frame once and
   * threw; then, when that failed about one run in three, it re-swept the
   * SAME points for 60s and called the re-sweep "waiting on an observable".
   * It was not. Sweeping identical coordinates again is the same lottery
   * ticket drawn twice, and CI drew it four times and lost four times
   * (run 34647748197, both tests, both retries).
   *
   * MEASURED 2026-09-11 against release 2026-09-10, this same 17-by-17 sweep:
   *
   *   the camera the builder opens on   0, 0, 0, and once 1, of 289 points
   *   seeded onto the walk (z14)        20 of 289
   *
   * A 16 px scan of 1,974 points on the builder's own camera found nothing
   * either — so density was never the problem. The builder opens on the
   * corridor rather than on the route it is editing, which draws a 2.9 mi
   * walk as a mark a few tens of pixels long. e2e/support/savedWalk.ts's
   * SAVED_WALK_CENTER carries that arithmetic; whether the app should open
   * there is #1404, not this spec's to assert.
   *
   * Sweeping at all, rather than a fixed coordinate: nothing hands a test the
   * route's screen position, and a hard-coded point would pin a projection
   * rather than the app. The bound is short now because it is guarding
   * against a line that draws late, not buying tickets — a route that never
   * draws should fail in seconds and say so.
   */
  async function hoverTheRoute(page: Page) {
    const box = await page.getByRole('region', { name: 'Trail map' }).boundingBox()
    if (box === null) throw new Error('the map region has no box, so it never mounted')
    const plate = page.locator('.route-hover')
    const deadline = Date.now() + SWEEP_BOUND_MS
    do {
      for (let down = 2; down < 19; down += 1) {
        for (let across = 2; across < 19; across += 1) {
          await page.mouse.move(
            box.x + (box.width * across) / 20,
            box.y + (box.height * down) / 20,
          )
          if ((await plate.count()) > 0) return plate
        }
      }
    } while (Date.now() < deadline)

    // WHERE THE MAP ACTUALLY WAS, read back rather than assumed. App.tsx
    // writes the settled camera to lib/cameraMemory.ts's key on every
    // `moveend`, so if the app moved off the seed this says where it went —
    // and features/FLOW_TESTING.md records a flake in which a seeded camera is
    // not the one the map opens at, about one run in three of another file.
    // Read only on the failure path: asserting it up front would add a second
    // way for this test to go red, and the plate is the observable it is about.
    const landed = await page.evaluate(() => {
      try {
        return sessionStorage.getItem('ourhike:camera')
      } catch {
        return 'unreadable'
      }
    })
    throw new Error(
      'no point on the map raised the hover plate in ' +
        `${SWEEP_BOUND_MS / 1000}s of sweeping. Seeded ` +
        `${JSON.stringify({ center: SAVED_WALK_CENTER, zoom: SAVED_WALK_ZOOM })}; ` +
        `the map settled at ${landed ?? 'nothing written'}. Same camera means ` +
        'the route is not being drawn; a different one means the app moved off ' +
        'the seed and the line is outside the frame this swept',
    )
  }

  test('entrance and states: hovering the route names it and prices it, in the column’s own words', async ({
    page,
  }) => {
    await seedCamera(page, SAVED_WALK_CENTER, SAVED_WALK_ZOOM)
    await editTheSavedRoute(page)

    // Read the column FIRST, so the comparison below is against this run's
    // figures rather than against a number written down here. By its text
    // rather than by a class: which element holds the figure is an
    // implementation detail, and the claim is about what a hiker READS in the
    // column — where the first distance is the route's DISTANCE row.
    const column = page.getByRole('region', { name: 'Your route' })
    const columnText = await column.innerText()
    const distance = /\d[\d.,]*\s*(?:mi|km)\b/.exec(columnText)?.[0]
    expect(
      distance,
      `no distance in the column: ${columnText.slice(0, 120)}`,
    ).toBeTruthy()

    const plate = await hoverTheRoute(page)
    await expect(plate).toBeVisible()

    // NOTHING IS DERIVED ON THE PLATE — RouteHover.tsx: "WHAT IT PRINTS IS
    // WHAT THE COLUMN PRINTS… so hovering the line cannot disagree with
    // reading the column." That is a rule a refactor can quietly break by
    // computing the figure twice, and this is the assertion that would go red.
    await expect(plate).toContainText(distance as string)
  })

  test('states: the plate goes when the pointer leaves the route', async ({ page }) => {
    await seedCamera(page, SAVED_WALK_CENTER, SAVED_WALK_ZOOM)
    await editTheSavedRoute(page)
    const plate = await hoverTheRoute(page)
    await expect(plate).toBeVisible()

    // Off the line and onto the panel beside it. A plate that stayed would be
    // a figure about a route the pointer is no longer on, sitting over a map
    // the hiker is trying to read.
    await page.locator('.day-hike-panel').first().hover()
    await expect(plate).toHaveCount(0)
  })
})
/**
 * R2 ON THE PLANNING SPINE, WHICH NOBODY HAD MEASURED. PATHWAY.md's R2 is
 * "The map never leaves… side by side on a desktop, stacked on a phone", and
 * `e2e/mapRoom.spec.ts` pins it on the map tab and with the legend up. The
 * builders are where it is hardest to keep and easiest to lose, because the
 * column they open is the widest thing in the app — and until now the only
 * evidence either way was a stylesheet read as a string.
 *
 * Measured 2026-09-11 against release 2026-09-10, the identical drive in both
 * projects, with support/layout.ts's probe:
 *
 *   step 2, route builder   phone 8% reachable   laptop 93%
 *   step 3, details         phone 0%             laptop 100%
 *
 * So the phone's builder covers all but a sliver and its review covers the
 * map outright — which is R2's "stacked", working — and the laptop's costs
 * the map essentially nothing. The two floors below are the laptop half of
 * that table with headroom for the chrome, and they are the assertions that
 * would go red if a future column started overlapping the canvas at a width
 * where it did not have to.
 *
 * `@unvalidated` as hiker-facing numbers, exactly as every other floor in
 * this suite is: measurements of today's layout, not findings about how much
 * map a person planning a walk needs to see.
 */
const STEP_TWO_FLOOR = 0.85
const STEP_THREE_FLOOR = 0.9

test.describe('the planning column beside the map', { tag: '@desktop' }, () => {
  test('states: neither builder step costs the map its room, where a phone gives it all up', async ({
    page,
  }) => {
    await editTheSavedRoute(page)
    await expectMapReach(page, STEP_TWO_FLOOR, 'step 2 beside the map on a laptop')

    await page
      .getByRole('button', { name: /Use this route/ })
      .first()
      .click()
    await expect(page.getByRole('button', { name: /^Save/ })).toBeVisible({
      timeout: NETWORK_BOUND_MS,
    })
    await expectMapReach(page, STEP_THREE_FLOOR, 'step 3 beside the map on a laptop')
  })

  test('states: the review announces itself as the walk, which the phone has no room to do', async ({
    page,
  }) => {
    await editTheSavedRoute(page)
    await page
      .getByRole('button', { name: /Use this route/ })
      .first()
      .click()
    await expect(page.getByRole('button', { name: /^Save/ })).toBeVisible({
      timeout: NETWORK_BOUND_MS,
    })

    // THE LANDMARK IS THE FORK. App.tsx docks the review as the rail above the
    // breakpoint (`docked={isDesktop && dayHikeReview !== null}`) and puts it
    // in the bar's slot over the map below it. Docked, it is a REGION NAMED
    // AFTER THE WALK, so somebody arriving by keyboard or screen reader is
    // told which walk this column is about without reading the form.
    //
    // Measured 2026-09-11 on the identical drive, the regions the page
    // exposes:
    //   phone    ["Trail map", "Map"]
    //   laptop   ["Ramapo-Dunderberg to Timp-Torne", "Trail map", "Map"]
    await expect(
      page.getByRole('region', { name: /Ramapo-Dunderberg to Timp-Torne/ }),
    ).toBeVisible()

    // And the map is still a region of its own beside it, rather than
    // something the column has taken over.
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
  })
})
