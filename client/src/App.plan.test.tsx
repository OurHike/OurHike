// The planning flow end to end (#755 → #756 → #757), through the "route by
// destination" builder: empty Plan tab → the entrance (where from, how far)
// → the editable stop surface → a destination added between the ends →
// "Break into days" → a target → a laid-out plan on the timeline, persisted
// with the added stop pinned.
//
// Its own file because it needs POIs that carry PIPELINE miles offset from
// the synthetic centerline's own scale - the two-mile-scales problem
// (HIKE_PLANNING.md Finding 1) reproduced deliberately, so the flow proves
// the anchor correction end to end: the map door's tap snaps on the client
// index, the start field prints the PIPELINE mile.
//
// No elevation profile is seeded, on purpose: it exercises the degraded
// path a pre-profile download is promised - distances still honest, climb
// and time declared missing, "How long" and the hours target not offered.

import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, act, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { appHarness, latOfMile } from './test/appHarness'
import { MockMap } from './test/mocks/maplibre-gl'
import { PLAN_KEY } from './lib/plan'
import { TRIPS_KEY, type TripStore } from './lib/trips'
import { hikeFigures } from './lib/hikes'

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
  fetchFieldNotes: vi.fn(async () => []),
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

async function openEntrance(user: ReturnType<typeof userEvent.setup>) {
  render(<App />)

  await user.click(await screen.findByRole('tab', { name: 'Plan' }))
  expect(
    await screen.findByText('No plan yet. You could just walk north and find out.'),
  ).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Start on the map' }))
  expect(await screen.findByRole('dialog', { name: 'Plan a route' })).toBeInTheDocument()
  expect(screen.getByText('Where from?')).toBeInTheDocument()
}

describe('the planning flow', () => {
  it('walks entrance → editor → added destination → a laid-out, persisted plan', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })

    await openEntrance(user)

    // No profile on this download: sizing by days is not offered, and the
    // sheet says why rather than pricing climbs at zero.
    expect(screen.getByRole('button', { name: 'How long' })).toBeDisabled()
    expect(
      screen.getByText(/Sizing by days needs the elevation profile/),
    ).toBeInTheDocument()

    // Search door: name first.
    await user.click(screen.getByRole('button', { name: /Shelter, town, or/ }))
    const picker = await screen.findByRole('dialog', { name: 'Choose a stop' })
    expect(picker).toBeInTheDocument()
    await user.type(screen.getByLabelText('Search for a stop'), 'front')
    await user.click(await screen.findByRole('button', { name: /Front Shelter/ }))

    // The start field carries the PIPELINE mile the plan will run on.
    expect(await screen.findByText('Front Shelter')).toBeInTheDocument()
    expect(screen.getByText('mi 3.2')).toBeInTheDocument()

    // 45 miles (the default) from 3.2 reaches for 48.2 - the nearest real
    // place to sleep is Beyond Shelter at 22.2, and the row says so.
    expect(screen.getByText('Ends near')).toBeInTheDocument()
    expect(screen.getByText('Beyond Shelter')).toBeInTheDocument()

    // Slide shorter: 5 miles reaches for 8.2, and the end re-snaps to
    // Middle Shelter (10.2) - then back out to 15, Beyond Shelter again
    // (|22.2 - 18.2| = 4 beats |13.2 - 18.2| = 5).
    fireEvent.change(screen.getByLabelText('Miles of trail'), { target: { value: '5' } })
    expect(screen.getByText('Middle Shelter')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Miles of trail'), { target: { value: '15' } })
    expect(screen.getByText('Beyond Shelter')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Use this stretch' }))

    // The editor: both ends as fields, the bar with direction and the
    // honest distance-only figures (no profile, and it says so).
    expect(await screen.findByRole('dialog', { name: 'Your route' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Front Shelter/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Beyond Shelter/ })).toBeInTheDocument()
    expect(screen.getByText('NOBO · 19.0 mi')).toBeInTheDocument()
    expect(screen.getByText(/No elevation profile in this download/)).toBeInTheDocument()

    // A destination on the way: Far Shelter joins between the ends.
    await user.click(screen.getByRole('button', { name: /Add a stop on the way/ }))
    await user.type(await screen.findByLabelText('Search for a stop'), 'far')
    await user.click(await screen.findByRole('button', { name: /^Far Shelter/ }))
    expect(await screen.findByRole('dialog', { name: 'Your route' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Far Shelter/ })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Break into days' }))
    expect(
      await screen.findByRole('dialog', { name: 'How long is a day?' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Walking hours' })).toBeDisabled()

    // At 8 mi/day the two legs (3.2→13.2, 13.2→22.2) plan as one day each.
    fireEvent.change(screen.getByLabelText('Miles per day'), { target: { value: '8' } })
    await user.click(screen.getByRole('button', { name: 'Lay out 2 days' }))

    // Landed on the timeline: both days, and the boundary the hiker chose.
    expect(await screen.findByText('DAY 1')).toBeInTheDocument()
    expect(screen.getByText('DAY 2')).toBeInTheDocument()
    expect(screen.getAllByText(/Far Shelter/).length).toBeGreaterThan(0)

    // Kept as a TRIP now (#787), named from its own ends - the plan itself
    // is unchanged inside it.
    const store = app.store.get(TRIPS_KEY) as TripStore
    expect(store.trips).toHaveLength(1)
    expect(store.trips[0].name).toBe('Front Shelter → Beyond Shelter')
    expect(store.openId).toBe(store.trips[0].id)
    const stored = store.trips[0].plan
    expect(stored.stops).toHaveLength(3)
    expect(stored.stops[0].mile).toBe(3.2)
    expect(stored.stops[1].mile).toBe(13.2)
    expect(stored.stops[2].mile).toBe(22.2)
    expect(stored.stops[0].name).toBe('Front Shelter')
    expect(stored.stops[1].name).toBe('Far Shelter')
    // The added destination is a decision: its arriving day is born pinned,
    // the generator's own boundary is not.
    expect(stored.days[0].pinned).toBe(true)
    expect(stored.days[1].pinned).toBe(false)
  })

  it('records a stretch already walked, and the hike roll-up counts it', async () => {
    // #789: most of a section hiker's trail predates the app. Without this
    // door the roll-up opens on somebody who has walked hundreds of miles
    // and tells them the whole trail is ahead of them.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })

    await openEntrance(user)

    await user.click(screen.getByRole('button', { name: /Shelter, town, or/ }))
    await user.type(await screen.findByLabelText('Search for a stop'), 'front')
    await user.click(await screen.findByRole('button', { name: /Front Shelter/ }))
    await user.click(screen.getByRole('button', { name: 'Use this stretch' }))
    expect(await screen.findByRole('dialog', { name: 'Your route' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'I already walked this' }))

    // Kept as a record, not a plan: the Plan tab shows it walked rather
    // than as a day anybody is about to walk.
    expect(await screen.findByText(/walked · not a plan any more/)).toBeInTheDocument()

    const store = app.store.get(TRIPS_KEY) as TripStore
    expect(store.trips).toHaveLength(1)
    expect(store.trips[0].recorded).toBe(true)
    expect(store.trips[0].plan.days.every((day) => day.walked === true)).toBe(true)

    // And it is walked ground as far as any roll-up is concerned - which is
    // the whole reason the door exists.
    const figures = hikeFigures(
      {
        id: 'h',
        name: 'Test',
        type: 'section',
        start: { mile: 0 },
        end: { mile: 30 },
        tripIds: store.trips.map((trip) => trip.id),
      },
      store.trips,
      [],
    )
    expect(figures.walkedMi).toBeGreaterThan(0)
  })

  it('keeps the timeline across a relaunch, migrating the single-plan key', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(PLAN_KEY, {
      target: { miles: 8 },
      stops: [
        { mile: 5.2, resupply: false },
        { mile: 13.2, name: 'Far Shelter', resupply: false },
        { mile: 20.2, name: 'Beyond Shelter', resupply: true },
      ],
      days: [
        { id: 'day-a', date: '2026-05-12', pinned: false, generated: true },
        { id: 'day-b', date: '2026-05-13', pinned: false, generated: true },
      ],
    })

    render(<App />)
    await user.click(await screen.findByRole('tab', { name: 'Plan' }))

    expect(await screen.findByText('TUE 12')).toBeInTheDocument()
    expect(screen.getByText(/2 days food/)).toBeInTheDocument()
    expect(screen.queryByText(/No plan yet/)).toBeNull()

    // The plan a phone was holding under the old key came across as a trip,
    // and the old key is left alone rather than destroyed (#787).
    const store = app.store.get(TRIPS_KEY) as TripStore
    expect(store.trips).toHaveLength(1)
    expect(store.trips[0].name).toBe('mi 5.2 → Beyond Shelter')
    expect(app.store.get(PLAN_KEY)).toBeDefined()
  })

  it('keeps a second trip instead of overwriting the first', async () => {
    // The bug this issue was filed for: planning again destroyed the last
    // plan. Two trips, both kept, and the switcher moves between them.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(TRIPS_KEY, {
      openId: 'trip-1',
      trips: [
        {
          id: 'trip-1',
          name: 'Autumn section',
          plan: {
            target: { miles: 8 },
            stops: [
              { mile: 3.2, name: 'Front Shelter', resupply: false },
              { mile: 13.2, name: 'Far Shelter', resupply: false },
            ],
            days: [{ id: 'day-a', pinned: false, generated: true }],
          },
        },
        {
          id: 'trip-2',
          name: 'Spring section',
          plan: {
            target: { miles: 8 },
            stops: [
              { mile: 13.2, name: 'Far Shelter', resupply: false },
              { mile: 22.2, name: 'Beyond Shelter', resupply: false },
            ],
            days: [{ id: 'day-b', pinned: false, generated: true }],
          },
        },
      ],
    })

    render(<App />)
    await user.click(await screen.findByRole('tab', { name: 'Plan' }))

    // Two trips, so the tab opens on its home (#805) - the open one under
    // "carry on with", and both of them listed.
    expect(await screen.findByText('Carry on with')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /Autumn section/ })).toHaveLength(2)
    await user.click(screen.getByRole('button', { name: /Spring section/ }))

    // Switched, and the other trip is still there rather than overwritten.
    expect(await screen.findByText('Spring section')).toBeInTheDocument()
    const store = app.store.get(TRIPS_KEY) as TripStore
    expect(store.trips.map((trip) => trip.name)).toEqual([
      'Autumn section',
      'Spring section',
    ])
    expect(store.openId).toBe('trip-2')
  })

  it('zooms out to the hike, and starts a route where a gap begins (#790)', async () => {
    // The section hiker's loop, end to end: what is walked, what is not,
    // and one tap from a gap into the builder that fills it.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(TRIPS_KEY, {
      openId: 'trip-1',
      trips: [
        {
          id: 'trip-1',
          name: 'Autumn section',
          plan: {
            target: { miles: 8 },
            stops: [
              { mile: 3.2, name: 'Front Shelter', poiId: 's3', resupply: false },
              { mile: 10.2, name: 'Middle Shelter', poiId: 's10', resupply: false },
            ],
            days: [{ id: 'day-a', pinned: false, generated: true, walked: true }],
          },
        },
      ],
      hikes: [
        {
          id: 'hike-1',
          name: 'The whole thing, eventually',
          type: 'section',
          start: { poiId: 's3', name: 'Front Shelter', mile: 3.2 },
          end: { poiId: 's22', name: 'Beyond Shelter', mile: 22.2 },
          tripIds: ['trip-1'],
        },
      ],
    })

    render(<App />)
    await user.click(await screen.findByRole('tab', { name: 'Plan' }))
    // The Plan tab now opens on its home when there is something to choose
    // between (#805), so the hike is one tap in rather than a zoom away.
    await user.click(
      await screen.findByRole('button', { name: /The whole thing, eventually/ }),
    )

    // The walked trip, and the ground past it that nobody has walked -
    // named at both ends rather than only measured.
    expect(
      await screen.findByRole('heading', { name: 'The whole thing, eventually' }),
    ).toBeInTheDocument()
    expect(screen.getByText('12.0 mi not walked')).toBeInTheDocument()
    expect(screen.getByText(/Middle Shelter → Beyond Shelter/)).toBeInTheDocument()
    expect(screen.getByText('7.0 mi walked · 12.0 mi to go')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Plan this stretch' }))

    // The builder, on the map, already starting where the gap does.
    expect(
      await screen.findByRole('dialog', { name: 'Plan a route' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Middle Shelter')).toBeInTheDocument()
  })

  it('starts a route from the SOUTH end of a gap, walking that way (#791)', async () => {
    // The flip-flopper's move, and the reason both ends are offered: the
    // direction is derived from which end was picked and stored nowhere.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(TRIPS_KEY, {
      openId: 'trip-1',
      trips: [
        {
          id: 'trip-1',
          name: 'Autumn section',
          plan: {
            target: { miles: 8 },
            stops: [
              { mile: 3.2, name: 'Front Shelter', poiId: 's3', resupply: false },
              { mile: 10.2, name: 'Middle Shelter', poiId: 's10', resupply: false },
            ],
            days: [{ id: 'day-a', pinned: false, generated: true, walked: true }],
          },
        },
      ],
      hikes: [
        {
          id: 'hike-1',
          name: 'The whole thing, eventually',
          type: 'section',
          start: { poiId: 's3', name: 'Front Shelter', mile: 3.2 },
          end: { poiId: 's22', name: 'Beyond Shelter', mile: 22.2 },
          tripIds: ['trip-1'],
        },
      ],
    })

    render(<App />)
    await user.click(await screen.findByRole('tab', { name: 'Plan' }))
    // The Plan tab now opens on its home when there is something to choose
    // between (#805), so the hike is one tap in rather than a zoom away.
    await user.click(
      await screen.findByRole('button', { name: /The whole thing, eventually/ }),
    )
    await user.click(screen.getByRole('button', { name: /What’s left/ }))

    // One walked stretch, one gap, and both of its ends offered.
    expect(await screen.findByText(/12\.0 mi in 1 piece/)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /North from Middle Shelter/ }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /South from Beyond Shelter/ }))

    const entrance = await screen.findByRole('dialog', { name: 'Plan a route' })
    expect(within(entrance).getByText('Beyond Shelter')).toBeInTheDocument()
    // Picked the high end, so the route walks south - nothing was stored to
    // say so, it fell out of the pair.
    expect(within(entrance).getByRole('button', { name: 'South' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('places a start through the map door, refusals said out loud, and keeps the draft across tabs', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })

    await openEntrance(user)

    await user.click(screen.getByRole('button', { name: 'Pick on the map' }))
    expect(
      await screen.findByText('Tap the trail where this stop goes.'),
    ).toBeInTheDocument()

    // The map is rebuilt by the tab switch; wait for the live one to be
    // listening before firing anything at it.
    await waitFor(() => {
      expect(MockMap.live).toHaveLength(1)
      expect(MockMap.live[0].listenerCount('click')).toBeGreaterThan(0)
    })
    const map = MockMap.live[0]

    // Four degrees of longitude west of the centerline - far past the
    // 3-mile gate. Refused out loud, and the door stays open.
    await act(async () => {
      map.emit('click', { lngLat: { lng: -81, lat: latOfMile(10) } })
    })
    expect(await screen.findByText(/no honest mile/)).toBeInTheDocument()

    // An on-trail tap at client mile 5 lands as PIPELINE mile 5.2 - the
    // anchor correction carrying the offset across, end to end.
    await act(async () => {
      map.emit('click', { lngLat: { lng: -77, lat: latOfMile(5) } })
    })
    expect(
      await screen.findByRole('dialog', { name: 'Plan a route' }),
    ).toBeInTheDocument()
    expect(screen.getByText('mi 5.2')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Use this stretch' }))
    expect(await screen.findByRole('dialog', { name: 'Your route' })).toBeInTheDocument()

    // The draft survives a walk to the Plan tab and back - the entrance is
    // never a toll gate on the way back to your own route.
    await user.click(screen.getByRole('tab', { name: 'Plan' }))
    await user.click(await screen.findByRole('button', { name: 'Back to your route' }))
    expect(await screen.findByRole('dialog', { name: 'Your route' })).toBeInTheDocument()
  })
})
