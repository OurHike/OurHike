import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'
import { MapIcon, TrailLineSwatch } from './MapIcon'
import { blazePaintColor, NEUTRAL_BLAZE_COLOR } from '../lib/blaze'
import { NEARBY_TRAIL_DASHARRAY, NEARBY_TRAIL_OPACITY } from './nearbyTrails'
import {
  CASING_OVERHANG,
  PRIMARY_TRAIL_WIDTH,
  RED_LIGHT_BLAZE_COLOR,
  SIDE_TRAIL_WIDTH,
  trailCasingColor,
} from './style'
import {
  glyphPath,
  pinGeometry,
  poiGlyphPath,
  POI_COLORS,
  POI_FALLBACK_COLOR,
  PIN_EDGE_COLOR,
  PIN_HALO_COLOR,
  RIM_DASHES,
  UNKNOWN_POI_TYPE,
} from './poiIcons'
import { WARNING_GLYPH } from './warningPin'
import { WARNING_PIN } from '../lib/seriousWarnings'
import {
  CLOSURE_CASING_COLOR,
  CLOSURE_COLOR,
  CLOSURE_STRIPE_EDGE,
  CLOSURE_TAPE_CADENCE,
} from '../lib/closureStyle'

// The map's pins, drawn in the DOM for the legend (#572).
//
// The whole value of this component is that it is not a second drawing of the
// pin, so what is tested is fidelity rather than appearance: every number in
// the SVG is checked against pinGeometry(), the colours against POI_COLORS,
// the silhouettes against GLYPHS, and the broken rim against RIM_DASHES. A
// test that only asserted "renders a circle" would pass just as happily over
// a legend teaching a symbol the map does not use.

const PIN = pinGeometry(1)

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
    const svg = draw(<MapIcon type="water" />)

    expect(svg.getAttribute('viewBox')).toBe('0 0 1 1')
    expect(num(part(svg, 'map-icon__disc'), 'r')).toBeCloseTo(PIN.rDisc)
    expect(num(part(svg, 'map-icon__disc'), 'cx')).toBeCloseTo(PIN.center)
  })

  it('puts the dark hairline exactly where the rasteriser puts it', () => {
    // buildPinImage inks the outermost `edgeWidth` of the rim dark, so a
    // stroke of that width centred half of it inside rOuter is the same band.
    const svg = draw(<MapIcon type="water" />)
    const edge = part(svg, 'map-icon__edge')

    expect(num(edge, 'r')).toBeCloseTo(PIN.rOuter - PIN.edgeWidth / 2)
    expect(num(edge, 'stroke-width')).toBeCloseTo(PIN.edgeWidth)
    expect(edge.getAttribute('stroke')).toBe(PIN_EDGE_COLOR)
  })

  it('overlaps the halo under both its neighbours, so no seam can show', () => {
    // The rasteriser picks one colour per pixel and its bands simply abut.
    // SVG antialiases each shape against what is behind it, so two shapes that
    // merely touch leave a hairline of page between them. Asserted as bounds
    // rather than as exact numbers - how much bleed is a tuning question, that
    // there is some is not.
    const svg = draw(<MapIcon type="water" />)
    const halo = part(svg, 'map-icon__halo')
    const inner = num(halo, 'r') - num(halo, 'stroke-width') / 2
    const outer = num(halo, 'r') + num(halo, 'stroke-width') / 2

    expect(inner).toBeLessThan(PIN.rDisc)
    expect(outer).toBeGreaterThanOrEqual(PIN.rOuter - PIN.edgeWidth)
    expect(halo.getAttribute('stroke')).toBe(PIN_HALO_COLOR)
  })

  it('draws the glyph in the box the rasteriser samples it in', () => {
    // Which is what keeps a glyph's corners off the halo: glyphBox is derived
    // from rDisc so its half-diagonal stays inside the disc.
    const svg = draw(<MapIcon type="shelter" />)
    const glyph = part(svg, 'map-icon__glyph')
    const numbers = (glyph.closest('g')?.getAttribute('transform') ?? '')
      .match(/-?\d+\.?\d*/g)
      ?.map(Number)

    expect(numbers).toHaveLength(3)
    const [tx, ty, scale] = numbers ?? []
    expect(scale).toBeCloseTo(PIN.glyphBox)
    expect(tx).toBeCloseTo(PIN.center - PIN.glyphBox / 2)
    expect(ty).toBeCloseTo(PIN.center - PIN.glyphBox / 2)
  })

  it('fills the glyph even-odd, which is what keeps the doorway open', () => {
    const svg = draw(<MapIcon type="shelter" />)

    expect(part(svg, 'map-icon__glyph').getAttribute('fill-rule')).toBe('evenodd')
  })

  it.each(Object.keys(POI_COLORS))('draws %s in its own map colour and shape', (type) => {
    const svg = draw(<MapIcon type={type} />)

    expect(part(svg, 'map-icon__disc').getAttribute('fill')).toBe(
      POI_COLORS[type as keyof typeof POI_COLORS],
    )
    expect(part(svg, 'map-icon__glyph').getAttribute('d')).toBe(poiGlyphPath(type))
  })

  it('falls back to the neutral diamond for a type this build never heard of', () => {
    // The map draws an unrecognised category as a neutral pin rather than as
    // nothing, so a release that adds one upstream looks unfamiliar here
    // instead of silently missing a row's icon.
    const svg = draw(<MapIcon type="hot_springs" />)

    expect(part(svg, 'map-icon__disc').getAttribute('fill')).toBe(POI_FALLBACK_COLOR)
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

describe('MapIcon: the rim says whether anyone has verified the waypoint', () => {
  it('leaves a verified rim solid, with no dash pattern at all', () => {
    // Absent rather than a solid-looking pattern, so "unbroken" is visible in
    // the DOM instead of being a number someone has to evaluate.
    const svg = draw(<MapIcon type="water" confidence="high" />)

    expect(part(svg, 'map-icon__edge')).not.toHaveAttribute('stroke-dasharray')
    expect(part(svg, 'map-icon__halo')).not.toHaveAttribute('stroke-dasharray')
  })

  it.each(['map-icon__edge', 'map-icon__halo'])(
    'breaks %s into the rasteriser’s own rhythm when nobody has verified it',
    (className) => {
      // buildPinImage inks the rim where floor(turns * RIM_DASHES * 2) is
      // even: sixteen equal arcs, alternating, around the full turn. Checked
      // against this ring's own circumference rather than against a literal,
      // which is what makes it the same rhythm and not a similar one.
      const svg = draw(<MapIcon type="water" confidence="low" />)
      const ring = part(svg, className)
      const [dash, gap] = (ring.getAttribute('stroke-dasharray') ?? '')
        .split(' ')
        .map(Number)

      expect(dash).toBeCloseTo(gap)
      expect(dash * RIM_DASHES * 2).toBeCloseTo(2 * Math.PI * num(ring, 'r'))
    },
  )
})

describe('MapIcon: a serious warning', () => {
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

    expect(part(svg, 'map-icon__closure-band').getAttribute('stroke')).toBe(CLOSURE_COLOR)
    expect(part(svg, 'map-icon__closure-casing').getAttribute('stroke')).toBe(
      CLOSURE_CASING_COLOR,
    )
    expect(svg.querySelector('.map-icon__disc')).toBeNull()
  })

  it('draws the stripes at the map’s own cadence, in the map’s own units', () => {
    // The swatch's viewBox is in CSS pixels at the tape's width, so every
    // number here is the number map/closureTape.ts rasterises - no conversion,
    // and nothing for the legend to drift from the map by.
    const svg = draw(<MapIcon type="closure" />)
    const band = svg.querySelectorAll('.map-icon__closure-band')

    expect(band.length).toBeGreaterThan(1)
    expect(band[0]?.getAttribute('stroke-width')).toBe(
      String(CLOSURE_TAPE_CADENCE.stripe),
    )
  })

  it('edges each stripe rather than laying a casing behind them all', () => {
    // THE DEFECT THIS SWATCH USED TO SHOW, held so it cannot come back. The
    // legend drew a filled casing rect with a dashed band over it - which was
    // honest, because that is what the map drew, and both were a near-black
    // line with red ticks in it. There is no rect now, and the casing is a
    // stroke wider than the stripe it outlines.
    const svg = draw(<MapIcon type="closure" />)
    const edge = Number(
      part(svg, 'map-icon__closure-casing').getAttribute('stroke-width'),
    )

    expect(svg.querySelector('rect')).toBeNull()
    expect(edge).toBe(CLOSURE_TAPE_CADENCE.stripe + CLOSURE_STRIPE_EDGE * 2)
  })

  it('leaves the ground between the stripes alone', () => {
    // What the map does, restated in the legend: the tape's gaps are
    // transparent, so nothing here may paint them either. A fill anywhere in
    // this swatch would be a legend claiming the map hides the trail.
    const svg = draw(<MapIcon type="closure" />)

    for (const node of svg.querySelectorAll('*')) {
      expect(node.getAttribute('fill')).toBeNull()
    }
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

  it('draws the chosen system solid and everything else as the map’s dot rhythm', () => {
    const solid = swatch({ chosen: true })
    expect(
      part(solid, 'map-icon__trail-blaze').getAttribute('stroke-dasharray'),
    ).toBeNull()
    expect(solid.getAttribute('data-drawn')).toBe('solid')

    const dotted = swatch({ chosen: false })
    // Zero-length dashes, NEARBY_TRAIL_DASHARRAY[1] line widths apart - and
    // the casing at the same absolute pitch, so its dots sit under the
    // blaze's.
    const pitch = `0 ${NEARBY_TRAIL_DASHARRAY[1] * SIDE_TRAIL_WIDTH}`
    expect(part(dotted, 'map-icon__trail-blaze').getAttribute('stroke-dasharray')).toBe(
      pitch,
    )
    expect(part(dotted, 'map-icon__trail-casing').getAttribute('stroke-dasharray')).toBe(
      pitch,
    )
    expect(dotted.getAttribute('data-drawn')).toBe('dotted')
  })

  it('ghosts a line outside the chosen system by the map’s own opacity', () => {
    const dotted = swatch({ chosen: false })
    expect(num(part(dotted, 'map-icon__trail-blaze'), 'stroke-opacity')).toBe(
      NEARBY_TRAIL_OPACITY,
    )
    expect(
      num(
        swatch({ chosen: true }).querySelector('.map-icon__trail-blaze')!,
        'stroke-opacity',
      ),
    ).toBe(1)
  })

  it('inks a DOTTED White blaze in the casing colour with no casing on a day sheet, and keeps both on a dark one', () => {
    // `chosen: false` since #1306: the dark ink is the dotted line's rule,
    // and the swatch follows the map's own DARK_INKED_BLAZE_LAYER_IDS.
    const day = swatch({ blazeColor: 'White', throughRoute: true, chosen: false })
    expect(day.querySelector('.map-icon__trail-casing')).toBeNull()
    expect(part(day, 'map-icon__trail-blaze').getAttribute('stroke')).toBe(
      trailCasingColor({ theme: 'light' }),
    )

    // Taken, on the same day sheet, it is the white blaze with its casing -
    // the swatch saying what the canvas beside it is drawing.
    const taken = swatch({ blazeColor: 'White', throughRoute: true, chosen: true })
    expect(taken.querySelector('.map-icon__trail-casing')).not.toBeNull()
    expect(part(taken, 'map-icon__trail-blaze').getAttribute('stroke')).toBe(
      blazePaintColor('White'),
    )

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

  it('falls back to the neutral grey for a line with no blaze', () => {
    const svg = swatch({ blazeColor: null })
    expect(part(svg, 'map-icon__trail-blaze').getAttribute('stroke')).toBe(
      NEUTRAL_BLAZE_COLOR,
    )
  })
})
