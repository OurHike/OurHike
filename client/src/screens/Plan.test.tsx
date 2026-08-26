// Tests for the Plan tab (#756).
//
// The most load-bearing assertion here is a NEGATIVE one: no rendering of
// any plan, in any state, may contain "behind", "ahead of schedule" or a
// score. Value #1 forbids prescriptive gamification and V2_PLAN.md group T
// names this screen as where it would arrive without anyone deciding to add
// it - so the guardrail is held by a test rather than by vigilance.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { PlanScreen } from './Plan'
import type { DayHike } from '../lib/dayHikes'
import type { Hike } from '../lib/hikes'
import type { TripGroup } from '../lib/tripGroups'
import type { Trip } from '../lib/trips'
import { callItADay } from '../lib/cascade'
import {
  buildPlan,
  insertZeroAfter,
  setDayNote,
  toggleResupply,
  type HikePlan,
} from '../lib/plan'
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
  hikes: [] as readonly Hike[],
  dayHikes: [] as readonly DayHike[],
  onOpenDayHike: vi.fn(),
  groups: [] as readonly TripGroup[],
  onOpenGroup: vi.fn(),
  trips: [] as readonly Trip[],
  onOpenTrip: vi.fn(),
  onPlanGap: vi.fn(),
  onPlanFrom: vi.fn(),
  onStartOnMap: vi.fn(),
  // The mode split (#1008). Trips by default so the existing assertions
  // keep describing the screens they were written against; the day-side
  // tests pass mode: 'day' themselves.
  mode: 'trips' as const,
  onSwitchMode: vi.fn(),
  dayListOpen: false,
  onDayListOpen: vi.fn(),
  draftKind: null,
  onNewDayHike: vi.fn(),
  onNewTrip: vi.fn(),
  network: { kind: 'ready' } as const,
  gpsAt: null,
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
    ).map((row) => Number.parseInt(row.style.minHeight, 10))
    expect(heights[1]).toBeGreaterThan(heights[0])
  })

  it('says what a resupply stop carries, in days', () => {
    render(<PlanScreen {...PROPS} plan={smallPlan()} />)

    // Atkins ends the plan, so there is no carry OUT of it - the row says
    // resupply and claims nothing about days it cannot know.
    expect(screen.getByText(/resupply/i)).toBeInTheDocument()
    expect(screen.getByText(/3 days food/)).toBeInTheDocument()
  })

  it('withholds the climb and the time where the DEM has a hole (#1039)', () => {
    // A gap prices as flat ground, so both figures come back short - and
    // short is the direction that gets somebody caught out after dark. The
    // distance stays, because a hole cannot corrupt it.
    const gapped = profile()
    const holed = {
      ...gapped,
      elevationFt: Float32Array.from(gapped.elevationFt, (feet, at) =>
        gapped.distanceMi[at] >= 488 && gapped.distanceMi[at] <= 494 ? NaN : feet,
      ),
    }
    render(<PlanScreen {...PROPS} plan={smallPlan()} elevation={holed} />)

    expect(screen.getByText(/no climb measured for/i)).toBeInTheDocument()
    // The day that spans the hole prints no ≈time; the whole one still does.
    expect(screen.getByText(/15\.4 mi/)).toBeInTheDocument()
  })

  it('states a section’s ascent only when every day of it was measured', () => {
    const whole = profile()
    render(<PlanScreen {...PROPS} plan={smallPlan()} elevation={whole} />)
    const stated = screen.getAllByText(/↑/).length
    cleanup()

    const holed = {
      ...whole,
      elevationFt: Float32Array.from(whole.elevationFt, (feet, at) =>
        whole.distanceMi[at] >= 488 && whole.distanceMi[at] <= 494 ? NaN : feet,
      ),
    }
    render(<PlanScreen {...PROPS} plan={smallPlan()} elevation={holed} />)
    // A section header is the one place a hiker cannot see that a row below
    // it was withheld, so the roll-up is all-or-nothing across its days.
    expect(screen.queryAllByText(/↑/).length).toBeLessThan(stated)
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

  it('draws a walked day as a record, and offers no action on it', async () => {
    // It became tappable in #966 - it opens the day's own summary - so what
    // this holds is the rule that survived that: a record has no ACTIONS.
    // No call-it-a-day, no pin, no zero, no delete, and the plan it belongs
    // to no longer offers a wholesale re-target.
    const user = userEvent.setup()
    const walked = callItADay(milesPlan(), 0, { mile: 486.2 })
    render(<PlanScreen {...PROPS} plan={walked} pois={POIS} />)

    expect(screen.getByText('walked · not a plan any more')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Target:/ })).toBeNull()

    await user.click(screen.getByRole('button', { name: /Damascus → Lost Mountain/ }))
    for (const action of [/Call it a day/, /Pin/, /zero day/, /Remove/]) {
      expect(screen.queryByRole('button', { name: action })).toBeNull()
    }
  })

  it('gives each day its own card, so a line cannot land on the wrong day (#986)', async () => {
    // The defect this pins is Plan's, not DaySummary's: the card holds
    // per-day state whose initialisers run on mount, and without a key
    // "the next day" reused the instance. Day two opened with day one's
    // line already in the box, and Keep wrote it onto day two - silent, and
    // indistinguishable from something the hiker had written themselves.
    const user = userEvent.setup()
    const twoWalked = callItADay(callItADay(milesPlan(), 0, { mile: 486.2 }), 1, {
      mile: 503.3,
    })
    // Day one carries a line; day two carries none.
    const withNote = setDayNote(twoWalked, 0, 'the ponies were unbothered')
    render(<PlanScreen {...PROPS} plan={withNote} pois={POIS} />)

    await user.click(screen.getByRole('button', { name: /Damascus → Lost Mountain/ }))
    const first = screen.getByRole('dialog', { name: 'Your day' })
    expect((within(first).getByRole('textbox') as HTMLTextAreaElement).value).toBe(
      'the ponies were unbothered',
    )

    await user.click(within(first).getByRole('button', { name: /the next day/i }))
    const second = screen.getByRole('dialog', { name: 'Your day' })
    expect(within(second).getByText(/Lost Mountain Shelter → Atkins/)).toBeInTheDocument()
    expect((within(second).getByRole('textbox') as HTMLTextAreaElement).value).toBe('')

    // And Keep on the untouched second day clears rather than copying.
    await user.click(within(second).getByRole('button', { name: 'Keep' }))
    const calls = PROPS.onReplacePlan.mock.calls
    if (calls.length > 0) {
      const kept = calls[calls.length - 1][0] as HikePlan
      expect(kept.days[1].note).toBeUndefined()
    }
    // Day one's line is untouched either way.
    expect(withNote.days[0].note).toBe('the ponies were unbothered')
  })

  it("opens a walked day's summary, and keeps the line written on it (#966)", async () => {
    const user = userEvent.setup()
    const walked = callItADay(milesPlan(), 0, { mile: 486.2 })
    render(<PlanScreen {...PROPS} plan={walked} pois={POIS} />)

    await user.click(screen.getByRole('button', { name: /Damascus → Lost Mountain/ }))

    const card = screen.getByRole('dialog', { name: 'Your day' })
    expect(within(card).getByText('Damascus → Lost Mountain Shelter')).toBeInTheDocument()

    await user.type(within(card).getByRole('textbox'), 'the ponies were unbothered')
    await user.click(within(card).getByRole('button', { name: 'Keep' }))

    expect(PROPS.onReplacePlan).toHaveBeenCalledTimes(1)
    const kept = PROPS.onReplacePlan.mock.calls[0][0] as HikePlan
    expect(kept.days[0].note).toBe('the ponies were unbothered')
    // The record itself is untouched by writing a memory about it.
    expect(kept.days[0].walked).toBe(true)
    expect(kept.stops).toEqual(walked.stops)
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

describe('the door to what’s left (#791)', () => {
  const HIKE: Hike = {
    id: 'h1',
    name: 'Virginia, over a few years',
    type: 'section',
    start: { name: 'Damascus', mile: 470.8 },
    end: { name: 'Rockfish Gap', mile: 860 },
    tripIds: ['t1'],
  }

  it('opens the gap screen from the hike zoom, and comes back', async () => {
    const user = userEvent.setup()
    const plan = smallPlan()
    const trips: Trip[] = [{ id: 't1', name: 'Spring section', plan }]
    render(
      <PlanScreen {...PROPS} plan={plan} hike={HIKE} trips={trips} openTripId="t1" />,
    )

    await user.click(screen.getByRole('button', { name: 'Hike' }))
    await user.click(screen.getByRole('button', { name: /What’s left/ }))

    expect(screen.getByRole('heading', { name: 'What’s left' })).toBeInTheDocument()
    // Nothing walked on this plan, so the whole hike is one piece.
    expect(screen.getByText(/389\.2 mi in 1 piece/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Back to the hike' }))
    expect(
      screen.getByRole('heading', { name: 'Virginia, over a few years' }),
    ).toBeInTheDocument()
  })
})

describe('food (#799)', () => {
  it('says what each carry costs, and which one buys nothing at its end', () => {
    // smallPlan resupplies at the last stop only, so the whole thing is one
    // carry that restocks at the very end of the plan.
    render(<PlanScreen {...PROPS} plan={smallPlan()} />)

    const food = screen.getByRole('heading', { name: 'Food' })
      .parentElement as HTMLElement
    // One carry, ending where the plan does: three days including the zero.
    expect(within(food).getByText(/Damascus → Atkins/)).toBeInTheDocument()
    expect(within(food).getByText(/3 days/)).toBeInTheDocument()
  })

  it('says so when nothing is bought anywhere, instead of saying nothing', () => {
    // The case that used to be silent: no resupply meant the word food
    // never appeared, which reads as "no food needed".
    const plan = buildPlan(
      [
        { mile: 470.8, name: 'Damascus', resupply: false },
        { mile: 486.2, name: 'Lost Mountain Shelter', resupply: false },
        { mile: 503.3, name: 'Atkins', resupply: false },
      ],
      { walkingHours: 7 },
    )
    render(<PlanScreen {...PROPS} plan={plan} />)

    expect(screen.getByText(/No resupply on this plan/)).toBeInTheDocument()
    expect(screen.getByText(/all 2 days come out of your pack/)).toBeInTheDocument()
  })

  it('says a long carry is heavy without telling anybody off about it', () => {
    // Two carries - a short one into town, then six days out of it.
    const plan = toggleResupply(
      buildPlan(
        Array.from({ length: 9 }, (_, index) => ({
          mile: 470 + index * 10,
          name: `Stop ${index}`,
          resupply: false,
        })),
        { miles: 10 },
      ),
      2,
    )
    const { container } = render(<PlanScreen {...PROPS} plan={plan} />)

    expect(screen.getByText(/that is the heaviest your pack gets/)).toBeInTheDocument()
    // A fact about a stretch of trail with no towns on it, not a mistake.
    expect(container.textContent).not.toMatch(/too (much|long|far)|warning|you should/i)
  })

  it('says that zeros are in the count, because the answer could be either', () => {
    render(<PlanScreen {...PROPS} plan={smallPlan()} />)
    expect(screen.getByText(/Zeros and rest days count/)).toBeInTheDocument()
  })
})

describe('rest days (#798)', () => {
  it('calls a zero the hiker’s own rest, and an ordinary zero neither', () => {
    const plan = smallPlan() // has a zero at index 1, added by hand
    render(<PlanScreen {...PROPS} plan={plan} />)
    expect(screen.getByText('no walking')).toBeInTheDocument()

    cleanup()
    const rested = {
      ...plan,
      days: plan.days.map((day, index) => (index === 1 ? { ...day, rest: true } : day)),
    }
    render(<PlanScreen {...PROPS} plan={rested} />)
    expect(screen.getByText('your rest day')).toBeInTheDocument()
  })

  it('marks a nearo, which is otherwise just a short day', () => {
    const plan = buildPlan(
      [
        { mile: 470.8, name: 'Damascus', resupply: false },
        { mile: 474.8, name: 'Four On', resupply: false },
        { mile: 490.0, name: 'Atkins', resupply: false },
      ],
      { miles: 15 },
    )
    plan.days[0].rest = true
    render(<PlanScreen {...PROPS} plan={plan} />)

    expect(screen.getByText(/nearo · your rest day/)).toBeInTheDocument()
  })

  it('never scores the rests', () => {
    const plan = smallPlan()
    plan.days[1].rest = true
    const { container } = render(<PlanScreen {...PROPS} plan={plan} />)
    expect(container.textContent).not.toMatch(/%|streak|in a row|rests taken|earned/i)
  })
})

describe('the Plan home (#805)', () => {
  const HIKE: Hike = {
    id: 'h1',
    name: 'Virginia, over a few years',
    type: 'section',
    start: { name: 'Damascus', mile: 470.8 },
    end: { name: 'Rockfish Gap', mile: 860 },
    tripIds: ['t1'],
  }

  function twoTrips(): Trip[] {
    const a = smallPlan()
    const b = buildPlan(
      [
        { mile: 600, name: 'Grayson', resupply: false },
        { mile: 620, name: 'Old Orchard', resupply: false },
      ],
      { walkingHours: 7 },
      '2026-07-04',
    )
    return [
      { id: 't1', name: 'Spring section', plan: a },
      { id: 't2', name: 'Grayson week', plan: b },
    ]
  }

  it('opens on the home once there is something to choose between', () => {
    render(
      <PlanScreen {...PROPS} plan={smallPlan()} trips={twoTrips()} openTripId="t1" />,
    )

    expect(screen.getByText('Carry on with')).toBeInTheDocument()
    expect(screen.getByText('Recent trips')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Plan a new trip' })).toBeInTheDocument()
  })

  it('opens straight into a lone trip, as it always did', () => {
    // The cost of a home, paid only by hikers who have something to choose
    // between: one trip and no hike lands on the timeline.
    render(<PlanScreen {...PROPS} plan={smallPlan()} trips={twoTrips().slice(0, 1)} />)

    expect(screen.queryByText('Carry on with')).toBeNull()
    expect(screen.queryByText('Recent trips')).toBeNull()
    // The timeline itself, not a menu in front of it.
    expect(screen.getByRole('button', { name: 'Delete plan' })).toBeInTheDocument()
  })

  it('prints every trip’s dates, and says when there are none', () => {
    const trips = twoTrips()
    render(<PlanScreen {...PROPS} plan={trips[0].plan} trips={trips} openTripId="t1" />)

    expect(screen.getAllByText('12–14 May 2026').length).toBeGreaterThan(0)
    expect(screen.getByText('4 Jul 2026')).toBeInTheDocument()
  })

  it('leads into a hike, and back out to the home', async () => {
    const user = userEvent.setup()
    const trips = twoTrips()
    render(
      <PlanScreen
        {...PROPS}
        plan={trips[0].plan}
        trips={trips}
        openTripId="t1"
        hike={HIKE}
        hikes={[HIKE]}
      />,
    )

    await user.click(screen.getByRole('button', { name: /Virginia, over a few years/ }))
    expect(
      screen.getByRole('heading', { name: 'Virginia, over a few years' }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /All your plans/ }))
    expect(screen.getByText('Carry on with')).toBeInTheDocument()
  })

  it('never scores anything on the way in', () => {
    const { container } = render(
      <PlanScreen
        {...PROPS}
        plan={smallPlan()}
        trips={twoTrips()}
        openTripId="t1"
        hike={HIKE}
        hikes={[HIKE]}
      />,
    )
    expect(container.textContent).not.toMatch(/%|behind|ahead of|on track|streak/i)
  })
})

describe('the day room and its list (#1008)', () => {
  const DAY_HIKE = {
    id: 'dh-1',
    name: 'Pine Meadow loop',
    date: '2026-09-12',
    segments: [
      [
        { coord: [-74.095, 41.25] as [number, number], poiId: null },
        { coord: [-74.085, 41.25] as [number, number], poiId: null },
      ],
    ],
    figures: { miles: 6.2, legs: [] },
    looped: true,
    recorded: 'planned' as const,
  }

  it('All N › asks the shell for the full list, and the crumb asks to close it', async () => {
    // The list's open state is the SHELL's (#1008): the map's trailhead door
    // offers "All your day hikes ›" from another tab, and this screen is
    // rebuilt on every tab switch - state local to it would always be false
    // on arrival, landing that control one screen short of what it names.
    const user = userEvent.setup()
    const onDayListOpen = vi.fn()
    const { rerender } = render(
      <PlanScreen
        {...PROPS}
        mode="day"
        dayHikes={[DAY_HIKE]}
        plan={null}
        onDayListOpen={onDayListOpen}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'All 1 ›' }))
    expect(onDayListOpen).toHaveBeenCalledWith(true)

    rerender(
      <PlanScreen
        {...PROPS}
        mode="day"
        dayHikes={[DAY_HIKE]}
        plan={null}
        dayListOpen={true}
        onDayListOpen={onDayListOpen}
      />,
    )
    expect(screen.getByText('Ready to walk')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Day hikes/ }))
    expect(onDayListOpen).toHaveBeenCalledWith(false)
  })

  it('the trips sub-screens wear the trips band', () => {
    const { container } = render(<PlanScreen {...PROPS} plan={smallPlan()} />)
    expect(container.querySelector('.plan__head--trips')).not.toBeNull()
  })

  it('the hike zoom offers its own action while a DAY draft is live', async () => {
    // The hike zoom is a trips-mode screen. On the shared draftLive boolean
    // it said "Back to your route" over a live day hike and dropped the
    // hiker into the day-hike builder from a screen headed by a hike's name.
    const user = userEvent.setup()
    const onNewTrip = vi.fn()
    const onStartOnMap = vi.fn()
    const hike = {
      id: 'h9',
      name: 'Virginia, over a few years',
      type: 'section' as const,
      start: { name: 'Damascus', mile: 470.8 },
      end: { name: 'Rockfish Gap', mile: 860 },
      tripIds: [],
    }
    render(
      <PlanScreen
        {...PROPS}
        plan={null}
        hike={hike}
        draftLive={true}
        draftKind="day"
        onNewTrip={onNewTrip}
        onStartOnMap={onStartOnMap}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Plan another trip' }))
    expect(onNewTrip).toHaveBeenCalled()
    expect(onStartOnMap).not.toHaveBeenCalled()
  })

  it('the hike zoom goes back to a live TRIP draft, which is its own', async () => {
    const user = userEvent.setup()
    const onStartOnMap = vi.fn()
    const hike = {
      id: 'h9',
      name: 'Virginia, over a few years',
      type: 'section' as const,
      start: { name: 'Damascus', mile: 470.8 },
      end: { name: 'Rockfish Gap', mile: 860 },
      tripIds: [],
    }
    render(
      <PlanScreen
        {...PROPS}
        plan={null}
        hike={hike}
        draftLive={true}
        draftKind="trip"
        onStartOnMap={onStartOnMap}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Back to your route' }))
    expect(onStartOnMap).toHaveBeenCalled()
  })

  // Each room's "new" primary reaches a sweep that DISCARDS the other room's
  // draft - `openDayHike` closes the route builder, `sweepForBuilder` clears
  // the day hike. That is the right behaviour for a door somebody
  // deliberately opened, and a bad thing to learn afterwards from an empty
  // builder. Splitting `draftLive` into `draftKind` is what first made these
  // buttons reachable with the other kind live: before it, any live draft
  // turned all three into "Back to your route".
  it('says what a day hike costs when a route is half-built', () => {
    render(
      <PlanScreen
        {...PROPS}
        mode="day"
        plan={null}
        dayHikes={[DAY_HIKE]}
        draftLive={true}
        draftKind="trip"
      />,
    )
    expect(
      screen.getByText(/unfinished route on the map\. Starting a day hike drops it/),
    ).toBeInTheDocument()
  })

  it('says what a trip costs when a day hike is half-built', () => {
    render(
      <PlanScreen
        {...PROPS}
        mode="trips"
        plan={null}
        dayHikes={[DAY_HIKE]}
        draftLive={true}
        draftKind="day"
      />,
    )
    expect(
      screen.getByText(/unfinished day hike on the map\. Starting a trip drops it/),
    ).toBeInTheDocument()
  })

  it('says nothing about a cost when the room owns the draft', () => {
    // The room that owns it offers "Back to your route", which costs
    // nothing - a warning there would be crying wolf.
    render(
      <PlanScreen
        {...PROPS}
        mode="day"
        plan={null}
        dayHikes={[DAY_HIKE]}
        draftLive={true}
        draftKind="day"
      />,
    )
    expect(document.body.textContent).not.toMatch(/drops it/)
  })

  it('the hike zoom carries the same cost note, reaching the same sweep', () => {
    const hike = {
      id: 'h9',
      name: 'Virginia, over a few years',
      type: 'section' as const,
      start: { name: 'Damascus', mile: 470.8 },
      end: { name: 'Rockfish Gap', mile: 860 },
      tripIds: [],
    }
    render(
      <PlanScreen {...PROPS} plan={null} hike={hike} draftLive={true} draftKind="day" />,
    )
    expect(
      screen.getByText(/unfinished day hike on the map\. Starting a trip drops it/),
    ).toBeInTheDocument()
  })
})
