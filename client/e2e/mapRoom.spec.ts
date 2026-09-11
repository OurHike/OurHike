// The map keeps its room (#1373, PATHWAY.md's rule R2 - "The map never
// leaves. Map and step column share the screen").
//
// THE RULE HAD NO MEASUREMENT. R2 is a layout promise, `entryLayout.test.ts`
// checks a constant against a stylesheet's text, and every other assertion in
// this repository about the map's room is either a CSS rule read as a string
// or a person looking at a render. None of them can see the failure that
// actually happens: the map still mounted, still full size, and covered.
//
// Measured at 390x844 with this suite's own probe (2026-09-11), sampling the
// map container directly, which is why the floors below are the numbers they
// are:
//
//   map tab, nothing open   box 0.915 of the viewport   88% reachable
//   legend open             box 0.915                   28% reachable
//   Today tab               box 0.915                    0% reachable
//
// The box is identical in all three; only the reach tells them apart. See
// support/layout.ts for what is sampled instead and why. (The third row is
// the container's own story - through a role query the map is not exposed at
// all on Today, which the last test here asserts.)
//
// NOT ASSERTED GLOBALLY, deliberately: the map being covered on the Today tab
// of a phone is R2 working, not failing. Each floor below names its state.

import { test, expect } from '@playwright/test'
import { seedPreferences } from './support/seed'
import { seedDayHikes } from '../preview-shots/fixtures/dayHike.mjs'
import { expectMapReach } from './support/layout'

/**
 * With nothing over it, the map is nearly all reachable - the gap is its own
 * chrome, which rule R8 puts there on purpose (compass and locate
 * bottom-right, the scale bar bottom-left, the header plate above).
 *
 * 0.80 against a measured 0.88: the eight points of headroom are for that
 * chrome growing a little - a longer trail name, a second status chip - which
 * is a layout change rather than a defect. A panel taking a third of the map
 * lands far below this and is what the floor is for. `@unvalidated` as a
 * hiker-facing number: what it is derived from is today's measurement, not a
 * finding about how much map somebody needs to navigate, which nothing here
 * has established.
 */
const OPEN_MAP_FLOOR = 0.8

/**
 * A sheet may take most of the map and must not take all of it. Measured 0.28
 * with the legend up, against `legend.css`'s own `max-height: 60%`.
 *
 * 0.20 is under that measurement with room for the chrome above, and is the
 * floor a sheet outgrowing its own max-height would break - the defect
 * `preview-shots/legend.mjs`'s header records having hit once already, where
 * the sheet "grew past its `max-height: 60%`" after its contents landed and
 * pushed its foot under the fold. `@unvalidated` for the same reason as
 * above: it is a measurement of today, not a finding about a hiker.
 */
const SHEET_OPEN_FLOOR = 0.2

test.describe('the map keeps its room (R2)', () => {
  test('with nothing over it, the map owns the map tab', async ({ page }) => {
    await seedPreferences(page)
    await page.goto('/')
    await page.getByRole('tab', { name: 'Map' }).click()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()

    await expectMapReach(page, OPEN_MAP_FLOOR, 'map tab with nothing open')
  })

  test('an open sheet leaves the map a share of the screen, and gives it back', async ({
    page,
  }) => {
    await seedPreferences(page)
    await page.goto('/')
    await page.getByRole('tab', { name: 'Map' }).click()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()

    // Exact: "Legend" is a substring of "Close legend", so the ordinary
    // substring match resolves to both buttons once the sheet is up.
    await page.getByRole('button', { name: 'Legend', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Close legend' })).toBeVisible()
    await expectMapReach(page, SHEET_OPEN_FLOOR, 'legend open')

    // And it lets go. A sheet that cannot be dismissed hides the map exactly
    // as completely as one that is too big.
    await page.getByRole('button', { name: 'Close legend' }).click()
    await expect(page.getByRole('button', { name: 'Close legend' })).toHaveCount(0)
    await expectMapReach(page, OPEN_MAP_FLOOR, 'legend closed again')
  })

  test('on a phone with nothing followed, Today does not expose the map at all', async ({
    page,
  }) => {
    // SCOPED TO THIS STATE ON PURPOSE - the map IS on Today in two others,
    // and a test that read as "the map is never on Today" would be wrong
    // about both:
    //
    //  - **Following a walk.** The follow card sits over the map on Today
    //    (#1373, F6), and the map needs its room there as much as anywhere -
    //    arguably more, since that is the screen a hiker reads while moving.
    //    Not asserted yet: reaching it needs the follow door, and the saved
    //    card offers neither "Walk this" nor "Edit the route" without a
    //    resolved route (measured 2026-09-11 - both doors absent on the
    //    fixture card, while Leave it with someone and Delete are there),
    //    which is #1387's blocker wearing a different hat. The skipped test
    //    below is the target.
    //  - **A desktop.** `mapShownUnder` is `tab === 'map' || (isDesktop &&
    //    tab === 'today')`, so above the breakpoint Today keeps the map
    //    beside its column by design. Needs the desktop project this suite
    //    does not have yet.
    //
    // What this does assert is the phone's default: sampling the container
    // directly measured a full-height box with 0% reachable - the shape that
    // makes a box assertion useless - and the map is also out of the
    // accessibility tree, which is the better behaviour and the stronger
    // thing to hold. If this goes red because the region IS exposed here,
    // the floors above stop describing what they think they describe.
    await seedPreferences(page)
    await page.goto('/')
    await page.getByRole('tab', { name: 'Map' }).click()
    await expect(page.getByRole('region', { name: 'Map' }).first()).toBeVisible()

    await page.getByRole('tab', { name: 'Today' }).click()
    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Map' })).toHaveCount(0)

    await page.getByRole('tab', { name: 'Map' }).click()
    await expect(page.getByRole('region', { name: 'Map' }).first()).toBeVisible()
    await expectMapReach(page, OPEN_MAP_FLOOR, 'back on the map tab')
  })

  // THE STATE THE MAP MOST NEEDS ITS ROOM IN, and the one this suite cannot
  // reach yet. While a walk is being followed the map is on Today under the
  // next-turn card (#1373, F6) - the screen a hiker actually reads while
  // moving, where a card that has grown over the map is worst.
  //
  // Blocked the same way everything else that needs a live route is: the
  // saved card offers no "Walk this" without a resolved route, and nothing
  // here can resolve one (#1387). Written out rather than described, so the
  // change that unblocks it only has to delete the `.skip` - and so the gap
  // is visible in the suite rather than only in prose.
  test.skip('while following a walk, the map on Today keeps its room - blocked on #1387', async ({
    page,
  }) => {
    await seedPreferences(page)
    await page.goto('/')
    await seedDayHikes(page)

    await page.getByRole('tab', { name: 'Plan' }).click()
    await page.getByRole('button', { name: /Pine Meadow loop/ }).click()
    await page.getByRole('button', { name: 'Walk this', exact: true }).click()

    await page.getByRole('tab', { name: 'Today' }).click()
    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    // The follow card is over the map here, so this is a sheet-shaped floor
    // rather than the open-map one - what it refuses is a card that has taken
    // the whole screen a hiker is navigating by.
    await expect(page.getByRole('region', { name: 'Map' }).first()).toBeVisible()
    await expectMapReach(page, SHEET_OPEN_FLOOR, 'Today while following a walk')
  })
})
