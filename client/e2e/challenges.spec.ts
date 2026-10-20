// Challenges (#1780, features/CHALLENGES.md) - F13 in features/FLOW_TESTING.md's
// battery, the More row and the three screens behind it, and the camp card
// that is the whole of what a challenge asks a hiker on Today.
//
// ONE FLOW, END TO END, in the order a hiker lives it: join a list from
// Browse, walk past McAfee Knob, be asked at camp, tag it, and find it on the
// challenge's own page - with the tag waiting in the outbox, which is the only
// thing that leaves the phone.
//
// WHAT IS SEEDED, AND WHY THAT IS HONEST.
//   - The list arrives the way a refresh leaves it: the kept copy in
//     IndexedDB (lib/conditionsCache.ts). This project's build carries no
//     data URL, so nothing is fetched - the "works with no signal" half of
//     principle 4, which is the harder half.
//   - The day's walk is lib/passedToday.ts's own record - merged mile
//     intervals, no fixes - covering miles 710 to 716, which McAfee Knob
//     Summit (mile 714.92) sits inside. That record is exactly what the app
//     keeps instead of a track, so seeding it is seeding the real input.
//   - The clock is fixed at 7:30 pm, America/New_York, on a day inside the
//     ATC draft's window: the camp card waits for the day to be over, and
//     with no day called and no walk logged, the evening is what says so.
//
// Nothing here is anybody's: the ATC items are the published list's own, and
// no account, position or photo is involved.

import { test, expect, type Page } from '@playwright/test'
import { seedPreferences } from './support/seed'
import { readIDBEntry, writeIDBEntries } from './support/idb'
import { CHALLENGES_DOCUMENT } from '../preview-shots/fixtures/challenges.mjs'

const EVENING = new Date('2027-07-14T23:30:00Z')
const TODAY = '2027-07-14'

test.use({ timezoneId: 'America/New_York' })

async function arrive(page: Page): Promise<void> {
  await page.clock.setFixedTime(EVENING)
  await seedPreferences(page)
  await writeIDBEntries(page, [
    [
      'ourhike:conditions:challenges.json',
      { document: CHALLENGES_DOCUMENT, storedAt: '2027-07-10T12:00:00.000Z' },
    ],
  ])
  await page.addInitScript((day) => {
    localStorage.setItem(
      'ourhike:passed-today',
      JSON.stringify({ day, ranges: [{ startMile: 710, endMile: 716 }] }),
    )
  }, TODAY)
  await page.goto('/')
}

async function openChallenges(page: Page): Promise<void> {
  await page.getByRole('tab', { name: 'More' }).click()
  await page.locator('.more__row').filter({ hasText: 'Challenges' }).first().click()
  await expect(page.getByRole('heading', { name: 'Your challenges' })).toBeVisible()
}

test.describe('challenges', () => {
  test('entrance and exit: Challenges opens from its More row and goes back to More', async ({
    page,
  }) => {
    await arrive(page)
    await openChallenges(page)
    await page.getByRole('button', { name: 'More', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Your challenges' })).toHaveCount(0)
  })

  test('join from Browse, be asked at camp about what the walk passed, tag it, find it done', async ({
    page,
  }) => {
    await arrive(page)

    // Not joined yet: Today asks nothing, whatever the walk passed.
    await page.getByRole('tab', { name: 'Today' }).click()
    await expect(page.getByText('From today’s walk')).toHaveCount(0)

    // Join, from Browse. The draft is labelled where it is offered.
    await openChallenges(page)
    await page.getByRole('button', { name: /Browse/ }).click()
    await expect(page.getByRole('heading', { name: 'Browse challenges' })).toBeVisible()
    await expect(
      page.getByText('Draft · not yet confirmed by the ATC').first(),
    ).toBeVisible()
    await page.getByRole('button', { name: 'Join A.T. Summer Bucket List' }).click()

    // At camp: one card, and only what the day passed.
    await page.getByRole('tab', { name: 'Today' }).click()
    const card = page.locator('.challenge-camp')
    await expect(card).toBeVisible()
    await expect(card).toContainText('Take the McAfee Knob shuttle')
    await expect(card).not.toContainText(/Katahdin|Springer|Monson/)
    await card.getByRole('button', { name: 'Tag all' }).click()
    await expect(page.locator('.challenge-camp')).toHaveCount(0)

    // The challenge's own page: tagged from the day's walk, so "done". More
    // kept its page across the tab switch - the navigator's rule, "a hiker
    // who steps out ... comes back to the page they left" - so the tab opens
    // on Browse, and Back goes up to the list.
    await page.getByRole('tab', { name: 'More' }).click()
    await expect(page.getByRole('heading', { name: 'Browse challenges' })).toBeVisible()
    await page.getByRole('button', { name: 'Challenges', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Your challenges' })).toBeVisible()
    await page.getByRole('button', { name: /A\.T\. Summer Bucket List/ }).click()
    const mcafee = page
      .locator('.challenge-row')
      .filter({ hasText: 'Take the McAfee Knob shuttle' })
    await expect(mcafee).toContainText('done')

    // And the one thing that leaves the phone is queued: the item and when.
    await expect
      .poll(async () => {
        const queue = (await readIDBEntry(page, 'ourhike:outbox')) as Array<{
          challengeTag?: { challenge_id: string; item_id: string; how: string }
          authoredAt: string
        }> | null
        return (queue ?? []).flatMap((item) =>
          item.challengeTag ? [item.challengeTag] : [],
        )
      })
      .toContainEqual({
        challenge_id: 'atc-summer-bucket-list-2027',
        item_id: 'mcafee-knob',
        how: 'gps',
      })
  })

  test('the camp card does not come back after Not tonight, even on a reload', async ({
    page,
  }) => {
    await arrive(page)
    await openChallenges(page)
    await page.getByRole('button', { name: /Browse/ }).click()
    await page.getByRole('button', { name: 'Join A.T. Summer Bucket List' }).click()

    await page.getByRole('tab', { name: 'Today' }).click()
    await page
      .locator('.challenge-camp')
      .getByRole('button', { name: 'Not tonight' })
      .click()
    await expect(page.locator('.challenge-camp')).toHaveCount(0)

    await page.reload()
    await page.getByRole('tab', { name: 'Today' }).click()
    await expect(page.getByRole('heading', { name: /today/i }).first()).toBeVisible()
    await expect(page.locator('.challenge-camp')).toHaveCount(0)
  })
})
