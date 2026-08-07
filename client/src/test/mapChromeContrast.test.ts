import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { MAP_BACKDROP } from '../map/style'

// Everything the app draws OVER the WebGL canvas, checked against the canvas it
// is drawn over.
//
// This is a different question from themeTokens.test.ts's, and #336 is why it
// needs asking separately. That file proves every colour comes from a semantic
// token, and the dark map controls passed it while being nearly unreadable:
// `--bg-surface` is a perfectly good token, it is simply a SCREEN surface - one
// picked to sit on `--bg-page` in a settings list. On the map's own backdrop it
// came out at 1.06:1, so the control was very nearly the colour of the map.
//
// The second half is subtler and is the one no token rule could have caught.
// maplibre-gl.css gives the control group its only boundary as
// `box-shadow: 0 0 0 2px rgba(0,0,0,.1)`, and the scale bar its own as
// `border: 2px solid #333`. Both assume something light behind them. On ink
// they are darker than the surfaces they separate, so they draw nothing -
// overriding the background silently removed the edge as well, and the symptom
// (grey glyphs floating on the map) looked like a glyph problem rather than a
// missing button.
//
// jsdom does no layout and does not resolve `var()`, so what is asserted here
// is the CSS contract, the way appShellLayout.test.ts and themeTokens.test.ts
// assert theirs.

const ROOT = resolve(process.cwd(), 'src')
const chrome = readFileSync(resolve(ROOT, 'chrome/chrome.css'), 'utf8')
const colours = readFileSync(resolve(ROOT, 'design-system/tokens/colors.css'), 'utf8')

/** The declaration block for one selector. Matched on the selector with its
 *  whitespace collapsed, so Prettier wrapping a long one across lines does not
 *  quietly turn a real assertion into a "not found". */
function rule(selector: string): string {
  const flat = chrome.replace(/\s+/g, ' ')
  const at = flat.indexOf(`${selector.replace(/\s+/g, ' ')} {`)
  expect(at, `${selector} not found in chrome.css`).toBeGreaterThan(-1)
  return flat.slice(at, flat.indexOf('}', at))
}

/** The `:root[data-theme='dark']` block, which is where a semantic alias means
 *  what it means on this canvas. */
const darkBlock = colours.slice(
  colours.indexOf(":root[data-theme='dark']{"),
  colours.indexOf('}', colours.indexOf(":root[data-theme='dark']{")),
)

/**
 * A token's literal value UNDER THE DARK THEME, following aliases down to a
 * hex, so a contrast figure comes from what actually renders rather than from a
 * number copied into a test.
 *
 * Resolving in the dark block rather than globally is the point: `--bg-surface`
 * is `--white` in one theme and `--ink-850` in the other, and reading the
 * `:root` value would compute the contrast of a colour this canvas never shows.
 */
function token(name: string): string {
  for (let current = name, hops = 0; hops < 5; hops += 1) {
    const scoped = new RegExp(`^--${current}:(.+);`, 'm')
    const found = scoped.exec(darkBlock) ?? scoped.exec(colours)
    expect(found, `--${current} is not declared in colors.css`).not.toBeNull()

    const value = found![1].trim()
    if (value.startsWith('#')) return value

    const alias = /^var\(--([a-z0-9-]+)\)$/.exec(value)
    expect(
      alias,
      `--${current} is neither a hex nor a plain alias: ${value}`,
    ).not.toBeNull()
    current = alias![1]
  }
  throw new Error(`--${name} does not resolve to a colour in five hops`)
}

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16) / 255)
  const linear = channels.map((v) =>
    v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4,
  )
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
}

function contrast(a: string, b: string): number {
  const [lighter, darker] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (lighter + 0.05) / (darker + 0.05)
}

/**
 * The colour `--edge-over-map` resolves to under the dark theme, as a hex.
 *
 * Declared as `rgb(r g b / a)` rather than a hex because an edge over a canvas
 * wants alpha. Only the channels are read: what is being asserted is that the
 * edge is LIGHTER than the map, and an alpha-blended light hairline is still a
 * light hairline.
 */
function edgeOverMap(): string {
  const found = /^--edge-over-map:rgb\(\s*(\d+)\s+(\d+)\s+(\d+)/m.exec(darkBlock)
  expect(found, '--edge-over-map is not declared in the dark block').not.toBeNull()
  const [, r, g, b] = found!
  return `#${[r, g, b].map((c) => Number(c).toString(16).padStart(2, '0')).join('')}`
}

describe('what the dark theme draws over the map canvas', () => {
  const group = ":root[data-theme='dark'] .map-view .maplibregl-ctrl-group"
  const scale = ":root[data-theme='dark'] .map-view .maplibregl-ctrl-scale"

  it('lifts the control chip off the backdrop rather than matching it', () => {
    // Not a WCAG threshold - this is surface against surface, not text. 1.2 is
    // simply "distinguishable at all", and the value that shipped (1.06) was
    // not. The real separation comes from the edge asserted below; this stops
    // the chip from being the same colour as the map while that edge exists.
    const chip = rule(group)
    const named = /background:\s*var\(--([a-z0-9-]+)\)/.exec(chip)
    expect(named, 'the control chip declares no background token').not.toBeNull()

    expect(contrast(token(named![1]), MAP_BACKDROP.dark)).toBeGreaterThan(1.2)
  })

  it('keeps it dark enough to be worth having at night', () => {
    // The other side of the same trade. The reason this theme exists is a phone
    // that does not cost night vision on a trail after dark
    // (features/UX_CUSTOMIZATION.md), and a control bright enough to separate
    // itself by luminance alone would undo that.
    const named = /background:\s*var\(--([a-z0-9-]+)\)/.exec(rule(group))!
    expect(contrast(token(named[1]), MAP_BACKDROP.dark)).toBeLessThan(3)
  })

  it('gives the control group an edge the dark canvas can show', () => {
    // The whole of #336. maplibre's own ring is 10% black, which on ink is
    // darker than both surfaces - so a rule that sets the background and stops
    // there leaves the control with no boundary at all.
    const chip = rule(group)

    expect(chip, 'the control chip sets a background but declares no edge').toMatch(
      /box-shadow:/,
    )
    expect(chip, 'the edge does not come from the over-map role').toMatch(
      /var\(--edge-over-map\)/,
    )
  })

  it('draws that edge lighter than the map, not darker', () => {
    // Computed rather than matched, because this is the actual rule and it is
    // the one that is easy to break by reaching for a shadow: over ink, a
    // boundary is only a boundary if it is lighter than what it separates.
    expect(luminance(edgeOverMap())).toBeGreaterThan(luminance(MAP_BACKDROP.dark))
    expect(contrast(edgeOverMap(), MAP_BACKDROP.dark)).toBeGreaterThan(4)
  })

  it('gives the scale bar the same edge, for the same reason', () => {
    // Its `border: 2px solid #333` is the other boundary that assumed
    // something light behind it.
    expect(rule(scale)).toMatch(/var\(--edge-over-map\)/)
  })

  it('keeps a disabled control visible as off rather than as absent', () => {
    // maplibre takes a disabled icon to 25%, which on white still reads as a
    // pale grey and on this chip left the zoom-in button at maximum zoom
    // effectively gone.
    const disabled = rule(
      ":root[data-theme='dark'] .map-view .maplibregl-ctrl button:disabled .maplibregl-ctrl-icon",
    )
    const opacity = /opacity:\s*([\d.]+)/.exec(disabled)

    expect(opacity, 'no opacity declared for a disabled icon').not.toBeNull()
    expect(Number(opacity![1])).toBeGreaterThan(0.25)
    // And still obviously weaker than the enabled one beside it.
    expect(Number(opacity![1])).toBeLessThan(0.7)
  })

  it('leaves the light theme controls to maplibre', () => {
    // The library's own white-chip-on-paper styling is correct there, and a
    // second set of overrides would be two things to keep in step for nothing.
    expect(chrome).not.toMatch(/:root\[data-theme='light'\][^{]*maplibregl/)
  })
})
