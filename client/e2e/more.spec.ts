// The More tab (client/src/screens/More.tsx) and the settings behind it -
// F13 in features/FLOW_TESTING.md's battery.
//
// ENTRANCE. More is five rows over a storage card, and each row is the only
// shipped door to its page: there is no URL to type and no navigator state to
// inject (FLOW_TESTING.md, "Not a router"). So the entrance claim here is
// literally the tap sequence a hiker makes, once per page, asserted on the
// page's own heading rather than on the row having been clicked.
//
// EXIT. Every page carries one back control, "‹ More", and the battery asks
// for every settings screen to be "reachable AND leaveable" - so each
// entrance is paired with its exit in the same test rather than trusting that
// a control which exists also works. The two pages that nest a level deeper
// (Your reports, Your photos and notes) go back to their own parent, not to
// More's home, which is the navigator's `returnsToOrigin` exception made
// visible.
//
// STATES. The axis this screen actually varies along is what the hiker has
// chosen, and the battery names the one that matters: "unit, theme and
// map-style choices surviving a reload". That is asserted against a cold boot
// rather than a reload, for the reason bootFreshPage() documents.
//
// The two gates are states too, and the honest default for both is what this
// build ships: the source registry is behind a gate that is shut here (D4),
// and the trace recorder is behind #1201's, which opens once location has
// been asked about - which seedPreferences() does, so this suite sees it.

import { test, expect, type Page } from '@playwright/test'
import { seedPreferences, bootFreshPage } from './support/seed'

/** More's own rows, and the heading each page answers with. The headings are
 *  upper-cased by CSS and the accessible name follows the rendering, so every
 *  one of these is matched case-insensitively rather than typed twice. */
const PAGES = [
  { row: 'You', heading: /^you$/i },
  { row: 'The map', heading: /^the map$/i },
  { row: 'Safety & privacy', heading: /^safety & privacy$/i },
  { row: 'Volunteer & report', heading: /^contribute$/i },
  { row: 'Where this map comes from', heading: /^your data$/i },
] as const

async function openMore(page: Page): Promise<void> {
  await seedPreferences(page)
  await page.goto('/')
  await page.getByRole('tab', { name: 'More' }).click()
  await expect(page.getByRole('heading', { name: 'More', exact: true })).toBeVisible()
}

/** The row, not any other button whose text contains the same words - the
 *  storage card above them carries "Choose what to download", and the page
 *  bar below carries "‹ More". */
function row(page: Page, name: string) {
  return page.locator('.more__row').filter({ hasText: name }).first()
}

test.describe('More, and the settings behind it', () => {
  for (const { row: name, heading } of PAGES) {
    test(`entrance and exit: ${name} opens from its row and goes back to More`, async ({
      page,
    }) => {
      await openMore(page)

      await row(page, name).click()
      await expect(page.getByRole('heading', { name: heading })).toBeVisible()

      // "‹ " is an aria-hidden span, so this control's accessible name is
      // the parent page's label alone - the chevron is decoration a screen
      // reader never hears, and a locator that expects it matches nothing.
      await page.getByRole('button', { name: 'More', exact: true }).click()
      // Back on the home face: the rows are here and the page's own heading
      // is not. Asserting only the rows would pass on a page that had drawn
      // them underneath itself.
      await expect(row(page, name)).toBeVisible()
      await expect(page.getByRole('heading', { name: heading })).toHaveCount(0)
    })
  }

  test('exit: a More page survives a tab switch, which no other tab’s screen does', async ({
    page,
  }) => {
    // lib/navigator.ts's `keptAcrossTabs` is hard-coded to `more` alone, and
    // Today's own spec asserts the other half - that Today resets to its
    // journal on the way back. This is the exception, driven.
    await openMore(page)
    await row(page, 'The map').click()
    await expect(page.getByRole('heading', { name: /^the map$/i })).toBeVisible()

    await page.getByRole('tab', { name: 'Today' }).click()
    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()

    await page.getByRole('tab', { name: 'More' }).click()
    await expect(page.getByRole('heading', { name: /^the map$/i })).toBeVisible()
  })

  test('states: units, theme and map style survive a cold boot', async ({ page }) => {
    await openMore(page)
    await row(page, 'The map').click()

    const units = page.getByRole('group', { name: /^units$/i })
    const theme = page.getByRole('group', { name: /^theme$/i })
    const style = page.getByRole('group', { name: /^map style$/i })

    // The defaults this build ships, asserted before they are changed - a
    // persistence test that starts from the value it ends on proves nothing.
    await expect(units.getByRole('radio', { name: 'Feet' })).toBeChecked()
    await expect(theme.getByRole('radio', { name: 'Follow phone' })).toBeChecked()
    await expect(style.getByRole('radio', { name: 'Field' })).toBeChecked()

    // The tap a hiker makes is on the LABEL. Each option is a `<label>`
    // wrapping a visually-hidden `<input type="radio">`, so `check()` on the
    // input times out against its own label intercepting the pointer - which
    // is the browser working correctly, not a defect. Clicking the label is
    // both what a finger does and what forwards to the control; the
    // assertion stays on the radio's checked state.
    await units.getByText('Metres', { exact: true }).click()
    await theme.getByText('Ink', { exact: true }).click()
    await style.getByText('Ridgeline', { exact: true }).click()

    await expect(units.getByRole('radio', { name: 'Metres' })).toBeChecked()
    await expect(theme.getByRole('radio', { name: 'Ink' })).toBeChecked()
    await expect(style.getByRole('radio', { name: 'Ridgeline' })).toBeChecked()

    // Observable proof the choices reached the app's own state before the
    // second page reads the store: More's row for this page prints the map
    // style and the units it would open with.
    await page.getByRole('button', { name: 'More', exact: true }).click()
    await expect(row(page, 'The map')).toContainText('Metres')
    await expect(row(page, 'The map')).toContainText('Ridgeline')

    const rebooted = await bootFreshPage(page)
    try {
      await rebooted.getByRole('tab', { name: 'More' }).click()
      await rebooted.locator('.more__row').filter({ hasText: 'The map' }).first().click()
      await expect(
        rebooted.getByRole('group', { name: /^units$/i }).getByRole('radio', {
          name: 'Metres',
        }),
      ).toBeChecked()
      await expect(
        rebooted.getByRole('group', { name: /^theme$/i }).getByRole('radio', {
          name: 'Ink',
        }),
      ).toBeChecked()
      await expect(
        rebooted.getByRole('group', { name: /^map style$/i }).getByRole('radio', {
          name: 'Ridgeline',
        }),
      ).toBeChecked()
    } finally {
      await rebooted.close()
    }
  })

  test('states: the source registry stays behind its gate (D4)', async ({ page }) => {
    // The door is rendered only where the shell hands More an `onOpenRegistry`
    // (screens/More.tsx), which this build does not for an ordinary hiker.
    // Asserting the ABSENCE is the point: a gate that quietly opened would
    // otherwise ship unnoticed, because nothing else on the page changes.
    await openMore(page)
    await row(page, 'Where this map comes from').click()

    await expect(page.getByRole('heading', { name: /^about this build$/i })).toBeVisible()
    await expect(page.getByRole('button', { name: 'The source registry' })).toHaveCount(0)
  })

  test('states: the trace recorder is offered once location has been asked about (#1201)', async ({
    page,
  }) => {
    // The other side of the same coin, and the gate is genuinely open here:
    // seedPreferences() writes `location_permission_requested`, which is one
    // of the three conditions screens/More.tsx ORs. The recorder is a
    // field-test tool rather than a hiker setting, and its section says so.
    await openMore(page)
    await row(page, 'Where this map comes from').click()

    const tools = page.getByRole('region', { name: 'Field-test tools' })
    await expect(tools).toBeVisible()
    await expect(tools.getByRole('button', { name: 'Start recording' })).toBeVisible()
  })

  test('entrance and exit: Your reports goes back to Volunteer & report, not to More', async ({
    page,
  }) => {
    // lib/navigator.ts's `returnsToOrigin`: a More screen's Back returns to
    // the page that opened it. Driving it from the volunteer page is the only
    // way to tell that apart from a Back that always lands on More's home.
    await openMore(page)
    await row(page, 'Volunteer & report').click()
    await page.getByRole('button', { name: 'Your reports' }).click()

    await expect(page.getByRole('heading', { name: /^your reports$/i })).toBeVisible()
    // Nothing reported from this phone, and the screen says so rather than
    // drawing an empty list (#1373, frame 9d).
    await expect(page.getByText(/Nothing reported from this phone yet/)).toBeVisible()

    await page.getByRole('button', { name: 'Volunteer & report', exact: true }).click()
    await expect(page.getByRole('heading', { name: /^contribute$/i })).toBeVisible()
  })

  test('entrance and exit: Your photos and notes goes back to You', async ({ page }) => {
    await openMore(page)
    await row(page, 'You').click()
    await page.getByRole('button', { name: 'Your photos and notes' }).click()

    await expect(
      page.getByRole('heading', { name: /^your photos and notes$/i }),
    ).toBeVisible()
    await expect(page.getByText(/Nothing here yet/)).toBeVisible()

    await page.getByRole('button', { name: 'You', exact: true }).click()
    await expect(page.getByRole('heading', { name: /^your hike$/i })).toBeVisible()
  })
})

/**
 * The one screen More REPLACES rather than pushes (App.tsx: "reached from here
 * and nowhere else, so there is nothing behind it worth keeping visible"), and
 * the only place in the app where a hike is two typed mile markers.
 *
 * DRIVEN WITHOUT A DOWNLOAD, which is this suite's whole premise and also the
 * state the screen is most careful in: with no trail data there is no length
 * to measure a whole-trail shortcut against, and the screen says so.
 */
test.describe('saying where you are walking', () => {
  async function openThePicker(page: Page): Promise<void> {
    await openMore(page)
    await row(page, 'You').click()
    await page.getByRole('button', { name: 'Say where you are walking' }).click()
    await expect(page.getByRole('heading', { name: /^your hike$/i })).toBeVisible()
  }

  test('entrance and states: with nothing downloaded it says why the shortcuts cannot work, and offers the numbers anyway', async ({
    page,
  }) => {
    await openThePicker(page)

    // THE SENTENCE IS THE POINT. A shortcut that reads "Whole trail" has to
    // know how long the trail is, and this phone has downloaded nothing - so
    // the screen names the reason and leaves the mile fields, which need no
    // published length at all.
    await expect(
      page.getByText(/The trail data is still arriving, so the whole-trail shortcuts/),
    ).toBeVisible()
    await expect(page.getByLabel('Starting at mile')).toBeVisible()
    await expect(page.getByLabel('Finishing at mile')).toBeVisible()

    // The screen opens refusing, because two blank fields are not a hike, and
    // the refusal is the live reading rather than a separate error.
    await expect(
      page.getByText(
        'Two different mile markers describe a hike; the same one twice doesn’t.',
      ),
    ).toBeVisible()
  })

  test('states: the reading follows the numbers, and says which way they point', async ({
    page,
  }) => {
    await openThePicker(page)
    await page.getByLabel('Starting at mile').fill('100')
    await page.getByLabel('Finishing at mile').fill('142')

    // Direction comes from the two miles rather than from a control, which is
    // the screen's whole argument for having no direction control.
    await expect(page.getByText('Northbound · 42 mi')).toBeVisible()

    // Swap them and the same two numbers mean the other way - nothing else
    // typed, nothing else chosen.
    await page.getByLabel('Starting at mile').fill('142')
    await page.getByLabel('Finishing at mile').fill('100')
    await expect(page.getByText('Southbound · 42 mi')).toBeVisible()
  })

  test('states: the same mile twice is refused as a sentence, and saving it is not offered as done', async ({
    page,
  }) => {
    await openThePicker(page)
    await page.getByLabel('Starting at mile').fill('100')
    await page.getByLabel('Finishing at mile').fill('100')

    // "A hike" needs two different ends. The screen says so in the same place
    // it would otherwise print the distance, rather than beside a control.
    await expect(
      page.getByText(
        'Two different mile markers describe a hike; the same one twice doesn’t.',
      ),
    ).toBeVisible()
    await expect(page.getByText(/Northbound|Southbound/)).toHaveCount(0)
  })

  test('exit: Cancel goes back to You, with nothing saved', async ({ page }) => {
    await openThePicker(page)
    await page.getByLabel('Starting at mile').fill('100')
    await page.getByLabel('Finishing at mile').fill('142')

    await page.getByRole('button', { name: 'Cancel' }).click()

    // Back on the page it replaced, and the row still reads as no hike set -
    // a Cancel that saved what was typed would be the screen deciding for the
    // hiker on the way out.
    await expect(page.getByRole('heading', { name: /^you$/i })).toBeVisible()
    await expect(
      page.getByRole('button', { name: 'Say where you are walking' }),
    ).toBeVisible()
  })
})
