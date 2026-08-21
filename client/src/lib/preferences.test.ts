import { describe, it, expect, vi, beforeEach } from 'vitest'
import { get, set } from 'idb-keyval'
import {
  adoptPreferences,
  forgetPreferencesSync,
  loadPreferences,
  normalisePreferences,
  preferencesSyncState,
  recordPreferencesPush,
  savePreferences,
  PREFERENCES_KEY,
  PREFERENCES_SYNC_KEY,
} from './preferences'
import { DEFAULT_PREFERENCES } from './userPreferences'

vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), update: vi.fn() }))

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

  // The repair used to be four hand-rolled per-key functions, which is how
  // these two keys ended up with no guard at all (#175). One case each on the
  // keys the generalisation newly covers; the per-key cases above prove the
  // behaviour the table inherited.
  it('drops a unit system this build does not know, rather than trusting it', async () => {
    store.set(PREFERENCES_KEY, { ...DEFAULT_PREFERENCES, unit_system: 'furlongs' })

    expect((await loadPreferences()).unit_system).toBe(DEFAULT_PREFERENCES.unit_system)
  })

  it('drops a background zoom this build does not offer', async () => {
    store.set(PREFERENCES_KEY, { ...DEFAULT_PREFERENCES, max_background_zoom: 15 })

    expect((await loadPreferences()).max_background_zoom).toBe(
      DEFAULT_PREFERENCES.max_background_zoom,
    )
  })

  it("keeps reporter_type's null - it is an answer, not a corrupt value", async () => {
    // Null means "hasn't said" (#233), and dropping it to the default would
    // re-ask a question the hiker declined - or worse, invent an answer.
    store.set(PREFERENCES_KEY, { ...DEFAULT_PREFERENCES, reporter_type: null })

    expect((await loadPreferences()).reporter_type).toBeNull()
  })

  it('drops a reporter type outside the four the trail cares about', async () => {
    store.set(PREFERENCES_KEY, { ...DEFAULT_PREFERENCES, reporter_type: 'influencer' })

    expect((await loadPreferences()).reporter_type).toBe(
      DEFAULT_PREFERENCES.reporter_type,
    )
  })
})

// --- The sync bookkeeping (#891) -------------------------------------------
//
// Two writers of one blob, and the tests that matter are about telling them
// apart. A local change must be pushable; an adopted one must not, or the
// device pushes back what it just pulled on every launch for ever.

describe('the sync bookkeeping', () => {
  it('says a phone that has never synced has never synced', async () => {
    // Null `syncedAt` is what makes a first sign-in adopt the account rather
    // than overwrite it, so its absence is a fact rather than an empty value.
    expect(await preferencesSyncState()).toEqual({ dirty: false, syncedAt: null })
  })

  it('marks a local change dirty', async () => {
    await savePreferences({ ...DEFAULT_PREFERENCES, theme: 'dark' })

    expect((await preferencesSyncState()).dirty).toBe(true)
  })

  it('keeps the last sync stamp when a local change is made', async () => {
    // The pair has to survive together: losing `syncedAt` on a local edit
    // would make this device look never-synced, and a never-synced device
    // pulls - which would throw away the very change that was just made.
    await recordPreferencesPush('2026-08-21T10:00:00Z')
    await savePreferences({ ...DEFAULT_PREFERENCES, theme: 'dark' })

    expect(await preferencesSyncState()).toEqual({
      dirty: true,
      syncedAt: '2026-08-21T10:00:00Z',
    })
  })

  it('adopting the account is not a local change', async () => {
    // The load-bearing one. `adoptPreferences` writing dirty would be an
    // infinite push loop that nothing in the app would surface.
    await adoptPreferences(
      { ...DEFAULT_PREFERENCES, theme: 'dark' },
      '2026-08-21T10:00:00Z',
    )

    expect(await preferencesSyncState()).toEqual({
      dirty: false,
      syncedAt: '2026-08-21T10:00:00Z',
    })
    expect((await loadPreferences()).theme).toBe('dark')
  })

  it('signing out keeps the preferences and drops the claim to an account', async () => {
    await adoptPreferences(
      { ...DEFAULT_PREFERENCES, theme: 'dark' },
      '2026-08-21T10:00:00Z',
    )

    await forgetPreferencesSync()

    expect((await loadPreferences()).theme).toBe('dark')
    expect(await preferencesSyncState()).toEqual({ dirty: false, syncedAt: null })
  })

  it('reads a corrupt bookkeeping entry as never-synced rather than trusting it', async () => {
    // The safe direction: never-synced means the next sign-in pulls, which
    // loses at most this device's unpushed edits. Reading a corrupt entry as
    // "synced and dirty" would push those over the account instead.
    await set(PREFERENCES_SYNC_KEY, { dirty: 'yes', syncedAt: 17 })

    expect(await preferencesSyncState()).toEqual({ dirty: false, syncedAt: null })
  })
})

describe('normalising a blob from somewhere else', () => {
  it('repairs an account’s blob exactly as it repairs a stored one', async () => {
    // The account is a second writer of this shape, and a blob that arrived
    // over TLS is not thereby a blob this build can render.
    const repaired = normalisePreferences({
      theme: 'dark',
      background_source: 'osm_styled_live' as never,
    })

    expect(repaired.theme).toBe('dark')
    expect(repaired.background_source).toBe(DEFAULT_PREFERENCES.background_source)
  })

  it('fills in a key the account’s build did not have', async () => {
    expect(normalisePreferences({}).wrong_way_alert_enabled).toBe(
      DEFAULT_PREFERENCES.wrong_way_alert_enabled,
    )
  })
})
