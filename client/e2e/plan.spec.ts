// The Plan tab (client/src/screens/PlanHome.tsx and the rooms under it) -
// F8 in features/FLOW_TESTING.md's battery.
//
// STATES: the mode axis, and the half of it that is easy to get wrong. Plan
// has TWO rooms, not three - PlanHome.tsx's own header says "VOLUNTEER GETS
// THE DAY ROOM, and there is no third room", and PlanStart.tsx's
// `planMode = mode === 'long' ? 'long' : 'day'` is the line that makes it
// true. So all three modes are driven here and volunteer is asserted to land
// in the day room, which is the claim rather than an omission.
//
// The other state axis is the hike profile: an empty install is not the app
// (FLOW_TESTING.md), so the rooms that matter are driven against the shared
// fixtures - a hike eight days in, and the same hike walked end to end.
//
// ENTRANCE: the Plan tab itself, and then the doors inside each room. Every
// one is a real tap from boot.
//
// EXIT: "What's left" carries its own way back to the hike, and the battery
// asks for it by name. A screen that can be opened and not left is the
// regression rule 2 exists for.

import { test, expect, type Page } from '@playwright/test'
import { seedPreferences, seedHikerMode, type HikerMode } from './support/seed'
import { seedLongHike, finishedStore } from '../preview-shots/fixtures/longHike.mjs'
import { seedDayHikes } from '../preview-shots/fixtures/dayHike.mjs'

/** Boot past first run in a given mode, and land on the Plan tab. The
 *  fixtures seed through `page.evaluate` + reload, so they need a navigation
 *  to have happened first - hence the goto before the seed rather than the
 *  init-script order support/seed.ts uses. */
async function planIn(
  page: Page,
  mode: HikerMode,
  seed?: (page: Page) => Promise<void>,
): Promise<void> {
  await seedPreferences(page)
  await seedHikerMode(page, mode)
  await page.goto('/')
  if (seed !== undefined) await seed(page)
  await page.getByRole('tab', { name: 'Plan' }).click()
  await expect(page.getByRole('tab', { name: 'Plan', selected: true })).toBeVisible()
}

test.describe('Plan', () => {
  test('states: a day hiker with nothing saved gets the day room’s own empty state', async ({
    page,
  }) => {
    await planIn(page, 'day')

    await expect(page.getByRole('heading', { name: 'Plan' })).toBeVisible()
    // The empty state is a sentence and a door, not a blank list - and the
    // door is the one this room actually ships (D10: absent rather than
    // disabled, everywhere).
    await expect(page.getByText(/No plan yet/)).toBeVisible()
    await expect(page.getByRole('button', { name: 'Start on the map' })).toBeVisible()
  })

  test('states: a volunteer gets the DAY room, because there is no third one', async ({
    page,
  }) => {
    // The forgotten third mode (FLOW_TESTING.md's mode axis). Asserting the
    // day room here is a positive claim about PlanStart.tsx's ternary, and
    // asserting no long-hike heading is what would catch a third room being
    // added without a decision.
    await planIn(page, 'volunteer')

    await expect(page.getByRole('heading', { name: 'Plan' })).toBeVisible()
    await expect(page.getByText(/No plan yet/)).toBeVisible()
    await expect(page.getByRole('button', { name: 'Start on the map' })).toBeVisible()
    // The long room's own control, absent - which is what "no third room"
    // means concretely, and what would catch one being added.
    await expect(page.getByRole('button', { name: 'Plan a section' })).toHaveCount(0)
  })

  test('states: a day hiker with a saved walk gets it on the day room’s shelf', async ({
    page,
  }) => {
    await planIn(page, 'day', seedDayHikes)

    await expect(page.getByRole('heading', { name: 'Day hikes' })).toBeVisible()
    await expect(page.getByRole('button', { name: /^Pine Meadow loop/ })).toBeVisible()
  })

  test('states: a long hiker with a hike gets the hike room, its sections and its doors', async ({
    page,
  }) => {
    await planIn(page, 'long', seedLongHike)

    await expect(page.getByRole('heading', { name: 'Springer → Katahdin' })).toBeVisible()
    // The room is about one hike, so the controls that say WHICH hike are
    // part of the state rather than decoration (#1344, #1367).
    await expect(page.getByRole('button', { name: /Switch hike/ })).toBeVisible()
    await expect(page.getByRole('button', { name: /Rename/ })).toBeVisible()
    // Both fixture sections, each naming its ends and its dates.
    // Anchored at the start: each row also has a "Take <section> out of this
    // hike" control whose accessible name contains the same ends, and an
    // unanchored pattern matches both (strict mode says so rather than
    // silently picking one). The dates are deliberately not matched - the
    // fixture dates itself relative to today, so a spec that pinned them
    // would pass in September and fail in March.
    await expect(
      page.getByRole('button', { name: /^Springer → Neels Gap/ }),
    ).toBeVisible()
    await expect(
      page.getByRole('button', { name: /^Neels Gap → Dicks Creek Gap/ }),
    ).toBeVisible()
    await expect(page.getByRole('button', { name: 'Plan a section' })).toBeVisible()
  })

  test('entrance and exit: What’s left opens on its two figures and goes back to the hike', async ({
    page,
  }) => {
    await planIn(page, 'long', seedLongHike)

    await page.getByRole('button', { name: /What’s left/ }).click()

    await expect(page.getByRole('heading', { name: /What’s left/ })).toBeVisible()
    // The two figures the battery names. Their labels, not their numbers:
    // the numbers are the fixture's, and pinning them would pin the fixture
    // rather than the screen (TESTING.md's rule, restated in FLOW_TESTING.md).
    await expect(page.getByText('Walked', { exact: true })).toBeVisible()
    await expect(page.getByText('To go', { exact: true })).toBeVisible()
    // The gaps, each naming both ends and offering the way into a plan.
    await expect(page.getByRole('button', { name: /North from/ })).toBeVisible()

    await page.getByRole('button', { name: /Back to the hike/ }).click()
    await expect(page.getByRole('heading', { name: 'Springer → Katahdin' })).toBeVisible()
    await expect(page.getByRole('heading', { name: /What’s left/ })).toHaveCount(0)
  })

  test('states and exit: a hike walked end to end lands on the walked shelf, and its zoom says so', async ({
    page,
  }) => {
    // The hike profile axis at its far end: the same fixture, walked. What
    // changes is not a number but the KIND of screen - a finished hike leaves
    // the planning room for the walked shelf (#1317) - and the row opens the
    // hike's own zoom (screens/HikeZoom.tsx), which is where both figures and
    // every section's state are printed together.
    await planIn(page, 'long', (p) => seedLongHike(p, finishedStore))

    const record = page.getByRole('button', { name: /mi walked · .* to go/ })
    await expect(record).toBeVisible()

    await record.click()
    await expect(
      page.getByRole('heading', { name: /Springer → Dicks Creek Gap/ }),
    ).toBeVisible()
    // Both fixture sections, counted rather than named: one ribbon band per
    // section is the zoom's own visual language for "these are its parts",
    // and each is labelled with what was done to it.
    await expect(page.getByRole('button', { name: /, walked$/ })).toHaveCount(2)
    // Both figures together at the head, which is what makes this the screen
    // a hiker checks their own progress from. Matched as text rather than by
    // role: the zoom prints them in one line inside the ribbon's head, which
    // is not a control.
    await expect(page.getByText(/MI WALKED · .* TO GO/i)).toBeVisible()
    // And each section is named under it. By text, because the row's
    // accessible name folds its badge and figures in and would have to be
    // matched whole - which would pin the fixture's dates.
    await expect(page.getByText('Springer → Neels Gap', { exact: true })).toBeVisible()
    await expect(
      page.getByText('Neels Gap → Dicks Creek Gap', { exact: true }),
    ).toBeVisible()

    // And it can be left. "‹ ALL YOUR PLANS" is the zoom's own way out, and a
    // screen reached from a shelf that could not be left would strand a hiker
    // on their own history.
    await page.getByRole('button', { name: /all your plans/i }).click()
    await expect(page.getByRole('heading', { name: 'Sections' })).toBeVisible()
  })
})
