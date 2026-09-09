// The long hike as a set of WINDOWS rather than takeovers (#1329), and the
// map door inside set-up that could not reach a map until they were.
//
// #1317 shipped nine long-hike surfaces in two arrangements - three sheets
// docked to the bottom edge, five screens in App's `flowScreen` chain - and
// a maintainer using it on a desktop found both: a sheet at the foot of a
// 1440px browser, and "having them full screen makes it hard for me to
// remember where I am". `flowScreen` is also what made "Choose on the map"
// impossible: it hides the map subtree and makes it inert, so the door had
// nothing behind it and was wired to close the picker and do nothing.
//
// The SHAPE of the window at each width is desktop.css's and is held by
// test/desktopLayout.test.ts, which can see a stylesheet. What is held here
// is what jsdom can see: that every surface goes through one chrome, that
// the map is inert underneath it and reachable while a point is being
// placed, and that a tap lands as a point on the hike.

import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, act, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { appHarness, latOfMile } from './test/appHarness'
import { MockMap } from './test/mocks/maplibre-gl'
import { TRIPS_KEY, type TripStore } from './lib/trips'
import { HIKER_MODE_KEY } from './lib/hikerMode'

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  getMany: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./map/archiveZooms', () => ({
  readArchiveZooms: () => Promise.resolve(null),
  readArchiveFootprint: () => Promise.resolve(null),
}))
vi.mock('./lib/api', () => ({
  API_CONFIGURED: false,
  accessToken: vi.fn(async () => null),
  sendReport: vi.fn(async () => undefined),
  permanentFailureReason: vi.fn(() => null),
  fetchClosures: vi.fn(async () => []),
  fetchFieldNotes: vi.fn(async () => []),
  fetchDisputes: vi.fn(async () => []),
  fetchReports: vi.fn(async () => []),
}))

const app = appHarness({ navigator: { onLine: false }, objectUrls: true })

/** Shelters on the synthetic centerline, with the pipeline's own mile 0.2
 *  above the client index's - App.plan.test.tsx's fixture and its reason:
 *  the anchor correction has to be visible end to end (HIKE_PLANNING.md
 *  Finding 1). */
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
  shelter(22, 'Beyond Shelter'),
]

function hikeStore(over: Partial<TripStore> = {}): TripStore {
  return {
    trips: [],
    openId: null,
    groups: [],
    hikes: [
      {
        id: 'hike-1',
        name: 'Springer → Katahdin',
        type: 'thru',
        trailId: 'AT',
        status: 'walking',
        points: [
          { poiId: 's3', name: 'Front Shelter', mile: 3.2 },
          { poiId: 's22', name: 'Beyond Shelter', mile: 22.2 },
        ],
        tripIds: [],
      },
    ],
    activeHikeId: 'hike-1',
    ...over,
  }
}

const windows = () => document.querySelectorAll('.hike-window')

describe('every long-hike surface goes through one window', () => {
  it('opens the pick sheet in the window chrome, not welded to the screen', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    render(<App />)

    await user.click(await screen.findByRole('radio', { name: 'Long hike' }))
    expect(
      await screen.findByRole('dialog', { name: 'Which long hike?' }),
    ).toBeInTheDocument()

    const dock = windows()
    expect(dock).toHaveLength(1)
    expect(dock[0]?.className).toContain('hike-window--sheet')
  })

  it('opens set-up in the same chrome rather than as a screen of its own', async () => {
    // Set-up was a `flowScreen` - the arrangement that replaces the screen
    // and unmounts the map. Whether the map behind is INERT is asserted in
    // the map-door test below, where there is a map to assert it about: a
    // launch that stays on Today builds none, deliberately (the entry
    // budget), so there is nothing to be inert here.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    render(<App />)

    await user.click(await screen.findByRole('radio', { name: 'Long hike' }))
    await user.click(await screen.findByRole('button', { name: /A new long hike/ }))

    const setUp = windows()
    expect(setUp).toHaveLength(1)
    expect(setUp[0]?.className).toContain('hike-window--screen')
    expect(screen.getByRole('heading', { name: 'A new long hike' })).toBeInTheDocument()
    // The sheet that opened it is gone rather than waiting underneath: one
    // window at a time, so closing set-up does not land on a second modal.
    expect(screen.queryByRole('dialog', { name: 'Which long hike?' })).toBeNull()
  })
})

describe('choosing a hike point on the map (#1329)', () => {
  it('arms a real tap, refuses off-trail out loud, and places the point', async () => {
    // The door was wired to `() => setHikePointAt(null)`: it closed the
    // picker and placed nothing, because a `flowScreen` had unmounted the
    // map it was offering.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    render(<App />)

    await user.click(await screen.findByRole('radio', { name: 'Long hike' }))
    await user.click(await screen.findByRole('button', { name: /A new long hike/ }))
    await user.click(
      await screen.findByRole('button', { name: /Add a point on the way/ }),
    )

    const picker = await screen.findByRole('dialog', { name: 'Choose a stop' })
    await user.click(within(picker).getByRole('button', { name: 'Choose on the map' }))

    // The bar is up, and the window has stood aside rather than closed - the
    // draft it holds is not something one tap may cost somebody.
    expect(
      await screen.findByText('Tap the trail where this stop goes.'),
    ).toBeInTheDocument()
    expect(document.querySelector('.hike-window--stood-aside')).not.toBeNull()
    // ...and the map is reachable again, because it is what the hiker is
    // aiming at.
    expect(document.querySelector('.map-screen')?.closest('[inert]')).toBeNull()

    await waitFor(() => {
      expect(MockMap.live).toHaveLength(1)
      expect(MockMap.live[0].listenerCount('click')).toBeGreaterThan(0)
    })
    const map = MockMap.live[0]

    // Four degrees west of the centerline, far past the 3-mile gate.
    // Refused where the finger landed, and the bar stays open.
    await act(async () => {
      map.emit('click', { lngLat: { lng: -81, lat: latOfMile(10) } })
    })
    expect(await screen.findByText(/no honest mile/)).toBeInTheDocument()

    // An on-trail tap at client mile 10 lands on Middle Shelter, whose
    // PIPELINE mile is 10.2 - the anchor correction, carried end to end.
    await act(async () => {
      map.emit('click', { lngLat: { lng: -77, lat: latOfMile(10) } })
    })
    const back = await screen.findByRole('heading', { name: 'A new long hike' })
    expect(back).toBeInTheDocument()
    expect(document.querySelector('.hike-window--stood-aside')).toBeNull()
    expect(screen.getByText('Middle Shelter')).toBeInTheDocument()
    expect(screen.getByText(/mi 10\.2/)).toBeInTheDocument()
    // ...and the map goes back behind the modal it came out from.
    expect(document.querySelector('.map-screen')?.closest('[inert]')).not.toBeNull()
  })
})

describe('the hike a hiker is on, in Plan (#1329)', () => {
  it('names the hike in the band and offers the way onto another', async () => {
    // "When I save a long hike, it is not displaying anywhere." Half of that
    // report was this: the Plan tab's band read "Sections" and the room
    // showed a generic list, so nothing said which hike.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(TRIPS_KEY, hikeStore())
    app.store.set(HIKER_MODE_KEY, 'long')
    render(<App />)

    await user.click(await screen.findByRole('tab', { name: 'Plan' }))
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Springer → Katahdin' }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Switch hike/ }))
    // Named for what it is doing: the dialog's label and its heading are one
    // string, so the sheet announces itself as the switch it is rather than
    // as the first pick it was written for.
    expect(
      await screen.findByRole('dialog', { name: 'Which hike are you on?' }),
    ).toBeInTheDocument()
  })

  it('closing the switch keeps the hike, rather than reverting to Day hike', async () => {
    // The handoff's deliberate exception is about the sheet's FIRST job.
    // Reverting a hiker who looked at their other hike and decided to stay
    // would be the app punishing them for looking.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({ pois: POIS })
    app.store.set(TRIPS_KEY, hikeStore())
    app.store.set(HIKER_MODE_KEY, 'long')
    render(<App />)

    await user.click(await screen.findByRole('tab', { name: 'Plan' }))
    await user.click(await screen.findByRole('button', { name: /Switch hike/ }))
    await user.click(await screen.findByRole('button', { name: 'Close' }))

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Springer → Katahdin' }),
    ).toBeInTheDocument()
    expect(windows()).toHaveLength(0)
  })
})
