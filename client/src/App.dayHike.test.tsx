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
import { NETWORK_STILL_ARRIVING } from './lib/dayHikeDraft'
import { DAY_HIKES_KEY } from './lib/dayHikes'
import { TRAIL_GRAPH_GEOMETRY_KEY, TRAIL_GRAPH_KEY } from './lib/config'
import { TRIPS_KEY } from './lib/trips'
import { POI_ID_PROPERTY, POI_LAYER_ID } from './map/poiLayers'
import { appHarness, latOfMile, openMapTab } from './test/appHarness'
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
  // Needed by PoiCard -> useCommunityPhotos, which runs on mount. Left out,
  // a POI tap THREW: the trail tab's ErrorBoundary swallowed the whole
  // MapScreen subtree, and a test asserting the trailhead door was gone
  // passed because the map had gone with it. A vi.mock factory is a full
  // replacement, so an export missing here is missing at run time.
  fetchPoiPhotos: vi.fn(async () => []),
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

/**
 * A hike saved by an earlier session: ends mid-first-edge and mid-second-edge
 * of Pine Meadow, walking through the Seven Hills junction. The cached
 * figures are deliberately stale (7 miles) - a card that opens must
 * re-resolve against the live graph rather than print the cache
 * (lib/dayHikes.ts's provenance rule).
 */
const SAVED_HIKE = {
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

/**
 * Serve the graph pair (hashed) and 404 everything else the shell asks for.
 *
 * `withGeometry: false` is the phone that has the network's TOPOLOGY and not
 * its LINES (#1093) - a release that published one half, a hash that does not
 * match, or simply the seconds before the lazy fetch lands. It is a state the
 * builder has to be able to speak about, so it is a state this harness can
 * produce.
 */
async function serveGraph({ withGraph = true, withGeometry = true } = {}) {
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
        ? withGeometry
          ? GEOMETRY
          : null
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

/**
 * Tap, and wait for the geometry artifact rather than hoping it has landed.
 *
 * The graph arrives in two halves and only the routing one is fetched at
 * launch: `trail_graph_geometry.json` is asked for when the DOOR opens, and
 * until it lands `canSnapToGraph` is false and every tap comes back refused
 * with NETWORK_STILL_ARRIVING instead of routed (lib/dayHikeDraft.ts, #1093).
 * So a test that taps straight after opening the door is racing a fetch, and
 * `liveMap()` above does not settle it - it proves the click listener is
 * attached, which happens earlier.
 *
 * A refused tap adds NO point (`tapAt` returns the draft with a refusal on
 * it and the points untouched), so retrying is safe and idempotent. That is
 * what makes this a wait on an observable that proves the sequence completed,
 * which is the rule in CLAUDE.md this file's own header cites - and which the
 * date-across-the-map test below was relying on luck for. It passed until
 * #1117 moved the launch graph fetch one render later; the margin was always
 * this thin.
 *
 * THE OFF-NETWORK TEST BELOW SOLVES THE SAME RACE ITS OWN WAY, and keeps it:
 * that one waits until a tap answers with the off-network sentence
 * specifically, which is stronger there because the sentence IS its subject -
 * this helper would only prove the still-arriving one had stopped. The two
 * were written independently against the same defect, on this branch and on
 * main, and the merge kept the better one for each test rather than making
 * them agree for its own sake.
 */
const tapWhenRoutable = async (map: MockMap, lng: number, lat: number) => {
  await waitFor(async () => {
    await tap(map, lng, lat)
    expect(screen.queryByText(NETWORK_STILL_ARRIVING)).toBeNull()
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

  it('keeps a date set on the review card across a trip back to the map (#1008)', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData()
    await serveGraph()

    await openDoor(user)
    await user.click(await screen.findByRole('button', { name: /A day hike/ }))
    const map = await liveMap()
    await tapWhenRoutable(map, -74.095, 41.25)
    await tap(map, -74.085, 41.25)
    await user.click(await screen.findByRole('button', { name: 'Done' }))

    // Date it on the review card, then go back to look at the route again -
    // which is the only thing that button is for, since the map is frozen
    // while the card is up.
    const when = (await screen.findByLabelText('When')) as HTMLInputElement
    await user.type(when, '2026-09-12')
    await user.click(screen.getByRole('button', { name: 'Back to the map' }))
    expect(await screen.findByText(/Tap a trail to walk it/)).toBeInTheDocument()

    // Done rebuilds the record from the draft. The date has to survive that,
    // or it is lost silently - and it is the field the list, the split and
    // the trailhead door all read.
    await user.click(await screen.findByRole('button', { name: 'Done' }))
    await user.click(await screen.findByRole('button', { name: 'Save this day hike' }))

    await waitFor(() => {
      expect(app.store.get(DAY_HIKES_KEY)).toBeDefined()
    })
    const stored = app.store.get(DAY_HIKES_KEY) as {
      hikes: Array<{ date: string | null }>
    }
    expect(stored.hikes[0].date).toBe('2026-09-12')
  })

  it('refuses a tap off every maintained line, with the sentence', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData()
    await serveGraph()

    await openDoor(user)
    await user.click(await screen.findByRole('button', { name: /A day hike/ }))
    const map = await liveMap()

    // ~5 km north of anything routable - tapped until the graph can answer.
    //
    // `liveMap()` proves the canvas is up and listening, which is NOT the
    // same as the LINES having landed: until the geometry artifact is
    // applied, `canSnapToGraph` is false and every tap comes back
    // NETWORK_STILL_ARRIVING - the other sentence, and the one the test below
    // is about. Nothing in the DOM tells the two states apart before a tap
    // lands (the bar reads `empty` either way), so the wait is the app's own
    // instruction carried out: tap, and tap again while the answer is still
    // "try again in a moment".
    //
    // Safe to repeat precisely because a refusal leaves the points untouched
    // (lib/dayHikeDraft.ts), which is what the last assertion here checks.
    // Measured on a clean tree before this wait existed: 2 failures in 6 runs
    // of the file, 0 in 6 after (2026-08-27, this container).
    await waitFor(async () => {
      await tap(map, -74.095, 41.3)
      expect(screen.getByRole('alert')).toHaveTextContent(
        /only builds routes on trails an organization maintains/,
      )
    })
    // Placed nothing: still no route total on the bar.
    expect(screen.queryByText(/leg ·/)).not.toBeInTheDocument()
  })

  it('does not call a tap off-network when it is the LINES that have not arrived', async () => {
    // #1093, end to end. The routing artifact is on the phone and the
    // geometry one is not, which is every phone for the first seconds after
    // this door opens. A tap dead on Pine Meadow cannot be answered - and the
    // sentence must not be the one that says the hiker aimed wrong, because
    // they did not.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData()
    await serveGraph({ withGeometry: false })

    await openDoor(user)
    await user.click(await screen.findByRole('button', { name: /A day hike/ }))
    const map = await liveMap()

    await tap(map, -74.095, 41.25)

    const said = await screen.findByRole('alert')
    expect(said).toHaveTextContent(/hasn.t got this area.s trail lines/)
    expect(said).not.toHaveTextContent(/isn.t on a marked hiking route/)
    // And placed nothing, which is the half that was never in doubt.
    expect(screen.queryByText(/leg ·/)).not.toBeInTheDocument()
  })

  it('does not restart the geometry fetch every time the hiker taps', async () => {
    // The other half of #1093. `tapAt` returns a NEW draft on every tap, a
    // refused one included, and the effect that fetches the geometry used to
    // carry the draft in its dependency list - so each tap aborted the
    // in-flight request and started it again. The taps that most need the
    // artifact are the refused ones, which is what makes somebody tap again.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData()
    const requested = await serveGraph({ withGeometry: false })

    await openDoor(user)
    await user.click(await screen.findByRole('button', { name: /A day hike/ }))
    const map = await liveMap()

    const asked = () =>
      requested.filter((url) => url.includes(TRAIL_GRAPH_GEOMETRY_KEY)).length
    await waitFor(() => {
      expect(asked()).toBe(1)
    })

    await tap(map, -74.095, 41.25)
    await tap(map, -74.085, 41.25)
    await tap(map, -74.09, 41.255)

    expect(asked()).toBe(1)
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

    app.store.set(DAY_HIKES_KEY, { hikes: [SAVED_HIKE], openId: null })

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
    // No organization on the rows since #1112, in either spelling - not the
    // steward join's name and not the raw key it falls back to. The card
    // still credits by count, and screens/DayHikeCard.test.tsx holds that.
    expect(within(card).queryByText('NYS Parks')).not.toBeInTheDocument()
    expect(
      within(card).queryByText(/oprhp_trails|nynjtc_long_path/),
    ).not.toBeInTheDocument()

    // Switching rooms puts the card away (#1008): a day-hike surface left
    // floating over the trips room is the mode confusion the split exists
    // to end, and switching rooms is navigation.
    await user.click(screen.getByRole('button', { name: /Trips/ }))
    await waitFor(() => {
      expect(
        screen.queryByRole('dialog', { name: 'Pine Meadow out and back' }),
      ).not.toBeInTheDocument()
    })
    expect(screen.getByRole('heading', { name: 'Trips' })).toBeInTheDocument()

    // Back to the day room, and the row is still there to reopen.
    await user.click(screen.getByRole('button', { name: /Day hikes/ }))
    await user.click(
      await screen.findByRole('button', { name: /Pine Meadow out and back/ }),
    )
    const reopened = await screen.findByRole('dialog', {
      name: 'Pine Meadow out and back',
    })

    // Delete takes two taps, and the row leaves the home with the record.
    await user.click(
      within(reopened).getByRole('button', { name: 'Delete this day hike' }),
    )
    await user.click(within(reopened).getByRole('button', { name: 'Delete' }))
    await waitFor(() => {
      expect(
        screen.queryByRole('button', { name: /Pine Meadow out and back/ }),
      ).not.toBeInTheDocument()
    })
    const stored = app.store.get(DAY_HIKES_KEY) as { hikes: unknown[] }
    expect(stored.hikes).toHaveLength(0)
  })

  it('opens a saved hike’s card from the Today tab, where the shelf also lives', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData()
    app.store.set('ourhike:stewards', STEWARDS)
    await serveGraph()
    app.store.set(DAY_HIKES_KEY, { hikes: [SAVED_HIKE], openId: null })

    // No tab click: Today is the tab the app opens on, and the shelf is on
    // it - the row a hiker meets first is the one this test taps.
    render(<App />)
    expect(await screen.findByText('Your day hikes')).toBeInTheDocument()
    await user.click(
      await screen.findByRole('button', { name: /Pine Meadow out and back/ }),
    )

    // The same card the Plan home opens, resolved against the live graph -
    // the row promised details, and details are what a tap has to produce.
    const card = await screen.findByRole('dialog', {
      name: 'Pine Meadow out and back',
    })
    expect(await within(card).findByText(/0\.5 mi · 1 leg\b/)).toBeInTheDocument()
    expect(within(card).getByText('If you need to get off')).toBeInTheDocument()
    expect(within(card).queryByText(/7\.0 mi/)).not.toBeInTheDocument()

    // And the tab bar is still underneath it: the card is a sheet over the
    // journal, not a screen that replaces it.
    expect(screen.getByRole('tab', { name: 'Today' })).toBeInTheDocument()

    // Closing puts the pointer away rather than leaving it set - a stored
    // openId nothing renders is how this bug looked from the store.
    await user.click(within(card).getByRole('button', { name: 'Close the day hike' }))
    await waitFor(() => {
      expect(
        screen.queryByRole('dialog', { name: 'Pine Meadow out and back' }),
      ).not.toBeInTheDocument()
    })
    expect((app.store.get(DAY_HIKES_KEY) as { openId: string | null }).openId).toBeNull()
  })

  it('opens it in the journal column when Today reads beside the map (#1054)', async () => {
    // The desktop's Today: the shell stands the Today branch aside and docks
    // the journal into MapScreen, so the phone's fix reaches none of it. The
    // shelf is the same shelf and the tap has to land the same way.
    //
    // Matched on the query rather than answering true to everything, for
    // App.test.tsx's reason: this shell also asks matchMedia whether it is
    // standalone and whether the pointer is fine.
    vi.stubGlobal(
      'matchMedia',
      vi.fn((query: string) => ({
        matches: query.includes('min-width: 900px'),
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
      })),
    )
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData()
    app.store.set('ourhike:stewards', STEWARDS)
    await serveGraph()
    app.store.set(DAY_HIKES_KEY, { hikes: [SAVED_HIKE], openId: null })

    render(<App />)
    await user.click(
      await screen.findByRole('button', { name: /Pine Meadow out and back/ }),
    )

    const card = await screen.findByRole('dialog', {
      name: 'Pine Meadow out and back',
    })
    expect(await within(card).findByText(/0\.5 mi · 1 leg\b/)).toBeInTheDocument()

    // In the column the row was tapped in, not over the map beside it: the
    // map's own sheet slot belongs to the builders and the trailhead door,
    // and desktop.css anchors this column so `bottom: 0` is its own edge.
    expect(card.closest('.map-screen__journal')).not.toBeNull()
  })

  it('closes the day hike when a route-builder door opens over it (#997)', async () => {
    // THE ASYMMETRY THAT SHIPPED. `openDayHike` always cleared the route
    // draft; nothing cleared the day hike. Both surfaces the two modes share
    // - the map tap and `routeSheet` - answer for the day hike first, so a
    // route builder opened on top of one held a live draft that nobody could
    // see or reach, and cancelling the day hike revealed a route the hiker
    // did not remember starting.
    //
    // Driven through the GAP DOOR rather than the Plan tab's primary action,
    // because the primary action was never the bug: `openPlanKind` guards on
    // `dayHike !== null` and sends the hiker back to their day hike. The
    // timeline's own doors call `openRouteBuilderFrom` directly, and the tab
    // bar reaches the timeline whatever is open.
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData({
      pois: [
        {
          id: 's10',
          type: 'shelter',
          name: 'Middle Shelter',
          lat: latOfMile(10),
          lon: -77,
          confidence: 'high',
          mile: 10.2,
        },
        {
          id: 's22',
          type: 'shelter',
          name: 'Beyond Shelter',
          lat: latOfMile(22),
          lon: -77,
          confidence: 'high',
          mile: 22.2,
        },
      ],
    })
    app.store.set('ourhike:stewards', STEWARDS)
    // A walked trip with ground past it, so the timeline offers a gap.
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
    await serveGraph()

    const openHike = async () => {
      await user.click(await screen.findByRole('tab', { name: 'Plan' }))
      await user.click(
        await screen.findByRole('button', { name: /The whole thing, eventually/ }),
      )
    }

    render(<App />)
    await openHike()
    // Into a day hike, with points on it - the work that used to be silently
    // outlived by an invisible route draft. Since #1008 the way in from here
    // is the day room's own action: home, the switch chip, then "Plan a day
    // hike" - the same guarded door (openDayHike), which lands the hiker on
    // the trail tab itself.
    await user.click(await screen.findByRole('button', { name: /All your plans/ }))
    await user.click(await screen.findByRole('button', { name: /Day hikes/ }))
    await user.click(await screen.findByRole('button', { name: 'Plan a day hike' }))
    const map = await liveMap()
    await tap(map, -74.095, 41.25)
    await tap(map, -74.085, 41.25)
    expect(await screen.findByText(/1 leg ·/)).toBeInTheDocument()

    // Back to the timeline - the tab bar consults neither builder. The Plan
    // tab reopens on the day room (the hiker's last pick sticks, #1008), so
    // the way to the hike is the chip back to the trips room - and then in
    // through the gap door, which calls openRouteBuilderFrom directly.
    await user.click(await screen.findByRole('tab', { name: 'Plan' }))
    await user.click(await screen.findByRole('button', { name: /Trips/ }))
    await user.click(
      await screen.findByRole('button', { name: /The whole thing, eventually/ }),
    )
    await user.click(await screen.findByRole('button', { name: 'Plan this stretch' }))

    // THE FIRST ASSERTION IS THE ONE THAT CATCHES IT, verified by reverting
    // the fix: `routeSheet` renders the day-hike bar OR the builder, never
    // both, so with the day hike still live the draft exists in state and
    // this dialog is simply not in the document. The two below are the
    // complement - they prove the day hike was closed, rather than the
    // builder having won some race for the same slot.
    expect(
      await screen.findByRole('dialog', { name: 'Plan a route' }),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Tap a trail to walk it/)).not.toBeInTheDocument()
    expect(screen.queryByText(/1 leg ·/)).not.toBeInTheDocument()
  })

  it('offers a saved hike from the map when the fix lands at its start (#1008)', async () => {
    const user = userEvent.setup()
    // The location step taken, so the watch this door reads actually runs -
    // with it declined there is no fix and, correctly, no door at all.
    app.onboard({ location_permission_requested: true })
    app.putTrailData()
    await serveGraph()

    // Two saved hikes starting at two different trailheads - which is what
    // makes the dismissal's specificity testable at all.
    const startsAtMile = (id: string, name: string, mile: number) => ({
      id,
      name,
      date: null,
      segments: [
        [
          { coord: [-77, latOfMile(mile)], poiId: null },
          { coord: [-77, latOfMile(mile + 1)], poiId: null },
        ],
      ],
      figures: { miles: 1, legs: [] },
      looped: false,
      recorded: 'planned' as const,
    })
    app.store.set(DAY_HIKES_KEY, {
      hikes: [
        startsAtMile('near-1', 'Reeves Meadow loop', 5),
        startsAtMile('near-2', 'Claudius Smith Den', 20),
      ],
      openId: null,
    })

    render(<App />)
    await openMapTab()
    // No door before a fix: the map cannot know where anybody parked.
    expect(
      screen.queryByRole('button', { name: /day hikes? starts? here/ }),
    ).not.toBeInTheDocument()

    await app.reportFixAtMile(5)

    // Closed first - one pill, never a sheet that opens itself over the map -
    // and only the hike whose start is actually here.
    await user.click(
      await screen.findByRole('button', { name: 'A day hike starts here' }),
    )
    expect(await screen.findByText('Reeves Meadow loop')).toBeInTheDocument()
    expect(screen.queryByText('Claudius Smith Den')).not.toBeInTheDocument()

    // "No thanks" is about the hike it was offering, not about the door for
    // ever.
    await user.click(screen.getByRole('button', { name: 'Put this away' }))
    await waitFor(() => {
      expect(
        screen.queryByRole('button', { name: /day hikes? starts? here/ }),
      ).not.toBeInTheDocument()
    })

    // Drive to the other trailhead in the same session: the hike nobody said
    // no to still gets to ask. A plain dismissed-boolean would stay silent
    // here, which is the defect this shape exists to prevent.
    await app.reportFixAtMile(20)
    await user.click(
      await screen.findByRole('button', { name: 'A day hike starts here' }),
    )
    expect(await screen.findByText('Claudius Smith Den')).toBeInTheDocument()
  })

  it('yields the map’s lower third to anything the hiker actually tapped (#1008)', async () => {
    app.onboard({ location_permission_requested: true })
    // A waypoint to tap: the door is the only occupant of that space nobody
    // asked for, and it is the last child of the canvas - so equal z-index
    // would let it win on DOM order over a card that answers a tap.
    app.putTrailData({
      pois: [
        {
          id: 'poi-1',
          name: 'Reeves Meadow Shelter',
          type: 'shelter',
          lat: latOfMile(5),
          lon: -77,
          confidence: 'high',
          mile: 5,
        },
      ],
    })
    await serveGraph()

    app.store.set(DAY_HIKES_KEY, {
      hikes: [
        {
          id: 'near-1',
          name: 'Reeves Meadow loop',
          date: null,
          segments: [
            [
              { coord: [-77, latOfMile(5)], poiId: null },
              { coord: [-77, latOfMile(6)], poiId: null },
            ],
          ],
          figures: { miles: 1, legs: [] },
          looped: false,
          recorded: 'planned',
        },
      ],
      openId: null,
    })

    render(<App />)
    await openMapTab()
    await app.reportFixAtMile(5)
    expect(
      await screen.findByRole('button', { name: 'A day hike starts here' }),
    ).toBeInTheDocument()

    // Tap the pin: the card is what was asked for, so the door stands down.
    // The mock answers queryRenderedFeatures from what a test says is drawn,
    // which is App.flows.test.tsx's own idiom for reaching a waypoint.
    const map = await liveMap()
    map.renderedFeatures.set(POI_LAYER_ID, [
      { properties: { [POI_ID_PROPERTY]: 'poi-1' } },
    ])
    await act(async () => {
      map.emit('click', { point: { x: 160, y: 300 } })
    })
    // BOTH HALVES, and the positive one is the load-bearing half. "The door
    // is gone" alone is true of the failure this test exists to catch as
    // well as of the behaviour it wants: a tap that opens nothing and takes
    // the door with it looks identical from here. Asserting the card is up
    // is what separates "yielded" from "both gone".
    expect(await screen.findByText('Reeves Meadow Shelter')).toBeInTheDocument()
    await waitFor(() => {
      expect(
        screen.queryByRole('button', { name: 'A day hike starts here' }),
      ).not.toBeInTheDocument()
    })
  })

  it('offers no day-hike button at all on a phone without the graph', async () => {
    const user = userEvent.setup()
    app.onboard()
    app.putTrailData()
    await serveGraph({ withGraph: false })

    await openDoor(user)

    // A sentence, not a dead control - and the other two doors still work.
    expect(screen.queryByRole('button', { name: /A day hike/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /A multi-day trip/ })).toBeInTheDocument()

    // AND THE SENTENCE IS THE TRUE ONE (#1049). `withGraph: false` serves a
    // 404, which is exactly what production serves today (#1048) - so this is
    // the end-to-end proof of the bug a hiker reported: the door used to tell
    // them to wait for a data sync that was never coming.
    expect(screen.getByText(/does not include the trail network/i)).toBeInTheDocument()
    expect(screen.queryByText(/data sync/i)).not.toBeInTheDocument()
  })
})
