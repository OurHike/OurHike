import { describe, it, expect, afterEach } from 'vitest'
import {
  backgroundOverridden,
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

describe('effectiveBackground', () => {
  it('draws the download only when Data Saver is on', () => {
    expect(effectiveBackground('hiking_topo_live', true)).toBe('usgs_topo_offline')
  })

  it('leaves the live sheet alone when it is off', () => {
    expect(effectiveBackground('hiking_topo_live', false)).toBe('hiking_topo_live')
  })

  it('never upgrades an offline choice into fetching tiles', () => {
    // The override only ever subtracts. Someone who asked for no background
    // requests must not start making them because their connection improved.
    expect(effectiveBackground('usgs_topo_offline', false)).toBe('usgs_topo_offline')
    expect(effectiveBackground('usgs_topo_offline', true)).toBe('usgs_topo_offline')
  })

  it('overrides the shipped default, which is the case that matters', () => {
    // The whole point: the default was our guess, and Data Saver is a better
    // signal about someone's plan than our guess.
    expect(effectiveBackground(DEFAULT_PREFERENCES.background_source, true)).toBe(
      'usgs_topo_offline',
    )
  })
})

describe('backgroundOverridden', () => {
  it('is true only when the drawn background disagrees with the chosen one', () => {
    expect(backgroundOverridden('hiking_topo_live', true)).toBe(true)
  })

  it('is false when Data Saver merely agrees with what was already picked', () => {
    // Telling someone their preference was overridden when it was honoured is
    // its own small lie, and this screen is where they would go to find out
    // why the map looks different.
    expect(backgroundOverridden('usgs_topo_offline', true)).toBe(false)
  })

  it('is false when nothing is overriding anything', () => {
    expect(backgroundOverridden('hiking_topo_live', false)).toBe(false)
    expect(backgroundOverridden('usgs_topo_offline', false)).toBe(false)
  })
})
