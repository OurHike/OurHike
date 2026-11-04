// What the season strip at the bottom of Today says (#1964, features/
// CHALLENGES_BLAZE_CARD.md slice 4; the frame is features/design/blaze-card/
// Home.dc.html): how much trail karma, which states it landed in, how many at
// home, and the club's finish line in the club's words. Never a numeral for
// what is missing (features/VOLUNTEERING.md §5 rule 2).
//
// WHICH STATE A MILE IS IN IS A GUESS HERE. The bands below are
// StateStrip.dc.html's, read off a map by eye - @unvalidated, and the brief
// says so: what settles them is the pipeline intersecting the published
// centerline with the state outlines (slice 5), which will emit the real
// boundaries beside challenges.json and replace this table. Slice 5 (#1965)
// does: challenge_map.json's state runs are measured against the published
// centerline, and a caller holding the map passes lib/challengeMap.ts's
// lookup as `stateOf`. These bands remain only for a phone with no map yet,
// where an item within a few miles of a state line may be told in the wrong
// state - which is why the strip prints states and never a count per state.

import type { Challenge, ChallengeItem } from './challenges'
import { isPlaceItem } from './challenges'
import { isItemDone, itemDoneAt, type ChallengeTag } from './challengeProgress'
import { TRAIL_STATES, type TrailStateCode } from './wherePlace'

/** NOBO mile bands per state, south to north. @unvalidated (see above). */
export const STATE_MILE_BANDS: readonly {
  code: TrailStateCode
  from: number
  to: number
}[] = [
  { code: 'GA', from: 0, to: 78.5 },
  { code: 'NC', from: 78.5, to: 165 },
  { code: 'TN', from: 165, to: 467 },
  { code: 'VA', from: 467, to: 1021 },
  { code: 'WV', from: 1021, to: 1025 },
  { code: 'MD', from: 1025, to: 1066 },
  { code: 'PA', from: 1066, to: 1295 },
  { code: 'NJ', from: 1295, to: 1367 },
  { code: 'NY', from: 1367, to: 1457 },
  { code: 'CT', from: 1457, to: 1508 },
  { code: 'MA', from: 1508, to: 1599 },
  { code: 'VT', from: 1599, to: 1749 },
  { code: 'NH', from: 1749, to: 1910 },
  { code: 'ME', from: 1910, to: 2198.5 },
]

/** The state a trail mile falls in, by the approximate bands; null off the
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
   *  at-home item the hiker did not place. */
  atHome: number
}

/** Which state a trail mile is in. The map's published runs
 *  (lib/challengeMap.ts `stateAtMile`) where the phone holds them; the
 *  approximate bands above otherwise. */
export type StateOfMile = (mile: number) => TrailStateCode | null

/** One earned item and where it landed. */
export interface EarnedPlace {
  item: ChallengeItem
  tag: ChallengeTag
  /** The trail mile it happened at, when anything says: a named place's
   *  own, the fix's, the middle of the walked day's extent, a picked
   *  place's. Null for "somewhere in a state", at home, or not said. */
  mile: number | null
  state: TrailStateCode | null
  /** On the trail at all - false for at home, "Not on the trail", and an
   *  at-home item nobody was asked to place. */
  onTrail: boolean
  /** The place's own name, when one is known. */
  placeName: string | null
}

/**
 * Where each of this hiker's earned items landed, in the club's order: a
 * named place's own mile, else what the hiker said when asked
 * (lib/wherePlace.ts), else "at home". A `gps` tag on "any shelter" carries
 * the shelter's place in `poi`, read the same way.
 */
export function earnedPlaces(
  challenge: Challenge,
  tags: readonly ChallengeTag[],
  stateOf: StateOfMile = stateAtMile,
): EarnedPlace[] {
  const out: EarnedPlace[] = []
  for (const item of challenge.items) {
    const tag = itemDoneAt(item, challenge.id, tags)
    if (tag === null || !isItemDone(item, challenge.id, tags)) continue
    let mile: number | null = null
    let state: TrailStateCode | null = null
    let onTrail = false
    let placeName: string | null = null
    if (isPlaceItem(item)) {
      const place =
        item.match.places.find((candidate) => candidate.poi === tag.poi) ??
        item.match.places[item.match.places.length - 1]
      mile = place.mile
      placeName = place.name
      onTrail = true
    } else if (tag.place !== undefined) {
      switch (tag.place.kind) {
        case 'here':
          mile = tag.place.mile
          onTrail = true
          break
        case 'walked':
          mile = (tag.place.fromMile + tag.place.toMile) / 2
          onTrail = true
          break
        case 'poi':
          mile = tag.place.mile
          placeName = tag.place.name
          onTrail = true
          break
        case 'state':
          state = tag.place.state
          onTrail = true
          break
        case 'off':
          break
      }
    }
    if (mile !== null) state = stateOf(mile)
    out.push({ item, tag, mile, state, onTrail, placeName })
  }
  return out
}

export function seasonSummary(
  challenge: Challenge,
  tags: readonly ChallengeTag[],
  stateOf: StateOfMile = stateAtMile,
): SeasonSummary {
  const places = earnedPlaces(challenge, tags, stateOf)
  const states = new Set<TrailStateCode>()
  for (const place of places) if (place.state !== null) states.add(place.state)
  const order = TRAIL_STATES.map((entry) => entry.code)
  return {
    earned: places.length,
    states: [...states].sort((a, b) => order.indexOf(a) - order.indexOf(b)),
    atHome: places.filter((place) => !place.onTrail).length,
  }
}

/** "summer" for a window that sits in June to September, else the season
 *  most of the window falls in, else "season" - the strip's eyebrow word. */
export function seasonWord(window: {
  opens: string | null
  closes: string | null
}): string {
  const month = (day: string | null) => (day === null ? null : Number(day.slice(5, 7)))
  const opens = month(window.opens)
  const closes = month(window.closes)
  const middle =
    opens !== null && closes !== null ? (opens + closes) / 2 : (opens ?? closes)
  if (middle === null || Number.isNaN(middle)) return 'season'
  if (middle >= 5.5 && middle <= 9) return 'summer'
  if (middle > 9 && middle <= 11.5) return 'autumn'
  if (middle >= 2.5 && middle < 5.5) return 'spring'
  return 'winter'
}
