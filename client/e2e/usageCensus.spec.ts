// Usage measurement's wiring, counted in a real browser (#1902).
//
// The unit tests pin each moment in isolation (lib/useUsageMeasurement.test.tsx)
// and the rows' shape against the server (lib/usageBatch.golden.test.ts). What
// neither can see is the wiring: App.tsx rendering the measurement at all, the
// chunk it loads arriving, first run's state reaching it before a fast Skip,
// and a relaunch closing the visit the last launch left open. A refactor that
// dropped any of those would pass every unit test and silently stop a metric -
// so this counts what the phone actually queues, and, against the
// backend-shaped build, what it actually sends.
//
// ENTRANCE: a fresh boot, and the More tab. EXIT: the counts themselves - the
// queue in IndexedDB (idb-keyval's store, e2e/support/idb.ts) and the
// requests e2e/support/backend.ts records.

import { test, expect, type Page } from '@playwright/test'

import { setBackendSignal, stubBackend } from './support/backend'
import { seedPreferences } from './support/seed'

/** The events waiting in the phone's usage queue, oldest first. */
function queuedEvents(page: Page): Promise<string[]> {
  return page.evaluate(
    () =>
      new Promise<string[]>((resolve, reject) => {
        const open = indexedDB.open('keyval-store')
        open.onupgradeneeded = () => open.result.createObjectStore('keyval')
        open.onerror = () => reject(open.error)
        open.onsuccess = () => {
          const read = open.result
            .transaction('keyval', 'readonly')
            .objectStore('keyval')
            .get('ourhike:usage')
          read.onerror = () => reject(read.error)
          read.onsuccess = () => {
            const rows = (read.result?.rows ?? []) as Array<{ row: { event: string } }>
            resolve(rows.map((queued) => queued.row.event))
          }
        }
      }),
  )
}

function count(events: string[], event: string): number {
  return events.filter((name) => name === event).length
}

test.describe('usage measurement, counted end to end', () => {
  test('a fresh install that skips first run is counted once, and its relaunch closes one visit', async ({
    page,
  }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Skip — take me to the map' }).click()
    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    await expect
      .poll(async () => count(await queuedEvents(page), 'app_installed'))
      .toBe(1)

    await page.reload()
    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()

    // The visit the first launch left open is ended at the second, dated the
    // day it began - and nothing about a relaunch is a new install or a sign-in.
    await expect.poll(async () => count(await queuedEvents(page), 'session')).toBe(1)
    const events = await queuedEvents(page)
    expect(count(events, 'app_installed')).toBe(1)
    expect(count(events, 'user_login')).toBe(0)
  })

  test('the map coming into view is counted once per arrival', async ({ page }) => {
    await seedPreferences(page)
    await page.goto('/')
    await page.getByRole('tab', { name: 'Map' }).click()
    await expect(page.getByRole('tab', { name: 'Map', selected: true })).toBeVisible()
    await expect
      .poll(async () => count(await queuedEvents(page), 'map_screen_viewed'))
      .toBe(1)

    await page.getByRole('tab', { name: 'Today' }).click()
    await page.getByRole('tab', { name: 'Map' }).click()

    await expect
      .poll(async () => count(await queuedEvents(page), 'map_screen_viewed'))
      .toBe(2)
    // An install that finished first run before this launch is not a new one.
    expect(count(await queuedEvents(page), 'app_installed')).toBe(0)
  })

  test('nothing waits once "Share usage statistics" is switched off', async ({
    page,
  }) => {
    await seedPreferences(page)
    await page.goto('/')
    await page.getByRole('tab', { name: 'Map' }).click()
    await expect.poll(async () => (await queuedEvents(page)).length).toBeGreaterThan(0)

    await page.getByRole('tab', { name: 'More' }).click()
    await page
      .locator('.more__row')
      .filter({ hasText: 'Safety & privacy' })
      .first()
      .click()
    const share = page.getByRole('checkbox', { name: 'Share usage statistics' })
    await expect(share).toBeChecked()
    await share.uncheck()

    await expect.poll(async () => (await queuedEvents(page)).length).toBe(0)
    // And nothing new is recorded while it stays off.
    await page.getByRole('tab', { name: 'Map' }).click()
    await expect(page.getByRole('tab', { name: 'Map', selected: true })).toBeVisible()
    expect(await queuedEvents(page)).toEqual([])
  })
})

test.describe('usage measurement, as sent', { tag: '@backend' }, () => {
  test('a first launch sends its rows without an account, once, and the queue empties', async ({
    page,
    context,
  }) => {
    const tokens: Array<string | undefined> = []
    const backend = await stubBackend(page, {
      'POST /usage-events': (request) => {
        tokens.push(request.headers()['authorization'])
        const events = (request.postDataJSON() as { events: unknown[] }).events
        return {
          status: 202,
          body: { accepted: events.length, duplicates: 0, refused: 0 },
        }
      },
    })

    await page.goto('/')
    await page.getByRole('button', { name: 'Skip — take me to the map' }).click()
    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    await expect
      .poll(async () => count(await queuedEvents(page), 'app_installed'))
      .toBe(1)

    // Signal lost and found - the moment a queue that has been waiting sends.
    await setBackendSignal(page, context, backend, { on: false })
    await setBackendSignal(page, context, backend, { on: true })

    const sent = () => backend.seen.filter((request) => request.path === '/usage-events')
    await expect.poll(() => sent().length, { timeout: 15_000 }).toBeGreaterThan(0)
    const [first] = sent()
    const body = first.body as { identified: boolean; events: Array<{ event: string }> }
    // Signed out: no yes to link, and nothing about an account in the rows.
    expect(body.identified).toBe(false)
    expect(tokens[0]).toBeUndefined()
    expect(body.events.map((row) => row.event)).toContain('app_installed')
    expect(JSON.stringify(body)).not.toMatch(/account|user_id|email/)
    await expect
      .poll(async () => count(await queuedEvents(page), 'app_installed'))
      .toBe(0)
  })
})
