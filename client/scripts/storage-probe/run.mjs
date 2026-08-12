// Runs the real archive download against a real browser, at a real size.
//
// WHY THIS EXISTS. The unit suite mocks `idb-keyval`, so between it and a full
// phone there is nothing - no real IndexedDB, no quota pressure - for the app's
// headline feature (TESTING.md, "Storage has one layer and it is simulated").
// #544 lived exactly in that gap: the Fine tier transferred all 1.18 GB and
// only then failed to store, because the Blob being accumulated is not charged
// against the origin's quota, so nothing refuses until the final `set()`. No
// jsdom test can see that. This can, in about a minute.
//
// It is deliberately MANUAL and not wired into CI - the same category as the
// full USGS fetch in TESTING.md. It moves gigabytes and its numbers depend on
// the machine's free disk, which is not a thing to assert against in a gate.
//
// USAGE
//
//   node scripts/storage-probe/run.mjs                     # the three tiers
//   node scripts/storage-probe/run.mjs --size 1184700000   # one size, in bytes
//   node scripts/storage-probe/run.mjs --unlimited         # quota out of the way
//   node scripts/storage-probe/run.mjs --store-only        # no network, store only
//   node scripts/storage-probe/run.mjs --watch             # is anything checkpointed?
//
// `--unlimited` passes Chromium's --unlimited-storage, which separates "this
// code cannot do it" from "this phone has no room": with it, 1.18 GB downloads,
// verifies against its published hash and stores fine.

import { createServer } from 'vite'
import { chromium } from 'playwright'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))

// The published tiers, so the default run is the decision a hiker faces
// (client/src/lib/downloadDetail.ts and hikingDetail.ts).
const TIERS = [
  { label: 'raster light', bytes: 65_000_000 },
  { label: 'raster standard', bytes: 315_100_000 },
  { label: 'raster fine', bytes: 1_184_700_000 },
]

const argv = process.argv.slice(2)
const has = (name) => argv.includes(name)
const flag = (name, fallback) => {
  const at = argv.indexOf(name)
  return at === -1 ? fallback : argv[at + 1]
}

const size = Number(flag('--size', 0))
const sizes = size > 0 ? [{ label: `${size} bytes`, bytes: size }] : TIERS

const server = await createServer({
  configFile: join(HERE, 'vite.config.mts'),
  root: HERE,
  // The download resolves its URLs through lib/config.ts, which reads this.
  define: { 'import.meta.env.VITE_DATA_BASE_URL': JSON.stringify('/data') },
})
await server.listen()
const url = server.resolvedUrls.local[0]

const browser = await chromium.launch({
  args: [
    '--no-sandbox',
    '--disable-dev-shm-usage',
    ...(has('--unlimited') ? ['--unlimited-storage'] : []),
  ],
  // Playwright pins a Chromium build per release and refuses to launch a
  // different one; this override is for an environment that already has one and
  // cannot download. Same escape hatch as scripts/check-deployed-app.mjs.
  ...(process.env.CHROMIUM_EXECUTABLE_PATH
    ? { executablePath: process.env.CHROMIUM_EXECUTABLE_PATH }
    : {}),
})

/** One page per size, so a size is never measured against usage that the
 *  previous one's delete has not given back yet - IndexedDB does not return it
 *  promptly, and that alone can make a size look like a ceiling. */
async function inFreshPage(body) {
  const context = await browser.newContext()
  const page = await context.newPage()
  page.on('console', (message) => {
    const text = message.text()
    if (text.startsWith('{')) console.log(text)
  })
  page.on('pageerror', (error) => console.log(`[pageerror] ${error.message}`))
  page.on('crash', () => console.log('[crash] the renderer was killed'))
  await page.goto(url, { waitUntil: 'load' })
  await page.evaluate(() => window.estimate())
  try {
    await body(page, context)
  } catch (error) {
    console.log(`[driver] ${error.message.split('\n')[0]}`)
  }
  await context.close()
}

for (const { label, bytes } of sizes) {
  console.log(`--- ${label} (${bytes} bytes) ---`)
  await inFreshPage(async (page, context) => {
    if (has('--store-only')) {
      await page.evaluate((n) => window.storeProbe(n), bytes)
      return
    }

    const running = page.evaluate((n) => window.probe(n), bytes)

    if (has('--watch')) {
      // A second page on the same origin sees the same IndexedDB, so it can
      // report what is on disk WHILE the transfer runs. Everything null
      // half-way through is the finding: nothing is checkpointed, so a killed
      // tab loses the whole transfer rather than resuming it.
      const watcher = await context.newPage()
      watcher.on('console', (message) => {
        const text = message.text()
        if (text.startsWith('{')) console.log(`[mid-transfer] ${text}`)
      })
      await watcher.goto(url, { waitUntil: 'load' })
      for (let seen = 0; seen < 2; seen++) {
        await new Promise((resolve) => setTimeout(resolve, 4000))
        await watcher.evaluate(() => window.survey('ourhike:probe'))
      }
    }

    await running
  })
}

await browser.close()
await server.close()
