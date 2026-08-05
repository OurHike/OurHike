import { describe, it, expect, afterEach } from 'vitest'
import {
  backgroundOverride,
  dataSaverConnection,
  dataSaverEnabled,
  effectiveBackground,
} from './dataSaver'
import { DEFAULT_PREFERENCES } from './userPreferences'

// The live background is the DEFAULT, so without this every hiker with signal
// pulls tiles whether or not they wanted to spend the data. What is asserted
// here is the decision itself, kept as a pure function precisely so it can be:
// which background actually gets drawn, and whether the app owes the hiker an
// explanation for it.

function setConnection(connection: unknown): void {
  Object.defineProperty(navigator, 'connection', {
    value: connection,
    configurable: true,
    writable: true,
  })
}

afterEach(() => {
  // Deleted rather than set to undefined, so the next test sees the property
  // genuinely absent - which is the iOS case, and a different code path from
  // "present but empty".
  Reflect.deleteProperty(navigator, 'connection')
})

describe('dataSaverEnabled', () => {
  it('is true when the phone says data is being saved', () => {
    setConnection({ saveData: true })

    expect(dataSaverEnabled()).toBe(true)
  })

  it('is false when the phone says it is not', () => {
    setConnection({ saveData: false })

    expect(dataSaverEnabled()).toBe(false)
  })

  it('is false where the API does not exist at all, which is every iPhone', () => {
    // Safari implements no part of the Network Information API. That is a
    // supported state, not a failure - and the honest answer there is "we do
    // not know", which must resolve to "do not withhold the map".
    expect(dataSaverConnection()).toBeUndefined()
    expect(dataSaverEnabled()).toBe(false)
  })

  it('is false when the connection exists but reports nothing', () => {
    setConnection({})

    expect(dataSaverEnabled()).toBe(false)
  })

  it.each([['yes'], [1], [{}], [null]])(
    'refuses to read %s as "saving data" - a truthy value is not consent',
    (value) => {
      // Compared against `true` rather than coerced on purpose: guessing that
      // someone is metered and quietly withholding contours is the worse of
      // the two ways to be wrong.
      setConnection({ saveData: value })

      expect(dataSaverEnabled()).toBe(false)
    },
  )
})

describe('effectiveBackground, with the corridor downloaded', () => {
  it('draws the download only when Data Saver is on', () => {
    expect(effectiveBackground('hiking_topo_live', true, true)).toBe('usgs_topo_offline')
  })

  it('leaves the live sheet alone when it is off', () => {
    expect(effectiveBackground('hiking_topo_live', false, true)).toBe('hiking_topo_live')
  })

  it('never upgrades an offline choice into fetching tiles', () => {
    // The override only ever subtracts. Someone who asked for no background
    // requests must not start making them because their connection improved.
    expect(effectiveBackground('usgs_topo_offline', false, true)).toBe(
      'usgs_topo_offline',
    )
    expect(effectiveBackground('usgs_topo_offline', true, true)).toBe('usgs_topo_offline')
  })

  it('overrides the shipped default, which is the case that matters', () => {
    // The whole point: the default was our guess, and Data Saver is a better
    // signal about someone's plan than our guess.
    expect(effectiveBackground(DEFAULT_PREFERENCES.background_source, true, true)).toBe(
      'usgs_topo_offline',
    )
  })
})

describe('effectiveBackground, with nothing downloaded', () => {
  // The reported bug. "Downloaded only" with no download draws no corridor and
  // fetches nothing, so the whole screen is the paper backdrop - which nobody
  // chose and which no other part of the app can recover from. Both overrides
  // wait until there is something offline to honour them with.
  it('draws the live sheet even when the hiker picked downloaded-only', () => {
    expect(effectiveBackground('usgs_topo_offline', false, false)).toBe(
      'hiking_topo_live',
    )
  })

  it('draws the live sheet even when Data Saver is on', () => {
    // The consent rule still protects everything it can: it costs a hiker
    // roughly 2 MB they did not ask for, against an app that opens on blank
    // paper. Once a download exists, Data Saver subtracts again - the case
    // above proves that has not changed.
    expect(effectiveBackground('hiking_topo_live', true, false)).toBe('hiking_topo_live')
    expect(effectiveBackground('usgs_topo_offline', true, false)).toBe('hiking_topo_live')
  })

  it('leaves the default exactly as it was', () => {
    expect(effectiveBackground(DEFAULT_PREFERENCES.background_source, false, false)).toBe(
      'hiking_topo_live',
    )
  })
})

describe('backgroundOverride', () => {
  it('names Data Saver when that is what changed the map', () => {
    expect(backgroundOverride('hiking_topo_live', true, true)).toBe('data-saver')
  })

  it('is null when Data Saver merely agrees with what was already picked', () => {
    // Telling someone their preference was overridden when it was honoured is
    // its own small lie, and Settings is where they would go to find out why
    // the map looks different.
    expect(backgroundOverride('usgs_topo_offline', true, true)).toBeNull()
  })

  it('is null when nothing is overriding anything', () => {
    expect(backgroundOverride('hiking_topo_live', false, true)).toBeNull()
    expect(backgroundOverride('usgs_topo_offline', false, true)).toBeNull()
  })

  it('names the missing download when that is the reason, not Data Saver', () => {
    // The two are opposite in kind - one withholds the live sheet, the other
    // supplies it - so a screen that reported the wrong one would tell a hiker
    // their tiles were being saved while the app fetched them.
    expect(backgroundOverride('usgs_topo_offline', false, false)).toBe(
      'nothing-downloaded',
    )
    expect(backgroundOverride('usgs_topo_offline', true, false)).toBe(
      'nothing-downloaded',
    )
  })

  it('reports nothing when the live sheet was what they wanted anyway', () => {
    // Data Saver is on and being ignored, but the drawn background is the one
    // in settings, so there is no mismatch to explain.
    expect(backgroundOverride('hiking_topo_live', true, false)).toBeNull()
  })
})
