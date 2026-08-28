import { describe, it, expect } from 'vitest'
import {
  EMPTY_STEWARDS,
  layerCountLine,
  parseStewards,
  storedStewards,
  trailSourceTableFrom,
  type Steward,
  orgLabelFrom,
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
  keys: ['centerline'],
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

describe('orgLabelFrom, which frame 1j tallies with', () => {
  const stewards = parseStewards({
    stewards: [
      {
        name: 'NY–NJ Trail Conference',
        keys: ['nynjtc_long_path', 'nynjtc_highlands_trail'],
      },
      { name: 'Appalachian Trail Conservancy', keys: ['centerline', 'side_trails'] },
    ],
  })
  const label = orgLabelFrom(stewards)

  it('turns a source key into the organization a hiker should read', () => {
    expect(label('nynjtc_long_path')).toBe('NY–NJ Trail Conference')
    expect(label('centerline')).toBe('Appalachian Trail Conservancy')
  })

  it('shows an unclaimed key as itself rather than a prettied guess', () => {
    // Ugly and true: a raw key says "this app has a key it cannot name",
    // where a cleaned-up guess would say something nobody stands behind.
    expect(label('oprhp_trails')).toBe('oprhp_trails')
  })

  it('calls an edge with no source at all Unattributed', () => {
    expect(label(null)).toBe('Unattributed')
  })

  it('has nothing to join on when the phone holds no steward list', () => {
    const bare = orgLabelFrom(EMPTY_STEWARDS)
    expect(bare('nynjtc_long_path')).toBe('nynjtc_long_path')
  })
})

describe('the tapped-line sheet’s attribution table (#1142)', () => {
  it('keys every steward’s attribution by each of their registry keys', () => {
    const table = trailSourceTableFrom([
      {
        provider: 'NYS OPRHP',
        name: 'New York State Office of Parks, Recreation and Historic Preservation',
        trust: null,
        licence: null,
        attribution:
          'New York State Office of Parks, Recreation and Historic Preservation',
        layers: [],
        keys: ['oprhp_trails', 'oprhp_trail_closures'],
      },
    ])

    // The closures layer's key resolves to the same attribution as the trails
    // layer's - one steward, two layers - which is what lets the sheet name
    // the org that closed the ground rather than the org that drew the line.
    expect(table['oprhp_trail_closures']?.attribution).toBe(
      'New York State Office of Parks, Recreation and Historic Preservation',
    )
    expect(table['oprhp_trails']?.attribution).toBe(
      table['oprhp_trail_closures']?.attribution,
    )
  })

  it('carries a null attribution as null rather than inventing one', () => {
    const table = trailSourceTableFrom([
      {
        provider: 'ATC',
        name: 'Appalachian Trail Conservancy',
        trust: null,
        licence: null,
        attribution: null,
        layers: [],
        keys: ['centerline'],
      },
    ])
    expect(table['centerline']).toEqual({ attribution: null })
  })

  it('is empty for an empty steward list', () => {
    expect(trailSourceTableFrom(EMPTY_STEWARDS)).toEqual({})
  })
})
