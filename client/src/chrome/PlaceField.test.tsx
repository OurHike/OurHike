import { describe, it, expect, vi, afterEach } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PlaceField, placeMeta, placeTitle } from './PlaceField'
import { NO_PLACES, type Place, type PlacesDocument } from '../lib/places'

const PARK: Place = {
  id: 'oprhp_park_polygons:1',
  name: 'Harriman State Park',
  kind: 'park',
  category: 'State Park',
  state: 'NY',
  lon: -74.1,
  lat: 41.25,
  bbox: [-74.2, 41.2, -74.0, 41.3],
  trailMiles: 46.3,
}
const TRAILHEAD: Place = {
  id: 'atc_parking:7',
  name: 'Reeves Meadow Visitor Center',
  kind: 'trailhead',
  state: 'NY',
  within: 'Harriman State Park',
  lon: -74.1,
  lat: 41.2,
  trailMiles: 12,
}
const TOWN: Place = {
  id: 'c1',
  name: 'Harriman',
  kind: 'town',
  state: 'TN',
  lon: -84.5,
  lat: 35.9,
}

const DOCUMENT: PlacesDocument = {
  generatedAt: '2026-09-10T00:00:00Z',
  trailRadiusMiles: 5,
  trailMilesMeasured: true,
  places: [PARK, TRAILHEAD, TOWN],
}

afterEach(() => cleanup())

const PROPS = {
  places: DOCUMENT,
  settled: true,
  online: true,
  units: 'imperial' as const,
  picked: null,
  onPick: vi.fn(),
  label: 'Where do you hike',
}

describe('a place row', () => {
  it('prints the publisher’s category, the state, and the trail the app holds there', () => {
    expect(placeTitle(PARK)).toBe('Harriman State Park, NY')
    expect(placeMeta(PARK, 'imperial', true)).toBe('state park · 46 mi of trail held')
    expect(placeMeta(PARK, 'metric', true)).toBe('state park · 75 km of trail held')
  })

  it('names the park a trailhead sits in ahead of its own miles', () => {
    expect(placeMeta(TRAILHEAD, 'imperial', true)).toBe('trailhead · Harriman State Park')
  })

  it('says "no trail data held" only when something measured and found nothing', () => {
    expect(placeMeta(TOWN, 'imperial', true)).toBe('town · no trail data held')
    // The published index writes a measured nothing as `trailMiles: 0.0`
    // (Harrisonburg, VA in UA's 2026-09-10 release); that is the same
    // nothing, not "0 mi of trail held".
    expect(placeMeta({ ...TOWN, trailMiles: 0 }, 'imperial', true)).toBe(
      'town · no trail data held',
    )
    // And a measured fraction of a mile keeps its tenth rather than
    // rounding to the zero sentence's figure.
    expect(placeMeta({ ...TOWN, trailMiles: 0.4 }, 'imperial', true)).toBe(
      'town · 0.4 mi of trail held',
    )
    // An unmeasured document is silent rather than claiming there is none.
    expect(placeMeta(TOWN, 'imperial', false)).toBe('town')
  })
})

describe('PlaceField', () => {
  it('resolves what is typed against the index and hands back the row taken', async () => {
    const user = userEvent.setup()
    const onPick = vi.fn()
    render(<PlaceField {...PROPS} onPick={onPick} />)

    await user.type(screen.getByRole('searchbox', { name: 'Where do you hike' }), 'harr')

    const rows = screen.getAllByRole('button')
    expect(rows.map((row) => row.textContent)).toEqual([
      'Harriman State Park, NYstate park · 46 mi of trail held',
      'Harriman, TNtown · no trail data held',
    ])

    await user.click(rows[0])
    expect(onPick).toHaveBeenCalledWith(PARK)
  })

  it('marks the place already taken', async () => {
    const user = userEvent.setup()
    render(<PlaceField {...PROPS} picked={PARK} />)

    await user.type(screen.getByRole('searchbox'), 'harriman state')

    expect(screen.getByRole('button', { name: /Harriman State Park/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('says when nothing matches, and what to try instead', async () => {
    const user = userEvent.setup()
    render(<PlaceField {...PROPS} />)

    await user.type(screen.getByRole('searchbox'), 'zzz')

    expect(screen.getByRole('status')).toHaveTextContent(/nothing here by that name/i)
    expect(screen.queryByRole('list')).toBeNull()
  })

  it('tells still-looking from nothing-on-the-phone from nothing-published, and names the way out of each', () => {
    const { rerender } = render(
      <PlaceField {...PROPS} places={NO_PLACES} settled={false} />,
    )
    expect(screen.getByRole('status')).toHaveTextContent(/looking for the list/i)
    expect(screen.getByRole('searchbox')).toBeEnabled()

    rerender(<PlaceField {...PROPS} places={NO_PLACES} settled online={false} />)
    expect(screen.getByRole('status')).toHaveTextContent(/arrives with signal/i)
    expect(screen.getByRole('status')).toHaveTextContent(/More → You/)
    expect(screen.getByRole('searchbox')).toBeDisabled()

    rerender(<PlaceField {...PROPS} places={NO_PLACES} settled online />)
    expect(screen.getByRole('status')).toHaveTextContent(/not been published yet/i)
    expect(screen.getByRole('status')).toHaveTextContent(/More → You/)
  })
})
