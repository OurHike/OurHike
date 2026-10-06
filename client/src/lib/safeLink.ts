// Whether a URL that arrived as DATA may be rendered as a link (#1578).
//
// Every `href` the app fills from something it did not write - a moderator's
// reroute notice, a reviewed club row, a Commons file page, a publisher's own
// hike page - passes through here first. The producers refuse a bad scheme
// too (pipeline/lib/atc_updates.py, backend/app/schemas/closure.py), and the
// check is repeated at the sink on purpose: a check that only exists at the
// far end is one a future second producer walks straight past.
//
// WHAT AN UNCHECKED SCHEME DOES, measured 2026-09-17 by rendering
// chrome/ClosureSheet.tsx in this repository's vitest harness (React 19.2.7):
// `javascript:` is rewritten by React itself to a stub that throws, and
// `data:`, `intent:`, `vbscript:` and `file:` reach the anchor unchanged. In
// the Android shell (@capacitor/android 8.5.1, Bridge.launchIntent, read
// rather than run on a device) a tapped `data:` or `blob:` link is loaded IN
// the app's own WebView, replacing the app with the linked document, and any
// other off-origin scheme is handed to the system as an ACTION_VIEW intent
// unless a plugin claims it first.
// So the allowlist below is the whole defence for everything React does not
// already block, and it is an allowlist rather than a blocklist because the
// set of schemes a WebView will act on is not a list this file could keep.

// AND A PAGE BACK INTO THE APP IS NOT ONE OF THEM (SEC-3 of PR #1805's
// second review; decision 94 in pipeline/ELT.md). Every sink below opens its
// link in a new tab, and a new tab of the app signs itself in from whatever
// session the URL carries: lib/supabase.ts sets `detectSessionInUrl` and no
// `flowType`, so auth-js 2.115.0 takes the implicit flow, reads
// `access_token` and `refresh_token` out of the fragment or the query
// (parseParametersFromURL, both through URLSearchParams), checks the token
// with the server and saves the session - whoever minted it (SEC-3 traced
// GoTrueClient.js:376-413). So refused, at every sink:
// - a link whose origin is the page's own;
// - any relative link, which is the page's own origin by construction - and
//   that includes `https:#…` and `https:host/…`, which an https page
//   resolves against itself while `new URL()` alone reads a host into them;
// - a link to anywhere that carries `access_token`, `refresh_token` or
//   `code` (a PKCE callback's) in its query or fragment, because a redirect
//   whose target has no fragment of its own keeps the one it was reached
//   with (the Fetch standard's redirect rule; Reasoned, not run here), so
//   another site can hand the tokens straight back to the app.
// What this cannot stop is another site that redirects into the app with
// tokens it adds itself. Only the PKCE flow refuses that - a callback this
// browser did not start has no verifier here - and moving sign-in to it is
// its own issue, because it changes every sign-in path.
//
// What it refuses of today's data: none of the links in UA's notices file.
// Measured 2026-10-06 on the copy of 2026-10-05T00:23:54Z (7,392 notices,
// 5,653 links): no link was relative, none was on an ourhike.org host, and
// none carried any of the three keys. The other sinks' data - POI and hike
// pages, podcast links, workday signups - was not measured.

const WEB_SCHEMES: ReadonlySet<string> = new Set(['http:', 'https:'])

// The club's own channel may be an address or a number as well as a page
// (pipeline/lib/work_projects.py's "a mailto: or tel: or https: string").
const CONTACT_SCHEMES: ReadonlySet<string> = new Set([...WEB_SCHEMES, 'mailto:', 'tel:'])

// The keys a sign-in callback carries, compared without case. A key counts
// with a value only, as auth-js reads one: `#code` is a page's anchor.
const SESSION_KEYS: ReadonlySet<string> = new Set([
  'access_token',
  'refresh_token',
  'code',
])

/** `url` as an anchor on `page` would resolve it, or null for a string the
 *  URL parser refuses. */
function resolve(url: string, page: string): URL | null {
  try {
    return new URL(url, page)
  } catch {
    return null
  }
}

/** Whether `url` names the same place on any page: absolute, with a host. */
function isAbsolute(url: string, resolved: URL): boolean {
  try {
    return new URL(url).href === resolved.href
  } catch {
    return false
  }
}

/** Whether the query or the fragment carries a sign-in key - the fragment
 *  read whole, as auth-js reads it, and after a `?` in it, as a hash route's
 *  own query. */
function carriesSession(url: URL): boolean {
  const fragment = url.hash.slice(1)
  const routeQuery = fragment.indexOf('?')
  const params = [url.searchParams, new URLSearchParams(fragment)]
  if (routeQuery >= 0) params.push(new URLSearchParams(fragment.slice(routeQuery + 1)))
  return params.some((found) =>
    [...found.entries()].some(
      ([key, value]) => value !== '' && SESSION_KEYS.has(key.toLowerCase()),
    ),
  )
}

/** A web page that is not the app's: http or https, absolute, on another
 *  origin than `page`, and carrying no sign-in key. */
function isPageElsewhere(url: string, page: string): boolean {
  const resolved = resolve(url, page)
  if (resolved === null || !WEB_SCHEMES.has(resolved.protocol)) return false
  return (
    isAbsolute(url, resolved) &&
    resolved.origin !== new URL(page).origin &&
    !carriesSession(resolved)
  )
}

/** A web page somewhere other than the app (see above). `page` is the page
 *  the link is on, the app's own unless a test says otherwise. */
export function isSafeLink(url: string, page: string = window.location.href): boolean {
  return isPageElsewhere(url, page)
}

/** A way to reach a person: a web page somewhere other than the app, an
 *  email address or a phone number. */
export function isSafeContactLink(
  url: string,
  page: string = window.location.href,
): boolean {
  const resolved = resolve(url, page)
  if (resolved === null || !CONTACT_SCHEMES.has(resolved.protocol)) return false
  return WEB_SCHEMES.has(resolved.protocol) ? isPageElsewhere(url, page) : true
}
