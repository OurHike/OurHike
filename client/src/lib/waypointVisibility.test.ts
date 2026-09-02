import { describe, it, expect } from 'vitest'
import {
  DEFAULT_SHOWN_TYPES,
  HIDEABLE_TYPES,
  hiddenTypesFrom,
  isFiltered,
  onlyType,
  showAllTypes,
  shownSelection,
  toggleType,
} from './waypointVisibility'
import { NEVER_HIDEABLE } from './legendContents'

// The stored preference is *shown*, the map consumes *hidden* (#530). What is
// worth testing is the translation, the collapse back to "all", and the safety
// rule - which has to be structural rather than a check somebody remembers,
// because the failure it prevents is a map with a closure hidden on it.

describe('hiddenTypesFrom', () => {
  it('hides nothing when the preference is empty', () => {
    // `[]` means ALL, which is what it has always meant - though a fresh
    // install no longer starts there (see DEFAULT_SHOWN_TYPES below).
    // Reading `[]` as "show nothing" would open the app to a blank map.
    expect(hiddenTypesFrom([]).size).toBe(0)
  })

  it('hides everything the preference does not name', () => {
    const hidden = hiddenTypesFrom(['water'])

    expect(hidden.has('privy')).toBe(true)
    expect(hidden.has('shelter')).toBe(true)
    expect(hidden.has('water')).toBe(false)
  })

  it('never hides a safety layer, whatever the preference says', () => {
    // Not reachable through the UI - the affordance is not built - but a stored
    // value can arrive from a hand-edited account or an older client, and this is
    // the map that gets drawn from it.
    for (const type of NEVER_HIDEABLE) {
      expect(hiddenTypesFrom(['water']).has(type)).toBe(false)
      expect(hiddenTypesFrom([]).has(type)).toBe(false)
    }
  })

  it('ignores a category it does not know', () => {
    // A preference synced from a later release naming a type this build has
    // never heard of must not blank the map.
    const hidden = hiddenTypesFrom(['water', 'gondola'])

    expect(hidden.has('water')).toBe(false)
    expect([...hidden].every((type) => HIDEABLE_TYPES.includes(type))).toBe(true)
  })
})

describe('toggleType', () => {
  it('hides one category from an all-on start', () => {
    const next = toggleType([], 'privy')

    expect(hiddenTypesFrom(next)).toEqual(new Set(['privy']))
  })

  it('shows it again on a second toggle', () => {
    const next = toggleType(toggleType([], 'privy'), 'privy')

    expect(hiddenTypesFrom(next).size).toBe(0)
  })

  it('collapses back to the empty list when everything is shown again', () => {
    // "All" gets ONE representation in storage. Two that behave the same today
    // is two that diverge the next time a category is added.
    expect(toggleType(toggleType([], 'privy'), 'privy')).toEqual([])
  })

  it('refuses to toggle a safety layer', () => {
    for (const type of NEVER_HIDEABLE) {
      expect(hiddenTypesFrom(toggleType([], type)).size).toBe(0)
    }
  })

  it('hides a second category without showing the first again', () => {
    const next = toggleType(toggleType([], 'privy'), 'viewpoint')

    expect(hiddenTypesFrom(next)).toEqual(new Set(['privy', 'viewpoint']))
  })
})

describe('onlyType', () => {
  it('shows one category and hides the rest', () => {
    // The control the whole issue is worth building for: at a crowded zoom this
    // is four water pins drawn against forty.
    const next = onlyType('water')

    expect(next).toEqual(['water'])
    expect(hiddenTypesFrom(next).has('viewpoint')).toBe(true)
  })

  it('falls back to showing everything for a safety layer', () => {
    // "Closures only" would be a map with the shelters, water and campsites
    // gone - not what anyone tapping that row means, and one tap from a map
    // missing the things a hiker navigates by.
    for (const type of NEVER_HIDEABLE) {
      expect(onlyType(type)).toEqual([])
    }
  })

  it('falls back to showing everything for a category it does not know', () => {
    expect(onlyType('gondola')).toEqual([])
  })
})

describe('the way back', () => {
  it('shows everything again', () => {
    expect(hiddenTypesFrom(showAllTypes()).size).toBe(0)
  })

  it('knows whether a filter is in force', () => {
    expect(isFiltered([])).toBe(false)
    expect(isFiltered(['water'])).toBe(true)
  })

  it('is not "filtered" when the preference names every category', () => {
    // Belt and braces against a client that wrote the expanded form: nothing is
    // hidden, so no way-out line should be claiming otherwise.
    expect(isFiltered([...HIDEABLE_TYPES])).toBe(false)
  })
})

describe('shownSelection', () => {
  it('is "all" when nothing is filtered', () => {
    expect(shownSelection([])).toEqual({ kind: 'all' })
  })

  it('is "all" when every category is listed out', () => {
    // The state the control DISPLAYS, so this matters on screen and not only in
    // storage: read off `shown.length` instead, a hiker who toggled the last
    // category back on would be looking at a picker reading "8 of 8 types".
    expect(shownSelection([...HIDEABLE_TYPES])).toEqual({ kind: 'all' })
  })

  it('names the one category on a single-type filter', () => {
    // The standing readout is the price of the filter PERSISTING. It survives a
    // pan on purpose - "where is the next water" is answered by panning along
    // the trail with water alone drawn - so the state has to stay visible or a
    // hiker forgets they set it.
    expect(shownSelection(['water'])).toEqual({ kind: 'one', type: 'water' })
  })

  it('counts them when several are shown', () => {
    expect(shownSelection(['water', 'shelter'])).toEqual({
      kind: 'some',
      shown: 2,
      of: HIDEABLE_TYPES.length,
    })
  })

  it('ignores a safety layer in the stored value rather than naming it', () => {
    // `['closure']` hides every hideable category, and the safety layers are
    // drawn regardless (NEVER_HIDEABLE). "0 of 8" is the honest readout; "closure
    // only" would claim a control the app does not have.
    expect(shownSelection(['closure'])).toEqual({
      kind: 'some',
      shown: 0,
      of: HIDEABLE_TYPES.length,
    })
  })
})

describe('HIDEABLE_TYPES', () => {
  it('excludes the safety layers', () => {
    for (const type of NEVER_HIDEABLE) expect(HIDEABLE_TYPES).not.toContain(type)
  })

  it('is the categories a release actually serves', () => {
    // Not a second list: these come from config.ts's POI_TYPES, which
    // verify_release.py parses to know which artifacts a release must publish.
    expect(HIDEABLE_TYPES).toContain('privy')
    expect(HIDEABLE_TYPES).toContain('water')
  })
})

describe('DEFAULT_SHOWN_TYPES (#865)', () => {
  it('is exactly shelter, water, campsite and privy', () => {
    expect([...DEFAULT_SHOWN_TYPES].sort()).toEqual(
      ['campsite', 'privy', 'shelter', 'water'].sort(),
    )
  })

  it('only names categories a release actually serves', () => {
    for (const type of DEFAULT_SHOWN_TYPES) expect(HIDEABLE_TYPES).toContain(type)
  })

  it('hides exactly the other five when used as the stored preference', () => {
    // What a fresh install's map actually draws: resupply, crossing, viewpoint,
    // parking and trailhead start off, same as if a hiker had toggled them off
    // by hand.
    const hidden = hiddenTypesFrom(DEFAULT_SHOWN_TYPES)
    expect([...hidden].sort()).toEqual(
      ['crossing', 'parking', 'resupply', 'trailhead', 'viewpoint'].sort(),
    )
  })

  it('leaves a category added after it OFF, which is not what the header used to claim', () => {
    // The behaviour #1197 made observable, pinned so the next category's
    // author meets it here rather than in a bug report. A stored `shown` list
    // predating a category does not contain it, so `hiddenTypesFrom` hides it
    // - the outcome the module header attributed to the REJECTED design.
    //
    // Asserted as the behaviour rather than argued as a defect: whether it
    // should change is #1214, and changing it changes what every existing
    // hiker's map draws.
    const storedBefore = ['shelter', 'water']
    expect(hiddenTypesFrom(storedBefore).has('trailhead')).toBe(true)

    // The one population it does not apply to, and the reason the claim read
    // as true for as long as it did.
    expect(hiddenTypesFrom([]).has('trailhead')).toBe(false)
  })
})
