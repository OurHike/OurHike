import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// jsdom does no layout and does not resolve `var()`, so - as with
// legendControlLayout.test.ts and appShellLayout.test.ts - this asserts the CSS
// CONTRACT rather than the pixels.
//
// Two of #526's requirements live entirely in this stylesheet and nowhere in the
// component, which is why they need a home here or they are pinned by nothing:
//
//   THE STRIP SCROLLS. The card is `min(264px, ...)` wide and the strip sits
//   inside 12px of body padding each side, so it has 240px to work with while a
//   chip carrying a 24px pin, a category and a distance is most of 110px. Two
//   fit. The alternative - wrapping - would change the CARD's height with the
//   number of parts, and PoiCard is positioned by its measured height whenever
//   it hangs below its pin, so a strip that grew a row would push itself over
//   the thing it describes.
//
//   EVERY CHIP IS A TOUCH TARGET. This is tapped with a gloved thumb, and the
//   whole chip is the button.
//
// Neither is sized to the sites that exist today. features/POI_SITES.md counts
// 94% of them at two or three members, but that shape is partly #529's water gap
// - 97% of shelters have no mapped water source, so 11 water points are members
// of anything - and it moves as that closes.
const css = readFileSync(resolve(process.cwd(), 'src/chrome/chrome.css'), 'utf8')

function rule(selector: string): string {
  const at = css.indexOf(`${selector} {`)
  expect(at, `${selector} not found in chrome.css`).toBeGreaterThan(-1)
  return css.slice(at, css.indexOf('}', at))
}

describe('the waypoint card’s strip of site parts', () => {
  it('scrolls sideways rather than wrapping to a second row', () => {
    const strip = rule('.poi-card__chips')

    expect(strip).toMatch(/overflow-x:\s*auto/)
    // Wrapping is the failure mode, and `flex-wrap: wrap` is the one-word way
    // to introduce it.
    expect(strip).not.toMatch(/flex-wrap:\s*wrap/)
  })

  it('does not spend a chip’s width on a scrollbar', () => {
    expect(rule('.poi-card__chips')).toMatch(/scrollbar-width:\s*none/)
    expect(css).toContain('.poi-card__chips::-webkit-scrollbar {')
  })

  it('lets a chip be as wide as what it says, so the strip overflows instead', () => {
    // `flex: 1 0 auto` is what tabs.css uses, because a tab strip fills its row.
    // Inherited here it would squeeze five chips into 240px rather than let the
    // strip scroll - which is requirement 4 defeated by a copied declaration.
    const chip = rule('.poi-card__chip')

    expect(chip).toMatch(/flex:\s*0 0 auto/)
    expect(chip).toMatch(/white-space:\s*nowrap/)
  })

  it('gives every chip the whole touch target', () => {
    // Against the token, never the literal 44px: desktop.css narrows it to 32px
    // under `pointer: fine`, and a hard-coded 44 here would silently opt this
    // one control out of that.
    expect(rule('.poi-card__chip')).toMatch(/min-height:\s*var\(--min-touch-target\)/)
  })

  it('marks the part you are on by more than a colour', () => {
    // The rule .legend__row--hidden states outright and tabs.css follows: hue
    // alone is not something this app rests an answer on, and a strip read at
    // arm's length in direct sun is exactly that kind of place.
    const current = rule(".poi-card__chip[aria-current='true']")

    expect(current).toMatch(/box-shadow:/)
    expect(current).toMatch(/font-weight:/)
  })

  it('keeps the focus ring inside the card, which clips', () => {
    // .poi-card sets `overflow: hidden` to round the photo's corners with the
    // card's, so an outward ring on the first or last chip would be cut off by
    // the rule that makes the card a card.
    expect(rule('.poi-card__chip:focus-visible')).toMatch(/outline-offset:\s*-/)
  })

  it('sizes the pin the chip carries, because MapIcon has no size of its own', () => {
    // Same fixed square slot .legend__icon gives it. A caller that sets none
    // gets whatever the flex context decides, and jsdom would never notice.
    const icon = rule('.poi-card__chip-icon')

    expect(icon).toMatch(/flex:\s*none/)
    expect(icon).toMatch(/width:\s*24px/)
    expect(icon).toMatch(/height:\s*24px/)
  })
})
