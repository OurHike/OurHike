import { describe, expect, it } from 'vitest'
import {
  NYNJTC_MAP_SHEETS_KEY,
  parseMapSheets,
  pointInRing,
  sheetsContaining,
} from './mapSheets'

// What the phone makes of pipeline/archive_nynjtc_sheet_extents.py's
// document (#1574). Reading the archive is a fetch like any conditions
// artifact; what is pinned here is the parse and the point test, where a
// wrong answer is a hiker sent to buy the wrong sheet.

const RING_118 = [
  [-74.2356, 41.1115],
  [-74.2356, 41.2534],
  [-73.9868, 41.2534],
  [-73.9868, 41.1115],
] as const

describe('the archive key', () => {
  it('is archive/nynjtc_map_sheets.json, at the bucket root', () => {
    expect(NYNJTC_MAP_SHEETS_KEY).toBe('archive/nynjtc_map_sheets.json')
  })
})

describe('parseMapSheets', () => {
  it('reads a sheet’s corners and the product the archive names', () => {
    const sheets = parseMapSheets({
      sheets: {
        '118': { bounds: RING_118, product: 'harriman-bear-mountain-trails-map' },
      },
    })

    expect(sheets).toEqual({
      '118': { bounds: RING_118, product: 'harriman-bear-mountain-trails-map' },
    })
  })

  it('drops a sheet the archive lists with no footprint - Catskill 145, which Avenza does not sell', () => {
    const sheets = parseMapSheets({
      sheets: {
        '118': { bounds: RING_118, product: 'x' },
        '145': { bounds: null, product: 'catskill-trails-map' },
      },
    })

    expect(Object.keys(sheets ?? {})).toEqual(['118'])
  })

  it('drops a footprint that does not read as corners, and keeps the rest', () => {
    const sheets = parseMapSheets({
      sheets: {
        '118': { bounds: RING_118, product: 'x' },
        '119': {
          bounds: [
            [-74, 'north'],
            [-74, 41],
          ],
          product: 'x',
        },
        '120': {
          bounds: [
            [-74, 41],
            [-74, 42],
          ],
          product: 'x',
        },
      },
    })

    expect(Object.keys(sheets ?? {})).toEqual(['118'])
  })

  it('refuses a document with no sheets object at all, rather than reading it as empty', () => {
    expect(parseMapSheets({})).toBeNull()
    expect(parseMapSheets(null)).toBeNull()
    expect(parseMapSheets({ sheets: [] })).toBeNull()
  })

  it('reads a product missing or empty as null', () => {
    const sheets = parseMapSheets({
      sheets: { '118': { bounds: RING_118, product: '' } },
    })

    expect(sheets?.['118'].product).toBeNull()
  })
})

describe('pointInRing', () => {
  it('holds a point inside sheet 118’s box and not one outside it', () => {
    expect(pointInRing(RING_118, -74.09, 41.17)).toBe(true)
    expect(pointInRing(RING_118, -74.09, 41.3)).toBe(false)
    expect(pointInRing(RING_118, -73.9, 41.17)).toBe(false)
  })

  it('works on a ring given in either winding', () => {
    const reversed = [...RING_118].reverse()

    expect(pointInRing(reversed, -74.09, 41.17)).toBe(true)
  })
})

describe('sheetsContaining', () => {
  it('lists every sheet holding the point, in sheet order', () => {
    const sheets = {
      '119': {
        bounds: [
          [-74.2095, 41.2238],
          [-74.2095, 41.3477],
          [-73.9192, 41.3477],
          [-73.9192, 41.2238],
        ] as const,
        product: null,
      },
      '118': { bounds: RING_118, product: null },
    }

    expect(sheetsContaining(sheets, -74.1, 41.24)).toEqual(['118', '119'])
    expect(sheetsContaining(sheets, -74.1, 41.3)).toEqual(['119'])
    expect(sheetsContaining(sheets, -80, 37)).toEqual([])
  })
})

// The read itself, against a stubbed bucket. config.ts reads
// VITE_DATA_BASE_URL once at module load and it is unset under test, so each
// case imports the module fresh - lib/publishedConditions.test.ts's pattern.
import 'fake-indexeddb/auto'
import { clear } from 'idb-keyval'
import { afterEach, beforeEach, vi } from 'vitest'

const BASE = 'https://cdn.example.org'

async function loadWithBase(base: string | undefined) {
  vi.resetModules()
  vi.stubEnv('VITE_DATA_BASE_URL', base ?? '')
  return await import('./mapSheets')
}

const ARCHIVE = {
  generated_at: '2026-09-17T14:20:23Z',
  sheets: { '118': { bounds: RING_118, product: 'harriman-bear-mountain-trails-map' } },
}

describe('fetchMapSheets', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    // An empty store per case, so a copy one case kept never answers for
    // another. Cleared through idb-keyval rather than by swapping the
    // IndexedDB factory: the library keeps its database handle across
    // vi.resetModules, so a new factory is a database nothing reads.
    await clear()
  })
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.restoreAllMocks()
  })

  it('reads archive/nynjtc_map_sheets.json from the bucket root, never a release folder', async () => {
    const fetched = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(
        async () => new Response(JSON.stringify(ARCHIVE), { status: 200 }),
      )
    const { fetchMapSheets } = await loadWithBase(BASE)

    const sheets = await fetchMapSheets(true)

    expect(fetched).toHaveBeenCalledWith(
      `${BASE}/archive/nynjtc_map_sheets.json`,
      expect.anything(),
    )
    expect(Object.keys(sheets ?? {})).toEqual(['118'])
  })

  it('answers null with no bucket configured, and asks nothing', async () => {
    const fetched = vi.spyOn(globalThis, 'fetch')
    const { fetchMapSheets } = await loadWithBase(undefined)

    expect(await fetchMapSheets(true)).toBeNull()
    expect(fetched).not.toHaveBeenCalled()
  })

  it('serves the copy it kept when the phone is offline, and fires no request', async () => {
    const fetched = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(
        async () => new Response(JSON.stringify(ARCHIVE), { status: 200 }),
      )
    const first = await loadWithBase(BASE)
    await first.fetchMapSheets(true)
    expect(fetched).toHaveBeenCalledTimes(1)

    // The same spy, its count cleared and its answer turned hostile: a
    // request from here on would be both counted and refused.
    fetched.mockClear()
    fetched.mockImplementation(async () => new Response('', { status: 500 }))
    const second = await loadWithBase(BASE)
    const sheets = await second.fetchMapSheets(false)

    expect(fetched).not.toHaveBeenCalled()
    expect(Object.keys(sheets ?? {})).toEqual(['118'])
  })

  it('answers null on a 404 with nothing kept - an environment the archive was never written to', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(
      async () => new Response('', { status: 404 }),
    )
    const { fetchMapSheets } = await loadWithBase(BASE)

    expect(await fetchMapSheets(true)).toBeNull()
  })
})
