// Which climb the ribbon highlights, and what its callout claims.
//
// lib/elevationGain.ts answers "how much ascent between these two mileposts".
// Picking THE NEXT CLIMB out of a profile is a different question: it needs a
// trough and a peak, not a total. See features/ELEVATION_PROFILE.md for the
// decision this file encodes, including where the 300 ft floor comes from.
//
// Two thresholds live here and they are different quantities, which is worth
// keeping straight. THRESHOLD_FT (from lib/elevationGain.ts, ~9.8 ft) is what
// the DEM can resolve - below it a reversal is measurement error rather than a
// hilltop. MIN_CLIMB_FT is what a hiker cares about. Confusing the two would
// either highlight noise or hide Blood Mountain.

import type { HikeDirection } from '../chrome/Header'
import type { UpcomingClimb } from '../chrome/ElevationRibbon'
import { gainBetween, THRESHOLD_FT, type ProfileSample } from './elevationGain'
import {
  profileSamples,
  type ElevationProfile,
  type MileWindow,
} from './elevationProfile'

/**
 * The smallest ascent worth highlighting.
 *
 * Derived rather than picked. naismithTime() rounds to five-minute steps and
 * Naismith gives one hour per 600 m of ascent, so 164 ft of ascent is exactly
 * one rounding step - below that a climb cannot move the number the callout
 * prints, and the ribbon would highlight a region only to caption it with a
 * time indistinguishable from flat ground. 300 ft clears that floor by most of
 * a step (about nine minutes on top of the walking) and is roughly where a
 * climb becomes a pacing decision. It stays far below anything anyone names:
 * Albert Mountain is ~500 ft, Blood Mountain ~1,400 ft, a Presidential day
 * 3,000-4,000 ft.
 *
 * DELIBERATELY NOT SCALED BY THE HIKER'S OWN PACE (#880)
 *
 * The derivation above is a floor on what can move a PRINTED number, and the
 * hiker's ascent coefficient changes what that floor is: at one hour per 300 m
 * of ascent - the steepest the pace control allows - a rounding step is 82 ft
 * rather than 164, so a smaller climb would qualify.
 *
 * It stays on the standard rule anyway, and the reason is what this constant
 * is for. It decides which climbs are WORTH MENTIONING, not how long any of
 * them takes; the second sentence of the derivation is the load-bearing one -
 * "roughly where a climb becomes a pacing decision" - and that is a fact about
 * the ground rather than about who is walking it. Scaling it would mean two
 * hikers on the same trail get callouts at different hills, which is a worse
 * kind of inconsistency than a threshold that is slightly conservative for the
 * slowest of them.
 *
 * Recorded rather than left silent, because "the threshold did not change" is
 * indistinguishable from "nobody thought about the threshold" six months from
 * now.
 */
export const MIN_CLIMB_FT = 300

interface Candidate {
  troughMile: number
  peakMile: number
}

/** A sample known to have an elevation, so the search below never has to ask
 *  again. Splitting the gaps out first is how cumulativeGainOverGaps() is built
 *  too, and it keeps one shape of "is this a number" check out of the machine. */
interface Point {
  mile: number
  ft: number
}

/** Runs of consecutive measured samples, split at every DEM gap. */
function measuredRuns(samples: ProfileSample[]): Point[][] {
  const runs: Point[][] = []
  let run: Point[] = []

  for (const { distanceMi, elevationFt } of samples) {
    if (elevationFt === null || Number.isNaN(elevationFt)) {
      if (run.length > 0) runs.push(run)
      run = []
    } else {
      run.push({ mile: distanceMi, ft: elevationFt })
    }
  }

  if (run.length > 0) runs.push(run)
  return runs
}

/**
 * Every confirmed trough-to-peak run within one unbroken stretch, in travel
 * order.
 *
 * The same state machine cumulativeGain() uses, and for the same reason: a peak
 * is believed only once the ground has come back down by more than the DEM can
 * invent. What differs is the bookkeeping - this keeps where the trough and the
 * peak were rather than accumulating their difference.
 *
 * That bookkeeping is why the comparisons below are not symmetric. Across a
 * flat stretch the trough moves to its LAST sample and the peak stays at its
 * FIRST, so a mile of level ground before a climb is not counted as part of it.
 * cumulativeGain() can use strict comparisons on both because it only ever
 * needs the difference in elevation, which is the same either way; a highlighted
 * region and a "· 2.6 mi ·" in a callout need the extent to be right too.
 */
function climbsInRun(run: Point[], threshold: number): Candidate[] {
  const climbs: Candidate[] = []
  if (run.length < 2) return climbs

  let low = run[0]
  let high = run[0]
  let rising: boolean | null = null

  for (const point of run.slice(1)) {
    if (rising === true) {
      if (point.ft > high.ft) {
        high = point
      } else if (point.ft <= high.ft - threshold) {
        climbs.push({ troughMile: low.mile, peakMile: high.mile })
        low = point
        rising = false
      }
    } else if (rising === false) {
      if (point.ft <= low.ft) {
        low = point
      } else if (point.ft >= low.ft + threshold) {
        high = point
        rising = true
      }
    } else {
      // Direction not established yet. Both extremes are tracked so that when
      // the ground does break out, the climb is measured from the true trough
      // rather than from wherever the run happened to begin.
      if (point.ft > high.ft) high = point
      if (point.ft <= low.ft) low = point
      if (high.ft - low.ft >= threshold) rising = point.ft >= high.ft
    }
  }

  // A climb still rising when the run ended. Unconfirmed, and kept anyway for
  // the same reason cumulativeGain() keeps one that runs off the end of its
  // window: discarding a real ascent because the measurement stopped is the
  // worse answer.
  if (rising) climbs.push({ troughMile: low.mile, peakMile: high.mile })

  return climbs
}

/**
 * Every confirmed climb in travel order.
 *
 * A DEM gap ends a run rather than being stepped over. Across an unmeasured
 * stretch there is no honest claim about whether a climb continued, so one
 * already rising into the gap is offered at the size it had reached and the
 * search starts again on the far side.
 */
function confirmedClimbs(samples: ProfileSample[], threshold: number): Candidate[] {
  return measuredRuns(samples).flatMap((run) => climbsInRun(run, threshold))
}

/**
 * The next climb of at least MIN_CLIMB_FT within the ribbon's window, or
 * undefined when there is none.
 *
 * Undefined is a real and common answer - rolling ridge with nothing over
 * 300 ft in the next nine miles - and ElevationRibbon draws the profile without
 * a highlight or a callout when it gets one.
 *
 * Undefined is also the answer while `direction` is unknown. The window is
 * centred then (see ribbonWindow), because showing the ground around someone
 * claims nothing about which way they face - but a climb callout is a claim
 * about work they are going to do, and with the direction still unresolved it
 * would be a coin flip.
 *
 * The returned bounds are in ASCENDING mile order, not travel order: they
 * describe the highlighted region's left and right edges, which is what
 * ElevationRibbon positions its rect from. For a southbounder the trough is the
 * higher milepost.
 */
export function upcomingClimb(
  profile: ElevationProfile,
  window: MileWindow,
  atMile: number,
  direction?: HikeDirection,
): UpcomingClimb | undefined {
  if (direction === undefined) return undefined

  const inWindow = profileSamples(profile, window)
  const travelOrder = direction === 'NOBO' ? inWindow : [...inWindow].reverse()
  const isAhead = (mile: number) => (direction === 'NOBO' ? mile > atMile : mile < atMile)

  for (const { troughMile, peakMile } of confirmedClimbs(travelOrder, THRESHOLD_FT)) {
    // A peak already behind is a climb that has been walked, whatever is left
    // of the descent off it.
    if (!isAhead(peakMile)) continue

    // Mid-climb, the trough is behind the hiker. The callout is a claim about
    // work not yet done, so it starts from where they are - printing +640 ft
    // when four hundred of those feet are underfoot would be a promise the
    // profile does not make.
    const start = isAhead(troughMile) ? troughMile : atMile
    const startMile = Math.min(start, peakMile)
    const endMile = Math.max(start, peakMile)

    // Counted with gainBetween() rather than the peak-minus-trough the search
    // already has, so the callout and any total computed elsewhere are the same
    // arithmetic over the same samples. It also stays right after the clamp
    // above, where peak-minus-trough would not be.
    //
    // Handed the TRAVEL-ordered samples, not the window's. gainBetween() picks
    // its range by milepost but counts in array order, and for a southbounder
    // those disagree: the same stretch read south-to-north is the descent off
    // the climb, and counts as no ascent at all.
    const ascentFt = Math.round(gainBetween(travelOrder, startMile, endMile))

    // Re-checked after the clamp: someone ninety percent up a 320 ft climb has
    // thirty feet left, which is below the floor and no longer the thing worth
    // showing them. The search carries on to whatever is past the top.
    if (ascentFt < MIN_CLIMB_FT) continue

    return { startMile, endMile, ascentFt }
  }

  return undefined
}
