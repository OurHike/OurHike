// ourhike.org/data/quality/'s "By mart" on a phone, drawn from the INVENTED
// many-problems files in site/src/lib/dataQualityExamples.mjs (pipeline/ELT.md
// decision 102).
//
// WHAT CHANGED, AND IS IN THIS FRAME. The maintainer's poll on 2026-10-08
// ("B: count under name"): on a phone the Checks column goes, each mart's
// lane and check count sit under its name ("Monthly · 412 checks"), and
// Result shrinks to its widest pill. Every one of the eleven mart names keeps
// to one line; beside a Checks column, points_of_interest broke in two at
// 390 px. A laptop keeps the four columns.
//
// WHY INVENTED, AND THE CLOCK, as in data-quality-needs-a-look.mjs: no
// published release carries the file yet, and the examples' own clock keeps
// the cards' ages the same whenever the frame is taken.
import {
  EXAMPLE_NOW,
  hourlyManyProblems,
  monthlyManyProblems,
} from '../../site/src/lib/dataQualityExamples.mjs'
import {
  openSitePage,
  scrollToTop,
  serveMarketingSite,
} from './fixtures/marketingSite.mjs'
import { labelInvented, serveDataQuality } from './fixtures/dataQuality.mjs'

export const caption =
  'ourhike.org/data/quality/ on a phone, from INVENTED example files (no release carries the file yet): By mart in two columns, each mart name on one line with its lane and check count under it. Nothing in this frame was measured.'
export const alt =
  'The data quality page at phone width, scrolled to the serif heading "By mart". Under it a white card holds a two-column table headed "Mart" and "Result". Each row names a mart in code type on one line - trail_lines, points_of_interest, trail_network, elevation, places, suggested_hikes - with a grey line under it such as "Monthly · 412 checks" and an outlined "Chart" button below that. On the right of each row are its pills: a red "2 failed" and an amber "2 warnings" for trail_lines, a red "1 failed" and an amber "2 warnings" for points_of_interest, one amber warning for most of the rest, and a red "1 could not run" under an amber warning for elevation. A dashed amber pill above the heading says the figures are invented.'

export async function before(page) {
  await page.clock.setFixedTime(new Date(EXAMPLE_NOW))
  await serveMarketingSite(page)
  await serveDataQuality(page, {
    monthly: monthlyManyProblems(),
    hourly: hourlyManyProblems(),
  })
}

export default async function drive(page) {
  await openSitePage(page, '/data/quality/')
  await page.getByRole('heading', { name: 'By mart' }).waitFor()
  await labelInvented(page, { before: page.locator('#dq-marts-title') })
  await scrollToTop(page.locator('#dq-marts-title'), 72)
}
