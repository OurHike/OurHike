// The trailhead door (#1008, frame D8): closed first, honest about
// distance, and sayable-no-to.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { DayHikesHere, type DayHikesHereProps } from './DayHikesHere'
import type { NearbyDayHike } from '../lib/dayHikeShelf'
import type { DayHike } from '../lib/dayHikes'

function nearby(id: string, miles: number, date: string | null = null): NearbyDayHike {
  const hike: DayHike = {
    id,
    name: id,
    date,
    segments: [
      [
        { coord: [-74.095, 41.25], poiId: null },
        { coord: [-74.085, 41.25], poiId: null },
      ],
    ],
    figures: { miles: 6.2, legs: [] },
    looped: true,
    recorded: 'planned',
  }
  return { hike, miles }
}

const PROPS: DayHikesHereProps = {
  near: [nearby('Pine Meadow loop', 0.04, '2026-09-12')],
  units: 'imperial',
  today: '2026-09-12',
  onOpen: vi.fn(),
  onAll: vi.fn(),
  onDismiss: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the door', () => {
  it('opens closed: one pill, no self-opened sheet over the map', () => {
    render(<DayHikesHere {...PROPS} />)
    expect(
      screen.getByRole('button', { name: 'Your hikes here · 1' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('region')).not.toBeInTheDocument()
  })

  it('counts plural honestly on the pill', () => {
    render(<DayHikesHere {...PROPS} near={[nearby('a', 0.04), nearby('b', 0.3)]} />)
    expect(
      screen.getByRole('button', { name: 'Your hikes here · 2' }),
    ).toBeInTheDocument()
  })

  it('renders nothing at all with nothing near', () => {
    const { container } = render(<DayHikesHere {...PROPS} near={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('the pill opens the rows; a row opens its hike', async () => {
    const user = userEvent.setup()
    const onOpen = vi.fn()
    render(<DayHikesHere {...PROPS} onOpen={onOpen} />)

    await user.click(screen.getByRole('button', { name: 'Your hikes here · 1' }))
    await user.click(screen.getByRole('button', { name: /Pine Meadow loop/ }))
    expect(onOpen).toHaveBeenCalledWith('Pine Meadow loop')
  })

  it('a row says how far off the start is, and that today is the day', async () => {
    const user = userEvent.setup()
    render(<DayHikesHere {...PROPS} />)
    await user.click(screen.getByRole('button', { name: 'Your hikes here · 1' }))
    // 'fine' precision: 0.04 mi keeps its two decimals rather than rounding
    // to a claim of a tenth of a mile.
    expect(screen.getByText('0.04 mi away')).toBeInTheDocument()
    expect(
      screen.getByText(/planned sat 12 sep\. That.{0,3}s today\./),
    ).toBeInTheDocument()
  })

  it('says nothing about a date a hike does not have', async () => {
    const user = userEvent.setup()
    render(<DayHikesHere {...PROPS} near={[nearby('undated', 0.1)]} />)
    await user.click(screen.getByRole('button', { name: 'Your hikes here · 1' }))
    expect(screen.queryByText(/planned/)).not.toBeInTheDocument()
  })

  it('the × puts the door away, from either state', async () => {
    const user = userEvent.setup()
    const onDismiss = vi.fn()
    render(<DayHikesHere {...PROPS} onDismiss={onDismiss} />)
    await user.click(screen.getByRole('button', { name: 'Put this away' }))
    expect(onDismiss).toHaveBeenCalled()
  })

  it('offers the full list', async () => {
    const user = userEvent.setup()
    const onAll = vi.fn()
    render(<DayHikesHere {...PROPS} onAll={onAll} />)
    await user.click(screen.getByRole('button', { name: 'Your hikes here · 1' }))
    await user.click(screen.getByRole('button', { name: 'All your day hikes ›' }))
    expect(onAll).toHaveBeenCalled()
  })

  it('says the distances are straight-line, which its own source demands', async () => {
    // dayHikeShelf's contract: "the caller MUST say so if it prints the
    // figure". At this radius straight-line and walked differ by a multiple
    // - a start 0.3 mi across an arm of a reservoir is a mile of walking.
    const user = userEvent.setup()
    render(<DayHikesHere {...PROPS} />)
    await user.click(screen.getByRole('button', { name: 'Your hikes here · 1' }))
    expect(
      screen.getByText(/Straight line to each start, not trail walked/),
    ).toBeInTheDocument()
  })

  it('never says "follow" - following is not built, opening is what it does', async () => {
    const user = userEvent.setup()
    render(<DayHikesHere {...PROPS} />)
    await user.click(screen.getByRole('button', { name: 'Your hikes here · 1' }))
    expect(document.body.textContent).not.toMatch(/follow/i)
  })
})
