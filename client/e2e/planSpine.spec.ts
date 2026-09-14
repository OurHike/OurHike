// Step 1 of the planning spine (client/src/screens/PlanStart.tsx, #1373,
// decisions D2/D6) - "Where do you want to go?"
//
// ENTRANCE: reached from Today's pinned Plan button, the same door
// App.pathway.test.tsx already drives at the rendered layer - this proves
// the same door is findable in a real browser.
//
// STATES: day mode refuses when the trail network is not on this phone
// (decision D10 - a sentence, never a disabled control); long mode never
// does, because `dayRefused` in PlanStart.tsx is `planMode === 'day' && ...`
// - a real, code-level asymmetry between the two modes, not a guess at what
// "loading" and "error" states generically look like.
//
// EXIT: Cancel lands back in Plan's room, never stuck on the spine with
// nothing routed - lib/navigator.ts's own comment: "leaving one by Cancel
// lands in Plan's room whatever door opened it."

import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'
import { seedPreferences, seedHikerMode } from './support/seed'

async function openStepOne(page: Page): Promise<void> {
  await page
    .getByRole('group', { name: 'Find or plan a hike' })
    .getByRole('button', { name: 'Plan a hike' })
    .click()
  await expect(
    page.getByRole('heading', { name: 'Where do you want to go?' }),
  ).toBeVisible()
}

test.describe('step 1 - Where do you want to go?', () => {
  test("entrance: reached from Today's pinned bar, under the Plan tab", async ({
    page,
  }) => {
    await seedPreferences(page)
    await page.goto('/')

    await openStepOne(page)
    await expect(page.getByRole('tab', { name: 'Plan', selected: true })).toBeVisible()
    // The retired kind sheet's question (chrome/PlanKindSheet.tsx, decision
    // D6) is not asked anywhere on the way - a regression that brought it
    // back would be exactly the "same fork asked twice" defect this spine
    // exists to fix.
    await expect(page.getByText(/what are you planning/i)).toHaveCount(0)
  })

  test('states: day mode refuses with no trail network on this phone (D10)', async ({
    page,
  }) => {
    await seedPreferences(page)
    await page.goto('/')

    await openStepOne(page)
    await expect(page.getByRole('group', { name: 'Start from' })).toHaveCount(0)
    await expect(page.getByRole('note')).toBeVisible()
  })

  test('states: long mode never refuses step 1, regardless of the trail network', async ({
    page,
  }) => {
    await seedPreferences(page)
    await seedHikerMode(page, 'long')
    await page.goto('/')

    await openStepOne(page)
    const doors = page.getByRole('group', { name: 'Start from' })
    await expect(doors).toBeVisible()
    await expect(doors.getByRole('button', { name: 'Pick on the map' })).toBeVisible()
    await expect(page.getByRole('note')).toHaveCount(0)
  })

  test("exit: Cancel leaves the spine and lands in Plan's room", async ({ page }) => {
    await seedPreferences(page)
    await page.goto('/')

    await openStepOne(page)
    await page.getByRole('button', { name: 'Cancel' }).click()

    await expect(
      page.getByRole('heading', { name: 'Where do you want to go?' }),
    ).toHaveCount(0)
    await expect(page.getByRole('tab', { name: 'Plan', selected: true })).toBeVisible()
  })
})
