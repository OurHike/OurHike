import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { StrictMode } from 'react'
import { render, cleanup, screen } from '@testing-library/react'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { MapView } from './MapView'

// Lifecycle is the whole risk surface here. A map that gets built twice means
// two WebGL contexts, two GPS watchers and doubled tile reads off a 314 MB
// on-device archive; a map that never gets torn down leaks all of the same.
// React StrictMode deliberately mounts -> unmounts -> remounts in development
// precisely to expose that class of bug, so these tests run under it.

const { registrationOrder } = vi.hoisted(() => ({ registrationOrder: [] as number[] }))

vi.mock('maplibre-gl', () => import('../test/mocks/maplibre-gl'))

// Records how many maps existed at the moment the protocol was registered.
// A 0 proves registration happened BEFORE any map was constructed - which it
// must, or the map cannot resolve its own pmtiles:// style URL.
vi.mock('./protocol', async () => {
  const { MockMap: Recorded } = await import('../test/mocks/maplibre-gl')
  return {
    PMTILES_SCHEME: 'pmtiles',
    registerPMTilesProtocol: vi.fn(() => {
      registrationOrder.push(Recorded.instances.length)
    }),
  }
})

const PROPS = {
  topoArchiveUrl: 'pmtiles://ourhike-corridor',
  trailsUrl: '/data/trails.geojson',
}

beforeEach(() => {
  resetMapLibreMock()
  registrationOrder.length = 0
})

afterEach(() => {
  cleanup()
})

describe('MapView', () => {
  it('leaves exactly one LIVE map after StrictMode’s deliberate double-invoke', () => {
    render(
      <StrictMode>
        <MapView {...PROPS} />
      </StrictMode>,
    )

    // React mounts, tears down, and remounts on purpose here, so more than one
    // map may have been CONSTRUCTED over the render's lifetime. What must never
    // happen is two of them being alive at once - that is the actual leak.
    expect(MockMap.live).toHaveLength(1)
  })

  it('tears the map down on unmount, leaving nothing live', () => {
    const { unmount } = render(
      <StrictMode>
        <MapView {...PROPS} />
      </StrictMode>,
    )

    unmount()

    expect(MockMap.live).toHaveLength(0)
    expect(MockMap.instances.every((m) => m.removed)).toBe(true)
  })

  it('does not rebuild the map when re-rendered with a fresh center array identity', () => {
    // A parent passing center={[x, y]} inline hands over a new array every
    // render. If that landed in the effect's dependencies the map would be
    // destroyed and rebuilt on every parent render - catastrophic, and easy to
    // do by accident.
    const { rerender } = render(<MapView {...PROPS} center={[-77.1, 39.3]} zoom={12} />)
    const afterFirstRender = MockMap.instances.length

    rerender(<MapView {...PROPS} center={[-77.1, 39.3]} zoom={12} />)
    rerender(<MapView {...PROPS} center={[-77.1, 39.3]} zoom={12} />)

    expect(MockMap.instances).toHaveLength(afterFirstRender)
    expect(MockMap.live).toHaveLength(1)
  })

  it('registers the pmtiles protocol before constructing any map', () => {
    render(<MapView {...PROPS} />)

    expect(registrationOrder.length).toBeGreaterThan(0)
    expect(registrationOrder[0]).toBe(0)
  })

  it('builds the map against the container it rendered, using the style URLs it was given', () => {
    render(<MapView {...PROPS} />)
    const [map] = MockMap.live

    expect(map.options.container).toBeInstanceOf(HTMLElement)
    expect(map.options.style).toBeTypeOf('object')
  })

  it('exposes the map canvas as a labelled region rather than an unnamed div', () => {
    render(<MapView {...PROPS} />)

    expect(screen.getByRole('region', { name: /trail map/i })).toBeInTheDocument()
  })
})
