// The junction (#1041, frame `D10`).
//
// The card exists so a hiker can check the app against the blaze in front of
// them, so the tests below are mostly about what it refuses to leave out: an
// arm, or the fact that an arm is not the route.

import { describe, expect, it, vi, afterEach } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { TurnCard } from './TurnCard'
import type { DayHikeTurn } from '../lib/dayHikeTurns'

/** The fixture's crossing, walked east: Seven Hills left, Pine Meadow
 *  straight on, Reeves Meadow right, and the way back behind. */
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
    blaze_color: 'Blue',
    source: 'oprhp_trails',
    side: 'back',
    bearingDeg: 270,
  },
  others: [
    {
      name: 'Pine Meadow Trail',
      blaze_color: 'Blue',
      source: 'oprhp_trails',
      side: 'straight',
      bearingDeg: 90,
    },
    {
      name: 'Reeves Meadow Trail',
      blaze_color: 'Yellow',
      source: 'oprhp_trails',
      side: 'right',
      bearingDeg: 180,
    },
  ],
}

const PROPS = { turn: TURN, milesAway: 0.1, onClose: vi.fn() }

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('TurnCard', () => {
  it('names the arm to take and the blaze to look for', () => {
    render(<TurnCard {...PROPS} />)

    expect(
      screen.getByRole('heading', { name: 'Turn left onto Seven Hills Trail' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Blue blaze')).toBeInTheDocument()
  })

  it('accounts for every other arm, and says each is not the route', () => {
    render(<TurnCard {...PROPS} />)

    expect(
      screen.getByText('Straight on is Pine Meadow Trail, blue blaze — not your route'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'To the right is Reeves Meadow Trail, yellow blaze — not your route',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Behind you is Pine Meadow Trail, blue blaze — the way you came'),
    ).toBeInTheDocument()
  })

  it('claims no distance to the next blaze', () => {
    // Frame `D10` writes "about 80 ft along, on the left". Nothing in this
    // repository knows where a blaze is painted, so the card carries the rule
    // of thumb and no number.
    render(<TurnCard {...PROPS} />)

    const check = screen.getByText(/Check the blazes/)
    expect(check).toHaveTextContent('blue')
    expect(check.textContent).not.toMatch(/\d/)
  })

  it('draws the junction from the real bearings, rotated to the hiker', () => {
    render(<TurnCard {...PROPS} />)

    expect(
      screen.getByRole('img', {
        name: 'The junction, with your route drawn from the direction you are walking',
      }),
    ).toBeInTheDocument()
  })

  it('draws no junction at all rather than one with an arm missing', () => {
    // A hiker counting three arms against the four they can see would
    // conclude they are somewhere else.
    render(
      <TurnCard
        {...PROPS}
        turn={{
          ...TURN,
          others: [{ ...TURN.others[0], side: null, bearingDeg: null }, TURN.others[1]],
        }}
      />,
    )

    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    // And the words survive without it, which is the point of the split.
    expect(
      screen.getByRole('heading', { name: 'Turn left onto Seven Hills Trail' }),
    ).toBeInTheDocument()
  })

  it('stops printing a distance once the hiker is standing at the fork', () => {
    // "In 0.0 mi" is the one number on this card that says nothing, and the
    // header is already reading "at a junction" at the same threshold.
    render(<TurnCard {...PROPS} milesAway={0.01} />)

    expect(screen.getByText('At the junction')).toBeInTheDocument()
  })

  it('still reads without a fix, minus the distance it cannot have', () => {
    render(<TurnCard {...PROPS} milesAway={null} />)

    expect(screen.getByText('Ahead on your route')).toBeInTheDocument()
    expect(screen.queryByText(/^In /)).not.toBeInTheDocument()
  })

  it('closes back to the map', async () => {
    render(<TurnCard {...PROPS} />)

    await userEvent.click(screen.getByRole('button', { name: 'Close the junction' }))
    expect(PROPS.onClose).toHaveBeenCalled()
  })
})
