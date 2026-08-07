import { describe, it, expect, vi, beforeEach } from 'vitest'
import { get } from 'idb-keyval'

// pmtiles' own docs say the Protocol "must be added once globally" - adding it
// twice would give MapLibre two handlers for the same scheme and split the
// archive cache, so every tile read would miss. Registration therefore has to
// be idempotent no matter how many components call it.
//
// Each test resets the module registry so it gets a fresh copy of both the
// mock and the module-scope singleton under test - otherwise the first test to
// register would make every later one trivially pass.

vi.mock('maplibre-gl', () => import('../test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({ get: vi.fn() }))

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

  // Two packages in the catalog means two archives resolvable by key - the
  // multi-package half of issue #200. The catalog is mocked here because the
  // real one currently has a single member; what is under test is that
  // registration is driven by the catalog rather than hardcoded to one key.
  it('registers every catalog package, each resolvable by its own key', async () => {
    vi.doMock('../lib/packages', () => ({
      MAP_PACKAGES: [
        { id: 'a', idbKey: 'ourhike:package-a', title: 'A' },
        { id: 'b', idbKey: 'ourhike:package-b', title: 'B' },
      ],
    }))
    const { registerPMTilesProtocol, packageArchiveUrl } = await import('./protocol')
    const { IndexedDbArchiveSource } = await import('./pmtilesSource')

    const protocol = registerPMTilesProtocol()
    const a = protocol.get('ourhike:package-a')
    const b = protocol.get('ourhike:package-b')

    expect(a?.source).toBeInstanceOf(IndexedDbArchiveSource)
    expect(b?.source).toBeInstanceOf(IndexedDbArchiveSource)
    expect(a).not.toBe(b)
    expect(packageArchiveUrl('ourhike:package-b')).toBe('pmtiles://ourhike:package-b')
    vi.doUnmock('../lib/packages')
  })

  /**
   * The smallest well-formed PMTiles archive: a valid header and an empty
   * root directory. Built byte-for-byte so the test states exactly what
   * "valid" means, per TESTING.md - the magic number, the spec version, and
   * a root directory of zero entries are all pmtiles' header reader checks.
   */
  function syntheticArchive(): Blob {
    const bytes = new Uint8Array(128)
    const view = new DataView(bytes.buffer)
    view.setUint16(0, 0x4d50, true) // "PM", the format's magic number
    bytes[7] = 3 // spec version
    view.setUint32(8, 127, true) // root directory offset...
    view.setUint32(16, 1, true) // ...and length: the single byte below
    bytes[97] = 1 // internal compression: none
    bytes[127] = 0 // root directory: zero entries
    return new Blob([bytes])
  }

  // The trailhead bug (#session-review): the style declares the archive
  // source on BOTH backgrounds, so on a phone with nothing downloaded the
  // first header read rejects - correctly. pmtiles' SharedPromiseCache then
  // held that rejected promise forever, so downloading the corridor changed
  // nothing: the hiker tapped "Downloaded", got blank paper, and only an app
  // restart fixed it. A failed read must be retried, not replayed.
  it('reads an archive downloaded after the first read failed, without a restart', async () => {
    const { registerPMTilesProtocol } = await import('./protocol')
    const { CORRIDOR_ARCHIVE_KEY } = await import('./pmtilesSource')

    // Nothing downloaded yet: the read rejects, as it should.
    vi.mocked(get).mockResolvedValue(undefined)
    const archive = registerPMTilesProtocol().get(CORRIDOR_ARCHIVE_KEY)!
    await expect(archive.getHeader()).rejects.toThrow(/No offline map archive/)

    // The download lands - same session, same map, no restart.
    vi.mocked(get).mockResolvedValue(syntheticArchive())

    const header = await archive.getHeader()

    expect(header.specVersion).toBe(3)
  })
})
