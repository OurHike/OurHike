// Tests for daySummary.ts (#966).
//
// What is worth pinning here is not the arithmetic - it is the two claims
// the screen makes on top of it. `longestDryRun` says "no water WAYPOINT",
// and the difference between that and "no water" is the difference between
// a true sentence and one that would have a hiker planning a carry off
// somebody else's missing data; so the null-on-a-pre-#753-download case and
// the whole-day-is-one-run case both get held here rather than being left
// to the component. `milestoneCrossed` is memory, and a memory that fires
// when the hiker is standing ON the marker is a small lie.

import { describe, expect, it } from 'vitest'

import { longestDryRun, milestoneCrossed, MILESTONE_STEP } from './daySummary'
import type { StoredPoi } from './trailData'

const poi = (id: string, type: string, mile: number | undefined): StoredPoi => ({
  id,
  type,
  name: id,
  lat: 0,
  lon: 0,
  confidence: 'high',
  ...(mile === undefined ? {} : { mile }),
})

describe('milestoneCrossed', () => {
  it('finds the hundred a northbound day walked through', () => {
    expect(milestoneCrossed(494.2, 503.4)).toBe(500)
  })

  it('finds it on a southbound day, walking the same marker the other way', () => {
    expect(milestoneCrossed(503.4, 494.2)).toBe(500)
  })

  it('says nothing about a day that crossed no hundred', () => {
    expect(milestoneCrossed(470.8, 486.2)).toBeNull()
  })

  it('does not fire for a day that ENDS on the marker', () => {
    // "Somewhere in there you passed mile 500" about a hiker standing at
    // the 500 marker is wrong in the way this card cannot afford to be.
    expect(milestoneCrossed(486.2, 500)).toBeNull()
  })

  it('does not fire for a day that STARTS on the marker either', () => {
    expect(milestoneCrossed(500, 515.5)).toBeNull()
  })

  it('returns the last one reached, in walk order', () => {
    // A day long enough to cross two is not a real day, but the rule has to
    // be decidable: what a hiker remembers as today's is the last one.
    expect(milestoneCrossed(495, 605)).toBe(600)
    expect(milestoneCrossed(605, 495)).toBe(500)
  })

  it('defaults to hundreds', () => {
    expect(MILESTONE_STEP).toBe(100)
    // The day that says nothing at the default step says something at 50 -
    // which is exactly why the default is 100 and not 50.
    expect(milestoneCrossed(470.8, 486.2)).toBeNull()
    expect(milestoneCrossed(470.8, 486.2, 25)).toBe(475)
  })

  it('refuses a non-finite mile rather than returning a made-up marker', () => {
    expect(milestoneCrossed(Number.NaN, 503.4)).toBeNull()
    expect(milestoneCrossed(494.2, Number.POSITIVE_INFINITY)).toBeNull()
  })
})

describe('longestDryRun', () => {
  const pois = [
    poi('w1', 'water', 472.0),
    poi('w2', 'water', 478.1),
    poi('w3', 'water', 484.2),
    poi('s1', 'shelter', 480.0),
  ]

  it('measures between the water waypoints inside the day', () => {
    const run = longestDryRun(pois, 470.8, 486.2)
    expect(run).not.toBeNull()
    // Runs are 1.2, 6.1, 6.1, 2.0 - the first 6.1 wins on strict >.
    expect(run?.miles).toBeCloseTo(6.1, 5)
    expect(run?.fromMile).toBeCloseTo(472.0, 5)
    expect(run?.toMile).toBeCloseTo(478.1, 5)
    expect(run?.waterCount).toBe(3)
  })

  it('ignores waypoints that are not water', () => {
    // The shelter at 480.0 sits inside the winning run and must not split it.
    expect(longestDryRun(pois, 470.8, 486.2)?.waterCount).toBe(3)
  })

  it('reports the whole day when no water waypoint is on it', () => {
    const run = longestDryRun([poi('s1', 'shelter', 480.0)], 470.8, 486.2)
    expect(run?.miles).toBeCloseTo(15.4, 5)
    expect(run?.waterCount).toBe(0)
  })

  it('measures the same day walked southbound', () => {
    const run = longestDryRun(pois, 486.2, 470.8)
    expect(run?.miles).toBeCloseTo(6.1, 5)
  })

  it('counts the day ends as run boundaries, not as water', () => {
    // One spring, 2 miles in: the run to the day's end is the long one.
    const run = longestDryRun([poi('w1', 'water', 472.8)], 470.8, 486.2)
    expect(run?.miles).toBeCloseTo(13.4, 5)
    expect(run?.waterCount).toBe(1)
  })

  it('returns null on a download whose POIs carry no miles', () => {
    // Absent miles and absent water are indistinguishable from in here, and
    // guessing between them would print "15.4 mi with no water" about a
    // stretch with four springs on it.
    expect(longestDryRun([poi('w1', 'water', undefined)], 470.8, 486.2)).toBeNull()
  })

  it('counts a spring sitting exactly on a day boundary (#986)', () => {
    // A day from one spring to the next: water at both ends, and nothing
    // between. A strict comparison excluded both and the card then said "no
    // water waypoint on any of today" about a day bounded by water.
    const run = longestDryRun(
      [poi('w1', 'water', 470.8), poi('w2', 'water', 486.2)],
      470.8,
      486.2,
    )
    expect(run?.waterCount).toBe(2)
    expect(run?.miles).toBeCloseTo(15.4, 5)
  })

  it('still reports zero water when the day genuinely has none', () => {
    // The boundary fix must not turn "no water" into a false positive.
    const run = longestDryRun([poi('w1', 'water', 500)], 470.8, 486.2)
    expect(run?.waterCount).toBe(0)
  })

  it('refuses a zero-length or backwards-collapsed day', () => {
    expect(longestDryRun(pois, 470.8, 470.8)).toBeNull()
  })
})
