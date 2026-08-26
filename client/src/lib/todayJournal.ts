// What the Today journal shows, and in what order (#1054).
//
// Chronology is the hierarchy: a hiker's question is ordered by distance, so
// the column is ordered by distance - a mile gutter down the left, one entry
// per thing you will meet, in the order you will meet it. This module is the
// pure half of that: which waypoints qualify, how they are ordered, and what
// the greeting may honestly claim. The screen renders; this decides.
//
// EVERY CLAIM HERE DEGRADES TO SILENCE, NOT TO A GUESS. No current mile means
// no entries (a journal of "what you will meet" needs to know where you are);
// no settled direction means the section is "NEARBY" rather than "AHEAD",
// because "ahead" is a claim about which way somebody is walking and the
// ribbon's own SUBJECT_LABELS already establish that saying it without
// knowing it is telling a hiker something false (chrome/ElevationRibbon.tsx).

import type { HikeDirection } from '../chrome/Header'
import type { ElevationSample } from '../chrome/ElevationRibbon'

export interface JournalPoi {
  id: string
  name: string
  type: string
  /** On the client mile axis, like every searchable POI - absent for a POI
   *  nothing could place on the trail, which the journal then cannot rank. */
  mile?: number
}

export interface JournalEntry {
  id: string
  name: string
  type: string
  mile: number
  /** Miles between the hiker and this entry, always positive - the gutter
   *  figure. The direction of travel decided membership; this is magnitude. */
  distanceMi: number
}

/**
 * The types the journal ranks: the ones a hiker meets and plans around -
 * water, sleep, resupply, and the towns those come from. Everything else
 * (parking, crossings, viewpoints, privies) stays reachable on the map and
 * in search; a journal that listed every crossing would bury the spring
 * somebody is rationing water toward.
 *
 * @unvalidated The set is a curation choice, not a finding. What would settle
 * it: which entry types hikers actually tap, once anything measures that.
 */
export const JOURNAL_TYPES = ['water', 'shelter', 'campsite', 'resupply', 'town'] as const

/**
 * One screen's worth. The journal is "what happens next today", not the whole
 * corridor - past this the map and search are the right tools, and a longer
 * list buries the near entries a hiker is actually walking toward.
 *
 * @unvalidated 7 is picked, not measured. What would settle it: how far down
 * the column hikers actually scroll.
 */
export const MAX_JOURNAL_ENTRIES = 7

/**
 * The entries the hiker will meet, nearest first.
 *
 * With a settled direction, "meet" means ahead in that direction, walked in
 * order. Without one, it means nearest in either direction - membership
 * changes because the claim does, and the screen labels the section
 * accordingly (AHEAD vs NEARBY).
 */
export function journalEntries(
  pois: readonly JournalPoi[],
  currentMile: number | undefined,
  direction: HikeDirection | undefined,
): JournalEntry[] {
  if (currentMile === undefined || !Number.isFinite(currentMile)) return []

  const placed = pois.filter(
    (poi): poi is JournalPoi & { mile: number } =>
      poi.mile !== undefined &&
      Number.isFinite(poi.mile) &&
      (JOURNAL_TYPES as readonly string[]).includes(poi.type),
  )

  const candidates =
    direction === 'NOBO'
      ? placed.filter((poi) => poi.mile >= currentMile)
      : direction === 'SOBO'
        ? placed.filter((poi) => poi.mile <= currentMile)
        : placed

  return candidates
    .map((poi) => ({
      id: poi.id,
      name: poi.name,
      type: poi.type,
      mile: poi.mile,
      distanceMi: Math.abs(poi.mile - currentMile),
    }))
    .sort((a, b) => a.distanceMi - b.distanceMi || a.id.localeCompare(b.id))
    .slice(0, MAX_JOURNAL_ENTRIES)
}

/** The greeting's destination: the first shelter the journal ranks, which is
 *  only a claim about "ahead" when the entries were built with a direction. */
export function nextShelter(entries: readonly JournalEntry[]): JournalEntry | undefined {
  return entries.find((entry) => entry.type === 'shelter')
}

/**
 * Feet of ascent between two miles, from the profile samples on hand - or
 * null when the samples do not cover the span.
 *
 * Null matters more than the number: the greeting's time estimate leans on
 * this, and pricing a walk's climbs at zero because the window ended early
 * would UNDERSTATE the time - the direction CLAUDE.md's "round toward
 * caution" forbids. No coverage, no estimate; the greeting then says the
 * distance and stops.
 *
 * Counted in walk order (from -> to), positive deltas only - the same
 * no-descent-credit stance as lib/naismith.ts, one measurement earlier.
 */
export function ascentBetween(
  samples: readonly ElevationSample[],
  fromMile: number,
  toMile: number,
): number | null {
  if (samples.length < 2) return null
  const low = Math.min(fromMile, toMile)
  const high = Math.max(fromMile, toMile)

  // The published profile is sampled roughly every 25 m (~0.016 mi); half a
  // tenth of a mile of slack at each end tolerates a window edge landing
  // between samples without accepting a window that plainly stops short.
  const COVERAGE_SLACK_MI = 0.05
  const first = samples[0].mile
  const last = samples[samples.length - 1].mile
  if (low < first - COVERAGE_SLACK_MI || high > last + COVERAGE_SLACK_MI) return null

  const inSpan = samples.filter((s) => s.mile >= low && s.mile <= high)
  if (inSpan.length < 2) return null

  // Walk order: southbound walks the same samples highest-mile first.
  const walked = fromMile <= toMile ? inSpan : [...inSpan].reverse()
  let ascent = 0
  for (let i = 1; i < walked.length; i += 1) {
    const climb = walked[i].elevationFt - walked[i - 1].elevationFt
    if (climb > 0) ascent += climb
  }
  return ascent
}
