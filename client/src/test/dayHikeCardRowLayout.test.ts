// The day-hike card's leg and way-off rows, pinned as a contract (#1112).
//
// jsdom does no layout, so - as with poiCardChipLayout.test.ts,
// hiddenInputContainment.test.ts and desktopLayout.test.ts - what is asserted
// here is the stylesheet's text. A rendering test can prove the row's three
// parts are on screen and cannot prove they are not drawn on top of each
// other, which is the entire defect this file exists for.
//
// WHAT BROKE. The row was `grid-template-columns: 1fr auto auto` with both
// trailing columns `white-space: nowrap`. An `auto` track sized by unbreakable
// text claims whatever width that text needs and then overflows the card: the
// `1fr` name track collapses to its `min-width: 0` floor, its text wraps and
// draws OVER the mileage, and the organization runs off the right edge and is
// cut. A hiker reported it from a desktop build, where the frame is wider and
// it collides anyway.
//
// WHY IT IS THE ORDINARY CASE AND NOT AN EDGE ONE. Measured against the
// published `stewards.json` (2026-08-27):
//
//     oprhp_trails       New York State Office of Parks,
//                        Recreation and Historic Preservation      68 chars
//     usdm_drought       National Drought Mitigation Center,
//                        University of Nebraska-Lincoln            66
//     dec_hiking_trails  New York State Department of
//                        Environmental Conservation                55
//
// Three of the six published stewards are past 55 characters, and the first
// and third cover much of the ground day hikes get built on. Nothing local
// reproduces it - a sandbox build has no stewards export, so `orgLabelFrom`
// falls back to the raw key (`oprhp_trails`, 12 characters) and the row fits.
// That is why this is pinned in the stylesheet rather than left to a preview
// somebody might not look at.
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
    expect(CARD).toMatch(/className="day-hike-card__row-org"/)
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

  it('never lets the organization be clipped at the card’s edge', () => {
    // The assertion this whole file is for. `nowrap` on a steward's name is
    // what pushed it off the card - and an ellipsis would be no better, which
    // is why the rule wraps the name rather than shortening it: naming an
    // organization and then declining to name it is a display outrunning its
    // source in the other direction.
    const org = declarationsOf('.day-hike-card__row-org')

    expect(org).not.toMatch(/white-space:\s*nowrap/)
    expect(org).not.toMatch(/text-overflow:\s*ellipsis/)
    // Allowed below its longest word, so a 68-character name wraps inside its
    // own box rather than widening the row until something overflows.
    expect(org).toMatch(/min-width:\s*0/)
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
