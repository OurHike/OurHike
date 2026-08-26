import { describe, it, expect, vi } from 'vitest'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { appHarness, centerlineGeoJSON, latOfMile, openMapTab } from './test/appHarness'
import { PREFERENCES_KEY } from './lib/preferences'
import {
  ELEVATION_STORE_KEY,
  POIS_KEY,
  SPURS_STORE_KEY,
  TRAILS_BLOB_KEY,
} from './lib/trailData'
import { CORRIDOR_ARCHIVE_KEY } from './map/pmtilesSource'
import { BASEMAP_PACKAGE } from './lib/packages'
import { readArchive, segmentKeyFor } from './lib/archiveStore'
import { POI_ID_PROPERTY, POI_LAYER_ID } from './map/poiLayers'
import { archiveUrl } from './lib/config'
import { MockMap } from './test/mocks/maplibre-gl'
import { liveMap } from './test/liveMap'
import { THEME_ATTRIBUTE } from './lib/theme'
import { BACKDROP_LAYER_ID, BLAZE_LAYER_ID, MAP_BACKDROP } from './map/style'
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
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  // `trailData.ts` commits a release in ONE transaction since #657, so any
  // double that reaches that path needs this call - without it the whole
  // commit throws and the failure reads as "the download produced nothing"
  // rather than as a missing mock.
  setMany: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))

const SHELTER = {
  id: 'atc_shelters:abc',
  type: 'shelter',
  name: 'Chairback Gap Lean-to',
  lat: latOfMile(5),
  lon: -77,
  confidence: 'high' as const,
  source: 'atc_shelters',
}

// No `onLine`, deliberately - App.safety.test.tsx is where the reads that need
// a connection are asserted, and these flows are the ones a hiker walks with
// no signal at all.
const app = appHarness({ navigator: { geolocation: true }, objectUrls: true })
const store = app.store

/** Onboarded, location allowed, trail data already on the phone. */
function hikerOnTrail(overrides: Record<string, unknown> = {}) {
  app.onboard({ location_permission_requested: true, ...overrides })
  app.putTrailData({ pois: [SHELTER] })
}

/** Report a GPS fix at a mile of the synthetic centerline. */
const reportFix = (mile = 5) => app.reportFixAtMile(mile)

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
 *
 * ONLY REACHABLE ON A PHONE THAT ALREADY HAS THE RASTER since #855: the sheet
 * is withdrawn, so its card exists exactly while there are bytes of it here -
 * finished, or stopped part-way with a Resume on it. Every caller below seeds
 * the store first for that reason. A test that wants a card to exercise the
 * download machinery generally wants `hikingSheetCard` instead.
 */
async function usgsSheetCard(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('tab', { name: /usgs sheet/i }))
  return screen.findByRole('region', { name: /usgs sheet/i })
}

/**
 * The hiking sheet's card - the one every phone is offered.
 *
 * No tab click: with the USGS sheet withdrawn there is usually one sheet and
 * so no strip at all (screens/Downloads.tsx), and where a second card does
 * appear this one is still the open tab. Finding the region by name works in
 * both, which is what keeps these tests about the download rather than about
 * how many sheets happen to be on offer.
 */
function hikingSheetCard() {
  return screen.findByRole('region', { name: /hiking sheet/i })
}

describe('once there is a GPS fix', () => {
  it('shows the mile instead of still looking for GPS', async () => {
    hikerOnTrail()
    render(<App />)
    await openMapTab()
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
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    // Wait for the map itself, not just its container div: findByRole resolves
    // a commit before MapView's effect constructs the map, so reading
    // instances[0] straight after it races the build and can find nothing at
    // all. That would fail as a TypeError rather than as the assertion.
    await waitFor(() => expect(MockMap.instances.length).toBeGreaterThan(0))

    await reportFix()
    expect(await screen.findByText(/mi 5\./)).toBeInTheDocument()

    await reportFix(6)
    expect(await screen.findByText(/mi 6\./)).toBeInTheDocument()

    expect(MockMap.instances[0].cameraMoves).toHaveLength(0)
  })

  it('starts tracking a direction of travel once it has two fixes', async () => {
    hikerOnTrail()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix(5)
    await reportFix(8)

    expect(await screen.findByText(/mi 8\./)).toBeInTheDocument()
  })
})

describe('search, with a real index behind it', () => {
  it('jumps the map to the result that was picked', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await openMapTab()
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
    await openMapTab()
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
    await openMapTab()
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
    await openMapTab()
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
    //
    // Explicitly all-on (#865): DEFAULT_PREFERENCES now starts with only the
    // curated subset shown, and this test is about the toggle mechanism, not
    // about which categories start on - that is waypointVisibility.test.ts's
    // and userPreferences.test.ts's job.
    const user = userEvent.setup()
    hikerOnTrail({ waypoint_types_shown: [] })
    render(<App />)
    await openMapTab()
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
    await openMapTab()
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
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })
    const card = await screen.findByRole('dialog', { name: /waypoint/i })
    // The card peeks (#941); the strip of parts is in the record behind the
    // pull, so reaching the privy now starts with opening the card. That the
    // gesture exists at all is still what this test is about.
    await user.click(within(card).getByTestId('poi-card-expand'))

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
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })
    const card = await screen.findByRole('dialog', { name: /waypoint/i })
    await userEvent.setup().click(within(card).getByTestId('poi-card-expand'))

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
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })

    const sheet = await screen.findByRole('dialog', { name: /waypoint/i })
    expect(within(sheet).getByText(/^mi 5\./)).toBeInTheDocument()
  })

  it('says which source listed it', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await tapPin({ [POI_ID_PROPERTY]: SHELTER.id, poi_type: 'shelter' })

    const sheet = await screen.findByRole('dialog', { name: /waypoint/i })
    // Under "About this place" since #941, which is the demotion the issue
    // asked for: where the pin came from is a fact about the pin, and it no
    // longer outranks the answer the hiker tapped it for.
    await user.click(within(sheet).getByTestId('poi-card-expand'))
    expect(within(sheet).getByText(/Appalachian Trail Conservancy/)).toBeInTheDocument()
  })

  it('closes again', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await openMapTab()
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
    await openMapTab()
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
    await openMapTab()
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
    await openMapTab()
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
    await openMapTab()
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
        blob: () => Promise.resolve(new Blob([centerlineGeoJSON()])),
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
                  ? centerlineGeoJSON()
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
    app.onboard()
    servesEverything()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await openDownloads(user)
    // The hiking sheet's card, named: each sheet has its own download button
    // (#237), and this is the one every phone is offered (#855).
    const card = await hikingSheetCard()
    await user.click(within(card).getByRole('button', { name: /download the map/i }))

    await waitFor(() => expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob))
    // Read through the accessor the map uses: since #553 a finished archive is a
    // run of segment records named by a completion marker, not one record.
    await waitFor(async () =>
      expect(await readArchive(BASEMAP_PACKAGE.idbKey)).toBeInstanceOf(Blob),
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
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await openDownloads(user)
    const usgsCard = await usgsSheetCard(user)
    await user.click(within(usgsCard).getByRole('button', { name: /delete the map/i }))
    await user.click(within(usgsCard).getByRole('button', { name: /yes, delete it/i }))

    await waitFor(() => expect(store.has(CORRIDOR_ARCHIVE_KEY)).toBe(false))
    expect(store.has(TRAILS_BLOB_KEY)).toBe(true)
    expect(store.has(POIS_KEY)).toBe(true)
  })

  it('records a level chosen on a card as the sheet’s own preference', async () => {
    // Each sheet's picker writes its own dial, never a shared one (#276).
    //
    // Asserted against the HIKING sheet since #855. It used to be the raster
    // card and `max_background_zoom`, which is that sheet's dial - and with
    // the USGS sheet withdrawn there is no card to turn it on, so a test
    // driving it through the UI would be testing a screen no hiker can
    // reach. The preference itself is untouched and still validated where it
    // is defined (lib/userPreferences.test.ts, and the backend's mirror).
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await openDownloads(user)
    const card = await hikingSheetCard()
    await user.click(within(card).getByRole('radio', { name: /fine/i }))

    await waitFor(() => {
      const saved = store.get(PREFERENCES_KEY) as { hiking_detail_level: string }
      expect(saved.hiking_detail_level).toBe('fine')
    })
  })
})

describe('reporting, with a fix to attach', () => {
  it('files the report at the position the hiker is actually standing', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await reportFix()

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /^volunteer & report/i }))
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
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /^volunteer & report/i }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))
    await user.click(await screen.findByRole('button', { name: /blow down/i }))
    await user.click(await screen.findByRole('button', { name: /^cancel$/i }))

    expect(await screen.findByRole('heading', { name: 'Contribute' })).toBeInTheDocument()
    expect(store.get('ourhike:outbox')).toBeUndefined()
  })

  it('counts what is waiting in the outbox', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /^volunteer & report/i }))
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
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /^volunteer & report/i }))
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
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /^volunteer & report/i }))
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
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /^the map/i }))
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
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    expect(document.documentElement.getAttribute(THEME_ATTRIBUTE)).toBe('light')
    // Waited on, exactly like the dark read at the end of this test. The map
    // is built in an effect that runs a commit AFTER the container div lands,
    // so `MockMap.live[0]` here was a race: one of the two reads in this test
    // was wrapped and the other was not, and this is the one that failed
    // under a full-suite run (#331).
    expect(backdropOf(await liveMap())).toBe(MAP_BACKDROP.light)

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /^the map/i }))
    await user.click(await screen.findByRole('radio', { name: /dark/i }))

    await waitFor(() => {
      const saved = store.get(PREFERENCES_KEY) as { theme: string }
      expect(saved.theme).toBe('dark')
    })
    expect(document.documentElement.getAttribute(THEME_ATTRIBUTE)).toBe('dark')

    await user.click(screen.getByRole('tab', { name: 'Map' }))
    await openMapTab()
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

describe('the actions on More that are not built yet', () => {
  // These used to be three clickable buttons wired to `notYet`, and this
  // block asserted that tapping them did not throw - which pinned the
  // placeholder in place rather than the promise. #657 named it: a control
  // that looks usable and is not costs more than a missing one, because it
  // gets pressed, nothing happens, and the hiker learns this app's buttons
  // sometimes lie. On the screen whose other buttons are export and sign-out.
  //
  // So what is asserted now is the opposite: they are NOT offered as buttons,
  // and they wear the "Later" tag the same screen already uses for "Roads &
  // walkability". The old assertion could only ever have caught a button that
  // threw; this one catches a button that came back.
  it.each([/^sync$/i, /export gpx/i, /export geojson/i])(
    'does not offer %s as a button that does nothing',
    async (name) => {
      const user = userEvent.setup()
      hikerOnTrail()
      render(<App />)
      await openMapTab()
      await screen.findByRole('region', { name: /trail map/i })
      await user.click(screen.getByRole('tab', { name: 'More' }))
      await user.click(
        await screen.findByRole('button', { name: /where this map comes from/i }),
      )
      await screen.findByRole('heading', { name: 'Your data' })

      expect(screen.queryByRole('button', { name })).toBe(null)
    },
  )

  it('says "Later" for both of them instead', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(
      await screen.findByRole('button', { name: /where this map comes from/i }),
    )
    await screen.findByRole('heading', { name: 'Your data' })

    expect(screen.getByText(/refresh now/i)).toBeInTheDocument()
    expect(screen.getByText(/export gpx or geojson/i)).toBeInTheDocument()
  })
})

describe('signing in from Settings', () => {
  it('opens the sign-in screen', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))

    await user.click(await screen.findByRole('button', { name: /^you/i }))
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
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))

    await user.click(await screen.findByRole('button', { name: /^you/i }))
    await user.click(await screen.findByRole('button', { name: /sign in/i }))
    await screen.findByRole('button', { name: /continue with google/i })

    expect(screen.queryByText(/already saved/i)).toBe(null)
  })

  it('backs out to the screen it came from', async () => {
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))

    await user.click(await screen.findByRole('button', { name: /^you/i }))
    await user.click(await screen.findByRole('button', { name: /sign in/i }))
    await user.click(await screen.findByRole('button', { name: /not now/i }))

    expect(await screen.findByRole('heading', { name: 'You' })).toBeInTheDocument()
  })

  it('offers only the providers this build has credentials for', async () => {
    // ENABLED_PROVIDERS is Google alone - v1's decided provider set (#397).
    // Apple needs a $99/yr membership and is deferred to v2 (#92); email left
    // the default because Supabase's built-in sender is not a delivery path
    // this project ships on, so offering it built a button whose sign-in
    // could not complete.
    //
    // Both absences are asserted rather than only Apple's, because they are
    // absent for different reasons and a single "not Apple" assertion would
    // pass on a build that had quietly restored email.
    const user = userEvent.setup()
    hikerOnTrail()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))

    await user.click(await screen.findByRole('button', { name: /^you/i }))
    await user.click(await screen.findByRole('button', { name: /sign in/i }))
    await screen.findByRole('button', { name: /continue with google/i })

    expect(screen.queryByRole('button', { name: /continue with email/i })).toBe(null)
    expect(screen.queryByRole('button', { name: /continue with apple/i })).toBe(null)
  })

  // Two tests stood here and were removed with the email default (#397): one
  // that the email button reaches a form asking only for an address, and one
  // that the form offers a password fallback. They drove App -> SignInPrompt
  // -> EmailSignIn, and that route is unreachable in a build offering Google
  // alone, so keeping them would have meant faking the configuration to test
  // a path no hiker can take.
  //
  // Nothing about EmailSignIn lost coverage: screens/EmailSignIn.test.tsx
  // renders it directly and covers both paths further than these did - the
  // address-only form, the link's wording, the password fallback, switching
  // between them and the failure messages. What is uncovered while email is
  // off is the App-level wiring between the button and the screen, which is
  // the thing that only exists when the button does. Restore these two with
  // the provider, not before.
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
    app.onboard()
    vi.mocked(fetch).mockRejectedValue('the network went away')
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await openDownloads(user)
    const card = await hikingSheetCard()
    await user.click(within(card).getByRole('button', { name: /download the map/i }))

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
    //
    // Built per call rather than handed back as one object, because the sheet
    // under test is the hiking one and that is two archives (#855 withdrew
    // the single-archive raster sheet these flows used to drive). A
    // ReadableStream can be read once, so a shared Response would leave the
    // second transfer reading a locked body - and the footer's figure is the
    // two of them combined, which is the number this asserts.
    vi.mocked(fetch).mockImplementation(
      () =>
        Promise.resolve({
          ok: true,
          status: 200,
          statusText: 'OK',
          headers: new Headers({ 'content-length': '10' }),
          body: new ReadableStream({
            start(controller) {
              controller.enqueue(new Uint8Array([1, 2, 3, 4]))
            },
          }),
        }) as unknown as Promise<Response>,
    )

    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await openDownloads(user)
    const card = await hikingSheetCard()
    await user.click(within(card).getByRole('button', { name: /download the map/i }))

    // The window's own bar first: proof the transfer really is running, so
    // that what the footer says next is a report and not a coincidence.
    await waitFor(() =>
      expect(within(card).getByRole('progressbar')).toHaveAttribute(
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
    await openMapTab()
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

// WIREFRAMES.md §1.3, and the next-up rail that replaced §1.4's lanes
// (#1054). What is worth testing here is the wiring and the conditions it is
// gated on - not the drawing, which ElevationRibbon.test.tsx and
// NextUpRail.test.tsx already cover.
describe('the elevation ribbon and the next-up rail', () => {
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
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()

    await waitFor(() => expect(ribbon()).toBeInTheDocument())
  })

  it('draws the rail of coming waypoints beside it', async () => {
    hikerOnTrail()
    store.set(ELEVATION_STORE_KEY, profileWithAClimb())
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()

    // One fix, no direction yet: the rail may not claim NEXT UP, and says
    // the honest word instead (chrome/NextUpRail.tsx).
    await waitFor(() => expect(screen.getByText('NEARBY')).toBeInTheDocument())
  })

  it('puts a POI the index can place onto a card that opens it', async () => {
    // The shelter sits at mile 5 on the synthetic centerline, inside the window
    // around a hiker standing at mile 5.
    hikerOnTrail()
    store.set(ELEVATION_STORE_KEY, profileWithAClimb())
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()

    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: /chairback gap lean-to/i }),
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
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    expect(ribbon()).not.toBeInTheDocument()
    expect(screen.queryByText('NEARBY')).not.toBeInTheDocument()
  })

  it('shows nothing when the release published no profile', async () => {
    // A data release built before pipeline/export_elevation.py existed. The
    // map still works; the ribbon and the lanes are simply absent.
    hikerOnTrail()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()

    await screen.findByText(/mi 5\./)
    expect(ribbon()).not.toBeInTheDocument()
    expect(screen.queryByText('NEARBY')).not.toBeInTheDocument()
  })

  it('waits for the direction before captioning a climb', async () => {
    // lib/hikeDirection.ts withholds the direction until a quarter mile of
    // movement, and which way someone faces decides which climb is ahead.
    hikerOnTrail()
    store.set(ELEVATION_STORE_KEY, profileWithAClimb())
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()

    await waitFor(() => expect(ribbon()).toBeInTheDocument())
    expect(screen.queryByTestId('climb-callout')).not.toBeInTheDocument()
  })

  it('captions the climb ahead once the direction is known', async () => {
    hikerOnTrail()
    store.set(ELEVATION_STORE_KEY, profileWithAClimb())
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await reportFix()
    // A mile further north: enough movement for NOBO to be established.
    await reportFix(6)

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
    await openMapTab()
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
    await openMapTab()
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
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await sourceFails('usgs-topo')
    await screen.findByText(/downloaded map not drawing/i)

    // Away to the More tab and back: the map is torn down and a new one built,
    // which is what used to make this permanent.
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await waitFor(() => expect(MockMap.live).toHaveLength(0))
    await user.click(screen.getByRole('tab', { name: 'Map' }))

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
    await openMapTab()
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
    // More keeps its page across trips (App holds it), so this may land on
    // home, on the volunteer page, or wherever the last trip ended - walk to
    // the report button from any of them.
    if (!screen.queryByRole('button', { name: /report a problem/i })) {
      const back = screen.queryByRole('button', { name: 'More' })
      if (back !== null) await user.click(back)
      await user.click(
        await screen.findByRole('button', { name: /^volunteer & report/i }),
      )
    }
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
    await openMapTab()
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
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /^you/i }))
    await user.selectOptions(
      await screen.findByRole('combobox', { name: /signed as/i }),
      'section',
    )

    await fileAReport(user)

    await waitFor(() => expect(queued()).toHaveLength(1))
    expect(queued()[0].payload.reporter_type).toBe('section')
  })
})

describe('tapping a trail line (#134)', () => {
  /** Touch the canvas where MapLibre would report a line - same arrangement
   *  as tapPin above, against the blaze layer. */
  async function tapLine(features: Array<Record<string, unknown>>) {
    await waitFor(() => {
      expect(MockMap.live).toHaveLength(1)
      expect(MockMap.live[0].listenerCount('click')).toBeGreaterThan(0)
    })
    const map = MockMap.live[0]
    map.renderedFeatures.set(BLAZE_LAYER_ID, features)
    await act(async () => {
      map.emit('click', { point: { x: 160, y: 300 } })
    })
  }

  it('opens the line-detail sheet with the spur’s facts, and a bare tap closes it', async () => {
    hikerOnTrail()
    // The published spur record for the line about to be tapped - stored the
    // way a download commits it, so this exercises the whole read path.
    store.set(SPURS_STORE_KEY, {
      'side_trails:abc': {
        name: 'Rocky Run Spur Trail',
        length_ft: 1056,
        destination_poi_id: SHELTER.id,
        destination_distance_m: 1,
        junction_mile: 1043.2,
      },
    })
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await tapLine([
      {
        properties: { id: 'side_trails:abc', source: 'side_trails', blaze_color: 'Blue' },
      },
    ])

    const sheet = await screen.findByRole('dialog', { name: /trail line/i })
    expect(within(sheet).getByRole('heading')).toHaveTextContent('Blue blaze · spur')
    // The destination's NAME, resolved from the stored POIs - the id alone
    // would be a link to nowhere a hiker can read.
    expect(within(sheet).getByText(/To Chairback Gap Lean-to/)).toBeInTheDocument()
    expect(within(sheet).getByText('Joins the AT at mi 1,043.2')).toBeInTheDocument()

    // Tap-elsewhere-to-dismiss, the gesture every map card teaches.
    const map = MockMap.live[0]
    map.renderedFeatures.set(BLAZE_LAYER_ID, [])
    await act(async () => {
      map.emit('click', { point: { x: 40, y: 60 } })
    })
    await waitFor(() => {
      expect(
        screen.queryByRole('dialog', { name: /trail line/i }),
      ).not.toBeInTheDocument()
    })
  })

  it('names the through-route, so the white line is not a dead surface', async () => {
    hikerOnTrail()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await tapLine([
      {
        properties: {
          id: 'centerline:chain:0',
          source: 'centerline',
          blaze_color: 'White',
        },
      },
    ])

    const sheet = await screen.findByRole('dialog', { name: /trail line/i })
    expect(within(sheet).getByRole('heading')).toHaveTextContent(
      'White blaze · Appalachian Trail',
    )
  })
})
