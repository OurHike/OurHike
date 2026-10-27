/// <reference types="vitest/config" />
import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { headersFile } from './headers'
import { PHOTO_CACHE, photoLinkPattern } from './src/photoCache'

/** Writes `_headers` into the build, for Cloudflare Pages (headers.ts says what is in it). */
function pagesHeaders(env: Record<string, string>): Plugin {
  return {
    name: 'steward-pages-headers',
    apply: 'build',
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: '_headers',
        source: headersFile({ supabaseUrl: env.VITE_SUPABASE_URL }),
      })
    },
  }
}

// Relative asset paths, so the build works at a Pages root or under any path.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  return {
    base: './',
    plugins: [
      react(),
      pagesHeaders(env),
      // Installable, and opens with no signal (#1911), on the plan OurHike's
      // client uses (client/vite.config.ts): generateSW.
      VitePWA({
        // A new version waits until the page offers a reload and the person
        // takes it (src/update.ts, which also registers the worker): swapped in
        // under an open page, it removed files that page still had to load
        // (the adversarial review's third pass, P4). A claim saved for offline
        // and the photos waiting for signal are in IndexedDB (src/offline.ts),
        // which an update leaves alone either way.
        registerType: 'prompt',
        injectRegister: false,
        workbox: {
          cleanupOutdatedCaches: true,
          // The app and this week's analysis: they are one deployment
          // (steward-analysis.yml), so precaching both keeps the phone's copy
          // of the scores in step with its copy of the code.
          globPatterns: ['**/*.{js,css,html,png,webmanifest}', 'data/*.json'],
          // sites.json was 4.3 MB on 2026-10-27; workbox skips anything over
          // its 2 MB default without a word, which would leave the app
          // offline with no sites.
          maximumFileSizeToCacheInBytes: 8 * 1024 * 1024,
          runtimeCaching: [
            {
              // Basemap tiles the phone has already shown: a site's
              // surroundings stay drawn after the signal goes. Capped, and
              // only what was viewed; nothing is downloaded in bulk. Only
              // tiles that never change at their address: vector tiles sit
              // under a dated planet build (/planet/20261025_080012_pt/ on
              // 2026-10-27) and the Natural Earth raster never changes.
              urlPattern:
                /^https:\/\/tiles\.openfreemap\.org\/(planet\/[^/]+\/\d+\/\d+\/\d+\.pbf|natural_earth\/)/,
              handler: 'CacheFirst',
              options: {
                cacheName: 'basemap',
                expiration: { maxEntries: 3000, maxAgeSeconds: 30 * 24 * 60 * 60 },
                cacheableResponse: { statuses: [0, 200] },
              },
            },
            {
              // The style, the TileJSON naming this week's planet build, the
              // sprites and the glyphs: kept for offline, but checked again
              // whenever there is signal, since a cached TileJSON would hold
              // the map to an old build for a month (the third pass, P6).
              urlPattern: /^https:\/\/tiles\.openfreemap\.org\//,
              handler: 'StaleWhileRevalidate',
              options: {
                cacheName: 'basemap-style',
                expiration: { maxEntries: 300, maxAgeSeconds: 30 * 24 * 60 * 60 },
                cacheableResponse: { statuses: [0, 200] },
              },
            },
            {
              // Claim photos the phone has shown, under the links Storage
              // signed for them: matched with the token ignored, so the before
              // photo a crew lines the after photo up with still shows at a
              // site with no signal, after its link has expired, and a fresh
              // link to the same photo is not a fresh download. A photo's
              // address never changes what it holds: its name carries the
              // phone's own id for it, which a claim takes once. Emptied at
              // sign-out with the claims saved for offline (src/account.tsx).
              urlPattern: photoLinkPattern(env.VITE_SUPABASE_URL),
              handler: 'CacheFirst',
              options: {
                cacheName: PHOTO_CACHE,
                matchOptions: { ignoreSearch: true },
                expiration: { maxEntries: 200, maxAgeSeconds: 30 * 24 * 60 * 60 },
                // Asked for with CORS (ClaimScreen's PhotoImage), so a failed
                // or refused answer is seen and not kept.
                cacheableResponse: { statuses: [200] },
              },
            },
            {
              urlPattern: /^https:\/\/fonts\.(googleapis|gstatic)\.com\//,
              handler: 'CacheFirst',
              options: {
                cacheName: 'fonts',
                expiration: { maxEntries: 30, maxAgeSeconds: 365 * 24 * 60 * 60 },
                cacheableResponse: { statuses: [0, 200] },
              },
            },
          ],
        },
        includeAssets: ['icons/apple-touch-icon.png'],
        manifest: {
          name: 'Campsite Steward',
          short_name: 'Steward',
          description:
            'Which Appalachian Trail campsites need restoration first, and how to claim, restore and verify one.',
          // src/styles.css's --ink and --ground.
          theme_color: '#15252a',
          background_color: '#f2f4f1',
          display: 'standalone',
          start_url: './',
          scope: './',
          icons: [
            { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
            { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png' },
            {
              src: 'icons/maskable-512.png',
              sizes: '512x512',
              type: 'image/png',
              purpose: 'maskable',
            },
          ],
        },
      }),
    ],
    build: {
      // MapLibre is one 1.1 MB chunk (298 KB gzipped, measured 2026-10-27) and is
      // already loaded only when a map first draws, so splitting it further buys nothing.
      chunkSizeWarningLimit: 1200,
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
    },
  }
})
