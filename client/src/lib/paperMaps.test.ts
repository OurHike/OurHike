import { describe, expect, it } from 'vitest'
import {
  MIN_CONTAINED_CHARS,
  paperMapLead,
  paperMapsAt,
  paperMapsForPlace,
  placeNamesMatch,
  sheetLabel,
  stewardForSource,
} from './paperMaps'
import type { MapSheets } from './mapSheets'
import type { Steward } from './stewards'

// The two joins that put "buy the paper map" on a screen (#1574), pinned on
// the cases that decide whether a hiker is told the right sheet or nothing.

const HARRIMAN = {
  handle: 'harriman-bear-mountain-trails-map',
  title: 'Harriman-Bear Mountain Trails Map',
  url: 'https://store.nynjtc.org/products/harriman-bear-mountain-trails-map?utm_source=ourhike',
  sheets: ['118', '119'],
  covers: ['Harriman State Park', 'Bear Mountain State Park'],
  sheetCovers: {
    '118': ['Southern Harriman State Park', 'Long Path'],
    '119': [
      'Northern Harriman State Park',
      'Bear Mountain State Park',
      'Appalachian Trail',
    ],
  },
}

const CATSKILL = {
  handle: 'catskill-trails-map',
  title: 'Catskill Trails Map',
  url: 'https://store.nynjtc.org/products/catskill-trails-map?utm_source=ourhike',
  sheets: ['141', '142'],
  covers: ['Catskill Park'],
  sheetCovers: {
    '141': ['Hunter Mountain', 'Devil’s Path'],
    '142': ['Panther Mountain'],
  },
}

const MORRIS = {
  handle: 'morris-county-highlands-trails-map',
  title: 'Morris County Highlands Trails Map',
  url: 'https://store.nynjtc.org/products/morris-county-highlands-trails-map',
  sheets: ['125'],
  covers: [],
  sheetCovers: { '125': ['Pequannock Watershed', 'Highlands Trail'] },
}

const NORTHERN_NJ = {
  handle: 'northern-new-jersey-highlands-trails-map',
  title: 'Northern New Jersey Highlands Trails Map',
  url: 'https://store.nynjtc.org/products/northern-new-jersey-highlands-trails-map',
  sheets: ['153'],
  covers: [],
  sheetCovers: { '153': ['Pequannock Watershed north of Route 23'] },
}

function nynjtc(over: Partial<Steward> = {}): Steward {
  return {
    provider: 'NYNJTC',
    name: 'New York-New Jersey Trail Conference',
    trust: 'authoritative',
    licence: null,
    attribution: null,
    terms: null,
    termsSource: null,
    layers: ['NYNJTC Long Path'],
    keys: ['nynjtc_long_path', 'nynjtc_hike_finder'],
    support: null,
    store: {
      storeUrl: 'https://store.nynjtc.org/collections/maps',
      storeCta: 'Trail Maps',
      storeSurfaces: ['sources_screen', 'hike_detail', 'trail_sheet'],
      paperMaps: [HARRIMAN, CATSKILL, MORRIS, NORTHERN_NJ],
    },
    ...over,
  }
}

const ATC: Steward = {
  provider: 'ATC',
  name: 'Appalachian Trail Conservancy',
  trust: null,
  licence: '© ATC, used with permission',
  attribution: null,
  terms: null,
  termsSource: null,
  layers: ['A.T. Centerline'],
  keys: ['centerline'],
  support: null,
  store: null,
}

/** Sheet 118's real footprint, read off Avenza 2026-09-17, and 119's, which
 *  overlaps it between 41.2238 and 41.2534 north. */
const SHEETS: MapSheets = {
  '118': {
    bounds: [
      [-74.2356, 41.1115],
      [-74.2356, 41.2534],
      [-73.9868, 41.2534],
      [-73.9868, 41.1115],
    ],
    product: 'harriman-bear-mountain-trails-map',
  },
  '119': {
    bounds: [
      [-74.2095, 41.2238],
      [-74.2095, 41.3477],
      [-73.9192, 41.3477],
      [-73.9192, 41.2238],
    ],
    product: 'harriman-bear-mountain-trails-map',
  },
  '141': {
    bounds: [
      [-74.4121, 42.032],
      [-74.4121, 42.3472],
      [-73.9192, 42.3472],
      [-73.9192, 42.032],
    ],
    product: 'catskill-trails-map',
  },
}

describe('stewardForSource', () => {
  it('finds the steward whose registry keys include the source', () => {
    expect(stewardForSource([ATC, nynjtc()], 'nynjtc_hike_finder')?.provider).toBe(
      'NYNJTC',
    )
  })

  it('answers null for a key no steward claims, and for no key', () => {
    expect(stewardForSource([ATC, nynjtc()], 'osm_water')).toBeNull()
    expect(stewardForSource([ATC, nynjtc()], null)).toBeNull()
  })
})

describe('placeNamesMatch', () => {
  it('matches "Harriman State Park" to NYNJTC’s "Southern Harriman State Park"', () => {
    expect(placeNamesMatch('Harriman State Park', 'Southern Harriman State Park')).toBe(
      true,
    )
  })

  it('ignores case and punctuation: "Sams Point Preserve" is "Sam’s Point Preserve"', () => {
    expect(placeNamesMatch('Sams Point Preserve', 'Sam’s Point Preserve')).toBe(true)
  })

  it(`refuses a contained name shorter than MIN_CONTAINED_CHARS (${MIN_CONTAINED_CHARS}) unless it is the whole name`, () => {
    expect(placeNamesMatch('Pond', 'Trout Pond')).toBe(false)
    expect(placeNamesMatch('Park', 'Harriman State Park')).toBe(false)
    expect(placeNamesMatch('Teatown', 'Teatown')).toBe(true)
  })

  it('matches whole words in order, never a word inside another word', () => {
    expect(placeNamesMatch('Pond Lane', 'Trout Pondside Lane')).toBe(false)
    expect(placeNamesMatch('State Park Harriman', 'Southern Harriman State Park')).toBe(
      false,
    )
  })
})

describe('paperMapsForPlace (the hike detail’s join, by park name)', () => {
  it('names the product and the sheets whose park lists name the park', () => {
    const matches = paperMapsForPlace(nynjtc(), 'hike_detail', 'Harriman State Park')

    expect(matches).toHaveLength(1)
    expect(matches[0].map.handle).toBe('harriman-bear-mountain-trails-map')
    expect(matches[0].sheets).toEqual(['118', '119'])
  })

  it('matches on the product’s own covers with no sheet named', () => {
    const matches = paperMapsForPlace(nynjtc(), 'hike_detail', 'Catskill Park')

    expect(matches).toHaveLength(1)
    expect(matches[0].map.handle).toBe('catskill-trails-map')
    expect(matches[0].sheets).toEqual([])
  })

  it('answers every product that names the park when two do - the Pequannock Watershed is on both', () => {
    const handles = paperMapsForPlace(
      nynjtc(),
      'hike_detail',
      'Pequannock Watershed',
    ).map((match) => match.map.handle)

    expect(handles).toEqual([
      'morris-county-highlands-trails-map',
      'northern-new-jersey-highlands-trails-map',
    ])
  })

  it('answers nothing for a park no sheet names', () => {
    expect(paperMapsForPlace(nynjtc(), 'hike_detail', 'Vernon State Forest')).toEqual([])
  })

  it('answers nothing on a surface the organization has not granted', () => {
    const steward = nynjtc({
      store: { ...nynjtc().store!, storeSurfaces: ['sources_screen'] },
    })

    expect(paperMapsForPlace(steward, 'hike_detail', 'Harriman State Park')).toEqual([])
  })

  it('answers nothing with no steward, no store, or no park', () => {
    expect(paperMapsForPlace(null, 'hike_detail', 'Harriman State Park')).toEqual([])
    expect(paperMapsForPlace(ATC, 'hike_detail', 'Harriman State Park')).toEqual([])
    expect(paperMapsForPlace(nynjtc(), 'hike_detail', undefined)).toEqual([])
    expect(paperMapsForPlace(nynjtc(), 'hike_detail', '  ')).toEqual([])
  })
})

describe('paperMapsAt (the line sheet’s join, by ground)', () => {
  it('names the product of the one sheet holding the point - Pine Meadow Lake is on 118', () => {
    const matches = paperMapsAt([ATC, nynjtc()], SHEETS, 'trail_sheet', -74.09, 41.17)

    expect(matches).toHaveLength(1)
    expect(matches[0].map.handle).toBe('harriman-bear-mountain-trails-map')
    expect(matches[0].sheets).toEqual(['118'])
  })

  it('carries both sheets where their footprints overlap - one product, two sheets', () => {
    const matches = paperMapsAt([nynjtc()], SHEETS, 'trail_sheet', -74.1, 41.24)

    expect(matches).toHaveLength(1)
    expect(matches[0].sheets).toEqual(['118', '119'])
  })

  it('answers nothing off every sheet - McAfee Knob is a long way from Harriman', () => {
    expect(paperMapsAt([nynjtc()], SHEETS, 'trail_sheet', -80.04, 37.39)).toEqual([])
  })

  it('answers nothing without the archive, and nothing on a surface not granted', () => {
    expect(paperMapsAt([nynjtc()], null, 'trail_sheet', -74.09, 41.17)).toEqual([])
    const steward = nynjtc({
      store: { ...nynjtc().store!, storeSurfaces: ['hike_detail'] },
    })
    expect(paperMapsAt([steward], SHEETS, 'trail_sheet', -74.09, 41.17)).toEqual([])
  })

  it('joins through the phone’s own sheet lists, not the archive’s product field', () => {
    // An archive written against a newer table names a product this phone's
    // stewards do not carry: the sheet holds the point and nothing is said.
    const newer: MapSheets = {
      '199': { bounds: SHEETS['118'].bounds, product: 'a-map-this-phone-never-heard-of' },
    }

    expect(paperMapsAt([nynjtc()], newer, 'trail_sheet', -74.09, 41.17)).toEqual([])
  })
})

describe('sheetLabel', () => {
  it('reads "sheet 118" for one, "sheets 118 and 119" for two', () => {
    expect(sheetLabel(['118'])).toBe('sheet 118')
    expect(sheetLabel(['118', '119'])).toBe('sheets 118 and 119')
  })

  it('collapses a run of three or more numbered sheets to "sheets 120–123"', () => {
    expect(sheetLabel(['120', '121', '122', '123'])).toBe('sheets 120–123')
  })

  it('lists lettered or gapped sheets in full: "sheets 104, 105 and 106A"', () => {
    expect(sheetLabel(['104', '105', '106A'])).toBe('sheets 104, 105 and 106A')
    expect(sheetLabel(['140', '141', '147'])).toBe('sheets 140, 141 and 147')
  })

  it('is null for no sheets, so no caller prints "sheets "', () => {
    expect(sheetLabel([])).toBeNull()
  })
})

describe('paperMapLead', () => {
  it('names the sheet and the organization before the linked title', () => {
    const [match] = paperMapsAt([nynjtc()], SHEETS, 'trail_sheet', -74.09, 41.17)

    expect(paperMapLead(match, 'This spot')).toBe(
      'This spot is on sheet 118 of the New York-New Jersey Trail Conference’s',
    )
  })

  it('drops the sheet clause when the match named none', () => {
    const [match] = paperMapsForPlace(nynjtc(), 'hike_detail', 'Catskill Park')

    expect(paperMapLead(match, 'The park')).toBe(
      'The park is on the New York-New Jersey Trail Conference’s',
    )
  })
})
