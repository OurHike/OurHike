// Tests for planBench.ts (#971) - the writer behind the one gesture the wide
// Plan layout exists for.
//
// WHAT IS PINNED HERE IS THE SAFETY ARCHITECTURE, in the shape cascade.test.ts
// pins it: the past never edited, pins never dragged through, the plan's own
// ends never moved, two days changed and never a third, both of them carrying
// what they used to be, and the plan handed in coming back untouched so an
// undo has something to undo.
//
// The asymmetry this module errs toward: a boundary REFUSED that could have
// moved is a hiker who drags and nothing happens. A boundary moved that should
// not have is a walked day rewritten, or a pinned hostel night silently made
// nineteen miles long. Only one of those is recoverable.

import { describe, expect, it } from 'vitest'

import { boundaryState, moveBoundary, planBoundaries, planStretch } from './planBench'
import {
  buildPlan,
  planDayViews,
  togglePinned,
  validatePlan,
  type HikePlan,
} from './plan'
import { callItADay } from './cascade'
import type { StoredPoi } from './trailData'

const stop = (mile: number, name: string, resupply = false) => ({ mile, name, resupply })

/** Damascus → Atkins, four walking days, dated. The same fixture shape
 *  cascade.test.ts uses, so a reader comparing the two is comparing the
 *  behaviour rather than the numbers. */
function plan(): HikePlan {
  return buildPlan(
    [
      stop(470.8, 'Damascus'),
      stop(486.2, 'Lost Mountain Shelter'),
      stop(503.3, 'Thomas Knob Shelter'),
      stop(516.1, 'Old Orchard Shelter'),
      stop(525.7, 'Atkins', true),
    ],
    { miles: 15 },
    '2026-05-12',
  )
}

/** The same walk south. Stop miles descend, which is the case a min/max
 *  clamp has to survive without a second branch. */
function southbound(): HikePlan {
  return buildPlan(
    [
      stop(525.7, 'Atkins'),
      stop(516.1, 'Old Orchard Shelter'),
      stop(503.3, 'Thomas Knob Shelter'),
      stop(486.2, 'Lost Mountain Shelter'),
    ],
    { miles: 15 },
  )
}

const shelter = (id: string, mile: number, name: string): StoredPoi => ({
  id,
  type: 'shelter',
  name,
  lat: 0,
  lon: 0,
  confidence: 'high',
  mile,
})

const POIS: StoredPoi[] = [
  shelter('lost', 486.2, 'Lost Mountain Shelter'),
  shelter('wise', 490.4, 'Wise Shelter'),
  shelter('thomas', 503.3, 'Thomas Knob Shelter'),
]

/** Day `index`'s length in miles, off the stored boundaries. */
const dayMiles = (p: HikePlan, index: number) =>
  Math.abs(p.stops[index + 1].mile - p.stops[index].mile)

describe('which boundaries may be taken', () => {
  it('fixes both ends of the plan - those are the walk, not a day inside it', () => {
    const p = plan()
    expect(boundaryState(p, 0)).toEqual({ movable: false, why: 'end' })
    expect(boundaryState(p, p.stops.length - 1)).toEqual({ movable: false, why: 'end' })
  })

  it('lets an interior boundary travel exactly as far as its neighbours', () => {
    expect(boundaryState(plan(), 2)).toEqual({
      movable: true,
      minMile: 486.2,
      maxMile: 516.1,
    })
  })

  it('reads a southbound plan the same way, without a second branch', () => {
    // Stops DESCEND here - 525.7, 516.1, 503.3, 486.2 - so the boundary at
    // 516.1 is hemmed in by a larger mile behind it and a smaller one ahead.
    // Taken as a min/max pair, that needs no second branch and no direction.
    expect(boundaryState(southbound(), 1)).toEqual({
      movable: true,
      minMile: 503.3,
      maxMile: 525.7,
    })
  })

  it('fixes the boundary a walked day ended at - the past is a record', () => {
    const walked = callItADay(plan(), 0, { mile: 486.2, name: 'Lost Mountain Shelter' })
    expect(boundaryState(walked, 1)).toEqual({ movable: false, why: 'walked' })
    // And only that one: the day after it is still a plan.
    expect(boundaryState(walked, 2).movable).toBe(true)
  })

  it('fixes both boundaries of a pinned day', () => {
    // Day 1 (index 1) pinned: nothing may change its miles, from either side.
    const pinned = togglePinned(plan(), 1)
    expect(boundaryState(pinned, 1)).toEqual({ movable: false, why: 'pinned' })
    expect(boundaryState(pinned, 2)).toEqual({ movable: false, why: 'pinned' })
    expect(boundaryState(pinned, 3).movable).toBe(true)
  })

  it('draws every stop, marking which of them can move', () => {
    const boundaries = planBoundaries(plan())

    expect(boundaries).toHaveLength(5)
    expect(boundaries.map((b) => b.movable)).toEqual([false, true, true, true, false])
    // A fixed edge is still drawn and still named - a section with invisible
    // ends reads as a plan running off both sides of the picture.
    expect(boundaries[0].label).toBe('Damascus')
    expect(boundaries[4].label).toBe('Atkins')
  })

  it('names a nameless stop by its mile marker rather than leaving it blank', () => {
    const bare = buildPlan(
      [
        { mile: 470.8, resupply: false },
        { mile: 486.2, resupply: false },
        { mile: 503.3, resupply: false },
      ],
      { miles: 15 },
    )
    expect(planBoundaries(bare)[1].label).toBe('mi 486.2')
  })

  it('gives the chart the plan’s own miles to rest on, low first', () => {
    expect(planStretch(plan())).toEqual({ startMile: 470.8, endMile: 525.7 })
    // Direction is not the window's business - a southbound plan covers the
    // same ground.
    expect(planStretch(southbound())).toEqual({ startMile: 486.2, endMile: 525.7 })
  })
})

describe('moving a boundary', () => {
  it('changes exactly the two days that meet at it, and no third', () => {
    const before = plan()
    const move = moveBoundary(before, 2, 500)

    expect(move).not.toBeNull()
    const after = move!.plan
    expect(move!.days).toEqual([1, 2])

    // Day 1 shortens, day 2 lengthens, and the total is unchanged.
    expect(dayMiles(after, 1)).toBeCloseTo(13.8, 6)
    expect(dayMiles(after, 2)).toBeCloseTo(16.1, 6)
    // Days 0 and 3 are byte-identical, boundaries and metadata alike.
    expect(after.stops[0]).toBe(before.stops[0])
    expect(after.stops[1]).toBe(before.stops[1])
    expect(after.stops[4]).toBe(before.stops[4])
    expect(after.days[0]).toBe(before.days[0])
    expect(after.days[3]).toBe(before.days[3])
  })

  it('does NOT cascade - the days after the two it touched keep their miles', () => {
    // The distinction the module header argues for: a drag is not a re-plan.
    // Day 3 is 9.6 mi before and 9.6 mi after, because nothing asked it to
    // absorb anything.
    const before = plan()
    const after = moveBoundary(before, 2, 495)!.plan
    expect(dayMiles(after, 3)).toBeCloseTo(dayMiles(before, 3), 6)
  })

  it('records what both days used to be, so the timeline can say so', () => {
    const move = moveBoundary(plan(), 2, 500)!
    const views = planDayViews(move.plan)

    expect(views[1].wasDistanceMi).toBeCloseTo(17.1, 6)
    expect(views[2].wasDistanceMi).toBeCloseTo(12.8, 6)
    // Both stop being the generator's - the hiker moved them.
    expect(views[1].generated).toBe(false)
    expect(views[2].generated).toBe(false)
  })

  it('keeps the ORIGINAL figure through repeated nudges', () => {
    // "was 17.1 mi" answers "what did the app lay out for me", not "what was
    // it three seconds ago" - shiftPlan's rule, applied here.
    const once = moveBoundary(plan(), 2, 500)!.plan
    const twice = moveBoundary(once, 2, 498)!.plan
    expect(planDayViews(twice)[1].wasDistanceMi).toBeCloseTo(17.1, 6)
  })

  it('says nothing about a day whose distance barely moved', () => {
    // Under the 0.05 mi cascade.ts already uses. A "was" line identical to
    // the figure beside it is noise on the one line that exists to be noticed.
    const move = moveBoundary(plan(), 2, 503.33)!
    expect(planDayViews(move.plan)[1].wasDistanceMi).toBeNull()
  })

  it('hands back the plan it was given, untouched, for the undo', () => {
    const before = plan()
    const move = moveBoundary(before, 2, 500)!

    expect(move.was).toBe(before)
    expect(before.stops[2].mile).toBe(503.3)
  })

  it('clamps to the neighbouring stops rather than reordering the plan', () => {
    // Dragged far past the day after it. The furthest it may go is that
    // neighbour, which makes day 2 a zero - a real edit the timeline draws as
    // "Zero", undoable in one click, and removable through the day's own
    // actions. (The two boundaries it leaves coincident are fixed after
    // that - see the `zero` case above.)
    const move = moveBoundary(plan(), 2, 900)!

    expect(move.mile).toBe(516.1)
    expect(planDayViews(move.plan)[2].zero).toBe(true)
    // Still a valid plan, which is the thing a reorder would have broken.
    expect(validatePlan(move.plan)).not.toBeNull()
  })

  it('clamps a southbound plan against its own descending neighbours', () => {
    const move = moveBoundary(southbound(), 1, 0)!
    expect(move.mile).toBe(503.3)
  })

  it('refuses every fixed boundary, rather than half-applying one', () => {
    const p = plan()
    expect(moveBoundary(p, 0, 475)).toBeNull()
    expect(moveBoundary(p, p.stops.length - 1, 520)).toBeNull()
    expect(moveBoundary(togglePinned(p, 1), 1, 490)).toBeNull()
    expect(moveBoundary(callItADay(p, 0, { mile: 486.2 }), 1, 490)).toBeNull()
    expect(moveBoundary(p, 99, 490)).toBeNull()
    expect(moveBoundary(p, 2, Number.NaN)).toBeNull()
  })

  it('refuses a move that lands where the boundary already is', () => {
    // Nothing to write and nothing to undo, so the screen is told so rather
    // than offered an Undo button that restores the current plan.
    expect(moveBoundary(plan(), 2, 503.3)).toBeNull()
  })

  it('drops the stop’s name when it is dragged off the place it named', () => {
    // A boundary at mi 495 is not Thomas Knob Shelter, and a shelter name over
    // ground nine miles from the shelter is the display outrunning its source.
    const move = moveBoundary(plan(), 2, 495)!

    expect(move.plan.stops[2].name).toBeUndefined()
    expect(move.plan.stops[2].poiId).toBeUndefined()
    expect(move.snappedTo).toBeNull()
  })

  it('takes a real place’s name when it lands on one', () => {
    // Within nearestStop's own half-mile window - the same one "call it a
    // day" uses to decide whether the hiker stopped somewhere with a name.
    const move = moveBoundary(plan(), 2, 490.3, POIS)!

    expect(move.mile).toBe(490.4)
    expect(move.plan.stops[2].name).toBe('Wise Shelter')
    expect(move.plan.stops[2].poiId).toBe('wise')
    expect(move.snappedTo).toBe('Wise Shelter')
  })

  it('never snaps past a neighbouring stop', () => {
    // Dragged to the very edge of its travel, where the nearest named place
    // is on the far side of the day after it. Snapping there would reorder
    // the plan's stops - so it does not, and the boundary keeps its mile.
    // Lost Mountain Shelter sits at mi 486.2, well inside nearestStop's
    // half-mile window of the drag - and just outside this boundary's own
    // travel, which starts at its neighbour's 486.25.
    const tight = buildPlan(
      [stop(486.0, 'A'), stop(486.25, 'B'), stop(486.3, 'C'), stop(486.5, 'D')],
      { miles: 15 },
    )
    const move = moveBoundary(tight, 2, 486.28, POIS)!

    expect(move.mile).toBeCloseTo(486.28, 6)
    expect(move.plan.stops[2].name).toBeUndefined()
  })

  it('carries the resupply flag with the boundary', () => {
    // The hiker's own claim that supplies get picked up where this day ends.
    // Moving where that is is not cancelling it.
    const withResupply = plan()
    withResupply.stops[2] = { ...withResupply.stops[2], resupply: true }
    const move = moveBoundary(withResupply, 2, 500)!

    expect(move.plan.stops[2].resupply).toBe(true)
  })

  it('drops a rest badge the move made untrue', () => {
    // #1031's rule, which every mutator that changes a day's distance has to
    // keep: the flag is a claim about a distance, and this changes distances.
    const withRest: HikePlan = (() => {
      const p = plan()
      return { ...p, days: p.days.map((d, i) => (i === 2 ? { ...d, rest: true } : d)) }
    })()

    // Day 2 runs 503.3 → 516.1 (12.8 mi) and is already too long to be a
    // nearo, so the fixture pins the flag first and the move must clear it.
    expect(withRest.days[2].rest).toBe(true)
    const move = moveBoundary(withRest, 2, 495)!
    expect(move.plan.days[2].rest).toBeUndefined()
  })

  it('leaves a plan that still validates, whatever the drag', () => {
    let p = plan()
    for (const [at, mile] of [
      [1, 480],
      [2, 500],
      [3, 505],
      [2, 481],
    ] as const) {
      const move = moveBoundary(p, at, mile)
      if (move !== null) p = move.plan
    }
    expect(validatePlan(p)).not.toBeNull()
    // Dates untouched: a boundary move changes miles, never the calendar.
    expect(planDayViews(p).map((d) => d.date)).toEqual([
      '2026-05-12',
      '2026-05-13',
      '2026-05-14',
      '2026-05-15',
    ])
  })
})

describe('a zero freezes the boundaries around it', () => {
  /** Damascus → Lost Mountain, a zero there, then on to Atkins. */
  function withZero(): HikePlan {
    return buildPlan(
      [
        stop(470.8, 'Damascus'),
        stop(486.2, 'Lost Mountain Shelter'),
        stop(486.2, 'Lost Mountain Shelter'),
        stop(503.3, 'Atkins'),
      ],
      { miles: 15 },
    )
  }

  it('fixes both edges of a zero, because moving either one un-zeros it', () => {
    const p = withZero()
    expect(boundaryState(p, 1)).toEqual({ movable: false, why: 'zero' })
    expect(boundaryState(p, 2)).toEqual({ movable: false, why: 'zero' })
  })

  it('refuses the move outright rather than half-applying it', () => {
    const p = withZero()
    expect(moveBoundary(p, 1, 480)).toBeNull()
    expect(moveBoundary(p, 2, 495)).toBeNull()
  })

  it('still draws them, because a hiker needs to see where their days end', () => {
    const boundaries = planBoundaries(withZero())
    expect(boundaries).toHaveLength(4)
    expect(boundaries.map((b) => b.movable)).toEqual([false, false, false, false])
    expect(boundaries[1].why).toBe('zero')
  })
})

describe('why a fixed boundary is fixed', () => {
  it('says which absence it is, and what would change it', () => {
    // #1049's lesson on this surface: a dashed line that says only "not this
    // one" sends a hiker looking for a fix that does not exist. Three of the
    // four are states somebody can undo, so each one names the way out.
    const p = plan()
    const reason = (candidate: HikePlan, at: number) =>
      planBoundaries(candidate)[at].fixedReason

    expect(reason(p, 0)).toMatch(/starts and ends/)
    expect(reason(callItADay(p, 0, { mile: 486.2 }), 1)).toMatch(/record, not a plan/)
    expect(reason(togglePinned(p, 1), 1)).toMatch(/Unpin it/)
    // And a movable one claims no reason at all.
    expect(planBoundaries(p)[2].fixedReason).toBeUndefined()
  })
})
