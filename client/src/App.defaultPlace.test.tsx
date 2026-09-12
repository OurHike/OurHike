import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { MockMap } from './test/mocks/maplibre-gl'
import { appHarness, openMapTab, stubDesktop } from './test/appHarness'
import { CAMERA_MEMORY_KEY } from './lib/cameraMemory'
import { PREFERENCES_KEY } from './lib/preferences'
import type { UserPreferences } from './lib/userPreferences'
import type { PlacesDocument } from './lib/places'

// Where the hiker hikes (#1373, first run's frame 1b and More → You), as the
// shell keeps it: a preference (`default_place`, synced since 2026-09-10 at
// the maintainer's decision - lib/defaultPlace.ts says why) that decides
// what the map opens on when there is no remembered camera and nothing
// else. These are the promises across the two doors - first run writes it
// and the map is built around it; More → You reads it back, changes it and
// forgets it.

vi.mock('maplibre-gl', () => import('./test/mocks/maplibre-gl'))
vi.mock('idb-keyval', () => ({
  get: vi.fn(),
  getMany: vi.fn(),
  set: vi.fn(),
  setMany: vi.fn(),
  del: vi.fn(),
  update: vi.fn(),
}))
vi.mock('./map/archiveZooms', () => ({
  readArchiveZooms: () => Promise.resolve(null),
  readArchiveFootprint: () => Promise.resolve(null),
}))

const { PLACES } = vi.hoisted(() => {
  const PLACES: PlacesDocument = {
    generatedAt: '2026-09-10T00:00:00Z',
    trailRadiusMiles: 5,
    trailMilesMeasured: true,
    places: [
      {
        id: 'oprhp_park_polygons:1',
        name: 'Harriman State Park',
        kind: 'park',
        category: 'State Park',
        state: 'NY',
        lon: -74.1,
        lat: 41.25,
        bbox: [-74.2, 41.2, -74.0, 41.3],
        trailMiles: 46.3,
      },
      { id: 'c1', name: 'Harriman', kind: 'town', state: 'TN', lon: -84.5, lat: 35.9 },
    ],
  }
  return { PLACES }
})
vi.mock('./lib/usePlaces', () => ({
  usePlaces: () => ({ places: PLACES, settled: true }),
}))

const app = appHarness()

const HARRIMAN = {
  id: 'oprhp_park_polygons:1',
  name: 'Harriman State Park',
  kind: 'park',
  category: 'State Park',
  state: 'NY',
  lon: -74.1,
  lat: 41.25,
  bbox: [-74.2, 41.2, -74.0, 41.3],
}

describe('first run’s "where do you hike?"', () => {
  it('keeps the place on this phone and builds the first map around it', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(await screen.findByRole('button', { name: 'Get set up' }))
    // Past the mode card (the review of #1374); the place is the subject here.
    await user.click(screen.getByRole('button', { name: /^skip — day hike/i }))
    await user.type(
      await screen.findByRole('searchbox', { name: 'Where do you hike' }),
      'harr',
    )
    await user.click(screen.getByRole('button', { name: /Harriman State Park/ }))
    await user.click(screen.getByRole('button', { name: 'Use Harriman State Park' }))
    await user.click(screen.getByRole('button', { name: 'Decide this later' }))
    await user.click(
      screen.getByRole('button', { name: 'Use Harriman State Park instead' }),
    )

    // On the preferences, and a snapshot rather than the index row - no
    // measurement rides along to go stale under the phone.
    await waitFor(() => expect(storedPlace()).toEqual(HARRIMAN))

    // The map opens fitted to the park, not to the whole corridor.
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await waitFor(() => expect(MockMap.instances).toHaveLength(1))
    expect(MockMap.instances[0].options.bounds).toEqual([
      [-74.2, 41.2],
      [-74.0, 41.3],
    ])
  })

  it('outranks a camera the tab remembered - the choice just made is what the map opens on', async () => {
    // A returning tab (lib/cameraMemory.ts, session storage) used to win over
    // the place picked two cards earlier: the maintainer chose Hudson
    // Highlands on the preview and the map opened on the corridor view the
    // tab had kept (2026-09-10).
    window.sessionStorage.setItem(
      CAMERA_MEMORY_KEY,
      JSON.stringify({ center: [-77.5, 39.5], zoom: 5 }),
    )
    const user = userEvent.setup()
    render(<App />)

    await user.click(await screen.findByRole('button', { name: 'Get set up' }))
    await user.click(screen.getByRole('button', { name: /^skip — day hike/i }))
    await user.type(
      await screen.findByRole('searchbox', { name: 'Where do you hike' }),
      'harr',
    )
    await user.click(screen.getByRole('button', { name: /Harriman State Park/ }))
    await user.click(screen.getByRole('button', { name: 'Use Harriman State Park' }))
    await user.click(screen.getByRole('button', { name: 'Decide this later' }))
    await user.click(
      screen.getByRole('button', { name: 'Use Harriman State Park instead' }),
    )

    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await waitFor(() => expect(MockMap.instances).toHaveLength(1))
    expect(MockMap.instances[0].options.bounds).toEqual([
      [-74.2, 41.2],
      [-74.0, 41.3],
    ])
  })

  it('on a laptop, whose map is built under the cards, moves that map to the place when the cards end', async () => {
    // The entry-end re-fit (#1296) used to put the corridor back over a
    // place chosen a card earlier; now it agrees with the choice.
    stubDesktop()
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('button', { name: 'Get set up' })
    await waitFor(() => expect(MockMap.live.length).toBeGreaterThan(0))
    const map = MockMap.live[0]

    await user.click(screen.getByRole('button', { name: 'Get set up' }))
    await user.click(screen.getByRole('button', { name: /^skip — day hike/i }))
    await user.type(
      await screen.findByRole('searchbox', { name: 'Where do you hike' }),
      'harr',
    )
    await user.click(screen.getByRole('button', { name: /Harriman State Park/ }))
    await user.click(screen.getByRole('button', { name: 'Use Harriman State Park' }))
    await user.click(screen.getByRole('button', { name: 'Decide this later' }))
    await user.click(
      screen.getByRole('button', { name: 'Use Harriman State Park instead' }),
    )

    await waitFor(() =>
      expect(map.cameraMoves.at(-1)?.fitBounds).toEqual([
        [-74.2, 41.2],
        [-74.0, 41.3],
      ]),
    )
  })
})

/** The place as the preferences blob on the phone holds it. */
const storedPlace = () =>
  (app.store.get(PREFERENCES_KEY) as Partial<UserPreferences> | undefined)
    ?.default_place ?? null

describe('More → You, "Where you hike"', () => {
  beforeEach(() => app.onboard())

  it('reads the kept place, and forgets it from the sheet', async () => {
    app.store.set(PREFERENCES_KEY, {
      ...(app.store.get(PREFERENCES_KEY) as Partial<UserPreferences> | undefined),
      default_place: HARRIMAN,
    })
    const user = userEvent.setup()
    render(<App />)

    await user.click(await screen.findByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /^You/ }))
    const row = (await screen.findByText('Where you hike')).parentElement!
    expect(row).toHaveTextContent('Harriman State Park, NY')

    await user.click(within(row).getByRole('button', { name: 'Change' }))
    const sheet = await screen.findByRole('dialog', { name: 'Where you hike' })
    expect(sheet).toHaveTextContent(/Now Harriman State Park, NY/)

    await user.click(
      within(sheet).getByRole('button', { name: 'Forget Harriman State Park' }),
    )

    await waitFor(() => expect(storedPlace()).toBeNull())
    expect(screen.queryByRole('dialog', { name: 'Where you hike' })).toBeNull()
    expect((await screen.findByText('Where you hike')).parentElement).toHaveTextContent(
      'Not set',
    )
  })

  it('sets one where there was none', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(await screen.findByRole('tab', { name: 'More' }))
    await user.click(await screen.findByRole('button', { name: /^You/ }))
    await user.click(await screen.findByRole('button', { name: 'Set' }))

    const sheet = await screen.findByRole('dialog', { name: 'Where you hike' })
    await user.type(within(sheet).getByRole('searchbox'), 'harriman')
    await user.click(within(sheet).getByRole('button', { name: /Harriman, TN/ }))
    await user.click(within(sheet).getByRole('button', { name: 'Use Harriman' }))

    await waitFor(() => expect(storedPlace()).toMatchObject({ id: 'c1', state: 'TN' }))
    expect((await screen.findByText('Where you hike')).parentElement).toHaveTextContent(
      'Harriman, TN',
    )
  })
})

// --- The map's search knows the places (#1373, frame 14d) ------------------
//
// The volunteer map's "place search" is the map's own search with the index
// under its waypoint matches: a park row moves the map to the park, fitted
// to its box, and the workday pins already drawn there are what a volunteer
// came to find. Held here because this file already owns the index mock.

describe('the map’s search, over the places index', () => {
  beforeEach(() => {
    app.onboard()
    app.putTrailData()
  })

  it('moves the map to a park picked by name, and closes the search', async () => {
    const user = userEvent.setup()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await waitFor(() => expect(MockMap.live.length).toBeGreaterThan(0))
    const map = MockMap.live[0]

    await user.click(screen.getByRole('button', { name: 'Search' }))
    await user.type(await screen.findByRole('searchbox'), 'harr')
    await user.click(
      await screen.findByRole('button', { name: /Harriman State Park, NY/ }),
    )

    // Fitted to the park's own box - `defaultPlaceCamera`'s rule, the same
    // one first run opens the map by - never a point at the corridor zoom.
    const moved = map.cameraMoves.at(-1)
    expect(moved?.fitBounds).toEqual([
      [-74.2, 41.2],
      [-74.0, 41.3],
    ])
    expect(screen.queryByRole('searchbox')).toBeNull()
  })

  it('centres on a point place at the planning zoom', async () => {
    const user = userEvent.setup()
    render(<App />)
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await waitFor(() => expect(MockMap.live.length).toBeGreaterThan(0))
    const map = MockMap.live[0]

    await user.click(screen.getByRole('button', { name: 'Search' }))
    await user.type(await screen.findByRole('searchbox'), 'harriman')
    // The town, which has no box: the second row, after the park.
    await user.click(await screen.findByRole('button', { name: /Harriman, TN/ }))

    const moved = map.cameraMoves.at(-1)
    expect(moved?.center).toEqual([-84.5, 35.9])
    expect(moved?.zoom).toBe(12)
  })
})
