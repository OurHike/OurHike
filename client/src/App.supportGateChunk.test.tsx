import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import type { ComponentType } from 'react'
import App from './App'
import { appHarness, openMapTab } from './test/appHarness'
import type { SupportGateProps } from './screens/SupportGate'

// The day-5 ask's chunk failing to arrive (RELEASING.md §8b, "the map
// drawing at all"). SupportGate is a screens/deferred.ts entry, and a
// deferred screen whose import() rejects throws from render so the nearest
// chrome/ErrorBoundary.tsx can show its fallback with the tab bar still up.
// The gate is mounted in App's top-level fragment, after the last in-app
// boundary, so the nearest one used to be main.tsx's - whose fallback is the
// whole page and cannot offer the tab bar. A precache evicted mid-hike, or a
// build served half from one deploy and half from the next, took the map
// down for an ask that is not worth a blank page. The gate's own boundary
// in App.tsx is what this guards.

const chunk = vi.hoisted(() => {
  let fail: ((error: Error) => void) | null = null
  let asked = 0
  return {
    /** The gate's import(), which never resolves: the test rejects it. */
    load: (): Promise<never> => {
      asked += 1
      return new Promise<never>((_, reject) => {
        fail = reject
      })
    },
    fail: (error: Error) => fail?.(error),
    get asked() {
      return asked
    },
  }
})

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  getMany: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./map/archiveZooms', () => ({
  readArchiveZooms: () => Promise.resolve(null),
  readArchiveFootprint: () => Promise.resolve(null),
}))
vi.mock('./lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./lib/api')>()),
  // The gate is mounted only in a build with a backend.
  API_CONFIGURED: true,
  accessToken: vi.fn(async () => null),
  fetchReports: vi.fn(async () => []),
  fetchClosures: vi.fn(async () => []),
  fetchFieldNotes: vi.fn(async () => []),
  fetchDisputes: vi.fn(async () => []),
}))
// Every other deferred screen loads as it does in the suite (the harness
// preloads the original registry); only the gate's chunk is the one that
// never comes.
vi.mock('./screens/deferred', async (importOriginal) => {
  const original = await importOriginal<typeof import('./screens/deferred')>()
  const { deferredScreen } = await import('./lib/deferredScreen')
  return {
    ...original,
    SupportGate: deferredScreen<SupportGateProps>(
      chunk.load as () => Promise<ComponentType<SupportGateProps>>,
      'SupportGate',
    ),
  }
})

const app = appHarness({ navigator: { onLine: true }, objectUrls: true })

beforeEach(() => {
  app.onboard()
})
afterEach(() => {
  vi.restoreAllMocks()
})

describe('the day-5 ask whose code never arrives', () => {
  it('a SupportGate chunk that never arrives leaves the map and the tab bar up', async () => {
    const logged = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    // The gate mounts a frame after the first commit and asks for its chunk
    // then; that ask is the observable that it is on screen and waiting.
    await act(async () => {
      await vi.waitFor(() => expect(chunk.asked).toBe(1))
    })

    await act(async () => {
      chunk.fail(new Error('ChunkLoadError: Loading chunk SupportGate failed'))
    })

    expect(screen.getByRole('region', { name: /trail map/i })).toBeInTheDocument()
    for (const name of ['Today', 'Map', 'Plan', 'More']) {
      expect(screen.getByRole('tab', { name })).toBeInTheDocument()
    }
    // Nothing is said to the hiker, and nothing is sent anywhere; the
    // failure reaches the console, which is where a developer looks.
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(logged).toHaveBeenCalledWith(
      'A screen failed and was replaced with a fallback.',
      expect.objectContaining({ message: expect.stringContaining('ChunkLoadError') }),
      expect.anything(),
    )
  })
})
