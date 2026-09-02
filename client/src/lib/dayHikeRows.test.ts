// Tests for lib/dayHikeRows.ts - the builder panel's route order (#1194).
//
// What is worth pinning here is mostly about what a row may CLAIM:
//
//   A LEG'S MILE RANGE IS CONTINUOUS AND CUMULATIVE, so the list reads as one
//   walk rather than as a set of trails each starting at zero.
//
//   A STOP GOES AFTER THE LEG THAT REACHED IT. A hiker reads the list as a
//   sequence of things that happen, and a shelter listed before the trail
//   that gets there is a lie about the order of the day.
//
//   NO STOP IS EVER DROPPED. The vertex-nearest projection can put a stop a
//   hair past the last leg's end, and a row that silently vanished would be
//   the app forgetting something the hiker chose.

import { describe, expect, it } from 'vitest'

import { routeRows, turnCount, turnMarks } from './dayHikeRows'
import type { DayHikeStop } from './dayHikeStops'
import type { DayHikeDraft } from './dayHikeDraft'
import type { GraphPoint, RouteLeg } from './trailGraph'

function leg(name: string, miles: number, blaze: string | null = 'blue'): RouteLeg {
  return {
    name,
    source: 'oprhp_trails',
    blaze_color: blaze,
    trail_id: `oprhp_trails:${name}`,
    miles,
  }
}

function stop(poiId: string, mile: number, type = 'shelter'): DayHikeStop {
  return {
    poiId,
    type,
    name: `${poiId} shelter`,
    lat: 41.25,
    lon: -74.1,
    mile,
    offCourseFeet: 120,
  }
}

/** A tap - only its identity matters to `turnMarks`. */
function tap(): GraphPoint {
  return {
    edgeIndex: 0,
    fraction: 0.5,
    at: { lon: -74.1, lat: 41.25 },
    offNetworkFeet: 0,
  }
}

function draftOf(stretches: number[]): DayHikeDraft {
  return {
    segments: stretches.map((count) => Array.from({ length: count }, tap)),
    refusal: null,
    looped: false,
    droppedMiles: 0,
  }
}

describe('the leg rows', () => {
  it('numbers them continuously from one', () => {
    const rows = routeRows([leg('A', 1), leg('B', 2), leg('C', 0.5)], [])

    expect(rows.map((row) => (row.kind === 'leg' ? row.index : null))).toEqual([1, 2, 3])
  })

  it('gives each one a cumulative mile range, so the list is one walk', () => {
    const rows = routeRows([leg('A', 1), leg('B', 2)], [])
    const legs = rows.filter((row) => row.kind === 'leg')

    expect(legs[0].fromMile).toBe(0)
    expect(legs[0].toMile).toBe(1)
    // NOT 0-2: the second leg starts where the first ended.
    expect(legs[1].fromMile).toBe(1)
    expect(legs[1].toMile).toBe(3)
  })

  it('carries the blaze through, including its absence', () => {
    const rows = routeRows([leg('A', 1, null)], [])
    const [first] = rows

    expect(first.kind === 'leg' && first.blazeColor).toBeNull()
  })

  it('is empty for a walk with no legs and no stops', () => {
    expect(routeRows([], [])).toEqual([])
  })
})

describe('where a stop lands', () => {
  it('goes after the leg that reached it', () => {
    const rows = routeRows([leg('A', 1), leg('B', 2)], [stop('s', 0.5)])

    expect(rows.map((row) => row.kind)).toEqual(['leg', 'stop', 'leg'])
  })

  it('resolves a stop at a leg boundary onto the leg that arrived', () => {
    // A shelter at a junction reads as the end of the leg that reached it,
    // never as the start of the one leaving.
    const rows = routeRows([leg('A', 1), leg('B', 2)], [stop('s', 1)])

    expect(rows.map((row) => row.kind)).toEqual(['leg', 'stop', 'leg'])
  })

  it('keeps two stops in the order they were handed over', () => {
    const rows = routeRows(
      [leg('A', 1), leg('B', 2)],
      [stop('early', 0.2), stop('late', 2)],
    )
    const stops = rows.filter((row) => row.kind === 'stop')

    expect(stops.map((row) => row.stop.poiId)).toEqual(['early', 'late'])
  })

  it('never drops a stop projected past the end of the walk', () => {
    // The vertex-nearest approximation can land a hair beyond the last
    // vertex; the row must still appear.
    const rows = routeRows([leg('A', 1)], [stop('past', 99)])

    expect(rows.filter((row) => row.kind === 'stop')).toHaveLength(1)
  })

  it('lists stops even when nothing has routed yet', () => {
    // A hiker who tapped a shelter should see it acknowledged rather than
    // swallowed while the walk is still one tap long.
    const rows = routeRows([], [stop('s', 0)])

    expect(rows).toHaveLength(1)
    expect(rows[0].kind).toBe('stop')
  })

  it('gives every row a key of its own', () => {
    const rows = routeRows([leg('A', 1), leg('B', 2)], [stop('a', 0.5), stop('b', 2)])
    const keys = rows.map((row) => row.key)

    expect(new Set(keys).size).toBe(keys.length)
  })
})

describe('the turns', () => {
  it('numbers taps across the whole walk, gaps included', () => {
    // The numbering has to match the marks App.tsx puts on the map, which run
    // straight through a gap - restarting at 1 would say the second stretch
    // is a second hike.
    const marks = turnMarks(draftOf([2, 2]))

    expect(marks.map((mark) => mark.label)).toEqual([1, 2, 3, 4])
    expect(marks.map((mark) => mark.ordinal)).toEqual([0, 1, 2, 3])
  })

  it('flags the tap a gap starts after', () => {
    const marks = turnMarks(draftOf([2, 2]))

    expect(marks.map((mark) => mark.endsStretch)).toEqual([false, true, false, false])
  })

  it('never flags the last tap of the walk, which starts no gap', () => {
    const marks = turnMarks(draftOf([3]))

    expect(marks.every((mark) => !mark.endsStretch)).toBe(true)
  })

  it('counts the taps without building the array', () => {
    expect(turnCount(draftOf([2, 3]))).toBe(5)
    expect(turnCount(draftOf([0]))).toBe(0)
  })
})
