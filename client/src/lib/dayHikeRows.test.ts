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
//
//   AND NEITHER IS A GAP (#1220). Ground the router declined to bridge is the
//   part of a walk nobody maintains, so a list that omitted it would read as
//   one continuous routed walk and understate what the hiker is taking on.

import { describe, expect, it } from 'vitest'

import { routeRows, turnCount, turnMarks } from './dayHikeRows'
import type { DayHikeStop } from './dayHikeStops'
import { draftStatus, tapAt, EMPTY_DRAFT, type DayHikeDraft } from './dayHikeDraft'
import {
  buildGraphIndex,
  type GraphPoint,
  type RouteLeg,
  type TrailGraph,
} from './trailGraph'

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
    outAndBack: false,
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

describe('the gap rows', () => {
  it('crosses the gap after the leg it follows', () => {
    const rows = routeRows([leg('A', 1), leg('B', 2)], [], [{ afterLegs: 1, miles: 0.4 }])

    expect(rows.map((row) => row.kind)).toEqual(['leg', 'gap', 'leg'])
    expect(rows[1]).toEqual({ kind: 'gap', key: 'gap-0', miles: 0.4 })
  })

  it("crosses it after that leg's stops, not before them", () => {
    // A hiker reads the list as a sequence of things that happen: you walk the
    // leg, you are at the shelter, THEN you cross ground with no trail on it.
    const rows = routeRows(
      [leg('A', 1), leg('B', 2)],
      [stop('s', 0.5)],
      [{ afterLegs: 1, miles: 0.4 }],
    )

    expect(rows.map((row) => row.kind)).toEqual(['leg', 'stop', 'gap', 'leg'])
  })

  it('lists every gap of a three-stretch walk, each in its place', () => {
    const rows = routeRows(
      [leg('A', 1), leg('B', 2), leg('C', 0.5)],
      [],
      [
        { afterLegs: 1, miles: 0.4 },
        { afterLegs: 2, miles: 1.1 },
      ],
    )

    expect(rows.map((row) => row.kind)).toEqual(['leg', 'gap', 'leg', 'gap', 'leg'])
    expect(rows.flatMap((row) => (row.kind === 'gap' ? [row.miles] : []))).toEqual([
      0.4, 1.1,
    ])
  })

  it('still lists a gap the walk has no trail beyond yet', () => {
    // The hiker has tapped the first point of a new stretch. There is gap
    // ground and no leg past it, and saying nothing would be the omission this
    // whole block exists to prevent.
    const rows = routeRows([leg('A', 1)], [], [{ afterLegs: 1, miles: 0.4 }])

    expect(rows.map((row) => row.kind)).toEqual(['leg', 'gap'])
  })

  it('lists nothing extra for a walk with no gaps', () => {
    // The default, and the shape every caller had before gaps were threaded
    // through at all.
    expect(routeRows([leg('A', 1)], []).map((row) => row.kind)).toEqual(['leg'])
  })
})

describe('no two rows a reader cannot tell apart (#1433)', () => {
  // The maintainer's rule: the path carries no duplicate consecutive row where
  // neither the trail name nor the blaze changed.
  //
  // What produced them: `trail_id` is `f"{key}:{feature_id}"` - one per source
  // FEATURE - so the trail below is ONE trail its publisher drew as two lines,
  // and a leg used to end at the seam. The route order printed "Pine Meadow
  // Trail, blue" twice for one walk down one trail, each row holding half the
  // miles. The grouping rule now lives in `sameTrail`; this walks the whole
  // builder to prove the rows a hiker actually reads come out of it right.
  const SPLIT: TrailGraph = {
    nodes: [
      [-74.1, 41.25],
      [-74.09, 41.25],
      [-74.08, 41.25],
    ],
    edges: [
      {
        from: 0,
        to: 1,
        length_m: 836,
        trail_id: 'oprhp_trails:1',
        source: 'oprhp_trails',
        name: 'Pine Meadow Trail',
        blaze_color: 'blue',
        geometry: [
          [-74.1, 41.25],
          [-74.09, 41.25],
        ],
      },
      {
        // The next line the publisher drew of the same trail.
        from: 1,
        to: 2,
        length_m: 836,
        trail_id: 'oprhp_trails:2',
        source: 'oprhp_trails',
        name: 'Pine Meadow Trail',
        blaze_color: 'blue',
        geometry: [
          [-74.09, 41.25],
          [-74.08, 41.25],
        ],
      },
    ],
  }

  /** The whole trail, tapped end to end - two taps, two published lines. */
  function theWholeTrail() {
    const index = buildGraphIndex(SPLIT)
    const draft = tapAt(index, tapAt(index, EMPTY_DRAFT, { lon: -74.1, lat: 41.25 }), {
      lon: -74.08,
      lat: 41.25,
    })
    const status = draftStatus(index, draft)
    if (status.kind !== 'routed') throw new Error('fixture should route')
    return status
  }

  it('lists the trail once, with the whole walk on it', () => {
    const status = theWholeTrail()
    const rows = routeRows(status.legs, [], status.gaps)
    const legs = rows.filter((row) => row.kind === 'leg')

    expect(legs).toHaveLength(1)
    expect(legs[0].name).toBe('Pine Meadow Trail')
    // And the row carries both lines' miles. One row holding half the walk
    // would be a quieter version of the same defect.
    expect(legs[0].fromMile).toBe(0)
    expect(legs[0].miles).toBeCloseTo(status.miles, 6)
  })

  it('agrees with the leg count printed beside it', () => {
    // chrome/DayHikePanel.tsx's summary and chrome/DayHikePickBar.tsx's `N
    // legs · org · N legs` read this same list, on screen with the rows.
    const status = theWholeTrail()

    expect(status.legs).toHaveLength(1)
    expect(status.legsBySource).toEqual([{ source: 'oprhp_trails', legs: 1 }])
  })

  // THE OTHER HALF OF THE RULE (the maintainer, 2026-09-15): the squash is for
  // the lines a publisher drew, not for the points a hiker placed. Same
  // fixture, one more tap - partway along the FIRST line, so what splits the
  // walk can only be the tap and not the seam.
  /** The same trail, with a point tapped halfway along the first line. */
  function withAPointInTheMiddle() {
    const index = buildGraphIndex(SPLIT)
    let draft = tapAt(index, EMPTY_DRAFT, { lon: -74.1, lat: 41.25 })
    draft = tapAt(index, draft, { lon: -74.095, lat: 41.25 })
    draft = tapAt(index, draft, { lon: -74.08, lat: 41.25 })
    const status = draftStatus(index, draft)
    if (status.kind !== 'routed') throw new Error('fixture should route')
    return status
  }

  it('keeps a row either side of a point the hiker placed', () => {
    const status = withAPointInTheMiddle()
    const legs = routeRows(status.legs, [], status.gaps).filter(
      (row) => row.kind === 'leg',
    )

    expect(legs).toHaveLength(2)
    expect(legs.map((row) => row.name)).toEqual([
      'Pine Meadow Trail',
      'Pine Meadow Trail',
    ])
  })

  it('splits at the hiker’s point, not at the publisher’s seam', () => {
    // The sharpest statement of the pair of rules, because the two candidate
    // boundaries are at different distances and only one of them is taken.
    // The tap is 418 m in; the seam between the two drawn lines is 836 m in.
    // A walk split at the seam would read 0.52 / 0.52; split at the tap it
    // reads 0.26 / 0.78, and the second row holds the rest of line one plus
    // the whole of line two.
    const status = withAPointInTheMiddle()
    const legs = routeRows(status.legs, [], status.gaps).filter(
      (row) => row.kind === 'leg',
    )

    expect(legs[0].miles).toBeCloseTo(418 / 1609.344, 4)
    expect(legs[1].miles).toBeCloseTo((418 + 836) / 1609.344, 4)
  })

  it('runs one mile axis through both rows, with no gap and no overlap', () => {
    // A row's `fromMile`/`toMile` is what the panel prints as
    // "mile 0.3–0.8". Two rows of one trail either side of a tap have to read
    // as one continuous walk, or the split has invented a discontinuity the
    // hiker did not walk.
    const status = withAPointInTheMiddle()
    const legs = routeRows(status.legs, [], status.gaps).filter(
      (row) => row.kind === 'leg',
    )

    expect(legs.map((row) => row.index)).toEqual([1, 2])
    expect(legs[0].fromMile).toBe(0)
    expect(legs[0].toMile).toBeCloseTo(legs[1].fromMile, 6)
    expect(legs[1].toMile).toBeCloseTo(status.miles, 6)
  })

  it('still counts one steward, on the walk the tap made two legs of', () => {
    const status = withAPointInTheMiddle()

    expect(status.legs).toHaveLength(2)
    expect(status.legsBySource).toEqual([{ source: 'oprhp_trails', legs: 2 }])
  })

  // AND THE ROW THAT MAKES THE TWO LEGIBLE. Two rows naming one trail are
  // only readable if the thing dividing them is on the screen between them,
  // which is why the taps moved into this list rather than staying beside it.
  it('puts the hiker\u2019s tap between the two rows it divides', () => {
    const status = withAPointInTheMiddle()
    const rows = routeRows(status.legs, [], status.gaps, status.turns)

    expect(rows.map((row) => row.kind)).toEqual(['turn', 'leg', 'turn', 'leg', 'turn'])
  })

  it('gives the tap the mile of the boundary it makes', () => {
    // The arithmetic that was impossible before the squash stopped at a tap:
    // the middle tap sits at the end of row 1, and the last at the end of the
    // walk. Nothing here is re-routed to find them.
    const status = withAPointInTheMiddle()
    const rows = routeRows(status.legs, [], status.gaps, status.turns)
    const turns = rows.filter((row) => row.kind === 'turn')
    const legs = rows.filter((row) => row.kind === 'leg')

    expect(turns.map((row) => row.mile)).toEqual([0, legs[0].toMile, legs[1].toMile])
    expect(turns[2].mile).toBeCloseTo(status.miles, 6)
  })

  it('numbers a tap as the map numbers it, and deletes by ordinal', () => {
    // The label a hiker matches against the mark on the map, and the ordinal
    // `removeTap` indexes `draftPoints` with. They differ by one, and a row
    // that confused them would delete somebody else's point.
    const status = withAPointInTheMiddle()
    const turns = routeRows(status.legs, [], status.gaps, status.turns).filter(
      (row) => row.kind === 'turn',
    )

    expect(turns.map((row) => row.label)).toEqual([1, 2, 3])
    expect(turns.map((row) => row.ordinal)).toEqual([0, 1, 2])
  })

  it('lists every tap, so none of them is undeletable', () => {
    // The first and the last included. They divide nothing - they bracket the
    // walk - but the list carries the only delete control there is, so a tap
    // missing from it is a tap a hiker cannot take back.
    const status = withAPointInTheMiddle()
    const turns = routeRows(status.legs, [], status.gaps, status.turns).filter(
      (row) => row.kind === 'turn',
    )

    expect(turns).toHaveLength(3)
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
