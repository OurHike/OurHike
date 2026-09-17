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
      '[--pause=800] [--settle=20000] [--maps=<dir of .js.map files>] [--stub-tiles] ' +
      '[--json=<path>]',
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
/**
 * Also write what was measured as JSON, for a reader that is not a person
 * (#1299): scripts/check-launch-speed.mjs turns it into a verdict against
 * features/LAUNCH_BUDGET.md §3, and .github/workflows/check-launch-speed.yml
 * runs the pair against production every morning.
 *
 * The JSON is a second RENDERING of this run, never a second measurement -
 * everything in it is a value already printed above it, so a number in a
 * tracking issue and a number a person read off this output cannot disagree.
 */
const jsonPath = flag('json', null)

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

/**
 * The card's own way past itself, named by what it IS rather than by what it
 * says.
 *
 * Every card carries exactly one decline control: `src/screens/Onboarding.tsx`
 * gives `what-ourhike-is`, `hiker-mode`, `default-place` and `map-size` an
 * `onboarding__skip`, and `location-permission` an `onboarding__secondary`
 * (both of ITS buttons call `finish()`, so it has no `next`). Measured against
 * the live bundle 2026-09-15 - `curl
 * https://ourhike.org/app/assets/main-Bx2gadkk.js` carries 5
 * `onboarding__title`, 4 `onboarding__skip` and 1 `onboarding__secondary`,
 * matching the checkout exactly.
 *
 * WHY NOT THE BUTTON'S NAME, WHICH IS WHAT THIS USED TO READ (#1376). It was
 * `/^(Skip|Decide this later)$/`, clicked exactly three times, and PR #1374 -
 * One pathway from first run to a walk finished: the front-end rebuild from
 * the ClaudeDesign flow review (merged 2026-09-14 17:55) broke both halves at
 * once. `Skip` became `Skip - take me to the map`, which is what crashed the
 * launch check the next morning - run 34975488353 spent three of its four
 * minutes inside one 180-second timeout and never started the stopwatch.
 *
 * AND THE COUNT WAS NEVER A CONSTANT. It is not five now and it was not three
 * before: the first card's decline says "straight to the map, with every
 * default" and finishes the flow outright, so DECLINING walks one card, while
 * the other four are only reached by accepting `Get set up`. Measured here
 * against a build of main on 2026-09-15: one card ("A map that works where
 * there is no signal."), then no heading at all. So the old loop, even with
 * the name fixed, would click once and then wait out two more 180-second
 * timeouts for a button that is not on screen. Ending on "is the flow still
 * showing" is the only form that survives the next rewording of it.
 *
 * Copy is the thing that moved twice in one week; the role each button plays
 * in the flow has not. `check-deployed-app.mjs` keeps a name-based matcher for
 * a reason that does not apply here - it asserts against a DEPLOYED build that
 * may be older than this checkout, where a class is no safer than a name. This
 * one drives a build to a stopwatch reading, and the bundle measurement above
 * is what says today's deployment carries these classes rather than an
 * assumption that it does.
 */
const PAST_THE_CARD = '.onboarding__skip, .onboarding__secondary'

/** A runaway guard on the loop below, not a count of the cards - the count is
 *  what got this wrong twice. One card is walked today and five is the most
 *  the flow could ask for; reaching ten means something is looping. It raises
 *  rather than returning, because a run that quietly gave up here goes on to
 *  time the onboarding screen and call it a launch. */
const MAX_CARDS = 10

/** The card on screen, by its heading, or null once onboarding is done. */
const currentCard = () =>
  page.evaluate(
    (selector) => document.querySelector(selector)?.textContent ?? null,
    ENTRY_TITLE,
  )

async function clickThrough() {
  await page.waitForSelector(ENTRY_TITLE, { timeout: 180_000 })
  for (let card = 0; card < MAX_CARDS; card += 1) {
    const before = await currentCard()
    if (before === null) return
    await page.locator(PAST_THE_CARD).first().click({ timeout: 180_000 })
    // Wait for the card to actually change before looking for the next one.
    // Without this the loop can click the same still-mounted button twice and
    // land two cards short with no error - the silent half of #1376.
    await page.waitForFunction(
      ([selector, previous]) =>
        (document.querySelector(selector)?.textContent ?? null) !== previous,
      [ENTRY_TITLE, before],
      { timeout: 180_000 },
    )
  }
  await refuseToMeasureOnboarding()
}

/**
 * Raise if onboarding is STILL up after `MAX_CARDS`, and say nothing if it is
 * not.
 *
 * The null check is the whole point and is not defensive: a flow of exactly
 * `MAX_CARDS` cards is walked to its end by the loops above and then falls out
 * of them, so a bare throw here would fail a run that had in fact finished -
 * and print `still showing "null"` while doing it, which is a message asserting
 * the opposite of what happened.
 */
async function refuseToMeasureOnboarding() {
  const stuck = await currentCard()
  if (stuck === null) return
  throw new Error(
    `onboarding still showing "${stuck}" after ${MAX_CARDS} cards - ` +
      'the flow grew, or a card has no .onboarding__skip / .onboarding__secondary. ' +
      'Measuring past this point would time the wrong screen (#1376).',
  )
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
          // And the launch mirror of it (lib/launchMirror.ts, #1301): left in
          // place, the replayed first run would open on Today for a tick and
          // then fall back to the steps when the deleted record came back
          // empty, which is not the launch being measured.
          localStorage.removeItem('ourhike:launch')
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

// The first-run walk, timed card by card. `clickThrough` above is the same
// walk untimed, for the warming pass whose numbers nobody reads.
//
// Bounded by the cards on screen rather than by a count (#1376): the loop
// stops when a card's own click takes the heading away, which is the flow
// telling it there is nothing left. The previous version ran exactly three
// times and special-cased the third as the end - a shape that only ever fit
// one version of the flow, and does not fit the one card declining walks now.
const stepChanges = []
for (let step = 0; !returning && step < MAX_CARDS; step += 1) {
  await page.waitForTimeout(pauseMs)
  const before = await currentCard()
  if (before === null) break
  const asked = Date.now()
  await page.locator(PAST_THE_CARD).first().click({ timeout: 180_000 })
  const clicked = Date.now()
  await page.waitForFunction(
    ([selector, previous]) =>
      (document.querySelector(selector)?.textContent ?? null) !== previous,
    [ENTRY_TITLE, before],
    { timeout: 180_000 },
  )
  stepChanges.push({
    accepted: clicked - asked,
    changed: Date.now() - clicked,
  })
}
// Same refusal as the warming walk, and for the same reason: everything below
// this line times what is on screen, so a walk that ran out of attempts with a
// card still up must not reach it.
if (!returning) await refuseToMeasureOnboarding()

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

// The app's own marks (#1299, src/lib/launchMarks.ts), read from the page so
// this prints the SAME seven moments Settings -> About this build shows on a
// phone and the bug-report prefill carries. That is the whole point of the
// marks: a number from a hiker's device and a number from this profile name
// the same events, so the two can finally be compared.
//
// A moment the launch never reached prints as such rather than being left
// out, for the reason the screen says it: an omitted row reads as instant.
const marks = await page.evaluate(() =>
  [
    ['ourhike:script', 'app code started'],
    ['ourhike:shell', 'tab bar rendered'],
    ['ourhike:preferences', 'settings read'],
    ['ourhike:today', 'waypoints ready'],
    ['ourhike:index', 'trail index ready'],
    // The map's own two (#1560): a phone landing on Today never reaches
    // them, and prints "not reached" for both - which is the right answer.
    ['ourhike:map', 'map built'],
    ['ourhike:map-drawn', 'map drawn'],
  ].map(([name, label]) => {
    const entry = performance.getEntriesByName(name, 'mark')[0]
    return { label, at: entry === undefined ? null : Math.round(entry.startTime) }
  }),
)
for (const mark of marks) {
  console.log(
    `${mark.label.padEnd(31)} ${mark.at === null ? 'not reached' : `${mark.at} ms`}`,
  )
}

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

if (!returning) console.log('\ntaps past each card')
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

if (jsonPath !== null) {
  const { writeFileSync } = await import('node:fs')
  writeFileSync(
    jsonPath,
    `${JSON.stringify(
      {
        url,
        mode: returning ? 'returning' : warm ? 'warm' : 'cold',
        cpu_throttle: cpuThrottle,
        viewport: '390x844',
        tiles_stubbed: stubTiles,
        paint: Object.fromEntries(paint.map((entry) => [entry.name, entry.at])),
        marks: Object.fromEntries(marks.map((mark) => [mark.label, mark.at])),
        taps: returning
          ? tabTaps.map((tap) => ({
              at: tap.at,
              label: tap.label,
              accepted_ms: tap.accepted,
              selected_ms: tap.selected,
            }))
          : stepChanges.map((change, index) => ({
              step: index + 1,
              accepted_ms: change.accepted,
              changed_ms: change.changed,
            })),
        long_tasks: long.length,
        longest_task_ms: Math.round(Math.max(0, ...long.map((task) => task.duration))),
        total_blocking_ms: Math.round(blocking),
      },
      null,
      2,
    )}\n`,
  )
  console.log(`\nwrote ${jsonPath}`)
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
