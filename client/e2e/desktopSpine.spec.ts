// The desktop layout — F16, and the first project in this suite that is not a
// phone (playwright.config.ts's `projects`).
//
// WHY THIS IS A SECOND PROJECT AND NOT A SECOND VIEWPORT IN AN EXISTING SPEC.
// `lib/useDesktop.ts`'s 900px breakpoint is a FORK, not a reflow. Most of what
// happens above it is CSS, and CSS is not what this file is about: it is about
// the handful of things a stylesheet cannot do, which is exactly the list that
// hook's own header gives. The legend "is `role="dialog" aria-modal="true"` and
// renders nothing when closed; on a desktop it is a persistent panel that is
// never dismissed. No stylesheet can change what a component announces itself
// as, or make it render when it has returned null."
//
// So every assertion here is about a claim that differs in KIND between the two
// widths, and each names its phone counterpart — because a desktop test that
// merely re-asserts something true at both widths is a slower copy of a phone
// test, which is the cost features/FLOW_TESTING.md warns a second project can
// quietly become.
//
// TAGGED `@desktop`, WHICH IS WHAT PUTS IT HERE. The phone project greps it
// out and the desktop project greps it in, so nothing in this file ever runs at
// 390px and nothing else ever runs at 1280.
//
// HERMETIC. None of these forks needs published data: the legend's shape, the
// rail's two faces, the nav, the mode block and the bail guard are all layout.

import { test, expect, type Page } from '@playwright/test'
import { seedPreferences, seedHikerMode } from './support/seed'
import { expectMapReach } from './support/layout'
// Untyped on purpose: a shot fixture is plain JavaScript, and its shape is
// the app's contract with IndexedDB rather than a type this spec restates.
import { seedLongHike } from '../preview-shots/fixtures/longHike.mjs'

/** Past first run, on the map. */
async function openMap(page: Page): Promise<void> {
  await seedPreferences(page)
  await page.goto('/')
  await page.getByRole('tab', { name: 'Map' }).click()
  await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
}

/**
 * THE MAP'S ROOM AT THIS WIDTH, measured 2026-09-11 with the same probe
 * `e2e/mapRoom.spec.ts` uses at 390x844 (support/layout.ts sampling
 * `document.elementFromPoint` over the map's own box):
 *
 *   map tab      box 0.979 of the viewport   95% reachable
 *   Today tab    box 0.964                   89% reachable
 *   Plan home    no map region in the tree at all
 *
 * The laptop reaches MORE of its map than the phone reaches of its (88% on
 * the map tab) rather than less, which is worth knowing because the opposite
 * is the intuition: the rail is a column BESIDE the canvas rather than a
 * sheet over it, and the map's own controls (rule R8) are a smaller share of
 * a wider frame.
 *
 * 0.85 against a measured 0.95, for the reason mapRoom.spec.ts's own floor
 * leaves eight points: the chrome in the corners can grow a little - a longer
 * trail name, a second status chip - and that is a layout change rather than
 * a defect. A panel landing over the canvas lands far below this.
 */
const DESKTOP_MAP_FLOOR = 0.85

/**
 * R2 IS A STRONGER CLAIM ABOVE THE BREAKPOINT, and this constant is where the
 * difference is written down. PATHWAY.md's R2 is "side by side on a desktop,
 * stacked on a phone" - so a phone's Today covering the map completely is the
 * rule working (mapRoom.spec.ts asserts that absence directly), and a
 * laptop's Today must cost the map almost nothing.
 *
 * Which is why this is the phone's UNCOVERED floor (`OPEN_MAP_FLOOR`, 0.80)
 * rather than its sheet floor (0.20): the claim is that Today beside the map
 * is not a covering at all. Measured 0.89, so nine points of headroom.
 *
 * `@unvalidated` as a hiker-facing number, exactly as both phone floors are:
 * it is a measurement of today's layout, not a finding about how much map
 * somebody needs to navigate by. Field testing would settle that; nothing
 * here has.
 */
const DESKTOP_TODAY_FLOOR = 0.8

test.describe('the laptop layout', { tag: '@desktop' }, () => {
  test('states: the legend is a panel that was never opened, not a dialog that was', async ({
    page,
  }) => {
    await openMap(page)

    // THE FORK, IN ONE ASSERTION. On a phone the legend is behind a button and
    // announces itself as a modal dialog (e2e/mapChrome.spec.ts opens it and
    // reads `role="dialog"`); here it is a region that is simply present. No
    // button has been pressed at this point in the drive, which is the half
    // that matters — a panel a test had to open would be a dialog wearing a
    // different word.
    await expect(page.getByRole('region', { name: 'Legend' })).toBeVisible()
    await expect(page.getByRole('dialog', { name: 'Legend' })).toHaveCount(0)

    // And there is nothing to dismiss it with, because it is not dismissible.
    await expect(page.getByRole('button', { name: /Close legend/ })).toHaveCount(0)
  })

  test('states: the rail carries both faces at once, switched at its head', async ({
    page,
  }) => {
    await openMap(page)

    // On a phone these are two separate doors in the header — "Legend" and
    // "In view · N" — and opening one closes the other, because two panels
    // over one map is the screen arguing with itself. On a laptop the column
    // has room for one of them at a time and a switch to say which, so the two
    // are tabs in a named tablist rather than doors.
    const rail = page.getByRole('tablist', { name: 'Beside the map' })
    await expect(rail).toBeVisible()
    await expect(rail.getByRole('tab', { name: 'Legend' })).toBeVisible()
    await expect(rail.getByRole('tab', { name: /In view/ })).toBeVisible()

    // The legend is the face it opens on, and the switch moves it.
    await expect(page.getByRole('region', { name: 'Legend' })).toBeVisible()
    await rail.getByRole('tab', { name: /In view/ }).click()
    await expect(page.getByRole('region', { name: 'Legend' })).toHaveCount(0)

    // The map is untouched by the switch — it is the column that changed, not
    // the canvas, which is the whole argument for putting the switch there.
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
  })

  test('states: Today is beside the map rather than instead of it', async ({ page }) => {
    await seedPreferences(page)
    await page.goto('/')

    // The Today tab, and the map is STILL THERE. On a phone Today replaces the
    // map entirely; here the journal column and the canvas share the window,
    // which is what makes the bail guard below behave differently.
    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    await expect(page.getByText('Nothing planned today')).toBeVisible()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
  })

  test('states: the mode block is a named radio group in the shell, not a chip in the tab row', async ({
    page,
  }) => {
    await seedPreferences(page)
    await page.goto('/')

    // The phone puts the mode behind a chip at the left of the tab row (the
    // room audit's option B, #1374). A laptop has a sidebar, so the three
    // modes are a labelled radiogroup with all three showing and the current
    // one checked — no tap needed to find out which mode the app is in.
    const modes = page.getByRole('radiogroup', { name: /Today I.m/ })
    await expect(modes).toBeVisible()
    for (const name of ['Day hike', 'Long hike', 'Volunteer']) {
      await expect(modes.getByRole('radio', { name })).toBeVisible()
    }
    await expect(modes.getByRole('radio', { name: 'Day hike' })).toBeChecked()
  })

  test('states: tapping Today with a live route draft is not an exit here, and asks nothing', async ({
    page,
  }) => {
    // THE WORKED EXAMPLE features/FLOW_TESTING.md gives for why this project
    // exists, driven at last. The guard is
    // `move.to === 'tab' && mapShownUnder(state.tab) && !mapShownUnder(move.tab)`,
    // and `mapShownUnder` is `tab === 'map' || (isDesktop && tab === 'today')`.
    // So the same tap that raises the bail sheet on a phone
    // (e2e/bailSheet.spec.ts's first test) raises nothing here — because the
    // hiker has not left the map, it is still on the screen beside Today.
    await seedPreferences(page)
    await seedHikerMode(page, 'long')
    await page.goto('/')
    await page
      .getByRole('group', { name: 'Find or plan a hike' })
      .getByRole('button', { name: 'Plan a hike' })
      .click()
    await page
      .getByRole('group', { name: 'Start from' })
      .getByRole('button', { name: 'Pick on the map' })
      .click()
    await expect(page.getByText('Where from?')).toBeVisible()

    await page.getByRole('tab', { name: 'Today' }).click()

    // NO ASK, because nothing is at risk.
    await expect(
      page.getByRole('dialog', { name: 'Keep this half-built route?' }),
    ).toHaveCount(0)

    // AND THE DRAFT IS STILL LIVE, which is the other half of the claim: a
    // guard that did not fire because the draft had been swept would look
    // identical from outside, and would be the bug rather than the feature.
    await expect(page.getByText('Where from?')).toBeVisible()
  })

  test('states: Today costs the map almost nothing, and Plan is where the map stops', async ({
    page,
  }) => {
    // THE BOX CANNOT TELL THESE APART, which is the whole argument for the
    // probe: the map screen stays mounted at full size under whatever is over
    // it, so `toBeVisible` and any assertion on width or height pass in every
    // state. See support/layout.ts.
    await seedPreferences(page)
    await page.goto('/')
    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    await expectMapReach(page, DESKTOP_TODAY_FLOOR, 'Today beside the map on a laptop')

    await page.getByRole('tab', { name: 'Map' }).click()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
    await expectMapReach(page, DESKTOP_MAP_FLOOR, 'the map tab on a laptop')

    // AND THE FORK HAS AN EDGE. `mapShownUnder` is
    // `tab === 'map' || (isDesktop && tab === 'today')` - Plan is in neither
    // half, so Plan home gets the whole window and no map. Asserted as an
    // ABSENCE FROM THE ACCESSIBILITY TREE rather than as a reach of zero,
    // which is the stronger statement and the one mapRoom.spec.ts makes about
    // the phone's Today: a screen reader is not told there is a map here.
    await page.getByRole('tab', { name: 'Plan' }).click()
    await expect(page.getByRole('region', { name: 'Map' })).toHaveCount(0)
  })

  test('states: the map credits every source on one line, with nothing behind a disclosure', async ({
    page,
  }) => {
    await openMap(page)

    // MapAttribution's own rule: "WHERE THERE IS ROOM, NOTHING IS HIDDEN."
    // On a phone three credits are a `<details>` whose summary reads
    // "© OpenStreetMap contributors · 2 more" and whose other two are one tap
    // away - the arrangement the OSMF guidelines contemplate for a medium too
    // narrow to carry the statement inline. A laptop is not that medium.
    //
    // Measured 2026-09-11, this suite's own two projects on the same boot:
    //   phone    "© OpenStreetMap contributors · 2 more"   (a summary)
    //   desktop  all three joined by "·"                    (a paragraph)
    const credits = page.getByText(/^© OpenStreetMap contributors/)
    await expect(credits).toBeVisible()

    // The other two sources, visible with nothing tapped. This is the
    // assertion that would go red if the desktop quietly started collapsing.
    await expect(credits).toContainText('OpenFreeMap')
    await expect(credits).toContainText(/Elevation/)

    // AND NO COUNT, because a count is the disclosure announcing what it is
    // withholding. Nothing is withheld here, so the phrase must not appear.
    await expect(page.getByText(/\d+ more$/)).toHaveCount(0)
  })

  test('states: the offline download says what it is for on a machine that is not going up a mountain', async ({
    page,
  }) => {
    await openMap(page)

    // The door is in the legend, which is a persistent region here rather
    // than the sheet e2e/settingsRooms.spec.ts opens on a phone - so the same
    // drive reaches it with one fewer tap.
    await page
      .getByRole('region', { name: 'Legend' })
      .getByRole('button', { name: /^Choose what to download/ })
      .click()

    const window_ = page.getByRole('dialog', { name: 'Offline map' })
    await expect(window_).toBeVisible()

    // THE SENTENCE IS THE FORK, and it is a claim about the world rather than
    // about layout: Downloads.tsx says the honest thing for the device it is
    // on (WEBSITE.md §6) instead of borrowing the phone's reason. A laptop
    // streams what it needs; the download is for the phone in the pack.
    await expect(window_.getByText(/the download is for the phone you/)).toBeVisible()
    await expect(window_.getByText(/the map works with no signal/)).toHaveCount(0)
  })

  test('entrance and states: a section’s days get a bench beside them, and it says when it cannot draw', async ({
    page,
  }) => {
    await seedPreferences(page)
    await seedHikerMode(page, 'long')
    await page.goto('/')
    await seedLongHike(page)
    await page.getByRole('tab', { name: 'Plan' }).click()

    // Into the section, by the same door e2e/planRooms.spec.ts uses - the
    // row IS the button, so its accessible name is the section's name.
    await page
      .getByRole('button', { name: /Springer → Neels Gap/ })
      .first()
      .click()
    await expect(page.getByRole('button', { name: 'Days', exact: true })).toBeVisible()

    // `Plan.tsx`: "Only at the day zoom, and only above the breakpoint.
    // Everything below this line is dead on a phone by construction rather
    // than by promise." Measured 2026-09-11: this navigation landmark is
    // present here and absent at 390px on the identical drive.
    const bench = page.getByRole('navigation', { name: 'This hike' })
    await expect(bench).toBeVisible()

    // AND THE HONEST REFUSAL, which is the half worth pinning. The bench's
    // reason to exist is dragging a day boundary along an elevation profile,
    // and this phone has downloaded none - so it says so, and says what is
    // still true, rather than drawing an empty frame or silently omitting the
    // control. That is the data-freshness axis' "which absence" branch on a
    // surface nobody would think to look for it on.
    await expect(
      page.getByText(/no elevation profile, so there is nothing to drag a day boundary/),
    ).toBeVisible()
    await expect(page.getByText(/days and their miles are unaffected/)).toBeVisible()
  })

  test('states: the sidebar carries which hike you are on, where the tab row has no room for it', async ({
    page,
  }) => {
    await seedPreferences(page)
    await seedHikerMode(page, 'long')
    await page.goto('/')
    await seedLongHike(page)

    // App.tsx's `sidebarHikeSwitch`, which is `isDesktop && activeHike !== null
    // && tripStore.hikes.length > 0` - all three conditions, so this is also
    // an assertion that the control is offered only where switching would do
    // something ("a control that does nothing" is LineSheet's rule).
    //
    // SCOPED TO THE NAV, and the first draft of this test was not, which is
    // why the scoping is the interesting part. Today's banner carries its own
    // hike-name switch (`today__hike-name--switch`) at BOTH widths, so an
    // unscoped query matches two buttons here and one on a phone - and would
    // have read as "the phone has this too" rather than as "this test is
    // pointed at the wrong control". What is desktop-only is the copy in the
    // navigation landmark, because a phone's tab row has four tabs and a mode
    // chip in 390px and no room for a fifth thing.
    //
    // Measured 2026-09-11 on the identical drive: inside `navigation "Main"`,
    // one such button at 1280 and none at 390.
    const nav = page.getByRole('navigation', { name: 'Main' })
    await expect(
      nav.getByRole('button', { name: /change which hike you.re on/ }),
    ).toBeVisible()
    await expect(
      nav.getByRole('button', { name: /change which hike you.re on/ }),
    ).toContainText('Springer → Katahdin')
  })

  test('entrance and exit: step 1 stands in the column beside the map, and the rail stands down for it', async ({
    page,
  }) => {
    // THE SPINE FORK, and the one the maintainer asked for by name in the
    // review of #1374: "That 3 step process should be a sidebar on the map."
    // On a phone step 1 is a PAGE on the Plan tab and the map is not on the
    // screen at all (e2e/planRooms.spec.ts drives that); here it is a column
    // in `map-screen__body` with the canvas beside it.
    // `App.desktopSpine.test.tsx` holds the same claim at the rendered layer,
    // down to which parent the column sits in; what this adds is that a hiker
    // can tap their way to it.
    await seedPreferences(page)
    await page.goto('/')
    await page.getByRole('tab', { name: 'Plan' }).click()
    await page.getByRole('button', { name: 'Start on the map' }).click()

    await expect(
      page.getByRole('heading', { name: 'Where do you want to go?' }),
    ).toBeVisible()
    // Beside the map, not instead of it.
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()

    // AND THE RAIL STANDS DOWN, which is the half a stylesheet cannot fake:
    // the legend is a persistent region on every other desktop screen (the
    // first test in this file), and it is gone here because the column has
    // taken its slot. Two columns beside one map is the room problem the
    // whole shell exists to avoid, at a width that makes it look affordable.
    await expect(page.getByRole('region', { name: 'Legend' })).toHaveCount(0)

    // EXIT: Cancel lands back in Plan's room, and the map goes with it -
    // `mapShownUnder` does not hold Plan, so a map left drawn here would be a
    // canvas nobody asked for under a list.
    await page.getByRole('button', { name: 'Cancel' }).click()
    await expect(
      page.getByRole('heading', { name: 'Where do you want to go?' }),
    ).toHaveCount(0)
    await expect(page.getByRole('region', { name: 'Trail map' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Start on the map' })).toBeVisible()
  })

  test('states: a pan leaves the plate whole here, where a phone folds it away for room', async ({
    page,
  }) => {
    // The plate folds on a gesture pan and hides its status strip - the room
    // audit of 2026-09-10, which bought back a phone's vertical room by
    // trading the strip for an eyebrow the hiker taps to get it back.
    //
    // A laptop pays nothing for that room and so does not make the trade:
    // `folded={plateFolded && !isDesktop}` in chrome/MapScreen.tsx. The state
    // still flips - the gesture sets it at both widths - and only the render
    // reads it, which is exactly the kind of fork a stylesheet cannot fake
    // and a phone-only suite cannot see.
    await seedPreferences(page)
    await seedHikerMode(page, 'day')
    await page.goto('/')
    await page.getByRole('tab', { name: 'Map' }).click()

    const region = page.getByRole('region', { name: 'Trail map' })
    await expect(region).toBeVisible()
    const box = await region.boundingBox()
    if (box === null) throw new Error('the map region has no box, so it never mounted')

    // A REAL GESTURE, not a camera call: `fromGesture` is what sets the latch,
    // so a programmatic move would leave the plate unfolded at both widths and
    // the test would pass without exercising anything.
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
    await page.mouse.down()
    await page.mouse.move(box.x + box.width / 2 - 140, box.y + box.height / 2 - 90, {
      steps: 14,
    })
    await page.mouse.up()

    // The strip is what the fold costs, so the strip is what this asserts -
    // by its text rather than by the class that hides it, because
    // `visually-hidden` is an implementation of "gone" and the claim is about
    // what a hiker can still read.
    //
    // Lower case on purpose: the plate SHOWS "NO TRAIL TAKEN" because a
    // stylesheet upper-cases it, and `innerText` reports the transform while
    // `toContainText` reads the DOM. Asserting what a probe printed would pin
    // a text-transform rather than the app's words.
    const plate = page.locator('.map-plate')
    await expect(plate).toContainText('No trail taken')
    await expect(plate).toContainText('No GPS fix')
    await expect(plate).not.toHaveClass(/map-plate--folded/)

    // And no door back, because nothing went away. A phone grows one here.
    await expect(page.getByRole('button', { name: /Show the rest|Unfold/i })).toHaveCount(
      0,
    )
  })

  test('states: "see it on the map" keeps the tab here, because the map is already beside it', async ({
    page,
  }) => {
    // THE C5 DEFECT AT ITS OTHER DOOR. e2e/data/desktopMap.spec.ts drives it
    // from a journal row, which needs a position fix and a release; this is
    // the same rule at a door a hermetic build can reach, and the rule is the
    // point: App.tsx's `showMap` is ONE callback every "see it on the map"
    // door reads - "the condition is the tab, not the caller, because it is
    // the tab that says whether the map is visible". A guard written per door
    // is a guard somebody adds a door without.
    //
    // Measured 2026-09-11, the identical drive at both widths: the phone
    // leaves Today for the Map tab, the laptop stays where it is.
    await seedPreferences(page)
    await seedHikerMode(page, 'long')
    await page.goto('/')
    await seedLongHike(page)
    await page.getByRole('tab', { name: 'Today' }).click()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()

    await page.getByRole('button', { name: 'See this day on the map' }).click()

    // THE TAB DID NOT MOVE. On a phone this same press selects Map, because
    // there the map is another screen and not going to it would be a door
    // that did nothing.
    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Map', selected: false })).toBeVisible()
    // And the map is still the thing beside it, rather than a tab away.
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
  })

  test('states: opening the day does not take the map away, where a phone has to give it up', async ({
    page,
  }) => {
    // `hikeWindowHidesMap = hikeWindowOpen && !hikePointOnMap && !isDesktop`.
    // A phone has one screen, so a window over it IS instead of the map; a
    // laptop puts the window beside a map that stays drawn, "which is the
    // ordinary desktop case for placing a point".
    //
    // ASSERTED BY THE HOLD CLASS AND BY REACH, not by the region's role -
    // and that is worth writing down rather than working around, because it
    // is the one asymmetry here: `inert` and `aria-hidden` are applied at
    // BOTH widths (App.tsx passes `hikeWindowOpen && !hikePointOnMap` to
    // them, without the width), so `getByRole` finds no map at either width
    // and a role-based assertion would pass for the wrong reason.
    //
    // Measured 2026-09-11, the identical drive: the phone gets
    // `app__map-held`, the laptop does not.
    await seedPreferences(page)
    await seedHikerMode(page, 'long')
    await page.goto('/')
    await seedLongHike(page)
    await page.getByRole('tab', { name: 'Today' }).click()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()

    await page.getByRole('button', { name: 'Open the day' }).click()
    await expect(page.getByRole('heading', { name: /\d/ }).first()).toBeVisible()

    await expect(page.locator('.app__map-held')).toHaveCount(0)
    await expect(page.locator('.map-screen').first()).toBeVisible()
  })

  test('states: the map header carries no mode read-out here, because the sidebar holds it', async ({
    page,
  }) => {
    // The other half of the mode test above, which asserted the sidebar's
    // radiogroup and called itself "not a chip in the tab row" without ever
    // checking the row. `modeReadout = isDesktop ? {} : { mode, onOpenMode }`
    // in App.tsx: the phone's map header carries the mode and a door into the
    // switch, and the laptop's does not because the sidebar's radiogroup is
    // already the one home for it.
    //
    // TWO HOMES IS THE DEFECT, not one missing. A mode showing in both places
    // can disagree with itself the moment one of them is switched, and would
    // look entirely correct in a screenshot of either.
    await seedPreferences(page)
    await seedHikerMode(page, 'day')
    await page.goto('/')
    await page.getByRole('tab', { name: 'Map' }).click()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()

    // The sidebar's block is the home, and it is a radiogroup rather than a
    // door into a sheet - a laptop has the room to show the choice itself.
    await expect(page.getByRole('radiogroup', { name: /Today I.m/ })).toBeVisible()

    // And the header's door is absent. Measured 2026-09-11: the phone draws
    // exactly one such button here and the laptop none.
    await expect(page.getByRole('button', { name: /^Day hike$/i })).toHaveCount(0)
  })

  test('states: the band along the map\u2019s foot is a phone\u2019s, and the chart replaces it here', async ({
    page,
  }) => {
    // `{!isDesktop && (<div className="next-up-band">…)}` in
    // chrome/MapScreen.tsx: "above the breakpoint the full chart below
    // replaces the ribbon, and the rail's cards would double the chart's own
    // annotations."
    //
    // The band is UNCONDITIONAL on a phone - it carries the map's credit even
    // with no profile downloaded, "because the credit may not depend on
    // whether a profile happened to download" - so its absence here is a
    // width fork and not an empty-data state. That is why this can be
    // hermetic at all: with nothing downloaded the phone still draws one.
    //
    // Measured 2026-09-11, nothing downloaded: the phone draws one band, the
    // laptop none. The credit it carries is not lost - the first test in this
    // file pins it inline on the map instead.
    await seedPreferences(page)
    await seedHikerMode(page, 'day')
    await page.goto('/')
    await page.getByRole('tab', { name: 'Map' }).click()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()

    await expect(page.locator('.next-up-band')).toHaveCount(0)
  })
})

/**
 * THE PHONE SIDE OF TWO OF THE FORKS ABOVE, and the only untagged describe in
 * this file — so the phone project runs it and the desktop project greps it
 * out, which is the pairing it exists to be.
 *
 * WHY IT EXISTS AT ALL. Two of the assertions above are `toHaveCount(0)` on a
 * CLASS rather than on a role: `app__map-held`, which has no accessible name
 * because it is a visual hold, and `next-up-band`, which is a container. A
 * class-based absence is the one assertion shape that goes green when somebody
 * RENAMES the thing — the locator matches nothing, the expectation passes, and
 * the fork it was guarding is unguarded from then on without a single test
 * going red.
 *
 * `next-up-band` was already safe by accident: chrome/MapScreen.test.tsx
 * asserts it exists in the phone render, so a rename reds that. `app__map-held`
 * was asserted NOWHERE as present — `grep -rn app__map-held` found it in
 * App.tsx, App.css and one absence assertion — so a rename would have made the
 * desktop test permanently vacuous. This is the positive control that stops
 * that, and it doubles as the phone behaviour the desktop test contrasts with.
 */
test.describe('what the phone does with the same two doors', () => {
  test('states: a hike window takes the map on a phone, which is the fork the laptop tests measure against', async ({
    page,
  }) => {
    await seedPreferences(page)
    await seedHikerMode(page, 'long')
    await page.goto('/')
    await seedLongHike(page)
    await page.getByRole('tab', { name: 'Today' }).click()
    await page.getByRole('button', { name: 'Open the day' }).click()
    await expect(page.getByRole('heading', { name: /\d/ }).first()).toBeVisible()

    // The class the laptop test asserts the ABSENCE of. One here, none there.
    await expect(page.locator('.app__map-held')).toHaveCount(1)
  })

  test('states: the band along the map’s foot is drawn here, with nothing downloaded', async ({
    page,
  }) => {
    await seedPreferences(page)
    await seedHikerMode(page, 'day')
    await page.goto('/')
    await page.getByRole('tab', { name: 'Map' }).click()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()

    // Unconditional on a phone — the band carries the map's credit even with
    // no profile, which is why the laptop's `toHaveCount(0)` is a width fork
    // and not an empty-data state.
    await expect(page.locator('.next-up-band')).toHaveCount(1)
  })
})
