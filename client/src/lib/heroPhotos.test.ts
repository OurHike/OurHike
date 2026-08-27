import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { HERO_PHOTOS, pickHero } from './heroPhotos'

// The first-run backdrop pool (#1054, grown to forty-eight by #1084). What is
// pinned here is the part a wrong edit would break silently: the pool is
// exactly the reviewed candidates, every entry carries the credit its licence
// conditions on, and the draw can never step outside the array.

describe('the hero pool', () => {
  it('is the forty-eight reviewed candidates, no more and no fewer', () => {
    // Adding a forty-ninth photo is not a matter of pushing to this array -
    // it is a licence and privacy review first (the module header). This
    // count is the tripwire that makes the shortcut visible.
    expect(HERO_PHOTOS).toHaveLength(48)
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

  it('names a photographer as well as a licence', () => {
    // The credit is rendered as "Photo: <credit>" on the frame
    // (screens/Onboarding.tsx), so a credit that is only a licence attributes
    // the work to nobody - which is the half of CC BY that a licence string
    // alone does not satisfy.
    for (const photo of HERO_PHOTOS) {
      const [who] = photo.credit.split(' · ')
      expect(who.trim().length).toBeGreaterThan(1)
    }
  })

  it('admits no NonCommercial or NoDerivatives photo, ever', () => {
    // The gate the module header describes, restated where it can fail. ND in
    // particular is not a stylistic preference here: every file in the pool is
    // resized and re-encoded from the Commons original, which is exactly the
    // derivative ND forbids.
    //
    // The LICENCE half only, and that is not fussiness - the first draft of
    // this test read the whole credit and failed on "NC Wetlands · CC0",
    // which is a photographer in North Carolina and a licence with no terms
    // at all. A name can be anything; only the half after the separator
    // asserts anything about what may be done with the photo.
    for (const photo of HERO_PHOTOS) {
      const licence = photo.credit.split(' · ').slice(1).join(' · ')
      expect(licence).not.toBe('')
      expect(licence).not.toMatch(/\bNC\b|\bND\b|NonCommercial|NoDeriv/i)
    }
  })

  it('draws each photo from a distinct file', () => {
    // Two entries pointing at one asset is a photo silently twice as likely
    // as the rest, and usually means a copy-paste in the import block rather
    // than a decision.
    expect(new Set(HERO_PHOTOS.map((photo) => photo.src)).size).toBe(HERO_PHOTOS.length)
  })

  it('records where every photo came from, in the module that ships it', () => {
    // Provenance that lives only in a pull request body is provenance nobody
    // has. The header carries one `File:` line per entry, and this is what
    // stops the array growing without it - a photo whose Commons page nobody
    // can open cannot be licence-checked again by the next person.
    const source = readFileSync(resolve(process.cwd(), 'src/lib/heroPhotos.ts'), 'utf8')
    const provenance = source.match(/^ \* {1,2}\d+ File:/gm) ?? []

    expect(provenance).toHaveLength(HERO_PHOTOS.length)
  })

  it('draws deterministically from the injected random', () => {
    expect(pickHero(() => 0)).toBe(HERO_PHOTOS[0])
    expect(pickHero(() => 0.999999)).toBe(HERO_PHOTOS[HERO_PHOTOS.length - 1])
  })

  it('never steps outside the pool, even for a random() that returns 1', () => {
    // Math.random() is [0, 1), but pickHero must not rely on every caller
    // knowing that - a test's stub or a future seeded source may hand it
    // exactly 1, and index 48 of 48 is a crash on a hiker's first screen.
    expect(pickHero(() => 1)).toBe(HERO_PHOTOS[HERO_PHOTOS.length - 1])
  })
})
