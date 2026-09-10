// What a cold start costs, counted in maps.
//
// Opening the app used to build the map THREE times on a phone that had been
// used before, and it looked exactly like what it was: the map appeared,
// blinked out, came back on a different background, blinked out again, and
// re-framed itself on the whole corridor. Twice over, in the second or two
// after launch, on the screen this app is mostly for.
//
// Nothing was wrong with any single piece. Three facts about the phone are
// read from IndexedDB at launch and land on their own schedules - the stored
// preferences, whether an archive is in the download store, and the trail lines
// themselves - and each one fed a prop that MapView rebuilt the whole map for.
// A map built three times is three WebGL contexts, three sets of tile reads
// against an archive that can be 1.18 GB, and three camera resets.
//
// So these tests hold the phone's reads open and land them one at a time,
// asserting on the count of maps ever CONSTRUCTED rather than on what is on
// screen at the end. Both the broken and the fixed version end up showing the
// same map; the difference is entirely in what it cost to get there, which is
// visible in `MockMap.instances` and nowhere else.
//
// Deliberately NOT timing-dependent. Every read is a promise this file resolves
// by hand, so what is asserted is that the count holds whatever order the phone
// answers in - not that it holds on a machine as fast as the one that ran it
// last.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { get, getMany } from 'idb-keyval'
import App from './App'
import { MockMap } from './test/mocks/maplibre-gl'
import { appHarness, openMapTab } from './test/appHarness'
import { PREFERENCES_KEY } from './lib/preferences'
import { HIKER_MODE_KEY } from './lib/hikerMode'
import { OPEN_WALK_KEY } from './lib/openWalk'
import { POIS_KEY, TRAILS_BLOB_KEY } from './lib/trailData'
import {
  CORRIDOR_BACKGROUND_PACKAGE,
  offeredPackages,
  offeredSheets,
  withdrawnSheets,
} from './lib/packages'
import { POI_SOURCE_ID } from './map/poiLayers'
import { buildPoiIcons } from './map/poiIcons'
import { TRAILS_SOURCE_ID } from './map/style'
import { OSM_SOURCE_ID } from './map/liveTopo'

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  getMany: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./map/archiveZooms', () => ({
  readArchiveZooms: () => Promise.resolve({ minZoom: 5, maxZoom: 14 }),
  readArchiveFootprint: () => Promise.resolve(null),
}))

const app = appHarness()
const store = app.store

/**
 * Every read the app has asked for and not yet been given an answer to.
 *
 * The whole point of the file. A `Promise.resolve()` mock answers within the
 * same commit that asked, which collapses the launch sequence into one render
 * and hides the very staggering these tests are about - the bug is invisible
 * against a mock that is faster than React.
 *
 * This is the one file that replaces the harness's `get`, rather than seeding
 * through it: what it is testing is the ORDER reads land in, which a mock that
 * answers immediately cannot express.
 */
let pending: Array<{ key: string; release: () => void }> = []

beforeEach(() => {
  pending = []
  vi.mocked(get).mockImplementation(
    (key) =>
      new Promise((resolve) => {
        pending.push({
          key: String(key),
          release: () => resolve(store.get(key as string)),
        })
      }),
  )
  // `getMany` follows whatever `get` is doing right now, so #1303's one
  // transaction in lib/trailData.ts reads this file's store like every other
  // read, and a test that re-points `get` need not re-point both.
  vi.mocked(getMany).mockImplementation((keys) =>
    Promise.all(keys.map((key) => vi.mocked(get)(key))),
  )
})

afterEach(() => vi.restoreAllMocks())

/**
 * Answers every outstanding read whose key matches, and lets React finish with
 * the result before returning.
 *
 * The drain is a real macrotask rather than a fixed number of microtask turns,
 * because the readers chain several awaits before they set any state - the
 * trail-data path reads four keys and then parses a blob. Anything counted in
 * ticks would be a guess about someone else's implementation.
 */
async function land(matches: (key: string) => boolean): Promise<void> {
  // Repeated, because answering a read is how the next one gets asked: a
  // package with no finished blob goes on to look for a partial under a second
  // key. Landing "the archive store" has to mean all of that, or the shell is
  // left waiting on a read this helper started and abandoned. Bounded rather
  // than `while`, so a read that re-queues itself fails the test instead of
  // hanging the suite.
  for (let round = 0; round < 8; round += 1) {
    const matched = pending.filter((read) => matches(read.key))
    if (matched.length === 0) return
    pending = pending.filter((read) => !matches(read.key))

    await act(async () => {
      for (const read of matched) read.release()
      await new Promise((resolve) => setTimeout(resolve, 0))
    })
  }
}

/** Answers everything still outstanding, whatever it is for. */
async function landEverything(): Promise<void> {
  await land(() => true)
}

const TRAILS = JSON.stringify({ type: 'FeatureCollection', features: [] })

/** A phone that has been used before: onboarding done, the corridor archive
 *  downloaded, and the trail lines already in the store. The ordinary state
 *  of the app for everyone except a first-run hiker. */
function aPhoneThatHasBeenUsed(): void {
  app.onboard({ background_source: 'usgs_topo_offline' })
  store.set(CORRIDOR_BACKGROUND_PACKAGE.idbKey, new Blob(['pmtiles']))
  store.set(TRAILS_BLOB_KEY, new Blob([TRAILS]))
  store.set(POIS_KEY, [])
}

// The bootstrap gate reads three keys - the preferences (which carry the
// place the hiker hikes since #1374), the "today I'm…" mode (#1054) and the
// open walk ride one Promise.all - so landing "the preferences" means
// landing all three, or the gate never opens and nothing renders.
const isPreferences = (key: string) =>
  key === PREFERENCES_KEY || key === HIKER_MODE_KEY || key === OPEN_WALK_KEY

/**
 * The download store's keys, taken from the package catalogue rather than
 * spelled out - there are three archives behind the sheets today and the
 * count is not this file's business. Each is read under its own key and then,
 * when nothing finished is there, under a `:progress` one beside it.
 *
 * WITHDRAWN sheets included, and it has to be the same set App.tsx registers
 * (#855). The shell holds off its first map until every registered archive
 * has been READ - a package it has not read yet answers "not downloaded",
 * which is also the answer for one that is genuinely absent - so a key
 * missing from this list is a read this helper never lands and a map that is
 * never built.
 */
const ARCHIVE_KEYS = [...offeredSheets(), ...withdrawnSheets()].flatMap((sheet) =>
  offeredPackages(sheet).map((pkg) => pkg.idbKey),
)
const isArchive = (key: string) =>
  ARCHIVE_KEYS.some((archive) => key === archive || key.startsWith(`${archive}:`))

const isTrailData = (key: string) => !isPreferences(key) && !isArchive(key)

/** Every source id ever declared by any map this test built, torn down or not.
 *  A source in a built style is tiles being asked for, which is the cost being
 *  counted here whether or not that map survived. */
function everySourceAskedFor(): string[] {
  return MockMap.instances.flatMap((map) =>
    Object.keys((map.options.style as { sources: Record<string, unknown> }).sources),
  )
}

/** What a map was BUILT pointing its trail source at, as against what was
 *  pushed into it afterwards (`map.sourceData`). The two together are the
 *  whole question this file asks about the lines. */
function trailsSourceOf(map: MockMap): unknown {
  const style = map.options.style as {
    sources: Record<string, { data?: unknown }>
  }
  return style.sources[TRAILS_SOURCE_ID]?.data
}

describe('what a cold start costs', () => {
  it('builds the map once, however late the phone answers about itself', async () => {
    aPhoneThatHasBeenUsed()
    render(<App />)

    // The order a phone actually answers in: the small preferences object
    // first, then the archive store, then twelve megabytes of trail lines.
    // Each of the last two used to be worth a whole map.
    await land(isPreferences)
    await land(isArchive)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    expect(MockMap.instances).toHaveLength(1)

    await land(isTrailData)
    expect(MockMap.instances).toHaveLength(1)

    await landEverything()
    expect(MockMap.instances).toHaveLength(1)

    // And the one that was built is the one still up - not a survivor of two
    // teardowns, which is what the count above would also allow if the shell
    // had simply stopped building any.
    expect(MockMap.live).toHaveLength(1)
  })

  it('paints the tab bar at once, and waits for the archive store before drawing a map', async () => {
    // The half of the fix that is not about counting. `statusFor` answers
    // "not downloaded" for a package it has not READ yet, which is the same
    // answer it gives for one that is genuinely absent - so the shell used to
    // conclude "no download, draw the live sheet" before the question had been
    // asked, and reverse itself a beat later.
    //
    // Since #1301 the wait is the MAP's alone: the tab bar is on screen before
    // the store has answered anything (the launch mirror says this phone is
    // past onboarding), and the map is still not built until it has.
    aPhoneThatHasBeenUsed()
    render(<App />)

    expect(screen.getByRole('tab', { name: 'Today' })).toBeInTheDocument()
    expect(MockMap.instances).toHaveLength(0)

    await land(isPreferences)
    expect(MockMap.instances).toHaveLength(0)
    expect(screen.queryByRole('region', { name: /trail map/i })).toBe(null)

    await land(isArchive)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    expect(MockMap.instances).toHaveLength(1)
  })

  it('keeps the tab bar when the map tab is tapped before the store has answered', async () => {
    // Since #1301 the shell paints before the archive markers are read, so a
    // hiker can reach the tab bar and tap Map inside that window. The map
    // subtree carries the map tab's own tab bar, and with no map to mount it
    // rendered nothing at all - a blank screen with no way back, which is the
    // failure TECHNICAL_ARCHITECTURE.md's boundary section exists to prevent
    // and worse than the one it was written for, because nothing had thrown.
    aPhoneThatHasBeenUsed()
    render(<App />)

    await land(isPreferences)
    await openMapTab()

    // No map yet - the store has not said which background it should be built
    // around - and still a way off this screen.
    expect(MockMap.instances).toHaveLength(0)
    expect(screen.getByRole('tab', { name: 'Today' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Map' })).toBeInTheDocument()

    await land(isArchive)
    await screen.findByRole('region', { name: /trail map/i })
    expect(MockMap.instances).toHaveLength(1)
  })

  it('never asks the network for a background this phone had already downloaded', async () => {
    // What the reversal above actually spent. The live sheet's vector and DEM
    // tiles are roughly 2 MB for a fresh view (lib/dataSaver.ts measured it),
    // and they were being pulled on launch for a hiker who had downloaded the
    // corridor precisely so that they would not be - then thrown away
    // unrendered when the archive won. Bytes nobody asked for is the spend
    // that module exists to prevent, arriving through the back door.
    aPhoneThatHasBeenUsed()
    render(<App />)

    // Landed in the phone's own order rather than all at once. Answering
    // everything in a single commit lets React batch the whole launch into one
    // render, which is the state this app is never in on a real device - and a
    // test written that way passes against the very bug it is here to catch.
    await land(isPreferences)
    await land(isArchive)
    await landEverything()
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    expect(everySourceAskedFor()).not.toContain(OSM_SOURCE_ID)
  })

  it('puts the trail lines onto the map that is already there', async () => {
    // The other half. The lines are a GeoJSON source, and a GeoJSON source
    // takes a new URL in place - which is what the POIs, the closures and the
    // warnings have always done. Rebuilding the map to deliver them dropped
    // the WebGL context, every tile in flight and the camera, one second after
    // a hiker had been given all three.
    aPhoneThatHasBeenUsed()
    render(<App />)

    await land(isPreferences)
    await land(isArchive)
    // The home is Today (#1054), so the map only starts building once the
    // hiker opens its tab - after the two reads the shell's render gate
    // waits on, and before the trail data lands, which keeps the order this
    // test is about: a map first, its lines after.
    await openMapTab()
    const map = MockMap.live[0]
    expect(map).toBeDefined()
    const seeded = trailsSourceOf(map)

    await land(isTrailData)
    await landEverything()

    // Same map object, now holding lines it was not built with - not a
    // replacement that held them from birth.
    expect(MockMap.live[0]).toBe(map)
    expect(map.sourceData.get(TRAILS_SOURCE_ID)).toEqual(expect.stringContaining('blob:'))
    expect(map.sourceData.get(TRAILS_SOURCE_ID)).not.toBe(seeded)
  })

  it('does not push lines the map was built holding', async () => {
    // The other end of the same seam, and the reason the style is seeded at
    // all: when the lines are already known, they go into the style, so the
    // very first frame has the trail on it. Writing them in again afterwards
    // would be correct and wasteful - MapLibre re-fetches and re-tiles twelve
    // megabytes of coordinates for a source that already holds them.
    //
    // Reached by landing the reads in a different order rather than by
    // contriving anything: the archive store is simply the slower of the two
    // on this run, which is a phone, not a scenario.
    aPhoneThatHasBeenUsed()
    render(<App />)

    await land(isPreferences)
    await land(isTrailData)
    await land(isArchive)
    await landEverything()
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    const map = MockMap.live[0]
    expect(MockMap.instances).toHaveLength(1)
    // Built holding the real lines...
    expect(trailsSourceOf(map)).toEqual(expect.stringContaining('blob:'))
    // ...and never handed them a second time.
    expect(map.sourceData.has(TRAILS_SOURCE_ID)).toBe(false)
  })

  it('has no hand-over to get wrong, because first run builds no map (#1324)', async () => {
    // This used to assert the opposite number for a real reason: the steps
    // drew their own inert backdrop map, the map screen built its own when
    // they finished, and two live maps would have been two WebGL contexts.
    // Since #1324 the steps build nothing - an opaque photograph has stood
    // over that map since #1054 - so the hand-over this was guarding is a
    // thing that cannot happen rather than a thing that is handled.
    //
    // Kept as a cold-start context count, which is what this file is. The
    // pair that says what happens instead, and what the Map tab then opens,
    // is in `what the first-run steps cost` below.
    render(<App />)
    await landEverything()

    await screen.findByText('A map that works where there is no signal.')
    expect(MockMap.instances).toHaveLength(0)
  })
})

/**
 * The other cost a launch has, and the one a hiker feels rather than counts.
 *
 * The file above counts WebGL contexts. This counts what runs on the main
 * thread while the three entry steps are up - which is the thread the Skip
 * button on those steps is waiting for.
 *
 * The report (#857): "when I hit skip on the first 3 screens there is some
 * serious lag. A lot of times it feels like that button is broken." Measured
 * 2026-08-20 in Chromium at 390x844 on a 4x CPU throttle, against a build
 * served locally with artifacts at the live release's sizes and counts (#717's
 * figures, synthetic data behind them), replaying first run with that release
 * already downloaded: 5,479 ms of blocking work in 22 long
 * tasks while the steps were up, the longest of them 2,374 ms, and the second
 * Skip could not be clicked for 3.4 s after the first. None of it drew
 * anything - the card covers up to 78% of the screen and the only thing behind
 * it is the trail line.
 *
 * Same phone, same profile, after: 3,673 ms, longest task 434 ms, the three
 * taps answered in 11, 4 and 220 ms.
 */
describe('what the first-run steps cost', () => {
  /**
   * A phone that has been used before, showing first run again.
   *
   * The expensive case rather than a contrived one: everything is already in
   * the store, so every read lands while the steps are up instead of several
   * seconds later behind a download. It is also the case a developer hits
   * every time they clear preferences to look at onboarding again.
   */
  function aReleaseOnThePhone(): void {
    store.set(CORRIDOR_BACKGROUND_PACKAGE.idbKey, new Blob(['pmtiles']))
    store.set(TRAILS_BLOB_KEY, new Blob([TRAILS]))
    store.set(POIS_KEY, [
      {
        id: 'atc_water:1',
        type: 'water',
        name: 'Big Spring',
        lat: 39.3,
        lon: -77.1,
        confidence: 'high',
      },
    ])
  }

  /** Every read answered, in the order a phone answers them, with the steps
   *  up. Returns nothing: since #1324 there is no map to return here, which
   *  is what the first test below is about. */
  async function launch(): Promise<void> {
    render(<App />)
    await land(isPreferences)
    await land(isArchive)
    await land(isTrailData)
    await landEverything()
    await screen.findByText('A map that works where there is no signal.')
  }

  /** The trail line on a map, from wherever it reached it - the style it was
   *  seeded with, or a push into a map that was already up. */
  function trailSource(map: MockMap): unknown {
    const pushed = map.sourceData.get(TRAILS_SOURCE_ID)
    if (pushed !== undefined) return pushed
    const style = map.options.style as { sources: Record<string, { data?: unknown }> }
    return style.sources[TRAILS_SOURCE_ID]?.data
  }

  /** Through the three steps, declining everything they offer - the cheapest
   *  way out, and the one a hiker in a hurry takes. */
  async function stepThrough(user: ReturnType<typeof userEvent.setup>): Promise<void> {
    await user.click(screen.getByRole('button', { name: 'Get set up' }))

    // Past the mode card with nothing chosen, then the place card with no
    // place (#1373; the mode card is the review of #1374's).
    await user.click(screen.getByRole('button', { name: /^skip — day hike/i }))
    await user.click(screen.getByRole('button', { name: /^skip — i/i }))
    // Declined: this file counts maps and reads, not downloads (#1054).
    await user.click(screen.getByRole('button', { name: 'Decide this later' }))
    await user.click(screen.getByRole('button', { name: /not now/i }))
    await landEverything()
  }

  it('builds no map at all while they are up (#1324)', async () => {
    // THIS TEST REVERSES ITS PREDECESSOR, which asserted the trail line was on
    // the map behind the steps. That map was real and so was the line; what
    // was not real, from #1054 onward, was anybody seeing either.
    // `.onboarding__hero` is `inset: 0` over an opaque `--bg-chrome`, so the
    // steps stand on a wall rather than on the map - MEASURED 2026-09-09 in
    // pixels on the built app: every layer of the map screen painted magenta
    // by injected CSS, first run rendered normally, 0 of 329,160 pixels of
    // the frame magenta with the map screen and its canvas both present. It
    // cost 730-950 ms of MapLibre self time inside the window a hiker is
    // tapping Skip.
    //
    // `landEverything` has answered every read the app asked for, so a shell
    // that wanted a map would have had everything it needs to build one.
    aReleaseOnThePhone()

    await launch()

    expect(MockMap.instances).toHaveLength(0)
    // And no pin rasterised for a map that does not exist. Every image rather
    // than a count: `images` also holds the serious-warning pin
    // (map/warningPin.ts), which is on its own clock and was never what the
    // steps were paying for.
    expect(buildPoiIcons().length).toBeGreaterThan(0)
  })

  it('warms one the moment they are done, and it is the one the Map tab opens', async () => {
    // The other half, and the reason this is a move rather than a removal.
    // #721's promise was that the map is warm when the steps finish; the
    // promise is kept, at the moment the thread is free instead of the moment
    // it is busiest. The idle callback is jsdom-shimmed to the next macrotask
    // (test/setup.ts), so this asserts that it is REACHED and what it builds -
    // not when a browser would reach it.
    aReleaseOnThePhone()
    const user = userEvent.setup()

    await launch()
    await stepThrough(user)

    await screen.findByRole('tab', { name: 'Today', selected: true })
    await waitFor(() => expect(MockMap.live).toHaveLength(1))
    const warmed = MockMap.live[0]

    // The trail line the steps read reaches it - held rather than dropped,
    // which is what made reading it during the steps worth doing at all.
    //
    // Read from the seeded style OR from a later push, because #1324 moved
    // which one it arrives by: with the map built after the line has landed,
    // the line is in the style the map is constructed with rather than pushed
    // into a map that already existed. Both are the line being there, and a
    // test that insisted on the second would be pinning the build order
    // rather than the outcome.
    await waitFor(() =>
      expect(trailSource(warmed)).toEqual(expect.stringContaining('blob:')),
    )

    // And the first Map open of the session is that same map, not a second
    // construction - #1081's rule, which this changes the location of and not
    // the count.
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    expect(MockMap.live[0]).toBe(warmed)
    expect(MockMap.instances).toHaveLength(1)
  })

  it('fills the waypoints in as soon as the steps are done', async () => {
    // Held, not dropped, and this is the half that says so. The read the steps
    // went without runs when they end, so a hiker who skips straight through
    // lands on a map with its waypoints rather than on the next launch.
    aReleaseOnThePhone()
    const user = userEvent.setup()

    await launch()
    await stepThrough(user)

    // The proof the hold released is the map the hiker opens next: built
    // already knowing the waypoint the steps went without. The read itself
    // runs the moment the steps end, whichever tab is up.
    await openMapTab()
    await landEverything()

    await waitFor(() => {
      const opened = MockMap.live[0]
      expect(opened).toBeDefined()
      const pushed = opened.sourceData.get(POI_SOURCE_ID) as
        { features: Array<{ properties?: { poi_id?: string } }> } | undefined
      const style = opened.options.style as {
        sources: Record<
          string,
          { data?: { features?: Array<{ properties?: { poi_id?: string } }> } }
        >
      }
      const features =
        pushed?.features ?? style.sources[POI_SOURCE_ID]?.data?.features ?? []
      expect(features).toHaveLength(1)
      expect(features[0]?.properties?.poi_id).toBe('atc_water:1')
    })
  })

  it('holds that map through a hiker who beats the idle callback to Map (#1081)', async () => {
    // The most expensive teardown the shell ever performed, in the shape it
    // takes after #1324. First run used to build a map to stand behind the
    // steps and landing on Today (#1054) unmounted it, so the first Map tap
    // rebuilt from scratch what had just been thrown away; the `mapKept` latch
    // fixed that and still holds. What #1324 changes is which map the latch is
    // holding - the warmed one rather than the backdrop.
    //
    // The race is the case this test exists for: a hiker who taps Map before
    // the idle callback runs builds the map through `mapNeededNow`, and the
    // callback must then find it and do nothing rather than build a second.
    aReleaseOnThePhone()
    const user = userEvent.setup()

    await launch()
    await stepThrough(user)

    // Straight to Map without waiting for the warm-up. `openMapTab` resolves
    // on the tap, so whichever of the two got there first, exactly one map
    // exists at the end of it.
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    const opened = MockMap.live[0]
    expect(opened).toBeDefined()

    // Given the shim, the callback has certainly run by here - and it built
    // nothing, because the latch was already set.
    await landEverything()
    expect(MockMap.live[0]).toBe(opened)
    expect(MockMap.instances).toHaveLength(1)
  })
})

describe('what the tab bar costs after the cold start (#1081)', () => {
  // The regression the v1.1.0 report was about. #1054 moved the home to
  // Today, and every trip back to the Map tab was a full teardown and
  // rebuild - 2,353 ms of blocking work on the throttled-phone profile once
  // the data is downloaded (the measured figures at the top of this file's
  // sibling, App.loadBudget.test.tsx). Counted here the same way the cold
  // start is: in maps constructed, which is the only place the cost shows
  // against a mock.

  it('keeps the one map across Today and More round trips', async () => {
    aPhoneThatHasBeenUsed()
    const user = userEvent.setup()
    render(<App />)
    await land(isPreferences)
    await land(isArchive)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await landEverything()
    expect(MockMap.instances).toHaveLength(1)
    const built = MockMap.live[0]

    await user.click(screen.getByRole('tab', { name: 'Today' }))
    // The map screen is put away, not merely covered: out of the
    // accessibility tree entirely while Today is up.
    expect(screen.queryByRole('region', { name: /trail map/i })).toBe(null)
    await user.click(screen.getByRole('tab', { name: 'Map' }))
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await screen.findByRole('heading', { name: 'More' })
    await user.click(screen.getByRole('tab', { name: 'Map' }))
    await screen.findByRole('region', { name: /trail map/i })

    // Two round trips, still the one construction, still the same map.
    expect(MockMap.instances).toHaveLength(1)
    expect(MockMap.live).toHaveLength(1)
    expect(MockMap.live[0]).toBe(built)
  })

  it('still builds nothing for a launch that stays on Today', async () => {
    // The half of #1054's arrangement that was worth keeping, and the latch
    // must not cost: a hiker who opens the app to read their journal and
    // closes it again never pays for a map. `entering` is true on every
    // launch until the preferences read lands, so a latch that counted it
    // before `preferencesLoaded` would mount a map on exactly this launch -
    // which is what this pins.
    aPhoneThatHasBeenUsed()
    render(<App />)
    await landEverything()

    await screen.findByRole('tab', { name: 'Today', selected: true })
    expect(MockMap.instances).toHaveLength(0)
  })

  it('keeps the one map through a report opened from Today', async () => {
    // The review of the first cut caught this: the full-screen flows were
    // still early returns, so a report opened from Today silently destroyed
    // the kept map and remounted it - hidden, at full build cost - the
    // moment the flow closed. The flows render over the held map now, the
    // way the tab screens do, and this pins it with the cheapest flow to
    // drive: open reporting, change your mind.
    //
    // #1133 made this cheaper still and the test is kept rather than
    // retired. Reporting is a WINDOW now, so it does not take the screen at
    // all and the map is held by construction rather than by care. But the
    // failure mode this guards is a rendering decision somebody could make
    // again - the window is one line away from being assigned to
    // `flowScreen`, which is what would destroy the map - and a test that
    // costs one click is worth keeping against that.
    aPhoneThatHasBeenUsed()
    const user = userEvent.setup()
    render(<App />)
    await land(isPreferences)
    await land(isArchive)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await landEverything()
    const built = MockMap.live[0]

    await user.click(screen.getByRole('tab', { name: 'Today' }))
    await user.click(screen.getByRole('button', { name: 'Report a problem' }))
    // The window is over the screen rather than instead of it, and the map
    // survives underneath both.
    await screen.findByRole('dialog', { name: 'What did you find?' })
    expect(MockMap.live).toHaveLength(1)
    expect(MockMap.live[0]).toBe(built)

    await user.click(screen.getByTestId('report-close'))
    await screen.findByRole('tab', { name: 'Today', selected: true })
    expect(MockMap.instances).toHaveLength(1)
    expect(MockMap.live[0]).toBe(built)
  })

  it('leaves a crashed map alone until the hiker comes back to it', async () => {
    // The other review catch: with the map permanently mounted, a resetKey
    // of `activeTab` cleared a caught map crash - and re-ran the whole
    // multi-second build, hidden and inert - on every tab switch for the
    // rest of the session. The reset is keyed to ARRIVALS at the map now,
    // so a deterministic fault costs its retries where the hiker can see
    // the result, and a trip through the other tabs costs none.
    aPhoneThatHasBeenUsed()
    const user = userEvent.setup()
    // React announces every boundary catch through console.error. The
    // crashes below are this test's subject, not failures to surface.
    vi.spyOn(console, 'error').mockImplementation(() => {})
    render(<App />)
    await land(isPreferences)
    await land(isArchive)

    MockMap.failConstruction = new Error('no WebGL context to be had')
    await openMapTab()
    await screen.findByRole('heading', { name: /the map stopped working/i })
    const attemptsWhileCrashed = MockMap.constructionAttempts
    expect(attemptsWhileCrashed).toBeGreaterThan(0)

    // Away through the tabs that draw no map: not one hidden retry.
    await user.click(screen.getByRole('tab', { name: 'Today' }))
    await screen.findByRole('tab', { name: 'Today', selected: true })
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await screen.findByRole('heading', { name: 'More' })
    await user.click(screen.getByRole('tab', { name: 'Today' }))
    await screen.findByRole('tab', { name: 'Today', selected: true })
    expect(MockMap.constructionAttempts).toBe(attemptsWhileCrashed)

    // Coming back is the one retry, and this time the phone can: the fault
    // has passed, and the arrival builds the session's map.
    MockMap.failConstruction = null
    await user.click(screen.getByRole('tab', { name: 'Map' }))
    await screen.findByRole('region', { name: /trail map/i })
    expect(MockMap.constructionAttempts).toBe(attemptsWhileCrashed + 1)
    expect(MockMap.live).toHaveLength(1)
  })
})
