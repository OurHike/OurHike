// The two Plan homes (#1008): the mode is the chrome, the switch chip is
// the door between the rooms, and each room's one action does what its
// label says.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { PlanHome, planRoomFor, type PlanHomeProps } from './PlanHome'
import { DEFAULT_TRAIL_ID, type Hike } from '../lib/hikes'
import { PlanStart } from './PlanStart'
import { STANDARD_PACE } from '../lib/pace'
import type { DayHike } from '../lib/dayHikes'
import type { Trip } from '../lib/trips'

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
    figures: { miles: 3.4, legs: [] },
    looped: false,
    recorded: 'planned',
    note: '',
    ...overrides,
  }
}

function trip(id: string): Trip {
  return {
    id,
    name: id,
    plan: {
      target: { miles: 8 },
      stops: [
        { mile: 3.2, resupply: false },
        { mile: 10.2, resupply: false },
      ],
      days: [{ id: `${id}-day`, pinned: false, generated: true }],
    },
  }
}

function hike(overrides: Partial<Hike> = {}): Hike {
  return {
    id: 'hike-1',
    name: 'Springer → Katahdin',
    type: 'thru',
    trailId: DEFAULT_TRAIL_ID,
    status: 'walking',
    points: [
      { name: 'Springer Mountain', mile: 0 },
      { name: 'Katahdin', mile: 100 },
    ],
    tripIds: [],
    ...overrides,
  }
}

const PROPS: PlanHomeProps = {
  network: { kind: 'ready' },
  activeHike: null,
  room: 'day' as const,
  trips: [],
  hikes: [],
  dayHikes: [],
  groups: [],
  pois: [],
  units: 'imperial',
  openTrip: null,
  draftKind: null,
  onOpenTrip: vi.fn(),
  onOpenHike: vi.fn(),
  onOpenDayHike: vi.fn(),
  onOpenGroup: vi.fn(),
  onAllTrips: vi.fn(),
  onAllDayHikes: vi.fn(),
  onNewDayHike: vi.fn(),
  onNewTrip: vi.fn(),
  onResumeDraft: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the mode band', () => {
  it('names the day room, and offers no switch of its own', () => {
    render(<PlanHome {...PROPS} room="day" />)

    expect(screen.getByText(/you.{0,3}re planning/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Day hikes' })).toBeInTheDocument()
    // #1317: the app's mode control is the door. A chip beside it would be a
    // second answer to a question the hiker has already given.
    expect(screen.queryByRole('button', { name: /⇄/ })).not.toBeInTheDocument()
  })

  it('names the sections room, and offers no switch of its own', () => {
    render(<PlanHome {...PROPS} room="sections" />)

    expect(screen.getByRole('heading', { name: 'Sections' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /⇄/ })).not.toBeInTheDocument()
  })

  it('takes its room from the app’s mode, and gives volunteer the day room', () => {
    // Not a third room: "today I'm volunteering" is a statement about the
    // day's work, not a kind of planning.
    expect(planRoomFor('long')).toBe('sections')
    expect(planRoomFor('day')).toBe('day')
    expect(planRoomFor('volunteer')).toBe('day')
  })
})

describe('the day room', () => {
  it('lists recent day hikes with an All N › door to the full list', async () => {
    const user = userEvent.setup()
    const onAllDayHikes = vi.fn()
    render(
      <PlanHome
        {...PROPS}
        room="day"
        dayHikes={[
          dayHike('Pine Meadow loop', { date: '2026-09-12' }),
          dayHike('Seven Hills, out and back'),
          dayHike('Bear Mountain over Perkins'),
          dayHike('Breakneck Ridge', { recorded: 'walked', date: '2026-08-02' }),
        ]}
        onAllDayHikes={onAllDayHikes}
      />,
    )

    // Three rows, to-walk first; the fourth is behind the All door.
    expect(screen.getByRole('button', { name: /Pine Meadow loop/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Breakneck/ })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'All 4 ›' }))
    expect(onAllDayHikes).toHaveBeenCalled()
  })

  it('shows no trip furniture at all - no groups, no recent trips, no hikes', () => {
    render(
      <PlanHome
        {...PROPS}
        room="day"
        trips={[trip('Damascus → Pearisburg')]}
        dayHikes={[dayHike('Pine Meadow loop')]}
      />,
    )
    expect(screen.queryByText('Recent sections')).not.toBeInTheDocument()
    expect(screen.queryByText('Your groups')).not.toBeInTheDocument()
    expect(screen.queryByText(/Damascus/)).not.toBeInTheDocument()
  })

  it('its one action opens the day-hike builder, saying so', async () => {
    const user = userEvent.setup()
    const onNewDayHike = vi.fn()
    render(<PlanHome {...PROPS} room="day" onNewDayHike={onNewDayHike} />)

    await user.click(screen.getByRole('button', { name: 'Plan a day hike' }))
    expect(onNewDayHike).toHaveBeenCalled()
  })

  it('without the graph, the action is a sentence and never a dead button', () => {
    render(
      <PlanHome
        {...PROPS}
        room="day"
        onNewDayHike={null}
        network={{ kind: 'absent', because: 'not-in-release' }}
      />,
    )
    expect(
      screen.queryByRole('button', { name: 'Plan a day hike' }),
    ).not.toBeInTheDocument()
    expect(screen.getByText(/does not include the trail network/i)).toBeInTheDocument()
  })

  it('says exactly step 1’s sentence for the missing network - two surfaces, one claim', () => {
    // This used to be a pin against two hand-written copies drifting. Since
    // #1049 both screens read lib/trailNetworkText.ts, so they cannot drift -
    // and the test stays, because what it really guards is that a hiker sees
    // ONE claim about one missing artifact wherever they meet it. The second
    // surface was chrome/PlanKindSheet.tsx until #1373 retired it (D6); it
    // is screens/PlanStart.tsx now, the spine's step 1.
    const network = { kind: 'absent', because: 'not-in-release' } as const
    render(<PlanHome {...PROPS} room="day" onNewDayHike={null} network={network} />)
    const home = screen.getByRole('note').textContent
    cleanup()
    render(
      <PlanStart
        mode="day"
        network={network}
        hasFix={false}
        hikes={[]}
        near={null}
        units="imperial"
        pace={STANDARD_PACE}
        onNamePlace={vi.fn()}
        onWhereIAm={vi.fn()}
        onPickOnMap={vi.fn()}
        onFindHike={vi.fn()}
        onOpenSuggestedHike={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    const step = screen.getByRole('note').textContent
    expect(home).toBe(step)
  })

  it('never tells anybody to wait for a data sync (#1049)', () => {
    // The string this issue is about. On production the graph is simply not
    // in the release (#1048), so "It arrives with the next data sync" was a
    // promise nothing was going to keep.
    for (const because of [
      'unconfigured',
      'unreachable',
      'not-in-release',
      'unverifiable',
      'not-a-graph',
    ] as const) {
      cleanup()
      render(
        <PlanHome
          {...PROPS}
          room="day"
          onNewDayHike={null}
          network={{ kind: 'absent', because }}
        />,
      )
      expect(screen.getByRole('note')).not.toHaveTextContent(/data sync/i)
    }
  })

  it('says nothing about the network when the door is shut for another reason', () => {
    // Today the call site only withholds the door when the network is absent,
    // so this is a guard rather than a bug fix - but a screen that INFERRED
    // the reason would start blaming the network the day a second reason
    // exists, on a phone whose network is fine.
    render(<PlanHome {...PROPS} room="day" onNewDayHike={null} />)

    expect(screen.queryByRole('note')).not.toBeInTheDocument()
  })

  it('a live draft turns the action into the way back to it', async () => {
    const user = userEvent.setup()
    const onResumeDraft = vi.fn()
    render(
      <PlanHome {...PROPS} room="day" draftKind="day" onResumeDraft={onResumeDraft} />,
    )
    await user.click(screen.getByRole('button', { name: 'Back to your route' }))
    expect(onResumeDraft).toHaveBeenCalled()
  })

  it('keeps its own action while a TRIP draft is live - that route is the other room’s', async () => {
    // One shared draftLive boolean put "Back to your route" here and dropped
    // the hiker into the multi-day route builder from a screen headed "Day
    // hikes", with this room's own action missing besides.
    const user = userEvent.setup()
    const onNewDayHike = vi.fn()
    const onResumeDraft = vi.fn()
    render(
      <PlanHome
        {...PROPS}
        room="day"
        draftKind="trip"
        onNewDayHike={onNewDayHike}
        onResumeDraft={onResumeDraft}
      />,
    )
    expect(
      screen.queryByRole('button', { name: 'Back to your route' }),
    ).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Plan a day hike' }))
    expect(onNewDayHike).toHaveBeenCalled()
    expect(onResumeDraft).not.toHaveBeenCalled()
  })
})

describe('the trips room', () => {
  it('keeps the old home’s shelves and its action opens the route builder', async () => {
    const user = userEvent.setup()
    const onNewTrip = vi.fn()
    render(
      <PlanHome
        {...PROPS}
        room="sections"
        trips={[trip('Damascus → Pearisburg')]}
        onNewTrip={onNewTrip}
      />,
    )
    expect(screen.getByText('Recent sections')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Plan a new section' }))
    expect(onNewTrip).toHaveBeenCalled()
  })

  it('keeps its own action while a DAY draft is live, symmetrically', async () => {
    const user = userEvent.setup()
    const onNewTrip = vi.fn()
    const onResumeDraft = vi.fn()
    render(
      <PlanHome
        {...PROPS}
        room="sections"
        draftKind="day"
        onNewTrip={onNewTrip}
        onResumeDraft={onResumeDraft}
      />,
    )
    await user.click(screen.getByRole('button', { name: 'Plan a new section' }))
    expect(onNewTrip).toHaveBeenCalled()
    expect(onResumeDraft).not.toHaveBeenCalled()
  })

  it('shows no day-hike shelf - that room is one chip away', () => {
    render(
      <PlanHome
        {...PROPS}
        room="sections"
        trips={[trip('Damascus → Pearisburg')]}
        dayHikes={[dayHike('Pine Meadow loop')]}
      />,
    )
    expect(screen.queryByText('Your day hikes')).not.toBeInTheDocument()
    expect(screen.queryByText(/Pine Meadow/)).not.toBeInTheDocument()
  })
})

describe("the hike's own room (#1329, handoff §4)", () => {
  const inRoom = (props: Partial<PlanHomeProps> = {}) =>
    render(<PlanHome {...PROPS} room="sections" activeHike={hike()} {...props} />)

  it("puts the hike's name in the band, where the room's word used to be", () => {
    // #1317 bound this tab to the mode and left the band reading "Sections",
    // so nothing on the Plan tab said WHICH hike. "When I save a long hike,
    // it is not displaying anywhere" was partly this.
    inRoom()

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Springer → Katahdin',
    )
  })

  it('offers a way onto a different hike, and only where there is one', async () => {
    // `activeHikeId` could be set exactly once before this - by the pick
    // sheet, which only opened where no hike was active - so a hiker with
    // two hikes was stuck on whichever they picked first.
    const user = userEvent.setup()
    const onSwitchHike = vi.fn()
    inRoom({ onSwitchHike })

    await user.click(screen.getByRole('button', { name: /Switch hike/ }))
    expect(onSwitchHike).toHaveBeenCalled()

    cleanup()
    inRoom()
    expect(screen.queryByRole('button', { name: /Switch hike/ })).toBeNull()
  })

  it('prints the two figures and draws them, and draws no third band', () => {
    // The handoff overrides features/SEGMENTS.md here in as many words: no
    // gap rows, no gap arithmetic, no dashed gap band. The bar is walked and
    // to-go, and it is `aria-hidden` because the line above it says the same
    // thing in words a screen reader can use.
    const { container } = inRoom()

    expect(screen.getByText(/mi walked · .* mi to go/)).toBeInTheDocument()
    expect(container.querySelectorAll('.plan-home__bar > *')).toHaveLength(2)
    expect(container.querySelector('.plan-home__bar')).toHaveAttribute(
      'aria-hidden',
      'true',
    )
  })

  it('draws no bar at all for a hike with no end to end', () => {
    // A full-width grey bar under two zeroes is an illustration of an
    // absence. Absent means unknown, and the figures line still says so.
    const { container } = inRoom({
      activeHike: hike({ points: [{ name: 'Springer', mile: 12 }] }),
    })

    expect(container.querySelector('.plan-home__bar')).toBeNull()
  })

  it('separates the sections in the hike from the ones that are not', async () => {
    // Nothing in the app puts a PLANNED section into a hike yet
    // (`assignTrip` has one caller, the day-hike sheet), so a room that
    // showed only `tripIds` would hide a section the hiker laid out from
    // this very screen - the report this issue started from, one level down.
    const user = userEvent.setup()
    const onOpenTrip = vi.fn()
    inRoom({
      activeHike: hike({ tripIds: ['Damascus → Pearisburg'] }),
      trips: [trip('Damascus → Pearisburg'), trip('Hot Springs → Erwin')],
      onOpenTrip,
    })

    expect(screen.getByText('Sections in this hike')).toBeInTheDocument()
    expect(screen.getByText('Your other sections')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Hot Springs → Erwin/ }))
    expect(onOpenTrip).toHaveBeenCalledWith('Hot Springs → Erwin')
  })

  it('leads with the hike rather than a generic list, and never lists it twice', () => {
    // The old room showed "Your hikes" - every hike, including this one, as
    // a row among rows. The room is ABOUT this hike now, so it appears once,
    // as the thing to carry on with.
    inRoom()

    expect(screen.queryByText('Your hikes')).toBeNull()
    expect(screen.getAllByText('Springer → Katahdin')).toHaveLength(2)
  })

  it('renames the hike in place, which nothing could do before', async () => {
    // `renameHike` has been in the store since #788 with no caller, so every
    // hike kept the "A new long hike" that `handleNewHike` invents (#1344).
    const user = userEvent.setup()
    const onRenameHike = vi.fn()
    inRoom({ onRenameHike })

    await user.click(screen.getByRole('button', { name: /Rename/ }))
    const field = screen.getByLabelText('New name for Springer → Katahdin')
    await user.clear(field)
    await user.type(field, 'Georgia to Maine')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    expect(onRenameHike).toHaveBeenCalledWith('Georgia to Maine')
  })

  it('offers no rename where the shell passes no way to do one', () => {
    inRoom()
    expect(screen.queryByRole('button', { name: /Rename/ })).toBeNull()
  })

  it('names its primary "Plan a section", and gives the place up to the planner', () => {
    // #1344: "that content should live on the same page". The planner takes
    // the primary's place rather than opening over it - one thing at a time
    // in one column.
    inRoom()
    expect(screen.getByRole('button', { name: 'Plan a section' })).toBeInTheDocument()

    cleanup()
    inRoom({ sectionPlanner: <p>the planner</p> })
    expect(screen.getByText('the planner')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Plan a section' })).toBeNull()
  })

  it('falls back to the kept-sections list when the mode is long and no hike is picked', () => {
    // Transient by design - the pick sheet opens on the way in - and
    // reachable anyway. The honest answer there is everything the hiker has
    // kept, not a room about a hike they have not named.
    render(<PlanHome {...PROPS} room="sections" activeHike={null} trips={[trip('a')]} />)

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Sections')
  })
})

describe('what no home may say', () => {
  it('no score, no behind, no arrival clock - the standing guard', () => {
    // THREE HOMES SINCE #1329, and the third is the one the handoff singles
    // out: "Figures: miles walked · miles to go only. No percentages, no
    // behind, no ahead of, no on track, no streaks, no comparison to other
    // hikers" - with the note that this guard "must cover the new surfaces".
    // The hike room is where breaking it would be easiest, because it is the
    // one that draws a bar.
    for (const activeHike of [null, hike({ tripIds: ['Damascus → Pearisburg'] })]) {
      for (const room of ['day', 'sections'] as const) {
        render(
          <PlanHome
            {...PROPS}
            room={room}
            activeHike={activeHike}
            trips={[trip('Damascus → Pearisburg')]}
            dayHikes={[dayHike('Pine Meadow loop', { date: '2026-09-12' })]}
          />,
        )
        const text = document.body.textContent ?? ''
        expect(text).not.toMatch(/%|behind|ahead of|on track|streak/i)
        expect(text).not.toMatch(/\d{1,2}:\d{2}\s*(am|pm)/i)
        cleanup()
      }
    }
  })
})
