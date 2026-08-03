import { describe, it, expect } from 'vitest'
import { validateStyleMin } from '@maplibre/maplibre-gl-style-spec'
import { BLAZE_MATCH_EXPRESSION } from '../lib/blaze'
import {
  buildMapStyle,
  ATTRIBUTION,
  TOPO_SOURCE_ID,
  TRAILS_SOURCE_ID,
  BLAZE_LAYER_ID,
  TRAIL_CASING_LAYER_ID,
  BACKDROP_LAYER_ID,
  MAP_BACKGROUND_COLOR,
  CENTERLINE_SOURCE,
  TRAIL_LINE_WIDTHS,
  DEFAULT_TRAIL_LINE_WIDTH,
  CASING_OVERHANG,
} from './style'
import { POI_LAYER_ID, POI_SOURCE_ID } from './poiLayers'

// See WIREFRAMES.md "Trail line rendering — blazes". Two rules there are
// load-bearing rather than decorative:
//   1. ONE `match` expression drives line-color for every trail source - no
//      per-layer hardcoded hexes, so a new imported source inherits the rule.
//   2. Trail lines are SOLID, and WIDTH is the second, hue-independent
//      channel: the AT centerline is the widest line on the map, so the
//      through-line survives greyscale and glare (WIREFRAMES.md `9d`) with
//      colour removed entirely. Dash rhythm used to carry that channel, and
//      the gaps it left were what made the near-white centerline unreadable -
//      what a hiker saw was a dotted grey-and-white thread, not a trail.

const STYLE_OPTIONS = {
  topoArchiveUrl: 'pmtiles://ourhike-corridor',
  trailsUrl: '/data/trails.geojson',
}

function style() {
  return buildMapStyle(STYLE_OPTIONS)
}

function layer(id: string) {
  const found = style().layers.find((l) => l.id === id)
  if (found === undefined) throw new Error(`no layer "${id}" in the style`)
  return found
}

/** What a `match` on `source` resolves to for one source key. */
function widthFor(expression: unknown, source: string): number {
  const [, , ...rest] = expression as unknown[]
  for (let i = 0; i + 1 < rest.length; i += 2) {
    if (rest[i] === source) return rest[i + 1] as number
  }
  return rest[rest.length - 1] as number
}

describe('buildMapStyle', () => {
  it('is a valid MapLibre style according to MapLibre’s own spec validator', () => {
    // Guards against typos and shape errors that hand-written assertions miss.
    expect(validateStyleMin(style())).toEqual([])
  })

  it('drives line-color from the single shared blaze match expression, not per-layer hexes', () => {
    const paint = layer(BLAZE_LAYER_ID).paint as Record<string, unknown>

    expect(paint['line-color']).toEqual(BLAZE_MATCH_EXPRESSION)
  })

  it('draws every trail line solid, so no line alternates with the casing beneath it', () => {
    // The regression this replaces a whole block of dash-rhythm assertions to
    // prevent from coming back. A dashed blaze over a dark casing is not a
    // coloured line - it is a line alternating between its blaze colour and
    // the casing showing through, and for the centerline, whose blaze is
    // near-white, the casing is the part that reads. Asserted across every
    // line layer bound to the trail source rather than on the blaze layer
    // alone, since a casing drawn dashed would leave exactly the same gaps.
    for (const l of style().layers) {
      if (l.type !== 'line' || !('source' in l) || l.source !== TRAILS_SOURCE_ID) continue

      expect(
        (l.paint as Record<string, unknown> | undefined)?.['line-dasharray'],
      ).toBeUndefined()
    }
  })

  it('drives line-width from the source attribute, as a second data-driven channel', () => {
    const paint = layer(BLAZE_LAYER_ID).paint as Record<string, unknown>
    const width = paint['line-width'] as unknown[]

    expect(width[0]).toBe('match')
    expect(width[1]).toEqual(['get', 'source'])
  })

  it('draws the AT centerline wider than every other trail, so the map has a subject', () => {
    // Width is what carries the hue-independent channel now. It has to be the
    // centerline that wins it: a hiker who cannot tell colours apart - in
    // glare, in greyscale, or at all - still needs to find the AT itself.
    const width = layer(BLAZE_LAYER_ID).paint as Record<string, unknown>
    const others = Object.entries(TRAIL_LINE_WIDTHS)
      .filter(([source]) => source !== CENTERLINE_SOURCE)
      .map(([, w]) => w)

    for (const other of [...others, DEFAULT_TRAIL_LINE_WIDTH]) {
      expect(widthFor(width['line-width'], CENTERLINE_SOURCE)).toBeGreaterThan(other)
    }
  })

  it('draws a source it has never heard of, rather than a zero-width line', () => {
    // A trail source imported later should reach the map on the fallback arm.
    // Drawn at nothing at all, it would be real data hidden behind a client
    // release - the same call poiLayers.ts makes for an unknown POI type.
    const paint = layer(BLAZE_LAYER_ID).paint as Record<string, unknown>

    expect(widthFor(paint['line-width'], 'some_source_added_in_2027')).toBeGreaterThan(0)
  })

  it('draws a casing layer underneath the blaze layer, never over it', () => {
    const ids = style().layers.map((l) => l.id)

    expect(ids.indexOf(TRAIL_CASING_LAYER_ID)).toBeLessThan(ids.indexOf(BLAZE_LAYER_ID))
  })

  it('overhangs that casing by the same hairline under a side trail as under the AT', () => {
    // A casing scaled proportionally instead of by a constant would be twice
    // as heavy under the centerline as under everything else, which reads as
    // a second, darker line rather than as an edge on the first one.
    const casing = layer(TRAIL_CASING_LAYER_ID).paint as Record<string, unknown>
    const blaze = layer(BLAZE_LAYER_ID).paint as Record<string, unknown>

    for (const source of [...Object.keys(TRAIL_LINE_WIDTHS), 'anything_else']) {
      const overhang =
        (widthFor(casing['line-width'], source) - widthFor(blaze['line-width'], source)) /
        2

      expect(overhang).toBe(CASING_OVERHANG)
    }
  })

  it('renders the topo raster beneath every trail layer', () => {
    const ids = style().layers.map((l) => l.id)

    expect(ids.indexOf('topo')).toBeLessThan(ids.indexOf(TRAIL_CASING_LAYER_ID))
  })

  it('paints a background under everything, so no camera position can show black', () => {
    // The corridor archive is a 30-mile strip. Panning off it, zooming out
    // below its minzoom, or opening the app before the download finishes all
    // leave the topo raster with nothing to draw - and a style with no
    // background layer draws nothing at all there, which composites to black.
    const backdrop = layer(BACKDROP_LAYER_ID)

    expect(backdrop.type).toBe('background')
    expect((backdrop.paint as Record<string, unknown>)['background-color']).toBe(
      MAP_BACKGROUND_COLOR,
    )
  })

  it('puts that background first, beneath every other layer', () => {
    expect(style().layers[0].id).toBe(BACKDROP_LAYER_ID)
  })

  it('needs no source for the background, so it survives a missing archive', () => {
    // A background layer bound to a source would go blank in exactly the case
    // it exists to cover: the archive absent or unreadable.
    expect(layer(BACKDROP_LAYER_ID)).not.toHaveProperty('source')
  })

  it('uses fully opaque paper, not a colour with alpha that black could show through', () => {
    expect(MAP_BACKGROUND_COLOR).toMatch(/^#[0-9a-f]{6}$/i)
  })

  it('reads the basemap from the pmtiles archive URL it was given', () => {
    const source = style().sources[TOPO_SOURCE_ID] as Record<string, unknown>

    expect(source.type).toBe('raster')
    expect(source.url).toBe(STYLE_OPTIONS.topoArchiveUrl)
  })

  it('reads trails from the local exported file, with no network path', () => {
    const source = style().sources[TRAILS_SOURCE_ID] as Record<string, unknown>

    expect(source.data).toBe(STYLE_OPTIONS.trailsUrl)
  })

  it('spells OpenStreetMap out in full, which is what ODbL attribution actually requires', () => {
    // WIREFRAMES.md's map-corner copy shows the "© OSM" shorthand, but its own
    // Assets section requires a visible "© OpenStreetMap" - the abbreviation
    // does not satisfy the licence. Full form wins.
    expect(ATTRIBUTION).toContain('© OpenStreetMap')
    expect(ATTRIBUTION).toContain('USGS US Topo')
  })

  it('attaches that attribution to every data source, so none can ship uncredited', () => {
    const sources = style().sources as Record<string, Record<string, unknown>>

    for (const id of [TOPO_SOURCE_ID, TRAILS_SOURCE_ID, POI_SOURCE_ID]) {
      expect(sources[id].attribution).toBe(ATTRIBUTION)
    }
  })
})

describe('POI pins', () => {
  it('draws them at all, which for a long time it did not', () => {
    // The regression this file exists to prevent from coming back: shelters,
    // water, campsites, resupply and crossings were fetched, stored,
    // searchable and counted in the legend, and the style had no layer that
    // could put any of them on the map. "Which of these is closest to me" is a
    // map question, and it could only be answered through a list.
    expect(layer(POI_LAYER_ID).type).toBe('symbol')
  })

  it('draws every pin over the trail line, never under it', () => {
    const ids = style().layers.map((l) => l.id)

    expect(ids.indexOf(BLAZE_LAYER_ID)).toBeLessThan(ids.indexOf(POI_LAYER_ID))
  })

  it('starts the POI source empty, to be filled once the download lands', () => {
    // POIs are read out of IndexedDB long after the map is built. Baking them
    // into the style would mean rebuilding the style to show them, and a style
    // rebuild takes the WebGL context down with it.
    const source = style().sources[POI_SOURCE_ID] as Record<string, unknown>

    expect(source.type).toBe('geojson')
    expect(source.data).toEqual({ type: 'FeatureCollection', features: [] })
  })

  it('declares no glyphs URL, and so must never ask for text', () => {
    // Fonts are fetched. There is no network on a mountain, so the style
    // cannot have a glyphs URL - which means a `text-field` anywhere in it
    // fails in the field and nowhere else. Asserted on the whole style rather
    // than on the pin layer, since the rule binds every layer.
    expect(style()).not.toHaveProperty('glyphs')

    for (const l of style().layers) {
      expect(
        (l.layout as Record<string, unknown> | undefined)?.['text-field'],
      ).toBeUndefined()
    }
  })
})
