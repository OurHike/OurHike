// The desktop layout's CSS contract.
//
// jsdom does not do layout, so - as with appShellLayout.test.ts and
// siteLayout.test.ts - this asserts the contract rather than the pixels.
//
// The contract that matters is WEBSITE.md §8's: the desktop layout must not
// regress the phone layout, which is the one that gets used on trail. That is
// enforced structurally here rather than by review - every layout rule in
// desktop.css lives inside a media query, so none of them can match a phone at
// all. This file proves that property still holds, which is the kind of thing
// that decays the first time someone adds "just one" unguarded rule.
//
// Resolved from the Vitest root (client/), which vite.config.ts pins.

import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { DESKTOP_MIN_WIDTH } from '../lib/useDesktop'

const css = readFileSync(resolve(process.cwd(), 'src/desktop.css'), 'utf8')

/** The declarations of one selector, comments removed - so a rule can be
 *  asserted on without a comment that mentions it counting as a match. */
function declarationsOf(selector: string): string {
  const bare = css.replace(/\/\*[\s\S]*?\*\//g, '')
  const start = bare.indexOf(`${selector} {`)
  if (start === -1) throw new Error(`no rule for ${selector} in desktop.css`)

  return bare.slice(start, bare.indexOf('}', start))
}

/** Strip comments, then every balanced @media block, leaving only rules that
 *  apply unconditionally. */
function unguardedRules(source: string): string {
  let rest = source.replace(/\/\*[\s\S]*?\*\//g, '')

  for (;;) {
    const start = rest.indexOf('@media')
    if (start === -1) return rest
    let depth = 0
    let i = rest.indexOf('{', start)
    if (i === -1) return rest
    for (; i < rest.length; i += 1) {
      if (rest[i] === '{') depth += 1
      else if (rest[i] === '}') {
        depth -= 1
        if (depth === 0) break
      }
    }
    rest = rest.slice(0, start) + rest.slice(i + 1)
  }
}

describe('desktop layout contract', () => {
  it('puts every layout rule behind a media query', () => {
    // The §8 guarantee. A rule out here reaches a 375px phone on a mountain.
    const unguarded = unguardedRules(css)

    expect(unguarded).not.toMatch(/\.tab-bar/)
    expect(unguarded).not.toMatch(/\.map-screen/)
    expect(unguarded).not.toMatch(/\.legend/)
    expect(unguarded).not.toMatch(/\.app__screen/)
  })

  it('leaves focus rings unguarded, which is the one deliberate exception', () => {
    // :focus-visible is already silent for a tap, so gating it on width or
    // pointer would only take focus rings away from a phone with a bluetooth
    // keyboard - a bug dressed as consistency.
    expect(unguardedRules(css)).toMatch(/:focus-visible/)
  })

  it('breaks at the width useDesktop() breaks at', () => {
    // A CSS breakpoint at 960 and a JS one at 900 would give a band of widths
    // showing a sidebar with a modal legend inside it - a layout nobody would
    // think to open.
    expect(css).toMatch(new RegExp(`@media \\(min-width: ${DESKTOP_MIN_WIDTH}px\\)`))
  })

  it('keys touch-target sizing on the pointer rather than the width', () => {
    // A 1024px tablet is a wide touch screen and still needs 44px targets.
    // Tying this to the breakpoint would shrink them on the device where that
    // hurts most.
    const pointerBlock = css.slice(css.indexOf('@media (pointer: fine)'))

    expect(pointerBlock).toMatch(/--min-touch-target/)
    expect(css.slice(0, css.indexOf('@media (pointer: fine)'))).not.toMatch(
      /--min-touch-target/,
    )
  })

  it('keeps the search out of the flow of the map canvas', () => {
    // The one rule here that a jsdom test cannot see the effect of, so it is
    // pinned as text instead. .map-screen__canvas is `display: flex`, so a
    // statically positioned .search stops overlaying the map and becomes a
    // flex sibling of it. The map does not give the width back, so the canvas
    // grows past the frame: measured in Chromium at 1440px, the document
    // gained 327px of horizontal overflow and the legend panel started at
    // x=1462 - off the screen entirely.
    const block = declarationsOf('.search')

    expect(block).not.toMatch(/position:\s*(static|relative)/)
  })

  // The brand mark's whole contract is the phone/desktop split, so both halves
  // are asserted together rather than one per stylesheet. The mark is drawn at
  // the foot of the sidebar, which is a corner that exists only in this layout;
  // on a phone the bar is three thumb-sized targets across the full width, and
  // anything added there comes out of a tab or out of the map.
  it('draws the brand mark only where there is a sidebar to put it in', () => {
    const chrome = readFileSync(resolve(process.cwd(), 'src/chrome/chrome.css'), 'utf8')
    const bare = chrome.replace(/\/\*[\s\S]*?\*\//g, '')
    const start = bare.indexOf('.tab-bar__brand {')
    expect(start, 'no .tab-bar__brand rule in chrome.css').toBeGreaterThan(-1)

    // Hidden by the component's own stylesheet...
    expect(bare.slice(start, bare.indexOf('}', start))).toMatch(/display:\s*none/)
    // ...and turned back on only from inside the media query, which is what
    // makes "cannot reach a phone" structural rather than a review promise.
    expect(unguardedRules(css)).not.toMatch(/\.tab-bar__brand/)
    expect(css).toMatch(/\.tab-bar__brand\s*\{[^}]*display:\s*flex/)
  })

  it('lets the tab list grow, which is what carries the mark to the bottom edge', () => {
    // The mark is the last child of the sidebar column and is NOT pinned there
    // by absolute positioning - the tab list growing is what pushes it down. A
    // fixed height on either would let a longer tab set slide under the mark.
    const block = declarationsOf('.map-screen > .tab-bar .tab-bar__brand')

    expect(block).not.toMatch(/position:\s*absolute/)
    expect(block).toMatch(/display:\s*flex/)
  })

  it('does not hide the legend close button without the component also dropping it', () => {
    // Belt and braces, and the test says so: the CSS hides the control and the
    // component omits it. Either alone would leave a release where a panel
    // that cannot be reopened has a button that closes it.
    expect(css).toMatch(/\.legend--persistent \.legend__close\s*\{[^}]*display:\s*none/)
  })
})
