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
import { act, render, screen } from '@testing-library/react'
import { get } from 'idb-keyval'
import App from './App'
import { MockMap } from './test/mocks/maplibre-gl'
import { appHarness } from './test/appHarness'
import { PREFERENCES_KEY } from './lib/preferences'
import { POIS_KEY, TRAILS_BLOB_KEY } from './lib/trailData'
import {
  CORRIDOR_BACKGROUND_PACKAGE,
  offeredPackages,
  offeredSheets,
} from './lib/packages'
import { TRAILS_SOURCE_ID } from './map/style'
import { OSM_SOURCE_ID } from './map/liveTopo'

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./map/archiveZooms', () => ({
  readArchiveZooms: () => Promise.resolve({ minZoom: 5, maxZoom: 14 }),
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

const isPreferences = (key: string) => key === PREFERENCES_KEY

/**
 * The download store's keys, taken from the package catalogue rather than
 * spelled out - there are three archives behind the two sheets today and the
 * count is not this file's business. Each is read under its own key and then,
 * when nothing finished is there, under a `:progress` one beside it.
 */
const ARCHIVE_KEYS = offeredSheets().flatMap((sheet) =>
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

  it('waits for the archive store before drawing anything at all', async () => {
    // The half of the fix that is not about counting. `statusFor` answers
    // "not downloaded" for a package it has not READ yet, which is the same
    // answer it gives for one that is genuinely absent - so the shell used to
    // conclude "no download, draw the live sheet" before the question had been
    // asked, and reverse itself a beat later.
    aPhoneThatHasBeenUsed()
    render(<App />)

    await land(isPreferences)
    expect(MockMap.instances).toHaveLength(0)
    expect(screen.queryByRole('region', { name: /trail map/i })).toBe(null)

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
    await screen.findByRole('region', { name: /trail map/i })

    const map = MockMap.live[0]
    expect(MockMap.instances).toHaveLength(1)
    // Built holding the real lines...
    expect(trailsSourceOf(map)).toEqual(expect.stringContaining('blob:'))
    // ...and never handed them a second time.
    expect(map.sourceData.has(TRAILS_SOURCE_ID)).toBe(false)
  })

  it('still hands over exactly one map when a first run finishes onboarding', async () => {
    // The one hand-over that IS worth a rebuild, kept honest: the first-run
    // steps draw their own inert backdrop map, and the map screen builds its
    // own when they finish. Two live maps would be two WebGL contexts; this
    // asserts the backdrop is really torn down rather than left behind.
    render(<App />)
    await landEverything()

    await screen.findByText('What OurHike is')
    expect(MockMap.live).toHaveLength(1)
  })
})
