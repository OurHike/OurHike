// The trailhead door (#1008, frame D8): closed first, honest about
// distance, and sayable-no-to.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { DayHikesHere, type DayHikesHereProps } from './DayHikesHere'
import { STANDARD_PACE } from '../lib/pace'
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
  pace: STANDARD_PACE,
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
      screen.getByRole('button', { name: 'A day hike starts here' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('region')).not.toBeInTheDocument()
  })

  it('counts plural honestly on the pill', () => {
    render(<DayHikesHere {...PROPS} near={[nearby('a', 0.04), nearby('b', 0.3)]} />)
    expect(
      screen.getByRole('button', { name: '2 day hikes start here' }),
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

    await user.click(screen.getByRole('button', { name: 'A day hike starts here' }))
    await user.click(screen.getByRole('button', { name: /Pine Meadow loop/ }))
    expect(onOpen).toHaveBeenCalledWith('Pine Meadow loop')
  })

  it('a row says how far off the start is, and that today is the day', async () => {
    const user = userEvent.setup()
    render(<DayHikesHere {...PROPS} />)
    await user.click(screen.getByRole('button', { name: 'A day hike starts here' }))
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
    await user.click(screen.getByRole('button', { name: 'A day hike starts here' }))
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
    await user.click(screen.getByRole('button', { name: 'A day hike starts here' }))
    await user.click(screen.getByRole('button', { name: 'All your day hikes ›' }))
    expect(onAll).toHaveBeenCalled()
  })

  it('says which distance is straight-line, which its own source demands', async () => {
    // dayHikeShelf's contract: "the caller MUST say so if it prints the
    // figure". At this radius straight-line and walked differ by a multiple
    // - a start 0.3 mi across an arm of a reservoir is a mile of walking.
    const user = userEvent.setup()
    render(<DayHikesHere {...PROPS} />)
    await user.click(screen.getByRole('button', { name: 'A day hike starts here' }))
    expect(
      screen.getByText(/“Away” is a straight line to the start, not trail walked/),
    ).toBeInTheDocument()
  })

  it('scopes that claim to the figure it is true of, and labels the other', async () => {
    // Each row prints TWO distances: "away" is straight-line to the start,
    // and the hike's own cached length is trail walked. An earlier note
    // claimed "the figures above" without separating them, which understated
    // the walk to a hiker reading the second as more of the first.
    const user = userEvent.setup()
    render(<DayHikesHere {...PROPS} />)
    await user.click(screen.getByRole('button', { name: 'A day hike starts here' }))
    expect(document.body.textContent).not.toMatch(/figures above/i)
    expect(screen.getByText(/to walk/)).toBeInTheDocument()
  })

  it('says day hikes, and says they start here', async () => {
    // "hike" alone is taken: a `hike` in this app is a SECTION hike, with its
    // own shelf in the trips room. And the candidates are starts only, while
    // the radius is loose enough to linger mid-walk - so a bare "here" reads
    // as "passing through". The pill is the only state a hiker sees before
    // deciding whether to tap, so it carries the whole claim.
    render(<DayHikesHere {...PROPS} />)
    const pill = screen.getByRole('button', { name: 'A day hike starts here' })
    expect(pill.textContent).toMatch(/day hike/)
    expect(pill.textContent).toMatch(/starts here/)
  })

  it('never says "follow" - following is not built, opening is what it does', async () => {
    const user = userEvent.setup()
    render(<DayHikesHere {...PROPS} />)
    await user.click(screen.getByRole('button', { name: 'A day hike starts here' }))
    expect(document.body.textContent).not.toMatch(/follow/i)
  })
})
