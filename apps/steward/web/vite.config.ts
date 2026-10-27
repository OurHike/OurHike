/// <reference types="vitest/config" />
import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { headersFile } from './headers'

/** Writes `_headers` into the build, for Cloudflare Pages (headers.ts says what is in it). */
function pagesHeaders(env: Record<string, string>): Plugin {
  return {
    name: 'steward-pages-headers',
    apply: 'build',
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: '_headers',
        source: headersFile({
          supabaseUrl: env.VITE_SUPABASE_URL,
          apiUrl: env.VITE_STEWARD_API_URL,
        }),
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
      // client uses (client/vite.config.ts): generateSW, updating itself.
      VitePWA({
        // Safe to swap automatically because the worker holds only files that
        // ship together; a claim saved for offline and the photos waiting for
        // signal are in IndexedDB (src/offline.ts), which an update leaves alone.
        registerType: 'autoUpdate',
        injectRegister: 'script-defer',
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
              // only what was viewed; nothing is downloaded in bulk.
              urlPattern: /^https:\/\/tiles\.openfreemap\.org\//,
              handler: 'CacheFirst',
              options: {
                cacheName: 'basemap',
                expiration: { maxEntries: 3000, maxAgeSeconds: 30 * 24 * 60 * 60 },
                cacheableResponse: { statuses: [0, 200] },
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
