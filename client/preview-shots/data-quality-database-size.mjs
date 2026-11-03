// docs.ourhike.org/data/quality/'s hourly lane with OurHike's own database past
// its warning, on a laptop, drawn from the INVENTED file
// site/src/lib/dataQualityExamples.mjs's hourlyDatabaseNearItsLimit(): 415 MB,
// mock B's figure, which the maintainer chose from by poll on 2026-10-28
// ("Hourly dbt check, with megabytes"). Nothing else in the file warns, so the
// row and the whole chart fit the frame.
//
// WHAT TO LOOK FOR, against mock B. Under "Needs a look", a Volume row for
// base_ourhike__database_size on the hourly conditions run, warned, reading
// "415 MB in this build · limit 475 MB." - where mock B read "above the usual
// 300 to 400 MB": the check holds the size to fixed lines rather than to a
// range learned from the runs before, so the row names the size it fails at.
// Then the chart, which opens on the size's week of hourly runs: a line
// climbing from 305 MB to 415 MB, an amber dashed line at 400 MB ("warns
// 400 MB") and a red one at 475 MB ("fails 475 MB"), each named at its left
// end, no shaded band and no triangle, a key naming the two lines, and a
// caption saying what they are.
//
// WHY A RECIPE OF ITS OWN. The standing data-quality recipes route in files
// with no database size, and data-quality-chart.mjs photographs the band this
// chart does not have.
//
// WHY INVENTED, AND THE CLOCK, as in data-quality-chart.mjs: no published
// release carries the file yet, and the examples' own clock keeps the cards'
// ages the same whenever the frame is taken.
import {
  EXAMPLE_NOW,
  hourlyDatabaseNearItsLimit,
  monthlyAllGreen,
} from '../../site/src/lib/dataQualityExamples.mjs'
import {
  openSitePage,
  scrollToTop,
  serveMarketingSite,
} from './fixtures/marketingSite.mjs'
import { labelInvented, serveDataQuality } from './fixtures/dataQuality.mjs'

export const caption =
  "docs.ourhike.org/data/quality/'s hourly lane on a laptop, from an INVENTED example file (no release carries the file yet): OurHike's own database warned at 415 MB, its row naming the 475 MB it fails at, and its week charted against dashed lines at 400 MB and 475 MB. Nothing in this frame was measured."
export const alt =
  'The data quality page at desktop width, scrolled to "Needs a look". A dashed amber pill says the figures are invented. Under the heading, a row with an amber "Warned" pill, "Volume", the table name base_ourhike__database_size and "Hourly conditions", reading "415 MB in this build · limit 475 MB." Below it a white card titled "Database size in base_ourhike__database_size, one point per hourly run", with a key: a dark line "Database size at each point", an amber dashed rule "Warns from 400 MB" and a red dashed rule "Fails from 475 MB". The chart\'s dark line climbs steadily from about 305 MB on the left to 415 MB at the right edge, crossing an amber dashed line labelled at its left end "warns 400 MB"; a red dashed line labelled "fails 475 MB" runs above it. No shaded band and no triangle. Under the chart a grey paragraph: "168 hourly runs, from 305 MB on 1 Oct 2026 to 415 MB on 7 Oct 2026. The check warns from 400 MB and fails from 475 MB. The dashed lines are the sizes at which the check warns and fails."'

export const desktop = true

export async function before(page) {
  await page.clock.setFixedTime(new Date(EXAMPLE_NOW))
  await serveMarketingSite(page)
  await serveDataQuality(page, {
    monthly: monthlyAllGreen(),
    hourly: hourlyDatabaseNearItsLimit(),
  })
}

export default async function drive(page) {
  await openSitePage(page, '/data/quality/')
  await page.getByRole('heading', { name: 'Needs a look' }).waitFor()
  // The chart opens on the size's history, the one entry in the file with one.
  await page.locator('[data-chart-svg] svg').waitFor()
  await labelInvented(page, { before: page.locator('#dq-look-title') })
  // Room above the heading for the pill that says the figures are invented.
  await scrollToTop(page.locator('#dq-look-title'), 72)
}
