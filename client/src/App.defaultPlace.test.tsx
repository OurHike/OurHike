import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { MockMap } from './test/mocks/maplibre-gl'
import { appHarness, openMapTab } from './test/appHarness'
import { DEFAULT_PLACE_KEY } from './lib/defaultPlace'
import type { PlacesDocument } from './lib/places'

// Where the hiker hikes (#1373, first run's frame 1b and More → You), as the
// shell keeps it: a fact about this phone, in its own store, that decides
// what the map opens on when there is no remembered camera and nothing
// else. These are the promises across the two doors - first run writes it
// and the map is built around it; More → You reads it back, changes it and
// forgets it - and the one promise underneath: the key is never a synced
// preference (lib/defaultPlace.test.ts holds that half).

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

    // Its own key, and a snapshot rather than the index row - no
    // measurement rides along to go stale under the phone.
    await waitFor(() => expect(app.store.get(DEFAULT_PLACE_KEY)).toEqual(HARRIMAN))

    // The map opens fitted to the park, not to the whole corridor.
    await openMapTab()
    await screen.findByRole('region', { name: /trail map/i })
    await waitFor(() => expect(MockMap.instances).toHaveLength(1))
    expect(MockMap.instances[0].options.bounds).toEqual([
      [-74.2, 41.2],
      [-74.0, 41.3],
    ])
  })
})

describe('More → You, "Where you hike"', () => {
  beforeEach(() => app.onboard())

  it('reads the kept place, and forgets it from the sheet', async () => {
    app.store.set(DEFAULT_PLACE_KEY, HARRIMAN)
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

    await waitFor(() => expect(app.store.has(DEFAULT_PLACE_KEY)).toBe(false))
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

    await waitFor(() =>
      expect(app.store.get(DEFAULT_PLACE_KEY)).toMatchObject({ id: 'c1', state: 'TN' }),
    )
    expect((await screen.findByText('Where you hike')).parentElement).toHaveTextContent(
      'Harriman, TN',
    )
  })
})
