/**
 * The one question the app's first frame asks about a URL, and the answer it
 * is not allowed to disagree with.
 *
 * `isOrgEntry` is a second reading of the same grammar `parseOrgRoute` reads,
 * kept separate so that a hiker who never types an org address does not carry
 * the whole router to their first frame (lib/orgEntry.ts says what that
 * measured). Two readings of one grammar is exactly the shape that drifts, and
 * the drift is not cosmetic in either direction:
 *
 *   PREDICATE YES, PARSE NULL is a blank screen on a real address. App.tsx has
 *   already returned the org surface by the time the full parse runs, so there
 *   is nothing to fall back to.
 *
 *   PREDICATE NO, PARSE NON-NULL is a welcome email's link opening the map.
 *
 * So the test that matters is the agreement, over every URL shape either
 * module could answer differently - not the happy path, which both get right.
 */

import { describe, expect, it } from 'vitest'
import { isOrgEntry } from './orgEntry'
import { parseOrgRoute } from './orgRoute'

const ROOT = '/'
const PROJECT_PAGES = '/OurHike/'

/** Every shape the two readings could disagree about, not every valid URL.
 *
 *  The trailing-slash, extra-segment and empty-segment cases are the ones a
 *  hand-written predicate gets wrong, which is why they outnumber the
 *  addresses that plainly work. */
const CORPUS = [
  // The five addresses, bare.
  'https://ourhike.org/my/tread',
  'https://ourhike.org/nominate',
  'https://ourhike.org/n/abc123',
  'https://ourhike.org/org/ramapo-trail-conference/setup',
  'https://ourhike.org/org/ramapo-trail-conference/volunteers',
  // The same five with the query parameters that carry a page, which change
  // what the route IS without changing whether it is one.
  'https://ourhike.org/my/tread?page=phone',
  'https://ourhike.org/my/tread?org=ramapo-trail-conference',
  'https://ourhike.org/nominate?website=https://example.org',
  'https://ourhike.org/org/ramapo-trail-conference/setup?page=approve',
  'https://ourhike.org/org/ramapo-trail-conference/volunteers?page=roster&person=7',
  // A trailing slash is the same address. A browser writes one when a hiker
  // edits the address bar, and an email client sometimes adds one.
  'https://ourhike.org/my/tread/',
  'https://ourhike.org/nominate/',
  'https://ourhike.org/org/ramapo-trail-conference/setup/',
  // The refusal address under a token, and the unrecognised path under one.
  'https://ourhike.org/n/abc123/no-thank-you',
  'https://ourhike.org/n/abc123/something-else',
  'https://ourhike.org/n/abc123/no-thank-you/extra',
  'https://ourhike.org/n/',
  'https://ourhike.org/n',
  // Too few segments, too many, and the wrong last one.
  'https://ourhike.org/my',
  'https://ourhike.org/my/tread/extra',
  'https://ourhike.org/org',
  'https://ourhike.org/org/ramapo-trail-conference',
  'https://ourhike.org/org/ramapo-trail-conference/setup/extra',
  'https://ourhike.org/org/ramapo-trail-conference/registry',
  'https://ourhike.org/org//setup',
  'https://ourhike.org/nominate/extra',
  // An empty segment in the middle. `segments` drops it, so `/my//tread` IS
  // `/my/tread` to the full parse - and a predicate that read the raw path
  // with a regex instead would call it a stranger and send a welcome email's
  // link to the map. These two are why both halves share `segments` rather
  // than each reading the path their own way.
  'https://ourhike.org/my//tread',
  'https://ourhike.org/org/ramapo-trail-conference//setup',
  // Everything the app itself is, which must stay not-a-route.
  'https://ourhike.org/',
  'https://ourhike.org',
  'https://ourhike.org/map/mi/476.6',
  'https://ourhike.org/my/treadmill',
  'https://ourhike.org/organisation/x/setup',
]

describe('the first frame’s question and the full parse give the same answer', () => {
  for (const url of CORPUS) {
    it(`agrees about ${url}`, () => {
      expect(isOrgEntry(url, ROOT)).toBe(parseOrgRoute(url, ROOT) !== null)
    })
  }

  it('agrees under a basename too, where a wrong answer shows in one environment only', () => {
    // #970's own first constraint, applied to the predicate: the basename is
    // what `VITE_BASE_PATH` made it, and a reading that ignored it would put
    // every org address on the map under /OurHike/ and nowhere else.
    for (const url of CORPUS) {
      const moved = url.replace('ourhike.org/', 'ourhike.org/OurHike/')
      expect(isOrgEntry(moved, PROJECT_PAGES)).toBe(
        parseOrgRoute(moved, PROJECT_PAGES) !== null,
      )
    }
  })

  it('says no to a path outside the basename rather than reading its first segment', () => {
    expect(isOrgEntry('https://ourhike.org/nominate', PROJECT_PAGES)).toBe(false)
    expect(parseOrgRoute('https://ourhike.org/nominate', PROJECT_PAGES)).toBeNull()
  })

  it('says no rather than throwing on a URL that does not parse', () => {
    // This runs on the first frame off `window.location.href`, so anything it
    // raises is a white screen instead of a map.
    expect(isOrgEntry('http://[', ROOT)).toBe(false)
  })
})
