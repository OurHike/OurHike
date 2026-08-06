// The community safety data reaching the map (#286 → #232): the app reads
// closures and reports from its backend, the closure becomes a band along
// the centerline the phone already holds, the serious warning becomes the
// map's biggest pin, and tapping either opens its sheet.
//
// Its own file for the same reason App.outboxRetry.test.tsx is: it needs a
// CONFIGURED api module, and lib/api reads the base URL once at module load,
// so the only honest way to have one is to mock the module before App is
// imported. App.test.tsx deliberately runs unconfigured.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { get, set } from 'idb-keyval'
import { MockMap, resetMapLibreMock } from './test/mocks/maplibre-gl'
import { PREFERENCES_KEY } from './lib/preferences'
import { DEFAULT_PREFERENCES } from './lib/userPreferences'
import { TRAILS_BLOB_KEY } from './lib/trailData'
import { CLOSURE_SOURCE_ID, CLOSURE_ID_PROPERTY } from './map/closureLayers'
import { WARNING_SOURCE_ID, WARNING_ID_PROPERTY } from './map/warningLayers'
import { CLOSURE_LAYER_ID } from './lib/closureStyle'
import type { closureFeatureCollection } from './map/closureLayers'
import type { warningFeatureCollection } from './map/warningLayers'

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))
vi.mock('./map/protocol', () => ({
  PMTILES_SCHEME: 'pmtiles',
  registerPMTilesProtocol: vi.fn(),
  CORRIDOR_ARCHIVE_URL: 'pmtiles://ourhike-corridor',
}))

// A closure the backend would serve: two mile markers, no geometry.
const CLOSURE = {
  id: 'closure-1',
  reported_by: 'profile-1',
  reported_at: '2026-08-01T12:00:00Z',
  trail_id: 'at',
  start_mile_marker: 0,
  // Far past the fixture centerline's total, so the band covers all of it -
  // this test is about the plumbing, not the slicing arithmetic, which
  // closureLayers.test.ts pins down.
  end_mile_marker: 10_000,
  reason_type: 'storm_damage' as const,
  note: 'Blowdowns across a half mile.',
  status: 'closed' as const,
  moderation_status: 'verified' as const,
  verified_by: 'profile-2',
  verified_at: '2026-08-02T12:00:00Z',
}

function report(id: string, overrides: Record<string, unknown>) {
  return {
    id,
    reporter_id: 'profile-3',
    type: 'animals',
    poi_id: null,
    lat: 34.001,
    lon: -83.999,
    reporter_type: 'thru',
    timestamp: '2026-08-01T09:00:00Z',
    note: 'A bear has been taking hung food bags overnight.',
    photo_url: null,
    received_at: '2026-08-01T09:00:05Z',
    status: 'verified',
    visibility: 'public',
    severity: 'serious',
    ...overrides,
  }
}

vi.mock('./lib/api', () => ({
  API_CONFIGURED: true,
  accessToken: vi.fn(async () => null),
  sendReport: vi.fn(async () => undefined),
  permanentFailureReason: vi.fn(() => null),
  fetchClosures: vi.fn(async () => [CLOSURE]),
  fetchReports: vi.fn(async () => [
    report('warning-1', {}),
    // Not serious: an ordinary verified report is data, not a warning pin.
    report('normal-1', { severity: 'normal' }),
    // Resolved: it reads as "Fixed", and the biggest pin on the map must not
    // point at a hazard somebody has dealt with.
    report('resolved-1', { status: 'resolved' }),
  ]),
}))

// The centerline the closure is placed along: a short diagonal, stored the
// way a real download is, so buildTrailIndex runs on exactly what it reads
// in production.
const TRAILS = JSON.stringify({
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { source: 'centerline' },
      geometry: {
        type: 'LineString',
        coordinates: [
          [-84.0, 34.0],
          [-83.99, 34.01],
          [-83.98, 34.02],
          [-83.97, 34.03],
        ],
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
  store.set(TRAILS_BLOB_KEY, new Blob([TRAILS]))
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

async function renderApp() {
  const { default: App } = await import('./App')
  render(<App />)
  await screen.findByRole('region', { name: /trail map/i })
  return MockMap.live[0]
}

describe('closures on the map', () => {
  it('turns the fetched mile range into a band along the stored centerline', async () => {
    const map = await renderApp()

    await waitFor(() => {
      const pushed = map.sourceData.get(CLOSURE_SOURCE_ID) as
        ReturnType<typeof closureFeatureCollection> | undefined
      expect(pushed?.features).toHaveLength(1)
    })

    const pushed = map.sourceData.get(CLOSURE_SOURCE_ID) as ReturnType<
      typeof closureFeatureCollection
    >
    expect(pushed.features[0].properties[CLOSURE_ID_PROPERTY]).toBe('closure-1')
    // The band is the centerline's own vertices - the closure arrived with
    // no geometry at all.
    expect(pushed.features[0].geometry.coordinates[0]).toEqual([-84.0, 34.0])
  })

  it('opens the closure sheet from a tap on the band, honestly about what it does not know', async () => {
    const map = await renderApp()
    await waitFor(() => {
      expect(map.sourceData.get(CLOSURE_SOURCE_ID)).toBeDefined()
    })

    map.renderedFeatures.set(CLOSURE_LAYER_ID, [
      { properties: { [CLOSURE_ID_PROPERTY]: 'closure-1' } },
    ])
    map.emit('click', { point: { x: 100, y: 100 } })

    const sheet = await screen.findByRole('dialog', { name: /trail closure/i })
    expect(within(sheet).getByText(/storm damage/i)).toBeInTheDocument()
    expect(within(sheet).getByText(/blowdowns across a half mile/i)).toBeInTheDocument()
    // #245: no closed-since, expected-reopen, marked-by or reroute link from
    // this backend - omitted, not guessed.
    expect(within(sheet).queryByText(/closed since/i)).not.toBeInTheDocument()
    expect(within(sheet).queryByText(/expected to reopen/i)).not.toBeInTheDocument()
    // The sheet still owns the two sentences that must always be there.
    expect(within(sheet).getByText(/does not work out detours/i)).toBeInTheDocument()
    expect(within(sheet).getByText(/your copy of this closure/i)).toBeInTheDocument()
  })

  it('closes the sheet from its own button', async () => {
    const user = userEvent.setup()
    const map = await renderApp()
    await waitFor(() => expect(map.sourceData.get(CLOSURE_SOURCE_ID)).toBeDefined())

    map.renderedFeatures.set(CLOSURE_LAYER_ID, [
      { properties: { [CLOSURE_ID_PROPERTY]: 'closure-1' } },
    ])
    map.emit('click', { point: { x: 100, y: 100 } })
    const sheet = await screen.findByRole('dialog', { name: /trail closure/i })

    await user.click(within(sheet).getByRole('button', { name: /close/i }))

    expect(
      screen.queryByRole('dialog', { name: /trail closure/i }),
    ).not.toBeInTheDocument()
  })
})

describe('serious warnings on the map', () => {
  it('pins exactly the verified serious reports - not normal ones, not resolved ones', async () => {
    const map = await renderApp()

    await waitFor(() => {
      const pushed = map.sourceData.get(WARNING_SOURCE_ID) as
        ReturnType<typeof warningFeatureCollection> | undefined
      expect(pushed?.features).toHaveLength(1)
    })

    const pushed = map.sourceData.get(WARNING_SOURCE_ID) as ReturnType<
      typeof warningFeatureCollection
    >
    expect(pushed.features[0].properties[WARNING_ID_PROPERTY]).toBe('warning-1')
  })

  it('opens the warning sheet from a tap on the pin', async () => {
    const map = await renderApp()
    await waitFor(() => expect(map.sourceData.get(WARNING_SOURCE_ID)).toBeDefined())

    map.renderedFeatures.set('serious-warning-pins', [
      { properties: { [WARNING_ID_PROPERTY]: 'warning-1' } },
    ])
    map.emit('click', { point: { x: 100, y: 100 } })

    const sheet = await screen.findByRole('dialog', { name: /serious warning/i })
    expect(within(sheet).getByText(/bear has been taking hung food/i)).toBeInTheDocument()
    expect(within(sheet).getByText(/confirmed by club moderators/i)).toBeInTheDocument()
    // The one-notification policy, said plainly on the sheet.
    expect(within(sheet).getByText(/didn.t buzz/i)).toBeInTheDocument()
  })
})
