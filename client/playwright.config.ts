// Playwright's own test runner (`@playwright/test`), new alongside the raw
// `playwright` package client/scripts/photograph-preview.mjs already uses to
// run the screenshot recipes (features/FLOW_TESTING.md). That script produces
// a picture for a person to look at; this config runs assertions that fail a
// build.

import { defineConfig } from '@playwright/test'
import { existsSync } from 'node:fs'
import { join } from 'node:path'

/**
 * Lifted from client/scripts/screenshot.mjs's launchChromium(): the agent
 * sandbox holds a Chromium under PLAYWRIGHT_BROWSERS_PATH that this
 * package's own resolution does not find (measured 2026-08-25 there, for the
 * same installed version this config now also drives). Overridden only when
 * that candidate actually exists, so a contributor's laptop - which sets
 * neither variable - keeps Playwright's own resolution untouched.
 */
function chromiumExecutable(): string | undefined {
  const candidate =
    process.env.CHROMIUM_PATH ??
    join(process.env.PLAYWRIGHT_BROWSERS_PATH ?? '', 'chromium')
  return existsSync(candidate) ? candidate : undefined
}

/**
 * The phone WIREFRAMES.md sizes against - the same object
 * client/scripts/screenshot.mjs's PHONE is, so a spec and a screenshot
 * recipe describe the same device.
 */
const PHONE = {
  width: 390,
  height: 844,
  isMobile: true,
  hasTouch: true,
  deviceScaleFactor: 2,
}

/**
 * The laptop, and the same object client/scripts/screenshot.mjs's DESKTOP is -
 * so a `@desktop` spec and a `--desktop` shot describe the same window.
 *
 * 1280 rather than 901: `lib/useDesktop.ts`'s DESKTOP_MIN_WIDTH is 900 and the
 * layout is `min-width: 900px`, so anything above it gets the desktop fork -
 * but a viewport sitting one pixel over the line would turn a change to that
 * constant into a mystifying failure rather than an obvious one, and 1280x800
 * is the window the recipes already photograph.
 *
 * `isMobile: false` and `hasTouch: false` are not decoration. Playwright's
 * `isMobile` sets a mobile user agent and a visual viewport, and the desktop
 * layout is a pointer layout - chrome/useRouteHover.ts listens for
 * `pointermove` and a touch context never sends one.
 */
const DESKTOP = {
  width: 1280,
  height: 800,
  isMobile: false,
  hasTouch: false,
  deviceScaleFactor: 1,
}

/**
 * Dev server locally - fast, and what every other client script targets by
 * default; the built app in CI - matching client/scripts/screenshot.mjs's own
 * --dist reasoning ("what CI shoots: same bytes it deploys"). The two ports
 * are vite's own defaults, which are also the two origins the R2 bucket's
 * CORS allowlist carries (screenshot.mjs's SHOT_HOST comment) - not that this
 * suite reaches the bucket at all (see FLOW_TESTING.md's boundaries), but a
 * third port would be one more thing to explain if that ever changed.
 */
const PORT = process.env.CI ? 4173 : 5173
const COMMAND = process.env.CI
  ? 'npm run build && npm run preview -- --port 4173 --strictPort'
  : 'npm run dev -- --port 5173 --strictPort'

/**
 * THE DATA-BACKED HALF (`FLOW_DATA=1`), and what it costs.
 *
 * Everything in `e2e/` runs against a phone holding no published data, which
 * is a real state and the one this suite could always reach. `e2e/data/` is
 * the other half: the same app reading the release it actually ships against,
 * so the builder has a junction graph, the map has waypoints, and the screens
 * behind those become drivable at all.
 *
 * THE COST WAS STATED BEFORE IT WAS CHOSEN (the maintainer's call,
 * 2026-09-11): a test that reads a bucket can go red because the bucket did,
 * not because the build broke, and a suite nobody trusts has already failed.
 * Three things hold that down, and they are why this is a separate mode
 * rather than more tests in `e2e/`:
 *
 * 1. IT READS THE PINNED RELEASE, never `latest`. `lib/dataRelease.ts`'s
 *    DATA_RELEASE is a committed constant and a release folder is immutable
 *    once written, so the bytes under a run cannot change without a commit
 *    somebody reviewed. This is the whole of why the flakiness is bounded.
 * 2. IT IS ITS OWN CI JOB. A bucket outage reds `flow-data` and leaves the
 *    hermetic tests in `flow` green, so the two failures never look alike.
 *    That half was 97 tests when this was written and is 155 across the two
 *    projects as of 2026-09-11; the count is scale, not the argument, and is
 *    re-measured by running `npx playwright test` rather than by reading it
 *    here.
 * 3. IT PREFLIGHTS. `e2e/support/dataPreflight.ts` fetches the manifest
 *    before any test runs and fails with "the bucket did not answer" rather
 *    than letting thirty assertions fail one at a time.
 *
 * WHY IT REUSES THE SAME PORT rather than running beside the hermetic half:
 * the bucket's CORS allowlist carries vite's two defaults and nothing else
 * (scripts/screenshot.mjs's SHOT_HOST comment). A third port is a third
 * origin, and the bucket answers a third origin with silence. So the two
 * halves are two runs, never concurrent.
 */
const DATA_MODE = process.env.FLOW_DATA === '1'

/**
 * A server the caller already started, which the browser is pointed at
 * instead of one this config builds.
 *
 * THE SANDBOX NEEDS THIS AND A LAPTOP DOES NOT. Headless Chromium here
 * cannot reach data.ourhike.org at all - measured 2026-09-11:
 * ERR_CONNECTION_RESET on every artifact, while `curl` to the same URL
 * returns 200, because the egress proxy is a shell-level thing the browser
 * does not use. `scripts/data-proxy.mjs` serves the built app and forwards
 * `/data/*` to the bucket through curl, so the app reads real data
 * same-origin and CORS never enters into it. Point this at that proxy and
 * this config starts no server of its own.
 */
const BYO_ORIGIN = process.env.FLOW_DATA_ORIGIN ?? ''

export default defineConfig({
  // The hermetic half by default; `e2e/data/` only in FLOW_DATA mode, and
  // never both, for the CORS reason above.
  testDir: DATA_MODE ? './e2e/data' : './e2e',
  testIgnore: DATA_MODE ? [] : ['data/**'],
  // Runs before any test in FLOW_DATA mode and says whether the bucket
  // answered, so an outage reads as an outage.
  globalSetup: DATA_MODE ? './e2e/support/dataPreflight.ts' : undefined,
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  // One retry in CI only, and only because a real browser adds real animation
  // frames and network waterfalls on top of what vitest's mocks already made
  // ordering-sensitive (FLOW_TESTING.md) - a spec that needs more than one to
  // pass is not settling on something observable and should be fixed, not
  // retried into passing.
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  timeout: DATA_MODE ? 90_000 : 30_000,
  // Every assertion in the data suite may be waiting on a fetch rather than on
  // a render, and the artifacts are large: measured 2026-09-11 through the
  // sandbox's proxy, the map had its waypoints about nine seconds after boot.
  // The hermetic half keeps the short window on purpose - there, five seconds
  // of waiting means something is wrong.
  expect: { timeout: DATA_MODE ? 30_000 : 5_000 },
  use: {
    baseURL: BYO_ORIGIN !== '' ? BYO_ORIGIN : `http://localhost:${PORT}`,
    trace: 'retain-on-failure',
    browserName: 'chromium',
    launchOptions: {
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
      executablePath: chromiumExecutable(),
    },
  },
  /**
   * TWO WIDTHS, AND A SPEC RUNS AT EXACTLY ONE OF THEM.
   *
   * `lib/useDesktop.ts`'s breakpoint is a real fork rather than a reflow - the
   * legend is a modal dialog on a phone and a persistent panel on a laptop, and
   * the bail guard's `mapShownUnder` makes tapping Today a guarded exit on one
   * and not an exit at all on the other. A suite that ran only one width would
   * call the other's behaviour a bug.
   *
   * SCOPED BY TAG, NOT BY RUNNING EVERYTHING TWICE, which is what
   * features/FLOW_TESTING.md asked for and the reason is worth keeping: most
   * specs here are meaningful at one width, and running them at both would
   * assert the wrong layout twice - a phone spec passing on a laptop proves
   * nothing about either. So `@desktop` is opt-in, everything else is the
   * phone, and no test runs in a layout it was not written for.
   *
   * `viewport` is its own nested option rather than a flat width/height, and
   * that is a scar: spreading PHONE directly once set two properties Playwright
   * does not read and left the default 1280x720 context in place, which made
   * the breakpoint match and ran every spec in the desktop layout regardless of
   * this file's own comments about it.
   */
  projects: [
    {
      name: 'phone',
      grepInvert: /@desktop/,
      use: {
        viewport: { width: PHONE.width, height: PHONE.height },
        isMobile: PHONE.isMobile,
        hasTouch: PHONE.hasTouch,
        deviceScaleFactor: PHONE.deviceScaleFactor,
      },
    },
    {
      name: 'desktop',
      grep: /@desktop/,
      use: {
        viewport: { width: DESKTOP.width, height: DESKTOP.height },
        isMobile: DESKTOP.isMobile,
        hasTouch: DESKTOP.hasTouch,
        deviceScaleFactor: DESKTOP.deviceScaleFactor,
      },
    },
  ],
  // None where the caller brought their own (the sandbox's proxy above);
  // otherwise the same build-and-serve as the hermetic half, carrying
  // VITE_DATA_BASE_URL through so the bundle knows which bucket to read.
  webServer:
    BYO_ORIGIN !== ''
      ? undefined
      : {
          command: COMMAND,
          url: `http://localhost:${PORT}/`,
          reuseExistingServer: !process.env.CI,
          // The data build fetches 1,943 artifacts' worth of manifest before
          // it draws anything, so it wants longer than a hermetic boot does.
          timeout: DATA_MODE ? 180_000 : 60_000,
        },
})
