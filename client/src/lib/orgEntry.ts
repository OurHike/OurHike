/**
 * Whether a URL belongs to the organization surface at all - the only question
 * App.tsx's first frame asks about one, and the only part of #970's router a
 * hiker who never opens an org page should have to carry.
 *
 * WHY THIS IS SPLIT OFF `orgRoute.ts`. Measured 2026-09-18, on this branch
 * merged with `main` at 57868716 and built the way `.github/workflows/
 * build-shells.yml` builds it (Node 24, `npm ci`, no `VITE_` variables set):
 * the org entry cost 1,255 bytes of the eager closure
 * `client/scripts/check-build-output.mjs` budgets, against 624 bytes of
 * headroom - 256,631 with it, 255,376 with the whole block stubbed out, and
 * 256,000 allowed. The three screens were already behind `import()`. What was
 * not was the router that decides which of them to open, so a hiker who never
 * types an org address was parsing the six volunteer pages, the eight console
 * pages, the five tread pages and the three coercions over them, to answer one
 * boolean.
 *
 * The boolean is here. Everything that reads a route rather than recognising
 * one is behind `org/OrgEntry.tsx`'s `import()`.
 *
 * THE TWO READINGS ARE HELD TOGETHER BY `segments`, not by care. `orgRoute.ts`
 * imports this module's `segments` rather than keeping its own, so the two can
 * only disagree about the switch below and never about what a basename is;
 * `orgEntry.test.ts` asserts the rest of the agreement over a corpus of URLs.
 * The failure that split invites is a blank screen on a real address - App.tsx
 * has already returned the org surface by the time the full parse says null.
 */

/** The app's base path, with exactly one trailing slash. */
export function basePath(base: string = import.meta.env.BASE_URL): string {
  const trimmed = base.replace(/\/+$/, '')
  return `${trimmed}/`
}

/**
 * `pathname` with the basename taken off, as segments.
 *
 * Returns null when the path is not under the base at all, which is what
 * makes a router mounted at `/OurHike/` ignore `/somewhere-else` rather than
 * misreading its first segment as a route.
 */
export function segments(pathname: string, base: string): string[] | null {
  const prefix = basePath(base)
  const path = pathname.endsWith('/') ? pathname : `${pathname}/`
  if (!path.startsWith(prefix)) return null
  return path
    .slice(prefix.length)
    .split('/')
    .filter((segment) => segment !== '')
}

/**
 * The five addresses, as the one grammar both halves of the router obey.
 *
 * Anchored at both ends, and every variable segment is `[^/]+`, so a path with
 * a segment too many or too few is not an address - which is the whole of what
 * `parseOrgRoute` checks before it starts reading query parameters. The
 * refusal path is optional under a token and nothing else is: a token is a
 * secret carried in a URL, so an unrecognised path under one is not quietly
 * treated as the proposal itself.
 */
const ORG_ADDRESS =
  /^(?:my\/tread|nominate|n\/[^/]+(?:\/no-thank-you)?|org\/[^/]+\/(?:setup|volunteers))$/

/**
 * Whether this URL is one of the organization surface's five addresses.
 *
 * NEVER THROWS, for the reason `parseOrgRoute` does not: this runs on App's
 * first frame off the browser's own `location.href`, so anything raised here
 * is a white screen instead of a map.
 *
 * The grammar is the path only. Every query parameter the surface reads -
 * `?page=`, `?org=`, `?person=`, `?website=` - changes which screen opens and
 * never whether one does, which is what makes recognising an address this much
 * cheaper than reading it.
 */
export function isOrgEntry(
  url: string | URL,
  base: string = import.meta.env.BASE_URL,
): boolean {
  let parsed: URL
  try {
    parsed = typeof url === 'string' ? new URL(url, 'https://ourhike.org') : url
  } catch {
    return false
  }
  const parts = segments(parsed.pathname, base)
  return parts !== null && ORG_ADDRESS.test(parts.join('/'))
}
