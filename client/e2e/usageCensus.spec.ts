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
// queue in IndexedDB (idb-keyval's store, read by e2e/support/usage.ts) and
// the requests e2e/support/backend.ts records.

import { test, expect } from '@playwright/test'

import { seedSession, setBackendSignal, stubBackend } from './support/backend'
import { seedPreferences } from './support/seed'
import { readIDBEntry } from './support/idb'
import { ageVisit, count, queuedEvents } from './support/usage'

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

/** One `POST /usage-events` as it arrived: the body's own `identified`, the
 *  Authorization header it carried, and the events in it. */
interface UsageBatch {
  identified: boolean
  token: string | undefined
  events: string[]
}

test.describe('usage measurement, linked to an account', { tag: '@backend' }, () => {
  test('ticking "Link them to my account" sends the next batch identified: true with a token, and unticking sends the one after with neither', async ({
    page,
    context,
  }) => {
    // The link of #1902 - Count six usage events with a sealed account id and
    // GPS fix, keep them six months, close each month into a table, and report
    // them per club - end to end: lib/usageQueue.ts's `sendUsageBatch` sends a
    // batch `identified: true`, with the session's token, only for rows
    // recorded under the account while the hiker's yes stands - and holds
    // linked rows back until that yes has reached the account
    // (lib/useUsageMeasurement.ts's `consentSyncs`). So the account's
    // preferences are answered too: none yet (404), and every push taken.
    const pushes: Array<{ measurement_linked?: unknown }> = []
    const backend = await stubBackend(page, {
      'GET /preferences/me': { status: 404, body: { detail: 'no preferences yet' } },
      'PUT /preferences/me': (request) => {
        const body = request.postDataJSON() as { measurement_linked?: unknown }
        pushes.push(body)
        return { status: 200, body: { ...body, updated_at: new Date().toISOString() } }
      },
      'POST /usage-events': (request) => {
        const events = (request.postDataJSON() as { events: unknown[] }).events
        return {
          status: 202,
          body: { accepted: events.length, duplicates: 0, refused: 0 },
        }
      },
    })
    const batches = (): UsageBatch[] =>
      backend.seen
        .filter(
          (request) => request.method === 'POST' && request.path === '/usage-events',
        )
        .map((request) => {
          const body = request.body as {
            identified: boolean
            events: Array<{ event: string }>
          }
          return {
            identified: body.identified,
            token: request.authorization,
            events: body.events.map((row) => row.event),
          }
        })
    await seedSession(page)
    // Signed in, with "no" as the standing answer to linking.
    await seedPreferences(page, { measurement_linked: false })
    await page.goto('/')
    await expect(
      page.getByRole('button', { name: 'Account, signed in as hiker@example.org' }),
    ).toBeVisible()

    /**
     * The map coming into view - a row recorded as things stand - then signal
     * lost and found, the moment a waiting queue sends. Returns the batches
     * from `from` on, once one of them has carried that row. WHAT WAS SENT IS
     * JUDGED, NEVER THE QUEUE IN BETWEEN: a flush already under way can take
     * the row the moment it is recorded, and a first draft that counted the
     * queue went red on 1 run in 8 for exactly that.
     */
    const viewTheMapAndSend = async (from: number) => {
      await page.getByRole('tab', { name: 'Map' }).click()
      await expect(page.getByRole('tab', { name: 'Map', selected: true })).toBeVisible()
      await setBackendSignal(page, context, backend, { on: false })
      await setBackendSignal(page, context, backend, { on: true })
      const carried = () =>
        batches()
          .slice(from)
          .filter((batch) => batch.events.includes('map_screen_viewed'))
      await expect.poll(() => carried().length, { timeout: 15_000 }).toBeGreaterThan(0)
      return carried()
    }
    const linkSwitch = page.getByRole('checkbox', { name: 'Link them to my account' })
    /** The consent answers this phone has given and not yet pushed - what
     *  `holdLinked` reads before a linked batch may leave. */
    const unpushedConsent = async () =>
      (
        (await readIDBEntry(page, 'ourhike:preferences:sync')) as
          { consentTouched?: string[] } | undefined
      )?.consentTouched ?? []

    // UNLINKED TO BEGIN WITH: a row recorded under the standing no goes
    // anonymous. (A launch past first run queues nothing of its own to send.)
    const before = await viewTheMapAndSend(0)
    for (const batch of batches()) {
      expect(batch.identified).toBe(false)
      expect(batch.token).toBeUndefined()
    }
    expect(before.length).toBeGreaterThan(0)

    // TICKED, and the yes reaches the account before anything goes linked.
    await page.getByRole('tab', { name: 'More' }).click()
    await page.getByRole('button', { name: /^Safety & privacy/ }).click()
    await expect(linkSwitch).not.toBeChecked()
    await linkSwitch.check()
    await expect
      .poll(() => pushes.some((body) => body.measurement_linked === true))
      .toBe(true)
    await expect.poll(unpushedConsent).toEqual([])
    const linkedFrom = batches().length
    const linked = await viewTheMapAndSend(linkedFrom)
    // The row recorded under the yes went linked, with the session's token.
    for (const batch of linked) {
      expect(batch.identified).toBe(true)
      expect(batch.token).toMatch(/^Bearer /)
    }

    // UNTICKED: the next row recorded goes anonymous again, with no token.
    // (The launch's own push already carried `false`, so the no is looked for
    // among the pushes after the untick.)
    await page.getByRole('tab', { name: 'More' }).click()
    const pushedBefore = pushes.length
    await linkSwitch.uncheck()
    await expect
      .poll(() =>
        pushes.slice(pushedBefore).some((body) => body.measurement_linked === false),
      )
      .toBe(true)
    const unlinkedFrom = batches().length
    await viewTheMapAndSend(unlinkedFrom)
    for (const batch of batches().slice(unlinkedFrom)) {
      expect(batch.identified).toBe(false)
      expect(batch.token).toBeUndefined()
    }
  })
})
