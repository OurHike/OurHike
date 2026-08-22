import { describe, it, expect } from 'vitest'

import { BLAZE_PALETTE_MEMBERS, NEUTRAL_BLAZE_COLOR, blazePaintColor } from './blaze'

// The palette's admission rules, enforced rather than described (#782).
//
// features/NEARBY_TRAILS.md §4 asks for a palette that "grows by pull-request
// review, never by data arrival", and names what an admission must clear. A
// rule written only in a comment is a rule the next admission reads after
// picking its hex — so the three bars are computed here, against the palette
// itself, and a member that fails one fails CI.
//
// WHY THE BARS ARE THE PALETTE'S OWN NUMBERS AND NOT A STANDARD
//
// There is no WCAG figure for "two trail lines a hiker can tell apart at a
// junction" — the standard is about text on a background, and this is one
// stroke of paint beside another. Inventing a threshold would be a number
// with nothing behind it. What CAN be justified is a no-regression bar: a new
// hue must be at least as separable as the closest pair a hiker already reads
// on this map, and at least as readable on each sheet as the dimmest hue
// already shipping there. Those are facts about the palette, so they move
// only when the palette does — and if a future admission lowers one, this
// test says so in the same breath.
//
// `@unvalidated` on all of it, and the tag belongs to the whole file rather
// than one constant: arithmetic is not legibility. **#105 — Outdoor usability
// pass** is what would settle whether these hues survive sunlight and a
// gloved hand, and no number here is evidence about that.

const DAY_SHEET = '#ffffff' // map/style.ts MAP_BACKGROUND_COLOR — the field sheet's paper
const NIGHT_SHEET = '#0c1410' // map/style.ts MAP_BACKDROP.dark — night_hike's ink

function channels(hex: string): [number, number, number] {
  const value = hex.replace('#', '')
  return [0, 2, 4].map((at) => parseInt(value.slice(at, at + 2), 16)) as [
    number,
    number,
    number,
  ]
}

function linear(channel: number): number {
  const unit = channel / 255
  return unit <= 0.04045 ? unit / 12.92 : ((unit + 0.055) / 1.055) ** 2.4
}

/** WCAG 2.x relative luminance. */
function luminance(hex: string): number {
  const [r, g, b] = channels(hex).map(linear)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

/** WCAG 2.x contrast ratio, 1–21. */
export function contrastRatio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

/** CIE L*a*b*, D65. */
function lab(hex: string): [number, number, number] {
  const [r, g, b] = channels(hex).map(linear)
  const x = (r * 0.4124564 + g * 0.3575761 + b * 0.1804375) / 0.95047
  const y = r * 0.2126729 + g * 0.7151522 + b * 0.072175
  const z = (r * 0.0193339 + g * 0.119192 + b * 0.9503041) / 1.08883
  const f = (t: number) =>
    t > (6 / 29) ** 3 ? Math.cbrt(t) : t / (3 * (6 / 29) ** 2) + 4 / 29
  const [fx, fy, fz] = [f(x), f(y), f(z)]
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)]
}

/** CIE76 ΔE — coarse, and enough for "are these two obviously different paints". */
export function deltaE(a: string, b: string): number {
  const [l1, a1, b1] = lab(a)
  const [l2, a2, b2] = lab(b)
  return Math.hypot(l1 - l2, a1 - a2, b1 - b2)
}

/** Every hue in the palette plus the neutral, which a line can also be. */
const DRAWN = [
  ...BLAZE_PALETTE_MEMBERS.map((name) => [name, blazePaintColor(name)] as const),
  ['Neutral', NEUTRAL_BLAZE_COLOR] as const,
]

function closestNeighbour(name: string): { other: string; distance: number } {
  const hex = DRAWN.find(([member]) => member === name)![1]
  return DRAWN.filter(([member]) => member !== name)
    .map(([other, otherHex]) => ({ other, distance: deltaE(hex, otherHex) }))
    .sort((a, b) => a.distance - b.distance)[0]
}

describe('the colour maths, checked against known values first', () => {
  it('computes the contrast ratio the way WCAG does', () => {
    // A guard on the guard. Every bar below is this function's output, so a
    // wrong implementation would enforce nothing while looking rigorous.
    expect(contrastRatio('#ffffff', '#000000')).toBeCloseTo(21, 5)
    expect(contrastRatio('#ffffff', '#ffffff')).toBeCloseTo(1, 5)
  })

  it('computes zero distance between a colour and itself', () => {
    expect(deltaE('#1f5fa8', '#1f5fa8')).toBeCloseTo(0, 5)
  })
})

describe('every admitted hue clears the palette’s own bars', () => {
  // Each bar is the exact figure of the palette member that sets it, not a
  // rounded one. Rounding UP was the first attempt and failed three tests
  // immediately: the pair a bar is derived from sits exactly on it, so
  // 24.2 excluded the Blue/Purple pair that defines 24.178. A bar written
  // to more precision than the thing it describes is a bar that fails its
  // own evidence.
  //
  // Blue/Purple, the closest pair shipping before Aqua was admitted
  // (measured 2026-08-22). A new hue at least this separable is not a
  // regression; a tighter one is, and this is where that gets caught.
  const SEPARATION_BAR = 24.178
  // Yellow's day contrast and Purple's night contrast, the dimmest shipping
  // on each sheet. White is exempt below, with a reason.
  const DAY_BAR = 2.076
  const NIGHT_BAR = 2.66

  // The AT's centerline, and the one member that cannot clear the day bar:
  // white paint on white paper is 1.02. It stays because the trail really is
  // white-blazed and because width and casing carry it (WIREFRAMES.md §3) —
  // exempted by name rather than by lowering the bar for everyone.
  const WASHES_OUT_ON_PAPER = new Set(['White'])

  for (const name of BLAZE_PALETTE_MEMBERS) {
    it(`${name} stays separable from its nearest neighbour`, () => {
      const { other, distance } = closestNeighbour(name)
      expect(
        distance,
        `${name} is ΔE ${distance.toFixed(1)} from ${other}, under the ${SEPARATION_BAR} bar`,
      ).toBeGreaterThanOrEqual(SEPARATION_BAR)
    })

    it(`${name} is readable on both sheets`, () => {
      const hex = blazePaintColor(name)
      if (!WASHES_OUT_ON_PAPER.has(name)) {
        expect(contrastRatio(hex, DAY_SHEET)).toBeGreaterThanOrEqual(DAY_BAR)
      }
      expect(contrastRatio(hex, NIGHT_SHEET)).toBeGreaterThanOrEqual(NIGHT_BAR)
    })
  }
})

describe('Aqua, the first admission under the rule (#782)', () => {
  it('is in the palette, because the Long Path wears it', () => {
    // 107 Aqua + 28 Teal rows on OPRHP's own Long Path segments, agreeing
    // with NYNJTC's separate layer (#771, measured 2026-08-18). Criterion
    // (a): a real trail wearing it.
    expect(BLAZE_PALETTE_MEMBERS).toContain('Aqua')
    expect(blazePaintColor('Aqua')).toBe('#0d8f96')
  })

  it('is not confusable with Blue or Green, which is the pair that would matter', () => {
    // The failure this guards is a hiker at a junction reading an aqua line
    // as the blue-blazed trail they meant to take.
    expect(deltaE('#0d8f96', blazePaintColor('Blue'))).toBeGreaterThan(40)
    expect(deltaE('#0d8f96', blazePaintColor('Green'))).toBeGreaterThan(30)
  })

  it('reads on the day sheet better than the candidate it beat', () => {
    // #00a0a8 separates slightly better and reads worse where it matters
    // more. Pinned so the trade is visible rather than remembered.
    expect(contrastRatio('#0d8f96', DAY_SHEET)).toBeGreaterThan(
      contrastRatio('#00a0a8', DAY_SHEET),
    )
  })
})

describe('the closed palette', () => {
  it('answers for exactly the members it admits, and nothing else', () => {
    // "Closed" has to mean something testable. A hue arriving from data
    // rather than from review renders neutral grey — never an invented paint.
    expect(blazePaintColor('Pink')).toBe(NEUTRAL_BLAZE_COLOR)
    expect(blazePaintColor('Lime')).toBe(NEUTRAL_BLAZE_COLOR)
    expect(blazePaintColor('Brown')).toBe(NEUTRAL_BLAZE_COLOR)
  })
})
