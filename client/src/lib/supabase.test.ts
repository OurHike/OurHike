import { describe, it, expect } from 'vitest'
import { parseProviders, ENABLED_PROVIDERS, AUTH_CONFIGURED } from './supabase'

// Which providers a build offers is configuration, and configuration arrives
// from a host's build settings where nobody is checking spelling. The rule
// this encodes is that a bad value costs a button, never the boot.

describe('parseProviders', () => {
  it('keeps the providers that were named', () => {
    expect(parseProviders('google,email')).toEqual(['google', 'email'])
  })

  it('presents them in one fixed order, whatever order they were written in', () => {
    // Otherwise two builds enabling the same providers would lay the screen
    // out differently, and the difference would be a comma in an env var.
    expect(parseProviders('email,google')).toEqual(['google', 'email'])
    expect(parseProviders('apple,email,google')).toEqual(['google', 'apple', 'email'])
  })

  it('ignores whitespace and casing, which a settings field will contain', () => {
    expect(parseProviders(' Google , EMAIL ')).toEqual(['google', 'email'])
  })

  it('drops an unknown name rather than throwing', () => {
    // A stray comma or a typo should cost one button, not the whole app.
    expect(parseProviders('google,,facebook,email')).toEqual(['google', 'email'])
  })

  it('returns nothing for an empty setting, rather than defaulting to all', () => {
    // "None configured" is a real answer, and silently offering all three
    // would put three broken buttons in front of a hiker.
    expect(parseProviders('')).toEqual([])
    expect(parseProviders('   ')).toEqual([])
  })

  it('never invents a provider that was not named', () => {
    expect(parseProviders('google')).toEqual(['google'])
  })
})

describe('the default build', () => {
  it('offers Google alone - not Apple, and no longer email', () => {
    // v1's decided provider set (#397). Apple needs a $99/yr Developer Program
    // membership that Google does not (LAUNCH_CHECKLIST.md 4.3), so it is
    // opt-in rather than assumed, and is deferred to v2 (#92).
    //
    // Email left the default rather than never being in it, and the direction
    // matters: it was included because switching it on costs nothing, which
    // was true of the setup and false of the outcome. Supabase's built-in
    // sender is not a delivery path this project ships on, so the default was
    // putting a button on the sign-in screen whose flow could not finish -
    // including in the deployed build, which is what made it a defect rather
    // than a preference.
    expect(ENABLED_PROVIDERS).toEqual(['google'])
  })

  it('falls back to the default when the setting is blank, not to nothing', () => {
    // This test environment has VITE_AUTH_PROVIDERS unset, which is the same
    // shape CI produces when it references a repository variable nobody has
    // created: an empty string, not undefined. `??` does not catch that, and
    // an empty string parses to zero providers - which would build a working
    // app whose only sign-in screen offers no way in.
    //
    // Asserting it here rather than trusting the ?? because the failure is
    // silent: nothing throws, nothing logs, the button is just missing.
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
