// One notice made recent, for the one test whose subject is freshness.
//
// WHY THIS EXISTS (#1426). `flow-data` runs against real published bytes, and
// for nearly everything in the suite that is the point: a test that invents a
// shelter proves nothing about a release. The "new trail notice" badge is the
// exception, because what it asserts is not a shape but an AGE.
// `newNoticesSince()` (client/src/lib/notices.ts) counts a notice as new while
// `now - updated_at` is inside `NEW_NOTICE_WINDOW_MS`, which is 72 hours, and
// `updated_at` is the organization's own edit timestamp carried through from
// their site. So the test as written asserted that ATC had published something
// in the preceding three days.
//
// They had not, and the check went red on `main` and on every pull request
// behind it. Measured 2026-09-15 against the bucket `flow-data` reads: the
// newest ATC notice was 2026-09-11T20:52:53Z, so the window closed at
// 2026-09-14 20:52:53Z and stayed closed. The median gap between consecutive
// ATC edits over the 38 published notices is 167 hours - seven days, against a
// three-day window - and 26 of the 37 gaps are longer than the window. A quiet
// week upstream is the ordinary case, not an outage.
//
// WHAT THIS DOES NOT DO. It does not pin the clock, and it does not invent an
// artifact. The real response is fetched, parsed, and handed back with ONE
// field moved: the newest row's `updated_at`. Every other byte is the
// published one - the count, the ids, the titles, the source keys, the shape
// the rest of the spec reads. So the test still runs against the release, and
// the only thing it stops depending on is whether a third party happened to
// post this week.
//
// WHY NOT THE OTHER THREE. Bumping `DATA_RELEASE` cannot work: `conditions/`
// is root-scoped (client/src/lib/dataRelease.ts's `ROOT_SCOPED_PREFIXES`), so
// the notices are not in the release at all and the pin never appears in their
// URL - tried in PR #1425 and it changed nothing. Pinning the clock with
// `page.clock` needs a moment inside the window of whatever the bucket
// currently holds, which is a moving target, so the clock ends up chasing the
// same upstream. Widening the window would fix the test by changing what a
// hiker sees, which is a product decision and belongs to whoever takes the
// badge's own coverage question rather than to a test trying to go green.
//
// SEPARATE FROM THIS, AND NOT FIXED HERE: the same measurement says the badge
// is dark most of the time in production. It is lit on 40.7% of days over the
// last 90, and 26.0% over the last year - and it is the only prompt telling a
// hiker to go and read notices, which carry closures. That is a live question
// about `NEW_NOTICE_WINDOW_MS`, tracked on #1442; nothing here changes what any
// hiker sees.

import type { Page } from '@playwright/test'

/** The published artifact the badge is computed from. Matched as a glob so it
 *  holds for whichever base the run points at - `flow-data` reads UA, a laptop
 *  may read production, and neither spelling belongs in a spec. */
const ATC_UPDATES = '**/conditions/atc_updates.json'

/** How far inside the window the freshened notice lands. An hour rather than a
 *  minute so a slow run cannot drift it back out, and well short of 72 so the
 *  test is not asserting the boundary - `notices.test.ts` owns the edges. */
const FRESH_BY_MS = 60 * 60 * 1000

interface NoticeRow {
  updated_at?: string
  [key: string]: unknown
}

/**
 * Makes the newest ATC notice recent, for every page in this page's context.
 *
 * ON THE CONTEXT, NOT THE PAGE, because the test that needs this boots a
 * second page to prove the watermark survives a cold start
 * (`bootFreshPage`) - and the two pages must agree about what the bucket
 * says, or the second one is answering a different question from the first.
 *
 * Call it before the navigation that loads the app.
 */
export async function freshenNewestNotice(page: Page): Promise<void> {
  // ONE TIMESTAMP FOR THE WHOLE TEST, computed here rather than per request,
  // and the reason is the thing the test it serves is about. The watermark a
  // hiker spends by reading the list is stored as "seen through <edit time>";
  // recomputing this inside the handler hands the second page an edit time
  // LATER than the watermark the first page wrote, so the badge comes back
  // across the cold boot - a badge that came back, which is the exact failure
  // the test calls worse than no badge. Found by that assertion going red.
  const freshAt = new Date(Date.now() - FRESH_BY_MS).toISOString()

  await page.context().route(ATC_UPDATES, async (route) => {
    const response = await route.fetch()
    const document = (await response.json()) as Record<string, unknown>

    const rows = Object.values(document).find(Array.isArray) as NoticeRow[] | undefined
    if (rows === undefined || rows.length === 0) {
      // Loudly, rather than continuing with the real bytes: a silent
      // fall-through would put the test back on ATC's posting cadence, which
      // is the whole thing this removes, and it would fail later wearing the
      // original defect's face.
      throw new Error(
        `${ATC_UPDATES} carried no array of notices, so there is nothing to freshen - ` +
          'the artifact has changed shape and e2e/support/freshNotice.ts needs to follow it.',
      )
    }

    let newest: NoticeRow | undefined
    for (const row of rows) {
      if (typeof row.updated_at !== 'string') continue
      if (newest === undefined || row.updated_at > (newest.updated_at as string)) {
        newest = row
      }
    }
    if (newest === undefined) {
      throw new Error(
        `no row in ${ATC_UPDATES} carries an \`updated_at\`, which is the field ` +
          '`noticeUpdatedAt` reads - the artifact has changed shape and ' +
          'e2e/support/freshNotice.ts needs to follow it.',
      )
    }

    newest.updated_at = freshAt
    await route.fulfill({ response, json: document })
  })
}
