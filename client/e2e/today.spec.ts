// Today (client/src/screens/Today.tsx) - the app's home screen since #1054.
//
// STATES: the setup head is mode-dependent and is the first thing a hiker
// with nothing planned sees - "Nothing planned today" for a day hiker and
// "You have no hike yet" for a long hiker are two different sentences for
// the same empty state, not one generic "nothing here yet" that would fit
// either mode and describe neither (features/FLOW_TESTING.md, rule 3).
//
// ENTRANCE: the pinned Find/Plan bar (chrome/PinnedBar.tsx) is on every
// state of this screen "forever", per its own header comment - so it is
// the one thing this file asserts in both states rather than in just one.
//
// EXIT: a tab switch away and back returns Today to its journal (#1284) -
// App.navigator.test.tsx already holds this at the rendered layer; this is
// the same claim in a real browser.

import { test, expect } from '@playwright/test'
import { seedPreferences, seedHikerMode } from './support/seed'

test.describe('Today', () => {
  test('states: day mode with nothing planned', async ({ page }) => {
    await seedPreferences(page)
    await page.goto('/')

    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    await expect(
      page.getByRole('heading', { name: 'Nothing planned today' }),
    ).toBeVisible()
    await expect(
      page.getByRole('group', { name: 'Find or plan a hike' }).getByRole('button', {
        name: 'Plan a hike',
      }),
    ).toBeVisible()
  })

  test('states: long mode with no hike taken', async ({ page }) => {
    await seedPreferences(page)
    await seedHikerMode(page, 'long')
    await page.goto('/')

    await expect(
      page.getByRole('heading', { name: 'You have no hike yet' }),
    ).toBeVisible()
    await expect(
      page.getByRole('group', { name: 'Find or plan a hike' }).getByRole('button', {
        name: 'Find a hike',
      }),
    ).toBeVisible()
  })

  test('exit: leaving Today for another tab and back resets it to the journal (#1284)', async ({
    page,
  }) => {
    await seedPreferences(page)
    await page.goto('/')

    await page.getByRole('tab', { name: 'Map' }).click()
    await expect(page.getByRole('tab', { name: 'Map', selected: true })).toBeVisible()

    await page.getByRole('tab', { name: 'Today' }).click()
    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    await expect(
      page.getByRole('heading', { name: 'Nothing planned today' }),
    ).toBeVisible()
  })
})
