// Trips, groups, and the sheet that folds a day hike into a long hike — the
// rooms under the Plan tab that a long hike's own structure opens, and the
// last of F8 that needs no published data.
//
// e2e/plan.spec.ts drives the two Plan homes; e2e/planRooms.spec.ts drives
// the rooms one level in. This file is the level under THAT: the list of
// every trip on a hike, the groups a hiker files them into, and the door
// that lets a day hike count toward a long one.
//
// HERMETIC, and that is worth saying because the sibling specs for these
// screens are not. A section's own figures are cached on the trip the
// fixture seeds, so the timeline and the trip list read them without a
// junction graph — the bucket is only needed to BUILD a section, which
// e2e/data/longSpine.spec.ts does.
//
// ENTRANCE. Every door is a real tap from boot. No navigator state is
// injected (features/FLOW_TESTING.md, "Not a router").

import { test, expect, type Page } from '@playwright/test'
// Untyped on purpose: a shot fixture is plain JavaScript, and its shape is
// the app's contract with IndexedDB rather than a type this spec restates.
import { seedLongHike } from '../preview-shots/fixtures/longHike.mjs'
import { seedPreferences, seedHikerMode } from './support/seed'

/** The Plan tab in long mode, with the fixture hike and its two sections. */
async function planRoom(page: Page): Promise<void> {
  await seedPreferences(page)
  await seedHikerMode(page, 'long')
  await page.goto('/')
  await seedLongHike(page)
  await page.getByRole('tab', { name: 'Plan' }).click()
  await expect(page.getByRole('button', { name: /Plan a section/ })).toBeVisible()
}

/** A section's timeline, which is where the trip list's door lives. */
async function aSectionsTimeline(page: Page): Promise<void> {
  await planRoom(page)
  await page.locator('.plan-home__row-open').first().click()
  await expect(page.getByRole('button', { name: /All \d+ trips/ })).toBeVisible()
}

test.describe('every trip on a hike', () => {
  test('entrance and states: the list says what each trip is, and what the hike has walked', async ({
    page,
  }) => {
    await aSectionsTimeline(page)
    await page.getByRole('button', { name: /All \d+ trips/ }).click()

    // THE HIKE'S OWN HEAD over the list, so a trip is read against the thing
    // it is part of rather than as a loose plan.
    await expect(page.getByText('Your sections')).toBeVisible()
    await expect(page.getByText(/[\d.,]+ mi walked · [\d.,]+ mi to go/)).toBeVisible()
    await expect(page.getByText(/\d+ trips? · \d+ days? walked/)).toBeVisible()

    // EVERY TRIP CARRIES ITS OWN STATE, and the three are different answers a
    // hiker plans differently around: one not started, one finished, one
    // begun. A list that showed only dates would make the second and third
    // look alike.
    // Case-insensitive: the chips are upper-cased by CSS, so `innerText`
    // shouts and the DOM text does not (the same trap e2e/data/followMode
    // records for the follow header). Matching the rendered spelling would be
    // asserting a stylesheet.
    await expect(page.getByText(/^walked$/i)).toBeVisible()
    await expect(page.getByText(/^part walked$/i)).toBeVisible()
    // And each is editable in place rather than through a settings screen.
    await expect(page.getByRole('button', { name: 'Rename' }).first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'Delete' }).first()).toBeVisible()
  })

  test('states: with no groups it says what a group IS, rather than showing an empty heading', async ({
    page,
  }) => {
    // THE README'S RULE FOR AN EMPTY STATE, and a good example of it: a
    // hiker who has never made a group does not know what one is for, so the
    // empty state is the explanation — "every Sunday, with Dad, this season"
    // — rather than the word "None".
    await aSectionsTimeline(page)
    await page.getByRole('button', { name: /All \d+ trips/ }).click()

    await expect(page.getByText('Your groups')).toBeVisible()
    await expect(
      page.getByText(/A group is any set of trips you want kept together/),
    ).toBeVisible()
    await expect(page.getByText(/every Sunday, with Dad, this season/)).toBeVisible()
    await expect(page.getByRole('button', { name: '+ New group' })).toBeVisible()
  })

  test('exit: the sheet closes on its own close, leaving the timeline behind it', async ({
    page,
  }) => {
    await aSectionsTimeline(page)
    await page.getByRole('button', { name: /All \d+ trips/ }).click()
    await expect(page.getByText('Your sections')).toBeVisible()

    await page.getByRole('button', { name: 'Close', exact: true }).click()

    await expect(page.getByText('Your sections')).toHaveCount(0)
    await expect(page.getByRole('button', { name: /All \d+ trips/ })).toBeVisible()
  })
})

test.describe('a group of trips', () => {
  test('states: a group is named before it exists, and opens on what it holds', async ({
    page,
  }) => {
    // screens/GroupScreen.tsx, which e2e/reportingDoors.spec.ts recorded as
    // having no reachable door — "nothing on the volunteer page reaches a
    // crew". That was true of the volunteer page and wrong about the app:
    // the door is here, two levels under the Plan tab, and a group has to be
    // MADE before there is one to open.
    await aSectionsTimeline(page)
    await page.getByRole('button', { name: /All \d+ trips/ }).click()

    await page.getByRole('button', { name: '+ New group' }).click()
    // Named in place rather than on a screen of its own: a group is one
    // field, and a screen for one field is a screen too many.
    const field = page.getByRole('textbox').last()
    await field.fill('Sundays with Dad')
    await page.getByRole('button', { name: 'Save', exact: true }).click()

    await expect(page.getByText('Sundays with Dad')).toBeVisible()
    // And the explanation goes, because there is now a group to look at.
    await expect(
      page.getByText(/A group is any set of trips you want kept together/),
    ).toHaveCount(0)

    // OPENED, not merely listed. Claiming this surface on the row alone
    // would be the walking-past the coverage ledger's own header forbids:
    // the group's screen is what `openGroup` mounts, and it REPLACES the
    // trip list rather than stacking over it — the one-thing-open rule every
    // other sheet in this shell keeps.
    await page
      .getByRole('button', { name: /Sundays with Dad/ })
      .first()
      .click()
    await expect(page.getByText('Your sections')).toHaveCount(0)
  })
})

test.describe('folding a day hike into a long hike', () => {
  test('states: the sheet says how a day hike counts, and is honest when there are none', async ({
    page,
  }) => {
    // THE RULE IS THE POINT, and it is the kind a hiker would otherwise have
    // to guess: a day hike joins a long hike like a section does, and one
    // that wandered off the trail still joins — only the miles ON the trail
    // are counted. Without that sentence a hiker would either not try it or
    // expect the side trail to count.
    await planRoom(page)
    await page.getByRole('button', { name: /Add a day hike to this hike/ }).click()

    const sheet = page.getByRole('dialog', { name: /Add a day hike to this hike/ })
    await expect(sheet).toBeVisible()
    await expect(
      sheet.getByText(/counts toward the hike like any section does/),
    ).toBeVisible()
    await expect(
      sheet.getByText(/only the miles on this trail are counted/i),
    ).toBeVisible()

    // THE EMPTY STATE NAMES WHAT WOULD FILL IT rather than saying "none":
    // this phone has no saved day hikes, and the sentence says what to do
    // about that — walk one on this trail.
    await expect(
      sheet.getByText(/No saved day hikes yet\. One you walk on this trail can join/),
    ).toBeVisible()
  })

  test('exit: closing the sheet leaves the hike room as it was', async ({ page }) => {
    await planRoom(page)
    await page.getByRole('button', { name: /Add a day hike to this hike/ }).click()
    const sheet = page.getByRole('dialog', { name: /Add a day hike to this hike/ })
    await expect(sheet).toBeVisible()

    await sheet.getByRole('button', { name: 'Close' }).click()

    await expect(page.getByRole('dialog', { name: /Add a day hike/ })).toHaveCount(0)
    await expect(page.getByRole('button', { name: /Plan a section/ })).toBeVisible()
  })
})
