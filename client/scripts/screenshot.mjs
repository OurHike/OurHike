// Photographs the running app, so a pull request can show what it changed.
//
//   node scripts/screenshot.mjs entry-card
//   node scripts/screenshot.mjs map-legend --wait=6000
//   node scripts/screenshot.mjs preview --url=https://pr-862.ourhike-preview.pages.dev/
//   node scripts/screenshot.mjs homepage --desktop --url=http://127.0.0.1:4321/
//
// WHY THIS EXISTS
//
// .claude/skills/pr-screenshot/SKILL.md asks every pull request to show what
// it changed. A rule with no tool is a rule that gets skipped, and the three
// things that make a screenshot here fiddly are all environment trivia nobody
// should rediscover per pull request: the agent sandbox holds a Chromium that
// Playwright did not install and will not find on its own, first run covers
// the whole app until a preference says otherwise, and a phone screenshot has
// to be captured at 2x but DISPLAYED at 1x or GitHub renders it enormous.
//
// It is deliberately NOT wired into `npm test` or into CI - same argument as
// measure-first-run.mjs. Nothing here asserts anything; it produces an
// artefact for a person to look at, on demand.
//
// WHAT IT DOES NOT DO
//
// It cannot photograph map DATA. The corridor archive lives in IndexedDB and
// nothing downloads it here, so the map canvas renders its paper background
// and no trail - measured 2026-08-25, where the console says
// `ArchiveNotDownloadedError: No offline map archive found in IndexedDB`.
// Everything drawn in DOM - chrome, cards, sheets, pickers, the legend, first
// run - photographs correctly. For a shot that needs real tiles under it,
// point --url at a deployed preview, which is built against the real data
// source (see .github/workflows/pr-preview.yml).
//
// --url AT A REMOTE HOST DOES NOT WORK FROM AN AGENT SANDBOX. Chromium there
// reaches nothing external: measured 2026-08-25 against a live pr-*.pages.dev
// preview and against example.com, both net::ERR_CONNECTION_RESET, with and
// without Playwright's `proxy` option pointed at HTTPS_PROXY - while `curl`
// on the same URL answers 200, so the host is permitted and the browser is
// the part that cannot use the egress proxy. It works from a laptop. Do not
// route around it; say in the pull request that the shot could not be taken.

import { chromium } from 'playwright'
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, statSync } from 'node:fs'
import { resolve, dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const CLIENT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..')

/**
 * Inside the built output, which is gitignored - and that is the whole point.
 *
 * A screenshot is never committed here (#988). `pr-preview.yml` writes one
 * into the directory it is about to upload to Cloudflare Pages, so the image
 * is served by the same deployment as the app it shows and disappears with it
 * when the pull request closes. Nothing about it reaches a commit, which is
 * what the previous mechanism cost: 79,290 bytes of permanent, unretractable
 * PNG per pull request in a public tree.
 *
 * `__screenshot/` rather than a bare name because it is served at the root of
 * the preview alongside the app's own routes, and a double underscore says
 * "not part of the app" to anybody reading a URL.
 */
export const DEFAULT_OUT_DIR = resolve(CLIENT_DIR, 'dist', '__screenshot')

/**
 * The phone WIREFRAMES.md sizes against, and the one measure-first-run.mjs
 * already uses - so the two instruments describe the same device.
 */
export const PHONE = { width: 390, height: 844, isMobile: true, hasTouch: true }

/** The marketing site (`site/`) is looked at on a laptop, not a phone. */
export const DESKTOP = { width: 1280, height: 800, isMobile: false, hasTouch: false }

/**
 * Capture at 2, display at 1.
 *
 * Derived rather than picked. GitHub renders a pull request body image at its
 * natural pixel width, capped by a container about 830 px wide, so a 390-wide
 * capture displays at 390 px and is soft on any retina screen, while a
 * 780-wide one displays at 780 px - a phone screenshot rendered twice
 * life-size. Capturing at 2 and emitting `<img width="390">` is the only
 * combination that is both sharp and the size of a phone. 3 buys nothing: the
 * browser has no more than 2x to show past a 780 px cap, and it measured
 * 119,643 bytes against 79,290 for the same frame (2026-08-25, entry card).
 */
export const CAPTURE_SCALE = 2

/** Settle after load — and after a recipe's drive, which reuses it (see
 *  capture()). Named so photograph-preview.mjs and parseArgs() cannot hold
 *  two different opinions of it. */
export const DEFAULT_WAIT_MS = 3500

/**
 * What one screenshot may weigh before it needs a second thought.
 *
 * Measured 2026-08-25, both at 390x844 scale 2 as PNG:
 *
 *   entry card, no map (agent sandbox, no network)        79,290
 *   entry card over a real basemap (CI, pr-989)          310,289
 *   trail screen, full basemap (CI, pr-989)              743,012
 *
 * The spread is the finding, and it is why the first number was the wrong
 * one to budget against. A sandbox cannot reach the tile source, so every
 * measurement taken there is of an app with an empty map canvas - roughly a
 * tenth of what the same frame weighs once terrain, water and labels render.
 * The budget was 150 KB on that basis and would have warned on every honest
 * screenshot CI takes.
 *
 * 1.2 MB is the largest real frame with room above it. It is not enforced and
 * costs nothing when exceeded - the bytes are served from a preview rather
 * than committed (#988) - so this is a smell test only: past here usually
 * means a capture that ran away, a `--full` page that kept scrolling, or a
 * map that rendered noise rather than a map.
 *
 * ONE HONEST EXCEEDANCE, so the next person past this line does not go
 * looking for a bug that is not there: a desktop first-run frame clears it.
 * Measured 1,698,683 bytes at 1280x800 scale 1 (2026-08-27, #1084). The
 * subject is a photograph filling the whole window, and photographic noise
 * is what PNG compresses worst - the same recipe on a phone, where the photo
 * is a band over flat paper, comes back at 911,160. Nothing ran away; the
 * frame is simply mostly photograph. The three causes above are still what
 * this number is for.
 */
export const BYTE_BUDGET = 1_200_000

/** idb-keyval's default store, which is where client/src/lib/preferences.ts
 *  keeps `ourhike:preferences`. Named here rather than imported because this
 *  script runs as plain node against an already-built page, with no bundler
 *  to resolve TypeScript for it. */
const IDB = { database: 'keyval-store', store: 'keyval', key: 'ourhike:preferences' }

export function usage() {
  return [
    'usage: node scripts/screenshot.mjs <name> [options]',
    '',
    '  --out=DIR        where the PNG goes (default client/dist/__screenshot/)',
    '  --dist           photograph the BUILT app (vite preview over dist/) rather',
    '                   than the dev server. What CI shoots: same bytes it deploys.',
    '  --url=URL        an app already running - a deployed preview, or your own',
    '                   dev server. Omitted: this script serves the app itself.',
    '  --entry          keep first run on screen (default: skip past it)',
    '  --wait=MS        settle time after load (default 3500)',
    '  --scale=N        device pixel ratio (default 2 - read CAPTURE_SCALE first)',
    '  --desktop        1280x800 and not a phone, for site/',
    '  --full           the whole scrollable page, not just the viewport',
  ].join('\n')
}

/**
 * `--flag` and `--flag=value` out of argv, plus the one positional name.
 *
 * Separated from everything that touches a browser so it can be tested
 * without one - see src/test/screenshotScript.test.ts.
 */
export function parseArgs(argv) {
  const flag = (name) => argv.includes(`--${name}`)
  const value = (name, fallback) => {
    const found = argv.find((arg) => arg.startsWith(`--${name}=`))
    return found === undefined ? fallback : found.slice(name.length + 3)
  }
  const name = argv.find((arg) => !arg.startsWith('--'))
  const viewport = flag('desktop') ? DESKTOP : PHONE
  return {
    name,
    outDir: value('out', DEFAULT_OUT_DIR),
    url: value('url', undefined),
    dist: flag('dist'),
    skipEntry: !flag('entry'),
    waitMs: Number(value('wait', DEFAULT_WAIT_MS)),
    scale: Number(value('scale', CAPTURE_SCALE)),
    fullPage: flag('full'),
    viewport,
  }
}

/**
 * A file name a reader can place without opening it.
 *
 * Lower case, dashes, no spaces: this string ends up inside a raw
 * githubusercontent URL, where a space becomes `%20` and the markdown around
 * it stops being copy-pasteable.
 */
export function slug(name) {
  return String(name)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

/** Whether a capture is small enough to ship in a preview without a
 *  second thought. */
export function budgetVerdict(bytes, budget = BYTE_BUDGET) {
  return {
    bytes,
    overBudget: bytes > budget,
    message:
      bytes > budget
        ? `${bytes} bytes is past the ${budget}-byte smell test - larger than a full-map frame. Look at it before trusting it.`
        : `${bytes} bytes.`,
  }
}

/**
 * A Chromium, from wherever this machine keeps one.
 *
 * Lifted from measure-first-run.mjs, whose comment explains the fallback: the
 * agent sandbox holds chromium-1194 under PLAYWRIGHT_BROWSERS_PATH while this
 * package wants a later revision, and Playwright's own resolution looks for a
 * headless shell that is not there. Confirmed 2026-08-25 - the default launch
 * fails with "Executable doesn't exist at .../chromium_headless_shell-1234"
 * and the fallback to /opt/pw-browsers/chromium works, WebGL included.
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

/** A port the OS says is free, rather than a guess.
 *
 *  Guessing is what this replaced, and the failure it produced was slow and
 *  confusing: `--strictPort` turns a collision with an already-running dev
 *  server into a vite that exits immediately, and the caller then waits the
 *  full 30s poll before reporting a timeout that says nothing about the real
 *  cause. Asking for port 0 and reading back what was bound leaves only the
 *  gap between closing this listener and vite opening its own. */
async function freePort() {
  const { createServer } = await import('node:net')
  return await new Promise((done, fail) => {
    const probe = createServer()
    probe.on('error', fail)
    probe.listen(0, '127.0.0.1', () => {
      const { port } = probe.address()
      probe.close(() => done(port))
    })
  })
}

/**
 * Vite, on a port nobody else is on, torn down when this exits.
 *
 * `dist` picks `vite preview`, which serves the BUILT output rather than the
 * dev server's on-the-fly modules. That is what CI shoots, and the reason is
 * that the screenshot then shows the exact bytes being deployed - a dev-server
 * frame can differ from a production one in ways a reviewer would be the first
 * to find out about (minification, the service worker, the PWA manifest).
 */
async function startServer({ dist }) {
  const port = await freePort()
  const bin = join(CLIENT_DIR, 'node_modules', '.bin', 'vite')
  const args = dist ? ['preview'] : []
  const child = spawn(
    bin,
    [...args, '--port', String(port), '--strictPort', '--host', '127.0.0.1'],
    {
      cwd: CLIENT_DIR,
      stdio: 'ignore',
    },
  )
  const url = `http://127.0.0.1:${port}/`
  let exited = null
  child.on('exit', (code) => {
    exited = code
  })

  for (let attempt = 0; attempt < 60; attempt += 1) {
    if (exited !== null)
      throw new Error(`vite exited with ${exited} before serving ${url}`)
    try {
      const response = await fetch(url)
      if (response.ok) return { url, stop: () => child.kill() }
    } catch {
      // Not listening yet.
    }
    await new Promise((done) => setTimeout(done, 500))
  }
  child.kill()
  throw new Error(`vite did not answer on ${url} within 30s`)
}

/**
 * Write `onboarding_completed` before the app's first read of it.
 *
 * First run covers the entire app - App.tsx gates on
 * `!preferences.onboarding_completed` - so without this every screenshot is
 * of the same three entry cards. As an init script rather than a click
 * through the three steps because the click path also asks for location
 * permission and records a hiking detail level, neither of which belongs in
 * an unrelated screenshot.
 */
async function skipFirstRun(context) {
  await context.addInitScript(
    ({ database, store, key }) =>
      new Promise((done, fail) => {
        const open = indexedDB.open(database)
        open.onupgradeneeded = () => open.result.createObjectStore(store)
        open.onerror = () => fail(open.error)
        open.onsuccess = () => {
          const write = open.result
            .transaction(store, 'readwrite')
            .objectStore(store)
            // Partial, deliberately: normalisePreferences() merges whatever is
            // stored over DEFAULT_PREFERENCES, so naming one key here cannot
            // drift out of date with the other forty.
            .put({ onboarding_completed: true }, key)
          write.onsuccess = () => done()
          write.onerror = () => fail(write.error)
        }
      }),
    IDB,
  )
}

export async function capture(options) {
  const { name, outDir, url, dist, skipEntry, waitMs, scale, fullPage, viewport, drive } =
    options
  mkdirSync(outDir, { recursive: true })
  const path = join(outDir, `${slug(name)}.png`)

  const server = url === undefined ? await startServer({ dist }) : null
  const target = url ?? server.url
  const browser = await launchChromium()
  try {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      deviceScaleFactor: scale,
      isMobile: viewport.isMobile,
      hasTouch: viewport.hasTouch,
    })
    if (skipEntry) await skipFirstRun(context)

    const page = await context.newPage()
    await page.goto(target, { waitUntil: 'load', timeout: 60_000 })
    await page.waitForTimeout(waitMs)
    // A shot recipe's taps (client/preview-shots/, driven by
    // photograph-preview.mjs). Not a CLI flag: a drive is a function, and the
    // command line cannot carry one — recipes are how one arrives here.
    if (drive !== undefined) {
      await drive(page)
      // The same settle again, deliberately the same constant: what a tap
      // opens animates in exactly like what a load does, and two numbers
      // here would be two opinions about how long this app takes to stop
      // moving.
      await page.waitForTimeout(waitMs)
    }
    await page.screenshot({ path, fullPage })
    return { path, bytes: statSync(path).size, displayWidth: Math.round(viewport.width) }
  } finally {
    await browser.close()
    server?.stop()
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const options = parseArgs(process.argv.slice(2))
  if (options.name === undefined) {
    console.error(usage())
    process.exit(2)
  }

  const { path, bytes, displayWidth } = await capture(options)
  const verdict = budgetVerdict(bytes)
  console.log(`Wrote ${path} (${displayWidth} px wide as displayed) - ${verdict.message}`)
}
