// The app's Content-Security-Policy, written once so the two places that serve
// it cannot disagree.
//
// WHAT IT IS FOR. `src/lib/safeLink.ts` checks the scheme of every URL the app
// renders as a link, and today that check is the ONLY thing between a bad URL
// and the Android WebView - `@capacitor/android` 8.5.1's `Bridge.launchIntent`
// hands any off-origin scheme to an `ACTION_VIEW` intent, and loads a tapped
// `data:` link in place of the app. A policy makes that check the second line
// rather than the only one. It is defence in depth and nothing more: there is
// no untrusted script on the page and no third-party frame. #1602 carries the
// argument and the staging.
//
// WHERE IT IS SERVED, AND WHERE IT CANNOT BE. Only the pull request preview
// carries it, as `Content-Security-Policy-Report-Only`, from two mouths that
// read this same function:
//
//   vite.config.ts        `vite preview`'s own response headers, so the camera
//                         in pr-preview.yml drives every shot recipe under the
//                         policy and a violation lands in the job log
//   pr-preview.yml        `_site/_headers` on the Cloudflare deployment, via
//                         the --headers CLI at the bottom of this file
//
// Production is GitHub Pages (`site/CNAME`, `pages.yml`) and GitHub Pages
// serves no custom headers at all - `pr-preview.yml` already says exactly that
// of `_redirects`, and `_headers` is the same story. So the route to an
// ENFORCED production policy is a `<meta http-equiv>` tag in index.html, and a
// meta tag cannot be report-only: the specification supports
// `Content-Security-Policy-Report-Only` as a header only. There is no
// report-only rehearsal available for production. The preview IS the
// rehearsal, which is the whole reason this string is shared rather than
// written twice.
//
// The Capacitor shells are untouched either way: they serve bundled assets
// from their own local server, which sets no headers and reads no `_headers`.
//
// WHAT THE REHEARSAL HAS ALREADY SHOWN, and what it has not. Driven
// 2026-09-23 against a real `VITE_BASE_PATH=/app/` build through `vite
// preview`, the first-run and today recipes report nothing under this policy.
// That number is only evidence because the control says so: the same driver
// against a deliberately impossible `img-src 'none'` reported four violations
// naming favicon.svg, so silence here is the browser agreeing rather than the
// listener being deaf. What it does NOT cover is every screen with a map on
// it - those recipes drive by tapping things that only exist once POI and
// trail artifacts have loaded, and a sandbox has no data to load. The preview
// is the first place this policy meets a map.
//
// NOTHING COLLECTS THE REPORTS. There is no `report-uri` and no `report-to`,
// so a violation appears in the browser console of whoever has the page open -
// which in CI is the camera, and in review is the reviewer. Wiring an endpoint
// is a decision about where a hiker's URL goes, so it is not made here.

/** Fixed in the source rather than named by an environment variable, which is
 *  why it needs no substitution: `src/map/liveTopo.ts` exports
 *  `OPENFREEMAP_TILEJSON = 'https://tiles.openfreemap.org/planet'`. The origin
 *  is taken rather than the path because the style document it returns points
 *  at tiles, glyphs and sprites on that same host. */
export const BASEMAP_ORIGIN = 'https://tiles.openfreemap.org'

/** Which environment variable each host comes from, and the only list of them.
 *
 *  `import.meta.env` is read in exactly four places in `client/src` (measured
 *  2026-09-21 against main at 79bc78b8); these are the three that name a host,
 *  the fourth being `BASE_URL`, which is a path. `policyFromEnv` reads the
 *  environment through this map rather than naming the variables again, so
 *  adding a fourth host is one edit and not two that can disagree. */
export const HOST_VARIABLES = {
  dataBase: 'VITE_DATA_BASE_URL',
  supabaseUrl: 'VITE_SUPABASE_URL',
  apiBase: 'VITE_API_BASE_URL',
}

/**
 * The origin of an absolute `http(s)` URL, or null for anything else.
 *
 * Null rather than a throw, and null rather than the string itself, because
 * the callers are a build and a deploy: an unset `VITE_API_BASE_URL` is the
 * normal state of a preview (pr-preview.yml declines to set it), and a policy
 * that answers that with `connect-src undefined` is a policy that names a host
 * nobody owns. Omitting the source is the honest reading of "we do not know
 * where this build talks to" - under report-only it costs a report, and under
 * the enforced policy this one rehearses it would cost the map.
 *
 * @param {string | undefined | null} url
 * @returns {string | null}
 */
export function originOf(url) {
  if (typeof url !== 'string' || url.trim() === '') return null
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'https:' || parsed.protocol === 'http:'
      ? parsed.origin
      : null
  } catch {
    return null
  }
}

/** Joins a directive's sources, dropping the nulls `originOf` produces and any
 *  host named twice - a build whose data and API share an origin should say it
 *  once. Insertion order is kept so the policy reads the same way every run,
 *  which is what lets a test diff two of them. */
function sources(...values) {
  const seen = []
  for (const value of values) {
    if (value !== null && value !== undefined && value !== '' && !seen.includes(value)) {
      seen.push(value)
    }
  }
  return seen.join(' ')
}

/**
 * The policy, as it is served on the preview.
 *
 * Every directive below was read out of a real `VITE_BASE_PATH=/app/` build of
 * `client/dist`, measured 2026-09-21 against main at 79bc78b8, rather than
 * picked from a template:
 *
 *   script-src 'self'       no inline `<script>` in dist/index.html or
 *                           dist/viewer.html - so no 'unsafe-inline' and no
 *                           hash list. vite-plugin-pwa's registerSW.js is a
 *                           same-origin file, not an inline block.
 *   worker-src 'self'       all six worker chunks are built from same-origin
 *                           `/app/assets/...` URLs (sha256Worker,
 *                           trailIndexWorker, poiIconWorker, demWorker,
 *                           mapWorker, maplibre-gl-worker). No `new
 *                           Worker(blob:...)` appears anywhere in the output,
 *                           so `blob:` is not in this directive.
 *   no 'unsafe-eval'        no .wasm in dist, and `new Function(` appears zero
 *                           times in the main chunk.
 *   img-src blob:           photo blobs are minted with `URL.createObjectURL`
 *                           in the MapScreen and main chunks.
 *   style/font: no host     `scripts/check-build-output.mjs` reports "no
 *                           cross-origin CSS, 10 UI font file(s) vendored and
 *                           precached" on every build, so a remote stylesheet
 *                           or font would already be failing that check.
 *   frame-ancestors 'none'  nothing in client/src or site/src renders an
 *                           `<iframe>`. An organization's embed is a `<script>`
 *                           tag on their own page, governed by their policy.
 *
 * Two are `@unvalidated`, and are the reason the preview runs report-only
 * rather than this being pasted straight into an enforced tag:
 *
 *   style-src 'unsafe-inline'  React writes `style` attributes and MapLibre
 *                              injects a stylesheet, and `style-src` covers
 *                              both. Kept because dropping it is the change
 *                              that would cost the map, and the rehearsal so
 *                              far cannot speak for the map: driving the
 *                              first-run and today recipes against a build
 *                              with `style-src 'self'` and no 'unsafe-inline'
 *                              produced zero reports (2026-09-23, chromium
 *                              1194 from the Playwright store, `vite preview`
 *                              over a real dist), but
 *                              every recipe that reaches a MAP screen needs
 *                              POI and trail artifacts and could not be driven
 *                              in a sandbox with no data. So the measurement
 *                              says those two screens do not need it, and says
 *                              nothing at all about the screens that matter.
 *                              The preview build has the data; its reports are
 *                              what settle this.
 *   child-src 'self'           carried as Safari's documented fallback for
 *                              `worker-src`, which matters because the iOS
 *                              shell is WebKit. Which WebKit versions still
 *                              need it has not been checked here; the line
 *                              costs nothing and removing it on a guess could
 *                              cost the map on one platform.
 *
 * @param {{ dataBase?: string | null, supabaseUrl?: string | null, apiBase?: string | null }} hosts
 * @returns {string}
 */
export function buildPolicy({ dataBase, supabaseUrl, apiBase } = {}) {
  const dataOrigin = originOf(dataBase)
  const supabaseOrigin = originOf(supabaseUrl)
  const apiOrigin = originOf(apiBase)

  const directives = [
    ['default-src', sources("'self'")],
    ['script-src', sources("'self'")],
    ['style-src', sources("'self'", "'unsafe-inline'")],
    ['font-src', sources("'self'")],
    ['img-src', sources("'self'", 'data:', 'blob:', BASEMAP_ORIGIN, dataOrigin)],
    [
      'connect-src',
      sources("'self'", BASEMAP_ORIGIN, dataOrigin, supabaseOrigin, apiOrigin),
    ],
    ['worker-src', sources("'self'")],
    ['child-src', sources("'self'")],
    ['manifest-src', sources("'self'")],
    ['form-action', sources("'self'")],
    ['base-uri', sources("'none'")],
    ['object-src', sources("'none'")],
    ['frame-src', sources("'none'")],
    ['frame-ancestors', sources("'none'")],
  ]

  return directives.map(([name, value]) => `${name} ${value}`).join('; ')
}

/** The path the `_headers` rule is written for.
 *
 *  `/app/*` rather than `/*` because this policy was measured against the app
 *  and the same deployment also carries the Astro marketing site at its root.
 *  A violation reported by the site would be a violation of a policy nobody
 *  wrote for it, and the first cost of a report-only run is that somebody
 *  believes the reports.
 *
 *  The splat matches `/app/` itself with nothing after it, so the app's own
 *  document is covered. What is NOT covered is `_site/404.html` - the app's
 *  shell, copied to the root so a console deep link boots the app on the
 *  preview - which is served at paths outside `/app/`. That is a gap in the
 *  rehearsal rather than in the app, and it is named here so the next reader
 *  does not have to find it. */
export const HEADERS_PATH = '/app/*'

/** The header name. Report-only for as long as the preview is a rehearsal;
 *  #1602 step 3 is where it stops being one, and that step is the maintainer's. */
export const HEADER_NAME = 'Content-Security-Policy-Report-Only'

/**
 * The body of a Cloudflare Pages `_headers` file carrying the policy.
 *
 * It belongs at the ROOT of the deployed directory - `_site/_headers`, beside
 * the `_site/_redirects` that pr-preview.yml already writes. A copy under
 * `_site/app/` is not a rule at all: Pages reads only the root file, and the
 * stray one is served as a static file to anybody who asks for it.
 *
 * @param {string} policy
 * @returns {string}
 */
export function headersFile(policy) {
  return `${HEADERS_PATH}\n  ${HEADER_NAME}: ${policy}\n`
}

/** The policy for a build, read from the same environment variables the build
 *  itself reads, so the two cannot describe different hosts. */
export function policyFromEnv(env = process.env) {
  return buildPolicy(
    Object.fromEntries(
      Object.entries(HOST_VARIABLES).map(([field, variable]) => [field, env[variable]]),
    ),
  )
}

// `node scripts/csp.mjs --headers` prints the `_headers` body; with no
// argument it prints the policy alone, which is the form a `<meta>` tag would
// carry and the quickest way to read what a given environment produces.
if (process.argv[1] && import.meta.url === `file://${process.argv[1]}`) {
  const policy = policyFromEnv()
  process.stdout.write(
    process.argv.includes('--headers') ? headersFile(policy) : `${policy}\n`,
  )
}
