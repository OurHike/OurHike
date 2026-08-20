import { execFileSync } from 'node:child_process'
import { existsSync, readFileSync, realpathSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// maplibre-contour@0.1.0 ships a malformed `exports` map: it lists `module`,
// `require`, `types` and `browser` conditions but no `import` and no
// `default`, so a plain ESM `import` of it fails outright under Node's
// resolution ("'.' is not exported under the conditions..."), which is what
// Vitest runs. The browser build happens to survive because Vite tries the
// `module` condition, but that is luck rather than a contract - and the
// `browser` entry it might otherwise pick is a UMD bundle, not ESM.
//
// So the package is pinned to its real ESM entry point here, once, rather than
// left to whichever condition each toolchain happens to try first. Resolved
// through the `require` condition (the one entry that IS reachable) and then
// walked to its sibling, so this keeps working wherever the package actually
// gets installed rather than assuming a node_modules layout. Delete this the
// day upstream publishes a valid exports map.
const CONTOUR_CJS = createRequire(import.meta.url).resolve('maplibre-contour')
const CONTOUR_ESM = join(dirname(CONTOUR_CJS), 'index.mjs')

// Where the app will be served from. GitHub Pages serves a project site under
// /<repo>/, not at the domain root, and a PWA is unusually sensitive to that:
// `scope` and `start_url` decide which pages the installed app owns, so a
// manifest claiming "/" on a subpath install either fails validation or
// installs an app that opens the wrong page. Settable so the same build works
// at a root domain later without editing this file.
//
// Must have a trailing slash - Vite joins it to asset paths directly.
const BASE = process.env.VITE_BASE_PATH ?? '/'

// The config's own directory, realpathed once and shared by `root` and the
// rollup inputs below - resolved differently they can disagree through a
// symlinked checkout, and an input outside `root` fails the build.
const ROOT = realpathSync.native(fileURLToPath(new URL('.', import.meta.url)))

// Which build this is, inlined so the app can say so (#378, RELEASING.md §4).
//
// DELIBERATELY NOT VITE_-PREFIXED ENVIRONMENT VARIABLES, which is how every
// other build-time value here arrives (lib/config.ts, lib/api.ts,
// lib/supabase.ts). Those name things a checkout cannot know - which bucket,
// which Supabase project - so they have to be configured per deployment, and
// each one is a line in a workflow that a fourth workflow can forget. These
// two are already sitting in the tree being built, so reading them here means
// production, UA, every pull request preview and a laptop all report their
// build correctly with no workflow change and nothing to keep in sync.
//
// package.json is the single source for the version, per RELEASING.md §4;
// pages.yml refuses to deploy a `v*` tag that disagrees with it, so the two
// cannot drift apart unnoticed.
const PACKAGE_VERSION: string =
  (JSON.parse(readFileSync(join(ROOT, 'package.json'), 'utf8')) as { version?: string })
    .version ?? ''

// HEAD first and GITHUB_SHA only as a fallback, because HEAD is literally the
// tree being built: on a `pull_request` event GITHUB_SHA names the ephemeral
// merge commit, and while actions/checkout has that checked out anyway, git is
// the answer that stays right if a workflow ever checks out something else.
//
// Empty when neither can answer - a tarball with no .git outside CI - and the
// app says "unknown" rather than inventing something. Never fatal: a build
// that fails because it could not work out its own version number would be
// this feature costing more than it is worth.
function buildCommit(): string {
  try {
    return execFileSync('git', ['rev-parse', 'HEAD'], {
      cwd: ROOT,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim()
  } catch {
    return process.env.GITHUB_SHA ?? ''
  }
}

// https://vite.dev/config/
export default defineConfig({
  base: BASE,
  // Substituted textually into the bundle. lib/buildInfo.ts is the only reader
  // and guards each one with `typeof`, so a toolchain that does not perform
  // the substitution gets "unknown" rather than a ReferenceError.
  //
  // The build time is here for a failure this app has already had: a service
  // worker can serve a bundle indefinitely after a newer one deployed (see the
  // registerType note below), and "built three weeks ago" on a site that
  // deployed yesterday is what makes that visible from the phone rather than
  // from the deploy log.
  define: {
    __APP_VERSION__: JSON.stringify(PACKAGE_VERSION),
    __BUILD_COMMIT__: JSON.stringify(buildCommit()),
    __BUILT_AT__: JSON.stringify(new Date().toISOString()),
  },
  // Explicit root resolved from this file's own URL, not process.cwd(): on
  // Windows, a shell invocation with a lowercase drive letter (e.g. `c:\...`)
  // makes Vitest's internal root-comparison silently mismatch against the
  // uppercase-cased path Vite resolves elsewhere, crashing with "Cannot read
  // properties of undefined (reading 'config')" before any test runs - see
  // https://github.com/vitest-dev/vitest/issues/5251. Resolving from
  // import.meta.url keeps the casing consistent regardless of how the
  // process was launched.
  root: ROOT,
  build: {
    rollupOptions: {
      // Two pages: the app, and the artifact viewer (viewer.html, issue
      // #202) - a reviewer tool that ships with every PR preview but is not
      // part of the app a hiker sees (no tab, no service worker
      // registration of its own; it rides the same origin).
      input: {
        main: join(ROOT, 'index.html'),
        viewer: join(ROOT, 'viewer.html'),
      },
    },
  },
  resolve: {
    // Falls back to whatever `require` resolved if upstream ever drops the
    // .mjs, so a future release can only cost the ESM build, never the app.
    alias: existsSync(CONTOUR_ESM) ? { 'maplibre-contour': CONTOUR_ESM } : {},
  },
  plugins: [
    react(),
    // Skipped under Vitest: vite-plugin-pwa's manifest/workbox hooks assume a
    // normal build/dev-server lifecycle and throw when Vitest's own Vite
    // instance loads this same config file just for the `test` block below.
    process.env.VITEST
      ? null
      : VitePWA({
          // generateSW only: this app's job is precaching the app shell
          // (HTML/JS/CSS/fonts/icons) so the UI itself loads offline. The
          // actual corridor map/POI download (tens of MB to ~1.2GB,
          // user-triggered, byte-range reads via pmtiles) is application
          // code, not a service-worker caching rule - see
          // src/map/pmtilesSource.ts - so there's no custom SW logic to
          // inject.
          // autoUpdate, reversing an earlier 'prompt' setting. The intent
          // behind prompt was sound - do not swap the app under a hiker
          // mid-junction - but nothing ever supplied the prompt, so a new
          // build installed, sat in `waiting`, and the old bundle kept being
          // served indefinitely. Every deploy looked like it had not
          // happened, and the only escape was clearing site data through
          // browser settings, which is not a thing to ask of someone who
          // wants a map.
          //
          // Safe to apply automatically because the service worker holds only
          // the app shell. The downloaded map, POIs, outbox and preferences
          // are all in IndexedDB, which a worker swap does not touch - so an
          // update can never cost someone the map they walked in with.
          registerType: 'autoUpdate',
          workbox: {
            // Drop precaches from superseded builds rather than letting a
            // phone accumulate every app shell it has ever seen.
            cleanupOutdatedCaches: true,
            // The first entry is workbox's own default, restated because
            // setting globPatterns at all replaces it. The second puts the
            // bundled glyph ranges (public/glyphs/, issue #188) into the
            // precache: symbol layers fetch them per 256-glyph range at
            // runtime, so leaving them out means labels render in town and
            // vanish in airplane mode - precisely the split this app cannot
            // ship. scripts/check-build-output.mjs verifies all 256 made it
            // into the generated manifest, so a glob drift here fails the
            // build rather than the hiker.
            //
            // The third is the UI typography, self-hosted for exactly the
            // reason the glyphs are (#717, and see
            // src/design-system/tokens/typography.css for the measurement).
            // Those three families used to arrive through a render-blocking
            // `@import` of fonts.googleapis.com, which no service worker can
            // precache because it is somebody else's origin - so the app
            // painted nothing until a third party answered. Emitted under
            // `assets/` by Vite, hence the bare glob rather than a directory.
            globPatterns: ['**/*.{js,css,html}', 'glyphs/**/*.pbf', '**/*.woff2'],
            // The share screen's detector engine (#837) is the one JS chunk
            // that must NOT be precached: it carries a whole TensorFlow.js
            // runtime behind src/lib/photoScreen.ts's dynamic import, and
            // putting it in the precache would make every install pay
            // megabytes for a feature most hikers never touch. It arrives
            // through the ordinary HTTP cache the first time a share sheet
            // opens instead - and by the same logic its model weights under
            // public/models/ are simply not matched by the globs above.
            // scripts/check-build-output.mjs fails the build if this
            // pattern stops matching the chunk Vite actually emits.
            globIgnores: ['**/photoScreenEngine-*.js'],
          },
          includeAssets: ['icons/icon-192.png', 'icons/icon-512.png'],
          manifest: {
            name: 'OurHike',
            short_name: 'OurHike',
            description:
              'Offline-first topo map and trail data for the Appalachian Trail.',
            // Pulled from the OurHike Design System tokens (--brand-primary /
            // --paper-100), not invented here - see
            // src/design-system/tokens/colors.css.
            theme_color: '#355c3a',
            background_color: '#f7f3e9',
            display: 'standalone',
            // Both follow BASE rather than being hardcoded to the root - see
            // the note above.
            id: BASE,
            scope: BASE,
            start_url: BASE,
            icons: [
              // Rasterized from the real logo mark (chosen 2026-07-28, see
              // .claude/OurHike Design System/ -> components/core/Logo.jsx) -
              // simplified slightly for these sizes (square corners, no
              // torn-edge texture; see that dir's assets/ for why).
              { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
              {
                src: 'icons/icon-512.png',
                sizes: '512x512',
                type: 'image/png',
                purpose: 'any maskable',
              },
            ],
          },
        }),
  ],
  test: {
    environment: 'jsdom',
    // Pinned so a date-formatting assertion means the same thing on every
    // machine (#323): nothing pinned it before, and DownloadCard's formatDay
    // sets no timeZone, so its tests survived on the fixture dates happening
    // to fall the same way in CI's zone and a developer's.
    env: { TZ: 'UTC' },
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text'], // visibility only, not a merge gate - matches
      // pipeline/pyproject.toml's pytest-cov stance exactly, see TESTING.md.

      // Measure the app, not the harness. An explicit `include` is what makes
      // a source file no test imports show up as 0% rather than vanishing from
      // the report - the whole point of looking at coverage is seeing what is
      // NOT covered. (Vitest 4 dropped the separate `all` flag that used to do
      // this; `include` covers it, and passing `all` fails `tsc -b`.)
      include: ['src/**/*.{ts,tsx,js,jsx}'],
      exclude: [
        // Test doubles and setup. Scaffolding, and measuring it says nothing
        // about the app: an unused branch of a mock is a mock with a spare
        // affordance, not untested product code.
        'src/test/**',
        '**/*.test.{ts,tsx}',
        // Types only - erased at build, no statements to execute.
        'src/**/*.d.ts',
        // The bootstrap. Three lines of createRoot().render() whose only
        // possible test is "does React mount", covered by every render() in
        // the suite already.
        'src/main.tsx',
        // The viewer page's bootstrap - DOM glue over viewerController.ts
        // and viewerStyle.ts, which are tested; same reasoning as main.tsx.
        'src/viewer/main.ts',
        // The DEM worker's entry - worker glue over demRpc.ts and
        // demTiles.ts, which are tested; jsdom cannot run a worker at all,
        // so covering the three lines of wiring would mean pretending to.
        'src/map/demWorker.ts',
        // The pin rasteriser's worker entry, on the same reasoning: one line
        // of glue over poiIcons.ts, which is tested to the pixel. Which side
        // of the boundary a build happens on IS tested - see
        // src/map/poiIconImages.test.ts, which drives every way the worker
        // can fail.
        'src/map/poiIconWorker.ts',
      ],
    },
  },
})
