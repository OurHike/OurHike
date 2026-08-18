// Tests for the plan target sheet (#756/#757) - the surface where the
// target's UNIT is stated, the ceiling is described without overclaiming,
// and a pre-#753 download is refused rather than planned dishonestly.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { PlanTargetSheet } from './PlanTargetSheet'
import type { ElevationProfile } from '../lib/elevationProfile'
import type { HikePlan } from '../lib/plan'
import type { StoredPoi } from '../lib/trailData'

const poi = (id: string, type: string, mile?: number): StoredPoi => ({
  id,
  type,
  name: `${type} at ${mile ?? '?'}`,
  lat: 0,
  lon: 0,
  confidence: 'high',
  ...(mile === undefined ? {} : { mile }),
})

const POIS = [
  poi('s1', 'shelter', 10),
  poi('s2', 'shelter', 20),
  poi('c1', 'campsite', 15),
  poi('w1', 'water', 12),
]

function flatProfile(): ElevationProfile {
  const miles: number[] = []
  for (let mile = 0; mile <= 30; mile += 0.25) miles.push(mile)
  return {
    distanceMi: Float32Array.from(miles),
    elevationFt: Float32Array.from(miles.map(() => 2000)),
  }
}

const PROPS = {
  fromMile: 0,
  toMile: 30,
  pois: POIS,
  units: 'imperial' as const,
  onCancel: vi.fn(),
  onLayOut: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the target and its unit', () => {
  it('defaults to walking hours, with miles one tap away', () => {
    render(<PlanTargetSheet {...PROPS} elevation={flatProfile()} />)

    expect(screen.getByRole('button', { name: 'Walking hours' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByText('per day, moving')).toBeInTheDocument()
  })

  it('states what Naismith leaves out, right on the sheet', () => {
    render(<PlanTargetSheet {...PROPS} elevation={flatProfile()} />)

    expect(screen.getByText(/not lunch, not water/)).toBeInTheDocument()
    // And the ceiling is described as it behaves - not "never exceeded",
    // because #754 measured stretches where the trail forces a longer day.
    expect(
      screen.getByText(/longer only where the trail offers no stop/),
    ).toBeInTheDocument()
  })

  it('never prints an arrival clock', () => {
    const { container } = render(<PlanTargetSheet {...PROPS} elevation={flatProfile()} />)

    expect(container.textContent).not.toMatch(/\d{1,2}:\d{2}\s*(am|pm)?/i)
  })

  it('offers only miles when the download has no profile', () => {
    render(<PlanTargetSheet {...PROPS} elevation={null} />)

    expect(screen.getByRole('button', { name: 'Walking hours' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Miles' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByText(/needs the elevation profile/)).toBeInTheDocument()
  })
})

describe('laying out', () => {
  it('counts the days it would make, and hands up a plan of generated days', async () => {
    const user = userEvent.setup()
    render(<PlanTargetSheet {...PROPS} elevation={flatProfile()} />)

    await user.click(screen.getByRole('button', { name: 'Miles' }))
    // 30 miles at a 15-mile default target over stops at 10/15/20: two days.
    const cta = screen.getByRole('button', { name: /Lay out \d+ days/ })
    await user.click(cta)

    expect(PROPS.onLayOut).toHaveBeenCalledTimes(1)
    const plan = PROPS.onLayOut.mock.calls[0][0] as HikePlan
    expect(plan.target).toEqual({ miles: 15 })
    expect(plan.stops[0].mile).toBe(0)
    expect(plan.stops[plan.stops.length - 1].mile).toBe(30)
    expect(plan.days.every((day) => day.generated)).toBe(true)
    expect(plan.days.every((day) => !day.pinned)).toBe(true)
  })

  it('carries the chosen first day into the plan', async () => {
    const user = userEvent.setup()
    render(<PlanTargetSheet {...PROPS} elevation={flatProfile()} />)

    fireEvent.change(screen.getByLabelText('First day (optional)'), {
      target: { value: '2026-05-12' },
    })
    await user.click(screen.getByRole('button', { name: /Lay out \d+ days/ }))

    const plan = PROPS.onLayOut.mock.calls[0][0] as HikePlan
    expect(plan.startDate).toBe('2026-05-12')
  })

  it('leaves the date off when none was picked - thru-hikers plan loosely', async () => {
    const user = userEvent.setup()
    render(<PlanTargetSheet {...PROPS} elevation={flatProfile()} />)

    await user.click(screen.getByRole('button', { name: /Lay out \d+ days/ }))
    const plan = PROPS.onLayOut.mock.calls[0][0] as HikePlan
    expect(plan.startDate).toBeUndefined()
  })

  it('re-prices the days as the target moves', () => {
    render(<PlanTargetSheet {...PROPS} elevation={null} />)

    const before = screen.getByRole('button', { name: /Lay out \d+ days/ }).textContent
    fireEvent.change(screen.getByLabelText('Miles per day'), { target: { value: '7' } })
    const after = screen.getByRole('button', { name: /Lay out \d+ days/ }).textContent

    expect(after).not.toBe(before)
  })
})

describe('a download from before #753', () => {
  it('refuses to lay out days it cannot place honestly', () => {
    render(
      <PlanTargetSheet
        {...PROPS}
        pois={[poi('s1', 'shelter'), poi('s2', 'campsite')]}
        elevation={flatProfile()}
      />,
    )

    expect(screen.getByText(/predates trail miles/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Lay out/ })).toBeNull()
  })
})
