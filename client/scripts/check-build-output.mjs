// Checks that the built app can actually draw a map, by reading the build
// output rather than trusting that it is right.
//
// WHY A CHECK ON `dist/` AND NOT A UNIT TEST
//
// Every test in src/ mocks `maplibre-gl` outright, because jsdom has no WebGL
// context and a real map cannot be constructed there at all. That mock is what
// makes map code testable, and it is also a blind spot with a precise shape:
// nothing in the suite ever asks whether the REAL MapLibre, in the REAL bundle,
// can find the files it goes looking for at runtime. The style can be valid,
// every layer can be in it, every unit test can pass, and the shipped app can
// still draw nothing at all.
//
// That is not hypothetical. maplibre-gl 6 stopped inlining its web worker and
// now resolves one from its own module URL - which after bundling is the app
// chunk, so it fetched `assets/maplibre-gl-worker.mjs`, which no build ever
// emitted, and 404'd. MapLibre fires no error for that. The worker is where
// vector tiles are parsed, rasters decoded, GeoJSON cut into tiles and symbols
// laid out, so the map drew nothing but its background colour: a blank sheet of
// paper, on every platform, online and off. See src/map/mapWorker.ts.
//
// The general shape of that bug is "the app asks for a file the build did not
// publish", so that is what is checked here, for every asset rather than only
// the one that bit. Runs as part of `npm run build`, so a bundle that cannot
// draw a map cannot be deployed - the build IS the artifact that ships, and it
// is the only honest place to look.
//
// There is a second shape, added after it happened too: "the app never asked
// for a file it needs." MapLibre's stylesheet was never imported, so nothing
// positioned the map's controls and every one of them rendered off the bottom
// of the screen. No reference is missing there - the reference was never
// written - which the check above cannot see by construction, so the built CSS
// is read for the rules themselves.

import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

// Overridable so the checker's own tests (src/test/checkBuildOutput.test.ts,
// #319) can run the real script against tiny synthetic dist/ trees and prove
// it fails red on each defect class. `npm run build` never sets it.
const DIST =
  process.env.CHECK_BUILD_OUTPUT_DIST ??
  join(dirname(fileURLToPath(import.meta.url)), '..', 'dist')

/**
 * Where the app's own emitted files live inside the output, and the prefix
 * every reference to one carries.
 *
 * Vite writes them under `assets/` whatever `base` is set to, and `base` is a
 * deploy-time variable (GitHub Pages serves this under /OurHike/app/), so
 * references are matched on the `assets/<file>` tail rather than on a full
 * path that changes per deploy.
 */
const ASSET_DIR = 'assets'

/**
 * The asset whose absence is silent.
 *
 * Listed by name rather than left to the generic check below, because the
 * generic check can only compare what IS referenced against what exists - and
 * the failure mode here was the reference disappearing entirely, leaving
 * MapLibre to fall back on a guess that resolves to nothing. A bundle that has
 * stopped mentioning the worker looks perfectly consistent; it is just blank.
 */
const REQUIRED_ASSETS = [
  {
    pattern: /^maplibre-gl-worker.*\.js$/,
    expected: 'assets/maplibre-gl-worker-<hash>.js',
    what: "MapLibre's web worker",
    why:
      'Without it MapLibre parses no tiles at all and the map draws nothing but ' +
      'its background colour - silently, with no error event. ' +
      'See src/map/mapWorker.ts.',
  },
]

/**
 * Stylesheets the app has to have imported, identified by rules only they
 * carry.
 *
 * Checked on the emitted CSS rather than on the import statement, because what
 * matters is that the rules reached the bundle - an import that a tree-shake or
 * a config change quietly dropped would still be sitting in the source.
 */
const REQUIRED_STYLESHEETS = [
  {
    what: "MapLibre's own stylesheet (maplibre-gl/dist/maplibre-gl.css)",
    // Both come from that file and nowhere else. chrome.css styles
    // `.maplibregl-ctrl button`, so the marker selectors are picked to be ones
    // the app's own CSS cannot supply.
    selectors: ['.maplibregl-canvas', '.maplibregl-ctrl-bottom-right'],
    why:
      'It is the only thing that positions what the map puts on itself. Without ' +
      'it the canvas is not absolutely positioned, so compass, locate, the scale ' +
      'bar and the zoom buttons follow it in normal flow and land past the bottom ' +
      'edge of the map - in the DOM, below the fold, on a map that otherwise draws ' +
      'perfectly. See src/map/MapView.tsx.',
  },
]

function walk(dir) {
  const out = []
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) out.push(...walk(full))
    else out.push(full)
  }
  return out
}

function fail(lines) {
  console.error(`\nBuild output check FAILED\n`)
  for (const line of lines) console.error(`  ${line}`)
  console.error('')
  process.exit(1)
}

let files
try {
  files = walk(DIST)
} catch {
  fail([
    `No build output at ${DIST}.`,
    'This check reads what `vite build` produced, so run it after a build.',
  ])
}

const present = new Set(
  files.map((f) => relative(DIST, f).split(/[\\/]/).join('/')).filter(Boolean),
)
const emittedAssets = [...present]
  .filter((p) => p.startsWith(`${ASSET_DIR}/`))
  .map((p) => p.slice(ASSET_DIR.length + 1))

// Only the text the browser actually executes. Sourcemaps and the precache
// manifest are read separately or not at all; scanning them here would report
// references that no runtime ever follows. The service worker and the workbox
// runtime are excluded by name for the same reason in the other direction
// (found by this file's own tests, #319): the precache manifest inside sw.js
// names every precached asset, so scanning it made anything precached count
// as "wired up" - and a worker that is emitted and precached but never
// referenced is exactly the silent blank-map case check 2 exists to catch.
const executable = files.filter(
  (f) =>
    /\.(js|mjs|css|html|webmanifest)$/.test(f) &&
    !/(^|[\\/])(sw|workbox-[^\\/]*)\.js$/.test(f),
)

const problems = []

// 1. Everything the app references, it publishes.
const referenced = new Map()
for (const file of executable) {
  const text = readFileSync(file, 'utf8')
  for (const [, name] of text.matchAll(/assets\/([A-Za-z0-9][A-Za-z0-9._-]*)/g)) {
    if (!referenced.has(name)) referenced.set(name, new Set())
    referenced.get(name).add(relative(DIST, file))
  }
}

for (const [name, from] of [...referenced].sort()) {
  if (present.has(`${ASSET_DIR}/${name}`)) continue
  problems.push(
    `Referenced but never emitted: ${ASSET_DIR}/${name}`,
    `  referenced from: ${[...from].join(', ')}`,
    `  The app will request this at runtime and get a 404.`,
  )
}

// 2. The assets whose absence would be silent are there, and wired up.
for (const { pattern, expected, what, why } of REQUIRED_ASSETS) {
  const emitted = emittedAssets.filter((name) => pattern.test(name))
  const wired = emitted.filter((name) => referenced.has(name))

  if (emitted.length === 0) {
    problems.push(`Missing from the build: ${what} (expected ${expected})`, `  ${why}`)
  } else if (wired.length === 0) {
    problems.push(
      `Emitted but never referenced: ${what} (${emitted.join(', ')})`,
      `  Nothing in the bundle points at it, so at runtime MapLibre falls back`,
      `  to guessing a path next to the app chunk, where nothing is published.`,
      `  ${why}`,
    )
  }
}

// 3. Whatever the app needs to draw a map, it needs on a ridge too.
//
// An offline-first map that fetches part of itself on demand works in town and
// fails where it matters, which is the one failure this app cannot ship. The
// service worker's precache list is generated by vite-plugin-pwa from the build
// output, so this asks whether the real manifest really names them.
const serviceWorker = files.find((f) => /(^|[\\/])sw\.js$/.test(f))
if (serviceWorker === undefined) {
  problems.push(
    'No service worker in the build output.',
    '  Without one nothing is precached and the app cannot open offline at all.',
  )
} else {
  const precache = readFileSync(serviceWorker, 'utf8')
  for (const { pattern, what } of REQUIRED_ASSETS) {
    const emitted = emittedAssets.filter((name) => pattern.test(name))
    if (emitted.length > 0 && !emitted.some((name) => precache.includes(name))) {
      problems.push(
        `Not precached: ${what} (${emitted.join(', ')})`,
        `  The map would work with signal and go blank without it, which is the`,
        `  one place this app is meant to work.`,
      )
    }
  }

  // The bundled glyph ranges (issue #188): all 256, present AND precached.
  //
  // Glyphs fail in the worst pattern this check exists for - per-range, at
  // runtime, only when a label needs a codepoint from a range that never made
  // it. A build missing half the ranges labels an English test session
  // perfectly and drops labels in the field, so the count is checked exactly
  // rather than "at least one". Checked against sw.js and not just dist/
  // because copying the files is Vite's default behaviour while precaching
  // them depends on a glob in vite.config.ts that nothing else exercises.
  const GLYPH_RANGES = 256
  const glyphsInDist = [...present].filter(
    (p) => p.startsWith('glyphs/') && p.endsWith('.pbf'),
  )
  const glyphsPrecached = glyphsInDist.filter(
    (p) => precache.includes(p) || precache.includes(encodeURI(p)),
  )
  if (glyphsInDist.length !== GLYPH_RANGES) {
    problems.push(
      `Expected ${GLYPH_RANGES} glyph range files under glyphs/, found ${glyphsInDist.length}.`,
      '  Labels for any codepoint in a missing range silently render nothing.',
      '  See src/map/liveTopo.ts (BUNDLED_GLYPHS) and client/public/glyphs/.',
    )
  } else if (glyphsPrecached.length !== GLYPH_RANGES) {
    problems.push(
      `Only ${glyphsPrecached.length} of ${GLYPH_RANGES} glyph ranges are in the service worker's precache.`,
      '  A fresh install would label its map in town and lose the labels in',
      '  airplane mode. Check workbox.globPatterns in vite.config.ts.',
    )
  }
}

// 4. Nothing in the built CSS reaches another origin.
//
// This is the check that would have caught #717, and it is deliberately about
// the SHAPE rather than about Google: any cross-origin `@import` or `url()`
// that survives into the emitted stylesheet is a third party the first paint
// waits on.
//
// A CSS `@import` of a cross-origin stylesheet is render-blocking, so the
// browser paints nothing until it resolves. Measured 2026-08-15 on the build
// before this check existed: app shell fully downloaded at 527 ms, first paint
// at 12,956 ms, main thread idle throughout. `display=swap` does not help - it
// governs how a font renders once its stylesheet has arrived, not whether the
// stylesheet gates paint. Neither does the service worker, because the request
// is not to this origin and so is not in the precache.
//
// Full airplane mode is not the bad case (the request fails at once). Some
// signal and poor is, which is the connection this app is built for.
const CROSS_ORIGIN_CSS = /(?:@import\s+|url\(\s*)["']?(https?:)?\/\/[^"')\s]+/g

const stylesheets = files.filter((f) => f.endsWith('.css'))

for (const file of stylesheets) {
  const text = readFileSync(file, 'utf8')
  for (const [match] of text.matchAll(CROSS_ORIGIN_CSS)) {
    problems.push(
      `Cross-origin reference in the built CSS: ${relative(DIST, file)}`,
      `  ${match.slice(0, 120)}`,
      `  An @import blocks the first paint on somebody else's server, and a`,
      `  url() cannot be precached, so it is missing exactly where this app is`,
      `  meant to work. Vendor the file into src/design-system/assets/ instead.`,
    )
  }
}

// 5. The UI typography shipped and is precached.
//
// Same failure shape as the glyphs above and the same remedy, one layer up:
// the glyphs label the map, these label everything else. Counted rather than
// "at least one", because a subset that is emitted but not precached is
// invisible until somebody opens the app without signal.
const fontsInDist = [...present].filter((p) => p.endsWith('.woff2'))
const UI_FONT_FILES = 10
if (fontsInDist.length !== UI_FONT_FILES) {
  problems.push(
    `Expected ${UI_FONT_FILES} self-hosted .woff2 files in the build, found ${fontsInDist.length}.`,
    '  See src/design-system/tokens/typography.css - the three families are',
    '  vendored precisely so no paint waits on another origin.',
  )
} else if (serviceWorker !== undefined) {
  const precache = readFileSync(serviceWorker, 'utf8')
  const notPrecached = fontsInDist.filter(
    (p) => !precache.includes(p) && !precache.includes(p.split('/').pop()),
  )
  if (notPrecached.length > 0) {
    problems.push(
      `${notPrecached.length} of ${UI_FONT_FILES} UI font files are not in the service worker's precache.`,
      `  ${notPrecached.join(', ')}`,
      '  The app would render in its own typeface in town and fall back to the',
      '  system stack in the field. Check workbox.globPatterns in vite.config.ts.',
    )
  }
}

// 6. The stylesheets that make the map usable actually shipped.
//
// Separate from the asset checks above because there is no reference to look
// for: Vite bundles imported CSS into the app's own stylesheet, so a forgotten
// import leaves a build that is internally consistent and visibly broken.
const styles = stylesheets.map((f) => readFileSync(f, 'utf8')).join('\n')

for (const { what, selectors, why } of REQUIRED_STYLESHEETS) {
  const missing = selectors.filter((selector) => !styles.includes(selector))
  if (missing.length === 0) continue

  problems.push(
    `Missing from the built CSS: ${what}`,
    `  no rule for ${missing.join(', ')} in ${stylesheets.length} emitted stylesheet(s)`,
    `  ${why}`,
  )
}

if (problems.length > 0) fail(problems)

console.log(
  `Build output OK: ${referenced.size} referenced assets all published, ` +
    `${REQUIRED_ASSETS.length} required asset(s) wired up and precached, ` +
    `${fontsInDist.length} UI font file(s) vendored and precached, ` +
    `no cross-origin CSS, ` +
    `${REQUIRED_STYLESHEETS.length} required stylesheet(s) in the built CSS.`,
)
