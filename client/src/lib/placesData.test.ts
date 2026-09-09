import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { fetchPlaces, recallPlaces } from './placesData'
import { PLACES_KEY } from './config'
import { conditionsCacheKey } from './conditionsCache'

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))
vi.mock('./config', async (importOriginal) => {
  const original = await importOriginal<typeof import('./config')>()
  return {
    ...original,
    DATA_CONFIGURED: true,
    dataUrl: (key: string) => `https://data.test/${key}`,
  }
})

import { get, set } from 'idb-keyval'

const store = new Map<string, unknown>()

beforeEach(() => {
  store.clear()
  vi.mocked(get).mockImplementation((key) => Promise.resolve(store.get(key as string)))
  vi.mocked(set).mockImplementation((key, value) => {
    store.set(key as string, value)
    return Promise.resolve()
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

const DOCUMENT = {
  generated_at: '2026-09-10T12:00:00Z',
  trailRadiusMiles: 5,
  trailMilesMeasured: true,
  places: [
    {
      id: 'p',
      name: 'Harriman State Park',
      kind: 'park',
      lon: -74.1,
      lat: 41.25,
      trailMiles: 46.3,
    },
  ],
}

describe('fetchPlaces', () => {
  it('keeps what the bucket said and hands back the places', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(new Response(JSON.stringify(DOCUMENT), { status: 200 })),
      ),
    )

    const places = await fetchPlaces()

    expect(places?.places[0].name).toBe('Harriman State Park')
    expect(store.get(conditionsCacheKey(PLACES_KEY))).toMatchObject({
      document: DOCUMENT,
    })
  })

  it('reads a 404 as nothing, and does not clear the kept copy', async () => {
    store.set(conditionsCacheKey(PLACES_KEY), { document: DOCUMENT, storedAt: 'x' })
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(new Response('', { status: 404 }))),
    )

    expect(await fetchPlaces()).toBeNull()
    expect(store.get(conditionsCacheKey(PLACES_KEY))).toMatchObject({
      document: DOCUMENT,
    })
  })

  it('reads a broken document as nothing rather than throwing', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(new Response('not json', { status: 200 }))),
    )

    expect(await fetchPlaces()).toBeNull()
  })
})

describe('recallPlaces', () => {
  it('validates the kept copy on the way back out', async () => {
    store.set(conditionsCacheKey(PLACES_KEY), {
      document: { ...DOCUMENT, places: [...DOCUMENT.places, { id: 'bad' }] },
      storedAt: 'x',
    })

    const kept = await recallPlaces()

    expect(kept?.places.map((p) => p.id)).toEqual(['p'])
  })

  it('is null when nothing was kept', async () => {
    expect(await recallPlaces()).toBeNull()
  })
})
