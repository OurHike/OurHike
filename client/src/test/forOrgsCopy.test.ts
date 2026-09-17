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

  it('links For clubs now that the page exists', () => {
    expect(nav).toMatch(/'\/for-orgs\/', label: 'For clubs'/)
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
