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
})
