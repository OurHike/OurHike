// The route order: what the builder's panel lists while a hiker builds (#1194).
//
// The design handoff's left rail has one scrolling list - numbered trail rows
// with a blaze chip, and stop rows folded in where the walk reaches them.
// This builds that list. No React, for lib/dayHikeDraft.ts's reason.
//
// WHAT A ROW IS, AND WHY TWO OF THE DESIGN'S FOUR ARE NOT HERE
//
// The handoff's model is `selectedSegmentIds: string[]` - the hiker picks
// segments off a graph and the list IS the state, so every row is deletable
// by definition. This app's model is the other way round (#928): the hiker
// taps PLACES and the router decides which trails join them, so a leg is
// derived. That difference decides what a row can honestly offer.
//
//   - A LEG ROW is read-only, and that is not an omission. "Delete this leg"
//     has no defined meaning when the leg was never chosen - the router
//     produced it from two taps, and removing it would leave a walk with a
//     hole the router would immediately fill back in. A delete control that
//     silently did nothing, or did something else, is worse than no control.
//   - A TURN (one of the hiker's taps) IS deletable - that is genuinely the
//     design's per-row delete, and `removeTap` is new for it - but it does
//     not appear in this list. It has no honest mile: `routeThrough` merges
//     legs across tap joins, so the walk knows how far it is to the end of a
//     LEG and does not, without re-routing every pair on every render, know
//     how far it is to a tap in the middle of one. A row printing "mile 1.8"
//     next to a number nobody computed is exactly what CLAUDE.md's standard
//     is about, and a row in a mile-ordered list with no mile is a row in the
//     wrong place. So turns are listed apart, as {@link turnMarks}, where
//     ordinal is the only claim made and it is one the draft can back.
//
// The gap between stretches is a row, because it is a real thing the walk
// contains and the one thing in it the app declines to describe.

import type { RouteLeg } from './trailGraph'
import type { DayHikeStop } from './dayHikeStops'
import type { DayHikeDraft } from './dayHikeDraft'
import { draftPoints } from './dayHikeDraft'

export interface LegRow {
  kind: 'leg'
  key: string
  /** 1-based, continuous across the whole walk - the design's `01`-`NN`. */
  index: number
  name: string | null
  /** The trail's blaze, for the chip. Null where nobody published one. */
  blazeColor: string | null
  source: string | null
  miles: number
  fromMile: number
  toMile: number
}

export interface StopRow {
  kind: 'stop'
  key: string
  stop: DayHikeStop
}

export interface GapRow {
  kind: 'gap'
  key: string
  miles: number
}

export type RouteRow = LegRow | StopRow | GapRow

/**
 * The legs and stops of a walk, in the order it reaches them.
 *
 * `legs` must be `DraftStatus.legs` - the flat concatenation in walking order
 * - and `stops` must already be ordered by {@link orderStops}. Both ride the
 * same local mile axis (lib/dayHikeCourse.ts), which is what lets them
 * interleave at all.
 *
 * A STOP GOES AFTER THE LEG IT SITS ON, not before it. A hiker reads the list
 * as a sequence of things that happen: you walk the Ramapo-Dunderberg for
 * 0.9 mi, THEN you are at the shelter. Ties - a stop at exactly a leg
 * boundary - resolve the same way, so a shelter at a junction reads as the
 * end of the leg that reached it rather than the start of the one leaving.
 */
export function routeRows(
  legs: readonly RouteLeg[],
  stops: readonly DayHikeStop[],
): RouteRow[] {
  const rows: RouteRow[] = []
  let mile = 0
  let placed = 0

  legs.forEach((leg, at) => {
    const fromMile = mile
    mile += leg.miles
    rows.push({
      kind: 'leg',
      key: `leg-${at}`,
      index: at + 1,
      name: leg.name,
      blazeColor: leg.blaze_color,
      source: leg.source,
      miles: leg.miles,
      fromMile,
      toMile: mile,
    })
    // Every stop this leg reached. The last leg sweeps up anything past its
    // end too - a stop projected a hair beyond the final vertex by the
    // vertex-nearest approximation must not fall out of the list.
    const last = at === legs.length - 1
    while (placed < stops.length && (last || stops[placed].mile <= mile)) {
      rows.push({
        kind: 'stop',
        key: `stop-${stops[placed].poiId}`,
        stop: stops[placed],
      })
      placed += 1
    }
  })

  // No legs at all and stops chosen anyway: they still list, because a hiker
  // who tapped a shelter should see it acknowledged rather than swallowed.
  while (placed < stops.length) {
    rows.push({ kind: 'stop', key: `stop-${stops[placed].poiId}`, stop: stops[placed] })
    placed += 1
  }

  return rows
}

/** A tap of the walk, as the list of removable turns shows it. */
export interface TurnMark {
  /** Index into `draftPoints(draft)` - what `removeTap` takes. */
  ordinal: number
  /** 1-based, matching the numbered mark this tap wears on the map. */
  label: number
  /** Whether a gap starts after this tap (it ends a stretch that is not the last). */
  endsStretch: boolean
}

/**
 * The hiker's taps, as removable marks.
 *
 * Numbered to match `dayHikeDrawing`'s point labels exactly - App.tsx numbers
 * those across the whole walk, gaps included, so these do too. A hiker
 * looking at "3" on the map and "3" in the panel is looking at one tap, and
 * that correspondence is the only thing making a delete control here
 * comprehensible at all.
 */
export function turnMarks(draft: DayHikeDraft): TurnMark[] {
  const marks: TurnMark[] = []
  let ordinal = 0
  draft.segments.forEach((stretch, at) => {
    const lastStretch = at === draft.segments.length - 1
    stretch.forEach((_point, index) => {
      marks.push({
        ordinal,
        label: ordinal + 1,
        endsStretch: !lastStretch && index === stretch.length - 1,
      })
      ordinal += 1
    })
  })
  return marks
}

/** How many taps the walk has - `turnMarks(draft).length` without the array. */
export function turnCount(draft: DayHikeDraft): number {
  return draftPoints(draft).length
}
