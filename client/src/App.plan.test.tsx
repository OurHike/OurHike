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
// The one exception is the last describe, which is about the profile: the
// planning ribbon (#910) has nothing to draw without one, and seeds its own.

import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, act, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { appHarness, latOfMile, openMapTab } from './test/appHarness'
import { MockMap } from './test/mocks/maplibre-gl'
import { ROUTE_SOURCE_ID, ROUTE_POINT_LABEL_PROPERTY } from './map/routeLayers'
import { ELEVATION_STORE_KEY } from './lib/trailData'
import { MIN_FLAT_PACE_MPH } from './lib/pace'
import { DAY_HIKES_KEY } from './lib/dayHikes'
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
  // Disputes ride the same read as the notes they are computed from (#876).
  fetchDisputes: vi.fn(async () => []),
  fetchReports: vi.fn(async () => []),
}))

// `geolocation` is installed but no fix is delivered except by the one test
// that wants one (#910's lane swap): the builder's "where I am" door stays
// refused without a fix, which is the state every test above assumes.
const app = appHarness({
  navigator: { onLine: false, geolocation: true },
  objectUrls: true,
})

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

/** The 1i door (#977) now interposes on the one primary action: every path
 *  into a builder chooses its kind first. These tests want the trip. */
async function throughPlanKind(user: ReturnType<typeof userEvent.setup>) {
  expect(
    await screen.findByRole('dialog', { name: 'What are you planning?' }),
  ).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /A multi-day trip/ }))
}

async function openEntrance(user: ReturnType<typeof userEvent.setup>) {
  render(<App />)

  await user.click(await screen.findByRole('tab', { name: 'Plan' }))
  expect(
    await screen.findByText('No plan yet. You could just walk north and find out.'),
  ).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Start on the map' }))
  await throughPlanKind(user)
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
    fireEvent.change(screen.getByLabelText('Trail distance in miles'), {
      target: { value: '5' },
    })
    expect(screen.getByText('Middle Shelter')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Trail distance in miles'), {
      target: { value: '15' },
    })
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

  it('lands the laid-out trip in the trips room, not on a day-hike list left open', async () => {
    // #1008. `dayListOpen` was lifted into the shell so the map's trailhead
    // door could reach the list from another tab; the cost is that it now
    // OUTLIVES the tab switch that used to reset it, and Plan.tsx tests it
    // BEFORE it tests the mode. So a list opened before a walk on the map
    // won the trips room outright: the trip the hiker just laid out never
    // appeared, and what greeted them was the day-hike list wearing the day
    // band. `enterTripsRoom` is the fix and this is its regression.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(DAY_HIKES_KEY, {
      hikes: [
        {
          id: 'saved-1',
          name: 'A walk from an earlier session',
          date: null,
          segments: [
            [
              { coord: [-74.095, 41.25], poiId: null },
              { coord: [-74.085, 41.25], poiId: null },
            ],
          ],
          figures: { miles: 4.2, legs: [] },
          looped: false,
          recorded: 'planned',
        },
      ],
      openId: null,
    })

    render(<App />)
    await user.click(await screen.findByRole('tab', { name: 'Plan' }))
    // One saved day hike and no trips opens the day room by itself. Start a
    // route from the trips room, so there is a live draft to come back to.
    await user.click(await screen.findByRole('button', { name: /^Trips/ }))
    await user.click(await screen.findByRole('button', { name: 'Plan a new trip' }))
    await user.click(await screen.findByRole('button', { name: /Shelter, town, or/ }))
    await user.type(await screen.findByLabelText('Search for a stop'), 'front')
    await user.click(await screen.findByRole('button', { name: /Front Shelter/ }))
    await user.click(screen.getByRole('button', { name: 'Use this stretch' }))
    expect(await screen.findByRole('dialog', { name: 'Your route' })).toBeInTheDocument()

    // Detour into the day room's list, mid-route. This is the state that used
    // to survive the trip being laid out.
    await user.click(screen.getByRole('tab', { name: 'Plan' }))
    await user.click(await screen.findByRole('button', { name: /^Day hikes/ }))
    await user.click(await screen.findByRole('button', { name: 'All 1 ›' }))
    expect(await screen.findByText('Ready to walk')).toBeInTheDocument()

    // Back to the half-built route, and finish it.
    await user.click(screen.getByRole('tab', { name: 'Map' }))
    await user.click(await screen.findByRole('button', { name: 'Break into days' }))
    fireEvent.change(await screen.findByLabelText('Miles per day'), {
      target: { value: '8' },
    })
    await user.click(screen.getByRole('button', { name: /^Lay out \d+ days?$/ }))

    // The trips room, showing the trip that was just made. (The trips HOME
    // rather than its timeline: #805 opens the tab on the home whenever
    // there is something to choose between, and a saved day hike is
    // something - that part is not this test's business.) What matters is
    // that the day-hike list is gone.
    expect(
      (await screen.findAllByText(/Front Shelter → Beyond Shelter/)).length,
    ).toBeGreaterThan(0)
    expect(screen.queryByText('Ready to walk')).toBeNull()
    expect(screen.queryByText('A walk from an earlier session')).toBeNull()

    const store = app.store.get(TRIPS_KEY) as TripStore
    expect(store.trips).toHaveLength(1)
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

  // Wireframe 2a frame 1, reached by its own door (#973). What this proves is
  // the thing that was broken rather than missing: the canvas has always been
  // in route-tap mode while the editor is open, and the handler declined to
  // act on it. Every rule the frame states falls out of insertRoutePoint,
  // which lib/route.test.ts already owns - so what is held here is the WIRING,
  // end to end and on the pipeline's mile scale.
  describe('building a route by tapping the trail (#973)', () => {
    /** The live map, listening. Rebuilt by the tab switch the entrance makes,
     *  so the wait is on the listener rather than on a tick. */
    async function liveMap() {
      await waitFor(() => {
        expect(MockMap.live).toHaveLength(1)
        expect(MockMap.live[0].listenerCount('click')).toBeGreaterThan(0)
      })
      return MockMap.live[0]
    }

    const tap = async (map: MockMap, clientMile: number, lng = -77) => {
      await act(async () => {
        map.emit('click', { lngLat: { lng, lat: latOfMile(clientMile) } })
      })
    }

    it('drops points in walk order, names them, and prices the legs', async () => {
      const user = userEvent.setup()
      app.onboard()
      app.putTrailData({ pois: POIS })

      await openEntrance(user)
      await user.click(
        screen.getByRole('button', { name: /just tap the trail to drop points/ }),
      )

      // An empty editor, asking for the first point rather than pretending to
      // hold a route.
      const panel = await screen.findByRole('dialog', { name: 'Your route' })
      expect(
        within(panel).getByText('Tap the trail to drop a point.'),
      ).toBeInTheDocument()
      expect(within(panel).getByText('0 points')).toBeInTheDocument()

      const map = await liveMap()

      // Client mile 3 is Front Shelter's own mile, so the tap arrives named -
      // the pipeline mile 3.2 the shelter carries, not the 3.2 the anchors
      // would have produced by coincidence.
      await tap(map, 3)
      expect(
        await screen.findByRole('button', { name: /Front Shelter/ }),
      ).toBeInTheDocument()
      expect(screen.getByText('1 point')).toBeInTheDocument()

      // The second tap appends: tapping in walking order always does.
      await tap(map, 22)
      expect(
        await screen.findByRole('button', { name: /Beyond Shelter/ }),
      ).toBeInTheDocument()
      expect(screen.getByText('NOBO · 2 points · 1 leg')).toBeInTheDocument()
      expect(screen.getByText('19.0 mi')).toBeInTheDocument()

      // And a tap BETWEEN them inserts there rather than appending - the
      // frame's "a new point inserts where it adds the least distance".
      await tap(map, 13)
      expect(
        await screen.findByRole('button', { name: /Far Shelter/ }),
      ).toBeInTheDocument()
      expect(screen.getByText('NOBO · 3 points · 2 legs')).toBeInTheDocument()

      const fields = within(panel)
        .getAllByRole('button')
        .map((node) => node.textContent ?? '')
        .filter((text) => /Shelter/.test(text))
      expect(fields[0]).toMatch(/Front Shelter/)
      expect(fields[1]).toMatch(/Far Shelter/)
      expect(fields[2]).toMatch(/Beyond Shelter/)
    })

    it('refuses a tap off the corridor, and says so where the tapping happens', async () => {
      const user = userEvent.setup()
      app.onboard()
      app.putTrailData({ pois: POIS })

      await openEntrance(user)
      await user.click(
        screen.getByRole('button', { name: /just tap the trail to drop points/ }),
      )
      const map = await liveMap()

      const panel = await screen.findByRole('dialog', { name: 'Your route' })
      await tap(map, 10, -81)
      expect((await within(panel).findByRole('status')).textContent).toMatch(
        /no honest mile/,
      )
      expect(within(panel).getByText('0 points')).toBeInTheDocument()

      // And the standing sentence comes back once a tap lands.
      await tap(map, 3)
      expect(
        await screen.findByText(/Only the A.T. centerline can carry a route/),
      ).toBeInTheDocument()
    })

    it('takes a mis-tap back, one edit at a time', async () => {
      const user = userEvent.setup()
      app.onboard()
      app.putTrailData({ pois: POIS })

      await openEntrance(user)
      await user.click(
        screen.getByRole('button', { name: /just tap the trail to drop points/ }),
      )
      const map = await liveMap()

      // Nothing to undo yet.
      expect(screen.queryByRole('button', { name: 'Undo the last change' })).toBeNull()

      await tap(map, 3)
      await tap(map, 22)
      await tap(map, 13)
      expect(await screen.findByText('NOBO · 3 points · 2 legs')).toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: 'Undo the last change' }))
      expect(await screen.findByText('NOBO · 2 points · 1 leg')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Far Shelter/ })).toBeNull()

      await user.click(screen.getByRole('button', { name: 'Undo the last change' }))
      expect(await screen.findByText('1 point')).toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: 'Undo the last change' }))
      expect(await screen.findByText('0 points')).toBeInTheDocument()
      // Back to nothing, and the control leaves with the history.
      expect(screen.queryByRole('button', { name: 'Undo the last change' })).toBeNull()
    })

    it('carries a start already placed on the entrance through the door', async () => {
      const user = userEvent.setup()
      app.onboard()
      app.putTrailData({ pois: POIS })

      await openEntrance(user)
      await user.click(screen.getByRole('button', { name: /Shelter, town, or/ }))
      await user.type(await screen.findByLabelText('Search for a stop'), 'front')
      await user.click(await screen.findByRole('button', { name: /Front Shelter/ }))
      expect(await screen.findByText('mi 3.2')).toBeInTheDocument()

      await user.click(
        screen.getByRole('button', { name: /just tap the trail to drop points/ }),
      )

      // Placing it was the same act either way - it does not get thrown away
      // for having been placed on the other door.
      const panel = await screen.findByRole('dialog', { name: 'Your route' })
      expect(
        within(panel).getByRole('button', { name: /Front Shelter/ }),
      ).toBeInTheDocument()
      expect(within(panel).getByText('1 point')).toBeInTheDocument()
      expect(
        within(panel).getByText('Tap the trail again for where this stretch ends.'),
      ).toBeInTheDocument()
    })

    it('labels each dropped point with its MILE MARKER, never converted (#986)', async () => {
      const user = userEvent.setup()
      app.onboard()
      app.putTrailData({ pois: POIS })

      await openEntrance(user)
      await user.click(
        screen.getByRole('button', { name: /just tap the trail to drop points/ }),
      )
      const map = await liveMap()
      await tap(map, 3)
      await tap(map, 22)
      await screen.findByText('NOBO · 2 points · 1 leg')

      const drawn = MockMap.live[0].sourceData.get(ROUTE_SOURCE_ID) as {
        features: Array<{
          geometry: { type: string }
          properties: Record<string, string>
        }>
      }
      const labels = drawn.features
        .filter((f) => f.geometry.type === 'Point')
        .map((f) => f.properties[ROUTE_POINT_LABEL_PROPERTY])
      // The pipeline miles the stops carry, said the way stopLabel says them.
      // Not run through formatDistance: mile 3.2 is a NAME, and "5.1 km"
      // names nothing on a trail ATC measures in miles.
      expect(labels).toEqual(['mi 3.2', 'mi 22.2'])
    })

    it('forgets a refused tap when the builder closes (#986)', async () => {
      const user = userEvent.setup()
      app.onboard()
      app.putTrailData({ pois: POIS })

      await openEntrance(user)
      await user.click(
        screen.getByRole('button', { name: /just tap the trail to drop points/ }),
      )
      const map = await liveMap()
      await tap(map, 10, -81)
      const panel = await screen.findByRole('dialog', { name: 'Your route' })
      expect((await within(panel).findByRole('status')).textContent).toMatch(
        /no honest mile/,
      )

      await user.click(screen.getByRole('button', { name: 'Close the route builder' }))

      // Back in through the OTHER door. It has to be this one: the tap door
      // clears the flag on its way through, so a test that reopened that way
      // would pass with the leak still in place - which is exactly what the
      // first draft of this test did.
      await user.click(await screen.findByRole('tab', { name: 'Plan' }))
      await user.click(await screen.findByRole('button', { name: /Start on the map/ }))
      await throughPlanKind(user)
      await user.click(screen.getByRole('button', { name: /Shelter, town, or/ }))
      await user.type(await screen.findByLabelText('Search for a stop'), 'front')
      await user.click(await screen.findByRole('button', { name: /Front Shelter/ }))
      await user.click(await screen.findByRole('button', { name: 'Use this stretch' }))

      // A brand new route, greeted by an accusation about somebody else's tap.
      const fresh = await screen.findByRole('dialog', { name: 'Your route' })
      expect(within(fresh).queryByRole('status')).toBeNull()
      expect(
        within(fresh).getByText(/Only the A.T. centerline can carry a route/),
      ).toBeInTheDocument()
    })

    it('forgets a refused tap at the ENTRANCE when the builder closes (#1040)', async () => {
      // The mirror of the test above, on the other flag. #986 named this
      // exact defect and fixed `editorRefusedTap`; `entranceRefusedTap` was
      // declared for the same reason on the next line and cleared in exactly
      // one place - a successful entrance tap - so cancelling after a refused
      // one carried the accusation into the next route.
      const user = userEvent.setup()
      app.onboard()
      app.putTrailData({ pois: POIS })

      await openEntrance(user)
      const map = await liveMap()
      // Off the corridor: the entrance refuses it and says so.
      await tap(map, 10, -81)
      const sheet = await screen.findByRole('dialog', { name: 'Plan a route' })
      expect(
        within(sheet).getByText(/off the trail, so nothing moved/),
      ).toBeInTheDocument()

      await user.click(within(sheet).getByRole('button', { name: /Close/ }))

      // Straight back in, with nothing in between that would clear it.
      await user.click(await screen.findByRole('tab', { name: 'Plan' }))
      await user.click(await screen.findByRole('button', { name: /Start on the map/ }))
      await throughPlanKind(user)

      const fresh = await screen.findByRole('dialog', { name: 'Plan a route' })
      expect(within(fresh).queryByText(/off the trail, so nothing moved/)).toBeNull()
      expect(within(fresh).getByText(/just tap the trail on the map/)).toBeInTheDocument()
    })

    it('spends one undo press per real edit, never on a re-tap (#986)', async () => {
      const user = userEvent.setup()
      app.onboard()
      app.putTrailData({ pois: POIS })

      await openEntrance(user)
      await user.click(
        screen.getByRole('button', { name: /just tap the trail to drop points/ }),
      )
      const map = await liveMap()
      await tap(map, 3)
      await tap(map, 22)
      // The same mile again: insertRoutePoint refuses it, so nothing changed
      // and nothing should have been recorded.
      await tap(map, 22)
      expect(await screen.findByText('NOBO · 2 points · 1 leg')).toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: 'Undo the last change' }))
      // One press, one real edit back - not a press spent undoing the re-tap.
      expect(await screen.findByText('1 point')).toBeInTheDocument()
    })

    it('re-prices the route when the pace changes (#996)', async () => {
      const user = userEvent.setup()
      app.onboard()
      app.putTrailData({ pois: POIS })
      // The ribbon suite's climb, seeded for the same reason it exists there:
      // leg minutes print only over real elevation, and #996 is about minutes.
      const miles: number[] = []
      const feet: number[] = []
      for (let mile = 0; mile <= 40; mile += 0.1) {
        const rounded = Number(mile.toFixed(2))
        miles.push(rounded)
        feet.push(
          rounded <= 15 ? 1000 : rounded <= 17 ? 1000 + (rounded - 15) * 500 : 2000,
        )
      }
      app.store.set(ELEVATION_STORE_KEY, {
        distanceMi: Float32Array.from(miles),
        elevationFt: Float32Array.from(feet),
      })

      await openEntrance(user)
      await user.click(
        screen.getByRole('button', { name: /just tap the trail to drop points/ }),
      )
      const map = await liveMap()
      await tap(map, 3)
      await tap(map, 22)
      await screen.findByText('NOBO · 2 points · 1 leg')

      // The priced line is the builder bar's joined figures ("NOBO · 19.2 mi
      // · ≈7h 25m walking") - a sibling of the dialog, not inside it. queryBy,
      // because the minutes arrive with the elevation store's async load - the
      // first wait below is on the priced line existing at all.
      const priced = () => screen.queryByText(/walking$/)?.textContent ?? null
      await waitFor(() => expect(priced()).not.toBeNull())
      const before = priced()
      expect(before).toMatch(/≈/)

      // Settings → Map & Display → the slowest flat pace. The route is
      // untouched; only the hiker's own speed moved.
      await user.click(screen.getByRole('tab', { name: 'More' }))
      await user.click(await screen.findByRole('tab', { name: 'Map & Display' }))
      fireEvent.change(await screen.findByLabelText('Flat pace'), {
        target: { value: String(MIN_FLAT_PACE_MPH) },
      })
      await user.click(screen.getByRole('tab', { name: 'Map' }))

      // The same walk at a slower pace is a longer time. Before #996's fix the
      // figures memo did not list pace, and this panel re-opened on the memo's
      // cached answer - priced at a speed the hiker had just corrected.
      await waitFor(() => expect(priced()).not.toBe(before))
      expect(priced()).toMatch(/≈/)
    })

    it('carries a tapped route into the day planner', async () => {
      const user = userEvent.setup()
      app.onboard()
      app.putTrailData({ pois: POIS })

      await openEntrance(user)
      await user.click(
        screen.getByRole('button', { name: /just tap the trail to drop points/ }),
      )
      const map = await liveMap()

      await tap(map, 3)
      await tap(map, 22)

      await user.click(await screen.findByRole('button', { name: 'Break into days' }))
      expect(
        await screen.findByRole('dialog', { name: 'How long is a day?' }),
      ).toBeInTheDocument()
    })
  })
})

// The phone's answer to the question the desktop chart already answers (#910).
//
// The wiring is what is worth testing here rather than the drawing, which
// lib/planRibbon.test.ts and ElevationRibbon.test.tsx cover between them: WHICH
// ribbon the shell hands the map screen, and what goes with it. Two claims:
// planning swaps the fix-anchored ribbon for the planned stretch, and the
// waypoint lanes leave with it rather than staying behind under a profile of
// different ground.
describe('the ribbon while a trip is being planned', () => {
  /** A profile over the synthetic centerline's own 40 miles, on the PIPELINE
   *  axis the plan runs on - a 1,000 ft climb between miles 15 and 17 so the
   *  drawn stretch has a shape rather than a flat line. */
  function profile() {
    const miles: number[] = []
    const feet: number[] = []
    for (let mile = 0; mile <= 40; mile += 0.1) {
      const rounded = Number(mile.toFixed(2))
      miles.push(rounded)
      feet.push(rounded <= 15 ? 1000 : rounded <= 17 ? 1000 + (rounded - 15) * 500 : 2000)
    }
    return { distanceMi: Float32Array.from(miles), elevationFt: Float32Array.from(feet) }
  }

  const planRibbon = () => screen.queryByRole('img', { name: /stretch being planned/i })
  const fixRibbon = () => screen.queryByRole('img', { name: /elevation profile ahead/i })
  const wholeTrailRibbon = () =>
    screen.queryByRole('img', { name: /profile of the whole trail/i })

  it('draws the stretch as soon as the entrance has resolved two ends', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(ELEVATION_STORE_KEY, profile())

    await openEntrance(user)

    // A start alone is not a stretch. With nothing selected the ribbon is the
    // whole trail (#910 review) - the desk's resting view, on a phone - and
    // that is not the planned stretch, which is what the name has to say.
    expect(planRibbon()).not.toBeInTheDocument()
    expect(wholeTrailRibbon()).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Shelter, town, or/ }))
    await screen.findByRole('dialog', { name: 'Choose a stop' })
    await user.type(screen.getByLabelText('Search for a stop'), 'front')
    await user.click(await screen.findByRole('button', { name: /Front Shelter/ }))

    // Front Shelter (3.2) to the resolved end, Beyond Shelter (22.2).
    expect(await screen.findByText('Beyond Shelter')).toBeInTheDocument()
    await waitFor(() => expect(planRibbon()).toBeInTheDocument())

    // Nothing on it claims anything about a hiker: there is no fix in this
    // test, and a planned stretch has no "next climb" even when there is.
    expect(screen.queryByTestId('you-are-here')).not.toBeInTheDocument()
    expect(screen.queryByTestId('climb-callout')).not.toBeInTheDocument()

    // The 1,000 ft climb the stretch contains, off the profile's own axis.
    expect(screen.getByText(/2,000 ft/)).toBeInTheDocument()
  })

  it('takes the lanes with it, and gives the fix window back on close', async () => {
    const user = userEvent.setup()
    app.onboard({ location_permission_requested: true })
    app.putTrailData({ pois: POIS })
    app.store.set(ELEVATION_STORE_KEY, profile())

    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await app.reportFixAtMile(5)

    // The field instrument first: ten miles around the fix, with its lanes.
    await waitFor(() => expect(fixRibbon()).toBeInTheDocument())
    expect(screen.getByTestId('lane-sleep')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Plan' }))
    await user.click(await screen.findByRole('button', { name: 'Start on the map' }))
    await throughPlanKind(user)
    await screen.findByRole('dialog', { name: 'Plan a route' })
    await user.click(screen.getByRole('button', { name: /Shelter, town, or/ }))
    await screen.findByRole('dialog', { name: 'Choose a stop' })
    await user.type(screen.getByLabelText('Search for a stop'), 'front')
    await user.click(await screen.findByRole('button', { name: /Front Shelter/ }))

    // The swap. The lanes are re-windowed onto the planned stretch rather than
    // dropped (#913) - and onto the PIPELINE's axis, which is what the count
    // proves: Front Shelter (3.2) to Beyond Shelter (22.2) holds all four,
    // where reading the client index's own miles would put the 3.0 that starts
    // the stretch outside it and draw three.
    await waitFor(() => expect(planRibbon()).toBeInTheDocument())
    expect(fixRibbon()).not.toBeInTheDocument()
    await waitFor(() =>
      expect(
        within(screen.getByTestId('lane-sleep')).getAllByRole('button'),
      ).toHaveLength(4),
    )

    // And the first of them sits exactly at the ribbon's left edge, because
    // the stretch starts at that shelter's published mile.
    expect(
      within(screen.getByTestId('lane-sleep')).getAllByRole('button')[0],
    ).toHaveStyle({ left: '0%' })

    await user.click(screen.getByRole('button', { name: 'Close the route builder' }))

    await waitFor(() => expect(fixRibbon()).toBeInTheDocument())
    expect(planRibbon()).not.toBeInTheDocument()
    // Back to the ten miles around the fix, which hold fewer of them.
    expect(
      within(screen.getByTestId('lane-sleep')).getAllByRole('button').length,
    ).toBeLessThan(4)
  })

  it('follows the map once the hiker pans it, and gives the fix back on request', async () => {
    // The review's "always in sync". A pan is something the hiker just DID, so
    // it outranks their fix - but only a real gesture does, and only until
    // they ask for themselves back.
    const user = userEvent.setup()
    app.onboard({ location_permission_requested: true })
    app.putTrailData({ pois: POIS })
    app.store.set(ELEVATION_STORE_KEY, profile())

    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await app.reportFixAtMile(5)
    await waitFor(() => expect(fixRibbon()).toBeInTheDocument())
    // One shelter is inside the ten-mile fix window; the pan below puts four
    // on screen, which is what makes the lane counts tell the domains apart.
    expect(within(screen.getByTestId('lane-sleep')).getAllByRole('button')).toHaveLength(
      1,
    )

    const map = MockMap.live[0]

    // A camera move the SHELL made carries no originalEvent, and must not take
    // the ribbon off the hiker - otherwise every download re-frame would.
    act(() => {
      map.bounds = {
        west: -77.5,
        east: -76.5,
        south: latOfMile(0),
        north: latOfMile(30),
      }
      map.emit('moveend', {})
    })
    await waitFor(() => expect(fixRibbon()).toBeInTheDocument())

    // The hiker's own pan does.
    act(() => {
      map.emit('moveend', { originalEvent: new Event('pointerup') })
    })

    const mapRibbon = await screen.findByRole('img', {
      name: /trail shown on the map/i,
    })
    expect(mapRibbon).toBeInTheDocument()
    expect(fixRibbon()).not.toBeInTheDocument()
    // The lanes go where the ribbon goes (#913): the mapped stretch holds all
    // four shelters, where the fix window held one.
    await waitFor(() =>
      expect(
        within(screen.getByTestId('lane-sleep')).getAllByRole('button'),
      ).toHaveLength(4),
    )

    await user.click(screen.getByRole('button', { name: 'Back to me' }))

    await waitFor(() => expect(fixRibbon()).toBeInTheDocument())
    await waitFor(() =>
      expect(
        within(screen.getByTestId('lane-sleep')).getAllByRole('button'),
      ).toHaveLength(1),
    )
  })

  it("offers the chart's own framing buttons, and only the ones that would do something", async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(ELEVATION_STORE_KEY, profile())

    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    // Resting on the whole trail: "Whole trail" would do nothing, and neither
    // would framing a domain that IS the whole trail. So neither is offered.
    await waitFor(() => expect(wholeTrailRibbon()).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Whole trail' })).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Zoom to stretch' }),
    ).not.toBeInTheDocument()

    // With a route being planned both are worth having, and "Zoom to stretch"
    // frames the plan on the map.
    await user.click(await screen.findByRole('tab', { name: 'Plan' }))
    await user.click(await screen.findByRole('button', { name: 'Start on the map' }))
    await throughPlanKind(user)
    await screen.findByRole('dialog', { name: 'Plan a route' })
    await user.click(screen.getByRole('button', { name: /Shelter, town, or/ }))
    await screen.findByRole('dialog', { name: 'Choose a stop' })
    await user.type(screen.getByLabelText('Search for a stop'), 'front')
    await user.click(await screen.findByRole('button', { name: /Front Shelter/ }))
    await waitFor(() => expect(planRibbon()).toBeInTheDocument())

    const before = MockMap.live[0].cameraMoves.length
    await user.click(screen.getByRole('button', { name: 'Zoom to stretch' }))
    expect(MockMap.live[0].cameraMoves.length).toBeGreaterThan(before)
    expect(screen.getByRole('button', { name: 'Whole trail' })).toBeInTheDocument()

    // And framing the map is not a gesture, so the ribbon stays on the plan
    // rather than flipping to the viewport it just moved.
    expect(planRibbon()).toBeInTheDocument()
  })
})
