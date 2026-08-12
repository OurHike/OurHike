import { describe, it, expect } from 'vitest'
import {
  HIDEABLE_TYPES,
  filterSummary,
  hiddenTypesFrom,
  isFiltered,
  onlyType,
  showAllTypes,
  toggleType,
} from './waypointVisibility'
import { NEVER_HIDEABLE } from './legendContents'

// The stored preference is *shown*, the map consumes *hidden* (#530). What is
// worth testing is the translation, the collapse back to "all", and the safety
// rule - which has to be structural rather than a check somebody remembers,
// because the failure it prevents is a map with a closure hidden on it.

describe('hiddenTypesFrom', () => {
  it('hides nothing when the preference is empty', () => {
    // `[]` means ALL, which is what a fresh install has and what it has always
    // meant. Reading it as "show nothing" would open the app to a blank map.
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

describe('filterSummary', () => {
  it('says nothing when nothing is filtered', () => {
    expect(filterSummary([])).toBeNull()
  })

  it('names the one category on a single-type filter', () => {
    // The standing sentence is the price of the filter PERSISTING. It survives a
    // pan on purpose - "where is the next water" is answered by panning along
    // the trail with water alone drawn - so the state has to stay visible or a
    // hiker forgets they set it.
    expect(filterSummary(['water'])).toBe('Showing water only')
  })

  it('counts them when several are shown', () => {
    expect(filterSummary(['water', 'shelter'])).toBe(
      `Showing 2 of ${HIDEABLE_TYPES.length} waypoint types`,
    )
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
