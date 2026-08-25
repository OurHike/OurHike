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

import { chromium } from 'playwright'
import { spawn } from 'node:child_process'
import { existsSync, mkdirSync, statSync } from 'node:fs'
import { resolve, dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const CLIENT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const REPO_ROOT = resolve(CLIENT_DIR, '..')

/** Where a committed screenshot lives, and the reason it is not under
 *  `client/`: every path in `client/` is in the client suite's scope
 *  (`scripts/suite_scopes.py client`), so a screenshot committed there would
 *  run the whole client suite to prove that a PNG still parses. `.github/` is
 *  in no suite's scope, which is the correct amount of CI for an image. */
export const DEFAULT_OUT_DIR = resolve(REPO_ROOT, '.github', 'pr-screenshots')

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

/**
 * What one screenshot may weigh before it needs a second thought.
 *
 * Measured 2026-08-25 on the first-run entry card, the densest DOM-only frame
 * the app has: 390x844 at scale 2 is 79,290 bytes as PNG. 150 KB is that with
 * room for a busier frame, and is NOT a technical limit - it is the point at
 * which "is this image worth carrying in a public repository forever" stops
 * being rhetorical. The whole repository packs to 14.3 MiB, so a screenshot
 * is roughly half a percent of it each.
 * @unvalidated Nobody has yet checked what a map-heavy frame with real tiles
 * under it weighs; the corridor archive does not download in this sandbox.
 * A shot taken against a deployed preview would settle it.
 */
export const BYTE_BUDGET = 150_000

/** idb-keyval's default store, which is where client/src/lib/preferences.ts
 *  keeps `ourhike:preferences`. Named here rather than imported because this
 *  script runs as plain node against an already-built page, with no bundler
 *  to resolve TypeScript for it. */
const IDB = { database: 'keyval-store', store: 'keyval', key: 'ourhike:preferences' }

export function usage() {
  return [
    'usage: node scripts/screenshot.mjs <name> [options]',
    '',
    '  --out=DIR        where the PNG goes (default .github/pr-screenshots/)',
    '  --url=URL        an app already running - a deployed preview, or your own',
    '                   dev server. Omitted: this script starts vite and stops it.',
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
    skipEntry: !flag('entry'),
    waitMs: Number(value('wait', 3500)),
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

/** The line to paste into the pull request body, with the width that makes a
 *  2x capture display at phone size. `<img>` rather than `![]()` for exactly
 *  that reason - markdown image syntax carries no width. */
export function markdownFor({ owner, repo, sha, path, width, alt }) {
  const url = `https://raw.githubusercontent.com/${owner}/${repo}/${sha}/${path}`
  return `<img src="${url}" width="${width}" alt="${alt}">`
}

/**
 * A screenshot's path as a raw URL would need it, or null if it is not in the
 * repository at all.
 *
 * The null case is the one worth handling rather than papering over: a
 * capture written to /tmp cannot be linked from a pull request body, because
 * the URL that renders one is a path INTO a commit. Printing a plausible
 * `raw.githubusercontent.com/.../tmp/...` line would be a broken image nobody
 * notices until the pull request is open.
 */
export function repoPath(absolutePath, root = REPO_ROOT) {
  const within = relative(root, absolutePath)
  return within.startsWith('..') || within === '' ? null : within
}

/** Whether a capture is small enough to commit without a conversation. */
export function budgetVerdict(bytes, budget = BYTE_BUDGET) {
  return {
    bytes,
    overBudget: bytes > budget,
    message:
      bytes > budget
        ? `${bytes} bytes is past the ${budget}-byte budget. Crop it, or say in the pull request why this frame needs the weight.`
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

/** Vite, on a port nobody else is on, torn down when this exits. */
async function startDevServer() {
  const port = await freePort()
  const bin = join(CLIENT_DIR, 'node_modules', '.bin', 'vite')
  const child = spawn(
    bin,
    ['--port', String(port), '--strictPort', '--host', '127.0.0.1'],
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
  const { name, outDir, url, skipEntry, waitMs, scale, fullPage, viewport } = options
  mkdirSync(outDir, { recursive: true })
  const path = join(outDir, `${slug(name)}.png`)

  const server = url === undefined ? await startDevServer() : null
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
  console.log(`Wrote ${path} - ${verdict.message}`)

  const tracked = repoPath(path)
  if (tracked === null) {
    console.log(
      '\nThat is outside the repository, so nothing can link to it. A pull request\n' +
        `body links INTO a commit - re-run with --out=${DEFAULT_OUT_DIR} to commit it.`,
    )
  } else {
    console.log(
      '\nCommit it, then put this in the pull request body with that commit sha:\n\n  ' +
        markdownFor({
          owner: 'OurHike',
          repo: 'OurHike',
          sha: '<sha>',
          path: tracked,
          width: displayWidth,
          alt: slug(options.name),
        }),
    )
  }
}
