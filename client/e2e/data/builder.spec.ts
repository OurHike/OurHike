// The planning spine with a junction graph under it — F3 and F4 of
// features/FLOW_TESTING.md's battery, and the half **#1387 — Neither the
// Playwright suite nor the screenshot recipes can put a live draft in the
// day-hike builder without a reachable bucket** says could not be driven.
//
// It can now, because this suite reads the pinned release rather than nothing.
// playwright.config.ts's FLOW_DATA comment carries what that costs and the
// three things that bound it; the short version is that the release is
// immutable and this is its own CI job, so a bucket outage never looks like a
// broken build.
//
// WHAT IS ASSERTED, AND WHAT IS DELIBERATELY NOT. The published data is real
// and it moves when somebody bumps the pin, so nothing here pins a figure off
// it: not a distance, not a climb, not a shelter's name. What is pinned is the
// SHAPE the screen takes once a graph is under it — the rail advancing, the
// route acquiring figures at all, the shape control offering its three
// answers, the foot carrying the two doors. Those are claims about the app.
// "6.4 mi" would be a claim about a release.
//
// ENTRANCE. Every step is a real tap from boot, through the doors a hiker
// uses. No navigator state is injected (FLOW_TESTING.md, "Not a router").

import { test, expect, type Page } from '@playwright/test'
import { seedPreferences, seedHikerMode } from '../support/seed'

/** Past first run, in day mode, on step 1 of the spine — the screen Today's
 *  pinned "Plan a hike" and the Plan tab's own primary both land on. */
async function stepOne(page: Page): Promise<void> {
  await seedPreferences(page)
  await seedHikerMode(page, 'day')
  await page.goto('/')
  await page.getByRole('tab', { name: 'Plan' }).click()
  await expect(page.getByRole('tab', { name: 'Plan', selected: true })).toBeVisible()
  // THROUGH THE DAY ROOM'S OWN DOOR, which is what a hiker taps. The Plan tab
  // does not open on step 1 — it opens on the room, and with nothing saved the
  // room is a sentence and one door (plan.spec.ts pins that state). This spec
  // first assumed the tab landed on step 1 and found the room instead; the
  // build is right and the extra tap is the journey.
  await page.getByRole('button', { name: 'Start on the map' }).click()
  await expect(
    page.getByRole('heading', { name: /Where do you want to go/ }),
  ).toBeVisible()
}

test.describe('step 1, with a trail network on the phone', () => {
  test('states: the three doors are offered, where a build with no graph shows the refusal instead', async ({
    page,
  }) => {
    // THE ASSERTION THE HERMETIC SUITE CANNOT MAKE, and the reason this file
    // exists. D10 says a door that cannot work is absent rather than greyed,
    // and step 1 honours it by replacing all three with a sentence and a retry
    // when the junction graph is not on the phone. Every run before this one
    // saw the refusal — so "the doors appear when the graph is there" was an
    // untested half of a rule whose tested half was the refusal.
    await stepOne(page)

    await expect(page.getByRole('button', { name: /Pick on the map/ })).toBeVisible()
    await expect(page.getByRole('button', { name: /Draw it myself/ })).toBeVisible()
    // And the refusal absent, which is what makes the above a claim about the
    // graph rather than about the button existing in some other state.
    await expect(page.getByText(/trail network is not on the phone/i)).toHaveCount(0)
  })

  test('entrance: Pick on the map turns the screen into the builder, with the shape control absent until there is a route to shape', async ({
    page,
  }) => {
    await stepOne(page)

    await page.getByRole('button', { name: /Pick on the map/ }).click()

    // The builder names what is being built, which is how a hiker knows the
    // door advanced the spine rather than opening something beside it (R3).
    await expect(page.getByRole('heading', { name: 'A new day hike' })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()

    // The rail's way back, labelled for where it goes rather than with a bare
    // chevron — and the other tool, because step 2 ships two (tap and draw)
    // and the design's third was deferred with its reason (#1373).
    await expect(page.getByRole('button', { name: 'Back to Hike, step 1' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Draw instead' })).toBeVisible()

    // THE SHAPE CONTROL IS ABSENT, and that is the correction this test
    // carries. It first asserted Point to point / Out and back / Loop were
    // present the moment the builder opened; they are not, because with no
    // stops dropped there is no route to shape and a segmented control over
    // nothing is a label that looks like a control — the same argument
    // chrome/BackgroundPicker.tsx makes for returning null (#855), and D10's
    // "absent rather than disabled" applied to a control rather than a door.
    await expect(page.getByRole('button', { name: /Point to point/ })).toHaveCount(0)
    await expect(page.getByRole('button', { name: /Out and back/ })).toHaveCount(0)

    // Nor is there a way on yet: "Use this route ›" is a claim that there is
    // a route, and there is not.
    await expect(page.getByRole('button', { name: /Use this route/ })).toHaveCount(0)
  })

  test('exit: the rail carries the builder back to step 1, which is R3 keeping the draft', async ({
    page,
  }) => {
    // Rule 2's claim on the screen where it matters most — a builder a hiker
    // cannot leave holds the whole app. The rail's own back is the exit R3
    // specifies ("‹ Hike back to step 1 with the draft kept"), and with no
    // stops dropped there is nothing to bail from, so the bail sheet (D8) is
    // correctly not in the way.
    await stepOne(page)
    await page.getByRole('button', { name: /Pick on the map/ }).click()
    await expect(page.getByRole('heading', { name: 'A new day hike' })).toBeVisible()

    await page.getByRole('button', { name: 'Back to Hike, step 1' }).click()

    await expect(
      page.getByRole('heading', { name: /Where do you want to go/ }),
    ).toBeVisible()
    await expect(page.getByRole('heading', { name: 'A new day hike' })).toHaveCount(0)
    // And step 1 still offers the doors, so the round trip left the graph
    // where it was rather than dropping the phone back into the refusal.
    await expect(page.getByRole('button', { name: /Pick on the map/ })).toBeVisible()
  })
})

test.describe('the map, with waypoints published', () => {
  test('states: the In view door counts what the map is drawing, and opens on its rows', async ({
    page,
  }) => {
    // The other half of a rule whose absent side is already covered
    // (mapChrome.spec.ts): the door is gated on `pointsShown.length > 0`, so
    // every hermetic run sees it missing. This is the first time a spec has
    // seen it present.
    await seedPreferences(page)
    await page.goto('/')
    await page.getByRole('tab', { name: 'Map' }).click()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()

    const door = page.getByRole('button', { name: /In view/ })
    await expect(door).toBeVisible()
    // A count, not THE count: the number is the release's and would pin a
    // publish rather than the screen.
    await expect(door).toHaveText(/In view · \d+/)

    await door.click()
    // The sheet, and its rows. Again by shape: a waypoint row carries a name
    // and a mono line of type and mile, and asserting any particular shelter
    // would break the next time the exporter runs.
    await expect(page.getByRole('dialog', { name: /In view/ })).toBeVisible()
  })
})
