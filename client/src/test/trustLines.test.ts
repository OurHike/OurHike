import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'

// The lines a hiker reads to decide whether to believe what is on screen - how
// old it is, who checked it, what was never measured - are printed in the
// secondary grey `--fg-2`, not the faint `--fg-3` (#1670 - --fg-3 text is under
// WCAG AA contrast on every light surface, and the app uses it 229 times).
//
// WHY THESE AND NOT ALL OF `--fg-3`. #1670 darkened `--fg-3` itself to the
// first grey that clears 4.5:1, which keeps it a separate third level at the
// cost of a thin margin: 4.53:1 on its worst surface. That is enough for a
// clock time or a section eyebrow. It is not much for the lines on the four
// paths CLAUDE.md names - lost, out of water, in front of something dangerous,
// or racing the dark - read outdoors on a phone, at 11 to 13px. `--fg-2` is
// 6.23:1 or better on every surface in both themes (tokens/contrast.test.ts
// holds that). The maintainer chose `--fg-2` for these by poll on 2026-09-26,
// over primary ink and over leaving them faint.
//
// The list is a judgement, made once, from reading what each selector renders.
// A new line of the same kind has to be added here by whoever writes it: no
// test can tell a trust line from a timestamp.
const TRUST_LINES: ReadonlyArray<{ selector: string; says: string }> = [
  {
    selector: '.closure-sheet__age',
    says: 'when OurHike last checked a closure, or that it never synced',
  },
  { selector: '.poi-card__note-when', says: 'how old a field note is and who left it' },
  { selector: '.poi-card__coords', says: 'the coordinates a lost hiker would read out' },
  { selector: '.poi-card__source', says: 'who listed the waypoint' },
  {
    selector: '.hike-detail__verified',
    says: 'when the publisher last verified the route',
  },
  { selector: '.hike-detail__measurement', says: 'whose distance is whose' },
  {
    selector: '.day-summary__unmeasured',
    says: 'how much of the day has no measured climb',
  },
  {
    selector: '.day-summary__caveat',
    says: 'that the water count is only what the map carries',
  },
  {
    selector: '.plan__day-figure--unmeasured',
    says: 'how much of a planned day has no measured climb',
  },
  {
    selector: '.day-row__figures--unmeasured',
    says: 'that a day has no climb measured or no profile',
  },
  {
    selector: '.day-hike-panel__unknown',
    says: 'that this phone cannot price the climb',
  },
]

const SRC = resolve(process.cwd(), 'src')

function filesUnder(dir: string, extension: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) return filesUnder(path, extension)
    return path.endsWith(extension) ? [path] : []
  })
}

const stylesheets = filesUnder(SRC, '.css').map((path) => ({
  path,
  css: readFileSync(path, 'utf8'),
}))

/** Every `color:` any rule in any stylesheet gives exactly this selector, in
 *  file order. A selector inside a longer compound (`.x .y`) is a different
 *  element's rule and is not counted. */
function colorsFor(selector: string): string[] {
  const found: string[] = []
  for (const { css } of stylesheets) {
    const bare = css.replace(/\/\*[\s\S]*?\*\//g, '')
    for (const [, selectors, body] of bare.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
      const listed = (selectors ?? '').split(',').map((part) => part.trim())
      if (!listed.includes(selector)) continue
      for (const [, value] of (body ?? '').matchAll(/(?:^|;|\s)color:\s*([^;]+);/g)) {
        found.push((value ?? '').trim())
      }
    }
  }
  return found
}

const components = filesUnder(SRC, '.tsx')
  .filter((path) => !path.endsWith('.test.tsx'))
  .map((path) => readFileSync(path, 'utf8'))
  .join('\n')

describe('the lines a hiker reads to decide whether to trust the screen', () => {
  for (const { selector, says } of TRUST_LINES) {
    it(`prints ${selector} (${says}) in --fg-2`, () => {
      const colors = colorsFor(selector)
      expect(colors, `no stylesheet gives ${selector} a color`).not.toEqual([])
      // Every declaration, not only the last: a second rule in another file
      // that still said `--fg-3` would win or lose on load order alone.
      for (const color of colors) expect(color).toBe('var(--fg-2)')
    })

    it(`still has an element that carries ${selector}`, () => {
      // A rule whose class no component renders protects nothing, and a rename
      // would leave this suite green over text back in the browser's default.
      expect(components).toContain(selector.slice(1))
    })
  }
})
