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
  BLAZE_DOTTED_LAYER_ID,
  BLAZE_LINE_LAYER_IDS,
  TRAIL_CASING_LAYER_ID,
  TRAIL_CASING_DOTTED_LAYER_ID,
  TRAIL_CASING_LAYER_IDS,
  NEARBY_BLAZE_DOTTED_LAYER_ID,
  NEARBY_TRAIL_CASING_DOTTED_LAYER_ID,
  NETWORK_OVERVIEW_DOTTED_LAYER_ID,
  NEARBY_TRAIL_CASING_DASHARRAY,
  NEAR_WHITE_BLAZES,
  SIDE_TRAIL_WIDTH,
  inksNearWhiteAsCasing,
  trailCasingWidthExpression,
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
  CHOSEN_TRAIL_SPLIT_LAYERS,
  NETWORK_OVERVIEW_FAR_WIDTH,
  NETWORK_OVERVIEW_WIDTH_EXPRESSION,
  TRAIL_WIDTH_EXPRESSION,
  sketchWidthExpression,
  dottedTrailWidthExpression,
  dottedTrailCasingWidthExpression,
  OVERVIEW_FAR_ZOOM,
  TRAIL_CASING_WIDTH_EXPRESSION,
  solidTrailWidthExpression,
  DARK_INKED_BLAZE_LAYER_IDS,
  DOTTED_TRAIL_CASING_LAYER_IDS,
  solidTrailCasingWidthExpression,
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
import {
  NEARBY_TRAIL_LABEL_LAYER_ID,
  TRAIL_LABEL_LAYER_ID,
  TRAIL_LABEL_MIN_ZOOM,
} from './trailLabels'
import {
  NEARBY_TRAIL_DASHARRAY,
  chosenSystemFilter,
  nearbyTrailFilter,
  nearbyTrailOpacityExpression,
  CHOSEN_TRAIL_OPACITY,
} from './nearbyTrails'
import {
  TRAIL_BADGE_ANCHORS,
  TRAIL_BADGE_LAYER_ID,
  TRAIL_BADGE_PLATE_DAY,
  TRAIL_BADGE_PLATE_NIGHT,
  TRAIL_BADGE_RADIAL_OFFSET,
  TRAIL_BADGE_SOURCE_ID,
  badgePlateImageId,
  badgeTextColor,
} from './trailBadges'
import { LABEL_TIER } from './labelLadder'
import { NETWORK_TILES_LAYER, NETWORK_TILES_URL } from './networkTiles'
import { NEARBY_TRAILS_TILES_MAX_ZOOM, NEARBY_TRAILS_TILES_MIN_ZOOM } from '../lib/config'

// See WIREFRAMES.md "Trail line rendering — blazes". Three rules there are
// load-bearing rather than decorative:
//   1. ONE `match` expression drives line-color for every trail source - no
//      per-layer hardcoded hexes, so a new imported source inherits the rule.
//   2. The CHOSEN system's lines are SOLID, and WIDTH is the second,
//      hue-independent channel: the AT centerline is the widest line on the
//      map, so the through-line survives greyscale and glare (WIREFRAMES.md
//      `9d`) with colour removed entirely. Dash rhythm used to carry that
//      channel, and the gaps it left were what made the near-white centerline
//      unreadable - what a hiker saw was a dotted grey-and-white thread, not
//      a trail. Since #1283 every OTHER line is a dot rhythm, on a layer of
//      its own under the solid one, and the tests below hold the three things
//      that keep that from being the old defect: the chosen trail is never
//      dotted, a dotted casing keeps the blaze's pitch, and a near-white line
//      on paper is inked dark with no casing to show through.
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
/**
 * The tier a trail line lands on at the seam.
 *
 * Since #1306 every trail-line width is a taper - `interpolate(zoom, 4,
 * <scaled tier>, POI_PIN_MIN_ZOOM, <tier>)` - because a line drawn at its
 * tier below the seam is a rope at the corridor camera. The cases below are
 * about the TIER, so they unwrap the taper rather than restating it; the
 * taper itself is pinned in its own cases further down.
 */
const seamTier = (width: unknown): unknown =>
  Array.isArray(width) && width[0] === 'interpolate' ? width[width.length - 1] : width

function widthFor(expression: unknown, source: string): number {
  const [, , ...rest] = expression as unknown[]
  for (let i = 0; i + 1 < rest.length; i += 2) {
    if (rest[i] === source) return rest[i + 1] as number
  }
  return rest[rest.length - 1] as number
}

/** A paint property of one layer, evaluated by MapLibre's own engine for
 *  one feature - the way the renderer will, rather than by reading the
 *  array back. `spec` is the property's entry in the style spec. */
function paintFor(
  built: ReturnType<typeof buildMapStyle>,
  layerId: string,
  property: string,
  spec: unknown,
  properties: Record<string, unknown>,
): unknown {
  const found = built.layers.find((l) => l.id === layerId)
  if (found === undefined) throw new Error(`no layer "${layerId}" in the style`)
  const compiled = createExpression(
    (found.paint as Record<string, unknown>)[property] as never,
    spec as never,
  )
  if (compiled.result === 'error') {
    throw new Error(`${property} on "${layerId}" is not a valid expression`)
  }
  const value = compiled.value.evaluate({ zoom: 12 }, { properties } as never)
  return typeof value === 'object' && value !== null && 'toString' in value
    ? String(value)
    : value
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
    // On a day sheet the expression is the shared match with near-white
    // swapped for the casing ink (NEAR_WHITE_BLAZES) - still ONE expression,
    // and the match is its fallback rather than a copy. On a dark sheet it
    // IS the match. Every blaze-coloured layer, so a fifth cannot drift.
    for (const id of BLAZE_LINE_LAYER_IDS) {
      const day = layer(id).paint as Record<string, unknown>
      if (DARK_INKED_BLAZE_LAYER_IDS.includes(id)) {
        // The dotted halves and both sketches: the match with near-white
        // swapped for the casing ink, the match still its fallback (#1306).
        expect((day['line-color'] as unknown[])[0], id).toBe('case')
        expect((day['line-color'] as unknown[])[3], id).toBe(BLAZE_MATCH_EXPRESSION)
      } else {
        // A solid line keeps its white blaze and its casing (#1306).
        expect(day['line-color'], id).toBe(BLAZE_MATCH_EXPRESSION)
      }

      const night = buildMapStyle({ ...STYLE_OPTIONS, theme: 'dark' }).layers.find(
        (l) => l.id === id,
      )
      if (night === undefined) throw new Error(`no layer "${id}" in the dark style`)
      expect((night.paint as Record<string, unknown>)['line-color']).toBe(
        BLAZE_MATCH_EXPRESSION,
      )
    }
  })

  it('draws the chosen system solid, so the taken trail never alternates with its casing', () => {
    // The regression a whole block of dash-rhythm assertions used to guard
    // against, narrowed to the lines it was ever about: a dashed blaze over a
    // dark casing is a line alternating between its blaze colour and the
    // casing showing through, and for the centerline, whose blaze is
    // near-white, the casing was the part that read. The chosen system's
    // pair stays solid, casing and blaze alike.
    //
    // The closure overlay is excluded and is the exception WIREFRAMES.md §3
    // states: the barrier tape is a barrier drawn over the trail, not the
    // trail - and the test below pins it patterned.
    for (const id of [TRAIL_CASING_LAYER_ID, BLAZE_LAYER_ID]) {
      expect(
        (layer(id).paint as Record<string, unknown>)['line-dasharray'],
      ).toBeUndefined()
      expect((layer(id) as { filter?: unknown }).filter).toEqual(chosenSystemFilter())
    }
  })

  it('draws every other line as a dot rhythm, on its own layer under the solid one (#1283)', () => {
    // The fourth channel: with a country's worth of trails on the opening
    // camera, opacity alone could not say which line the map was about.
    for (const id of [TRAIL_CASING_DOTTED_LAYER_ID, BLAZE_DOTTED_LAYER_ID]) {
      expect((layer(id) as { filter?: unknown }).filter).toEqual(nearbyTrailFilter())
    }
    expect(
      (layer(BLAZE_DOTTED_LAYER_ID).paint as Record<string, unknown>)['line-dasharray'],
    ).toEqual(NEARBY_TRAIL_DASHARRAY)
    // Round caps are what turn a zero-length dash into a dot.
    expect(
      (layer(BLAZE_DOTTED_LAYER_ID).layout as Record<string, unknown>)['line-cap'],
    ).toBe('round')

    const ids = style().layers.map((l) => l.id)
    expect(ids.indexOf(TRAIL_CASING_DOTTED_LAYER_ID)).toBeLessThan(
      ids.indexOf(BLAZE_DOTTED_LAYER_ID),
    )
    expect(ids.indexOf(BLAZE_DOTTED_LAYER_ID)).toBeLessThan(
      ids.indexOf(TRAIL_CASING_LAYER_ID),
    )
  })

  it('dots the casing under a dotted line at the blaze’s own pitch, never solid', () => {
    // A solid casing under dots is the 2026-08-03 defect drawn one layer
    // down. Dash units scale with each layer's width, so the casing's
    // pattern is the blaze's scaled by the ratio of the two widths - and the
    // two pitches come out equal in CSS px at the side-trail tier, which is
    // the only tier the dotted layers draw.
    const casing = layer(TRAIL_CASING_DOTTED_LAYER_ID).paint as Record<string, unknown>
    expect(casing['line-dasharray']).toEqual(NEARBY_TRAIL_CASING_DASHARRAY)

    const blazePitch = NEARBY_TRAIL_DASHARRAY[1] * SIDE_TRAIL_WIDTH
    const casingPitch =
      NEARBY_TRAIL_CASING_DASHARRAY[1] * (SIDE_TRAIL_WIDTH + CASING_OVERHANG * 2)
    expect(casingPitch).toBeCloseTo(blazePitch)
  })

  it('gives both halves of the split one treatment, differing only in filter, dash and taper', () => {
    // Four layers from one builder. Anything else that differed would be a
    // channel added to one side and forgotten on the other. The three that
    // do differ are the three the split exists for: which lines each half
    // draws, the dot rhythm, and the width taper the dotted side takes
    // below the seam (#1306) - and the taper is not a fourth treatment,
    // because it LANDS on the solid side's own width at the seam, which
    // the two assertions under the loop hold.
    const strip = (id: string) => {
      const built = layer(id) as { filter?: unknown; paint: Record<string, unknown> }
      const paint = { ...built.paint }
      delete paint['line-dasharray']
      delete paint['line-width']
      delete paint['line-color']
      return { ...built, id: undefined, paint, filter: undefined }
    }
    expect(strip(BLAZE_DOTTED_LAYER_ID)).toEqual(strip(BLAZE_LAYER_ID))
    expect(strip(TRAIL_CASING_DOTTED_LAYER_ID)).toEqual(strip(TRAIL_CASING_LAYER_ID))

    const seam = (id: string) =>
      seamTier((layer(id).paint as Record<string, unknown>)['line-width'])
    expect(seam(BLAZE_DOTTED_LAYER_ID)).toEqual(seam(BLAZE_LAYER_ID))
    // The casing halves land on the same tier too, with the one difference
    // the near-white rule puts there on a day sheet (#1306): under a DOTTED
    // white line the casing is zero, because that line is inked dark.
    const dottedCasing = seam(TRAIL_CASING_DOTTED_LAYER_ID) as unknown[]
    expect(dottedCasing[0]).toBe('case')
    expect(dottedCasing[2]).toBe(0)
    expect(dottedCasing[3]).toEqual(seam(TRAIL_CASING_LAYER_ID))

    // Colour is the fourth difference and the newest (#1306): the dotted
    // half inks a near-white blaze dark and the solid half leaves it white,
    // off the same match expression either way.
    const color = (id: string) =>
      (layer(id).paint as Record<string, unknown>)['line-color']
    expect((color(BLAZE_DOTTED_LAYER_ID) as unknown[])[3]).toEqual(color(BLAZE_LAYER_ID))
  })

  it('partitions the trail source: every line lands on exactly one side', () => {
    // The filters are complements (nearbyTrails.test.ts holds that) and the
    // style uses exactly that pair, so this is the one-line check that the
    // style did not spell its own.
    expect((layer(BLAZE_DOTTED_LAYER_ID) as { filter?: unknown }).filter).toEqual([
      '!',
      (layer(BLAZE_LAYER_ID) as { filter?: unknown }).filter,
    ])
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
    const taper = paint['line-width'] as unknown[]
    const width = seamTier(taper) as unknown[]

    // Wrapped in the zoom taper (#1306), and data-driven inside it.
    expect(taper[0]).toBe('interpolate')
    expect(taper[2]).toEqual(['zoom'])
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
        expect(widthFor(seamTier(width['line-width']), primary)).toBeGreaterThan(other)
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
      expect(widthFor(seamTier(paint['line-width']), source)).toBe(PRIMARY_TRAIL_WIDTH)
    }
  })

  it('draws a source it has never heard of, rather than a zero-width line', () => {
    // A trail source imported later should reach the map on the fallback arm.
    // Drawn at nothing at all, it would be real data hidden behind a client
    // release - the same call poiLayers.ts makes for an unknown POI type.
    const paint = layer(BLAZE_LAYER_ID).paint as Record<string, unknown>

    expect(
      widthFor(seamTier(paint['line-width']), 'some_source_added_in_2027'),
    ).toBeGreaterThan(0)
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
    // Evaluated by MapLibre's engine for a Blue line, since the day sheet's
    // casing width is a `case` over the blaze (see the near-white block
    // below) rather than the bare match.
    const spec = latest.paint_line['line-width']
    for (const theme of ['light', 'dark'] as const) {
      const built = buildMapStyle({ ...STYLE_OPTIONS, theme })
      for (const source of [...Object.keys(TRAIL_LINE_WIDTHS), 'anything_else']) {
        const feature = { source, blaze_color: 'Blue' }
        const casing = paintFor(built, TRAIL_CASING_LAYER_ID, 'line-width', spec, feature)
        const blaze = paintFor(built, BLAZE_LAYER_ID, 'line-width', spec, feature)
        expect(((casing as number) - (blaze as number)) / 2).toBe(CASING_OVERHANG)
      }
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
    const dotted = layer(BLAZE_DOTTED_LAYER_ID).paint as Record<string, unknown>

    // Width from the side it is standing in for - this style has the A.T.
    // taken, so the sketch is solid and carries the solid taper.
    expect(sketch['line-width']).toEqual(blaze['line-width'])
    // Colour from the dotted half, always: the sketch has no casing pair,
    // so a near-white line has to be inked dark or it has no edge at all
    // (#1306, DARK_INKED_BLAZE_LAYER_IDS).
    expect(sketch['line-color']).toEqual(dotted['line-color'])
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
    // A blue blaze is a blue blaze on paper and on ink. Re-hueing the trail
    // lines per theme would make the map lie about which trail a hiker is
    // standing on, which is a different and much worse problem than a bright
    // map at night. Every hue but the near-white ones, which are the
    // exception the block below argues - they have no hue to keep on paper.
    const spec = latest.paint_line['line-color']
    for (const blaze of ['Blue', 'Yellow', 'Orange', 'Red', 'Green', 'Purple', 'Aqua']) {
      const feature = { source: 'side_trails', blaze_color: blaze }
      expect(
        paintFor(styled('dark'), BLAZE_LAYER_ID, 'line-color', spec, feature),
      ).toEqual(paintFor(styled('light'), BLAZE_LAYER_ID, 'line-color', spec, feature))
    }
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
    ...TRAIL_CASING_LAYER_IDS,
    ...BLAZE_LINE_LAYER_IDS,
    TRAIL_BADGE_LAYER_ID,
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

    // Leaving red light is a true restore: the blaze colour goes back
    // exactly as buildMapStyle spells it for the day sheet (the shared match
    // with near-white inked as casing), and the casing returns to the field
    // ink at the day sheet's width.
    // BLAZE_LAYER_ID is a SOLID half, so its restore is the plain match:
    // a white blaze keeps its own colour and its casing (#1306).
    expect(m.paintProperties.get(`${BLAZE_LAYER_ID}/line-color`)).toEqual(
      blazeLineColor({ theme: 'light' }, false),
    )
    expect(m.paintProperties.get(`${BLAZE_DOTTED_LAYER_ID}/line-color`)).toEqual(
      blazeLineColor({ theme: 'light' }, true),
    )
    expect(m.paintProperties.get(`${TRAIL_CASING_LAYER_ID}/line-color`)).toBe(
      TOPO_PALETTE.label,
    )
    expect(m.paintProperties.get(`${TRAIL_CASING_LAYER_ID}/line-width`)).toEqual(
      solidTrailCasingWidthExpression({ theme: 'light' }),
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

  it('is a vector source over the published tiles, read by range (#1257)', () => {
    // One shape of style whatever the bucket holds: the tiles are asked for
    // through a scheme networkTiles.ts answers, and a bucket with no archive
    // answers every tile empty rather than changing the style. The zoom range
    // is the archive's - lib/config.ts holds both ends against the pipeline's.
    expect(style().sources[NEARBY_TRAILS_SOURCE_ID]).toEqual({
      type: 'vector',
      tiles: [NETWORK_TILES_URL],
      minzoom: NEARBY_TRAILS_TILES_MIN_ZOOM,
      maxzoom: NEARBY_TRAILS_TILES_MAX_ZOOM,
      attribution: expect.any(String),
    })
  })

  it('cuts the tiles to start at the seam its layers start at', () => {
    // The source's minzoom, its layers' minzoom and the pipeline's
    // TILES_MIN_ZOOM are one number. A source that started above its layers
    // would leave a band of zooms asking for tiles that do not exist; one
    // that started below would cut tiles nothing asks for.
    expect(NEARBY_TRAILS_TILES_MIN_ZOOM).toBe(POI_PIN_MIN_ZOOM)
    expect(layer(NEARBY_BLAZE_LAYER_ID).minzoom).toBe(NEARBY_TRAILS_TILES_MIN_ZOOM)
  })

  it('names the one layer inside the tiles on every layer drawn from them', () => {
    // A vector layer with no source-layer, or the wrong one, draws nothing and
    // says nothing - the quietest failure a tileset has. Every layer over this
    // source, not a sample, so a fourth layer added later cannot forget it.
    const over = style().layers.filter(
      (l) => 'source' in l && l.source === NEARBY_TRAILS_SOURCE_ID,
    ) as { 'source-layer'?: string }[]

    expect(over.length).toBeGreaterThanOrEqual(4)
    for (const l of over) expect(l['source-layer']).toBe(NETWORK_TILES_LAYER)
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
    // `minzoom` and `source-layer` are the TWO permitted differences - the
    // seam, and the layer inside the tiles - and each is asserted on its own
    // elsewhere in this block, so that admitting them here cannot quietly
    // admit a third.
    expect(layer(NEARBY_BLAZE_LAYER_ID)).toEqual({
      ...layer(BLAZE_LAYER_ID),
      id: NEARBY_BLAZE_LAYER_ID,
      source: NEARBY_TRAILS_SOURCE_ID,
      'source-layer': NETWORK_TILES_LAYER,
      minzoom: POI_PIN_MIN_ZOOM,
    })
    expect(layer(NEARBY_TRAIL_CASING_LAYER_ID)).toEqual({
      ...layer(TRAIL_CASING_LAYER_ID),
      id: NEARBY_TRAIL_CASING_LAYER_ID,
      source: NEARBY_TRAILS_SOURCE_ID,
      'source-layer': NETWORK_TILES_LAYER,
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
      'source-layer': NETWORK_TILES_LAYER,
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
    expect(widthFor(seamTier(fullLines['line-width']), 'oprhp_trails')).toBe(
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

describe('a near-white blaze on paper is inked in the casing colour, with no casing (#1283)', () => {
  // lib/blaze.ts measures White at 1.02:1 against the field sheet's paper.
  // What carried it was the casing, and two dark rails around a near-white
  // line read as two dark rails - and around a DOTTED line, as nothing at
  // all. So on a day sheet the line takes the casing ink and the casing goes
  // to zero. Dark sheets keep both: on ink a white line has the surround it
  // needs, and the casing colour there is near-black.
  const colorSpec = latest.paint_line['line-color']
  const widthSpec = latest.paint_line['line-width']
  const white = { source: 'centerline', blaze_color: 'White' }
  const blue = { source: 'side_trails', blaze_color: 'Blue' }

  const DAY = [
    { name: 'field by day', options: { theme: 'light', mapStyle: 'field' } },
    { name: 'parchment by day', options: { theme: 'light', mapStyle: 'parchment' } },
  ] as const
  const NIGHT = [
    { name: 'the dark sheet', options: { theme: 'dark', mapStyle: 'field' } },
    { name: 'night hike', options: { theme: 'dark', mapStyle: 'night_hike' } },
  ] as const

  it('names White, and only White, as near-white today', () => {
    expect(NEAR_WHITE_BLAZES).toEqual(['White'])
  })

  it.each(DAY)(
    'inks a White line in the sheet’s casing colour — $name',
    ({ options }) => {
      const built = buildMapStyle({ ...STYLE_OPTIONS, ...options })
      expect(inksNearWhiteAsCasing(options)).toBe(true)
      // The dotted halves and both sketches (#1306): dark ink, because a
      // dotted white line has nothing between its rails.
      for (const id of DARK_INKED_BLAZE_LAYER_IDS) {
        expect(paintFor(built, id, 'line-color', colorSpec, white), id).toBe(
          trailCasingColor(options),
        )
      }
      // The solid halves keep the white blaze, with the casing that gives it
      // an edge - the maintainer's call on the frame, 2026-09-09.
      for (const id of [BLAZE_LAYER_ID, NEARBY_BLAZE_LAYER_ID]) {
        expect(paintFor(built, id, 'line-color', colorSpec, white), id).toBe('#fffdf7')
      }
      // And leaves a Blue one exactly as the shared match paints it.
      expect(paintFor(built, BLAZE_LAYER_ID, 'line-color', colorSpec, blue)).toBe(
        '#1f5fa8',
      )
    },
  )

  it.each(DAY)('draws no casing under a DOTTED one — $name', ({ options }) => {
    // paintFor evaluates at zoom 12, above the seam, where the taper
    // (#1306) is already at the layer's own tier.
    const built = buildMapStyle({ ...STYLE_OPTIONS, ...options })
    for (const id of DOTTED_TRAIL_CASING_LAYER_IDS) {
      expect(paintFor(built, id, 'line-width', widthSpec, white), id).toBe(0)
      expect(paintFor(built, id, 'line-width', widthSpec, blue), id).toBe(
        SIDE_TRAIL_WIDTH + CASING_OVERHANG * 2,
      )
    }
    // And keeps it under a solid one, which is what lets that line stay
    // white (#1306).
    for (const id of [TRAIL_CASING_LAYER_ID, NEARBY_TRAIL_CASING_LAYER_ID]) {
      expect(paintFor(built, id, 'line-width', widthSpec, white), id).toBeGreaterThan(0)
    }
  })

  it.each(NIGHT)(
    'keeps a White line white, with its casing, on ink — $name',
    ({ options }) => {
      const built = buildMapStyle({ ...STYLE_OPTIONS, ...options })
      expect(inksNearWhiteAsCasing(options)).toBe(false)
      expect(paintFor(built, BLAZE_LAYER_ID, 'line-color', colorSpec, white)).toBe(
        '#fffdf7',
      )
      expect(paintFor(built, TRAIL_CASING_LAYER_ID, 'line-width', widthSpec, white)).toBe(
        PRIMARY_TRAIL_WIDTH + CASING_OVERHANG * 2,
      )
    },
  )

  it('takes red light as the dark half, where the blaze is red anyway', () => {
    const redLight = { theme: 'dark', mapStyle: 'night_hike', redLight: true } as const
    expect(inksNearWhiteAsCasing(redLight)).toBe(false)
    expect(blazeLineColor(redLight)).toBe(RED_LIGHT_BLAZE_COLOR)
    expect(trailCasingWidthExpression(redLight)).toEqual(
      trailCasingWidthExpression({ theme: 'dark' }),
    )
  })
})

describe('attachMapAppearance repaints every trail line, not two of them (#1283)', () => {
  it('repaints both halves of both splits and both sketches', async () => {
    // The old repaint wrote two layers by name and left the nearby pair and
    // the sketches on the previous sheet's ink. A theme switch has to reach
    // every layer painting a blaze or a casing, or the dotted lines keep the
    // night sheet's colours on the way to day.
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const m = new MockMap({})
    m.layerIds = [BACKDROP_LAYER_ID, ...TRAIL_CASING_LAYER_IDS, ...BLAZE_LINE_LAYER_IDS]

    attachMapAppearance(m as never, { theme: 'dark' })

    for (const id of BLAZE_LINE_LAYER_IDS) {
      expect(m.paintProperties.get(`${id}/line-color`), id).toEqual(
        blazeLineColor({ theme: 'dark' }, DARK_INKED_BLAZE_LAYER_IDS.includes(id)),
      )
    }
    for (const id of TRAIL_CASING_LAYER_IDS) {
      const dotted = DOTTED_TRAIL_CASING_LAYER_IDS.includes(id)
      expect(m.paintProperties.get(`${id}/line-color`), id).toBe(
        trailCasingColor({ theme: 'dark' }),
      )
      // Per side since #1306, so a theme switch cannot put the dotted
      // half's zero-under-white casing under a solid line, or vice versa.
      expect(m.paintProperties.get(`${id}/line-width`), id).toEqual(
        dotted
          ? dottedTrailCasingWidthExpression({ theme: 'dark' })
          : solidTrailCasingWidthExpression({ theme: 'dark' }),
      )
    }
  })

  it('lists every blaze-coloured and every casing layer the style builds', () => {
    // The lists are what the repaint walks, so a layer in the style and not
    // in a list is a layer a theme switch leaves behind.
    const built = style()
    const blazePainted = built.layers
      .filter((l) => l.type === 'line' && JSON.stringify(l.paint).includes('blaze_color'))
      .map((l) => l.id)
      .filter((id) => !id.includes('closure') && !id.includes('corridor'))
    for (const id of blazePainted) {
      expect([...BLAZE_LINE_LAYER_IDS, ...TRAIL_CASING_LAYER_IDS]).toContain(id)
    }
    for (const id of [...BLAZE_LINE_LAYER_IDS, ...TRAIL_CASING_LAYER_IDS]) {
      expect(built.layers.map((l) => l.id)).toContain(id)
    }
  })

  it('swaps the badge’s plate and ink with the sheet', async () => {
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const m = new MockMap({})
    m.layerIds = [BACKDROP_LAYER_ID, TRAIL_BADGE_LAYER_ID]

    attachMapAppearance(m as never, { theme: 'dark' })
    expect(m.layoutProperties.get(`${TRAIL_BADGE_LAYER_ID}/icon-image`)).toBe(
      TRAIL_BADGE_PLATE_NIGHT.id,
    )
    expect(m.paintProperties.get(`${TRAIL_BADGE_LAYER_ID}/text-color`)).toBe(
      TRAIL_BADGE_PLATE_NIGHT.text,
    )

    attachMapAppearance(m as never, { theme: 'light' })
    expect(m.layoutProperties.get(`${TRAIL_BADGE_LAYER_ID}/icon-image`)).toBe(
      TRAIL_BADGE_PLATE_DAY.id,
    )
    expect(m.paintProperties.get(`${TRAIL_BADGE_LAYER_ID}/text-color`)).toBe(
      TRAIL_BADGE_PLATE_DAY.text,
    )
  })
})

describe('the through-route badge (#1283)', () => {
  const ids = () => style().layers.map((l) => l.id)

  it('draws from its own point source, declared empty', () => {
    const source = style().sources[TRAIL_BADGE_SOURCE_ID] as {
      type: string
      data: { features: unknown[] }
    }
    expect(source.type).toBe('geojson')
    expect(source.data.features).toEqual([])
  })

  it('sits after both label layers and before every pin', () => {
    // Placement runs top-down, later winning: a badge beats an along-line
    // name for a contested spot and loses to anything a hiker acts on.
    const order = ids()
    expect(order.indexOf(TRAIL_BADGE_LAYER_ID)).toBeGreaterThan(
      order.indexOf(TRAIL_LABEL_LAYER_ID),
    )
    expect(order.indexOf(TRAIL_BADGE_LAYER_ID)).toBeGreaterThan(
      order.indexOf(NEARBY_TRAIL_LABEL_LAYER_ID),
    )
    expect(order.indexOf(TRAIL_BADGE_LAYER_ID)).toBeLessThan(order.indexOf(POI_LAYER_ID))
    expect(order.indexOf(TRAIL_BADGE_LAYER_ID)).toBeLessThan(
      order.indexOf(WARNING_LAYER_ID),
    )
  })

  it('is one symbol: the plate fitted to a text that carries the mark and the name', () => {
    const badge = layer(TRAIL_BADGE_LAYER_ID)
    const layout = badge.layout as Record<string, unknown>
    expect(badge.type).toBe('symbol')
    expect(layout['symbol-placement']).toBe('point')
    expect(layout['icon-text-fit']).toBe('both')
    expect(layout['icon-image']).toBe(badgePlateImageId({ theme: 'light' }))
    // A `case` on the feature's fit - the full form or the mark alone
    // (trailBadges.ts's header) - and either branch is one `format`.
    const text = layout['text-field'] as unknown[]
    expect(text[0]).toBe('case')
    expect((text[2] as unknown[])[0]).toBe('format')
    expect((text[3] as unknown[])[0]).toBe('format')
    expect(JSON.stringify(text)).toContain('"image"')
    expect(JSON.stringify(text)).toContain('["get","name"]')
    // Both halves required: a plate with no name says nothing, and a name
    // with no plate is the along-line label this layer must differ from.
    expect(layout['icon-optional']).toBe(false)
    expect(layout['text-optional']).toBe(false)
  })

  it('may slide round its vertex when a pin is in the way, mark-first', () => {
    // The first preview frame's lesson: pins are placed first, a symbol
    // with one position that collides is dropped whole, and Harriman's
    // one badge vanished beside a water pin. Reproduced and fixed in a
    // stand-alone render (trailBadges.ts's TRAIL_BADGE_ANCHORS).
    const layout = layer(TRAIL_BADGE_LAYER_ID).layout as Record<string, unknown>
    expect(layout['text-variable-anchor']).toEqual(TRAIL_BADGE_ANCHORS)
    expect(TRAIL_BADGE_ANCHORS[0]).toBe('left')
    expect(TRAIL_BADGE_ANCHORS.length).toBeGreaterThanOrEqual(4)
    expect(layout['text-radial-offset']).toBe(TRAIL_BADGE_RADIAL_OFFSET)
    expect(layout['text-anchor']).toBeUndefined()
  })

  it('ranks on the label ladder’s route-trail rung and dims with its line', () => {
    const badge = layer(TRAIL_BADGE_LAYER_ID)
    expect((badge.layout as Record<string, unknown>)['symbol-sort-key']).toBe(
      LABEL_TIER.routeTrail,
    )
    const paint = badge.paint as Record<string, unknown>
    expect(paint['icon-opacity']).toEqual(nearbyTrailOpacityExpression())
    expect(paint['text-opacity']).toEqual(nearbyTrailOpacityExpression())
    expect(paint['text-color']).toBe(badgeTextColor({ theme: 'light' }))
  })

  it('starts where the trail labels start, at the overview band', () => {
    expect(layer(TRAIL_BADGE_LAYER_ID).minzoom).toBe(TRAIL_LABEL_MIN_ZOOM)
    expect(layer(TRAIL_LABEL_LAYER_ID).minzoom).toBe(TRAIL_LABEL_MIN_ZOOM)
  })

  it('validates with the badge in it, on both sheets', () => {
    for (const theme of ['light', 'dark'] as const) {
      expect(validateStyleMin(buildMapStyle({ ...STYLE_OPTIONS, theme }))).toEqual([])
    }
  })
})

describe('the network overview and the nearby network split like the trail source (#1283)', () => {
  it('draws the overview’s dotted half under its solid half, with the shared taper', () => {
    const ids = style().layers.map((l) => l.id)
    expect(ids.indexOf(NETWORK_OVERVIEW_DOTTED_LAYER_ID)).toBeLessThan(
      ids.indexOf(NETWORK_OVERVIEW_LAYER_ID),
    )
    const dotted = layer(NETWORK_OVERVIEW_DOTTED_LAYER_ID)
    const solid = layer(NETWORK_OVERVIEW_LAYER_ID)
    expect((dotted.paint as Record<string, unknown>)['line-dasharray']).toEqual(
      NEARBY_TRAIL_DASHARRAY,
    )
    expect((dotted.paint as Record<string, unknown>)['line-width']).toEqual(
      (solid.paint as Record<string, unknown>)['line-width'],
    )
    expect((dotted as { filter?: unknown }).filter).toEqual(nearbyTrailFilter())
    expect((solid as { filter?: unknown }).filter).toEqual(chosenSystemFilter())
    expect(dotted.maxzoom).toBe(POI_PIN_MIN_ZOOM)
  })

  it('gives the nearby network the same dotted pair, above the seam, in the tiles’ layer', () => {
    expect(layer(NEARBY_BLAZE_DOTTED_LAYER_ID)).toEqual({
      ...layer(BLAZE_DOTTED_LAYER_ID),
      id: NEARBY_BLAZE_DOTTED_LAYER_ID,
      source: NEARBY_TRAILS_SOURCE_ID,
      'source-layer': NETWORK_TILES_LAYER,
      minzoom: POI_PIN_MIN_ZOOM,
    })
    expect(layer(NEARBY_TRAIL_CASING_DOTTED_LAYER_ID)).toEqual({
      ...layer(TRAIL_CASING_DOTTED_LAYER_ID),
      id: NEARBY_TRAIL_CASING_DOTTED_LAYER_ID,
      source: NEARBY_TRAILS_SOURCE_ID,
      'source-layer': NETWORK_TILES_LAYER,
      minzoom: POI_PIN_MIN_ZOOM,
    })
    const ids = style().layers.map((l) => l.id)
    expect(ids.indexOf(NEARBY_BLAZE_DOTTED_LAYER_ID)).toBeLessThan(
      ids.indexOf(NEARBY_TRAIL_CASING_LAYER_ID),
    )
  })
})

describe('nothing taken (#1306)', () => {
  // First launch: `chosenTrailId` null, every line dotted, nothing ghosted.
  const untaken = buildMapStyle({ ...STYLE_OPTIONS, chosenTrailId: null })
  const taken = buildMapStyle(STYLE_OPTIONS)
  const layerIn = (style: { layers: Array<{ id: string }> }, id: string) =>
    style.layers.find((candidate) => candidate.id === id) as
      { filter?: unknown; paint?: Record<string, unknown> } | undefined

  it('puts every line on the dotted side and nothing on the solid one', () => {
    for (const [id, side] of CHOSEN_TRAIL_SPLIT_LAYERS) {
      expect(layerIn(untaken, id)?.filter, id).toEqual(
        side === 'chosen' ? chosenSystemFilter([]) : nearbyTrailFilter([]),
      )
    }
  })

  it('ghosts nothing - lines, sketches, labels and the badge alike', () => {
    for (const id of [
      BLAZE_DOTTED_LAYER_ID,
      NEARBY_BLAZE_DOTTED_LAYER_ID,
      NETWORK_OVERVIEW_DOTTED_LAYER_ID,
      TRAIL_OVERVIEW_LAYER_ID,
    ]) {
      expect(layerIn(untaken, id)?.paint?.['line-opacity'], id).toBe(CHOSEN_TRAIL_OPACITY)
    }
    expect(layerIn(untaken, TRAIL_LABEL_LAYER_ID)?.paint?.['text-opacity']).toBe(
      CHOSEN_TRAIL_OPACITY,
    )
    expect(layerIn(untaken, TRAIL_BADGE_LAYER_ID)?.paint?.['icon-opacity']).toBe(
      CHOSEN_TRAIL_OPACITY,
    )
  })

  it("dots the A.T.'s own sketch, since the line it stands in for is dotted", () => {
    expect(layerIn(untaken, TRAIL_OVERVIEW_LAYER_ID)?.paint?.['line-dasharray']).toEqual(
      NEARBY_TRAIL_DASHARRAY,
    )
    expect(
      layerIn(taken, TRAIL_OVERVIEW_LAYER_ID)?.paint?.['line-dasharray'],
    ).toBeUndefined()
  })

  it('tapers every dotted line below the seam, and no solid one', () => {
    // A dot rhythm below the seam is a stroke of the line's own width (the
    // A.T. folds inside a pixel at the corridor camera), so the tier there
    // is a rope; the handoff's frame 2a draws every untaken line at one
    // fine weight. The solid side is untouched - a taken trail keeps its
    // 4.5 px at every zoom.
    for (const id of [BLAZE_DOTTED_LAYER_ID, NEARBY_BLAZE_DOTTED_LAYER_ID]) {
      expect(layerIn(untaken, id)?.paint?.['line-width'], id).toEqual(
        dottedTrailWidthExpression(),
      )
    }
    // The solid side tapers too, by its own tier rather than flat: a TAKEN
    // A.T. at 4.5 px from Georgia to Maine is the same rope by another name
    // ("it looks like a black line", 2026-09-09).
    for (const id of [BLAZE_LAYER_ID, NEARBY_BLAZE_LAYER_ID]) {
      expect(layerIn(untaken, id)?.paint?.['line-width'], id).toEqual(
        solidTrailWidthExpression(),
      )
    }
    // And the scale is derived, not picked: a side trail's far end IS the
    // network overview's own far width, so the two agree where they meet.
    expect(
      widthFor(
        (solidTrailWidthExpression() as unknown[])[4],
        Object.keys(TRAIL_LINE_WIDTHS).find(
          (source) => !PRIMARY_TRAIL_SOURCES.includes(source),
        ) as string,
      ),
    ).toBeCloseTo(NETWORK_OVERVIEW_FAR_WIDTH)
    // Both stops land on the layer's own tier at the seam and on the
    // network overview's weight at the far end, so the three tapers agree
    // to the pixel where they meet.
    const width = dottedTrailWidthExpression() as unknown[]
    expect(width[3]).toBe(OVERVIEW_FAR_ZOOM)
    expect(width[4]).toBe(NETWORK_OVERVIEW_FAR_WIDTH)
    expect(width[5]).toBe(POI_PIN_MIN_ZOOM)
    expect(width[6]).toEqual(TRAIL_WIDTH_EXPRESSION)
  })

  it('keeps the hairline under a tapered dotted line, and no casing under near-white', () => {
    // The casing takes the same taper plus the same overhang at both stops,
    // so the hairline is a hairline at 1.5 px and at 4.5 px alike. On a day
    // sheet a near-white line is inked in the casing colour and carries no
    // casing at any zoom - the `case` sits inside each stop, because a zoom
    // expression nested in a `case` is a style error.
    const day = dottedTrailCasingWidthExpression({ theme: 'light' }) as unknown[]
    expect(day[4]).toEqual([
      'case',
      expect.anything(),
      0,
      NETWORK_OVERVIEW_FAR_WIDTH + CASING_OVERHANG * 2,
    ])
    expect(day[6]).toEqual(trailCasingWidthExpression({ theme: 'light' }))
    expect(dottedTrailCasingWidthExpression({ theme: 'dark' })).toEqual([
      'interpolate',
      ['linear'],
      ['zoom'],
      OVERVIEW_FAR_ZOOM,
      NETWORK_OVERVIEW_FAR_WIDTH + CASING_OVERHANG * 2,
      POI_PIN_MIN_ZOOM,
      TRAIL_CASING_WIDTH_EXPRESSION,
    ])
  })

  it("draws the untaken sketch at the network's weight, its own tier only once taken", () => {
    // 4.5 px dots on a 51,068-vertex line at z4 fill their own gaps and read
    // as a black rope (the eleventh preview build); the handoff's frame 2a
    // draws every untaken line at 1.5 px at the `us` scope. Taken, the
    // sketch is the real line's width at every zoom, as before #1306.
    expect(layerIn(untaken, TRAIL_OVERVIEW_LAYER_ID)?.paint?.['line-width']).toEqual([
      'interpolate',
      ['linear'],
      ['zoom'],
      4,
      NETWORK_OVERVIEW_FAR_WIDTH,
      POI_PIN_MIN_ZOOM,
      TRAIL_WIDTH_EXPRESSION,
    ])
    expect(layerIn(taken, TRAIL_OVERVIEW_LAYER_ID)?.paint?.['line-width']).toEqual(
      solidTrailWidthExpression(),
    )
    expect(sketchWidthExpression([])).toEqual(
      layerIn(untaken, TRAIL_OVERVIEW_LAYER_ID)?.paint?.['line-width'],
    )
  })

  it('names every line layer that reads the chosen system, so a new split cannot be left behind', () => {
    // attachChosenTrail re-points the layers in CHOSEN_TRAIL_SPLIT_LAYERS on a
    // live map; this holds that list equal to the style's own set of layers
    // filtering on the chosen system, in either direction.
    const solid = JSON.stringify(chosenSystemFilter())
    const dotted = JSON.stringify(nearbyTrailFilter())
    const readers = taken.layers
      .filter((candidate) => {
        const filter = JSON.stringify((candidate as { filter?: unknown }).filter ?? null)
        return filter === solid || filter === dotted
      })
      .map((candidate) => candidate.id)
      .sort()
    expect([...CHOSEN_TRAIL_SPLIT_LAYERS].map(([id]) => id).sort()).toEqual(readers)
  })

  it("opens the network's dots at the prototype's weight, not a sub-pixel haze", () => {
    // 0.8 px dots at 45% were the tenth preview build's faint speckle over
    // New York - the maintainer read the opening camera as the A.T. alone.
    // The prototype draws every untaken line at 1.5 px at the `us` scope
    // (Opening Map Options.html, frame 2a).
    expect(NETWORK_OVERVIEW_FAR_WIDTH).toBe(1.5)
    expect(NETWORK_OVERVIEW_WIDTH_EXPRESSION[4]).toBe(NETWORK_OVERVIEW_FAR_WIDTH)
  })
})
