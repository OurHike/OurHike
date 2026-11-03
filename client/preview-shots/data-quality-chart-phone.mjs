// docs.ourhike.org/data/quality/'s chart on a phone, drawn from the INVENTED
// many-problems files in site/src/lib/dataQualityExamples.mjs, with the maximum of elevation's gain_ft chosen in the Show
// menu.
//
// WHAT CHANGED, AND IS IN THIS FRAME. The review of #1805 (2026-10-15, thread
// 4279330043) found the label beside a flagged point running left over the
// y-axis's labels on a 390 px phone. site/src/lib/dataQualityHtml.mjs's
// flaggedLabel() now keeps it inside the plot: beside its point on the side
// with room for the whole label, or, where neither side has, the shorter
// "Flagged as high", the value being in the sentence under the chart. Here
// the whole label fits, left of the point. The label the review saw run over
// the axis was a source's freshness history ("41 days between updates,
// flagged as high", 249 px measured), which went when freshness became our
// last read of a source, along with the history, and no example label left is that long, so this frame shows
// the placement holding at a phone's width rather than the fault itself;
// dataQualityHtml.test.mjs holds every example label inside the plot from
// 300 to 1300 px.
//
// WHY A RECIPE OF ITS OWN. data-quality-chart.mjs is a laptop's, where the
// label has room, and data-quality-by-mart-phone.mjs stops above the chart.
//
// THE MENU HERE IS THE PHONE'S OWN. A touch screen keeps the system's select
// (site.css, "THE LIST DRAWN IN THE SITE'S OWN TYPE"), so the other half of
// the same review - a styled select at 390 px cutting its chosen option's
// wrapped lines - is a mouse's frame, which no recipe takes: the camera's
// phone has a touch screen.
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

/** The chart this frame chooses, by the menu's own value (dataQuality.mjs's seriesKey). */
const ELEVATION_MAX = JSON.stringify(['monthly', 'elevation', 'gain_ft', 'max'])

export const caption =
  "docs.ourhike.org/data/quality/'s chart on a phone, from INVENTED example files (no release carries the file yet): the flagged point's label stays inside the plot, clear of the y-axis's numbers. Nothing in this frame was measured."
export const alt =
  'The data quality page at phone width, scrolled to a white card. A dashed amber pill says the figures are invented. Under it "Show" over a full-width select reading "Maximum of gain_ft in elevation · M", cut at the right edge as a phone\'s select is, then a key: a dark line "Maximum at each point", a pale green swatch "Usual range" and an amber triangle "Flagged by Elementary". The chart\'s axis runs from 0 to 10,000 in steps of 2,500. A dark line holds near 2,500 from Nov 2025 to Sep 2026 inside a thin pale green band, then climbs steeply to an amber triangle at the top right, Oct 2026, with the bold label "Maximum: 9,812, flagged as high" to its left, starting clear of the "10,000" on the axis. Under the chart a grey paragraph begins "12 monthly builds, from 2,860 on 6 Nov 2025 to 9,812 on 7 Oct 2026."'

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
  await page.locator('#dq-show').selectOption(ELEVATION_MAX)
  await page.locator('#dq-chart-title').getByText('gain_ft').waitFor()
  await labelInvented(page, { before: page.locator('.dq-show') })
  await scrollToTop(
    page.getByText('Invented figures, routed in by the preview recipe.'),
    16,
  )
}
