import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { get, set } from 'idb-keyval'
import App from './App'
import { MockMap, NavigationControl, resetMapLibreMock } from './test/mocks/maplibre-gl'
import { PREFERENCES_KEY } from './lib/preferences'
import { DEFAULT_PREFERENCES } from './lib/userPreferences'
import { POIS_KEY, TRAILS_BLOB_KEY } from './lib/trailData'
import { CORRIDOR_BACKGROUND_PACKAGE } from './lib/packages'

// The shell decides what a hiker sees, so what is worth testing here is the
// routing between screens and the honesty of what it shows before any data
// exists - not the screens themselves, which have their own tests.

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))

const store = new Map<string, unknown>()

beforeEach(() => {
  store.clear()
  resetMapLibreMock()
  vi.mocked(get).mockImplementation((key) => Promise.resolve(store.get(key as string)))
  vi.mocked(set).mockImplementation((key, value) => {
    store.set(key as string, value)
    return Promise.resolve()
  })
  vi.stubGlobal('fetch', vi.fn())
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

/** A phone that has been through onboarding already. */
function returningHiker() {
  store.set(PREFERENCES_KEY, {
    ...DEFAULT_PREFERENCES,
    onboarding_completed: true,
    download_choice_made: true,
  })
}

/**
 * A finished corridor archive on the phone.
 *
 * Needed by anything asserting Data Saver's override, because the override
 * only subtracts the live sheet once there is a download to fall back on -
 * see lib/dataSaver.ts. Without this the map draws the live sheet whatever
 * Data Saver says, which is the whole point of that rule.
 */
function withDownloadedArchive() {
  store.set(CORRIDOR_BACKGROUND_PACKAGE.idbKey, new Blob(['pmtiles']))
}

async function completeOnboarding(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByText('What OurHike is')
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.click(screen.getByRole('button', { name: /not now/i }))
}

/**
 * The live map, once MapView's effect has actually built it.
 *
 * `findByRole('region')` resolves the moment MapView's container div lands in
 * the DOM - which is a commit BEFORE the effect that constructs the map runs.
 * Reading `MockMap.live[0]` straight after it is therefore a race that usually
 * wins on a quiet machine and loses under load: it went green on both of #86's
 * PR runs and red on the merge commit, with `Cannot read properties of
 * undefined (reading 'options')`. Waiting for the map itself is the thing these
 * tests actually mean.
 */
async function liveMap() {
  await waitFor(() => expect(MockMap.live.length).toBeGreaterThan(0))
  return MockMap.live[0]
}

function styleOf(map: MockMap): { sources: Record<string, unknown> } {
  return map.options.style as { sources: Record<string, unknown> }
}

describe('App shell', () => {
  it('opens on onboarding the very first time', async () => {
    render(<App />)

    expect(await screen.findByText('What OurHike is')).toBeInTheDocument()
  })

  it('does not show onboarding again once it has been completed', async () => {
    returningHiker()
    render(<App />)

    expect(await screen.findByRole('region', { name: /trail map/i })).toBeInTheDocument()
    expect(screen.queryByText('What OurHike is')).not.toBeInTheDocument()
  })

  it('sends someone to Downloads when onboarding finishes, since there is no map yet', async () => {
    const user = userEvent.setup()
    render(<App />)

    await completeOnboarding(user)

    expect(await screen.findByText('Offline map')).toBeInTheDocument()
  })

  it('remembers that onboarding was completed, so a reload does not repeat it', async () => {
    const user = userEvent.setup()
    render(<App />)

    await completeOnboarding(user)

    await waitFor(() => {
      const saved = store.get(PREFERENCES_KEY) as { onboarding_completed: boolean }
      expect(saved.onboarding_completed).toBe(true)
    })
  })

  it('says the position is unknown rather than claiming mile zero before a fix', async () => {
    returningHiker()
    render(<App />)

    // Mile 0.0 is Springer Mountain - a confident claim about somewhere the
    // hiker is almost certainly not standing.
    expect(await screen.findByText(/looking for gps/i)).toBeInTheDocument()
    expect(screen.queryByText(/mi 0\.0/)).not.toBeInTheDocument()
  })

  it('moves between the three tabs', async () => {
    const user = userEvent.setup()
    returningHiker()
    render(<App />)

    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'Downloads' }))
    expect(await screen.findByText('Offline map')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'More' }))
    expect(await screen.findByRole('heading', { name: 'You' })).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Trail' }))
    expect(await screen.findByRole('region', { name: /trail map/i })).toBeInTheDocument()
  })

  // Reported as "the Downloads tab shows no data, nothing", and it was worse
  // than that: leaving the map tore the map down, MapView's next effect cleanup
  // then removed controls that teardown had already detached, and the TypeError
  // escaping a commit-phase cleanup unmounted the entire root. A white page with
  // no tab bar on it - reachable from either non-map tab, and on a phone as
  // readily as on a desktop. The three-tab test above covers the same path, but
  // reads as navigation rather than as the crash it is really guarding.
  it.each(['Downloads', 'More'])(
    'still renders %s after the map tab, rather than blanking the whole app',
    async (tab) => {
      const user = userEvent.setup()
      returningHiker()
      render(<App />)
      await screen.findByRole('region', { name: /trail map/i })

      await user.click(screen.getByRole('tab', { name: tab }))

      expect(await screen.findByRole('tab', { name: tab, selected: true })).toBeVisible()
      expect(screen.queryByRole('region', { name: /trail map/i })).not.toBeInTheDocument()
    },
  )

  it('comes back to the view the hiker left, not to the whole trail, after another tab', async () => {
    // The bug: the map screen unmounts whenever another tab is showing, so
    // coming back builds a new map - and the new one was handed the opening
    // corridor bounds again. Checking the download progress threw away where
    // someone had zoomed to, every time, and the first-fix jump was a one-way
    // latch that never brought them back.
    const user = userEvent.setup()
    returningHiker()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    const opening = await liveMap()
    // Stand in for the hiker panning and zooming to a shelter.
    opening.center = { lng: -78.4, lat: 38.6 }
    opening.zoom = 15
    act(() => opening.emit('moveend'))

    await user.click(screen.getByRole('tab', { name: 'Downloads' }))
    await screen.findByText('Offline map')
    await user.click(screen.getByRole('tab', { name: 'Trail' }))
    await screen.findByRole('region', { name: /trail map/i })

    const rebuilt = await liveMap()
    expect(rebuilt).not.toBe(opening)
    expect(rebuilt.options.center).toEqual([-78.4, 38.6])
    expect(rebuilt.options.zoom).toBe(15)
    // Bounds would re-fit the whole corridor and win over the centre.
    expect(rebuilt.options.bounds).toBeUndefined()
  })

  it('opens on the whole corridor when there is no view to come back to', async () => {
    returningHiker()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    // Before a fix or a pan the app genuinely does not know where the hiker
    // is, and the whole trail is the honest opening answer.
    expect((await liveMap()).options.bounds).toEqual([
      [-84.73, 34.2],
      [-68.3, 46.34],
    ])
  })

  it('zooms in on a search result rather than nudging the corridor view', async () => {
    // The bug: the jump set a centre and left the zoom alone. From the opening
    // view of the entire trail that moved the map by a few pixels, so tapping
    // a shelter you had just searched for looked like nothing had happened.
    const user = userEvent.setup()
    returningHiker()
    store.set(
      'ourhike:trails',
      new Blob([JSON.stringify({ type: 'FeatureCollection', features: [] })]),
    )
    store.set('ourhike:pois', [
      {
        id: 'atc_shelters:abc',
        type: 'shelter',
        name: 'Chairback Gap Lean-to',
        lat: 45.45,
        lon: -69.26,
        confidence: 'high',
      },
    ])

    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('button', { name: 'Search' }))
    await user.type(await screen.findByRole('searchbox'), 'chairback')
    // Waiting for the result also waits out the map rebuild that loading trail
    // data triggers - the POIs and the new trails URL land in the same commit.
    const result = await screen.findByRole('button', { name: /chairback/i })
    const map = await liveMap()

    await user.click(result)

    const moved = map.cameraMoves.at(-1)
    expect(moved?.center).toEqual([-69.26, 45.45])
    expect(moved?.zoom as number).toBeGreaterThanOrEqual(14)
  })

  it('does not pull the map back out when a search result is found while zoomed in', async () => {
    const user = userEvent.setup()
    returningHiker()
    store.set(
      'ourhike:trails',
      new Blob([JSON.stringify({ type: 'FeatureCollection', features: [] })]),
    )
    store.set('ourhike:pois', [
      {
        id: 'atc_water:xyz',
        type: 'water',
        name: 'Spring below the gap',
        lat: 45.45,
        lon: -69.26,
        confidence: 'high',
      },
    ])

    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('button', { name: 'Search' }))
    await user.type(await screen.findByRole('searchbox'), 'spring')
    // Zoom in only once the result is on screen: loading the trail data
    // rebuilds the map, and a zoom set on the outgoing one goes with it.
    const result = await screen.findByRole('button', { name: /spring below/i })

    const map = await liveMap()
    map.zoom = 16
    act(() => map.emit('moveend'))

    await user.click(result)

    expect(map.cameraMoves.at(-1)?.zoom).toBe(16)
  })

  it('reaches the report flow from More', async () => {
    const user = userEvent.setup()
    returningHiker()
    render(<App />)

    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))

    expect(
      await screen.findByRole('heading', { name: 'Report a problem' }),
    ).toBeInTheDocument()
  })

  it('backs out of the report flow without filing anything', async () => {
    // The reporting flow replaces the whole shell, tab bar included, so the
    // type picker was a screen with no exit: the only way off it was to pick a
    // report type and then cancel the form behind it.
    const user = userEvent.setup()
    returningHiker()
    render(<App />)

    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))
    await user.click(await screen.findByRole('button', { name: /^cancel$/i }))

    expect(await screen.findByRole('heading', { name: 'You' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'More', selected: true })).toBeInTheDocument()
  })

  it('saves a report to the outbox rather than asking to sign in first', async () => {
    const user = userEvent.setup()
    returningHiker()
    render(<App />)

    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))
    await user.click(await screen.findByRole('button', { name: /blow down/i }))
    await user.click(await screen.findByRole('button', { name: /send|save to outbox/i }))

    await waitFor(() => {
      const queued = store.get('ourhike:outbox') as Array<{ payload: { type: string } }>
      expect(queued).toHaveLength(1)
      expect(queued[0].payload.type).toBe('blowdown')
    })
  })

  it('queues a report with no coordinates rather than pinning it at 0,0', async () => {
    // There is no GPS in jsdom, which is exactly the case that was broken: the
    // shell filled in lat 0 / lon 0 / mile 0, so every report written before a
    // fix arrived was filed in the Atlantic and at Springer Mountain at once.
    const user = userEvent.setup()
    returningHiker()
    render(<App />)

    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))
    await user.click(await screen.findByRole('button', { name: /blow down/i }))
    await user.click(await screen.findByRole('button', { name: /send|save to outbox/i }))

    await waitFor(() => {
      const queued = store.get('ourhike:outbox') as Array<{
        payload: { lat?: number; lon?: number }
      }>
      expect(queued).toHaveLength(1)
      expect(queued[0].payload.lat).toBeUndefined()
      expect(queued[0].payload.lon).toBeUndefined()
    })
  })

  it('warns on the Downloads screen when no data source was configured at build time', async () => {
    const user = userEvent.setup()
    returningHiker()
    render(<App />)

    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'Downloads' }))

    // VITE_DATA_BASE_URL is unset under test, so this is the real state - and a
    // download that would silently 404 is worth saying out loud.
    expect(await screen.findByRole('alert')).toHaveTextContent(/VITE_DATA_BASE_URL/)
  })

  /** POIs on the phone, but a trails.geojson too damaged to index - the state
   *  in which search used to go silently empty. */
  function poisWithoutAUsableIndex() {
    returningHiker()
    store.set(TRAILS_BLOB_KEY, new Blob(['{"type":"FeatureCollection","featu']))
    store.set(POIS_KEY, [
      {
        id: 'atc_shelters:abc',
        type: 'shelter',
        name: 'Chairback Gap Lean-to',
        lat: 45.45,
        lon: -69.26,
        confidence: 'high',
      },
    ])
  }

  it('can still find a shelter by name when the trail index could not be built', async () => {
    // The bug: searchablePois returned [] whenever trailIndex was null, so a
    // failed or not-yet-built centerline index silently emptied search while
    // hundreds of POIs sat in memory. Finding a shelter by name needs no
    // geometry - the mile is decoration on the row.
    //
    // Driven through the real App rather than by calling searchPois() on a
    // hand-built list: the defect was in App's own searchablePois memo, and a
    // test that never renders App cannot see it. The first version of this
    // test did exactly that and passed against the unfixed code.
    const user = userEvent.setup()
    poisWithoutAUsableIndex()
    render(<App />)

    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('button', { name: /search/i }))
    await user.type(
      await screen.findByRole('searchbox', { name: /search the downloaded map/i }),
      'chairback',
    )

    expect(await screen.findByText('Chairback Gap Lean-to')).toBeInTheDocument()
  })

  it('omits the mile on a result rather than inventing mile zero for it', async () => {
    // The other half of the same fix. The old code defaulted an uncomputable
    // mile to `?? 0`, which reads as Springer Mountain - a confident, precise,
    // wrong answer of exactly the kind this app is not supposed to give.
    const user = userEvent.setup()
    poisWithoutAUsableIndex()
    render(<App />)

    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('button', { name: /search/i }))
    await user.type(
      await screen.findByRole('searchbox', { name: /search the downloaded map/i }),
      'chairback',
    )

    await screen.findByText('Chairback Gap Lean-to')
    expect(screen.getByText('Shelter')).toBeInTheDocument()
    expect(screen.queryByText(/mi 0\.0/)).not.toBeInTheDocument()
  })

  it('keeps the POIs usable when the trail lines arrive damaged, instead of throwing', async () => {
    // JSON.parse on half a downloaded file throws, and that used to escape
    // through `void refreshTrailData()` as an unhandled rejection - taking the
    // POIs with it and saying nothing to anyone.
    const seen: unknown[] = []
    const onUnhandled = (reason: unknown) => seen.push(reason)
    process.on('unhandledRejection', onUnhandled)
    try {
      poisWithoutAUsableIndex()
      render(<App />)
      await screen.findByRole('region', { name: /trail map/i })
      await new Promise((resolve) => setTimeout(resolve, 50))
    } finally {
      process.off('unhandledRejection', onUnhandled)
    }

    expect(seen).toEqual([])
  })

  it('says why the archive download failed instead of just returning to the button', async () => {
    // The failure that made this undiagnosable in production: the archive 404'd,
    // the hook's bare catch swallowed the reason, and the screen went back to
    // "Download the map" with nothing said. "Nothing happened" leaves someone
    // with no idea whether to retry, wait, or check their signal.
    const user = userEvent.setup()
    returningHiker()
    vi.mocked(fetch).mockImplementation((url) =>
      String(url).includes('.pmtiles')
        ? Promise.resolve({ ok: false, status: 404, statusText: 'Not Found' } as Response)
        : Promise.resolve({
            ok: true,
            blob: () =>
              Promise.resolve(new Blob(['{"type":"FeatureCollection","features":[]}'])),
            text: () => Promise.resolve('{"features":[]}'),
          } as unknown as Response),
    )

    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'Downloads' }))
    await user.click(await screen.findByRole('button', { name: /download the map/i }))

    await waitFor(() => {
      expect(screen.getByText(/404|not found|failed/i)).toBeInTheDocument()
    })
  })

  it('does not start the huge archive download once the small one has already failed', async () => {
    // The few megabytes of trail lines and POIs are the canary. Whatever
    // stopped them - no signal, a missing key, a misconfigured bucket - will
    // stop the next several hundred too, and a hiker pays for that in data to
    // learn nothing.
    const user = userEvent.setup()
    returningHiker()
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
    } as Response)

    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'Downloads' }))
    await user.click(await screen.findByRole('button', { name: /download the map/i }))

    await waitFor(() => {
      expect(screen.getByText(/failed to fetch/i)).toBeInTheDocument()
    })

    // Only the trail-data attempt should have gone out. The archive request
    // would be the one after it.
    const requested = vi.mocked(fetch).mock.calls.map((c) => String(c[0]))
    expect(requested.some((url) => url.includes('.pmtiles'))).toBe(false)
  })
})

describe('the map controls the shell asks for', () => {
  // WIREFRAMES.md §1.5 makes the zoom buttons web-only: on a phone pinch
  // already zooms and the bottom-right corner belongs to locate, which is the
  // control that matters while walking. Nothing was passing that decision down,
  // so `showZoomButtons` sat on its `false` default everywhere and a browser
  // with a mouse had no visible way to zoom at all.

  /** A browser whose primary pointer is, or is not, a mouse. */
  function pointerIsFine(fine: boolean) {
    vi.stubGlobal(
      'matchMedia',
      vi.fn((query: string) => ({
        matches: query.includes('pointer: fine') ? fine : false,
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
      })),
    )
  }

  /** The compass control, which is also the one carrying the zoom buttons. */
  async function navigationControl(map: MockMap) {
    // Chrome is attached in an effect after the map is built, so it is not
    // there the instant liveMap() resolves.
    await waitFor(() =>
      expect(map.controls.some((c) => c.control instanceof NavigationControl)).toBe(true),
    )
    return map.controls.find((c) => c.control instanceof NavigationControl)
      ?.control as NavigationControl
  }

  it('gives a browser driven by a mouse its zoom buttons', async () => {
    pointerIsFine(true)
    returningHiker()

    render(<App />)
    const nav = await navigationControl(await liveMap())

    expect(nav.options?.showZoom).toBe(true)
  })

  it('keeps them off a touch screen, where they would cost the thumb zone', async () => {
    pointerIsFine(false)
    returningHiker()

    render(<App />)
    const nav = await navigationControl(await liveMap())

    expect(nav.options?.showZoom).toBe(false)
  })
})

describe('Data Saver', () => {
  // The end of the wire. dataSaver.ts decides, Settings explains, and this is
  // the part that actually stops the bytes: with Data Saver on, the style the
  // map is built with must carry no live sources at all. Asserting the setting
  // or the copy alone would pass just as happily while the tiles kept coming.
  function setSaveData(saveData: boolean): void {
    Object.defineProperty(navigator, 'connection', {
      value: { saveData },
      configurable: true,
      writable: true,
    })
  }

  afterEach(() => {
    Reflect.deleteProperty(navigator, 'connection')
  })

  it('builds the map with no live background sources when Data Saver is on', async () => {
    setSaveData(true)
    returningHiker()
    withDownloadedArchive()
    render(<App />)

    const sources = Object.keys(styleOf(await liveMap()).sources)

    expect(sources).not.toContain('osm')
    expect(sources).not.toContain('dem')
    expect(sources).not.toContain('contours')
  })

  it('still draws the downloaded archive and the trail, which is the point', async () => {
    // Respecting Data Saver must cost the background and nothing else - a
    // hiker who saves data has not asked to lose the map.
    setSaveData(true)
    returningHiker()
    withDownloadedArchive()
    render(<App />)

    const sources = Object.keys(styleOf(await liveMap()).sources)

    expect(sources).toContain('usgs-topo')
    expect(sources).toContain('trails')
  })

  it('fetches the live sheet by default when Data Saver is off', async () => {
    setSaveData(false)
    returningHiker()
    render(<App />)

    expect(Object.keys(styleOf(await liveMap()).sources)).toContain('osm')
  })

  it('tells the hiker on the map screen that Data Saver took the live sheet', async () => {
    // The cases above prove the sources are subtracted and said nothing about
    // whether anyone is told. lib/dataSaver.ts's rule is that the app may
    // override a preference and may not do it silently, and the map screen is
    // where the override is actually visible: for someone who has downloaded
    // nothing, it is the entire background.
    setSaveData(true)
    returningHiker()
    withDownloadedArchive()
    render(<App />)
    await liveMap()

    expect(screen.getByText(/data saver/i)).toBeInTheDocument()
  })

  it('draws the live sheet anyway when Data Saver is on and nothing is downloaded', async () => {
    // The reported bug, at the level the hiker meets it. "Downloaded only"
    // with no download is not a cheaper map, it is no map - the archive source
    // resolves to nothing and the live layers were never added, so the whole
    // screen is the paper backdrop. Both overrides wait for a download.
    setSaveData(true)
    returningHiker()
    render(<App />)

    expect(Object.keys(styleOf(await liveMap()).sources)).toContain('osm')
  })

  it('draws the live sheet when the hiker picked downloaded-only and has no download', async () => {
    setSaveData(false)
    store.set(PREFERENCES_KEY, {
      ...DEFAULT_PREFERENCES,
      background_source: 'usgs_topo_offline',
      onboarding_completed: true,
      download_choice_made: true,
    })
    render(<App />)

    expect(Object.keys(styleOf(await liveMap()).sources)).toContain('osm')
    expect(screen.getByText(/nothing downloaded yet/i)).toBeInTheDocument()
  })

  it('honours downloaded-only once the download is actually there', async () => {
    // The other side of the rule, and what keeps it a fallback rather than a
    // silent reversal of the setting.
    setSaveData(false)
    store.set(PREFERENCES_KEY, {
      ...DEFAULT_PREFERENCES,
      background_source: 'usgs_topo_offline',
      onboarding_completed: true,
      download_choice_made: true,
    })
    withDownloadedArchive()
    render(<App />)

    expect(Object.keys(styleOf(await liveMap()).sources)).not.toContain('osm')
  })
  it('keeps the tab bar reachable when the map screen throws', async () => {
    // #131 in miniature, and what #141 is about. A throw anywhere under the
    // root - render, effect, or effect CLEANUP - unmounts the WHOLE tree by
    // default, tab bar included. The hiker got a white page with no navigation
    // on it, and the reported symptom was "the download tab shows nothing".
    //
    // The map is the likeliest thing here to throw and the worst to lose, so
    // it has its own boundary: the map goes, the tabs stay.
    const user = userEvent.setup()
    returningHiker()
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const MapLibre = await import('maplibre-gl')
    vi.spyOn(MapLibre, 'Map').mockImplementation(() => {
      throw new Error('WebGL context could not be created')
    })

    render(<App />)

    // Something is on screen, and it says which screen went.
    expect(await screen.findByRole('alert')).toHaveTextContent(/map stopped working/i)
    // And the way out is still there, which is the whole point.
    await user.click(screen.getByRole('tab', { name: 'Downloads' }))
    expect(await screen.findByText('Offline map')).toBeInTheDocument()
  })
})
