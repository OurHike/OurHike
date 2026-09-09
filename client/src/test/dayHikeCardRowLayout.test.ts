// The day-hike card's leg and way-off rows, pinned as a contract (#1112).
//
// jsdom does no layout, so - as with poiCardChipLayout.test.ts,
// hiddenInputContainment.test.ts and desktopLayout.test.ts - what is asserted
// here is the stylesheet's text. A rendering test can prove the row's three
// parts are on screen and cannot prove they are not drawn on top of each
// other, which is the entire defect this file exists for.
//
// WHAT BROKE. The row used to carry a THIRD part - the maintaining
// organization - and was `grid-template-columns: 1fr auto auto` with both
// trailing columns `white-space: nowrap`. An `auto` track sized by unbreakable
// text claims whatever width that text needs and then overflows the card: the
// `1fr` name track collapsed to its `min-width: 0` floor, its text wrapped and
// drew OVER the mileage, and the organization ran off the right edge and was
// cut. A hiker reported it from a desktop build, where the frame is wider and
// it collided anyway. Measured against the published `stewards.json`
// (2026-08-27), `oprhp_trails` carries 68 characters, so no unusual name was
// needed to get there.
//
// WHAT FIXED IT is not this file's subject: the organization came off the row
// (screens/DayHikeCard.tsx's header has the reasoning and the check that it is
// not an attribution obligation), and with it gone the collision has no cause.
// screens/DayHikeCard.test.tsx is where THAT is pinned, in both spellings.
//
// WHAT THIS FILE PINS is the guard that keeps it from coming back: the row is
// a wrapping flex line, so an item too long for it moves to the next line
// rather than drawing over its neighbour - whatever a later change adds to the
// row. A two-column grid would render correctly today and quietly reintroduce
// #1112 the first time a third part is added back.
//
// Resolved from the Vitest root (client/), which vite.config.ts pins.

import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const CARD = readFileSync(resolve(process.cwd(), 'src/screens/DayHikeCard.tsx'), 'utf8')
const CSS = readFileSync(resolve(process.cwd(), 'src/screens/plan.css'), 'utf8')

/** One selector's declarations, comments stripped - so a comment naming a
 *  property does not count as the property being set. */
function declarationsOf(selector: string): string {
  const bare = CSS.replace(/\/\*[\s\S]*?\*\//g, '')
  const at = bare.indexOf(`${selector} {`)
  if (at === -1) throw new Error(`no rule for ${selector} in plan.css`)
  return bare.slice(at, bare.indexOf('}', at))
}

describe('the day-hike card’s rows', () => {
  // poiCardChipLayout.test.ts's point, and it applies with full force here:
  // a rule whose selector matches no element is exactly as absent as a
  // deleted one, so every assertion below is worth nothing unless the
  // classes are really on the markup.
  it('puts these classes on the rows the card actually renders', () => {
    expect(CARD).toMatch(/className="day-hike-card__row"/)
    expect(CARD).toMatch(/className="day-hike-card__row-name"/)
    expect(CARD).toMatch(/className="day-hike-card__row-figures"/)
  })

  it('lets a row wrap instead of overflowing, which is the fix', () => {
    const row = declarationsOf('.day-hike-card__row')

    expect(row).toMatch(/display:\s*flex/)
    expect(row).toMatch(/flex-wrap:\s*wrap/)
    // The grid is the defect, not a second way of spelling the same layout:
    // its `auto` tracks are what could overflow the card in the first place.
    expect(row).not.toMatch(/display:\s*grid/)
    expect(row).not.toMatch(/grid-template-columns/)
  })

  it('keeps no rule for the organization that left the row', () => {
    // The org came off the row, so its rule went with it. Asserted rather than
    // just deleted: a stylesheet keeping `.day-hike-card__row-org` alive is an
    // invitation to put the span back without re-reading why it went, which is
    // how #1112 would return wearing the same 68-character name.
    expect(CSS).not.toMatch(/\.day-hike-card__row-org\s*\{/)
    expect(CARD).not.toMatch(/day-hike-card__row-org/)
  })

  it('still refuses to break the mileage, which is a different kind of text', () => {
    // "0.4 mi" split across two lines reads as a different number at a
    // glance. This is the one part of the row that keeps `nowrap`, so the
    // test above cannot be satisfied by deleting `nowrap` everywhere.
    expect(declarationsOf('.day-hike-card__row-figures')).toMatch(/white-space:\s*nowrap/)
  })

  it('leaves the trail name holding the slack', () => {
    // What keeps the one-line arrangement wherever the row still fits, so the
    // fix degrades the layout only on the rows that were broken anyway.
    const name = declarationsOf('.day-hike-card__row-name')

    expect(name).toMatch(/flex:\s*1\s/)
    expect(name).toMatch(/min-width:\s*0/)
  })

  it('drops the variant whose only job was ordering grid columns', () => {
    // `.day-hike-card__row--mile` existed to re-order `auto 1fr auto` so a
    // way-off row leads with its mile. DOM order does that under flex, so the
    // rule went - and the class went from the markup with it, because a class
    // in the markup with no rule behind it reads as styling that is missing
    // rather than styling that is unnecessary.
    expect(CSS).not.toMatch(/\.day-hike-card__row--mile\s*\{/)
    expect(CARD).not.toMatch(/day-hike-card__row--mile/)
  })
})
