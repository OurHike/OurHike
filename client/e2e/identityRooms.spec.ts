// Where a hiker says who they are and what they have put back — the rooms
// behind More's "You" and "Volunteer & report" doors, and the one sheet that
// asks where they hike.
//
// e2e/more.spec.ts drives More's own rows and the settings behind them;
// e2e/settingsRooms.spec.ts drives the controls inside those rooms;
// e2e/reportingDoors.spec.ts drives the report forms and the hours form's
// empty state. What none of them reach is what happens AFTER a hiker hands
// something over — the sign-in ask, and the panel counting what they gave.
//
// THE ONE CLAIM RUNNING THROUGH ALL THREE is the project's line that reading
// the map never needs an account. A sign-in prompt is where an app usually
// takes something hostage, so every screen here is tested for what it says it
// will still do WITHOUT one, not only for the button working.
//
// ENTRANCE. Every room is a real tap from boot. No navigator state is
// injected (features/FLOW_TESTING.md, "Not a router").
//
// EXIT. Each is left the way it ships, asserted on the screen behind it
// rather than on the control having been clicked.

import { test, expect, type Page } from '@playwright/test'
import { seedPreferences, seedHikerMode, bootFreshPage } from './support/seed'

/** More → You, which is where identity lives on this build. The row is
 *  matched by its text rather than by a role name, because the row's
 *  accessible name carries its whole summary line ("Day hiking · not signed
 *  in") and that line changes with the state under test. */
async function openYou(page: Page): Promise<void> {
  await seedPreferences(page)
  await page.goto('/')
  await page.getByRole('tab', { name: 'More' }).click()
  await page.locator('.more__row').filter({ hasText: 'You' }).first().click()
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible()
}

/** More → Volunteer & report, in volunteer mode — the hours form is only on
 *  that page, and the mode axis is the one FLOW_TESTING.md says is most often
 *  forgotten (e2e/reportingDoors.spec.ts's note). */
async function openContribute(page: Page): Promise<void> {
  await seedPreferences(page)
  await seedHikerMode(page, 'volunteer')
  await page.goto('/')
  await page.getByRole('tab', { name: 'More' }).click()
  await page
    .locator('.more__row')
    .filter({ hasText: 'Volunteer & report' })
    .first()
    .click()
  await expect(page.getByRole('heading', { name: 'Your hours' })).toBeVisible()
}

/** One logged day, through the form rather than the store. Four hours of
 *  maintenance on a date the form already holds — the point is the panel that
 *  arrives afterwards, not the figures. */
async function logADay(page: Page, hours = '4'): Promise<void> {
  await page.getByTestId('hours-count').fill(hours)
  await page.getByTestId('hours-activity').selectOption({ label: 'Trail maintenance' })
  await page.getByTestId('hours-log').click()
  // WITH NO ACCOUNT, LOGGING ASKS FOR ONE — and the ask is the next test's
  // subject. Here it is passed through, because the promise the prompt makes
  // ("already saved on your phone") is what makes the panel below reachable
  // at all without signing in.
  await page.getByRole('button', { name: 'Not now' }).click()
}

test.describe('where you hike', () => {
  test('entrance and states: the sheet is honest that it has no places to offer', async ({
    page,
  }) => {
    // THE ABSENT-INDEX STATE, which is the one this environment can reach and
    // is a real one: `places.json` is a published artifact, so a phone that
    // has downloaded nothing has no list. What the sheet must not do is offer
    // an empty picker — it says which of the two it is, and says what to do
    // instead, which is the README's rule for an empty state.
    await openYou(page)
    await expect(page.getByText('Not set', { exact: true }).first()).toBeVisible()

    await page.getByRole('button', { name: 'Set' }).click()

    const sheet = page.getByRole('dialog', { name: 'Where you hike' })
    await expect(sheet).toBeVisible()
    await expect(sheet).toContainText('The list of places has not been published yet')
    // AND THE PRIVACY LINE, which is the sentence that makes the setting
    // something a hiker will use: a place they NAMED, kept with their
    // settings — never a fix, and never where they are standing.
    await expect(sheet).toContainText(/never where you are standing/i)
  })

  test('exit: closing the sheet leaves the setting as it was', async ({ page }) => {
    await openYou(page)
    await page.getByRole('button', { name: 'Set' }).click()
    const sheet = page.getByRole('dialog', { name: 'Where you hike' })
    await expect(sheet).toBeVisible()

    await sheet.getByRole('button', { name: 'Close' }).click()

    await expect(page.getByRole('dialog', { name: 'Where you hike' })).toHaveCount(0)
    // Back in the room, with the row still unset and its door still there —
    // the assertion that the close was a close rather than a choice.
    await expect(page.getByRole('button', { name: 'Set' })).toBeVisible()
    await expect(page.getByText('Not set', { exact: true }).first()).toBeVisible()
  })
})

test.describe('the sign-in ask', () => {
  test('entrance and states: asked for its own sake, it promises the map without one', async ({
    page,
  }) => {
    await openYou(page)
    await page.getByRole('button', { name: 'Sign in' }).click()

    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
    // THE SENTENCE THE WHOLE SCREEN IS FOR. Not "sign in to continue" —
    // an enumeration of what stays available to somebody who does not, and
    // the four things it names are the four this app can hurt somebody with
    // (CLAUDE.md's "Four ways this app can hurt somebody").
    await expect(page.getByText(/Reading the map never needs an account/)).toBeVisible()
    await expect(page.getByText(/water, shelters, closures and warnings/)).toBeVisible()

    // A provider, and a way past. Which providers are offered is a build
    // setting (ENABLED_PROVIDERS) and an `online` question, so the claim is
    // that at least one is offered and that declining is always there.
    await expect(page.getByRole('button', { name: /^Continue with/ })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Not now' })).toBeVisible()
  })

  test('states: asked after work is handed over, it leads with the work being safe', async ({
    page,
  }) => {
    // THE SAME SCREEN, DIFFERENT FRAMING, and the difference is the whole
    // point: a prompt that appears the moment a hiker finishes writing
    // something is a prompt that could be read as holding it. This one leads
    // with "already saved on your phone", so the ask is about REACHING
    // somebody rather than about keeping the work.
    await openContribute(page)
    await page.getByTestId('hours-count').fill('4')
    await page.getByTestId('hours-activity').selectOption({ label: 'Trail maintenance' })
    await page.getByTestId('hours-log').click()

    await expect(page.getByRole('heading', { name: 'One thing first' })).toBeVisible()
    await expect(page.getByText(/already saved on your phone/)).toBeVisible()
    await expect(
      page.getByText(/Signing in is what lets it reach the people who can act on it/),
    ).toBeVisible()
  })

  test('exit: “Not now” keeps the work and returns to the room it came from', async ({
    page,
  }) => {
    // Rule 2 where it matters most. If declining lost the logged day, the
    // promise two lines above it would be false — so the exit test asserts
    // the record, not just the screen.
    await openContribute(page)
    await logADay(page)

    await expect(page.getByRole('heading', { name: 'One thing first' })).toHaveCount(0)
    await expect(page.getByRole('heading', { name: 'Your hours' })).toBeVisible()
    await expect(page.getByText(/4 hours over 1 day/)).toBeVisible()
  })
})

test.describe('what you have put back', () => {
  test('states: the panel arrives with the first logged day, and says what it does not count', async ({
    page,
  }) => {
    // ABSENT UNTIL THERE IS SOMETHING TO SAY — `VolunteerImpact` returns null
    // with no tiles, which is D10's "absent rather than disabled" applied to
    // a summary: a panel of zeroes would read as a score of nought rather
    // than as an empty logbook.
    await openContribute(page)
    await expect(page.getByTestId('impact-tiles')).toHaveCount(0)

    await logADay(page)

    await expect(page.getByTestId('impact-tiles')).toBeVisible()
    // THE CAVEAT IS THE REASON THIS PANEL IS ALLOWED TO EXIST. It counts
    // logged hours and nothing else, and it says so in the app's own voice —
    // "that is this app's gap, not a gap in what you did." A summary that
    // undercounted silently would tell a volunteer their work was smaller
    // than it was.
    await expect(
      page.getByText(/Field notes and water reports are not counted here/),
    ).toBeVisible()
    await expect(
      page.getByText(/this app’s gap, not a gap in what you did/),
    ).toBeVisible()
    // And the privacy line, which is what makes a count of somebody's
    // volunteering something they might want kept at all.
    await expect(page.getByText(/Kept for you, seen by no one/)).toBeVisible()
  })

  test('states: a day logged without an account is still there after a restart', async ({
    page,
  }) => {
    // THE PROMISE THIS TEST EXISTS TO KEEP, in the section's own words: a
    // logged day "is claimed in your name until a club confirms it — and it
    // stays yours either way". Writing this test is what found it broken.
    //
    // The day went to the outbox and was echoed into React state, and the
    // echo was the only thing the logbook read — so before the fix in
    // lib/volunteerHours.ts's `queuedHoursSummary` and App.tsx's boot
    // restore, a second page onto the same store showed an empty "Your
    // hours" and no impact panel, while the reports row above it still said
    // "1 waiting to send". Nothing was ever lost; no screen asked.
    //
    // A sibling page rather than a reload, for the trap support/seed.ts
    // documents — a reload would rewrite the seeded preferences over
    // whatever the app has saved since.
    await openContribute(page)
    await logADay(page, '4')
    await expect(page.getByText(/4 hours over 1 day/)).toBeVisible()

    const fresh = await bootFreshPage(page)
    await fresh.getByRole('tab', { name: 'More' }).click()
    await fresh
      .locator('.more__row')
      .filter({ hasText: 'Volunteer & report' })
      .first()
      .click()

    await expect(fresh.getByText(/4 hours over 1 day/)).toBeVisible()
    await expect(fresh.getByText('Claimed — not yet confirmed')).toBeVisible()
    // And the panel that counts it, because a logbook that came back without
    // its summary would be half the promise.
    await expect(fresh.getByTestId('impact-tiles')).toBeVisible()
    await fresh.close()
  })

  test('states: the hiker can put the panel away, and it stays away across a restart', async ({
    page,
  }) => {
    // `impact_panel_shown` is a stored preference, so the claim is only worth
    // making across a cold boot — a sibling page, for the reload trap
    // support/seed.ts documents.
    await openContribute(page)
    await logADay(page)
    await expect(page.getByTestId('impact-tiles')).toBeVisible()

    await page.getByLabel('Show what I’ve put back').uncheck()

    await expect(page.getByTestId('impact-tiles')).toHaveCount(0)
    await expect(page.getByTestId('impact-off')).toBeVisible()
    // The heading stays, so the way back is where the way out was — hiding a
    // panel and its own switch together is a setting a hiker cannot undo.
    //
    // A STRAIGHT APOSTROPHE, and deliberately matched as one: lib/
    // volunteerImpact.ts spells IMPACT_TITLE "What you've put back" while the
    // switch under it and the caveat beside it both use a typographic one.
    // The straight spelling is the wireframe's and runs through the module,
    // its stylesheet comment, its shot recipe and features/VOLUNTEERING.md
    // §5, so this matches the build rather than correcting it — the copy call
    // is the maintainer's.
    await expect(page.getByText("What you've put back")).toBeVisible()

    const fresh = await bootFreshPage(page)
    await fresh.getByRole('tab', { name: 'More' }).click()
    await fresh
      .locator('.more__row')
      .filter({ hasText: 'Volunteer & report' })
      .first()
      .click()
    await expect(fresh.getByRole('heading', { name: 'Your hours' })).toBeVisible()
    await expect(fresh.getByTestId('impact-off')).toBeVisible()
    await expect(fresh.getByTestId('impact-tiles')).toHaveCount(0)
    await fresh.close()
  })
})
