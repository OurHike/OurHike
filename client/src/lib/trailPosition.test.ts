import { describe, it, expect } from 'vitest'
import type { Feature, FeatureCollection } from 'geojson'
import { buildTrailIndex, locateOnTrail } from './trailPosition'

// Synthetic geometry throughout, in the shape the real trails.geojson uses:
// LineString features carrying a `source` of 'centerline' or something else.

function line(coordinates: Array<[number, number]>, source = 'centerline'): Feature {
  return {
    type: 'Feature',
    properties: { source },
    geometry: { type: 'LineString', coordinates },
  }
}

function collection(features: Feature[]): FeatureCollection {
  return { type: 'FeatureCollection', features }
}

/** A feature with `geometry: null` - valid GeoJSON, and not expressible in
 *  @types/geojson's default Feature, which is why this casts. */
function nullGeometry(): Feature {
  return {
    type: 'Feature',
    properties: { source: 'centerline' },
    geometry: null,
  } as unknown as Feature
}

/** Roughly a mile of latitude, near enough for asserting on tenths. */
const MILE_IN_DEGREES_LAT = 1 / 69.05

describe('buildTrailIndex', () => {
  it('measures cumulative miles from the southern end', () => {
    const index = buildTrailIndex(
      collection([
        line([
          [-77, 39],
          [-77, 39 + MILE_IN_DEGREES_LAT],
        ]),
      ]),
    )

    expect(index.miles[0]).toBe(0)
    expect(index.miles[1]).toBeCloseTo(1, 1)
  })

  it('flips a piece whose own coordinates run north-to-south', () => {
    // Same segment as above, written backwards. Mile 0 still has to be the
    // southern end, or a hiker walking north would watch their mile count down.
    const index = buildTrailIndex(
      collection([
        line([
          [-77, 39 + MILE_IN_DEGREES_LAT],
          [-77, 39],
        ]),
      ]),
    )

    expect(index.lats[0]).toBeCloseTo(39, 5)
    expect(index.miles[0]).toBe(0)
  })

  it('orders disconnected pieces south to north however they arrive', () => {
    const northern = line([
      [-77, 40],
      [-77, 40 + MILE_IN_DEGREES_LAT],
    ])
    const southern = line([
      [-77, 39],
      [-77, 39 + MILE_IN_DEGREES_LAT],
    ])

    const index = buildTrailIndex(collection([northern, southern]))

    expect(index.lats[0]).toBeCloseTo(39, 5)
    expect(index.lats[index.lats.length - 1]).toBeCloseTo(40 + MILE_IN_DEGREES_LAT, 5)
  })

  // Regression, caught against the real corridor rather than a fixture: with
  // the gaps counted, trails.geojson measured 4,055 miles against the AT's
  // real ~2,197. The straight-line jump from the end of one piece to the start
  // of the next is not trail, and a hiker's mile marker must not include it.
  it('does not count the gap between two disconnected pieces as distance walked', () => {
    const index = buildTrailIndex(
      collection([
        line([
          [-77, 39],
          [-77, 39 + MILE_IN_DEGREES_LAT],
        ]),
        // Starts a full degree north - a gap of about 69 miles.
        line([
          [-77, 40],
          [-77, 40 + MILE_IN_DEGREES_LAT],
        ]),
      ]),
    )

    // Two one-mile pieces total two miles, however far apart they sit.
    expect(index.totalMiles).toBeCloseTo(2, 1)
  })

  it('ignores spurs, so a mile marker always means distance along the AT itself', () => {
    const index = buildTrailIndex(
      collection([
        line([
          [-77, 39],
          [-77, 39 + MILE_IN_DEGREES_LAT],
        ]),
        line(
          [
            [-77, 39],
            [-76.9, 39],
          ],
          'spur',
        ),
      ]),
    )

    expect(index.lons).toHaveLength(2)
  })

  it('is empty rather than broken when there is no centerline at all', () => {
    const index = buildTrailIndex(collection([]))

    expect(index.lons).toHaveLength(0)
    expect(index.totalMiles).toBe(0)
  })

  // This runs on whatever bytes came out of a bucket. Every one of these
  // degrades to "we don't know where you are", which is survivable; a throw
  // here surfaces to the hiker as a failed download of data that in fact
  // arrived, and takes the POI search down with it.
  describe('given a payload that is not what it should be', () => {
    it('survives a collection with no features array', () => {
      const index = buildTrailIndex({
        type: 'FeatureCollection',
      } as unknown as FeatureCollection)

      expect(index.lons).toHaveLength(0)
    })

    it('survives a null geometry, which is valid GeoJSON in its own right', () => {
      const index = buildTrailIndex(collection([nullGeometry()]))

      expect(index.lons).toHaveLength(0)
    })

    it('keeps the good centerline pieces alongside a broken one', () => {
      // The case that matters most: one bad feature must not cost the map
      // every other mile marker in the file.
      const index = buildTrailIndex(
        collection([
          nullGeometry(),
          line([
            [-77, 39],
            [-77, 39 + MILE_IN_DEGREES_LAT],
          ]),
        ]),
      )

      expect(index.lons).toHaveLength(2)
      expect(index.totalMiles).toBeCloseTo(1, 1)
    })

    it('survives a LineString with no coordinates', () => {
      const index = buildTrailIndex(
        collection([
          {
            type: 'Feature',
            properties: { source: 'centerline' },
            geometry: { type: 'LineString' },
          } as unknown as Feature,
        ]),
      )

      expect(index.lons).toHaveLength(0)
    })
  })
})

describe('locateOnTrail', () => {
  const index = buildTrailIndex(
    collection([
      line(
        Array.from({ length: 50 }, (_, i) => [-77, 39 + i * MILE_IN_DEGREES_LAT * 0.1]),
      ),
    ]),
  )

  it('reports the mile of the nearest point on the trail', () => {
    const fix = locateOnTrail(index, { lon: -77, lat: 39 + MILE_IN_DEGREES_LAT })

    expect(fix?.mile).toBeCloseTo(1, 1)
  })

  it('reports how far off the trail the fix is', () => {
    const onTrail = locateOnTrail(index, { lon: -77, lat: 39 })
    expect(onTrail?.offTrailFeet).toBeCloseTo(0, 0)

    // A tenth of a degree of longitude at this latitude is several miles out.
    const wellOff = locateOnTrail(index, { lon: -76.9, lat: 39 })
    expect(wellOff?.offTrailFeet).toBeGreaterThan(20_000)
  })

  it('finds the trail across a latitude-bucket boundary', () => {
    // Buckets are 0.05 degrees, so a fix just below a boundary must still see
    // the trail points sitting just above it - otherwise a hiker's mile would
    // blank out at regular intervals up the trail.
    const boundary = 39.05
    const near = buildTrailIndex(
      collection([
        line([
          [-77, boundary + 0.0001],
          [-77, boundary + 0.001],
        ]),
      ]),
    )

    expect(locateOnTrail(near, { lon: -77, lat: boundary - 0.0001 })).not.toBeNull()
  })

  it('says it does not know rather than guessing when the fix is nowhere near the corridor', () => {
    expect(locateOnTrail(index, { lon: -122.4, lat: 37.8 })).toBeNull()
  })

  it('says it does not know when there is no trail data yet', () => {
    expect(
      locateOnTrail(buildTrailIndex(collection([])), { lon: -77, lat: 39 }),
    ).toBeNull()
  })

  it('says it does not know when a coordinate in the index is not a number', () => {
    // A payload that survived JSON.parse but carries a broken coordinate pair.
    // Every distance to it comes out NaN, so no candidate ever beats the
    // starting best - and the honest answer is "no idea", not the first index
    // in the list.
    const broken = buildTrailIndex(
      collection([
        {
          type: 'Feature',
          properties: { source: 'centerline' },
          geometry: {
            type: 'LineString',
            coordinates: [
              [NaN, 39],
              [NaN, 39.01],
            ],
          },
        } as Feature,
      ]),
    )

    expect(broken.lons).toHaveLength(2)
    expect(locateOnTrail(broken, { lon: -77, lat: 39 })).toBeNull()
  })
})
