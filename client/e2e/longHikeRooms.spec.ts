// The rooms a LONG hike opens that no published data can reach — setting one
// up before it exists, planning a section inside the hike's own room, and the
// card that meets a hiker who stepped off the trail and came back.
//
// e2e/plan.spec.ts and e2e/planRooms.spec.ts drive the Plan tab around a hike
// that is already walking; e2e/tripRooms.spec.ts drives the trips on it. This
// file is the two ends of that life: the screen where a hike is invented
// (screens/HikeSetup.tsx, F3), the panel that adds a section without leaving
// the room (chrome/SectionPlanner.tsx, F4, #1344's whole point), and the
// welcome-back card (chrome/WelcomeBackCard.tsx, F2, #1317).
//
// HERMETIC. Nothing here needs a junction graph or a waypoint: a hike is two
// mile markers and a name, a section's two ends are named on a sheet, and the
// resume offer is computed from the trip store's own dates. The one thing
// that does need the bucket — turning two named ends into laid-out days — is
// where this file stops, and e2e/data/longSpine.spec.ts picks it up.
//
// ENTRANCE. Every door below is a real tap from boot, including the pause:
// the hike is put into `paused` by driving More → the hike's own row → the
// step-away sheet, rather than by seeding a status the app would then only
// have to read back (features/FLOW_TESTING.md, "Not a router").

import { test, expect, type Page } from '@playwright/test'
// Untyped on purpose: a shot fixture is plain JavaScript, and its shape is
// the app's contract with IndexedDB rather than a type this spec restates.
import { seedLongHike } from '../preview-shots/fixtures/longHike.mjs'
import { seedPreferences, seedHikerMode } from './support/seed'

/** Long mode with NO hike — the state Today's setup head is written for, and
 *  the only one from which a hike can be invented. */
async function noHikeYet(page: Page): Promise<void> {
  await seedPreferences(page)
  await seedHikerMode(page, 'long')
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'You have no hike yet' })).toBeVisible()
}

/** Long mode WITH the fixture hike, on Today. */
async function walkingIt(page: Page): Promise<void> {
  await seedPreferences(page)
  await seedHikerMode(page, 'long')
  await page.goto('/')
  await seedLongHike(page)
  await expect(page.getByText(/mi walked · [\d.,]+ mi to go/)).toBeVisible()
}

/** More's "You" page, which is where both the hike's own row and the picker
 *  live. `.more__row` rather than the text: the rows carry a chevron and a
 *  summary line, so the accessible name is the whole card. */
async function youPage(page: Page): Promise<void> {
  await page.getByRole('tab', { name: 'More' }).click()
  await page.locator('.more__row').filter({ hasText: 'You' }).first().click()
  await expect(page.getByRole('heading', { name: 'You', exact: true })).toBeVisible()
}

test.describe('inventing a long hike', () => {
  test('entrance and states: the setup screen opens named, and refuses to start until it has two ends', async ({
    page,
  }) => {
    await noHikeYet(page)
    await page.getByRole('button', { name: /^Pick a trail on the map/ }).click()

    // THE BAND AND THE FIELD SHOW THE SAME NAME, which is the claim
    // HikeSetup.tsx's own comment makes about why the field is here at all
    // ("a hiker typing here watches their own hike get its name").
    await expect(page.getByRole('heading', { name: 'A new long hike' })).toBeVisible()
    await expect(page.getByLabel('Its name')).toHaveValue('A new long hike')

    // THE REFUSAL IS A SENTENCE, and it is the state the screen opens in:
    // a hike invented from this door has no points yet.
    await expect(
      page.getByText('A long hike needs two ends before it can be walked.'),
    ).toBeVisible()

    // Nothing has been counted, because nothing has been named. "Its points"
    // carries the count, and a leg needs two points to exist.
    await expect(page.getByText(/^Its points · 0 points$/)).toBeVisible()
  })

  test('states: typing a name renames the hike in the heading, not only in the field', async ({
    page,
  }) => {
    await noHikeYet(page)
    await page.getByRole('button', { name: /^Pick a trail on the map/ }).click()
    await page.getByLabel('Its name').fill('Georgia in April')

    // The draft lives in the shell, so the band reads it back — which is the
    // difference between a rename and a text box that remembers nothing.
    await expect(page.getByRole('heading', { name: 'Georgia in April' })).toBeVisible()
  })

  test('exit: Cancel goes back to Today with no hike started', async ({ page }) => {
    await noHikeYet(page)
    await page.getByRole('button', { name: /^Pick a trail on the map/ }).click()
    await expect(page.getByRole('heading', { name: 'A new long hike' })).toBeVisible()

    await page.getByRole('button', { name: 'Cancel' }).click()

    // NOTHING WAS CREATED. The screen is gone and no hike named after it is
    // anywhere — a draft that survived a Cancel would sit in the store as the
    // literal "A new long hike" that `handleNewHike` invents.
    await expect(page.getByRole('heading', { name: 'A new long hike' })).toHaveCount(0)

    // AND THE MODE GOES BACK TO DAY, which is the part worth pinning because
    // it looks like a bug until you follow it: switching to long mode with no
    // active hike opens this flow (App.tsx), so a Cancel that left the mode
    // alone would land the hiker on a Today screen whose only content is the
    // ask they just declined. `handleCancelHikePick` drops the mode ONLY when
    // `activeHikeId` is null — cancelling a switch between two existing hikes
    // leaves it exactly where it was.
    await expect(page.getByRole('radio', { name: 'Day hike' })).toBeChecked()
  })
})

test.describe('a section, planned without leaving the hike room', () => {
  test('entrance and states: the panel opens IN the room, and says where the days will come from', async ({
    page,
  }) => {
    await walkingIt(page)
    await page.getByRole('tab', { name: 'Plan' }).click()
    await page.getByRole('button', { name: 'Plan a section' }).click()

    const panel = page.getByRole('region', { name: 'Plan a section' })
    await expect(panel).toBeVisible()

    // #1344's ask in one assertion: the room is STILL THERE under the panel.
    // The primary this replaced ran `sweepForBuilder`, whose first act is
    // `setActiveTab('map')` — so a panel that had navigated would leave no
    // "SECTIONS IN THIS HIKE" heading behind it.
    await expect(page.getByText('Sections in this hike')).toBeVisible()

    // Two ends, each saying so rather than showing a gap.
    await expect(
      panel.getByRole('button', { name: /^From Choose a place/ }),
    ).toBeVisible()
    await expect(panel.getByRole('button', { name: /^To Choose a place/ })).toBeVisible()

    // The panel declines to be a day planner, on screen. Nothing here asks
    // how long a day is, and the sentence says which screen will.
    await expect(
      panel.getByText(/the days come from the profile between them, not from this panel/),
    ).toBeVisible()
  })

  test('states: the map is offered as a door, never as the only way in', async ({
    page,
  }) => {
    await walkingIt(page)
    await page.getByRole('tab', { name: 'Plan' }).click()
    await page.getByRole('button', { name: 'Plan a section' }).click()

    const panel = page.getByRole('region', { name: 'Plan a section' })
    // Both routes to the same section are present at once: name the ends
    // here, or go and tap them. A build that offered only the map would be
    // the thing #1344 was filed about.
    await expect(
      panel.getByRole('button', { name: 'Draw it on the map instead' }),
    ).toBeVisible()
    await expect(panel.getByRole('button', { name: /^From/ })).toBeVisible()
  })

  test('exit: Cancel puts the room back exactly as it was', async ({ page }) => {
    await walkingIt(page)
    await page.getByRole('tab', { name: 'Plan' }).click()
    await page.getByRole('button', { name: 'Plan a section' }).click()
    await expect(page.getByRole('region', { name: 'Plan a section' })).toBeVisible()

    await page
      .getByRole('region', { name: 'Plan a section' })
      .getByRole('button', { name: 'Cancel' })
      .click()

    await expect(page.getByRole('region', { name: 'Plan a section' })).toHaveCount(0)
    // The door it was opened from is back, which is what "as it was" means
    // here — a panel that closed onto a room missing its own primary would
    // strand the hiker.
    await expect(page.getByRole('button', { name: 'Plan a section' })).toBeVisible()
  })
})

test.describe('stepping off the trail, and being met on the way back', () => {
  /** Pause the fixture hike the way a hiker does: More → the hike's own row →
   *  the step-away sheet's one non-destructive door. */
  async function pauseTheHike(page: Page): Promise<void> {
    await youPage(page)
    await page.getByRole('button', { name: 'Springer → Katahdin', exact: true }).click()
    const sheet = page.getByRole('dialog', { name: 'Step away from this hike' })
    await expect(sheet).toBeVisible()
    await sheet.getByRole('button', { name: /Off trail — pause the hike/ }).click()
    await expect(sheet).toHaveCount(0)
  }

  test('entrance and states: every door names what it costs, and only one is behind a confirm', async ({
    page,
  }) => {
    await walkingIt(page)
    await youPage(page)
    await page.getByRole('button', { name: 'Springer → Katahdin', exact: true }).click()

    const sheet = page.getByRole('dialog', { name: 'Step away from this hike' })
    await expect(sheet).toBeVisible()

    // EVERY DOOR SAYS WHAT HAPPENS UNDERNEATH ITS NAME. StepAwaySheet.tsx
    // argues this is the design rather than a copy preference — these six do
    // very different things to a record, and a sheet of verbs alone would
    // make the destructive one look like the reversible ones. So the
    // assertion is on the consequence line, not on the verb.
    await expect(
      sheet.getByText('The day stays; the ones after it shift by one.'),
    ).toBeVisible()
    await expect(
      sheet.getByText('Resupply logged at the stop. Nothing else moves.'),
    ).toBeVisible()
    await expect(
      sheet.getByText(
        'Keeps the mile you stopped at. Resume whenever, this year or next.',
      ),
    ).toBeVisible()
    await expect(
      sheet.getByText('Swaps the two ends. The miles already walked stay walked.'),
    ).toBeVisible()
    await expect(
      sheet.getByText('Closes the hike and keeps every section in it.'),
    ).toBeVisible()
    await expect(
      sheet.getByText('Ungroups it. Every section stays in Plan.'),
    ).toBeVisible()
  })

  test('states: “Forget this hike” arms before it acts, and “Keep it” disarms it', async ({
    page,
  }) => {
    await walkingIt(page)
    await youPage(page)
    await page.getByRole('button', { name: 'Springer → Katahdin', exact: true }).click()
    const sheet = page.getByRole('dialog', { name: 'Step away from this hike' })

    await sheet.getByRole('button', { name: /^Forget this hike/ }).click()

    // The confirm says the thing a hiker cannot see from outside: ungrouping
    // is not deleting. It is here rather than only in the door's note because
    // this is the press that would otherwise be irreversible.
    await expect(sheet.getByText('Forget this hike?')).toBeVisible()
    await expect(
      sheet.getByText(
        /Every section stays in Plan, with its days, its miles and its dates/,
      ),
    ).toBeVisible()

    await sheet.getByRole('button', { name: 'Keep it' }).click()

    // Disarmed, and the hike is still here — the door is back in its
    // unarmed shape rather than the confirm staying up as a dead end.
    await expect(sheet.getByText('Forget this hike?')).toHaveCount(0)
    await expect(sheet.getByRole('button', { name: /^Forget this hike/ })).toBeVisible()
  })

  test('entrance and states: a paused hike is met with an offer, and never with a count of what was missed', async ({
    page,
  }) => {
    await walkingIt(page)
    await pauseTheHike(page)
    await page.getByRole('tab', { name: 'Today' }).click()

    const card = page.getByRole('region', { name: 'Welcome back' })
    await expect(card).toBeVisible()

    // THE OFFER IS THE WHOLE CARD: what is still dated, and two ways to
    // answer. Neither is pre-selected — WelcomeBackCard.tsx's own promise,
    // "doing nothing changes nothing".
    await expect(card.getByText(/days? (is|are) still dated from/)).toBeVisible()
    await expect(card.getByRole('button', { name: 'Move them to today' })).toBeVisible()
    await expect(card.getByRole('button', { name: 'Leave it' })).toBeVisible()

    // NEVER A SCOLD. The card's header says it outright and this is the
    // assertion that keeps it: no "you missed N", no count of reports filed
    // while the hiker was off the trail.
    await expect(card.getByText(/missed/i)).toHaveCount(0)
  })

  test('states: “Leave it” puts the card away and moves nothing — the hike is still paused', async ({
    page,
  }) => {
    await walkingIt(page)
    await pauseTheHike(page)
    await page.getByRole('tab', { name: 'Today' }).click()
    await expect(page.getByRole('region', { name: 'Welcome back' })).toBeVisible()

    await page.getByRole('button', { name: 'Leave it' }).click()

    // The card goes and the STATUS STAYS, which is the difference between
    // this button and the one beside it. A "Leave it" that also un-paused
    // the hike would be the card editing the plan on a hiker's behalf.
    await expect(page.getByRole('region', { name: 'Welcome back' })).toHaveCount(0)
    await expect(page.getByText(/^paused\b/)).toBeVisible()
  })

  test('states: the offer comes back on a restart, because the hike is still paused', async ({
    page,
  }) => {
    await walkingIt(page)
    await pauseTheHike(page)
    await page.getByRole('tab', { name: 'Today' }).click()
    await page.getByRole('button', { name: 'Leave it' }).click()
    await expect(page.getByRole('region', { name: 'Welcome back' })).toHaveCount(0)

    // Deliberate, and said in App.tsx: `resumeDismissed` is "hikes whose
    // resume offer this session has already made" — session state, not a
    // stored choice. So a hiker who dismissed it and closed the app is asked
    // again, because the thing the card is about has not changed.
    await page.reload({ waitUntil: 'load' })

    await expect(page.getByRole('region', { name: 'Welcome back' })).toBeVisible()
  })

  test('states: “Move them to today” takes the hike off pause, which “Leave it” does not', async ({
    page,
  }) => {
    await walkingIt(page)
    await pauseTheHike(page)
    await page.getByRole('tab', { name: 'Today' }).click()
    await expect(page.getByText(/^paused\b/)).toBeVisible()

    await page.getByRole('button', { name: 'Move them to today' }).click()

    // Walking again: the away line goes with the card. Measured against the
    // sibling test above, where the same card's other button leaves it.
    await expect(page.getByRole('region', { name: 'Welcome back' })).toHaveCount(0)
    await expect(page.getByText(/^paused\b/)).toHaveCount(0)
  })
})
