// Which miles of the trail this hiker has actually walked (#598's `visited`).
//
// THE RULE, AND WHOSE IT IS
//
// The maintainer's, 2026-08-19: a stretch counts as walked when two GPS fixes
// fall inside it no more than half a mile apart. {@link MAX_FIX_GAP_MILES} is
// that number, taken verbatim rather than derived.
//
// The gate is the whole mechanism. Two fixes further apart than half a mile
// could be a car, a shuttle, a hitch into town, a flight home, or the app
// simply having been shut for a day - and painting the ground between them as
// walked would be a claim about a hiker's legs that nothing observed. Half a
// mile is close enough together that the only ordinary way to produce the pair
// is to have walked between them.
//
// WHY THIS RUNS HERE AND UPLOADS NOTHING
//
// features/EVENTING.md §1 rule 2: "No geography, ever. No coordinates, no
// mile, no segment id, no POI id, no region. This is the #252 half of the pair,
// and on a trail app it is the more dangerous half." A stable identifier beside
// a trail position and a time is a hiker's route down the corridor, and #252
// already paid to have that pair removed from the report API.
//
// The rule above needs none of that to work. Deciding whether two fixes are
// half a mile apart is arithmetic the PHONE can do about ITS OWN fixes, and
// the answer - "you have walked these miles" - is a fact worth having on its
// own. So this module computes it on the device and stores it on the device,
// and nothing here reaches the network. What it enables is a hiker being told
// what they have walked, not a popularity count; a count across hikers is a
// different feature and needs an explicit, dated decision about rule 2 before
// anybody builds it.
//
// WHAT IS STORED, AND WHAT DELIBERATELY IS NOT
//
// Mile INTERVALS, merged. Not fixes, not coordinates, not timestamps, not an
// ordering. "Miles 940.2-951.8 have been walked" cannot be replayed into a
// route down the corridor the way a fix log can, because it does not record
// when, in what order, or how many times. That distinction is the reason this
// stores the ANSWER rather than the evidence for it: a local file that would be
// a route if somebody read it is still a route.

/**
 * How far apart two fixes may be and still have walking between them, in
 * trail miles.
 *
 * The maintainer's number (2026-08-19), not a derived one. @unvalidated
 * against real GPS behaviour: what would settle it is a field pass with the
 * phone in a pocket under tree canopy, where fixes are sparser and the gate
 * will reject more than it does in the open - the same outdoor testing
 * HIKER_SAFETY.md §5 declines to guess at. Erring small is the safe direction:
 * a rejected pair costs a hiker credit for miles they walked, while a generous
 * gate credits them with miles they rode.
 */
export const MAX_FIX_GAP_MILES = 0.5

/** A half-open mile interval, `[startMile, endMile)`. */
export interface MileRange {
  startMile: number
  endMile: number
}

/** Nothing walked yet - a fresh phone, or a hiker who has cleared it. */
export const NOTHING_WALKED: readonly MileRange[] = []

/**
 * Merges one interval into a sorted, disjoint set, and keeps it sorted and
 * disjoint.
 *
 * Touching intervals join rather than sitting adjacent: 940.0-941.0 beside
 * 941.0-942.0 is one walk of two miles, and leaving them apart would grow the
 * stored set without bound over a thru-hike - one entry per fix pair, tens of
 * thousands of them, to describe a single line.
 */
export function mergeRange(
  covered: readonly MileRange[],
  range: MileRange,
): readonly MileRange[] {
  const startMile = Math.min(range.startMile, range.endMile)
  const endMile = Math.max(range.startMile, range.endMile)
  if (!Number.isFinite(startMile) || !Number.isFinite(endMile)) return covered
  if (endMile === startMile) return covered

  // Already inside a range this set holds, so there is nothing to merge and -
  // the part that matters - nothing to hand back a new array for (#1090).
  //
  // WHY IDENTITY IS THE POINT. This is React state. `setWalked` is called once
  // per GPS fix whose mile differs from the last, a jittering fix under tree
  // cover flips between adjacent centerline vertices without anybody moving,
  // and a fresh array on an unchanged answer is a re-render of the whole shell
  // plus a synchronous `localStorage` write from the effect that persists it -
  // twice over, since `advanceToday` runs the same arithmetic for today's
  // slice. React bails out of the render when an updater returns the state it
  // was given, so returning `covered` is what makes a no-op cost nothing.
  //
  // The returned set is `readonly` for exactly this reason: a caller that
  // mutated the array it got back would now be mutating the state it came
  // from. Nothing does, and the type is what keeps it that way.
  if (covered.some((held) => startMile >= held.startMile && endMile <= held.endMile)) {
    return covered
  }

  // Sort-then-sweep rather than find-the-insertion-point-and-splice. The
  // second is what this was written as first, and it needed four branches to
  // handle "the new interval swallows several existing ones" - the ordinary
  // case after an hour's walking, and the one a subtle bug would hide in.
  const all = [...covered, { startMile, endMile }].sort(byStart)
  const merged: MileRange[] = []
  for (const next of all) {
    const last = merged[merged.length - 1]
    // `<=` and not `<`: intervals that merely touch are one walk, not two.
    // Left apart, a thru-hike would store one entry per fix pair - tens of
    // thousands of them - to describe a single line.
    if (last !== undefined && next.startMile <= last.endMile) {
      last.endMile = Math.max(last.endMile, next.endMile)
    } else {
      merged.push({ ...next })
    }
  }
  return merged
}

function byStart(a: MileRange, b: MileRange): number {
  return a.startMile - b.startMile
}

/**
 * One step: the hiker was at `fromMile` and is now at `toMile`.
 *
 * Returns the set unchanged when the pair is too far apart to stand for
 * walking - which is the rule, and the only place it is applied. A caller that
 * wants to record a walk it is sure of should still come through here, so
 * there is exactly one gate rather than one per call site.
 *
 * "Unchanged" means the SAME ARRAY, not an equal one (#1090). See `mergeRange`.
 */
export function recordStep(
  covered: readonly MileRange[],
  fromMile: number | null,
  toMile: number | null,
): readonly MileRange[] {
  // The set ITSELF back on every refusal, not a copy of it (#1090) - see
  // `mergeRange` for why the reference is the whole point.
  if (fromMile === null || toMile === null) return covered
  if (!Number.isFinite(fromMile) || !Number.isFinite(toMile)) return covered
  if (Math.abs(toMile - fromMile) > MAX_FIX_GAP_MILES) return covered
  return mergeRange(covered, { startMile: fromMile, endMile: toMile })
}

/**
 * How many of `range`'s miles the hiker has walked.
 *
 * The number a sheet actually shows - "you have walked 40.2 of this club's 77
 * miles" - so it is an overlap sum rather than a boolean. A hiker who has done
 * two thirds of a stretch has not "visited" it and has not not-visited it
 * either, and a yes/no would have to pick one.
 */
export function walkedWithin(covered: readonly MileRange[], range: MileRange): number {
  const low = Math.min(range.startMile, range.endMile)
  const high = Math.max(range.startMile, range.endMile)
  let total = 0
  for (const walked of covered) {
    const overlap = Math.min(high, walked.endMile) - Math.max(low, walked.startMile)
    if (overlap > 0) total += overlap
  }
  return total
}

/** Total miles walked, over the whole trail. */
export function walkedTotal(covered: readonly MileRange[]): number {
  return covered.reduce((sum, range) => sum + (range.endMile - range.startMile), 0)
}

export const WALKED_STORAGE_KEY = 'ourhike:walked-miles'

/**
 * localStorage rather than IndexedDB, for lib/trailShape.ts's reason: this is
 * read synchronously while a sheet renders, and an async read would mean the
 * sheet drawing once without the line and again with it.
 *
 * Every accessor swallows its own failure. Private browsing, a full quota and
 * a disabled store all end here, and none of them is worth costing a hiker the
 * club sheet they actually tapped for.
 */
export function readWalked(): MileRange[] {
  try {
    const raw = localStorage.getItem(WALKED_STORAGE_KEY)
    if (raw === null) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter(
        (entry): entry is MileRange =>
          typeof entry === 'object' &&
          entry !== null &&
          Number.isFinite((entry as MileRange).startMile) &&
          Number.isFinite((entry as MileRange).endMile),
      )
      .map((entry) => ({ startMile: entry.startMile, endMile: entry.endMile }))
      .sort(byStart)
  } catch {
    return []
  }
}

export function writeWalked(covered: readonly MileRange[]): void {
  try {
    localStorage.setItem(WALKED_STORAGE_KEY, JSON.stringify(covered))
  } catch {
    // Ignored on purpose - see readWalked.
  }
}

/** Forgets everything walked. Nothing calls this yet; it exists because a
 *  record of where somebody has been is one they are entitled to delete, and a
 *  store with no way out is the kind this app should not be adding. */
export function clearWalked(): void {
  try {
    localStorage.removeItem(WALKED_STORAGE_KEY)
  } catch {
    // Ignored on purpose - see readWalked.
  }
}
