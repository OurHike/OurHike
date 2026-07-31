import { describe, it, expect, vi, beforeEach } from 'vitest'

// pmtiles' own docs say the Protocol "must be added once globally" - adding it
// twice would give MapLibre two handlers for the same scheme and split the
// archive cache, so every tile read would miss. Registration therefore has to
// be idempotent no matter how many components call it.
//
// Each test resets the module registry so it gets a fresh copy of both the
// mock and the module-scope singleton under test - otherwise the first test to
// register would make every later one trivially pass.

vi.mock('maplibre-gl', () => import('../test/mocks/maplibre-gl'))

describe('registerPMTilesProtocol', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  it('registers the pmtiles protocol with MapLibre exactly once, however many times it is called', async () => {
    const { addProtocol } = await import('maplibre-gl')
    const { registerPMTilesProtocol } = await import('./protocol')

    registerPMTilesProtocol()
    registerPMTilesProtocol()
    registerPMTilesProtocol()

    expect(addProtocol).toHaveBeenCalledTimes(1)
  })

  it('registers under the "pmtiles" scheme, matching the pmtiles:// URLs the style uses', async () => {
    const { addProtocol } = await import('maplibre-gl')
    const { registerPMTilesProtocol, PMTILES_SCHEME } = await import('./protocol')

    registerPMTilesProtocol()

    expect(PMTILES_SCHEME).toBe('pmtiles')
    expect(addProtocol).toHaveBeenCalledWith(PMTILES_SCHEME, expect.any(Function))
  })

  it('hands back the same Protocol instance every time, so tile caching is never split across two', async () => {
    const { registerPMTilesProtocol } = await import('./protocol')

    const first = registerPMTilesProtocol()
    const second = registerPMTilesProtocol()

    expect(first).toBe(second)
  })

  // The bug this guards against renders a perfectly convincing map on wifi and
  // nothing at all on a ridge: an unregistered pmtiles:// URL falls through to
  // pmtiles' own FetchSource and goes to the network, so the corridor package
  // sitting in IndexedDB is downloaded and then never read.
  it('resolves the corridor archive URL to the copy in IndexedDB, not to the network', async () => {
    const { registerPMTilesProtocol, CORRIDOR_ARCHIVE_URL } = await import('./protocol')
    const { CORRIDOR_ARCHIVE_KEY, IndexedDbArchiveSource } =
      await import('./pmtilesSource')

    const protocol = registerPMTilesProtocol()
    const archive = protocol.get(CORRIDOR_ARCHIVE_KEY)

    expect(archive).toBeDefined()
    expect(archive?.source).toBeInstanceOf(IndexedDbArchiveSource)
    // The URL has to carry the same key, since that is what a lookup matches.
    expect(CORRIDOR_ARCHIVE_URL).toBe(`pmtiles://${CORRIDOR_ARCHIVE_KEY}`)
  })
})
