// map/clubClosureTaps.ts reaches MapView behind import(), as
// map/hazardAreaTaps.ts does (MapView.hazardChunk.test.tsx), and a chunk can
// fail to arrive: a precache a service-worker update left stale, on a phone
// with no signal to fetch the new one. A failure kept would draw no club
// closure, and answer no tap on one, for the rest of the app's life. These
// hold the next use to a fresh import, and the tap to the builder's rule.
//
// Its own file because the module is mocked to fail once, for every test here.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, render, waitFor } from '@testing-library/react'
import { resetMapLibreMock } from '../test/mocks/maplibre-gl'
import type { TrailClosure } from '../lib/publishedConditions'
import { loadMapEngine } from './mapEngineLoader'
import { MapView } from './MapView'

const chunk = vi.hoisted(() => ({
  loads: 0,
  attachClubClosureData: vi.fn(() => () => undefined),
  attachClubClosureTaps: vi.fn(() => () => undefined),
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
vi.mock('./clubClosureTaps', () => {
  chunk.loads += 1
  if (chunk.loads === 1) {
    throw new TypeError('Failed to fetch dynamically imported module')
  }
  return {
    attachClubClosureData: chunk.attachClubClosureData,
    attachClubClosureTaps: chunk.attachClubClosureTaps,
  }
})

const PROPS = {
  topoArchiveUrl: 'pmtiles://ourhike-corridor',
  trailsUrl: '/data/trails.geojson',
}

/** MapView reads only how many closures there are; everything else about
 *  one is map/clubClosureTaps.ts's, which is mocked here. */
const CLOSURE = { notice_id: 'example:line' } as unknown as TrailClosure

beforeEach(async () => {
  resetMapLibreMock()
  await loadMapEngine()
})

afterEach(() => {
  cleanup()
})

describe('map/clubClosureTaps.ts failing to load once', () => {
  it('is imported again the next time there are closures to draw, and draws them and wires their tap', async () => {
    const onSelect = vi.fn()
    const { rerender } = render(
      <MapView {...PROPS} clubClosures={[CLOSURE]} onSelectClubClosure={onSelect} />,
    )
    await waitFor(() => expect(chunk.loads).toBe(1))
    await act(async () => {})
    expect(chunk.attachClubClosureData).not.toHaveBeenCalled()

    // The next conditions read hands the map its closures again, as a new
    // list.
    rerender(
      <MapView {...PROPS} clubClosures={[CLOSURE]} onSelectClubClosure={onSelect} />,
    )

    await waitFor(() => expect(chunk.attachClubClosureData).toHaveBeenCalled())
    expect(chunk.loads).toBe(2)
    expect(chunk.attachClubClosureData).toHaveBeenLastCalledWith(expect.anything(), [
      CLOSURE,
    ])
    // And the tap, which a drawn mark that opens nothing would be without.
    await waitFor(() =>
      expect(chunk.attachClubClosureTaps).toHaveBeenCalledWith(
        expect.anything(),
        onSelect,
      ),
    )
  })

  it('wires no tap on a closure while the route builder owns the tap', async () => {
    chunk.attachClubClosureTaps.mockClear()
    render(
      <MapView
        {...PROPS}
        clubClosures={[CLOSURE]}
        onSelectClubClosure={vi.fn()}
        onRouteTap={vi.fn()}
      />,
    )
    await waitFor(() => expect(chunk.attachClubClosureData).toHaveBeenCalled())
    expect(chunk.attachClubClosureTaps).not.toHaveBeenCalled()
  })
})
