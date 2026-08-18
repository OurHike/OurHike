// The planning flow end to end (#755 → #756 → #757): empty Plan tab → route
// builder on the map → two dropped points → "Break into days" → a target →
// a laid-out plan on the timeline, persisted.
//
// Its own file because it needs POIs that carry PIPELINE miles offset from
// the synthetic centerline's own scale - the two-mile-scales problem
// (HIKE_PLANNING.md Finding 1) reproduced deliberately, so the flow proves
// the anchor correction end to end: the tap snaps on the client index, the
// printed leg is the difference of PIPELINE miles.
//
// No elevation profile is seeded, on purpose: it exercises the degraded
// path a pre-profile download is promised - distances still honest, climb
// and time declared missing, hours target not offered.

import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { appHarness, latOfMile } from './test/appHarness'
import { MockMap } from './test/mocks/maplibre-gl'
import { PLAN_KEY } from './lib/plan'

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./map/archiveZooms', () => ({ readArchiveZooms: () => Promise.resolve(null) }))
vi.mock('./lib/api', () => ({
  API_CONFIGURED: false,
  accessToken: vi.fn(async () => null),
  sendReport: vi.fn(async () => undefined),
  permanentFailureReason: vi.fn(() => null),
  fetchClosures: vi.fn(async () => []),
  fetchReports: vi.fn(async () => []),
}))

const app = appHarness({ navigator: { onLine: false }, objectUrls: true })

/** Shelters on the synthetic centerline. `mile` is the PIPELINE's published
 *  value, deliberately 0.2 above the client index's own answer for the same
 *  spot - the offset the anchor correction exists to carry across. */
function shelter(clientMile: number, name: string) {
  return {
    id: `s${clientMile}`,
    type: 'shelter',
    name,
    lat: latOfMile(clientMile),
    lon: -77,
    confidence: 'high',
    mile: clientMile + 0.2,
  }
}

const POIS = [
  shelter(3, 'Front Shelter'),
  shelter(10, 'Middle Shelter'),
  shelter(13, 'Far Shelter'),
  shelter(22, 'Beyond Shelter'),
]

async function openBuilderAndDropTwoPoints(user: ReturnType<typeof userEvent.setup>) {
  render(<App />)

  await user.click(await screen.findByRole('tab', { name: 'Plan' }))
  expect(
    await screen.findByText('No plan yet. You could just walk north and find out.'),
  ).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Start on the map' }))
  expect(await screen.findByRole('dialog', { name: 'Route builder' })).toBeInTheDocument()

  // The builder owns the tap now. The map is rebuilt by the tab switch, so
  // wait for the new one to be listening before firing anything at it.
  await waitFor(() => {
    expect(MockMap.live).toHaveLength(1)
    expect(MockMap.live[0].listenerCount('click')).toBeGreaterThan(0)
  })
  const map = MockMap.live[0]

  await act(async () => {
    map.emit('click', { lngLat: { lng: -77, lat: latOfMile(5) } })
  })
  expect(await screen.findByText('1 point')).toBeInTheDocument()

  await act(async () => {
    map.emit('click', { lngLat: { lng: -77, lat: latOfMile(20) } })
  })
  expect(await screen.findByText('2 points · 1 leg')).toBeInTheDocument()

  return map
}

describe('the planning flow', () => {
  it('walks from an empty Plan tab to a laid-out, persisted plan', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })

    await openBuilderAndDropTwoPoints(user)

    // The leg is the difference of PIPELINE miles: the taps snapped to
    // client miles 5 and 20, anchored to 5.2 and 20.2 - fifteen miles even.
    // A leg computed on the client scale would read the same 15.0 here, but
    // the plan below gives the anchors away. (Leg row and total row both
    // print it, hence getAllBy.)
    expect(screen.getAllByText(/15\.0 mi/).length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: 'Break into days' }))
    expect(
      await screen.findByRole('dialog', { name: 'How long is a day?' }),
    ).toBeInTheDocument()

    // No profile on this download: hours are not offered, and the sheet
    // says why rather than pricing climbs at zero.
    expect(screen.getByRole('button', { name: 'Walking hours' })).toBeDisabled()
    expect(screen.getByText(/needs the elevation profile/)).toBeInTheDocument()

    // At 8 mi/day the two shelters inside the route split it into two days.
    fireEvent.change(screen.getByLabelText('Miles per day'), { target: { value: '8' } })
    await user.click(screen.getByRole('button', { name: 'Lay out 2 days' }))

    // Landed on the timeline: both days, numbered, ending at the shelters
    // the generator chose - and the boundary miles are the pipeline's.
    expect(await screen.findByText('DAY 1')).toBeInTheDocument()
    expect(screen.getByText('DAY 2')).toBeInTheDocument()
    // The chosen stop names both days that meet it - one row ends there,
    // the next starts there.
    expect(screen.getAllByText(/Far Shelter/).length).toBeGreaterThan(0)

    const stored = app.store.get(PLAN_KEY) as {
      stops: { mile: number; name?: string }[]
    }
    // Close-to rather than exact: the synthetic centerline's haversine mile
    // differs from its vertex index by a thousandth or two, and the anchor
    // carries that same offset across - which is the correction working,
    // not error. The 0.2 pipeline offset is what must survive exactly.
    expect(stored.stops).toHaveLength(3)
    expect(stored.stops[0].mile).toBeCloseTo(5.2, 2)
    expect(stored.stops[1].mile).toBe(13.2)
    expect(stored.stops[2].mile).toBeCloseTo(20.2, 2)
    expect(stored.stops[1].name).toBe('Far Shelter')
  })

  it('keeps the timeline across a relaunch', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(PLAN_KEY, {
      target: { miles: 8 },
      startDate: '2026-05-12',
      stops: [
        { mile: 5.2, resupply: false },
        { mile: 13.2, name: 'Far Shelter', resupply: false },
        { mile: 20.2, name: 'Beyond Shelter', resupply: true },
      ],
      days: [
        { id: 'day-a', pinned: false, generated: true },
        { id: 'day-b', pinned: false, generated: true },
      ],
    })

    render(<App />)
    await user.click(await screen.findByRole('tab', { name: 'Plan' }))

    expect(await screen.findByText('TUE 12')).toBeInTheDocument()
    expect(screen.getByText(/2 days food/)).toBeInTheDocument()
    expect(screen.queryByText(/No plan yet/)).toBeNull()
  })

  it('refuses an off-corridor tap out loud and keeps the route unchanged', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })

    const map = await openBuilderAndDropTwoPoints(user)

    await act(async () => {
      // Four degrees of longitude west of the centerline - far past the
      // 3-mile gate.
      map.emit('click', { lngLat: { lng: -81, lat: latOfMile(10) } })
    })

    expect(await screen.findByText(/no honest mile/)).toBeInTheDocument()
    expect(screen.getByText('2 points · 1 leg')).toBeInTheDocument()
  })
})
