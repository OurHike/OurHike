import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { usePlaces } from './usePlaces'
import { fetchPlaces, recallPlaces } from './placesData'
import { NO_PLACES, type PlacesDocument } from './places'

vi.mock('./placesData', () => ({ fetchPlaces: vi.fn(), recallPlaces: vi.fn() }))
vi.mock('./config', async (importOriginal) => {
  const original = await importOriginal<typeof import('./config')>()
  return { ...original, DATA_CONFIGURED: true }
})

const KEPT: PlacesDocument = {
  generatedAt: '2026-09-01T00:00:00Z',
  trailRadiusMiles: 5,
  trailMilesMeasured: true,
  places: [{ id: 'kept', name: 'Kept Park', kind: 'park', lon: -74, lat: 41 }],
}
const FRESH: PlacesDocument = { ...KEPT, places: [{ ...KEPT.places[0], id: 'fresh' }] }

beforeEach(() => {
  vi.mocked(recallPlaces).mockReset()
  vi.mocked(fetchPlaces).mockReset()
})

describe('usePlaces', () => {
  it('reads nothing until wanted, and says it has not settled', () => {
    vi.mocked(recallPlaces).mockResolvedValue(KEPT)
    const { result } = renderHook(() => usePlaces(true, false))

    expect(result.current.places).toBe(NO_PLACES)
    expect(result.current.settled).toBe(false)
    expect(recallPlaces).not.toHaveBeenCalled()
    expect(fetchPlaces).not.toHaveBeenCalled()
  })

  it('offline: the kept copy, settled once it has answered, and the network never asked', async () => {
    vi.mocked(recallPlaces).mockResolvedValue(KEPT)
    const { result } = renderHook(() => usePlaces(false))

    await waitFor(() => expect(result.current.settled).toBe(true))
    expect(result.current.places).toBe(KEPT)
    expect(fetchPlaces).not.toHaveBeenCalled()
  })

  it('online: the bucket replaces the kept copy, and settles only when both have answered', async () => {
    vi.mocked(recallPlaces).mockResolvedValue(KEPT)
    let answer: (document: PlacesDocument | null) => void = () => {}
    vi.mocked(fetchPlaces).mockReturnValue(
      new Promise((resolve) => {
        answer = resolve
      }),
    )
    const { result } = renderHook(() => usePlaces(true))

    await waitFor(() => expect(result.current.places).toBe(KEPT))
    expect(result.current.settled).toBe(false)

    answer(FRESH)
    await waitFor(() => expect(result.current.settled).toBe(true))
    expect(result.current.places).toBe(FRESH)
  })

  it('a bucket with nothing published leaves the kept copy, and is still settled', async () => {
    vi.mocked(recallPlaces).mockResolvedValue(null)
    vi.mocked(fetchPlaces).mockResolvedValue(null)
    const { result } = renderHook(() => usePlaces(true))

    await waitFor(() => expect(result.current.settled).toBe(true))
    expect(result.current.places).toBe(NO_PLACES)
  })
})
