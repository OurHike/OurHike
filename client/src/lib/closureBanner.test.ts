import { describe, it, expect } from 'vitest'
import {
  closureBanner,
  nearestClosure,
  nearestClosureBanner,
  closureReasonLabel,
  type Closure,
} from './closureBanner'

// WIREFRAMES.md §7's header banner: "Trail closed 1.4 mi ahead · Storm damage
// · mi 1,408.6 – 1,411.0".
//
// "Ahead" depends on which way you are walking, which is the part that is
// easy to get wrong. A NOBO hiker at mile 1,407 has a closure at 1,408.6
// ahead of them; a SOBO hiker at the same spot has already walked through it.
// Telling a southbounder about a closure behind them is noise, and worse,
// silently omitting the one actually in front of them is a real failure.

const CLOSURE = {
  id: 'c1',
  reason_type: 'storm_damage' as const,
  note: null,
  status: 'closed' as const,
  start_mile_marker: 1408.6,
  end_mile_marker: 1411.0,
}

describe('closureBanner', () => {
  it('warns a northbound hiker about a closure up-trail', () => {
    expect(closureBanner(CLOSURE, 1407.2, 'NOBO')).toBe(
      'Trail closed 1.4 mi ahead · Storm damage · mi 1,408.6 – 1,411.0',
    )
  })

  it('says nothing to a northbound hiker who has already passed it', () => {
    expect(closureBanner(CLOSURE, 1412.0, 'NOBO')).toBeNull()
  })

  it('warns a southbound hiker about a closure down-trail', () => {
    // Walking south from 1,412, the closure's far end (1,411.0) comes first.
    expect(closureBanner(CLOSURE, 1412.0, 'SOBO')).toBe(
      'Trail closed 1.0 mi ahead · Storm damage · mi 1,408.6 – 1,411.0',
    )
  })

  it('says nothing to a southbound hiker who has already passed it', () => {
    expect(closureBanner(CLOSURE, 1407.2, 'SOBO')).toBeNull()
  })

  it('warns while standing inside the closure, whichever way they face', () => {
    // "Here", not "0.0 mi ahead" - a distance pretending to be a place.
    expect(closureBanner(CLOSURE, 1409.5, 'NOBO')).toContain('Trail closed here')
    expect(closureBanner(CLOSURE, 1409.5, 'SOBO')).toContain('Trail closed here')
  })

  it('warns while standing inside even before a direction is known', () => {
    // Direction takes a quarter mile of walking to establish
    // (lib/hikeDirection.ts). A hiker who opens the app standing in a closed
    // section has not walked that quarter mile yet, and that first quarter
    // mile is exactly where the warning matters - gating "inside" on
    // direction kept the banner blank there.
    expect(closureBanner(CLOSURE, 1409.5, undefined)).toContain('Trail closed here')
  })

  it('stays silent about a closure merely nearby until a direction is known', () => {
    // Without a direction there is no "ahead". Guessing would warn half of
    // all hikers about the closure behind them - and stay silent about the
    // one in front.
    expect(closureBanner(CLOSURE, 1407.2, undefined)).toBeNull()
    expect(closureBanner(CLOSURE, 1412.0, undefined)).toBeNull()
  })

  it('reports the whole mile range, not just the near edge', () => {
    expect(closureBanner(CLOSURE, 1407.2, 'NOBO')).toContain('1,408.6 – 1,411.0')
  })

  it('says nothing about a closure that is open again', () => {
    const reopened = { ...CLOSURE, status: 'open' as const }

    expect(closureBanner(reopened, 1407.2, 'NOBO')).toBeNull()
  })

  it('still warns when a reroute exists - a reroute is not an all-clear', () => {
    const reroute = { ...CLOSURE, status: 'reroute_available' as const }

    expect(closureBanner(reroute, 1407.2, 'NOBO')).toContain('Trail closed')
  })
})

describe('closureReasonLabel', () => {
  it.each([
    ['storm_damage', 'Storm damage'],
    ['flooding', 'Flooding'],
    ['maintenance', 'Maintenance'],
    ['relocation', 'Trail relocation'],
  ] as const)('says %s in plain language', (reason, label) => {
    expect(closureReasonLabel(reason)).toBe(label)
  })

  it('falls back to plain "Closed" rather than printing a raw enum value', () => {
    expect(closureReasonLabel('other')).toBe('Closed')
  })
})

// --- Picking one closure out of many (#232) ------------------------------
//
// The header has room for one line. Which closure gets it is the whole
// question: the one two hundred miles north does not change what a hiker
// does next, and showing it instead of the one at mile 3 is worse than
// showing nothing.

const CLOSED = {
  reason_type: 'storm_damage' as const,
  note: null,
  status: 'closed' as const,
}

describe('nearestClosureBanner', () => {
  it('says nothing when the way ahead is clear', () => {
    const behind = { ...CLOSED, id: 'c1', start_mile_marker: 10, end_mile_marker: 11 }

    expect(nearestClosureBanner([behind], 100, 'NOBO')).toBeNull()
  })

  it('says nothing about an empty list', () => {
    expect(nearestClosureBanner([], 100, 'NOBO')).toBeNull()
  })

  it('picks the nearest of several ahead', () => {
    const near = { ...CLOSED, id: 'near', start_mile_marker: 105, end_mile_marker: 106 }
    const far = { ...CLOSED, id: 'far', start_mile_marker: 300, end_mile_marker: 301 }

    const banner = nearestClosureBanner([far, near], 100, 'NOBO')

    expect(banner).toContain('5.0 mi ahead')
  })

  it('prefers the closure being stood in over one further up', () => {
    // Zero distance, and it has to sort ahead of everything - a plain
    // subtraction would make "inside" negative and lose it entirely.
    const inside = {
      ...CLOSED,
      id: 'inside',
      start_mile_marker: 99,
      end_mile_marker: 101,
    }
    const ahead = { ...CLOSED, id: 'ahead', start_mile_marker: 102, end_mile_marker: 103 }

    const banner = nearestClosureBanner([inside, ahead], 100, 'NOBO')

    expect(banner).toContain('Trail closed here')
    expect(banner).toContain('mi 99.0 – 101.0')
  })

  it('warns about the closure being stood in even before a direction is known', () => {
    // The App used to gate the whole banner on a known direction, which takes
    // a quarter mile of walking (lib/hikeDirection.ts) - so a hiker opening
    // the app inside a closed section saw nothing for exactly the quarter
    // mile where it mattered most.
    const inside = {
      ...CLOSED,
      id: 'inside',
      start_mile_marker: 99,
      end_mile_marker: 101,
    }
    const ahead = { ...CLOSED, id: 'ahead', start_mile_marker: 102, end_mile_marker: 103 }

    const banner = nearestClosureBanner([inside, ahead], 100, undefined)

    expect(banner).toContain('Trail closed here')
    // And the one merely ahead stays quiet alone - "ahead" needs a direction.
    expect(nearestClosureBanner([ahead], 100, undefined)).toBeNull()
  })

  it('reads direction, not just distance', () => {
    // The same closure and the same standing mile. A NOBO hiker has it in
    // front of them; a SOBO hiker walked through it an hour ago. Getting
    // this backwards means silence about the one being walked into.
    const closure = { ...CLOSED, id: 'c', start_mile_marker: 105, end_mile_marker: 106 }

    expect(nearestClosureBanner([closure], 100, 'NOBO')).toContain('5.0 mi ahead')
    expect(nearestClosureBanner([closure], 100, 'SOBO')).toBeNull()
  })

  it('ignores a reopened closure even when it is the nearest thing', () => {
    const reopened = {
      ...CLOSED,
      id: 'r',
      status: 'open' as const,
      start_mile_marker: 101,
      end_mile_marker: 102,
    }
    const real = { ...CLOSED, id: 'real', start_mile_marker: 110, end_mile_marker: 111 }

    expect(nearestClosureBanner([reopened, real], 100, 'NOBO')).toContain('10.0 mi ahead')
  })

  it('still warns about a reroute - somewhere else to walk is not passable trail', () => {
    const reroute = {
      ...CLOSED,
      id: 'rr',
      status: 'reroute_available' as const,
      start_mile_marker: 105,
      end_mile_marker: 106,
    }

    expect(nearestClosureBanner([reroute], 100, 'NOBO')).toContain('5.0 mi ahead')
  })
})

function closure(overrides: Partial<Closure> = {}): Closure {
  return { ...CLOSURE, ...overrides }
}

describe('nearestClosure', () => {
  // Exported so the header's one banner line can be shared with the ATC's own
  // notices (lib/atcUpdates.ts, #461). Comparing distances is what lets the
  // nearer warning win without either source being ranked above the other.

  it('reports how far ahead the winner is, not just which it is', () => {
    const near = closure({ id: 'near', start_mile_marker: 12, end_mile_marker: 13 })
    const far = closure({ id: 'far', start_mile_marker: 40, end_mile_marker: 41 })

    const best = nearestClosure([far, near], 10, 'NOBO')

    expect(best?.closure.id).toBe('near')
    expect(best?.distance).toBeCloseTo(2, 5)
  })

  it('reports zero for a closure the hiker is standing in', () => {
    // Zero has to sort ahead of every closure further up the trail, which a
    // plain subtraction would lose to a negative number.
    const best = nearestClosure(
      [closure({ start_mile_marker: 10, end_mile_marker: 20 })],
      15,
      'NOBO',
    )

    expect(best?.distance).toBe(0)
  })

  it('answers null when everything is behind', () => {
    expect(
      nearestClosure([closure({ start_mile_marker: 1, end_mile_marker: 2 })], 10, 'NOBO'),
    ).toBeNull()
  })

  it('ignores a reopened closure, exactly as the banner does', () => {
    // The band and the banner must not disagree about what is closed.
    const reopened = closure({
      status: 'open',
      start_mile_marker: 12,
      end_mile_marker: 13,
    })

    expect(nearestClosure([reopened], 10, 'NOBO')).toBeNull()
  })

  it('agrees with the banner about which closure won', () => {
    const near = closure({ id: 'near', start_mile_marker: 12, end_mile_marker: 13 })
    const far = closure({ id: 'far', start_mile_marker: 40, end_mile_marker: 41 })

    const best = nearestClosure([far, near], 10, 'NOBO')

    expect(nearestClosureBanner([far, near], 10, 'NOBO')).toBe(
      closureBanner(best!.closure, 10, 'NOBO'),
    )
  })
})
