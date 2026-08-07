import { describe, it, expect } from 'vitest'
import {
  isSeriousWarning,
  placeAll,
  warningsOnRoute,
  routeBannerText,
  WARNING_PIN,
  type PlaceableReport,
} from './seriousWarnings'
import { buildTrailIndex } from './trailPosition'
import { POI_PIN_SIZE } from '../map/poiIcons'

// WIREFRAMES.md §8. `severity: serious` is set by a moderator, never
// self-declared, and a serious warning surfaces prominently IN-APP - a route
// banner on map open and a distinct pin - but never pushes.
//
// The pin is a variant inside the existing icon spec (44px, red,
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

describe('isSeriousWarning', () => {
  it('is the same rule warningsOnRoute filters by, not a second one', () => {
    // The map draws these as pins and the banner counts them along a route.
    // Two spellings of "=== serious" is how a map full of pins ends up beside
    // a banner counting none of them, so the predicate is shared and this is
    // what says so.
    const mixed = [WARNING, { ...WARNING, id: 'w2', severity: 'normal' as const }]

    expect(mixed.filter(isSeriousWarning)).toEqual(
      warningsOnRoute(mixed, { fromMile: 0, toMile: 2200 }),
    )
  })

  it('needs no mile, which is why the pin can use it', () => {
    // A report carries lat/lon and no mile (#244). The pin goes where the
    // report was written; only the banner needs a position along the trail.
    expect(isSeriousWarning({ severity: 'serious' })).toBe(true)
    expect(isSeriousWarning({ severity: 'normal' })).toBe(false)
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
    expect(WARNING_PIN).toMatchObject({ sizePx: 44, icon: 'triangle-alert' })
  })

  it('carries a high-contrast halo, so it survives a busy topo background', () => {
    expect(WARNING_PIN.halo).toBe(true)
  })

  it('is larger than the pins really being drawn, not than a remembered number', () => {
    // This reads POI_PIN_SIZE through WARNING_PIN.ordinaryPinPx rather than a
    // literal of its own, which is what makes it a guard: the field used to
    // say 17 while the map drew pins at 30, so growing the pins past the
    // warning would not have failed anything here.
    expect(WARNING_PIN.ordinaryPinPx).toBe(POI_PIN_SIZE)
    expect(WARNING_PIN.sizePx).toBeGreaterThan(WARNING_PIN.ordinaryPinPx)
  })
})

// --- Placing a report on the trail (#244) ----------------------------------
//
// The form snapped the fix to the centerline to render "mi 1,407.2" and then
// dropped it at submit, so the one number this module filters on was computed
// and discarded in the same breath. It now travels with the report - and this
// app still prefers its own snap where it can run one, because that is
// measured against the same index the hiker's own position is.

/** Ten miles of centerline running due north, with a VERTEX every mile.
 *
 *  `locateOnTrail` snaps to the nearest vertex and gives up past
 *  `MAX_OFF_TRAIL_MILES`, so a two-point line would put every fix in the
 *  middle four miles from anything and fail to snap - which would make these
 *  cases pass through the fallback while claiming to test the snap. */
const MILE_LAT = 1 / 69.05
const INDEX = buildTrailIndex({
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { source: 'centerline' },
      geometry: {
        type: 'LineString',
        coordinates: Array.from(
          { length: 11 },
          (_, i) => [-77, 39 + i * MILE_LAT] as [number, number],
        ),
      },
    },
  ],
})

function placeable(over: Partial<PlaceableReport> = {}): PlaceableReport {
  return {
    id: 'r1',
    type: 'animals',
    severity: 'serious',
    lat: null,
    lon: null,
    mile: null,
    ...over,
  }
}

describe('placeAll', () => {
  it('snaps lat/lon against this index rather than trusting the stored mile', () => {
    // The stored mile was measured against whatever centerline was published
    // the day it was filed, and relocations move those numbers. The snap is
    // measured against the same index the hiker's own position is, which is
    // what makes "3 miles ahead" mean the same thing on both sides.
    const placed = placeAll(
      [placeable({ lat: 39 + 4 * MILE_LAT, lon: -77, mile: 900 })],
      INDEX,
    )

    expect(placed).toHaveLength(1)
    expect(placed[0].mile).toBeCloseTo(4, 1)
  })

  it('falls back to the reported mile when there are no coordinates at all', () => {
    // A report filed against a POI. Under the old lat/lon-only derivation it
    // could never appear on anybody's banner, however serious a moderator
    // marked it - which for a `bad_hikers` report is the warning not arriving.
    const placed = placeAll([placeable({ mile: 6 })], INDEX)

    expect(placed.map((warning) => warning.mile)).toEqual([6])
  })

  it('falls back when the coordinates are too far off trail to snap', () => {
    const placed = placeAll([placeable({ lat: 45, lon: -100, mile: 6 })], INDEX)

    expect(placed.map((warning) => warning.mile)).toEqual([6])
  })

  it('drops a report with neither, rather than defaulting it to mile 0', () => {
    // Mile 0 is Springer Mountain. A warning at the wrong end of the trail is
    // worse than a missing one: it is on somebody's banner about a place they
    // are nowhere near.
    expect(placeAll([placeable()], INDEX)).toEqual([])
  })

  it("does not filter by severity - that is warningsOnRoute's rule, not a second one", () => {
    // Two spellings of "which reports are warnings" is how a map full of pins
    // ends up beside a banner that counts none of them.
    const placed = placeAll([placeable({ severity: 'normal', mile: 6 })], INDEX)

    expect(placed).toHaveLength(1)
  })

  it('carries id and type through, so the caller can still tell them apart', () => {
    const placed = placeAll(
      [placeable({ id: 'bad-1', type: 'bad_hikers', mile: 6 })],
      INDEX,
    )

    expect(placed[0]).toMatchObject({ id: 'bad-1', type: 'bad_hikers' })
  })
})
