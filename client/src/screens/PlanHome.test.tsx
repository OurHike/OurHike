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
  network: { kind: 'ready' },
  mode: 'day',
  onSwitchMode: vi.fn(),
  trips: [],
  hikes: [],
  dayHikes: [],
  groups: [],
  pois: [],
  units: 'imperial',
  openTrip: null,
  draftKind: null,
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
    render(
      <PlanHome
        {...PROPS}
        mode="day"
        onNewDayHike={null}
        network={{ kind: 'absent', because: 'not-in-release' }}
      />,
    )
    expect(
      screen.queryByRole('button', { name: 'Plan a day hike' }),
    ).not.toBeInTheDocument()
    expect(screen.getByText(/does not include the trail network/i)).toBeInTheDocument()
  })

  it('says exactly PlanKindSheet’s sentence for the missing network - two surfaces, one claim', () => {
    // This used to be a pin against two hand-written copies drifting. Since
    // #1049 both screens read lib/trailNetworkText.ts, so they cannot drift -
    // and the test stays, because what it really guards is that a hiker sees
    // ONE claim about one missing artifact wherever they meet it.
    const network = { kind: 'absent', because: 'not-in-release' } as const
    render(<PlanHome {...PROPS} mode="day" onNewDayHike={null} network={network} />)
    const home = screen.getByRole('note').textContent
    cleanup()
    // The sheet carries a SECOND note - the walked door's "isn't built yet" -
    // so this one is found by its own sentence rather than by the role.
    render(
      <PlanKindSheet
        network={network}
        walkedAvailable={false}
        onPickDayHike={vi.fn()}
        onPickTrip={vi.fn()}
        onPickWalked={vi.fn()}
        onClose={vi.fn()}
      />,
    )
    const sheet = screen.getByText(/trail network/i).textContent
    expect(home).toBe(sheet)
  })

  it('never tells anybody to wait for a data sync (#1049)', () => {
    // The string this issue is about. On production the graph is simply not
    // in the release (#1048), so "It arrives with the next data sync" was a
    // promise nothing was going to keep.
    for (const because of [
      'unconfigured',
      'unreachable',
      'not-in-release',
      'unverifiable',
      'not-a-graph',
    ] as const) {
      cleanup()
      render(
        <PlanHome
          {...PROPS}
          mode="day"
          onNewDayHike={null}
          network={{ kind: 'absent', because }}
        />,
      )
      expect(screen.getByRole('note')).not.toHaveTextContent(/data sync/i)
    }
  })

  it('says nothing about the network when the door is shut for another reason', () => {
    // Today the call site only withholds the door when the network is absent,
    // so this is a guard rather than a bug fix - but a screen that INFERRED
    // the reason would start blaming the network the day a second reason
    // exists, on a phone whose network is fine.
    render(<PlanHome {...PROPS} mode="day" onNewDayHike={null} />)

    expect(screen.queryByRole('note')).not.toBeInTheDocument()
  })

  it('a live draft turns the action into the way back to it', async () => {
    const user = userEvent.setup()
    const onResumeDraft = vi.fn()
    render(
      <PlanHome {...PROPS} mode="day" draftKind="day" onResumeDraft={onResumeDraft} />,
    )
    await user.click(screen.getByRole('button', { name: 'Back to your route' }))
    expect(onResumeDraft).toHaveBeenCalled()
  })

  it('keeps its own action while a TRIP draft is live - that route is the other room’s', async () => {
    // One shared draftLive boolean put "Back to your route" here and dropped
    // the hiker into the multi-day route builder from a screen headed "Day
    // hikes", with this room's own action missing besides.
    const user = userEvent.setup()
    const onNewDayHike = vi.fn()
    const onResumeDraft = vi.fn()
    render(
      <PlanHome
        {...PROPS}
        mode="day"
        draftKind="trip"
        onNewDayHike={onNewDayHike}
        onResumeDraft={onResumeDraft}
      />,
    )
    expect(
      screen.queryByRole('button', { name: 'Back to your route' }),
    ).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Plan a day hike' }))
    expect(onNewDayHike).toHaveBeenCalled()
    expect(onResumeDraft).not.toHaveBeenCalled()
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

  it('keeps its own action while a DAY draft is live, symmetrically', async () => {
    const user = userEvent.setup()
    const onNewTrip = vi.fn()
    const onResumeDraft = vi.fn()
    render(
      <PlanHome
        {...PROPS}
        mode="trips"
        draftKind="day"
        onNewTrip={onNewTrip}
        onResumeDraft={onResumeDraft}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Plan a new trip' }))
    expect(onNewTrip).toHaveBeenCalled()
    expect(onResumeDraft).not.toHaveBeenCalled()
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
