// The controls INSIDE More's pages and the legend's foot - the second half of
// F13 in features/FLOW_TESTING.md's battery, and the first half of "The
// download".
//
// WHY A SECOND FILE RATHER THAN MORE TESTS IN more.spec.ts. That file's claim
// is about doors: each of More's five rows opens its page and the page can be
// left. This one is about what is behind the doors - a picker that has to
// remember, a pace that has to move a printed estimate, a provenance section
// that has to say nothing rather than say an empty something. Different claim,
// different fixtures, and one file per claim keeps a failure legible.
//
// ENTRANCE. Every control here is reached by tapping to it: the tab bar, then
// More's row, or the map's Legend button. No navigator state is injected
// (FLOW_TESTING.md, "Not a router") and no screen is mounted directly.
//
// STATES. The axis that matters for a settings control is whether the choice
// survives - so each one that writes a preference is asserted against a COLD
// BOOT rather than a reload, for the reason support/seed.ts's bootFreshPage()
// documents at length: `addInitScript` re-runs on reload and whole-record-puts
// the seed back over whatever the app saved, so a reload would assert that the
// seed survived and pass with the feature broken.
//
// THE DATA AXIS, AND WHAT THIS SUITE HONESTLY HAS. This suite does not reach
// the bucket (playwright.config.ts's own note, FLOW_TESTING.md's boundaries),
// so the phone under test holds no published data and no steward list. That is
// not a gap to work around here - it is one of the states the battery asks
// about, and it is the state a hiker is in before their first download. So the
// provenance and download claims below are claims about the EMPTY phone, named
// as such, and the full-phone half stays `planned` rather than being faked.

import { test, expect, type Page } from '@playwright/test'
import { seedPreferences, bootFreshPage } from './support/seed'

/** Past first run, on More's home. The same entrance more.spec.ts uses, and
 *  deliberately the same shape: a spec that reached these pages a different
 *  way would be testing a door this app does not ship. */
async function openMore(page: Page): Promise<void> {
  await seedPreferences(page)
  await page.goto('/')
  await page.getByRole('tab', { name: 'More' }).click()
  await expect(page.getByRole('heading', { name: 'More', exact: true })).toBeVisible()
}

/** More's row, not the storage card above it or the page bar below - the same
 *  narrowing more.spec.ts makes, for the same collisions. */
function moreRow(page: Page, name: string) {
  return page.locator('.more__row').filter({ hasText: name }).first()
}

/** More → "The map", which is where both of this page's pickers live: the map
 *  detail level (screens/MapDetailPicker.tsx, inside MapSettings) and the pace
 *  profile (screens/PaceSettings.tsx, put here because a pace is a speed and
 *  reads in the unit picker's units). */
async function openTheMapPage(page: Page): Promise<void> {
  await openMore(page)
  await moreRow(page, 'The map').click()
  await expect(page.getByRole('heading', { name: /^the map$/i })).toBeVisible()
}

/** The legend, whose foot carries the background picker and the only door to
 *  the download window. Exact, for the reason mapChrome.spec.ts gives:
 *  "Legend" is a substring of "Close legend". */
async function openLegend(page: Page) {
  await seedPreferences(page)
  await page.goto('/')
  await page.getByRole('tab', { name: 'Map' }).click()
  await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
  await page.getByRole('button', { name: 'Legend', exact: true }).click()
  const legend = page.getByRole('dialog', { name: 'Legend' })
  await expect(legend).toBeVisible()
  return legend
}

/**
 * Clicks a radio by its VISIBLE label, not by `check()` on the input.
 *
 * Every picker in this build hides its input under the label that styles it,
 * so the label intercepts the pointer and `check()` times out waiting for an
 * element the hiker can never hit either. Tapping the label is what a thumb
 * does; asserting `toBeChecked()` afterwards is what proves the tap landed on
 * the control rather than on decoration.
 */
async function pick(scope: ReturnType<Page['locator']>, label: string): Promise<void> {
  await scope.getByText(label, { exact: true }).click()
  await expect(scope.getByRole('radio', { name: new RegExp(`^${label}`) })).toBeChecked()
}

test.describe('the controls behind More’s rows', () => {
  test('states: the map-detail picker opens on the shipped Standard and the choice survives a cold boot', async ({
    page,
  }) => {
    await openTheMapPage(page)

    // The group names itself, which is what makes three one-word options
    // ("Full", "Standard", "Minimal") mean anything on a screen that also
    // carries a background picker and a theme picker.
    const detail = page.getByRole('group', { name: 'Map detail' })
    await expect(detail).toBeVisible()
    // The shipped default is STANDARD, not Full - `layer_detail_level:
    // 'standard'` in lib/userPreferences.ts's DEFAULT_PREFERENCES. Asserted
    // rather than assumed, and this spec asserted Full first and was wrong:
    // a picker opening on a different level than the map is drawing would be
    // a lie about what the hiker is looking at, in either direction.
    await expect(detail.getByRole('radio', { name: /^Standard/ })).toBeChecked()

    await pick(detail, 'Minimal')

    // The description under the options is part of the control: MapDetailPicker
    // names what STAYS at each level rather than what goes, deliberately, so
    // the level a cautious hiker wants does not read as "less map".
    await expect(detail.getByText(/essentials/i).first()).toBeVisible()

    const second = await bootFreshPage(page)
    await second.getByRole('tab', { name: 'More' }).click()
    await second.locator('.more__row').filter({ hasText: 'The map' }).first().click()
    await expect(
      second.getByRole('group', { name: 'Map detail' }).getByRole('radio', {
        name: /^Minimal/,
      }),
    ).toBeChecked()
    await second.close()
  })

  test('states: pace opens at the standard rule, and offers no reset until there is something to undo', async ({
    page,
  }) => {
    await openTheMapPage(page)

    const pace = page.getByRole('region', { name: 'Pace' })
    await expect(pace).toBeVisible()
    // The three controls the screen ships, each named. Their VALUES are not
    // pinned: they are unit-dependent and the standard is a constant this spec
    // would be restating rather than checking (TESTING.md's rule).
    await expect(pace.getByLabel('Flat pace')).toBeVisible()
    await expect(pace.getByLabel('Climbing penalty')).toBeVisible()
    await expect(pace.getByLabel('Descent penalty')).toBeVisible()

    // The preview is the whole point of the screen - a number a hiker can
    // recognize as theirs - so it is present from the first frame rather than
    // after a change.
    await expect(pace.getByText('Your estimates now read')).toBeVisible()

    // At the standard pace there is nothing to undo, and the reset is ABSENT
    // rather than disabled (D10). This is the assertion that would catch it
    // being shown always, which is what invites fiddling with a number a
    // hiker has no reason to move.
    await expect(pace.getByRole('button', { name: 'Reset to standard' })).toHaveCount(0)
  })

  test('states: moving the flat pace changes the printed estimate, and reset puts it back', async ({
    page,
  }) => {
    await openTheMapPage(page)
    const pace = page.getByRole('region', { name: 'Pace' })

    // The sentence before, read off the screen rather than computed here: the
    // claim is that the preview FOLLOWS the slider, and computing the expected
    // minutes would be re-implementing paceEstimate() in the test.
    const preview = pace.locator('.settings__preview-time')
    const standardText = await preview.innerText()

    // A range input is the one control a thumb cannot be simulated onto
    // usefully - a click lands at a pixel, which is a different value on a
    // different viewport. The keyboard is the accessible path the app ships
    // and the one a test can state exactly: focus, then arrow.
    const flat = pace.getByLabel('Flat pace')
    await flat.focus()
    for (let i = 0; i < 4; i += 1) await flat.press('ArrowRight')

    // Wait on the preview having CHANGED, not on a timeout: React re-renders
    // on the change event, and asserting the new text is what proves the
    // sequence finished (FLOW_TESTING.md's ordering rule).
    await expect(preview).not.toHaveText(standardText)

    // Now there is something to undo, so the reset appears - the other half of
    // the previous test's absence claim.
    const reset = pace.getByRole('button', { name: 'Reset to standard' })
    await expect(reset).toBeVisible()
    await reset.click()

    await expect(preview).toHaveText(standardText)
    await expect(reset).toHaveCount(0)
  })

  test('states: a row that is not built yet is shown, tagged Later and disabled — not hidden', async ({
    page,
  }) => {
    // WIREFRAMES.md's explicit instruction, and the one place this build
    // deliberately breaks D10's "absent rather than disabled". The argument
    // is in Settings.tsx: "a visible, dimmed row answers the question 'can I
    // do this at all?' honestly, where a missing one leaves someone hunting
    // through every screen for it."
    //
    // Worth a test rather than a comment because the two rules point opposite
    // ways, and the next person to apply D10 across the settings screens would
    // delete these rows believing they were tidying up.
    await openMore(page)
    await moreRow(page, 'Safety & privacy').click()
    await expect(page.getByRole('heading', { name: /^safety & privacy$/i })).toBeVisible()

    const later = page.locator('.settings__row--later').filter({
      hasText: 'Hide my name on reports for',
    })
    await expect(later).toBeVisible()
    await expect(later.getByText('Later', { exact: true })).toBeVisible()
    // Disabled, and the control is really there rather than a picture of one -
    // which is what makes "can I do this at all?" answerable by looking.
    await expect(later.getByRole('checkbox')).toBeDisabled()
  })

  test('states: an empty phone says nothing about provenance rather than an empty something', async ({
    page,
  }) => {
    // THE HONEST CLAIM THIS SUITE CAN MAKE. chrome/SourcesSection.tsx returns
    // null on an empty steward list, deliberately - "a bordered section with
    // nothing in it reads as a rendering fault" - and this suite's phone has
    // downloaded nothing, so this is that state rather than a contrivance.
    // The full-phone half (one card per organization, licence and attribution
    // verbatim) needs published data and stays `planned`.
    await openMore(page)
    await moreRow(page, 'Where this map comes from').click()
    await expect(page.getByRole('heading', { name: /^your data$/i })).toBeVisible()

    await expect(
      page.getByRole('heading', { name: 'Where this map comes from' }),
    ).toHaveCount(0)
    await expect(page.getByText(/sets its own licence/)).toHaveCount(0)

    // And the page is not empty because of it: the build is still named, which
    // is what a bug report has to carry (#626), so the absence above is one
    // section declining rather than the page failing to render.
    await expect(page.getByRole('heading', { name: /^about this build$/i })).toBeVisible()
  })
})

test.describe('the legend’s foot, and the door to the download', () => {
  test('states: with no raster archive there is no background choice, and no label pretending to be one (#855)', async ({
    page,
  }) => {
    // NOT THE TEST THIS STARTED AS. It asserted a two-option picker at the
    // foot of the legend and failed, because chrome/BackgroundPicker.tsx
    // returns null on `!offlineBackgroundAvailable` and the raster build was
    // withdrawn (#855) - so there is no second background to choose and the
    // control is gone rather than stuck on one option. The build is right and
    // the assumption was wrong, so the claim is the absence, with the reason
    // named: "a segmented pair with one segment left in it is not a choice;
    // it is a label that looks like a control."
    //
    // WHAT THIS GUARDS. Re-enabling the picker without an archive to back it
    // puts the word "Background" over a decision a hiker does not have, and
    // the only reachable override tells them to "download the map and this
    // setting takes effect" - which stopped being true when the sheet went.
    // That regression is invisible in a screenshot and fails here.
    const legend = await openLegend(page)

    await expect(legend.getByRole('group', { name: 'Background' })).toHaveCount(0)
    await expect(legend.getByText('Live topo')).toHaveCount(0)
    await expect(legend.getByText('Downloaded')).toHaveCount(0)

    // The foot is not empty because of it: the download door is the other
    // half of that block, and it is still there. So the absence above is one
    // control declining rather than the whole foot failing to render.
    await expect(
      legend.getByRole('button', { name: /^Choose what to download/ }),
    ).toBeVisible()
  })

  test('entrance and exit: the download window opens from the legend’s only door, and closes', async ({
    page,
  }) => {
    const legend = await openLegend(page)

    // The label, not a generic "Downloads": DownloadsLink says "Choose what to
    // download" on a phone with nothing on it and "Change what's downloaded"
    // on one that has some. Asserting the first is a claim about THIS phone's
    // state as well as about the door.
    const door = legend.getByRole('button', { name: /^Choose what to download/ })
    await expect(door).toBeVisible()
    await door.click()

    const window_ = page.getByRole('dialog', { name: 'Offline map' })
    await expect(window_).toBeVisible()

    // AND THE LEGEND IS GONE, not stacked under it. App.tsx's openDownloads()
    // sets the window open and the legend shut in the same callback, with the
    // selected waypoint cleared - one panel over the map at a time. This spec
    // asserted the legend survived and was wrong; the build's answer is the
    // better one, and worth pinning: two stacked sheets on a 390px phone is
    // the room problem the whole shell is built to avoid.
    await expect(legend).toHaveCount(0)

    // A window with no way out is the regression rule 2 exists for, and this
    // one is a dialog over the map rather than a screen in the stack - so its
    // exit is its own Close, not the tab bar.
    await window_.getByRole('button', { name: 'Close' }).click()
    await expect(window_).toHaveCount(0)
    // It lands back on the map, which is where it was opened from - not on
    // the legend, which the open already shut.
    await expect(page.getByRole('region', { name: 'Trail map' })).toBeVisible()
  })
})

test.describe('the download window, on a phone holding nothing', () => {
  /** The window, from the map's legend - which is the ONLY door to it since
   *  the Downloads tab went (chrome/tabs.ts, chrome/DownloadsLink.tsx). */
  async function openDownloadWindow(page: Page) {
    const legend = await openLegend(page)
    await legend.getByRole('button', { name: /^Choose what to download/ }).click()
    const window_ = page.getByRole('dialog', { name: 'Offline map' })
    await expect(window_).toBeVisible()
    return window_
  }

  test('states: the window says what the download is for, and offers it', async ({
    page,
  }) => {
    const window_ = await openDownloadWindow(page)

    // The scope sentence is the phone's, not the desktop's - this project runs
    // at 390x844 (playwright.config.ts) and the two sentences say different
    // things about WHY somebody would download: "the map works with no signal"
    // against "the download is for the phone you'll actually be carrying".
    // Getting the desktop copy here would mean useDesktop.ts's breakpoint had
    // matched, which is the bug that once made every spec in this suite run in
    // the wrong layout.
    await expect(window_.getByText(/the map works with no signal/i)).toBeVisible()
    await expect(window_.getByText(/phone you.ll actually be carrying/i)).toHaveCount(0)

    // The offer itself. "Download the map", not "Delete the map": nothing is
    // on this phone, and DownloadCard.tsx words the control from what is
    // actually there rather than from a fixed label.
    await expect(window_.getByRole('button', { name: /^Download the map/ })).toBeVisible()
    await expect(window_.getByRole('button', { name: /^Delete the map/ })).toHaveCount(0)
  })

  test('states: every trail-data row is answered for, including the ones that are not here', async ({
    page,
  }) => {
    const window_ = await openDownloadWindow(page)

    // THE CLAIM IS THE WHOLE LIST, PRESENT OR NOT. Downloads.tsx renders every
    // artifact row whatever the store holds - "a missing row would be an
    // artifact this window forgot to answer for" - and the four names are the
    // hiker-facing ones from TRAIL_DATA_LABEL, not the pipeline's.
    const trailData = window_.getByTestId('downloads-trail-data')
    await expect(trailData).toBeVisible()
    await expect(trailData.getByText('Trail data on this phone')).toBeVisible()

    for (const name of [
      'Trail line',
      'Waypoints',
      'Elevation profile',
      'Nearby trails, zoomed out',
    ]) {
      await expect(trailData.getByText(name, { exact: true })).toBeVisible()
    }

    // And the note that makes the list readable rather than alarming: these
    // arrive on their own, so four rows saying "not here" on a phone with no
    // signal is a status and not a list of things to go and press.
    await expect(trailData.getByText(/nothing here to press/i)).toBeVisible()
  })
})
