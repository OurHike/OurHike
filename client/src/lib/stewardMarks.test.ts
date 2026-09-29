import { describe, it, expect } from 'vitest'
import { stewardMarkForName, STEWARD_MARK_COUNT } from './stewardMarks'
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
