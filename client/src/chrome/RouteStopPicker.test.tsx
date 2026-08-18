// Tests for the stop picker (#755): one search screen behind every field -
// name-first results, the map and distance doors as rows, remove only where
// removing is honest, and the snap disclosed before anything is kept.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { RouteStopPicker } from './RouteStopPicker'
import type { StoredPoi } from '../lib/trailData'

const poi = (
  id: string,
  type: string,
  mile: number | undefined,
  name: string,
): StoredPoi => ({
  id,
  type,
  name,
  lat: 0,
  lon: 0,
  confidence: 'high',
  ...(mile === undefined ? {} : { mile }),
})

const POIS = [
  poi('s1', 'shelter', 516.1, 'Old Orchard Shelter'),
  poi('w1', 'water', 515.8, 'Old Orchard Spring'),
  poi('c1', 'campsite', 522.4, 'Orchard Hill Campsite'),
]

const CHOICES = [
  { id: 's1', name: 'Old Orchard Shelter', type: 'shelter', mile: 516.1 },
  { id: 'w1', name: 'Old Orchard Spring', type: 'water', mile: 515.8 },
  { id: 'c1', name: 'Orchard Hill Campsite', type: 'campsite', mile: 522.4 },
  // A designated A.T. Community, and an outfitter. Both are `resupply`;
  // only the layer that published them tells them apart (#802).
  {
    id: 't1',
    name: 'Damascus, VA',
    type: 'resupply',
    mile: 470.8,
    source: 'atc_communities',
  },
  {
    id: 'r1',
    name: 'Mount Rogers Outfitters',
    type: 'resupply',
    mile: 470.7,
    source: 'opentrail_at',
  },
]

const PROPS = {
  choices: CHOICES,
  pois: POIS,
  previous: { mile: 490.4, label: 'Wise Shelter' },
  south: false,
  removable: false,
  units: 'imperial' as const,
  onPick: vi.fn(),
  onMapPick: vi.fn(),
  onRemove: vi.fn(),
  onClose: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('searching by name', () => {
  it('matches like the waypoint search and shows type and mile', async () => {
    const user = userEvent.setup()
    render(<RouteStopPicker {...PROPS} />)

    await user.type(screen.getByLabelText('Search for a stop'), 'old or')
    expect(screen.getByText('Old Orchard Shelter')).toBeInTheDocument()
    expect(screen.getByText('Shelter · mi 516.1')).toBeInTheDocument()
    expect(screen.getByText('Old Orchard Spring')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Old Orchard Shelter/ }))
    expect(PROPS.onPick).toHaveBeenCalledWith({
      mile: 516.1,
      name: 'Old Orchard Shelter',
      poiId: 's1',
    })
  })

  it('says when a name is not in the download, in the search’s own words', async () => {
    const user = userEvent.setup()
    render(<RouteStopPicker {...PROPS} />)

    await user.type(screen.getByLabelText('Search for a stop'), 'katahdin')
    expect(
      screen.getByText(/may exist outside the part of the trail/),
    ).toBeInTheDocument()
  })
})

describe('the other doors', () => {
  it('offers the map always, the distance only with somewhere to measure from', () => {
    const { rerender } = render(<RouteStopPicker {...PROPS} />)

    expect(screen.getByRole('button', { name: 'Choose on the map' })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /A distance from Wise Shelter/ }),
    ).toBeInTheDocument()

    rerender(<RouteStopPicker {...PROPS} previous={null} />)
    expect(screen.queryByRole('button', { name: /A distance from/ })).toBeNull()
  })

  it('offers removal only for a destination between the ends', () => {
    const { rerender } = render(<RouteStopPicker {...PROPS} />)
    expect(screen.queryByRole('button', { name: 'Remove this stop' })).toBeNull()

    rerender(<RouteStopPicker {...PROPS} removable={true} />)
    expect(screen.getByRole('button', { name: 'Remove this stop' })).toBeInTheDocument()
  })

  it('states the centerline-only limit where the choosing happens', () => {
    render(<RouteStopPicker {...PROPS} />)
    expect(
      screen.getByText(/Only the AT centerline can carry a route/),
    ).toBeInTheDocument()
  })

  it('hands the map door to the shell', async () => {
    const user = userEvent.setup()
    render(<RouteStopPicker {...PROPS} />)

    await user.click(screen.getByRole('button', { name: 'Choose on the map' }))
    expect(PROPS.onMapPick).toHaveBeenCalled()
  })
})

describe('a distance from the previous stop', () => {
  it('snaps to the nearest place to sleep and shows it before anything is kept', async () => {
    const user = userEvent.setup()
    render(<RouteStopPicker {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /A distance from Wise Shelter/ }))
    expect(
      screen.getByRole('dialog', { name: 'A distance from here' }),
    ).toBeInTheDocument()

    // 26 miles north of 490.4 asks for 516.4: the shelter at 516.1 is the
    // snap, named and mile'd before the hiker commits.
    fireEvent.change(screen.getByLabelText('Miles from Wise Shelter'), {
      target: { value: '26' },
    })
    expect(screen.getByText('Lands near')).toBeInTheDocument()
    expect(screen.getByText('Old Orchard Shelter')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Use this stop' }))
    expect(PROPS.onPick).toHaveBeenCalledWith({
      mile: 516.1,
      name: 'Old Orchard Shelter',
      poiId: 's1',
    })
  })

  it('walks south when the route does', async () => {
    const user = userEvent.setup()
    render(
      <RouteStopPicker
        {...PROPS}
        south={true}
        previous={{ mile: 522.4, label: 'Orchard Hill' }}
      />,
    )

    await user.click(screen.getByRole('button', { name: /A distance from Orchard Hill/ }))
    fireEvent.change(screen.getByLabelText('Miles from Orchard Hill'), {
      target: { value: '6' },
    })
    // 6 miles SOUTH of 522.4 asks for 516.4 - the shelter, not the water.
    expect(screen.getByText('Old Orchard Shelter')).toBeInTheDocument()
    expect(screen.getByText(/south of Orchard Hill/)).toBeInTheDocument()
  })

  it('falls back to the bare clamped mile when nothing sleeps that way', async () => {
    const user = userEvent.setup()
    render(
      <RouteStopPicker
        {...PROPS}
        pois={[poi('w1', 'water', 515.8, 'Old Orchard Spring')]}
        previous={{ mile: 516.1, label: 'Old Orchard' }}
      />,
    )

    await user.click(screen.getByRole('button', { name: /A distance from Old Orchard/ }))
    fireEvent.change(screen.getByLabelText('Miles from Old Orchard'), {
      target: { value: '4' },
    })
    // Asked for 520.1; nothing sleepable lies north, so the bare mile is
    // offered as exactly that - clamped to the data's own reach (522.4).
    expect(screen.getByText('mi 520.1')).toBeInTheDocument()
    expect(screen.getByText(/no shelter or campsite nearby/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Use this stop' }))
    expect(PROPS.onPick).toHaveBeenCalledWith({ mile: 520.1 })
  })
})

describe('searching by mile, and telling a town from a shop (#802)', () => {
  it('answers a mile with what is around it, nearest first, on both sides', async () => {
    const user = userEvent.setup()
    render(<RouteStopPicker {...PROPS} />)

    await user.type(screen.getByLabelText('Search for a stop'), 'mi 516')

    expect(screen.getByText('Around mile 516')).toBeInTheDocument()
    const rows = screen.getAllByRole('listitem').map((row) => row.textContent)
    expect(rows[0]).toContain('Old Orchard Shelter')
    expect(rows[0]).toContain('0.1 mi north')
    expect(rows[1]).toContain('Old Orchard Spring')
    expect(rows[1]).toContain('0.2 mi south')
  })

  it('offers the bare mile too, because sometimes that is the answer', async () => {
    const user = userEvent.setup()
    render(<RouteStopPicker {...PROPS} />)

    await user.type(screen.getByLabelText('Search for a stop'), '500')
    await user.click(screen.getByRole('button', { name: /Just mile 500\.0/ }))

    expect(PROPS.onPick).toHaveBeenCalledWith({ mile: 500 })
  })

  it('calls a town a town, and an outfitter what it is', async () => {
    const user = userEvent.setup()
    render(<RouteStopPicker {...PROPS} />)

    await user.type(screen.getByLabelText('Search for a stop'), 'damas')
    const town = screen.getByRole('button', { name: /Damascus, VA/ })
    expect(town.textContent).toContain('town')
  })

  it('filters to towns, which is not a poi_type at all', async () => {
    const user = userEvent.setup()
    render(<RouteStopPicker {...PROPS} />)

    await user.click(screen.getByRole('button', { name: 'Towns' }))
    await user.type(screen.getByLabelText('Search for a stop'), 'o')

    // The outfitter is `resupply` too and is filtered out; the shelter and
    // the spring are other types entirely.
    expect(screen.queryByRole('button', { name: /Mount Rogers Outfitters/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Old Orchard Shelter/ })).toBeNull()
  })
})
