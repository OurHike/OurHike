// ourhike.org/data/quality/'s "Needs a look" on a laptop, on a bad day:
// drawn from the INVENTED many-problems files in
// site/src/lib/dataQualityExamples.mjs (pipeline/ELT.md decision 102).
//
// WHAT CHANGED, AND IS IN THIS FRAME. The maintainer's round-3 choice by
// poll on 2026-10-08: every check that failed or could not run is listed in
// full, and the warnings are folded one closed line per kind; the chart below
// gains a Show menu, and each row with a history a Chart button. The frame
// stops on the last failures, so it holds all three: rows with "Could not
// run" pills, the four folded lines, and the chart's title over its menu.
// Since the maintainer's answers to round 3's forks (2026-10-08), the line
// under that title names the row the first chart came from, whose Chart
// button starts pressed; every kind here holds 4 or more warnings, so all
// four stay folded.
//
// WHY INVENTED. No published release carries the file yet. The label goes
// above the folded warnings, because this frame is scrolled past the lede
// where data-quality.mjs puts it.
//
// THE CLOCK IS THE EXAMPLES' OWN, as in data-quality.mjs, so the rows' "Since"
// dates and the cards' ages read the same whenever the frame is taken.
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
  'ourhike.org/data/quality/ on a laptop, from INVENTED example files with 43 entries (no release carries the file yet): the checks that could not run listed in full above the 35 warnings, folded one line per kind, and the chart below with its new Show menu. Nothing in this frame was measured.'
export const alt =
  'The data quality page at desktop width, scrolled into its "Needs a look" list. White rows each name a kind of check and a table in code type - Volume, Freshness, Anomalies - with a red "Could not run" pill on the right and the sentence "The check could not run, so this went unchecked at this build." Below them a dashed amber pill says the figures are invented, and a bold line, "Warnings · 35, by kind", heads four white bars, each with an amber triangle, a kind and a count - "Freshness · 8 warnings", "Volume · 14 warnings", "Schema · 6 warnings", "Anomalies · 7 warnings" - and a downward chevron on the right. At the bottom a white card begins with the serif title "Null rate of trail_status in trail_lines, one point per monthly build", a grey line under it reading "Charted from Needs a look · trail_lines · trail_status · Back to the row" with the last words a link, and "Show" beside a select reading "Null rate of trail_status in trail_lines · Monthly".'

export const desktop = true

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
  await page.getByRole('heading', { name: 'Needs a look' }).waitFor()
  await labelInvented(page, { before: page.locator('.dq-look__subhead').nth(1) })
  // From the sixth row, the second that could not run, down to the chart's
  // menu fits one laptop window.
  await scrollToTop(page.locator('#dq-row-5'), 24)
}
