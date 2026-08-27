// Following a saved day hike, wired end to end (#1041, frames `D9`-`D11`).
//
// Every rule in the flow has an owner elsewhere - lib/dayHikeTurns.test.ts
// holds which junctions are turns and which way each arm goes,
// lib/dayHikeFollow.test.ts holds where the hiker is and the hysteresis that
// stops the band strobing, and the three chrome suites hold what each card
// is allowed to say. What is held HERE is the WIRING: the card's door starts
// the mode, the header stops saying "mi 486.2 · NOBO" and starts saying the
// walk's own distances, the fix drives the turn card, and leaving the route
// puts the band up.
//
// ORDERING NOTE (CLAUDE.md): this file awaits fetches, then delivers GPS
// fixes, then asserts on re-renders - the shape that has passed locally and
// failed on CI before. Every wait below is on something observable (a
// rendered consequence), never a tick, and the file is run three times
// before any push.

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import App from './App'
import { DAY_HIKE_SOURCE_ID } from './map/dayHikeLayers'
import { MockMap } from './test/mocks/maplibre-gl'
import { DAY_HIKES_KEY } from './lib/dayHikes'
import { ELEVATION_STORE_KEY } from './lib/trailData'
import {
  TRAIL_GRAPH_GEOMETRY_KEY,
  TRAIL_GRAPH_KEY,
  TRAIL_GRAPH_PROFILE_KEY,
} from './lib/config'
import { appHarness, MILE_LAT } from './test/appHarness'

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
  fetchDisputes: vi.fn(async () => []),
  fetchReports: vi.fn(async () => []),
  fetchPoiPhotos: vi.fn(async () => []),
}))
vi.mock('./lib/config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./lib/config')>()),
  DATA_BASE_URL: 'https://data.example',
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.example/${key}`,
}))

const app = appHarness({
  navigator: { onLine: true, geolocation: true },
  objectUrls: true,
  stubFetch: false,
})

// The same Harriman-ish T the builder's suite uses: Pine Meadow east-west
// with a junction at node 1, Seven Hills north from it.
//
//        3 (-74.09, 41.26)   Seven Hills Trail, NYNJTC, white
//        |
//   0 -- 1 -- 2              Pine Meadow Trail, NYS Parks, blue
const GRAPH = JSON.stringify({
  nodes: [
    [-74.1, 41.25],
    [-74.09, 41.25],
    [-74.08, 41.25],
    [-74.09, 41.26],
  ],
  edges: [
    {
      from: 0,
      to: 1,
      length_m: 836,
      trail_id: 'oprhp_trails:1',
      source: 'oprhp_trails',
      name: 'Pine Meadow Trail',
      blaze_color: 'Blue',
    },
    {
      from: 1,
      to: 2,
      length_m: 836,
      trail_id: 'oprhp_trails:1',
      source: 'oprhp_trails',
      name: 'Pine Meadow Trail',
      blaze_color: 'Blue',
    },
    {
      from: 1,
      to: 3,
      length_m: 1112,
      trail_id: 'nynjtc_long_path:2',
      source: 'nynjtc_long_path',
      name: 'Seven Hills Trail',
      blaze_color: 'White',
    },
  ],
})

const GEOMETRY = JSON.stringify([
  [
    [-74.1, 41.25],
    [-74.09, 41.25],
  ],
  [
    [-74.09, 41.25],
    [-74.08, 41.25],
  ],
  [
    [-74.09, 41.25],
    [-74.09, 41.26],
  ],
])

/** West end of Pine Meadow, up and over onto Seven Hills. One turn. */
const HIKE = {
  hikes: [
    {
      id: 'followed-hike',
      name: 'Pine Meadow to Seven Hills',
      date: null,
      segments: [
        [
          { coord: [-74.1, 41.25], poiId: null },
          { coord: [-74.09, 41.26], poiId: null },
        ],
      ],
      figures: {
        miles: 1.21,
        legs: [
          {
            name: 'Pine Meadow Trail',
            source: 'oprhp_trails',
            blaze_color: 'Blue',
            miles: 1.21,
          },
        ],
      },
      looped: false,
      recorded: 'planned',
    },
  ],
  openId: null,
}

/** Out to the junction and back, over one edge, both ways. The shape
 *  `route.edgeIndices` cannot describe: deduplicated it is `[0]`, and the
 *  first and last tap are the same coordinate. */
const OUT_AND_BACK = {
  hikes: [
    {
      id: 'there-and-back',
      name: 'Pine Meadow out and back',
      date: null,
      segments: [
        [
          { coord: [-74.1, 41.25], poiId: null },
          { coord: [-74.09, 41.25], poiId: null },
          { coord: [-74.1, 41.25], poiId: null },
        ],
      ],
      figures: {
        miles: 1.04,
        legs: [
          {
            name: 'Pine Meadow Trail',
            source: 'oprhp_trails',
            blaze_color: 'Blue',
            miles: 1.04,
          },
        ],
      },
      looped: false,
      recorded: 'planned',
    },
  ],
  openId: null,
}

async function hashOf(body: string): Promise<string> {
  const digest = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(body) as unknown as BufferSource,
  )
  return [...new Uint8Array(digest)]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
}

/** The dense per-edge profile (#1045), one array of whole feet per edge.
 *  Pine Meadow climbs west to east and Seven Hills climbs north, so the walk
 *  in `HIKE` is one long rise and any test reading an edge backwards would
 *  draw a different shape. */
const PROFILE = JSON.stringify([
  [900, 950, 1000, 1050, 1100],
  [1100, 1150, 1200, 1250, 1300],
  [1100, 1200, 1300, 1400, 1500],
])

async function serveGraph({ profile = false } = {}) {
  const manifest = {
    artifacts: {
      [TRAIL_GRAPH_KEY]: { sha256: await hashOf(GRAPH) },
      [TRAIL_GRAPH_GEOMETRY_KEY]: { sha256: await hashOf(GEOMETRY) },
      // Absent unless a test asks for it, because absent is the ordinary
      // state: the profile is fetched only once a walk is being followed, and
      // a release built without `include_elevation` does not carry it at all.
      ...(profile
        ? { [TRAIL_GRAPH_PROFILE_KEY]: { sha256: await hashOf(PROFILE) } }
        : {}),
    },
  }
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      const key = String(url)
      if (key.includes('latest.json')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(manifest),
        } as unknown as Response)
      }
      const body =
        profile && key.includes(TRAIL_GRAPH_PROFILE_KEY)
          ? PROFILE
          : key.includes(TRAIL_GRAPH_GEOMETRY_KEY)
            ? GEOMETRY
            : key.includes(TRAIL_GRAPH_KEY)
              ? GRAPH
              : null
      if (body === null) {
        return Promise.resolve({ ok: false, status: 404 } as unknown as Response)
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        arrayBuffer: () => Promise.resolve(new TextEncoder().encode(body).buffer),
      } as unknown as Response)
    }),
  )
}

/** The harness delivers a fix by mile of its synthetic north-south
 *  centerline; this is the mile whose latitude is the one wanted. Harriman is
 *  nowhere near that centerline, which is the point - see the first
 *  assertion below. */
const mileAtLatitude = (lat: number) => (lat - 39) / MILE_LAT

/** Through the Plan tab to the saved hike's card, and out onto the map. */
async function startFollowing(user: ReturnType<typeof userEvent.setup>) {
  render(<App />)
  await user.click(await screen.findByRole('tab', { name: 'Plan' }))
  await user.click(
    await screen.findByRole('button', { name: /Pine Meadow to Seven Hills/ }),
  )
  await user.click(
    await screen.findByRole('button', { name: 'Follow this hike on the map' }),
  )
}

describe('following a day hike, end to end', () => {
  it('replaces the Springer mile with the walk s own distances', async () => {
    const user = userEvent.setup()
    app.onboard({ location_permission_requested: true })
    app.putTrailData()
    app.store.set(DAY_HIKES_KEY, HIKE)
    await serveGraph()

    await startFollowing(user)
    // Halfway along Pine Meadow, 2,000 miles from the A.T. centerline this
    // harness draws - so `locateOnTrail` refuses the fix and the old header
    // would have said "Off the trail" to somebody standing on a blazed trail.
    await app.reportFixAtMile(mileAtLatitude(41.25), -74.095)

    expect(await screen.findByText('0.3 mi in · 1.0 mi to go')).toBeInTheDocument()
    // And the eyebrow carries the mode, at no cost in pixels.
    expect(await screen.findByText(/Day hike · leg 1 of 2/)).toBeInTheDocument()
  })

  it('calls the turn ahead, and opens the junction on it', async () => {
    const user = userEvent.setup()
    app.onboard({ location_permission_requested: true })
    app.putTrailData()
    app.store.set(DAY_HIKES_KEY, HIKE)
    await serveGraph()

    await startFollowing(user)
    await app.reportFixAtMile(mileAtLatitude(41.25), -74.095)

    expect(
      await screen.findByText('turn left onto Seven Hills Trail'),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'This turn' }))
    expect(
      await screen.findByRole('heading', { name: 'Turn left onto Seven Hills Trail' }),
    ).toBeInTheDocument()
    // Both arms accounted for: the one that carries on and the one behind.
    expect(
      screen.getByText(/Straight on is Pine Meadow Trail, blue blaze — not your route/),
    ).toBeInTheDocument()
  })

  it('raises the band, and refuses a line back, once the hiker leaves it', async () => {
    const user = userEvent.setup()
    app.onboard({ location_permission_requested: true })
    app.putTrailData()
    app.store.set(DAY_HIKES_KEY, HIKE)
    await serveGraph()

    await startFollowing(user)
    // ~600 ft north of the line, which is well past OFF_ROUTE_FEET.
    await app.reportFixAtMile(mileAtLatitude(41.2516), -74.095)

    await waitFor(() => {
      expect(screen.getByText('You are not on your route')).toBeInTheDocument()
    })
    // What is SAID, end to end: one polite sentence with no figure in it, on
    // the screen's single live region (#1055). The band keeps the distance
    // for the eye; a live region holding a per-fix number re-announces on
    // every fix, which is #315's defect and was this band's until #1055.
    const live = document.querySelector('[aria-live="polite"].visually-hidden')
    expect(live).toHaveTextContent('You are off your route.')
    expect(live).not.toHaveTextContent(/\d/)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByText('We will not draw you a line back')).toBeInTheDocument()
    // The one navigational thing this screen can honestly offer.
    expect(
      screen.getByRole('button', { name: 'Show the whole route' }),
    ).toBeInTheDocument()
  })

  it('keeps a way out of the mode when the fix is lost', async () => {
    // Following with no fix used to render no card at all - and the only
    // Stop control in the app lives inside these cards, so a hiker whose GPS
    // dropped under canopy was left in a mode the header still announced with
    // nothing on screen to leave it by (#1044 review).
    const user = userEvent.setup()
    app.onboard({ location_permission_requested: true })
    app.putTrailData()
    app.store.set(DAY_HIKES_KEY, HIKE)
    await serveGraph()

    await startFollowing(user)
    // No fix has been delivered at all - the ordinary first seconds.
    expect(await screen.findByText(/Waiting for GPS/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument()
    // And the header still says which mode this is, so the two agree.
    expect(screen.getByText(/Day hike/)).toBeInTheDocument()
  })

  it('stops following when a builder opens, rather than covering it', async () => {
    // The follow card outranks the route builder in MapScreen's routeSheet
    // slot, so leaving following on meant the card sat over a live builder -
    // no end picker, no Cancel - while map taps still went into the draft
    // underneath (#1044 review). Following is a surface, and the shell's
    // one-thing-open sweep is where that rule lives.
    const user = userEvent.setup()
    app.onboard({ location_permission_requested: true })
    app.putTrailData()
    app.store.set(DAY_HIKES_KEY, HIKE)
    await serveGraph()

    await startFollowing(user)
    await app.reportFixAtMile(mileAtLatitude(41.25), -74.095)
    await screen.findByText('turn left onto Seven Hills Trail')

    await user.click(await screen.findByRole('tab', { name: 'Plan' }))
    // The day room's primary goes straight into the builder (App.tsx wires
    // onNewDayHike to openDayHike), which is the sweep under test.
    await user.click(await screen.findByRole('button', { name: 'Plan a day hike' }))

    await waitFor(() => {
      expect(
        screen.queryByText('turn left onto Seven Hills Trail'),
      ).not.toBeInTheDocument()
    })
    expect(screen.queryByText(/Waiting for GPS/i)).not.toBeInTheDocument()
  })

  it('gives the map back when following stops', async () => {
    const user = userEvent.setup()
    app.onboard({ location_permission_requested: true })
    app.putTrailData()
    app.store.set(DAY_HIKES_KEY, HIKE)
    await serveGraph()

    await startFollowing(user)
    await app.reportFixAtMile(mileAtLatitude(41.25), -74.095)
    await screen.findByText('turn left onto Seven Hills Trail')

    await user.click(screen.getByRole('button', { name: 'Stop' }))

    await waitFor(() => {
      expect(
        screen.queryByText('turn left onto Seven Hills Trail'),
      ).not.toBeInTheDocument()
    })
    // Back to the A.T.'s own header, and to its own honest refusal about a
    // fix two thousand miles off the corridor.
    expect(screen.getByText('Off the trail')).toBeInTheDocument()
  })

  it('draws the ground walked twice, on a walk that re-uses one edge', async () => {
    // #1040's defect, on this surface. Following used to hand
    // `segment.route.edgeIndices` and the outer taps to routeGeometry; that
    // list is deduplicated across leg joins, so an out-and-back over one edge
    // is `[0]` trimmed between two taps that are the SAME COORDINATE - a
    // zero-length span, which routeGeometry refuses, which meant no route on
    // the map at all. #1040 measured it on the builder at 0.62 mi; the same
    // call was still here, under a hiker who is out walking the thing.
    const user = userEvent.setup()
    app.onboard({ location_permission_requested: true })
    app.putTrailData()
    app.store.set(DAY_HIKES_KEY, OUT_AND_BACK)
    await serveGraph()

    render(<App />)
    await user.click(await screen.findByRole('tab', { name: 'Plan' }))
    await user.click(
      await screen.findByRole('button', { name: /Pine Meadow out and back/ }),
    )
    await user.click(
      await screen.findByRole('button', { name: 'Follow this hike on the map' }),
    )
    await app.reportFixAtMile(mileAtLatitude(41.25), -74.095)
    // Waits on the follow state itself, not on a tick: the drawing and this
    // line come from the same resolution, so a rendered distance proves the
    // route was resolved before sourceData is read.
    await screen.findByText(/mi in ·/)

    const drawn = MockMap.live[0].sourceData.get(DAY_HIKE_SOURCE_ID) as {
      features: Array<{ geometry: { type: string; coordinates: number[][][] } }>
    }
    const walked = drawn.features.filter(
      (feature) => feature.geometry.type === 'MultiLineString',
    )
    // Twice, because it was walked twice. Drawn once over itself is what
    // happened on the ground; drawn not at all is the bug.
    expect(walked).toHaveLength(1)
    expect(walked[0].geometry.coordinates).toEqual([
      [
        [-74.1, 41.25],
        [-74.09, 41.25],
      ],
      [
        [-74.09, 41.25],
        [-74.1, 41.25],
      ],
    ])
  })

  it('draws the walk\u2019s own elevation once the profile arrives (#1045)', async () => {
    // The whole wiring in one assertion: the fetch fires because a walk is
    // being followed, lib/walkProfile.ts turns the walk into samples on its
    // own axis, and lib/ribbonView.ts prefers them. The accessible name is
    // the claim being checked - "ahead" is about the A.T. and this is not.
    const user = userEvent.setup()
    app.onboard({ location_permission_requested: true })
    app.putTrailData()
    app.store.set(DAY_HIKES_KEY, HIKE)
    await serveGraph({ profile: true })

    await startFollowing(user)
    await app.reportFixAtMile(mileAtLatitude(41.25), -74.095)
    await screen.findByText(/mi in \u00b7/)

    expect(
      await screen.findByRole('img', { name: /whole walk today/i }),
    ).toBeInTheDocument()
  })

  it('draws no ribbon at all when the release carries no profile', async () => {
    // #1041's honest state, kept - and this is the half #1045 calls a bug.
    // The A.T.'s OWN profile is in this phone's download, so before the fix
    // the ribbon fell through to it and drew the Appalachian Trail under a
    // header counting down a Harriman walk. A walk this phone has no shape
    // for gets NOTHING rather than another walk's shape borrowed.
    const user = userEvent.setup()
    app.onboard({ location_permission_requested: true })
    app.putTrailData()
    app.store.set(ELEVATION_STORE_KEY, {
      distanceMi: Float32Array.from({ length: 200 }, (_, i) => i / 10),
      elevationFt: Float32Array.from({ length: 200 }, (_, i) => 1000 + (i % 20) * 60),
    })
    app.store.set(DAY_HIKES_KEY, HIKE)
    await serveGraph()

    await startFollowing(user)
    await app.reportFixAtMile(mileAtLatitude(41.25), -74.095)
    await screen.findByText(/mi in \u00b7/)

    expect(
      screen.queryByRole('img', { name: /Elevation profile/i }),
    ).not.toBeInTheDocument()
  })
})
