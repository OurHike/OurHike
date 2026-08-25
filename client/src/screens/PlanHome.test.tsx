// The two Plan homes (#1008): the mode is the chrome, the switch chip is
// the door between the rooms, and each room's one action does what its
// label says.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { PlanHome, type PlanHomeProps } from './PlanHome'
import { PlanKindSheet } from '../chrome/PlanKindSheet'
import type { DayHike } from '../lib/dayHikes'
import type { Trip } from '../lib/trips'

function dayHike(id: string, overrides: Partial<DayHike> = {}): DayHike {
  return {
    id,
    name: id,
    date: null,
    segments: [
      [
        { coord: [-74.095, 41.25], poiId: null },
        { coord: [-74.085, 41.25], poiId: null },
      ],
    ],
    figures: { miles: 3.4, legs: [] },
    looped: false,
    recorded: 'planned',
    ...overrides,
  }
}

function trip(id: string): Trip {
  return {
    id,
    name: id,
    plan: {
      target: { miles: 8 },
      stops: [
        { mile: 3.2, resupply: false },
        { mile: 10.2, resupply: false },
      ],
      days: [{ id: `${id}-day`, pinned: false, generated: true }],
    },
  }
}

const PROPS: PlanHomeProps = {
  mode: 'day',
  onSwitchMode: vi.fn(),
  trips: [],
  hikes: [],
  dayHikes: [],
  groups: [],
  pois: [],
  units: 'imperial',
  openTrip: null,
  draftLive: false,
  onOpenTrip: vi.fn(),
  onOpenHike: vi.fn(),
  onOpenDayHike: vi.fn(),
  onOpenGroup: vi.fn(),
  onAllTrips: vi.fn(),
  onAllDayHikes: vi.fn(),
  onNewDayHike: vi.fn(),
  onNewTrip: vi.fn(),
  onResumeDraft: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the mode band', () => {
  it('names the day room, and its chip goes to the trips room', async () => {
    const user = userEvent.setup()
    const onSwitchMode = vi.fn()
    render(<PlanHome {...PROPS} mode="day" onSwitchMode={onSwitchMode} />)

    expect(screen.getByText(/you.{0,3}re planning/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Day hikes' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Trips/ }))
    expect(onSwitchMode).toHaveBeenCalledWith('trips')
  })

  it('names the trips room, and its chip goes to the day room', async () => {
    const user = userEvent.setup()
    const onSwitchMode = vi.fn()
    render(<PlanHome {...PROPS} mode="trips" onSwitchMode={onSwitchMode} />)

    expect(screen.getByRole('heading', { name: 'Trips' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Day hikes/ }))
    expect(onSwitchMode).toHaveBeenCalledWith('day')
  })
})

describe('the day room', () => {
  it('lists recent day hikes with an All N › door to the full list', async () => {
    const user = userEvent.setup()
    const onAllDayHikes = vi.fn()
    render(
      <PlanHome
        {...PROPS}
        mode="day"
        dayHikes={[
          dayHike('Pine Meadow loop', { date: '2026-09-12' }),
          dayHike('Seven Hills, out and back'),
          dayHike('Bear Mountain over Perkins'),
          dayHike('Breakneck Ridge', { recorded: 'walked', date: '2026-08-02' }),
        ]}
        onAllDayHikes={onAllDayHikes}
      />,
    )

    // Three rows, to-walk first; the fourth is behind the All door.
    expect(screen.getByRole('button', { name: /Pine Meadow loop/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Breakneck/ })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'All 4 ›' }))
    expect(onAllDayHikes).toHaveBeenCalled()
  })

  it('shows no trip furniture at all - no groups, no recent trips, no hikes', () => {
    render(
      <PlanHome
        {...PROPS}
        mode="day"
        trips={[trip('Damascus → Pearisburg')]}
        dayHikes={[dayHike('Pine Meadow loop')]}
      />,
    )
    expect(screen.queryByText('Recent trips')).not.toBeInTheDocument()
    expect(screen.queryByText('Your groups')).not.toBeInTheDocument()
    expect(screen.queryByText(/Damascus/)).not.toBeInTheDocument()
  })

  it('its one action opens the day-hike builder, saying so', async () => {
    const user = userEvent.setup()
    const onNewDayHike = vi.fn()
    render(<PlanHome {...PROPS} mode="day" onNewDayHike={onNewDayHike} />)

    await user.click(screen.getByRole('button', { name: 'Plan a day hike' }))
    expect(onNewDayHike).toHaveBeenCalled()
  })

  it('without the graph, the action is a sentence and never a dead button', () => {
    render(<PlanHome {...PROPS} mode="day" onNewDayHike={null} />)
    expect(
      screen.queryByRole('button', { name: 'Plan a day hike' }),
    ).not.toBeInTheDocument()
    expect(screen.getByText(/hasn.{0,3}t got the trail network yet/i)).toBeInTheDocument()
  })

  it('says exactly PlanKindSheet’s sentence for the missing network - two surfaces, one claim', () => {
    // The pin that keeps the two copies from drifting: reword one and this
    // fails until the other matches.
    render(<PlanHome {...PROPS} mode="day" onNewDayHike={null} />)
    const home = screen.getByText(/trail network yet/i).textContent
    cleanup()
    render(
      <PlanKindSheet
        networkAvailable={false}
        walkedAvailable={false}
        onPickDayHike={vi.fn()}
        onPickTrip={vi.fn()}
        onPickWalked={vi.fn()}
        onClose={vi.fn()}
      />,
    )
    const sheet = screen.getByText(/trail network yet/i).textContent
    expect(home).toBe(sheet)
  })

  it('a live draft turns the action into the way back to it', async () => {
    const user = userEvent.setup()
    const onResumeDraft = vi.fn()
    render(
      <PlanHome {...PROPS} mode="day" draftLive={true} onResumeDraft={onResumeDraft} />,
    )
    await user.click(screen.getByRole('button', { name: 'Back to your route' }))
    expect(onResumeDraft).toHaveBeenCalled()
  })
})

describe('the trips room', () => {
  it('keeps the old home’s shelves and its action opens the route builder', async () => {
    const user = userEvent.setup()
    const onNewTrip = vi.fn()
    render(
      <PlanHome
        {...PROPS}
        mode="trips"
        trips={[trip('Damascus → Pearisburg')]}
        onNewTrip={onNewTrip}
      />,
    )
    expect(screen.getByText('Recent trips')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Plan a new trip' }))
    expect(onNewTrip).toHaveBeenCalled()
  })

  it('shows no day-hike shelf - that room is one chip away', () => {
    render(
      <PlanHome
        {...PROPS}
        mode="trips"
        trips={[trip('Damascus → Pearisburg')]}
        dayHikes={[dayHike('Pine Meadow loop')]}
      />,
    )
    expect(screen.queryByText('Your day hikes')).not.toBeInTheDocument()
    expect(screen.queryByText(/Pine Meadow/)).not.toBeInTheDocument()
  })
})

describe('what neither home may say', () => {
  it('no score, no behind, no arrival clock - the standing guard', () => {
    for (const mode of ['day', 'trips'] as const) {
      render(
        <PlanHome
          {...PROPS}
          mode={mode}
          trips={[trip('Damascus → Pearisburg')]}
          dayHikes={[dayHike('Pine Meadow loop', { date: '2026-09-12' })]}
        />,
      )
      const text = document.body.textContent ?? ''
      expect(text).not.toMatch(/behind/i)
      expect(text).not.toMatch(/ahead of/i)
      expect(text).not.toMatch(/\d{1,2}:\d{2}\s*(am|pm)/i)
      cleanup()
    }
  })
})
