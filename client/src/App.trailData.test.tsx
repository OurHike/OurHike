// The trail lines arriving on their own, without a 314 MB download first.
//
// Its own file because it needs a CONFIGURED data source, and lib/config reads
// the base URL once at module load - so the only honest way to have one is to
// mock the module before App is imported. App.test.tsx deliberately runs
// unconfigured, which is the state the Downloads screen's warning is about, and
// mocking config there would quietly change the subject of every test in it.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { get, set } from 'idb-keyval'
import { MockMap, resetMapLibreMock } from './test/mocks/maplibre-gl'
import { PREFERENCES_KEY } from './lib/preferences'
import { DEFAULT_PREFERENCES } from './lib/userPreferences'
import { TRAILS_BLOB_KEY } from './lib/trailData'

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))
vi.mock('./map/protocol', () => ({
  PMTILES_SCHEME: 'pmtiles',
  registerPMTilesProtocol: vi.fn(),
  CORRIDOR_ARCHIVE_URL: 'pmtiles://ourhike-corridor',
}))
// Only the base URL and the two helpers keyed off it. Spreading the real
// module keeps POI_TYPES and the file-name constants exactly as they ship, so
// this stays a test about a configured build rather than about a fake one.
vi.mock('./lib/config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./lib/config')>()),
  DATA_BASE_URL: 'https://data.example',
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.example/${key}`,
  archiveUrl: () => 'https://data.example/corridor.pmtiles',
}))

const store = new Map<string, unknown>()

const TRAILS = '{"type":"FeatureCollection","features":[]}'

beforeEach(() => {
  store.clear()
  resetMapLibreMock()
  vi.mocked(get).mockImplementation((key) => Promise.resolve(store.get(key as string)))
  vi.mocked(set).mockImplementation((key, value) => {
    store.set(key as string, value)
    return Promise.resolve()
  })
  store.set(PREFERENCES_KEY, {
    ...DEFAULT_PREFERENCES,
    onboarding_completed: true,
    download_choice_made: true,
  })
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers(),
        // Bytes, because trail data is hashed before it is stored (#197).
        arrayBuffer: () => Promise.resolve(new TextEncoder().encode(TRAILS).buffer),
        blob: () => Promise.resolve(new Blob([TRAILS])),
        text: () => Promise.resolve(TRAILS),
        json: () => Promise.resolve(JSON.parse(TRAILS)),
      } as unknown as Response),
    ),
  )
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  // restore, not just clear: the offline cases spy on `navigator.onLine`'s
  // getter, and a cleared spy still answers false - which silently turned the
  // fetch-failure case below into a test about being offline.
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

async function renderApp() {
  const { default: App } = await import('./App')
  render(<App />)
  await screen.findByRole('region', { name: /trail map/i })
}

function requested() {
  return vi.mocked(fetch).mock.calls.map((c) => String(c[0]))
}

describe('trail data on a phone that has downloaded nothing', () => {
  it('fetches the trail lines without waiting for anyone to tap Download', async () => {
    // The reported gap: the centerline only appeared after the corridor
    // archive was downloaded. The lines are a few megabytes against 314 MB,
    // and without them the app opens on a background with no trail on it -
    // nothing to search, no POIs, no elevation ribbon.
    await renderApp()

    await waitFor(() => {
      expect(requested().some((url) => url.includes('trails'))).toBe(true)
    })
  })

  it('stores what it fetched, so the next launch reads it off the phone', async () => {
    await renderApp()

    await waitFor(() => {
      expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob)
    })
  })

  it('never asks for the huge archive, which stays the hiker’s decision', async () => {
    // The whole point of the split. Trail lines are the map; the corridor
    // raster is hundreds of megabytes of someone's data allowance and stays
    // behind the button on the Downloads screen.
    await renderApp()

    await waitFor(() => {
      expect(requested().some((url) => url.includes('trails'))).toBe(true)
    })
    expect(requested().some((url) => url.includes('.pmtiles'))).toBe(false)
  })

  it('does not re-fetch when the phone already has the lines', async () => {
    store.set(TRAILS_BLOB_KEY, new Blob([TRAILS]))
    store.set('ourhike:pois', [])

    await renderApp()

    await waitFor(() => expect(MockMap.live.length).toBeGreaterThan(0))
    expect(requested().some((url) => url.includes('trails'))).toBe(false)
  })

  it('still reads the stored lines with no signal, which is the whole point of storing them', async () => {
    // The regression this guards: gating the read on "configured and online"
    // alongside the fetch left a hiker on a ridge - exactly who the offline
    // store exists for - looking at a map with no trail on it.
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
    store.set(TRAILS_BLOB_KEY, new Blob([TRAILS]))
    store.set('ourhike:pois', [])

    await renderApp()

    await waitFor(() => expect(MockMap.live.length).toBeGreaterThan(0))
    expect(vi.mocked(get).mock.calls.map((c) => String(c[0]))).toContain(TRAILS_BLOB_KEY)
    expect(requested()).toEqual([])
  })

  it('waits for signal rather than failing a fetch it knows cannot work', async () => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)

    await renderApp()

    await waitFor(() => expect(MockMap.live.length).toBeGreaterThan(0))
    expect(requested()).toEqual([])
  })

  it('says nothing when the fetch fails, because nobody asked for it', async () => {
    // Not a result the hiker is owed a message about: it leaves exactly the
    // empty map they would have had anyway, and the Downloads screen still
    // reports errors for the download they DO ask for.
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
    } as Response)

    await renderApp()

    await waitFor(() => {
      expect(requested().some((url) => url.includes('trails'))).toBe(true)
    })
    expect(screen.queryByText(/404|not found|failed/i)).not.toBeInTheDocument()
    expect(store.get(TRAILS_BLOB_KEY)).toBeUndefined()
  })
})
