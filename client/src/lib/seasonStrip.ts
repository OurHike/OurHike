// What the season strip at the bottom of Today says (#1964, features/
// CHALLENGES_BLAZE_CARD.md slice 4; the frame is features/design/blaze-card/
// Home.dc.html): how much trail karma, which states it landed in, how many at
// home, and the club's finish line in the club's words. Never a numeral for
// what is missing (features/VOLUNTEERING.md §5 rule 2).
//
// WHICH STATE A MILE IS IN IS MEASURED, AND ALONG A SHARED BORDER IT IS NOT
// SETTLED. The bands below replace StateStrip.dc.html's, which were read off
// a map by eye and put Harpers Ferry (mile 1,026.5) in Maryland and the whole
// NC/TN line - Max Patch, Hot Springs - in Tennessee (review of #2020).
//
// Measured 2026-11-04: slice 5's exporter (#1965, pipeline/
// export_challenge_map.py) intersected UA's published trails.geojson, at
// trail_miles.json's miles, with us-atlas 3.0.1's 1:10m state outlines (the
// Census Bureau's 2017 cartographic boundaries). It found 206 runs of one
// state; runs shorter than 2 mi were folded into the longer neighbour, which
// leaves the 48 below. Where the trail CROSSES a line the bands land within a
// mile of the mock's (Georgia ends at 78.2 against 78.5). Where it FOLLOWS
// one - NC/TN from about mile 176 to 393, VA/WV near 653 and from 1,009 to
// 1,027, NJ/NY from 1,346 to 1,371 - the outline's scale decides which side
// a vertex is on, and a place there can honestly be either state:
// @unvalidated, settled only by a survey-grade boundary. The strip prints
// states and never a count per state for that reason. Slice 5 reads the
// unfolded runs from the published map file and keeps this table as the
// fallback for a phone without it. The ends are widened to mile 0 and to
// 2,198.5, so both termini land in a state.

import type { Challenge } from './challenges'
import { isPlaceItem } from './challenges'
import { isItemDone, itemDoneAt, type ChallengeTag } from './challengeProgress'
import { TRAIL_STATES, type TrailStateCode } from './wherePlace'

/** NOBO mile bands per state, south to north: measured, folded at 2 mi,
 *  and unsettled along a shared border (see above). */
export const STATE_MILE_BANDS: readonly {
  code: TrailStateCode
  from: number
  to: number
}[] = [
  { code: 'GA', from: 0, to: 78.2 },
  { code: 'NC', from: 78.2, to: 183.25 },
  { code: 'TN', from: 183.25, to: 194.43 },
  { code: 'NC', from: 194.43, to: 201.06 },
  { code: 'TN', from: 201.06, to: 204.55 },
  { code: 'NC', from: 204.55, to: 211.28 },
  { code: 'TN', from: 211.28, to: 217.94 },
  { code: 'NC', from: 217.94, to: 223.99 },
  { code: 'TN', from: 223.99, to: 227.14 },
  { code: 'NC', from: 227.14, to: 231.71 },
  { code: 'TN', from: 231.71, to: 235.53 },
  { code: 'NC', from: 235.53, to: 244.8 },
  { code: 'TN', from: 244.8, to: 250.92 },
  { code: 'NC', from: 250.92, to: 288.38 },
  { code: 'TN', from: 288.38, to: 308.99 },
  { code: 'NC', from: 308.99, to: 320.89 },
  { code: 'TN', from: 320.89, to: 324.15 },
  { code: 'NC', from: 324.15, to: 327.09 },
  { code: 'TN', from: 327.09, to: 329.52 },
  { code: 'NC', from: 329.52, to: 335.58 },
  { code: 'TN', from: 335.58, to: 352.28 },
  { code: 'NC', from: 352.28, to: 361.93 },
  { code: 'TN', from: 361.93, to: 364.86 },
  { code: 'NC', from: 364.86, to: 371.91 },
  { code: 'TN', from: 371.91, to: 378.45 },
  { code: 'NC', from: 378.45, to: 382.93 },
  { code: 'TN', from: 382.93, to: 387.08 },
  { code: 'NC', from: 387.08, to: 392.62 },
  { code: 'TN', from: 392.62, to: 467.38 },
  { code: 'VA', from: 467.38, to: 652.74 },
  { code: 'WV', from: 652.74, to: 654.85 },
  { code: 'VA', from: 654.85, to: 1009.36 },
  { code: 'WV', from: 1009.36, to: 1011.74 },
  { code: 'VA', from: 1011.74, to: 1014.97 },
  { code: 'WV', from: 1014.97, to: 1017.52 },
  { code: 'VA', from: 1017.52, to: 1022.51 },
  { code: 'WV', from: 1022.51, to: 1027.2 },
  { code: 'MD', from: 1027.2, to: 1068.25 },
  { code: 'PA', from: 1068.25, to: 1298.4 },
  { code: 'NJ', from: 1298.4, to: 1345.56 },
  { code: 'NY', from: 1345.56, to: 1352.75 },
  { code: 'NJ', from: 1352.75, to: 1370.77 },
  { code: 'NY', from: 1370.77, to: 1461.84 },
  { code: 'CT', from: 1461.84, to: 1514.03 },
  { code: 'MA', from: 1514.03, to: 1604.21 },
  { code: 'VT', from: 1604.21, to: 1755.09 },
  { code: 'NH', from: 1755.09, to: 1915.99 },
  { code: 'ME', from: 1915.99, to: 2198.5 },
]

/** The state a trail mile falls in, by the bands above; null off the
 *  table's ends. */
export function stateAtMile(mile: number): TrailStateCode | null {
  const band = STATE_MILE_BANDS.find((entry) => mile >= entry.from && mile < entry.to)
  return band?.code ?? null
}

export interface SeasonSummary {
  earned: number
  /** States an earned item landed in, south to north, each once. */
  states: TrailStateCode[]
  /** Items earned with no place on the trail: at home, in town, or an
   *  at-home item the hiker did not place. Never an item the walk earned. */
  atHome: number
}

/**
 * Where this hiker's earned items landed: a named place's own mile, else what the
 * hiker said when asked (lib/wherePlace.ts), else - for a `gps` tag - on the
 * trail, else "at home".
 *
 * A `gps` tag was earned by the walk, so it is never "at home" (review of
 * #2020: a camp-card shelter, a height and a workday all read as at home).
 * A section walked lands at its middle mile. "Any shelter", a height and a
 * workday land in no named state: tag() keeps `poi` only for a Triple
 * Crown, and the tag carries no mile, so the state they were earned in is
 * not on the phone to read - counted, and not guessed.
 */
export function seasonSummary(
  challenge: Challenge,
  tags: readonly ChallengeTag[],
): SeasonSummary {
  const states = new Set<TrailStateCode>()
  let earned = 0
  let atHome = 0
  for (const item of challenge.items) {
    if (!isItemDone(item, challenge.id, tags)) continue
    earned += 1
    const tag = itemDoneAt(item, challenge.id, tags)
    let state: TrailStateCode | null = null
    let placed = false
    if (isPlaceItem(item)) {
      const place =
        item.match.places.find((candidate) => candidate.poi === tag?.poi) ??
        item.match.places[item.match.places.length - 1]
      state = stateAtMile(place.mile)
      placed = true
    } else if (tag?.place !== undefined) {
      switch (tag.place.kind) {
        case 'here':
          state = stateAtMile(tag.place.mile)
          placed = true
          break
        case 'walked':
          state = stateAtMile((tag.place.fromMile + tag.place.toMile) / 2)
          placed = true
          break
        case 'poi':
          state = tag.place.mile === null ? null : stateAtMile(tag.place.mile)
          placed = true
          break
        case 'state':
          state = tag.place.state
          placed = true
          break
        case 'off':
          placed = false
          break
      }
    } else if (tag?.how === 'gps') {
      placed = true
      if (item.match.kind === 'section_walked')
        state = stateAtMile((item.match.fromMile + item.match.toMile) / 2)
    }
    if (!placed) atHome += 1
    if (state !== null) states.add(state)
  }
  const order = TRAIL_STATES.map((entry) => entry.code)
  return {
    earned,
    states: [...states].sort((a, b) => order.indexOf(a) - order.indexOf(b)),
    atHome,
  }
}

/** "summer" for a window that sits in June to September, else the season
 *  its middle falls in, else "season" - the strip's eyebrow word. A window
 *  across the new year (Nov 15 - Feb 28) is winter, not the average of 11
 *  and 2; a window of a whole year or more is no one season (review of
 *  #2020: all three read "summer"). */
export function seasonWord(window: {
  opens: string | null
  closes: string | null
}): string {
  // Months counted from year 0, with the day as a fraction, so a window that
  // closes in a later year is later and its middle is in the right month.
  const months = (day: string | null) =>
    day === null
      ? null
      : Number(day.slice(0, 4)) * 12 +
        Number(day.slice(5, 7)) -
        1 +
        (Number(day.slice(8, 10)) - 1) / 31
  const opens = months(window.opens)
  const closes = months(window.closes)
  if (opens !== null && closes !== null && closes - opens >= 11) return 'season'
  const mid = opens !== null && closes !== null ? (opens + closes) / 2 : (opens ?? closes)
  if (mid === null || Number.isNaN(mid)) return 'season'
  // Back to a month of the year, January 1 to December 12.99.
  const middle = (((mid % 12) + 12) % 12) + 1
  if (middle >= 5.5 && middle <= 9) return 'summer'
  if (middle > 9 && middle <= 11.5) return 'autumn'
  if (middle >= 2.5 && middle < 5.5) return 'spring'
  return 'winter'
}
