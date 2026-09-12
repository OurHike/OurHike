// The turn a hiker is walking toward (#1041, frame `D9`).

import { describe, expect, it, vi, afterEach } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { NextTurnCard } from './NextTurnCard'
import type { DayHikeTurn } from '../lib/dayHikeTurns'

const TURN: DayHikeTurn = {
  miles: 2.8,
  onto: {
    name: 'Seven Hills Trail',
    blaze_color: 'Blue',
    source: 'nynjtc',
    side: 'left',
    bearingDeg: 0,
  },
  from: {
    name: 'Pine Meadow Trail',
    blaze_color: 'Red',
    source: 'oprhp_trails',
    side: 'back',
    bearingDeg: 270,
  },
  others: [],
}

const PROPS = {
  turn: TURN,
  milesAway: 0.4,
  onTrail: 'Pine Meadow Trail',
  onTrailBlaze: 'Red',
  toGoMi: 3.4,
  onOpenTurn: vi.fn(),
  onStopFollowing: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('NextTurnCard', () => {
  it('leads with the distance and the instruction', () => {
    render(<NextTurnCard {...PROPS} />)

    expect(screen.getByText('In 0.4 mi')).toBeInTheDocument()
    expect(screen.getByText('turn left onto Seven Hills Trail')).toBeInTheDocument()
  })

  it('names the trail the hiker should be seeing blazes for right now', () => {
    // The line that can be falsified from where somebody is standing, which
    // is the only kind of navigation statement worth printing on a network
    // where 48% of A.T. points sit within 150 m of a different marked trail.
    render(<NextTurnCard {...PROPS} />)

    expect(screen.getByText('On Pine Meadow Trail · red blaze')).toBeInTheDocument()
  })

  it('prints no time to the turn', () => {
    // The walk's ≈time belongs to the card read before leaving (#980, #1011).
    // Pricing 0.4 mi mid-walk would be Naismith applied to a stretch shorter
    // than its own error bars, printed as a promise.
    render(<NextTurnCard {...PROPS} />)

    expect(screen.queryByText(/min|≈|h /)).not.toBeInTheDocument()
  })

  it('says so out loud when the turns have run out', () => {
    render(<NextTurnCard {...PROPS} turn={null} />)

    expect(screen.getByText(/No more turns/)).toBeInTheDocument()
    expect(screen.getByText(/3.4 mi/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'This turn' })).not.toBeInTheDocument()
  })

  it('opens the junction, and always offers the way out of the mode', () => {
    render(<NextTurnCard {...PROPS} />)

    expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument()
  })

  it('makes the whole lead the target rather than a chevron', async () => {
    // A gloved hand in sun reaching for a 15px "›" is the mis-tap #105
    // measured the touch floor against.
    render(<NextTurnCard {...PROPS} />)

    await userEvent.click(screen.getByText('turn left onto Seven Hills Trail'))
    expect(PROPS.onOpenTurn).toHaveBeenCalled()
  })

  it('reads in the hiker s own units', () => {
    render(<NextTurnCard {...PROPS} units="metric" />)

    expect(screen.getByText('In 640 m')).toBeInTheDocument()
  })
})

describe('when nothing knows where the hiker is', () => {
  it('still carries the only way out of the mode', () => {
    // The card used to disappear entirely for every no-fix state - the first
    // seconds of following, and every time GPS drops under canopy - taking
    // the app's only Stop control with it and leaving a hiker in a mode the
    // header still announced (#1044 review).
    render(<NextTurnCard {...PROPS} positionKnown={false} />)

    expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument()
    expect(screen.getByText(/Waiting for GPS/i)).toBeInTheDocument()
  })

  it('claims nothing about a position it has not got', () => {
    render(<NextTurnCard {...PROPS} positionKnown={false} />)

    // No distance, no turn, no trail name: every one of those is a claim
    // about where somebody is standing.
    expect(screen.queryByText(/In 0.4 mi/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Seven Hills/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Pine Meadow/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'This turn' })).not.toBeInTheDocument()
  })
})

describe('walking it (#1373, F6)', () => {
  it('says at its head, in the strip’s own words, when the hiker has walked off the download - with the door', async () => {
    const onTakeStretch = vi.fn()
    render(<NextTurnCard {...PROPS} outsideDownload onTakeStretch={onTakeStretch} />)

    const note = screen.getByRole('note')
    expect(note).toHaveTextContent('Outside what you downloaded')
    expect(note).toHaveTextContent('The trail line and your position still work.')
    await userEvent.click(screen.getByRole('button', { name: 'Take this stretch' }))
    expect(onTakeStretch).toHaveBeenCalledOnce()

    cleanup()
    render(<NextTurnCard {...PROPS} />)
    expect(screen.queryByRole('note')).toBeNull()
  })

  it('keeps the coverage note even while nothing knows where the hiker is', () => {
    render(<NextTurnCard {...PROPS} positionKnown={false} outsideDownload />)
    expect(screen.getByRole('note')).toHaveTextContent('Outside what you downloaded')
  })

  it('lists what is left today - the water ahead and the finish, each with its miles and no time', () => {
    render(
      <NextTurnCard
        {...PROPS}
        ahead={[
          {
            key: 'w1',
            kind: 'water',
            title: 'Spring at Murray property',
            milesAway: 0.4,
          },
        ]}
        walkedMi={3.0}
        onFinish={vi.fn()}
      />,
    )

    const left = screen.getByRole('region', { name: 'What’s left today' })
    expect(left).toHaveTextContent('3.4 mi')
    expect(left).toHaveTextContent('Spring at Murray property')
    expect(left).toHaveTextContent('0.4 mi')
    expect(left).toHaveTextContent('The finish')
    // No ≈time and no minutes on any row - only distances.
    expect(left).not.toHaveTextContent(/≈|\bmin\b|\d ?h\b/)
  })

  it('prints no what’s-left at all with nothing to place it against', () => {
    render(<NextTurnCard {...PROPS} />)
    expect(screen.queryByRole('region', { name: 'What’s left today' })).toBeNull()
  })

  it('asks before it finishes, and "Still going" changes nothing', async () => {
    const onFinish = vi.fn()
    render(<NextTurnCard {...PROPS} ahead={[]} walkedMi={6.4} onFinish={onFinish} />)

    await userEvent.click(screen.getByRole('button', { name: 'Finish here instead' }))
    const ask = screen.getByRole('group', { name: 'Done for the day?' })
    expect(ask).toHaveTextContent('6.4 mi walked')
    expect(ask).toHaveTextContent(/never closes the walk for you/)
    expect(onFinish).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: 'Still going' }))
    expect(onFinish).not.toHaveBeenCalled()
    expect(screen.queryByRole('group', { name: 'Done for the day?' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Finish here instead' }))
    await userEvent.click(screen.getByRole('button', { name: 'Finish this walk' }))
    expect(onFinish).toHaveBeenCalledOnce()
  })

  it('offers no finish door without a handler behind it', () => {
    render(<NextTurnCard {...PROPS} ahead={[]} walkedMi={1} />)
    expect(screen.queryByRole('button', { name: 'Finish here instead' })).toBeNull()
  })
})
