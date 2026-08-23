// The legend's filters, owned by one file instead of by App.tsx (#327).
//
// Which waypoint categories are drawn, whether unconfirmed places are drawn
// at all, and whether the drought tint is on. Three questions a hiker answers
// in the legend, and the only three things on this screen that decide what
// the map leaves OUT - which is why they moved together.
//
// See chrome/atcNoticesPanel.tsx for why the hook returns a
// `Pick<MapScreenProps, …>` the shell spreads.
//
// Nothing here holds a preference. Two of the three ARE preferences and are
// read back out of the stored object every render (#530: the category toggles
// were once a `useState`, so hiding privies lasted until the next launch and
// never reached an account). The third, `verifiedOnly`, is deliberately still
// ephemeral - it is #530's problem too, not this file's, and moving it did
// not change that.

import { useCallback, useMemo, useState } from 'react'
import type { MapScreenProps } from './MapScreen'
import type { UserPreferences } from '../lib/userPreferences'
import {
  hiddenTypesFrom,
  onlyType,
  showAllTypes,
  toggleType,
} from '../lib/waypointVisibility'
import type { DroughtBand } from '../map/droughtLayers'

/** The `MapScreenProps` fields this feature owns. See atcNoticesPanel.tsx. */
export type WaypointFiltersMapProps = Pick<
  MapScreenProps,
  | 'hiddenTypes'
  | 'onToggleType'
  | 'onOnlyType'
  | 'onShowAllTypes'
  | 'typesShown'
  | 'verifiedOnly'
  | 'onToggleVerifiedOnly'
  | 'drought'
  | 'droughtShown'
  | 'onToggleDrought'
  | 'droughtWeek'
>

export interface WaypointFiltersPanel {
  /** Spread into `<MapScreen>`. */
  mapScreen: WaypointFiltersMapProps
  /**
   * The same "which categories are hidden" set the legend gets.
   *
   * Returned as well as passed, because the map's own POI filtering will want
   * it the moment anything but the legend reads it - and a second derivation
   * from `waypoint_types_shown` is exactly the duplicate this extraction is
   * meant to make impossible.
   */
  hiddenTypes: ReadonlySet<string>
}

/**
 * The shell's preference writer, in the two shapes it accepts.
 *
 * The function form is what a toggle needs: it reads the current value
 * INSIDE the update rather than closing over a render's copy, so a fast
 * double-tap cannot land two flips on one stale value.
 */
export type UpdatePreferences = (
  patch:
    Partial<UserPreferences> | ((current: UserPreferences) => Partial<UserPreferences>),
) => void

export interface WaypointFiltersInput {
  preferences: UserPreferences
  updatePreferences: UpdatePreferences
  /** The drought bands as published, straight through to the map. */
  drought: readonly DroughtBand[]
  /** The week those bands describe, or null. */
  droughtWeek: { start: Date; end: Date } | null
}

export function useWaypointFiltersPanel({
  preferences,
  updatePreferences,
  drought,
  droughtWeek,
}: WaypointFiltersInput): WaypointFiltersPanel {
  // Derived from the STORED preference rather than held in a `useState` (#530).
  // `waypoint_types_shown` had been declared in the preferences model, in the
  // backend schema and in IDENTITY_AND_PRIVACY.md's canonical model since long
  // before this control, and was read by nothing - so hiding privies lasted
  // until the next reload and never reached an account.
  const hiddenTypes = useMemo(
    () => hiddenTypesFrom(preferences.waypoint_types_shown),
    [preferences.waypoint_types_shown],
  )

  // The legend's "Verified?" filter. Off by default: an unconfirmed spring is
  // still the best information anyone has about that spring, and a first run
  // that quietly withheld it would be the app deciding for a hiker what they
  // are allowed to know about. Ephemeral, exactly like hiddenTypes was before
  // #530 - and still #530's problem rather than this file's.
  const [verifiedOnly, setVerifiedOnly] = useState(false)

  // Through the same `updatePreferences` path every other map preference uses,
  // so this one persists and syncs like the rest of them rather than being the
  // one control that forgets (#530).
  const handleToggleType = useCallback(
    (type: string) => {
      updatePreferences((current) => ({
        waypoint_types_shown: toggleType(current.waypoint_types_shown, type),
      }))
    },
    [updatePreferences],
  )

  /** One tap to show a single category - the control #530 is worth building
   *  for. At a crowded zoom it is the difference between four water pins drawn
   *  and forty, and it answers "where is the next water" in two taps rather
   *  than by zooming in and panning along the trail. */
  const handleOnlyType = useCallback(
    (type: string) => updatePreferences({ waypoint_types_shown: onlyType(type) }),
    [updatePreferences],
  )

  /** The way out, which is what makes persisting the filter honest. */
  const handleShowAllTypes = useCallback(
    () => updatePreferences({ waypoint_types_shown: showAllTypes() }),
    [updatePreferences],
  )

  const handleToggleVerifiedOnly = useCallback(() => {
    setVerifiedOnly((current) => !current)
  }, [])

  /**
   * The drought tint, on or off.
   *
   * A stored preference rather than a `useState`, and that is the whole
   * point: `hiddenTypes` learned this lesson the hard way (#530). A
   * background tint somebody turned off should stay off.
   */
  const handleToggleDrought = useCallback(() => {
    updatePreferences((current) => ({
      drought_layer_shown: !current.drought_layer_shown,
    }))
  }, [updatePreferences])

  const mapScreen = useMemo<WaypointFiltersMapProps>(
    () => ({
      hiddenTypes,
      onToggleType: handleToggleType,
      onOnlyType: handleOnlyType,
      onShowAllTypes: handleShowAllTypes,
      typesShown: preferences.waypoint_types_shown,
      verifiedOnly,
      onToggleVerifiedOnly: handleToggleVerifiedOnly,
      drought,
      droughtShown: preferences.drought_layer_shown,
      onToggleDrought: handleToggleDrought,
      droughtWeek,
    }),
    [
      hiddenTypes,
      handleToggleType,
      handleOnlyType,
      handleShowAllTypes,
      preferences.waypoint_types_shown,
      preferences.drought_layer_shown,
      verifiedOnly,
      handleToggleVerifiedOnly,
      drought,
      handleToggleDrought,
      droughtWeek,
    ],
  )

  return { mapScreen, hiddenTypes }
}
