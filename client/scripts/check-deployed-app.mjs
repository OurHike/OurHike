// Loads the deployed app in a real browser and asks whether it draws a trail.
//
// Tier 2 of #431, tracked in #467. `pipeline/check_deployment.py` (tier 1)
// proves the bucket will answer a browser; only this proves the *app* works.
// They are different questions and both have failed independently:
//
//   tier 1   can a browser REACH the data          daily, no downloads
//   tier 2   does the APP draw a trail with it     daily, one real page load
//
// WHY A BROWSER AND NOT ANOTHER FETCH. #427 took the map down for eight days
// while every check stayed green, because none of them was a browser. Tier 1
// closed that by sending an `Origin` header. It still cannot see a build that
// shipped without its data URL, a service worker serving a stale shell, a
// bundle that throws before the first fetch, or a CORS rule that passes a
// bare GET and fails the app's real request. All of those are "the map is
// broken" and none of them is visible to curl.
//
// SILENCE IS NOT SUCCESS, and this is the trap the check is written around.
// #431 specifies the assertion as "the status strip does not say *No trail
// line*, and no data-error notice is showing". Both are NEGATIVE, and the app
// only raises them once a download has failed - so a build that never gets as
// far as requesting anything shows neither, and a purely negative check would
// call that healthy. `App.tsx` makes it explicit: `trailLinesMissing` is
// `!haveTrailLines && dataError !== null`, so with no error there is no flag,
// whether or not a trail exists.
//
// So the negative assertions are kept AND a positive one is added: the page
// must actually have received the trail artifact over the network. A CORS
// refusal surfaces here as a failed request, which is exactly the #427 shape.

import { chromium } from 'playwright'

const DEFAULT_URL = 'https://ourhike.github.io/OurHike/app/'

// Long, because this is a real page loading a real 12 MB artifact over a
// public CDN, and a slow morning is not an outage. The check reports what it
// saw either way; the timeout only bounds how long it waits to see it.
const LOAD_TIMEOUT_MS = 120_000

// The strings the app uses to say it is broken. Read from the rendered page
// rather than imported, deliberately: this runs against a DEPLOYED build,
// which may be older than this checkout, and importing the current source's
// copy would assert against a string that build never shipped.
const NO_TRAIL_FLAG = 'No trail line'

const argv = process.argv.slice(2)
const flag = (name, fallback) => {
  const at = argv.indexOf(name)
  return at === -1 ? fallback : argv[at + 1]
}

const url = flag('--url', process.env.APP_URL || DEFAULT_URL)
// Where the app is built to fetch its data from. Passed in rather than
// guessed so the check can report "requested nothing from the bucket" as a
// failure instead of silently having nothing to match against.
const dataBase = (flag('--data-base', process.env.DATA_BASE_URL || '') || '').replace(
  /\/+$/,
  '',
)
const jsonOut = flag('--json', null)
const exitZero = argv.includes('--exit-zero')

const report = []
const add = (check, state, detail) => report.push({ check, state, detail })

const browser = await chromium.launch({
  args: ['--no-sandbox'],
  // Playwright pins a Chromium build per release and refuses to launch a
  // different one. CI installs the matching build, which is the normal path;
  // this override exists for an environment that already has a Chromium and
  // cannot download (a sandbox with one preinstalled, a distro package).
  // Absent means "use the one Playwright manages", which is the default.
  ...(process.env.CHROMIUM_EXECUTABLE_PATH
    ? { executablePath: process.env.CHROMIUM_EXECUTABLE_PATH }
    : {}),
})
// A fresh context per run: no service worker, no IndexedDB, no stored
// preferences. The question is what a hiker opening this for the first time
// gets, and a warm cache would answer a different one - and would hide
// exactly the failure where the bucket is unreachable but a cached copy makes
// the screen look fine.
const context = await browser.newContext()
const page = await context.newPage()

// Everything the page asked the data bucket for, and how it went. A CORS
// refusal is a `requestfailed`, not a response - which is what makes this the
// assertion that would have caught #427 from the app's side.
const dataResponses = []
const failures = []
const consoleErrors = []

page.on('response', (response) => {
  if (dataBase && response.url().startsWith(dataBase)) {
    dataResponses.push({ url: response.url(), status: response.status() })
  }
})
page.on('requestfailed', (request) => {
  failures.push({
    url: request.url(),
    reason: request.failure()?.errorText ?? 'unknown',
  })
})
page.on('pageerror', (error) => consoleErrors.push(String(error)))

try {
  const response = await page.goto(url, {
    waitUntil: 'domcontentloaded',
    timeout: LOAD_TIMEOUT_MS,
  })
  const status = response?.status() ?? 0
  add('loads', status === 200 ? 'ok' : 'failed', `${url} answered ${status}`)

  // Onboarding stands between a first-time visitor and the map, so the check
  // has to pass through it the way a hiker does.
  //
  // Several steps, and the control differs per step - "Skip" and "Continue"
  // on the first, "Not now" on the location one. So this clicks whichever of
  // them is on screen, in preference order, rather than naming one: the first
  // version of this waited for "Not now", never found it on step one, and
  // reported the whole flow skipped while quietly never reaching the map.
  //
  // "Skip"/"Not now" ahead of "Continue" because a headless browser has no
  // location to grant and the map is what is being checked, not the
  // permission prompt.
  const ONBOARDING_CONTROLS = ['Skip', 'Not now', 'Continue']
  // Wait for ANY of them to exist before asking which, because
  // `locator.isVisible()` is an immediate check rather than an auto-waiting
  // one - its `timeout` bounds resolving the locator, it does not wait for
  // the element to appear. Measured: written that way this failed 1 run in 4,
  // reporting "no onboarding control appeared" on a page that was simply
  // still rendering. A health check that cries wolf one morning in four is
  // the thing #431 spends its length warning against.
  const anyControl = page.getByRole('button', { name: /^(Skip|Not now|Continue)$/ })

  let steps = 0
  for (let attempt = 0; attempt < 6; attempt += 1) {
    await anyControl
      .first()
      .waitFor({ state: 'visible', timeout: attempt === 0 ? 30_000 : 3_000 })
      .catch(() => {})

    let clicked = false
    for (const name of ONBOARDING_CONTROLS) {
      const control = page.getByRole('button', { name, exact: true })
      if (await control.isVisible().catch(() => false)) {
        await control.click()
        steps += 1
        clicked = true
        break
      }
    }
    if (!clicked) break
  }
  add(
    'onboarding',
    steps > 0 ? 'ok' : 'failed',
    steps > 0
      ? `cleared in ${steps} step(s)`
      : `no onboarding control appeared (looked for ${ONBOARDING_CONTROLS.join(', ')}) - ` +
          'the check never reached the map, so everything below it is about the wrong screen',
  )

  // The app fetches trail lines on its own once it believes it is online, so
  // this waits for the network to settle rather than driving a download.
  await page.waitForLoadState('networkidle', { timeout: LOAD_TIMEOUT_MS }).catch(() => {})

  const body =
    (await page
      .locator('body')
      .innerText()
      .catch(() => '')) || ''

  // --- The two negative assertions #431 asks for ---

  add(
    'no-trail-line-flag',
    body.includes(NO_TRAIL_FLAG) ? 'failed' : 'ok',
    body.includes(NO_TRAIL_FLAG)
      ? `the status strip says "${NO_TRAIL_FLAG}" - the app has data but no trail`
      : 'the status strip does not claim the trail is missing',
  )

  const alerts = await page
    .locator('[role="alert"]')
    .allInnerTexts()
    .catch(() => [])
  const notices = alerts.map((text) => text.trim()).filter((text) => text !== '')
  add(
    'no-data-error',
    notices.length === 0 ? 'ok' : 'failed',
    notices.length === 0
      ? 'no data-error notice showing'
      : `showing: ${notices.join(' | ')}`,
  )

  // --- The positive assertion, without which the two above mean nothing ---

  if (!dataBase) {
    add(
      'fetched-data',
      'skipped',
      'no --data-base given, so nothing could be matched against the bucket',
    )
  } else {
    const ok = dataResponses.filter((r) => r.status === 200 || r.status === 206)
    const bad = dataResponses.filter((r) => r.status >= 400)
    if (ok.length === 0) {
      add(
        'fetched-data',
        'failed',
        `the app requested nothing readable from ${dataBase}. This is the case the two ` +
          'assertions above cannot see: with no request there is no error, and with no error ' +
          'there is no flag.',
      )
    } else {
      add('fetched-data', 'ok', `${ok.length} successful response(s) from the bucket`)
    }
    if (bad.length > 0) {
      add('bucket-errors', 'failed', bad.map((r) => `${r.status} ${r.url}`).join(', '))
    }
  }

  const dataFailures = dataBase
    ? failures.filter((f) => f.url.startsWith(dataBase))
    : failures
  add(
    'no-blocked-requests',
    dataFailures.length === 0 ? 'ok' : 'failed',
    dataFailures.length === 0
      ? 'nothing the page asked for was refused'
      : dataFailures.map((f) => `${f.reason} ${f.url}`).join(', '),
  )

  // Reported, never failed. A third-party tile host having a moment is not an
  // outage of ours, and #431 is explicit that it must not be able to declare
  // one.
  if (consoleErrors.length > 0) {
    add('page-errors', 'noted', consoleErrors.slice(0, 3).join(' | '))
  }
} catch (error) {
  add('loads', 'failed', `${error.name}: ${error.message}`)
} finally {
  await browser.close()
}

for (const line of report) {
  console.log(
    `  ${line.state.toUpperCase().padEnd(8)} ${line.check.padEnd(20)} ${line.detail}`,
  )
}

const failed = report.filter((line) => line.state === 'failed')
const verdict = {
  checked_at: new Date().toISOString().slice(0, 10),
  url,
  data_base: dataBase || null,
  checks: report,
  failed,
}

if (jsonOut) {
  const { writeFileSync } = await import('node:fs')
  writeFileSync(jsonOut, `${JSON.stringify(verdict, null, 2)}\n`)
}

console.log(
  failed.length === 0
    ? '\nThe deployed app loads its map data and does not report itself broken.'
    : `\n${failed.length} check(s) failed.`,
)

process.exit(exitZero || failed.length === 0 ? 0 : 1)
