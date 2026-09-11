// The reporting doors, the mode switch and the two forms behind them —
// F9 in features/FLOW_TESTING.md's battery, plus the surfaces that are means
// to an end everywhere else and are the subject here.
//
// WHY THE MODE SWITCH GETS ITS OWN TEST. Three other spec files tap it to
// reach somewhere, which is exactly the "walking past" the coverage ledger
// refuses to count. The switch is a screen in its own right — it is the one
// control that changes what every other screen shows (R11), and #1317 made
// it the one deliberate exception to an instant mode, because switching to
// long with nothing active has to ask WHICH hike. That asymmetry is what a
// spec that merely taps it would never notice breaking.
//
// ENTRANCE. Every door is a real tap from boot. No navigator state is
// injected (FLOW_TESTING.md, "Not a router").
//
// CORRECTED 2026-09-11: screens/GroupScreen.tsx DOES have a door, and this
// file was right about the volunteer page and wrong about the app. The door
// is under the Plan tab, two levels in — a section's timeline, "All N trips",
// "+ New group", then the group itself — and e2e/tripRooms.spec.ts drives it.
// The note below stands as written about the volunteer page, which is what it
// actually probed; "no door on the volunteer page this build ships" was the
// true sentence, and "no door" was the one it turned into.
//
// WHAT IS DELIBERATELY NOT HERE. screens/GroupScreen.tsx has no door on the
// volunteer page this build ships — probed 2026-09-11: More → Volunteer &
// report offers "Report a problem", "Your reports" and "Log the day", and
// nothing reaches a crew. It stays `planned` rather than being driven
// through a route that does not exist, which is the second time this rule
// has saved a false claim on this branch (see `TripList` in planRooms).
//
// screens/Moderation.tsx stays `planned` for the other reason: its door is
// behind `onOpenModeration`, which needs a signed-in moderator, and this
// suite signs nobody in.

import { test, expect, type Page } from '@playwright/test'
import {
  seedPreferences,
  seedHikerMode,
  bootFreshPage,
  type HikerMode,
} from './support/seed'
import { seedDayHikes } from '../preview-shots/fixtures/dayHike.mjs'

/** More → "Volunteer & report", which is where every reporting door lives.
 *  The row, not the page bar under it — the same narrowing more.spec.ts
 *  makes, for the same collisions. */
async function openContribute(page: Page, mode: HikerMode = 'day'): Promise<void> {
  await seedPreferences(page)
  await seedHikerMode(page, mode)
  await page.goto('/')
  await page.getByRole('tab', { name: 'More' }).click()
  await page
    .locator('.more__row')
    .filter({ hasText: 'Volunteer & report' })
    .first()
    .click()
  await expect(page.getByRole('heading', { name: 'Contribute' })).toBeVisible()
}

/** The report window, opened from the Contribute group's own door. */
async function openReportWindow(page: Page) {
  await page.getByRole('button', { name: 'Report a problem' }).click()
  const window_ = page.getByTestId('report-window')
  await expect(window_).toBeVisible()
  return window_
}

test.describe('the reporting doors', () => {
  test('entrance and exit: the report window opens on its kinds and closes without filing', async ({
    page,
  }) => {
    await openContribute(page)
    const window_ = await openReportWindow(page)

    // The eyebrow says which half of its own life the window is in — "Report
    // a problem" before, "Report · filed" after — so asserting the first is a
    // claim that nothing has been sent, which matters on a screen whose whole
    // risk is sending something by accident.
    await expect(window_.getByText('Report a problem')).toBeVisible()
    await expect(window_.getByText('Report · filed')).toHaveCount(0)

    // The kinds, each with the sentence that tells a hiker which one they
    // want. Not all eight: the three asserted are the ones whose wording
    // carries a decision — a closure asks for two miles, and the unsafe
    // report is private to moderators and never a public pin.
    await expect(window_.getByRole('button', { name: /^Blow down/ })).toBeVisible()
    await expect(
      window_.getByRole('button', {
        name: /The trail is closed.*two miles it runs between/s,
      }),
    ).toBeVisible()
    await expect(
      window_.getByRole('button', {
        name: /Something unsafe happened.*never a public pin/s,
      }),
    ).toBeVisible()

    // A window that cannot be left without filing is the worst version of
    // this particular screen. Its own Close, and the page behind it intact.
    await window_.getByRole('button', { name: /^Close/ }).click()
    await expect(window_).toHaveCount(0)
    await expect(page.getByRole('heading', { name: 'Contribute' })).toBeVisible()
  })

  test('states: a simple kind files on ONE TAP, and the only thing between a mis-tap and a filed report is the undo', async ({
    page,
  }) => {
    // NOT WHAT THIS SPEC FIRST ASSERTED, twice over, and both corrections are
    // the point.
    //
    // It expected "Blow down" to open screens/ReportForm.tsx titled for the
    // kind. It does not: the window keeps the screen. Then it expected the
    // tap merely to advance a step. It does not do that either — the tap
    // FILES the report, and "Anything to add?" is an optional note AFTER the
    // fact. That is the right design for the six kinds that need nothing but
    // a note: a hiker standing in the rain in front of a blowdown taps once
    // and walks on, and the ceremony of a form would be paid on every report.
    //
    // WHICH MAKES THE UNDO LOAD-BEARING, and this is the assertion that
    // matters. One tap files; a mis-tap is therefore a filed report; and the
    // eight-second countdown is the whole of what stands between them. It is
    // asserted here as a control that exists, is labelled with its remaining
    // time, and WORKS — a countdown that ran out silently on a tap nobody
    // meant would put a false report in a club's queue.
    await openContribute(page)
    const window_ = await openReportWindow(page)

    await window_.getByRole('button', { name: /^Blow down/ }).click()

    // Filed, and the receipt says what and where it went. Matched on the
    // sentence rather than the time, which is the clock's and not this
    // spec's — the receipt's own claim is that the moment is KEPT, so a
    // report written at dusk and sent at the trailhead still reads as dusk.
    await expect(window_.getByText('Report · filed')).toBeVisible()
    await expect(window_.getByText(/Filed — blow down here/)).toBeVisible()
    await expect(window_.getByText(/waits in your outbox and sends itself/)).toBeVisible()
    // The optional note, offered after rather than demanded before.
    await expect(page.getByRole('heading', { name: 'Anything to add?' })).toBeVisible()

    // The undo, labelled with the seconds it has left so a hiker can see it
    // is running rather than discovering it has stopped.
    const undo = window_.getByRole('button', { name: /^Undo · \d+s/ })
    await expect(undo).toBeVisible()

    await undo.click()

    // Back to the kinds, with nothing filed — the state the window opened in.
    // This is the claim that the undo is a real retraction rather than a
    // dismissal of the receipt.
    await expect(window_.getByText('Report · filed')).toHaveCount(0)
    await expect(window_.getByText('Report a problem')).toBeVisible()
    await expect(window_.getByRole('button', { name: /^Blow down/ })).toBeVisible()
  })

  test('entrance: the closure door opens the closure form, which is a different form', async ({
    page,
  }) => {
    // ClosureForm is not ReportForm with a different title: a closure runs
    // BETWEEN two miles, so it asks for two where a report asks for one. The
    // window's own copy promises that ("Asks for the two miles it runs
    // between"), and this is the assertion that the promise is kept.
    await openContribute(page)
    const window_ = await openReportWindow(page)

    await window_.getByRole('button', { name: /^The trail is closed/ }).click()

    await expect(page.getByRole('heading', { name: 'Report a closure' })).toBeVisible()
  })

  test('states: the hours form is on the volunteer page, and cannot log a day with nothing in it', async ({
    page,
  }) => {
    // screens/VolunteerHours.tsx IS A SECTION, not a screen behind a door —
    // which is what this test found by trying to open one. It sits on the
    // volunteer page with its three fields, and "Log the day" is its submit.
    //
    // ONLY IN VOLUNTEER MODE, which is the mode axis FLOW_TESTING.md names
    // and the one most often forgotten: two of the three modes never see this
    // section at all, so a spec that drove only `day` would have called it
    // unreachable.
    await openContribute(page, 'volunteer')

    await expect(page.getByRole('heading', { name: 'Your hours' })).toBeVisible()
    await expect(page.getByText('Hours', { exact: true })).toBeVisible()
    await expect(page.getByText('What kind of work', { exact: true })).toBeVisible()

    // Disabled, not absent — and that is NOT the D10 exception being broken.
    // D10 is about doors: a control that claims a screen exists when it does
    // not. This is a form's own submit, where disabled is the honest state of
    // "there is nothing here to send yet", and hiding it would leave a hiker
    // filling in fields with no visible way to finish.
    await expect(page.getByTestId('hours-log')).toBeDisabled()
  })

  test('states: the day-hike card hands its walk to the plain-text card', async ({
    page,
  }) => {
    // screens/ShareHike.tsx — D6's "leave it with somebody at home", and the
    // one door on the saved card that produces something to hand over rather
    // than something to walk. Reached from the card, which is where a hiker
    // is when they decide to.
    await seedPreferences(page)
    await seedHikerMode(page, 'day')
    await page.goto('/')
    await seedDayHikes(page)
    await page.getByRole('tab', { name: 'Plan' }).click()
    await page.getByRole('button', { name: /^Pine Meadow loop/ }).click()

    await page.getByRole('button', { name: /Leave it with someone/ }).click()

    await expect(
      page.getByRole('heading', { name: 'Leave this with someone' }),
    ).toBeVisible()
  })
})

test.describe('the mode switch, as a screen rather than a way through', () => {
  test('states: it opens on the mode the phone is in, and the choice survives a cold boot', async ({
    page,
  }) => {
    await seedPreferences(page)
    await seedHikerMode(page, 'day')
    await page.goto('/')

    // The read-out names itself for the question it asks, not for the mode it
    // shows — "Today I'm ‹mode›. Switch mode" — which is what makes a chip
    // that could otherwise read as a label answerable by a screen reader.
    await page.getByRole('button', { name: /Switch mode/ }).click()

    const group = page.getByRole('radiogroup', { name: "Today I'm" })
    await expect(group).toBeVisible()
    await expect(group.getByRole('radio', { name: /Day hike/ })).toBeChecked()

    // Volunteer is the third mode, and the one the app's own docs say gets
    // forgotten. Clicked by its visible label: the radios are hidden under
    // the labels that style them.
    await page.getByText('Volunteer', { exact: true }).click()
    await expect(page.getByRole('button', { name: /Today I.m volunteer/ })).toBeVisible()

    const second = await bootFreshPage(page)
    await expect(
      second.getByRole('button', { name: /Today I.m volunteer/ }),
    ).toBeVisible()
    await second.close()
  })
})
