import { describe, it, expect } from 'vitest'
import { closureDraft, closureGeometry, CLOSURE_REASONS } from './closureDraft'
import { buildTrailIndex } from './trailPosition'
import type { FeatureCollection } from 'geojson'

// The geometry half of #832. What this file is really guarding is the reason
// the geometry exists at all (#674): a mile is a reading against one
// measurement of the centerline, so the POINTS are the anchor and the miles
// are a per-release projection of them. Capture goes wrong in two ways that
// both look fine from the outside - a transposed lon/lat pair, and a
// half-captured closure - and neither is visible downstream.

/** A short straight run of trail, roughly 0.0691 miles per 0.001° of
 *  latitude at this longitude - the numbers below are read off the index
 *  rather than assumed, so this fixture only has to be monotonic. */
function fixture(): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        // `source: 'centerline'` is what puts a feature on the mile axis at
        // all - anything else is tread and gets no miles (trailPosition.ts).
        properties: { source: 'centerline' },
        geometry: {
          type: 'LineString',
          coordinates: [
            [-73.9, 41.0],
            [-73.9, 41.01],
            [-73.9, 41.02],
            [-73.9, 41.03],
          ],
        },
      },
    ],
  }
}

describe('closureGeometry', () => {
  it('answers lat and lon the right way round', () => {
    const index = buildTrailIndex(fixture())
    const last = index.miles[index.miles.length - 1]

    const geometry = closureGeometry(index, 0, last)

    expect(geometry).not.toBeNull()
    // The failure this exists to catch: `trailPointAtMile` answers GeoJSON
    // order, [lon, lat], and the wire's field order is the other way. A
    // silent transposition puts every closure this app files off the coast
    // of Somalia, and nothing downstream can tell.
    expect(geometry?.start_lat).toBeCloseTo(41.0, 5)
    expect(geometry?.start_lon).toBeCloseTo(-73.9, 5)
    expect(geometry?.end_lat).toBeCloseTo(41.03, 5)
    expect(geometry?.end_lon).toBeCloseTo(-73.9, 5)
  })

  it('gives nothing at all when only one end can be placed', () => {
    const index = buildTrailIndex(fixture())
    const last = index.miles[index.miles.length - 1]

    // A far end past the end of the published trail: `trailPointAtMile`
    // returns null rather than extrapolating.
    const geometry = closureGeometry(index, 0, last + 50)

    // All four or none. Half a closure's geometry is a row that LOOKS
    // anchored - and projectClosure would then read a stretch measured half
    // against one ruler and half against another, whose length is the
    // difference between two rulers rather than a distance.
    expect(geometry).toBeNull()
  })

  it('gives nothing when the phone has no trail index yet', () => {
    // The ordinary first-run state, and not a failure: a closure with no
    // geometry is exactly what every closure filed before this form looks
    // like, and the projection already knows to show the mile as stored.
    expect(closureGeometry(null, 10, 12)).toBeNull()
  })
})

describe('closureDraft', () => {
  it('carries the miles as authored and the points beside them', () => {
    const index = buildTrailIndex(fixture())
    const last = index.miles[index.miles.length - 1]

    const draft = closureDraft(
      { reason: 'flooding', startMile: 0, endMile: last, note: '  ford is chest deep  ' },
      index,
    )

    expect(draft.reason_type).toBe('flooding')
    expect(draft.start_mile_marker).toBe(0)
    expect(draft.end_mile_marker).toBe(last)
    expect(draft.note).toBe('ford is chest deep')
    expect(draft.start_lat).toBeCloseTo(41.0, 5)
  })

  it('leaves a reversed pair reversed, for the server to normalise', () => {
    const index = buildTrailIndex(fixture())
    const last = index.miles[index.miles.length - 1]

    const draft = closureDraft({ reason: 'other', startMile: last, endMile: 0 }, index)

    // Not sorted here on purpose. `ClosureCreate` swaps the miles AND the
    // geometry together (#257 meeting #674); normalising in two places is
    // how the two come to disagree, and a pair whose points and miles were
    // ordered by different rules is a closure whose ends are each other's.
    expect(draft.start_mile_marker).toBe(last)
    expect(draft.end_mile_marker).toBe(0)
    expect(draft.start_lat).toBeCloseTo(41.03, 5)
    expect(draft.end_lat).toBeCloseTo(41.0, 5)
  })

  it('omits the note key entirely rather than sending an empty one', () => {
    const draft = closureDraft(
      { reason: 'other', startMile: 1, endMile: 1, note: '   ' },
      null,
    )

    expect('note' in draft).toBe(false)
    expect('start_lat' in draft).toBe(false)
  })

  it('offers only reasons the column accepts', () => {
    // The vocabulary is the backend's `ReasonType` and cannot be widened
    // here; what this file chooses is how the five READ to somebody standing
    // in front of the thing.
    expect(CLOSURE_REASONS.map((option) => option.id)).toEqual([
      'storm_damage',
      'flooding',
      'maintenance',
      'relocation',
      'other',
    ])
    // "other" is "Something else" here and "Closed" on a banner, and that is
    // deliberate: the two answer different questions.
    expect(CLOSURE_REASONS.at(-1)?.label).toBe('Something else')
  })
})
