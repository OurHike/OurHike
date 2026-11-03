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
//   - A TURN ROW is one of the hiker's own taps, and it IS deletable - the
//     design's per-row delete, which `removeTap` exists for. It carries the
//     mile it sits at and the number the map draws beside it.
//
// The gap between stretches is a row, because it is a real thing the walk
// contains and the one thing in it the app declines to describe.
//
// WHY THE TAPS MOVED INTO THIS LIST (2026-09-15)
//
// They were listed apart until then, under "Your taps", and the reason was
// arithmetic rather than design: `routeThrough` merged legs across tap joins,
// so the walk knew the mile at the end of a LEG and not the mile at a tap
// inside one, and a row with no mile in a mile-ordered list is a row in the
// wrong place.
//
// The maintainer's rule ended that. A tap is a leg boundary now - a point a
// hiker placed is not a seam a publisher drew - so its mile is exactly
// `toMile` of the row above it, which this function is computing anyway.
//
// AND THE SAME RULE IS WHY THEY HAD TO MOVE, not merely why they could. Two
// consecutive rows naming one trail and one blaze are legal now, and the ONLY
// thing that distinguishes them is the tap between them. Listed apart, that
// tap is off-screen from the two rows it explains, and the list reads as the
// duplicate rows #1433 was about. In the list, it reads as the walk.

import type { RouteLeg } from './trailGraph'
import type { DayHikeStop } from './dayHikeStops'
import type { DayHikeDraft, DraftGap, DraftTurn } from './dayHikeDraft'
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

/** One of the hiker's own taps, in the list where they placed it. */
export interface TurnRow {
  kind: 'turn'
  key: string
  /** Index into `draftPoints(draft)` - what `removeTap` takes. */
  ordinal: number
  /** 1-based, matching the numbered mark this tap wears on the map. */
  label: number
  /** Miles from the first step of the walk to this tap. */
  mile: number
  /** Whether a gap starts after this tap. */
  endsStretch: boolean
}

export type RouteRow = LegRow | StopRow | GapRow | TurnRow

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
 *
 * AND SO DOES A GAP, for the same reason and one that matters more. `gaps` is
 * `DraftStatus.gaps`; each one goes after the last leg before it and after
 * that leg's stops, because crossing it is the next thing that happens. A gap
 * is ground nobody maintains and nobody has walked for us, so a list that
 * omitted it would read as one continuous routed walk and understate what the
 * hiker is actually taking on.
 */
export function routeRows(
  legs: readonly RouteLeg[],
  stops: readonly DayHikeStop[],
  gaps: readonly DraftGap[] = [],
  turns: readonly DraftTurn[] = [],
): RouteRow[] {
  const rows: RouteRow[] = []
  let mile = 0
  let placed = 0
  let crossed = 0
  let tapped = 0

  /** Every tap the walk reaches by the time `walked` legs are behind it.
   *
   *  AFTER the leg's stops and BEFORE its gap, which is the order a hiker
   *  reads: you walk the trail, you are at the shelter on it, you are at the
   *  point you placed, and then you cross the ground nobody maintains. */
  const tapsThrough = (walked: number) => {
    while (tapped < turns.length && turns[tapped].afterLegs <= walked) {
      rows.push({
        kind: 'turn',
        // The ordinal repeats on a walk that passes one tap twice - an
        // out-and-back, a loop - so the position is in the key as well.
        key: `turn-${tapped}-${turns[tapped].ordinal}`,
        ordinal: turns[tapped].ordinal,
        label: turns[tapped].label,
        mile,
        endsStretch: turns[tapped].endsStretch,
      })
      tapped += 1
    }
  }

  /** Every gap the walk reaches by the time `walked` legs are behind it. */
  const gapsThrough = (walked: number) => {
    while (crossed < gaps.length && gaps[crossed].afterLegs <= walked) {
      rows.push({ kind: 'gap', key: `gap-${crossed}`, miles: gaps[crossed].miles })
      crossed += 1
    }
  }

  // Where the walk starts, before the first row of trail.
  tapsThrough(0)

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
    tapsThrough(at + 1)
    gapsThrough(at + 1)
  })

  // No legs at all and stops chosen anyway: they still list, because a hiker
  // who tapped a shelter should see it acknowledged rather than swallowed.
  while (placed < stops.length) {
    rows.push({ kind: 'stop', key: `stop-${stops[placed].poiId}`, stop: stops[placed] })
    placed += 1
  }

  // Anything left: a gap the hiker has tapped across but not yet walked any
  // trail beyond, and - defensively - a gap positioned past the legs it was
  // measured against, which lists last rather than silently vanishing.
  tapsThrough(Number.POSITIVE_INFINITY)
  gapsThrough(Number.POSITIVE_INFINITY)

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
 * The hiker's taps, read straight off the draft.
 *
 * FOR THE WALK THAT HAS NOT ROUTED YET, which is the one case
 * `DraftStatus.turns` cannot cover: a draft with one tap is `started` rather
 * than `routed`, so there are no legs to place a tap against - and somebody
 * who has placed exactly one point still has to be able to take it back.
 * Everything else reads the placed turns, which carry a mile.
 *
 * Numbered to match `dayHikeDrawing`'s point labels exactly - App.tsx numbers
 * those across the whole walk, gaps included, so these do too. A hiker
 * looking at "3" on the map and "3" in the panel is looking at one tap, and
 * that correspondence is the only thing making a delete control
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
