import { describe, it, expect } from 'vitest'
import {
  EMPTY_STEWARDS,
  layerCountLine,
  parseStewards,
  storedStewards,
  type Steward,
} from './stewards'

// What the phone makes of pipeline/export_sources.py's artifact (#927). The
// exporter's own tests cover which stewards get published; these cover what
// happens to the file afterwards, where the failures are a card claiming
// something its steward never recorded.

const ATC = {
  provider: 'ATC',
  name: 'Appalachian Trail Conservancy',
  trust: null,
  licence: '© ATC, used with permission',
  attribution: null,
  layers: ['A.T. Centerline', 'A.T. Shelters'],
}

function only(value: unknown): Steward {
  const parsed = parseStewards(value)
  expect(parsed).toHaveLength(1)
  return parsed[0]
}

describe('reading the published steward list', () => {
  it('carries a record through field for field', () => {
    expect(only({ stewards: [ATC] })).toEqual(ATC)
  })

  it('reads an absent artifact as no stewards, not as a failure', () => {
    // A release built before the exporter existed, and a phone that has
    // downloaded nothing. Both ordinary.
    expect(parseStewards(undefined)).toEqual(EMPTY_STEWARDS)
    expect(parseStewards(null)).toEqual(EMPTY_STEWARDS)
    expect(parseStewards({})).toEqual(EMPTY_STEWARDS)
    expect(parseStewards({ stewards: 'not a list' })).toEqual(EMPTY_STEWARDS)
  })

  it('keeps every field independently absent, because the registry is ragged', () => {
    // Measured 2026-08-23: the ATC has a licence and no attribution and no
    // tier; OpenStreetMap has an attribution and no licence. A parser that
    // required a full record would drop real organizations.
    const sparse = only({ stewards: [{ name: 'Somebody' }] })

    expect(sparse.name).toBe('Somebody')
    expect(sparse.trust).toBeNull()
    expect(sparse.licence).toBeNull()
    expect(sparse.attribution).toBeNull()
    expect(sparse.layers).toEqual([])
  })

  it('drops a record with no name, which has nothing to say', () => {
    // The one field a card cannot do without: this screen exists to say whose
    // data this is, and a nameless card answers nothing while implying there
    // is a fourth organization.
    expect(parseStewards({ stewards: [{ licence: '© Someone' }] })).toEqual([])
    expect(parseStewards({ stewards: [{ name: '   ' }] })).toEqual([])
  })

  it('treats an empty string as absent rather than as a value', () => {
    // A blank licence rendered would be an empty line under an organization's
    // name, which reads as a rendering fault rather than as "not recorded".
    const blank = only({ stewards: [{ name: 'Org', licence: '', attribution: '  ' }] })

    expect(blank.licence).toBeNull()
    expect(blank.attribution).toBeNull()
  })

  it('falls back to the name when no provider key is published', () => {
    expect(only({ stewards: [{ name: 'Org' }] }).provider).toBe('Org')
  })

  it('drops non-string entries from the layer list rather than rendering them', () => {
    const messy = only({
      stewards: [{ name: 'Org', layers: ['Real', 3, null, '', 'Also real'] }],
    })

    expect(messy.layers).toEqual(['Real', 'Also real'])
  })
})

describe('what came back out of the store', () => {
  it('re-parses rather than trusting what an older build wrote', () => {
    expect(storedStewards([ATC])).toEqual([ATC])
    expect(storedStewards({ stewards: [ATC] })).toEqual([ATC])
  })

  it('reads nothing in the store as no stewards', () => {
    expect(storedStewards(undefined)).toEqual(EMPTY_STEWARDS)
    expect(storedStewards(null)).toEqual(EMPTY_STEWARDS)
  })

  it('drops a record an older build stored without a name', () => {
    expect(storedStewards([{ name: 'Kept' }, { licence: 'no name' }])).toHaveLength(1)
  })
})

describe('the layer count', () => {
  it('counts rather than summarising', () => {
    // Frame `1h` shows "Centerline, shelters, closures · 12 layers", and the
    // first half is a human choosing three layers to stand for eleven. This
    // app has the titles and no basis for choosing among them - a
    // machine-picked three would read like an editorial summary somebody
    // wrote. The count is the true half; the description wants a registry
    // field that does not exist yet (#929).
    expect(layerCountLine({ ...ATC, layers: ['a', 'b', 'c'] })).toBe('3 layers')
  })

  it('does not say "1 layers"', () => {
    expect(layerCountLine({ ...ATC, layers: ['only one'] })).toBe('1 layer')
  })

  it('says nothing at all when no layers are published', () => {
    expect(layerCountLine({ ...ATC, layers: [] })).toBeNull()
  })
})
