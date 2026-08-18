// Tests for hikes.ts (#788).
//
// The load-bearing ones are in `resolvePlace`: they are what decides
// whether a hike opened in 2026 still describes the same ground in 2031,
// which is the whole reason the ends are references rather than miles.

import { describe, expect, it } from 'vitest'

import {
  clipSpans,
  gapSpans,
  hikeBounds,
  hikeFigures,
  hikePieces,
  recordedPlan,
  hikeFromTrips,
  hikeOfTrip,
  mergeSpans,
  resolvePlace,
  spanFraction,
  spanLength,
  tripSpan,
  validateHike,
  walkedSpans,
  type Hike,
} from './hikes'
import { buildPlan, type HikePlan } from './plan'
import type { StoredPoi } from './trailData'
import type { Trip } from './trips'

const poi = (id: string, name: string, mile: number | undefined): StoredPoi => ({
  id,
  type: 'shelter',
  name,
  lat: 0,
  lon: 0,
  confidence: 'high',
  ...(mile === undefined ? {} : { mile }),
})

/** The download as it stands today: Damascus has been re-measured 0.4 mi
 *  further along since the hike was written. */
const POIS = [
  poi('damascus', 'Damascus', 471.2),
  poi('atkins', 'Atkins', 503.3),
  poi('nomile', 'Pre-#753 Shelter', undefined),
]

describe('resolvePlace - why the ends are references', () => {
  it('uses the POI’s CURRENT mile, not the mile that was stored', () => {
    // The hike was written when Damascus published as 470.8. A relocation
    // moved it. The reference still names the same place, so the resolved
    // mile is today's - which is the entire point of storing a reference.
    const resolved = resolvePlace(
      { poiId: 'damascus', name: 'Damascus', mile: 470.8 },
      POIS,
    )

    expect(resolved.mile).toBe(471.2)
    expect(resolved.from).toBe('reference')
    expect(resolved.movedMi).toBeCloseTo(0.4)
    expect(resolved.name).toBe('Damascus')
  })

  it('reports no movement when the published mile has not moved', () => {
    const resolved = resolvePlace({ poiId: 'atkins', mile: 503.3 }, POIS)

    expect(resolved.mile).toBe(503.3)
    expect(resolved.movedMi).toBe(0)
  })

  it('says a dropped point is a dropped point', () => {
    // No reference was ever recorded, so its mile is all there has ever
    // been. Honest, and not drift-proof - and it says which it is.
    const resolved = resolvePlace({ mile: 486.2 }, POIS)

    expect(resolved.mile).toBe(486.2)
    expect(resolved.from).toBe('stored')
    expect(resolved.movedMi).toBeNull()
  })

  it('falls back to the hint when the reference is gone, and SAYS so', () => {
    // The open question this issue names: a POI removed or merged away by a
    // later release. The cached mile is used because there is nothing else,
    // and `from` is what the screen reads to admit it.
    const resolved = resolvePlace(
      { poiId: 'demolished', name: 'Old Shelter', mile: 490.1 },
      POIS,
    )

    expect(resolved.mile).toBe(490.1)
    expect(resolved.from).toBe('missing')
    expect(resolved.name).toBe('Old Shelter')
  })

  it('treats a POI without a published mile as missing too', () => {
    // A pre-#753 download has the POI but no mile to resolve against, which
    // leaves the hint load-bearing in exactly the same way.
    expect(resolvePlace({ poiId: 'nomile', mile: 12.0 }, POIS).from).toBe('missing')
  })
})

describe('validateHike', () => {
  const good: Hike = {
    id: 'h1',
    name: 'Appalachian Trail',
    type: 'thru',
    start: { poiId: 'damascus', mile: 470.8 },
    end: { mile: 2197.4 },
    tripIds: ['a'],
  }

  it('accepts a hike, keeping both ends', () => {
    const validated = validateHike(good)
    expect(validated?.start.poiId).toBe('damascus')
    expect(validated?.end.mile).toBe(2197.4)
  })

  it('refuses what cannot be a hike', () => {
    expect(validateHike(null)).toBeNull()
    expect(validateHike({ ...good, type: 'expedition' })).toBeNull()
    expect(validateHike({ ...good, start: { mile: -3 } })).toBeNull()
    expect(validateHike({ ...good, end: undefined })).toBeNull()
    expect(validateHike({ ...good, id: '' })).toBeNull()
  })
})

describe('spans', () => {
  it('records only walked days, and never a zero', () => {
    const plan = buildPlan(
      [
        { mile: 10, resupply: false },
        { mile: 20, resupply: false },
        { mile: 20, resupply: false },
        { mile: 32, resupply: false },
      ],
      { miles: 12 },
    )
    plan.days[0].walked = true
    plan.days[1].walked = true // the zero: walked, but no ground covered

    expect(walkedSpans(plan)).toEqual([{ from: 10, to: 20 }])
  })

  it('merges rather than sums, so a re-walked mile counts once', () => {
    // A hiker who walked Georgia twice has not walked twice the trail.
    const merged = mergeSpans([
      { from: 0, to: 30 },
      { from: 20, to: 50 },
      { from: 80, to: 90 },
    ])
    expect(merged).toEqual([
      { from: 0, to: 50 },
      { from: 80, to: 90 },
    ])
    expect(spanLength(merged)).toBe(60)
  })

  it('clips to the hike, so a trip past its ends does not lengthen it', () => {
    expect(clipSpans([{ from: 0, to: 100 }], { from: 20, to: 60 })).toEqual([
      { from: 20, to: 60 },
    ])
    expect(clipSpans([{ from: 0, to: 10 }], { from: 20, to: 60 })).toEqual([])
  })
})

describe('hikeFigures', () => {
  function trip(id: string, from: number, to: number, walked: boolean): Trip {
    const plan: HikePlan = buildPlan(
      [
        { mile: from, resupply: false },
        { mile: to, resupply: false },
      ],
      { miles: 15 },
    )
    if (walked) plan.days[0].walked = true
    return { id, name: id, plan }
  }

  const hike: Hike = {
    id: 'h1',
    name: 'Virginia',
    type: 'section',
    start: { mile: 0 },
    end: { mile: 100 },
    tripIds: ['a', 'b'],
  }

  it('counts walked miles as a union, and leaves the rest', () => {
    const trips = [trip('a', 0, 30, true), trip('b', 20, 50, true)]
    const figures = hikeFigures(hike, trips, POIS)

    expect(figures.totalMi).toBe(100)
    expect(figures.walkedMi).toBe(50) // not 60 - the overlap counts once
    expect(figures.leftMi).toBe(50)
    expect(figures.daysWalked).toBe(2)
    expect(figures.tripCount).toBe(2)
  })

  it('does not count a planned trip as walked', () => {
    // A trip on the calendar closes no gap until it happens.
    const figures = hikeFigures(hike, [trip('a', 0, 30, false)], POIS)

    expect(figures.walkedMi).toBe(0)
    expect(figures.leftMi).toBe(100)
    expect(figures.tripCount).toBe(1)
  })

  it('ignores trips that belong to another hike', () => {
    const figures = hikeFigures(
      { ...hike, tripIds: ['a'] },
      [trip('a', 0, 30, true), trip('b', 30, 60, true)],
      POIS,
    )
    expect(figures.walkedMi).toBe(30)
  })

  it('flags figures resting on a reference this download has lost', () => {
    const stranded: Hike = { ...hike, start: { poiId: 'demolished', mile: 0 } }
    expect(hikeFigures(stranded, [], POIS).uncertain).toBe(true)
    expect(hikeFigures(hike, [], POIS).uncertain).toBe(false)
  })

  it('moves with the reference, so a relocation does not silently resize a hike', () => {
    const anchored: Hike = {
      ...hike,
      start: { poiId: 'damascus', mile: 470.8 },
      end: { poiId: 'atkins', mile: 503.3 },
      tripIds: [],
    }
    // 471.2 → 503.3 today, not the 32.5 the stored hints would have given.
    expect(hikeFigures(anchored, [], POIS).totalMi).toBeCloseTo(32.1)
  })
})

describe('hikeFromTrips', () => {
  function trip(id: string, from: number, to: number): Trip {
    return {
      id,
      name: id,
      plan: buildPlan(
        [
          { mile: from, name: 'Damascus', poiId: 'damascus', resupply: false },
          { mile: to, name: 'Atkins', poiId: 'atkins', resupply: false },
        ],
        { miles: 15 },
      ),
    }
  }

  it('spans the outermost stops, carrying their references across', () => {
    const hike = hikeFromTrips([trip('a', 470.8, 503.3), trip('b', 520, 560)], 'Virginia')

    expect(hike?.start.mile).toBe(470.8)
    expect(hike?.start.poiId).toBe('damascus')
    expect(hike?.end.mile).toBe(560)
    expect(hike?.tripIds).toEqual(['a', 'b'])
    expect(hike?.type).toBe('section')
  })

  it('refuses to make a hike out of no ground', () => {
    expect(hikeFromTrips([], 'Nothing')).toBeNull()
  })
})

describe('hikeOfTrip', () => {
  it('finds the one hike holding a trip, or null', () => {
    const hikes: Hike[] = [
      {
        id: 'h1',
        name: 'One',
        type: 'section',
        start: { mile: 0 },
        end: { mile: 10 },
        tripIds: ['a'],
      },
    ]
    expect(hikeOfTrip(hikes, 'a')?.id).toBe('h1')
    expect(hikeOfTrip(hikes, 'b')).toBeNull()
  })
})

describe('recordedPlan - ground already walked (#789)', () => {
  it('arrives walked, and nobody generated it', () => {
    const plan = recordedPlan([
      { mile: 0, name: 'Springer', resupply: false },
      { mile: 470.8, name: 'Damascus', resupply: false },
    ])

    expect(plan.days).toHaveLength(1)
    expect(plan.days[0].walked).toBe(true)
    expect(plan.days[0].generated).toBe(false)
    expect(walkedSpans(plan)).toEqual([{ from: 0, to: 470.8 }])
  })

  it('keeps every boundary the hiker could remember', () => {
    // More detail when they have it: three stops record two walked
    // stretches rather than flattening to one.
    const plan = recordedPlan([
      { mile: 0, resupply: false },
      { mile: 165.7, resupply: false },
      { mile: 470.8, resupply: false },
    ])

    expect(walkedSpans(plan)).toEqual([
      { from: 0, to: 165.7 },
      { from: 165.7, to: 470.8 },
    ])
  })

  it('takes a date when there is one to give', () => {
    const plan = recordedPlan(
      [
        { mile: 0, resupply: false },
        { mile: 10, resupply: false },
      ],
      '2019-06-01',
    )
    expect(plan.days[0].date).toBe('2019-06-01')
  })

  it('counts once where a recorded stretch overlaps a walked trip', () => {
    // The open question #789 raised, settled by the union rather than by
    // whichever loop ran first: a hiker who recorded Georgia AND walked
    // part of it again has not walked more trail than exists.
    const recorded: Trip = {
      id: 'r',
      name: 'From memory',
      recorded: true,
      plan: recordedPlan([
        { mile: 0, resupply: false },
        { mile: 100, resupply: false },
      ]),
    }
    const walkedAgain: HikePlan = buildPlan(
      [
        { mile: 60, resupply: false },
        { mile: 140, resupply: false },
      ],
      { miles: 15 },
    )
    walkedAgain.days[0].walked = true

    const hike: Hike = {
      id: 'h',
      name: 'Overlapping',
      type: 'section',
      start: { mile: 0 },
      end: { mile: 200 },
      tripIds: ['r', 'w'],
    }
    const figures = hikeFigures(
      hike,
      [recorded, { id: 'w', name: 'Again', plan: walkedAgain }],
      [],
    )

    expect(figures.walkedMi).toBe(140) // not 180
    expect(figures.leftMi).toBe(60)
  })
})

describe('gapSpans - what is left, and where (#790)', () => {
  function trip(id: string, from: number, to: number, walked: boolean): Trip {
    const plan: HikePlan = buildPlan(
      [
        { mile: from, resupply: false },
        { mile: to, resupply: false },
      ],
      { miles: 15 },
    )
    if (walked) plan.days[0].walked = true
    return { id, name: id, plan }
  }

  const hike: Hike = {
    id: 'h1',
    name: 'Virginia',
    type: 'section',
    start: { mile: 0 },
    end: { mile: 100 },
    tripIds: ['a', 'b'],
  }

  it('is the complement of the walked ground, in trail order', () => {
    const gaps = gapSpans(hike, [trip('a', 10, 30, true), trip('b', 60, 80, true)], POIS)

    expect(gaps).toEqual([
      { from: 0, to: 10 },
      { from: 30, to: 60 },
      { from: 80, to: 100 },
    ])
  })

  it('is the whole hike when nothing has been walked', () => {
    expect(gapSpans(hike, [], POIS)).toEqual([{ from: 0, to: 100 }])
  })

  it('is nothing at all when the hike is finished', () => {
    // The only honest way to say "done": no gaps left to draw. Not a
    // percentage, not a badge - the rows simply run out.
    expect(gapSpans(hike, [trip('a', 0, 100, true)], POIS)).toEqual([])
  })

  it('does not let a PLANNED trip close a gap', () => {
    // The distinction the whole screen turns on: an intention is not a
    // record, and a hiker looking at what is left must see ground they have
    // not walked even where they have already booked the shuttle.
    const gaps = gapSpans(hike, [trip('a', 10, 30, false)], POIS)
    expect(gaps).toEqual([{ from: 0, to: 100 }])
  })

  it('does not let a trip past the ends shrink the hike', () => {
    const gaps = gapSpans(hike, [trip('a', -50, 20, true)], POIS)
    expect(gaps).toEqual([{ from: 20, to: 100 }])
  })

  it('drops slivers too short to be anything but arithmetic', () => {
    // Two trips that meet 0.05 mi apart left a gap nobody skipped.
    const gaps = gapSpans(
      hike,
      [trip('a', 0, 49.95, true), trip('b', 50, 100, true)],
      POIS,
    )
    expect(gaps).toEqual([])

    // A tenth of a mile more and it is a real, if short, piece of trail.
    expect(
      gapSpans(hike, [trip('a', 0, 49.5, true), trip('b', 50, 100, true)], POIS),
    ).toEqual([{ from: 49.5, to: 50 }])
  })

  it('ignores trips belonging to another hike', () => {
    const gaps = gapSpans({ ...hike, tripIds: ['a'] }, [trip('b', 0, 100, true)], POIS)
    expect(gaps).toEqual([{ from: 0, to: 100 }])
  })

  it('follows the references, so a relocation moves the gap with the hike', () => {
    const anchored: Hike = {
      ...hike,
      start: { poiId: 'damascus', mile: 470.8 },
      end: { poiId: 'atkins', mile: 503.3 },
      tripIds: [],
    }
    // Damascus publishes at 471.2 today, not the 470.8 that was cached.
    expect(gapSpans(anchored, [], POIS)).toEqual([{ from: 471.2, to: 503.3 }])
  })
})

describe('tripSpan', () => {
  it('spans the outermost stops, planned or walked', () => {
    const plan = buildPlan(
      [
        { mile: 30, resupply: false },
        { mile: 10, resupply: false },
        { mile: 20, resupply: false },
      ],
      { miles: 15 },
    )
    expect(tripSpan({ id: 't', name: 't', plan })).toEqual({ from: 10, to: 30 })
  })

  it('is null for a trip covering no ground', () => {
    const plan = buildPlan(
      [
        { mile: 10, resupply: false },
        { mile: 10, resupply: false },
      ],
      { miles: 15 },
    )
    expect(tripSpan({ id: 't', name: 't', plan })).toBeNull()
  })
})

describe('spanFraction', () => {
  const bounds = { from: 100, to: 200 }

  it('places a span as a fraction of the hike', () => {
    expect(spanFraction({ from: 125, to: 150 }, bounds)).toEqual({
      start: 0.25,
      length: 0.25,
    })
  })

  it('clamps a span that runs past the ends, rather than painting outside', () => {
    expect(spanFraction({ from: 0, to: 300 }, bounds)).toEqual({ start: 0, length: 1 })
    expect(spanFraction({ from: 0, to: 50 }, bounds)).toEqual({ start: 0, length: 0 })
  })

  it('refuses to divide by a hike with no length', () => {
    expect(spanFraction({ from: 0, to: 10 }, { from: 5, to: 5 })).toEqual({
      start: 0,
      length: 0,
    })
  })
})

describe('hikeBounds', () => {
  it('resolves both ends and orders them low to high', () => {
    const hike: Hike = {
      id: 'h',
      name: 'Backwards',
      type: 'section',
      start: { poiId: 'atkins', mile: 503.3 },
      end: { poiId: 'damascus', mile: 470.8 },
      tripIds: [],
    }
    expect(hikeBounds(hike, POIS)).toEqual({ from: 471.2, to: 503.3 })
  })
})

describe('hikePieces - a hike’s contents in trail order (#790)', () => {
  function trip(id: string, from: number, to: number, walked: boolean): Trip {
    const plan: HikePlan = buildPlan(
      [
        { mile: from, name: `Stop ${from}`, resupply: false },
        { mile: to, name: `Stop ${to}`, resupply: false },
      ],
      { miles: 15 },
    )
    if (walked) plan.days[0].walked = true
    return { id, name: id, plan }
  }

  const hike: Hike = {
    id: 'h1',
    name: 'Virginia',
    type: 'section',
    start: { name: 'Damascus', mile: 0 },
    end: { name: 'Rockfish Gap', mile: 100 },
    tripIds: ['a', 'b'],
  }

  it('interleaves trips and gaps, low mile first', () => {
    const pieces = hikePieces(
      hike,
      [trip('b', 60, 80, true), trip('a', 10, 30, true)],
      POIS,
    )

    expect(pieces.map((piece) => piece.kind)).toEqual([
      'gap',
      'trip',
      'gap',
      'trip',
      'gap',
    ])
    expect(pieces.map((piece) => piece.span.from)).toEqual([0, 10, 30, 60, 80])
  })

  it('names a gap’s ends from what the hike already knows', () => {
    const pieces = hikePieces(hike, [trip('a', 10, 30, true)], POIS)
    const gaps = pieces.filter((piece) => piece.kind === 'gap')

    // The hike's own end, then the stop the trip started at - as
    // references, so "plan this stretch" opens on the place the row named.
    expect(gaps[0]).toMatchObject({
      from: { name: 'Damascus', mile: 0 },
      to: { name: 'Stop 10', mile: 10 },
    })
    expect(gaps[1]).toMatchObject({
      from: { name: 'Stop 30', mile: 30 },
      to: { name: 'Rockfish Gap', mile: 100 },
    })
  })

  it('leaves a boundary nobody named as a bare mile rather than inventing a place', () => {
    const unnamed: Hike = { ...hike, start: { mile: 0 }, end: { mile: 100 } }
    const plan = buildPlan(
      [
        { mile: 10, resupply: false },
        { mile: 30, resupply: false },
      ],
      { miles: 15 },
    )
    plan.days[0].walked = true
    const pieces = hikePieces(unnamed, [{ id: 'a', name: 'a', plan }], POIS)
    const gaps = pieces.filter((piece) => piece.kind === 'gap')

    // No name anywhere to take, and none invented: the mile is all it has.
    expect(gaps[0]).toMatchObject({ from: { mile: 0 }, to: { mile: 10 } })
    expect(gaps[0].kind === 'gap' && gaps[0].from.name).toBeUndefined()
  })

  it('gives a planned trip a row of its own, not a gap row over the top of it', () => {
    // The rows partition the hike; the arithmetic does not. A trip on the
    // calendar still counts as ground to walk (`gapSpans`, `leftMi`), and
    // still gets its own row rather than being buried under a gap saying
    // the same ground twice.
    const pieces = hikePieces(hike, [trip('a', 10, 30, false)], POIS)

    expect(pieces.map((piece) => piece.kind)).toEqual(['gap', 'trip', 'gap'])
    expect(pieces.map((piece) => piece.span)).toEqual([
      { from: 0, to: 10 },
      { from: 10, to: 30 },
      { from: 30, to: 100 },
    ])
    // ...and the same trip closes none of what is left to walk.
    expect(spanLength(gapSpans(hike, [trip('a', 10, 30, false)], POIS))).toBe(100)
  })

  it('says whether a trip is walked, part walked, or only planned', () => {
    const part = buildPlan(
      [
        { mile: 10, resupply: false },
        { mile: 20, resupply: false },
        { mile: 30, resupply: false },
      ],
      { miles: 15 },
    )
    part.days[0].walked = true

    const pieces = hikePieces(
      { ...hike, tripIds: ['a', 'b', 'c'] },
      [
        trip('a', 10, 30, true),
        trip('b', 60, 80, false),
        { id: 'c', name: 'c', plan: part },
      ],
      POIS,
    )
    const states = pieces
      .filter((piece) => piece.kind === 'trip')
      .map((piece) => (piece.kind === 'trip' ? piece.state : null))

    // 'a' and 'c' cover the same ground; the walked one sorts first.
    expect(states).toEqual(['walked', 'part', 'planned'])
  })

  it('carries the walked parts of a part-walked trip', () => {
    const part = buildPlan(
      [
        { mile: 10, resupply: false },
        { mile: 20, resupply: false },
        { mile: 30, resupply: false },
      ],
      { miles: 15 },
    )
    part.days[1].walked = true

    const pieces = hikePieces(
      { ...hike, tripIds: ['c'] },
      [{ id: 'c', name: 'c', plan: part }],
      POIS,
    )
    const only = pieces.find((piece) => piece.kind === 'trip')

    expect(only?.kind === 'trip' && only.walked).toEqual([{ from: 20, to: 30 }])
  })

  it('clips a trip that wanders past the hike, and drops one entirely outside', () => {
    const pieces = hikePieces(
      { ...hike, tripIds: ['a', 'b'] },
      [trip('a', -20, 30, true), trip('b', 200, 260, true)],
      POIS,
    )

    expect(pieces.filter((piece) => piece.kind === 'trip')).toHaveLength(1)
    expect(pieces[0].span).toEqual({ from: 0, to: 30 })
  })

  it('drops a trip covering no ground rather than drawing a zero-width piece', () => {
    const nowhere = buildPlan(
      [
        { mile: 10, resupply: false },
        { mile: 10, resupply: false },
      ],
      { miles: 15 },
    )
    const pieces = hikePieces(
      { ...hike, tripIds: ['z'] },
      [{ id: 'z', name: 'z', plan: nowhere }],
      POIS,
    )

    expect(pieces).toEqual([
      {
        kind: 'gap',
        id: 'gap-0-100',
        span: { from: 0, to: 100 },
        from: { name: 'Damascus', mile: 0 },
        to: { name: 'Rockfish Gap', mile: 100 },
      },
    ])
  })
})
