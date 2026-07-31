import { realpathSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// Where the app will be served from. GitHub Pages serves a project site under
// /<repo>/, not at the domain root, and a PWA is unusually sensitive to that:
// `scope` and `start_url` decide which pages the installed app owns, so a
// manifest claiming "/" on a subpath install either fails validation or
// installs an app that opens the wrong page. Settable so the same build works
// at a root domain later without editing this file.
//
// Must have a trailing slash - Vite joins it to asset paths directly.
const BASE = process.env.VITE_BASE_PATH ?? '/'

// https://vite.dev/config/
export default defineConfig({
  base: BASE,
  // Explicit root resolved from this file's own URL, not process.cwd(): on
  // Windows, a shell invocation with a lowercase drive letter (e.g. `c:\...`)
  // makes Vitest's internal root-comparison silently mismatch against the
  // uppercase-cased path Vite resolves elsewhere, crashing with "Cannot read
  // properties of undefined (reading 'config')" before any test runs - see
  // https://github.com/vitest-dev/vitest/issues/5251. Resolving from
  // import.meta.url keeps the casing consistent regardless of how the
  // process was launched.
  root: realpathSync.native(fileURLToPath(new URL('.', import.meta.url))),
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
          registerType: 'prompt', // never silently swap the running app
          // mid-session - matches this project's "honest about staleness"
          // stance elsewhere (a hiker relying on the app mid-junction should
          // choose when to reload, not have it happen under them).
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
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text'], // visibility only, not a merge gate - matches
      // pipeline/pyproject.toml's pytest-cov stance exactly, see TESTING.md.
    },
  },
})
