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
