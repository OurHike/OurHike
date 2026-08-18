// Tests for the trip switcher (#787).
//
// The point of the screen is that a second trip no longer destroys the
// first, so what is asserted here is mostly that both are there, that the
// open one is identifiable, and that deleting one takes a second tap.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { TripList } from './TripList'
import type { Hike } from '../lib/hikes'
import { buildPlan, type HikePlan } from '../lib/plan'
import type { StoredPoi } from '../lib/trailData'
import type { Trip } from '../lib/trips'

function plan(from: number, to: number, dated = false): HikePlan {
  return buildPlan(
    [
      { mile: from, name: 'Damascus', resupply: false },
      { mile: to, name: 'Atkins', resupply: false },
    ],
    { walkingHours: 7 },
    dated ? '2026-05-12' : undefined,
  )
}

const TRIPS: Trip[] = [
  { id: 'a', name: 'Spring section', plan: plan(470.8, 503.3, true) },
  { id: 'b', name: 'Grayson week', plan: plan(600, 620) },
]

const PROPS = {
  trips: TRIPS,
  openId: 'b',
  hikes: [] as readonly Hike[],
  pois: [] as readonly StoredPoi[],
  elevation: null,
  units: 'imperial' as const,
  onOpen: vi.fn(),
  onRename: vi.fn(),
  onRemove: vi.fn(),
  onNew: vi.fn(),
  onGroupIntoHike: vi.fn(),
  onClose: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the trip switcher', () => {
  it('lists every kept trip with its own figures', () => {
    render(<TripList {...PROPS} />)

    expect(screen.getByRole('button', { name: /Spring section/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Grayson week/ })).toBeInTheDocument()
    // Distance and days come off the plan, not from anything stored beside it.
    expect(screen.getByText(/32\.5 mi · 1 day/)).toBeInTheDocument()
    expect(screen.getByText(/20\.0 mi · 1 day/)).toBeInTheDocument()
    // A dated trip says when it starts; an undated one claims nothing.
    expect(screen.getByText(/from TUE 12/)).toBeInTheDocument()
  })

  it('marks which trip is open', () => {
    render(<TripList {...PROPS} />)
    expect(screen.getByText('open')).toBeInTheDocument()
  })

  it('opens a trip by tapping it', async () => {
    const user = userEvent.setup()
    render(<TripList {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /Spring section/ }))
    expect(PROPS.onOpen).toHaveBeenCalledWith('a')
  })

  it('renames through an inline field', async () => {
    const user = userEvent.setup()
    render(<TripList {...PROPS} />)

    await user.click(screen.getAllByRole('button', { name: 'Rename' })[0])
    const field = screen.getByLabelText('New name for Spring section')
    await user.clear(field)
    await user.type(field, 'Damascus to Atkins')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(PROPS.onRename).toHaveBeenCalledWith('a', 'Damascus to Atkins')
  })

  it('takes two taps to delete, and only deletes the one asked for', async () => {
    const user = userEvent.setup()
    render(<TripList {...PROPS} />)

    const deletes = screen.getAllByRole('button', { name: 'Delete' })
    await user.click(deletes[0])
    expect(PROPS.onRemove).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Tap again to delete' }))
    expect(PROPS.onRemove).toHaveBeenCalledTimes(1)
    expect(PROPS.onRemove).toHaveBeenCalledWith('a')
  })

  it('says what a walked trip is without scoring it', () => {
    const walked = buildPlan(
      [
        { mile: 470.8, name: 'Damascus', resupply: false },
        { mile: 503.3, name: 'Atkins', resupply: false },
      ],
      { walkingHours: 7 },
    )
    walked.days[0].walked = true

    const { container } = render(
      <TripList
        {...PROPS}
        trips={[{ id: 'c', name: 'Done', plan: walked }]}
        openId="c"
      />,
    )

    expect(screen.getByText('walked')).toBeInTheDocument()
    // A record, not a performance: no percentage, nothing left to catch up on.
    expect(container.textContent).not.toMatch(/%|behind|ahead of|complete/i)
  })

  it('says so when nothing is kept yet, and still offers the way in', async () => {
    const user = userEvent.setup()
    render(<TripList {...PROPS} trips={[]} openId={null} />)

    expect(screen.getByText(/Nothing kept yet/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Plan another trip' }))
    expect(PROPS.onNew).toHaveBeenCalled()
  })
})

describe('the hike over those trips (#788)', () => {
  const HIKE: Hike = {
    id: 'h1',
    name: 'Virginia, over a few years',
    type: 'section',
    start: { mile: 470.8 },
    end: { mile: 620 },
    tripIds: ['a', 'b'],
  }

  it('sums the walked ground and what is left, in miles and trips', () => {
    const walked = plan(470.8, 503.3, true)
    walked.days[0].walked = true
    const trips: Trip[] = [
      { id: 'a', name: 'Spring section', plan: walked },
      { id: 'b', name: 'Grayson week', plan: plan(600, 620) },
    ]

    render(<TripList {...PROPS} trips={trips} hikes={[HIKE]} />)

    expect(screen.getByText('Virginia, over a few years')).toBeInTheDocument()
    // 32.5 of 149.2 walked; the unwalked trip counts as no ground at all.
    expect(screen.getByText(/32\.5 mi walked · 116\.7 mi to go/)).toBeInTheDocument()
    expect(screen.getByText(/2 trips · 1 day walked/)).toBeInTheDocument()
  })

  it('never turns the roll-up into a score', () => {
    const { container } = render(<TripList {...PROPS} hikes={[HIKE]} />)

    expect(container.textContent).not.toMatch(/%|behind|ahead of|on track|streak/i)
  })

  it('says when an end rests on a reference this download has lost', () => {
    const stranded: Hike = { ...HIKE, start: { poiId: 'gone', mile: 470.8 } }
    render(<TripList {...PROPS} hikes={[stranded]} />)

    expect(
      screen.getByText(/points at a place this download doesn’t have/),
    ).toBeInTheDocument()
  })

  it('offers grouping only when there are trips and no hike yet', async () => {
    const user = userEvent.setup()
    const { rerender } = render(<TripList {...PROPS} />)

    await user.click(screen.getByRole('button', { name: 'Group these into one hike' }))
    expect(PROPS.onGroupIntoHike).toHaveBeenCalled()

    rerender(<TripList {...PROPS} hikes={[HIKE]} />)
    expect(screen.queryByRole('button', { name: 'Group these into one hike' })).toBeNull()
  })
})
