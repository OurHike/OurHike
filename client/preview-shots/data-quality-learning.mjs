// ourhike.org/data/quality/ on a laptop while the anomaly checks are still
// learning, drawn from the INVENTED learning files in
// site/src/lib/dataQualityExamples.mjs (pipeline/ELT.md decision 102): the
// monthly build is the third of the 11 an anomaly check needs before it can
// flag anything, and every check of the hourly run passed.
//
// WHY A RECIPE OF ITS OWN. This is the one state that shows the monthly
// card's "Learning, 3 of 11 builds" and the sentence under it, and the one
// where all five kinds of check say what they cover: a kind with something to
// look at shows that instead. No recipe reached it, so the word-choice review
// of #1805 (2026-10-09), which re-worded both, had no frame to be checked in.
//
// WHAT TO LOOK FOR. The card: "Its anomaly checks compare each build with the
// ones before it, and can't flag anything until they have 11 builds, this one
// included. Until then they pass even if something is wrong." Under
// Freshness, Volume and Anomalies, the same caveat beside each "All pass":
// "Learning, 3 of 11 monthly builds: until then its anomaly checks can't flag
// anything." And the five cards' sentences, with none of the pipeline's words
// ("raw table", "mart", "retyped upstream", "phone file", "safety columns").
//
// WHY INVENTED, AND THE CLOCK, as in data-quality-needs-a-look.mjs: no
// published release carries the file yet, and the examples' own clock keeps
// the cards' ages the same whenever the frame is taken.
import {
  EXAMPLE_NOW,
  hourlyAllGreen,
  monthlyLearning,
} from '../../site/src/lib/dataQualityExamples.mjs'
import {
  openSitePage,
  scrollToTop,
  serveMarketingSite,
} from './fixtures/marketingSite.mjs'
import { labelInvented, serveDataQuality } from './fixtures/dataQuality.mjs'

export const caption =
  'ourhike.org/data/quality/ on a laptop while the anomaly checks are learning, from INVENTED example files (no release carries the file yet): the monthly card says they can’t flag anything until 11 builds, and each kind of check says what it covers. Nothing in this frame was measured.'
export const alt =
  'The data quality page at desktop width, scrolled to a dashed amber pill saying the figures are invented, above two white cards. "Monthly build" reads "Release 2026-10-03-2 · built 7 Oct 2026, 06:12 UTC, 17 hours ago", three pills with 0 warnings and 0 failed, and a learning line, "Learning, 3 of 11 builds", with a sentence saying its anomaly checks cannot flag anything until they have 11 builds and pass until then even if something is wrong. "Hourly conditions" beside it has every check passed. Below, the heading "The five kinds of check" over five cards - Freshness, Volume, Schema, dbt tests and Anomalies - each with a green "All pass", a large count, a sentence saying what that kind of check looks at, and on Freshness, Volume and Anomalies the line "Learning, 3 of 11 monthly builds: until then its anomaly checks can’t flag anything."'

export const desktop = true

export async function before(page) {
  await page.clock.setFixedTime(new Date(EXAMPLE_NOW))
  await serveMarketingSite(page)
  await serveDataQuality(page, { monthly: monthlyLearning(), hourly: hourlyAllGreen() })
}

export default async function drive(page) {
  await openSitePage(page, '/data/quality/')
  await page.getByRole('heading', { name: 'Needs a look' }).waitFor()
  const runs = page.locator('section.dq-runs')
  await labelInvented(page, { before: runs })
  // The pill itself 16 px from the top, so the frame says in full that its
  // figures are invented, at either width; the cards and the five kinds of
  // check follow it. Scrolled to the cards at 64 px, it was cut at its top
  // edge on a laptop and to its last line on a phone (measured 2026-10-09).
  await scrollToTop(
    page.getByText('Invented figures, routed in by the preview recipe.'),
    16,
  )
}
