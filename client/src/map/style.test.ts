import { describe, it, expect } from 'vitest'
import {
  createExpression,
  latest,
  validateStyleMin,
} from '@maplibre/maplibre-gl-style-spec'
import { BLAZE_MATCH_EXPRESSION } from '../lib/blaze'
import { OSM_CREDIT, USGS_TOPO_CREDIT } from './credits'
import {
  buildMapStyle,
  TOPO_SOURCE_ID,
  TRAILS_SOURCE_ID,
  BLAZE_LAYER_ID,
  TRAIL_CASING_LAYER_ID,
  BACKDROP_LAYER_ID,
  MAP_BACKGROUND_COLOR,
  CENTERLINE_SOURCE,
  PRIMARY_TRAIL_SOURCES,
  PRIMARY_TRAIL_WIDTH,
  TRAIL_LINE_WIDTHS,
  DEFAULT_TRAIL_LINE_WIDTH,
  CASING_OVERHANG,
  TOPO_LAYER_ID,
  MAP_BACKDROP,
  ARCHIVE_RASTER_PAINT,
  attachMapTheme,
} from './style'
import { LIVE_TOPO_LAYER_IDS, TOPO_PALETTE, TOPO_PALETTE_DARK } from './liveTopo'
import { POI_LAYER_ID, POI_SOURCE_ID } from './poiLayers'
import { CAMERA_ZOOM_TILE_OFFSET } from '../lib/archiveCoverage'

// See WIREFRAMES.md "Trail line rendering — blazes". Three rules there are
// load-bearing rather than decorative:
//   1. ONE `match` expression drives line-color for every trail source - no
//      per-layer hardcoded hexes, so a new imported source inherits the rule.
//   2. Trail lines are SOLID, and WIDTH is the second, hue-independent
//      channel: the AT centerline is the widest line on the map, so the
//      through-line survives greyscale and glare (WIREFRAMES.md `9d`) with
//      colour removed entirely. Dash rhythm used to carry that channel, and
//      the gaps it left were what made the near-white centerline unreadable -
//      what a hiker saw was a dotted grey-and-white thread, not a trail.
//   3. A side trail never covers the through-route it branches from. They
//      share geometry often enough that leaving it to export order put grey
//      and blue stretches through the white AT.

// The background is PINNED rather than left to the default, and that is the
// point of the `as const`. This file is about the offline sheet - the archive
// raster, the trail lines, the pins, the paper - and every rule it asserts is
// a rule about that style. Left implicit, `background` defaulted to the live
// sheet and these cases only passed because a live style with no terrain used
// to collapse into the offline one. The day that collapse was fixed, twenty-
// four tests silently changed subject and the glyphs case below started
// failing for a reason that had nothing to do with POI pins.
//
// The live sheet has its own file (liveTopo.test.ts), which is where a live
// style's glyphs and text-fields are asserted.
const STYLE_OPTIONS = {
  topoArchiveUrl: 'pmtiles://ourhike-corridor',
  trailsUrl: '/data/trails.geojson',
  background: 'usgs_topo_offline' as const,
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

/**
 * What one trail line's sort key comes out as, evaluated by MapLibre's own
 * expression engine rather than by reading the array back.
 *
 * Draw order is the thing under test here, and it is decided at render time
 * from a feature's properties - so the assertion has to go through the same
 * evaluator MapLibre will, or it is checking the shape of an expression
 * instead of the order it produces.
 */
function sortKeyFor(layerId: string, source: string): number {
  const layout = layer(layerId).layout as Record<string, unknown>
  const compiled = createExpression(
    layout['line-sort-key'] as never,
    latest.layout_line['line-sort-key'] as never,
  )
  if (compiled.result === 'error') {
    throw new Error(`line-sort-key on "${layerId}" is not a valid expression`)
  }
  return compiled.value.evaluate({ zoom: 14 }, { properties: { source } } as never)
}

/** Every trail layer bound to the trail source - casing and blaze alike. */
function trailLayerIds(): string[] {
  return style()
    .layers.filter(
      (l) => l.type === 'line' && 'source' in l && l.source === TRAILS_SOURCE_ID,
    )
    .map((l) => l.id)
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

  it('draws every through-route wider than every side trail, so the map has a subject', () => {
    // Width is what carries the hue-independent channel now, and a
    // through-route has to win it: a hiker who cannot tell colours apart - in
    // glare, in greyscale, or at all - still needs to find the trail the map
    // is about. Asserted over the whole primary tier rather than over the
    // centerline alone, because the tier is where a second system lands.
    const width = layer(BLAZE_LAYER_ID).paint as Record<string, unknown>
    const others = Object.entries(TRAIL_LINE_WIDTHS)
      .filter(([source]) => !PRIMARY_TRAIL_SOURCES.includes(source))
      .map(([, w]) => w)

    expect(PRIMARY_TRAIL_SOURCES.length).toBeGreaterThan(0)
    for (const primary of PRIMARY_TRAIL_SOURCES) {
      for (const other of [...others, DEFAULT_TRAIL_LINE_WIDTH]) {
        expect(widthFor(width['line-width'], primary)).toBeGreaterThan(other)
      }
    }
  })

  it('draws every source in the primary tier at the same through-route width', () => {
    // The tier is a role, not another name for the AT. The NYNJTC maintains
    // several trail systems, so a second through-route is a question of when
    // rather than if, and it should arrive by joining PRIMARY_TRAIL_SOURCES -
    // not by adding a layer, a width or a branch. Holding the whole list to
    // one width is what keeps that a one-line change; it also means this test
    // covers a source that does not exist yet, the day someone adds it.
    const paint = layer(BLAZE_LAYER_ID).paint as Record<string, unknown>

    for (const source of PRIMARY_TRAIL_SOURCES) {
      expect(widthFor(paint['line-width'], source)).toBe(PRIMARY_TRAIL_WIDTH)
    }
  })

  it('draws a source it has never heard of, rather than a zero-width line', () => {
    // A trail source imported later should reach the map on the fallback arm.
    // Drawn at nothing at all, it would be real data hidden behind a client
    // release - the same call poiLayers.ts makes for an unknown POI type.
    const paint = layer(BLAZE_LAYER_ID).paint as Record<string, unknown>

    expect(widthFor(paint['line-width'], 'some_source_added_in_2027')).toBeGreaterThan(0)
  })

  it('never lets a side trail be drawn over the AT centerline', () => {
    // The defect this exists to prevent, in the words a hiker would use: the
    // white line showing grey and blue stretches. A side trail and the
    // through-route it branches from share geometry for a stretch more often
    // than not, they are in ONE layer, and so whichever the export happened to
    // write last was the colour on screen. That reads as "the blaze changes
    // here" - a false statement, at a junction, which is the one place this
    // map cannot afford to make one.
    expect(sortKeyFor(BLAZE_LAYER_ID, CENTERLINE_SOURCE)).toBeGreaterThan(
      sortKeyFor(BLAZE_LAYER_ID, 'side_trails'),
    )
  })

  it('gives every through-route that same standing over every other source', () => {
    // Asserted over the tier rather than over the centerline alone, for the
    // same reason the width test is: a second through-route arrives by joining
    // PRIMARY_TRAIL_SOURCES, and it should inherit this rule on the way in.
    // The unknown source stands for one imported after this build - it may be
    // drawn, but not over the trail the map is about.
    const others = [
      ...Object.keys(TRAIL_LINE_WIDTHS).filter(
        (source) => !PRIMARY_TRAIL_SOURCES.includes(source),
      ),
      'some_source_added_in_2027',
    ]

    expect(PRIMARY_TRAIL_SOURCES.length).toBeGreaterThan(0)
    for (const primary of PRIMARY_TRAIL_SOURCES) {
      for (const other of others) {
        expect(sortKeyFor(BLAZE_LAYER_ID, primary)).toBeGreaterThan(
          sortKeyFor(BLAZE_LAYER_ID, other),
        )
      }
    }
  })

  it('sorts every trail layer the same way, so a casing cannot reintroduce the overlap', () => {
    // Nothing visible turns on this while every casing is one colour - but a
    // casing that ever stops being one colour would be the same bug again,
    // one layer down, and the rule belongs on the layer rather than on the
    // colour that currently makes it moot.
    const ids = trailLayerIds()

    expect(ids).toContain(TRAIL_CASING_LAYER_ID)
    for (const id of ids) {
      expect(sortKeyFor(id, CENTERLINE_SOURCE)).toBeGreaterThan(
        sortKeyFor(id, 'side_trails'),
      )
    }
  })

  it('draws a casing layer underneath the blaze layer, never over it', () => {
    const ids = style().layers.map((l) => l.id)

    expect(ids.indexOf(TRAIL_CASING_LAYER_ID)).toBeLessThan(ids.indexOf(BLAZE_LAYER_ID))
  })

  it('overhangs that casing by the same hairline under a side trail as under a through-route', () => {
    // A casing scaled proportionally instead of by a constant would be twice
    // as heavy under a through-route as under everything else, which reads as
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

  it('never lets the tiler simplify a whole trail segment away', () => {
    // geojson-vt's per-zoom tolerance does not only thin vertices - it drops
    // any whole feature shorter than the tolerance for that zoom, ~700 m at
    // z5 under the default. The centerline is ~3,000 surveyed segments
    // averaging ~1.2 km, so at corridor zooms runs of consecutive short
    // segments vanished together and the AT drew with miles-long gaps that
    // are not in the data (#160). Zero is the one tolerance under which the
    // drop rule cannot fire, whatever shape a later import arrives in.
    const source = style().sources[TRAILS_SOURCE_ID] as Record<string, unknown>

    expect(source.tolerance).toBe(0)
  })

  it('spells OpenStreetMap out in full, which is what ODbL attribution actually requires', () => {
    // WIREFRAMES.md's map-corner copy shows the "© OSM" shorthand, but its own
    // Assets section requires a visible "© OpenStreetMap" - the abbreviation
    // does not satisfy the licence. Full form wins.
    expect(OSM_CREDIT).toContain('© OpenStreetMap')
  })

  it('gives every data source an attribution, so none can ship uncredited', () => {
    const sources = style().sources as Record<string, Record<string, unknown>>

    for (const id of [TOPO_SOURCE_ID, TRAILS_SOURCE_ID, POI_SOURCE_ID]) {
      expect(sources[id].attribution).toBeTruthy()
    }
  })

  it('credits each source for the data IT is, not for the whole app', () => {
    // All three used to carry one composed "USGS US Topo · © OpenStreetMap
    // contributors", which made the corner's job impossible: three sources
    // declaring one string cannot say which of them is drawing, so the corner
    // had to guess and guessed wrong (map/credits.ts). The raster IS the USGS
    // survey; the trail lines and the pins contain none of it.
    const sources = style().sources as Record<string, Record<string, unknown>>

    expect(sources[TOPO_SOURCE_ID].attribution).toBe(USGS_TOPO_CREDIT)
    expect(sources[TRAILS_SOURCE_ID].attribution).not.toContain(USGS_TOPO_CREDIT)
    expect(sources[POI_SOURCE_ID].attribution).not.toContain(USGS_TOPO_CREDIT)
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

  it('declares the archive @2x, paired with the coverage math it changes', () => {
    // tileSize 256 over 512px tiles (#191): retina phones get the tiles'
    // full resolution, and MapLibre requests tiles one level deeper than
    // the camera. archiveCoverage.ts's floor arithmetic must carry exactly
    // that offset - this is the pairing its comment points at, asserted so
    // a change to either is a failing test rather than an invisible
    // off-by-one at the archive floor.
    const topo = style().sources[TOPO_SOURCE_ID] as { tileSize?: number }

    expect(topo.tileSize).toBe(256)
    expect(CAMERA_ZOOM_TILE_OFFSET).toBe(Math.log2(512 / 256))
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

describe('the canvas under light and dark', () => {
  // The chrome follows `data-theme` through the design tokens; the canvas
  // cannot, because it is WebGL. These are the three things that have to
  // change instead, and the one that deliberately does not.
  const styled = (
    theme: 'light' | 'dark',
    background: 'usgs_topo_offline' | 'hiking_topo_live' = 'usgs_topo_offline',
  ) => buildMapStyle({ ...STYLE_OPTIONS, background, theme })

  const layerIn = (built: ReturnType<typeof buildMapStyle>, id: string) => {
    const found = built.layers.find((l) => l.id === id)
    if (found === undefined) throw new Error(`no layer "${id}" in the style`)
    return found.paint as Record<string, unknown>
  }

  it('defaults to light, so a caller with no opinion builds what it always built', () => {
    expect(
      layerIn(buildMapStyle(STYLE_OPTIONS), BACKDROP_LAYER_ID)['background-color'],
    ).toBe(MAP_BACKGROUND_COLOR)
  })

  it('paints the backdrop in the theme, so a cold start is never a white flash', () => {
    // attachMapTheme can repaint a live map, but it necessarily runs after the
    // map exists. On a phone at night, one white frame is the thing the theme
    // was chosen to avoid.
    expect(layerIn(styled('light'), BACKDROP_LAYER_ID)['background-color']).toBe(
      MAP_BACKDROP.light,
    )
    expect(layerIn(styled('dark'), BACKDROP_LAYER_ID)['background-color']).toBe(
      MAP_BACKDROP.dark,
    )
  })

  it('keeps the light backdrop identical to the paper every other file reads', () => {
    // poiIcons.ts's halo and chrome.css's pre-WebGL fallback are both keyed to
    // this one tone. A second paper would show as a seam at the handover.
    expect(MAP_BACKDROP.light).toBe(MAP_BACKGROUND_COLOR)
  })

  it('uses opaque colours for both backdrops, not alpha black could show through', () => {
    for (const colour of Object.values(MAP_BACKDROP)) {
      expect(colour).toMatch(/^#[0-9a-f]{6}$/i)
    }
  })

  it('dims the downloaded archive rather than pretending it can go dark', () => {
    // US Topo quads are pre-rendered raster - their ink is pixels, and nothing
    // here knows which pixels are contours. So the layer is turned down.
    const dark = layerIn(styled('dark'), TOPO_LAYER_ID)

    expect(dark['raster-brightness-max']).toBe(
      ARCHIVE_RASTER_PAINT.dark['raster-brightness-max'],
    )
    expect(dark['raster-brightness-max'] as number).toBeLessThan(1)
  })

  it('leaves the archive at full strength under the light theme', () => {
    const light = layerIn(styled('light'), TOPO_LAYER_ID)

    expect(light['raster-brightness-max']).toBe(1)
    expect(light['raster-saturation']).toBe(0)
  })

  it('keeps the dim readable rather than handsome', () => {
    // The one screen a hiker uses to decide where to walk. 0.3 makes a better
    // screenshot and a sheet whose 1:24,000 contour labels cannot be read.
    expect(ARCHIVE_RASTER_PAINT.dark['raster-brightness-max']).toBeGreaterThanOrEqual(0.5)
  })

  it('names every archive property in both themes, so switching back restores it', () => {
    // These are applied to a LIVE map. A property set under one theme and
    // absent from the other would stay at the dark value forever after one
    // trip through dark mode.
    expect(Object.keys(ARCHIVE_RASTER_PAINT.dark).sort()).toEqual(
      Object.keys(ARCHIVE_RASTER_PAINT.light).sort(),
    )
  })

  it('draws the live sheet in the dark palette', () => {
    const dark = layerIn(styled('dark', 'hiking_topo_live'), LIVE_TOPO_LAYER_IDS.wood)

    expect(dark['fill-color']).toBe(TOPO_PALETTE_DARK.wood)
  })

  it('leaves the blaze colours alone, because they mean something', () => {
    // A white blaze is the AT. Re-hueing the trail lines per theme would make
    // the map lie about which trail a hiker is standing on, which is a
    // different and much worse problem than a bright map at night.
    expect(layerIn(styled('dark'), BLAZE_LAYER_ID)['line-color']).toEqual(
      layerIn(styled('light'), BLAZE_LAYER_ID)['line-color'],
    )
  })

  it('validates in both themes', () => {
    for (const theme of ['light', 'dark'] as const) {
      expect(validateStyleMin(styled(theme, 'hiking_topo_live'), latest)).toEqual([])
    }
  })
})

describe('attachMapTheme', () => {
  // Repaints a map that is already built. Not an optimisation: swapping the
  // style out drops the WebGL context, and with it the POI source pushed in
  // from IndexedDB, every archive tile in flight, and the camera. A hiker who
  // taps "Dark" while walking must not lose the map they were reading.
  it('repaints the backdrop, the archive and the sheet in place', async () => {
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const m = new MockMap({})
    m.layerIds = [BACKDROP_LAYER_ID, TOPO_LAYER_ID, LIVE_TOPO_LAYER_IDS.wood]

    attachMapTheme(m as never, 'dark')

    expect(m.paintProperties.get(`${BACKDROP_LAYER_ID}/background-color`)).toBe(
      MAP_BACKDROP.dark,
    )
    expect(m.paintProperties.get(`${TOPO_LAYER_ID}/raster-brightness-max`)).toBe(
      ARCHIVE_RASTER_PAINT.dark['raster-brightness-max'],
    )
    expect(m.paintProperties.get(`${LIVE_TOPO_LAYER_IDS.wood}/fill-color`)).toBe(
      TOPO_PALETTE_DARK.wood,
    )
  })

  it('never swaps the style out, and never tears the map down', async () => {
    // The whole point. `setStyle` would drop the WebGL context; `remove` would
    // take the GPS watcher and the camera with it.
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const m = new MockMap({})
    m.layerIds = [BACKDROP_LAYER_ID, TOPO_LAYER_ID, LIVE_TOPO_LAYER_IDS.wood]

    attachMapTheme(m as never, 'dark')

    expect(m.styles).toEqual([])
    expect(m.removed).toBe(false)
  })

  it('restores the light values on the way back', async () => {
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const m = new MockMap({})
    m.layerIds = [BACKDROP_LAYER_ID, TOPO_LAYER_ID, LIVE_TOPO_LAYER_IDS.wood]

    attachMapTheme(m as never, 'dark')()
    attachMapTheme(m as never, 'light')

    expect(m.paintProperties.get(`${BACKDROP_LAYER_ID}/background-color`)).toBe(
      MAP_BACKDROP.light,
    )
    expect(m.paintProperties.get(`${TOPO_LAYER_ID}/raster-brightness-max`)).toBe(1)
    expect(m.paintProperties.get(`${LIVE_TOPO_LAYER_IDS.wood}/fill-color`)).toBe(
      TOPO_PALETTE.wood,
    )
  })

  it('still repaints the backdrop where the live sheet is not in the style', async () => {
    // The downloaded background has none of the sheet's layers. Folding the
    // two waits into one probe would leave the backdrop waiting on a layer
    // that is never coming, and the canvas paper-white behind a dark app.
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const m = new MockMap({})
    m.layerIds = [BACKDROP_LAYER_ID, TOPO_LAYER_ID]

    attachMapTheme(m as never, 'dark')

    expect(m.paintProperties.get(`${BACKDROP_LAYER_ID}/background-color`)).toBe(
      MAP_BACKDROP.dark,
    )
  })

  it('waits for a style that has not brought its layers yet', async () => {
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const m = new MockMap({})

    attachMapTheme(m as never, 'dark')
    expect(m.paintProperties.size).toBe(0)

    m.layerIds = [BACKDROP_LAYER_ID, TOPO_LAYER_ID, LIVE_TOPO_LAYER_IDS.wood]
    m.emit('styledata')

    expect(m.paintProperties.get(`${BACKDROP_LAYER_ID}/background-color`)).toBe(
      MAP_BACKDROP.dark,
    )
    expect(m.paintProperties.get(`${LIVE_TOPO_LAYER_IDS.wood}/fill-color`)).toBe(
      TOPO_PALETTE_DARK.wood,
    )
  })

  it('detaches without writing anything', async () => {
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const m = new MockMap({})

    attachMapTheme(m as never, 'dark')()
    m.layerIds = [BACKDROP_LAYER_ID, TOPO_LAYER_ID, LIVE_TOPO_LAYER_IDS.wood]
    m.emit('styledata')

    expect(m.paintProperties.size).toBe(0)
  })
})
