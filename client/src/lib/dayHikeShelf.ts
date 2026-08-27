// What the day-hike shelf derives: the list split by the only state that
// matters, and the map's trailhead door (#1008).
//
// A saved day hike (#976) had exactly one way back to it - a row on the Plan
// home - and the storyboard's missing-screen frames (D7, D8) are both
// answers to "you planned it at home; here is how you get back to it". This
// module is the pure half of both: no React, no store reads, so the rules
// are testable without rendering anything and cannot drift into a component.
//
// TO-WALK AGAINST WALKED, NOT DATED AGAINST UNDATED. The split reads
// `recorded`, the provenance flag the store already carries, because that is
// the state a hiker at 7am actually sorts by: what can I still walk. Nothing
// in the client sets 'walked' tonight (#982 builds that flow), so the walked
// shelf is usually empty and a screen renders it only when it holds
// something - a header over an empty list is a shelf with a label and no
// answer on it (#805's rule).
//
// ORDERING IS THE STORE'S EXISTING ONE - newest date first, undated last -
// unchanged from the Plan home's `sortedByDate`, which moved here rather
// than growing a second copy. "Soonest planned hike first" would arguably
// serve a planner better; nobody has watched a hiker choose, so this keeps
// the ordering the shipped row already had rather than trading one guess for
// another.

import type { DayHike } from './dayHikes'
import { paceEstimate, type PaceEstimate, type PaceProfile } from './pace'
import type { LonLat } from './trailGraph'
import { metresToMiles } from './trailGraph'

/** The list, split by what a hiker can still do with each entry. */
export interface DayHikeShelf {
  toWalk: DayHike[]
  walked: DayHike[]
}

/** Newest first, undated last - an undated day hike is a plan without a
 *  date, not an error. The Plan home's own ordering, kept on the move. */
export function sortedByDate(dayHikes: readonly DayHike[]): DayHike[] {
  return [...dayHikes].sort((a, b) => {
    if (a.date === null && b.date === null) return 0
    if (a.date === null) return 1
    if (b.date === null) return -1
    return b.date.localeCompare(a.date)
  })
}

export function splitDayHikes(dayHikes: readonly DayHike[]): DayHikeShelf {
  const sorted = sortedByDate(dayHikes)
  return {
    toWalk: sorted.filter((hike) => hike.recorded === 'planned'),
    walked: sorted.filter((hike) => hike.recorded === 'walked'),
  }
}

/**
 * How near "starts here" is, in miles.
 *
 * @unvalidated - a reading of the storyboard, not a measurement. The D8
 * frame lists a hike "0.4 mi away" as still offered, so the door has to
 * reach at least that far; half a mile covers it with margin for a lot
 * across the road and a fix wandering under canopy. The cost of generosity
 * is stated rather than hidden: on a short loop the start can sit inside
 * this radius for much of the walk, so the door lingers mid-hike. What
 * would settle the number is real fixes logged at trailheads against their
 * hikes' saved starts - which needs #982's walked flow to exist first.
 */
export const NEAR_START_MILES = 0.5

/** A saved hike whose start is near the fix, and how far off it is. */
export interface NearbyDayHike {
  hike: DayHike
  /** Straight-line miles from the fix to the hike's first tapped end. */
  miles: number
}

/**
 * Straight-line metres between two WGS84 points, by local equirectangular
 * approximation - the error at trailhead scales (under a mile) is far below
 * what a GPS fix under canopy contributes, so nothing here earns a great
 * circle.
 */
function straightLineMetres(a: LonLat, b: LonLat): number {
  const EARTH_RADIUS_M = 6_371_000
  const toRad = Math.PI / 180
  const midLatRad = ((a.lat + b.lat) / 2) * toRad
  const dLat = (b.lat - a.lat) * toRad
  const dLon = (b.lon - a.lon) * toRad * Math.cos(midLatRad)
  return Math.sqrt(dLat * dLat + dLon * dLon) * EARTH_RADIUS_M
}

/** Straight-line miles from the fix to a hike's first tapped end, or null
 *  for a record with no readable start. */
export function distanceToStartMiles(hike: DayHike, at: LonLat): number | null {
  const start = hike.segments[0]?.[0]
  if (start === undefined) return null
  return metresToMiles(
    straightLineMetres(at, { lon: start.coord[0], lat: start.coord[1] }),
  )
}

/**
 * The saved day hikes whose start is within `NEAR_START_MILES` of the fix,
 * nearest first.
 *
 * Only hikes still to walk: the door offers a walk somebody can set off on,
 * and a walked record is not one. (The door OPENS a hike rather than
 * following it - chrome/DayHikesHere.tsx has the reason, and following a
 * network hike is not built.) The start is the first
 * tapped end of the first segment - for a loop that is also the finish,
 * which is why the door can reappear at the end of a walk; that is true
 * rather than a defect, and the honest fix is the unvalidated radius above,
 * not a second rule.
 *
 * STRAIGHT-LINE, AND THE CALLER MUST SAY SO if it prints the figure: this
 * is distance across the ground to the start, not trail walked - the same
 * distinction planDisplay.ts draws for way-off rows.
 */
export function dayHikesNearHere(
  dayHikes: readonly DayHike[],
  at: LonLat,
): NearbyDayHike[] {
  const near: NearbyDayHike[] = []
  for (const hike of dayHikes) {
    if (hike.recorded !== 'planned') continue
    const miles = distanceToStartMiles(hike, at)
    if (miles !== null && miles <= NEAR_START_MILES) near.push({ hike, miles })
  }
  return near.sort((a, b) => a.miles - b.miles)
}

/**
 * The to-walk shelf by distance to each start, nearest first - the list's
 * "nearest me" sort. Hikes whose start cannot be read sort last rather than
 * vanishing: a record the sort cannot place is still a record.
 */
export function sortedByNearest(dayHikes: readonly DayHike[], at: LonLat): DayHike[] {
  return [...dayHikes].sort((a, b) => {
    const aMiles = distanceToStartMiles(a, at)
    const bMiles = distanceToStartMiles(b, at)
    if (aMiles === null && bMiles === null) return 0
    if (aMiles === null) return 1
    if (bMiles === null) return -1
    return aMiles - bMiles
  })
}

/**
 * A saved walk priced from its CACHE, or null when it cannot be priced.
 *
 * The one way a surface that must not load the routing graph can put a ≈time
 * on a row. Null means exactly one thing here - this record has no climb -
 * and there are two ways to arrive at it, which callers should not try to
 * tell apart: a hike saved before `DayHikeFigures.climb` existed
 * (2026-08-27), and a hike whose graph could not price some edge of it. Both
 * mean the same to a reader: the app has no time to offer for this walk.
 *
 * What it must never do is fall back to distance alone. Naismith without
 * ascent is a flat-ground claim, and on this network the flat-ground answer
 * is short - which is the direction that gets somebody caught by the dark.
 */
export function cachedEstimate(hike: DayHike, pace: PaceProfile): PaceEstimate | null {
  const climb = hike.figures.climb
  if (climb === undefined || climb === null) return null
  return paceEstimate(
    { distanceMi: hike.figures.miles, ascentFt: climb.gainFt, descentFt: climb.lossFt },
    pace,
  )
}

/**
 * The walks that can be priced, shortest first, then the rest in the order
 * they arrived.
 *
 * Unpriceable hikes go last rather than being hidden: this is a sort, and a
 * sort that drops rows is a filter wearing a sort's label.
 */
export function sortedByTime(dayHikes: readonly DayHike[], pace: PaceProfile): DayHike[] {
  return [...dayHikes].sort((a, b) => {
    const aTime = cachedEstimate(a, pace)
    const bTime = cachedEstimate(b, pace)
    if (aTime === null && bTime === null) return 0
    if (aTime === null) return 1
    if (bTime === null) return -1
    return aTime.minutes - bTime.minutes
  })
}

/** A stretch between two segments with no trail under it (#935's deliberate
 *  gap), measured straight-line between the tapped ends that face it. */
export interface DayHikeGap {
  /** The gap follows this segment (0-based). */
  afterSegment: number
  /** Straight-line miles from one segment's last end to the next one's
   *  first. The ground walked is the hiker's own guess - that is what a gap
   *  IS - so nothing rounder than a straight line exists to print. */
  miles: number
}

export function dayHikeGaps(hike: DayHike): DayHikeGap[] {
  const gaps: DayHikeGap[] = []
  for (let at = 0; at + 1 < hike.segments.length; at += 1) {
    const from = hike.segments[at][hike.segments[at].length - 1]
    const to = hike.segments[at + 1][0]
    if (from === undefined || to === undefined) continue
    gaps.push({
      afterSegment: at,
      miles: metresToMiles(
        straightLineMetres(
          { lon: from.coord[0], lat: from.coord[1] },
          { lon: to.coord[0], lat: to.coord[1] },
        ),
      ),
    })
  }
  return gaps
}
