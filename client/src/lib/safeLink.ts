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

const WEB_SCHEMES: ReadonlySet<string> = new Set(['http:', 'https:'])

// The club's own channel may be an address or a number as well as a page
// (pipeline/lib/work_projects.py's "a mailto: or tel: or https: string").
const CONTACT_SCHEMES: ReadonlySet<string> = new Set([...WEB_SCHEMES, 'mailto:', 'tel:'])

/** The scheme the browser would resolve `url` to, or null for a string the
 *  URL parser refuses. Relative strings resolve against the page, as an
 *  anchor would resolve them, so they answer with the app's own scheme. */
function schemeOf(url: string): string | null {
  try {
    return new URL(url, window.location.href).protocol
  } catch {
    return null
  }
}

/** A web page: `http:` or `https:`, and nothing else. */
export function isSafeLink(url: string): boolean {
  const scheme = schemeOf(url)
  return scheme !== null && WEB_SCHEMES.has(scheme)
}

/** A way to reach a person: a web page, an email address or a phone number. */
export function isSafeContactLink(url: string): boolean {
  const scheme = schemeOf(url)
  return scheme !== null && CONTACT_SCHEMES.has(scheme)
}
