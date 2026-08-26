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

/** The same profile with miles 10-14 never measured by the DEM. */
function holedProfile(): ElevationProfile {
  const whole = flatProfile()
  return {
    ...whole,
    elevationFt: Float32Array.from(whole.elevationFt, (feet, at) =>
      whole.distanceMi[at] >= 10 && whole.distanceMi[at] <= 14 ? NaN : feet,
    ),
  }
}

const PROPS = {
  route: [{ mile: 0 }, { mile: 30 }],
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

  it('will not plan by hours over ground the DEM never measured (#1039)', () => {
    // The same refusal as no profile at all, for the same reason stated one
    // stretch down: a hole prices that stretch's climb at zero, so an hours
    // target understates the effort of any day crossing it - and the planner
    // answers by making those days LONGER. Wrong direction, on the one
    // control whose job is keeping a day walkable, and invisible if allowed.
    render(<PlanTargetSheet {...PROPS} elevation={holedProfile()} />)

    expect(screen.getByRole('button', { name: 'Walking hours' })).toBeDisabled()
    expect(screen.getByText(/no elevation measured/)).toBeInTheDocument()
    // And it is a different sentence from the no-profile one, because it is
    // a different fact about a different thing.
    expect(screen.queryByText(/needs the elevation profile/)).toBeNull()
  })

  it('still plans by hours over a wholly measured route', () => {
    render(<PlanTargetSheet {...PROPS} elevation={flatProfile()} />)

    expect(screen.getByRole('button', { name: 'Walking hours' })).not.toBeDisabled()
    expect(screen.queryByText(/no elevation measured/)).toBeNull()
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
    expect(plan.days[0].date).toBe('2026-05-12')
    expect(plan.days[1]?.date).toBe('2026-05-13')
  })

  it('leaves the dates off when none was picked - thru-hikers plan loosely', async () => {
    const user = userEvent.setup()
    render(<PlanTargetSheet {...PROPS} elevation={flatProfile()} />)

    await user.click(screen.getByRole('button', { name: /Lay out \d+ days/ }))
    const plan = PROPS.onLayOut.mock.calls[0][0] as HikePlan
    expect(plan.days.every((day) => day.date === undefined)).toBe(true)
  })

  it('re-prices the days as the target moves', () => {
    render(<PlanTargetSheet {...PROPS} elevation={null} />)

    const before = screen.getByRole('button', { name: /Lay out \d+ days/ }).textContent
    fireEvent.change(screen.getByLabelText('Miles per day'), { target: { value: '7' } })
    const after = screen.getByRole('button', { name: /Lay out \d+ days/ }).textContent

    expect(after).not.toBe(before)
  })

  it('plans through an added destination, and the day arriving there is pinned', async () => {
    // The hiker routed Damascus → the campsite at 15 → 30: the campsite is
    // a boundary BY CONSTRUCTION however the targets fall, its name rides
    // into the plan, and the day arriving there is born pinned - a
    // destination the hiker added is a decision the cascade must go around.
    const user = userEvent.setup()
    render(
      <PlanTargetSheet
        {...PROPS}
        route={[
          { mile: 0 },
          { mile: 15, name: 'Grassy Camp', poiId: 'c1' },
          { mile: 30 },
        ]}
        elevation={null}
      />,
    )

    await user.click(screen.getByRole('button', { name: /Lay out \d+ days/ }))
    const plan = PROPS.onLayOut.mock.calls[0][0] as HikePlan

    const viaIndex = plan.stops.findIndex((stop) => stop.mile === 15)
    expect(viaIndex).toBeGreaterThan(0)
    expect(plan.stops[viaIndex].name).toBe('Grassy Camp')
    expect(plan.days[viaIndex - 1].pinned).toBe(true)
    // Only that day: the generator's own boundaries stay movable.
    expect(plan.days.filter((day) => day.pinned)).toHaveLength(1)
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

describe('the rest rhythm (#798)', () => {
  it('asks for none by default, and never suggests one', () => {
    const { container } = render(<PlanTargetSheet {...PROPS} elevation={flatProfile()} />)

    expect(screen.getByText('none')).toBeInTheDocument()
    // No opinion about whether a rhythm is needed, and nothing marking its
    // absence as a problem.
    expect(container.textContent).not.toMatch(
      /you should|recommended|don’t forget|too many days without/i,
    )
  })

  it('lays out rest days when one is asked for, and stores what was asked', async () => {
    const user = userEvent.setup()
    render(<PlanTargetSheet {...PROPS} elevation={flatProfile()} />)

    // Every walking day, because this fixture's 30 flat miles lay out as
    // two days and a rest never lands on the last one.
    fireEvent.change(screen.getByLabelText('A rest day every how many walking days'), {
      target: { value: '1' },
    })
    expect(screen.getByText('every 1 day')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /^Lay out/ }))

    const plan = PROPS.onLayOut.mock.calls[0][0] as HikePlan
    expect(plan.rhythm).toEqual({ everyDays: 1, kind: 'zero' })
    // The rhythm is real days, not just a label: zeros are in the plan.
    expect(plan.days.filter((day) => day.rest === true).length).toBeGreaterThan(0)
  })

  it('offers the two kinds of rest, and says what a nearo is', async () => {
    const user = userEvent.setup()
    render(<PlanTargetSheet {...PROPS} elevation={flatProfile()} />)

    fireEvent.change(screen.getByLabelText('A rest day every how many walking days'), {
      target: { value: '3' },
    })
    expect(screen.getByText(/eats a day of food/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Nearo' }))
    expect(screen.getByText(/is a zero where there isn’t one/)).toBeInTheDocument()
  })
})
