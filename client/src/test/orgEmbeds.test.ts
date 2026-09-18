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
