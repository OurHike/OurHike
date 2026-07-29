import { describe, it, expect } from 'vitest'
import { warningsOnRoute, routeBannerText, WARNING_PIN } from './seriousWarnings'

// WIREFRAMES.md §8. `severity: serious` is set by a moderator, never
// self-declared, and a serious warning surfaces prominently IN-APP - a route
// banner on map open and a distinct pin - but never pushes.
//
// The pin is a variant inside the existing icon spec (34px, red,
// triangle-alert, high-contrast halo), not a new visual language. A warning
// that looks like nothing else on the map is a warning nobody has learned to
// read.

const WARNING = {
  id: 'w1',
  type: 'animals' as const,
  severity: 'serious' as const,
  mile: 1045,
}

describe('warningsOnRoute', () => {
  it('counts warnings between where you are and where you are going', () => {
    const reports = [
      WARNING,
      { ...WARNING, id: 'w2', mile: 1060 },
      { ...WARNING, id: 'w3', mile: 1200 },
    ]

    expect(warningsOnRoute(reports, { fromMile: 1040, toMile: 1100 })).toHaveLength(2)
  })

  it('ignores anything that is not serious - normal reports are not warnings', () => {
    const reports = [WARNING, { ...WARNING, id: 'w2', severity: 'normal' as const }]

    expect(warningsOnRoute(reports, { fromMile: 1040, toMile: 1100 })).toHaveLength(1)
  })

  it('handles a southbound route, where the range runs backwards', () => {
    const reports = [WARNING]

    expect(warningsOnRoute(reports, { fromMile: 1100, toMile: 1040 })).toHaveLength(1)
  })

  it('includes one exactly at the route boundary rather than dropping it', () => {
    expect(warningsOnRoute([WARNING], { fromMile: 1045, toMile: 1100 })).toHaveLength(1)
  })

  it('returns nothing for a clear route', () => {
    expect(warningsOnRoute([WARNING], { fromMile: 1200, toMile: 1300 })).toEqual([])
  })
})

describe('routeBannerText', () => {
  it('says nothing when the route is clear - no banner for good news', () => {
    expect(routeBannerText(0)).toBeNull()
  })

  it('speaks in the singular for one', () => {
    expect(routeBannerText(1)).toBe('1 serious warning on your route')
  })

  it('speaks in the plural for more', () => {
    expect(routeBannerText(2)).toBe('2 serious warnings on your route')
  })
})

describe('WARNING_PIN', () => {
  it('is the size and icon WIREFRAMES.md specifies', () => {
    expect(WARNING_PIN).toMatchObject({ sizePx: 34, icon: 'triangle-alert' })
  })

  it('carries a high-contrast halo, so it survives a busy topo background', () => {
    expect(WARNING_PIN.halo).toBe(true)
  })

  it('is larger than an ordinary waypoint pin, without being a new language', () => {
    expect(WARNING_PIN.sizePx).toBeGreaterThan(WARNING_PIN.ordinaryPinPx)
  })
})
