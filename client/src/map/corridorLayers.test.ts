import { describe, it, expect } from 'vitest'
import type { Feature, FeatureCollection } from 'geojson'
import { buildTrailIndex } from '../lib/trailPosition'
import { NEUTRAL_BLAZE_COLOR } from '../lib/blaze'
import { parseClubSections, type ClubSections } from '../lib/clubSections'
import {
  BOUNDARY_KIND,
  CORRIDOR_BOUNDARY_LAYER_ID,
  CORRIDOR_KIND_PROPERTY,
  CORRIDOR_MAX_ZOOM,
  CORRIDOR_UNATTRIBUTED_CASING_LAYER_ID,
  CORRIDOR_UNATTRIBUTED_LAYER_ID,
  UNATTRIBUTED_KIND,
  buildCorridorLayers,
  corridorFeatures,
} from './corridorLayers'
import {
  BLAZE_LAYER_ID,
  BLAZE_LINE_WIDTH,
  CASING_LINE_WIDTH,
  buildMapStyle,
} from './style'
import { POI_PIN_MIN_ZOOM } from './poiLayers'

const MILE_IN_DEGREES_LAT = 1 / 69.05
const CASING = '#14130f'

/** The trail paint style.ts hands down, so the corridor is measured against
 *  the same numbers the blaze layer is actually drawn with. */
const TRAIL_PAINT = {
  casingColor: CASING,
  blazeWidth: BLAZE_LINE_WIDTH,
  casingWidth: CASING_LINE_WIDTH,
}

function collection(features: Feature[]): FeatureCollection {
  return { type: 'FeatureCollection', features }
}

/** A straight north-running centerline, one vertex per mile. */
function straightTrail(miles: number) {
  return buildTrailIndex(
    collection([
      {
        type: 'Feature',
        properties: { source: 'centerline' },
        geometry: {
          type: 'LineString',
          coordinates: Array.from({ length: miles + 1 }, (_, i): [number, number] => [
            -77,
            39 + i * MILE_IN_DEGREES_LAT,
          ]),
        },
      },
    ]),
  )
}

/** Two clubs abutting at mile 10, with 20-30 unattributed behind them. */
function sections(): ClubSections {
  return parseClubSections({
    clubs: [
      {
        acronym: 'GATC',
        name: 'Georgia Appalachian Trail Club',
        stretches: [{ start_mile: 0, end_mile: 10 }],
      },
      {
        acronym: 'NHC',
        name: 'Nantahala Hiking Club',
        stretches: [{ start_mile: 10, end_mile: 20 }],
      },
      {
        acronym: 'MATC',
        name: 'Maine Appalachian Trail Club',
        stretches: [{ start_mile: 30, end_mile: 40 }],
      },
    ],
    unattributed: [{ start_mile: 20, end_mile: 30 }],
  })
}

function kindsOf(features: ReturnType<typeof corridorFeatures>['features']) {
  return features.map((f) => f.properties[CORRIDOR_KIND_PROPERTY])
}

describe('corridorFeatures', () => {
  it('draws the miles nobody can name, and only those', () => {
    // The attributed runs are NOT drawn: the blaze layer is already painting
    // them white, and the whole two-colour decision is that the corridor adds
    // grey rather than repainting the trail.
    const drawn = corridorFeatures(sections(), straightTrail(40))
    const lines = drawn.features.filter(
      (f) => f.properties[CORRIDOR_KIND_PROPERTY] === UNATTRIBUTED_KIND,
    )
    expect(lines).toHaveLength(1)
    expect(lines[0].geometry.type).toBe('MultiLineString')
  })

  it('puts a mark where responsibility changes hands', () => {
    // Three boundaries in this fixture - 10, 20 and 30 - and not the trail's
    // two outer ends, which are where the trail stops rather than where the
    // answer changes.
    const drawn = corridorFeatures(sections(), straightTrail(40))
    const marks = drawn.features.filter(
      (f) => f.properties[CORRIDOR_KIND_PROPERTY] === BOUNDARY_KIND,
    )
    expect(marks).toHaveLength(3)
    expect(marks.every((m) => m.geometry.type === 'Point')).toBe(true)
  })

  it('drops what the centerline index cannot place, rather than guessing at it', () => {
    // A ten-mile index cannot locate mile 20-30. That is a gap in what this
    // build knows, and the tap sheet still answers from the mile numbers - so
    // dropping the geometry costs a drawn run and no sentence.
    const drawn = corridorFeatures(sections(), straightTrail(10))
    expect(kindsOf(drawn.features)).not.toContain(UNATTRIBUTED_KIND)
  })

  it('draws nothing at all for a release that publishes no attribution', () => {
    const drawn = corridorFeatures(parseClubSections({}), straightTrail(40))
    expect(drawn.features).toEqual([])
  })
})

/**
 * The seam, and the two colours.
 *
 * These are the assertions that keep #598's decisions from being undone by a
 * later change that looks reasonable on its own. Both were the maintainer's
 * calls on 2026-08-19 and neither is visible from the code alone.
 */
describe('the corridor layers', () => {
  const layers = buildCorridorLayers(TRAIL_PAINT)

  it('stops every layer at the seam, where the map changes subject', () => {
    // Above POI_PIN_MIN_ZOOM a hiker is navigating by the line. Nothing in the
    // corridor view may follow them up there - which is the other half of
    // style.test.ts's "a blaze never changes colour where a hiker is
    // navigating by it".
    expect(layers).not.toHaveLength(0)
    for (const layer of layers) {
      expect({ id: layer.id, maxzoom: layer.maxzoom }).toEqual({
        id: layer.id,
        maxzoom: POI_PIN_MIN_ZOOM,
      })
    }
    expect(CORRIDOR_MAX_ZOOM).toBe(POI_PIN_MIN_ZOOM)
  })

  it('spends no colour beyond the neutral grey and the sheet’s own casing', () => {
    // "Only use 2 colours - the blaze colour and neutral" (2026-08-19). The
    // blaze is not repainted, so what this may introduce is the grey; the
    // casing is the sheet's, already on every trail line.
    const painted = layers.flatMap((layer) =>
      Object.entries(layer.paint ?? {})
        .filter(([property]) => property.endsWith('color'))
        .map(([, value]) => value),
    )
    expect(painted).not.toHaveLength(0)
    expect(new Set(painted)).toEqual(new Set([NEUTRAL_BLAZE_COLOR, CASING]))
  })

  it('carries a casing wide enough to cover the blaze the dash sits over', () => {
    // A dashed grey line alone shows the WHITE BLAZE through every gap, which
    // is the dotted grey-and-white thread WIREFRAMES.md section 3's superseded
    // note records failing. The casing covers it first, so the gaps show the
    // casing like every other trail line here.
    const casing = layers.find((l) => l.id === CORRIDOR_UNATTRIBUTED_CASING_LAYER_ID)
    const dash = layers.find((l) => l.id === CORRIDOR_UNATTRIBUTED_LAYER_ID)
    const casingWidth = (casing?.paint as Record<string, number>)['line-width']
    const dashWidth = (dash?.paint as Record<string, number>)['line-width']

    expect((dash?.paint as Record<string, unknown>)['line-dasharray']).toBeDefined()
    expect(casingWidth).toBeGreaterThan(dashWidth)
    // Exactly the blaze's width, not merely enough today: a grey narrower than
    // the white leaves a hairline of trail down both sides of every
    // unattributed run, and a wider one thickens the corridor where the answer
    // is least certain.
    expect(dashWidth).toBe(BLAZE_LINE_WIDTH)
    expect(casingWidth).toBe(CASING_LINE_WIDTH)
  })

  it('draws the casing before the dash, or the dash is covered by its own casing', () => {
    const order = layers.map((l) => l.id)
    expect(order.indexOf(CORRIDOR_UNATTRIBUTED_CASING_LAYER_ID)).toBeLessThan(
      order.indexOf(CORRIDOR_UNATTRIBUTED_LAYER_ID),
    )
  })

  it('asks for no text, since the offline sheet has no font to draw it in', () => {
    // map/style.test.ts asserts the whole style; this asserts the layers this
    // module contributes, so the reason travels with the code that would
    // otherwise be the first to break it.
    for (const layer of layers) {
      expect(
        (layer.layout as Record<string, unknown> | undefined)?.['text-field'],
      ).toBeUndefined()
    }
  })
})

describe('the corridor in the built style', () => {
  const STYLE_OPTIONS = {
    topoArchiveUrl: 'pmtiles://ourhike-corridor',
    trailsUrl: '/data/trails.geojson',
    background: 'usgs_topo_offline' as const,
  }

  it('paints the grey over the blaze, not under it', () => {
    // Under the blaze the grey would be invisible: the white line is drawn at
    // the same width, straight over the top of it.
    const ids = buildMapStyle(STYLE_OPTIONS).layers.map((l) => l.id)
    expect(ids.indexOf(BLAZE_LAYER_ID)).toBeLessThan(
      ids.indexOf(CORRIDOR_UNATTRIBUTED_LAYER_ID),
    )
  })

  it('leaves closures and the route above it', () => {
    // A barrier across the trail, or the line a hiker is building, both matter
    // more than who maintains the ground under them.
    const ids = buildMapStyle(STYLE_OPTIONS).layers.map((l) => l.id)
    const corridor = ids.indexOf(CORRIDOR_BOUNDARY_LAYER_ID)
    const closures = ids.findIndex((id) => id.includes('closure'))
    expect(closures).toBeGreaterThan(corridor)
  })
})
