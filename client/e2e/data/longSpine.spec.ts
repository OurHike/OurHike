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

import { test, expect, type Page } from '@playwright/test'
// Untyped on purpose: a shot fixture is plain JavaScript, and its shape is the
// app's contract with IndexedDB rather than a type this spec should restate.
import { seedLongHike } from '../../preview-shots/fixtures/longHike.mjs'
import { seedPreferences, seedHikerMode } from '../support/seed'

const ENTRANCE = { name: 'Plan a route' }
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
 * Wait until the waypoint index is actually on the phone.
 *
 * The map's "In view" door is the app's own statement that it is drawing
 * waypoints, which is the nearest observable to "the stops exist". Waiting on
 * it rather than on a timer is what CLAUDE.md's ordering rule asks for, and
 * here it is also the subject: the test below the fix exists to say what the
 * entrance shows BEFORE this has happened.
 */
async function waypointsOnThePhone(page: Page): Promise<void> {
  await page.getByRole('tab', { name: 'Map' }).click()
  await expect(page.getByRole('button', { name: /In view/ })).toBeVisible({
    timeout: 60_000,
  })
  await page.getByRole('tab', { name: 'Today' }).click()
}

test.describe('the route builder’s entrance', () => {
  test('states: with the stops on the phone it asks where from, and offers three ways to answer', async ({
    page,
  }) => {
    await planALongHike(page)
    await waypointsOnThePhone(page)
    await page
      .getByRole('group', { name: 'Find or plan a hike' })
      .getByRole('button', { name: 'Plan a hike' })
      .click()
    await page.getByRole('button', { name: 'Pick on the map' }).click()

    const sheet = page.getByRole('dialog', ENTRANCE)
    await expect(sheet).toBeVisible()
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
    // And the cross-check that this really is the waypoint-less state rather
    // than a fast fetch — the map offers no In view door with nothing drawn.
    await sheet.getByRole('button', { name: /Close the route builder/ }).click()
    await page.getByRole('tab', { name: 'Map' }).click()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
    await expect(page.getByRole('button', { name: /In view/ })).toHaveCount(0)
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
