// The sidebar and Today stay on screen while MapScreen's own code is still on
// its way, and the same column is handed over when it lands (#1560).
//
// WHAT WENT WRONG. On a laptop the tab bar lives inside MapScreen, and
// MapScreen is a deferred screen (screens/deferred.ts, #1302) that renders
// nothing until its chunk has arrived. #1429 gave the launch a pre-map branch
// - the sidebar and Today's journal, drawn while the archive store is still
// being asked - and that branch let go the moment the map was WANTED
// (`mapMounted`), not the moment its code was HERE. Between the two, nothing:
// measured 2026-09-17 at 1728x1080 on a cold cache, the sidebar on screen at
// 471 ms, gone at 897 ms when the store answered, back at 2,044 ms when the
// chunk did. With the precache warm the chunk lands first and nobody sees it,
// which is why it took a launch after a deploy to notice.
//
// WHY THE MODULE IS HELD BY A MOCK. The harness preloads every deferred
// screen before each test (test/appHarness.ts), so `MapScreen.loaded()` is
// true from the first render everywhere else in the suite - which is the
// production state on a warm cache and exactly the state that cannot show
// this. The mock below replaces MapScreen alone with a copy whose import
// waits for the test to release it; `preloadScreens` still primes the real
// module, so the release is a resolved promise and never a race.
//
// One test, deliberately: a deferred screen memoises its module for the life
// of the process, so a second test in this file would find MapScreen already
// here.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { get, getMany } from 'idb-keyval'
import App from './App'
import { MockMap } from './test/mocks/maplibre-gl'
import { appHarness, stubDesktop } from './test/appHarness'
import * as deferred from './screens/deferred'
import { PREFERENCES_KEY } from './lib/preferences'
import { HIKER_MODE_KEY } from './lib/hikerMode'
import { TAKEN_TRAIL_KEY } from './lib/takenTrail'
import { OPEN_WALK_KEY } from './lib/openWalk'
import { POIS_KEY, TRAILS_BLOB_KEY } from './lib/trailData'
import {
  CORRIDOR_BACKGROUND_PACKAGE,
  offeredPackages,
  offeredSheets,
  withdrawnSheets,
} from './lib/packages'

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
vi.mock('./screens/deferred', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./screens/deferred')>()
  const { deferredScreen } = await import('./lib/deferredScreen')
  let release: () => void = () => {}
  const held = new Promise<void>((resolve) => {
    release = resolve
  })
  const MapScreen = deferredScreen(
    () => held.then(() => import('./chrome/MapScreen')).then((m) => m.MapScreen),
    'MapScreen',
  )
  return { ...actual, MapScreen, releaseMapScreen: () => release() }
})

/** The mock's extra export: lets MapScreen's module through. */
const releaseMapScreen = (deferred as unknown as { releaseMapScreen: () => void })
  .releaseMapScreen

const app = appHarness()
const store = app.store

/**
 * Every read the app has asked for and not been given an answer to - the
 * ordering machinery App.mapLifecycle.test.tsx explains: a mock that answers
 * within the commit that asked collapses the launch into one render, and the
 * blank this file is about lives between two of its steps.
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
  vi.mocked(getMany).mockImplementation((keys) =>
    Promise.all(keys.map((key) => vi.mocked(get)(key))),
  )
})

afterEach(() => vi.restoreAllMocks())

async function land(matches: (key: string) => boolean): Promise<void> {
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

const isPreferences = (key: string) =>
  key === PREFERENCES_KEY ||
  key === HIKER_MODE_KEY ||
  key === OPEN_WALK_KEY ||
  key === TAKEN_TRAIL_KEY

const ARCHIVE_KEYS = [...offeredSheets(), ...withdrawnSheets()].flatMap((sheet) =>
  offeredPackages(sheet).map((pkg) => pkg.idbKey),
)
const isArchive = (key: string) =>
  ARCHIVE_KEYS.some((archive) => key === archive || key.startsWith(`${archive}:`))

const TRAILS = JSON.stringify({ type: 'FeatureCollection', features: [] })

describe('a laptop launch whose map screen code is still on its way (#1560)', () => {
  it('keeps the sidebar and Today up until the code lands, then hands the same column over', async () => {
    stubDesktop()
    app.onboard({ background_source: 'usgs_topo_offline' })
    store.set(CORRIDOR_BACKGROUND_PACKAGE.idbKey, new Blob(['pmtiles']))
    store.set(TRAILS_BLOB_KEY, new Blob([TRAILS]))
    store.set(POIS_KEY, [])

    render(<App />)
    await land(isPreferences)
    // The moment the old branch let go: the store has answered for every
    // package, so the map is wanted - and its code is not here.
    await land(isArchive)
    await land(() => true)

    expect(screen.getByRole('tab', { name: 'Today' })).toBeInTheDocument()
    expect(document.querySelector('.app__screen > .map-screen__journal')).not.toBe(null)
    expect(document.querySelector('.today')).not.toBe(null)
    expect(screen.queryByRole('region', { name: /trail map/i })).toBe(null)
    expect(MockMap.instances).toHaveLength(0)

    // The code lands.
    await act(async () => {
      releaseMapScreen()
      await new Promise((resolve) => setTimeout(resolve, 0))
    })

    await screen.findByRole('region', { name: /trail map/i })
    expect(screen.getByRole('tab', { name: 'Today' })).toBeInTheDocument()
    // One journal, in MapScreen's column now and nowhere else.
    expect(document.querySelector('.map-screen .map-screen__journal')).not.toBe(null)
    expect(document.querySelector('.app__screen > .map-screen__journal')).toBe(null)
    expect(document.querySelectorAll('.today')).toHaveLength(1)
  })
})
