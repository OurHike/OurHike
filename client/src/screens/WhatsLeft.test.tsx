// Tests for "What's left" (#791).
//
// Three things are load-bearing and the rest is chrome.
//
// BOTH ENDS OF EVERY GAP, because flip-floppers are the design rather than
// an edge case, and a screen that offered one end would quietly make the
// trail a queue.
//
// THE PACE REFUSAL: nothing about how far a day of theirs reaches is shown
// until there is enough log to say it. Borrowing Naismith's moving-time
// estimate and calling it "yours" is the exact failure this screen must not
// have.
//
// AND THE NEGATIVE ONE the whole planner carries: no percentage, nothing
// overdue, no streaks, and nothing calling a piece "next".

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { WhatsLeft } from './WhatsLeft'
import { type Hike } from '../lib/hikes'
import { buildPlan, type HikePlan } from '../lib/plan'
import type { StoredPoi } from '../lib/trailData'
import type { Trip } from '../lib/trips'

/** A walked trip of `days` days, `perDay` miles each, from `from`. */
function walked(id: string, from: number, days: number, perDay: number): Trip {
  const stops = Array.from({ length: days + 1 }, (_, index) => ({
    mile: from + index * perDay,
    ...(index === 0 || index === days ? { name: `Stop ${from + index * perDay}` } : {}),
    resupply: false,
  }))
  const plan: HikePlan = buildPlan(stops, { miles: perDay })
  plan.days.forEach((day) => (day.walked = true))
  return { id, name: id, plan }
}

const HIKE: Hike = {
  id: 'h1',
  name: 'The whole thing, eventually',
  type: 'thru',
  start: { name: 'Springer', mile: 0 },
  end: { name: 'Katahdin', mile: 500 },
  tripIds: ['a'],
}

const PROPS = {
  hike: HIKE,
  trips: [walked('a', 0, 6, 12)] as readonly Trip[],
  pois: [] as readonly StoredPoi[],
  units: 'imperial' as const,
  gpsMile: null as number | null,
  onPlanFrom: vi.fn(),
  onClose: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('what is left', () => {
  it('counts the pieces and the miles in them', () => {
    render(<WhatsLeft {...PROPS} />)
    // 72 of 500 walked, in one piece.
    expect(screen.getByText('428.0 mi in 1 piece')).toBeInTheDocument()
  })

  it('offers BOTH ends of a gap, and the direction follows the pick', async () => {
    const user = userEvent.setup()
    render(<WhatsLeft {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /North from Stop 72/ }))
    expect(PROPS.onPlanFrom).toHaveBeenCalledWith(
      { name: 'Stop 72', mile: 72 },
      { name: 'Katahdin', mile: 500 },
    )

    await user.click(screen.getByRole('button', { name: /South from Katahdin/ }))
    expect(PROPS.onPlanFrom).toHaveBeenLastCalledWith(
      { name: 'Katahdin', mile: 500 },
      { name: 'Stop 72', mile: 72 },
    )
  })

  it('never numbers a piece or calls one next', () => {
    const { container } = render(<WhatsLeft {...PROPS} />)
    expect(container.textContent).not.toMatch(/\bnext\b|\b1st\b|piece 1/i)
  })

  it('never turns what is left into a score', () => {
    const { container } = render(<WhatsLeft {...PROPS} />)
    expect(container.textContent).not.toMatch(
      /%|behind|ahead of|on track|streak|overdue|complete/i,
    )
  })
})

describe('the days the hiker has', () => {
  it('answers with a range off their own log, and says what it rests on', () => {
    render(<WhatsLeft {...PROPS} />)

    // Six 12-mile days: the middle half is 12 to 12, five days ≈ 60.
    expect(screen.getByText(/≈ 60 mi, from your own 6 days walked/)).toBeInTheDocument()
    // The assumption printed rather than buried: walking days, not days off.
    expect(screen.getByText(/days of walking rather than days away/)).toBeInTheDocument()
  })

  it('moves the answer when the hiker moves the days', async () => {
    const user = userEvent.setup()
    render(<WhatsLeft {...PROPS} />)

    await user.click(screen.getByRole('button', { name: 'One day more' }))
    expect(screen.getByText('6 days')).toBeInTheDocument()
    expect(screen.getByText(/≈ 72 mi, from your own/)).toBeInTheDocument()
  })

  it('says nothing about pace at all when there is not enough log', () => {
    // Two walked days is not a pace. The screen says so instead of
    // borrowing the terrain estimate and calling it theirs.
    render(<WhatsLeft {...PROPS} trips={[walked('a', 0, 2, 12)]} />)

    expect(screen.getByText(/Only 2 days walked so far/)).toBeInTheDocument()
    expect(screen.queryByText(/from your own/)).toBeNull()
  })

  it('says so plainly when nothing has been walked yet', () => {
    render(<WhatsLeft {...PROPS} hike={{ ...HIKE, tripIds: [] }} trips={[]} />)

    expect(screen.getByText(/no pace of yours to reckon with/)).toBeInTheDocument()
    expect(
      screen.getByText(/a made-up average would be worse than none/),
    ).toBeInTheDocument()
  })

  it('says the whole stretch fits when it does, rather than a number', () => {
    // A 20-mile gap against a 60-mile reach is not "≈ 60 mi of it": "all of
    // it" and "some of it" are different answers, and one number for both
    // would blur them.
    const trips = [walked('a', 0, 6, 12), walked('b', 92, 9, 12)]
    render(
      <WhatsLeft
        {...PROPS}
        hike={{ ...HIKE, end: { name: 'Katahdin', mile: 200 }, tripIds: ['a', 'b'] }}
        trips={trips}
      />,
    )
    expect(screen.getByText(/the whole stretch, with room/)).toBeInTheDocument()
  })
})

describe('the orderings', () => {
  const trips = [walked('a', 0, 6, 12), walked('b', 200, 2, 10)]
  const hike: Hike = { ...HIKE, tripIds: ['a', 'b'] }

  it('offers no sort that cannot be computed honestly', () => {
    render(<WhatsLeft {...PROPS} hike={hike} trips={trips} />)
    // No fix, so no "nearest me" - not a nearest that is really trail order.
    expect(screen.queryByRole('button', { name: 'Nearest me' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Trail order' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Fits my days' })).toBeInTheDocument()
  })

  it('reorders the cards without renaming anything', async () => {
    const user = userEvent.setup()
    render(<WhatsLeft {...PROPS} hike={hike} trips={trips} gpsMile={300} />)

    const namesNow = () =>
      screen.getAllByRole('listitem').map((item) => {
        const name = within(item).getAllByText(/→/)[0]
        return name.textContent
      })

    expect(namesNow()[0]).toMatch(/Stop 72 → Stop 200/)

    await user.click(screen.getByRole('button', { name: 'Nearest me' }))
    // Standing at mile 300, inside the second gap - nearest of all.
    expect(namesNow()[0]).toMatch(/Stop 220 → Katahdin/)
  })
})

describe('the slivers', () => {
  // #791's open question, settled: a stated threshold with the remainder
  // still visible, rather than either extreme chosen silently.
  const trips = [walked('a', 0, 1, 99.9), walked('b', 100, 1, 200)]

  it('counts what it does not show, beside the pieces it does', () => {
    render(<WhatsLeft {...PROPS} hike={{ ...HIKE, tripIds: ['a', 'b'] }} trips={trips} />)

    expect(screen.getByText(/1 short stretch adding up to 0\.1 mi/)).toBeInTheDocument()
    expect(screen.getByText(/still trail nobody has walked/)).toBeInTheDocument()
    // And the piece that IS worth a card is still there.
    expect(screen.getByText(/Stop 300 → Katahdin/)).toBeInTheDocument()
  })

  it('still says so when the slivers are all that is left', () => {
    // The case that decides whether the app calls a hike finished that is
    // not: nothing to show, and it does not say "done".
    const { container } = render(
      <WhatsLeft
        {...PROPS}
        hike={{ ...HIKE, end: { name: 'Katahdin', mile: 300 }, tripIds: ['a', 'b'] }}
        trips={trips}
      />,
    )

    expect(
      screen.getByText(/Nothing left in this hike but 1 short stretch/),
    ).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/finished|done|complete/i)
  })
})
