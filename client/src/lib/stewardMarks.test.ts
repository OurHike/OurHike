import { describe, it, expect } from 'vitest'
import {
  stewardMarkForName,
  stewardMarkForSlug,
  STEWARD_MARK_COUNT,
} from './stewardMarks'
import { longTrailMarkerSlugs } from '../map/longTrailNames'
import { trailForName } from './trails'

// The stewards' own markers (#1543), shipped by default on the maintainer's
// decision of 2026-09-30 and reached only through an `import()` from
// chrome/LineSheet.tsx so their bytes stay out of the launch path.

describe('stewardMarkForName', () => {
  it('carries a marker for all 32 stewards, so a dropped import goes red here', () => {
    // The count is the guard: these are 32 separate import statements and a
    // silently deleted one would otherwise only show as a trail quietly
    // losing its mark on a screen nobody photographs.
    expect(STEWARD_MARK_COUNT).toBe(32)
  })

  it('finds a marker for a steward trail, and folds case and spacing to do it', () => {
    expect(stewardMarkForName('Ouachita Trail')).not.toBeNull()
    expect(stewardMarkForName('  ouachita trail  ')).toBe(
      stewardMarkForName('Ouachita Trail'),
    )
  })

  it('refuses a substring, because a longer name is a different trail', () => {
    // lib/trails.ts's own refusal, and the reason this lookup is exact:
    // "Long Path Link Trail" is not the Long Path.
    expect(stewardMarkForName('Ouachita')).toBeNull()
    expect(stewardMarkForName('Ouachita Trail Spur')).toBeNull()
    expect(stewardMarkForName('')).toBeNull()
  })

  it('leaves the four registry trails to lib/trails.ts rather than answering twice', () => {
    // Two tables would be two places to change a mark, and the sheet prefers
    // the registry's - so a name in both would make that preference silent
    // rather than stated. CDT is the one that moved: it wears CDTC's own
    // mark now, from the registry, not a second copy here.
    for (const name of [
      'Appalachian Trail',
      'Long Path',
      'Pacific Crest Trail',
      'Continental Divide Trail',
    ]) {
      expect(trailForName(name)).toBeDefined()
      expect(stewardMarkForName(name)).toBeNull()
    }
  })

  it('resolves every marker to a distinct file, so no two trails share one', () => {
    const names = ['Ouachita Trail', 'Ice Age Trail', 'Buckeye Trail', 'Cohos Trail']
    const urls = names.map((n) => stewardMarkForName(n))
    expect(urls.every((u) => u !== null)).toBe(true)
    expect(new Set(urls).size).toBe(names.length)
  })
})

describe('the badge asking this module by slug', () => {
  it('finds a file for every slug longTrailNames claims a marker for', () => {
    // THE CHECK NEITHER MODULE COULD DO ALONE, and the defect that earned it:
    // map/longTrailNames.ts listed `cdt` in SLUGS_WITH_A_STEWARD_MARKER while
    // STEWARD_MARKS_BY_SLUG had no `cdt` row. map/trailBadges.ts's
    // badgeMarkImageId therefore named `trail-mark-steward-cdt`, an id nothing
    // ever registered, so the badge on the 267 USFS Continental Divide
    // segments drew an empty slot beside its name - with cdt-logo.png sitting
    // in the tree the whole time. An unavailable image is dropped rather than
    // thrown, so this failed on a phone and nowhere else.
    const unregistered = longTrailMarkerSlugs().filter(
      (s) => stewardMarkForSlug(s) === null,
    )
    expect(unregistered).toEqual([])
  })

  it('does not require the reverse, because the line sheet reaches the rest by name', () => {
    // Containment, not equality. STEWARD_MARKS_BY_SLUG carries markers for
    // trails the badge has no slug entry for; chrome/LineSheet.tsx finds those
    // through stewardMarkForName. Asserting equality here would fail on a
    // marker that is doing its job.
    const claimed = new Set(longTrailMarkerSlugs())
    expect(claimed.has('buckeye')).toBe(false)
    expect(stewardMarkForSlug('buckeye')).not.toBeNull()
  })

  it('answers for the two registry trails the badge cannot reach by source', () => {
    // map/trailBadges.ts's BADGE_MARK_BY_SOURCE is keyed by SOURCE and holds
    // only `centerline` and `nynjtc_long_path`, so a USFS segment spelled
    // "CONTINENTAL DIVIDE NST" or "PACIFIC CREST TRAIL" reaches its mark only
    // through this map - which is why cdt and pct are in it although
    // lib/trails.ts already answers both by name.
    expect(stewardMarkForSlug('cdt')).not.toBeNull()
    expect(stewardMarkForSlug('pct')).not.toBeNull()
    expect(stewardMarkForSlug('cdt')).not.toBe(stewardMarkForSlug('pct'))
  })
})
