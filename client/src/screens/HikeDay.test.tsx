// A day inside a long hike (#1317).
//
// The load-bearing test is the last one: nothing about a day's completion
// may depend on a tap, and the screen has to SAY so - a button a hiker is
// afraid of not pressing has invented an obligation the model does not have.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { HikeDay } from './HikeDay'

function samples(from = 700, to = 711.2) {
  const out = []
  for (let mile = from; mile <= to; mile += 0.5) {
    out.push({ mile, elevationFt: 2000 + (mile - from) * 30 })
  }
  return out
}

const PROPS = {
  hikeName: 'Springer → Katahdin',
  title: 'Tue 8 Sep',
  subtitle: 'Pine Swamp Branch → Bailey Gap · 11.2 mi',
  samples: samples(),
  domain: { startMile: 700, endMile: 711.2 },
  ascentFt: 1840,
  currentMile: 703.4,
  waypoints: [
    { id: 'w1', type: 'water', name: 'Dismal Branch', mile: 703.1 },
    { id: 's1', type: 'shelter', name: 'Bailey Gap Shelter', mile: 710.8 },
  ],
  units: 'imperial' as const,
  onBack: vi.fn(),
  onOpenWaypoint: vi.fn(),
  onStopShort: vi.fn(),
  onPushOn: vi.fn(),
  onTakeZero: vi.fn(),
  onCallItADay: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the day inside a hike', () => {
  it('names the hike it belongs to, and the day', () => {
    render(<HikeDay {...PROPS} />)

    expect(
      screen.getByRole('button', { name: /Springer → Katahdin/ }),
    ).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Tue 8 Sep' })).toBeInTheDocument()
    expect(
      screen.getByText(/Pine Swamp Branch → Bailey Gap · 11\.2 mi/),
    ).toBeInTheDocument()
  })

  it('draws the real ribbon, and calls it today’s walk rather than what is ahead', () => {
    // The accessible name is a claim: "ahead" over a whole day's profile
    // tells a screen-reader user something false about where they are.
    render(<HikeDay {...PROPS} />)

    expect(
      screen.getByRole('img', { name: 'Elevation profile of your whole walk today' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('img', { name: /ahead/i })).not.toBeInTheDocument()
  })

  it('says nothing about the climb when the download has no profile', () => {
    // Absent rather than "+0 ft": a hiker deciding whether they beat the
    // dark is better served by no answer than by a made-up one.
    render(<HikeDay {...PROPS} samples={[]} ascentFt={null} />)

    expect(screen.getByText(/No elevation profile in this download/)).toBeInTheDocument()
    expect(screen.queryByText(/\+0/)).not.toBeInTheDocument()
  })

  it('lists today’s stops by their mile MARKER, never converted', () => {
    // `mi 703.1` is where somebody is - the reference a shelter register and
    // a shuttle driver share - and converting it names somewhere else.
    render(<HikeDay {...PROPS} units="metric" />)

    expect(screen.getByText('703.1')).toBeInTheDocument()
    expect(screen.getByText('710.8')).toBeInTheDocument()
  })

  it('opens a stop’s own card rather than a second kind of screen', async () => {
    const user = userEvent.setup()
    const onOpenWaypoint = vi.fn()
    render(<HikeDay {...PROPS} onOpenWaypoint={onOpenWaypoint} />)

    await user.click(screen.getByRole('button', { name: 'Dismal Branch' }))
    expect(onOpenWaypoint).toHaveBeenCalledWith('w1')
  })

  it('offers the three edits, and promises nothing moves until you say so', async () => {
    const user = userEvent.setup()
    const onTakeZero = vi.fn()
    render(<HikeDay {...PROPS} onTakeZero={onTakeZero} />)

    expect(screen.getByRole('button', { name: 'Stop short' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Push on' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Take a zero' }))
    expect(onTakeZero).toHaveBeenCalled()
    expect(screen.getByText(/Nothing moves until you say so/)).toBeInTheDocument()
  })

  it('answers what happens if the day is never called', () => {
    // The rule the whole screen is built around, on the screen rather than
    // only in the code: day rollover comes from the calendar and miles from
    // position, so skipping this button changes nothing.
    render(<HikeDay {...PROPS} />)

    expect(screen.getByRole('button', { name: 'Call it a day here' })).toBeInTheDocument()
    expect(screen.getByText(/Nothing waits on this button/)).toBeInTheDocument()
    expect(screen.getByText(/the miles you walked stay walked/)).toBeInTheDocument()
  })

  it('prints no percentage, nothing behind and nothing on track', () => {
    const { container } = render(<HikeDay {...PROPS} />)
    expect(container.textContent).not.toMatch(/%|behind|ahead of|on track|streak/i)
  })
})
