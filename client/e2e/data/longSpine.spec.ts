// The long hike's own spine — F3 and F4 for the builder a section hiker uses,
// driven BY NAME rather than by a tap on the canvas.
//
// WHY THIS ONE CAN BE DRIVEN WHERE THE DAY BUILDER CANNOT. The day-hike
// builder starts with a tap on tread and nothing in the suite can aim one
// (features/FLOW_TESTING.md carries that measurement, under #1387). The A.T.
// builder's entrance offers a stop by NAME — a field over the published
// waypoints — so the whole spine is reachable through controls, which is also
// how preview-shots/plan-step-3.mjs photographs it.
//
// It needs the waypoint index, so it lives here rather than in the hermetic
// half: every stop the picker can offer is a published POI carrying a
// published mile.
//
// WHAT IS ASSERTED, AND WHAT IS NOT. No mileage, day count or stop name is
// written down — the release owns those. What is pinned is the shape of each
// screen and, above all, WHICH SENTENCE the entrance shows, because that is
// where this file found a defect.

import { test, expect, type Page, type Locator } from '@playwright/test'
// Untyped on purpose: a shot fixture is plain JavaScript, and its shape is the
// app's contract with IndexedDB rather than a type this spec should restate.
import { seedLongHike } from '../../preview-shots/fixtures/longHike.mjs'
import { seedPreferences, seedHikerMode } from '../support/seed'

const ENTRANCE = { name: 'Plan a route' }

/**
 * How long a step that waits on the network may take.
 *
 * Every wait in this file is either instant (a render) or bounded by a fetch
 * of graph cells, and the two must not share a number: the config's 30-second
 * expect timeout is generous for a render and not always enough for a cell
 * fetch under two workers. Measured 2026-09-11: the whole spine drives in
 * 20-35 seconds with the machine to itself, and the failures that sent this
 * constant up were a cluster of two runs in eight, all of them on the steps
 * that wait for a stretch to resolve.
 */
const NETWORK_BOUND_MS = 60_000

/**
 * This file's own test budget, above the 90 seconds playwright.config.ts
 * gives the data suite.
 *
 * These drives are the longest in the suite: boot, seed, the entrance
 * waiting on the stop index, a search over it, then a stretch resolved
 * against graph cells — four network-bound steps in one test, where every
 * other spec here has one or two. Measured 2026-09-11: 20 to 35 seconds with
 * the machine to itself, and past 90 under two workers, where the failure
 * reads as an inner wait timing out when what actually ran out was the
 * test's whole budget. Raised so the two cannot be confused: no single wait
 * here may exceed NETWORK_BOUND_MS, and the test has room for all four.
 */
test.describe.configure({ timeout: 240_000 })
const REFUSAL = /predates trail miles on waypoints/

/** Long mode, past first run, with the fixture hike in the store. */
async function planALongHike(page: Page): Promise<void> {
  await seedPreferences(page)
  await seedHikerMode(page, 'long')
  await page.goto('/')
  await seedLongHike(page)
  await page
    .getByRole('group', { name: 'Find or plan a hike' })
    .getByRole('button', { name: 'Plan a hike' })
    .click()
  await expect(
    page.getByRole('heading', { name: 'Where do you want to go?' }),
  ).toBeVisible()
}

/**
 * Open the entrance, and wait for the stops rather than for a timer.
 *
 * WHAT THIS WAITS ON, AND WHY IT IS THE RIGHT THING. The search door
 * ("Shelter, town, or 'mi 500'") renders only in the branch chrome/
 * RouteEntranceSheet.tsx takes when it has stops to offer — so its presence
 * IS "the published waypoints are on the phone", said by the screen under
 * test, in the one place that matters to the drive.
 *
 * THE FIRST VERSION WAITED ON THE MAP'S "In view" DOOR and was wrong in a way
 * that took eight runs to show: that door is gated on what the map is DRAWING
 * (`pointsShown.length > 0`), not on what the phone holds, so with a long
 * hike seeded the camera opens on the whole trail, below the pin seam, and
 * the door is legitimately absent however long you wait. It passed whenever
 * the camera happened to sit somewhere pins draw. A wait on the wrong
 * observable is a flake with a plausible explanation attached, which is worse
 * than no wait at all.
 */
async function openTheEntrance(page: Page): Promise<Locator> {
  await page.getByRole('button', { name: 'Pick on the map' }).click()
  const sheet = page.getByRole('dialog', ENTRANCE)
  await expect(sheet).toBeVisible()
  await expect(sheet.getByRole('button', { name: /Shelter, town, or/ })).toBeVisible({
    timeout: NETWORK_BOUND_MS,
  })
  return sheet
}

test.describe('the route builder’s entrance', () => {
  test('states: with the stops on the phone it asks where from, and offers three ways to answer', async ({
    page,
  }) => {
    await planALongHike(page)
    const sheet = await openTheEntrance(page)

    await expect(sheet).toContainText('Where from?')
    // THREE WAYS TO NAME A START, which is the shape #801 rebuilt this into
    // after a row of three small words "was missed outright in a walkthrough".
    await expect(sheet.getByText('Where I am')).toBeVisible()
    await expect(sheet.getByText('Pick on the map')).toBeVisible()
    await expect(sheet.getByText(/Shelter, town, or/)).toBeVisible()
    // And the end as OPTIONAL, with "how far" offered instead — a section
    // hiker often knows how long they have rather than where they stop.
    await expect(sheet).toContainText(/END — optional/i)
    await expect(sheet.getByRole('button', { name: 'Use this stretch' })).toBeVisible()

    await expect(sheet.getByText(REFUSAL)).toHaveCount(0)
  })

  test('states: with no waypoints at all it does not blame the download', async ({
    page,
  }) => {
    // THE DEFECT THIS FILE FOUND, driven in the one state that reproduces it
    // deterministically: no waypoints on the phone at all — the "absent" case
    // features/FLOW_TESTING.md's data-freshness axis asks every screen to be
    // driven in.
    //
    // `refused` was `routeStopChoices.length === 0`, which is true when no
    // published stop carries a mile and ALSO true when there are no published
    // stops yet. In that second case the sheet said something definite and
    // wrong about the hiker's data: "This download predates trail miles on
    // waypoints… Newer trail data carries them." It named the download, and
    // handed over a remedy that was not the hiker's to take.
    //
    // WHAT WAS MEASURED, 2026-09-11 against release 2026-09-10 through the
    // local proxy: opening the builder straight after boot showed the
    // refusal, and the same sheet left alone had recovered twenty seconds
    // later — so on a real phone it is a race with the fetch, and the slower
    // the connection the longer a hiker is told their data is too old. A race
    // is not something a flow test should chase (driving it by timing passed
    // with the defect in place, which is the worst kind of test), so the
    // request is refused outright instead. Same condition, no stopwatch.
    await page.route('**/poi_*.geojson', (route) => route.abort())
    await planALongHike(page)
    await page.getByRole('button', { name: 'Pick on the map' }).click()

    const sheet = page.getByRole('dialog', ENTRANCE)
    await expect(sheet).toBeVisible()
    await expect(sheet.getByText(REFUSAL)).toHaveCount(0)
    // The fields instead, which are the honest state: a map tap needs no
    // index, and the rest fill themselves in if one lands.
    await expect(sheet.getByText('Pick on the map')).toBeVisible()
    // No cross-check on the map's "In view" door, deliberately: that door is
    // gated on what the map is DRAWING rather than on what the phone holds,
    // so its absence would prove nothing here. The aborted request is the
    // proof, and it is proof by construction.
  })

  test('exit: the sheet closes on its own close, leaving step 1', async ({ page }) => {
    await planALongHike(page)
    await page.getByRole('button', { name: 'Pick on the map' }).click()
    const sheet = page.getByRole('dialog', ENTRANCE)
    await expect(sheet).toBeVisible()

    await sheet.getByRole('button', { name: /Close the route builder/ }).click()

    await expect(page.getByRole('dialog', ENTRANCE)).toHaveCount(0)
  })
})

/**
 * A start named in the picker, which is the door that makes this spine
 * drivable at all.
 *
 * NOT `{ name: /Start/ }`, which is what preview-shots/plan-step-3.mjs
 * reaches for: "START" is a LABEL over three options, and the options are
 * the buttons. That recipe guards every step with `.catch(() => {})` and
 * returns early, so it has been photographing the entrance sheet under a
 * caption that hedges for exactly this ("or, where the drive could not name
 * a start, the stop picker or the entrance sheet asking where from") — no
 * false claim published, and no step 3 photographed either. Fixed in the
 * same change as this spec.
 */
async function nameAStart(page: Page, stop: string): Promise<void> {
  const sheet = page.getByRole('dialog', ENTRANCE)
  await sheet
    .getByRole('button', { name: /Shelter, town, or/ })
    .first()
    .click()
  const search = page.getByLabel('Search for a stop')
  await search.waitFor({ timeout: NETWORK_BOUND_MS })
  await search.fill(stop)
  const hit = page.getByRole('button', { name: new RegExp(stop) }).first()
  await hit.waitFor({ timeout: NETWORK_BOUND_MS })
  await hit.click()
}

/** Step 2 of the long spine, with a stretch in it. */
async function aStretchInTheBuilder(page: Page): Promise<void> {
  await planALongHike(page)
  await openTheEntrance(page)
  await nameAStart(page, 'Fingerboard Shelter')
  const use = page.getByRole('button', { name: 'Use this stretch' })
  await use.waitFor({ timeout: NETWORK_BOUND_MS })
  await use.click()
  // WAIT ON THE ROUTE, NOT ON THE BUTTON. "Use this route ›" is rendered
  // from the draft's two ends, which exist the moment the stretch is taken;
  // the FIGURES come from resolving that stretch against graph cells fetched
  // over the network, and every assertion below is about a resolved route.
  // Waiting on the button let the tests run against a panel whose numbers
  // had not arrived — two runs in eight failed that way, in a cluster, which
  // is what a race looks like from the outside (CLAUDE.md's ordering rule).
  await expect(page.getByText(/ft ↑ · [\d,]+ ft ↓/)).toBeVisible({
    timeout: NETWORK_BOUND_MS,
  })
  await expect(page.getByRole('button', { name: /Use this route/ })).toBeVisible()
}

test.describe('the route, as a list of stops', () => {
  test('states: every leg carries climb AND descent, and the total says it is walking', async ({
    page,
  }) => {
    // BOTH NUMBERS OR NEITHER (#973). RouteStopsPanel printed only the climb
    // for its whole life while `legFigures` computed the descent and threw it
    // away — and the descent is the half a hiker's knees are asking about,
    // the half Naismith gives no credit for, so a leg that reads easy on time
    // can still be the one that hurts.
    await aStretchInTheBuilder(page)

    await expect(page.getByText(/[\d,]+ ft ↑ · [\d,]+ ft ↓/)).toBeVisible()
    // AND "WALKING" ON THE TOTAL, which is the word that keeps the figure
    // honest: Naismith knows nothing about lunch, water, or forty minutes at
    // a shelter. A bare "≈18h 10m" would read as when you arrive.
    await expect(page.getByText(/≈.+ walking/)).toBeVisible()
    // The ≈, which is the other half of the same promise.
    await expect(page.getByText(/≈/).first()).toBeVisible()
  })

  test('states: the panel names the boundary it will not route across', async ({
    page,
  }) => {
    // A missing capability the app NAMES reads as a boundary; one it is
    // silent about reads as a bug — the same argument chrome/DayHikePickBar
    // makes for roads, here for everything that is not the centerline.
    await aStretchInTheBuilder(page)

    await expect(
      page.getByText(/Only the A\.T\. centerline can carry a route/),
    ).toBeVisible()
    await expect(
      page.getByText(
        /Side trails, alternates and the road walks into town aren’t routable yet/,
      ),
    ).toBeVisible()
    // The two stops as fields, and the way to put one between them — the
    // anatomy #755 chose so the route reads as a sequence a hiker can edit.
    await expect(
      page.getByRole('button', { name: /Add a stop on the way/ }),
    ).toBeVisible()
  })

  test('exit: the rail leaves step 2 with the stretch behind it', async ({ page }) => {
    await aStretchInTheBuilder(page)

    // Labelled for where it GOES rather than with a bare chevron, which is
    // the rail's rule and the reason to ask for it by that name: the visible
    // glyph is "‹ Hike" and the accessible name is the sentence.
    await page.getByRole('button', { name: 'Back to Hike, step 1' }).click()

    await expect(
      page.getByRole('heading', { name: 'Where do you want to go?' }),
    ).toBeVisible()
  })
})

test.describe('how long is a day', () => {
  /** Step 3 of the long spine. */
  async function theDays(page: Page): Promise<void> {
    await aStretchInTheBuilder(page)
    await page.getByRole('button', { name: /Use this route/ }).click()
    await expect(page.getByText('How long is a day?')).toBeVisible({ timeout: 30_000 })
  }

  test('states: the days are laid out before they are kept, each named for where it ends', async ({
    page,
  }) => {
    await theDays(page)

    // THE ROUTE'S OWN HEAD, so the days are read against the thing they
    // divide rather than against a number remembered from the last screen.
    await expect(page.getByText(/[\d.]+ mi · \d+ days? · [\d,]+ ft up/)).toBeVisible()
    // A day is named for WHERE IT ENDS, not "D1 · 19.2 mi" — a hiker plans
    // to a shelter, not to a distance.
    await expect(page.getByText(/^→ .+/).first()).toBeVisible()
    // And Save is the last button (D7), with the promise that keeps the
    // screen from feeling final.
    await expect(page.getByRole('button', { name: 'Save this long hike' })).toBeVisible()
    await expect(
      page.getByText(/you can move every one of them afterwards/),
    ).toBeVisible()
  })

  test('states: the sheet says what a walking hour is not, and names its hard ceiling', async ({
    page,
  }) => {
    // THE SENTENCE THIS WHOLE CONTROL RESTS ON. "Walking hours" is a
    // measure a hiker will read as a day's length, and it is not one —
    // Naismith counts moving time. The app says so in its own voice rather
    // than letting the number imply an arrival.
    await theDays(page)

    await expect(page.getByText(/Naismith counts walking/)).toBeVisible()
    await expect(
      page.getByText(/A \d+-hour walking day is longer than \d+ hours/),
    ).toBeVisible()
    // And the ceiling, which is the safety half: a target that would put a
    // hiker past it is refused rather than planned, except where the trail
    // offers nowhere to stop.
    await expect(page.getByText('Hard ceiling')).toBeVisible()
    await expect(
      page.getByText(/longer only where the trail offers no stop inside it/),
    ).toBeVisible()

    // Both units offered, because a hiker who thinks in miles should not
    // have to convert.
    await expect(page.getByRole('button', { name: 'Walking hours' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Miles' })).toBeVisible()
  })

  test('exit: the rail goes back to the route, with the stretch still there', async ({
    page,
  }) => {
    await theDays(page)

    await page.getByRole('button', { name: 'Back to Route, step 2' }).click()

    await expect(page.getByText('How long is a day?')).toHaveCount(0)
    await expect(page.getByRole('button', { name: /Use this route/ })).toBeVisible()
    await expect(
      page.getByText(/Only the A\.T\. centerline can carry a route/),
    ).toBeVisible()
  })
})
