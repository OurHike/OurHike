// The setup every App.*.test.tsx file was writing out for itself.
//
// Nine files each built the same fake for the mocked idb-keyval, the same
// north-running synthetic centerline, the same geolocation watch, and the same
// teardown. That is roughly three hundred lines saying nothing about any of
// them - and worse, it buried the four or five lines per file that DO say
// something. App.safety.test.tsx's navigator stub carried the comment "onLine:
// true, unlike App.flows' stub - the closure reads are gated on it", which is
// exactly the kind of difference a reader should be able to see at a glance
// and could not.
//
// What stays in each file: its `vi.mock(...)` calls, which are hoisted and are
// the real subject - whether lib/api is configured, whether lib/config is,
// what the map protocol resolves to. Those differ on purpose and the files say
// so in their own headers.
//
// `appHarness()` is called at MODULE scope, not inside `beforeEach`. It
// registers its own hooks there, so the store it returns has a stable identity
// the tests below can close over, and its `beforeEach` is registered before the
// file's own - which is the order the seeding needs.

import { afterEach, beforeEach, expect, vi } from 'vitest'
import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { del, get, set, update } from 'idb-keyval'
import { loadMapEngine } from '../map/mapEngineLoader'
import { resetMapLibreMock } from './mocks/maplibre-gl'
import { PREFERENCES_KEY } from '../lib/preferences'
import { DEFAULT_PREFERENCES } from '../lib/userPreferences'
import { POIS_KEY, TRAILS_BLOB_KEY } from '../lib/trailData'

/** A mile of latitude, near enough that a vertex index IS a mile marker on the
 *  due-north centerline below. */
export const MILE_LAT = 1 / 69.05

/** The latitude a given mile of that centerline sits at. */
export function latOfMile(mile: number): number {
  return 39 + mile * MILE_LAT
}

/**
 * A centerline running due north from (-77, 39), one vertex per mile.
 *
 * Due north so that the mile arithmetic is legible in the assertions: a fix at
 * `latOfMile(5)` is at mile 5, and a closure from marker 8 to 9 is three miles
 * ahead of it. A real centerline wanders, and a test that had to account for
 * that would be testing trigonometry rather than the shell.
 */
export function centerlineGeoJSON(
  miles = 40,
  properties: Record<string, unknown> = { source: 'centerline' },
): string {
  return JSON.stringify({
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties,
        geometry: {
          type: 'LineString',
          coordinates: Array.from({ length: miles }, (_, i) => [-77, latOfMile(i)]),
        },
      },
    ],
  })
}

export interface HarnessOptions {
  /**
   * Replace `navigator`, or leave jsdom's alone.
   *
   * OPT-IN, and that is the important part. A stubbed navigator is a plain
   * object, so `vi.spyOn(navigator, 'onLine', 'get')` cannot be applied to it -
   * and three tests in App.trailData.test.tsx do exactly that to go offline
   * mid-test. Files that only ever need one answer stub it; files that need to
   * change the answer do not.
   *
   * `onLine` is worth setting deliberately when it is set at all: the shell's
   * reads of closures, reports and ATC notices are all gated on it, so a file
   * asserting a banner appears needs true and one asserting the offline path
   * needs false. `geolocation` installs the watch `reportFixAtMile` delivers
   * through.
   */
  navigator?: { onLine?: boolean; geolocation?: boolean }
  /**
   * Stub `URL.createObjectURL`/`revokeObjectURL`, which jsdom implements
   * neither of and the shell calls once per trail-data load.
   */
  objectUrls?: boolean
  /** Stub `fetch` with a mock that resolves nothing. On by default - a test
   *  reaching the real one is a test making a network call. Off for files
   *  that install their own. */
  stubFetch?: boolean
}

export interface AppHarness {
  /** What the mocked idb-keyval reads and writes. Cleared before each test. */
  store: Map<string, unknown>
  /**
   * Preferences that put a hiker past onboarding and past the download
   * question - the state nearly every test wants to start from, since neither
   * screen is the subject.
   */
  onboard(overrides?: Record<string, unknown>): void
  /** Trail data already on the phone, so nothing is fetched and the centerline
   *  index is built from exactly this geometry. */
  putTrailData(options?: { miles?: number; pois?: readonly unknown[] }): void
  /**
   * Deliver a GPS fix at a mile of the synthetic centerline.
   *
   * Waits for the watch to exist first, and that is not defensive padding. The
   * watch starts in an effect that runs only once loaded preferences say
   * location is allowed - a commit or two AFTER the map screen appears - so
   * firing straight after `findByRole` sometimes found nothing registered, the
   * fix was swallowed, and the test failed looking for a mile that was never
   * going to arrive.
   */
  reportFixAtMile(mile: number, lon?: number): Promise<void>
}

/**
 * Land on the map screen after rendering <App />.
 *
 * The home tab is Today since #1054, and most of these files were written
 * when the map WAS the front door: they render, reach for the trail-map
 * region, and go to work. One shared click here rather than a copy in every
 * file, so the day the navigation changes again there is one place that
 * knows how a test gets to the map.
 */
export async function openMapTab(): Promise<void> {
  fireEvent.click(await screen.findByRole('tab', { name: 'Map' }))
}

export function appHarness(options: HarnessOptions = {}): AppHarness {
  const { navigator: nav, objectUrls = false, stubFetch = true } = options

  const store = new Map<string, unknown>()
  let watchSuccess: ((position: GeolocationPosition) => void) | undefined

  beforeEach(async () => {
    store.clear()
    watchSuccess = undefined
    resetMapLibreMock()

    // Primes the deferred map engine (#722) before anything renders.
    //
    // In production `maplibre-gl` arrives through `import()` a beat after the
    // first paint, and `MapView` builds its map when it lands. A test that
    // renders and reaches straight for `MockMap.live` would be racing that
    // beat - so the engine is loaded HERE, in the same tick order every test
    // already relies on, and every `MapView` mount then takes the synchronous
    // branch exactly as it did before the deferral.
    //
    // It has to be here rather than in test/setup.ts: this runs after the
    // test file's `vi.mock('maplibre-gl', ...)` is registered, so the engine
    // closes over the MOCK. Loaded in setup it would close over the real
    // library, which throws GPUInitializationError in jsdom - the trap
    // recorded on #722.
    await loadMapEngine()

    vi.mocked(get).mockImplementation((key) => Promise.resolve(store.get(key as string)))
    vi.mocked(set).mockImplementation((key, value) => {
      store.set(key as string, value)
      return Promise.resolve()
    })
    vi.mocked(del).mockImplementation((key) => {
      store.delete(key as string)
      return Promise.resolve()
    })
    // Applied synchronously against the store, mirroring the real update()'s
    // single-transaction semantics - the outbox's mutators go through it
    // since #288, so a harness without it strands every report flow.
    vi.mocked(update).mockImplementation((key, updater) => {
      store.set(key as string, updater(store.get(key as string)))
      return Promise.resolve()
    })

    if (stubFetch) vi.stubGlobal('fetch', vi.fn())

    if (nav !== undefined) {
      vi.stubGlobal('navigator', {
        onLine: nav.onLine ?? false,
        userAgent: '',
        platform: '',
        ...(nav.geolocation === true
          ? {
              geolocation: {
                watchPosition: (success: (position: GeolocationPosition) => void) => {
                  watchSuccess = success
                  return 1
                },
                clearWatch: () => {},
              },
            }
          : {}),
      })
    }

    if (objectUrls) {
      vi.stubGlobal('URL', {
        ...URL,
        createObjectURL: vi.fn(() => 'blob:trails'),
        revokeObjectURL: vi.fn(),
      })
    }
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  return {
    store,

    onboard(overrides: Record<string, unknown> = {}) {
      store.set(PREFERENCES_KEY, {
        ...DEFAULT_PREFERENCES,
        onboarding_completed: true,
        download_choice_made: true,
        ...overrides,
      })
    },

    putTrailData({ miles = 40, pois = [] } = {}) {
      store.set(TRAILS_BLOB_KEY, new Blob([centerlineGeoJSON(miles)]))
      store.set(POIS_KEY, pois)
    },

    async reportFixAtMile(mile: number, lon = -77) {
      await waitFor(() => expect(watchSuccess).toBeDefined())
      await act(async () => {
        watchSuccess?.({
          coords: { latitude: latOfMile(mile), longitude: lon, accuracy: 5 },
          timestamp: 1_754_000_000_000,
        } as unknown as GeolocationPosition)
      })
    },
  }
}
