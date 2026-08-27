// Which miles this hiker walked TODAY - the Volunteer tab's "places you
// passed today" list (features/DATA_NUDGES.md's fourth surface, #759).
//
// A today-scoped sibling of lib/walkedMiles.ts, holding itself to the same
// privacy posture that module documents at length: mile INTERVALS, merged -
// no fixes, no coordinates, no timestamps, no ordering - computed on the
// device about the device's own fixes, stored on the device, and never
// uploaded. The one thing added is a single LOCAL calendar date naming which
// day the intervals belong to, which is what lets yesterday's walking stop
// claiming to be today's. One date beside merged intervals still cannot be
// replayed into a route: it says which day, never when, in what order, or
// how many times.
//
// THE LIST THIS FEEDS HAS A RULE, and it is the reason the module stores so
// little: "it never counts, and it never mentions what was skipped"
// (DATA_NUDGES.md). It is a shortcut for logging from memory at camp, not a
// scoreboard of the day's omissions - so nothing here records what was asked,
// what was answered, or what was walked past.

import { recordStep, type MileRange } from './walkedMiles'

export interface PassedToday {
  /** The hiker's own calendar day, local time - a day on the trail ends when
   *  theirs does, not at UTC midnight over Greenwich. */
  day: string
  /** Readonly for lib/walkedMiles.ts's reason: an unchanged step hands back
   *  the array it was given rather than a copy of it (#1090), so mutating one
   *  of these would reach into React state. */
  ranges: readonly MileRange[]
}

/** The hiker's local date as YYYY-MM-DD. `en-CA` formats exactly that. */
export function localDay(now: Date): string {
  return now.toLocaleDateString('en-CA')
}

export function emptyDay(now: Date): PassedToday {
  return { day: localDay(now), ranges: [] }
}

/**
 * One step, today: the same half-mile gate as walkedMiles (one gate, one
 * home - recordStep is the only place it is applied), on a record that
 * resets itself the first step after local midnight.
 */
export function advanceToday(
  current: PassedToday | null,
  now: Date,
  fromMile: number | null,
  toMile: number | null,
): PassedToday {
  const today = localDay(now)
  const base = current !== null && current.day === today ? current : emptyDay(now)
  const ranges = recordStep(base.ranges, fromMile, toMile)
  // The RECORD THAT CAME IN, where the step changed nothing and the day has
  // not turned (#1090). `recordStep` hands back the same array on a no-op, so
  // this is the wrapper keeping the same promise: a jittering fix that records
  // no new ground costs no re-render and no `localStorage` write.
  //
  // `base === current` is the whole of "the day has not turned" - it holds only
  // where the record passed in was today's, and a new day has to change the
  // state whatever the step did.
  if (base === current && ranges === base.ranges) return current
  return { day: today, ranges }
}

export const PASSED_TODAY_STORAGE_KEY = 'ourhike:passed-today'

/** localStorage, and swallowing its own failures, for walkedMiles' reasons.
 *  A stored record from another day reads as empty rather than as today's. */
export function readPassedToday(now: Date): PassedToday {
  try {
    const raw = localStorage.getItem(PASSED_TODAY_STORAGE_KEY)
    if (raw === null) return emptyDay(now)
    const parsed: unknown = JSON.parse(raw)
    if (
      typeof parsed !== 'object' ||
      parsed === null ||
      typeof (parsed as PassedToday).day !== 'string' ||
      !Array.isArray((parsed as PassedToday).ranges)
    ) {
      return emptyDay(now)
    }
    const stored = parsed as PassedToday
    if (stored.day !== localDay(now)) return emptyDay(now)
    return {
      day: stored.day,
      ranges: stored.ranges.filter(
        (range) => Number.isFinite(range?.startMile) && Number.isFinite(range?.endMile),
      ),
    }
  } catch {
    return emptyDay(now)
  }
}

export function writePassedToday(record: PassedToday): void {
  try {
    localStorage.setItem(PASSED_TODAY_STORAGE_KEY, JSON.stringify(record))
  } catch {
    // Ignored on purpose - see walkedMiles.readWalked.
  }
}

/**
 * The places inside today's walked miles that the ask is scoped to - what
 * the Volunteer tab lists for a hiker logging from memory at camp.
 *
 * Sorted by mile so the list reads as the day did. The interval test is
 * inclusive on both ends: a spring at exactly the fix's mile was passed.
 */
export function passedPlaces<T extends { mile?: number; type: string }>(
  ranges: readonly MileRange[],
  pois: readonly T[],
  scopedTypes: readonly string[],
): T[] {
  return pois
    .filter((poi) => poi.mile !== undefined && scopedTypes.includes(poi.type))
    .filter((poi) =>
      ranges.some(
        (range) =>
          (poi.mile as number) >= Math.min(range.startMile, range.endMile) &&
          (poi.mile as number) <= Math.max(range.startMile, range.endMile),
      ),
    )
    .sort((a, b) => (a.mile as number) - (b.mile as number))
}
