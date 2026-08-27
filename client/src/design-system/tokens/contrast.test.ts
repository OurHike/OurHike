import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve as resolvePath } from 'node:path'

// Whether a label on a filled surface can actually be read (#1131).
//
// THE PAIRS ARE RESOLVED OUT OF colors.css, NOT WRITTEN DOWN HERE. A test
// holding its own copy of the hex proves that two literals in a test file
// agree with each other, which is not the claim worth making - and it goes
// stale silently the first time somebody re-points a token, which is exactly
// the event it exists to catch. What is written here is the PAIRING - which
// foreground lands on which background, under which theme - because that is a
// fact about the components, and the components are what this is about.
//
// WHY THIS EXISTS AT ALL. `Button.jsx` hardcoded `--paper-0` as the label for
// both filled variants and read the BASE token `--blaze-orange` for the
// secondary fill. Measured 2026-08-27, that was 4.14:1 under both themes for
// secondary and 3.42:1 under the dark theme for primary - and the same
// `--brand-secondary` carries `.wrong-way-cue__primary`, the primary action on
// the one alert HIKER_SAFETY.md lets this app send.
//
// It checks the two filled variants and nothing else. A full audit of every
// pair in the app is real work and is not this; a test that tried it would
// either be wrong about which pairs actually occur or would need every
// stylesheet parsed. These four are the ones a filled Button and the wrong-way
// cue genuinely produce.

// `process.cwd()` rather than `import.meta.url`, matching
// src/test/poiCardChipLayout.test.ts - the convention this repo already has
// for a test that reads a stylesheet rather than importing it.
const CSS = readFileSync(
  resolvePath(process.cwd(), 'src/design-system/tokens/colors.css'),
  'utf8',
)

/**
 * The value a token resolves to, following `var(--x)` aliases down to a hex.
 *
 * `theme` picks which block to read from: `:root` for light, and
 * `:root[data-theme='dark']` layered over it for dark - which is how the
 * cascade actually resolves it, and why a token the dark block does not
 * mention keeps its light value rather than having none.
 */
function resolve(token: string, theme: 'light' | 'dark'): string {
  const darkBlock = CSS.slice(CSS.indexOf("[data-theme='dark']"))
  const lightBlock = CSS.slice(0, CSS.indexOf("[data-theme='dark']"))

  const read = (name: string, block: string): string | null => {
    // The last declaration wins, matching the cascade.
    const found = [...block.matchAll(new RegExp(`^--${name}\\s*:\\s*([^;]+);`, 'gm'))]
    return found.length === 0 ? null : (found[found.length - 1]?.[1]?.trim() ?? null)
  }

  let value =
    (theme === 'dark' ? read(token, darkBlock) : null) ?? read(token, lightBlock)

  // Follow the alias chain. Bounded rather than `while (true)`: a token that
  // pointed at itself would otherwise hang the suite instead of failing it.
  for (let hop = 0; hop < 10 && value !== null; hop += 1) {
    const alias = /^var\(--([\w-]+)\)$/.exec(value)
    if (alias === null) break
    const next = alias[1]
    if (next === undefined) break
    value = (theme === 'dark' ? read(next, darkBlock) : null) ?? read(next, lightBlock)
  }

  if (value === null) throw new Error(`no such token: --${token}`)
  return value
}

function channels(hex: string): [number, number, number] {
  const clean = hex.replace('#', '')
  return [0, 2, 4].map((i) => parseInt(clean.slice(i, i + 2), 16) / 255) as [
    number,
    number,
    number,
  ]
}

/** WCAG relative luminance. */
function luminance(hex: string): number {
  const [r, g, b] = channels(hex).map((c) =>
    c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4,
  ) as [number, number, number]
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number]
  return (hi + 0.05) / (lo + 0.05)
}

/** `color-mix(in srgb, X p%, Y)` the way a browser computes it - in sRGB, not
 *  linear light. Only the shape colors.css actually uses. */
function flatten(value: string, theme: 'light' | 'dark'): string {
  const mix = /^color-mix\(in srgb,\s*var\(--([\w-]+)\)\s+(\d+)%,\s*var\(--([\w-]+)\)\)$/.exec(
    value,
  )
  if (mix === null) return value
  const [, front, percent, back] = mix as unknown as [string, string, string, string]
  const p = Number(percent) / 100
  const f = channels(resolve(front, theme))
  const b = channels(resolve(back, theme))
  return `#${[0, 1, 2]
    .map((i) =>
      Math.round((f[i] * p + b[i] * (1 - p)) * 255)
        .toString(16)
        .padStart(2, '0'),
    )
    .join('')}`
}

function pair(fg: string, bg: string, theme: 'light' | 'dark'): number {
  return contrast(
    flatten(resolve(fg, theme), theme),
    flatten(resolve(bg, theme), theme),
  )
}

// AA for normal text. The large-text exemption is 3.0 and deliberately not
// used here: `Button` at `size="s"` sets `--text-body-s`, which is 14px, and
// 18.66px bold is where that exemption starts.
const AA = 4.5

describe('a filled button’s label, against its own fill', () => {
  for (const theme of ['light', 'dark'] as const) {
    it(`carries the primary button under the ${theme} theme`, () => {
      // The dark side is what was broken: `--brand-primary` re-points to
      // moss-400 there, and a hardcoded `--paper-0` label sat on it at 3.42:1.
      expect(pair('fg-on-brand', 'brand-primary', theme)).toBeGreaterThanOrEqual(AA)
    })

    it(`carries the secondary button under the ${theme} theme`, () => {
      // And this is the one that also carries `.wrong-way-cue__primary`.
      expect(pair('fg-on-brand', 'brand-secondary', theme)).toBeGreaterThanOrEqual(AA)
    })

    it(`still carries both while they are hovered, under the ${theme} theme`, () => {
      // A hover state is still text on a fill. `--brand-secondary-hover` is a
      // color-mix rather than an alias, which is the reason `flatten` exists.
      expect(pair('fg-on-brand', 'brand-primary-hover', theme)).toBeGreaterThanOrEqual(AA)
      expect(pair('fg-on-brand', 'brand-secondary-hover', theme)).toBeGreaterThanOrEqual(
        AA,
      )
    })
  }

  it('would have failed on what shipped before #1131', () => {
    // The regression this guards, stated as the thing it caught rather than
    // left as a claim in a comment. `--paper-0` on the BASE `--blaze-orange`
    // is what Button.jsx painted, and a base token cannot follow a theme, so
    // it was the same number under both.
    for (const theme of ['light', 'dark'] as const) {
      expect(pair('paper-0', 'blaze-orange', theme)).toBeLessThan(AA)
    }
  })

  it('is still what Button actually paints', () => {
    // THE GAP THIS CLOSES. Everything above reasons about token PAIRS, and a
    // pair is only the right question while the component still reads those
    // tokens. Button.jsx's whole defect was that it did not - it hardcoded
    // `--paper-0` and reached for a base token - so a suite that checked only
    // colors.css would have gone green over the exact bug it exists to catch,
    // and would go green again the day somebody reverts the component.
    //
    // Read as text rather than rendered, because Button.jsx is untyped JS
    // styled through inline `style` (see design-system/README.md): there is no
    // stylesheet to query and jsdom resolves no custom properties, so a render
    // would assert on the literal string `var(--fg-on-brand)` anyway. This
    // says the same thing without mounting anything.
    const button = readFileSync(
      resolvePath(process.cwd(), 'src/design-system/components/core/Button.jsx'),
      'utf8',
    )
    const opens = button.indexOf('const variants')
    // From `const variants`, not from the file's first `};` - `sizes` is
    // declared above it and closes first.
    const filled = button.slice(opens, button.indexOf('};', opens))

    for (const variant of ['primary', 'secondary']) {
      const line = filled
        .split('\n')
        .find((row) => row.trimStart().startsWith(`${variant}:`))
      expect(line, `no ${variant} variant`).toBeDefined()
      // The label follows the theme...
      expect(line).toContain('var(--fg-on-brand)')
      // ...and neither fill reads a base palette entry, which cannot.
      expect(line).not.toContain('var(--paper-0)')
      expect(line).not.toContain('var(--blaze-orange)')
    }
  })

  it('leaves the decorative blaze hue alone', () => {
    // The split #1131 turns on: `--accent-blaze-orange` is the mark nothing
    // sits on - pins, dots, rails, the drought wash - so it keeps the brand
    // hue and is deliberately NOT held to a text ratio. If this ever starts
    // failing it means somebody put a label on it, and the fix is a different
    // token rather than a darker accent.
    expect(resolve('accent-blaze-orange', 'light')).toBe(resolve('blaze-orange', 'light'))
  })
})
