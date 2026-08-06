import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'

// The theme is a token re-point, not a second stylesheet - so what has to hold
// is a contract about the tokens, and jsdom does no layout and resolves no
// custom properties. These assert the contract, the same way
// appShellLayout.test.ts and siteLayout.test.ts assert theirs.
//
// The failure they exist to catch is not a crash and would not show in any
// component test: one rule reading a base palette token instead of a semantic
// one, which is invisible under the light theme - `--stone-900` and `--fg-1`
// are the same colour there - and is dark-grey text on an ink background under
// the dark one. That is exactly the bug this change had to fix in five places
// (the tab bar's wordmark, the elevation ribbon's line and cursor, the app
// shell's own canvas), and nothing but a rule like this would have found them.

const ROOT = resolve(process.cwd(), 'src')
const TOKENS = join(ROOT, 'design-system/tokens')

const colours = readFileSync(join(TOKENS, 'colors.css'), 'utf8')

function block(selector: string): string {
  const at = colours.indexOf(`${selector}{`)
  expect(at, `${selector} not found in colors.css`).toBeGreaterThan(-1)
  return colours.slice(at, colours.indexOf('}', at))
}

/** Every `--name:` declared in a block. */
function declared(css: string): string[] {
  return [...css.matchAll(/^--([a-z0-9-]+):/gm)].map((m) => m[1])
}

/** Every app stylesheet, which is every .css under src/ except the design
 *  system's own - those files ARE the palette, so naming a base colour in them
 *  is the point rather than a leak. */
function appStylesheets(dir = ROOT): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) {
      return full.startsWith(join(ROOT, 'design-system')) ? [] : appStylesheets(full)
    }
    return full.endsWith('.css') ? [full] : []
  })
}

/** The base palette: colours named for what they look like. A stylesheet that
 *  reads one of these cannot follow a theme, because the token means the same
 *  colour in both. */
const BASE_PALETTE =
  /var\(--(?:pine|forest|moss|sage|stone|paper|blaze|ink|bone|amber|alert|white|black)[a-z0-9-]*\)/

describe('the theme token contract', () => {
  it('re-points the semantic aliases under the dark theme', () => {
    const dark = declared(block(":root[data-theme='dark']"))

    // The ones that carry meaning rather than a hue. A spot check with teeth:
    // every one of these is a colour that would be unreadable if it did not
    // move - dark ink text on an ink page, forest green on ink.
    for (const token of [
      'bg-page',
      'bg-surface',
      'bg-sunken',
      'surface-card',
      'fg-1',
      'fg-2',
      'fg-3',
      'border-1',
      'border-2',
      'brand-primary',
      'link',
      'danger',
      'info',
      'success',
    ]) {
      expect(dark, `--${token} has no dark value`).toContain(token)
    }
  })

  it('redefines no base palette entry, so a colour name keeps meaning its colour', () => {
    // `--forest-600` has to be green in both themes. What changes is which
    // semantic alias points at it - otherwise a stylesheet reaching for a hue
    // by name gets something else, which is worse than the leak this file is
    // mostly about.
    const dark = declared(block(":root[data-theme='dark']"))

    for (const token of dark) {
      expect(token, `${token} looks like a base palette entry`).not.toMatch(
        /^(pine|forest|moss|sage|stone|paper|blaze|ink|bone|amber|alert|white|black)-?\d*$/,
      )
    }
  })

  it('declares a colour-scheme in both themes', () => {
    // Not cosmetic: it is what decides the scrollbars, the form controls and
    // the default canvas. Left at `light` under the dark theme, the app gets
    // white scrollbars down the side of an ink screen.
    expect(block(':root')).toMatch(/color-scheme:\s*light/)
    expect(block(":root[data-theme='dark']")).toMatch(/color-scheme:\s*dark/)
  })

  it('leaves no app stylesheet reading a base palette token', () => {
    const leaks = appStylesheets()
      .map((file) => ({ file, css: readFileSync(file, 'utf8') }))
      .flatMap(({ file, css }) =>
        css
          .split('\n')
          .map((line, index) => ({ line, at: index + 1 }))
          .filter(({ line }) => BASE_PALETTE.test(line))
          .map(({ line, at }) => `${relative(ROOT, file)}:${at} ${line.trim()}`),
      )

    expect(leaks).toEqual([])
  })

  it('leaves no app stylesheet reading a token nothing defines', () => {
    // `var(--warning-100, #fdf1d6)` was in two files and `--warning-100` has
    // never existed anywhere, so both got their hardcoded fallback every time.
    // A fallback is not a bug; a fallback that is ALWAYS what renders is a
    // hardcoded colour wearing a token's clothes, and it cannot follow a theme.
    const defined = new Set([
      ...declared(colours),
      ...declared(readFileSync(join(TOKENS, 'spacing.css'), 'utf8')),
      ...declared(readFileSync(join(TOKENS, 'typography.css'), 'utf8')),
      ...declared(readFileSync(join(TOKENS, 'effects.css'), 'utf8')),
    ])

    const unknown = appStylesheets().flatMap((file) => {
      const css = readFileSync(file, 'utf8')
      return [...css.matchAll(/var\(--([a-z0-9-]+)\s*,\s*#[0-9a-f]{3,8}\)/gi)]
        .map((m) => m[1])
        .filter((name) => !defined.has(name))
        .map((name) => `${relative(ROOT, file)}: --${name}`)
    })

    expect(unknown).toEqual([])
  })
})
