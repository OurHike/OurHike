// The day-5 ask and More → Your support (#1876 - Ask every hiker to choose
// what they give after their fifth day of use, $0 included, and take payment
// only on the website), against the stubbed backend (`@backend`,
// e2e/support/backend.ts).
//
// screens/SupportAsk.tsx and screens/YourSupport.tsx were `planned` in
// src/test/flowCoverage.ts because "a flow spec needs a stubbed API the suite
// does not have yet", which stopped being true when #1643 - The org console's
// permission matrix skips ten endpoints, and the position mark and outbox
// drain have no end-to-end test - gave the suite e2e/support/backend.ts.
// lib/support.test.ts holds `shouldAsk`'s rules, SupportAsk.test.tsx the
// window's three views and YourSupport.test.tsx the page's states, each with
// the API mocked at the module. What none of them can see is the launch:
// screens/SupportGate.tsx loading after the first frame (screens/deferred.ts),
// reading the day count lib/activeDays.ts kept in localStorage, waiting for
// the stored session and the account's answer, and opening the window over
// Today within its fifteen-second window with nobody having tapped - or not
// opening it, a day early. Nor what a paid choice does to the browser:
// `window.location.assign` to a page that is not this app, with no field
// anywhere in the window a card number could go into. Nor that a Stop on the
// page reaches the More row through lib/useSupport.ts's window event.
//
// THE WEB BUILD, WHICH IS WHAT PLAYWRIGHT DRIVES. In the store apps a paid
// choice is email-only ("Email me how to set it up") and offered only on a US
// store account (lib/storefront.ts); here `Capacitor.isNativePlatform()` is
// false, `usePaidChoiceAllowed` answers true at once, and a paid choice goes
// to the payment page by `delivery: 'redirect'`. What this asserts is the
// website's behaviour and nothing about the shells.
//
// THE DAY COUNT IS SEEDED, NOT WAITED FOR. lib/activeDays.ts counts a day on
// the first tap of each local date, so "the fifth day" is a localStorage
// record of four days with the last one yesterday, which `daysIncludingToday`
// reads as five at launch. A test cannot wait five days; it can put the phone
// on day four and on day five and read what each launch does.
//
// ENTRANCE: the ask opens itself over Today on launch; Your support is More's
// own row. EXIT: the ask closes on an answer - there is no "Not now", by the
// maintainer's choice - and the page goes back to More.

import { test, expect, type Page } from '@playwright/test'

import {
  BACKEND_ORIGIN,
  seedSession,
  sent,
  stubBackend,
  type Recorded,
} from './support/backend'
import { seedPreferences } from './support/seed'
import { queuedUsageRows } from './support/usage'

/** lib/activeDays.ts's key and shape - the wire contract with localStorage,
 *  not imported, for support/seed.ts's reason. */
const ACTIVE_DAYS_KEY = 'ourhike:active-days'
/** lib/support.ts's LOCAL_CHOICE_KEY: the $0 record this phone keeps. */
const LOCAL_CHOICE_KEY = 'ourhike:support'

/**
 * Put the phone `days` distinct days into this year, the last of them
 * yesterday, so this launch is day `days + 1`. Written once, before the first
 * navigation, and left alone on later ones: a record a test writes itself
 * (to move the phone on a day) survives the reload that makes the app read it.
 */
async function seedActiveDays(page: Page, days: number): Promise<void> {
  await page.addInitScript(
    ({ key, days }) => {
      if (localStorage.getItem(key) !== null) return
      const now = new Date()
      const last = new Date(now.getTime() - 86_400_000)
      const pad = (value: number) => String(value).padStart(2, '0')
      localStorage.setItem(
        key,
        JSON.stringify({
          year: now.getFullYear(),
          days,
          last: `${last.getFullYear()}-${pad(last.getMonth() + 1)}-${pad(last.getDate())}`,
        }),
      )
    },
    { key: ACTIVE_DAYS_KEY, days },
  )
}

/** The same record, written now - for moving a phone already booted. */
async function moveToDay(page: Page, days: number): Promise<void> {
  await page.evaluate(
    ({ key, days }) => {
      const now = new Date()
      const last = new Date(now.getTime() - 86_400_000)
      const pad = (value: number) => String(value).padStart(2, '0')
      localStorage.setItem(
        key,
        JSON.stringify({
          year: now.getFullYear(),
          days,
          last: `${last.getFullYear()}-${pad(last.getMonth() + 1)}-${pad(last.getDate())}`,
        }),
      )
    },
    { key: ACTIVE_DAYS_KEY, days },
  )
}

/**
 * `GET /support/me`'s answer, as backend app/schemas/support.py sends it
 * (lib/api.ts's SupportSummary): nothing chosen unless overridden.
 */
function summary(overrides: Record<string, unknown> = {}) {
  return {
    status: 'none',
    amount_cents: null,
    cadence: null,
    provider: null,
    provider_label: null,
    email: null,
    chosen_at: null,
    started_at: null,
    period_end: null,
    stop_requested_at: null,
    ended_at: null,
    supporting: false,
    can_stop: false,
    can_choose: true,
    support_emails: true,
    ...overrides,
  }
}

/** The requests to one exact path, by method - `sent` matches a prefix, and
 *  `/support/me` is a prefix of `/support/me/stop`. */
function exactly(seen: readonly Recorded[], method: string, path: string): Recorded[] {
  return sent(seen, method, path).filter((entry) => entry.path === path)
}

const ask = (page: Page) => page.getByRole('dialog', { name: 'Choose what you give' })

/** More's own row for the page. Matched from the start of its name, because
 *  the row's accessible name carries its summary line ("Stopped", "$0 this
 *  year") and that line is what the tests below change. */
const supportRow = (page: Page) => page.getByRole('button', { name: /^Your support/ })

/** More → Your support. */
async function openYourSupport(page: Page): Promise<void> {
  await page.getByRole('tab', { name: 'More' }).click()
  await supportRow(page).click()
  await expect(page.getByRole('heading', { name: 'Your support' })).toBeVisible()
}

/** screens/SupportGate.tsx's answer for this launch, on `<html>`: "asked"
 *  or "not-asked", written once when the gate decides. */
const decision = (page: Page) => page.locator('html')

test.describe('the day-5 ask', { tag: '@backend' }, () => {
  test('the ask opens by itself on the fifth active day (ASK_ON_DAY) and not on the fourth', async ({
    page,
  }) => {
    const backend = await stubBackend(page, {
      'GET /support/me': { status: 200, body: summary() },
    })
    // Signed in, so the gate decides on the account's answer, the first time
    // it has settled (screens/SupportGate.tsx).
    await seedSession(page)
    await seedActiveDays(page, 3)
    await seedPreferences(page)
    await page.goto('/')

    // THE FOURTH DAY: the gate has decided, on the account's answer, and
    // decided not to ask. A "no" draws nothing, so what is waited on is the
    // gate's own answer on `<html data-support-ask>`. The browser having the
    // answer to `/support/me` would not do: that still leaves the gate a
    // parse, two state updates, an effect and two renders from deciding.
    // Checked 2026-11-04 by setting lib/support.ts's ASK_ON_DAY to
    // 4: the wait went red on 3 of 3 runs, the attribute reading "asked", and
    // green on 3 of 3 with it back at 5.
    await expect(decision(page)).toHaveAttribute('data-support-ask', 'not-asked')
    expect(exactly(backend.seen, 'GET', '/support/me')).toHaveLength(1)
    await expect(ask(page)).toHaveCount(0)

    // THE FIFTH: the same phone, one more day, relaunched - no tap in
    // between, because a tap before the gate decides is "the hiker is using
    // the app" and the ask would rightly wait for the next launch.
    await moveToDay(page, 4)
    await page.reload()
    await expect(ask(page)).toBeVisible()
    await expect(ask(page)).toContainText(/used OurHike on 5 days this year/)
    // REQUIRED, AND $0 IS ONE OF THE ANSWERS: no "Not now", and the fourth
    // option is the one that keeps everything working for nothing.
    await expect(ask(page).getByRole('button', { name: 'Not now' })).toHaveCount(0)
    await expect(ask(page).getByRole('radio', { name: /^\$0/ })).toBeVisible()
    await expect(ask(page)).toContainText(
      /Any choice, including \$0, keeps everything working/,
    )
  })

  test('$0 is kept on a signed-in phone with no PUT /support/me, and queues one support_chosen row at 0 cents', async ({
    page,
  }) => {
    const backend = await stubBackend(page, {
      // SIGNED IN, so a $0 sent to the server would arrive here as a PUT:
      // lib/api.ts's `authedFetch` throws before making any request when
      // there is no token, and a signed-out phone could never show one.
      'GET /support/me': { status: 200, body: summary() },
      'POST /usage-events': (request) => ({
        status: 202,
        body: {
          accepted: (request.postDataJSON() as { events: unknown[] }).events.length,
          duplicates: 0,
          refused: 0,
        },
      }),
    })
    await seedSession(page)
    await seedActiveDays(page, 4)
    await seedPreferences(page)
    await page.goto('/')
    await expect(ask(page)).toBeVisible()
    await expect(ask(page)).toContainText(
      /Payments happen on a payment page, never in the app/,
    )

    await ask(page).getByRole('radio', { name: /^\$0/ }).click()
    await ask(page).getByRole('button', { name: 'Continue' }).click()

    // THE ONCE-A-YEAR NUDGE, with "Keep it at $0" on screen and readable -
    // the maintainer's choice over a second confirm step.
    const nudge = page.getByRole('dialog', { name: 'Before you pick $0' })
    await expect(nudge).toBeVisible()
    await expect(nudge).toContainText('You picked $0')
    await expect(nudge).toContainText(/\$0 is a real answer/)
    await nudge.getByRole('button', { name: /keep it at \$0/i }).click()

    // ANSWERED: the window is gone, and the map was never left.
    await expect(
      page.getByRole('dialog', { name: /Before you pick \$0|Choose what you give/ }),
    ).toHaveCount(0)
    expect(new URL(page.url()).origin).toBe(BACKEND_ORIGIN)
    // NO LINK: $0 stays on this phone, kept for the year.
    const local = await page.evaluate(
      (key) => JSON.parse(localStorage.getItem(key) ?? 'null') as { year: number } | null,
      LOCAL_CHOICE_KEY,
    )
    const year = await page.evaluate(() => new Date().getFullYear())
    expect(local?.year).toBe(year)
    // COUNTED, ONCE, AT $0 - the `support_chosen` row usage measurement
    // queues when lib/support.ts announces the answer (#1902 - Count six usage
    // events with a sealed account id and GPS fix, keep them six months, close
    // each month into a table, and report them per club).
    await expect
      .poll(async () =>
        (await queuedUsageRows(page)).filter((row) => row.event === 'support_chosen'),
      )
      .toHaveLength(1)
    const [row] = (await queuedUsageRows(page)).filter(
      (row) => row.event === 'support_chosen',
    )
    expect(JSON.stringify(row)).toContain('"support_cents":0')

    // AND YOUR SUPPORT SAYS SO, in the year's own words.
    await openYourSupport(page)
    await expect(
      page.getByText(`You chose $0 for ${year}.`, { exact: false }),
    ).toBeVisible()
    await expect(page.getByRole('button', { name: 'Choose an amount' })).toBeVisible()

    // NO CALL, judged last: Your support's own GET /support/me, which the
    // page makes after the answer, has arrived, so anything the answer sent
    // left the phone before it. Checked 2026-11-04 by having SupportAsk's
    // `keepZero` also send the $0 through `chooseSupport`: red on 3 of 3
    // runs, one PUT recorded, and green on 3 of 3 without it.
    await expect.poll(() => exactly(backend.seen, 'GET', '/support/me').length).toBe(2)
    expect(exactly(backend.seen, 'PUT', '/support/me')).toHaveLength(0)
  })

  test('a paid choice sends PUT /support/me with delivery "redirect" and lands on its checkout_url, with no card field in the window', async ({
    page,
  }) => {
    // The payment page is not this app: an https page on another origin,
    // answered here so the navigation has somewhere to land.
    const CHECKOUT = 'https://pay.example.invalid/checkout/e2e'
    await page.route(CHECKOUT, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'text/html; charset=utf-8',
        body: '<!doctype html><title>Payment page (example)</title><h1>Payment page (example)</h1>',
      }),
    )
    const backend = await stubBackend(page, {
      'GET /support/me': { status: 200, body: summary() },
      'PUT /support/me': () => {
        return {
          status: 200,
          body: {
            support: summary({
              status: 'pending',
              amount_cents: 1200,
              cadence: 'year',
              chosen_at: new Date().toISOString(),
              can_stop: true,
            }),
            checkout_url: CHECKOUT,
            emailed: false,
          },
        }
      },
    })
    await seedSession(page)
    await seedActiveDays(page, 4)
    await seedPreferences(page)
    await page.goto('/')
    await expect(ask(page)).toBeVisible()

    await ask(page)
      .getByRole('radio', { name: /^\$12 a year/ })
      .click()
    await ask(page).getByRole('button', { name: 'Continue' }).click()

    const confirm = page.getByRole('dialog', { name: 'Confirm your choice' })
    await expect(confirm.getByRole('heading', { name: '$12 a year' })).toBeVisible()
    await expect(confirm).toContainText('Your receipt goes to hiker@example.org')
    await expect(confirm).toContainText(/Stop any time: More → Your support → Stop/)
    // NO CARD FIELD: nothing anywhere in the window takes typing. Payment
    // never happens in the app (lib/support.ts), and a field here would be
    // the first sign it had started to.
    await expect(confirm.locator('input, textarea, select')).toHaveCount(0)
    await expect(confirm.locator('[autocomplete*="cc-"]')).toHaveCount(0)

    await confirm.getByRole('button', { name: 'Continue to payment' }).click()

    // HANDED TO THE LINK THE SERVER GAVE, on its own origin.
    await page.waitForURL(CHECKOUT)
    await expect(
      page.getByRole('heading', { name: 'Payment page (example)' }),
    ).toBeVisible()
    // What the server was told: the tier, the website's delivery, the usage
    // switch's state, and the account it is for.
    const puts = exactly(backend.seen, 'PUT', '/support/me')
    expect(puts).toHaveLength(1)
    expect(puts[0].body).toMatchObject({
      amount_cents: 1200,
      delivery: 'redirect',
      accounting_email: false,
      usage_counts: true,
    })
    expect(puts[0].authorization).toMatch(/^Bearer /)
  })
})

test.describe('More → Your support', { tag: '@backend' }, () => {
  test('Stop on a pending choice reads "Stopped" on the page and on the More row, with no further GET /support/me', async ({
    page,
  }) => {
    const chosenAt = new Date(Date.now() - 86_400_000).toISOString()
    const pending = summary({
      status: 'pending',
      amount_cents: 1200,
      cadence: 'year',
      provider: 'stripe',
      provider_label: 'Stripe',
      email: 'hiker@example.org',
      chosen_at: chosenAt,
      can_stop: true,
      can_choose: true,
    })
    // A pending choice has nothing to cancel and is `stopped` at once
    // (backend app/routers/support.py's `stop_support`), with nothing ever
    // started.
    const stopped = summary({
      status: 'stopped',
      amount_cents: 1200,
      cadence: 'year',
      provider: 'stripe',
      provider_label: 'Stripe',
      email: 'hiker@example.org',
      chosen_at: chosenAt,
      ended_at: new Date().toISOString(),
      can_stop: false,
      can_choose: true,
    })
    const backend = await stubBackend(page, {
      'GET /support/me': { status: 200, body: pending },
      'POST /support/me/stop': { status: 200, body: stopped },
    })
    await seedSession(page)
    // No day count seeded: day one, so the ask stays out of the way and the
    // page is reached through More alone.
    await seedPreferences(page)
    await page.goto('/')
    await expect(
      page.getByRole('button', { name: 'Account, signed in as hiker@example.org' }),
    ).toBeVisible()

    // The More row reads the gate's copy of the account's answer before
    // anything is stopped.
    await page.getByRole('tab', { name: 'More' }).click()
    await expect(supportRow(page)).toContainText('$12 a year, waiting to be confirmed')

    await supportRow(page).click()
    await expect(page.getByRole('heading', { name: 'Your support' })).toBeVisible()
    // THE PENDING CHOICE, as the server holds it: the amount, and that it
    // waits on the payment.
    await expect(page.getByText('$12 a year', { exact: true })).toBeVisible()
    await expect(page.getByText(/waiting for the payment to be confirmed/)).toBeVisible()
    // Two reads so far, and both expected: the gate's at launch, and the
    // page's own (screens/YourSupport.tsx's YourSupportPage holds a second
    // lib/useSupport.ts, so the shell holds none of it).
    await expect.poll(() => exactly(backend.seen, 'GET', '/support/me').length).toBe(2)

    // ONE TAP AND ONE CONFIRM, and the confirm says what stopping does.
    await page.getByRole('button', { name: 'Stop my support' }).click()
    const confirm = page.getByRole('group', { name: 'Stop your support' })
    await expect(confirm).toContainText('Stop $12 a year?')
    await expect(confirm).toContainText(/\$0 is fine/)
    await confirm.getByRole('button', { name: 'Yes, stop it' }).click()

    // STOPPED, in the page's own words for a choice nobody paid.
    await expect(page.getByText('Stopped', { exact: true })).toBeVisible()
    await expect(
      page.getByText(/Nothing was paid, so nothing needed cancelling/),
    ).toBeVisible()
    await expect(page.getByRole('button', { name: 'Stop my support' })).toHaveCount(0)
    await expect(
      page.getByRole('button', { name: 'Choose an amount again' }),
    ).toBeVisible()
    expect(exactly(backend.seen, 'POST', '/support/me/stop')).toHaveLength(1)

    // AND THE MORE ROW SAYS SO TOO, without a fetch: the page's answer
    // reaches the gate's own copy through lib/useSupport.ts's window event
    // (the fourth review of #1885 - Ask every hiker to choose what they give
    // after day five, $0 included, and pay only on the website - found the
    // row still reading the old amount).
    // So no third GET - a row that only caught up by asking again would be
    // the window event gone and a fetch hiding it.
    await page.getByRole('button', { name: 'More', exact: true }).click()
    await expect(supportRow(page)).toContainText('Stopped')
    expect(exactly(backend.seen, 'GET', '/support/me')).toHaveLength(2)
  })
})
