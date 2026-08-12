import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// jsdom does no layout and does not resolve `var()`, so - as with
// appShellLayout.test.ts and siteLayout.test.ts - this asserts the CSS CONTRACT
// that was broken rather than the pixels.
//
// THE BUG. The legend's type picker (#530) shipped as an inline `<select>` in a
// paragraph of prose: a sentence saying what was filtered, a "Show all" button
// and the picker, strung together with middots. Photographed in Chromium at the
// two widths the panel actually has, it was wrong in three ways at once:
//
//   272px (desktop, desktop.css `flex: 0 0 17rem`)
//     "Showing water only · Show all ·"   <- the line ended on a separator
//     "  Show one only…  ⌄"               <- with the control orphaned under it
//
//   390px (phone sheet)
//     "Showing all waypoints · Show one only… ⌄"
//     one run-on sentence, in which the last clause was a control
//
//   and the paragraph measured 47px tall for 13px text, because an inline box
//   with `min-height: var(--min-touch-target)` grows the line box it sits in and
//   aligns on its own baseline - so the words beside it sat where nothing else
//   on the panel sits.
//
// Both causes are structural, which is why they are pinned here rather than left
// to review: a control laid out as a flex ITEM sets its row's height instead of
// distorting a line of text, and a control with a border reads as a control
// rather than as the sentence it is standing in.
const css = readFileSync(resolve(process.cwd(), 'src/chrome/chrome.css'), 'utf8')

function rule(selector: string): string {
  const at = css.indexOf(`${selector} {`)
  expect(at, `${selector} not found in chrome.css`).toBeGreaterThan(-1)
  return css.slice(at, css.indexOf('}', at))
}

describe('the legend type picker sits on a row, not in a sentence', () => {
  it('lays the row out as flex, so a touch-target control cannot distort text', () => {
    const row = rule('.legend__shown')

    expect(row).toMatch(/display:\s*flex/)
    expect(row).toMatch(/align-items:\s*center/)
  })

  it('gives the row the same shape as the verified switch under it', () => {
    // Same kind of thing - one switch cutting across every row above it - so the
    // panel should not have two vocabularies for it. This is what keeps the
    // control on ONE touch-target line rather than a wrapped paragraph.
    const row = rule('.legend__shown')
    const verified = rule('.legend__verified')

    for (const declaration of [
      /justify-content:\s*space-between/,
      /min-height:\s*var\(--min-touch-target\)/,
      /border-top:\s*1px solid var\(--border-1\)/,
    ]) {
      expect(row).toMatch(declaration)
      expect(verified).toMatch(declaration)
    }
  })

  it('bounds the control, so its text is not mistaken for prose', () => {
    // `border: 0; background: none` was the whole of the "bleeding into other
    // words" complaint: same size, same line, a colour apart from the sentence
    // it sat in.
    const select = rule('.legend__shown-select')

    expect(select).toMatch(/border:\s*1px solid/)
    expect(select).not.toMatch(/border:\s*0/)
    expect(select).toMatch(/background:\s*var\(/)
    expect(select).not.toMatch(/background:\s*none/)
  })

  it('caps the control rather than the label it would crush', () => {
    // A select sizes to its widest option and will neither wrap nor ellipsise, so
    // in a 272px panel the flexible item beside it goes first - and that item is
    // the one word saying what the control IS.
    expect(rule('.legend__shown-select')).toMatch(/max-width:/)
    expect(rule('.legend__shown-name')).toMatch(/flex:\s*1/)
  })

  it('leaves nothing behind of the sentence it replaced', () => {
    // The old classes going stale in the stylesheet is how a panel ends up with
    // two ways to draw one control, one of them dead.
    for (const gone of [
      '.legend__filtered',
      '.legend__show-all',
      '.legend__only-one',
      '.legend__only-select',
    ]) {
      expect(css, `${gone} is still in chrome.css`).not.toContain(`${gone} {`)
    }
  })
})
