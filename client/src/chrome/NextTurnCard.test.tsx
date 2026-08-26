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
