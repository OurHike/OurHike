/// <reference types="vitest/config" />
import { defineConfig, loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
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
    plugins: [react(), pagesHeaders(env)],
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
