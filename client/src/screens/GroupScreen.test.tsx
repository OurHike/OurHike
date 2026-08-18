// Tests for a group's screen (#800).
//
// Two things are held here. What the screen SAYS it cannot do - no ribbon,
// no gaps - because a set with no two ends has nothing to draw them
// against, and leaving that unsaid makes it read as a missing feature. And
// the guard: a bucket of weekly day hikes is exactly where a streak would
// arrive uninvited.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { GroupScreen } from './GroupScreen'
import { buildPlan, type HikePlan } from '../lib/plan'
import type { TripGroup } from '../lib/tripGroups'
import type { Trip } from '../lib/trips'

function trip(id: string, name: string, from: number, to: number, date?: string): Trip {
  const plan: HikePlan = buildPlan(
    [
      { mile: from, resupply: false },
      { mile: to, resupply: false },
    ],
    { miles: 15 },
    date,
  )
  plan.days[0].walked = true
  return { id, name, plan }
}

const TRIPS: Trip[] = [
  trip('a', 'Bear Mountain loop', 0, 8.2, '2026-02-15'),
  trip('b', 'Anthony’s Nose', 20, 24.6, '2026-02-08'),
  trip('c', 'Not in the group', 40, 50),
]

const GROUP: TripGroup = { id: 'g', name: 'Every Sunday', tripIds: ['a', 'b'] }

const PROPS = {
  group: GROUP,
  trips: TRIPS as readonly Trip[],
  units: 'imperial' as const,
  onOpenTrip: vi.fn(),
  onAddTrip: vi.fn(),
  onRemoveTrip: vi.fn(),
  onRename: vi.fn(),
  onRemove: vi.fn(),
  onClose: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('a group', () => {
  it('rolls up trips, ground and days, and the span of dates', () => {
    render(<GroupScreen {...PROPS} />)

    expect(
      screen.getByText(/2 trips · 12\.8 mi of trail · 2 days walked/),
    ).toBeInTheDocument()
    expect(screen.getByText('SUN 8 – SUN 15')).toBeInTheDocument()
  })

  it('lists its trips earliest first, and nothing that is not in it', () => {
    render(<GroupScreen {...PROPS} />)

    const names = screen.getAllByRole('listitem').map((item) => item.textContent)
    expect(names[0]).toContain('Anthony’s Nose')
    expect(names[1]).toContain('Bear Mountain loop')
    expect(screen.queryByText('Not in the group')).toBeNull()
  })

  it('says what a group cannot do, rather than leaving a hole', () => {
    render(<GroupScreen {...PROPS} />)
    expect(screen.getByText(/No ribbon and no gaps here/)).toBeInTheDocument()
  })

  it('never turns a bucket of Sundays into a streak', () => {
    const { container } = render(<GroupScreen {...PROPS} />)
    expect(container.textContent).not.toMatch(
      /%|streak|in a row|behind|ahead of|on track|complete/i,
    )
  })

  it('offers only the trips that are not in it yet', async () => {
    const user = userEvent.setup()
    render(<GroupScreen {...PROPS} />)

    await user.click(screen.getByRole('button', { name: 'Add a trip' }))
    expect(screen.getByRole('button', { name: 'Not in the group' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Bear Mountain loop' })).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Not in the group' }))
    expect(PROPS.onAddTrip).toHaveBeenCalledWith('c')
  })

  it('takes a trip out without deleting it', async () => {
    const user = userEvent.setup()
    render(<GroupScreen {...PROPS} />)

    await user.click(screen.getAllByRole('button', { name: 'Take out' })[0])
    expect(PROPS.onRemoveTrip).toHaveBeenCalledWith('b')
  })

  it('promises the trips survive the group, and asks twice', async () => {
    const user = userEvent.setup()
    render(<GroupScreen {...PROPS} />)

    await user.click(screen.getByRole('button', { name: 'Delete this group' }))
    expect(PROPS.onRemove).not.toHaveBeenCalled()
    // The second tap says what will and will not happen.
    await user.click(screen.getByRole('button', { name: 'Tap again — the trips stay' }))
    expect(PROPS.onRemove).toHaveBeenCalled()
  })

  it('says so when nothing is in it, and that adding keeps other groups', () => {
    render(<GroupScreen {...PROPS} group={{ ...GROUP, tripIds: [] }} />)
    expect(
      screen.getByText(/stays in whatever other groups it is already in/),
    ).toBeInTheDocument()
  })
})
