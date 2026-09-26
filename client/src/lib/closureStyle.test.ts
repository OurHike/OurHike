import { describe, it, expect } from 'vitest'
import { createExpression, latest } from '@maplibre/maplibre-gl-style-spec'
import {
  CLOSURE_COLOR,
  CLOSURE_CROSS_ARM,
  CLOSURE_CROSS_ICON_ID,
  CLOSURE_CROSS_PADDING,
  CLOSURE_CROSS_SIZE,
  CLOSURE_CROSS_SPACING,
  CLOSURE_CROSS_STROKE,
  CLOSURE_FULL_WIDTH_ZOOM,
  CLOSURE_INK,
  CLOSURE_LAYER_ID,
  CLOSURE_MARK_MIN_ZOOM,
  CLOSURE_NEAR_MIN_ZOOM,
  CLOSURE_PAPER_FAR_WIDTH,
  CLOSURE_PAPER_WIDTH,
  CLOSURE_TRACE_WIDTH,
  buildClosureLayers,
  closureCrossImageSize,
  closureCrossesId,
  closureLayerIds,
  closureMarkId,
  closureTraceId,
} from './closureStyle'
import {
  buildMapStyle,
  BLAZE_LAYER_ID,
  BLAZE_LINE_WIDTH,
  CASING_LINE_WIDTH,
  RED_LIGHT_BLAZE_COLOR,
} from '../map/style'
import { PLAIN_TRAIL_COLOR } from './blaze'
import { POI_DOT_LAYER_ID, POI_LAYER_ID, POI_PIN_MIN_ZOOM } from '../map/poiLayers'

// WIREFRAMES.md §7 and its Load-bearing values: a closure is the closed trail
// crossed out, a blaze is the trail.
//
// This file exists for one reason. A closure that reads as a trail is a
// safety failure - a hiker glancing at a phone in glare would see a side
// trail where the real message is "do not walk down there." So the two must
// differ STRUCTURALLY, not only in hue: colour alone disappears in greyscale,
// in sunlight, and for a red-green colour-blind hiker.
//
// THE QUESTIONS HAVE OUTLIVED FOUR SPELLINGS OF THE MARK, which is the point
// of writing them as questions. They were asked of a dashed line over a
// casing, of barrier tape, of a barred band, and now of the crossed-out trail
// (#1677) - lib/closureStyle.ts's header has why each ended. What has not
// moved: does a closure carry something no trail line has, does it take the
// trail's own colour off the map, and does it survive with hue removed. What
// is new is the zoom question, because the red bands failed it: every zoom a
// closure can be drawn at is drawn with SOME mark a hiker can read.

/** A zoom-dependent value, as MapLibre's own engine resolves it at `zoom`,
 *  compiled against the real property spec - so a taper this file reads is a
 *  taper the map would draw. */
function evaluateZoom(value: unknown, zoom: number, spec: unknown): number {
  const compiled = createExpression(value as never, spec as never)
  if (compiled.result === 'error') throw new Error('not a valid expression')
  return compiled.value.evaluate({ zoom }, {} as never) as number
}
const lineWidthAt = (value: unknown, zoom: number) =>
  evaluateZoom(value, zoom, latest.paint_line['line-width'])
const spacingAt = (value: unknown, zoom: number) =>
  evaluateZoom(value, zoom, latest.layout_symbol['symbol-spacing'])
const iconSizeAt = (value: unknown, zoom: number) =>
  evaluateZoom(value, zoom, latest.layout_symbol['icon-size'])

type AnyLayer = {
  id: string
  type: string
  source?: string
  filter?: unknown
  minzoom?: number
  maxzoom?: number
  layout?: Record<string, unknown>
  paint?: Record<string, unknown>
}

const GROUND = '#ffffff'
const INK = CLOSURE_INK
const LAYERS = buildClosureLayers('closures', { ground: GROUND, ink: INK }) as AnyLayer[]
const byId = (id: string): AnyLayer => {
  const found = LAYERS.find((l) => l.id === id)
  if (found === undefined) throw new Error(`no layer ${id}`)
  return found
}
const PAPER = byId(CLOSURE_LAYER_ID)
const TRACE = byId(closureTraceId(CLOSURE_LAYER_ID))
const CROSSES = byId(closureCrossesId(CLOSURE_LAYER_ID))
const MARK = byId(closureMarkId(CLOSURE_LAYER_ID))

/** The built style's layers, read rather than described - the claims below
 *  about trail lines and pins are about what actually ships. */
function builtLayers(): AnyLayer[] {
  return buildMapStyle({
    topoArchiveUrl: 'pmtiles://ourhike-corridor',
    trailsUrl: '/data/trails.geojson',
  }).layers as AnyLayer[]
}

describe('closure vs blaze, as structural difference', () => {
  it('crosses the closed line out with a shape no trail line carries', () => {
    // The whole mark in one assertion: a chain of crosses placed along the
    // line. No trail layer in the built style places anything along a line
    // but its name, so an icon along a line is the closure's alone.
    expect(CROSSES.type).toBe('symbol')
    expect(CROSSES.layout?.['symbol-placement']).toBe('line')
    expect(CROSSES.layout?.['icon-image']).toBe(CLOSURE_CROSS_ICON_ID)
    const closureIds = new Set(
      [
        'closure-band',
        'long-term-closure-band',
        'nearby-long-term-closure-band',
        'network-overview-closure-band',
        'atc-update-band',
      ].flatMap(closureLayerIds),
    )
    const iconsAlongLines = builtLayers().filter(
      (l) =>
        l.layout?.['symbol-placement'] === 'line' &&
        l.layout?.['icon-image'] !== undefined &&
        !closureIds.has(l.id),
    )
    expect(iconsAlongLines.map((l) => l.id)).toEqual([])
  })

  it('covers the widest trail line and its casing, so no red shows along a closure', () => {
    // The trail's own red is what every red band before this one competed
    // with, and lost to. The paper takes it off the map: it is wider than
    // the widest line the map draws with its casing (the A.T. with blaze
    // colours on), with half a pixel to spare each side.
    expect(CLOSURE_PAPER_WIDTH).toBeGreaterThanOrEqual(CASING_LINE_WIDTH + 1)
    expect(lineWidthAt(PAPER.paint?.['line-width'], CLOSURE_FULL_WIDTH_ZOOM)).toBe(
      CLOSURE_PAPER_WIDTH,
    )
    // And it is the opaque paper, with no texture to let the red through.
    expect(PAPER.paint?.['line-dasharray']).toBeUndefined()
    expect(PAPER.paint?.['line-opacity']).toBeUndefined()
    expect(PAPER.paint?.['line-color']).toBe(GROUND)
  })

  it('never draws the closure in the trails’ red', () => {
    // Every trail is PLAIN_TRAIL_COLOR by default (#1575), and it is the
    // same hex as CLOSURE_COLOR - which is the red-on-red the maintainer
    // could not read. Nothing in the mark may paint either.
    const colours = JSON.stringify(LAYERS).toLowerCase()
    expect(PLAIN_TRAIL_COLOR.toLowerCase()).toBe(CLOSURE_COLOR.toLowerCase())
    expect(colours).not.toContain(CLOSURE_COLOR.toLowerCase())
  })

  it('traces the closed trail dotted, where the trail a hiker takes is solid', () => {
    // A BLAZE IS SOLID UNDER THE HUES, which is the appearance blazePaint
    // builds with; the default sheet dashes its context trails (#1588), and
    // the dots differ from those too, in rhythm and in colour.
    const blaze = builtLayers().find((l) => l.id === BLAZE_LAYER_ID)
    expect(blaze?.paint?.['line-dasharray']).toBeUndefined()
    expect(TRACE.paint?.['line-dasharray']).toBeDefined()
    expect(TRACE.layout?.['line-cap']).toBe('round')
  })

  it('stays distinguishable with hue removed entirely', () => {
    // The greyscale test: strip colour and the two must still differ on at
    // least two independent channels. A shape (the crosses) and a texture
    // (the dotted trace), neither of which is a colour.
    const differsOnShape = CROSSES.layout?.['icon-image'] !== undefined
    const differsOnTexture = TRACE.paint?.['line-dasharray'] !== undefined
    const differsOnWidth = (CLOSURE_PAPER_WIDTH as number) !== BLAZE_LINE_WIDTH

    expect(
      [differsOnShape, differsOnTexture, differsOnWidth].filter(Boolean).length,
    ).toBeGreaterThanOrEqual(2)
  })
})

describe('a closure is drawn with a readable mark at every zoom', () => {
  it('hands the far mark to the chain at one zoom, with no gap and no overlap', () => {
    // The far mark draws [CLOSURE_MARK_MIN_ZOOM, CLOSURE_NEAR_MIN_ZOOM) and
    // the chain from CLOSURE_NEAR_MIN_ZOOM up, so at every zoom from the pin
    // seam in exactly one of them is drawn.
    expect(MARK.minzoom).toBe(CLOSURE_MARK_MIN_ZOOM)
    expect(MARK.maxzoom).toBe(CLOSURE_NEAR_MIN_ZOOM)
    expect(CROSSES.minzoom).toBe(CLOSURE_NEAR_MIN_ZOOM)
    expect(CROSSES.maxzoom).toBeUndefined()
  })

  it('starts the far mark at the pin seam, like every other point mark', () => {
    // Below the seam the map draws trail lines only (#1292). A literal in
    // lib/ because lib/ does not import map/, so held equal here.
    expect(CLOSURE_MARK_MIN_ZOOM).toBe(POI_PIN_MIN_ZOOM)
  })

  it('starts the chain where the shortest closure first holds one cross', () => {
    // The arithmetic CLOSURE_NEAR_MIN_ZOOM is derived from, re-run rather
    // than trusted. MapLibre puts a symbol on a line only where the line is
    // at least as long as the symbol, and OPRHP's shortest closed run is
    // 1.1 km; at latitude 41 a zoom covers 117,610 / 2^z metres per pixel.
    const SHORTEST_CLOSED_RUN_M = 1100
    const runInPixels = (zoom: number) => SHORTEST_CLOSED_RUN_M / (117610 / 2 ** zoom)
    const crossAtNear =
      closureCrossImageSize() *
      iconSizeAt(CROSSES.layout?.['icon-size'], CLOSURE_NEAR_MIN_ZOOM)

    expect(runInPixels(CLOSURE_NEAR_MIN_ZOOM)).toBeGreaterThan(crossAtNear)
    expect(runInPixels(CLOSURE_NEAR_MIN_ZOOM - 1)).toBeLessThan(crossAtNear)
  })

  it('spaces the chain wider than MapLibre’s own floor, so the number drawn is the number written', () => {
    // MapLibre silently widens a symbol spacing under 1.25 of the symbol's
    // length. A stop under that floor would draw a spacing nobody chose.
    for (const [zoom, spacing] of CLOSURE_CROSS_SPACING) {
      const length =
        closureCrossImageSize() * iconSizeAt(CROSSES.layout?.['icon-size'], zoom)
      expect(spacing, `z${zoom}`).toBeGreaterThanOrEqual(length * 1.25)
    }
    expect(CLOSURE_CROSS_SIZE[0][0]).toBe(CLOSURE_NEAR_MIN_ZOOM)
  })

  it('grows the paper and the trace with the zoom, and never shrinks them as a hiker zooms in', () => {
    const zooms = [0, 4, 7, 9, 11, 12, 13, 16, 20]
    for (const layer of [PAPER, TRACE]) {
      const widths = zooms.map((z) => lineWidthAt(layer.paint?.['line-width'], z))
      expect(widths, layer.id).toEqual([...widths].sort((a, b) => a - b))
    }
    expect(lineWidthAt(PAPER.paint?.['line-width'], CLOSURE_MARK_MIN_ZOOM)).toBe(
      CLOSURE_PAPER_FAR_WIDTH,
    )
    expect(lineWidthAt(TRACE.paint?.['line-width'], 16)).toBe(CLOSURE_TRACE_WIDTH)
  })
})

describe('buildClosureLayers', () => {
  it('draws paper, trace, chain and far mark, in that order', () => {
    // The order is the claim: the trace on the paper, the crosses over the
    // trace. No layer anywhere is a `line-pattern`, the texture that tore at
    // every bend (#1599).
    expect(LAYERS.map((l) => l.id)).toEqual(closureLayerIds(CLOSURE_LAYER_ID))
    expect(LAYERS.map((l) => l.type)).toEqual(['line', 'line', 'symbol', 'symbol'])
    expect(JSON.stringify(LAYERS)).not.toContain('line-pattern')
  })

  it('reads every layer from the source and filter it was given', () => {
    const filter = ['==', ['get', 'trail_status'], 'closed']
    const filtered = buildClosureLayers('trails', {
      ground: GROUND,
      ink: INK,
      bandId: 'x',
      filter,
    }) as AnyLayer[]

    expect(filtered.every((l) => l.source === 'trails')).toBe(true)
    expect(
      filtered.every((l) => JSON.stringify(l.filter) === JSON.stringify(filter)),
    ).toBe(true)
    expect(LAYERS.every((l) => l.source === 'closures' && l.filter === undefined)).toBe(
      true,
    )
  })

  it('paints the paper and ink it was given, and the crosses’ halo in the paper', () => {
    const red = buildClosureLayers('closures', {
      ground: '#140503',
      ink: RED_LIGHT_BLAZE_COLOR,
    }) as AnyLayer[]
    const [paper, trace, crosses, mark] = red

    expect(paper.paint?.['line-color']).toBe('#140503')
    expect(trace.paint?.['line-color']).toBe(RED_LIGHT_BLAZE_COLOR)
    for (const symbol of [crosses, mark]) {
      expect(symbol.paint?.['icon-color']).toBe(RED_LIGHT_BLAZE_COLOR)
      expect(symbol.paint?.['icon-halo-color']).toBe('#140503')
    }
  })

  it('spaces the ATC’s chain by the scale it is handed, and nothing else', () => {
    const slower = buildClosureLayers('atc', {
      ground: GROUND,
      ink: INK,
      bandId: CLOSURE_LAYER_ID,
      spacingScale: 2,
    }) as AnyLayer[]
    for (const [zoom] of CLOSURE_CROSS_SPACING) {
      expect(spacingAt(slower[2].layout?.['symbol-spacing'], zoom)).toBe(
        2 * spacingAt(CROSSES.layout?.['symbol-spacing'], zoom),
      )
    }
    const strip = (layers: AnyLayer[]) =>
      layers.map(({ source: _source, layout, ...rest }) => ({
        ...rest,
        layout: { ...layout, 'symbol-spacing': undefined },
      }))
    expect(strip(slower)).toEqual(strip(LAYERS))
  })

  it('never drops a cross from the chain, and never lets one push a label off', () => {
    // A cross dropped by the collision engine is a gap in the closure; a
    // cross that took part in collision would evict trail names along it.
    expect(CROSSES.layout?.['icon-allow-overlap']).toBe(true)
    expect(CROSSES.layout?.['icon-ignore-placement']).toBe(true)
  })

  it('lets far marks thin each other out, and cannot hide a waypoint doing it', () => {
    // CLOSURE_MARK_PADDING's docstring: a closed network is a hundred line
    // parts, and the far marks collide so it reads as a few. A pin a far
    // mark displaces is not hidden: every waypoint is also drawn by the dot
    // layer under the pins (#597), a `circle` layer, which takes no part in
    // collision - so the waypoint falls back to its dot. Read off the built
    // style, over the pins' own source and filter.
    expect(MARK.layout?.['icon-allow-overlap']).toBe(false)
    expect(MARK.layout?.['symbol-placement']).toBe('line-center')
    const built = builtLayers()
    const pins = built.find((l) => l.id === POI_LAYER_ID)
    const dots = built.find((l) => l.id === POI_DOT_LAYER_ID)
    expect(dots?.type).toBe('circle')
    expect(dots?.source).toBe(pins?.source)
    expect(dots?.filter).toEqual(pins?.filter)
    // And the far marks are placed first, so they win the pixels: MapLibre
    // places the top layer first, and every closure draws over the pins.
    const ids = built.map((l) => l.id)
    expect(ids.indexOf(closureMarkId(CLOSURE_LAYER_ID))).toBeGreaterThan(
      ids.indexOf(POI_LAYER_ID),
    )
  })

  it('does not data-drive colour off blaze_color - a closure is not a blaze', () => {
    expect(JSON.stringify(LAYERS)).not.toContain('blaze_color')
  })
})

describe('the cross image', () => {
  it('sizes the image to the ink plus its halo room, on whole pixels', () => {
    const reach = CLOSURE_CROSS_ARM + CLOSURE_CROSS_STROKE / 2
    expect(closureCrossImageSize()).toBe(Math.ceil(2 * (reach + CLOSURE_CROSS_PADDING)))
    expect(Number.isInteger(closureCrossImageSize())).toBe(true)
  })

  it('keeps the closure red for the marks still drawn in it', () => {
    // The ATC notice triangle (lib/atcUpdateStyle.ts) is drawn in it; the
    // crossed-out mark is not (the test above).
    expect(CLOSURE_COLOR).toBe('#b2321f')
  })
})
