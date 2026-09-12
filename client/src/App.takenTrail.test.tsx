import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import App from './App'
import { appHarness, openMapTab } from './test/appHarness'

// The map's plate is named for what is taken (the maintainer's review of
// #1374, 2026-09-10), never for the A.T. by default. A fresh install names
// the place the hiker gave, or says no trail is taken; the ATC's mark and
// "Off the trail" arrive only once a long hike or a tap on the line has
// taken the trail. lib/takenTrail.ts is the store; chrome/LineSheet.test.tsx
// holds the tap itself, and this file holds what the shell does with it.

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

const app = appHarness({ navigator: { geolocation: true } })

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

async function plate() {
  await openMapTab()
  return within(await screen.findByRole('banner'))
}

describe('the plate, and what it is named for', () => {
  it('says no trail is taken on a fresh install, with no mark and no "Off the trail"', async () => {
    app.onboard()
    render(<App />)

    const banner = await plate()
    expect(banner.getByText('No trail taken')).toBeInTheDocument()
    expect(banner.queryByText(/Appalachian Trail/)).toBeNull()
    expect(document.querySelector('.map-plate__trail-logo')).toBeNull()
    expect(banner.getByText('Location is off')).toBeInTheDocument()
  })

  it('names the place the hiker gave at first run while nothing is taken', async () => {
    app.onboard({ default_place: HARRIMAN })
    render(<App />)

    const banner = await plate()
    expect(banner.getByText('Harriman State Park')).toBeInTheDocument()
    expect(banner.queryByText(/Appalachian Trail/)).toBeNull()
  })

  it('names a taken trail and wears its mark, and the mile is its to give', async () => {
    app.onboard({ default_place: HARRIMAN }, { takenTrail: 'AT' })
    render(<App />)

    const banner = await plate()
    expect(banner.getByText('Appalachian Trail')).toBeInTheDocument()
    expect(banner.queryByText('Harriman State Park')).toBeNull()
    // The mark is decorative (alt="", aria-hidden), so it is found by its
    // class rather than a role it deliberately does not have.
    expect(document.querySelector('.map-plate__trail-logo')).not.toBeNull()
  })

  it('with a fix and nothing taken, says where the fix stands rather than "Off the trail"', async () => {
    app.onboard({ location_permission_requested: true })
    app.putTrailData()
    render(<App />)

    const banner = await plate()
    await app.reportFixAtMile(12)
    expect(
      await banner.findByText('Located · tap a trail to take it'),
    ).toBeInTheDocument()
    expect(banner.queryByText(/Off the trail|^mi /)).toBeNull()
  })

  it('with a fix and the trail taken, reads the mile as before', async () => {
    app.onboard({ location_permission_requested: true }, { takenTrail: 'AT' })
    app.putTrailData()
    render(<App />)

    const banner = await plate()
    await app.reportFixAtMile(12)
    expect(await banner.findByText(/^mi 12\.0/)).toBeInTheDocument()
  })
})
