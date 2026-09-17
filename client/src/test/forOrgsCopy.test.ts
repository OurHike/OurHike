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
