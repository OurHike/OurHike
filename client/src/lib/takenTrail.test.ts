import { describe, it, expect, vi, beforeEach } from 'vitest'
import { get, set } from 'idb-keyval'
import {
  TAKEN_TRAIL_KEY,
  loadTakenTrail,
  normaliseTakenTrail,
  saveTakenTrail,
} from './takenTrail'

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn() }))

const store = new Map<string, unknown>()

beforeEach(() => {
  store.clear()
  vi.mocked(get).mockImplementation((key) => Promise.resolve(store.get(key as string)))
  vi.mocked(set).mockImplementation((key, value) => {
    store.set(key as string, value)
    return Promise.resolve()
  })
})

describe('takenTrail', () => {
  it('is null on a phone that has taken nothing - the plate names no trail it was not given', async () => {
    expect(await loadTakenTrail()).toBeNull()
  })

  it('round-trips a registry trail, and letting it go', async () => {
    await saveTakenTrail('AT')
    expect(await loadTakenTrail()).toBe('AT')
    expect(store.get(TAKEN_TRAIL_KEY)).toBe('AT')

    await saveTakenTrail(null)
    expect(await loadTakenTrail()).toBeNull()
  })

  it('falls back to null for an id this build does not know, rather than naming it', () => {
    expect(normaliseTakenTrail('AT')).toBe('AT')
    expect(normaliseTakenTrail('LP')).toBe('LP')
    expect(normaliseTakenTrail('appalachian')).toBeNull()
    expect(normaliseTakenTrail(42)).toBeNull()
    expect(normaliseTakenTrail(undefined)).toBeNull()
  })
})
