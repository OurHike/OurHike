import { describe, it, expect } from 'vitest'
import { HERO_PHOTOS, pickHero } from './heroPhotos'

// The first-run backdrop pool (#1054). What is pinned here is the part a
// wrong edit would break silently: the pool is exactly the maintainer's
// seventeen reviewed candidates, every entry carries the credit its licence
// conditions on, and the draw can never step outside the array.

describe('the hero pool', () => {
  it('is the seventeen reviewed candidates, no more and no fewer', () => {
    // Adding an eighteenth photo is not a matter of pushing to this array -
    // it is a licence and privacy review first (the module header). This
    // count is the tripwire that makes the shortcut visible.
    expect(HERO_PHOTOS).toHaveLength(17)
  })

  it('gives every photo a source and a credit that names a licence', () => {
    for (const photo of HERO_PHOTOS) {
      expect(photo.src).not.toBe('')
      // CC families or the public domain - the only terms the gallery review
      // admitted. A credit that stops naming one is a licence condition
      // silently dropped.
      expect(photo.credit).toMatch(/ · (CC[0 ]|CC BY|Public domain)/)
    }
  })

  it('draws deterministically from the injected random', () => {
    expect(pickHero(() => 0)).toBe(HERO_PHOTOS[0])
    expect(pickHero(() => 0.999999)).toBe(HERO_PHOTOS[HERO_PHOTOS.length - 1])
  })

  it('never steps outside the pool, even for a random() that returns 1', () => {
    // Math.random() is [0, 1), but pickHero must not rely on every caller
    // knowing that - a test's stub or a future seeded source may hand it
    // exactly 1, and index 17 of 17 is a crash on a hiker's first screen.
    expect(pickHero(() => 1)).toBe(HERO_PHOTOS[HERO_PHOTOS.length - 1])
  })
})
