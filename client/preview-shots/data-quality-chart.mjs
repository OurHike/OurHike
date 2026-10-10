// ourhike.org/data/quality/'s chart on a laptop, drawn from the INVENTED light
// files in site/src/lib/dataQualityExamples.mjs (pipeline/ELT.md decision
// 102) that fixtures/dataQuality.mjs serves by default, so the chart is the
// rows of preview_fixture__trails, the series the maintainer's poll on the
// band was drawn from.
//
// WHAT CHANGED, AND IS IN THIS FRAME. Decision 118, the maintainer's poll of
// 2026-10-09 ("A: band from before"): the shaded band at each point is the
// band Elementary stored at the point before it. So at 7 Oct 2026, where the
// rows fall to 4,118, the band stays level at September's 5,199 to 5,322
// instead of fanning down to meet the fall, and the axis stops at 5,500
// rather than 7,000. The triangle is Elementary's own verdict, read from the
// entry that warned, and the key now names it "Flagged by Elementary". The
// caption under the chart says what the band is, and that a point can sit
// outside it unflagged; 7 Feb 2026 does (5,252 against 5,222 to 5,249), too
// close to see at this scale, and "The numbers behind the chart" lists it.
//
// RE-WORDED SINCE by the word-choice review of #1805 (2026-10-09): the key
// calls the band "Usual range", the rows' word for it, where it said
// "Expected range"; the triangle's label says "4,118 rows, flagged as low",
// the verdict's one wording on the page, where it said "below the range";
// and the caption says the band is "the usual range, from the monthly builds
// before each point", where it said "the range Elementary expected ... which
// does not count the point itself", the wording the maintainer called
// jargony in the rows on 2026-10-09.
//
// WHY A RECIPE OF ITS OWN. data-quality-needs-a-look.mjs stops at the chart's
// key, and data-quality.mjs and data-quality-by-mart-phone.mjs never reach
// the chart, so until this one no frame showed the band.
//
// WHY INVENTED, AND THE CLOCK, as in data-quality-needs-a-look.mjs: no
// published release carries the file yet, and the examples' own clock keeps
// the cards' ages the same whenever the frame is taken.
import { EXAMPLE_NOW } from '../../site/src/lib/dataQualityExamples.mjs'
import {
  openSitePage,
  scrollToTop,
  serveMarketingSite,
} from './fixtures/marketingSite.mjs'
import { labelInvented, serveDataQuality } from './fixtures/dataQuality.mjs'

export const caption =
  "ourhike.org/data/quality/'s chart on a laptop, from INVENTED example files (no release carries the file yet): each point drawn against the band from the builds before it, so the band stays level where the rows fall to 4,118, and a triangle on the point Elementary flagged. Nothing in this frame was measured."
export const alt =
  'The data quality page at desktop width, scrolled to a white card. A dashed amber pill says the figures are invented. Under it the serif title "Rows in preview_fixture__trails, one point per monthly build", a grey line "Charted from Needs a look · preview_fixture__trails · Back to the row", and a key: a dark line "Rows at each point", a pale green swatch "Usual range" and an amber triangle "Flagged by Elementary". The chart\'s axis runs from 4,000 to 5,500. A dark line holds level near 5,250 from Nov 2025 to Sep 2026 inside a thin pale green band that starts at Jan 2026, then drops steeply to an amber triangle at Oct 2026 labelled "4,118 rows, flagged as low", while the band carries on level above it to the right edge. Under the chart a grey paragraph begins "12 monthly builds, from 5,231 on 7 Nov 2025 to 4,118 on 7 Oct 2026. Elementary flagged 1 of them in its latest checks. The shaded band is the usual range, from the monthly builds before each point", and a closed "The numbers behind the chart" sits below it.'

export const desktop = true

export async function before(page) {
  await page.clock.setFixedTime(new Date(EXAMPLE_NOW))
  await serveMarketingSite(page)
  await serveDataQuality(page)
}

export default async function drive(page) {
  await openSitePage(page, '/data/quality/')
  await page.getByRole('heading', { name: 'Needs a look' }).waitFor()
  // The chart's SVG is drawn once the files are read; the band is in it.
  await page.locator('[data-chart-svg] svg').waitFor()
  await labelInvented(page, { before: page.locator('#dq-chart-title') })
  await scrollToTop(page.locator('#dq-chart'), 24)
}
