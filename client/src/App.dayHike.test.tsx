// The day-hike builder, wired end to end (#978, #977, #976 - wireframe
// frames `1i`-`1j`).
//
// Every rule in the flow already has an owner - lib/dayHikeDraft.test.ts holds
// the draft's rules, lib/trailGraph.test.ts the router's, and
// chrome/DayHikePickBar.test.tsx the bar's honesty. What is held HERE is the
// WIRING: the Plan tab's one primary action opens the door, the door opens
// the mode, the canvas hands taps to tapAt, the bar renders what the router
// answered, and Done lands one record in the store.
//
// ORDERING NOTE (CLAUDE.md): this file awaits fetches, then emits map events,
// then asserts on re-renders - the exact shape that has passed locally and
// failed on CI before. Every wait below is on something observable (a
// rendered consequence, a listener count), never a tick, and the file is run
// three times before any push.

import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import App from './App'
import { DAY_HIKES_KEY } from './lib/dayHikes'
import { TRAIL_GRAPH_GEOMETRY_KEY, TRAIL_GRAPH_KEY } from './lib/config'
import { appHarness } from './test/appHarness'
import { MockMap } from './test/mocks/maplibre-gl'

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
}))
// The graph loader reads DATA_CONFIGURED and dataUrl; the harness's app runs
// with neither configured, so this file turns them on and serves the two
// artifacts itself - trailGraphData.test.ts's pattern, inside the whole app.
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

// A Harriman-ish T: Pine Meadow east-west with a junction at node 1, Seven
// Hills north from it. Lengths are what the pipeline would publish.
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
      blaze_color: 'blue',
    },
    {
      from: 1,
      to: 2,
      length_m: 836,
      trail_id: 'oprhp_trails:1',
      source: 'oprhp_trails',
      name: 'Pine Meadow Trail',
      blaze_color: 'blue',
    },
    {
      from: 1,
      to: 3,
      length_m: 1112,
      trail_id: 'nynjtc_long_path:2',
      source: 'nynjtc_long_path',
      name: 'Seven Hills Trail',
      blaze_color: 'white',
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

const STEWARDS = {
  stewards: [
    {
      provider: 'NYS OPRHP',
      name: 'NYS Parks',
      trust: null,
      licence: null,
      attribution: null,
      layers: [],
      keys: ['oprhp_trails'],
    },
    {
      provider: 'NYNJTC',
      name: 'NY–NJ Trail Conference',
      trust: null,
      licence: null,
      attribution: null,
      layers: [],
      keys: ['nynjtc_long_path'],
    },
  ],
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

/** Serve the graph pair (hashed) and 404 everything else the shell asks for. */
async function serveGraph({ withGraph = true } = {}) {
  const manifest = {
    artifacts: {
      [TRAIL_GRAPH_KEY]: { sha256: await hashOf(GRAPH) },
      [TRAIL_GRAPH_GEOMETRY_KEY]: { sha256: await hashOf(GEOMETRY) },
    },
  }
  const requested: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      const key = String(url)
      requested.push(key)
      if (key.includes('latest.json')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(manifest),
        } as unknown as Response)
      }
      const body = key.includes(TRAIL_GRAPH_GEOMETRY_KEY)
        ? GEOMETRY
        : key.includes(TRAIL_GRAPH_KEY)
          ? GRAPH
          : null
      if (body === null || !withGraph) {
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
  return requested
}

/** Through the Plan tab's one primary action to the door. */
async function openDoor(user: ReturnType<typeof userEvent.setup>) {
  render(<App />)
  await user.click(await screen.findByRole('tab', { name: 'Plan' }))
  await user.click(await screen.findByRole('button', { name: 'Start on the map' }))
  return await screen.findByRole('dialog', { name: 'What are you planning?' })
}

/** The live map with the tap listener attached - a wait on something
 *  observable that proves the wiring, never on a tick. */
async function liveMap() {
  await waitFor(() => {
    expect(MockMap.live.length).toBeGreaterThan(0)
    expect(MockMap.live[0].listenerCount('click')).toBeGreaterThan(0)
  })
  return MockMap.live[0]
}

const tap = async (map: MockMap, lng: number, lat: number) => {
  await act(async () => {
    map.emit('click', { lngLat: { lng, lat } })
  })
}

describe('the day-hike builder, end to end', () => {
  it('walks door → taps → live tally → close the loop → a saved day hike', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData()
    app.store.set('ourhike:stewards', STEWARDS)
    await serveGraph()

    await openDoor(user)

    // The graph loaded, so the day-hike option is a BUTTON - waiting on this
    // rendered consequence is what proves the fetch landed, not a timer.
    await user.click(await screen.findByRole('button', { name: /A day hike/ }))

    // Frame 1j's bar, on the trail tab, listening.
    expect(await screen.findByText(/Tap a trail to walk it/)).toBeInTheDocument()
    const map = await liveMap()

    // Two taps along Pine Meadow: mid-first-edge to mid-second-edge.
    await tap(map, -74.095, 41.25)
    await tap(map, -74.085, 41.25)

    // One trail so far - one leg, and NYS Parks' name from the steward join,
    // never the raw source key.
    expect(await screen.findByText(/1 leg ·/)).toBeInTheDocument()
    expect(screen.getByText(/NYS Parks · 1 leg/)).toBeInTheDocument()
    expect(screen.queryByText(/oprhp_trails/)).not.toBeInTheDocument()

    // Up Seven Hills: a second org joins the tally, live.
    await tap(map, -74.09, 41.255)
    expect(await screen.findByText(/2 legs/)).toBeInTheDocument()
    expect(screen.getByText(/NY–NJ Trail Conference · 1 leg/)).toBeInTheDocument()

    // Close the loop, then Done - which exists only now that a route does.
    await user.click(screen.getByRole('button', { name: 'Close the loop' }))
    await user.click(await screen.findByRole('button', { name: 'Done' }))

    // Done opens frame `1l`'s card as a REVIEW - nothing stored yet. Every
    // edge the fixture holds is on this loop, so the ways-off block prints
    // its decided sentence rather than omitting itself.
    expect(
      await screen.findByRole('button', { name: 'Save this day hike' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/No marked trail leaves this loop/)).toBeInTheDocument()
    expect(app.store.get(DAY_HIKES_KEY)).toBeUndefined()

    // The commit is the card's own primary action.
    await user.click(screen.getByRole('button', { name: 'Save this day hike' }))

    // ONE record landed, ends as coordinates - never a GraphPoint.edgeIndex,
    // which a republished graph would silently shift.
    await waitFor(() => {
      expect(app.store.get(DAY_HIKES_KEY)).toBeDefined()
    })
    const stored = app.store.get(DAY_HIKES_KEY) as {
      hikes: Array<{
        name: string
        looped: boolean
        segments: Array<Array<{ coord: [number, number]; poiId: null }>>
        figures: { miles: number; legs: Array<{ name: string | null }> }
      }>
      openId: string | null
    }
    expect(stored.hikes).toHaveLength(1)
    const hike = stored.hikes[0]
    expect(hike.looped).toBe(true)
    expect(hike.segments[0]).toHaveLength(3)
    expect(hike.segments[0][0].coord[0]).toBeCloseTo(-74.095, 2)
    expect(hike.figures.miles).toBeGreaterThan(0)
    expect(screen.queryByText(/Tap a trail to walk it/)).not.toBeInTheDocument()
  })

  it('refuses a tap off every maintained line, with the sentence', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData()
    await serveGraph()

    await openDoor(user)
    await user.click(await screen.findByRole('button', { name: /A day hike/ }))
    const map = await liveMap()

    // ~5 km north of anything routable.
    await tap(map, -74.095, 41.3)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /only builds routes on trails an organization maintains/,
    )
    // Placed nothing: still no route total on the bar.
    expect(screen.queryByText(/leg ·/)).not.toBeInTheDocument()
  })

  it('fetches the heavy geometry only after the door opens', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData()
    const requested = await serveGraph()

    const door = await openDoor(user)
    expect(door).toBeInTheDocument()
    await screen.findByRole('button', { name: /A day hike/ })

    // The routing half loads at launch; the geometry half must not have been
    // asked for yet - it is by far the heavier artifact.
    expect(requested.some((url) => url.includes(TRAIL_GRAPH_KEY))).toBe(true)
    expect(requested.some((url) => url.includes(TRAIL_GRAPH_GEOMETRY_KEY))).toBe(false)

    await user.click(screen.getByRole('button', { name: /A day hike/ }))
    await waitFor(() => {
      expect(requested.some((url) => url.includes(TRAIL_GRAPH_GEOMETRY_KEY))).toBe(true)
    })
  })

  it('reopens a saved hike from the Plan home, shows its ways off, and deletes it', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData()
    app.store.set('ourhike:stewards', STEWARDS)
    await serveGraph()

    // A hike saved by an earlier session: ends mid-first-edge and
    // mid-second-edge of Pine Meadow, walking through the Seven Hills
    // junction. Cached figures deliberately stale (7 miles) - the card must
    // re-derive against the live graph, not print the cache.
    app.store.set(DAY_HIKES_KEY, {
      hikes: [
        {
          id: 'saved-1',
          name: 'Pine Meadow out and back',
          date: '2026-08-29',
          segments: [
            [
              { coord: [-74.095, 41.25], poiId: null },
              { coord: [-74.085, 41.25], poiId: null },
            ],
          ],
          figures: {
            miles: 7,
            legs: [
              {
                name: 'Pine Meadow Trail',
                source: 'oprhp_trails',
                blaze_color: 'blue',
                miles: 7,
              },
            ],
          },
          looped: false,
          recorded: 'planned',
        },
      ],
      openId: null,
    })

    render(<App />)
    await user.click(await screen.findByRole('tab', { name: 'Plan' }))

    // The home lists it - a saved day hike is enough to have a home at all.
    expect(await screen.findByText('Your day hikes')).toBeInTheDocument()
    await user.click(
      await screen.findByRole('button', { name: /Pine Meadow out and back/ }),
    )

    // The card, resolved against the live graph: real miles, and Seven Hills
    // as the marked way off at the junction - never the cache's 7 miles.
    const card = await screen.findByRole('dialog', {
      name: 'Pine Meadow out and back',
    })
    expect(await within(card).findByText(/0\.5 mi · 1 leg\b/)).toBeInTheDocument()
    expect(within(card).getByText('If you need to get off')).toBeInTheDocument()
    expect(within(card).getByText(/Seven Hills Trail \(white\)/)).toBeInTheDocument()
    expect(within(card).queryByText(/7\.0 mi/)).not.toBeInTheDocument()
    // The steward join reaches the card too - names, never raw keys.
    expect(within(card).getByText('NYS Parks')).toBeInTheDocument()
    expect(
      within(card).queryByText(/oprhp_trails|nynjtc_long_path/),
    ).not.toBeInTheDocument()

    // Delete takes two taps, and the row leaves the home with the record.
    await user.click(within(card).getByRole('button', { name: 'Delete this day hike' }))
    await user.click(within(card).getByRole('button', { name: 'Delete' }))
    await waitFor(() => {
      expect(
        screen.queryByRole('button', { name: /Pine Meadow out and back/ }),
      ).not.toBeInTheDocument()
    })
    const stored = app.store.get(DAY_HIKES_KEY) as { hikes: unknown[] }
    expect(stored.hikes).toHaveLength(0)
  })

  it('offers no day-hike button at all on a phone without the graph', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData()
    await serveGraph({ withGraph: false })

    await openDoor(user)

    // A sentence, not a dead control - and the other two doors still work.
    expect(screen.queryByRole('button', { name: /A day hike/ })).not.toBeInTheDocument()
    expect(screen.getByText(/hasn.{0,3}t got the trail network yet/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /A multi-day trip/ })).toBeInTheDocument()
  })
})
