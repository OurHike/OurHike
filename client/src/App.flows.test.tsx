import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { get, set, del } from 'idb-keyval'
import App from './App'
import { PREFERENCES_KEY } from './lib/preferences'
import { DEFAULT_PREFERENCES } from './lib/userPreferences'
import { ELEVATION_STORE_KEY, POIS_KEY, TRAILS_BLOB_KEY } from './lib/trailData'
import { CORRIDOR_ARCHIVE_KEY } from './map/pmtilesSource'
import { readArchive, segmentKeyFor } from './lib/archiveStore'
import { POI_ID_PROPERTY, POI_LAYER_ID } from './map/poiLayers'
import { archiveUrl } from './lib/config'
import { MockMap, resetMapLibreMock } from './test/mocks/maplibre-gl'
import { liveMap } from './test/liveMap'
import { THEME_ATTRIBUTE } from './lib/theme'
import { BACKDROP_LAYER_ID, MAP_BACKDROP } from './map/style'
import { SHEET_VARIANTS } from './map/liveTopo'

/** The colour the backdrop layer was BUILT with, off the style the mock map
 *  was constructed from - which is the only half of the theme a screen that
 *  unmounts the canvas can be asked about. */
function backdropOf(map: MockMap): unknown {
  const style = map.options.style as { layers: Array<Record<string, never>> }
  const backdrop = style.layers.find((l) => l.id === (BACKDROP_LAYER_ID as never))
  return (backdrop?.paint as Record<string, unknown> | undefined)?.['background-color']
}

// App.test.tsx covers the shell: which screen you land on and what it says
// before any data exists. This covers what happens once data and a GPS fix DO
// exist - the paths a hiker is actually on for the length of a hike, and the
// ones that only run after a download succeeds.

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({ get: vi.fn(), set: vi.fn(), del: vi.fn() }))

const store = new Map<string, unknown>()

/** A centerline running due north, so a mile of latitude is about a mile. */
const MILE_LAT = 1 / 69.05
const TRAILS_GEOJSON = JSON.stringify({
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { source: 'centerline' },
      geometry: {
        type: 'LineString',
        coordinates: Array.from({ length: 40 }, (_, i) => [-77, 39 + i * MILE_LAT]),
      },
    },
  ],
})

const SHELTER = {
  id: 'atc_shelters:abc',
  type: 'shelter',
  name: 'Chairback Gap Lean-to',
  lat: 39 + 5 * MILE_LAT,
  lon: -77,
  confidence: 'high' as const,
  source: 'atc_shelters',
}

let watchSuccess: ((position: GeolocationPosition) => void) | undefined

beforeEach(() => {
  store.clear()
  watchSuccess = undefined
  resetMapLibreMock()

  vi.mocked(get).mockImplementation((key) => Promise.resolve(store.get(key as string)))
  vi.mocked(set).mockImplementation((key, value) => {
    store.set(key as string, value)
    return Promise.resolve()
  })
  vi.mocked(del).mockImplementation((key) => {
    store.delete(key as string)
    return Promise.resolve()
  })

  vi.stubGlobal('fetch', vi.fn())
  vi.stubGlobal('navigator', {
    geolocation: {
      watchPosition: (success: (position: GeolocationPosition) => void) => {
        watchSuccess = success
        return 1
      },
      clearWatch: () => {},
    },
    userAgent: '',
    platform: '',
  })
  // jsdom implements neither, and App revokes/creates one per trail-data load.
  vi.stubGlobal('URL', {
    ...URL,
    createObjectURL: vi.fn(() => 'blob:trails'),
    revokeObjectURL: vi.fn(),
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

/** Onboarded, location allowed, trail data already on the phone. */
function hikerOnTrail(overrides: Record<string, unknown> = {}) {
  store.set(PREFERENCES_KEY, {
    ...DEFAULT_PREFERENCES,
    onboarding_completed: true,
    download_choice_made: true,
    location_permission_requested: true,
    ...overrides,
  })
  store.set(TRAILS_BLOB_KEY, new Blob([TRAILS_GEOJSON]))
  store.set(POIS_KEY, [SHELTER])
}

/**
 * Report a GPS fix five miles up the synthetic centerline.
 *
 * Waits for the watch to exist first, and that is not defensive padding. The
 * watch starts in an effect that runs only once loaded preferences say
 * location is allowed - a commit or two AFTER the map screen appears - so
 * firing straight after `findByRole` sometimes found `watchSuccess` still
 * undefined. The optional call then swallowed the fix, no further fix was ever
 * sent, and the test failed looking for a mile that was never going to arrive.
 */
async function reportFix(lat = 39 + 5 * MILE_LAT, lon = -77) {
  await waitFor(() => expect(watchSuccess).toBeDefined())
  await act(async () => {
    watchSuccess?.({
      coords: { latitude: lat, longitude: lon, accuracy: 5 },
      timestamp: Date.now(),
    } as unknown as GeolocationPosition)
  })
}

/**
 * The download window, opened the way a hiker reaches it.
 *
 * There is no Downloads tab (chrome/tabs.ts): the door is the link at the foot
 * of the legend, which is where the map screen keeps it.
 */
async function openDownloads(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('button', { name: /legend/i }))
  await user.click(await screen.findByRole('button', { name: /download/i }))
  return screen.findByRole('dialog', { name: /offline map/i })
}

/**
 * The USGS sheet's card, behind its own tab in the download window (#298).
 *
 * The sheets are tabs rather than a stack, so the card a test wants is not on
 * screen until its tab is chosen - which is exactly what a hiker does.
 */
async function usgsSheetCard(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('tab', { name: /usgs sheet/i }))
  return screen.findByRole('region', { name: /usgs sheet/i })
}

describe('once there is a GPS fix', () => {
  it('shows the mile instead of still looking for GPS', async () => {
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()

    expect(await screen.findByText(/mi 5\./)).toBeInTheDocument()
  })

  // The mile assertions are what make this test mean anything: they prove each
  // fix arrived and was used, so a run with an unmoved camera cannot be a run
  // where no fix ever showed up.
  it('leaves the camera on the whole corridor, since the view belongs to the hiker', async () => {
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    // Wait for the map itself, not just its container div: findByRole resolves
    // a commit before MapView's effect constructs the map, so reading
    // instances[0] straight after it races the build and can find nothing at
    // all. That would fail as a TypeError rather than as the assertion.
    await waitFor(() => expect(MockMap.instances.length).toBeGreaterThan(0))

    await reportFix()
    expect(await screen.findByText(/mi 5\./)).toBeInTheDocument()

    await reportFix(39 + 6 * MILE_LAT)
    expect(await screen.findByText(/mi 6\./)).toBeInTheDocument()

    expect(MockMap.instances[0].cameraMoves).toHaveLength(0)
  })

  it('starts tracking a direction of travel once it has two fixes', async () => {
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix(39 + 5 * MILE_LAT)
    await reportFix(39 + 8 * MILE_LAT)

    expect(await screen.findByText(/mi 8\./)).toBeInTheDocument()
  })
})

describe('search, with a real index behind it', () => {
  it('jumps the map to the result that was picked', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('button', { name: /search/i }))
    await user.type(
      await screen.findByRole('searchbox', { name: /search the downloaded map/i }),
      'chairback',
    )
    await user.click(await screen.findByText('Chairback Gap Lean-to'))

    // Centre AND zoom: from the opening view of the whole corridor, centring
    // alone moves the map a few pixels and looks like nothing happened.
    await waitFor(() =>
      expect(MockMap.instances[0].cameraMoves).toContainEqual(
        expect.objectContaining({ center: [SHELTER.lon, SHELTER.lat] }),
      ),
    )
    const jump = MockMap.instances[0].cameraMoves.find(
      (move) => Array.isArray(move.center) && move.center[0] === SHELTER.lon,
    )
    expect(jump?.zoom).toBeGreaterThanOrEqual(14)
  })

  it('shows the mile alongside a result once the index exists', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('button', { name: /search/i }))
    await user.type(
      await screen.findByRole('searchbox', { name: /search the downloaded map/i }),
      'chairback',
    )

    expect(await screen.findByText(/Shelter · mi 5\./)).toBeInTheDocument()
  })

  it('closes without moving the map when the search is cancelled', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('button', { name: /search/i }))
    await user.click(await screen.findByRole('button', { name: /cancel/i }))

    expect(
      screen.queryByRole('searchbox', { name: /search the downloaded map/i }),
    ).not.toBeInTheDocument()
  })
})

describe('the legend', () => {
  it('opens and closes', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('button', { name: /legend/i }))
    const legend = await screen.findByRole('dialog', { name: /legend/i })

    await user.click(within(legend).getByRole('button', { name: /close|done/i }))

    expect(screen.queryByRole('dialog', { name: /legend/i })).not.toBeInTheDocument()
  })

  it('hides a type when it is toggled off, and shows it again when toggled back', async () => {
    // Found by pressed state rather than by name. The control used to be a dot
    // labelled "Hide Water"; since #572 the row itself is the button, and a
    // category is on or off according to whether it reports itself pressed.
    //
    // The version this replaces looked the button up by /hide|show/, read an
    // `aria-label` that control never had, and then asserted no button was
    // named `''` - which was true before the click as well. It could not fail.
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('button', { name: /legend/i }))
    const legend = await screen.findByRole('dialog', { name: /legend/i })

    // queryAll, not getAll: this fixture puts one category in the viewport, so
    // the count after the click is legitimately zero and getAll would throw
    // rather than report it.
    const shown = () => within(legend).queryAllByRole('button', { pressed: true })
    const before = shown().length
    expect(before).toBeGreaterThan(0)

    await user.click(shown()[0])

    expect(shown()).toHaveLength(before - 1)
    // Still on screen, still counted - hiding a category takes its pins off
    // the map without taking the row out of the legend, which is the only
    // thing left to turn it back on with.
    expect(within(legend).getAllByRole('button', { pressed: false })).toHaveLength(1)

    // Toggling back is the half that a Set-based toggle gets wrong if it only
    // ever adds.
    await user.click(within(legend).getByRole('button', { pressed: false }))

    expect(shown()).toHaveLength(before)
  })
})

describe('tapping a pin on the map', () => {
  /**
   * Touch the canvas where MapLibre would report a pin.
   *
   * The map is real code with a mock MapLibre under it, so the pin has to be
   * put where a rendered-feature query will find it - which is what the live
   * map's own tile rendering does for a real one.
   */
  async function tapPin(properties: Record<string, unknown>) {
    // The LIVE map, and only once it is listening. The map screen builds a new
    // map when the trail lines land - a different object URL is a different
    // style - so the first map constructed is routinely one that has already
    // been torn down, and touching it would be touching nothing.
    await waitFor(() => {
      expect(MockMap.live).toHaveLength(1)
      expect(MockMap.live[0].listenerCount('click')).toBeGreaterThan(0)
    })
    const map = MockMap.live[0]
    map.renderedFeatures.set(POI_LAYER_ID, [{ properties }])
    await act(async () => {
      map.emit('click', { point: { x: 160, y: 300 } })
    })
  }

  it('opens the waypoint’s details, which used to do nothing at all', async () => {
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })

    const sheet = await screen.findByRole('dialog', { name: /waypoint/i })
    expect(
      within(sheet).getByRole('heading', { name: 'Chairback Gap Lean-to' }),
    ).toBeInTheDocument()
    expect(within(sheet).getByText('Shelter')).toBeInTheDocument()
  })

  it('reaches the shelter’s privy, which has no pin of its own to tap', async () => {
    // The whole of #526 end to end, and the reason it is a shell test rather
    // than a card one: the card is handed a single waypoint, and the shell is
    // the only layer holding the others. Since #524 gave the site one pin there
    // is nothing on the canvas to aim at for the privy, so if this row is not
    // wired through, no gesture in the app reaches it at all.
    const user = userEvent.setup()
    hikerOnTrail()
    store.set(POIS_KEY, [
      { ...SHELTER, siteId: 'site_abc', siteRole: 'anchor' },
      {
        id: 'atc_privies:xyz',
        type: 'privy',
        name: 'Chairback Gap Privy',
        // 0.00036 degrees of latitude is 40 m by the pipeline's own constant,
        // which the chip says as 131 ft - the units this hiker has, since
        // DEFAULT_PREFERENCES starts at the ones the trail is signed in.
        lat: SHELTER.lat + 0.00036,
        lon: SHELTER.lon,
        confidence: 'low' as const,
        source: 'atc_privies',
        siteId: 'site_abc',
        siteRole: 'member',
      },
    ])
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })
    const card = await screen.findByRole('dialog', { name: /waypoint/i })

    // Both parts of the place, named as the site they belong to.
    const strip = within(card).getByRole('group', {
      name: 'Parts of Chairback Gap Lean-to',
    })
    expect(within(strip).getAllByRole('button')).toHaveLength(2)

    await user.click(within(strip).getByRole('button', { name: 'Privy 131 ft' }))

    expect(
      within(card).getByRole('heading', { name: 'Chairback Gap Privy' }),
    ).toBeInTheDocument()
    expect(within(card).getByText(/privy data/)).toBeInTheDocument()
    // And its mile, which is the card's headline fact and the only line saying
    // where along the A.T. this thing is. The privy arrives from IndexedDB as a
    // StoredPoi with no mile on it - the number comes from the same
    // locateOnTrail() call search paid for, through App's `cardDetail` - so the
    // natural wrong wiring is to hand the card the raw roster, and the privy then
    // silently loses its position on the trail. This is the only place that
    // wiring exists to be tested.
    expect(within(card).getByText(/^mi 5\.0$/)).toBeInTheDocument()
  })

  it('says how far the parts are in the units they chose in Settings (#625)', async () => {
    // The bug as it was reported: "I've selected ft, but everything still
    // shows in meters". The chips were the app's one exempt line and the
    // sentence above them was published prose, so this card answered in metres
    // whatever the hiker had chosen - and it is the only card that did.
    //
    // Both halves, in one assertion pass, because the reason neither could move
    // alone was that they print the same distances: `Privy · 131 ft` over a
    // sentence saying 40 m would have been worse than either unit alone.
    const metricHiker = { ...SHELTER, siteId: 'site_abc', siteRole: 'anchor' }
    hikerOnTrail({ unit_system: 'metric' })
    store.set(POIS_KEY, [
      {
        ...metricHiker,
        // What export_poi.py publishes for a privy 0.00036° of latitude away.
        nearby: [{ phrase: 'a multi-seat moldering privy', distance_ft: 131.48 }],
      },
      {
        id: 'atc_privies:xyz',
        type: 'privy',
        name: 'Chairback Gap Privy',
        lat: SHELTER.lat + 0.00036,
        lon: SHELTER.lon,
        confidence: 'low' as const,
        siteId: 'site_abc',
        siteRole: 'member',
      },
    ])
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })
    const card = await screen.findByRole('dialog', { name: /waypoint/i })

    expect(within(card).getByRole('button', { name: 'Privy 40 m' })).toBeInTheDocument()
    expect(
      within(card).getByText('Nearby: a multi-seat moldering privy 40 m away.'),
    ).toBeInTheDocument()
  })

  it('places the waypoint on the trail, at the mile search would give it', async () => {
    // One number from one computation. A second way of working out the mile
    // could disagree with search about the same shelter, which is exactly the
    // kind of quiet contradiction OurHikeValues.md #4 is about.
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })

    const sheet = await screen.findByRole('dialog', { name: /waypoint/i })
    expect(within(sheet).getByText(/^mi 5\./)).toBeInTheDocument()
  })

  it('says which source listed it', async () => {
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })

    const sheet = await screen.findByRole('dialog', { name: /waypoint/i })
    expect(within(sheet).getByText(/Appalachian Trail Conservancy/)).toBeInTheDocument()
  })

  it('closes again', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })
    const sheet = await screen.findByRole('dialog', { name: /waypoint/i })
    await user.click(within(sheet).getByRole('button', { name: /close/i }))

    expect(screen.queryByRole('dialog', { name: /waypoint/i })).not.toBeInTheDocument()
  })

  it('goes away on a tap on bare map, without hunting for the close button', async () => {
    // The card floats beside its pin, so it dismisses the way every floating
    // map card does: tap anywhere else. Only a TAP - MapLibre withholds the
    // click event when the gesture was a pan, so riding the map around with
    // the card open keeps it.
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })
    await screen.findByRole('dialog', { name: /waypoint/i })

    const map = await liveMap()
    map.renderedFeatures.set(POI_LAYER_ID, [])
    await act(async () => {
      map.emit('click', { point: { x: 40, y: 60 } })
    })

    expect(screen.queryByRole('dialog', { name: /waypoint/i })).not.toBeInTheDocument()
  })

  it('ignores a tap on a pin the app no longer holds', async () => {
    // A stale tile can name a POI that a re-download has since dropped. An
    // empty sheet would be worse than no sheet.
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: 'atc_shelters:gone', poi_type: 'shelter' })

    expect(screen.queryByRole('dialog', { name: /waypoint/i })).not.toBeInTheDocument()
  })

  it('replaces the legend rather than stacking on it', async () => {
    // Both sit at the bottom of the map. Two at once leaves the lower one
    // unreadable and its close button unreachable.
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('button', { name: /legend/i }))
    await screen.findByRole('dialog', { name: /legend/i })
    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })

    expect(await screen.findByRole('dialog', { name: /waypoint/i })).toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: /legend/i })).not.toBeInTheDocument()
  })

  it('gets out of the way when the legend is opened over it', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })
    await screen.findByRole('dialog', { name: /waypoint/i })
    await user.click(screen.getByRole('button', { name: /legend/i }))

    expect(await screen.findByRole('dialog', { name: /legend/i })).toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: /waypoint/i })).not.toBeInTheDocument()
  })
})

describe('downloading everything', () => {
  function servesEverything() {
    vi.mocked(fetch).mockImplementation((url) =>
      Promise.resolve({
        ok: true,
        status: 200,
        statusText: 'OK',
        blob: () => Promise.resolve(new Blob([TRAILS_GEOJSON])),
        // The vector artifacts are hashed before they are stored (#197), so
        // the double has to answer with bytes as well as with text.
        arrayBuffer: () =>
          Promise.resolve(
            new TextEncoder().encode(
              String(url).includes('poi_shelter')
                ? JSON.stringify({
                    type: 'FeatureCollection',
                    features: [
                      {
                        type: 'Feature',
                        properties: {
                          id: SHELTER.id,
                          name: SHELTER.name,
                          confidence: 'high',
                        },
                        geometry: {
                          type: 'Point',
                          coordinates: [SHELTER.lon, SHELTER.lat],
                        },
                      },
                    ],
                  })
                : String(url).includes('trails')
                  ? TRAILS_GEOJSON
                  : JSON.stringify({ type: 'FeatureCollection', features: [] }),
            ).buffer,
          ),
        text: () =>
          Promise.resolve(
            String(url).includes('poi_shelter')
              ? JSON.stringify({
                  type: 'FeatureCollection',
                  features: [
                    {
                      type: 'Feature',
                      properties: {
                        id: SHELTER.id,
                        name: SHELTER.name,
                        confidence: 'high',
                      },
                      geometry: {
                        type: 'Point',
                        coordinates: [SHELTER.lon, SHELTER.lat],
                      },
                    },
                  ],
                })
              : JSON.stringify({ type: 'FeatureCollection', features: [] }),
          ),
        headers: new Headers({ 'content-length': '3' }),
        body: new ReadableStream({
          start(controller) {
            controller.enqueue(new Uint8Array([1, 2, 3]))
            controller.close()
          },
        }),
      } as unknown as Response),
    )
  }

  it('fetches the trail data and then the archive, in that order', async () => {
    const user = userEvent.setup()
    store.set(PREFERENCES_KEY, {
      ...DEFAULT_PREFERENCES,
      onboarding_completed: true,
      download_choice_made: true,
    })
    servesEverything()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await openDownloads(user)
    // The USGS card, named: two sheets each have a download button now (#237).
    const usgsCard = await usgsSheetCard(user)
    await user.click(within(usgsCard).getByRole('button', { name: /download the map/i }))

    await waitFor(() => expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob))
    // Read through the accessor the map uses: since #553 a finished archive is a
    // run of segment records named by a completion marker, not one record.
    await waitFor(async () =>
      expect(await readArchive(CORRIDOR_ARCHIVE_KEY)).toBeInstanceOf(Blob),
    )
  })

  it('deletes the background and keeps the trail (#192)', async () => {
    // Someone reclaiming space is reclaiming the BACKGROUND - that is what
    // the hundreds of megabytes are, and what they chose. The centerline and
    // the POIs are a rounding error beside it, they are what makes this an
    // app rather than a map viewer, and they are downloaded by default
    // wherever they are missing - so taking them would blank the trail line
    // until the next launch with signal fetched them straight back.
    const user = userEvent.setup()
    hikerOnTrail()
    store.set(CORRIDOR_ARCHIVE_KEY, new Blob(['archive']))
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await openDownloads(user)
    const usgsCard = await usgsSheetCard(user)
    await user.click(within(usgsCard).getByRole('button', { name: /delete the map/i }))
    await user.click(within(usgsCard).getByRole('button', { name: /yes, delete it/i }))

    await waitFor(() => expect(store.has(CORRIDOR_ARCHIVE_KEY)).toBe(false))
    expect(store.has(TRAILS_BLOB_KEY)).toBe(true)
    expect(store.has(POIS_KEY)).toBe(true)
  })

  it('records a new detail level as a max background zoom', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await openDownloads(user)
    // The levels live on the sheet that has them - the USGS raster. One
    // stored level all the same: max_background_zoom is what the next
    // download is fetched at.
    await usgsSheetCard(user)
    await user.click(await screen.findByRole('radio', { name: /light/i }))

    await waitFor(() => {
      const saved = store.get(PREFERENCES_KEY) as { max_background_zoom: number }
      expect(saved.max_background_zoom).toBe(11)
    })
  })
})

describe('reporting, with a fix to attach', () => {
  it('files the report at the position the hiker is actually standing', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await reportFix()

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))
    await user.click(await screen.findByRole('button', { name: /blow down/i }))
    await user.click(await screen.findByRole('button', { name: /send|save to outbox/i }))

    await waitFor(() => {
      const queued = store.get('ourhike:outbox') as Array<{
        payload: { lat?: number; lon?: number }
      }>
      expect(queued).toHaveLength(1)
      expect(queued[0].payload.lat).toBeCloseTo(SHELTER.lat, 4)
      expect(queued[0].payload.lon).toBeCloseTo(SHELTER.lon, 4)
    })
  })

  it('drops the draft and returns to the tab it came from when cancelled', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))
    await user.click(await screen.findByRole('button', { name: /blow down/i }))
    await user.click(await screen.findByRole('button', { name: /^cancel$/i }))

    expect(await screen.findByRole('heading', { name: 'You' })).toBeInTheDocument()
    expect(store.get('ourhike:outbox')).toBeUndefined()
  })

  it('counts what is waiting in the outbox', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))
    await user.click(await screen.findByRole('button', { name: /blow down/i }))
    await user.click(await screen.findByRole('button', { name: /send|save to outbox/i }))

    // Saving now hands over to the sign-in step (lib/contributionFlow.ts's
    // stepAfterSaving). Declining it is the path this test cares about: the
    // count has to be the same either way, because the report was already
    // written before anyone was asked to authenticate.
    await user.click(await screen.findByRole('button', { name: /not now/i }))

    expect(await screen.findByText(/1 .*(waiting|queued|outbox)/i)).toBeInTheDocument()
  })

  it('saves the report even when sign-in is declined', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))
    await user.click(await screen.findByRole('button', { name: /blow down/i }))
    await user.click(await screen.findByRole('button', { name: /send|save to outbox/i }))
    await user.click(await screen.findByRole('button', { name: /not now/i }))

    // The promise the whole flow exists to keep: someone who cannot or will
    // not authenticate still has what they wrote.
    await waitFor(() => {
      expect(store.get('ourhike:outbox')).toBeDefined()
    })
  })

  it('asks to sign in only after the report is already saved', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))
    await user.click(await screen.findByRole('button', { name: /blow down/i }))
    await user.click(await screen.findByRole('button', { name: /send|save to outbox/i }))

    // Ordering is the design, not a detail - the screen says the report is
    // already saved, and it has to be true when it says it.
    expect(await screen.findByText(/already saved/i)).toBeInTheDocument()
    expect(store.get('ourhike:outbox')).toBeDefined()
  })
})

describe('preferences from the More screen', () => {
  it('saves a changed setting straight away, with no explicit save step', async () => {
    // The theme is the vehicle here because it is a live control. This test
    // used to flip the wrong-way alert toggle, which is now marked Later and
    // disabled like its neighbours - nothing implements the alert yet, and a
    // live-looking safety switch that armed nothing was worse than none.
    const user = userEvent.setup()
    hikerOnTrail({ theme: 'light' })
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('radio', { name: /dark/i }))

    await waitFor(() => {
      const saved = store.get(PREFERENCES_KEY) as { theme: string }
      expect(saved.theme).toBe('dark')
    })
  })

  it('takes the whole app dark from the theme control, map included', async () => {
    // The end-to-end shape of the feature: one tap writes the preference, the
    // chrome follows the attribute the design tokens key their dark block off,
    // and the canvas - which is WebGL and cannot read a CSS variable - is
    // built in the same theme rather than staying paper-white inside a dark
    // app.
    //
    // The map is unmounted while More is showing (it is a different screen,
    // not a hidden one), so what this can observe on the way back is the style
    // the canvas was built with. That a theme change on a LIVE map repaints in
    // place instead of rebuilding is map/style.test.ts's attachMapAppearance block.
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    expect(document.documentElement.getAttribute(THEME_ATTRIBUTE)).toBe('light')
    // Waited on, exactly like the dark read at the end of this test. The map
    // is built in an effect that runs a commit AFTER the container div lands,
    // so `MockMap.live[0]` here was a race: one of the two reads in this test
    // was wrapped and the other was not, and this is the one that failed
    // under a full-suite run (#331).
    expect(backdropOf(await liveMap())).toBe(MAP_BACKDROP.light)

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('radio', { name: /dark/i }))

    await waitFor(() => {
      const saved = store.get(PREFERENCES_KEY) as { theme: string }
      expect(saved.theme).toBe('dark')
    })
    expect(document.documentElement.getAttribute(THEME_ATTRIBUTE)).toBe('dark')

    await user.click(screen.getByRole('tab', { name: 'Trail' }))
    await screen.findByRole('region', { name: /trail map/i })

    // Waited on the built style rather than on a tick: the map is constructed
    // inside an effect, so what proves the sequence completed is a live map
    // carrying the dark backdrop, not time passing. Field/night's backdrop
    // specifically: dark CHOSEN from the control reaches field's own night
    // sheet, where an auto theme resolving dark would land on night_hike -
    // liveTopo.ts's sheetVariant owns that distinction.
    await waitFor(() => {
      expect(MockMap.live.length).toBeGreaterThan(0)
      expect(backdropOf(MockMap.live[0])).toBe(SHEET_VARIANTS.field.night.backdrop)
    })
  })
})

describe('the placeholder actions on More', () => {
  // Sync and export are wired to no-ops today: the backend they need is Phase
  // 2 (ROADMAP.md). Rendered and clickable anyway so the shape of the screen
  // is real, and asserted here so a wiring mistake shows up as a failing test
  // rather than as a button that throws in someone's hand.
  //
  // Sign in used to be in this list and is not a placeholder any more, which
  // is what the sign-in tests below cover instead.
  it.each([/^sync$/i, /export gpx/i, /export geojson/i])(
    'does not throw when %s is tapped',
    async (name) => {
      const user = userEvent.setup()
      hikerOnTrail()
      render(<App />)
      await screen.findByRole('region', { name: /trail map/i })
      await user.click(screen.getByRole('tab', { name: 'More' }))

      await user.click(await screen.findByRole('button', { name }))

      expect(await screen.findByRole('heading', { name: 'You' })).toBeInTheDocument()
    },
  )
})

describe('signing in from Settings', () => {
  it('opens the sign-in screen', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))

    await user.click(await screen.findByRole('button', { name: /sign in/i }))

    expect(
      await screen.findByRole('button', { name: /continue with google/i }),
    ).toBeInTheDocument()
  })

  it('does not claim a report is saved, because this path has no report', async () => {
    // The same screen serves the contribution flow, where "your report is
    // already saved" is both true and the point. Reached from Settings there
    // is nothing saved, and saying so would be a promise about something that
    // does not exist.
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))

    await user.click(await screen.findByRole('button', { name: /sign in/i }))
    await screen.findByRole('button', { name: /continue with google/i })

    expect(screen.queryByText(/already saved/i)).toBe(null)
  })

  it('backs out to the screen it came from', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))

    await user.click(await screen.findByRole('button', { name: /sign in/i }))
    await user.click(await screen.findByRole('button', { name: /not now/i }))

    expect(await screen.findByRole('heading', { name: 'You' })).toBeInTheDocument()
  })

  it('offers only the providers this build has credentials for', async () => {
    // ENABLED_PROVIDERS defaults to Google and email. Apple needs a $99/yr
    // membership, and a button for a provider with no credentials behind it
    // reaches an error page rather than an account.
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))

    await user.click(await screen.findByRole('button', { name: /sign in/i }))
    await screen.findByRole('button', { name: /continue with google/i })

    expect(
      screen.getByRole('button', { name: /continue with email/i }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /continue with apple/i })).toBe(null)
  })

  it('reaches the email form, which asks only for an address', async () => {
    // The link is the default way in: one field, and nothing to remember.
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))

    await user.click(await screen.findByRole('button', { name: /sign in/i }))
    await user.click(await screen.findByRole('button', { name: /continue with email/i }))

    expect(await screen.findByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/password/i)).toBe(null)
  })

  it('still offers a password, for someone who would rather not leave the app', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))

    await user.click(await screen.findByRole('button', { name: /sign in/i }))
    await user.click(await screen.findByRole('button', { name: /continue with email/i }))
    await user.click(
      await screen.findByRole('button', { name: /use a password instead/i }),
    )

    expect(await screen.findByLabelText(/password/i)).toBeInTheDocument()
  })
})

describe('when the trail data cannot be downloaded', () => {
  it('says so even when what failed was not an Error', async () => {
    // fetch can reject with anything at all, and a rejection this code cannot
    // read the message off still has to produce a sentence rather than
    // "undefined" or a blank alert.
    //
    // It used to produce exactly one sentence for every such rejection -
    // "Trail data failed to download." - which said nothing about which of the
    // eight requests died. lib/trailData.ts now names the artifact and carries
    // whatever the rejection stringifies to, so even a thrown string arrives
    // attached to the file it was thrown for. This build has no bucket
    // configured, so the host is described rather than named: printing this
    // app's own origin would name the one host that is certainly not at fault.
    const user = userEvent.setup()
    store.set(PREFERENCES_KEY, {
      ...DEFAULT_PREFERENCES,
      onboarding_completed: true,
      download_choice_made: true,
    })
    vi.mocked(fetch).mockRejectedValue('the network went away')
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await openDownloads(user)
    const usgsCard = await usgsSheetCard(user)
    await user.click(within(usgsCard).getByRole('button', { name: /download the map/i }))

    const notice = await screen.findByText(/could not be fetched/i)
    expect(notice).toHaveTextContent(/trails\.geojson/)
    expect(notice).toHaveTextContent(/the network went away/)
    expect(notice).toHaveTextContent(/the data source/)
  })
})

describe('a download left running', () => {
  it('is still visible from the map after its window is shut', async () => {
    // The download belongs to the shell, not to the window it was started
    // from, so shutting that window used to leave an app that looked
    // completely idle while it pulled several hundred megabytes over a
    // connection somebody is paying for by the mile. The only way to find out
    // was to open the window again and hope.
    //
    // Driven through the real transfer rather than by handing the legend a
    // prop, because the wiring is the part that was missing: every piece of
    // this existed except the line joining them.
    const user = userEvent.setup()
    hikerOnTrail()

    // A body that arrives and then simply does not end - which is what a
    // download in progress IS. Held open deliberately: a stream that closes
    // races the assertions to 'downloaded', and the state under test would be
    // gone before anything could look at it.
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 200,
      statusText: 'OK',
      headers: new Headers({ 'content-length': '10' }),
      body: new ReadableStream({
        start(controller) {
          controller.enqueue(new Uint8Array([1, 2, 3, 4]))
        },
      }),
    } as unknown as Response)

    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await openDownloads(user)
    const usgsCard = await usgsSheetCard(user)
    await user.click(within(usgsCard).getByRole('button', { name: /download the map/i }))

    // The window's own bar first: proof the transfer really is running, so
    // that what the footer says next is a report and not a coincidence.
    await waitFor(() =>
      expect(within(usgsCard).getByRole('progressbar')).toHaveAttribute(
        'aria-valuenow',
        '40',
      ),
    )

    // Away: window shut, back to the map, legend open again - the walk a
    // hiker actually takes.
    await user.click(screen.getByRole('button', { name: /close/i }))
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: /offline map/i })).toBeNull(),
    )
    await user.click(screen.getByRole('button', { name: /legend/i }))

    const legend = await screen.findByRole('dialog', { name: 'Legend' })
    expect(within(legend).getByText('Downloading 40%')).toBeVisible()
  })
})

describe('resuming an interrupted download', () => {
  it('picks up where it left off rather than starting again', async () => {
    // WIREFRAMES.md 7a. Re-pulling 300 MB from zero because a connection
    // dropped at 90% is the failure that promise exists to prevent.
    const user = userEvent.setup()
    hikerOnTrail()
    // Held as a segment record - where an interrupted transfer leaves its bytes
    // since #553, checkpointed as they arrived.
    store.set(
      segmentKeyFor(CORRIDOR_ARCHIVE_KEY, 0, 0),
      new Blob([new Uint8Array([1, 2, 3])]),
    )
    store.set('ourhike:corridor-archive:progress', { receivedBytes: 3, totalBytes: 6 })
    // Must be the URL this build would request. VITE_DATA_BASE_URL is unset
    // under test, so that is a bare '/background.pmtiles' - and a partial
    // recorded against any other URL is deliberately discarded, not resumed.
    store.set('ourhike:corridor-archive:source', {
      url: archiveUrl('standard'),
      generation: 0,
      segments: 1,
    })

    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })
    await openDownloads(user)
    const usgsCard = await usgsSheetCard(user)
    const resume = within(usgsCard).getByRole('button', { name: /resume/i })

    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 206,
      statusText: 'Partial Content',
      headers: new Headers({ 'content-length': '3', 'content-range': 'bytes 3-5/6' }),
      body: new ReadableStream({
        start(controller) {
          controller.enqueue(new Uint8Array([4, 5, 6]))
          controller.close()
        },
      }),
    } as unknown as Response)
    await user.click(resume)

    await waitFor(() =>
      expect(vi.mocked(fetch).mock.calls[0][1]).toMatchObject({
        headers: expect.objectContaining({ Range: 'bytes=3-' }),
      }),
    )
  })
})

// WIREFRAMES.md §1.3 and §1.4. Both components were built, tested and accepted
// by MapScreen as optional props long before anything downloaded a profile to
// pass them, so they could never appear on any device in any state. What is
// worth testing here is the wiring and the three conditions it is gated on -
// not the drawing, which ElevationRibbon.test.tsx and WaypointLanes.test.tsx
// already cover.
describe('the elevation ribbon and the waypoint lanes', () => {
  /** Flat to mile 8, a 1,000 ft climb to mile 10, back down by mile 12, flat
   *  to the end of the synthetic centerline. */
  function profileWithAClimb() {
    const miles: number[] = []
    const feet: number[] = []

    for (let mile = 0; mile <= 40; mile += 0.1) {
      const rounded = Number(mile.toFixed(2))
      miles.push(rounded)
      feet.push(
        rounded <= 8
          ? 1000
          : rounded <= 10
            ? 1000 + (rounded - 8) * 500
            : rounded <= 12
              ? 2000 - (rounded - 10) * 500
              : 1000,
      )
    }

    return {
      distanceMi: Float32Array.from(miles),
      elevationFt: Float32Array.from(feet),
    }
  }

  function ribbon() {
    return screen.queryByRole('img', { name: /elevation profile ahead/i })
  }

  it('draws the profile once there is a fix and a profile to draw', async () => {
    hikerOnTrail()
    store.set(ELEVATION_STORE_KEY, profileWithAClimb())
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()

    await waitFor(() => expect(ribbon()).toBeInTheDocument())
  })

  it('draws the three waypoint lanes beside it', async () => {
    hikerOnTrail()
    store.set(ELEVATION_STORE_KEY, profileWithAClimb())
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()

    await waitFor(() => expect(screen.getByTestId('lane-water')).toBeInTheDocument())
    expect(screen.getByTestId('lane-sleep')).toBeInTheDocument()
    expect(screen.getByTestId('lane-else')).toBeInTheDocument()
  })

  it('puts a POI the index can place into its lane', async () => {
    // The shelter sits at mile 5 on the synthetic centerline, inside the window
    // around a hiker standing at mile 5.
    hikerOnTrail()
    store.set(ELEVATION_STORE_KEY, profileWithAClimb())
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()

    await waitFor(() =>
      expect(
        within(screen.getByTestId('lane-sleep')).getByRole('button'),
      ).toBeInTheDocument(),
    )
  })

  it('shows nothing at all before there is a fix', async () => {
    // Without a position there is no "ahead". An empty ribbon would read as
    // "nothing ahead of you", which is a different and much worse claim than
    // not drawing one.
    hikerOnTrail()
    store.set(ELEVATION_STORE_KEY, profileWithAClimb())
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    expect(ribbon()).not.toBeInTheDocument()
    expect(screen.queryByTestId('lane-water')).not.toBeInTheDocument()
  })

  it('shows nothing when the release published no profile', async () => {
    // A data release built before pipeline/export_elevation.py existed. The
    // map still works; the ribbon and the lanes are simply absent.
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()

    await screen.findByText(/mi 5\./)
    expect(ribbon()).not.toBeInTheDocument()
    expect(screen.queryByTestId('lane-water')).not.toBeInTheDocument()
  })

  it('waits for the direction before captioning a climb', async () => {
    // lib/hikeDirection.ts withholds the direction until a quarter mile of
    // movement, and which way someone faces decides which climb is ahead.
    hikerOnTrail()
    store.set(ELEVATION_STORE_KEY, profileWithAClimb())
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()

    await waitFor(() => expect(ribbon()).toBeInTheDocument())
    expect(screen.queryByTestId('climb-callout')).not.toBeInTheDocument()
  })

  it('captions the climb ahead once the direction is known', async () => {
    hikerOnTrail()
    store.set(ELEVATION_STORE_KEY, profileWithAClimb())
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()
    // A mile further north: enough movement for NOBO to be established.
    await reportFix(39 + 6 * MILE_LAT)

    // 1,000 ft between mile 8 and mile 10, and Naismith's duration for it -
    // never an arrival clock.
    expect(await screen.findByTestId('climb-callout')).toHaveTextContent(
      '+1,000 ft · 2.0 mi · ≈1h 10m',
    )
  })
})

describe('a download that finished and cannot be read (#334)', () => {
  /**
   * Fail one of the map's sources, once the map is listening for it.
   *
   * The wait is load-bearing: the map is CONSTRUCTED during the render that
   * puts "trail map" on screen, and MapView's listeners attach on the render
   * after that. An error emitted in between reaches nobody.
   */
  async function sourceFails(sourceId: string) {
    const map = await waitFor(() => {
      const live = MockMap.live[0]
      expect(live?.listenerCount('error')).toBeGreaterThan(0)
      return live!
    })
    act(() => {
      map.emit('error', { sourceId, error: new Error(`${sourceId} unavailable`) })
    })
    return map
  }

  /** The download window reached from the More tab, which is the path that
   *  unmounts the map on the way - see the test below. */
  async function openDownloadsFromMore(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /download/i }))
    return screen.findByRole('dialog', { name: /offline map/i })
  }

  it('tells the Downloads card, even though reaching it unmounts the map', async () => {
    // The whole reason the shell holds this rather than the map screen. A
    // hiker reads "Downloaded map not drawing" on the map, goes looking for
    // the fix, and the only door on the More tab takes the map down on the
    // way - taking the observation with it, if the observation lived there.
    const user = userEvent.setup()
    hikerOnTrail()
    store.set(CORRIDOR_ARCHIVE_KEY, new Blob(['damaged']))
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await sourceFails('usgs-topo')
    expect(await screen.findByText(/downloaded map not drawing/i)).toBeInTheDocument()

    await openDownloadsFromMore(user)
    const usgsCard = await usgsSheetCard(user)

    // The map really is gone by now - otherwise this proves nothing about
    // surviving the teardown.
    expect(MockMap.live).toHaveLength(0)
    expect(within(usgsCard).getByRole('alert')).toHaveTextContent(
      /could not draw from it/i,
    )
  })

  it('says nothing on the card about a source that recovered', async () => {
    // The failure mode of remembering: a source that errors on one tile
    // before anything has drawn and then draws is a working download. Telling
    // that hiker to delete and re-fetch 314 MB would be the same false
    // statement as #314's, pointed the other way.
    const user = userEvent.setup()
    hikerOnTrail()
    store.set(CORRIDOR_ARCHIVE_KEY, new Blob(['fine']))
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    const map = await sourceFails('usgs-topo')
    await screen.findByText(/downloaded map not drawing/i)

    // A tile lands: the archive is being read after all.
    act(() => {
      map.emit('sourcedata', { sourceId: 'usgs-topo', tile: { state: 'loaded' } })
    })
    await waitFor(() =>
      expect(screen.queryByText(/downloaded map not drawing/i)).not.toBeInTheDocument(),
    )

    await openDownloadsFromMore(user)
    const usgsCard = await usgsSheetCard(user)

    expect(within(usgsCard).queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('a remembered failure that stopped being true (#352)', () => {
  // Both halves of the memory, from the hiker's side. #334 shipped one that
  // only ever accumulated: it survived a teardown, which it had to, and
  // nothing could ever lower it again.

  async function sourceFails(sourceId: string) {
    const map = await waitFor(() => {
      const live = MockMap.live[0]
      expect(live?.listenerCount('error')).toBeGreaterThan(0)
      return live!
    })
    act(() => {
      map.emit('error', { sourceId, error: new Error(`${sourceId} unavailable`) })
    })
    return map
  }

  async function openDownloadsFromMore(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /download/i }))
    return screen.findByRole('dialog', { name: /offline map/i })
  }

  it('lets a later, healthy map retract what an earlier one reported', async () => {
    // The shipped bug. A map that only ever SUCCEEDS used to say nothing at
    // all - `report()` fires on change and a healthy map computes the answer
    // it started with - so the flag an earlier map raised was never
    // contradicted. One transient error marked a good 314 MB archive damaged
    // for the rest of the session, on both screens.
    const user = userEvent.setup()
    hikerOnTrail()
    store.set(CORRIDOR_ARCHIVE_KEY, new Blob(['fine']))
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await sourceFails('usgs-topo')
    await screen.findByText(/downloaded map not drawing/i)

    // Away to the More tab and back: the map is torn down and a new one built,
    // which is what used to make this permanent.
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await waitFor(() => expect(MockMap.live).toHaveLength(0))
    await user.click(screen.getByRole('tab', { name: 'Trail' }))

    // The new map reads the archive perfectly.
    const rebuilt = await waitFor(() => {
      const live = MockMap.live[0]
      expect(live?.listenerCount('sourcedata')).toBeGreaterThan(0)
      return live!
    })
    act(() => {
      rebuilt.emit('sourcedata', { sourceId: 'usgs-topo', tile: { state: 'loaded' } })
    })

    await waitFor(() =>
      expect(screen.queryByText(/downloaded map not drawing/i)).not.toBeInTheDocument(),
    )

    await openDownloadsFromMore(user)
    const usgsCard = await usgsSheetCard(user)
    expect(within(usgsCard).queryByRole('alert')).not.toBeInTheDocument()
  })

  it('does not call a resumed download damaged', async () => {
    // The path the download-side clear missed. Nothing downloaded, so the
    // archive source fails for the ordinary reason; the transfer drops; the
    // resume completes byte-correct - and the card announced it as damaged,
    // telling the hiker to spend signal fetching what they already had.
    const user = userEvent.setup()
    hikerOnTrail()
    // Held as a segment record - where an interrupted transfer leaves its bytes
    // since #553, checkpointed as they arrived.
    store.set(
      segmentKeyFor(CORRIDOR_ARCHIVE_KEY, 0, 0),
      new Blob([new Uint8Array([1, 2, 3])]),
    )
    store.set('ourhike:corridor-archive:progress', { receivedBytes: 3, totalBytes: 6 })
    store.set('ourhike:corridor-archive:source', {
      url: archiveUrl('standard'),
      generation: 0,
      segments: 1,
    })
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    // The ordinary, correct failure on a phone whose archive is not there yet.
    await sourceFails('usgs-topo')

    await openDownloads(user)
    const usgsCard = await usgsSheetCard(user)

    // The rest of the archive, arriving clean - the same 206 the resume test
    // above serves.
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 206,
      statusText: 'Partial Content',
      headers: new Headers({ 'content-length': '3', 'content-range': 'bytes 3-5/6' }),
      body: new ReadableStream({
        start(controller) {
          controller.enqueue(new Uint8Array([4, 5, 6]))
          controller.close()
        },
      }),
    } as unknown as Response)
    await user.click(within(usgsCard).getByRole('button', { name: /resume/i }))

    await waitFor(async () =>
      expect(await readArchive(CORRIDOR_ARCHIVE_KEY)).toBeInstanceOf(Blob),
    )
    await waitFor(() =>
      expect(within(usgsCard).queryByRole('alert')).not.toBeInTheDocument(),
    )
  })
})

describe('who a report says it is from (#233)', () => {
  // `reporterType="thru"` was a literal at both call sites, so every report in
  // the moderation queue claimed to be from a thru-hiker - and
  // screens/IdentitySetup.tsx, which collects the real answer, was built,
  // tested, and imported by nothing.

  async function fileAReport(user: ReturnType<typeof userEvent.setup>) {
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))
    await user.click(await screen.findByRole('button', { name: /blow down/i }))
    await user.click(await screen.findByRole('button', { name: /send|save to outbox/i }))
  }

  function queued() {
    return store.get('ourhike:outbox') as Array<{
      payload: { reporter_type?: string }
    }>
  }

  it('does not sign an unanswered report as a thru-hiker', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await fileAReport(user)

    await waitFor(() => expect(queued()).toHaveLength(1))
    expect(queued()[0].payload.reporter_type).not.toBe('thru')
    expect(queued()[0].payload.reporter_type).toBe('day')
  })

  it('signs later reports with what Settings says, not with a literal', async () => {
    // The wiring end to end, without an account: the reporter type is stored
    // on this phone and is what every report carries, signed in or not.
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.selectOptions(
      await screen.findByRole('combobox', { name: /signed as/i }),
      'section',
    )

    await fileAReport(user)

    await waitFor(() => expect(queued()).toHaveLength(1))
    expect(queued()[0].payload.reporter_type).toBe('section')
  })
})
