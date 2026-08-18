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
import type { Hike } from '../lib/hikes'
import type { Trip } from '../lib/trips'
import { callItADay } from '../lib/cascade'
import { buildPlan, insertZeroAfter, toggleResupply, type HikePlan } from '../lib/plan'
import type { ElevationProfile } from '../lib/elevationProfile'
import type { StoredPoi } from '../lib/trailData'

const PROPS = {
  elevation: null,
  pois: [] as readonly StoredPoi[],
  gpsMile: null,
  units: 'imperial' as const,
  draftLive: false,
  tripName: null,
  openTripId: null,
  tripCount: 1,
  onOpenTrips: vi.fn(),
  hike: null as Hike | null,
  trips: [] as readonly Trip[],
  onOpenTrip: vi.fn(),
  onPlanGap: vi.fn(),
  onStartOnMap: vi.fn(),
  onChangeTarget: vi.fn(),
  onInsertZeroAfter: vi.fn(),
  onRemoveDay: vi.fn(),
  onTogglePinned: vi.fn(),
  onToggleEndResupply: vi.fn(),
  onReplacePlan: vi.fn(),
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

  it('reads as a way back when a route draft is already in progress', () => {
    // The entrance is for starting, never a toll gate: openRouteBuilder
    // reopens a live draft where it stood, and the button says so.
    render(<PlanScreen {...PROPS} plan={null} draftLive={true} />)

    expect(screen.getByRole('button', { name: 'Back to your route' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Start on the map' })).toBeNull()
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

describe('the cascade (#758)', () => {
  const shelter = (id: string, mile: number, name: string): StoredPoi => ({
    id,
    type: 'shelter',
    name,
    lat: 0,
    lon: 0,
    confidence: 'high',
    mile,
  })

  const POIS = [
    shelter('lost', 486.2, 'Lost Mountain Shelter'),
    shelter('wise', 490.4, 'Wise Shelter'),
    shelter('a', 496, 'Shelter A'),
  ]

  /** Two walking days at a miles target, dated. */
  function milesPlan(): HikePlan {
    return buildPlan(
      [
        { mile: 470.8, name: 'Damascus', resupply: false },
        { mile: 486.2, name: 'Lost Mountain Shelter', resupply: false },
        { mile: 503.3, name: 'Atkins', resupply: false },
      ],
      { miles: 15 },
      '2026-05-12',
    )
  }

  it('draws a walked day as a record - grey, plain, and not a button', () => {
    const walked = callItADay(milesPlan(), 0, { mile: 486.2 })
    render(<PlanScreen {...PROPS} plan={walked} pois={POIS} />)

    expect(screen.getByText('walked · not a plan any more')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Damascus → Lost Mountain/ })).toBeNull()
    // And a plan with a record no longer offers a wholesale re-target.
    expect(screen.queryByRole('button', { name: /Target:/ })).toBeNull()
  })

  it('offers "call it a day" only on the current day', async () => {
    const user = userEvent.setup()
    render(<PlanScreen {...PROPS} plan={milesPlan()} pois={POIS} />)

    await user.click(
      screen.getByRole('button', { name: /Lost Mountain Shelter → Atkins/ }),
    )
    expect(screen.queryByRole('button', { name: /Call it a day/ })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    await user.click(screen.getByRole('button', { name: /Damascus → Lost Mountain/ }))
    expect(screen.getByRole('button', { name: /Call it a day/ })).toBeInTheDocument()
  })

  it('records the day where the hiker is, then offers three computed outcomes', async () => {
    const user = userEvent.setup()
    const { rerender } = render(
      <PlanScreen {...PROPS} plan={milesPlan()} pois={POIS} gpsMile={490.3} />,
    )

    await user.click(screen.getByRole('button', { name: /Damascus → Lost Mountain/ }))
    await user.click(screen.getByRole('button', { name: /Call it a day/ }))

    // The position names its nearest real stop.
    await user.click(screen.getByRole('button', { name: /Where you are — Wise Shelter/ }))

    expect(PROPS.onReplacePlan).toHaveBeenCalledTimes(1)
    const called = PROPS.onReplacePlan.mock.calls[0][0] as HikePlan
    expect(called.days[0].walked).toBe(true)
    expect(called.stops[1].name).toBe('Wise Shelter')

    // The shell would re-render with the recorded plan; do the same.
    rerender(<PlanScreen {...PROPS} plan={called} pois={POIS} gpsMile={490.3} />)

    const sheet = screen.getByRole('dialog', { name: 'The rest of the plan' })
    expect(sheet).toBeInTheDocument()
    expect(screen.getByText(/Finish ≈ 13 May, unchanged/)).toBeInTheDocument()
    expect(screen.getByText(/tomorrow: 12\.9 mi/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Absorb/ }))
    expect(PROPS.onReplacePlan).toHaveBeenCalledTimes(2)
    const absorbed = PROPS.onReplacePlan.mock.calls[1][0] as HikePlan
    expect(absorbed.days).toHaveLength(2)
    expect(absorbed.days.map((day) => day.date)).toEqual(['2026-05-12', '2026-05-13'])
  })

  it('skips the choice sheet when the day ended exactly as planned', async () => {
    const user = userEvent.setup()
    render(<PlanScreen {...PROPS} plan={milesPlan()} pois={POIS} />)

    await user.click(screen.getByRole('button', { name: /Damascus → Lost Mountain/ }))
    await user.click(screen.getByRole('button', { name: /Call it a day/ }))
    await user.click(
      screen.getByRole('button', { name: /At Lost Mountain Shelter, as planned/ }),
    )

    expect(PROPS.onReplacePlan).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('dialog', { name: 'The rest of the plan' })).toBeNull()
  })

  it('says why a position past tomorrow’s stop cannot be recorded', async () => {
    const user = userEvent.setup()
    render(<PlanScreen {...PROPS} plan={milesPlan()} pois={POIS} gpsMile={510} />)

    await user.click(screen.getByRole('button', { name: /Damascus → Lost Mountain/ }))
    await user.click(screen.getByRole('button', { name: /Call it a day/ }))

    expect(screen.getByText(/past tomorrow’s stop/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Where you are/ })).toBeNull()
  })

  it('never says ahead or behind, even mid-cascade', async () => {
    const user = userEvent.setup()
    const { container, rerender } = render(
      <PlanScreen {...PROPS} plan={milesPlan()} pois={POIS} gpsMile={490.3} />,
    )
    await user.click(screen.getByRole('button', { name: /Damascus → Lost Mountain/ }))
    await user.click(screen.getByRole('button', { name: /Call it a day/ }))
    await user.click(screen.getByRole('button', { name: /Where you are — Wise Shelter/ }))
    rerender(
      <PlanScreen
        {...PROPS}
        plan={PROPS.onReplacePlan.mock.calls[0][0] as HikePlan}
        pois={POIS}
        gpsMile={490.3}
      />,
    )

    expect(container.textContent).not.toMatch(/behind/i)
    expect(container.textContent).not.toMatch(/ahead of/i)
  })
})

describe('the three zooms (#790)', () => {
  const HIKE: Hike = {
    id: 'h1',
    name: 'Virginia, over a few years',
    type: 'section',
    start: { name: 'Damascus', mile: 470.8 },
    end: { name: 'Rockfish Gap', mile: 860 },
    tripIds: ['t1'],
  }

  function tripOf(plan: HikePlan): Trip {
    return { id: 't1', name: 'Spring section', plan }
  }

  it('offers no control at all when there is only one depth', () => {
    // One trip, one section, no hike: nothing to zoom out to, and a control
    // whose other segments do nothing is the dead button this app keeps
    // designing out.
    render(<PlanScreen {...PROPS} plan={smallPlan()} />)

    expect(screen.queryByRole('group', { name: 'Zoom' })).toBeNull()
  })

  it('offers the hike once the trip belongs to one, and zooms out to it', async () => {
    const user = userEvent.setup()
    const plan = smallPlan()
    render(
      <PlanScreen
        {...PROPS}
        plan={plan}
        hike={HIKE}
        trips={[tripOf(plan)]}
        openTripId="t1"
      />,
    )

    expect(screen.getByRole('group', { name: 'Zoom' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Trip' })).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Hike' }))
    expect(
      screen.getByRole('heading', { name: 'Virginia, over a few years' }),
    ).toBeInTheDocument()
    // The trip's own row, and the ground past it nobody has walked.
    expect(screen.getByText(/Spring section/)).toBeInTheDocument()
    expect(screen.getAllByText(/not walked/).length).toBeGreaterThan(0)
  })

  it('offers the trip zoom only when there is more than one section', async () => {
    const user = userEvent.setup()
    // Resupply in the middle: two sections, so the middle tier has
    // something to say the day list does not.
    const plan = toggleResupply(smallPlan(), 2)
    render(<PlanScreen {...PROPS} plan={plan} />)

    await user.click(screen.getByRole('button', { name: 'Trip' }))
    expect(screen.getByText('SEC 1/2')).toBeInTheDocument()
    expect(screen.getByText('SEC 2/2')).toBeInTheDocument()
  })

  it('shows the hike when the open plan is gone, rather than "no plan yet"', () => {
    // A deleted plan does not delete the years already walked.
    render(<PlanScreen {...PROPS} plan={null} hike={HIKE} trips={[]} />)

    expect(screen.queryByText(/No plan yet/)).toBeNull()
    expect(
      screen.getByRole('heading', { name: 'Virginia, over a few years' }),
    ).toBeInTheDocument()
  })

  it('leads back up to the hike from the days', async () => {
    const user = userEvent.setup()
    const plan = smallPlan()
    render(<PlanScreen {...PROPS} plan={plan} hike={HIKE} trips={[tripOf(plan)]} />)

    await user.click(screen.getByRole('button', { name: /Virginia, over a few years/ }))
    expect(
      screen.getByRole('heading', { name: 'Virginia, over a few years' }),
    ).toBeInTheDocument()
  })

  it('never scores a hiker at any zoom', async () => {
    const user = userEvent.setup()
    const plan = toggleResupply(smallPlan(), 2)
    const { container } = render(
      <PlanScreen
        {...PROPS}
        plan={plan}
        hike={HIKE}
        trips={[tripOf(plan)]}
        openTripId="t1"
      />,
    )

    const forbidden = /%|behind|ahead of|on track|streak|complete/i
    expect(container.textContent).not.toMatch(forbidden)

    await user.click(screen.getByRole('button', { name: 'Trip' }))
    expect(container.textContent).not.toMatch(forbidden)

    await user.click(screen.getByRole('button', { name: 'Hike' }))
    expect(container.textContent).not.toMatch(forbidden)
  })
})
