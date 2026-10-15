// docs.ourhike.org/data/quality/'s Show menu open on a laptop, drawn from the
// INVENTED many-problems files in site/src/lib/dataQualityExamples.mjs
// (pipeline/ELT.md decision 102).
//
// WHAT CHANGED, AND IS IN THIS FRAME. The review of #1805 (2026-10-15, thread
// 4279330043): UA's hourly file put 127 options under one "Needs a look"
// group, 97 of them one kind's. The menu now groups them by kind, in the
// order of the five kinds of check - "Needs a look · Volume", then
// "Needs a look · Anomalies" here, the two kinds with a history in these
// files - and "Every finished table" stays last. Freshness has no group: a
// source's freshness has no history to chart since decision 203.
//
// WHY A RECIPE OF ITS OWN. Every other frame shows the menu closed, and a
// closed menu shows one option. The list is drawn in the site's own type on
// a laptop (site.css, "THE LIST DRAWN IN THE SITE'S OWN TYPE"); a phone opens
// its own picker, which no recipe can photograph.
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
  "docs.ourhike.org/data/quality/'s Show menu open on a laptop, from INVENTED example files (no release carries the file yet): Needs a look's charts grouped by kind, Volume then Anomalies, above Every finished table. Nothing in this frame was measured."
export const alt =
  'The data quality page at desktop width, scrolled to the chart\'s card, with a dashed amber pill saying the figures are invented at its top. Beside "Show", the select reading "Null rate of trail_status in trail_lines · Monthly" is open over the chart: a white list with a soft shadow, starting on the last options of the first group, "Rows in preview_fixture_19__closures · Hourly" and "Rows in warnings · Hourly", then small grey capitals "NEEDS A LOOK · ANOMALIES" over eight options, the first, "Null rate of trail_status in trail_lines · Monthly", in bold with a check mark, and at the bottom "EVERY FINISHED TABLE" over "Rows in trail_network · Monthly".'

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
  await page.locator('[data-chart-svg] svg').waitFor()
  await labelInvented(page, { before: page.locator('#dq-chart-title') })
  await scrollToTop(page.locator('#dq-chart'), 72)
  const menu = page.locator('#dq-show')
  await menu.click()
  // The list opens scrolled to the chosen option, the first anomaly's. Its
  // group's heading is brought to the middle of the list, so the end of the
  // Volume group shows above it and Every finished table's heading below.
  await menu
    .locator('optgroup')
    .nth(1)
    .evaluate((group) => group.scrollIntoView({ block: 'center' }))
}
