import { describe, it, expect } from 'vitest'
import { viewportMiles } from './viewportMiles'
import { buildTrailIndex } from './trailPosition'
import type { FeatureCollection } from 'geojson'

// The span this returns is what keeps the ribbon and the map saying the same
// thing (#910 review), so what is worth testing is the two ways a span can lie:
// claiming ground that is not on screen, and missing ground that is.

/** A centerline running due north up one meridian, a vertex every 0.01 degrees
 *  - about 0.7 miles apart, which is fine enough for the assertions below and
 *  coarse enough to keep the fixture readable. */
function northboundLine(): FeatureCollection {
  const coordinates: Array<[number, number]> = []
  for (let i = 0; i <= 100; i += 1) {
    coordinates.push([-77, 34 + i * 0.01])
  }
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

const index = buildTrailIndex(northboundLine())

describe('viewportMiles', () => {
  it('spans only the trail actually inside the box', () => {
    const span = viewportMiles(index, {
      west: -77.5,
      east: -76.5,
      south: 34.2,
      north: 34.4,
    })

    expect(span).not.toBeNull()
    // The vertex at 34.2 and the one at 34.4 bound it, and both are real
    // positions on the index's own axis rather than an interpolation.
    const low = viewportMiles(index, {
      west: -77.5,
      east: -76.5,
      south: 34.2,
      north: 34.2,
    })
    expect(span!.startMile).toBeCloseTo(low!.startMile, 6)
    expect(span!.endMile).toBeGreaterThan(span!.startMile)
  })

  it('grows as the box grows, and never shrinks below what is on screen', () => {
    const tight = viewportMiles(index, {
      west: -77.1,
      east: -76.9,
      south: 34.4,
      north: 34.5,
    })!
    const wide = viewportMiles(index, {
      west: -77.1,
      east: -76.9,
      south: 34.2,
      north: 34.7,
    })!

    expect(wide.startMile).toBeLessThan(tight.startMile)
    expect(wide.endMile).toBeGreaterThan(tight.endMile)
  })

  it('excludes trail that is at the right latitude but off to the side', () => {
    // The buckets are latitude-only (lib/trailPosition.ts), so a box east of
    // the corridor would match every vertex in the band unless longitude is
    // tested too. This is that test.
    expect(
      viewportMiles(index, { west: -70, east: -69, south: 34.2, north: 34.4 }),
    ).toBeNull()
  })

  it('returns null when no centerline vertex is in view at all', () => {
    expect(
      viewportMiles(index, { west: -100, east: -99, south: 10, north: 11 }),
    ).toBeNull()
  })

  it('reads a box given corner-swapped the same way', () => {
    // MapLibre hands back a normalised box, but nothing in the type says so,
    // and a ribbon that silently drew nothing would be a hard bug to find.
    const normal = viewportMiles(index, {
      west: -77.5,
      east: -76.5,
      south: 34.2,
      north: 34.4,
    })
    const swapped = viewportMiles(index, {
      west: -76.5,
      east: -77.5,
      south: 34.4,
      north: 34.2,
    })

    expect(swapped).toEqual(normal)
  })
})
