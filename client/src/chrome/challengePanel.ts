// The challenge places on the map, owned by one file instead of by App.tsx -
// BRANCHING.md §2's pattern (#327), for #1780 — Let a club publish a
// challenge — places on its own trails that hikers opt into and tag at camp —
// starting with the ATC's A.T. Summer Bucket List (features/CHALLENGES.md,
// frame #1 "Map layer").
//
// The hook returns a `Pick<MapScreenProps, …>` of exactly the four props this
// feature owns, which the shell spreads into `<MapScreen>` as one line, so a
// change here does not reach App.tsx.
//
// WHERE THE SWITCH LIVES. In the hiker's challenge record
// (lib/challengeProgress.ts's `layerShown`), read back every render - not in
// lib/userPreferences.ts beside the drought and blaze switches. A new
// preferences key is a backend schema change as well (the preferences sync
// to the account), and this record is device-only until a sync for it is
// built (features/CHALLENGES.md, "On the phone"). The cost: the switch does
// not follow the hiker to a second phone, the same as everything else they
// have done on a challenge.
//
// WHEN THE ROW IS LISTED AT ALL. Only while a challenge the hiker joined is
// on the chosen trail - the design's own words, "listed only when a joined
// challenge is on the chosen trail". Off that trail the handler is withheld,
// which is the legend's own signal for "no row", and the layer is hidden
// whatever the switch says: a switch that is not on screen must not be the
// reason something is drawn.

import { useMemo } from 'react'
import type { MapScreenProps } from './MapScreen'
import type { Challenge } from '../lib/challenges'
import type { ChallengeState } from '../lib/challengeProgress'
import { challengePinFeatures } from '../map/challengePins'

/** The `MapScreenProps` fields this feature owns. */
export type ChallengeMapProps = Pick<
  MapScreenProps,
  | 'challengePins'
  | 'showChallengePins'
  | 'challengePlacesShown'
  | 'onToggleChallengePlaces'
>

export interface ChallengePanel {
  /** Spread into `<MapScreen>`. */
  mapScreen: ChallengeMapProps
}

export interface ChallengePanelInput {
  /** The challenges this hiker joined (lib/useChallenges.ts's `joined`).
   *  Leaving one takes it out of this list, and its pins with it. */
  joined: readonly Challenge[]
  /** The hiker's record: its tags decide which pins are filled, and its
   *  `layerShown` is the switch. */
  state: ChallengeState
  /** The hiker's local YYYY-MM-DD (lib/passedToday.ts's localDay) - the
   *  clock a mystery place's reveal date is read on. */
  today: string
  /** The trail the app is about, by lib/trails.ts registry id ('AT'), or
   *  null with none taken. Compared with each challenge's own `trail`. */
  chosenTrail: string | null
  /** Flips `layerShown`. Should be stable across renders (useCallback), like
   *  every handler MapScreen takes, or the props below change every render. */
  onToggle: () => void
}

export function useChallengePanel({
  joined,
  state,
  today,
  chosenTrail,
  onToggle,
}: ChallengePanelInput): ChallengePanel {
  const onChosenTrail =
    chosenTrail !== null && joined.some((challenge) => challenge.trail === chosenTrail)

  // Every joined challenge's places, not only the chosen trail's: a place is
  // where it is, and two trails can share ground (the A.T. and the Long Path
  // do in New York). What the chosen trail decides is whether the layer is
  // offered, below - not which of the hiker's places exist.
  const challengePins = useMemo(
    () => challengePinFeatures(joined, state, today),
    [joined, state, today],
  )

  const mapScreen = useMemo<ChallengeMapProps>(
    () => ({
      challengePins,
      showChallengePins: state.layerShown && onChosenTrail,
      challengePlacesShown: state.layerShown,
      onToggleChallengePlaces: onChosenTrail ? onToggle : undefined,
    }),
    [challengePins, state.layerShown, onChosenTrail, onToggle],
  )

  return { mapScreen }
}
