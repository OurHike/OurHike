import { describe, it, expect, vi, beforeEach } from 'vitest'
import { get, set } from 'idb-keyval'
import { loadPreferences, savePreferences, PREFERENCES_KEY } from './preferences'
import { DEFAULT_PREFERENCES } from './userPreferences'

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

describe('preferences', () => {
  it('hands back the defaults on a phone that has never saved any', async () => {
    expect(await loadPreferences()).toEqual(DEFAULT_PREFERENCES)
  })

  it('round-trips what was saved', async () => {
    await savePreferences({ ...DEFAULT_PREFERENCES, trail_name: 'Sourdough' })

    expect((await loadPreferences()).trail_name).toBe('Sourdough')
  })

  // The one that matters: a build adding a key would otherwise read undefined
  // for it on every phone that saved preferences before it existed - and an
  // undefined wrong_way_alert_enabled is a safety default silently switching
  // itself off on exactly the phones that have been in use longest.
  it('fills in a key the stored copy predates, rather than reading it as undefined', async () => {
    const { wrong_way_alert_enabled: _omitted, ...withoutTheKey } = DEFAULT_PREFERENCES
    store.set(PREFERENCES_KEY, withoutTheKey)

    expect((await loadPreferences()).wrong_way_alert_enabled).toBe(true)
  })

  it('lets a stored value win over the default it is replacing', async () => {
    store.set(PREFERENCES_KEY, { ...DEFAULT_PREFERENCES, wrong_way_alert_enabled: false })

    expect((await loadPreferences()).wrong_way_alert_enabled).toBe(false)
  })
})
