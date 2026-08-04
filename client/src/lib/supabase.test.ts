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
  it('offers Google and email, and not Apple', () => {
    // Apple needs a $99/yr Developer Program membership that the other two do
    // not (LAUNCH_CHECKLIST.md 4.3), so it is opt-in rather than assumed.
    expect(ENABLED_PROVIDERS).toEqual(['google', 'email'])
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
