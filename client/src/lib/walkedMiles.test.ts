import { describe, it, expect, beforeEach } from 'vitest'
import {
  MAX_FIX_GAP_MILES,
  WALKED_STORAGE_KEY,
  clearWalked,
  mergeRange,
  readWalked,
  recordStep,
  walkedTotal,
  walkedWithin,
  writeWalked,
  type MileRange,
} from './walkedMiles'

beforeEach(() => {
  localStorage.removeItem(WALKED_STORAGE_KEY)
})

/**
 * The gate is the mechanism (#598).
 *
 * The maintainer's rule, 2026-08-19: two fixes count as walking between them
 * only if they are no more than half a mile apart. Everything else this module
 * does is bookkeeping; this is the part that decides whether a claim about a
 * hiker's legs is true.
 */
describe('the half-mile gate', () => {
  it('records the ground between two fixes close enough to have been walked', () => {
    expect(recordStep([], 940.0, 940.4)).toEqual([{ startMile: 940.0, endMile: 940.4 }])
  })

  it('refuses a pair that could as easily have been a ride', () => {
    // Two fixes eight miles apart is a shuttle, a hitch, or the app having
    // been shut - and claiming the ground between them is a statement about
    // somebody's legs that nothing observed.
    expect(recordStep([], 940, 948)).toEqual([])
  })

  it('takes the boundary itself, and refuses just past it', () => {
    expect(recordStep([], 100, 100 + MAX_FIX_GAP_MILES)).toHaveLength(1)
    expect(recordStep([], 100, 100 + MAX_FIX_GAP_MILES + 0.01)).toEqual([])
  })

  it('works walking south as well as north', () => {
    // A SOBO hiker's fixes descend. Direction-agnostic, like trailSlice.
    expect(recordStep([], 940.4, 940.0)).toEqual([{ startMile: 940.0, endMile: 940.4 }])
  })

  it('keeps what was already walked when a step is refused', () => {
    const covered = recordStep([], 940.0, 940.4)
    expect(recordStep(covered, 940.4, 990)).toEqual(covered)
  })

  it.each([
    ['no previous fix', null, 940.2],
    ['no current fix', 940.2, null],
    ['a fix off the trail entirely', Number.NaN, 940.2],
  ])('records nothing given %s', (_label, from, to) => {
    expect(recordStep([], from, to)).toEqual([])
  })
})

describe('mergeRange', () => {
  it('joins intervals that merely touch, so a walk stays one walk', () => {
    // Left apart, a thru-hike stores one entry per fix pair - tens of
    // thousands of them - to describe a single line down the trail.
    const covered = mergeRange([{ startMile: 940, endMile: 941 }], {
      startMile: 941,
      endMile: 942,
    })
    expect(covered).toEqual([{ startMile: 940, endMile: 942 }])
  })

  it('swallows several existing intervals at once', () => {
    // The ordinary case after an hour's walking, and the one the first
    // hand-rolled splice version got wrong.
    const covered: MileRange[] = [
      { startMile: 10, endMile: 11 },
      { startMile: 12, endMile: 13 },
      { startMile: 14, endMile: 15 },
    ]
    expect(mergeRange(covered, { startMile: 10.5, endMile: 14.5 })).toEqual([
      { startMile: 10, endMile: 15 },
    ])
  })

  it('keeps disjoint walks apart, and in mile order', () => {
    let covered = mergeRange([], { startMile: 900, endMile: 900.4 })
    covered = mergeRange(covered, { startMile: 100, endMile: 100.4 })
    covered = mergeRange(covered, { startMile: 500, endMile: 500.4 })
    expect(covered.map((r) => r.startMile)).toEqual([100, 500, 900])
  })

  it('adds nothing for a step that covered no ground', () => {
    expect(mergeRange([], { startMile: 940, endMile: 940 })).toEqual([])
  })

  it('never mutates what it was given', () => {
    const covered: MileRange[] = [{ startMile: 10, endMile: 11 }]
    mergeRange(covered, { startMile: 10.5, endMile: 12 })
    expect(covered).toEqual([{ startMile: 10, endMile: 11 }])
  })
})

describe('walkedWithin', () => {
  const covered: MileRange[] = [
    { startMile: 0, endMile: 20 },
    { startMile: 40, endMile: 50 },
  ]

  it('sums the overlap, because a part-walked stretch is neither yes nor no', () => {
    // A hiker who has done two thirds of a club's section has not "visited" it
    // and has not not-visited it, and a boolean would have to pick one.
    expect(walkedWithin(covered, { startMile: 0, endMile: 77 })).toBe(30)
  })

  it('clips to the range asked about', () => {
    expect(walkedWithin(covered, { startMile: 10, endMile: 45 })).toBe(15)
  })

  it('is zero for a stretch nobody has walked', () => {
    expect(walkedWithin(covered, { startMile: 100, endMile: 200 })).toBe(0)
  })

  it('counts the whole trail', () => {
    expect(walkedTotal(covered)).toBe(30)
  })
})

/**
 * What is on the phone, and what deliberately is not.
 *
 * features/EVENTING.md rule 2 forbids geography in the event pipe. This module
 * answers the same question without one, by computing on the device - so the
 * thing worth asserting is that what it leaves behind is an ANSWER and not the
 * evidence a route could be rebuilt from.
 */
describe('what is stored', () => {
  it('survives a restart', () => {
    writeWalked([{ startMile: 940, endMile: 941 }])
    expect(readWalked()).toEqual([{ startMile: 940, endMile: 941 }])
  })

  it('stores mile intervals and nothing else - no coordinates, no times', () => {
    writeWalked(recordStep([], 940.0, 940.4))
    const raw = localStorage.getItem(WALKED_STORAGE_KEY) ?? ''

    expect(JSON.parse(raw)).toEqual([{ startMile: 940, endMile: 940.4 }])
    // The three things that would turn this file into a route down the
    // corridor if anybody read it.
    expect(raw).not.toMatch(/lat|lon|lng|time|stamp|date/i)
  })

  it('can be forgotten, because a record of where somebody has been should be', () => {
    writeWalked([{ startMile: 940, endMile: 941 }])
    clearWalked()
    expect(readWalked()).toEqual([])
  })

  it('reads nothing rather than throwing on a corrupted store', () => {
    localStorage.setItem(WALKED_STORAGE_KEY, 'not json at all')
    expect(readWalked()).toEqual([])
  })

  it('drops entries it cannot read without losing the ones beside them', () => {
    localStorage.setItem(
      WALKED_STORAGE_KEY,
      JSON.stringify([{ startMile: 1, endMile: 2 }, { nope: true }, null]),
    )
    expect(readWalked()).toEqual([{ startMile: 1, endMile: 2 }])
  })
})
