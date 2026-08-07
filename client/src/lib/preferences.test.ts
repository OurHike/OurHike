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

  // A key holding a value this build no longer knows is the mirror image of a
  // missing key, and merging over the defaults does not fix it: the key IS
  // present, so there is nothing to fill in. background_source has already
  // been through one such change - it used to offer usgs_topo_live and
  // osm_styled_live, neither of which was ever built - and a phone that ran
  // that build would otherwise reach buildMapStyle with a value matching no
  // background, and draw none.
  it('drops a background this build no longer knows, rather than trusting it', async () => {
    await savePreferences({
      ...DEFAULT_PREFERENCES,
      background_source: 'osm_styled_live' as never,
    })

    expect((await loadPreferences()).background_source).toBe(
      DEFAULT_PREFERENCES.background_source,
    )
  })

  it('keeps a background it does know, so this is a repair and not a reset', async () => {
    await savePreferences({
      ...DEFAULT_PREFERENCES,
      background_source: 'usgs_topo_offline',
    })

    expect((await loadPreferences()).background_source).toBe('usgs_topo_offline')
  })

  // The same road to the same black map, via the newest preference: an
  // unknown stored theme rides the merge into resolveTheme, comes back out
  // unresolved, and reaches the map as MAP_BACKDROP[value] - undefined, which
  // MapLibre paints as its default black.
  it('drops a theme this build does not know, rather than trusting it', async () => {
    await savePreferences({ ...DEFAULT_PREFERENCES, theme: 'sepia' as never })

    expect((await loadPreferences()).theme).toBe(DEFAULT_PREFERENCES.theme)
  })

  it('keeps a theme it does know, so this too is a repair and not a reset', async () => {
    await savePreferences({ ...DEFAULT_PREFERENCES, theme: 'dark' })

    expect((await loadPreferences()).theme).toBe('dark')
  })

  // The style list is the one that has ALREADY changed once - v1 shipped two
  // of the five and the rest followed - so a phone moving between builds can
  // hold a value some build has no colours for. Trusted, it reaches the
  // palette lookup and draws nothing - the same road to the same black map.
  it('drops a map style this build cannot draw, rather than trusting it', async () => {
    await savePreferences({ ...DEFAULT_PREFERENCES, map_style: 'sepia' as never })

    expect((await loadPreferences()).map_style).toBe(DEFAULT_PREFERENCES.map_style)
  })

  it('keeps a map style it does know, so this too is a repair and not a reset', async () => {
    await savePreferences({ ...DEFAULT_PREFERENCES, map_style: 'parchment' })

    expect((await loadPreferences()).map_style).toBe('parchment')
  })

  it('leaves the rest of a stored blob alone while repairing the background', async () => {
    await savePreferences({
      ...DEFAULT_PREFERENCES,
      trail_name: 'Switchback',
      background_source: 'usgs_topo_live' as never,
    })

    const loaded = await loadPreferences()

    expect(loaded.trail_name).toBe('Switchback')
    expect(loaded.background_source).toBe(DEFAULT_PREFERENCES.background_source)
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
