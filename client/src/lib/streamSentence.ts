// The sentence naming a shelter's nearest USGS-mapped stream - "Nearest
// mapped stream: Stony Brook, about 250 ft (USGS; mapped as year-round, not
// recently verified)." - from the facts export_poi.py publishes as `stream`
// (#529, WATER_SOURCES.md §7 option 2).
//
// WRITTEN HERE FOR nearbyClause.ts's EXACT REASON (#625): the sentence
// contains a distance, a distance is the reader's question, and published
// prose cannot ask anybody anything. The pipeline publishes the name, the
// flow class and the feet; this file owns the words around them.
//
// The wording is the load-bearing part, and three constraints travel with it
// from the pipeline's research (WATER_SOURCES.md §5):
//
// - "MAPPED AS", NEVER "IS". NHD's perennial/intermittent code disagrees
//   with field observations ~20% of the time and far more at headwaters, and
//   the snapshot it comes from was frozen in 2023 - so year-round is what
//   the map says, "not recently verified" is what the freeze means, and both
//   qualifiers stay attached to the claim they qualify. An unclassified
//   reach makes no flow claim at all rather than a hedged one.
// - "ABOUT", WITH COARSE ROUNDING TO MATCH. The distance came from an
//   envelope query against survey-era stream geometry; "about 236 ft" would
//   dress that as a measurement. Coarsened in the unit about to be written,
//   so both readers get a walking number rather than a converted artefact.
// - THE NO-STREAM FACT PRINTS. "No mapped stream within 1 km" is a fact a
//   hiker plans an evening around - Blood Mountain's card owes them that
//   sentence most of all - so {"none": true} composes a sentence rather
//   than rendering nothing. Nothing at all (no reference row) is the app
//   not knowing, and that stays silent.

import type { UnitSystem } from './units'

const FEET_PER_METRE = 3.28084

/**
 * The stream facts as the artifact publishes them (export_poi.py's `stream`).
 * Field names in the artifact's own snake_case, for NearbyPart's reason: a
 * field that reads differently in two places is a field somebody has to check
 * the mapping of. Feet because the export converts the measured metres once,
 * at its boundary.
 */
export interface StreamFacts {
  name?: string | null
  distance_ft?: number
  flow?: string | null
  none?: boolean
}

/** What each flow class may claim, and that unknown classes claim nothing -
 *  a flow value this build has never heard of degrades to the bare "(USGS)"
 *  rather than to a promise nobody made. */
const FLOW_QUALIFIERS: Record<string, string> = {
  perennial: 'mapped as year-round, not recently verified',
  intermittent: 'mapped as seasonal, not recently verified',
  ephemeral: 'mapped as seasonal, not recently verified',
}

/** The claim's edge, spelled per unit system rather than converted: the
 *  pipeline's radius is 1,000 m, and "within 3,281 ft" is not a sentence a
 *  hiker says in either system. */
const NO_STREAM = {
  metric: 'No mapped stream within 1 km (USGS).',
  imperial: 'No mapped stream within 0.6 mi (USGS).',
} as const

/**
 * "about 70 m" / "about 250 ft" - coarsened in the unit about to be written,
 * so the roundness a reader takes as "roughly" is real in the number they
 * read. Metres step by 10 under 100 m and 50 above; feet by 25 under 300 ft
 * and 100 above - the same walking-scale coarseness in each system's own
 * round numbers. Floored at one step so a streamside shelter reads "about
 * 10 m", never "about 0 m".
 */
function aboutDistance(feet: number, units: UnitSystem): string {
  if (units === 'metric') {
    const metres = feet / FEET_PER_METRE
    const step = metres < 100 ? 10 : 50
    const about = Math.max(step, Math.round(metres / step) * step)
    return `about ${about.toLocaleString('en-US')} m`
  }
  const step = feet < 300 ? 25 : 100
  const about = Math.max(step, Math.round(feet / step) * step)
  return `about ${about.toLocaleString('en-US')} ft`
}

/**
 * The stream sentence, or null when the artifact published no facts - an
 * older artifact, or a POI that is not a shelter. Null rather than '' so the
 * card renders nothing instead of an empty paragraph.
 */
export function describeStream(
  facts: StreamFacts | undefined,
  units: UnitSystem,
): string | null {
  if (facts === undefined) return null
  if (facts.none === true) return NO_STREAM[units]
  if (typeof facts.distance_ft !== 'number' || !Number.isFinite(facts.distance_ft)) {
    return null
  }

  const qualifier = FLOW_QUALIFIERS[facts.flow ?? '']
  const parenthetical = qualifier === undefined ? '(USGS)' : `(USGS; ${qualifier})`
  const distance = aboutDistance(facts.distance_ft, units)

  if (typeof facts.name === 'string' && facts.name !== '') {
    return `Nearest mapped stream: ${facts.name}, ${distance} ${parenthetical}.`
  }
  return `Nearest mapped stream ${distance} ${parenthetical}.`
}
