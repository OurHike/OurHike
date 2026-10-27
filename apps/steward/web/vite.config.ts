/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Relative asset paths, so the build works at a Pages root or under any path.
export default defineConfig({
  base: './',
  plugins: [react()],
  build: {
    // MapLibre is one 1.1 MB chunk (298 KB gzipped, measured 2026-10-27) and is
    // already loaded only when a map first draws, so splitting it further buys nothing.
    chunkSizeWarningLimit: 1200,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
