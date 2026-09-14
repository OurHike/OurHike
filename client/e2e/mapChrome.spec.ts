// The map's chrome - the legend's switches, the "In view" door, and the
// search panel. F12 in features/FLOW_TESTING.md's battery, minus the parts
// that need published waypoint data.
//
// NOT THE MAP'S ROOM. e2e/mapRoom.spec.ts already measures what the legend
// leaves the map and drives the sheet's open and close against those floors.
// This file opens the legend only to reach the controls inside it, and asserts
// nothing about how much map is left.
//
// ENTRANCE. Two buttons in the map header (chrome/Header.tsx) are the only
// shipped doors to either panel, and there is no URL to type
// (FLOW_TESTING.md, "Not a router"): the Map tab, then Legend, or the Map tab,
// then Search. A third door - "In view · N" - is the one this environment does
// not get, and its absence is asserted rather than assumed (below).
//
// EXIT. The legend closes on its own "Close legend"; the search panel has two
// exits and both are driven, because Search.tsx built the second one
// deliberately (#315: "the panel covers the map opaquely and its only other
// exit was the Cancel button, which on a phone means finding a target with a
// thumb").
//
// STATES.
//
//  - **The three switches**, each asserted at the default this build ships -
//    Alerts on, Verified? off, Drought off - before anything is toggled. A
//    persistence test that starts from the value it ends on proves nothing,
//    and neither does a toggle test.
//  - **What a toggle reaches.** Alerts is the switch with something to see:
//    the legend's own safety rows re-tag themselves and the map's status strip
//    prints "Alerts hidden" (chrome/StatusStrip.tsx). That is the mechanism -
//    the panel and the map agreeing about the canvas - rather than a number.
//  - **What each switch is allowed to remember**, which is a safety claim
//    rather than a preference one. chrome/alertLayerPanel.ts keeps the alert
//    flag in `useState` on the maintainer's constraint for #1047 ("the map
//    should always open to the alerts being shown"), while
//    chrome/waypointFiltersPanel.ts writes the drought tint through the stored
//    preferences. A cold boot is what tells those two apart, so a cold boot is
//    what this asserts - through bootFreshPage(), for the reload trap
//    support/seed.ts documents.
//  - **Data freshness: which absence.** This environment publishes no
//    waypoints, so both no-data sentences are reachable and they are not the
//    same sentence. Below the pin seam the panel says the app is declining to
//    draw ("Waypoints appear from a closer zoom."); above it, that there is
//    nothing here to draw ("No waypoints on this part of the map yet"). The
//    remedies differ, so the spec asserts the sentence and not the zero beside
//    it. The live branch needs the fixture #1387 tracks.
//  - **D10, absent rather than disabled.** No waypoints drawn means no "In
//    view" door at all, at either zoom - chrome/MapScreen.tsx gates it on
//    `pointsShown.length > 0`. The two doors that ARE there are asserted in
//    the same breath, so "In view is absent" cannot pass on a header that
//    failed to render.
//
// MODE IS NOT AN AXIS HERE, and that is a claim rather than an omission. None
// of chrome/Legend.tsx, chrome/Header.tsx or chrome/Search.tsx reads
// lib/hikerMode.ts - Search.tsx's own header says the places index is "offered
// on every mode for lib/hikerMode.ts's reason (a mode never hides a feature)"
// - so one mode covers all three. Volunteer's own map chrome is the workday
// window (F14), which is a different screen and a different spec.

import { test, expect, type Page } from '@playwright/test'
import {
  seedPreferences,
  bootFreshPage,
  seedCamera,
  ON_THE_TRAIL,
  ABOVE_THE_SEAM_ZOOM,
} from './support/seed'
import { writeIDBEntries } from './support/idb'
// Untyped on purpose: a shot fixture is plain JavaScript, and its shape is the
// app's contract with IndexedDB rather than a type this spec restates.
import { DAY_HIKES } from '../preview-shots/fixtures/dayHike.mjs'

/**
 * On the map tab, past first run.
 *
 * The entrance every test here starts from, and it is a real tap: boot, then
 * the tab bar. Waits on the map's own region rather than on the tab being
 * selected, because every control this file drives is drawn inside that
 * region's chrome and none of it exists until the screen has mounted.
 */
async function openMap(page: Page): Promise<void> {
  await seedPreferences(page)
  await page.goto('/')
  await page.getByRole('tab', { name: 'Map' }).click()
  await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
}

/**
 * A camera above the pin seam, on the A.T. near the Smokies.
 *
 * The seed itself lives in support/seed.ts, where e2e/data/mapSheets.spec.ts
 * reads the same two constants — one answer to "where does the suite look",
 * rather than two specs each picking their own point on the same trail.
 */
async function rememberCameraOnTheTrail(page: Page): Promise<void> {
  await seedCamera(page, ON_THE_TRAIL, ABOVE_THE_SEAM_ZOOM)
}

/** The phone's legend is a dialog; the desktop's persistent panel is a region
 *  and this suite has no desktop project (FLOW_TESTING.md's device axis). */
function legendOf(page: Page) {
  return page.getByRole('dialog', { name: 'Legend' })
}

async function openLegend(page: Page) {
  // Exact: "Legend" is a substring of "Close legend", so the ordinary
  // substring match resolves to both once the sheet is up.
  await page.getByRole('button', { name: 'Legend', exact: true }).click()
  const legend = legendOf(page)
  await expect(legend).toBeVisible()
  return legend
}

test.describe('the map’s chrome', () => {
  test('entrance and exit: the legend’s three switches open on their shipped defaults, and go away with the sheet', async ({
    page,
  }) => {
    await openMap(page)
    const legend = await openLegend(page)

    // Unlike the settings radios (e2e/more.spec.ts), these inputs are real
    // 13x13 checkboxes a finger can land on - measured through
    // getBoundingClientRect while writing this - so the control itself is
    // both what is clicked and what is asserted. Their accessible names come
    // from the wrapping <label>, which is why each is anchored: the alerts
    // label folds its whole explanatory sentence into its name.
    const verified = legend.getByRole('checkbox', { name: /Verified/ })
    const alerts = legend.getByRole('checkbox', { name: /^Alerts/ })
    const drought = legend.getByRole('checkbox', { name: /^Drought/ })

    // The defaults this build ships, each with a decision behind it:
    // alerts on every launch (chrome/alertLayerPanel.ts, #1047), Verified?
    // off because "an unconfirmed spring is still the best information
    // anyone has" (chrome/waypointFiltersPanel.ts), drought off
    // (lib/userPreferences.ts's DEFAULT_PREFERENCES).
    await expect(alerts).toBeChecked()
    await expect(verified).not.toBeChecked()
    await expect(drought).not.toBeChecked()

    // Verified? is live, and its own state is ALL that can be asserted here:
    // the filter has nothing to filter, so no count and no sentence on this
    // panel moves with it. What would settle whether it actually withholds
    // anything is published waypoint data (#1387), not a longer wait.
    await verified.click()
    await expect(verified).toBeChecked()
    await verified.click()
    await expect(verified).not.toBeChecked()

    // And the sheet lets go of them. Asserted on the switches rather than on
    // the sheet, because this test's subject is the controls: a legend that
    // closed while leaving its checkboxes in the tree would leave a hiker
    // able to toggle a safety layer through a panel they cannot see.
    await page.getByRole('button', { name: 'Close legend' }).click()
    await expect(alerts).toHaveCount(0)
    await expect(verified).toHaveCount(0)
    await expect(drought).toHaveCount(0)
  })

  test('states: turning Alerts off is said by the legend’s safety rows and by the map’s own strip, both ways', async ({
    page,
  }) => {
    await openMap(page)
    const legend = await openLegend(page)
    const alerts = legend.getByRole('checkbox', { name: /^Alerts/ })

    // The closure and serious-warning rows are a key rather than a tally
    // (#1051) and carry no count in any state, so their TAG is what moves.
    // Two of them, and the count is the assertion: a row that stopped
    // agreeing with the switch would be the panel contradicting the canvas
    // beside it, which Legend.tsx's header calls the one thing a legend may
    // never do. Case-insensitive because the tag is upper-cased by CSS.
    await expect(legend.getByText(/^alerts$/i)).toHaveCount(2)
    await expect(page.getByText('Alerts hidden')).toHaveCount(0)

    await alerts.click()

    await expect(alerts).not.toBeChecked()
    await expect(legend.getByText(/^alerts off$/i)).toHaveCount(2)
    // chrome/StatusStrip.tsx, on the plate above the sheet: the map saying
    // for itself that ink is missing, which is what keeps the hide from
    // being silent once the legend is shut.
    await expect(page.getByText('Alerts hidden')).toBeVisible()

    // Back on, which is the branch that matters most: a switch that cannot
    // be undone has taken the marks away for good.
    await alerts.click()

    await expect(alerts).toBeChecked()
    await expect(legend.getByText(/^alerts$/i)).toHaveCount(2)
    await expect(page.getByText('Alerts hidden')).toHaveCount(0)
  })

  test('states: the drought tint is remembered across a cold boot and the alerts switch deliberately is not', async ({
    page,
  }) => {
    // The two halves of #1047's constraint, which only a restart can tell
    // apart. Both switches look identical on the panel; one is a stored
    // preference and the other is `useState` on purpose, and the difference
    // is the whole reason a control over a safety layer was allowed to exist
    // at all.
    await openMap(page)
    const legend = await openLegend(page)

    await legend.getByRole('checkbox', { name: /^Drought/ }).click()
    await legend.getByRole('checkbox', { name: /^Alerts/ }).click()
    await expect(legend.getByRole('checkbox', { name: /^Drought/ })).toBeChecked()
    await expect(legend.getByRole('checkbox', { name: /^Alerts/ })).not.toBeChecked()
    // Observable proof the alert flip reached the map itself before anything
    // is restarted - the strip is fed from the same state the next boot is
    // being asked about.
    await expect(page.getByText('Alerts hidden')).toBeVisible()

    // NOT page.reload(): support/seed.ts's init script re-runs on every
    // navigation and whole-record-puts the seeded preferences over whatever
    // the app has saved since, so a reload would assert the seed survived.
    // A sibling page shares the context's IndexedDB and carries no init
    // scripts - the app booting cold onto the store as the hiker left it.
    const rebooted = await bootFreshPage(page)
    try {
      await rebooted.getByRole('tab', { name: 'Map' }).click()
      await expect(rebooted.getByRole('region', { name: 'Trail map' })).toBeVisible()
      await rebooted.getByRole('button', { name: 'Legend', exact: true }).click()
      const second = legendOf(rebooted)
      await expect(second).toBeVisible()

      await expect(second.getByRole('checkbox', { name: /^Drought/ })).toBeChecked()
      // The map opens on the alerts. Asserted positively rather than as the
      // absence of a hide, so a boot that failed cannot pass this.
      await expect(second.getByRole('checkbox', { name: /^Alerts/ })).toBeChecked()
      await expect(rebooted.getByText('Alerts hidden')).toHaveCount(0)
      // Verified? is ephemeral too, and for a different reason: #530 moved
      // the category filter into storage and left this one out.
      await expect(second.getByRole('checkbox', { name: /Verified/ })).not.toBeChecked()
    } finally {
      await rebooted.close()
    }
  })

  test('states: the drought row says its week is not available, rather than that there is none', async ({
    page,
  }) => {
    // The absent branch of the data-freshness axis, on the one row whose
    // numbers ARE its content. Nothing published reaches this environment, so
    // there is no week - and Legend.tsx's own rule is that a missing week
    // must not be reported as a dry-free one: "the pipeline publishes an
    // EMPTY band set precisely so that a genuinely dry-free week can say so,
    // and that case still has a week". The two sentences are one character
    // apart in effort and a world apart in what they claim, which is why this
    // asserts the absence of the reassuring one as well.
    await openMap(page)
    const legend = await openLegend(page)

    await expect(legend.getByText('not available')).toBeVisible()
    await expect(legend.getByText(/none on the trail/)).toHaveCount(0)
    await expect(legend.getByText(/affected · week of/)).toHaveCount(0)
  })

  test('states: below the pin seam the legend says waypoints appear from a closer zoom, and the In view door is absent for want of points rather than zoom (D10)', async ({
    page,
  }) => {
    // The camera the app opens on is the whole corridor, which is below
    // map/poiLayers.ts's POI_PIN_MIN_ZOOM. Legend.tsx checks this first "so
    // the true sentence wins over the general one", and the two sentences
    // have opposite remedies - zoom in, versus there is nothing here - so the
    // spec asserts which one is printed rather than the zeros beside it.
    await openMap(page)

    // The door D10 says must be absent rather than dead, with the two that
    // are present asserted beside it: chrome/MapScreen.tsx offers "In view"
    // only where `pointsShown.length > 0`, and a header that failed to draw
    // at all would otherwise pass this.
    //
    // THE SEAM DOES NOT GATE THIS DOOR, and the title used to read as though
    // it did. The gate is `pointsShown.length > 0 && !buildingDayHike &&
    // !isDesktop` — no zoom term anywhere in it — so the door is missing here
    // because this suite's phone holds no waypoints at all, not because the
    // camera is out at the corridor. Measured against the published preview
    // at the same z7 camera on UA's data (2026-09-11): the header reads
    // "IN VIEW · 906". A reader who took the old title at face value would
    // have believed the opposite of what the build does. The test below is
    // the half that proves the real rule, by finding the door still absent at
    // a zoom where pins WOULD be drawn.
    await expect(page.getByRole('button', { name: /In view/ })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Legend', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Search', exact: true })).toBeVisible()

    const legend = await openLegend(page)
    await expect(legend.getByText('Waypoints appear from a closer zoom.')).toBeVisible()
    await expect(
      legend.getByText(/No waypoints on this part of the map yet/),
    ).toHaveCount(0)
  })

  test('states: above the seam the legend says there is nothing here, Verified? cannot change which absence that is, and In view is still absent', async ({
    page,
  }) => {
    await seedPreferences(page)
    await rememberCameraOnTheTrail(page)
    await page.goto('/')
    await page.getByRole('tab', { name: 'Map' }).click()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()

    const legend = await openLegend(page)
    await expect(
      legend.getByText(
        'No waypoints on this part of the map yet — pan or zoom out to see more.',
      ),
    ).toBeVisible()
    await expect(legend.getByText(/Waypoints appear from a closer zoom/)).toHaveCount(0)

    // The panel's third no-data sentence, and the one that would be a lie
    // here: "Nothing here has been confirmed yet — turn Verified? off to see
    // what is reported" promises pins behind the filter, and there are none
    // to promise. It is gated on points existing and being filtered out
    // rather than on the filter being on, so turning the filter on must not
    // summon it. That distinction is exactly the kind a screen loses quietly.
    await legend.getByRole('checkbox', { name: /Verified/ }).click()
    await expect(legend.getByRole('checkbox', { name: /Verified/ })).toBeChecked()
    await expect(legend.getByText(/Nothing here has been confirmed yet/)).toHaveCount(0)
    await expect(
      legend.getByText(
        'No waypoints on this part of the map yet — pan or zoom out to see more.',
      ),
    ).toBeVisible()

    // Still no door, at a zoom where pins WOULD be drawn - which is the
    // stronger half of the D10 claim: the door is absent because nothing is
    // drawn, not because the camera is too far out.
    await page.getByRole('button', { name: 'Close legend' }).click()
    await expect(page.getByRole('button', { name: /In view/ })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Legend', exact: true })).toBeVisible()
  })

  test('entrance and exit: search opens from the map header, refuses a name it cannot serve, and Cancel closes it', async ({
    page,
  }) => {
    await openMap(page)
    await page.getByRole('button', { name: 'Search', exact: true }).click()

    const box = page.getByRole('searchbox', { name: 'Search the downloaded map' })
    await expect(box).toBeVisible()

    // What the box PROMISES is a state: Search.tsx names parks and towns only
    // where a places index is on the phone, because "a placeholder promising
    // what the box cannot find is a refusal dressed as a door (D10)". This
    // phone holds none, so the placeholder must not say parks.
    await expect(box).toHaveAttribute('placeholder', 'Search shelters, water, towns')
    // And no verdict before there is a query to judge - an empty panel is not
    // the same claim as "nothing by that name".
    await expect(page.getByText(/Nothing here by that name/)).toHaveCount(0)

    await box.fill('katahdin')

    // The sentence, which is the whole design: local-only search that says
    // what to do next rather than "no results". Matched loosely because what
    // is being asserted is that the panel answered, not its wording of the
    // second clause.
    await expect(page.getByText(/Nothing here by that name/)).toBeVisible()
    // Nothing is offered to tap - not an empty list, and no places group.
    await expect(page.getByRole('list', { name: 'Waypoints' })).toHaveCount(0)
    await expect(page.getByRole('heading', { name: 'Places' })).toHaveCount(0)

    await page.getByRole('button', { name: 'Cancel' }).click()
    await expect(box).toHaveCount(0)
    // Back to the map's own header, which is what makes this an exit rather
    // than a panel that merely emptied itself.
    await expect(page.getByRole('button', { name: 'Search', exact: true })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
  })

  test('exit: Escape closes the search panel, which is the exit a thumb cannot miss', async ({
    page,
  }) => {
    // #315 built this second exit on purpose: the panel covers the map
    // opaquely, and with nothing downloaded it is a blank page over the map
    // where "how do I get out of this" is a real question. Driven from the
    // results side of the panel rather than the input, because the handler is
    // on the container for exactly that case.
    await openMap(page)
    await page.getByRole('button', { name: 'Search', exact: true }).click()

    const box = page.getByRole('searchbox', { name: 'Search the downloaded map' })
    await expect(box).toBeVisible()
    await box.fill('katahdin')
    await expect(page.getByText(/Nothing here by that name/)).toBeVisible()

    await box.press('Escape')
    await expect(box).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Search', exact: true })).toBeVisible()
  })
})

/**
 * The door the map raises when a saved walk starts where the hiker is standing
 * (chrome/DayHikesHere.tsx, #1008, storyboard frame D8) — the second way back
 * into a day hike, and the one that matters at 8am with no signal.
 *
 * HERMETIC, WHICH IS WORTH SAYING because this is a map surface and the rest
 * of them are not. `dayHikesNearHere` compares a fix against the walk's own
 * first tapped end and nothing else: no junction graph, no waypoint index, no
 * trail line. So the whole feature is reachable on a phone that has downloaded
 * nothing, which is exactly the phone a hiker has at a trailhead.
 *
 * THE FIX IS A REAL ONE, through Playwright's geolocation rather than a stub,
 * and it is placed at the fixture walk's own start rather than at a coordinate
 * written down here — so the two cannot drift apart when the fixture moves.
 */
test.describe('the day hike that starts where you are', () => {
  /** The fixture's first tapped end, read off the fixture. `lib/dayHikeShelf.ts`
   *  measures to exactly this point, so standing on it is unambiguous. */
  const START = DAY_HIKES.hikes[0].segments[0][0].coord as [number, number]

  test.use({
    permissions: ['geolocation'],
    geolocation: { longitude: START[0], latitude: START[1] },
  })

  async function atTheTrailhead(page: Page): Promise<void> {
    await seedPreferences(page)
    await writeIDBEntries(page, [['ourhike:day-hikes', DAY_HIKES]])
    await page.goto('/')
    await page.getByRole('tab', { name: 'Map' }).click()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
  }

  test('entrance and states: the door offers itself folded, and opens onto the walk it means', async ({
    page,
  }) => {
    await atTheTrailhead(page)

    // FOLDED FIRST. Nobody asked for this — it is the one occupant of the
    // map's lower third that is not the answer to a tap (App.tsx's
    // `lowerThirdTaken` exists to keep it from landing on one) — so it arrives
    // as a line, not as a panel.
    const door = page.getByRole('button', { name: 'A day hike starts here' })
    await expect(door).toBeVisible()

    await door.click()

    const panel = page.getByRole('region', { name: 'Your day hikes near here' })
    await expect(panel).toBeVisible()
    await expect(panel.getByText(/Pine Meadow loop/)).toBeVisible()

    // THE FIGURE SAYS WHAT KIND OF FIGURE IT IS, which is the assertion worth
    // having on this card: "away" is a straight line to the start and not
    // trail walked, and the card says so rather than letting a hiker read it
    // as a walking distance. D14, on a screen where the difference could send
    // somebody the wrong way round a ridge.
    await expect(
      panel.getByText(/straight line to the start, not trail walked/),
    ).toBeVisible()
    await expect(panel.getByText(/[\d.]+ mi away/)).toBeVisible()

    // And a way out to the whole list, so the door is a shortcut rather than
    // the only route to a saved walk.
    await expect(panel.getByRole('button', { name: /All your day hikes/ })).toBeVisible()
  })

  test('states: putting it away clears it for this session, and it offers again on a cold boot', async ({
    page,
  }) => {
    await atTheTrailhead(page)
    await page.getByRole('button', { name: 'A day hike starts here' }).click()

    await page.getByRole('button', { name: /^Put this away/ }).click()
    await expect(
      page.getByRole('region', { name: 'Your day hikes near here' }),
    ).toHaveCount(0)
    await expect(
      page.getByRole('button', { name: 'A day hike starts here' }),
    ).toHaveCount(0)

    // SESSION STATE, DELIBERATELY — the same shape as the welcome-back card's
    // "Leave it". A hiker who waved it away at the car park and came back an
    // hour later is still standing at the start of that walk, so the answer to
    // "is this still true" has not changed. Asserted against a cold boot
    // rather than a reload, for the reason bootFreshPage() documents.
    const rebooted = await bootFreshPage(page)
    try {
      await rebooted.getByRole('tab', { name: 'Map' }).click()
      await expect(
        rebooted.getByRole('button', { name: 'A day hike starts here' }),
      ).toBeVisible()
    } finally {
      await rebooted.close()
    }
  })

  test('states: a walk this phone holds but is nowhere near raises no door at all', async ({
    page,
  }) => {
    // The other side of the radius, and the one that keeps the door honest:
    // `NEAR_START_MILES` is half a mile and `@unvalidated`, so a test that only
    // ever drove the positive case would pass with the radius set to the whole
    // continent. A degree of latitude is about 69 miles from the start.
    await seedPreferences(page)
    await writeIDBEntries(page, [['ourhike:day-hikes', DAY_HIKES]])
    await page.context().setGeolocation({ longitude: START[0], latitude: START[1] + 1 })
    await page.goto('/')
    await page.getByRole('tab', { name: 'Map' }).click()
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()

    // Waits on something that proves the fix landed before claiming the door
    // is absent — otherwise this passes while the app is still looking for GPS
    // and would pass with the feature deleted.
    await expect(page.getByText(/Located/)).toBeVisible()
    await expect(
      page.getByRole('button', { name: 'A day hike starts here' }),
    ).toHaveCount(0)
  })
})
