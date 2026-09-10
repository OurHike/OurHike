// Step 1 of the planning spine: "Where do you want to go?" (#1373, the
// design's frame 3e, decisions D2 and D6).
//
// ONE SCREEN, TWO WAYS IN. "Find a hike" and step 1 are one screen: type a
// place, or take a published one, and the same route screen follows either.
// Two screens asking a hiker to declare an intent they already declared by
// tapping Plan was the "same fork asked twice" defect (D2), and the screen
// whose only job was to restate the mode - chrome/PlanKindSheet.tsx, "What
// are you planning?" - is the one the spine is better without (D6). The
// kind of hike is the mode on the bar, printed on the rail's first stop and
// never asked again.
//
// EVERY DOOR ROUTES. There is no "Route it ›" primary under an empty field,
// because a control that cannot do its job is not offered (D10): naming a
// place, "Where I am", "Pick on the map" and "Draw it myself" each open the
// route screen already started, and a published walk opens its own detail.
// Where a day hike cannot be built - no junction graph on this phone yet -
// the doors are replaced by the sentence saying why and the one thing that
// might change it (R5, lib/trailNetworkText.ts), not by greyed buttons.
//
// The one door the retired sheet carried that nothing else did survives at
// the foot: "A walk I've already done", the same builder entered in the past
// tense (#982), offered in day mode where that builder is.

import { StepRail } from '../chrome/StepRail'
import { HikeFinderIcon } from '../chrome/HikeFinderIcon'
import { SuggestedHikeCard } from '../chrome/SuggestedHikeCard'
import { HIKER_MODE_LABELS, type HikerMode } from '../lib/hikerMode'
import type { TrailNetworkState } from '../lib/trailGraphData'
import { canRetryTrailNetwork, trailNetworkRefusal } from '../lib/trailNetworkText'
import {
  timeBucketLabel,
  type HikeFacets,
  type SuggestedHike,
} from '../lib/suggestedHikes'
import { shelfPicks } from '../lib/suggestedHikes'
import type { LonLat } from '../lib/trailGraph'
import type { UnitSystem } from '../lib/units'
import type { PaceProfile } from '../lib/pace'
import './planStart.css'

export interface PlanStartProps {
  /** The mode on the bar - the answer to "which kind of hike", never asked
   *  again here. Volunteer plans as a day hiker. */
  mode: HikerMode
  /** Whether a day hike can be built on this phone (lib/trailGraphData.ts). */
  network: TrailNetworkState
  onRetryNetwork?: () => void
  /** Whether "Where I am" has a fix to start from. Without one the door is
   *  absent, not disabled. */
  hasFix: boolean
  hikes: readonly SuggestedHike[]
  near: LonLat | null
  units: UnitSystem
  pace: PaceProfile
  /** The field: opens the stop search (chrome/RouteStopPicker.tsx). */
  onNamePlace: () => void
  onWhereIAm: () => void
  onPickOnMap: () => void
  /** Day hikes only - the drawn stroke is the day-hike builder's tool. */
  onDraw?: () => void
  onFindHike: (facets?: Partial<HikeFacets>) => void
  onOpenSuggestedHike: (id: string) => void
  /** Day hikes only: the same builder, entered in the past tense (#982). */
  onRecordWalked?: () => void
  onCancel: () => void
}

export function PlanStart({
  mode,
  network,
  onRetryNetwork,
  hasFix,
  hikes,
  near,
  units,
  pace,
  onNamePlace,
  onWhereIAm,
  onPickOnMap,
  onDraw,
  onFindHike,
  onOpenSuggestedHike,
  onRecordWalked,
  onCancel,
}: PlanStartProps) {
  const planMode: 'day' | 'long' = mode === 'long' ? 'long' : 'day'
  const dayRefused = planMode === 'day' && network.kind !== 'ready'
  const picks = shelfPicks(hikes, near)

  return (
    <div className="plan-start">
      <StepRail step={1} kind={HIKER_MODE_LABELS[planMode]} />

      <h1 className="plan-start__title">Where do you want to go?</h1>
      <p className="plan-start__lede">
        Name a place, or take one of these. Either way you land on the same route screen
        next.
      </p>

      <button type="button" className="plan-start__field" onClick={onNamePlace}>
        <HikeFinderIcon name="search" className="plan-start__field-icon" />
        <span className="plan-start__field-text">
          A shelter, a summit, a town, or &ldquo;mi 500&rdquo;
        </span>
      </button>

      {dayRefused ? (
        <div className="plan-kind__door plan-kind__door--unavailable">
          <span className="plan-kind__door-name">Pick on the map, or draw it</span>
          {/* Not a disabled button: a sentence that names what is missing,
              so this reads as a thing the phone has not got yet rather
              than a thing the app cannot do (R5, D10). */}
          <span
            className="plan-kind__door-note plan-kind__door-note--refused"
            role="note"
          >
            {trailNetworkRefusal(network)}
          </span>
          {canRetryTrailNetwork(network) && onRetryNetwork !== undefined && (
            <button type="button" className="plan-kind__retry" onClick={onRetryNetwork}>
              Try again
            </button>
          )}
        </div>
      ) : (
        <div className="plan-start__doors" role="group" aria-label="Start from">
          {hasFix && (
            <button type="button" className="plan-start__door" onClick={onWhereIAm}>
              Where I am
            </button>
          )}
          <button type="button" className="plan-start__door" onClick={onPickOnMap}>
            Pick on the map
          </button>
          {planMode === 'day' && onDraw !== undefined && (
            <button type="button" className="plan-start__door" onClick={onDraw}>
              Draw it myself
            </button>
          )}
        </div>
      )}

      {hikes.length > 0 && (
        <section className="plan-start__published" aria-label="Published hikes">
          <p className="plan-start__or">or start from one of these</p>
          <div className="plan-start__browse">
            <button
              type="button"
              className="plan-start__all"
              onClick={() => onFindHike()}
            >
              {hikes.length} {hikes.length === 1 ? 'hike' : 'hikes'} ›
            </button>
            {/* The finder's own facets, in its own words (lib/suggestedHikes.ts):
                a chip here opens the results with the filter already on. */}
            {hasFix && (
              <button
                type="button"
                className="plan-start__chip"
                onClick={() => onFindHike({ sort: 'nearest' })}
              >
                Near me
              </button>
            )}
            <button
              type="button"
              className="plan-start__chip"
              onClick={() => onFindHike({ time: 'under2' })}
            >
              {timeBucketLabel('under2')}
            </button>
            <button
              type="button"
              className="plan-start__chip"
              onClick={() => onFindHike({ transitOnly: true })}
            >
              No car
            </button>
            <button
              type="button"
              className="plan-start__chip"
              onClick={() => onFindHike({ difficulty: ['easy'] })}
            >
              Easy
            </button>
          </div>
          <div className="plan-start__rail">
            {picks.map((hike) => (
              <SuggestedHikeCard
                key={hike.id}
                hike={hike}
                variant="shelf"
                units={units}
                pace={pace}
                onOpen={onOpenSuggestedHike}
              />
            ))}
          </div>
        </section>
      )}

      {planMode === 'day' && onRecordWalked !== undefined && (
        <button type="button" className="plan-start__walked" onClick={onRecordWalked}>
          <span className="plan-start__walked-name">A walk I&rsquo;ve already done</span>
          <span className="plan-start__walked-note">
            The same two ends, in the past tense — record it ›
          </span>
        </button>
      )}

      <div className="plan-start__foot">
        <button type="button" className="plan-start__cancel" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  )
}
