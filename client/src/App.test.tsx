import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { get, set, setMany, update } from 'idb-keyval'
import App from './App'
import { MockMap, NavigationControl, resetMapLibreMock } from './test/mocks/maplibre-gl'
import { loadMapEngine } from './map/mapEngineLoader'
// The shared helper this file's own copy became (#331) - two other suites had
// written the same wait by hand, and one of them had written it wrong.
import { liveMap } from './test/liveMap'
// This file keeps its own store/mock setup (it predates appHarness); the one
// thing it borrows is the way to the map screen, which stopped being the
// front door when Today became the home tab (#1054).
import { openMapTab } from './test/appHarness'
import { PREFERENCES_KEY } from './lib/preferences'
import { HIKER_MODE_KEY } from './lib/hikerMode'
import { DEFAULT_PREFERENCES } from './lib/userPreferences'
import { POIS_KEY, TRAILS_BLOB_KEY } from './lib/trailData'
import { CORRIDOR_BACKGROUND_PACKAGE } from './lib/packages'
import type { ArchiveZooms } from './lib/archiveCoverage'

// The shell decides what a hiker sees, so what is worth testing here is the
// routing between screens and the honesty of what it shows before any data
// exists - not the screens themselves, which have their own tests.

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

/**
 * What the archive's PMTiles header says it covers (#216).
 *
 * Mocked at this seam rather than at `pmtiles` itself: the real PMTiles class
 * is also what map/protocol.ts registers the offline protocol with, and
 * replacing it wholesale breaks map construction for every other test in this
 * file. The header read has its own unit tests in map/archiveZooms.test.ts.
 */
const archiveHeader: { value: ArchiveZooms | null } = { value: null }
vi.mock('./map/archiveZooms', () => ({
  readArchiveZooms: () => Promise.resolve(archiveHeader.value),
}))

const store = new Map<string, unknown>()

beforeEach(async () => {
  store.clear()
  archiveHeader.value = null
  resetMapLibreMock()
  // The map engine arrives through `import()` in production (#722); primed
  // here so every render below builds its map synchronously, exactly as it did
  // before the deferral. After this file's `vi.mock('maplibre-gl', ...)`, so
  // the engine closes over the mock rather than the real library.
  await loadMapEngine()
  vi.mocked(get).mockImplementation((key) => Promise.resolve(store.get(key as string)))
  vi.mocked(set).mockImplementation((key, value) => {
    store.set(key as string, value)
    return Promise.resolve()
  })
  // Into the same store, so a test does not have to know which call wrote a
  // key - the whole point of the one-transaction commit (#657).
  vi.mocked(setMany).mockImplementation((entries) => {
    for (const [key, value] of entries) store.set(key as string, value)
    return Promise.resolve()
  })
  vi.mocked(update).mockImplementation((key, updater) => {
    store.set(key as string, updater(store.get(key as string)))
    return Promise.resolve()
  })
  vi.stubGlobal('fetch', vi.fn())
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  // `clearAllMocks` empties the recorded calls and leaves the IMPLEMENTATION
  // in place, which is not what a spy set inside one test should do to the
  // rest of the file. The error-boundary tests below replace MapLibre's Map
  // constructor with one that throws; without this line every test declared
  // after them inherits a map that cannot be built, and fails looking like a
  // bug in whatever it was actually testing. Found by adding a describe at
  // the end of this file and watching five unrelated assertions go red while
  // each one passed on its own.
  vi.restoreAllMocks()
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
 * A viewport wide enough for the desktop layout (lib/useDesktop.ts).
 *
 * Matched on the query rather than answering `true` to everything, because
 * `matchMedia` is asked several other questions in this shell - whether the
 * app is running standalone (lib/useInstallPrompt.ts), whether the pointer is
 * fine (lib/useFinePointer.ts) - and a stub that says yes to all of them is
 * testing a browser that does not exist.
 */
function onADesktop() {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => ({
      matches: query.includes('min-width: 900px'),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    })),
  )
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
  // The size step's own primary since #1054 - it also starts the download,
  // which these shell tests let run into their stubbed fetch.
  await user.click(screen.getByRole('button', { name: 'Keep going' }))
  await user.click(screen.getByRole('button', { name: /not now/i }))
}

/**
 * The download window, opened the way a hiker reaches it.
 *
 * There is no Downloads tab any more (chrome/tabs.ts): the door is the link at
 * the foot of the legend, so getting there means opening the legend first.
 * Going through both is the point - a test that reached the window by some
 * other route would pass with the only door to it painted shut.
 */
async function openDownloads(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('button', { name: /legend/i }))
  await user.click(await screen.findByRole('button', { name: /download/i }))
  return screen.findByRole('dialog', { name: /offline map/i })
}

/**
 * The hiking sheet's card - the one every phone is offered.
 *
 * No tab click: the USGS sheet is withdrawn (#855), so the window usually
 * holds one card and renders no strip at all (screens/Downloads.tsx), and
 * where a second card does appear this one is still the open tab. Finding the
 * region by name works in both, which keeps these tests about the download
 * rather than about how many sheets happen to be on offer.
 */
function hikingSheetCard() {
  return screen.findByRole('region', { name: /hiking sheet/i })
}

function styleOf(map: MockMap): { sources: Record<string, unknown> } {
  return map.options.style as { sources: Record<string, unknown> }
}

describe('App shell', () => {
  it('opens on onboarding the very first time', async () => {
    render(<App />)

    expect(await screen.findByText('What OurHike is')).toBeInTheDocument()
  })

  it('draws the map behind the first-run steps, rather than describing one', async () => {
    render(<App />)

    await screen.findByText('What OurHike is')

    // Every step is a claim about the map. It is behind them from the first
    // frame, so the claims are shown rather than only asserted.
    await waitFor(() => expect(MockMap.live.length).toBe(1))
  })

  it('opens that map on the whole corridor, the same view the map screen opens on', async () => {
    render(<App />)

    await screen.findByText('What OurHike is')
    const map = await liveMap()

    expect(map.options.bounds).toEqual([
      [-84.73, 34.2],
      [-68.3, 46.34],
    ])
  })

  it('keeps the first-run map inert, so nothing behind the steps can be reached', async () => {
    render(<App />)

    await screen.findByText('What OurHike is')
    await liveMap()

    // Not only about stray taps. MapView attaches a locate control, and
    // reaching it would raise the OS location prompt before the step whose
    // whole job is to explain why we are asking. `inert` also keeps the canvas
    // out of the tab order and its region out of the accessibility tree.
    // The map screen IS the backdrop now (#721) - there is no separate entry
    // map to find, which is the whole point. What has to hold is what held
    // before: nothing behind the steps is reachable or announced.
    const backdrop = document.querySelector('.map-screen')
    expect(backdrop).not.toBe(null)
    expect(backdrop).toHaveClass('map-screen--entering')
    expect(backdrop).toHaveAttribute('inert')
    expect(backdrop).toHaveAttribute('aria-hidden', 'true')
    expect(screen.queryByRole('region', { name: /trail map/i })).toBe(null)
  })

  it('never holds two live maps, before or after the steps finish', async () => {
    const user = userEvent.setup()
    render(<App />)

    await completeOnboarding(user)

    // WHAT #721 STILL GUARANTEES, RESTATED FOR THE TODAY HOME (#1054). The
    // steps draw over the one real map screen - never a second copy beside it
    // - and that half is unchanged. What changed is the landing: finishing
    // first run goes to Today, which unmounts the backdrop map the way every
    // trip to another tab always has. So "one map ever constructed" stopped
    // being true by design - the honest invariant is that no two maps are
    // ever alive at once, and that opening the Map tab builds exactly one.
    await waitFor(() => expect(MockMap.live.length).toBeLessThanOrEqual(1))

    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await waitFor(() => expect(MockMap.live).toHaveLength(1))
  })

  it('does not show onboarding again once it has been completed', async () => {
    returningHiker()
    render(<App />)

    // A returning hiker opens on Today (#1054), not on the steps and not on
    // the map - the map is one tap away and asserted reachable elsewhere.
    expect(
      await screen.findByRole('tab', { name: 'Today', selected: true }),
    ).toBeInTheDocument()
    expect(screen.queryByText('What OurHike is')).not.toBeInTheDocument()
  })

  it('opens no window when the steps finish - the download already started on the step that asked', async () => {
    // #1054: "Keep going" on the size step starts the transfer through the
    // shell's own machinery, so the window that used to open here would be a
    // takeover restating a decision already in motion. It is the manage
    // surface now, reachable from the legend and from More - on a phone and
    // a desktop alike, which is why the old desktop carve-out went with it.
    const user = userEvent.setup()
    render(<App />)

    await completeOnboarding(user)

    // The preference write is the observable half of the completion callback
    // and lands after anything that would have opened a window - a bare
    // queryByRole would pass just as readily against one about to open.
    await waitFor(() => {
      const saved = store.get(PREFERENCES_KEY) as
        { onboarding_completed: boolean; download_choice_made: boolean } | undefined
      expect(saved?.onboarding_completed).toBe(true)
      expect(saved?.download_choice_made).toBe(true)
    })

    expect(screen.getByRole('tab', { name: 'Today', selected: true })).toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: /offline map/i })).not.toBeInTheDocument()
  })

  it('still offers a desktop the download, on screen and one click away', async () => {
    // Withheld, not removed. Above 900px the legend is a permanent panel, so
    // the link into the download window is visible without opening anything -
    // which is more exposure than the phone gives it, not less.
    onADesktop()
    const user = userEvent.setup()
    render(<App />)

    await completeOnboarding(user)
    await openMapTab()

    await user.click(
      await screen.findByRole('button', { name: /choose what to download/i }),
    )

    expect(
      await screen.findByRole('dialog', { name: /offline map/i }),
    ).toBeInTheDocument()
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

  it('says location is off rather than pretending to look for it', async () => {
    // This fixture is a hiker who never allowed location - which is what
    // skipping the onboarding step leaves behind, and what the default
    // preference is. The header used to tell them "Looking for GPS…" for the
    // life of the install, about a watch that had never started and never
    // would (#312).
    returningHiker()
    render(<App />)

    expect(await screen.findByText(/location is off/i)).toBeInTheDocument()
    expect(screen.queryByText(/looking for gps/i)).not.toBeInTheDocument()
    // Mile 0.0 is Springer Mountain - a confident claim about somewhere the
    // hiker is almost certainly not standing.
    expect(screen.queryByText(/mi 0\.0/)).not.toBeInTheDocument()
  })

  it('is still allowed to say it is looking, while it genuinely is', async () => {
    // The other half, and the reason the line above is not simply a rename:
    // with location allowed and no fix yet, waiting is exactly what the app is
    // doing and saying so is honest.
    store.set(PREFERENCES_KEY, {
      ...DEFAULT_PREFERENCES,
      onboarding_completed: true,
      download_choice_made: true,
      location_permission_requested: true,
    })
    render(<App />)

    expect(await screen.findByText(/looking for gps/i)).toBeInTheDocument()
    expect(screen.queryByText(/mi 0\.0/)).not.toBeInTheDocument()
  })

  it('moves between the two tabs', async () => {
    const user = userEvent.setup()
    returningHiker()
    render(<App />)

    await openMapTab()

    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    expect(await screen.findByRole('heading', { name: 'More' })).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Map' }))
    expect(await screen.findByRole('region', { name: /trail map/i })).toBeInTheDocument()
  })

  // Reported as "the Downloads tab shows no data, nothing", and it was worse
  // than that: leaving the map tore the map down, MapView's next effect cleanup
  // then removed controls that teardown had already detached, and the TypeError
  // escaping a commit-phase cleanup unmounted the entire root. A white page with
  // no tab bar on it - and on a phone as readily as on a desktop. The tab that
  // reported it is gone; the path it broke on is not, since More still tears
  // the map down on the way in. The two-tab test above covers the same ground
  // but reads as navigation rather than as the crash this is really guarding.
  it('still renders More after the map tab, rather than blanking the whole app', async () => {
    const user = userEvent.setup()
    returningHiker()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))

    expect(await screen.findByRole('tab', { name: 'More', selected: true })).toBeVisible()
    expect(screen.queryByRole('region', { name: /trail map/i })).not.toBeInTheDocument()
  })

  it('opens the download over the map, without taking the map away', async () => {
    // The whole reason the tab went. Checking on a download used to cost the
    // hiker the screen they were reading, and rebuilt the map on the way back.
    const user = userEvent.setup()
    returningHiker()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await openDownloads(user)

    expect(screen.getByRole('region', { name: /trail map/i })).toBeInTheDocument()
    // One sheet on offer and so no strip, which is the window's own rule for
    // a single sheet (#237, #298) - the USGS raster is withdrawn and this
    // phone never took it (#855). Still exactly one download button: what
    // this test is really about is that opening the window costs nobody the
    // map behind it.
    expect(await screen.findByRole('region', { name: /hiking sheet/i })).toBeVisible()
    expect(screen.queryByRole('tab', { name: /usgs sheet/i })).toBeNull()
    const buttons = screen.getAllByRole('button', { name: /download the map/i })
    expect(buttons).toHaveLength(1)
    expect(buttons[0]).toBeVisible()
  })

  it('closes the download window and leaves the map exactly where it was', async () => {
    const user = userEvent.setup()
    returningHiker()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    const map = await liveMap()

    await openDownloads(user)
    await user.click(screen.getByRole('button', { name: /close/i }))

    expect(screen.queryByRole('dialog', { name: /offline map/i })).toBeNull()
    // The same map object, never torn down and rebuilt - which is what a trip
    // through the old tab always cost.
    expect(await liveMap()).toBe(map)
  })

  it('offers no background choice at all on a phone that cannot have one (#855)', async () => {
    // These two used to be a pair: choosing "downloaded only" with nothing
    // downloaded opened the download window, and stored the choice anyway so
    // it would take effect when an archive landed. Both were right while the
    // window sold that archive.
    //
    // The USGS sheet is withdrawn, so on this phone there is one background
    // and the picker renders nothing (chrome/BackgroundPicker.tsx). The rule
    // those tests covered is not deleted - App's `handleChangeBackground`
    // still opens the window for an unobtainable choice - it simply cannot be
    // reached from any screen until the sheet comes back. What IS still
    // reachable is asserted directly below, on a phone holding the archive.
    const user = userEvent.setup()
    returningHiker()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(await screen.findByRole('button', { name: /legend/i }))

    const legend = await screen.findByRole('dialog', { name: 'Legend' })
    expect(within(legend).queryByRole('group', { name: /background/i })).toBeNull()
    expect(within(legend).queryByRole('radio', { name: /downloaded/i })).toBeNull()
  })

  it('does not interrupt that choice on a phone that already has the download', async () => {
    const user = userEvent.setup()
    returningHiker()
    withDownloadedArchive()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(await screen.findByRole('button', { name: /legend/i }))
    await user.click(await screen.findByRole('radio', { name: /downloaded/i }))

    await waitFor(() => {
      const saved = store.get(PREFERENCES_KEY) as { background_source: string }
      expect(saved.background_source).toBe('usgs_topo_offline')
    })
    expect(screen.queryByRole('dialog', { name: /offline map/i })).toBeNull()
  })

  it('closes the legend it was opened from, rather than stacking two dialogs', async () => {
    // One thing open at a time. Both announce themselves as modal dialogs on a
    // phone, and leaving the legend behind would put a screen-reader user
    // inside one with the other on top of it.
    const user = userEvent.setup()
    returningHiker()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await openDownloads(user)

    expect(screen.queryByRole('dialog', { name: /legend/i })).toBeNull()
  })

  it('reaches the download from More as well, through the same picker', async () => {
    const user = userEvent.setup()
    returningHiker()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /download/i }))

    expect(
      await screen.findByRole('dialog', { name: /offline map/i }),
    ).toBeInTheDocument()
  })

  it('comes back to the view the hiker left, not to the whole trail, after another tab', async () => {
    // The bug, and then the bug behind it. First pass: the map screen
    // unmounted whenever another tab was showing, so coming back built a new
    // map - and the new one was handed the opening corridor bounds again,
    // throwing away where someone had zoomed to. The fix then was to hand the
    // REBUILT map the saved camera. #1081 removed the rebuild itself: a trip
    // through another tab hides the map without unmounting it, so the same
    // map survives with its camera untouched - the stronger form of the same
    // promise, and what this test asserts now. If the shell ever goes back
    // to a rebuild per tab switch, the identity check below is what fails.
    const user = userEvent.setup()
    returningHiker()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    const opening = await liveMap()
    // Stand in for the hiker panning and zooming to a shelter.
    opening.center = { lng: -78.4, lat: 38.6 }
    opening.zoom = 15
    act(() => opening.emit('moveend'))

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await screen.findByRole('heading', { name: 'More' })
    await user.click(screen.getByRole('tab', { name: 'Map' }))
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    // The same map, still up, still where the hiker put it - not a second
    // build that was handed the camera back.
    const survivor = await liveMap()
    expect(survivor).toBe(opening)
    expect(MockMap.instances).toHaveLength(1)
    expect(survivor.center).toEqual({ lng: -78.4, lat: 38.6 })
    expect(survivor.zoom).toBe(15)
  })

  it('opens on the whole corridor when there is no view to come back to', async () => {
    returningHiker()
    render(<App />)
    await openMapTab()
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
    await openMapTab()
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

  it('opens the card on the part that was searched for, even when it has no pin of its own', async () => {
    // §3 of #527. Selecting a result moved the camera and opened nothing, which
    // was survivable while every POI had a pin and became a dead end when sites
    // landed: `composeSites` takes a folded member out of the source, so this
    // privy is not on the map at all - it rides the shelter's pin. Searching it
    // centred the map on a coordinate with nothing there and said nothing.
    const user = userEvent.setup()
    returningHiker()
    store.set(
      'ourhike:trails',
      new Blob([JSON.stringify({ type: 'FeatureCollection', features: [] })]),
    )
    store.set('ourhike:pois', [
      {
        id: 'atc_shelters:algo',
        type: 'shelter',
        name: 'Mt. Algo Shelter',
        lat: 41.66,
        lon: -73.48,
        confidence: 'high',
        siteId: 'site:algo',
        siteRole: 'anchor',
      },
      {
        id: 'atc_privies:algo',
        type: 'privy',
        name: 'Mt. Algo Shelter Privy',
        lat: 41.6604,
        lon: -73.4803,
        confidence: 'high',
        siteId: 'site:algo',
        siteRole: 'member',
      },
    ])

    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('button', { name: 'Search' }))
    await user.type(await screen.findByRole('searchbox'), 'algo shelter privy')
    await user.click(await screen.findByRole('button', { name: /algo shelter privy/i }))

    // The card is open AND showing the privy - not the shelter that carries the
    // pin. `aria-current` is what PoiCard marks the shown chip with, so this
    // asserts which part the card landed on rather than merely that a card
    // exists, which the shelter would also satisfy.
    const card = await screen.findByRole('dialog')
    // The strip lives in the opened card (#941), so the assertion opens it -
    // what is being checked is which part the card LANDED on, and the peek
    // says that with its heading rather than with a chip.
    expect(
      within(card).getByRole('heading', { name: 'Mt. Algo Shelter Privy' }),
    ).toBeInTheDocument()
    await user.click(within(card).getByTestId('poi-card-expand'))
    expect(
      within(card).getByRole('button', { name: /privy/i, current: true }),
    ).toBeInTheDocument()
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
    await openMapTab()
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

    await openMapTab()

    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /^volunteer & report/i }))
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

    await openMapTab()

    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /^volunteer & report/i }))
    await user.click(await screen.findByRole('button', { name: /report a problem/i }))
    await user.click(await screen.findByRole('button', { name: /^cancel$/i }))

    expect(await screen.findByRole('heading', { name: 'Contribute' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'More', selected: true })).toBeInTheDocument()
  })

  it('saves a report to the outbox rather than asking to sign in first', async () => {
    const user = userEvent.setup()
    returningHiker()
    render(<App />)

    await openMapTab()

    await screen.findByRole('region', { name: /trail map/i })
    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /^volunteer & report/i }))
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

    await openMapTab()

    await screen.findByRole('region', { name: /trail map/i })
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
      expect(queued[0].payload.lat).toBeUndefined()
      expect(queued[0].payload.lon).toBeUndefined()
    })
  })

  it('warns in the download window when no data source was configured at build time', async () => {
    const user = userEvent.setup()
    returningHiker()
    render(<App />)

    await openMapTab()

    await screen.findByRole('region', { name: /trail map/i })
    await openDownloads(user)

    // VITE_DATA_BASE_URL is unset under test, so this is the real state - and a
    // download that would silently 404 is worth saying out loud.
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/built without a place to download maps/i)
    // In the hiker's language, to the one person guaranteed to read it: no env
    // var names in a role="alert". The builder finds theirs via lib/config.ts.
    expect(alert).not.toHaveTextContent(/VITE_|BASE_URL|bucket/i)
  })

  it('keeps that warning inside the window rather than over the map', async () => {
    // The notices belong to the download and travelled with it. Left on a
    // screen, an archive that failed overnight would announce itself over the
    // map for the rest of the walk.
    const user = userEvent.setup()
    returningHiker()
    render(<App />)

    await openMapTab()

    await screen.findByRole('region', { name: /trail map/i })
    await openDownloads(user)
    await user.click(screen.getByRole('button', { name: /close/i }))

    expect(screen.queryByRole('alert')).toBeNull()
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

    await openMapTab()

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

    await openMapTab()

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
      await openMapTab()
      await screen.findByRole('region', { name: /trail map/i })
      // Node reports an unhandled rejection only after the microtask queue
      // has drained and the promise is still handler-less, so this has to
      // outlast a macrotask - the same reasoning as rejectionsWhile in
      // useAppUpdate.test.ts. A deliberate real-clock wait, kept (#323): it
      // waits for the ABSENCE reporter, not for the app.
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
            headers: new Headers(),
            arrayBuffer: () =>
              Promise.resolve(
                new TextEncoder().encode('{"type":"FeatureCollection","features":[]}')
                  .buffer,
              ),
            blob: () =>
              Promise.resolve(new Blob(['{"type":"FeatureCollection","features":[]}'])),
            text: () => Promise.resolve('{"features":[]}'),
          } as unknown as Response),
    )

    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await openDownloads(user)
    const card = await hikingSheetCard()
    await user.click(within(card).getByRole('button', { name: /download the map/i }))

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
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await openDownloads(user)
    const card = await hikingSheetCard()
    await user.click(within(card).getByRole('button', { name: /download the map/i }))

    await waitFor(() => {
      expect(screen.getByText(/trail details could not be fetched/i)).toBeInTheDocument()
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
    await openMapTab()
    const nav = await navigationControl(await liveMap())

    expect(nav.options?.showZoom).toBe(true)
  })

  it('keeps them off a touch screen, where they would cost the thumb zone', async () => {
    pointerIsFine(false)
    returningHiker()

    render(<App />)
    await openMapTab()
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
    await openMapTab()

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
    await openMapTab()

    const sources = Object.keys(styleOf(await liveMap()).sources)

    expect(sources).toContain('usgs-topo')
    expect(sources).toContain('trails')
  })

  it('fetches the live sheet by default when Data Saver is off', async () => {
    setSaveData(false)
    returningHiker()
    render(<App />)
    await openMapTab()

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
    await openMapTab()
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
    await openMapTab()

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
    await openMapTab()

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
    await openMapTab()

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
    await openMapTab()

    // Something is on screen, and it says which screen went.
    expect(await screen.findByRole('alert')).toHaveTextContent(/map stopped working/i)
    // And the way out is still there, which is the whole point.
    await user.click(screen.getByRole('tab', { name: 'More' }))
    expect(await screen.findByRole('heading', { name: 'More' })).toBeInTheDocument()
  })

  it('can still reach the download when the map has fallen over', async () => {
    // The window is outside the error boundary on purpose. A map that failed
    // because there is nothing to draw is exactly the case where the download
    // is the fix, and losing the door to it with the map would be circular.
    const user = userEvent.setup()
    returningHiker()
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const MapLibre = await import('maplibre-gl')
    vi.spyOn(MapLibre, 'Map').mockImplementation(() => {
      throw new Error('WebGL context could not be created')
    })

    render(<App />)
    await openMapTab()
    await screen.findByRole('alert')

    await user.click(screen.getByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /download/i }))

    expect(
      await screen.findByRole('dialog', { name: /offline map/i }),
    ).toBeInTheDocument()
  })
})

// #216, reported from a real phone: a complete 314 MB download, the offline
// background selected, and no background drawn at all. The archive was
// present, complete and correctly counted - the pipeline simply exported from
// z6 while the app opens on the whole trail at about z4, and nothing anywhere
// compared the two numbers.
describe('an archive that does not reach the view', () => {
  /** A finished archive whose header declares the zooms it really holds. */
  function archiveCovering(minZoom: number) {
    withDownloadedArchive()
    archiveHeader.value = { minZoom, maxZoom: 12 }
  }

  /** Report a camera position, the way a real moveend does. */
  async function atZoom(zoom: number) {
    const live = await liveMap()
    live.zoom = zoom
    live.center = { lng: -77, lat: 39 }
    act(() => live.emit('moveend'))
  }

  /**
   * The map, once the archive's coverage has actually been applied to it.
   *
   * Three things have to land before the flag below can mean anything, and
   * they land in an order this test does not control: the archive read says
   * downloaded, the background flips to offline (which rebuilds the map), and
   * the header read reports the zoom range. The clamp firing is the one
   * observable event that proves all three - so waiting for it is the
   * precondition, not an assertion.
   *
   * Without it these passed locally and failed on CI, where the ordering came
   * out differently. A `findByText` retry window does not fix that: a rebuild
   * lands a fresh map with no reported camera, so the moveend this test fired
   * beforehand is simply gone.
   */
  async function offlineMapSettledAt(floor: number) {
    await waitFor(() => expect(MockMap.live[0]?.getZoom()).toBe(floor))
  }

  it('opens the map at the archive floor rather than on blank paper', async () => {
    returningHiker()
    store.set(PREFERENCES_KEY, {
      ...DEFAULT_PREFERENCES,
      onboarding_completed: true,
      download_choice_made: true,
      background_source: 'usgs_topo_offline',
    })
    archiveCovering(6)

    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })

    // MockMap does not fit bounds, so it starts at 0 - under any real floor,
    // and the state the clamp exists for. 5, not the header's 6: under the
    // @2x tileSize declaration (#191) camera z5 already draws z6 tiles.
    await waitFor(() => expect(MockMap.live[0]?.getZoom()).toBe(5))
  })

  it('says so when the hiker zooms out past what the download covers', async () => {
    returningHiker()
    store.set(PREFERENCES_KEY, {
      ...DEFAULT_PREFERENCES,
      onboarding_completed: true,
      download_choice_made: true,
      background_source: 'usgs_topo_offline',
    })
    archiveCovering(6)

    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await offlineMapSettledAt(5)
    await atZoom(3)

    expect(await screen.findByText(/zoomed out past your download/i)).toBeVisible()
  })

  it('stays quiet once the view is back inside the download', async () => {
    returningHiker()
    store.set(PREFERENCES_KEY, {
      ...DEFAULT_PREFERENCES,
      onboarding_completed: true,
      download_choice_made: true,
      background_source: 'usgs_topo_offline',
    })
    archiveCovering(6)

    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await offlineMapSettledAt(5)
    await atZoom(3)
    await screen.findByText(/zoomed out past your download/i)

    await atZoom(11)

    await waitFor(() =>
      expect(screen.queryByText(/zoomed out past your download/i)).toBeNull(),
    )
  })

  it('never says it on the live sheet, which covers every zoom', async () => {
    returningHiker()
    archiveCovering(6)

    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await atZoom(3)

    expect(screen.queryByText(/zoomed out past your download/i)).toBeNull()
  })

  it('claims nothing before the archive has said what it holds', async () => {
    // No archive at all: coverage is unknown, and unknown must not render as
    // "your download does not reach here".
    returningHiker()
    store.set(PREFERENCES_KEY, {
      ...DEFAULT_PREFERENCES,
      onboarding_completed: true,
      download_choice_made: true,
      background_source: 'usgs_topo_offline',
    })

    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await atZoom(3)

    expect(screen.queryByText(/zoomed out past your download/i)).toBeNull()
  })
})

describe('a storage read that fails', () => {
  it('still opens the app instead of a permanently blank page', async () => {
    // Safari private browsing, an evicted database, iOS Lockdown - IndexedDB
    // reads can reject wholesale. The preferences read used to have no
    // rejection handler, so `preferencesLoaded` never turned true and the
    // shell rendered null forever: a white screen with the whole map one
    // tick away. Falling back to defaults means first-run onboarding, which
    // is a working app rather than a blank one.
    vi.mocked(get).mockImplementation((key) =>
      key === PREFERENCES_KEY
        ? Promise.reject(new Error('The user denied permission to access the database.'))
        : Promise.resolve(store.get(key as string)),
    )

    render(<App />)

    expect(await screen.findByText('What OurHike is')).toBeInTheDocument()
  })
})

// --- The desktop planning station (#1054) ----------------------------------
//
// Above the breakpoint the Today tab stops being its own screen: the map
// branch renders, with the journal docked beside the canvas and the mode
// switch in the sidebar. What is asserted here is the wiring - which branch
// renders, that both surfaces are present, and that the sidebar's switch
// writes through to the same store the Today header's does. How the column
// LOOKS is desktop.css, under test/desktopLayout.test.ts's contract.

describe('the desktop planning station (#1054)', () => {
  it('reads the journal beside the map on the Today tab', async () => {
    onADesktop()
    returningHiker()
    const { container } = render(<App />)

    // The map screen is what renders - Today is the active tab, not a
    // separate screen replacing the canvas.
    expect(await screen.findByRole('region', { name: /trail map/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Today', selected: true })).toBeInTheDocument()
    expect(container.querySelector('.map-screen__journal .today')).not.toBeNull()
  })

  it('keeps the journal off the Map tab, which is the map alone', async () => {
    onADesktop()
    returningHiker()
    const user = userEvent.setup()
    const { container } = render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    await user.click(screen.getByRole('tab', { name: 'Map' }))

    expect(container.querySelector('.map-screen__journal')).toBeNull()
    expect(screen.getByRole('region', { name: /trail map/i })).toBeInTheDocument()
  })

  it('keeps the phone as it was: Today is its own screen, no journal column', async () => {
    returningHiker()
    const { container } = render(<App />)

    // The Today screen renders directly - no map region behind it.
    expect(await screen.findByText(/location is off/i)).toBeInTheDocument()
    expect(container.querySelector('.map-screen__journal')).toBeNull()
    expect(screen.queryByRole('region', { name: /trail map/i })).toBe(null)
  })

  it('offers the mode switch in the sidebar, writing through to the phone store', async () => {
    onADesktop()
    returningHiker()
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('region', { name: /trail map/i })

    // Scoped to the navigation: the journal's own (CSS-hidden) copy of the
    // switch is still in the tree under jsdom, and the sidebar's is the one
    // this test is about.
    const nav = screen.getByRole('navigation', { name: 'Main' })
    const group = within(nav).getByRole('radiogroup', { name: /today i/i })
    await user.click(within(group).getByRole('radio', { name: 'Volunteer' }))

    await waitFor(() => expect(store.get(HIKER_MODE_KEY)).toBe('volunteer'))
  })

  it('keeps the mode switch out of the phone bar, which has no room for it', async () => {
    returningHiker()
    render(<App />)
    await screen.findByText(/location is off/i)

    const nav = screen.getByRole('navigation', { name: 'Main' })
    expect(within(nav).queryByRole('radiogroup')).toBe(null)
  })
})
