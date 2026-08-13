// The sentence naming the parts around a site's anchor - "Nearby: a multi-seat
// moldering privy 130 ft away, a group campsite 82 ft and water 295 ft."
//
// WRITTEN HERE BECAUSE THE UNIT IS A QUESTION ONLY THE PHONE CAN ANSWER (#625).
// The pipeline composed this whole sentence until a hiker who had chosen Feet
// in Settings read metres off it, on the one card in the app that could not
// answer them. Published prose cannot ask anybody anything: it was written into
// the artifact months before that hiker opened the card, and the only way to
// change a word of it was to re-export the corridor.
//
// So the split is drawn at the unit. `pipeline/lib/poi_description.py` still
// composes the noun phrases - "a multi-seat moldering privy", "a group
// campsite" - because those are ATC's inventory columns read aloud and nothing
// about them depends on the reader, and porting that here would buy a second
// implementation of the same wording in a second language. What crossed is the
// punctuation holding the numbers: the lead word, the list, the single carried
// "away", and the distance itself through lib/units.ts.
//
// THE ORDER IS THE PIPELINE'S AND IS NOT RE-DERIVED. Parts arrive ranked by
// NEARBY_ORDER (privy, water, campsite) and then by distance, which is the same
// order map/poiSites.ts's SITE_MEMBER_TYPES gives the pin's footer glyphs and
// the card's chips. Sorting them again here would be a second opinion about
// which part comes first, and a hiker would read the disagreement as three
// different answers about one site.

import { formatShortDistance, type UnitSystem } from './units'

/**
 * One part of a site as the artifact publishes it (export_poi.py's `nearby`).
 *
 * `distance_ft` in the artifact's own snake_case rather than renamed on the
 * way in: this is the published shape, and a field that reads differently in
 * two places is a field somebody has to check the mapping of. Feet because that
 * is the unit the source states - ATC's water distance is feet, and a member's
 * metres are converted once at the export boundary - and because it is what
 * lib/units.ts formats from.
 */
export interface NearbyPart {
  phrase: string
  distance_ft: number
}

/** The word the parts are introduced with. One label rather than "away" after
 *  every part: the reader carries it forward across the list, and three of them
 *  in a row is a sentence explaining its own grammar. */
const LEAD = 'Nearby'

/** Said once, on the first part only, for the reason LEAD exists. */
const AWAY = ' away'

/**
 * The parts as one sentence, or null when there are none to name.
 *
 * Null rather than an empty string so a caller renders nothing rather than an
 * empty paragraph - the card has a `<p>` for this, and an empty one is a gap
 * in the layout that reads as something failing to load.
 */
export function describeNearby(
  parts: readonly NearbyPart[] | undefined,
  units: UnitSystem,
): string | null {
  if (parts === undefined || parts.length === 0) return null

  const named = parts.map(
    (part, index) =>
      `${part.phrase} ${formatShortDistance(part.distance_ft, units)}${index === 0 ? AWAY : ''}`,
  )
  return `${LEAD}: ${joinParts(named)}.`
}

/** "a, b and c" - an Oxford-comma-free list, matching the pipeline's own
 *  `_join` and the app's prose elsewhere. */
function joinParts(parts: readonly string[]): string {
  if (parts.length === 1) return parts[0]
  return `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`
}
