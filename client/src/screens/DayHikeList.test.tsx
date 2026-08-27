// The day-hike list (#1008, frame D7): the split shelves, the sorts that
// exist only when honest, and the figures a list may print.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { DayHikeList, type DayHikeListProps } from './DayHikeList'
import { STANDARD_PACE } from '../lib/pace'
import type { DayHike } from '../lib/dayHikes'

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
    figures: {
      miles: 3.4,
      legs: [{ name: 'Pine Meadow Trail', source: null, blaze_color: null, miles: 3.4 }],
    },
    looped: false,
    recorded: 'planned',
    note: '',
    ...overrides,
  }
}

const PROPS: DayHikeListProps = {
  dayHikes: [],
  units: 'imperial',
  pace: STANDARD_PACE,
  at: null,
  onOpen: vi.fn(),
  onBack: vi.fn(),
  onNewDayHike: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the shelves', () => {
  it('splits still-to-walk from walked, and a row opens its hike', async () => {
    const user = userEvent.setup()
    const onOpen = vi.fn()
    render(
      <DayHikeList
        {...PROPS}
        dayHikes={[
          dayHike('Pine Meadow loop', { date: '2026-09-12' }),
          dayHike('Breakneck Ridge', { recorded: 'walked', date: '2026-08-02' }),
        ]}
        onOpen={onOpen}
      />,
    )

    const ready = screen.getByText('Ready to walk').closest('section') as HTMLElement
    expect(within(ready).getByText(/Pine Meadow loop/)).toBeInTheDocument()
    const walked = screen.getByText('Walked').closest('section') as HTMLElement
    expect(within(walked).getByText(/Breakneck Ridge/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Pine Meadow loop/ }))
    expect(onOpen).toHaveBeenCalledWith('Pine Meadow loop')
  })

  it('renders no walked shelf when nothing is walked - no header over an empty list', () => {
    render(<DayHikeList {...PROPS} dayHikes={[dayHike('Pine Meadow loop')]} />)
    expect(screen.queryByText('Walked')).not.toBeInTheDocument()
  })

  it('a row prints the cached miles and legs and the date - never a walking time', () => {
    render(
      <DayHikeList
        {...PROPS}
        dayHikes={[dayHike('Pine Meadow loop', { date: '2026-09-12' })]}
      />,
    )
    expect(screen.getByText(/3\.4 mi · 1 leg · sat 12 sep/)).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/walking|≈/)
  })
})

describe('the sorts', () => {
  const three = [
    dayHike('far-hike', {
      segments: [
        [
          { coord: [-74.06, 41.25], poiId: null },
          { coord: [-74.05, 41.25], poiId: null },
        ],
      ],
      date: '2026-09-20',
    }),
    dayHike('near-hike', { date: '2026-09-01' }),
  ]

  it('offers nearest-me only with a fix, and it reorders by distance', async () => {
    const user = userEvent.setup()
    render(<DayHikeList {...PROPS} dayHikes={three} at={{ lon: -74.095, lat: 41.25 }} />)

    // Recent first: the later date leads. The pattern dodges the back
    // crumb, whose name also carries the word "hikes".
    let rows = screen.getAllByRole('button', { name: /-hike/ })
    expect(rows[0]).toHaveTextContent('far-hike')

    await user.click(screen.getByRole('button', { name: 'nearest me' }))
    rows = screen.getAllByRole('button', { name: /-hike/ })
    expect(rows[0]).toHaveTextContent('near-hike')
  })

  it('with no fix there are no sort chips at all - no dead controls', () => {
    render(<DayHikeList {...PROPS} dayHikes={three} at={null} />)
    expect(screen.queryByRole('button', { name: 'nearest me' })).not.toBeInTheDocument()
  })
})

describe('the edges', () => {
  it('empty list says so in the app’s voice, with the sync fact', () => {
    render(<DayHikeList {...PROPS} dayHikes={[]} />)
    expect(screen.getByText(/Nothing saved yet/)).toBeInTheDocument()
  })

  it('offers no builder door when the shell has none to give', () => {
    render(<DayHikeList {...PROPS} dayHikes={[dayHike('one')]} onNewDayHike={null} />)
    expect(
      screen.queryByRole('button', { name: 'Plan a day hike' }),
    ).not.toBeInTheDocument()
  })

  it('the back crumb returns to the day home', async () => {
    const user = userEvent.setup()
    const onBack = vi.fn()
    render(<DayHikeList {...PROPS} onBack={onBack} />)
    await user.click(screen.getByRole('button', { name: /Day hikes/ }))
    expect(onBack).toHaveBeenCalled()
  })
})
