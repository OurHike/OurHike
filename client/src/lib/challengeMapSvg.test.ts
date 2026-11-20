// The challenge map's drawing (#1965), on the brief's three uses: the Where
// view, the Where sheet's "where it lands", and the welcome map.
//
// GOLDEN AS A HASH, NOT AN IMAGE. The brief asks for a golden-image test on
// three fixtures; CLAUDE.md forbids committing a picture. So each fixture's
// drawing is pinned by the SHA-256 of its SVG text, beside assertions that
// say in words what the drawing must hold. A hash that moves means the
// picture moved: render the fixture (`drawChallengeMap(fixtureMap(), ...)`
// into an .svg file) and look before updating it.

import { createHash } from 'node:crypto'
import { describe, expect, it } from 'vitest'
import { conicConformal, drawChallengeMap, type DrawOptions } from './challengeMapSvg'
import { fixtureMap } from './challengeMap.fixtures'

const sha = (text: string) => createHash('sha256').update(text).digest('hex').slice(0, 16)
const count = (svg: string, needle: string) => svg.split(needle).length - 1

const PHONE: DrawOptions = {
  width: 358,
  height: 400,
  units: 'imperial',
  title: 'The trail with your trail karma',
  pins: [
    { mile: 0, earned: true },
    { mile: 714.9, earned: true },
    { mile: 715.2, earned: true },
    { mile: 1026.5, earned: false },
    { mile: 2197.9, earned: false },
  ],
  walked: [{ startMile: 700, endMile: 725 }],
}

describe('the conic conformal projection (#1965)', () => {
  it('puts the central meridian at x = 0, mirrors either side of it, and runs north up the page', () => {
    expect(conicConformal([-76.5, 40])[0]).toBeCloseTo(0, 12)
    const [west] = conicConformal([-80, 40])
    const [east] = conicConformal([-73, 40])
    expect(west).toBeCloseTo(-east, 12)
    expect(conicConformal([-76.5, 45])[1]).toBeLessThan(conicConformal([-76.5, 35])[1])
  })
})

describe('drawing the challenge map (#1965)', () => {
  it('the Where view: earned pins gold and clustered, the rest hollow, the walked stretch yellow, the credits from the file', () => {
    const svg = drawChallengeMap(fixtureMap(), PHONE)
    expect(count(svg, 'fill="#d69a2d" stroke=')).toBe(2)
    expect(svg).toContain('>2</text>')
    expect(count(svg, 'fill="#fffdf7" stroke="#be8a2b"')).toBe(2)
    expect(svg).toContain('stroke="#d69a2d" stroke-width="4.2"')
    expect(svg).toContain(
      'Appalachian Trail Conservancy · U.S. Census Bureau · Natural Earth',
    )
    expect(svg).toContain('role="img" aria-label="The trail with your trail karma"')
    expect(sha(svg)).toBe('fc66be49d244ab5c')
  })

  it('the Where sheet: the chosen place ringed in orange, with its label escaped', () => {
    const svg = drawChallengeMap(fixtureMap(), {
      ...PHONE,
      height: 360,
      pins: [{ mile: 714.9, earned: false }],
      walked: [],
      chosen: 714.9,
      labels: [{ mile: 714.9, text: 'McAfee Knob & <Summit>', dx: 30, dy: -6 }],
    })
    expect(count(svg, 'stroke="#c1611a"')).toBe(2)
    expect(svg).toContain('McAfee Knob &#38; &#60;Summit&#62;')
    expect(svg).not.toContain('<Summit>')
    expect(sha(svg)).toBe('e58093430428182a')
  })

  it('the welcome map: every place hollow, the termini with their miles, the scale bar in kilometres for a metric hiker', () => {
    const svg = drawChallengeMap(fixtureMap(), {
      ...PHONE,
      height: 330,
      units: 'metric',
      pins: PHONE.pins!.map((pin) => ({ ...pin, earned: false })),
      walked: [],
      terminiMiles: true,
    })
    expect(count(svg, 'fill="#d69a2d" stroke=')).toBe(0)
    expect(svg).toContain('Springer Mtn · mi 0')
    expect(svg).toContain('Katahdin · mi 2,198')
    expect(svg).toContain('>300 km</text>')
    expect(svg).not.toContain('200 mi')
    expect(sha(svg)).toBe('a221b61ef60a9a5e')
  })

  it('writes a trail mile as a position on the axis and a distance in the hiker’s units', () => {
    const svg = drawChallengeMap(fixtureMap(), PHONE)
    expect(svg).toContain('>mi 1,000</text>')
    expect(svg).toContain('>200 mi</text>')
  })
})
