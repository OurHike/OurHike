// ourhike.org/data/quality/ on a laptop, drawn from INVENTED data_quality.json
// files (pipeline/ELT.md decision 102, step 4) - the page mock B laid out,
// which the maintainer chose by poll on 2026-10-07.
//
// WHY INVENTED. No published release carries the file yet: it starts with the
// first build that runs Elementary's checks. fixtures/dataQuality.mjs routes
// in the site's own example files and labels the frame as invented, and the
// caption says it again, so the picture cannot be taken for a measurement.
//
// WHAT TO LOOK FOR, against mock B: the "Data docs" / "Data quality" tabs
// under the site's own nav; both build cards with their passed, warning and
// failed counts; the five kinds of check, each with what needs a look in it.
// Everything is drawn from the files: change one count in
// site/src/lib/dataQualityExamples.mjs and this frame changes with it.
//
// FROM THE TABS DOWN, because the site's nav above them is every page's and
// is not what this pull request changed; the chart and the per-mart table are
// further down the same page.
//
// THE CLOCK IS THE EXAMPLES' OWN. The cards say how long ago each build ran,
// by the page's clock, so it is fixed an hour after the invented hourly run:
// otherwise every later pull request would photograph "last run ... 40 days
// ago" and the hourly lane would look stalled.
import { EXAMPLE_NOW } from '../../site/src/lib/dataQualityExamples.mjs'
import {
  openSitePage,
  scrollToTop,
  serveMarketingSite,
} from './fixtures/marketingSite.mjs'
import { labelInvented, serveDataQuality } from './fixtures/dataQuality.mjs'

export const caption =
  'ourhike.org/data/quality/ on a laptop, from INVENTED example files (no release carries the file yet): the data tabs, both build cards and the five kinds of check. Nothing in this frame was measured.'
export const alt =
  'The data quality page at desktop width. A white band holds two tabs, "Data docs" and "Data quality", the second highlighted in pale green. Below, the eyebrow "ourhike.org/data/quality", the serif heading "Data quality", a grey paragraph saying the page shows counts and table names, never rows, and a dashed amber pill reading "Invented figures, routed in by the preview recipe. Nothing here was measured." Two white cards side by side, "Monthly build" and "Hourly conditions", each with a line naming when it was built and three pills - a number passed with a green check, a number of warnings with an amber triangle, and "0 failed" - then the heading "The five kinds of check" over five cards: Freshness, Volume, Schema, dbt tests and Anomalies, each with an amber "1 late"-style pill or a green "All pass", a large count of checks passed and a short note naming a table.'

export const desktop = true

export async function before(page) {
  await page.clock.setFixedTime(new Date(EXAMPLE_NOW))
  await serveMarketingSite(page)
  await serveDataQuality(page)
}

export default async function drive(page) {
  await openSitePage(page, '/data/quality/')
  await page.getByRole('heading', { name: 'Needs a look' }).waitFor()
  await labelInvented(page)
  await scrollToTop(page.locator('nav.data-nav'), 0)
}
