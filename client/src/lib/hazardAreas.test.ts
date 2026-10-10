import { describe, expect, it } from 'vitest'
import type { FeatureCollection } from 'geojson'
import {
  HAZARD_ADVISORIES,
  crossedHazardAreas,
  hazardAreasOf,
  hazardDates,
  hazardFeatureCollection,
  hazardsAt,
  longDay,
} from './hazardAreas'
import type { TrailNotice } from './notices'
import { buildTrailIndex } from './trailPosition'

// Decision 67 (the maintainer, 2026-10-04): a hunting area, a shooting site
// or a burned area draws where a downloaded trail crosses one, with the
// advisory on the card for that stretch, and THE TRAIL STAYS OPEN.

function line(lon: number): FeatureCollection {
  const coordinates: Array<[number, number]> = []
  for (let i = 0; i <= 100; i += 1) coordinates.push([lon, 34 + i * 0.01])
  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: { source: 'centerline' },
        geometry: { type: 'LineString', coordinates },
      },
    ],
  } as FeatureCollection
}

const INDEX = buildTrailIndex(line(-77))

function area(
  id: string,
  hazard: TrailNotice['hazard'],
  west: number,
  east: number,
  extra: Partial<TrailNotice> = {},
): TrailNotice {
  return {
    notice_id: id,
    source_key: id.split(':')[0],
    title: id,
    category: null,
    locality: '',
    place: {
      kind: 'geometry',
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [west, 34.3],
            [east, 34.3],
            [east, 34.31],
            [west, 34.31],
            [west, 34.3],
          ],
        ],
      },
    },
    obstructs_trail: false,
    updated_at: null,
    source_url: null,
    review_state: 'unreviewed',
    hazard,
    ...extra,
  }
}

const crossed = area('iata_lands_hunting_regs:1', 'hunting', -77.01, -76.99)
const away = area('iata_lands_hunting_regs:2', 'hunting', -76.9, -76.8)
const plain = area('club_closure:1', null, -77.01, -76.99)
const shooting: TrailNotice = {
  ...area('blm_shooting_points:1', 'shooting', 0, 0),
  place: { kind: 'geometry', geometry: { type: 'Point', coordinates: [-76.9997, 34.4] } },
}

describe('which areas draw', () => {
  it('draws an area a trail on this phone runs through, and not one no trail meets', () => {
    const drawn = crossedHazardAreas(hazardAreasOf([crossed, away]), INDEX, null)
    expect(drawn.map((a) => a.notice.notice_id)).toEqual(['iata_lands_hunting_regs:1'])
  })

  it('draws a shooting site beside the trail', () => {
    const drawn = crossedHazardAreas(hazardAreasOf([shooting]), INDEX, null)
    expect(drawn.map((a) => a.notice.notice_id)).toEqual(['blm_shooting_points:1'])
  })

  it('draws nothing before any trail data has loaded', () => {
    expect(crossedHazardAreas(hazardAreasOf([crossed]), null, null)).toEqual([])
  })

  it('is only hazard notices: an ordinary notice with a shape is not an area to draw', () => {
    expect(hazardAreasOf([plain])).toEqual([])
  })

  it('carries each drawn area’s id and kind to the map, never a closure flag', () => {
    const collection = hazardFeatureCollection(hazardAreasOf([crossed]))
    expect(collection.features).toHaveLength(1)
    expect(collection.features[0].properties).toEqual({
      notice_id: 'iata_lands_hunting_regs:1',
      hazard: 'hunting',
    })
  })
})

describe('the advisory on a tapped stretch', () => {
  it('names the area a tapped place on the trail is inside', () => {
    const drawn = crossedHazardAreas(hazardAreasOf([crossed, away]), INDEX, null)
    expect(hazardsAt(drawn, [-77, 34.305]).map((a) => a.hazard)).toEqual(['hunting'])
    expect(hazardsAt(drawn, [-77, 34.5])).toEqual([])
  })

  it('says the trail stays open, every kind, and never that it is closed', () => {
    for (const advisory of Object.values(HAZARD_ADVISORIES)) {
      expect(advisory.body).toContain('The trail stays open.')
      expect(advisory.areaBody).toMatch(/Trails (through|near) it stay open\.$/)
      expect(
        `${advisory.heading} ${advisory.body} ${advisory.areaBody}`.toLowerCase(),
      ).not.toMatch(/\bclosed?\b/)
    }
  })

  // Decision 99 (poll, 2026-10-07): a tapped stretch's sheet keeps "This
  // stretch…"; the area's own card, opened by tapping the area, never says it.
  it('words the stretch and the area each for what was tapped, every kind', () => {
    for (const advisory of Object.values(HAZARD_ADVISORIES)) {
      expect(advisory.body).toMatch(/^This stretch /)
      expect(advisory.areaBody).not.toMatch(/stretch/i)
    }
  })
})

describe('the dates on an area', () => {
  const ORG = 'Fixture Parks'

  it('prints a hunting area’s own season in long dates, credited to its publisher', () => {
    expect(
      hazardDates({ ...crossed, starts_on: '2026-11-15', ends_on: '2026-12-13' }, ORG),
    ).toBe('From November 15, 2026 to December 13, 2026, according to Fixture Parks.')
  })

  it('prints a start or an end alone when the publisher gives only one', () => {
    expect(hazardDates({ ...crossed, starts_on: '2026-11-15' }, ORG)).toBe(
      'From November 15, 2026, according to Fixture Parks.',
    )
    expect(hazardDates({ ...crossed, ends_on: '2026-12-13' }, ORG)).toBe(
      'Until December 13, 2026, according to Fixture Parks.',
    )
  })

  it('says a hunting area’s publisher gives no season rather than inventing one', () => {
    expect(hazardDates(crossed, ORG)).toBe(
      'Fixture Parks gives no season dates. Check hunting seasons before you go.',
    )
  })

  it('says a shooting site’s publisher gives no end date when it gives none', () => {
    expect(hazardDates({ ...crossed, hazard: 'shooting' as const }, ORG)).toBe(
      'Fixture Parks gives no end date.',
    )
  })

  it('reads a burned area’s date as the fire’s start, not the danger’s', () => {
    const burned = { ...crossed, hazard: 'burned_area' as const, starts_on: '2026-08-26' }
    expect(hazardDates(burned, ORG)).toBe(
      'The fire started August 26, 2026, according to Fixture Parks. Shown while Fixture Parks lists this area.',
    )
    expect(hazardDates({ ...burned, starts_on: null }, ORG)).toBe(
      'Shown while Fixture Parks lists this area.',
    )
  })
})

describe('longDay', () => {
  it('reads "2026-10-01" as October 1, 2026, the calendar day, in every zone', () => {
    expect(longDay('2026-10-01')).toBe('October 1, 2026')
    expect(longDay('2026-12-31')).toBe('December 31, 2026')
  })

  it('shows a date that is not an ISO day as the source wrote it, never "Invalid Date"', () => {
    expect(longDay('late October')).toBe('late October')
    expect(longDay('2026-13-45')).toBe('2026-13-45')
  })

  it('shows "2026-04-31" as written, never as May 1, 2026, the day V8 rolls it over to', () => {
    // Measured 2026-10-09 in Node 22: new Date('2026-04-31T00:00:00Z') is
    // 2026-05-01, and '2026-02-30' is 2026-03-02. A closure's end date one
    // day off is worse than the source's own string.
    expect(longDay('2026-04-31')).toBe('2026-04-31')
    expect(longDay('2026-02-29')).toBe('2026-02-29')
    expect(longDay('2028-02-29')).toBe('February 29, 2028')
  })
})
