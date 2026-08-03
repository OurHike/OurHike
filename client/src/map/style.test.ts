import { describe, it, expect } from 'vitest'
import { validateStyleMin } from '@maplibre/maplibre-gl-style-spec'
import { BLAZE_MATCH_EXPRESSION } from '../lib/blaze'
import {
  buildMapStyle,
  BLAZE_DASH_RHYTHMS,
  ATTRIBUTION,
  TOPO_SOURCE_ID,
  TRAILS_SOURCE_ID,
  BLAZE_LAYER_ID,
  TRAIL_CASING_LAYER_ID,
  BACKDROP_LAYER_ID,
  MAP_BACKGROUND_COLOR,
} from './style'
import { POI_LAYER_ID, POI_SOURCE_ID } from './poiLayers'

// See WIREFRAMES.md "Trail line rendering — blazes". Two rules there are
// load-bearing rather than decorative:
//   1. ONE `match` expression drives line-color for every trail source - no
//      per-layer hardcoded hexes, so a new imported source inherits the rule.
//   2. Dash rhythm is a SECOND, hue-independent channel, so warm hues stay
//      separable in greyscale and in glare (WIREFRAMES.md `9d`).

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

describe('buildMapStyle', () => {
  it('is a valid MapLibre style according to MapLibre’s own spec validator', () => {
    // Guards against typos and shape errors that hand-written assertions miss.
    expect(validateStyleMin(style())).toEqual([])
  })

  it('drives line-color from the single shared blaze match expression, not per-layer hexes', () => {
    const paint = layer(BLAZE_LAYER_ID).paint as Record<string, unknown>

    expect(paint['line-color']).toEqual(BLAZE_MATCH_EXPRESSION)
  })

  it('drives the dash rhythm from the same blaze_color attribute, as a second data-driven channel', () => {
    const paint = layer(BLAZE_LAYER_ID).paint as Record<string, unknown>
    const dash = paint['line-dasharray'] as unknown[]

    expect(dash[0]).toBe('match')
    expect(dash[1]).toEqual(['get', 'blaze_color'])
  })

  it.each([
    ['White', [10, 6]],
    ['Blue', [10, 6]],
    ['Yellow', [6, 5]],
    ['Orange', [10, 5]],
    ['Red', [15, 5]],
    ['Green', [13, 5]],
  ] as const)('uses WIREFRAMES.md’s exact dash rhythm for %s', (blaze, rhythm) => {
    expect(BLAZE_DASH_RHYTHMS[blaze]).toEqual(rhythm)
  })

  it('gives the neutral-grey fallback the sparse dotted rhythm, so undecoded lines read as uncertain', () => {
    expect(BLAZE_DASH_RHYTHMS.None).toEqual([4, 6])
  })

  it('keeps the warm hues pairwise-distinct by rhythm, so they survive greyscale and glare', () => {
    // The whole point of rhythm being a second channel: yellow/orange/red are
    // near-indistinguishable once desaturated (WIREFRAMES.md `9d`).
    const warm = (['Yellow', 'Orange', 'Red'] as const).map((b) =>
      BLAZE_DASH_RHYTHMS[b].join('/'),
    )

    expect(new Set(warm).size).toBe(warm.length)
  })

  it('draws a casing layer underneath the blaze layer, never over it', () => {
    const ids = style().layers.map((l) => l.id)

    expect(ids.indexOf(TRAIL_CASING_LAYER_ID)).toBeLessThan(ids.indexOf(BLAZE_LAYER_ID))
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
