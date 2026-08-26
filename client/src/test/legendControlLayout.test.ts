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

// THE SECOND BUG, same panel, same cause as the first - a CSS contract that
// nothing enforced (#528).
//
// The drawn counts made a pin row end in a block of mono digits: `Viewpoint`
// against the corridor's 1,223 of them renders `0/1223`. Photographed in
// Chromium at the three widths this panel has:
//
//   272px (desktop, desktop.css `flex: 0 0 17rem`)
//     five of the seven rows overflowed their grid track outright - the widest
//     surface for the panel was the worst affected, and the least looked at
//
//   320px (iPhone SE)
//     the 8px gutter between the columns measured 0.6px of actual ink
//
//   390px
//     8px, which is the designed gutter and still reads as the columns touching
//
// A flex item defaults to `min-width: auto` and will not shrink below its own
// min-content, so every link from the grid track down to the label has to opt
// out before a row can fit itself into its track. One link left at `auto`
// restores the overflow, silently and only at narrow widths - which is what
// makes this worth pinning rather than reviewing.
describe('a legend row can shrink into its column', () => {
  /**
   * The `.legend__pins` block that lays the grid out.
   *
   * Not `rule()`, which takes the first `.legend__pins {` in the file - and
   * that is the reset above it, whose body is margins. (That reset used to be
   * a grouped `.legend__blazes, .legend__pins`; the blaze half went with the
   * legend's blaze rows on 2026-08-25, and the ambiguity it caused did not.)
   * Anchored on the property being asserted about instead.
   */
  function pinsGrid(): string {
    const at = css.indexOf('grid-template-columns')
    expect(at, 'no grid-template-columns in chrome.css').toBeGreaterThan(-1)
    return css.slice(css.lastIndexOf('{', at), css.indexOf('}', at))
  }

  it('opens the whole chain, not only the label', () => {
    // The grid track, the button inside the row, and the one flexible item.
    expect(pinsGrid()).toMatch(/minmax\(\s*150px/)
    expect(rule('.legend__toggle')).toMatch(/min-width:\s*0/)
    expect(rule('.legend__label')).toMatch(/min-width:\s*0/)
  })

  it('drops to one column rather than truncating the category names', () => {
    // Measured at 320px: a hard two-column grid there cuts `Campsite`,
    // `Resupply` and `Viewpoint` to `Cam…`, `Resu…` and `Vie…`. A category name
    // is what the row IS, so the column count gives way before the word does.
    expect(pinsGrid()).toMatch(/repeat\(\s*auto-fit/)
    expect(pinsGrid()).not.toMatch(/repeat\(\s*2\s*,/)
  })

  it('spends the label on an ellipsis and never the count', () => {
    // A label that loses a letter is still readable beside its own pin. A count
    // that lost a digit would be a different number, with nothing saying so.
    expect(rule('.legend__label')).toMatch(/text-overflow:\s*ellipsis/)
    expect(rule('.legend__count')).toMatch(/flex:\s*none/)
  })
})

// THE SHEET ITSELF, now that the grid inside it is every hideable category
// rather than the two or three in the viewport (#723).
//
// The list is reliably taller than the sheet on a phone, so scrolling stopped
// being the occasional case and became the normal one. What that changes is not
// the cap - this thing covers the map, and features/MAP_OPTIONS.md §4 documents
// the 60% cap and the trade it accepts - but what the scroll has to survive at
// its two ends.
describe('the legend sheet scrolls a list longer than itself', () => {
  const sheet = rule('.legend')

  it('still scrolls its own overflow rather than growing', () => {
    expect(sheet).toMatch(/overflow-y:\s*auto/)
    expect(sheet).toMatch(/max-height:\s*60%/)
  })

  it('stops the scroll at its own edges', () => {
    // Chained to the document, a flick past the end of the list reaches Chrome
    // for Android's pull-to-refresh - so a hiker reaching for the row below the
    // fold could reload the app instead. Reasoned from the documented chaining
    // behaviour rather than measured: nothing here can drive a real Android
    // touch stack, which is exactly why it is pinned rather than reviewed.
    expect(sheet).toMatch(/overscroll-behavior:\s*contain/)
  })

  it('keeps the end of that list clear of the system bar', () => {
    // The sheet is positioned against the initial containing block, so its
    // bottom edge IS the viewport's - and the last thing in it is the row a
    // hiker just scrolled down to reach.
    expect(sheet).toMatch(/padding-bottom:.*env\(safe-area-inset-bottom/)
  })
})

// THE ALERTS SWITCH (#1047), which is the fourth control on this panel and the
// first over a safety layer.
//
// The reason it is pinned here rather than left to review is the reason the
// picker above is: this panel's controls are read at 272px beside a desktop map
// and at 390px on a phone, and every previous control that grew a second line
// of text got that second line by accident. This one carries a sentence on
// purpose - what the switch does NOT take away - so the row has to be the shape
// that can hold one.
describe('the alerts switch sits on a row like the overlay switch above it', () => {
  it('is laid out as the drought row is, because it is the same kind of thing', () => {
    // A map overlay with a name, a sentence under the name and a checkbox at
    // the end. Two vocabularies for one shape is how a panel comes to look
    // assembled rather than designed.
    const alerts = rule('.legend__alerts')
    const drought = rule('.legend__drought')

    for (const declaration of [
      /display:\s*flex/,
      /align-items:\s*center/,
      /justify-content:\s*space-between/,
      /min-height:\s*var\(--min-touch-target\)/,
      /border-top:\s*1px solid var\(--border-1\)/,
    ]) {
      expect(alerts).toMatch(declaration)
      expect(drought).toMatch(declaration)
    }
  })

  it('stacks the name over its sentence rather than running them together', () => {
    // Without the column direction the sentence sits beside the word "Alerts"
    // on one line and the checkbox is pushed off the row's end at 272px. The
    // sentence is the part a hiker reads before deciding to turn a safety layer
    // off, so it is not the part allowed to fall off the panel.
    const name = rule('.legend__alerts-name')

    expect(name).toMatch(/display:\s*flex/)
    expect(name).toMatch(/flex-direction:\s*column/)
    expect(name).toMatch(/flex:\s*1/)
  })

  it('draws that sentence quieter than the switch it explains', () => {
    // Same treatment as the drought row's own detail line: smaller, secondary
    // colour. The switch is the control; the sentence is the caveat on it.
    // 12px, not the 11px this first shipped at: the #1054 typography pass set
    // a 12px floor under prose a hiker reads in sun, and the sentence a hiker
    // reads before switching a safety layer off is squarely that. Quieter
    // survives the bump - the row's own label inherits the panel's larger
    // size, and the secondary colour is the other half of the treatment.
    expect(rule('.legend__alerts-detail')).toMatch(/font-size:\s*12px/)
    // --fg-2, not --text-2 (#1057): the --text-* family is typography, and
    // --text-2 was never declared anywhere in the repo. An undefined custom
    // property with no fallback is invalid at computed-value time, so the
    // rule inherited body colour instead of demoting the line - and this
    // assertion pinned the typo as the contract.
    expect(rule('.legend__alerts-detail')).toMatch(/color:\s*var\(--fg-2\)/)
  })
})
