/**
 * The four promises the console makes about the embeds, checked against the
 * file that has to keep them.
 *
 * These are not style rules. Each one is a sentence an organization reads on
 * the console screen before pasting a script tag onto their own homepage, and
 * breaking any of them breaks it on somebody else's site where we would never
 * find out. The copy is in `client/src/org/screens/SetupHub.tsx` and
 * `site/src/pages/for-orgs/demo.astro`; the file is one `public/` asset with
 * no build step, so what an organization audits is what runs.
 *
 * WHY THIS LIVES IN THE CLIENT SUITE. `site/` carries its own vitest and
 * nothing in CI runs it - `pages.yml` builds the site and never tests it - so
 * a guard there would be a guard nobody ran. `site/` is already in this
 * workflow's scope list, so editing the embed runs this.
 */

import { describe, expect, it } from 'vitest'
import { readRepoFile } from './repoFile'

const EMBED = readRepoFile('site/public/embed/v1/ourhike.js')

/** The file with its comments taken out.
 *
 *  Every rule below is about what the code DOES, and the comments explaining
 *  why it does not use cookies would otherwise trip the cookie check - which
 *  would teach the next person to delete the explanation rather than keep the
 *  promise.
 */
const CODE = EMBED.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')

describe('no URL the embed was handed becomes an href without a scheme check', () => {
  /**
   * The embed runs on the ORGANIZATION'S own page, so a `javascript:` or
   * `data:` URL it renders is stored XSS on their site, shipped there by us.
   * That is the worst of the three sinks reading these fields, and the only
   * one where no framework is quietly rewriting `javascript:` first.
   *
   * `client/src/lib/safeLink.ts` is the same rule for the app and says why
   * it is repeated at every sink. This file cannot import it - the embed is
   * one `public/` asset with no build step, on purpose, so that what an
   * organization audits is what runs - so the embed carries its own copy
   * and this block is what keeps the two from drifting apart.
   */

  /** The embed's own `safeHref`, lifted out and made callable.
   *
   *  The file is one IIFE and exposes nothing, so the alternative was a
   *  regex asserting the shape of the function's source - which would pass
   *  on a version of it that always returned the URL. This runs the real
   *  lines against jsdom's own URL parser, which is the thing the function
   *  delegates the hard part to.
   */
  function liftSafeHref(): (url: unknown) => string | null {
    const opened = CODE.indexOf('function safeHref(url) {')
    expect(opened).toBeGreaterThan(-1)
    let depth = 0
    let closed = -1
    for (let at = CODE.indexOf('{', opened); at < CODE.length; at += 1) {
      if (CODE[at] === '{') depth += 1
      else if (CODE[at] === '}') {
        depth -= 1
        if (depth === 0) {
          closed = at + 1
          break
        }
      }
    }
    expect(closed).toBeGreaterThan(opened)
    // `safeHref` reads SAFE_SCHEMES from the enclosing IIFE, so the list
    // travels with it - which is the point: the test runs the real list.
    const list = /var SAFE_SCHEMES = \[[^\]]*\]/.exec(CODE)?.[0]
    expect(list).toBeDefined()
    const source = `${list}; ${CODE.slice(opened, closed)}; return safeHref`
    return new Function(source)() as (url: unknown) => string | null
  }

  it('passes a page, an address and a number through unchanged', () => {
    const safeHref = liftSafeHref()
    expect(safeHref('https://cmc.org/volunteer')).toBe('https://cmc.org/volunteer')
    expect(safeHref('http://cmc.org/volunteer')).toBe('http://cmc.org/volunteer')
    expect(safeHref('mailto:trails@cmc.org')).toBe('mailto:trails@cmc.org')
    expect(safeHref('tel:+12015550134')).toBe('tel:+12015550134')
  })

  it('refuses every scheme a browser or a phone would act on', () => {
    const safeHref = liftSafeHref()
    for (const url of [
      'javascript:alert(document.cookie)',
      'data:text/html,<script>alert(1)</script>',
      'vbscript:msgbox(1)',
      'file:///etc/passwd',
      'intent://evil#Intent;scheme=http;end',
      'blob:https://cmc.org/8f7e',
    ]) {
      expect(safeHref(url)).toBeNull()
    }
  })

  it('refuses the spellings that read differently to a regex than to an anchor', () => {
    const safeHref = liftSafeHref()
    expect(safeHref('  javascript:alert(1)')).toBeNull()
    expect(safeHref('JaVaScRiPt:alert(1)')).toBeNull()
    expect(safeHref('java\nscript:alert(1)')).toBeNull()
    expect(safeHref('\u0001javascript:alert(1)')).toBeNull()
  })

  it('answers null for nothing at all, so a missing link is a missing link', () => {
    const safeHref = liftSafeHref()
    expect(safeHref(null)).toBeNull()
    expect(safeHref(undefined)).toBeNull()
    expect(safeHref('')).toBeNull()
  })

  it('routes every data-driven href through it', () => {
    // Sound against the variable form the callers use: an assignment may
    // read a name only if that name was bound from `safeHref(`. Without
    // that second half the rule passes on `x = org.donation_url; a.href = x`.
    const assignments = CODE.match(/\.href\s*=\s*[^\n]+/g) ?? []
    expect(assignments.length).toBeGreaterThan(0)
    for (const assignment of assignments) {
      const value = assignment.replace(/^\.href\s*=\s*/, '').trim()
      const builtFromLiterals = value.startsWith("'") || value.startsWith('"')
      const guardedHere = value.startsWith('safeHref(')
      const name = /^([A-Za-z_$][\w$]*)\s*$/.exec(value)?.[1]
      const guardedEarlier =
        name !== undefined && new RegExp(`var\\s+${name}\\s*=\\s*safeHref\\(`).test(CODE)
      expect(builtFromLiterals || guardedHere || guardedEarlier).toBe(true)
    }
  })

  it('allows only the schemes a contact can legitimately be', () => {
    expect(CODE).toMatch(/SAFE_SCHEMES/)
    // Kept in step by hand with `client/src/lib/safeLink.ts`'s
    // CONTACT_SCHEMES and `backend/app/schemas/org.py`'s
    // SAFE_CONTACT_SCHEMES - three copies, each naming the others.
    const listed = /var SAFE_SCHEMES = \[([^\]]*)\]/.exec(CODE)?.[1] ?? ''
    expect(listed.match(/'[^']+'/g)?.sort()).toEqual([
      "'http:'",
      "'https:'",
      "'mailto:'",
      "'tel:'",
    ])
  })
})

describe('the embeds keep the four promises the console prints', () => {
  it('stores nothing on a visitor: no cookies, no web storage, no IndexedDB', () => {
    expect(CODE).not.toMatch(/document\s*\.\s*cookie/)
    expect(CODE).not.toMatch(/localStorage/)
    expect(CODE).not.toMatch(/sessionStorage/)
    expect(CODE).not.toMatch(/indexedDB/i)
  })

  it('sends no beacon and opens no socket, so there is nothing to track with', () => {
    expect(CODE).not.toMatch(/sendBeacon/)
    expect(CODE).not.toMatch(/new\s+WebSocket/)
    expect(CODE).not.toMatch(/new\s+Image\s*\(/)
  })

  it('lets an organization remove the OurHike credit line', () => {
    expect(EMBED).toContain('data-credit')
    expect(EMBED).toContain("'off'")
  })

  it('names no font and no colour, so it inherits the host page instead', () => {
    // A hex colour or a font-family in the stylesheet would make the widget
    // look like an advert on somebody's own page.
    expect(CODE).not.toMatch(/#[0-9a-fA-F]{3,8}\b/)
    expect(CODE).not.toMatch(/font-family/)
    expect(CODE).not.toMatch(/!important/)
  })

  it('draws nothing rather than an error when a request fails', () => {
    // Both failure paths answer with the same null the caller draws nothing
    // from. An outage of ours must not print itself on an org's homepage.
    expect(CODE).toMatch(/onerror\s*=\s*function\s*\(\)\s*\{\s*done\(null\)/)
    expect(CODE).toMatch(/if \(request\.status < 200 \|\| request\.status >= 300\)/)
  })

  it('wraps every mount so one failing widget cannot take the page down', () => {
    expect(CODE).toMatch(/try \{\s*WIDGETS\[i\]\.mount\(host\)/)
  })

  it('refuses a console key secret placed in the page rather than using it', () => {
    // The one case in the file that writes an error somewhere visible: the
    // refusal has to be louder than the mistake, because a secret in page
    // source lets anybody reading it mint tokens for anybody.
    expect(CODE).toMatch(/getAttribute\('data-secret'\)/)
    expect(EMBED).toContain('has been ignored rather than used')
  })

  it('asks the server what a console token permits rather than reading it', () => {
    // Parsing the claims in JavaScript would let somebody edit them in a
    // debugger and change what the widget draws, which teaches a reader that
    // the widget's own display is the permission check.
    expect(CODE).toContain('/console/whoami')
    expect(CODE).not.toMatch(/atob\(/)
  })

  it('mounts exactly the four host elements the console tells orgs to paste', () => {
    expect(CODE).toContain("'ourhike-hikes'")
    expect(CODE).toContain("'ourhike-workdays'")
    expect(CODE).toContain("'ourhike-coverage'")
    expect(CODE).toContain("'ourhike-console'")
  })

  it('takes the backend host from the deployment seam, never a hardcoded one', () => {
    expect(CODE).toContain('window.__OURHIKE_API__')
    expect(CODE).not.toMatch(/https:\/\/[a-z0-9.-]*ourhike\.org/)
  })
})

describe('the coverage badge is three counts, in two shapes', () => {
  // WHAT THIS BADGE USED TO BE, and why it changed. It drew the gap count -
  // "three sections are looking for somebody" - by reading
  // `GET /clubs/{slug}/coverage`. That endpoint depends on `org_access`, which
  // depends on a signed-in caller, so an anonymous visitor got a 401 and the
  // badge rendered NOTHING: on every real site, always. It only ever appeared
  // to work on /for-orgs/demo/, where a fixture answers it without auth.
  //
  // The coverage report is right to be gated - a public list of which miles
  // nobody is looking after is a list of miles to avoid - so the fix is the
  // design's own badge, which was never the gap count:
  // miles maintained · active volunteers · hours this season, from
  // `GET /clubs/{slug}/scoreboard`, which is public and returns three numbers.
  const body = () => {
    const from = CODE.slice(CODE.indexOf('function mountCoverage'))
    const end = from.indexOf('function mountConsole')
    return from.slice(0, end === -1 ? undefined : end)
  }

  it('reads the public endpoint rather than the gated one', () => {
    expect(body()).toContain('/scoreboard')
    expect(body()).not.toContain('/coverage')
  })

  it('draws the design’s three figures', () => {
    for (const label of ['miles maintained', 'active volunteers', 'hours this season']) {
      expect(body()).toContain(label)
    }
  })

  it('never names or lists anything', () => {
    // The old badge read `.length` off an array of gaps WITH their section
    // names and discarded the rest, which put a safety property in a browser
    // where the next edit could drop it. There is nothing to discard now, and
    // this is what keeps it that way.
    expect(body()).not.toContain('section_name')
    expect(body()).not.toContain('gaps')
    expect(body()).not.toMatch(/\.\s*map\(/)
  })

  it('has two shapes off one snippet, as the design says', () => {
    expect(body()).toContain('data-shape')
    expect(CODE).toContain('function footerStrip')
    expect(CODE).toContain('function sidebarCard')
  })

  it('does not put words in an organization’s mouth on their own page', () => {
    // The design's card is headed "Our park, live" - an organization's own
    // words about its own donate page, which we cannot know. `data-title` is
    // how they say it and their registered name is the fallback.
    expect(body()).toContain('data-title')
  })

  it('does not claim a freshness the mechanism does not have', () => {
    // The design's mock-up card reads "Updated nightly from our own registry".
    // The figures are computed when the badge loads, so the foot says that
    // instead. A line claiming a freshness nothing delivers is the same defect
    // as a heading claiming a reading nobody did.
    expect(body()).not.toMatch(/nightly/i)
    expect(body()).toMatch(/when this page loaded/i)
  })
})

/**
 * The workdays widget says whether a workday is full.
 *
 * The design's Workdays Widget draws a `spots` field on every card
 * (features/org-onboarding-handoff - the component prototype), and the built
 * widget had none: a visitor read a title, a date, a meet point and a signup
 * line, and could not tell a workday with two places left from one with
 * none until they had followed the link.
 *
 * ABSENT MEANS UNKNOWN, which is the constraint that shapes this. A workday
 * with no `cap` has no published ceiling, and CLAUDE.md's rule for the
 * safety-adjacent surfaces applies here too: a made-up number is worse than
 * no number. So the pill appears only when the organization published a cap.
 *
 * And it counts CONFIRMED rather than interested, because SPEC.md is explicit
 * that "a signup is an introduction, not an enrolment" and the app "must
 * never leave somebody believing they are on a roster when they are not".
 */
describe('the workdays widget and a workday that is full', () => {
  const body = () => {
    const start = CODE.indexOf('function mountWorkdays')
    const end = CODE.indexOf('function mountCoverage')
    return CODE.slice(start, end === -1 ? undefined : end)
  }

  it('shows how full a workday is when the organization published a cap', () => {
    expect(body()).toMatch(/workday\.cap/)
    expect(body()).toMatch(/confirmed_count/)
  })

  it('shows nothing at all when no cap was published', () => {
    // The guard rather than the happy path: a widget that rendered "0 of 0"
    // or "unlimited" would be inventing a fact about somebody else's crew.
    expect(body()).toMatch(/cap\s*(!==|!=)\s*null|typeof workday\.cap|workday\.cap\s*&&/)
  })

  it('counts confirmed places and never interested ones', () => {
    // An introduction is not an enrolment. Counting `interested_count` here
    // would tell a visitor a workday is full when nobody has been confirmed.
    const pill = body().slice(body().indexOf('cap'))
    expect(pill).not.toContain('interested_count')
  })
})
