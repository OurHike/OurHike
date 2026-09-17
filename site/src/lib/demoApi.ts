/**
 * The demo organization's data, served at the paths the real API serves it at.
 *
 * WHY THIS EXISTS. `/for-orgs/demo/` mounts the three REAL public embeds
 * rather than drawing its own tables - the design's own structural rule, and
 * the reason it is worth keeping: "the moment the demo gets its own copies it
 * starts lying about the product". Those embeds read `window.__OURHIKE_API__`
 * and, with nothing set, draw nothing: `site/public/embed/v1/ourhike.js` says
 * "an unconfigured page renders empty rather than pointing at a guessed host".
 * So the page that exists to show a whole published organization was showing
 * three empty boxes, everywhere - in previews, and on ourhike.org too, because
 * #600 leaves the production backend unbuilt.
 *
 * The answer is not to give the demo page its own tables. It is to give the
 * real embeds a real host to read: these endpoints, generated at build time,
 * at exactly the four paths `ourhike.js` requests. Nothing about the embed
 * changes - same code, same XHR, same JSON shapes, same failure behaviour -
 * so what a visitor sees here is still what an organization's own visitors
 * would see.
 *
 * ONE HOME FOR THE FIXTURE. Every object below comes from
 * `client/src/org/demoOrg.ts`, which is what the console renders from. A
 * second copy here would be a second demo organization wearing one name, and
 * the first edit to either would put two different Central Parks in front of
 * the same reader.
 *
 * WHAT THIS IS NOT. It is not a backend, and it must never become one: no
 * writes, no auth, no `POST`. The four reads are the four the public embeds
 * make and nothing else. An organization's real page is served by the real
 * API; this serves one invented organization the page already labels as
 * invented, in its first sentence, above everything else.
 */
import {
  DEMO_COVERAGE,
  DEMO_ORG,
  DEMO_REGISTRY,
  DEMO_SLUG,
  DEMO_WORKDAYS,
} from '../../../client/src/org/demoOrg'

export { DEMO_COVERAGE, DEMO_ORG, DEMO_REGISTRY, DEMO_SLUG, DEMO_WORKDAYS }

/** The base `/for-orgs/demo/` points `window.__OURHIKE_API__` at. */
export const DEMO_API_BASE = '/for-orgs/demo/api'

/** A read, answered the way the real API answers it.
 *
 *  `Cache-Control` is short rather than immutable: these files change with
 *  every deployment and a stale demo is a demo arguing with the console.
 */
export function served(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'public, max-age=300',
    },
  })
}
