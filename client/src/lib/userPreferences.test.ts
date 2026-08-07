import { describe, it, expect } from 'vitest'
import {
  BACKGROUND_SOURCES,
  DEFAULT_PREFERENCES,
  MAP_STYLE_VALUES,
  PREFERENCE_KEYS,
  type UserPreferences,
} from './userPreferences'

// TESTING.md invariant 16, asserted where it says to assert it: on the
// SCHEMA, not the DOM. "No closures toggle rendered on the settings screen"
// is a weaker claim than "no such preference exists" - the first survives
// someone adding the control on a different screen, the second does not.
//
// Closures and serious warnings are always shown, with no switch here or
// anywhere (features/MAP_OPTIONS.md, features/HIKER_SAFETY.md). The backend
// enforces the same thing from its side: backend/app/schemas/preferences.py
// sets extra="forbid" precisely so a client sending `show_closures` gets a
// visible 422 rather than having it silently dropped.

describe('UserPreferences schema', () => {
  it.each([
    'show_closures',
    'showClosures',
    'hide_closures',
    'show_warnings',
    'showWarnings',
    'hide_warnings',
    'show_serious_warnings',
  ])('has no "%s" key - a safety layer is not a preference', (forbidden) => {
    expect(PREFERENCE_KEYS).not.toContain(forbidden)
    expect(DEFAULT_PREFERENCES).not.toHaveProperty(forbidden)
  })

  it('exposes no key that would let closures or warnings be switched off', () => {
    // Catches a differently-named future variant, which the exact list above
    // would sail straight past.
    const suspicious = PREFERENCE_KEYS.filter((key) => /closure|warning/i.test(key))

    expect(suspicious).toEqual([])
  })

  it('keeps the wrong-way alert togglable - it is the one push, and it is opt-out', () => {
    // Distinct from the above: the alert is a NOTIFICATION preference, not a
    // question of whether hazards appear on the map. WIREFRAMES.md §10 puts
    // this toggle in Safety & privacy on purpose.
    expect(PREFERENCE_KEYS).toContain('wrong_way_alert_enabled')
  })

  it('matches the backend contract field-for-field', () => {
    // backend/app/schemas/preferences.py is the sync target; a key here that
    // it does not accept becomes a 422 the moment an account is linked.
    //
    // This list is a THIRD copy of the model, which the real cross-language
    // guard warns against in its own docstring
    // (backend/tests/test_preferences_contract.py: "any check that restated
    // the field list here would be a third copy to keep in step"). It is kept
    // because it fails fast, in the client's own suite, where a field is
    // added - but it proves nothing on its own. That test reads both files
    // and compares them; this one only remembers.
    expect([...PREFERENCE_KEYS].sort()).toEqual(
      [
        'anonymity_window_days',
        'auto_rotate_enabled',
        'background_source',
        'download_choice_made',
        'hiking_detail_level',
        'layer_detail_level',
        'location_permission_requested',
        'map_style',
        'max_background_zoom',
        'onboarding_completed',
        'red_light_enabled',
        'reporter_type',
        'show_roads',
        'theme',
        'trail_name',
        'unit_system',
        'waypoint_types_shown',
        'wrong_way_alert_enabled',
      ].sort(),
    )
  })

  it('defaults to the live topo sheet, which still renders the download with no signal', () => {
    // Not a reversal of the offline-first premise: the live background is
    // drawn OVER the archive rather than instead of it (map/style.ts), so with
    // no signal this default shows exactly what usgs_topo_offline would. What
    // it changes is first run, where nothing is downloaded yet and the other
    // default would open the app on blank paper.
    expect(DEFAULT_PREFERENCES.background_source).toBe('hiking_topo_live')
  })

  it('offers only backgrounds that are actually implemented', () => {
    // The enum used to carry usgs_topo_live and osm_styled_live, neither of
    // which was ever built. A value nothing can render is a settings row
    // nobody can honour and a preference the backend would happily store.
    expect([...BACKGROUND_SOURCES].sort()).toEqual(
      ['hiking_topo_live', 'usgs_topo_offline'].sort(),
    )
  })

  it('defaults theme to auto and units to imperial, per the canonical model', () => {
    expect(DEFAULT_PREFERENCES.theme).toBe('auto')
    expect(DEFAULT_PREFERENCES.unit_system).toBe('imperial')
  })

  it('defaults the wrong-way alert to on, so the one safety push is not opt-in', () => {
    expect(DEFAULT_PREFERENCES.wrong_way_alert_enabled).toBe(true)
  })

  it('starts a fresh install with onboarding not yet done', () => {
    const fresh: UserPreferences = DEFAULT_PREFERENCES

    expect(fresh.onboarding_completed).toBe(false)
    expect(fresh.download_choice_made).toBe(false)
    expect(fresh.location_permission_requested).toBe(false)
  })
})

describe('the hiking sheet level (#276)', () => {
  it('defaults to Standard, the recommended and envelope-sized cut', () => {
    expect(DEFAULT_PREFERENCES.hiking_detail_level).toBe('standard')
  })
})

describe('map appearance (MAP_STYLE_SPEC.md)', () => {
  it('defaults to the field style with red light off - the reviewed day sheet, never the red one', () => {
    expect(DEFAULT_PREFERENCES.map_style).toBe('field')
    expect(DEFAULT_PREFERENCES.red_light_enabled).toBe(false)
  })

  it('offers all five specced styles, every one with palettes to draw', () => {
    // A style nothing can render is a settings row nobody can honour - all
    // five carry reviewed day and night sheets in map/liveTopo.ts's
    // SHEET_VARIANTS, which liveTopo.test.ts sweeps against this same list.
    expect([...MAP_STYLE_VALUES].sort()).toEqual(
      ['quiet_pine', 'field', 'night_hike', 'parchment', 'ridgeline'].sort(),
    )
  })

  it('defaults layer detail to standard - borders off, everything else on', () => {
    expect(DEFAULT_PREFERENCES.layer_detail_level).toBe('standard')
  })
})
