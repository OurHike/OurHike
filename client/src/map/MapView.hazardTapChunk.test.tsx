// A hazard area's TAP after map/hazardAreaTaps.ts failed to load once.
//
// MapView.hazardChunk.test.tsx holds the data to a fresh import; this holds
// the tap. The tap was wired on whether there are areas at all, which stays
// true through the next conditions read, so after one failed import nothing
// asked for the module again: the areas drew from the retried import and
// stayed deaf to a touch for the rest of the app's life. Now the tap is
// wired again with each list, as the data is (and as the club closures' tap
// is, MapView.clubClosureChunk.test.tsx).
//
// Its own file because the module is mocked to fail once, for every test
// here, and then to load for real: the touch below goes through the real
// handler to the notice id that opens the area's sheet.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, render, waitFor } from '@testing-library/react'
import { resetMapLibreMock } from '../test/mocks/maplibre-gl'
import { liveMap } from '../test/liveMap'
import { hazardAreasOf } from '../lib/hazardAreas'
import type { TrailNotice } from '../lib/notices'
import { HAZARD_FILL_LAYER_ID, HAZARD_ID_PROPERTY } from './hazardAreaLayers'
import { loadMapEngine } from './mapEngineLoader'
import { MapView } from './MapView'

const chunk = vi.hoisted(() => ({ loads: 0 }))

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
vi.mock('./hazardAreaTaps', async (importOriginal) => {
  chunk.loads += 1
  if (chunk.loads === 1) {
    throw new TypeError('Failed to fetch dynamically imported module')
  }
  return importOriginal()
})

const PROPS = {
  topoArchiveUrl: 'pmtiles://ourhike-corridor',
  trailsUrl: '/data/trails.geojson',
}

const NOTICE_ID = 'iata_lands_hunting_regs:1'

/** An invented hunting area, as hazardAreaTaps.test.ts builds one. */
const HUNTING: TrailNotice = {
  notice_id: NOTICE_ID,
  source_key: 'iata_lands_hunting_regs',
  title: 'Fixture hunting area (example)',
  category: 'Open for public hunting',
  locality: '',
  place: {
    kind: 'geometry',
    geometry: {
      type: 'Polygon',
      coordinates: [
        [
          [-77.01, 34.3],
          [-76.99, 34.3],
          [-76.99, 34.31],
          [-77.01, 34.31],
          [-77.01, 34.3],
        ],
      ],
    },
  },
  obstructs_trail: false,
  updated_at: null,
  source_url: null,
  review_state: 'unreviewed',
  hazard: 'hunting',
}

beforeEach(async () => {
  resetMapLibreMock()
  await loadMapEngine()
})

afterEach(() => {
  cleanup()
})

describe('map/hazardAreaTaps.ts failing to load once', () => {
  it('still answers a touch on a drawn area with its notice id, which opens its sheet, once the next list loads the chunk', async () => {
    const onSelect = vi.fn()
    const { rerender } = render(
      <MapView
        {...PROPS}
        hazardAreas={hazardAreasOf([HUNTING])}
        onSelectHazardArea={onSelect}
      />,
    )
    const map = await liveMap()
    await waitFor(() => expect(chunk.loads).toBe(1))
    await act(async () => {})

    // The next conditions read hands the map its areas again, as a new list.
    rerender(
      <MapView
        {...PROPS}
        hazardAreas={hazardAreasOf([HUNTING])}
        onSelectHazardArea={onSelect}
      />,
    )
    await waitFor(() => expect(chunk.loads).toBe(2))

    // A touch on the area and nothing else, until the handler answers: the
    // answer is the proof it was wired, so no wait guesses how long that
    // takes. On the old wiring it never answers.
    map.renderedFeatures.set(HAZARD_FILL_LAYER_ID, [
      { properties: { [HAZARD_ID_PROPERTY]: NOTICE_ID } },
    ])
    await waitFor(() => {
      map.emit('click', { point: { x: 120, y: 240 } })
      expect(onSelect).toHaveBeenCalledWith(NOTICE_ID)
    })
  })
})
