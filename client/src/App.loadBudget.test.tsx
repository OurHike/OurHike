// What a launch is allowed to DO before a hiker can use the screen.
//
// WHY THIS FILE COUNTS WORK RATHER THAN MILLISECONDS
//
// The bug that prompted it (#857) was reported as a feeling - "when I hit skip
// on the first 3 screens there is some serious lag. A lot of times it feels
// like that button is broken" - and it was real: measured in Chromium at
// 390x844 on a 4x CPU throttle, replaying first run with a release already
// downloaded, 5,479 ms of blocking work ran while the entry steps were up, in
// 22 long tasks, the longest of them 2,374 ms.
//
// None of that is measurable here, and pretending otherwise would be worse
// than not trying. jsdom has no compositor, no WebGL, no tile worker and no
// paint, `maplibre-gl` is mocked outright (TESTING.md §19), and a CI runner's
// milliseconds are not a phone's - a timing assertion tuned on one machine is
// the flaky test CLAUDE.md warns about, green when it is pushed and red on
// somebody else's merge commit.
//
// What IS measurable, exactly and deterministically, is how much work the
// launch asks for. Every millisecond in that measurement came from one of four
// operations, each of them countable:
//
//   rasterising the 46 pin images     2,521 ms   map/poiIcons.ts
//   MapLibre, once it has the data    2,353 ms   (one map, built once)
//   parsing 12.2 MB of trail lines      149 ms   lib/useTrailData.ts
//   indexing 219,293 vertices            74 ms   lib/trailPosition.ts
//   deserialising 2,837 POIs              82 ms   idb-keyval
//
// So the budget is spelled in calls: which of those a screen may perform
// before it is on screen, and how many times. A regression that puts the work
// back fails here loudly, on a machine of any speed, whatever the clock says.
//
// THE STOPWATCH LIVES SOMEWHERE ELSE, and it is not a gate.
// `client/scripts/measure-first-run.mjs` drives a real throttled Chromium
// against a real deployment - a pull request's preview URL, or production -
// and prints long tasks, total blocking time and the latency of each tap on
// Skip. That is where a number in milliseconds can be honest. See TESTING.md.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { get } from 'idb-keyval'
import App from './App'
import { appHarness } from './test/appHarness'
import { renderedMap } from './test/liveMap'
import { POIS_KEY, TRAILS_BLOB_KEY } from './lib/trailData'
import { buildPoiIcons } from './map/poiIcons'
import { buildTrailIndex } from './lib/trailPosition'

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./map/archiveZooms', () => ({ readArchiveZooms: () => Promise.resolve(null) }))

// The two expensive pure functions, wrapped rather than replaced: the app runs
// the real ones, and this file gets to ask how often. Counting the call is the
// whole point - what makes them expensive is that they run at all, and their
// cost does not depend on anything a test could vary.
vi.mock('./map/poiIcons', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./map/poiIcons')>()
  return { ...actual, buildPoiIcons: vi.fn(actual.buildPoiIcons) }
})
vi.mock('./lib/trailPosition', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./lib/trailPosition')>()
  return { ...actual, buildTrailIndex: vi.fn(actual.buildTrailIndex) }
})

const app = appHarness()

/** One water source, which is all it takes: the question is whether the
 *  waypoints are read at all, not how many there are. */
const POIS = [
  {
    id: 'atc_water:1',
    type: 'water',
    name: 'Big Spring',
    lat: 39.3,
    lon: -77.1,
    confidence: 'high' as const,
  },
]

/** How many times a key was read out of the phone this launch. */
function readsOf(key: string): number {
  return vi.mocked(get).mock.calls.filter(([asked]) => asked === key).length
}

beforeEach(() => {
  vi.mocked(buildPoiIcons).mockClear()
  vi.mocked(buildTrailIndex).mockClear()
})

describe('what first run may do before the steps are done', () => {
  // The expensive launch, and the ordinary one for anyone looking at
  // onboarding twice: everything is already on the phone, so every read that
  // is going to happen happens while the steps are up rather than several
  // seconds later behind a download.
  beforeEach(() => {
    app.putTrailData({ pois: POIS })
  })

  it('reads the trail line, and does not read the waypoints', async () => {
    render(<App />)
    await screen.findByText('What OurHike is')

    // Waited on the line, because it is the read that comes first in the same
    // hook: a run where it has landed and the waypoints have not is the state
    // being asserted rather than a race with it.
    await waitFor(() => expect(readsOf(TRAILS_BLOB_KEY)).toBeGreaterThan(0))
    expect(readsOf(POIS_KEY)).toBe(0)
  })

  it('rasterises none of the 46 pin images', async () => {
    render(<App />)
    await screen.findByText('What OurHike is')

    await waitFor(() => expect(readsOf(TRAILS_BLOB_KEY)).toBeGreaterThan(0))
    expect(buildPoiIcons).not.toHaveBeenCalled()
  })

  it('does not parse the trail lines to index them', async () => {
    // 12.2 MB of JSON.parse and 219,293 vertices, for a mile axis nothing is
    // showing: the waypoint cards, the search rows and the ribbon are all
    // behind the card.
    render(<App />)
    await screen.findByText('What OurHike is')

    await waitFor(() => expect(readsOf(TRAILS_BLOB_KEY)).toBeGreaterThan(0))
    expect(buildTrailIndex).not.toHaveBeenCalled()
  })
})

describe('what a launch does once, and must not do twice', () => {
  it('reads the waypoints once when the steps release them', async () => {
    // Held, not dropped - and held ONCE. An effect that re-ran on every render
    // would deserialise 2,837 POIs and re-index 219,293 vertices repeatedly,
    // which is the same bill as before with extra steps.
    app.putTrailData({ pois: POIS })
    const user = userEvent.setup()
    render(<App />)

    await screen.findByText('What OurHike is')
    await user.click(screen.getByRole('button', { name: 'Continue' }))
    await user.click(screen.getByRole('button', { name: 'Continue' }))
    await user.click(screen.getByRole('button', { name: /not now/i }))
    await renderedMap()

    await waitFor(() => expect(readsOf(POIS_KEY)).toBe(1))
    await waitFor(() => expect(buildTrailIndex).toHaveBeenCalledTimes(1))
  })

  it('reads and indexes the release once for a hiker who is past onboarding', async () => {
    // The ordinary launch, every day after the first. Nothing here is deferred
    // - the map screen is the first thing on screen and wants all of it - so
    // the budget is that each expensive thing happens exactly once.
    app.onboard()
    app.putTrailData({ pois: POIS })
    render(<App />)

    await renderedMap()

    await waitFor(() => expect(readsOf(POIS_KEY)).toBe(1))
    expect(vi.mocked(buildTrailIndex).mock.calls.length).toBe(1)
  })

  it('rasterises the pin artwork at most once, however many maps are built', async () => {
    // Every trip to the More tab and back builds a new map, and each one asks
    // for the images. They are the same 46 whatever asks, so the answer is
    // cached - on the main thread by `buildPoiIcons`, and one thread out by
    // map/poiIconImages.ts, which is where this actually runs in a browser.
    app.onboard()
    app.putTrailData({ pois: POIS })
    const user = userEvent.setup()
    render(<App />)
    await renderedMap()

    await user.click(await screen.findByRole('tab', { name: /settings/i }))
    await user.click(await screen.findByRole('tab', { name: /^trail$/i }))
    await renderedMap()

    expect(vi.mocked(buildPoiIcons).mock.calls.length).toBeLessThanOrEqual(1)
  })
})
