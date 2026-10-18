// docs.ourhike.org/data/quality/ on a laptop, drawn from INVENTED data_quality.json
// files - the page mock B laid out,
// which the maintainer chose by poll on 2026-10-07.
//
// WHY INVENTED. No published release carries the file yet: it starts with the
// first build that runs Elementary's checks. fixtures/dataQuality.mjs routes
// in the site's own example files and labels the frame as invented, and the
// caption says it again, so the picture cannot be taken for a measurement.
//
// WHAT TO LOOK FOR, against mock B: the "How the data is built" / "Data quality" tabs
// under the site's own nav; both build cards with their passed, warning and
// failed counts; the five kinds of check, each with what needs a look in it.
// Everything is drawn from the files: change one count in
// site/src/lib/dataQualityExamples.mjs and this frame changes with it.
//
// WHAT CHANGED SINCE, AND IS IN THIS FRAME: two kinds' notes. The
// maintainer's poll of 2026-10-09 makes "its usual range" on a kind's
// card the range expected from the builds before, the one its row quotes, so
// a card names a side of it only where that range gives the side Elementary
// flagged, and otherwise says which side Elementary flagged. The light files
// hold no history for the anomalies entry, so Anomalies reads "Null rate:
// 4.2%, flagged as high.", where it said "above its expected range";
// Freshness said the same of "26 hours between updates" until it became our
// last read of each source.
//
// AND THE WORD-CHOICE REVIEW OF #1805 (2026-10-09), in this frame: the
// monthly card's line starts "Release <the pinned id>" (2026-10-10-2 since
// 2026-10-15), not "Made release";
// Volume's note says "below its usual range", not "its expected range"; the
// two notes above say "flagged as high" where they said "flagged by
// Elementary", the verdict's one wording on the page now; and dbt tests,
// the one kind with nothing to look at, says what it covers in a visitor's
// words: "Unique IDs, required values filled in, links between tables, and
// each finished table's promised columns."
//
// AND DECISION 203 (the maintainer, 2026-10-15), in this frame: a source's
// freshness is measured from OurHike's last read of it, read or confirmed
// unchanged, against that source's own limits, so Freshness counts sources,
// "295 of 296 sources on time", where it said "checks on time", and its note
// reads "preview_fixture__alerts: read or confirmed 13 h ago · limit 24 h.",
// the words of the frame the maintainer was shown.
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
  "docs.ourhike.org/data/quality/ on a laptop, from INVENTED example files (no release carries the file yet): the data tabs, both build cards and the five kinds of check, Freshness counted in sources and timed from OurHike's last read of each. Nothing in this frame was measured."
export const alt =
  'The data quality page at desktop width. A white band holds two tabs, "How the data is built" and "Data quality", the second highlighted in pale green. Below, the eyebrow "docs.ourhike.org/data/quality", the serif heading "Data quality", a grey paragraph saying the page shows counts and table names, never rows, and a dashed amber pill reading "Invented figures, routed in by the preview recipe. Nothing here was measured." Two white cards side by side, "Monthly build" and "Hourly conditions", each with a line naming when it was built and three pills - a number passed with a green check, a number of warnings with an amber triangle, and "0 failed" - then the heading "The five kinds of check" over five cards: Freshness, Volume, Schema, dbt tests and Anomalies, each with an amber "1 late"-style pill or a green "All pass", a large count passed and a short note naming a table. Freshness reads "295 of 296 sources on time" and "preview_fixture__alerts: read or confirmed 13 h ago · limit 24 h."'

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
