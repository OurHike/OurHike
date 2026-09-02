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
// THE SECOND BUDGET (#1192) is the returning hiker's, and it is the one this
// file did not have when it was written. Once the release is read, the shell
// used to place every stored waypoint on the index in one memo on the launch
// thread - 16,949 of them after #1095, measured 2026-09-02 at 13,078 ms in one
// task on the throttled profile, with a tab tap waiting 14,557 ms behind it.
// That placement now happens where the index is built (lib/trailIndexBuild.ts,
// off the thread where there is a worker), so the rule here is: after the
// index has landed, the launch thread runs the nearest-vertex search for
// NOTHING - not one waypoint. A GPS fix is the only thing that may ask it,
// and this file delivers none.
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
import { appHarness, openMapTab } from './test/appHarness'
import { renderedMap } from './test/liveMap'
import { POIS_KEY, TRAILS_BLOB_KEY } from './lib/trailData'
import { buildPoiIcons } from './map/poiIcons'
import { mileOnTrail } from './lib/trailPosition'
import { resolveTrailIndex } from './lib/trailIndexBuild'

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
// The index build as the shell asks for it - one call per release read, and
// the only thing that may run the per-waypoint search - and the search itself,
// counted so the launch thread can be shown to run it for nothing.
vi.mock('./lib/trailIndexBuild', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./lib/trailIndexBuild')>()
  return { ...actual, resolveTrailIndex: vi.fn(actual.resolveTrailIndex) }
})
vi.mock('./lib/trailPosition', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./lib/trailPosition')>()
  return { ...actual, mileOnTrail: vi.fn(actual.mileOnTrail) }
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
  vi.mocked(resolveTrailIndex).mockClear()
  vi.mocked(mileOnTrail).mockClear()
})

/** The index the launch asked for has been handed back - the moment after
 *  which any search on this thread is the shell's own doing. */
async function indexLanded(): Promise<void> {
  await waitFor(() => expect(resolveTrailIndex).toHaveBeenCalledTimes(1))
  await vi.mocked(resolveTrailIndex).mock.results[0].value
}

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

  it('does not build the index or place a waypoint', async () => {
    // 12.2 MB of JSON.parse, 219,293 vertices and 16,949 placements, for a
    // mile axis nothing is showing: the waypoint cards, the search rows and
    // the ribbon are all behind the card.
    render(<App />)
    await screen.findByText('What OurHike is')

    await waitFor(() => expect(readsOf(TRAILS_BLOB_KEY)).toBeGreaterThan(0))
    expect(resolveTrailIndex).not.toHaveBeenCalled()
    expect(mileOnTrail).not.toHaveBeenCalled()
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
    // Declined, deliberately: this file counts what a LAUNCH costs, and
    // "Keep going" would start the download machinery on top of it (#1054).
    await user.click(screen.getByRole('button', { name: 'Decide this later' }))
    await user.click(screen.getByRole('button', { name: /not now/i }))
    await openMapTab()
    await renderedMap()

    await waitFor(() => expect(readsOf(POIS_KEY)).toBe(1))
    await waitFor(() => expect(resolveTrailIndex).toHaveBeenCalledTimes(1))
  })

  it('reads and indexes the release once for a hiker who is past onboarding', async () => {
    // The ordinary launch, every day after the first. Nothing here is deferred
    // - the map screen is the first thing on screen and wants all of it - so
    // the budget is that each expensive thing happens exactly once.
    app.onboard()
    app.putTrailData({ pois: POIS })
    render(<App />)
    await openMapTab()

    await renderedMap()

    await waitFor(() => expect(readsOf(POIS_KEY)).toBe(1))
    await indexLanded()
    expect(vi.mocked(resolveTrailIndex).mock.calls.length).toBe(1)
  })

  it('places no waypoint on the launch thread once the index has landed', async () => {
    // The #1192 budget. Every placement the launch needs is answered inside
    // resolveTrailIndex - off this thread on a phone, in slices here, where
    // jsdom has no Worker - so the count of searches AFTER it returns is the
    // count the shell ran on its own. It has to be zero: there is no GPS fix
    // in this test, and nothing else on a launch has a reason to ask.
    app.onboard()
    app.putTrailData({ pois: POIS })
    render(<App />)
    await openMapTab()
    await renderedMap()
    await indexLanded()
    const insideTheBuild = vi.mocked(mileOnTrail).mock.calls.length

    // The search rows are what the placement feeds, so their appearance is
    // the index having landed in the shell - the moment a memo that placed
    // waypoints here would have run.
    await screen.findByRole('tab', { name: 'Map' })
    await waitFor(() => expect(readsOf(POIS_KEY)).toBe(1))
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(vi.mocked(mileOnTrail).mock.calls.length).toBe(insideTheBuild)
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
    await openMapTab()
    await renderedMap()

    await user.click(await screen.findByRole('tab', { name: /more/i }))
    await user.click(await screen.findByRole('tab', { name: /^map$/i }))
    await renderedMap()

    expect(vi.mocked(buildPoiIcons).mock.calls.length).toBeLessThanOrEqual(1)
  })
})
