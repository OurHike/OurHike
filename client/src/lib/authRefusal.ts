// A sign-in refused at the provider, read back off the URL it returns on
// (#1573).
//
// WHY THIS FILE EXISTS. `signInWithProvider` hands the browser to Google or
// GitHub, and the round trip can fail after the app has let go of the hiker:
// Cancel on a consent screen, a GitHub account with no verified email
// address, a provider enabled with the wrong secret. Supabase redirects back
// to this app with the failure on the URL - `#error=access_denied&
// error_code=…&error_description=…` - and supabase-js surfaces it only
// through `GoTrueClient._initialize()`, which nothing here awaits and which
// fires no `onAuthStateChange` event.
//
// So a hiker who tapped Cancel landed back on the map, signed out, with the
// sign-in window closed and NOTHING anywhere saying what had happened - the
// one failure shape in the whole of sign-in that was still silent after
// #279 gave the email path a sentence for every refusal. #397's acceptance
// is that no sign-in path ends in silence; this is what that costs for the
// two paths that leave the app.
//
// PURE FUNCTIONS OF A URL, deliberately. `window` is touched in exactly one
// place, `clearRefusalFromUrl`, and everything it decides is worked out by
// `urlWithoutRefusal` above it. That is what lets the parsing be tested
// against the shapes a provider really returns rather than against a jsdom
// that has to be talked into having a fragment.

import { signInMessage, UNCLEAR } from './authMessages'

/** The keys Supabase and the OAuth2 spec put a refusal under, in the order
 *  to try them. Both halves of each pair are read because neither is
 *  reliable alone: `error_description` is the provider's own prose and
 *  carries the most to match on, while `error_code` and `error` are machine
 *  names that stay put - `access_denied` arrives as a CODE beside a
 *  description ("The user denied the request") that says nothing this app
 *  can recognise. */
const KEYS = ['error_description', 'error_code', 'error'] as const

/** Every refusal value on one half of a URL, in `KEYS` order.
 *
 *  @param part `location.hash` or `location.search`, with or without its
 *              leading `#` or `?`. */
function valuesIn(part: string): string[] {
  const params = new URLSearchParams(part.replace(/^[#?]/, ''))
  const found: string[] = []
  for (const key of KEYS) {
    const value = params.get(key)
    // `.trim()` and not just truthiness: `error=` with nothing after it is a
    // present key carrying no information, and treating it as a refusal
    // would put an empty alert in front of somebody who signed in fine.
    if (value !== null && value.trim() !== '') found.push(value)
  }
  return found
}

/**
 * The refusal on a returned-to URL, as a sentence for a hiker - or null.
 *
 * BOTH HALVES OF THE URL, because which one carries it is not ours to
 * choose: the implicit flow puts it in the fragment and the PKCE flow in the
 * query, and a build that reads one is a build that is silent on the other
 * every time Supabase's default flow changes underneath it.
 *
 * THE FIRST KEY THAT SAYS SOMETHING WINS, rather than the first key present.
 * `signInMessage` matches on text and answers `UNCLEAR` for anything it does
 * not recognise, so a description of "The user denied the request" beside
 * `error_code=access_denied` would otherwise throw away the one value in the
 * URL this app knows how to explain. Nothing recognised anywhere falls back
 * to the general case, which is a true sentence rather than a raw code.
 *
 * @param hash   `window.location.hash`, with or without its leading `#`.
 * @param search `window.location.search`, with or without its leading `?`.
 */
export function refusalIn(hash: string, search: string): string | null {
  const values = [...valuesIn(hash), ...valuesIn(search)]
  if (values.length === 0) return null

  for (const value of values) {
    const message = signInMessage(value)
    if (message !== UNCLEAR) return message
  }
  // Through the same mapping everything else goes through even here, so a
  // hiker meets one voice rather than Google's wording on this path and
  // ours everywhere else.
  return signInMessage(values[0])
}

/**
 * The same URL with the refusal keys taken off it, or the URL unchanged.
 *
 * ONLY THE KEYS THIS FILE READS. The first version rebuilt the URL from
 * `location.pathname` alone, which is correct today - nothing in this app
 * puts anything on the query or the fragment, and `grep -rn 'location\.
 * search' src/` finds only this file - and would silently eat the first
 * deep link somebody adds. Deleting three named keys cannot.
 *
 * Untouched when there is nothing to delete, so a query string this app did
 * not write is not re-serialised (`URLSearchParams` normalises `+` and
 * percent-encoding on the way back out) for no reason.
 */
export function urlWithoutRefusal(href: string): string {
  const url = new URL(href)

  for (const key of KEYS) {
    if (url.searchParams.has(key)) url.searchParams.delete(key)
  }

  const fragment = new URLSearchParams(url.hash.replace(/^#/, ''))
  let cutFromFragment = false
  for (const key of KEYS) {
    if (fragment.has(key)) {
      fragment.delete(key)
      cutFromFragment = true
    }
  }
  if (cutFromFragment) {
    const rest = fragment.toString()
    // Assigning `''` drops the `#` as well, which is the point: a bare `#`
    // left behind is a URL that looks like it still has something on it.
    url.hash = rest === '' ? '' : `#${rest}`
  }

  return url.toString()
}

/**
 * Take the refusal off the address bar, without adding a history entry.
 *
 * A RELOAD MUST NOT REPEAT IT. Left in place, the fragment outlives the
 * message: the hiker dismisses the window, pulls to refresh, and is told
 * again that a sign-in they have since forgotten about was refused.
 *
 * `replaceState` rather than assigning `location.hash = ''`, which pushes a
 * history entry - so Back would walk them through the refusal again, which
 * is the same bug wearing a different hat.
 */
export function clearRefusalFromUrl(): void {
  if (
    typeof window === 'undefined' ||
    typeof window.history?.replaceState !== 'function'
  ) {
    return
  }
  const cleaned = urlWithoutRefusal(window.location.href)
  if (cleaned === window.location.href) return
  window.history.replaceState(window.history.state, '', cleaned)
}
