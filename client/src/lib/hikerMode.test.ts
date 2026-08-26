import { describe, it, expect, vi, beforeEach } from 'vitest'
import { get, set } from 'idb-keyval'
import {
  DEFAULT_HIKER_MODE,
  HIKER_MODE_KEY,
  HIKER_MODE_VALUES,
  loadHikerMode,
  normaliseHikerMode,
  saveHikerMode,
} from './hikerMode'

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

describe('hikerMode', () => {
  it('defaults to a day hike on a phone that has never said otherwise', async () => {
    expect(await loadHikerMode()).toBe('day')
    expect(DEFAULT_HIKER_MODE).toBe('day')
  })

  it('round-trips what was saved', async () => {
    await saveHikerMode('volunteer')

    expect(await loadHikerMode()).toBe('volunteer')
  })

  it('round-trips every mode the control offers', async () => {
    // The control renders all three segments, always (#1054); each one has to
    // survive a relaunch or the switch is a label, not a setting.
    for (const mode of HIKER_MODE_VALUES) {
      await saveHikerMode(mode)
      expect(await loadHikerMode()).toBe(mode)
    }
  })

  it('drops a mode this build does not know, rather than trusting it', async () => {
    // The same repair lib/preferences.ts makes for its enum keys: a renamed
    // mode leaves the old word in IndexedDB, and trusting it would hand a
    // value nothing renders to every screen that ranks by it.
    store.set(HIKER_MODE_KEY, 'section')

    expect(await loadHikerMode()).toBe(DEFAULT_HIKER_MODE)
  })

  it('reads null and garbage as absent, not as an answer', async () => {
    expect(normaliseHikerMode(null)).toBe(DEFAULT_HIKER_MODE)
    expect(normaliseHikerMode(undefined)).toBe(DEFAULT_HIKER_MODE)
    expect(normaliseHikerMode(42)).toBe(DEFAULT_HIKER_MODE)
    expect(normaliseHikerMode({ mode: 'thru' })).toBe(DEFAULT_HIKER_MODE)
  })
})
