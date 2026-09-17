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
  seedFixAtMile,
  bootFreshPage,
  type HikerMode,
} from './support/seed'
import { seedDayHikes } from '../preview-shots/fixtures/dayHike.mjs'

/** More → "Volunteer & report", which is where every reporting door lives.
 *  The row, not the page bar under it — the same narrowing more.spec.ts
 *  makes, for the same collisions.
 *
 *  `fix` seeds a real GPS position through Playwright's own geolocation
 *  before the app boots (#1563). WITHOUT ONE THE WINDOW OPENS ON ITS PICKER
 *  and a tile refuses to file until the report has a place, which is the
 *  state one spec below is about and the state every other spec here must
 *  not be in by accident: the "one tap files" claim is a claim about a phone
 *  that knows where it is. */
async function openContribute(
  page: Page,
  mode: HikerMode = 'day',
  { fix = false }: { fix?: boolean } = {},
): Promise<void> {
  await seedPreferences(page)
  await seedHikerMode(page, mode)
  if (fix) await seedFixAtMile(page, 5)
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

  test('layout: the 911 line is on screen without scrolling, on both phones this app designs for', async ({
    page,
  }) => {
    // #1480, and the one assertion in this repository that needs a real
    // browser to make. The unit suite runs in jsdom, which has no layout: it
    // can hold the notice OUTSIDE the scrolling element and above it, which
    // is what makes this true, but it cannot see a pixel and so cannot tell
    // a reader whether the thing is actually legible on a phone.
    //
    // WHAT WENT WRONG WITHOUT IT. The notice was the last child of a body
    // that overflowed its cap, so every existing test passed - the words were
    // right, the role was right, the document order was right - while the
    // line sat 39 px below the fold at 390x844 and 170 px below it at
    // 375x667. The maintainer found it by opening the app.
    //
    // 375x667 IS THE POINT OF THE SECOND HALF. The room audit of #1374 calls
    // it the smallest phone this app is designed for, and it is where the
    // window was 184 px over rather than 53. Set here rather than left to the
    // project's viewport, because the `phone` project is 390x844 and the
    // claim that matters is the one made on the smaller screen.
    //
    // WITH A FIX, since #1563: this measures the TILE frame, and without a
    // fix the window opens on its location picker above the tiles, which is
    // a taller frame by design. The picker's own frame is measured in the
    // no-fix spec below - and what it holds to is the one thing that must
    // survive any scroll, the 911 line, not "no scroll at all".
    await openContribute(page, 'day', { fix: true })

    for (const size of [
      { width: 390, height: 844 },
      { width: 375, height: 667 },
    ]) {
      await page.setViewportSize(size)
      const window_ = await openReportWindow(page)
      const notice = window_.getByRole('note')

      // Visible AND inside the viewport's own box. `toBeVisible` alone passes
      // for an element scrolled out of frame inside a scrolling parent, which
      // is exactly the state this test exists to catch.
      await expect(notice).toBeVisible()
      await expect(notice).toContainText('Call 911 if you are in danger now')
      await expect(notice).toBeInViewport({ ratio: 1 })

      // NOT MERELY REACHABLE - never scrolled to. Asserted on the scrolling
      // element itself rather than by comparing positions, because "the body
      // has no overflow" is the property, and it is the one that stops the
      // next category added to the grid pushing anything below the fold.
      const overflow = await window_
        .locator('.report-window__body')
        .evaluate((body) => body.scrollHeight - body.clientHeight)
      expect(overflow, `the body scrolls at ${size.width}x${size.height}`).toBe(0)

      // BOTH heavy rows whole inside their own borders, not just the one that
      // was caught clipping. They declare the same `min-height: 44px`, which
      // is what let the flex squeeze read a touch floor as a target: the
      // closure row rendered at 44 px against a natural 77 and spilled its
      // description 15 px past its own edge.
      //
      // The unsafe row is here because it is the one the container-level fix
      // does NOT reach. `.report-window__body > *` is a child combinator and
      // that row is a grandchild, inside `.report-window__unsafe` - so it is
      // floored by `.report-window__row`'s own `flex: none` and by nothing
      // else. Asserting only the closure row would have left the row the 911
      // line exists to qualify covered by a coincidence.
      //
      // Compared against each row's own padding box rather than against a
      // number, so this keeps meaning what it says if the copy or the type
      // changes.
      for (const row of [/^The trail is closed/, /^Something unsafe happened/]) {
        const spill = await window_.getByRole('button', { name: row }).evaluate((el) => {
          const description = el.querySelector('.report-window__row-description')
          if (description === null) return Number.NaN
          return Math.round(
            description.getBoundingClientRect().bottom -
              el.getBoundingClientRect().bottom,
          )
        })
        expect(spill, `${row.source} clips at ${size.width}x${size.height}`).toBeLessThan(
          0,
        )
      }

      await window_.getByRole('button', { name: /^Close/ }).click()
      await expect(window_).toHaveCount(0)
    }
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
    // A phone that knows where it is (#1563): the tap has a place to file
    // at, so it files. With no trail data on this phone the fix has no mile,
    // and the header says "Where you are" rather than inventing one.
    await openContribute(page, 'day', { fix: true })
    const window_ = await openReportWindow(page)
    await expect(window_.getByTestId('report-anchor')).toContainText('Where you are')

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

  test('states: with no fix, a kind does not file until the report has a place - and the words file it', async ({
    page,
  }) => {
    // THE GAP #1563 CLOSED. A one-tap report from a phone with no fix used to
    // file with no location of any kind - a blowdown a moderator reads as
    // "no location" and cannot act on. The window now opens on its location
    // picker (reporting/LocationPicker.tsx), the tile refuses until the
    // report has a place, and the hiker's own words are the last resort:
    // sent as prose, never turned into a pin.
    //
    // Measured on the small phone, because the picker makes this frame
    // taller and the one thing that must survive that is the 911 line.
    await page.setViewportSize({ width: 375, height: 667 })
    await openContribute(page)
    const window_ = await openReportWindow(page)

    await expect(window_.getByTestId('report-anchor')).toContainText('No location yet')
    const picker = window_.getByTestId('location-picker')
    await expect(picker).toBeVisible()
    // The map row is offered - the shell always has a map - and the words
    // field, because nothing else can place this report.
    await expect(picker.getByTestId('location-map')).toBeVisible()
    await expect(picker.getByTestId('location-words')).toBeVisible()
    // No fix, no "where you are": a row that cannot do anything is not drawn.
    await expect(picker.getByTestId('location-fix')).toHaveCount(0)
    // The 911 line is pinned outside the body, so the taller frame does not
    // push it below the fold.
    await expect(window_.getByRole('note')).toBeInViewport({ ratio: 1 })

    await window_.getByRole('button', { name: /^Blow down/ }).click()

    // Refused, and said so. Nothing filed: the eyebrow still reads the
    // before-state and there is no receipt to undo.
    await expect(window_.getByRole('alert')).toContainText('Say where this is first')
    await expect(window_.getByText('Report · filed')).toHaveCount(0)
    await expect(window_.getByRole('button', { name: /^Undo/ })).toHaveCount(0)

    await picker.getByTestId('location-words').fill('The ford below the gap')
    await window_.getByRole('button', { name: /^Blow down/ }).click()

    await expect(window_.getByText('Report · filed')).toBeVisible()
    await expect(window_.getByText(/Filed — blow down where you described/)).toBeVisible()
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

/**
 * The long form, which is the OTHER half of F9 and reached by a different door
 * (screens/ReportForm.tsx). The report window files a simple kind on one tap;
 * `step: 'form'` exists for the two kinds that have things to type, and
 * "Say thanks" on Today is its shipped door.
 *
 * features/SAYING_THANKS.md's premise is the reason it is this form rather
 * than another: a thanks is a REPORT TYPE, not a separate model, so it gets
 * the same provenance lines as a blowdown — where it happened, and who signed
 * it — and those two lines are what the tests below are about.
 */
test.describe('the form for the kinds you have to write', () => {
  async function openThanks(page: Page): Promise<void> {
    await seedPreferences(page)
    await seedHikerMode(page, 'long')
    await page.goto('/')
    // A PREFIX since #1438: Today's doors are rows now, and a row's
    // accessible name carries the line under its title ("Say thanks to
    // whoever keeps it up…") the way More's rows do. The heading inside the
    // form is still the exact words, which is what the next line checks.
    await page.getByRole('button', { name: /^Say thanks/ }).click()
    await expect(page.getByRole('heading', { name: 'Say thanks' })).toBeVisible()
  }

  test('entrance and states: it says where it will be filed from and who will sign it, before anything is typed', async ({
    page,
  }) => {
    await openThanks(page)

    // THE TWO PROVENANCE LINES, both of which are about not overclaiming.
    //
    // With no fix the form says the report has no place yet — it does not
    // quietly send 0,0, which lib/reportLocation.ts calls "a confident,
    // wrong place in the Atlantic" rather than a missing one. Since #1563 the
    // line is the shared picker's, open under it because nothing has placed
    // the report: a named place to find, the map, and the words a thanks may
    // leave empty (a thanks is not a problem, and files without a place).
    await expect(page.getByTestId('report-form-location')).toContainText(
      'No location yet',
    )
    await expect(page.getByTestId('location-picker')).toBeVisible()
    await expect(page.getByTestId('location-words')).toBeVisible()

    // And the signature falls back to the WEAKEST claim rather than the
    // strongest: "day", not "thru" (lib/reporterIdentity.ts). A form that
    // signed every unset report as a thru-hiker would be putting a claim in
    // a hiker's mouth on the one surface a maintainer reads for credibility.
    await expect(page.getByText(/^Signed as not set · day$/)).toBeVisible()
  })

  test('states: the photo field is here and empty, with no claim attached to it', async ({
    page,
  }) => {
    await openThanks(page)

    // The field exists (#234 wired it; #89 had deliberately left it visible
    // and disabled rather than removing it), and says nothing about a photo
    // until there is one — no "0 photos", no placeholder thumbnail. Since
    // #1439 it is a row of tiles rather than one input, so what is here with
    // nothing picked is the `+` tile and nothing else: no count, and no
    // summary line, because both are claims about attachments there are none
    // of.
    await expect(page.getByText('Photos', { exact: true })).toBeVisible()
    await expect(page.getByLabel(/add a photo/i)).toBeAttached()
    await expect(page.getByText(/photos? · \d+ KB so far/)).toHaveCount(0)
    await expect(page.getByText(/Photo attached —/)).toHaveCount(0)
    await expect(page.getByText(/Shrinking the photo/)).toHaveCount(0)
  })

  test('exit: Cancel leaves without filing, and nothing lands in Your reports', async ({
    page,
  }) => {
    await openThanks(page)
    await page.getByRole('textbox').first().fill('The privy at Low Gap was spotless.')

    await page.getByRole('button', { name: 'Cancel' }).click()

    // Back on Today, and — the part that matters — the words are gone rather
    // than filed. Checked at the one place a filed report would show up.
    await expect(page.getByRole('heading', { name: 'Say thanks' })).toHaveCount(0)
    await page.getByRole('tab', { name: 'More' }).click()
    await page
      .locator('.more__row')
      .filter({ hasText: 'Volunteer & report' })
      .first()
      .click()
    await page.getByRole('button', { name: 'Your reports' }).click()
    await expect(page.getByText(/Nothing reported from this phone yet/)).toBeVisible()
  })
})
