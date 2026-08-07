// What the shell puts on the canvas once the reads land (#232).
//
// Its own file for the reason App.outboxRetry.test.tsx and
// App.trailData.test.tsx each have one: this needs BOTH lib/api and lib/config
// mocked as configured, and either would change the subject of every test in
// App.test.tsx, which deliberately runs unconfigured.
//
// The seam being covered is App's own: `closureBands` and `isSeriousWarning`
// are tested where they live, and MapScreen's pass-through is tested in
// chrome/MapScreen.test.tsx. What only this file can catch is the shell
// handing the wrong array to either - a normal report drawn as a serious
// warning, or a closure placed against the wrong index.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { get, set } from 'idb-keyval'
import { MockMap, resetMapLibreMock } from './test/mocks/maplibre-gl'
import { renderedMap } from './test/liveMap'
import { PREFERENCES_KEY } from './lib/preferences'
import { DEFAULT_PREFERENCES } from './lib/userPreferences'
import { TRAILS_BLOB_KEY } from './lib/trailData'
import { CLOSURE_SOURCE_ID } from './map/closureLayers'
import { WARNING_SOURCE_ID } from './map/warningLayers'

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))
vi.mock('./map/archiveZooms', () => ({ readArchiveZooms: () => Promise.resolve(null) }))
vi.mock('./map/protocol', () => ({
  PMTILES_SCHEME: 'pmtiles',
  registerPMTilesProtocol: vi.fn(),
  CORRIDOR_ARCHIVE_URL: 'pmtiles://ourhike-corridor',
}))
vi.mock('./lib/config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./lib/config')>()),
  DATA_BASE_URL: 'https://data.example',
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.example/${key}`,
  archiveUrl: () => 'https://data.example/corridor.pmtiles',
}))

const CLOSURE = {
  id: 'c1',
  reason_type: 'storm_damage' as const,
  note: null,
  status: 'closed' as const,
  start_mile_marker: 2,
  end_mile_marker: 4,
  reported_at: '2026-08-01T10:00:00Z',
  verified_at: '2026-08-02T10:00:00Z',
}

const REPORT = {
  reporter_type: 'thru',
  status: 'verified' as const,
  poi_id: null,
  note: null,
  timestamp: '2026-08-01T10:00:00Z',
}

const REPORTS = [
  {
    ...REPORT,
    id: 'serious-1',
    type: 'animals',
    severity: 'serious' as const,
    lat: 39.05,
    lon: -77,
  },
  // Not escalated. Every report on the trail would be a pin if the shell
  // filtered on nothing, and the pin is supposed to mean a moderator acted.
  {
    ...REPORT,
    id: 'normal-1',
    type: 'blowdown',
    severity: 'normal' as const,
    lat: 39.06,
    lon: -77,
  },
  // Serious, and nowhere - a report filed against a POI rather than a
  // position. There is no honest place to draw this.
  {
    ...REPORT,
    id: 'serious-nowhere',
    type: 'water',
    severity: 'serious' as const,
    lat: null,
    lon: null,
  },
]

vi.mock('./lib/api', () => ({
  API_CONFIGURED: true,
  accessToken: vi.fn(async () => null),
  sendReport: vi.fn(async () => undefined),
  permanentFailureReason: vi.fn(() => null),
  fetchClosures: vi.fn(async () => [CLOSURE]),
  fetchReports: vi.fn(async () => REPORTS),
}))

/** A mile of latitude, near enough that a vertex index IS a mile marker. */
const MILE_IN_DEGREES_LAT = 1 / 69.05

const TRAILS = JSON.stringify({
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { source: 'centerline', blaze_color: 'White' },
      geometry: {
        type: 'LineString',
        coordinates: Array.from({ length: 11 }, (_, i) => [
          -77,
          39 + i * MILE_IN_DEGREES_LAT,
        ]),
      },
    },
  ],
})

const store = new Map<string, unknown>()

beforeEach(() => {
  store.clear()
  resetMapLibreMock()
  vi.mocked(get).mockImplementation((key) => Promise.resolve(store.get(key as string)))
  vi.mocked(set).mockImplementation((key, value) => {
    store.set(key as string, value)
    return Promise.resolve()
  })
  store.set(PREFERENCES_KEY, {
    ...DEFAULT_PREFERENCES,
    onboarding_completed: true,
    download_choice_made: true,
  })
  // Already on the phone, so nothing is fetched and the centerline index is
  // built from exactly the geometry above.
  store.set(TRAILS_BLOB_KEY, new Blob([TRAILS]))
  store.set('ourhike:pois', [])
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

async function renderApp(): Promise<MockMap> {
  const { default: App } = await import('./App')
  render(<App />)

  // `renderedMap`, not `findByRole` then `MockMap.live[0]`. The container div
  // commits before the effect that builds the map runs, so reading the array
  // straight after the div is a race - it passed here every time and failed on
  // the fourth consecutive full-suite run with `Cannot set properties of
  // undefined (setting 'sourceIds')` (#331). See test/liveMap.ts.
  const map = await renderedMap()

  // Real MapLibre holds its sources by the time `load` fires; the mock has to
  // be told. Emitted after the first render so the attach helpers exercise
  // their wait-for-the-style path, which is the one that actually runs.
  map.sourceIds = [CLOSURE_SOURCE_ID, WARNING_SOURCE_ID]
  map.emit('load')
  return map
}

function featuresIn(map: MockMap, sourceId: string) {
  const data = map.sourceData.get(sourceId) as
    { features: Array<{ id: string }> } | undefined
  return data?.features ?? []
}

describe('what the shell draws once the reads land', () => {
  it('places the closure on the trail, from its mile markers', async () => {
    // The only place the two halves meet: the backend sends mile markers, the
    // phone holds the centerline, and neither on its own can put a band on the
    // map.
    const map = await renderApp()

    await waitFor(() => {
      expect(featuresIn(map, CLOSURE_SOURCE_ID)).toHaveLength(1)
    })
    expect(featuresIn(map, CLOSURE_SOURCE_ID)[0].id).toBe('c1')
  })

  it('draws only the reports a moderator escalated', async () => {
    const map = await renderApp()

    await waitFor(() => {
      expect(featuresIn(map, WARNING_SOURCE_ID).map((f) => f.id)).toEqual(['serious-1'])
    })
  })

  it('draws a warning even before the app knows which way anyone is walking', async () => {
    // There is no GPS fix in this test and no direction, so the alert strip
    // says nothing - `closureAhead` and `warningsAhead` both need a heading.
    // The canvas is what a hiker has until then, which is the whole reason
    // these are separate props.
    const map = await renderApp()

    await waitFor(() => {
      expect(featuresIn(map, WARNING_SOURCE_ID)).toHaveLength(1)
    })
    expect(screen.queryByRole('alert')).toBe(null)
  })
})
