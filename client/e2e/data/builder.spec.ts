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
import {
  seedPreferences,
  seedHikerMode,
  seedCamera,
  ON_THE_TRAIL,
  ABOVE_THE_SEAM_ZOOM,
} from '../support/seed'
import { editTheSavedRoute } from '../support/savedWalk'

/** Room for GRAPH_READY_MS, which is larger than playwright.config.ts's
 *  data-mode per-test ceiling because the junction graph resolving a saved
 *  walk is the slowest door in this suite. support/savedWalk.ts carries the
 *  measurement and why the old 60_000 was not one. */
test.describe.configure({ timeout: 300_000 })

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
    //
    // ASSERTED ON THE RADIOGROUP, and the first version of this was worse
    // than useless: it looked for BUTTONS named "Point to point" and "Out and
    // back", and the control is a `radiogroup` of `role="radio"` options
    // (DayHikePickBar.tsx). So it passed whether the control was there or
    // not, and the sibling test below — which asserts the same control
    // PRESENT once a route is loaded — is what exposed it.
    await expect(page.getByRole('radiogroup', { name: 'Shape' })).toHaveCount(0)

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

test.describe('the bar over the map at step 2', () => {
  /** Step 2 with the tap tool open, at a camera above the pin seam so the
   *  map is drawing tread rather than a corridor sketch. */
  async function pickOnTheMap(page: Page): Promise<void> {
    await seedCamera(page, ON_THE_TRAIL, ABOVE_THE_SEAM_ZOOM)
    await stepOne(page)
    await page.getByRole('button', { name: /Pick on the map/ }).click()
    await expect(page.getByRole('heading', { name: 'A new day hike' })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
  }

  test('states: the bar says what a tap will do, and names the boundary it will not cross', async ({
    page,
  }) => {
    await pickOnTheMap(page)

    // TWO TAPS, SAID IN ORDER. The gesture is not obvious — one tap starts
    // walking a trail and the second decides where to turn off it — so the
    // bar spells it out rather than leaving a hiker to discover it.
    await expect(
      page.getByText(/Tap a trail to walk it\. Tap again further along to turn\./),
    ).toBeVisible()

    // THE BOUNDARY, SAID RATHER THAN IMPLIED. A missing capability the app is
    // silent about reads as a bug; one it names reads as a boundary
    // (DayHikePickBar.tsx's own argument for #931). Roads are drawn because a
    // hiker needs to see them and never routed on, which is
    // build_trail_graph.py's rule — roads are not edges — surfaced on the one
    // screen where a hiker would otherwise try.
    await expect(page.getByText('Roads are drawn, never routed on')).toBeVisible()

    // The tool's own way out, which is not the rail's: Cancel abandons the
    // tap tool, where "Back to Hike, step 1" leaves the step (asserted above).
    await expect(page.getByRole('button', { name: 'Cancel' })).toBeVisible()

    // WHAT IS DELIBERATELY NOT ASSERTED, and it is a measurement rather than
    // an omission. The bar's refusal sentence — "that tap isn't on a marked
    // hiking route" — fires only on a tap the graph can place and decline,
    // and no tap this suite can aim reaches one: ninety taps across this map
    // at this camera, over two runs on 2026-09-11 against release 2026-09-10,
    // produced neither a routed stop nor a refusal. They land on open ground,
    // where the bar correctly says nothing at all. features/FLOW_TESTING.md
    // carries that measurement under #1387, which is the issue this is.
    await expect(page.getByText(/isn’t on a marked hiking route/)).toHaveCount(0)
  })
})

test.describe('the builder with a route already in it', () => {
  /**
   * A live day-hike draft, without a single canvas tap.
   *
   * THE DOOR IS "EDIT THE ROUTE" on a saved walk's card, and finding it is
   * what unblocked this whole group. The obvious way in — tap the map until
   * the router accepts a stop — cannot be aimed from a spec
   * (features/FLOW_TESTING.md carries the measurement, under #1387). Editing
   * a walk the phone already holds loads its legs into step 2 and puts the
   * builder in exactly the state a hiker reaches by tapping, which is what
   * the assertions below are about.
   *
   * The walk is e2e/data/followMode.spec.ts's, for the same reason that spec
   * imports it rather than inventing one: its ends were measured against
   * published tread, and a second fixture would be a second answer to which
   * walk resolves.
   */
  test('states: with a route in it the builder offers the shape control and the way on, which it withholds with nothing', async ({
    page,
  }) => {
    // THE OTHER HALF OF THIS FILE'S OWN D10 CLAIM. The empty-builder test
    // above asserts that Point to point / Out and back and "Use this route ›"
    // are ABSENT with no stops — a segmented control over nothing is a label
    // that looks like a control, and a way on is a claim that there is a
    // route. Until now nothing asserted they appear when there IS one, which
    // made that an untested half: a build that never rendered them would have
    // passed.
    await editTheSavedRoute(page)

    const shape = page.getByRole('radiogroup', { name: 'Shape' })
    await expect(shape).toBeVisible()
    await expect(shape.getByRole('radio', { name: 'Point to point' })).toBeVisible()
    await expect(shape.getByRole('radio', { name: 'Out and back' })).toBeVisible()
    await expect(shape.getByRole('radio', { name: 'Loop' })).toBeVisible()
    await expect(page.getByRole('button', { name: /Use this route/ })).toBeVisible()
    // And the two tools a route makes meaningful: taking back the last tap,
    // and starting again without leaving the step.
    await expect(page.getByRole('button', { name: 'Undo' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Start a new stretch' })).toBeVisible()
  })

  test('states: the route reads back as an ordered list of legs with the miles they cover', async ({
    page,
  }) => {
    // WHAT THE PANEL IS FOR. A route is a sequence, and a hiker checking one
    // is asking "in what order, and how far is each" — so the panel numbers
    // the legs and gives each its own span of the walk rather than printing a
    // total and leaving the shape to the map.
    await editTheSavedRoute(page)

    const order = page.locator('.day-hike-panel__list > li')
    expect(await order.count()).toBeGreaterThan(1)
    // A mile range per leg, by shape: the numbers are the release's.
    await expect(page.getByText(/mile [\d.]+–[\d.]+/).first()).toBeVisible()
    // And who keeps it walkable, counted live while the hiker builds rather
    // than added as a credit at the end — three organizations keeping one
    // loop walkable is the thing this app exists to make visible.
    await expect(page.getByText(/· \d+ legs?$/).first()).toBeVisible()
  })

  test('states: a walk whose climb nobody measured says so, and prices nothing', async ({
    page,
  }) => {
    // ROUND TOWARD CAUTION, AND SAY WHICH WAY YOU ROUNDED (CLAUDE.md). The
    // panel could fill WALKING from distance alone; a flat-ground time on a
    // walk with unmeasured climb is an optimistic number wearing an honest
    // one's ≈. Instead it prints neither, and says which of the two reasons
    // it is — the download, or the trail.
    //
    // Reachable because release 2026-09-10 publishes no elevation cell over
    // this walk (e2e/data/followMode.spec.ts's header carries that
    // measurement), so this is the first branch rather than a contrived one.
    await editTheSavedRoute(page)

    await expect(page.getByText(/can’t price the climb on this walk/)).toBeVisible()
    await expect(
      page.getByText(
        /the elevation download hasn’t landed, or one of these trails has never been measured/,
      ),
    ).toBeVisible()
  })
})

test.describe('a half-built route the hiker walks away from', () => {
  /** The same live draft as above, parked one step back — the premise for
   *  both tests here, and the state R3 is a claim about. */
  async function draftUnderStepOne(page: Page): Promise<void> {
    await editTheSavedRoute(page)
    await page.getByRole('button', { name: 'Back to Hike, step 1' }).click()
    await expect(
      page.getByRole('heading', { name: /Where do you want to go/ }),
    ).toBeVisible()
  }

  test('states: R3 with a route actually in it — the rail’s back keeps every leg', async ({
    page,
  }) => {
    // THE CLAIM R3 MAKES, tested for the first time against something worth
    // keeping. The empty-builder exit test above drives the same control and
    // can only assert that step 1 came back, because an empty draft survives
    // trivially. This one counts the legs on the way out and again on the way
    // in: a back that quietly emptied the builder would pass that test and
    // fail this one.
    await draftUnderStepOne(page)

    await page.getByRole('button', { name: /Pick on the map/ }).click()

    await expect(page.getByRole('button', { name: /Use this route/ })).toBeVisible()
    expect(await page.locator('.day-hike-panel__list > li').count()).toBeGreaterThan(1)
    await expect(page.getByRole('radiogroup', { name: 'Shape' })).toBeVisible()
  })

  test('states: leaving the whole flow by the tab bar parks the route, and Plan offers the way back', async ({
    page,
  }) => {
    // NOT ASKED ABOUT, AND THAT IS RIGHT HERE — which is worth asserting
    // because the long-hike builder DOES ask in the same position
    // (e2e/bailSheet.spec.ts's first test), and the asymmetry looks like a
    // missing guard until you follow it through. A day-hike draft under step
    // 1 is parked rather than swept: nothing is at risk, so nothing is asked,
    // and the Plan tab carries the way back to it.
    //
    // That is exactly the outcome the bail sheet's "Keep it for later" reaches
    // for the other builder. The day builder gets there without the question.
    await draftUnderStepOne(page)

    await page.getByRole('tab', { name: 'Today' }).click()
    await expect(
      page.getByRole('dialog', { name: 'Keep this half-built route?' }),
    ).toHaveCount(0)

    await page.getByRole('tab', { name: 'Plan' }).click()
    const back = page.getByRole('button', { name: /Back to your route/ })
    await expect(back).toBeVisible()

    // AND THE WAY BACK ACTUALLY GOES BACK, which is the half that makes the
    // absent question defensible. A "Back to your route" that reopened an
    // empty builder would be worse than no button at all.
    await back.click()
    await expect(page.getByRole('button', { name: /Use this route/ })).toBeVisible()
    expect(await page.locator('.day-hike-panel__list > li').count()).toBeGreaterThan(1)
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
