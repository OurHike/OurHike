import { describe, it, expect } from 'vitest'
import { ribbonView, type RibbonInputs } from './ribbonView'
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

/** Nothing selected, no fix, no map: the resting state. */
function inputs(over: Partial<RibbonInputs> = {}): RibbonInputs {
  return {
    profile: longProfile(),
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
