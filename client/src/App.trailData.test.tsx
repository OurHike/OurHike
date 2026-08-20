// The trail lines arriving on their own, without a 314 MB download first.
//
// Its own file because it needs a CONFIGURED data source, and lib/config reads
// the base URL once at module load - so the only honest way to have one is to
// mock the module before App is imported. App.test.tsx deliberately runs
// unconfigured, which is the state the Downloads screen's warning is about, and
// mocking config there would quietly change the subject of every test in it.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import { get } from 'idb-keyval'
import { MockMap } from './test/mocks/maplibre-gl'
import { appHarness } from './test/appHarness'
import { liveMap } from './test/liveMap'
import { POIS_KEY, TRAILS_BLOB_KEY } from './lib/trailData'
import { PREFERENCES_KEY } from './lib/preferences'
import { TRAILS_SOURCE_ID } from './map/style'

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  set: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./map/protocol', () => ({
  PMTILES_SCHEME: 'pmtiles',
  registerPMTilesProtocol: vi.fn(),
  CORRIDOR_ARCHIVE_URL: 'pmtiles://ourhike-corridor',
}))
// Only the base URL and the two helpers keyed off it. Spreading the real
// module keeps POI_TYPES and the file-name constants exactly as they ship, so
// this stays a test about a configured build rather than about a fake one.
vi.mock('./lib/config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./lib/config')>()),
  DATA_BASE_URL: 'https://data.example',
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.example/${key}`,
  archiveUrl: () => 'https://data.example/corridor.pmtiles',
}))

const TRAILS = '{"type":"FeatureCollection","features":[]}'

// jsdom's own navigator, not a stub: three tests below spy on `onLine`'s
// getter to go offline mid-test, which a plain stubbed object cannot carry.
// Its own fetch too - this file is about what the trail-data fetch does with
// what comes back, so an empty mock would have nothing to say.
const app = appHarness({ stubFetch: false })
const store = app.store

beforeEach(() => {
  app.onboard()
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers(),
        // Bytes, because trail data is hashed before it is stored (#197).
        arrayBuffer: () => Promise.resolve(new TextEncoder().encode(TRAILS).buffer),
        blob: () => Promise.resolve(new Blob([TRAILS])),
        text: () => Promise.resolve(TRAILS),
        json: () => Promise.resolve(JSON.parse(TRAILS)),
      } as unknown as Response),
    ),
  )
})

afterEach(() => {
  // restore, not just clear: the offline cases spy on `navigator.onLine`'s
  // getter, and a cleared spy still answers false - which silently turned the
  // fetch-failure case below into a test about being offline.
  vi.restoreAllMocks()
})

async function renderApp() {
  const { default: App } = await import('./App')
  render(<App />)
  await screen.findByRole('region', { name: /trail map/i })
}

function requested() {
  return vi.mocked(fetch).mock.calls.map((c) => String(c[0]))
}

/**
 * The hiking sheet's card - the one every phone is offered.
 *
 * No tab click: the USGS sheet is withdrawn (#855), so the window usually
 * holds one card and renders no strip at all (screens/Downloads.tsx), and
 * where a second card does appear this one is still the open tab. The canary
 * these tests are about runs before any sheet's bytes are asked for, so which
 * card starts it does not matter to them.
 */
function hikingSheetCard() {
  return screen.findByRole('region', { name: /hiking sheet/i })
}

describe('trail data on a phone that has downloaded nothing', () => {
  it('fetches the trail lines without waiting for anyone to tap Download', async () => {
    // The reported gap: the centerline only appeared after the corridor
    // archive was downloaded. The lines are a few megabytes against 314 MB,
    // and without them the app opens on a background with no trail on it -
    // nothing to search, no POIs, no elevation ribbon.
    await renderApp()

    await waitFor(() => {
      expect(requested().some((url) => url.includes('trails'))).toBe(true)
    })
  })

  it('draws the trail line behind the first-run steps, before the waypoints are fetched', async () => {
    // #863, and the reason the download is ordered the way it is. The entry
    // steps are a card over the map, and on a phone holding nothing there was
    // no map behind them: the commit waited for the whole release, which is
    // ~12 s on a 4x-throttled phone profile at 12 Mbps, against about eight
    // seconds to click through three steps. So a newcomer read three sentences
    // about a map over an empty background.
    //
    // The waypoints are held here rather than answered, which is what makes
    // this a statement about ORDER: the line is on the map while their fetches
    // are still outstanding, not merely by the end.
    store.delete(PREFERENCES_KEY)
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        String(url).includes('poi_')
          ? new Promise(() => {})
          : Promise.resolve({
              ok: true,
              status: 200,
              headers: new Headers(),
              arrayBuffer: () => Promise.resolve(new TextEncoder().encode(TRAILS).buffer),
              blob: () => Promise.resolve(new Blob([TRAILS])),
              text: () => Promise.resolve(TRAILS),
              json: () => Promise.resolve(JSON.parse(TRAILS)),
            } as unknown as Response),
      ),
    )

    const { default: App } = await import('./App')
    render(<App />)
    await screen.findByText('What OurHike is')
    const map = await liveMap()

    await waitFor(() =>
      expect(map.sourceData.get(TRAILS_SOURCE_ID)).toEqual(
        expect.stringContaining('blob:'),
      ),
    )
    // Still out there, which is the half that makes the other half worth
    // having.
    expect(requested().some((url) => url.includes('poi_'))).toBe(true)
    expect(store.has(POIS_KEY)).toBe(false)
  })

  it('stores what it fetched, so the next launch reads it off the phone', async () => {
    await renderApp()

    await waitFor(() => {
      expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob)
    })
  })

  it('never asks for the huge archive, which stays the hiker’s decision', async () => {
    // The whole point of the split. Trail lines are the map; the corridor
    // raster is hundreds of megabytes of someone's data allowance and stays
    // behind the button on the Downloads screen.
    await renderApp()

    await waitFor(() => {
      expect(requested().some((url) => url.includes('trails'))).toBe(true)
    })
    expect(requested().some((url) => url.includes('.pmtiles'))).toBe(false)
  })

  it('does not re-fetch when the phone already has the lines', async () => {
    store.set(TRAILS_BLOB_KEY, new Blob([TRAILS]))
    store.set('ourhike:pois', [])

    await renderApp()

    await waitFor(() => expect(MockMap.live.length).toBeGreaterThan(0))
    expect(requested().some((url) => url.includes('trails'))).toBe(false)
  })

  it('still reads the stored lines with no signal, which is the whole point of storing them', async () => {
    // The regression this guards: gating the read on "configured and online"
    // alongside the fetch left a hiker on a ridge - exactly who the offline
    // store exists for - looking at a map with no trail on it.
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
    store.set(TRAILS_BLOB_KEY, new Blob([TRAILS]))
    store.set('ourhike:pois', [])

    await renderApp()

    await waitFor(() => expect(MockMap.live.length).toBeGreaterThan(0))
    expect(vi.mocked(get).mock.calls.map((c) => String(c[0]))).toContain(TRAILS_BLOB_KEY)
    expect(requested()).toEqual([])
  })

  it('waits for signal rather than failing a fetch it knows cannot work', async () => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)

    await renderApp()

    await waitFor(() => expect(MockMap.live.length).toBeGreaterThan(0))
    expect(requested()).toEqual([])
  })

  it('says the trail line is missing when the fetch nobody asked for fails', async () => {
    // This asserted the opposite until the bug it describes was reported: the
    // launch fetch was silent on the reasoning that nobody asked for it, so a
    // bucket refusing the app's origin produced a finished-looking map with no
    // Appalachian Trail on it and no account of itself anywhere in the UI.
    // Nobody asking for the fetch is not the same as nobody noticing it
    // failed - what is missing is the map.
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not Found',
    } as Response)

    await renderApp()

    expect(await screen.findByText(/no trail line/i)).toBeInTheDocument()
    expect(store.get(TRAILS_BLOB_KEY)).toBeUndefined()
  })

  it('carries the reason to the download window, where the retry is', async () => {
    // The strip has room for three words; the sentence naming the artifact and
    // what the browser said belongs where someone can act on it. Both come
    // from one description of the failure (App's describeTrailDataError), so
    // the flag and the sentence cannot disagree about whether anything is
    // wrong.
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    vi.mocked(fetch).mockRejectedValue(
      new TypeError('NetworkError when attempting to fetch resource.'),
    )

    await renderApp()
    await screen.findByText(/no trail line/i)

    await user.click(await screen.findByRole('button', { name: /legend/i }))
    await user.click(await screen.findByRole('button', { name: /download/i }))
    await screen.findByRole('dialog', { name: /offline map/i })

    const notice = await screen.findByRole('alert')
    expect(notice).toHaveTextContent(/trails\.geojson/)
    expect(notice).toHaveTextContent(/data\.example/)
    expect(notice).toHaveTextContent(/NetworkError when attempting to fetch resource/)
  })

  it('does not flag a missing trail line on a launch that works', async () => {
    // The flag has to mean "not coming", not "not yet". A cold start spends a
    // moment with no line on the map in the ordinary case, and a flag that
    // fired during it would be raised on every launch - which is how a flag
    // stops being read.
    await renderApp()

    await waitFor(() => expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob))
    expect(screen.queryByText(/no trail line/i)).not.toBeInTheDocument()
  })

  it('leaves the flag down for a phone that already holds the lines', async () => {
    // Offline with the lines on the phone is the working state this app is
    // built for, and the fetch is skipped entirely - nothing has failed and
    // the map has its trail.
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
    store.set(TRAILS_BLOB_KEY, new Blob([TRAILS]))
    store.set('ourhike:pois', [])

    await renderApp()

    await waitFor(() => expect(MockMap.live.length).toBeGreaterThan(0))
    expect(screen.queryByText(/no trail line/i)).not.toBeInTheDocument()
  })
})

describe('the trail data a tapped download waits for', () => {
  // The reported bug, from a first run: the download "did not start - it just
  // stayed at 0". It had started. Tapping the button runs `ensureTrailData`
  // first, which is 12.3 MB of trails.geojson in the shipped bucket, and the
  // card had nothing to say for the whole of that wait - it went on offering
  // the button that had just been pressed.

  /** A trail-data fetch this test decides when to finish, so the wait it
   *  causes can be looked at rather than raced. Everything else answers
   *  normally. */
  function holdTrailsFetch() {
    let release = () => {}
    const held = new Promise<void>((resolve) => {
      release = resolve
    })
    const answer = () =>
      ({
        ok: true,
        status: 200,
        headers: new Headers(),
        arrayBuffer: () => Promise.resolve(new TextEncoder().encode(TRAILS).buffer),
        blob: () => Promise.resolve(new Blob([TRAILS])),
        text: () => Promise.resolve(TRAILS),
        json: () => Promise.resolve(JSON.parse(TRAILS)),
      }) as unknown as Response

    vi.mocked(fetch).mockImplementation(async (input: RequestInfo | URL) => {
      if (String(input).includes('trails')) await held
      return answer()
    })
    return () => release()
  }

  it('says the tap landed, instead of re-offering the button just pressed', async () => {
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    const release = holdTrailsFetch()

    await renderApp()
    await user.click(await screen.findByRole('button', { name: /legend/i }))
    await user.click(await screen.findByRole('button', { name: /download/i }))
    const card = await hikingSheetCard()
    await user.click(within(card).getByRole('button', { name: /download the map/i }))

    // The state the whole wait used to be invisible in.
    expect(await within(card).findByText(/getting the trail/i)).toBeVisible()
    expect(within(card).queryByRole('button', { name: /download the map/i })).toBeNull()

    // And it really is the archive that is being waited for, not something
    // that already went out: nothing has asked for the map yet.
    expect(requested().some((url) => url.includes('.pmtiles'))).toBe(false)

    // Released and then WAITED OUT, not just released: the fetch this test
    // holds open outlives the test otherwise, and its writes land in the next
    // one's store. That is not hypothetical - it put trail data on the phone
    // of the hash-mismatch test below, which then had nothing to download and
    // no failure to report.
    release()
    await waitFor(() => expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob))
    // And it gives way to the transfer rather than sticking - the failure
    // mode of a state that only ever gets switched on.
    await waitFor(() => expect(within(card).queryByText(/getting the trail/i)).toBeNull())
  })

  it('joins the fetch already running rather than pulling the same megabytes twice', async () => {
    // On a first run the launch fetch is already going when the window opens,
    // and `loadTrailData()` answers null until it commits - so a tap used to
    // start a SECOND download of the same 12.3 MB, against the same
    // connection, ahead of the archive the hiker was waiting for.
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    const release = holdTrailsFetch()

    await renderApp()
    // The launch fetch is in flight and cannot finish yet.
    await waitFor(() =>
      expect(requested().filter((url) => url.includes('trails'))).toHaveLength(1),
    )

    await user.click(await screen.findByRole('button', { name: /legend/i }))
    await user.click(await screen.findByRole('button', { name: /download/i }))
    const card = await hikingSheetCard()
    await user.click(within(card).getByRole('button', { name: /download the map/i }))

    // Waited on rather than duplicated: the tap is visibly in the canary
    // step, and the request count has not moved.
    expect(await within(card).findByText(/getting the trail/i)).toBeVisible()
    expect(requested().filter((url) => url.includes('trails'))).toHaveLength(1)

    // Waited out rather than merely released - see the test above.
    release()
    await waitFor(() => expect(store.get(TRAILS_BLOB_KEY)).toBeInstanceOf(Blob))
    // Still one fetch once it lands: the tap was sharing it, not queued
    // behind it waiting to start its own.
    expect(requested().filter((url) => url.includes('trails'))).toHaveLength(1)
  })
})

describe('a refused trail-data download, told apart by type (#238)', () => {
  // The one failure whose remedy is not "retry what stopped": the bytes
  // arrived whole, matched no published build, and were deliberately not
  // saved. This file is where the real path can run - it needs a configured
  // bucket, a published hash to disagree with, and the genuine
  // downloadTrailData underneath - so the notice is driven by the actual
  // TrailDataHashMismatchError, never by matching on a sentence.

  it('says nothing was saved and that downloading again fetches a fresh copy', async () => {
    const { default: userEvent } = await import('@testing-library/user-event')
    const user = userEvent.setup()
    vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('latest.json')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () =>
            Promise.resolve({
              version: 'v1',
              // A published hash the served bytes cannot match.
              artifacts: { 'trails.geojson': { sha256: '00'.repeat(32) } },
            }),
        } as unknown as Response)
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers(),
        arrayBuffer: () => Promise.resolve(new TextEncoder().encode(TRAILS).buffer),
        blob: () => Promise.resolve(new Blob([TRAILS])),
        text: () => Promise.resolve(TRAILS),
        json: () => Promise.resolve(JSON.parse(TRAILS)),
      } as unknown as Response)
    })

    await renderApp()
    await user.click(await screen.findByRole('button', { name: /legend/i }))
    await user.click(await screen.findByRole('button', { name: /download/i }))
    await screen.findByRole('dialog', { name: /offline map/i })
    const card = await hikingSheetCard()
    await user.click(within(card).getByRole('button', { name: /download the map/i }))

    const notice = await screen.findByText(/this release was not kept/i)
    expect(notice).toHaveTextContent(/untouched/i)
    expect(notice).toHaveTextContent(/fresh copy from the start/i)
    // Nothing was stored, exactly as the sentence claims.
    expect(store.get(TRAILS_BLOB_KEY)).toBeUndefined()
  })
})
