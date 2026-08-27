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
  TRAIL_OVERVIEW_LAYER_ID,
  TRAIL_OVERVIEW_SOURCE_ID,
  NEARBY_TRAILS_SOURCE_ID,
  NEARBY_BLAZE_LAYER_ID,
  NEARBY_TRAIL_CASING_LAYER_ID,
  NEARBY_LONG_TERM_CLOSURE_LAYER_ID,
  NETWORK_OVERVIEW_SOURCE_ID,
  NETWORK_OVERVIEW_LAYER_ID,
  NETWORK_OVERVIEW_CLOSURE_LAYER_ID,
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
  RED_LIGHT_BLAZE_COLOR,
  archiveRasterPaint,
  attachMapAppearance,
  blazeLineColor,
  mapBackdrop,
  redLightActive,
  sheetIsDark,
  trailCasingColor,
} from './style'
import {
  BUNDLED_GLYPHS,
  LIVE_TOPO_LAYER_IDS,
  TOPO_PALETTE,
  TOPO_PALETTE_DARK,
  TOPO_PALETTE_RED,
} from './liveTopo'
import { POI_LAYER_ID, POI_SOURCE_ID, POI_PIN_MIN_ZOOM } from './poiLayers'
import { CLOSURE_SOURCE_ID } from './closureLayers'
import { WARNING_LAYER_ID, WARNING_SOURCE_ID } from './warningLayers'
import {
  CLOSURE_TAPE_IMAGE_ID,
  CLOSURE_LAYER_ID,
  LONG_TERM_CLOSED_FILTER,
  LONG_TERM_CLOSURE_LAYER_ID,
} from '../lib/closureStyle'
import { CAMERA_ZOOM_TILE_OFFSET } from '../lib/archiveCoverage'
import { NEARBY_TRAIL_LABEL_LAYER_ID, TRAIL_LABEL_LAYER_ID } from './trailLabels'

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

/**
 * The closure treatment drawn over the trails source (#783,
 * features/NEARBY_TRAILS.md §3). Bound to that source because a long-term
 * closure's geometry IS the trail line, but it is a BARRIER rather than a
 * trail line - so the two invariants below, which are about how trail lines
 * are drawn, do not reach it. Its own rules are lib/closureStyle.ts's and are
 * tested there.
 */
const CLOSURE_OVERLAY_LAYER_IDS: readonly string[] = [LONG_TERM_CLOSURE_LAYER_ID]

/** Every trail layer bound to the trail source - casing and blaze alike. */
function trailLayerIds(): string[] {
  return style()
    .layers.filter(
      (l) =>
        l.type === 'line' &&
        'source' in l &&
        l.source === TRAILS_SOURCE_ID &&
        !CLOSURE_OVERLAY_LAYER_IDS.includes(l.id),
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
    //
    // The closure overlay is excluded and is the ONE exception WIREFRAMES.md
    // §3 states: the barrier tape is the map's only permitted non-solid
    // trail-line treatment, specced in §7. It is a barrier drawn over the
    // trail, not the trail - and the test below pins it patterned, so
    // admitting the exception here cannot quietly become "closures went solid
    // too".
    for (const id of trailLayerIds()) {
      expect(
        (layer(id).paint as Record<string, unknown> | undefined)?.['line-dasharray'],
      ).toBeUndefined()
    }
  })

  it('keeps the long-term closure TAPE, which is the exception the rule above allows', () => {
    // The other half of the exception. A long-term closure that lost its
    // texture would be a wide red line over a trail - which reads as a route,
    // and is the confident false statement lib/closureStyle.ts exists to
    // prevent.
    const band = layer(LONG_TERM_CLOSURE_LAYER_ID).paint as Record<string, unknown>

    expect(band['line-pattern']).toBe(CLOSURE_TAPE_IMAGE_ID)
  })

  it('draws the long-term closure with exactly the temporary closure’s treatment', () => {
    // §3's "one vocabulary for 'do not walk this'". Asserted as byte equality
    // of the paint rather than as matching constants, so a change to either
    // feed's appearance that forgets the other fails here - the two kinds of
    // closed are told apart by the SHEET, never by the line.
    expect(layer(LONG_TERM_CLOSURE_LAYER_ID).paint).toEqual(layer(CLOSURE_LAYER_ID).paint)
  })

  it('draws the barrier only on lines their steward marks closed, and reads the status case-insensitively', () => {
    const filter = (layer(LONG_TERM_CLOSURE_LAYER_ID) as { filter?: unknown })
      .filter as unknown[]

    expect(filter).toEqual(LONG_TERM_CLOSED_FILTER)
    // `downcase` over the raw value, so a layer that starts publishing
    // `CLOSED` keeps drawing its barrier rather than silently dropping it.
    expect(JSON.stringify(filter)).toContain('downcase')
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

  it('draws the corridor-view sketch under the real trail, never over it', () => {
    // They overlap for one frame at most - the shell clears the sketch when
    // the real line lands (lib/useTrailData.ts) - and in that frame the real
    // line is what a hiker sees.
    const ids = style().layers.map((l) => l.id)

    expect(ids.indexOf(TRAIL_OVERVIEW_LAYER_ID)).toBeGreaterThan(-1)
    expect(ids.indexOf(TRAIL_OVERVIEW_LAYER_ID)).toBeLessThan(
      ids.indexOf(TRAIL_CASING_LAYER_ID),
    )
  })

  it('stops drawing that sketch at the pin seam, where 100 m starts to show', () => {
    // THE assertion in this pair (#869). No point on the overview is more
    // than 100 m from the surveyed centerline, which is 0.43 px at the seam
    // and 14 px at z14 - a trail drawn somewhere it does not go. The seam is
    // the same constant the waypoints use, because it is the same question:
    // above it the map stops being an overview and starts being something a
    // hiker reads a position off.
    expect(layer(TRAIL_OVERVIEW_LAYER_ID).maxzoom).toBe(POI_PIN_MIN_ZOOM)
  })

  it('paints the sketch with the trail expressions rather than a second set', () => {
    // The swap has to be invisible: same colour, same width, off the same two
    // published properties. Two appearances would be two things to keep in
    // step, and the drift would show as the line changing when the real one
    // arrives.
    const sketch = layer(TRAIL_OVERVIEW_LAYER_ID).paint as Record<string, unknown>
    const blaze = layer(BLAZE_LAYER_ID).paint as Record<string, unknown>

    expect(sketch['line-color']).toEqual(blaze['line-color'])
    expect(sketch['line-width']).toEqual(blaze['line-width'])
  })

  it('opens with an empty sketch, so a launch with no overview draws nothing', () => {
    const source = style().sources[TRAIL_OVERVIEW_SOURCE_ID] as {
      data: { features: unknown[] }
    }

    expect(source.data.features).toEqual([])
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

  it('never lets the tiler simplify a whole trail segment away, for pre-merge data', () => {
    // geojson-vt's per-zoom tolerance does not only thin vertices - it drops
    // any whole feature shorter than the tolerance for that zoom, ~700 m at
    // z5 under the default. The pre-merge centerline was ~3,000 surveyed
    // segments averaging ~1.2 km, so at corridor zooms runs of consecutive
    // short segments vanished together and the AT drew with miles-long gaps
    // that are not in the data (#160). Zero is the one tolerance under which
    // the drop rule cannot fire, and it stays the answer for every copy of
    // the data that predates the chain merge - including when the caller
    // says nothing, because "cannot tell" must round toward the missing
    // performance, never toward a missing trail.
    const source = style().sources[TRAILS_SOURCE_ID] as Record<string, unknown>

    expect(source.tolerance).toBe(0)
  })

  it('returns to per-zoom simplification once the stored trails are merged chains', () => {
    // #161: the export merges the centerline into maximal chains far above
    // the drop bar at any zoom, so for that shape the default tolerance is
    // safe - and buys back the vertex thinning `tolerance: 0` disables.
    // Omitting the property (rather than writing the default's number) is
    // deliberate: the default lives in geojson-vt, and restating it here
    // would pin a value this file has no say over.
    const source = buildMapStyle({ ...STYLE_OPTIONS, trailsMerged: true }).sources[
      TRAILS_SOURCE_ID
    ] as Record<string, unknown>

    expect(source).not.toHaveProperty('tolerance')
  })

  it('spells OpenStreetMap out in full, which is what ODbL attribution actually requires', () => {
    // WIREFRAMES.md's map-corner copy shows the "© OSM" shorthand, but its own
    // Assets section requires a visible "© OpenStreetMap" - the abbreviation
    // does not satisfy the licence. Full form wins.
    expect(OSM_CREDIT).toContain('© OpenStreetMap')
  })

  it('gives every third-party data source an attribution, so none ships uncredited', () => {
    const sources = style().sources as Record<string, Record<string, unknown>>

    for (const id of [TOPO_SOURCE_ID, TRAILS_SOURCE_ID, POI_SOURCE_ID]) {
      expect(sources[id].attribution).toBeTruthy()
    }
  })

  it('credits nobody for the reports, because there is nobody to credit', () => {
    // The closures and the serious warnings are hikers' own observations,
    // moderated by the clubs that maintain the trail. They contain no
    // third-party data at all, so an attribution here would not be a
    // formality - map/credits.ts assembles the corner out of whichever
    // sources are actually on screen, and a "© OpenStreetMap" over a closure
    // somebody walked up to and photographed is a false statement about where
    // it came from.
    //
    // Enumerated rather than skipped so the absence is a decision on the
    // record, and so the test above cannot be read as covering these too.
    const sources = style().sources as Record<string, Record<string, unknown>>

    for (const id of [CLOSURE_SOURCE_ID, WARNING_SOURCE_ID]) {
      expect(sources[id].attribution).toBeUndefined()
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

  it('asks for text only from the bundled glyph endpoint, never from a network host', () => {
    // THIS USED TO ASSERT THE OPPOSITE, and the change is deliberate (#930).
    //
    // It read "declares no glyphs URL, and so must never ask for text",
    // reasoning that "fonts are fetched, there is no network on a mountain".
    // The rule that protects is right and still holds; the proxy it used to
    // enforce it - no text anywhere on the offline sheet - stopped being the
    // only way to get there, and #930's trail-name labels need text on both
    // sheets.
    //
    // What actually makes text safe here is that the endpoint is the app's own
    // origin and its 256 ranges are PRECACHED: vite.config.ts puts
    // `glyphs/**/*.pbf` in globPatterns for exactly this failure ("labels
    // render in town and vanish in airplane mode"), and
    // scripts/check-build-output.mjs fails the build if a range is missing
    // from the generated manifest. So the assertion is now the real invariant
    // rather than its proxy: text may exist, and every glyph it needs must
    // come from somewhere a service worker can hold.
    expect(style().glyphs).toBe(BUNDLED_GLYPHS)
    expect(BUNDLED_GLYPHS).not.toMatch(/^[a-z]+:\/\//i)
  })

  it('never leaves a text-field in a style with no glyph endpoint to render it', () => {
    // The other half, and the one that survives unchanged in spirit: a
    // `text-field` in a style with no `glyphs` is a per-glyph load failure in
    // the field and nowhere else. Written as an implication rather than a
    // prohibition so it keeps biting if the endpoint is ever made conditional
    // again.
    const drawn = style()
    const usesText = drawn.layers.some(
      (l) =>
        (l.layout as Record<string, unknown> | undefined)?.['text-field'] !== undefined,
    )

    if (usesText) expect(drawn.glyphs).toBeDefined()
  })
})

describe('the safety overlays', () => {
  it('draws the closure band over the blaze, not under it', () => {
    // The entire job of the band. Under the trail line it would be a closure
    // the trail is drawn straight through, which is a picture of an open
    // trail - and lib/closureStyle.ts's careful width and texture differences
    // would all be spent on something nobody can see.
    //
    // Drawn OVER is not the same as hiding, and that is the tape's whole
    // point: its gaps are transparent, so the blaze underneath still shows
    // between the stripes and a hiker can read WHICH trail is shut.
    const ids = style().layers.map((l) => l.id)

    expect(ids.indexOf(BLAZE_LAYER_ID)).toBeLessThan(ids.indexOf(CLOSURE_LAYER_ID))
  })

  it('draws a serious warning over every waypoint pin', () => {
    // Belt and braces with warningLayers.ts's `icon-allow-overlap`: that keeps
    // the pin from being dropped, this keeps it from being covered. A warning
    // underneath a shelter pin is as unread as one that was decluttered away.
    const ids = style().layers.map((l) => l.id)

    expect(ids.indexOf(POI_LAYER_ID)).toBeLessThan(ids.indexOf(WARNING_LAYER_ID))
  })

  it('binds each overlay to its own source, never to the trail source', () => {
    // A closure drawn from TRAILS_SOURCE_ID would need a filter to pick out
    // the closed features, and there are none in that file - the geometry is
    // sliced client-side from mile markers (map/closureLayers.ts).
    const bySource = Object.fromEntries(
      style()
        .layers.filter((l) => 'source' in l)
        .map((l) => [l.id, (l as { source: string }).source]),
    )

    expect(bySource[CLOSURE_LAYER_ID]).toBe(CLOSURE_SOURCE_ID)
    expect(bySource[WARNING_LAYER_ID]).toBe(WARNING_SOURCE_ID)
  })

  it('starts both sources empty, because both arrive over the network', () => {
    // And very often never arrive at all - this is an offline-first app whose
    // backend is reachable only with signal. Empty is the honest opening
    // state, and App.tsx keeps "empty" and "could not ask" apart above it.
    for (const id of [CLOSURE_SOURCE_ID, WARNING_SOURCE_ID]) {
      const source = style().sources[id] as Record<string, unknown>

      expect(source.type).toBe('geojson')
      expect(source.data).toEqual({ type: 'FeatureCollection', features: [] })
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
    // attachMapAppearance can repaint a live map, but it necessarily runs
    // after the map exists. On a phone at night, one white frame is the thing
    // the theme was chosen to avoid.
    expect(layerIn(styled('light'), BACKDROP_LAYER_ID)['background-color']).toBe(
      MAP_BACKDROP.light,
    )
    expect(layerIn(styled('dark'), BACKDROP_LAYER_ID)['background-color']).toBe(
      MAP_BACKDROP.dark,
    )
  })

  it('keeps the light backdrop identical to the paper every other file reads', () => {
    // chrome.css's pre-WebGL fallback is keyed to this one tone. A second
    // paper would show as a seam at the handover.
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

describe('attachMapAppearance', () => {
  // Repaints a map that is already built. Not an optimisation: swapping the
  // style out drops the WebGL context, and with it the POI source pushed in
  // from IndexedDB, every archive tile in flight, and the camera. A hiker who
  // taps "Dark" while walking must not lose the map they were reading.
  it('repaints the backdrop, the archive and the sheet in place', async () => {
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const m = new MockMap({})
    m.layerIds = [BACKDROP_LAYER_ID, TOPO_LAYER_ID, LIVE_TOPO_LAYER_IDS.wood]

    attachMapAppearance(m as never, { theme: 'dark' })

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

    attachMapAppearance(m as never, { theme: 'dark' })

    expect(m.styles).toEqual([])
    expect(m.removed).toBe(false)
  })

  it('restores the light values on the way back', async () => {
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const m = new MockMap({})
    m.layerIds = [BACKDROP_LAYER_ID, TOPO_LAYER_ID, LIVE_TOPO_LAYER_IDS.wood]

    attachMapAppearance(m as never, { theme: 'dark' })()
    attachMapAppearance(m as never, { theme: 'light' })

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

    attachMapAppearance(m as never, { theme: 'dark' })

    expect(m.paintProperties.get(`${BACKDROP_LAYER_ID}/background-color`)).toBe(
      MAP_BACKDROP.dark,
    )
  })

  it('waits for a style that has not brought its layers yet', async () => {
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const m = new MockMap({})

    attachMapAppearance(m as never, { theme: 'dark' })
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

    attachMapAppearance(m as never, { theme: 'dark' })()
    m.layerIds = [BACKDROP_LAYER_ID, TOPO_LAYER_ID, LIVE_TOPO_LAYER_IDS.wood]
    m.emit('styledata')

    expect(m.paintProperties.size).toBe(0)
  })
})

describe('the map style and red light (MAP_STYLE_SPEC.md)', () => {
  const TRAIL_LAYER_IDS = [
    BACKDROP_LAYER_ID,
    TOPO_LAYER_ID,
    TRAIL_CASING_LAYER_ID,
    BLAZE_LAYER_ID,
    LIVE_TOPO_LAYER_IDS.wood,
  ]

  it('treats night_hike as a dark sheet even under the light theme', () => {
    // A hiker readying night vision before dusk picks the style, not the
    // whole app's theme - and everything keyed to "dark sheet" has to agree:
    // the backdrop, the archive's dimming, and the palette itself.
    const appearance = { theme: 'light', mapStyle: 'night_hike' } as const

    expect(sheetIsDark(appearance)).toBe(true)
    expect(mapBackdrop(appearance)).toBe(MAP_BACKDROP.dark)
    expect(archiveRasterPaint(appearance)).toBe(ARCHIVE_RASTER_PAINT.dark)
  })

  it('keeps field by day a day sheet, red-light toggle armed or not', () => {
    expect(sheetIsDark({ theme: 'light', mapStyle: 'field' })).toBe(false)
    // The toggle refines night_hike only; armed under field it changes nothing.
    expect(sheetIsDark({ theme: 'light', mapStyle: 'field', redLight: true })).toBe(false)
    expect(redLightActive({ theme: 'light', mapStyle: 'field', redLight: true })).toBe(
      false,
    )
  })

  it('gives red light its own ink, the red palette halo, so halos dissolve into ground', () => {
    const appearance = { mapStyle: 'night_hike', redLight: true } as const

    expect(redLightActive(appearance)).toBe(true)
    expect(mapBackdrop(appearance)).toBe(TOPO_PALETTE_RED.labelHalo)
  })

  it('inks each sheet its own casing - field at label black, dark sheets near-black', () => {
    expect(trailCasingColor({ theme: 'light' })).toBe(TOPO_PALETTE.label)
    // Dark sheets drop the casing into ground rather than keeping a warm
    // hairline: on ink the blaze itself is the edge.
    expect(trailCasingColor({ theme: 'dark' })).toBe('#060907')
    expect(trailCasingColor({ mapStyle: 'night_hike' })).toBe('#060907')
    expect(trailCasingColor({ mapStyle: 'parchment' })).toBe('#241d12')
  })

  it('overrides the blazes to one red under red light, and only there', () => {
    // A blaze colour is a fact about the ground. The override is the honest
    // form of a loss that red light imposes anyway - every hue would render
    // as murky dark red - so it applies exactly when the red palette does.
    expect(blazeLineColor({ mapStyle: 'night_hike', redLight: true })).toBe(
      RED_LIGHT_BLAZE_COLOR,
    )
    expect(blazeLineColor({ mapStyle: 'night_hike' })).toBe(BLAZE_MATCH_EXPRESSION)
    expect(blazeLineColor({ theme: 'dark' })).toBe(BLAZE_MATCH_EXPRESSION)
  })

  it('seeds a red-light cold start red in its first frame', () => {
    const built = buildMapStyle({
      ...STYLE_OPTIONS,
      background: 'hiking_topo_live',
      mapStyle: 'night_hike',
      redLight: true,
    })
    const paintOf = (id: string) =>
      (built.layers.find((l) => l.id === id)?.paint ?? {}) as Record<string, unknown>

    expect(paintOf(BLAZE_LAYER_ID)['line-color']).toBe(RED_LIGHT_BLAZE_COLOR)
    expect(paintOf(BACKDROP_LAYER_ID)['background-color']).toBe(
      TOPO_PALETTE_RED.labelHalo,
    )
    expect(paintOf(LIVE_TOPO_LAYER_IDS.wood)['fill-color']).toBe(TOPO_PALETTE_RED.wood)
  })

  it('still validates as a MapLibre style under night_hike and red light', () => {
    for (const redLight of [false, true]) {
      const built = buildMapStyle({
        ...STYLE_OPTIONS,
        background: 'hiking_topo_live',
        mapStyle: 'night_hike',
        redLight,
      })
      expect(validateStyleMin(built, latest)).toEqual([])
    }
  })

  it('repaints casing and blaze in place on an appearance change, and restores', async () => {
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const m = new MockMap({})
    m.layerIds = [...TRAIL_LAYER_IDS]

    attachMapAppearance(m as never, { mapStyle: 'night_hike', redLight: true })()
    attachMapAppearance(m as never, { theme: 'light' })

    // Leaving red light is a true restore: the shared match expression goes
    // back exactly as buildMapStyle spelled it, and the casing returns to the
    // field ink.
    expect(m.paintProperties.get(`${BLAZE_LAYER_ID}/line-color`)).toBe(
      BLAZE_MATCH_EXPRESSION,
    )
    expect(m.paintProperties.get(`${TRAIL_CASING_LAYER_ID}/line-color`)).toBe(
      TOPO_PALETTE.label,
    )
    expect(m.paintProperties.get(`${BACKDROP_LAYER_ID}/background-color`)).toBe(
      MAP_BACKDROP.light,
    )
    expect(m.styles).toEqual([])
  })
})

/**
 * A blaze colour is a fact about the ground, and zoom is not a hiker's choice.
 *
 * The corridor view (#598) draws the trail differently BELOW the seam: the
 * 38.5 miles ATC's centerline names no maintaining club for render in the
 * neutral grey, dashed. That is a deliberate relaxation of WIREFRAMES.md §3's
 * no-dash rule, scoped by the maintainer on 2026-08-19 to
 * z <= POI_PIN_MIN_ZOOM, on the grounds that down there the line is
 * representational - 2.5 px standing for 2,197 miles, with no contours behind
 * it and nobody following it.
 *
 * This file asserts the OTHER half of that decision, which is the half a
 * later change can break without anybody noticing: ABOVE the seam a blaze
 * renders in its real colour, at every zoom. style.ts already says why, in
 * RED_LIGHT_BLAZE_COLOR's own docstring - "a blaze colour is a fact about the
 * ground, and recolouring facts is exactly what this map exists not to do".
 *
 * Red light is the one sanctioned exception and the distinction is the whole
 * point: it is an APPEARANCE, armed deliberately by a hiker who has accepted
 * the loss and can disarm it. A zoom-varying colour is neither chosen nor
 * reversible by anyone reading the map, which is why the corridor view's
 * treatments have to live in their own layer capped at the seam rather than
 * in this one's paint.
 *
 * The blazes are spelled out rather than imported from blaze.ts's private
 * table on purpose: this is the list a reviewer should have to read.
 */
describe('a blaze never changes colour where a hiker is navigating by it (#598)', () => {
  const BLAZES = [
    'White',
    'Blue',
    'Yellow',
    'Orange',
    'Red',
    'Green',
    'Purple',
    'None',
    'Other',
    'Unknown',
  ]

  /** The seam itself, and a spread of the zooms a hiker actually navigates at. */
  const NAVIGATIONAL_ZOOMS = [POI_PIN_MIN_ZOOM, 10, 11, 12, 13, 14, 16, 18, 22]

  const APPEARANCES: {
    name: string
    options: Partial<typeof STYLE_OPTIONS> & Record<string, unknown>
  }[] = [
    { name: 'field by day', options: { theme: 'light', mapStyle: 'field' } },
    { name: 'the dark sheet', options: { theme: 'dark', mapStyle: 'field' } },
    { name: 'night hike', options: { theme: 'dark', mapStyle: 'night_hike' } },
    {
      name: 'night hike under red light',
      options: { theme: 'dark', mapStyle: 'night_hike', redLight: true },
    },
  ]

  /** The blaze layer's `line-color`, evaluated by MapLibre's own engine. */
  function blazeColorAt(
    options: Record<string, unknown>,
    blazeColor: string,
    zoom: number,
  ): string {
    const built = buildMapStyle({ ...STYLE_OPTIONS, ...options })
    const found = built.layers.find((l) => l.id === BLAZE_LAYER_ID)
    if (found === undefined) throw new Error('no blaze layer in the style')
    const compiled = createExpression(
      (found.paint as Record<string, unknown>)['line-color'] as never,
      latest.paint_line['line-color'] as never,
    )
    if (compiled.result === 'error') {
      throw new Error('the blaze layer’s line-color is not a valid expression')
    }
    return JSON.stringify(
      compiled.value.evaluate({ zoom }, {
        properties: { blaze_color: blazeColor },
      } as never),
    )
  }

  /** Whether an expression reads the zoom at all, at any depth. */
  function readsZoom(expression: unknown): boolean {
    if (!Array.isArray(expression)) return false
    if (expression[0] === 'zoom') return true
    return expression.some(readsZoom)
  }

  it.each(APPEARANCES)(
    'paints every blaze the same colour at every navigational zoom — $name',
    ({ options }) => {
      for (const blaze of BLAZES) {
        const atTheSeam = blazeColorAt(options, blaze, POI_PIN_MIN_ZOOM)
        for (const zoom of NAVIGATIONAL_ZOOMS) {
          // Not `toEqual(atTheSeam)` on a collected array: naming the zoom in
          // the assertion is what makes a failure say WHERE the blaze moved.
          expect({ blaze, zoom, color: blazeColorAt(options, blaze, zoom) }).toEqual({
            blaze,
            zoom,
            color: atTheSeam,
          })
        }
      }
    },
  )

  it.each(APPEARANCES)(
    'never lets zoom into the blaze paint at all — $name',
    ({ options }) => {
      // The stronger statement, and the one that survives a future expression
      // this test did not think to evaluate: if the paint cannot read the zoom,
      // it cannot vary with it - above the seam or below.
      const built = buildMapStyle({ ...STYLE_OPTIONS, ...options })
      const found = built.layers.find((l) => l.id === BLAZE_LAYER_ID)
      if (found === undefined) throw new Error('no blaze layer in the style')
      expect(readsZoom((found.paint as Record<string, unknown>)['line-color'])).toBe(
        false,
      )
    },
  )

  it('keeps the blazes distinct from one another, so the rule has something to protect', () => {
    // Without this, collapsing every blaze to one hue would pass every
    // assertion above - it is perfectly zoom-invariant.
    const day = { theme: 'light', mapStyle: 'field' } as const
    const painted = new Set(BLAZES.map((blaze) => blazeColorAt(day, blaze, 14)))
    // Seven real hues; None, Other and Unknown share the neutral grey by
    // contract (blaze.ts), so ten blazes make eight colours.
    expect(painted.size).toBe(8)
  })

  it('takes red light as the one recolouring, and takes it honestly', () => {
    // MAP_STYLE_SPEC.md's decision: under red light every hue would render as
    // a barely-distinguishable dark red anyway, so the loss is taken openly -
    // one colour, every trail, and blaze identity moves to the tap sheet.
    const redLight = { theme: 'dark', mapStyle: 'night_hike', redLight: true } as const
    const painted = new Set(BLAZES.map((blaze) => blazeColorAt(redLight, blaze, 14)))
    expect(painted.size).toBe(1)
    // And it is still a choice rather than a zoom - covered by the cases
    // above, which run this appearance through both.
    expect(redLightActive(redLight)).toBe(true)
  })
})

describe('the trails other organizations maintain (#950)', () => {
  const ids = () => style().layers.map((l) => l.id)

  it('declares its own source, because the two artifacts are separately licensed', () => {
    // One MapLibre GeoJSON source takes one `data`. These lines ship as their
    // own artifact because publish.py holds them back while NYS OPRHP's and
    // NYNJTC's reuse terms are unstated, so two artifacts is two sources -
    // see NEARBY_TRAILS_SOURCE_ID for the whole argument.
    expect(style().sources[NEARBY_TRAILS_SOURCE_ID]).toBeDefined()
  })

  it('opens empty, so a bucket with no network is one shape of style', () => {
    // The ordinary state today. An absent source would mean the style
    // depended on what the bucket happened to hold.
    expect(style().sources[NEARBY_TRAILS_SOURCE_ID]).toMatchObject({
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })
  })

  it('draws the network under the chosen trail, both lines and casings', () => {
    // Opacity says which SYSTEM a line belongs to; ORDER is what keeps the
    // chosen trail's pixels. Half the A.T.'s length in Harriman runs within
    // 150 m of another marked trail (#771), so where the two are coincident
    // the last-drawn line wins whatever its opacity - and it must not be the
    // nearby one.
    const order = ids()
    expect(order.indexOf(NEARBY_BLAZE_LAYER_ID)).toBeLessThan(
      order.indexOf(TRAIL_CASING_LAYER_ID),
    )
    expect(order.indexOf(NEARBY_TRAIL_CASING_LAYER_ID)).toBeLessThan(
      order.indexOf(NEARBY_BLAZE_LAYER_ID),
    )
  })

  it('paints a nearby trail with the same expressions the chosen trail is painted with', () => {
    // THE TEST THE SECOND SOURCE EXISTS TO NEED. Two instances of one
    // treatment, not two treatments that currently agree: a channel added to
    // one and not the other is a nearby trail that stops looking like a
    // trail, and nothing else in the build would catch it.
    //
    // `minzoom` is the ONE permitted difference and is asserted on its own
    // below, so that admitting it here cannot quietly admit a second.
    expect(layer(NEARBY_BLAZE_LAYER_ID)).toEqual({
      ...layer(BLAZE_LAYER_ID),
      id: NEARBY_BLAZE_LAYER_ID,
      source: NEARBY_TRAILS_SOURCE_ID,
      minzoom: POI_PIN_MIN_ZOOM,
    })
    expect(layer(NEARBY_TRAIL_CASING_LAYER_ID)).toEqual({
      ...layer(TRAIL_CASING_LAYER_ID),
      id: NEARBY_TRAIL_CASING_LAYER_ID,
      source: NEARBY_TRAILS_SOURCE_ID,
      minzoom: POI_PIN_MIN_ZOOM,
    })
  })

  it('draws the network only above the seam, so the corridor view keeps its subject', () => {
    // features/NEARBY_TRAILS.md §8: "Forty short trails are not a below-seam
    // subject - at z7 Harriman is one green shape." 3,663 lines drawn across
    // the corridor view would be a smear over the thirty club sections that
    // view exists to show.
    //
    // The chosen trail carries no minzoom and must not gain one from this:
    // the A.T. IS the corridor view's line.
    expect(layer(NEARBY_BLAZE_LAYER_ID).minzoom).toBe(POI_PIN_MIN_ZOOM)
    expect(layer(NEARBY_TRAIL_CASING_LAYER_ID).minzoom).toBe(POI_PIN_MIN_ZOOM)
    expect(layer(BLAZE_LAYER_ID).minzoom).toBeUndefined()
    expect(layer(TRAIL_CASING_LAYER_ID).minzoom).toBeUndefined()
  })

  it('gives a long-term closed nearby trail the same barrier tape', () => {
    // features/NEARBY_TRAILS.md §3: one mark for "do not walk this",
    // whoever's trail it is. OPRHP publishes the status
    // (export_nearby_trails.py's `trail_status`) and lib/closureStyle.ts's
    // filter is what reads it.
    expect(layer(NEARBY_LONG_TERM_CLOSURE_LAYER_ID)).toEqual({
      ...layer(LONG_TERM_CLOSURE_LAYER_ID),
      id: NEARBY_LONG_TERM_CLOSURE_LAYER_ID,
      source: NEARBY_TRAILS_SOURCE_ID,
    })
  })

  it('labels the network, and lets the chosen trail win a contested name', () => {
    // Placement runs top-down, so the LATER symbol layer has priority
    // (liveTopo.test.ts's finding). Where both names cannot be placed, the
    // one the map is about survives.
    const order = ids()
    expect(order.indexOf(NEARBY_TRAIL_LABEL_LAYER_ID)).toBeGreaterThan(-1)
    expect(order.indexOf(NEARBY_TRAIL_LABEL_LAYER_ID)).toBeLessThan(
      order.indexOf(TRAIL_LABEL_LAYER_ID),
    )
  })

  it('dims a nearby label with its own line, by the shared opacity rule', () => {
    // features/NEARBY_TRAILS.md §1: "labels dim with their lines". Not a copy
    // of the rule - the same expression object.
    expect(layer(NEARBY_TRAIL_LABEL_LAYER_ID).paint).toEqual(
      layer(TRAIL_LABEL_LAYER_ID).paint,
    )
  })
})

describe('the network overview sketch (#1135)', () => {
  it('draws below the seam, exactly where the full network does not', () => {
    // The two representations partition the zoom range rather than overlap:
    // the sketch's maxzoom is the full network layers' minzoom, so every
    // camera draws exactly one of them. The tape cap rides along, or closed
    // ground would be taped twice - from 100 m geometry - above the seam.
    expect(layer(NETWORK_OVERVIEW_LAYER_ID).maxzoom).toBe(POI_PIN_MIN_ZOOM)
    expect(layer(NETWORK_OVERVIEW_CLOSURE_LAYER_ID).maxzoom).toBe(POI_PIN_MIN_ZOOM)
    expect(layer(NEARBY_BLAZE_LAYER_ID).minzoom).toBe(POI_PIN_MIN_ZOOM)
  })

  it('sits under everything the A.T. draws, its own sketch included', () => {
    // The full network's ordering argument, one zoom band earlier: a nearby
    // trail must never cover the trail the map is about, and below the seam
    // "the trail the map is about" is drawn by the A.T. sketch too.
    const ids = style().layers.map((l) => l.id)

    expect(ids.indexOf(NETWORK_OVERVIEW_LAYER_ID)).toBeGreaterThan(-1)
    expect(ids.indexOf(NETWORK_OVERVIEW_LAYER_ID)).toBeLessThan(
      ids.indexOf(NETWORK_OVERVIEW_CLOSURE_LAYER_ID),
    )
    expect(ids.indexOf(NETWORK_OVERVIEW_CLOSURE_LAYER_ID)).toBeLessThan(
      ids.indexOf(TRAIL_OVERVIEW_LAYER_ID),
    )
    expect(ids.indexOf(TRAIL_OVERVIEW_LAYER_ID)).toBeLessThan(
      ids.indexOf(TRAIL_CASING_LAYER_ID),
    )
  })

  it('paints with the shared colour and ghost, and a width that lands on the seam', () => {
    // Colour and opacity are the A.T. sketch's own expressions - one
    // appearance, and the ghost is the whole reason these lines read as
    // context rather than as a second chosen trail. Width is the ONE
    // deliberate deviation (#1135): at the side-trail width the opening
    // camera's dense park clusters render as a cloud of coloured dots, so it
    // tapers - and what this pins is the handoff: the taper's seam-end stop
    // is the exact width the full network's layers draw these sources at, so
    // crossing z9 cannot restyle a line.
    const network = layer(NETWORK_OVERVIEW_LAYER_ID).paint as Record<string, unknown>
    const sketch = layer(TRAIL_OVERVIEW_LAYER_ID).paint as Record<string, unknown>

    expect(network['line-color']).toEqual(sketch['line-color'])
    expect(network['line-opacity']).toEqual(sketch['line-opacity'])

    const taper = network['line-width'] as unknown[]
    const fullLines = layer(NEARBY_BLAZE_LAYER_ID).paint as Record<string, unknown>
    expect(taper[taper.length - 2]).toBe(POI_PIN_MIN_ZOOM)
    expect(taper[taper.length - 1]).toBe(DEFAULT_TRAIL_LINE_WIDTH)
    expect(widthFor(fullLines['line-width'], 'oprhp_trails')).toBe(
      DEFAULT_TRAIL_LINE_WIDTH,
    )
  })

  it('carries its stewards own attribution, because the credit follows the lines', () => {
    // OPRHP's terms require credit whenever their lines are drawn, and below
    // the seam this source is the only drawing of them - an overview credited
    // like the A.T. would lapse the condition at exactly the camera every
    // launch opens on.
    const sources = style().sources as Record<string, { attribution?: string }>

    expect(sources[NETWORK_OVERVIEW_SOURCE_ID].attribution).toEqual(
      sources[NEARBY_TRAILS_SOURCE_ID].attribution,
    )
  })

  it('opens empty, so a launch with no artifact draws the A.T.-only map', () => {
    const source = style().sources[NETWORK_OVERVIEW_SOURCE_ID] as {
      data: { features: unknown[] }
    }

    expect(source.data.features).toEqual([])
  })
})
