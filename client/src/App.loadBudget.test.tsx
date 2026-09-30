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
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { get, getMany } from 'idb-keyval'
import App from './App'
import { appHarness, openMapTab, stubDesktop } from './test/appHarness'
import { renderedMap } from './test/liveMap'
import { MockMap } from './test/mocks/maplibre-gl'
import { loadMapEngine } from './map/mapEngineLoader'
import { POIS_KEY, TRAILS_BLOB_KEY } from './lib/trailData'
import { readLaunchMirror, writeLaunchMirror } from './lib/launchMirror'
import { PREFERENCES_KEY } from './lib/preferences'
import { HIKER_MODE_KEY } from './lib/hikerMode'
import { buildPoiIcons } from './map/poiIcons'
import { mileOnTrail } from './lib/trailPosition'
import { packPois, resolveTrailIndex } from './lib/trailIndexBuild'
import { searchableFrom } from './lib/searchPoi'
import { mapPointsFrom } from './lib/legendContents'
import { hikePlaces } from './lib/suggestedHikes'

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
// The engine seam, spied rather than replaced: every call goes through to the
// real loader (which the harness has already pointed at the mock library), and
// the count is what the two engine tests below are spelled in (#1560).
vi.mock('./map/mapEngineLoader', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./map/mapEngineLoader')>()
  return { ...actual, loadMapEngine: vi.fn(actual.loadMapEngine) }
})
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
  return {
    ...actual,
    resolveTrailIndex: vi.fn(actual.resolveTrailIndex),
    packPois: vi.fn(actual.packPois),
  }
})
vi.mock('./lib/trailPosition', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./lib/trailPosition')>()
  return { ...actual, mileOnTrail: vi.fn(actual.mileOnTrail) }
})
// The full passes over the waypoint list, wrapped rather than replaced, for
// the reason the two above are: the app runs the real ones and this file gets
// to ask how often. Since #1095 the list is 16,949 rows and each of these
// allocates a row per waypoint, so what makes them expensive is that they run
// at all.
vi.mock('./lib/searchPoi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./lib/searchPoi')>()
  return { ...actual, searchableFrom: vi.fn(actual.searchableFrom) }
})
vi.mock('./lib/legendContents', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./lib/legendContents')>()
  return { ...actual, mapPointsFrom: vi.fn(actual.mapPointsFrom) }
})
vi.mock('./lib/suggestedHikes', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./lib/suggestedHikes')>()
  return { ...actual, hikePlaces: vi.fn(actual.hikePlaces) }
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

/**
 * Every IndexedDB read hangs forever, for the tests that ask what is on screen
 * BEFORE the store has answered.
 *
 * The strong form of that question: a test that merely raced a fast mock would
 * pass against a tree that waits, which is the regression these are here to
 * catch. `getMany` follows whatever `get` is doing right now, so #1303's one
 * transaction in lib/trailData.ts reads this file's store like every other
 * read, and a caller that re-points `get` need not re-point both.
 */
function stallEveryRead(): void {
  vi.mocked(get).mockImplementation(() => new Promise(() => {}))
  vi.mocked(getMany).mockImplementation((keys) =>
    Promise.all(keys.map((key) => vi.mocked(get)(key))),
  )
}

/** A beat for anything that would land one commit later to land. The counting
 *  tests above use the same 50 ms, and the reason is the same: a frame sampled
 *  the tick a render finished cannot see what the next tick does. */
async function settle(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 50))
}

beforeEach(() => {
  vi.mocked(buildPoiIcons).mockClear()
  vi.mocked(resolveTrailIndex).mockClear()
  vi.mocked(mileOnTrail).mockClear()
  vi.mocked(searchableFrom).mockClear()
  vi.mocked(mapPointsFrom).mockClear()
  vi.mocked(hikePlaces).mockClear()
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
    await screen.findByText('A map that works where there is no signal.')

    // Waited on the line, because it is the read that comes first in the same
    // hook: a run where it has landed and the waypoints have not is the state
    // being asserted rather than a race with it.
    await waitFor(() => expect(readsOf(TRAILS_BLOB_KEY)).toBeGreaterThan(0))
    expect(readsOf(POIS_KEY)).toBe(0)
  })

  it('rasterises none of the 46 pin images', async () => {
    render(<App />)
    await screen.findByText('A map that works where there is no signal.')

    await waitFor(() => expect(readsOf(TRAILS_BLOB_KEY)).toBeGreaterThan(0))
    expect(buildPoiIcons).not.toHaveBeenCalled()
  })

  it('builds no map (#1324)', async () => {
    // The largest of the four operations this file's header prices, and the
    // one first run was still paying in full: 2,353 ms of blocking work on a
    // loaded phone here, 730-950 ms of MapLibre self time on the stopwatch's
    // cold first run against 659598a8 (three runs, 2026-09-09).
    //
    // It bought a backdrop nobody sees. `.onboarding__hero` is `inset: 0` over
    // an opaque `--bg-chrome`, so the map has stood behind a wall since #1054
    // - measured in pixels on the built app, where the map screen painted
    // magenta contributed 0 of the frame's 329,160 pixels. The map is built
    // when the steps are done instead (App.mapLifecycle).
    //
    // Anchored on the trail-line read like its neighbours above: it is the
    // read the map would have been waiting for, so a shell that wanted one
    // has had everything it needs by the time this asserts.
    render(<App />)
    await screen.findByText('A map that works where there is no signal.')

    await waitFor(() => expect(readsOf(TRAILS_BLOB_KEY)).toBeGreaterThan(0))
    expect(MockMap.instances).toHaveLength(0)
  })

  it('does not build the index or place a waypoint', async () => {
    // 12.2 MB of JSON.parse, 219,293 vertices and 16,949 placements, for a
    // mile axis nothing is showing: the waypoint cards, the search rows and
    // the ribbon are all behind the card.
    render(<App />)
    await screen.findByText('A map that works where there is no signal.')

    await waitFor(() => expect(readsOf(TRAILS_BLOB_KEY)).toBeGreaterThan(0))
    expect(resolveTrailIndex).not.toHaveBeenCalled()
    expect(mileOnTrail).not.toHaveBeenCalled()
  })
})

describe('what the launch mirror is allowed to say (#1301)', () => {
  it('does not write the defaults into the mirror when the record could not be read', async () => {
    // The read rejecting still opens the gate - a private-browsing failure
    // must not leave the app blank - and the state then holds the defaults.
    // Writing THOSE to the mirror would tell the next launch that a returning
    // hiker has not onboarded, and the first-run steps would be flashed at
    // somebody who finished them months ago, persistently, because the bad
    // mirror is what the next launch reads first.
    app.onboard({}, { mirror: false })
    // Only the two keys the bootstrap reads: a store that refuses everything
    // would be a different test, and would leave every other reader's
    // rejection unhandled in this one.
    const store = vi.mocked(get).getMockImplementation()!
    vi.mocked(get).mockImplementation((key) =>
      key === PREFERENCES_KEY || key === HIKER_MODE_KEY
        ? Promise.reject(new Error('no IndexedDB here'))
        : store(key),
    )

    render(<App />)
    // A phone whose record cannot be read looks like a first run, which is
    // the honest fallback and unchanged by #1301. What must NOT happen is
    // that reading it back becomes the next launch's answer.
    await screen.findByText('A map that works where there is no signal.')
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(readLaunchMirror()).toBeNull()
  })

  it('keeps a mode the hiker chose before the record came back', async () => {
    // The Today header's mode switch is ON the first frame now, so a tap can
    // land in the window before the record's read returns. Applying the
    // stored answer over it would undo a choice the hiker watched themselves
    // make - and the switch is the one control on this screen that changes
    // what the whole journal is ordered by.
    app.onboard()
    writeLaunchMirror({ onboarding_completed: true, theme: 'auto' }, 'day')
    app.store.set(HIKER_MODE_KEY, 'long')
    const store = vi.mocked(get).getMockImplementation()!
    let releaseMode: (() => void) | null = null
    vi.mocked(get).mockImplementation((key) =>
      key === HIKER_MODE_KEY
        ? new Promise((resolve) => {
            releaseMode = () => resolve(store(key))
          })
        : store(key),
    )
    const user = userEvent.setup()

    render(<App />)
    await user.click(await screen.findByRole('radio', { name: /volunteer/i }))
    await waitFor(() => expect(releaseMode).not.toBeNull())
    releaseMode!()
    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(screen.getByRole('radio', { name: /volunteer/i })).toHaveAttribute(
      'aria-checked',
      'true',
    )
  })

  it('writes the mirror once the record has actually answered', async () => {
    app.onboard({}, { mirror: false })

    render(<App />)

    await waitFor(() => expect(readLaunchMirror()?.onboardingCompleted).toBe(true))
  })
})

describe('how often a launch walks the waypoint list (#1303)', () => {
  // THE FOURTH BUDGET. The placement moved off this thread in #1192, and what
  // stayed was the walking: `searchablePois`, `viewportPoints`,
  // `hikePlaceOptions`, `passedPlacesToday`, `mileAnchors` and `packPois` each
  // allocated a row per waypoint - five or six full passes over 16,949 of them,
  // in render, before Today had drawn anything. Every pass that feeds something
  // NOT on screen is now conditional on that thing being on screen, so the
  // count is what the budget is spelled in.

  beforeEach(() => {
    app.onboard()
    app.putTrailData({ pois: POIS })
  })

  /** The release has been read and its miles placed - after which any further
   *  pass is one the shell chose to make. */
  async function releaseRead(): Promise<void> {
    await waitFor(() => expect(readsOf(POIS_KEY)).toBe(1))
    await indexLanded()
  }

  it('builds the map its points only once there is a map, which on Today is never', async () => {
    render(<App />)
    await screen.findByRole('tab', { name: 'Today' })
    await releaseRead()

    expect(mapPointsFrom).not.toHaveBeenCalled()
  })

  it('does not walk the list for the Find screen nobody has opened', async () => {
    render(<App />)
    await screen.findByRole('tab', { name: 'Today' })
    await releaseRead()

    expect(hikePlaces).not.toHaveBeenCalled()
  })

  it('walks the list once for what Today reads, and once more when the miles land', async () => {
    // Twice is the honest floor, not a target met by luck: the waypoints and
    // their miles arrive in two steps by design (lib/useTrailData.ts's
    // honest-unknown order), and the searchable view is what Today's journal,
    // the search rows and the ribbon all read.
    //
    // Counted over a NON-EMPTY list, because the call before the waypoints
    // have landed walks nothing and costs nothing - budgeting it would be
    // counting a `for` loop that runs zero times.
    render(<App />)
    await screen.findByRole('tab', { name: 'Today' })
    await releaseRead()
    await new Promise((resolve) => setTimeout(resolve, 50))

    const walks = vi.mocked(searchableFrom).mock.calls.filter(([pois]) => pois.length > 0)
    expect(walks.length).toBeLessThanOrEqual(2)
    expect(walks.length).toBeGreaterThan(0)
  })

  it('reads the whole release in one transaction rather than nine round trips', async () => {
    // Eight `await get(...)` calls in a row, each waiting for the last, on the
    // thread the launch is drawn on. The trail lines stay their own read
    // because they decide whether there is a release to read at all.
    render(<App />)
    await screen.findByRole('tab', { name: 'Today' })
    await releaseRead()

    expect(vi.mocked(getMany).mock.calls.length).toBeGreaterThan(0)
    expect(vi.mocked(getMany).mock.calls[0][0]).toContain(POIS_KEY)
  })

  it('packs the waypoints for the worker exactly once', async () => {
    render(<App />)
    await screen.findByRole('tab', { name: 'Today' })
    await releaseRead()

    expect(vi.mocked(packPois).mock.calls.length).toBeLessThanOrEqual(1)
  })
})

describe('what the shell paints before the phone has answered (#1301)', () => {
  it('puts the tab bar and the Today header on screen before any IndexedDB read has resolved', async () => {
    // THE THIRD BUDGET. The tree used to render nothing - not the tab bar, not
    // the Today header - until the preferences and a status for every archive
    // package had come back from IndexedDB, and re-blanked twice more as the
    // coverage cells arrived. Measured 2026-09-09 against production: first
    // content at 1,152-1,572 ms on the throttled profile, behind a blank page
    // painted at ~120 ms. The launch mirror (lib/launchMirror.ts) answers what
    // the first frame needs synchronously, so the shell paints from the first
    // commit and the store is asked afterwards.
    //
    // Proven the strong way: every IndexedDB read hangs forever, and the shell
    // is on screen anyway. A test that merely raced a fast mock would pass
    // against the old gate too.
    app.onboard()
    app.putTrailData({ pois: POIS })
    stallEveryRead()

    render(<App />)

    const today = await screen.findByRole('tab', { name: 'Today' })
    expect(today).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Map' })).toBeInTheDocument()
    expect(vi.mocked(get).mock.calls.length).toBeGreaterThan(0)
  })

  it('asks for the map engine zero times on a launch that stays on Today', async () => {
    // A laptop warms the engine at the first frame now (#1560, the desktop
    // block below), and this is the count that keeps #722's saving on a
    // phone: the engine is 860 ms of parse on the throttled profile, and a
    // launch that lands on Today and builds no map has no business fetching
    // it. The harness primes the loader before every test, so the count
    // starts at the render.
    app.onboard()
    app.putTrailData({ pois: POIS })
    vi.mocked(loadMapEngine).mockClear()

    render(<App />)
    await screen.findByRole('tab', { name: 'Today' })
    await settle()

    expect(loadMapEngine).not.toHaveBeenCalled()
    expect(MockMap.instances).toHaveLength(0)
  })

  it('still waits for the record on a phone that holds no mirror of it', async () => {
    // The first launch after #1301 shipped, or storage that was cleared: the
    // slow path, and the honest one - a returning hiker must never see the
    // first-run steps flash by, and without the mirror the record is the only
    // thing that says they are a returning hiker.
    app.onboard({}, { mirror: false })
    app.putTrailData({ pois: POIS })
    const original = vi.mocked(get).getMockImplementation()!
    const pending: Array<() => void> = []
    vi.mocked(get).mockImplementation(
      (key) =>
        new Promise((resolve) => {
          pending.push(() => resolve(original(key)))
        }),
    )

    render(<App />)
    await waitFor(() => expect(pending.length).toBeGreaterThan(0))
    expect(screen.queryByRole('tab', { name: 'Today' })).toBe(null)
    expect(screen.queryByText('A map that works where there is no signal.')).toBe(null)

    // The record lands: every held read answers, and later reads answer at once.
    vi.mocked(get).mockImplementation(original)
    for (const release of pending.splice(0)) release()
    await screen.findByRole('tab', { name: 'Today' })
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

    await screen.findByText('A map that works where there is no signal.')
    await user.click(screen.getByRole('button', { name: 'Get set up' }))

    // Past the mode card with nothing chosen, then the place card with no
    // place (#1373; the mode card is the review of #1374's).
    await user.click(screen.getByRole('button', { name: /^skip — day hike/i }))
    await user.click(screen.getByRole('button', { name: /^skip — i/i }))
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

describe('what a desktop launch paints before the store has answered', () => {
  // THE FIFTH BUDGET, and the form factor the other four do not cover.
  //
  // features/LAUNCH_BUDGET.md §6 excluded desktop in one sentence - "the
  // budget above is the phone's, and a desktop budget is not decided here" -
  // written on the reading that what a laptop pays extra for is the MAP, which
  // `isDesktop` mounts at launch by design. That reading is incomplete, and
  // this block is the incompleteness written down as counts.
  //
  // Today is not its own screen above the breakpoint. `App.tsx`'s Today branch
  // is guarded `activeTab === 'today' && !isDesktop`, and the journal is handed
  // to `MapScreen` as its `journal` prop instead - so on a laptop the front
  // door renders only once the map's own gate (`preferencesLoaded &&
  // archivesRead`) has opened AND MapScreen's deferred chunk has landed.
  // Excluding desktop from the budget therefore excluded Today from it, on the
  // one form factor where Today is behind the map.
  //
  // Measured 2026-09-15, cold cache, returning hiker with the 2026-09-14
  // release on the machine, Chromium at 1728x1080 against a LOCAL BUILD of
  // `main` carrying production's public build values, 4x CPU: the sidebar is
  // on screen at 212 ms and the journal has text at 2,230 ms. The whole
  // 2,018 ms between them is the frame the report that prompted this shows -
  // a sidebar and an empty pane. `archivesRead` is the last gate to open, at
  // 2,009 ms; MapScreen's chunk landed at 1,662 ms and the engine at 2,394 ms,
  // so on that run neither was on the journal's critical path. WHAT MAKES
  // `archivesRead` LATE IS NOT ESTABLISHED and is @unvalidated: the sweep is
  // one IndexedDB read per package and the package set grows to the coverage
  // cells (62 basemap + 681 network as published on 2026-09-15), but the same
  // window holds the release read and the index build, so "the sweep is slow"
  // and "the thread was busy" are not separated by anything measured. What
  // would settle it is a mark at the sweep's own first and last read.
  //
  // These are counts rather than milliseconds, like every other budget here.
  //
  // WHAT EACH TEST BELOW ASSERTS IS DESKTOP-ONLY, deliberately. A block that
  // passes with `stubDesktop()` removed is a block quietly testing the phone,
  // and the stub is a `matchMedia` fake keyed on lib/useDesktop.ts's query -
  // renaming that export or moving the breakpoint would disarm it in silence.
  // So each test names something the phone's own frame does not have.

  beforeEach(() => {
    stubDesktop()
    app.onboard()
    app.putTrailData({ pois: POIS })
  })

  it('puts the sidebar on screen before any IndexedDB read has resolved', async () => {
    // The half that already holds above the breakpoint, and must keep holding:
    // the launch mirror answers what the first frame needs synchronously, so
    // the spine paints from the first commit on a laptop exactly as the tab bar
    // does on a phone. Proven the strong way, like its phone twin - every read
    // hangs forever and the navigation is there anyway.
    stallEveryRead()

    render(<App />)

    const today = await screen.findByRole('tab', { name: 'Today' })
    expect(today).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Map' })).toBeInTheDocument()
    // The desktop-only half of the frame, and what stops this passing on a
    // phone. App.tsx hands TabBar a `modeSwitch` only above the breakpoint
    // (`isDesktop ? sidebarModeSwitch : undefined`), so the switch is IN THE
    // BAR here. Asking for the radiogroup unscoped would not say that: a phone
    // renders Today on this same frame and Today's own header carries an
    // identical one, so the unscoped query passes either way - checked by
    // running this block with `stubDesktop()` removed, where it stayed green
    // until the scope was added.
    const bar = screen.getByRole('tab', { name: 'Today' }).closest('.tab-bar')
    expect(bar).not.toBe(null)
    expect(
      within(bar as HTMLElement).getByRole('radiogroup', { name: "Today I'm" }),
    ).toBeInTheDocument()
    // And that the store really was asked, so "before any read has resolved"
    // cannot be vacuously true of a launch that stopped reading.
    expect(vi.mocked(get).mock.calls.length).toBeGreaterThan(0)
  })

  it('puts Today beside the sidebar before the store answers, and without a map', async () => {
    // THE INVERSION THIS TEST WAS BUILT FOR (#1429). It stood as
    // characterisation - "leaves the pane beside it empty until the store
    // answers, which is the defect" - and said in as many words that whoever
    // fixed the defect should invert it rather than delete it. This is that.
    //
    // What it now holds is the fix's whole claim: Today draws on a laptop
    // while the archive store is still being asked, because the wait belongs
    // to the map's background decision and Today does not participate in it.
    // Its phone twin above asserts the same thing for the phone's layout, so
    // the two layouts now make one promise instead of two.
    stallEveryRead()

    render(<App />)
    await screen.findByRole('tab', { name: 'Today' })
    // Sampled after a beat rather than on the frame the tab bar appeared, for
    // the reason the characterisation version needed it: a journal that only
    // arrives a commit later would satisfy an assertion taken immediately, and
    // "before the store answers" is a claim about the whole window.
    await settle()

    // Today is here, and the map it used to wait for is not - which is the
    // pairing that makes this the fix rather than a slower map. The store has
    // answered nothing: every read is still hanging.
    expect(document.querySelector('.today')).not.toBe(null)
    expect(screen.queryByRole('region', { name: /trail map/i })).toBe(null)
    expect(MockMap.instances).toHaveLength(0)
  })

  it('asks for the map engine before the store has answered', async () => {
    // THE SERIAL LINK #1560 REMOVED. MapView asks for the engine in its mount
    // effect, and MapView mounts only once the archive store has answered and
    // MapScreen's chunk has landed - so on a cold cache the engine's 257 KB
    // was fetched after both, measured 2026-09-17 at 1x CPU as the whole
    // 0.85 s between the map screen appearing and the canvas existing. A
    // laptop builds a map on every launch, so the fetch can start with the
    // first frame. Proven the strong way, like the two tests above: every
    // read hangs forever, and the engine has been asked for anyway - without
    // a map being built, because the store has said nothing.
    stallEveryRead()
    vi.mocked(loadMapEngine).mockClear()

    render(<App />)
    await screen.findByRole('tab', { name: 'Today' })

    await waitFor(() => expect(loadMapEngine).toHaveBeenCalled())
    expect(MockMap.instances).toHaveLength(0)
  })

  it('builds no more than one map for a launch that lands on Today', async () => {
    // What the §6 sentence DOES say, held: a laptop mounts the map at launch
    // deliberately, so one is allowed here where the phone's budget allows
    // none - which is also what proves `stubDesktop()` took effect, since the
    // phone's own launch onto Today builds zero (the block above).
    //
    // NOT a guard against the coverage cells rebuilding it. `mapKept` exists
    // for that, and this test cannot see it: readArchiveZooms and
    // readArchiveFootprint are mocked to null at the top of this file, so the
    // sweep never re-answers here and no growth is simulated. The bound is on
    // the launch, and App.mapLifecycle.test.tsx holds the growth case.
    render(<App />)
    await renderedMap()
    await indexLanded()
    await settle()

    expect(MockMap.instances).toHaveLength(1)
  })
})
