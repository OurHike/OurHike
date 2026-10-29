import { describe, expect, it } from 'vitest'
import { isUnitedStates, paidChoiceAllowed } from './storefront'

// Which installs may offer a paid choice (#1876): the website always; a
// store app only on a US store account, and never on a guess.

const store = (answer: () => Promise<{ country?: string }>) => () => ({
  getCountry: answer,
})

describe('the storefront check', () => {
  it('reads both stores’ spellings of the United States', () => {
    expect(isUnitedStates('USA')).toBe(true)
    expect(isUnitedStates('us')).toBe(true)
    expect(isUnitedStates('CAN')).toBe(false)
    expect(isUnitedStates('DE')).toBe(false)
    expect(isUnitedStates(undefined)).toBe(false)
  })

  it('always allows the website, without asking any store', async () => {
    const never = store(() => Promise.reject(new Error('asked')))
    expect(await paidChoiceAllowed(false, never)).toBe(true)
  })

  it('allows a store app on a US account', async () => {
    expect(
      await paidChoiceAllowed(
        true,
        store(async () => ({ country: 'USA' })),
      ),
    ).toBe(true)
  })

  it('refuses a store app on any other account, with no account, or when the store errs', async () => {
    expect(
      await paidChoiceAllowed(
        true,
        store(async () => ({ country: 'DEU' })),
      ),
    ).toBe(false)
    expect(
      await paidChoiceAllowed(
        true,
        store(async () => ({})),
      ),
    ).toBe(false)
    expect(
      await paidChoiceAllowed(
        true,
        store(() => Promise.reject(new Error('no billing'))),
      ),
    ).toBe(false)
  })

  it('refuses when the store does not answer in time, rather than waiting on it', async () => {
    const silent = store(() => new Promise(() => {}))
    expect(await paidChoiceAllowed(true, silent, 10)).toBe(false)
  })
})
