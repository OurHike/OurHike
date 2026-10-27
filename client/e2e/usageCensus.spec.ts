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

/** Moves the visit in progress `minutes` into the past, as if the phone had
 *  been put away that long - the idle gap is half an hour
 *  (lib/usageEvents.ts `SESSION_IDLE_MS`), and a test does not wait it out. */
function ageVisit(page: Page, minutes: number): Promise<void> {
  return page.evaluate(
    (ms) =>
      new Promise<void>((resolve, reject) => {
        const open = indexedDB.open('keyval-store')
        open.onerror = () => reject(open.error)
        open.onsuccess = () => {
          const store = open.result
            .transaction('keyval', 'readwrite')
            .objectStore('keyval')
          const read = store.get('ourhike:usage')
          read.onsuccess = () => {
            const usage = read.result
            if (usage?.session) {
              usage.session.startedAt -= ms
              usage.session.lastSeenAt -= ms
            }
            const write = store.put(usage, 'ourhike:usage')
            write.onsuccess = () => resolve()
            write.onerror = () => reject(write.error)
          }
        }
      }),
    minutes * 60_000,
  )
}

test.describe('usage measurement, counted end to end', () => {
  test('a fresh install that skips first run is counted once, and a relaunch continues its visit until the idle gap has passed', async ({
    page,
  }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Skip — take me to the map' }).click()
    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    await expect
      .poll(async () => count(await queuedEvents(page), 'app_installed'))
      .toBe(1)

    // Back within half an hour: the same visit, not a second one (#1903's
    // review - a killed app or an OAuth redirect counted two).
    await page.reload()
    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
    await expect.poll(async () => (await queuedEvents(page)).length).toBeGreaterThan(0)
    expect(count(await queuedEvents(page), 'session')).toBe(0)

    // Back after longer: the visit the last launch left open is ended at this
    // one, dated the day it began - and nothing about a relaunch is a new
    // install or a sign-in.
    await ageVisit(page, 45)
    await page.reload()
    await expect(page.getByRole('tab', { name: 'Today', selected: true })).toBeVisible()
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

    // Signal lost and found - the moment a queue that has been waiting sends.
    // The install may already have left with the launch's own send; either
    // way it is what was SENT that is judged, not the queue in between.
    await setBackendSignal(page, context, backend, { on: false })
    await setBackendSignal(page, context, backend, { on: true })

    const sent = () => backend.seen.filter((request) => request.path === '/usage-events')
    const bodies = () =>
      sent().map(
        (request) =>
          request.body as { identified: boolean; events: Array<{ event: string }> },
      )
    const installsSent = () =>
      bodies()
        .flatMap((body) => body.events)
        .filter((row) => row.event === 'app_installed').length
    await expect.poll(installsSent, { timeout: 15_000 }).toBe(1)
    // Signed out: no yes to link, and nothing about an account in the rows.
    for (const body of bodies()) {
      expect(body.identified).toBe(false)
      expect(JSON.stringify(body)).not.toMatch(/account|user_id|email/)
    }
    expect(tokens.every((token) => token === undefined)).toBe(true)
    await expect
      .poll(async () => count(await queuedEvents(page), 'app_installed'))
      .toBe(0)
  })
})
