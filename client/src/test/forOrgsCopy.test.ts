/**
 * What /for-orgs/ may and may not say to an organization.
 *
 * THE SENTENCE THIS EXISTS FOR, and it has been wrong once already.
 * features/ONBOARDING.md records the maintainer's correction of 2026-08-27:
 * the app's value-prop screen had said OurHike "funds the ATC and affiliated
 * clubs" and it was never true - *"There is no funding model today for the
 * orgs. The hope is we will drive membership and donations to those orgs."*
 *
 * `screens/Onboarding.test.tsx` guards the app's copy against it coming back,
 * and that guard reads the app's value-prop step only. It cannot see the
 * site. So the page that is *about* money, addressed to the treasurer of a
 * volunteer organization, had no guard at all until this one.
 *
 * WHY IT LIVES IN THE CLIENT SUITE rather than in site/'s own. site/ has a
 * vitest suite (`src/lib/heroOrgs.test.mjs`) and nothing in CI runs it -
 * pages.yml builds the site and never tests it. A guard in a suite nobody
 * runs is a comment with a test framework around it. The read goes through
 * repoFile.ts, which is what keeps `site/` in this workflow's scope list
 * (#503).
 */
import { describe, it, expect } from 'vitest'
import { readRepoFile } from './repoFile'

const copy = readRepoFile('site/src/lib/orgOnboarding.mjs')
const page = readRepoFile('site/src/pages/for-orgs/index.astro')

/** The rendered sentences, with the file's own comments stripped.
 *
 *  Comments are stripped because this file's header quotes the forbidden
 *  sentence in order to explain itself, and a guard that its own explanation
 *  fails is a guard that gets deleted.
 */
function sentences(source: string): string {
  return source
    .split('\n')
    .filter((line) => !/^\s*(\/\/|\/\*|\*|-{3})/.test(line))
    .join('\n')
}

describe('the money copy on /for-orgs/', () => {
  it('never puts OurHike, a purchase or a donation in front of the verb "fund"', () => {
    // The app's own guard's shape, applied to this surface: any inflection of
    // "fund" with OurHike, a purchase or a donation ahead of it in the same
    // sentence. That is the claim, and the claim is what was false.
    const forbidden =
      /\b(ourhike|purchase|donation|donate|subscription)\b[^.!?]*\bfund(s|ed|ing)?\b/i
    for (const source of [sentences(copy), sentences(page)]) {
      expect(source).not.toMatch(forbidden)
    }
  })

  it('says where money actually goes, which is straight to the organization', () => {
    expect(copy).toMatch(/money goes to trail organizations/i)
  })

  it('marks the shared-revenue block as not live, in the markup rather than in a comment', () => {
    // The reader is a treasurer. A promise about money that is only qualified
    // in a source comment is a promise as far as they are concerned.
    expect(sentences(page)).toMatch(
      /none of this is live yet, and none of it is promised/i,
    )
    expect(sentences(page)).toMatch(/no money passes through ourhike today/i)
  })
})

describe('the homepage card that points here', () => {
  const home = readRepoFile('site/src/pages/index.astro')

  it('asks a question rather than announcing a category', () => {
    // "For organisations" as a heading filters itself out before it is read:
    // the reader is a hiker until the moment they realise it is about them.
    expect(home).toMatch(/Do you maintain these trails\?/)
  })

  it('keeps GIS, registries and pull requests off a consumer homepage', () => {
    const card = home.slice(home.indexOf('Do you maintain these trails?'))
    const upToNextSection = card.slice(0, card.indexOf('</div>'))
    expect(upToNextSection).not.toMatch(/\bGIS\b|\bregistry\b|pull request/i)
  })
})

describe('the nav link this page was waiting for', () => {
  const nav = readRepoFile('site/src/components/NavBar.astro')

  it('links the org page now that it exists', () => {
    // The label became "For orgs" on 2026-09-17 - the wireframe audit's
    // decision, and the reason is in the test below it. What this one is
    // about is unchanged: the link exists because the page does.
    expect(nav).toMatch(/'\/for-orgs\/', label: 'For orgs'/)
  })

  it('still does not link the two pages that are not real yet', () => {
    // NavBar.astro's own rule: a nav link to a page that is not there is a
    // promise the site breaks on its second click. Explore the trail and Get
    // involved are still not there.
    expect(nav).not.toMatch(/label: 'Get involved'/)
    expect(nav).not.toMatch(/label: 'Explore/)
  })
})

/**
 * The four public org doors reach each other from the top of each of them.
 *
 * The app's console already did this - `org/OrgShell.tsx` puts the same four
 * links across the top of every console screen - and the marketing pages did
 * not, until 2026-09-17. The site nav offers `For clubs` and the footer
 * offers `Claim your org`, so three of the four doors were reachable from
 * /for-orgs/ only through a section most of a page down. Four doors are worth
 * nothing if three of them are below the fold.
 *
 * Read off the pages rather than the component, because the failure this
 * catches is a page that forgot to mount it rather than a component that
 * lost a link.
 */
describe('the four org pages reach each other', () => {
  const PAGES = ['index', 'demo', 'nominate', 'claim'] as const

  it.each(PAGES)('/for-orgs/%s mounts the shared door row', (name) => {
    const source = readRepoFile(`site/src/pages/for-orgs/${name}.astro`)
    expect(source).toContain("import OrgNav from '../../components/OrgNav.astro'")
    expect(source).toContain('<OrgNav />')
  })

  it('names all four doors, each with the address it opens', () => {
    // The console's half of this pair is asserted in org/OrgShell.test.tsx,
    // which renders the shell and reads THIS file for the labels - so the row
    // has one source of truth rather than two lists that can drift apart
    // while both stay green.
    const nav = readRepoFile('site/src/components/OrgNav.astro')
    for (const label of ['For orgs', 'Demo org', 'Nominate an org', 'Claim your org']) {
      expect(nav, `OrgNav.astro is missing "${label}"`).toContain(label)
    }
    for (const href of [
      '/for-orgs/',
      '/for-orgs/demo/',
      '/for-orgs/nominate/',
      '/for-orgs/claim/',
    ]) {
      expect(nav, `OrgNav.astro is missing ${href}`).toContain(href)
    }
  })
})

/**
 * The demo organization has data behind it, and it is the console's data.
 *
 * /for-orgs/demo/ mounts the three REAL public embeds rather than drawing its
 * own tables - the design's structural rule, and the reason it is worth
 * keeping is that "the moment the demo gets its own copies it starts lying
 * about the product". The cost of that rule is that the embeds read
 * `window.__OURHIKE_API__` and draw NOTHING when it is unset, which is what
 * the page did everywhere until 2026-09-17: three empty boxes on the page
 * whose whole job is showing a published organization.
 *
 * Four generated endpoints under the page answer the four reads `ourhike.js`
 * makes, from `client/src/org/demoOrg.ts` - the same fixture the console
 * renders. This checks the wiring rather than the bytes: a page that stopped
 * setting the base, or an endpoint that stopped being generated, is three
 * empty boxes again and nothing else in the suite would notice.
 */
describe('the demo org has data behind it', () => {
  it('points the embeds at the endpoints generated beside the page', () => {
    const page = readRepoFile('site/src/pages/for-orgs/demo.astro')
    expect(page).toContain('window.__OURHIKE_API__')
    expect(page).toContain('DEMO_API_BASE')

    const lib = readRepoFile('site/src/lib/demoApi.ts')
    expect(lib).toContain("DEMO_API_BASE = '/for-orgs/demo/api'")
    // The fixture is the console's, not a second copy of it.
    expect(lib).toContain("from '../../../client/src/org/demoOrg'")
  })

  // Literal paths rather than a template, because `readRepoFile` only accepts
  // paths declared in OUT_OF_TREE_READS and the type is what enforces it.
  it.each([
    [
      'site/src/pages/for-orgs/demo/api/clubs/central-park-throughikers/index.html.ts',
      'DEMO_ORG',
    ],
    [
      'site/src/pages/for-orgs/demo/api/clubs/central-park-throughikers/registry.ts',
      'DEMO_REGISTRY',
    ],
    [
      'site/src/pages/for-orgs/demo/api/clubs/central-park-throughikers/coverage.ts',
      'DEMO_COVERAGE',
    ],
    [
      'site/src/pages/for-orgs/demo/api/clubs/central-park-throughikers/scoreboard.ts',
      'DEMO_SCOREBOARD',
    ],
    ['site/src/pages/for-orgs/demo/api/workdays.ts', 'DEMO_WORKDAYS'],
  ] as const)('%s answers with %s', (path, fixture) => {
    expect(readRepoFile(path)).toContain(`served(${fixture})`)
  })
})

/**
 * No Astro attribute carries an uninterpolated `{PLACEHOLDER}`.
 *
 * THE DEFECT THIS IS MADE FROM. /for-orgs/demo/ shipped its primary call to
 * action as `href="/app/my/tread?org={ORG_SLUG}"`. Astro interpolates inside
 * `href={...}`, not inside a quoted string, so the button that opens "the view
 * that matters most" - the screen the page says every admin screen exists to
 * produce - linked to a literal `{ORG_SLUG}`.
 *
 * It survived every check the branch had: the page built, the link was
 * present, the copy was right, and nothing read the attribute's VALUE. It took
 * a comparison that dumps controls rather than text to see it.
 *
 * Written against the class rather than the instance, because the next one
 * will be a different attribute on a different page.
 */
describe('Astro placeholders are interpolated', () => {
  const PAGES = [
    'site/src/pages/for-orgs/index.astro',
    'site/src/pages/for-orgs/demo.astro',
    'site/src/pages/for-orgs/nominate.astro',
    'site/src/pages/for-orgs/claim.astro',
  ] as const

  it.each(PAGES)('%s has no braces left inside a quoted attribute', (path) => {
    const source = readRepoFile(path)
    // An attribute written as name="...{THING}..." - the shape that renders
    // the braces literally. `name={...}` is the correct form and is not
    // matched, because the value does not open with a quote.
    const literal = [...source.matchAll(/\s[a-zA-Z-]+="[^"]*\{[A-Za-z_$][^"]*"/g)].map(
      (match) => match[0].trim(),
    )
    expect(literal, `${path} renders these braces literally`).toEqual([])
  })
})

/**
 * What the 2026-09-17 wireframe audit found on this surface, and the
 * maintainer decided to follow.
 *
 * Each of these is a difference from the design that was approved as a change
 * to the BUILD rather than accepted as a deviation, so each gets a guard: the
 * point of an approved fidelity decision is that it does not quietly rot back.
 */
describe('the wireframe decisions of 2026-09-17', () => {
  const nav = () => readRepoFile('site/src/components/NavBar.astro')

  it('names the org surface "For orgs", the word the design and the data model use', () => {
    // ORG_ONBOARDING.md's conflict 2: not every organization is a club - OPRHP
    // is a state agency, Mohonk a preserve, a land trust neither. The site said
    // "For clubs" while the design, the console and the routes all said org.
    expect(nav()).toContain("label: 'For orgs'")
    expect(nav()).not.toContain("label: 'For clubs'")
  })

  it("offers an organization the design's own call to action in the nav", () => {
    // The design's nav button is "Add your trails". The site's was "Support
    // the trail" - a hiker's action, on the row an organization arrives by.
    expect(nav()).toContain('Add your trails')
  })

  it('gives every reason card the icon the design draws on it', () => {
    // REASONS carried title and body only, and the card template rendered only
    // those, so four cards the design gives an icon each had none.
    const copy = readRepoFile('site/src/lib/orgOnboarding.mjs')
    const reasons = copy.slice(copy.indexOf('export const REASONS'))
    const block = reasons.slice(0, reasons.indexOf('export const', 10))
    const titles = [...block.matchAll(/title:/g)].length
    const glyphs = [...block.matchAll(/glyph:/g)].length
    expect(glyphs, 'every reason needs a glyph').toBe(titles)
    expect(readRepoFile('site/src/pages/for-orgs/index.astro')).toContain('reason.glyph')
  })

  it('carries a skip link, which the design has on every screen and the site had on none', () => {
    const base = readRepoFile('site/src/layouts/Base.astro')
    expect(base).toMatch(/skip/i)
    expect(base).toContain('#main')
  })

  it("asks a nominating hiker for the website and not for the org's name", () => {
    // Dropped on the maintainer's decision: the design opens with the website
    // and nothing else, and a name field ahead of it made the hiker answer a
    // question the reading was supposed to answer.
    const page = readRepoFile('site/src/pages/for-orgs/nominate.astro')
    expect(page).not.toContain('nominate-name')
  })

  it('does not ask a nominating hiker for a data link they are unlikely to have', () => {
    const page = readRepoFile('site/src/pages/for-orgs/nominate.astro')
    expect(page).not.toContain('nominate-data')
    expect(page).not.toContain('OPTIONAL · IF YOU ALREADY KNOW')
  })
})

/**
 * The demo page describes the widget it actually mounts.
 *
 * "Their sections" promised "the same table and map your own admins sign off
 * on" and mounted the Hike Finder, which draws an organization's HIKES - a
 * name, a park, a length - and has neither a map nor a status column. The
 * table an admin signs off on is the console's registry table, which is not
 * a public embed at all.
 *
 * A page that describes one widget and shows another is the failure the demo
 * exists to avoid: it is supposed to be what a visitor to an organization's
 * own site would see.
 */
describe('the demo page describes what it shows', () => {
  const page = () => readRepoFile('site/src/pages/for-orgs/demo.astro')

  /** The page with its Astro comment blocks removed.
   *
   *  Comments are stripped for the same reason `sentences()` above strips
   *  them: this file's explanations quote the copy they are about, and a
   *  guard its own explanation fails is a guard somebody deletes.
   */
  const rendered = () => page().replace(/\{\s*\/\*[\s\S]*?\*\/\s*\}/g, '')

  it('does not promise the registry table an admin signs off on', () => {
    const sections = rendered().slice(rendered().indexOf('Their sections'))
    const lede = sections.slice(0, sections.indexOf('</p>'))
    expect(lede).not.toMatch(/sign off|signs off/i)
    expect(lede).not.toMatch(/\bmap\b/i)
  })
})

describe('the nominate page describes where the reading actually happens', () => {
  // THE PAGE USED TO CLAIM A READING NOBODY DID. It said "We read the public
  // site the way you would" and headed a result panel "WHAT WE COULD SEE ON
  // THEIR SITE", over an answer a model produced from its own memory - nothing
  // had ever been fetched. That is CLAUDE.md's "never let a display outrun its
  // source", and it is fixed on both sides: the backend really reads now
  // (app/core/sitefetch.py), and the reading needs a signed-in hiker and a
  // proof of work, neither of which this site has - it carries no Supabase
  // client and no sign-in at all.
  //
  // So the reading moved into the app and this page is the door to it. These
  // guards are about the seam: a marketing page that describes a step it
  // cannot perform is the same defect in a new place.
  const source = () => readRepoFile('site/src/pages/for-orgs/nominate.astro')

  /** What the page actually renders, with both kinds of comment removed.
   *
   *  Needed rather than tidy: the file's own header quotes the old heading in
   *  order to explain why it went, and a guard reading the raw source would
   *  fail on the sentence recording the fix. The frontmatter block between the
   *  `---` fences is comments and imports and never reaches a reader either. */
  const rendered = () =>
    source()
      .replace(/^---[\s\S]*?^---/m, '')
      .replace(/\{\s*\/\*[\s\S]*?\*\/\s*\}/g, '')

  it('does not head a panel with what we saw on a site it never opened', () => {
    expect(rendered()).not.toContain('WHAT WE COULD SEE ON THEIR SITE')
  })

  it('does not say this page reads anybody', () => {
    // Present tense about this page. The example block below the form is
    // allowed to describe what the reading looks for, because it is labelled
    // as an example - the thing being refused here is a claim about now.
    expect(rendered()).not.toMatch(/We read the public site/i)
  })

  it('sends a hiker to the app, where the reading needs an account', () => {
    expect(source()).toContain('/app/nominate')
  })

  it('says why signing in is asked for at all', () => {
    // Not a hoop. A page that asks for an account without saying why reads as
    // a sign-up wall, and this one is standing in front of somebody doing a
    // favour for a club they are not a member of.
    expect(source()).toMatch(/sign in|signed in/i)
  })

  it('still refuses flat files where a hiker can read it', () => {
    // The sentence that survives all of this, because the person reading is
    // about to go and ask a club for something: "ask them for the layer
    // behind it" is what makes that ask possible.
    expect(source()).toMatch(/PDF/)
  })
})
