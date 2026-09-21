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

/** Every `--name:` declared anywhere in a stylesheet, at any indent.
 *
 *  `declared` above is anchored to the line start because the token files
 *  write their declarations flush left. An app stylesheet indents inside a
 *  rule, and `--min-touch-target: 44px` two spaces in is a definition like any
 *  other. */
function declarations(css: string): string[] {
  return [...css.matchAll(/(?:^|[\s;{])--([a-z0-9-]+)\s*:/gm)].map((m) => m[1])
}

/** Every custom property a component sets from TSX, e.g. NextUpRail.tsx's
 *  `{ '--chip-accent': poiColor(point.type) }`.
 *
 *  A property set in an inline style is as defined as one in a stylesheet -
 *  the element carries it and everything under it reads it. Matching any
 *  quoted `'--name'` rather than one followed by a colon is deliberate:
 *  PoiCard.tsx writes its key as `['--poi-accent' as string]: accent`, which a
 *  colon-anchored pattern misses. This list only ever has to be a superset,
 *  because its job is to keep a real definition from being reported as a
 *  missing one. */
function componentSetProperties(): string[] {
  const walk = (dir: string): string[] =>
    readdirSync(dir).flatMap((entry) => {
      const full = join(dir, entry)
      if (statSync(full).isDirectory()) return walk(full)
      return /\.tsx?$/.test(full) ? [full] : []
    })

  return walk(ROOT).flatMap((file) =>
    [...readFileSync(file, 'utf8').matchAll(/'(--[a-z0-9-]+)'/gi)].map((m) =>
      m[1].slice(2),
    ),
  )
}

/** The same CSS with every comment blanked out, character for character.
 *
 *  Blanked rather than removed so that line numbers still point at the line
 *  the reader will open. This exists because the first run of the rule below
 *  reported `var(--bg-raised)` out of a COMMENT explaining that
 *  `var(--bg-raised)` had been the bug - the one place in the repository where
 *  the name should still appear. */
function withoutComments(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, (block) => block.replace(/[^\n]/g, ' '))
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
  /var\(--(?:pine|forest|moss|sage|stone|paper|blaze|ink|bone|amber|alert|olive|terracotta|white|black)[a-z0-9-]*\)/

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
        /^(pine|forest|moss|sage|stone|paper|blaze|ink|bone|amber|alert|olive|terracotta|white|black)-?\d*$/,
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

  it('leaves no app stylesheet on a var() chain with nothing at the end of it', () => {
    // THE SISTER OF THE RULE ABOVE, AND THE HALF THAT WAS MISSING. That one
    // catches `var(--never-defined, #fdf1d6)` - a hardcoded colour wearing a
    // token's clothes. It cannot see `var(--never-defined)`, or
    // `var(--never-defined, var(--also-never-defined))`, because there is no
    // literal in either to match on.
    //
    // Those two are worse. A var() whose every name is undefined and which
    // has no literal to fall back to resolves to the guaranteed-invalid
    // value, which makes the WHOLE declaration invalid at computed-value time
    // - so the property is not "wrong colour", it is absent. For a background
    // that means transparent.
    //
    // `--bg-raised` and `--bg-0` were six such surfaces on 2026-09-20 and
    // nothing has ever defined either name: the dropped-waypoint chip's
    // background (#528), the waypoint card's expand button and note field,
    // that card's observation hover, the volunteer form's inputs, and the
    // Show points switch's own pill and knob. Every one of them rendered with
    // no background at all, on both themes, for as long as it had shipped.
    // The switch is how it was finally noticed - a pill with the map showing
    // through it and a knob that was not there, on the pr-1590 preview frame.
    // WIDER THAN THE RULE ABOVE'S `defined`, on purpose. That one asks "is
    // this a design-system token", because its subject is a colour that
    // cannot follow the theme. This one asks "does anything, anywhere, give
    // this name a value" - the cascade is global, so a property declared in
    // chrome.css (`--min-touch-target`) or set inline by a component
    // (`--poi-accent`, NextUpRail.tsx's `--chip-accent`) is as real as one in
    // colors.css. Counting only the token files here reported 60 false
    // positives on first run.
    const defined = new Set([
      ...appStylesheets().flatMap((file) => declarations(readFileSync(file, 'utf8'))),
      ...declared(colours),
      ...declarations(readFileSync(join(TOKENS, 'spacing.css'), 'utf8')),
      ...declarations(readFileSync(join(TOKENS, 'typography.css'), 'utf8')),
      ...declarations(readFileSync(join(TOKENS, 'effects.css'), 'utf8')),
      ...componentSetProperties(),
    ])

    /** Every `var(...)` in `css`, as {name, fallback, at}, outermost first. */
    function varCalls(css: string): { name: string; fallback: string; at: number }[] {
      const found: { name: string; fallback: string; at: number }[] = []
      for (const match of css.matchAll(/var\(\s*--([a-z0-9-]+)/gi)) {
        const open = css.indexOf('(', match.index)
        // Walk to this var()'s own closing paren, so a nested var() in the
        // fallback comes back whole rather than cut at the first ')'.
        let depth = 0
        let close = open
        for (; close < css.length; close += 1) {
          if (css[close] === '(') depth += 1
          else if (css[close] === ')') {
            depth -= 1
            if (depth === 0) break
          }
        }
        const inner = css.slice(open + 1, close)
        const comma = inner.indexOf(',')
        found.push({
          name: match[1],
          fallback: comma === -1 ? '' : inner.slice(comma + 1).trim(),
          at: css.slice(0, match.index).split('\n').length,
        })
      }
      return found
    }

    /** Whether this chain can produce a value: any defined name, or a literal
     *  tail. A literal is anything that is not another var(). */
    function resolves(name: string, fallback: string): boolean {
      if (defined.has(name)) return true
      if (fallback === '') return false
      if (!fallback.startsWith('var(')) return true
      const [next] = varCalls(fallback)
      return next === undefined ? true : resolves(next.name, next.fallback)
    }

    const blank = appStylesheets().flatMap((file) => {
      const css = withoutComments(readFileSync(file, 'utf8'))
      return varCalls(css)
        .filter(({ name, fallback }) => !resolves(name, fallback))
        .map(({ name, at }) => `${relative(ROOT, file)}:${at} var(--${name})`)
    })

    expect(blank).toEqual([])
  })
})
