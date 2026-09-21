import { describe, it, expect } from 'vitest'
import { ENABLED_PROVIDERS, AUTH_CONFIGURED, getAuthClient } from './supabase'

// Which doors this app ships. A code constant since #1572, not the
// `AUTH_PROVIDERS` repository variable it was until 2026-09-20 - lib/supabase.ts
// carries the four reasons that variable was removed. What these pin is the
// list itself, because changing it is now a reviewed commit and these are the
// lines a reviewer sees change.

describe('ENABLED_PROVIDERS', () => {
  it('ships GitHub, then Google, then an emailed code - the order SignInPrompt draws them in', () => {
    // Each of the three is enabled in both Supabase projects with credentials
    // behind it (#1572). backend/check_supabase_config.py reads this same line
    // and compares it against the live project.
    //
    // THE ORDER IS PART OF THE ASSERTION, not an artefact of writing the
    // array down: screens/SignInPrompt.tsx maps this straight into buttons,
    // so the first name here is the first door a hiker meets. GitHub leads
    // since 2026-09-20, on the maintainer's instruction - "we are an open
    // source and open data project". It was Google's slot before that for no
    // reason anybody had recorded, which is the kind of default worth a test
    // going red over.
    expect(ENABLED_PROVIDERS).toEqual(['github', 'google', 'email'])
  })

  it('does not ship Apple, which needs a $99/yr membership and is deferred to v2 (#92)', () => {
    // Asserted separately from the equality above, because an absence has its
    // own reason and a reader changing the list should meet that reason here.
    expect(ENABLED_PROVIDERS).not.toContain('apple')
  })

  it('offers at least one door, so the sign-in screen is never a dead end', () => {
    // An empty list renders a screen with nothing on it but "Not now". That
    // was reachable while this was a variable - unset parsed to zero providers
    // - and is now only reachable by editing this file.
    expect(ENABLED_PROVIDERS.length).toBeGreaterThan(0)
  })
})

describe('AUTH_CONFIGURED', () => {
  it('is false when no project was configured at build time', () => {
    // Which is exactly the case under test, and the case a fork gets before
    // it sets anything up. The UI reads this to avoid offering a sign-in that
    // cannot complete - the same job DATA_CONFIGURED does for downloads.
    expect(AUTH_CONFIGURED).toBe(false)
  })
})

describe('the client, behind an import (#1302)', () => {
  it('forgets an import that failed, so the next ask tries again', async () => {
    // A chunk that did not arrive - a deploy swapping the assets mid-session,
    // a tunnel at a trailhead - is not an answer. Memoising the rejection
    // would make one dropped request the state of the app for the rest of the
    // walk: no sign-in, no outbox flush, no live conditions.
    //
    // Asserted through the module's own behaviour rather than by stubbing the
    // dynamic import, which Vitest cannot intercept for a bare specifier: with
    // no project configured (AUTH_CONFIGURED is false in this environment) the
    // client resolves to null without importing anything, so what this pins is
    // the contract every caller now depends on - a promise, and one that is
    // safe to ask for twice.
    const first = getAuthClient()
    const second = getAuthClient()

    expect(first).toBeInstanceOf(Promise)
    await expect(first).resolves.toBeNull()
    await expect(second).resolves.toBeNull()
  })
})
