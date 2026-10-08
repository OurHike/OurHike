// /data/quality/ for the camera, drawn from INVENTED data_quality.json files,
// because no published release carries one yet (pipeline/ELT.md decision 102,
// step 4: the file starts with the build that runs the checks). A recipe's
// `before`, after serveMarketingSite (fixtures/marketingSite.mjs), whose
// catch-all route these two override.
//
// THE PAGE AS A DEPLOY WOULD SERVE IT. site/dist holds the page with its two
// placeholders; .github/scripts/configure_quality_page.py replaces them when
// pages.yml or pr-preview.yml assembles the site, which is after the camera
// runs. So this answers /data/quality/ with the same two replacements made:
// the client's own DATA_RELEASE, and a data base on `.invalid`, a name that
// can never resolve, so nothing the page asks for here can leave the runner
// or read the real bucket.
//
// NOBODY'S DATA, and nothing measured. The files are
// site/src/lib/dataQualityExamples.mjs's, the same ones the site's tests read;
// that module says how they are invented and why their tables are named for
// `preview_fixture`.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import {
  hourlyWithWarning,
  monthlyWithWarnings,
} from '../../../site/src/lib/dataQualityExamples.mjs'

const PAGE = fileURLToPath(
  new URL('../../../site/dist/data/quality/index.html', import.meta.url),
)
const DATA_RELEASE_TS = fileURLToPath(
  new URL('../../src/lib/dataRelease.ts', import.meta.url),
)

/** Where the page is told its data is: a host that cannot exist. */
export const EXAMPLE_BASE = 'https://data-quality-example.invalid'

/**
 * Serve /data/quality/ pointed at EXAMPLE_BASE, and answer EXAMPLE_BASE with
 * `monthly` and `hourly` - invented files, or null for "not published" (404).
 * Throws when site/dist is not built, which the runner turns into a sentence
 * in the comment rather than a photograph of the wrong page.
 *
 * Typed loosely on purpose: a spec passes any of the examples' files, whose
 * shapes differ, and the page itself is what judges a file.
 *
 * @param {import('playwright').Page} page
 * @param {{ monthly?: object | null, hourly?: object | null }} [files]
 */
export async function serveDataQuality(
  page,
  { monthly = monthlyWithWarnings(), hourly = hourlyWithWarning() } = {},
) {
  const html = readFileSync(PAGE, 'utf8')
  const release = /^export const DATA_RELEASE = '(.*)'$/m.exec(
    readFileSync(DATA_RELEASE_TS, 'utf8'),
  )?.[1]
  if (!release) throw new Error('could not read DATA_RELEASE out of dataRelease.ts')
  const served = html
    .replace('__DATA_BASE_URL__', EXAMPLE_BASE)
    .replace('__DATA_RELEASE__', release)

  await page.route('**/data/quality/', (route) =>
    route.fulfill({ status: 200, contentType: 'text/html; charset=utf-8', body: served }),
  )
  await page.route(`${EXAMPLE_BASE}/**`, (route) => {
    const path = new URL(route.request().url()).pathname
    const file = /^\/releases\/[^/]+\/data_quality\.json$/.test(path)
      ? monthly
      : path === '/conditions/data_quality.json'
        ? hourly
        : null
    if (file === null) return route.fulfill({ status: 404, body: '' })
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(file),
    })
  })
}

/**
 * Say on the frame itself that its figures are invented, in the dashed pill
 * mock B carried for the same reason ("Example figures for this mock-up.
 * Nothing here was measured."), so the picture cannot travel without the
 * sentence. Under the lede, where the mock put it; styled from the site's own
 * aliases, because the real page has no such element to style.
 *
 * `before` puts it ahead of another element instead, for a frame scrolled
 * past the lede, so the frame still says it wherever the camera stops - in
 * the page's flow, where it covers nothing the frame is there to show.
 */
export async function labelInvented(page, { before = null } = {}) {
  const anchor = before ?? page.locator('.dq-lede')
  await anchor.evaluate((node, ahead) => {
    const pill = document.createElement('p')
    pill.textContent =
      'Invented figures, routed in by the preview recipe. Nothing here was measured.'
    pill.style.cssText = [
      'display: inline-block',
      ahead ? 'margin-bottom: 12px' : 'margin-top: 12px',
      'padding: 4px 12px',
      'border: 1px dashed var(--border-2)',
      'border-radius: 999px',
      'font-size: 13px',
      'color: var(--fg-1)',
      'background: var(--surface-warning)',
    ].join(';')
    if (ahead) node.before(pill)
    else node.after(pill)
  }, before !== null)
}
