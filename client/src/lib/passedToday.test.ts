import { describe, it, expect, beforeEach } from 'vitest'
import {
  advanceToday,
  emptyDay,
  localDay,
  passedPlaces,
  readPassedToday,
  writePassedToday,
  PASSED_TODAY_STORAGE_KEY,
} from './passedToday'
import { MAX_FIX_GAP_MILES } from './walkedMiles'
import { NOTE_SCOPED_TYPES } from './fieldNotes'

// The Volunteer tab's "places you passed today" record (#759,
// DATA_NUDGES.md's fourth surface). The privacy posture is walkedMiles.ts's,
// held to: merged intervals plus ONE local date - no fixes, no timestamps,
// no ordering - so the record cannot be replayed into a route.

const NOON = new Date('2026-08-20T12:00:00')

describe('advanceToday', () => {
  it('records a walked step into today', () => {
    const record = advanceToday(null, NOON, 100.0, 100.3)

    expect(record.day).toBe(localDay(NOON))
    expect(record.ranges).toEqual([{ startMile: 100.0, endMile: 100.3 }])
  })

  it('applies the same half-mile gate as the durable record - one gate, one home', () => {
    const record = advanceToday(null, NOON, 100.0, 100.0 + MAX_FIX_GAP_MILES + 0.1)

    expect(record.ranges).toEqual([])
  })

  it('resets itself on the first step after local midnight', () => {
    const yesterday = advanceToday(null, new Date('2026-08-19T23:50:00'), 99.0, 99.2)
    const today = advanceToday(yesterday, new Date('2026-08-20T06:10:00'), 99.2, 99.4)

    // Yesterday's walking stops claiming to be today's; only the fresh step
    // survives the day boundary.
    expect(today.day).toBe('2026-08-20')
    expect(today.ranges).toEqual([{ startMile: 99.2, endMile: 99.4 }])
  })

  it('merges touching steps rather than growing without bound', () => {
    let record = advanceToday(null, NOON, 100.0, 100.2)
    record = advanceToday(record, NOON, 100.2, 100.4)

    expect(record.ranges).toEqual([{ startMile: 100.0, endMile: 100.4 }])
  })
})

describe('storage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('round-trips today and reads another day as empty', () => {
    writePassedToday(advanceToday(null, NOON, 100.0, 100.3))

    expect(readPassedToday(NOON).ranges).toEqual([{ startMile: 100.0, endMile: 100.3 }])
    // The morning after, the stored record is yesterday's and reads as empty
    // rather than as today's - the list must not open on a stale day.
    expect(readPassedToday(new Date('2026-08-21T07:00:00')).ranges).toEqual([])
  })

  it('reads garbage as an empty day rather than throwing', () => {
    localStorage.setItem(PASSED_TODAY_STORAGE_KEY, '{"day": 3, "ranges": "no"}')

    expect(readPassedToday(NOON)).toEqual(emptyDay(NOON))
  })
})

describe('passedPlaces', () => {
  const POIS = [
    { id: 'w1', name: 'Spring', type: 'water', mile: 100.1 },
    { id: 's1', name: 'Shelter', type: 'shelter', mile: 100.25 },
    { id: 'v1', name: 'Vista', type: 'viewpoint', mile: 100.2 },
    { id: 'w2', name: 'Far spring', type: 'water', mile: 140.0 },
    { id: 'w3', name: 'No-mile spring', type: 'water' },
  ]

  it('lists the scoped places inside the walked miles, in trail order', () => {
    const ranges = [{ startMile: 100.0, endMile: 100.3 }]

    const places = passedPlaces(ranges, POIS, NOTE_SCOPED_TYPES)

    // The vista is walked past too, and deliberately not listed: a viewpoint
    // with no data is not a gap (DATA_NUDGES.md's scoping).
    expect(places.map((place) => place.id)).toEqual(['w1', 's1'])
  })

  it('lists nothing when nothing was walked', () => {
    expect(passedPlaces([], POIS, NOTE_SCOPED_TYPES)).toEqual([])
  })
})

describe('costing nothing when nothing was passed (#1090)', () => {
  // walkedMiles.ts's identity rule, kept by the wrapper around it. This record
  // is React state too, with its own persisting effect, so a fresh object on an
  // unchanged step is the second of the two `localStorage` writes a jittering
  // fix used to pay for.

  it('hands back the record it was given when the step adds nothing', () => {
    const now = new Date('2026-08-27T12:00:00')
    const current = { day: localDay(now), ranges: [{ startMile: 940, endMile: 941 }] }

    expect(advanceToday(current, now, 940.2, 940.6)).toBe(current)
  })

  it('hands it back when the pair is too far apart to be walking', () => {
    const now = new Date('2026-08-27T12:00:00')
    const current = { day: localDay(now), ranges: [{ startMile: 940, endMile: 941 }] }

    expect(advanceToday(current, now, 940, 940 + MAX_FIX_GAP_MILES + 0.1)).toBe(current)
  })

  it('still turns the day over on the first step after midnight', () => {
    // The identity check is "the day has not turned AND the step added
    // nothing". A record from yesterday has to be replaced whatever the step
    // did, or a hiker's "places you passed today" would still be yesterday's at
    // breakfast - and the step itself is measured against the NEW day's empty
    // record, so ground they walked yesterday is ground they have walked again.
    const yesterday = { day: '2026-08-26', ranges: [{ startMile: 940, endMile: 941 }] }
    const now = new Date('2026-08-27T07:00:00')

    const next = advanceToday(yesterday, now, 940.2, 940.6)

    expect(next).not.toBe(yesterday)
    expect(next).toEqual({
      day: localDay(now),
      ranges: [{ startMile: 940.2, endMile: 940.6 }],
    })
  })

  it('still records new ground', () => {
    const now = new Date('2026-08-27T12:00:00')
    const current = { day: localDay(now), ranges: [{ startMile: 940, endMile: 941 }] }

    const next = advanceToday(current, now, 940.9, 941.3)

    expect(next).not.toBe(current)
    expect(next.ranges).toEqual([{ startMile: 940, endMile: 941.3 }])
  })
})
