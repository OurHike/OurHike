import { describe, it, expect, afterEach } from 'vitest'
import { act, cleanup, renderHook } from '@testing-library/react'
import { useWaypointFiltersPanel, type UpdatePreferences } from './waypointFiltersPanel'
import { DEFAULT_PREFERENCES, type UserPreferences } from '../lib/userPreferences'

// #327 moved the legend's filters out of App.tsx. What is tested here is the
// contract with the shell's preference writer - which of the three filters
// persists, and that the two toggles read the CURRENT value rather than a
// captured one. The visibility rules themselves are lib/waypointVisibility.ts's
// and are tested there.

/**
 * A stand-in for the shell's `updatePreferences`, holding the preferences the
 * way the real one does: a functional patch is applied to whatever is stored
 * NOW, not to what the caller last saw.
 */
function shell(initial: UserPreferences = DEFAULT_PREFERENCES) {
  let stored = initial
  const update: UpdatePreferences = (patch) => {
    stored = { ...stored, ...(typeof patch === 'function' ? patch(stored) : patch) }
  }
  return {
    update,
    get current() {
      return stored
    },
  }
}

function panel(store = shell()) {
  const view = renderHook(
    ({ preferences }: { preferences: UserPreferences }) =>
      useWaypointFiltersPanel({
        preferences,
        updatePreferences: store.update,
        drought: [],
        droughtWeek: null,
      }),
    { initialProps: { preferences: store.current } },
  )
  /** Re-render with whatever the store now holds, which is what the shell's
   *  own `setPreferences` would have caused. */
  const settle = () => view.rerender({ preferences: store.current })
  return { ...view, store, settle }
}

afterEach(cleanup)

describe('useWaypointFiltersPanel', () => {
  it('hides a category through the stored preference, not a local state', () => {
    // #530's bug in one assertion: the toggle has to reach the preferences
    // object, because that is the only thing that survives a relaunch and the
    // only thing an account carries.
    const { result, store, settle } = panel()

    act(() => result.current.mapScreen.onToggleType?.('privy'))
    settle()

    expect(store.current.waypoint_types_shown).not.toContain('privy')
    expect(result.current.hiddenTypes.has('privy')).toBe(true)
    expect(result.current.mapScreen.hiddenTypes?.has('privy')).toBe(true)
  })

  it('gives the legend and the caller the same hidden set', () => {
    // Two readers, one derivation. A second `hiddenTypesFrom` anywhere is the
    // duplicate this file exists to make impossible.
    const { result } = panel()

    expect(result.current.mapScreen.hiddenTypes).toBe(result.current.hiddenTypes)
  })

  it('narrows to one category and finds the way back', () => {
    const { result, store, settle } = panel()

    act(() => result.current.mapScreen.onOnlyType?.('water'))
    settle()
    expect(store.current.waypoint_types_shown).toEqual(['water'])

    act(() => result.current.mapScreen.onShowAllTypes?.())
    settle()
    // "Show all" is what makes persisting the filter honest: a hiker who
    // narrowed to water three weeks ago must be able to get everything back.
    expect(result.current.hiddenTypes.size).toBe(0)
  })

  it('does not lose a second toggle landing on the same render', () => {
    // The reason both toggles take the function form. Two taps inside one
    // render - a fast double-tap, or two categories at once - used to be able
    // to compute both patches from the same captured value, so the second
    // overwrote the first.
    const { result, store, settle } = panel()

    act(() => {
      result.current.mapScreen.onToggleType?.('privy')
      result.current.mapScreen.onToggleType?.('water')
    })
    settle()

    expect(result.current.hiddenTypes.has('privy')).toBe(true)
    expect(result.current.hiddenTypes.has('water')).toBe(true)
    expect(store.current.waypoint_types_shown).not.toContain('privy')
    expect(store.current.waypoint_types_shown).not.toContain('water')
  })

  it('flips the drought tint through the same writer', () => {
    const { result, store, settle } = panel()
    const before = store.current.drought_layer_shown

    act(() => result.current.mapScreen.onToggleDrought?.())
    settle()

    expect(store.current.drought_layer_shown).toBe(!before)
    expect(result.current.mapScreen.droughtShown).toBe(!before)
  })

  it('leaves the verified filter off, and does not persist it', () => {
    // Off by default: an unconfirmed spring is still the best information
    // anyone has about that spring. Ephemeral on purpose - that is #530's
    // problem, and moving this file did not settle it.
    const { result, store } = panel()

    expect(result.current.mapScreen.verifiedOnly).toBe(false)

    act(() => result.current.mapScreen.onToggleVerifiedOnly?.())

    expect(result.current.mapScreen.verifiedOnly).toBe(true)
    expect(store.current).toEqual(DEFAULT_PREFERENCES)
  })
})
