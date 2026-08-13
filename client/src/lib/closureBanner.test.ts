import { describe, it, expect } from 'vitest'
import {
  closureBanner,
  closureLanes,
  closureReasonLabel,
  type Closure,
  type HikeDirection,
} from './closureBanner'
import { MAX_BAND_MILES } from './closureSpan'

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

describe('the specific-closure line', () => {
  // These were written against `nearestClosureBanner`, which ranked every
  // closure into one line and is gone (#485). Each rule below is unchanged;
  // what changed is that it is now the SPECIFIC lane's rule, asked through
  // `closureLanes`. The broad lane has its own describe further down.
  const specificBanner = (
    closures: readonly Closure[],
    currentMile: number,
    direction: HikeDirection | undefined,
  ): string | null => {
    const best = closureLanes(closures, currentMile, direction).specific
    return best === null ? null : closureBanner(best.closure, currentMile, direction)
  }

  it('says nothing when the way ahead is clear', () => {
    const behind = { ...CLOSED, id: 'c1', start_mile_marker: 10, end_mile_marker: 11 }

    expect(specificBanner([behind], 100, 'NOBO')).toBeNull()
  })

  it('says nothing about an empty list', () => {
    expect(specificBanner([], 100, 'NOBO')).toBeNull()
  })

  it('picks the nearest of several ahead', () => {
    const near = { ...CLOSED, id: 'near', start_mile_marker: 105, end_mile_marker: 106 }
    const far = { ...CLOSED, id: 'far', start_mile_marker: 300, end_mile_marker: 301 }

    const banner = specificBanner([far, near], 100, 'NOBO')

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

    const banner = specificBanner([inside, ahead], 100, 'NOBO')

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

    const banner = specificBanner([inside, ahead], 100, undefined)

    expect(banner).toContain('Trail closed here')
    // And the one merely ahead stays quiet alone - "ahead" needs a direction.
    expect(specificBanner([ahead], 100, undefined)).toBeNull()
  })

  it('reads direction, not just distance', () => {
    // The same closure and the same standing mile. A NOBO hiker has it in
    // front of them; a SOBO hiker walked through it an hour ago. Getting
    // this backwards means silence about the one being walked into.
    const closure = { ...CLOSED, id: 'c', start_mile_marker: 105, end_mile_marker: 106 }

    expect(specificBanner([closure], 100, 'NOBO')).toContain('5.0 mi ahead')
    expect(specificBanner([closure], 100, 'SOBO')).toBeNull()
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

    expect(specificBanner([reopened, real], 100, 'NOBO')).toContain('10.0 mi ahead')
  })

  it('still warns about a reroute - somewhere else to walk is not passable trail', () => {
    const reroute = {
      ...CLOSED,
      id: 'rr',
      status: 'reroute_available' as const,
      start_mile_marker: 105,
      end_mile_marker: 106,
    }

    expect(specificBanner([reroute], 100, 'NOBO')).toContain('5.0 mi ahead')
  })
})

function closure(overrides: Partial<Closure> = {}): Closure {
  return { ...CLOSURE, ...overrides }
}

describe('closureLanes', () => {
  // Exported so the header's one banner line can be shared with the ATC's own
  // notices (lib/atcUpdates.ts, #461). Comparing distances is what lets the
  // nearer warning win without either source being ranked above the other.

  it('reports how far ahead the winner is, not just which it is', () => {
    const near = closure({ id: 'near', start_mile_marker: 12, end_mile_marker: 13 })
    const far = closure({ id: 'far', start_mile_marker: 40, end_mile_marker: 41 })

    const best = closureLanes([far, near], 10, 'NOBO').specific

    expect(best?.closure.id).toBe('near')
    expect(best?.distance).toBeCloseTo(2, 5)
  })

  it('reports zero for a closure the hiker is standing in', () => {
    // Zero has to sort ahead of every closure further up the trail, which a
    // plain subtraction would lose to a negative number.
    const best = closureLanes(
      [closure({ start_mile_marker: 10, end_mile_marker: 20 })],
      15,
      'NOBO',
    ).specific

    expect(best?.distance).toBe(0)
  })

  it('answers null when everything is behind', () => {
    expect(
      closureLanes([closure({ start_mile_marker: 1, end_mile_marker: 2 })], 10, 'NOBO')
        .specific,
    ).toBeNull()
  })

  it('ignores a reopened closure, exactly as the banner does', () => {
    // The band and the banner must not disagree about what is closed.
    const reopened = closure({
      status: 'open',
      start_mile_marker: 12,
      end_mile_marker: 13,
    })

    expect(closureLanes([reopened], 10, 'NOBO').specific).toBeNull()
  })

  it('keeps a broad advisory out of the specific lane', () => {
    // Was a test that `nearestClosure` and `nearestClosureBanner` agreed, which
    // became tautological when the two collapsed into one. This is the rule that
    // replaced it and the one #485 turns on.
    const advisory = closure({
      id: 'advisory',
      start_mile_marker: 10,
      end_mile_marker: 10 + MAX_BAND_MILES + 1,
    })
    const specific = closure({
      id: 'specific',
      start_mile_marker: 30,
      end_mile_marker: 31,
    })

    const lanes = closureLanes([advisory, specific], 20, 'NOBO')

    expect(lanes.specific?.closure.id).toBe('specific')
    expect(lanes.broad?.closure.id).toBe('advisory')
  })
})

// THE CASE #485 REPORTS, in the numbers it reports it in.
//
// ATC's Hurricane Helene advisory runs NOBO 239.4 to 637.8 - 398 miles. A hiker
// at mile 242 is inside it, which scored 0 and won the header outright, so for
// 398 miles of walking they read "Trail closed here" while the nine-mile Creeper
// Trail closure three miles ahead never appeared at all.
describe('a broad advisory does not bury the closure inside it', () => {
  const HELENE = {
    ...CLOSED,
    id: 'helene',
    start_mile_marker: 239.4,
    end_mile_marker: 637.8,
  }
  const CREEPER = {
    ...CLOSED,
    id: 'creeper',
    start_mile_marker: 245,
    end_mile_marker: 254,
  }

  it('gives the nine-mile closure the actionable line', () => {
    const lanes = closureLanes([HELENE, CREEPER], 242, 'NOBO')

    expect(lanes.specific?.closure.id).toBe('creeper')
    expect(closureBanner(lanes.specific!.closure, 242, 'NOBO')).toContain('3.0 mi ahead')
  })

  it('keeps the advisory rather than dropping it', () => {
    // The alternative #485 weighs - rank a broad advisory by its nearer edge
    // instead of 0 - is silent here, not merely quieter: 239.4 - 242 is negative,
    // so the advisory would be treated as behind and skipped while the hiker
    // stands in it.
    const lanes = closureLanes([HELENE, CREEPER], 242, 'NOBO')

    expect(lanes.broad?.closure.id).toBe('helene')
  })

  it('stops telling a hiker the trail is closed where they are standing', () => {
    // #485's second complaint, and true whichever line this lands on: the trail
    // is not closed at their feet, a region has damage in it, and ATC's own text
    // says the damage is patchy.
    const banner = closureBanner(HELENE, 242, 'NOBO')

    expect(banner).not.toContain('closed here')
    expect(banner).toContain('Advisory along 398 mi of trail')
    expect(banner).toContain('mi 239.4 – 637.8')
  })

  it('does not claim a closure ahead of a broad advisory either', () => {
    // Same overclaim in the future tense - walking toward a region with damage
    // in it is not walking toward a barrier across the treadway.
    const banner = closureBanner(HELENE, 200, 'NOBO')

    expect(banner).toContain('Advisory 39.4 mi ahead')
    expect(banner).not.toContain('Trail closed')
  })

  // #619. One sentence, two kinds of number: how far the hiker walks before
  // they are in it, and where on the A.T. "it" is. The first converts and the
  // second cannot - a metric hiker who reads `km 385.0 – 1,026.5` has a
  // coordinate nobody else on the trail can check.
  it('reads the distance in kilometres while the mile markers stay put', () => {
    const banner = closureBanner(HELENE, 200, 'NOBO', 'metric')

    expect(banner).toContain('Advisory 63.4 km ahead')
    expect(banner).toContain('mi 239.4 – 637.8')
  })

  it('states a broad advisory’s extent in kilometres too', () => {
    const banner = closureBanner(HELENE, 242, 'NOBO', 'metric')

    expect(banner).toContain('Advisory along 641 km of trail')
    expect(banner).toContain('mi 239.4 – 637.8')
  })

  it('still says "closed here" for a closure that really is one', () => {
    // The ordinary case has to keep the ordinary sentence - it is what
    // WIREFRAMES.md §7 specifies, and the whole reason breadth is a predicate
    // rather than a rewrite.
    expect(closureBanner(CREEPER, 250, 'NOBO')).toContain('Trail closed here')
  })

  it('draws the line at MAX_BAND_MILES rather than a second number', () => {
    // #485 asks for this explicitly. One constant decides what gets a band and
    // what gets the quiet line, so the two surfaces cannot disagree about which
    // closures are region-sized.
    const atCeiling = {
      ...CLOSED,
      id: 'at',
      start_mile_marker: 100,
      end_mile_marker: 100 + MAX_BAND_MILES,
    }
    const over = {
      ...CLOSED,
      id: 'over',
      start_mile_marker: 100,
      end_mile_marker: 100.1 + MAX_BAND_MILES,
    }

    expect(closureLanes([atCeiling], 120, 'NOBO').specific?.closure.id).toBe('at')
    expect(closureLanes([atCeiling], 120, 'NOBO').broad).toBeNull()
    expect(closureLanes([over], 120, 'NOBO').broad?.closure.id).toBe('over')
    expect(closureLanes([over], 120, 'NOBO').specific).toBeNull()
  })

  it('leaves both lanes empty when nothing is ahead', () => {
    const lanes = closureLanes([HELENE, CREEPER], 700, 'NOBO')

    expect(lanes.specific).toBeNull()
    expect(lanes.broad).toBeNull()
  })
})
