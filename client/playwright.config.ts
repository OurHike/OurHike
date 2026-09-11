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
 * recipe describe the same device. No desktop project yet: every spec this
 * suite has today drives the phone-primary spine; add one the way this one
 * is built once a spec needs the desktop-only layout (App.desktopSpine.test.tsx
 * already covers that layout at the rendered layer).
 */
const PHONE = {
  width: 390,
  height: 844,
  isMobile: true,
  hasTouch: true,
  deviceScaleFactor: 2,
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

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  // One retry in CI only, and only because a real browser adds real animation
  // frames and network waterfalls on top of what vitest's mocks already made
  // ordering-sensitive (FLOW_TESTING.md) - a spec that needs more than one to
  // pass is not settling on something observable and should be fixed, not
  // retried into passing.
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  timeout: 30_000,
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'retain-on-failure',
    browserName: 'chromium',
    // `viewport` is its own nested option, not a flat width/height on `use` -
    // spreading PHONE directly here once set two properties Playwright does
    // not read and left the default 1280x720 context in place, which made
    // lib/useDesktop.ts's breakpoint match and every spec run in the desktop
    // layout regardless of this file's own comments about it.
    viewport: { width: PHONE.width, height: PHONE.height },
    isMobile: PHONE.isMobile,
    hasTouch: PHONE.hasTouch,
    deviceScaleFactor: PHONE.deviceScaleFactor,
    launchOptions: {
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
      executablePath: chromiumExecutable(),
    },
  },
  webServer: {
    command: COMMAND,
    url: `http://localhost:${PORT}/`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
})
