import { describe, it, expect } from 'vitest'
import {
  MAX_LANE_SPAN_MI,
  ribbonLanes,
  ribbonView,
  type RibbonInputs,
} from './ribbonView'
import { ENVELOPE_BUCKETS } from './chartProfile'
import { ribbonWindow, type ElevationProfile } from './elevationProfile'

// The precedence is the subject here, because it is the part that cannot be
// read off any one call: four things the ribbon can be showing, exactly one
// true at a time, and a wrong order shows a hiker somebody else's ground.
//
// The other load-bearing claim is which domains carry which CLAIMS - the
// you-are-here rule and the climb callout - since both assert something about
// a person rather than about terrain.

function profileOf(samples: Array<[number, number | null]>): ElevationProfile {
  const distanceMi = new Float32Array(samples.length)
  const elevationFt = new Float32Array(samples.length)
  samples.forEach(([mile, ft], i) => {
    distanceMi[i] = mile
    elevationFt[i] = ft === null ? Number.NaN : ft
  })
  return { distanceMi, elevationFt }
}

/** 100 miles at one sample every 0.01 mi, with a 1,000 ft climb from mile 40
 *  to 42 - big enough to clear upcomingClimb's 300 ft floor. */
function longProfile(): ElevationProfile {
  const samples: Array<[number, number | null]> = []
  for (let i = 0; i <= 10000; i += 1) {
    const mile = i / 100
    const ft = mile <= 40 ? 1000 : mile <= 42 ? 1000 + (mile - 40) * 500 : 2000
    samples.push([mile, ft])
  }
  return profileOf(samples)
}

/** The AT's own length, one sample a mile - enough profile for the spans the
 *  lane ceiling is about, without ten thousand samples per test. */
function atLengthProfile(): ElevationProfile {
  return profileOf(Array.from({ length: 2191 }, (_, i) => [i, 1000 + (i % 7) * 100]))
}

/** Nothing selected, no fix, no map: the resting state. */
function inputs(over: Partial<RibbonInputs> = {}): RibbonInputs {
  return {
    profile: longProfile(),
    todaysWalk: null,
    planStretch: null,
    mapStretch: null,
    fixClientMile: null,
    fixPlanMile: null,
    fixWindow: null,
    ...over,
  }
}

describe('ribbonView precedence', () => {
  it('draws the whole trail when nothing has been selected', () => {
    const view = ribbonView(inputs())

    expect(view?.source).toBe('whole-trail')
    expect(view?.domain).toEqual({ startMile: 0, endMile: 100 })
  })

  it('prefers the fix window to the whole trail', () => {
    const profile = longProfile()
    const view = ribbonView(
      inputs({
        profile,
        fixClientMile: 39,
        fixWindow: ribbonWindow(profile, 39, 'NOBO'),
      }),
    )

    expect(view?.source).toBe('ahead')
    // One mile behind, nine ahead - the field window, untouched by #910.
    expect(view?.domain.startMile).toBeCloseTo(38, 5)
    expect(view?.domain.endMile).toBeCloseTo(48, 5)
  })

  it('prefers the map viewport to the fix window once the hiker takes the map', () => {
    const profile = longProfile()
    const view = ribbonView(
      inputs({
        profile,
        mapStretch: { startMile: 70, endMile: 80 },
        fixClientMile: 39,
        fixPlanMile: 39,
        fixWindow: ribbonWindow(profile, 39, 'NOBO'),
      }),
    )

    // Panning to ground the hiker is not on is a thing they just DID, and
    // outranking the fix is what makes the sync visible at all.
    expect(view?.source).toBe('map-view')
    expect(view?.domain.startMile).toBeCloseTo(70, 2)
  })

  it('prefers the route being planned to everything else', () => {
    const profile = longProfile()
    const view = ribbonView(
      inputs({
        profile,
        planStretch: { startMile: 10, endMile: 30 },
        mapStretch: { startMile: 70, endMile: 80 },
        fixClientMile: 39,
        fixPlanMile: 39,
        fixWindow: ribbonWindow(profile, 39, 'NOBO'),
      }),
    )

    expect(view?.source).toBe('planned-stretch')
    expect(view?.domain.startMile).toBeCloseTo(10, 2)
  })
})

describe("today's walk (#1045)", () => {
  const WALK = [
    { mile: 0, elevationFt: 900 },
    { mile: 1.5, elevationFt: 1400 },
    { mile: 3, elevationFt: 950 },
  ]

  it('draws a followed day hike on its own axis, not on the A.T.’s', () => {
    const profile = longProfile()
    const view = ribbonView(
      inputs({
        profile,
        todaysWalk: { kind: 'route', samples: WALK, alongMi: 1.2 },
        fixClientMile: 39,
        fixWindow: ribbonWindow(profile, 39, 'NOBO'),
      }),
    )

    expect(view?.source).toBe('todays-walk')
    expect(view?.domain).toEqual({ startMile: 0, endMile: 3 })
    expect(view?.currentMile).toBe(1.2)
    expect(view?.samples).toEqual(WALK)
  })

  it('draws nothing at all when the followed walk has no shape to draw', () => {
    // THE BUG #1045 CALLS A BUG. The A.T. runs through the same woods as a
    // Harriman loop, so `fix.mile` is a real number while somebody walks that
    // loop - and before this the ribbon fell through to the A.T.'s ten-mile
    // window and captioned it "ahead". A picture of a different walk, on the
    // band a hiker reads to judge daylight. #1041 chose "no ribbon at all" as
    // the honest state and this is what keeps that promise.
    const profile = longProfile()
    const view = ribbonView(
      inputs({
        profile,
        todaysWalk: { kind: 'route', samples: null, alongMi: 1.2 },
        fixClientMile: 39,
        fixWindow: ribbonWindow(profile, 39, 'NOBO'),
      }),
    )

    expect(view).toBeUndefined()
  })

  it('needs no A.T. profile to draw a day hike', () => {
    // The samples came off the walk's own edges. A phone whose download
    // carries no elevation_profile.json can still draw a Harriman loop.
    const view = ribbonView(
      inputs({
        profile: null,
        todaysWalk: { kind: 'route', samples: WALK, alongMi: null },
      }),
    )

    expect(view?.source).toBe('todays-walk')
    expect(view?.currentMile).toBeNull()
  })

  it('draws a trip day camp to camp instead of the ten-mile window', () => {
    const profile = longProfile()
    const view = ribbonView(
      inputs({
        profile,
        todaysWalk: { kind: 'trail', domain: { startMile: 35, endMile: 52 } },
        fixClientMile: 39,
        fixPlanMile: 39,
        fixWindow: ribbonWindow(profile, 39, 'NOBO'),
      }),
    )

    // The window's edges are arbitrary and can hide the climb that decides
    // whether somebody makes the shelter before dark; the day's own ends
    // cannot.
    expect(view?.source).toBe('todays-walk')
    expect(view?.domain).toEqual({ startMile: 35, endMile: 52 })
    expect(view?.currentMile).toBe(39)
  })

  it('still yields to a route being planned and to a map the hiker took', () => {
    const profile = longProfile()
    const today = { kind: 'trail' as const, domain: { startMile: 35, endMile: 52 } }

    expect(
      ribbonView(
        inputs({
          profile,
          todaysWalk: today,
          mapStretch: { startMile: 70, endMile: 80 },
        }),
      )?.source,
    ).toBe('map-view')
    expect(
      ribbonView(
        inputs({
          profile,
          todaysWalk: today,
          planStretch: { startMile: 10, endMile: 30 },
        }),
      )?.source,
    ).toBe('planned-stretch')
  })

  it('falls back to the fix window on a trip day it cannot draw, and never on a day hike', () => {
    // The one asymmetry in this module. `ahead` under a trip is a different
    // window of the hiker's OWN trail, correctly labelled - honest if less
    // useful. Under a day hike it is different ground entirely.
    const profile = longProfile()
    const fixWindow = ribbonWindow(profile, 39, 'NOBO')

    const trip = ribbonView(
      inputs({
        profile,
        todaysWalk: { kind: 'trail', domain: { startMile: 200, endMile: 200 } },
        fixClientMile: 39,
        fixWindow,
      }),
    )
    expect(trip?.source).toBe('ahead')

    const hike = ribbonView(
      inputs({
        profile,
        todaysWalk: { kind: 'route', samples: [WALK[0]], alongMi: null },
        fixClientMile: 39,
        fixWindow,
      }),
    )
    expect(hike).toBeUndefined()
  })

  it('carries no climb callout, because the callout is about the A.T.', () => {
    const profile = longProfile()
    const view = ribbonView(
      inputs({
        profile,
        todaysWalk: { kind: 'trail', domain: { startMile: 38, endMile: 48 } },
        fixClientMile: 39,
        fixPlanMile: 39,
        fixWindow: ribbonWindow(profile, 39, 'NOBO'),
        direction: 'NOBO',
      }),
    )

    expect(view?.source).toBe('todays-walk')
    expect(view?.upcomingClimb).toBeUndefined()
  })
})

describe('what each domain is allowed to claim', () => {
  it('captions the climb only on the fix window', () => {
    const profile = longProfile()
    const fixWindow = ribbonWindow(profile, 39, 'NOBO')

    const onFix = ribbonView(
      inputs({ profile, fixClientMile: 39, fixWindow, direction: 'NOBO' }),
    )
    expect(onFix?.source).toBe('ahead')
    expect(onFix?.upcomingClimb?.ascentFt).toBeGreaterThan(300)

    // The same climb, the same hiker, the same direction - but the domain is
    // now a stretch somebody chose to look at, and "next" means nothing on it.
    const onPlan = ribbonView(
      inputs({
        profile,
        planStretch: { startMile: 38, endMile: 48 },
        fixClientMile: 39,
        fixPlanMile: 39,
        fixWindow,
        direction: 'NOBO',
      }),
    )
    expect(onPlan?.source).toBe('planned-stretch')
    expect(onPlan?.upcomingClimb).toBeUndefined()
  })

  it('never calls a domain something it is not', () => {
    // The source IS the accessible name (ElevationRibbon's RibbonSubject), so
    // a whole-trail ribbon reporting itself as a planned stretch would have a
    // screen reader announce ground nobody is planning.
    const profile = longProfile()
    const fixWindow = ribbonWindow(profile, 39, 'NOBO')

    expect(ribbonView(inputs({ profile, fixClientMile: 39, fixWindow }))?.source).toBe(
      'ahead',
    )
    expect(ribbonView(inputs())?.source).toBe('whole-trail')
    expect(
      ribbonView(inputs({ mapStretch: { startMile: 5, endMile: 20 } }))?.source,
    ).toBe('map-view')
    expect(
      ribbonView(inputs({ planStretch: { startMile: 5, endMile: 20 } }))?.source,
    ).toBe('planned-stretch')
  })

  it('marks the hiker on a chosen domain only when they stand on it', () => {
    expect(
      ribbonView(inputs({ planStretch: { startMile: 10, endMile: 30 }, fixPlanMile: 22 }))
        ?.currentMile,
    ).toBe(22)
    expect(
      ribbonView(inputs({ planStretch: { startMile: 10, endMile: 30 }, fixPlanMile: 74 }))
        ?.currentMile,
    ).toBeNull()
    expect(
      ribbonView(inputs({ planStretch: { startMile: 10, endMile: 30 } }))?.currentMile,
    ).toBeNull()
  })

  it('reads a stretch given end-first the same way as start-first', () => {
    // A SOBO draft's stops arrive in walk order, which puts the larger mile
    // first. The ribbon is a picture of ground, and ground has no direction.
    const south = ribbonView(inputs({ planStretch: { startMile: 30, endMile: 10 } }))
    const north = ribbonView(inputs({ planStretch: { startMile: 10, endMile: 30 } }))

    expect(south?.samples).toEqual(north?.samples)
  })
})

describe('what ribbonView refuses to draw', () => {
  it('refuses without a profile', () => {
    expect(ribbonView(inputs({ profile: null }))).toBeUndefined()
    expect(ribbonView(inputs({ profile: profileOf([]) }))).toBeUndefined()
  })

  it('refuses a zero-width stretch rather than dividing by it', () => {
    expect(
      ribbonView(inputs({ planStretch: { startMile: 12, endMile: 12 } })),
    ).toBeUndefined()
  })

  it('refuses a stretch the DEM never covered rather than drawing a blank', () => {
    const gap = profileOf([
      [10, 1000],
      [20, null],
      [21, null],
      [22, null],
      [40, 1200],
    ])

    // One surviving sample is a dot, not a shape - and a ribbon showing a dot
    // over a 2-mile plan says "flat" about ground nobody measured.
    expect(
      ribbonView(inputs({ profile: gap, planStretch: { startMile: 20, endMile: 22 } })),
    ).toBeUndefined()
  })
})

describe('drawing cost', () => {
  it('decimates a domain too long to draw sample by sample', () => {
    // The whole trail here is ~10,000 samples; the real one is ~141,000.
    // Handing every one to an SVG path is the honesty problem
    // lib/chartProfile.ts describes, not only a cost one: what survives is
    // decided by paint order.
    const view = ribbonView(inputs())

    expect(view?.samples.length).toBeLessThanOrEqual(ENVELOPE_BUCKETS * 2)
  })

  it('keeps the real samples on a stretch short enough to draw whole', () => {
    const view = ribbonView(inputs({ planStretch: { startMile: 40, endMile: 43 } }))

    expect(view?.samples).toHaveLength(301)
  })
})

// The lanes under whichever ribbon won (#913). What matters is which mile
// places a pin, which window it is placed in, and the three states where no
// lanes at all is the honest answer.
describe('ribbonLanes', () => {
  const shelter = (id: string, mile?: number) => ({ id, type: 'shelter', ...{ mile } })
  const both = (pois: ReturnType<typeof shelter>[]) => ({
    onPipelineAxis: pois,
    onClientAxis: pois,
  })

  it('keeps the POIs inside the domain and leaves out the ones off it', () => {
    const view = ribbonView(inputs({ planStretch: { startMile: 10, endMile: 30 } }))
    const lanes = ribbonLanes(
      view,
      both([
        shelter('before', 9.5),
        shelter('start', 10),
        shelter('middle', 20),
        shelter('end', 30),
        shelter('after', 30.5),
      ]),
    )

    expect(lanes?.points.map((p) => p.id)).toEqual(['start', 'middle', 'end'])
  })

  it('places a pin on the axis the winning domain is windowed on', () => {
    // The two mile scales, reproduced: the same shelter is at 20 on the
    // pipeline's axis and 19.8 on the client index's (HIKE_PLANNING.md
    // Finding 1). `ahead` is a client-axis window and everything else is a
    // pipeline-axis span, so each has to read its own list or the pin lands
    // a couple of tenths off the climb it sits under.
    const pois = {
      onPipelineAxis: [shelter('s', 20)],
      onClientAxis: [shelter('s', 19.8)],
    }
    const profile = longProfile()
    const fixWindow = ribbonWindow(profile, 19.8)

    const planned = ribbonLanes(
      ribbonView(inputs({ planStretch: { startMile: 10, endMile: 30 } })),
      pois,
    )
    const ahead = ribbonLanes(
      ribbonView(inputs({ profile, fixClientMile: 19.8, fixWindow })),
      pois,
    )

    expect(planned?.points[0].mile).toBe(20)
    expect(ahead?.points[0].mile).toBe(19.8)
  })

  it('windows the lanes on the view’s own domain, not on its samples', () => {
    // A destination between two samples, which is where a real one falls: the
    // profile is sampled every 25 m and a shelter is where it is. Windowed on
    // the samples, the stop the route walks TO drops out of the SLEEP lane.
    const view = ribbonView(inputs({ planStretch: { startMile: 10, endMile: 30.005 } }))
    const lanes = ribbonLanes(view, both([shelter('destination', 30.005)]))

    expect(lanes?.startMile).toBe(10)
    expect(lanes?.endMile).toBe(30.005)
    expect(view!.samples[view!.samples.length - 1].mile).toBeLessThan(30.005)
    expect(lanes?.points.map((p) => p.id)).toEqual(['destination'])
  })

  it('draws empty lanes for a domain that genuinely holds nothing', () => {
    // Emptiness that is a fact about the trail rather than about the
    // download - so the lanes are drawn, and say so by being empty.
    const view = ribbonView(inputs({ planStretch: { startMile: 10, endMile: 30 } }))

    expect(ribbonLanes(view, both([shelter('far', 80)]))?.points).toEqual([])
  })

  it('refuses when nothing in the set carries a mile on that axis', () => {
    // Empty lanes here would report "nothing along here" about POIs the app
    // cannot place anywhere - a pre-#753 download, or a centerline index that
    // placed none of them.
    const view = ribbonView(inputs({ planStretch: { startMile: 10, endMile: 30 } }))

    expect(ribbonLanes(view, both([shelter('a'), shelter('b')]))).toBeUndefined()
  })

  it('refuses on a ribbon measured with the walk’s own ruler (#1045)', () => {
    // A followed day hike's "mile 2" is a place in Harriman. Every POI this
    // app holds carries a mile on the A.T. centerline, so lanes here would
    // pin the shelters at A.T. mile 2 - in Georgia - under a Harriman loop.
    // Nothing about the picture would look wrong.
    const walk = ribbonView(
      inputs({
        todaysWalk: {
          kind: 'route',
          samples: [
            { mile: 0, elevationFt: 900 },
            { mile: 3, elevationFt: 1200 },
          ],
          alongMi: null,
        },
      }),
    )

    expect(walk?.source).toBe('todays-walk')
    expect(ribbonLanes(walk, both([shelter('georgia', 2)]))).toBeUndefined()
  })

  it('keeps them on a TRIP day, which is measured with the same ruler as the POIs', () => {
    const trip = ribbonView(
      inputs({ todaysWalk: { kind: 'trail', domain: { startMile: 10, endMile: 25 } } }),
    )

    expect(trip?.source).toBe('todays-walk')
    expect(ribbonLanes(trip, both([shelter('on-today', 18)]))?.points).toHaveLength(1)
  })

  it('refuses without a ribbon to sit under', () => {
    expect(ribbonLanes(undefined, both([shelter('a', 12)]))).toBeUndefined()
  })

  it('drops the lanes on the whole trail, where a pill is not a place', () => {
    // 1.5% of the AT is 33 miles. The resting domain is exactly where this
    // guard earns itself; a 20-mile plan on the same profile keeps its lanes.
    const whole = ribbonView(inputs({ profile: atLengthProfile() }))
    const planned = ribbonView(
      inputs({ profile: atLengthProfile(), planStretch: { startMile: 0, endMile: 20 } }),
    )

    expect(whole?.source).toBe('whole-trail')
    expect(ribbonLanes(whole, both([shelter('a', 12)]))).toBeUndefined()
    expect(ribbonLanes(planned, both([shelter('a', 12)]))).toBeDefined()
  })

  it('draws them either side of the span the arithmetic puts them at', () => {
    const profile = atLengthProfile()
    const under = ribbonView(
      inputs({
        profile,
        planStretch: { startMile: 0, endMile: MAX_LANE_SPAN_MI - 10 },
      }),
    )
    const over = ribbonView(
      inputs({
        profile,
        planStretch: { startMile: 0, endMile: MAX_LANE_SPAN_MI + 10 },
      }),
    )

    expect(ribbonLanes(under, both([shelter('a', 12)]))).toBeDefined()
    expect(ribbonLanes(over, both([shelter('a', 12)]))).toBeUndefined()
  })
})
