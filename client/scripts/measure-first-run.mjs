// The stopwatch for a launch: what the main thread is doing while the three
// entry steps are up and how long each tap on Skip takes to answer - or, with
// --returning, what it is doing after a hiker who finished first run days ago
// opens the app again, and how long each tab tap waits.
//
//   node scripts/measure-first-run.mjs https://pr-862.ourhike-preview.pages.dev/
//   node scripts/measure-first-run.mjs https://ourhike.org/app/ --warm
//   node scripts/measure-first-run.mjs https://ourhike.org/app/ --returning
//
// WHY THIS IS A SCRIPT AND NOT A TEST
//
// It is the half of "is the app fast" that a suite cannot honestly answer.
// Every test in src/ mocks `maplibre-gl`, jsdom has no compositor, no WebGL,
// no tile worker and no paint - and a CI runner's milliseconds are not a
// phone's, so a timing assertion tuned on one machine is the flaky test
// CLAUDE.md warns about. src/App.loadBudget.test.tsx holds the half that CAN
// be asserted: which expensive operations a launch is allowed to perform at
// all. This holds the half that has to be looked at by somebody, on demand,
// against a real deployment.
//
// It is deliberately NOT wired into `npm test` or into CI. Run it when
// touching the launch path, and paste what it prints into the pull request -
// that is what #857 did, and what turned "it feels like the button is broken"
// into 2,374 ms in one task with a name on it.
//
// WHAT IT MEASURES
//
//  - `event` timing entries for each tap: the input delay (the thread was
//    busy), the processing, and the presentation delay. This is the number
//    that IS the complaint - a tap that takes half a second to show anything
//    reads as a broken button.
//  - the long-task timeline: how many, the longest, and total blocking time
//    (the part of each task past 50 ms).
//  - a sampled CPU profile, attributed by function and mapped back through the
//    build's source maps where the deployment publishes them.
//
// A 4x CPU throttle is the default because that is roughly the phone this app
// is for, against the machine most people write it on. The numbers are only
// comparable against other runs on the SAME machine with the SAME flags - it
// is a before-and-after instrument, not an absolute one.

import { chromium } from 'playwright'
import { existsSync, readFileSync } from 'node:fs'

const argv = process.argv.slice(2)
const url = argv.find((arg) => !arg.startsWith('--'))
const flag = (name, fallback) => {
  const found = argv.find((arg) => arg.startsWith(`--${name}=`))
  return found === undefined ? fallback : found.slice(name.length + 3)
}

if (url === undefined) {
  console.error(
    'usage: node scripts/measure-first-run.mjs <url> [--warm | --returning] [--cpu=4] ' +
      '[--pause=800] [--settle=20000] [--maps=<dir of .js.map files>] [--stub-tiles]',
  )
  process.exit(2)
}

/** Replay first run on a phone that has already downloaded a release, rather
 *  than measuring a cold one. The expensive case, and the one anyone clearing
 *  preferences to look at onboarding again is in. */
const warm = argv.includes('--warm')
/**
 * The launch the bug report behind #1192 describes: onboarding done, the
 * release on the phone, opening the app again. Takes a release onto the phone
 * the way --warm does, leaves onboarding completed rather than clearing it,
 * and then measures a reload - the long tasks, and how long a tap on each tab
 * waits to be taken. Measured 2026-09-02 before the fix: one task of 13,078 ms
 * and a Today tap that waited 14,557 ms.
 */
const returning = argv.includes('--returning')
/** How long after the release lands before the measured reload, so the first
 *  launch's own index build and cache write are not what gets measured. */
const settleMs = Number(flag('settle', '20000'))
/** Answer the live sheet's tile requests locally. For a sandbox that cannot
 *  reach tiles.openfreemap.org - the map then draws no basemap, which makes
 *  the numbers a floor rather than a measurement. */
const stubTiles = argv.includes('--stub-tiles')
const cpuThrottle = Number(flag('cpu', '4'))
const pauseMs = Number(flag('pause', '800'))
/** Where to find `<chunk>.js.map`, so the profile names functions instead of
 *  minified letters. `dist/assets` after a local build. */
const mapsDir = flag('maps', null)

const sourceMaps = new Map()
async function originalName(scriptUrl, line, column) {
  if (mapsDir === null || !scriptUrl || line < 0 || column < 0) return null
  const file = scriptUrl.split('/').pop()
  if (!sourceMaps.has(file)) {
    const path = `${mapsDir}/${file}.map`
    if (!existsSync(path)) {
      sourceMaps.set(file, null)
    } else {
      const { TraceMap } = await import('@jridgewell/trace-mapping')
      sourceMaps.set(file, new TraceMap(JSON.parse(readFileSync(path, 'utf8'))))
    }
  }
  const map = sourceMaps.get(file)
  if (map === null || map === undefined) return null
  const { originalPositionFor } = await import('@jridgewell/trace-mapping')
  const found = originalPositionFor(map, { line: line + 1, column })
  if (found.source === null) return null
  return `${found.source.split('/').slice(-2).join('/')}:${found.line}`
}

/**
 * A Chromium, from wherever this machine keeps one.
 *
 * Playwright's own resolution first, which is right on a laptop that ran
 * `npx playwright install`. The fallbacks are for a container that ships a
 * browser Playwright did not install and does not expect - the agent sandbox
 * holds `chromium-1194` under PLAYWRIGHT_BROWSERS_PATH while this package
 * wants a later revision, and refusing to run there would make this script
 * unusable in the one place that has no display and needs it most.
 */
async function launchChromium() {
  const args = ['--no-sandbox', '--disable-dev-shm-usage']
  const candidates = [
    process.env.CHROMIUM_PATH,
    `${process.env.PLAYWRIGHT_BROWSERS_PATH ?? ''}/chromium`,
  ].filter((path) => path !== undefined && path !== '/chromium' && existsSync(path))

  try {
    return await chromium.launch({ args })
  } catch (error) {
    for (const executablePath of candidates) {
      return await chromium.launch({ args, executablePath })
    }
    throw error
  }
}

const browser = await launchChromium()

// A phone, and specifically the one WIREFRAMES.md sizes the entry card
// against: the card is capped at 78% of the viewport, so its height decides
// how much map is visible behind the steps.
const context = await browser.newContext({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 3,
  isMobile: true,
  hasTouch: true,
})

if (stubTiles) {
  await context.route('https://tiles.openfreemap.org/**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        tilejson: '2.2.0',
        tiles: ['http://127.0.0.1:9/{z}/{x}/{y}.pbf'],
        minzoom: 0,
        maxzoom: 14,
        vector_layers: [],
      }),
    }),
  )
  await context.route('https://s3.amazonaws.com/**', (route) => route.abort())
  await context.route('http://127.0.0.1:9/**', (route) => route.abort())
}

// Installed before any app code runs, because `buffered: true` only reaches
// back to entries the browser kept - and the first long task of a launch is
// the one worth having.
await context.addInitScript(() => {
  window.__ourhikePerf = { longtasks: [], taps: [] }
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      window.__ourhikePerf.longtasks.push({
        start: entry.startTime,
        duration: entry.duration,
      })
    }
  }).observe({ type: 'longtask', buffered: true })
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      if (entry.name !== 'pointerdown') continue
      window.__ourhikePerf.taps.push({
        start: entry.startTime,
        inputDelay: entry.processingStart - entry.startTime,
        processing: entry.processingEnd - entry.processingStart,
        presentation: entry.startTime + entry.duration - entry.processingEnd,
        total: entry.duration,
      })
    }
  }).observe({ type: 'event', buffered: true, durationThreshold: 0 })
})

const page = await context.newPage()
page.on('pageerror', (error) => console.error(`  page error: ${error.message}`))

const cdp = await context.newCDPSession(page)
await cdp.send('Emulation.setCPUThrottlingRate', { rate: cpuThrottle })
await cdp.send('Network.enable')
await cdp.send('Network.emulateNetworkConditions', {
  offline: false,
  latency: 80,
  downloadThroughput: (12 * 1024 * 1024) / 8,
  uploadThroughput: (2 * 1024 * 1024) / 8,
})

const ENTRY_TITLE = '.onboarding__title'

/** The step's way past itself. Two of the three steps say Skip; the map-size
 *  step says "Decide this later" (#1054), and clicking Skip three times used
 *  to stall on it. */
const SKIP = /^(Skip|Decide this later)$/

async function clickThrough() {
  await page.waitForSelector(ENTRY_TITLE, { timeout: 180_000 })
  for (let step = 0; step < 3; step += 1) {
    await page.getByRole('button', { name: SKIP }).first().click({ timeout: 180_000 })
  }
}

/** The release is on the phone: the waypoints are stored and the partial
 *  marker is down (lib/trailData.ts). Read out of IndexedDB rather than off
 *  the screen, because the screen a launch lands on is Today now (#1054) and
 *  says nothing about waypoint counts. */
async function releaseLanded() {
  await page.waitForFunction(
    () =>
      new Promise((resolve) => {
        const open = indexedDB.open('keyval-store')
        open.onsuccess = () => {
          const db = open.result
          const store = db.transaction('keyval').objectStore('keyval')
          const pois = store.get('ourhike:pois')
          const partial = store.get('ourhike:trail-data-partial')
          let left = 2
          let ready = true
          const done = () => {
            left -= 1
            if (left === 0) {
              db.close()
              resolve(ready)
            }
          }
          pois.onsuccess = () => {
            if (pois.result === undefined) ready = false
            done()
          }
          partial.onsuccess = () => {
            if (partial.result === true) ready = false
            done()
          }
          pois.onerror = partial.onerror = () => {
            ready = false
            done()
          }
        }
        open.onerror = () => resolve(false)
      }),
    null,
    { timeout: 600_000, polling: 1000 },
  )
}

if (warm || returning) {
  console.log('warming: taking one whole release onto the phone...')
  await page.goto(url, { waitUntil: 'commit' })
  await clickThrough()
  await releaseLanded()
  // The first launch's own index build and cache write, and whatever the
  // background artifacts are still doing, are not the thing being measured.
  await page.waitForTimeout(settleMs)
}

if (warm) {
  // First run again, with everything already downloaded.
  await page.evaluate(
    () =>
      new Promise((resolve, reject) => {
        const open = indexedDB.open('keyval-store')
        open.onsuccess = () => {
          const db = open.result
          const tx = db.transaction('keyval', 'readwrite')
          tx.objectStore('keyval').delete('ourhike:preferences')
          tx.oncomplete = () => {
            db.close()
            resolve()
          }
          tx.onerror = () => reject(tx.error)
        }
        open.onerror = () => reject(open.error)
      }),
  )
  console.log('warm: the release is on the phone, first run replayed\n')
}

await cdp.send('Profiler.enable')
await cdp.send('Profiler.setSamplingInterval', { interval: 200 })
await cdp.send('Profiler.start')

// Out of the old document first, not a reload. A same-origin reload shares
// the renderer's main thread with whatever the old page is still doing, and
// that work is reported inside the NEW page's timeline as a task starting at
// 0 ms - measured 2026-09-02, a 5-20 s "first task" that was the previous
// launch's unfinished index build, not the launch being timed.
if (warm || returning) {
  await page.goto('about:blank')
  await page.waitForTimeout(3_000)
}
const started = Date.now()
await page.goto(url, { waitUntil: 'commit' })

/**
 * The returning hiker's taps: each tab, on a schedule that reaches into the
 * seconds the index used to hold the thread, and then a burst once the
 * launch has settled for comparison. Each is measured two ways: how long
 * Playwright's click waited to be accepted (the thread was busy), and how
 * long until the tab reported itself selected.
 */
const TAB_TAPS = [
  [800, 'Plan'],
  [2000, 'More'],
  [3500, 'Today'],
  [5000, 'Plan'],
  [7000, 'More'],
  [9000, 'Today'],
  [11000, 'Plan'],
  [14000, 'Today'],
]

const tabTaps = []
if (returning) {
  for (const [at, label] of TAB_TAPS) {
    const wait = at - (Date.now() - started)
    if (wait > 0) await page.waitForTimeout(wait)
    const asked = Date.now()
    let accepted = null
    let selected = null
    try {
      await page.getByRole('tab', { name: label, exact: true }).click({ timeout: 60_000 })
      accepted = Date.now() - asked
      await page.waitForFunction(
        (name) =>
          document
            .querySelector('[role=tab][aria-selected=true]')
            ?.textContent?.trim() === name,
        label,
        { timeout: 60_000, polling: 16 },
      )
      selected = Date.now() - asked
    } catch (error) {
      console.error(`  tap ${label} at ${at} ms: ${error.message.split('\n')[0]}`)
    }
    tabTaps.push({ at: asked - started, label, accepted, selected })
  }
  await page.waitForTimeout(Math.max(0, 16_000 - (Date.now() - started)))
} else {
  await page.waitForSelector(ENTRY_TITLE, { timeout: 180_000 })
  console.log(`first entry step reachable      ${Date.now() - started} ms`)
}

const stepChanges = []
for (let step = 0; step < (returning ? 0 : 3); step += 1) {
  await page.waitForTimeout(pauseMs)
  const before = await page.evaluate(
    (selector) => document.querySelector(selector)?.textContent ?? null,
    ENTRY_TITLE,
  )
  const asked = Date.now()
  await page.getByRole('button', { name: SKIP }).first().click({ timeout: 180_000 })
  const clicked = Date.now()
  await page.waitForFunction(
    ([selector, previous]) => {
      const now = document.querySelector(selector)?.textContent ?? null
      return previous === null ? now === null : now !== previous
    },
    [ENTRY_TITLE, step === 2 ? null : before],
    { timeout: 180_000 },
  )
  stepChanges.push({
    accepted: clicked - asked,
    changed: Date.now() - clicked,
  })
}

// Long enough for whatever the last tap started to finish, so the timeline
// covers the hand-over into the map screen as well as the steps themselves.
if (!returning) await page.waitForTimeout(8_000)

const paint = await page.evaluate(() =>
  performance.getEntriesByType('paint').map((entry) => ({
    name: entry.name,
    at: Math.round(entry.startTime),
  })),
)
for (const entry of paint) console.log(`${entry.name.padEnd(31)} ${entry.at} ms`)

const perf = await page.evaluate(() => window.__ourhikePerf)

if (returning) {
  console.log('\ntaps on the tab bar (ms after navigation)')
  for (const tap of tabTaps) {
    console.log(
      `  ${String(tap.at).padStart(6)}  ${tap.label.padEnd(6)} accepted after ` +
        `${tap.accepted ?? 'timeout'} ms, selected after ${tap.selected ?? 'timeout'} ms`,
    )
  }
}

if (!returning) console.log('\ntaps on Skip')
stepChanges.forEach((change, index) => {
  const tap = perf.taps[index]
  const timing =
    tap === undefined
      ? ''
      : `  (input delay ${Math.round(tap.inputDelay)}, processing ${Math.round(
          tap.processing,
        )}, presentation ${Math.round(tap.presentation)})`
  console.log(
    `  ${index + 1}. accepted after ${change.accepted} ms, ` +
      `next step after ${change.changed} ms${timing}`,
  )
})

const long = perf.longtasks.filter((task) => task.duration >= 50)
const blocking = long.reduce((sum, task) => sum + (task.duration - 50), 0)
console.log(`\nlong tasks                      ${long.length}`)
console.log(
  `longest single task             ${Math.round(
    Math.max(0, ...long.map((task) => task.duration)),
  )} ms`,
)
console.log(`total blocking time             ${Math.round(blocking)} ms`)
for (const task of [...long].sort((a, b) => b.duration - a.duration).slice(0, 8)) {
  console.log(`  ${Math.round(task.duration)} ms at ${Math.round(task.start)} ms`)
}

const { profile } = await cdp.send('Profiler.stop')
const nodes = new Map(profile.nodes.map((node) => [node.id, node]))
const samples = new Map()
for (const id of profile.samples) samples.set(id, (samples.get(id) ?? 0) + 1)
const msPerSample =
  (profile.endTime - profile.startTime) / Math.max(1, profile.samples.length) / 1000

const byFunction = new Map()
for (const [id, count] of samples) {
  const node = nodes.get(id)
  if (node === undefined) continue
  const frame = node.callFrame
  if (frame.functionName === '(idle)' || frame.functionName === '(program)') continue
  const mapped = await originalName(frame.url, frame.lineNumber, frame.columnNumber)
  const key =
    mapped ??
    `${frame.functionName || '(anonymous)'}  ${(frame.url ?? '').split('/').pop() ?? ''}:${
      frame.lineNumber + 1
    }`
  byFunction.set(key, (byFunction.get(key) ?? 0) + count * msPerSample)
}

console.log('\nmain-thread self time by function (sampled)')
if (mapsDir === null) {
  console.log('  (minified - pass --maps=dist/assets after a local build for names)')
}
for (const [key, ms] of [...byFunction].sort((a, b) => b[1] - a[1]).slice(0, 15)) {
  console.log(`  ${String(Math.round(ms)).padStart(6)} ms  ${key}`)
}

console.log(
  `\nmeasured against ${url} at 390x844, ${cpuThrottle}x CPU throttle, ` +
    `12 Mbps/80 ms, ${
      returning
        ? 'returning (release on the phone, onboarding done)'
        : warm
          ? 'warm (release on the phone)'
          : 'cold (nothing on the phone)'
    }` +
    `${stubTiles ? ', tiles stubbed' : ''}`,
)

await browser.close()
