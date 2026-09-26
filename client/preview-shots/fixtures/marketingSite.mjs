// Serves the built marketing site (site/dist/) through the camera's own
// server, so a recipe can photograph ourhike.org's pages and not only the app.
//
// WHY A ROUTE. The camera (scripts/screenshot.mjs) serves `client/dist`
// through `vite preview` under the app's base, `/app/` in CI, and nothing
// else: `/for-orgs/` on that server is the app's own fallback page. So the
// four org pages had no recipe at all, and #1547 - Let an organization put
// its own trails, roster and workdays in - and let a hiker offer a club's,
// with the club deciding - shipped them with "seven recipes, all desktop",
// none of them of the site. They went out unreadable in dark mode and
// misaligned on a phone, and a maintainer found it on their own phone
// (#1663 - The /for-orgs/ pages are unreadable in dark mode and misaligned
// on a phone).
//
// pr-preview.yml runs "Build the site" before "Photograph the build", so
// site/dist is on the runner by the time a recipe drives. Every request on
// the camera's origin outside the app's base is answered from there -
// the pages, their `/_astro/` assets, `/fonts/`, `/embed/`, and the demo
// org's fixture JSON - the same layout production serves at the root.
//
// NOBODY'S DATA. The site is static and signed out by construction: it
// carries no Supabase client, so there is no account to photograph.

import { existsSync, readFileSync, statSync } from 'node:fs'
import { extname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const SITE_DIST = fileURLToPath(new URL('../../../site/dist/', import.meta.url))

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css',
  '.js': 'text/javascript',
  '.mjs': 'text/javascript',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
  '.webp': 'image/webp',
  '.jpg': 'image/jpeg',
  '.png': 'image/png',
  '.woff2': 'font/woff2',
}

/** Where `pathname` lives in site/dist, or null. `/x/` is `/x/index.html`. */
function siteFile(pathname) {
  const clean = decodeURIComponent(pathname).replace(/\.\.+/g, '')
  const candidates = clean.endsWith('/')
    ? [join(SITE_DIST, clean, 'index.html')]
    : [join(SITE_DIST, clean), join(SITE_DIST, clean, 'index.html')]
  return candidates.find((path) => existsSync(path) && statSync(path).isFile()) ?? null
}

/**
 * A recipe's `before`: answer every same-origin request outside the app's
 * base from site/dist. Throws when the site has not been built, which the
 * runner turns into a sentence in the comment naming the recipe rather than
 * a photograph of the app's fallback page captioned as the site.
 */
export async function serveMarketingSite(page) {
  if (!existsSync(join(SITE_DIST, 'index.html'))) {
    throw new Error(
      `site/dist is not built (looked in ${SITE_DIST}) - run \`npm run build\` in site/ first`,
    )
  }
  await page.route('**/*', async (route) => {
    const url = new URL(route.request().url())
    const appBase = process.env.VITE_BASE_PATH ?? '/'
    const isApp = appBase !== '/' && url.pathname.startsWith(appBase)
    const file = isApp ? null : siteFile(url.pathname)
    if (file === null) return route.fallback()
    return route.fulfill({
      status: 200,
      contentType: TYPES[extname(file)] ?? 'application/octet-stream',
      body: readFileSync(file),
    })
  })
}

/** Open a site page on the camera's origin, wherever the app itself is served. */
export async function openSitePage(page, pathname) {
  await page.goto(new URL(pathname, page.url()).href, { waitUntil: 'networkidle' })
}

/**
 * Bring `locator` to `offset` px below the top of the viewport, in one
 * instant jump.
 *
 * ONE JUMP, AND INSTANT, because site.css sets `scroll-behavior: smooth` on
 * <html>. A recipe that called scrollIntoView and then scrollBy(0, -24)
 * started a smooth scroll and interrupted it a frame later with a second
 * one, from wherever the first had got to - which on CI's runner was the
 * top of the page. site-for-orgs-reasons-dark and site-demo-tread-phone
 * both went out photographing the header they were meant to scroll past
 * (#1672's first preview comment).
 */
export async function scrollToTop(locator, offset = 24) {
  await locator.evaluate((node, gap) => {
    const top = node.getBoundingClientRect().top + window.scrollY - gap
    window.scrollTo({ top, behavior: 'instant' })
  }, offset)
}
