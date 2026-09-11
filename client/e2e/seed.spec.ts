// The environment seed the Playwright test agents start from
// (`npx playwright init-agents`, features/FLOW_TESTING.md).
//
// WHAT A SEED FILE IS FOR. The planner and the generator each open the app
// before they explore or record anything, and they open it through this file:
// whatever state it leaves the page in is the state every generated test
// begins from. Playwright's own scaffold puts an empty `test('seed')` here
// with "generate code here" in the body, which would start every agent run on
// the first-run cards - so the first thing any generated test would record is
// five taps through onboarding, in front of whatever it was actually meant to
// be about.
//
// So this is the app past first run, which is where nearly every spec in this
// directory starts, written with the same helper they use
// (support/seed.ts's `seedPreferences`) rather than a second way of doing it.
// An agent that needs a different starting state - a hike seeded, a mode set,
// a fix granted - composes it from support/seed.ts and the shared fixtures,
// exactly as a hand-written spec does.
//
// IT IS ALSO A REAL TEST, and deliberately: it runs with the suite, so a seed
// that has quietly stopped working fails here, once, instead of failing
// mysteriously inside the next agent run. What it asserts is the least this
// file promises - the app is past first run and showing Today.

import { test, expect } from '@playwright/test'
import { seedPreferences } from './support/seed'

test.describe('agent seed', () => {
  test('boots past first run, onto Today', async ({ page }) => {
    await seedPreferences(page)
    await page.goto('/')

    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    // The entry cards are gone rather than merely behind something: an agent
    // exploring from here must not find a modal over the app.
    await expect(page.getByRole('button', { name: 'Get set up' })).toHaveCount(0)
  })
})
