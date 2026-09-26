import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'
import { MapIcon, TrailLineSwatch } from './MapIcon'
import { blazePaintColor, NEUTRAL_BLAZE_COLOR, PLAIN_TRAIL_COLOR } from '../lib/blaze'
import { NEARBY_TRAIL_OPACITY } from './nearbyTrails'
import {
  CASING_OVERHANG,
  PRIMARY_TRAIL_WIDTH,
  RED_LIGHT_BLAZE_COLOR,
  SIDE_TRAIL_WIDTH,
  trailCasingColor,
  MAP_BACKDROP,
  mapBackdrop,
} from './style'
import {
  glyphPath,
  pinGeometry,
  poiGlyphPath,
  poiTier,
  waypointPinGeometry,
  waypointPinInks,
  POI_COLORS,
  POI_FALLBACK_COLOR,
  PIN_EDGE_COLOR,
  PIN_HALO_COLOR,
  UNKNOWN_POI_TYPE,
} from './poiIcons'
import { WARNING_GLYPH } from './warningPin'
import { WARNING_PIN } from '../lib/seriousWarnings'
import {
  CLOSURE_CASING_COLOR,
  CLOSURE_COLOR,
  CLOSURE_OUTLINE_WIDTH,
  CLOSURE_DASH,
  CLOSURE_TAPE_WIDTH,
} from '../lib/closureStyle'

// The map's pins, drawn in the DOM for the legend (#572).
//
// The whole value of this component is that it is not a second drawing of the
// pin, so what is tested is fidelity rather than appearance: every number in
// the SVG is checked against the geometry the rasteriser uses -
// waypointPinGeometry() for a waypoint since #1682, pinGeometry() for the
// warning's coin - the inks against waypointPinInks(), and the silhouettes
// against GLYPHS. A test that only asserted "renders a circle" would pass just
// as happily over a legend teaching a symbol the map does not use.

const PIN = pinGeometry(1)
const WAYPOINT = waypointPinGeometry(1, 1)

afterEach(cleanup)

function draw(node: React.ReactElement): SVGElement {
  const { container } = render(node)
  const svg = container.querySelector('svg')
  if (svg === null) throw new Error('no icon rendered')
  return svg
}

function part(svg: SVGElement, className: string): Element {
  const found = svg.querySelector(`.${className}`)
  if (found === null) throw new Error(`no .${className} in the icon`)
  return found
}

function num(element: Element, attribute: string): number {
  return Number(element.getAttribute(attribute))
}

describe('MapIcon: a waypoint pin', () => {
  it('takes its disc straight from the pin geometry, in a unit box', () => {
    // The unit is the DRAWN pin, not its 38 px footprint: a legend slot is a
    // key, and the footprint's margin would only shrink the pin in it.
    const svg = draw(<MapIcon type="water" />)

    expect(svg.getAttribute('viewBox')).toBe('0 0 1 1')
    expect(num(part(svg, 'map-icon__disc'), 'r')).toBeCloseTo(WAYPOINT.rDisc)
    expect(num(part(svg, 'map-icon__disc'), 'cx')).toBeCloseTo(WAYPOINT.center)
  })

  it('puts the paper hairline exactly where the rasteriser puts it', () => {
    // buildSlimPinImage inks paper between rDisc and rInk; a paper disc of
    // radius rInk under the coloured one is the same band, with no seam.
    const svg = draw(<MapIcon type="water" />)
    const halo = part(svg, 'map-icon__halo')

    expect(num(halo, 'r')).toBeCloseTo(WAYPOINT.rInk)
    expect(halo.getAttribute('fill')).toBe(PIN_HALO_COLOR)
  })

  it('draws the glyph in the box the rasteriser samples it in', () => {
    const svg = draw(<MapIcon type="shelter" />)
    const glyph = part(svg, 'map-icon__glyph')
    const numbers = (glyph.closest('g')?.getAttribute('transform') ?? '')
      .match(/-?\d+\.?\d*/g)
      ?.map(Number)

    expect(numbers).toHaveLength(3)
    const [tx, ty, scale] = numbers ?? []
    expect(scale).toBeCloseTo(WAYPOINT.glyphBox)
    expect(tx).toBeCloseTo(WAYPOINT.center - WAYPOINT.glyphBox / 2)
    expect(ty).toBeCloseTo(WAYPOINT.center - WAYPOINT.glyphBox / 2)
  })

  it('fills the glyph even-odd, which is what keeps the doorway open', () => {
    const svg = draw(<MapIcon type="shelter" />)

    expect(part(svg, 'map-icon__glyph').getAttribute('fill-rule')).toBe('evenodd')
  })

  it.each(Object.keys(POI_COLORS))('draws %s in its own map inks and shape', (type) => {
    const svg = draw(<MapIcon type={type} />)
    const inks = waypointPinInks(type, 'high')

    expect(part(svg, 'map-icon__disc').getAttribute('fill')).toBe(inks.fill)
    expect(part(svg, 'map-icon__glyph').getAttribute('fill')).toBe(inks.glyph)
    expect(part(svg, 'map-icon__glyph').getAttribute('d')).toBe(poiGlyphPath(type))
    // A loud pin is its accent; a quiet one a pale tint with the accent on it.
    const accent = POI_COLORS[type as keyof typeof POI_COLORS]
    if (poiTier(type) === 'loud') expect(inks.fill).toBe(accent)
    else expect(inks.glyph).toBe(accent)
  })

  it('falls back to the neutral diamond for a type this build never heard of', () => {
    // The map draws an unrecognised category as a neutral pin rather than as
    // nothing, so a release that adds one upstream looks unfamiliar here
    // instead of silently missing a row's icon.
    const svg = draw(<MapIcon type="hot_springs" />)

    expect(part(svg, 'map-icon__glyph').getAttribute('fill')).toBe(POI_FALLBACK_COLOR)
    expect(part(svg, 'map-icon__glyph').getAttribute('d')).toBe(
      poiGlyphPath(UNKNOWN_POI_TYPE),
    )
  })

  it('is decorative, because whatever carries it names the category in text', () => {
    const svg = draw(<MapIcon type="water" />)

    expect(svg.getAttribute('aria-hidden')).toBe('true')
    expect(svg.getAttribute('focusable')).toBe('false')
  })
})

describe('MapIcon: hollow says nobody has verified the waypoint (#1682)', () => {
  it('fills a verified loud pin with its accent and draws no ring', () => {
    const svg = draw(<MapIcon type="water" confidence="high" />)

    expect(part(svg, 'map-icon__disc').getAttribute('fill')).toBe(POI_COLORS.water)
    expect(svg.querySelector('.map-icon__ring')).toBeNull()
  })

  it('draws an unverified pin hollow: paper inside a solid accent ring', () => {
    const svg = draw(<MapIcon type="water" confidence="low" />)
    const ring = part(svg, 'map-icon__ring')

    expect(part(svg, 'map-icon__disc').getAttribute('fill')).toBe(PIN_HALO_COLOR)
    expect(ring.getAttribute('stroke')).toBe(POI_COLORS.water)
    expect(num(ring, 'stroke-width')).toBeCloseTo(WAYPOINT.hollowRing)
    expect(num(ring, 'r') + num(ring, 'stroke-width') / 2).toBeCloseTo(WAYPOINT.rDisc)
    // Never broken: the old rim's rhythm belongs to the coin now.
    expect(ring).not.toHaveAttribute('stroke-dasharray')
    expect(part(svg, 'map-icon__glyph').getAttribute('fill')).toBe(POI_COLORS.water)
  })
})

describe('MapIcon: a serious warning', () => {
  it('is the coin, from pinGeometry, in a unit box', () => {
    const svg = draw(<MapIcon type="serious-warning" />)

    expect(svg.getAttribute('viewBox')).toBe('0 0 1 1')
    expect(num(part(svg, 'map-icon__disc'), 'r')).toBeCloseTo(PIN.rDisc)
    const edge = part(svg, 'map-icon__edge')
    expect(num(edge, 'r')).toBeCloseTo(PIN.rOuter - PIN.edgeWidth / 2)
    expect(num(edge, 'stroke-width')).toBeCloseTo(PIN.edgeWidth)
    expect(edge.getAttribute('stroke')).toBe(PIN_EDGE_COLOR)
    const halo = part(svg, 'map-icon__halo')
    expect(num(halo, 'r') - num(halo, 'stroke-width') / 2).toBeLessThan(PIN.rDisc)
    expect(halo.getAttribute('stroke')).toBe(PIN_HALO_COLOR)
  })

  it('is the hollow hazard triangle, in the warning pin’s own red', () => {
    const svg = draw(<MapIcon type="serious-warning" />)

    expect(part(svg, 'map-icon__disc').getAttribute('fill')).toBe(WARNING_PIN.color)
    expect(part(svg, 'map-icon__glyph').getAttribute('d')).toBe(glyphPath(WARNING_GLYPH))
  })

  it('keeps a solid rim even when asked for an unverified one', () => {
    // `serious` is set by a moderator and never self-declared, so a warning
    // that reaches this pin has been looked at by a person. A broken rim means
    // "nobody has verified this", which is the opposite of the one thing that
    // is certainly true about it.
    const svg = draw(<MapIcon type="serious-warning" confidence="low" />)

    expect(part(svg, 'map-icon__edge')).not.toHaveAttribute('stroke-dasharray')
  })
})

describe('MapIcon: a closure', () => {
  it('is the barrier tape the map draws, not a pin', () => {
    const svg = draw(<MapIcon type="closure" />)

    expect(part(svg, 'map-icon__closure-band').getAttribute('fill')).toBe(CLOSURE_COLOR)
    expect(part(svg, 'map-icon__closure-outline').getAttribute('fill')).toBe(
      CLOSURE_CASING_COLOR,
    )
    expect(svg.querySelector('.map-icon__disc')).toBeNull()
  })

  it('draws the ticks at the map’s own rhythm, in the map’s own units', () => {
    // The swatch's viewBox is in CSS pixels at the band's width, so every
    // number here resolves from a constant the map ships - no conversion, and
    // nothing for the legend to drift from the map by. The map writes its
    // rhythm in LINE WIDTHS (a `line-dasharray`), so a tick is that fraction
    // of the band's width.
    const svg = draw(<MapIcon type="closure" />)
    const ticks = svg.querySelectorAll('.map-icon__closure-band')

    expect(ticks.length).toBeGreaterThan(1)
    expect(Number(ticks[0]?.getAttribute('width'))).toBeCloseTo(
      CLOSURE_DASH.tick * CLOSURE_TAPE_WIDTH,
      6,
    )
  })

  it('stands its ticks square to the band, as the map does since #1599', () => {
    // The legend taught a 55-degree lean while the map drew one; the map
    // stopped, because that lean was what tore at every bend. A swatch that
    // kept it would be teaching a mark the map does not draw, which is this
    // file's whole rule.
    const svg = draw(<MapIcon type="closure" />)

    expect(svg.querySelectorAll('line')).toHaveLength(0)
    for (const tick of svg.querySelectorAll('.map-icon__closure-band')) {
      expect(Number(tick.getAttribute('height'))).toBe(CLOSURE_TAPE_WIDTH)
    }
  })

  it('edges the band rather than laying a casing behind it', () => {
    // THE DEFECT THIS SWATCH USED TO SHOW, held so it cannot come back. The
    // legend drew a filled casing rect with a dashed band over it - which was
    // honest, because that is what the map drew, and both were a near-black
    // line with red ticks in it. The casing is a stroke wider than the stripe
    // it outlines, and no rect behind them is the casing: the ground rect is
    // the sheet's paper (#1575), and the two dark rects since #1598 are the
    // band's own outline, each one CLOSURE_OUTLINE_WIDTH tall at an edge of
    // the tape rather than the full height behind it.
    const svg = draw(<MapIcon type="closure" />)
    const rects = [...svg.querySelectorAll('rect')]

    expect(rects.map((r) => r.getAttribute('class'))).toEqual([
      'map-icon__closure-ground',
      ...rects.slice(1, -2).map(() => 'map-icon__closure-band'),
      'map-icon__closure-outline',
      'map-icon__closure-outline',
    ])
    expect(rects[0]?.getAttribute('fill')).not.toBe(CLOSURE_CASING_COLOR)
    for (const outline of rects.slice(-2)) {
      expect(outline.getAttribute('fill')).toBe(CLOSURE_CASING_COLOR)
      expect(Number(outline.getAttribute('height'))).toBe(CLOSURE_OUTLINE_WIDTH)
      // An EDGE and not a band: whatever the band's own height, an outline
      // that ever grew to a share of it would be the filled casing rect
      // back under a new name.
      expect(Number(outline.getAttribute('height'))).toBeLessThan(CLOSURE_TAPE_WIDTH / 4)
    }
  })

  it('lays the sheet’s paper under the ticks, in the map’s own colour (#1575)', () => {
    // What the map does, restated in the legend: since option E the tape's
    // gaps hold the sheet's paper, so the swatch holds it too - the field day
    // sheet's by default, and night ink beside a night map. Nothing else in
    // the swatch carries a fill; the stripes are strokes.
    const day = draw(<MapIcon type="closure" />)
    expect(part(day, 'map-icon__closure-ground').getAttribute('fill')).toBe(
      mapBackdrop({ theme: 'light' }),
    )
    // Every other fill in the swatch is the closure red or the sheet's
    // darkest ink - the ticks and the two edges - and nothing carries a
    // stroke at all, which is the swatch's half of "no diagonals left".
    for (const node of day.querySelectorAll('*:not(.map-icon__closure-ground)')) {
      expect(node.getAttribute('stroke')).toBeNull()
    }

    // Beside a night map the ground is the day paper too, since 2026-09-18
    // (closureTapeGround): red and white, never red on ink. Red light keeps
    // its ink, and the swatch follows.
    const night = draw(<MapIcon type="closure" appearance={{ theme: 'dark' }} />)
    expect(part(night, 'map-icon__closure-ground').getAttribute('fill')).toBe(
      MAP_BACKDROP.light,
    )
    const redLight = { mapStyle: 'night_hike', redLight: true } as const
    const under = draw(<MapIcon type="closure" appearance={redLight} />)
    expect(part(under, 'map-icon__closure-ground').getAttribute('fill')).toBe(
      mapBackdrop(redLight),
    )
  })
})

describe('TrailLineSwatch: a trail line as the map draws it (#1283)', () => {
  // Same rule as the pins above: fidelity, not appearance. Every number is
  // checked against the constants the map's own layers are built from.

  function swatch(props: Partial<Parameters<typeof TrailLineSwatch>[0]> = {}) {
    return draw(
      <TrailLineSwatch
        blazeColor="Blue"
        throughRoute={false}
        chosen={false}
        {...props}
      />,
    )
  }

  it('draws a side trail at the side-trail width over a casing one overhang wider', () => {
    const svg = swatch({ chosen: true })
    expect(num(part(svg, 'map-icon__trail-blaze'), 'stroke-width')).toBe(SIDE_TRAIL_WIDTH)
    expect(num(part(svg, 'map-icon__trail-casing'), 'stroke-width')).toBe(
      SIDE_TRAIL_WIDTH + CASING_OVERHANG * 2,
    )
    expect(part(svg, 'map-icon__trail-blaze').getAttribute('stroke')).toBe(
      blazePaintColor('Blue'),
    )
    expect(part(svg, 'map-icon__trail-casing').getAttribute('stroke')).toBe(
      trailCasingColor({ theme: 'light' }),
    )
  })

  it('draws a through-route at the through-route width', () => {
    const svg = swatch({ throughRoute: true, chosen: true })
    expect(num(part(svg, 'map-icon__trail-blaze'), 'stroke-width')).toBe(
      PRIMARY_TRAIL_WIDTH,
    )
  })

  it('draws every line solid, in and out of the chosen system, as the map does', () => {
    // Solid against dotted until 2026-09-10 (map/style.ts's header, rule
    // 2): the swatch follows the canvas, and the canvas has no dots.
    for (const chosen of [true, false]) {
      const line = swatch({ chosen })
      for (const cls of ['map-icon__trail-blaze', 'map-icon__trail-casing']) {
        expect(part(line, cls).getAttribute('stroke-dasharray'), cls).toBeNull()
      }
    }
  })

  it('ghosts a line outside the chosen system by the map’s own opacity', () => {
    const ghosted = swatch({ chosen: false })
    expect(num(part(ghosted, 'map-icon__trail-blaze'), 'stroke-opacity')).toBe(
      NEARBY_TRAIL_OPACITY,
    )
    expect(
      num(
        swatch({ chosen: true }).querySelector('.map-icon__trail-blaze')!,
        'stroke-opacity',
      ),
    ).toBe(1)
  })

  it('keeps a White blaze white with its casing on every sheet, taken or not', () => {
    // The dark ink was the dotted line's rule (#1306) and the dots are gone
    // (2026-09-10): a legend row is always a cased line, and on the canvas
    // every cased line keeps its white blaze - the swatch saying what the
    // canvas beside it is drawing. The uncased sketches, which do ink dark
    // on a day sheet, have no row here.
    for (const chosen of [false, true]) {
      const day = swatch({ blazeColor: 'White', throughRoute: true, chosen })
      expect(day.querySelector('.map-icon__trail-casing')).not.toBeNull()
      expect(part(day, 'map-icon__trail-casing').getAttribute('stroke')).toBe(
        trailCasingColor({ theme: 'light' }),
      )
      expect(part(day, 'map-icon__trail-blaze').getAttribute('stroke')).toBe(
        blazePaintColor('White'),
      )
    }

    const night = swatch({
      blazeColor: 'White',
      throughRoute: true,
      chosen: false,
      appearance: { theme: 'dark' },
    })
    expect(night.querySelector('.map-icon__trail-casing')).not.toBeNull()
    expect(part(night, 'map-icon__trail-blaze').getAttribute('stroke')).toBe(
      blazePaintColor('White'),
    )
  })

  it('takes red light’s one hue, like the line', () => {
    const svg = swatch({ appearance: { mapStyle: 'night_hike', redLight: true } })
    expect(part(svg, 'map-icon__trail-blaze').getAttribute('stroke')).toBe(
      RED_LIGHT_BLAZE_COLOR,
    )
  })

  it('keeps the blaze hue while the appearance has blaze colours off (#1575)', () => {
    // The one place the swatch and the line disagree on purpose: the map
    // draws every line PLAIN_TRAIL_COLOR with the switch off, and the row's
    // swatch stays the blaze - "Changing the color option should only
    // affect the map itself, not the other options" (the maintainer,
    // 2026-09-17) - so the legend is where a named trail's blaze is read
    // while the map is red.
    const svg = swatch({ appearance: { theme: 'light', blazeColorsShown: false } })
    expect(part(svg, 'map-icon__trail-blaze').getAttribute('stroke')).toBe(
      blazePaintColor('Blue'),
    )
    expect(part(svg, 'map-icon__trail-blaze').getAttribute('stroke')).not.toBe(
      PLAIN_TRAIL_COLOR,
    )
  })

  it('falls back to the neutral grey for a line with no blaze', () => {
    const svg = swatch({ blazeColor: null })
    expect(part(svg, 'map-icon__trail-blaze').getAttribute('stroke')).toBe(
      NEUTRAL_BLAZE_COLOR,
    )
  })
})
