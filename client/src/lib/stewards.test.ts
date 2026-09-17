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
  terms: null,
  termsSource: null,
  layers: ['A.T. Centerline', 'A.T. Shelters'],
  keys: ['centerline'],
  support: null,
  store: null,
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
        support: null,
        store: null,
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
        terms: null,
        termsSource: null,
        attribution:
          'New York State Office of Parks, Recreation and Historic Preservation',
        layers: [],
        keys: ['oprhp_trails', 'oprhp_trail_closures'],
        support: null,
        store: null,
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
        terms: null,
        termsSource: null,
        layers: [],
        keys: ['centerline'],
        support: null,
        store: null,
      },
    ])
    expect(table['centerline']).toEqual({ attribution: null })
  })

  it('is empty for an empty steward list', () => {
    expect(trailSourceTableFrom(EMPTY_STEWARDS)).toEqual({})
  })
})

describe('the support and store records (#932, #1574)', () => {
  const SUPPORT = {
    donate_url: 'https://www.nynjtc.org/support/',
    donate_cta: 'Donate Today',
    donate_surfaces: ['sources_screen', 'trail_card'],
  }
  const STORE = {
    store_url: 'https://store.nynjtc.org/collections/maps?utm_source=ourhike',
    store_cta: 'Trail Maps',
    store_surfaces: ['sources_screen', 'hike_detail', 'trail_sheet'],
    paper_maps: [
      {
        handle: 'harriman-bear-mountain-trails-map',
        title: 'Harriman-Bear Mountain Trails Map',
        url: 'https://store.nynjtc.org/products/harriman-bear-mountain-trails-map?utm_source=ourhike',
        sheets: ['118', '119'],
        covers: ['Harriman State Park'],
        sheet_covers: {
          '118': ['Southern Harriman State Park'],
          '119': ['Bear Mountain State Park'],
        },
      },
    ],
  }

  it('reads a support record whole: the url, the org’s own button, the screens and the recipient', () => {
    const steward = only({
      stewards: [
        { ...ATC, support: { ...SUPPORT, donate_recipient: 'Natural Heritage Trust' } },
      ],
    })

    expect(steward.support).toEqual({
      donateUrl: 'https://www.nynjtc.org/support/',
      donateCta: 'Donate Today',
      donateRecipient: 'Natural Heritage Trust',
      donateSurfaces: ['sources_screen', 'trail_card'],
    })
  })

  it('reads support with no donate_recipient as recipient null, not as a missing record', () => {
    expect(
      only({ stewards: [{ ...ATC, support: SUPPORT }] }).support?.donateRecipient,
    ).toBeNull()
  })

  it('drops a support record missing its button text or its screens, rather than half a button', () => {
    const { donate_cta: _cta, ...withoutCta } = SUPPORT
    const { donate_surfaces: _surfaces, ...withoutSurfaces } = SUPPORT

    expect(only({ stewards: [{ ...ATC, support: withoutCta }] }).support).toBeNull()
    expect(only({ stewards: [{ ...ATC, support: withoutSurfaces }] }).support).toBeNull()
    expect(
      only({ stewards: [{ ...ATC, support: { ...SUPPORT, donate_surfaces: [] } }] })
        .support,
    ).toBeNull()
  })

  it('refuses a donate_url that is not https', () => {
    expect(
      only({
        stewards: [
          { ...ATC, support: { ...SUPPORT, donate_url: 'javascript:alert(1)' } },
        ],
      }).support,
    ).toBeNull()
  })

  it('reads a store record with its products, sheets and per-sheet covers, camel-cased', () => {
    const steward = only({ stewards: [{ ...ATC, store: STORE }] })

    expect(steward.store).toEqual({
      storeUrl: 'https://store.nynjtc.org/collections/maps?utm_source=ourhike',
      storeCta: 'Trail Maps',
      storeSurfaces: ['sources_screen', 'hike_detail', 'trail_sheet'],
      paperMaps: [
        {
          handle: 'harriman-bear-mountain-trails-map',
          title: 'Harriman-Bear Mountain Trails Map',
          url: 'https://store.nynjtc.org/products/harriman-bear-mountain-trails-map?utm_source=ourhike',
          sheets: ['118', '119'],
          covers: ['Harriman State Park'],
          sheetCovers: {
            '118': ['Southern Harriman State Park'],
            '119': ['Bear Mountain State Park'],
          },
        },
      ],
    })
  })

  it('drops a product with no sheets or no https url and keeps the store link', () => {
    const steward = only({
      stewards: [
        {
          ...ATC,
          store: {
            ...STORE,
            paper_maps: [
              { ...STORE.paper_maps[0], sheets: [] },
              { ...STORE.paper_maps[0], url: 'http://store.nynjtc.org/x' },
            ],
          },
        },
      ],
    })

    expect(steward.store?.storeCta).toBe('Trail Maps')
    expect(steward.store?.paperMaps).toEqual([])
  })

  it('reads a store record with no store_surfaces as no store at all', () => {
    const { store_surfaces: _surfaces, ...withoutSurfaces } = STORE

    expect(only({ stewards: [{ ...ATC, store: withoutSurfaces }] }).store).toBeNull()
  })

  it('reads a record that carries neither as null and null - the state before #932', () => {
    const steward = only({
      stewards: [{ provider: 'OSM', name: 'OpenStreetMap contributors' }],
    })

    expect(steward.support).toBeNull()
    expect(steward.store).toBeNull()
  })
})
