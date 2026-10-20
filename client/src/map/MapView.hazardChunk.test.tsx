// map/hazardAreaTaps.ts reaches MapView behind import(), and a chunk can fail
// to arrive: a precache that a service-worker update left stale, on a phone
// with no signal to fetch the new one. MapView kept that import's promise at
// module scope, so a failure was kept with it, and no hazard area drew or
// answered a tap again for the rest of the app's life. These hold the next
// use to a fresh import.
//
// Its own file because the module is mocked to fail once, for every test here;
// the other mocks are MapView.test.tsx's, without the recording.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, render, waitFor } from '@testing-library/react'
import { resetMapLibreMock } from '../test/mocks/maplibre-gl'
import type { HazardArea } from '../lib/hazardAreas'
import { loadMapEngine } from './mapEngineLoader'
import { MapView } from './MapView'

const chunk = vi.hoisted(() => ({
  loads: 0,
  attachHazardData: vi.fn(() => () => undefined),
  attachHazardTaps: vi.fn(() => () => undefined),
}))

vi.mock('maplibre-gl', () => import('../test/mocks/maplibre-gl'))
vi.mock('./protocol', () => ({
  PMTILES_SCHEME: 'pmtiles',
  registerPMTilesProtocol: vi.fn(),
}))
vi.mock('./basemap', () => ({ registerBasemapProtocol: vi.fn() }))
vi.mock('./networkTiles', () => ({
  NETWORK_SCHEME: 'network',
  NETWORK_TILES_URL: 'network://{z}/{x}/{y}',
  NETWORK_TILES_LAYER: 'trails',
  registerNetworkProtocol: vi.fn(),
}))
vi.mock('./mapWorker', () => ({
  registerMapWorker: vi.fn(() => '/assets/maplibre-gl-worker-test.js'),
}))
vi.mock('./hazardAreaTaps', () => {
  chunk.loads += 1
  if (chunk.loads === 1) {
    throw new TypeError('Failed to fetch dynamically imported module')
  }
  return {
    attachHazardData: chunk.attachHazardData,
    attachHazardTaps: chunk.attachHazardTaps,
  }
})

const PROPS = {
  topoArchiveUrl: 'pmtiles://ourhike-corridor',
  trailsUrl: '/data/trails.geojson',
}

/** MapView reads only how many areas there are; everything else about one is
 *  map/hazardAreaTaps.ts's, which is mocked here. */
const AREA = { hazard: 'hunting' } as unknown as HazardArea

beforeEach(async () => {
  resetMapLibreMock()
  await loadMapEngine()
})

afterEach(() => {
  cleanup()
})

describe('map/hazardAreaTaps.ts failing to load once', () => {
  it('is imported again the next time there are areas to draw, and draws them', async () => {
    const { rerender } = render(<MapView {...PROPS} hazardAreas={[AREA]} />)
    await waitFor(() => expect(chunk.loads).toBe(1))
    // Let the failed import settle before looking.
    await act(async () => {})
    expect(chunk.attachHazardData).not.toHaveBeenCalled()

    // The next conditions read hands the map its areas again, as a new list.
    rerender(<MapView {...PROPS} hazardAreas={[AREA]} />)

    await waitFor(() => expect(chunk.attachHazardData).toHaveBeenCalled())
    expect(chunk.loads).toBe(2)
  })
})
