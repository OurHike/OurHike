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
//
// HALF OF THAT CONTRACT IS NOT HERE, AND CANNOT BE: a rule whose selector
// matches no element is exactly as absent as a deleted one, so everything below
// is worth nothing unless `poi-card__chip` and `poi-card__chips` are really on
// the button and the strip. chrome/PoiCard.test.tsx asserts that against the
// rendered DOM, for the same reason it asserts the icon's slot class there.
const css = readFileSync(resolve(process.cwd(), 'src/chrome/chrome.css'), 'utf8')

function rule(selector: string): string {
  const at = css.indexOf(`${selector} {`)
  expect(at, `${selector} not found in chrome.css`).toBeGreaterThan(-1)
  return css.slice(at, css.indexOf('}', at))
}

/**
 * The inset rings a rule draws, as {spread, colour} in the order declared -
 * which is the order they paint, first on top.
 *
 * Parsed rather than string-matched because what these tests have to say is
 * how WIDE the ring is and how far in it starts, and `box-shadow: none` passes
 * every test that only asks whether the property is mentioned - which is
 * TESTING.md's "a test that cannot fail is worse than no test".
 */
function ringBands(declarations: string): Array<{ spread: number; color: string }> {
  return [...declarations.matchAll(/inset 0 0 0 (\d+)px (var\([^)]*\)|#[0-9a-f]+)/g)].map(
    ([, spread, color]) => ({ spread: Number(spread), color }),
  )
}

/** The width of an outline, in px, or 0 for `outline: none` - which is the
 *  regression worth catching, because it leaves `outline-offset` behind looking
 *  deliberate. */
function focusRingWidth(declarations: string): number {
  return Number(/outline:\s*(\d+)px\s+solid/.exec(declarations)?.[1] ?? 0)
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

  it('gives every chip the whole touch target, in both directions', () => {
    // Against the token, never the literal 44px: desktop.css narrows it to 32px
    // under `pointer: fine`, and a hard-coded 44 here would silently opt this
    // one control out of that.
    //
    // WIDTH JOINED HEIGHT IN #711. A chip used to be its words, so it was never
    // narrower than 97px and the height was the whole of the guarantee. An
    // unselected chip is now its pin alone - 24px of icon in 8px of padding
    // either side - which is 40px, under the token in the one direction nothing
    // was checking. Dropping this line does not fail a single other test in
    // this suite: jsdom does no layout, so the strip still "fits" and the chips
    // still carry their class.
    const chip = rule('.poi-card__chip')

    expect(chip).toMatch(/min-width:\s*var\(--min-touch-target\)/)
    expect(chip).toMatch(/min-height:\s*var\(--min-touch-target\)/)
  })

  it('takes an unread chip’s words out of the layout, not just out of sight', () => {
    // #711, and the half of it that lives in CSS. chrome/PoiCard.test.tsx
    // asserts the other half - that `visually-hidden` really lands on the label
    // of every chip but the one being read - and the two together are what stop
    // a three-part site asking for 406px of a 240px strip.
    //
    // Asserted from here, on a shared utility this file otherwise has no
    // business in, because the strip's fit now DEPENDS on that utility: soften
    // `.visually-hidden` to `opacity: 0` or `color: transparent` and every test
    // in both files stays green - the class is still applied, the accessible
    // name is unchanged, jsdom measures nothing - while all 406px of the
    // overflow comes back and the bug is exactly as it was.
    const hidden = rule('.visually-hidden')

    expect(hidden).toMatch(/position:\s*absolute/)
    expect(hidden).toMatch(/width:\s*1px/)
    expect(hidden).toMatch(/height:\s*1px/)
  })

  it('keeps a chip’s words in a flex box of their own, so the spacing does not double', () => {
    // The category, the middot and the distance used to be direct children of
    // the chip, spaced by ITS `gap` - and the whitespace text nodes between
    // them, which exist so the accessible name reads "Privy 131 ft" rather than
    // "Privy131 ft", were dropped as whitespace-only runs by that same flex
    // context. #711 wrapped the three in one span so one class could hide them
    // all. A plain inline wrapper would start rendering those spaces, putting a
    // space AND a 4px gap between each pair - the reason the accessible name
    // and the visual spacing can share one set of nodes at all.
    const label = rule('.poi-card__chip-label')

    expect(label).toMatch(/display:\s*inline-flex/)
    expect(label).toMatch(/gap:/)
  })

  it('marks the part you are on by more than a colour', () => {
    // The rule .legend__row--hidden states outright and tabs.css follows: hue
    // alone is not something this app rests an answer on, and a strip read at
    // arm's length in direct sun is exactly that kind of place.
    //
    // The VALUES, not the property names. `box-shadow: none` and
    // `font-weight: 400` are the realistic regressions - the first is what
    // somebody reaches for when an inset ring looks wrong against a 999px
    // radius - and both would satisfy a test that only asked whether the
    // declaration was present, while leaving the current chip marked by colour
    // alone - which is the one thing this test's name says it must not be, and a
    // test that cannot fail spending its credibility on the ones that can
    // (TESTING.md's third rule).
    const current = rule(".poi-card__chip[aria-current='true']")

    expect(ringBands(current).length).toBeGreaterThan(0)
    for (const band of ringBands(current)) expect(band.spread).toBeGreaterThan(0)

    // Heavier than the chip's own text, which sets no weight and so inherits the
    // card's 400. Anything under 600 is not a channel at 13px.
    const weight = Number(/font-weight:\s*(\d+)/.exec(current)?.[1])
    expect(weight).toBeGreaterThanOrEqual(600)
  })

  it('keeps the focus ring inside the card, which clips', () => {
    // .poi-card sets `overflow: hidden` to round the photo's corners with the
    // card's, so an outward ring on the first or last chip would be cut off by
    // the rule that makes the card a card.
    //
    // Again the value: `outline: none` with the offset left behind reads as a
    // deliberate inward ring and is invisible keyboard focus.
    const focus = rule('.poi-card__chip:focus-visible')

    expect(focusRingWidth(focus)).toBeGreaterThan(0)
    expect(focus).toMatch(/outline-offset:\s*-/)
  })

  it('leaves the focus ring room to land on the chip you are on', () => {
    // The anchor chip is both first in the tab order and the current one when
    // the card opens, so it is where a keyboard user lands first - and the focus
    // outline is drawn in the band at the chip's edge. A current-marker ring in
    // those same pixels leaves "focused" signalled by hue: resolving the tokens,
    // --brand-primary against --fg-2 is 1.01:1 in the light theme and 1.65:1 in
    // the dark one, both far under 3:1. So the marker starts further in, and what
    // holds that open is an inset shadow in the chip's own background colour.
    const current = rule(".poi-card__chip[aria-current='true']")
    const ring = focusRingWidth(rule('.poi-card__chip:focus-visible'))

    // The chip's OWN background, read off the chip, so a change of background
    // that forgot this shadow shows up here as a stripe of the wrong colour
    // rather than passing.
    const background = /background:\s*(var\([^)]*\))/.exec(rule('.poi-card__chip'))?.[1]
    expect(background).toBeDefined()

    const bands = ringBands(current)
    const clear = bands.filter((band) => band.color === background)
    expect(clear).toHaveLength(1)
    // Wide enough to cover the whole outline, or the two rings still touch - and
    // narrower than the marker, or the marker is painted out altogether. It masks
    // rather than is masked because a shadow list paints front to back: the first
    // one declared is the one on top.
    expect(clear[0].spread).toBeGreaterThanOrEqual(ring)
    expect(Math.max(...bands.map((band) => band.spread))).toBeGreaterThan(clear[0].spread)
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
