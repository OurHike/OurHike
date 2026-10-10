// ourhike.org/data/quality/'s "Needs a look" rows on a laptop, drawn from the
// INVENTED light files in site/src/lib/dataQualityExamples.mjs (pipeline/ELT.md
// decision 102) that fixtures/dataQuality.mjs serves by default.
//
// WHAT CHANGED, AND IS IN THIS FRAME. Decision 130, the maintainer's poll of
// 2026-10-09: a row quotes the range expected from the builds before, the band
// the chart draws at the same build, where it quoted the range Elementary
// scored the value against, which counts the value itself. So the row on
// preview_fixture__trails reads "4,118 rows in this build, below the usual
// 5,199 to 5,322", where it read "below the 4,174 to 6,156 Elementary
// expected". Since the word-choice review of #1805 (2026-10-09), every row
// says "in this build" where it said "at this build", and the schema row says
// "Its columns changed since the last build." where it said "Its columns no
// longer match what Elementary expected.": a schema_changes check compares
// the table with the build before, so that is what changed means here. The light files carry no history for the null rate of
// trail_lines.surface or for preview_fixture__alerts' time between updates
// (the contract's first shape), so those two rows say which side Elementary
// flagged each on and that there is no earlier range: "flagged as high. No
// earlier range to compare it with." The words are the maintainer's ask of
// the same day, shown the first wording: "both of those are jargony ... be
// more concise and simple".
//
// WHY A RECIPE OF ITS OWN. data-quality-needs-a-look.mjs frames the heavy
// files from their sixth row, whose rows could not run and quote no range, and
// its warnings stay folded; the other three never reach a row. So until this
// one no frame showed a row's range.
//
// WHY INVENTED, AND THE CLOCK, as in data-quality-needs-a-look.mjs: no
// published release carries the file yet, and the examples' own clock keeps
// the rows' "Since" dates and the cards' ages the same whenever the frame is
// taken.
import { EXAMPLE_NOW } from '../../site/src/lib/dataQualityExamples.mjs'
import {
  openSitePage,
  scrollToTop,
  serveMarketingSite,
} from './fixtures/marketingSite.mjs'
import { labelInvented, serveDataQuality } from './fixtures/dataQuality.mjs'

export const caption =
  "ourhike.org/data/quality/'s Needs a look on a laptop, from INVENTED example files (no release carries the file yet): the row on preview_fixture__trails quotes the usual 5,199 to 5,322 rows, the range the chart draws at that build, and the two rows whose files carry no history say they have no earlier range. Nothing in this frame was measured."
export const alt =
  'The data quality page at desktop width, scrolled to a dashed amber pill saying the figures are invented, above the serif heading "Needs a look" and a bold line "Warnings · 4, by kind". Four open white folds follow, each headed by an amber triangle, a kind and "1 warning", and each holding one row: an amber stripe on its left, the kind and a table in code type, a sentence, and on the right an amber "Warned" pill over its lane and since when. Freshness, on preview_fixture__alerts: "26 hours between updates in this build, flagged as high. No earlier range to compare it with." Volume, on preview_fixture__trails, with a dark green "Chart" button: "4,118 rows in this build, below the usual 5,199 to 5,322." Schema, on preview_fixture__trails and trail_class: "Its columns changed since the last build." Anomalies, on trail_lines and surface, at the bottom edge: "Null rate: 4.2% in this build, flagged as high. No earlier range to compare it with."'

export const desktop = true

export async function before(page) {
  await page.clock.setFixedTime(new Date(EXAMPLE_NOW))
  await serveMarketingSite(page)
  await serveDataQuality(page)
}

export default async function drive(page) {
  await openSitePage(page, '/data/quality/')
  await page.getByRole('heading', { name: 'Needs a look' }).waitFor()
  await labelInvented(page, { before: page.locator('#dq-look-title') })
  await scrollToTop(page.locator('section[aria-labelledby="dq-look-title"]'), 24)
}
