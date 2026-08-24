import { describe, it, expect } from 'vitest'
import type { Feature, FeatureCollection } from 'geojson'
import { buildTrailIndex } from '../lib/trailPosition'
import { NEUTRAL_BLAZE_COLOR } from '../lib/blaze'
import { parseClubSections, type ClubSections } from '../lib/clubSections'
import { parseHighlights } from '../lib/highlights'
import { CLOSURE_LAYER_ID, LONG_TERM_CLOSURE_LAYER_ID } from '../lib/closureStyle'
import {
  BOUNDARY_KIND,
  CORRIDOR_BOUNDARY_LAYER_ID,
  CORRIDOR_HIGHLIGHT_LAYER_ID,
  CORRIDOR_KIND_PROPERTY,
  CORRIDOR_MAX_ZOOM,
  CORRIDOR_UNATTRIBUTED_CASING_LAYER_ID,
  CORRIDOR_UNATTRIBUTED_LAYER_ID,
  UNATTRIBUTED_KIND,
  HIGHLIGHT_ID_PROPERTY,
  HIGHLIGHT_KIND,
  buildCorridorLayers,
  corridorFeatures,
  corridorWithHighlights,
  highlightFeatures,
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
const SELECTION = '#c1611a'

const TRAIL_PAINT = {
  casingColor: CASING,
  selectionColor: SELECTION,
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

  it('spends no colour on a LINE beyond the neutral grey and the casing', () => {
    // "Only use 2 colours - the blaze colour and neutral" (2026-08-19). The
    // rule is about the trail itself: the blaze is not repainted, so the only
    // colour a line here may introduce is the grey, over the casing every
    // trail line already has.
    const lineColors = layers
      .filter((layer) => layer.type === 'line')
      .flatMap((layer) =>
        Object.entries(layer.paint ?? {})
          .filter(([property]) => property.endsWith('color'))
          .map(([, value]) => value),
      )
    expect(lineColors).not.toHaveLength(0)
    expect(new Set(lineColors)).toEqual(new Set([NEUTRAL_BLAZE_COLOR, CASING]))
  })

  it('lets a MARK carry the selection colour, which is not a trail line', () => {
    // A highlight is the one thing down here a hiker is meant to reach for,
    // and it is drawn BESIDE the corridor rather than on it - which is what
    // keeps the two-colour rule about the trail intact. The approved mock-up
    // draws these in the app's blaze orange.
    const mark = layers.find((l) => l.id === CORRIDOR_HIGHLIGHT_LAYER_ID)
    expect((mark?.paint as Record<string, unknown>)['circle-color']).toBe(SELECTION)
  })

  it('never lets the selection colour touch a line layer', () => {
    // The failure this guards: painting the corridor itself orange, which is
    // recolouring a blaze by another name.
    for (const layer of layers.filter((l) => l.type === 'line')) {
      const paint = Object.values(layer.paint ?? {})
      expect(paint).not.toContain(SELECTION)
    }
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

  it('draws a highlight mark over the boundary ticks, not under them', () => {
    // These two collide often at corridor zooms rather than rarely - a pixel
    // is several trail miles at z5, the mark is 5 px, and the ~30 club
    // boundaries average ~73 miles apart. Under the ticks, a neutral 2.6 px
    // dot sits in the middle of the one mark a hiker is meant to tap.
    const order = layers.map((l) => l.id)
    expect(order.indexOf(CORRIDOR_BOUNDARY_LAYER_ID)).toBeLessThan(
      order.indexOf(CORRIDOR_HIGHLIGHT_LAYER_ID),
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
    //
    // NAMED LAYERS RATHER THAN A SUBSTRING MATCH ON 'closure'. This read
    // `ids.findIndex((id) => id.includes('closure'))`, which asked "is the
    // first layer with 'closure' in its name above the corridor" - a question
    // about whatever happens to sort first, not about the chosen trail's
    // barriers. #950 added a closure band over the NEARBY-trail source, which
    // sits UNDER the chosen trail's whole stack by design and so appears
    // earlier, and the loose match read that correct ordering as this
    // property being broken. The property itself never changed.
    const ids = buildMapStyle(STYLE_OPTIONS).layers.map((l) => l.id)
    const corridor = ids.indexOf(CORRIDOR_BOUNDARY_LAYER_ID)

    for (const id of [CLOSURE_LAYER_ID, LONG_TERM_CLOSURE_LAYER_ID]) {
      expect(ids.indexOf(id), id).toBeGreaterThan(corridor)
    }
  })
})

/** Two highlights on the A.T., one of them a loop that leaves it. */
function highlights() {
  return parseHighlights({
    highlights: [
      {
        id: 'mcafee-knob',
        name: 'McAfee Knob',
        bases: ['named'],
        legs: [{ trail: 'AT', start_mile: 5, end_mile: 8 }],
      },
      {
        id: 'franconia-loop',
        name: 'Franconia Ridge Loop',
        bases: ['named'],
        legs: [
          { trail: 'AT', start_mile: 20, end_mile: 21.7 },
          { trail: 'Falling Waters Trail', start_mile: 0, end_mile: 3.2 },
        ],
      },
    ],
  })
}

describe('highlightFeatures', () => {
  it('marks where each walk begins', () => {
    const drawn = highlightFeatures(highlights(), straightTrail(40))
    expect(drawn.features).toHaveLength(2)
    expect(drawn.features.every((f) => f.geometry.type === 'Point')).toBe(true)
  })

  it('marks a loop once, not once per leg', () => {
    // Three marks for one walk would read as three walks.
    const drawn = highlightFeatures(highlights(), straightTrail(40))
    const loop = drawn.features.filter(
      (f) => f.properties[HIGHLIGHT_ID_PROPERTY] === 'franconia-loop',
    )
    expect(loop).toHaveLength(1)
  })

  it('carries the id, so a tap can resolve to a record', () => {
    const drawn = highlightFeatures(highlights(), straightTrail(40))
    expect(drawn.features.map((f) => f.properties[HIGHLIGHT_ID_PROPERTY]).sort()).toEqual(
      ['franconia-loop', 'mcafee-knob'],
    )
    expect(drawn.features[0].properties[CORRIDOR_KIND_PROPERTY]).toBe(HIGHLIGHT_KIND)
  })

  it('drops a highlight the centerline index cannot place', () => {
    // A gap in what this build knows. The sheet still answers from the mile
    // numbers, so what is lost is the mark and not the record.
    expect(highlightFeatures(highlights(), straightTrail(4)).features).toEqual([])
  })

  it('marks a loop written in walking order, whose A.T. leg is not first', () => {
    // Franconia Ridge really is walked Falling Waters up, A.T. along the
    // ridge, Old Bridle Path down - so leg zero is off the A.T. and the mile
    // that can be drawn is on leg one. Keyed off leg zero this record would
    // simply not be on the map.
    const walkingOrder = parseHighlights({
      highlights: [
        {
          id: 'franconia-loop',
          name: 'Franconia Ridge Loop',
          bases: ['named'],
          legs: [
            { trail: 'Falling Waters Trail', start_mile: 0, end_mile: 3.2 },
            { trail: 'AT', start_mile: 20, end_mile: 21.7 },
            { trail: 'Old Bridle Path', start_mile: 0, end_mile: 4 },
          ],
        },
      ],
    })
    const drawn = highlightFeatures(walkingOrder, straightTrail(40))
    expect(drawn.features).toHaveLength(1)
    expect(drawn.features[0].properties[HIGHLIGHT_ID_PROPERTY]).toBe('franconia-loop')
  })

  it('draws no mark for a highlight that never touches the A.T.', () => {
    // There is no honest place to put it on a map of this trail. The record
    // survives; only the mark is absent.
    const elsewhere = parseHighlights({
      highlights: [
        {
          id: 'welch-dickey',
          name: 'Welch-Dickey Loop',
          bases: ['named'],
          legs: [{ trail: 'Welch-Dickey Loop Trail', start_mile: 0, end_mile: 4.4 }],
        },
      ],
    })
    expect(highlightFeatures(elsewhere, straightTrail(40)).features).toEqual([])
  })

  it('draws nothing for a release that publishes no highlights', () => {
    expect(highlightFeatures([], straightTrail(40)).features).toEqual([])
  })
})

describe('corridorWithHighlights', () => {
  it('puts the corridor and the marks in one source', () => {
    // One source because they are one answer about the same stretch of map,
    // and a second would be a second thing to keep in step.
    const drawn = corridorWithHighlights(sections(), highlights(), straightTrail(40))
    const kinds = new Set(drawn.features.map((f) => f.properties[CORRIDOR_KIND_PROPERTY]))
    expect(kinds).toEqual(new Set([UNATTRIBUTED_KIND, BOUNDARY_KIND, HIGHLIGHT_KIND]))
  })
})
