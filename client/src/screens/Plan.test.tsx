// Tests for the Plan tab (#756).
//
// The most load-bearing assertion here is a NEGATIVE one: no rendering of
// any plan, in any state, may contain "behind", "ahead of schedule" or a
// score. Value #1 forbids prescriptive gamification and V2_PLAN.md group T
// names this screen as where it would arrive without anyone deciding to add
// it - so the guardrail is held by a test rather than by vigilance.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { PlanScreen } from './Plan'
import { buildPlan, insertZeroAfter, toggleResupply, type HikePlan } from '../lib/plan'
import type { ElevationProfile } from '../lib/elevationProfile'

const PROPS = {
  elevation: null,
  units: 'imperial' as const,
  onStartOnMap: vi.fn(),
  onChangeTarget: vi.fn(),
  onInsertZeroAfter: vi.fn(),
  onRemoveDay: vi.fn(),
  onTogglePinned: vi.fn(),
  onToggleEndResupply: vi.fn(),
  onDeletePlan: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

/** Damascus → Atkins: two walking days, a zero between them, resupply at
 *  the end. */
function smallPlan(): HikePlan {
  const plan = buildPlan(
    [
      { mile: 470.8, name: 'Damascus', resupply: false },
      { mile: 486.2, name: 'Lost Mountain Shelter', resupply: false },
      { mile: 503.3, name: 'Atkins', resupply: false },
    ],
    { walkingHours: 7 },
    '2026-05-12',
  )
  return toggleResupply(insertZeroAfter(plan, 0), 3)
}

/** A flat-ish profile over the plan's miles, dense enough for every day to
 *  hold samples. */
function profile(): ElevationProfile {
  const miles: number[] = []
  const feet: number[] = []
  for (let mile = 470; mile <= 504; mile += 0.25) {
    miles.push(mile)
    feet.push(2000 + (mile % 2) * 400)
  }
  return {
    distanceMi: Float32Array.from(miles),
    elevationFt: Float32Array.from(feet),
  }
}

describe('with no plan', () => {
  it('speaks in the app’s own voice and offers the map', async () => {
    const user = userEvent.setup()
    render(<PlanScreen {...PROPS} plan={null} />)

    expect(
      screen.getByText('No plan yet. You could just walk north and find out.'),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Start on the map' }))
    expect(PROPS.onStartOnMap).toHaveBeenCalled()
  })
})

describe('the timeline', () => {
  it('gives every day a row - zeros too - and numbers only the walked ones', () => {
    render(<PlanScreen {...PROPS} plan={smallPlan()} />)

    expect(screen.getByText('DAY 1')).toBeInTheDocument()
    expect(screen.getByText('DAY 2')).toBeInTheDocument()
    expect(screen.queryByText('DAY 3')).toBeNull()
    expect(screen.getByText(/Zero · Lost Mountain Shelter/)).toBeInTheDocument()
    expect(screen.getByText('no walking')).toBeInTheDocument()
  })

  it('dates the rows from the start date, in UTC', () => {
    render(<PlanScreen {...PROPS} plan={smallPlan()} />)

    expect(screen.getByText('TUE 12')).toBeInTheDocument()
    expect(screen.getByText('WED 13')).toBeInTheDocument()
    expect(screen.getByText('THU 14')).toBeInTheDocument()
  })

  it('marks untouched generated days quietly, and only those', () => {
    render(<PlanScreen {...PROPS} plan={smallPlan()} />)

    // Two generated walking days; the hand-inserted zero is nobody's guess.
    expect(screen.getAllByText('auto')).toHaveLength(2)
  })

  it('draws terrain and hour-proportional heights only with a profile', () => {
    const { container, rerender } = render(<PlanScreen {...PROPS} plan={smallPlan()} />)
    expect(container.querySelector('.plan__terrain')).toBeNull()

    rerender(<PlanScreen {...PROPS} plan={smallPlan()} elevation={profile()} />)
    // The resupply day draws no terrain (its row carries the carry line),
    // so one walking day's silhouette remains.
    expect(container.querySelectorAll('.plan__terrain').length).toBeGreaterThan(0)

    // Row height = walking hours: the 17.1-mile day outgrows the 15.4-mile
    // one. Read off the style attribute, since jsdom does no layout.
    const heights = Array.from(
      container.querySelectorAll<HTMLButtonElement>('.plan__day:not(.plan__day--zero)'),
    ).map((row) => Number.parseInt(row.style.height, 10))
    expect(heights[1]).toBeGreaterThan(heights[0])
  })

  it('says what a resupply stop carries, in days', () => {
    render(<PlanScreen {...PROPS} plan={smallPlan()} />)

    // Atkins ends the plan, so there is no carry OUT of it - the row says
    // resupply and claims nothing about days it cannot know.
    expect(screen.getByText(/resupply/i)).toBeInTheDocument()
    expect(screen.getByText(/3 days food/)).toBeInTheDocument()
  })

  it('never scores a hiker against their plan', () => {
    const { container } = render(
      <PlanScreen {...PROPS} plan={smallPlan()} elevation={profile()} />,
    )

    expect(container.textContent).not.toMatch(/behind/i)
    expect(container.textContent).not.toMatch(/ahead of/i)
    expect(container.textContent).not.toMatch(/on track|on schedule|streak/i)
  })
})

describe('editing a day', () => {
  it('opens the tapped day’s actions and routes each to its callback', async () => {
    const user = userEvent.setup()
    render(<PlanScreen {...PROPS} plan={smallPlan()} />)

    await user.click(screen.getByRole('button', { name: /Damascus → Lost Mountain/ }))
    expect(screen.getByRole('dialog', { name: 'Day actions' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Add a zero day after this' }))
    expect(PROPS.onInsertZeroAfter).toHaveBeenCalledWith(0)
    // Acting closes the sheet - the timeline is the confirmation.
    expect(screen.queryByRole('dialog', { name: 'Day actions' })).toBeNull()
  })

  it('offers resupply on the day’s END stop, named', async () => {
    const user = userEvent.setup()
    render(<PlanScreen {...PROPS} plan={smallPlan()} />)

    await user.click(screen.getByRole('button', { name: /Damascus → Lost Mountain/ }))
    await user.click(
      screen.getByRole('button', { name: 'Resupply at Lost Mountain Shelter' }),
    )
    expect(PROPS.onToggleEndResupply).toHaveBeenCalledWith(0)
  })

  it('pins through the same sheet', async () => {
    const user = userEvent.setup()
    render(<PlanScreen {...PROPS} plan={smallPlan()} />)

    await user.click(screen.getByRole('button', { name: /Zero · Lost Mountain/ }))
    await user.click(
      screen.getByRole('button', { name: 'Pin this day — it does not move' }),
    )
    expect(PROPS.onTogglePinned).toHaveBeenCalledWith(1)
  })
})

describe('the foot of the screen', () => {
  it('names the target it would reopen', async () => {
    const user = userEvent.setup()
    render(<PlanScreen {...PROPS} plan={smallPlan()} />)

    await user.click(screen.getByRole('button', { name: 'Target: 7h walking' }))
    expect(PROPS.onChangeTarget).toHaveBeenCalled()
  })

  it('asks twice before deleting a plan', async () => {
    const user = userEvent.setup()
    render(<PlanScreen {...PROPS} plan={smallPlan()} />)

    await user.click(screen.getByRole('button', { name: 'Delete plan' }))
    expect(PROPS.onDeletePlan).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Tap again to delete the plan' }))
    expect(PROPS.onDeletePlan).toHaveBeenCalled()
  })
})
