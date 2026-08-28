import { describe, it, expect } from 'vitest'
import {
  HIKING_DETAIL_LEVELS,
  getHikingDetail,
  offeredHikingDetails,
} from './hikingDetail'
import { HIKING_DETAIL_LEVEL_VALUES } from './userPreferences'

describe('the hiking sheet’s levels', () => {
  it('catalogues exactly the levels the stored preference can hold', () => {
    // The enum and this table are the same fact said twice, and preferences.ts
    // guards a stored value against the enum. A level here that the preference
    // cannot hold is unreachable; one there that this lacks throws on read.
    expect(HIKING_DETAIL_LEVELS.map((d) => d.level).sort()).toEqual(
      [...HIKING_DETAIL_LEVEL_VALUES].sort(),
    )
  })

  it('offers only levels whose artifacts are actually in the bucket', () => {
    // packages.ts's memory, one level up: "the app was offering a Light tier
    // that did not exist" - a 404 on a mountain. Light WAS that case between
    // #1088 (which named its artifacts) and #1107 (which built them), and this
    // line held it out of the picker for the day and a half in between.
    //
    // All three are published now, so the filter removes nothing - which makes
    // this the tripwire rather than the guard. A level added to the table
    // before its build has run turns this red, and the red is the reminder to
    // check that the picker greys the new rung instead of dropping it.
    const offered = offeredHikingDetails().map((d) => d.level)

    expect(offered).toEqual(['light', 'standard', 'fine'])
  })

  it('states no size at all, so none can go stale', () => {
    // The grade rule from CLAUDE.md at its sharpest, and #1167's whole point.
    // A size shown before a download is what a hiker weighs against their
    // remaining storage, so it may not be a hand-copied literal wearing a
    // measurement's clothes - and these had drifted up to 34.7% before they
    // were removed. The manifest prices this sheet now; this table names it.
    //
    // Matched on the SHAPE of the key rather than on the two names that used
    // to be here, so a re-added `basemapSizeBytes` fails without anybody
    // having remembered to assert on it - and so would a differently spelled
    // one.
    for (const detail of HIKING_DETAIL_LEVELS) {
      expect(Object.keys(detail).filter((key) => /SizeBytes$/.test(key))).toEqual([])
    }
  })

  it('recommends exactly one level, and it is an offered one', () => {
    const recommended = offeredHikingDetails().filter((d) => d.recommended)

    expect(recommended).toHaveLength(1)
    expect(recommended[0].level).toBe('standard')
  })

  it('throws on a level it does not know, rather than guessing one', () => {
    expect(() => getHikingDetail('nonsense' as never)).toThrow(
      /Unknown hiking detail level/,
    )
  })
})
