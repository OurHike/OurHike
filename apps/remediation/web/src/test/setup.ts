import '@testing-library/jest-dom/vitest'
// IndexedDB for src/offline.ts, in memory: jsdom has none.
import 'fake-indexeddb/auto'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// jsdom has scrollTo but logs "Not implemented" on every call; a route change calls it.
window.scrollTo = () => {}

afterEach(() => cleanup())
