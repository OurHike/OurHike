// First run (client/src/screens/Onboarding.tsx) - features/FLOW_TESTING.md's
// entrance/exit/states rules applied to the five-card flow.
//
// ENTRANCE: a fresh boot with nothing in IndexedDB shows card 1. No seeding
// here on purpose - this is the one screen a spec reaches by doing nothing.
//
// STATES: card 2's decision D10 ("no dead control") - the primary is absent
// until a mode is taken, not disabled.
//
// EXIT: skipping every card lands on Today, which is the app's actual home
// screen since #1054 - not an assumption, App.navigator.test.tsx already
// pins it and this proves the same claim in a real browser.

import { test, expect } from '@playwright/test'

test.describe('first run', () => {
  test('entrance: a fresh boot shows card 1, not the map or Today', async ({ page }) => {
    await page.goto('/')
    await expect(
      page.getByRole('heading', { name: 'A map that works where there is no signal.' }),
    ).toBeVisible()
    await expect(page.getByText('1 / 5')).toBeVisible()
    // Findable, not merely rendered: nothing else on this boot claims a tab.
    await expect(page.getByRole('tab', { name: 'Today' })).toHaveCount(0)
  })

  test('states: the mode card offers no primary until a mode is taken (D10)', async ({
    page,
  }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Get set up' }).click()
    await expect(
      page.getByRole('heading', { name: 'What brings you out?' }),
    ).toBeVisible()

    const modes = page.getByRole('radiogroup', { name: "Today I'm" })
    await expect(modes).toBeVisible()
    await expect(page.getByRole('button', { name: /^Continue as/ })).toHaveCount(0)

    await modes.getByRole('radio', { name: /^Long hike/ }).click()
    await expect(
      page.getByRole('button', { name: 'Continue as long hike' }),
    ).toBeVisible()
  })

  test("exit: card 1's Skip finishes the whole flow immediately, not just its own card", async ({
    page,
  }) => {
    // "Skip — take me to the map" is its own finish(false), not next() - a
    // hiker who skips from the very first card never sees cards 2-5 at all.
    await page.goto('/')
    await page.getByRole('button', { name: 'Skip — take me to the map' }).click()

    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    await expect(
      page.getByRole('heading', { name: 'A map that works where there is no signal.' }),
    ).toHaveCount(0)
  })

  test('exit: walking every card via Get set up, then skip/decide-later/not-now, lands on Today', async ({
    page,
  }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Get set up' }).click() // card 1 -> 2
    await page
      .getByRole('button', { name: 'Skip — day hike for now, change it on Today' })
      .click() // card 2, the mode -> 3
    await page.getByRole('button', { name: 'Skip — I’ll set this later' }).click() // card 3, the place -> 4
    await page.getByRole('button', { name: 'Decide this later' }).click() // card 4, the download -> 5
    await page.getByRole('button', { name: 'Not now' }).click() // card 5, location -> done

    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    // First run cannot be re-entered by going back to it - the guard against
    // asking the same five cards twice in one session.
    await expect(
      page.getByRole('heading', { name: 'A map that works where there is no signal.' }),
    ).toHaveCount(0)
  })
})
