import { afterEach, describe, expect, it } from 'vitest'
import {
  PACKED_ESSENTIALS_KEY,
  REI_AFFILIATE_LINK,
  TEN_ESSENTIALS,
  readPackedEssentials,
  reiLink,
  writePackedEssentials,
} from './tenEssentials'

afterEach(() => {
  window.localStorage.clear()
})

describe('the Ten Essentials list (#1689)', () => {
  it('has ten entries with ten different ids', () => {
    expect(TEN_ESSENTIALS).toHaveLength(10)
    expect(new Set(TEN_ESSENTIALS.map((e) => e.id)).size).toBe(10)
  })

  it('links every entry to an REI category page (/c/ or /s/), never to one product', () => {
    for (const essential of TEN_ESSENTIALS) {
      expect(essential.reiPath).toMatch(/^\/[cs]\/[a-z-]+$/)
    }
  })

  it('tells a hiker that navigation means a map and compass, not only this phone', () => {
    const navigation = TEN_ESSENTIALS.find((e) => e.id === 'navigation')
    expect(navigation?.note).toMatch(/not only a phone/)
  })
})

describe('reiLink', () => {
  it('ships with no affiliate code, so every link is a plain REI page', () => {
    // The banner's commission sentence keys off this. Flipping it is a
    // deliberate commit once the maintainer has an account (lib docstring).
    expect(REI_AFFILIATE_LINK).toBeNull()
    expect(reiLink({ reiPath: '/c/headlamps' })).toBe('https://www.rei.com/c/headlamps')
  })

  it('puts the REI page, URL-encoded, where an affiliate template says {url}', () => {
    const link = reiLink(
      { reiPath: '/c/headlamps' },
      'https://track.example/click?id=42&url={url}',
    )
    expect(link).toBe(
      'https://track.example/click?id=42&url=https%3A%2F%2Fwww.rei.com%2Fc%2Fheadlamps',
    )
  })
})

describe('the packed checklist on this phone', () => {
  it('reads back what was written, in the list order rather than the tick order', () => {
    writePackedEssentials(new Set(['water', 'navigation']))
    expect([...readPackedEssentials()]).toEqual(['navigation', 'water'])
    expect(window.localStorage.getItem(PACKED_ESSENTIALS_KEY)).toBe(
      JSON.stringify(['navigation', 'water']),
    )
  })

  it('reads nothing ticked when nothing was ever written', () => {
    expect(readPackedEssentials().size).toBe(0)
  })

  it('reads nothing ticked from a value it cannot parse, rather than guessing a tick', () => {
    for (const junk of ['not json', 'null', '{"navigation":true}', '42']) {
      window.localStorage.setItem(PACKED_ESSENTIALS_KEY, junk)
      expect(readPackedEssentials().size).toBe(0)
    }
  })

  it('drops an id this build does not know and keeps the ones it does', () => {
    window.localStorage.setItem(
      PACKED_ESSENTIALS_KEY,
      JSON.stringify(['headlamp', 'bear-spray', 7]),
    )
    expect([...readPackedEssentials()]).toEqual(['headlamp'])
  })

  it('keeps out of the synced preferences record (lib/pace.ts reason)', () => {
    writePackedEssentials(new Set(['knife']))
    expect(window.localStorage.getItem('ourhike:preferences')).toBeNull()
  })
})
