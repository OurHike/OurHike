// A walk already done (#982).
//
// THE STANDING NEGATIVE ASSERTION LIVES HERE TOO, and this is the surface it
// matters most on. `Plan.test.tsx` carries it, `DaySummary.test.tsx` mirrors
// it, and #982 says plainly why a third copy earns its place: a screen about a
// walk somebody already finished is exactly where prescriptive gamification
// creeps in, and value #1 forbids it. A change that makes this screen score a
// walk should fail here rather than ship.

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ResolvedDayHike } from '../lib/dayHikeCard'
import type { DayHike } from '../lib/dayHikes'
import type { Stewards } from '../lib/stewards'
import { WalkedHike } from './WalkedHike'

// Explicit, because this project runs Vitest without `globals`, so Testing
// Library's automatic cleanup never registers. Without it every render in this
// file stacks on the one before and `getByText` finds two of everything -
// which is exactly how this suite first failed.
afterEach(cleanup)

const STEWARDS: Stewards = [
  {
    provider: 'NYS OPRHP',
    name: 'NYS Parks',
    trust: null,
    licence: null,
    attribution: null,
    layers: [],
    keys: ['oprhp_trails'],
  },
  {
    provider: 'NYNJTC',
    name: 'NYNJTC',
    trust: null,
    licence: null,
    attribution: null,
    layers: [],
    keys: ['nynjtc_long_path'],
  },
]

const WALKED: DayHike = {
  id: 'walk-1',
  name: 'Pine Meadow loop',
  date: '2026-08-24',
  segments: [
    [
      { coord: [-74.095, 41.25], poiId: null },
      { coord: [-74.085, 41.25], poiId: null },
    ],
  ],
  figures: {
    miles: 5.9,
    legs: [
      {
        name: 'Pine Meadow Trail',
        source: 'oprhp_trails',
        blaze_color: 'blue',
        miles: 3.1,
      },
      {
        name: 'Seven Hills Trail',
        source: 'nynjtc_long_path',
        blaze_color: 'orange',
        miles: 2.8,
      },
    ],
    climb: { gainFt: 1240, lossFt: 1240 },
  },
  looped: true,
  recorded: 'walked',
  note: '',
}

function renderWalk(overrides: Partial<Parameters<typeof WalkedHike>[0]> = {}) {
  const props = {
    hike: WALKED,
    resolved: null as ResolvedDayHike | null,
    stewards: STEWARDS,
    units: 'imperial' as const,
    onClose: vi.fn(),
    onSetNote: vi.fn(),
    onSetDate: vi.fn(),
    onDelete: vi.fn(),
    ...overrides,
  }
  const view = render(<WalkedHike {...props} />)
  return { ...props, ...view }
}

describe('what it says about the walk', () => {
  it('leads with the date, because a walk that happened happened on a day', () => {
    renderWalk()

    expect(screen.getByLabelText('The day you walked it')).toHaveValue('2026-08-24')
  })

  it('prints the distance and the climb', () => {
    renderWalk()

    // Scoped to the <dd>, because a bare text match hits the definition and
    // its wrapper both.
    expect(screen.getByText(/5\.9 mi/, { selector: 'dd' })).toBeInTheDocument()
    expect(screen.getByText(/1,240/, { selector: 'dd' })).toBeInTheDocument()
  })

  it('names the organizations that keep the ground walkable', () => {
    // The one thing this screen says that is not about the hiker.
    renderWalk()

    expect(
      screen.getByText(/NYS Parks and NYNJTC/, { selector: '.walked-hike__orgs' }),
    ).toBeInTheDocument()
  })

  it('says the figures are the stored ones when it cannot check them', () => {
    // The same disclosure DayHikeCard makes: printing numbers computed from a
    // graph this phone no longer holds, without comment, is a display
    // outrunning its source.
    renderWalk({ resolved: null })

    expect(
      screen.getByText(/figures saved with the walk/, {
        selector: '.walked-hike__cached',
      }),
    ).toBeInTheDocument()
  })
})

describe("the hiker's own line", () => {
  it('starts from what they wrote, and keeps what they type', () => {
    const props = renderWalk({
      hike: { ...WALKED, note: 'Blueberries on the open rock.' },
    })

    expect(screen.getByRole('textbox')).toHaveValue('Blueberries on the open rock.')

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Cold start.' } })
    expect(props.onSetNote).toHaveBeenCalledWith('Cold start.')
  })

  it('never fills it in for them', () => {
    // The app does not suggest, complete or seed this field. It is the part of
    // the screen the app did not write, and a placeholder is the most it says.
    const props = renderWalk()

    expect(screen.getByRole('textbox')).toHaveValue('')
    expect(props.onSetNote).not.toHaveBeenCalled()
  })
})

describe('what it must never do', () => {
  it('does not score the walk, compare it, or judge the pace', () => {
    // #982's own rule. `DaySummary.test.tsx`'s list, inherited whole - this
    // screen prints no pace line at all, so `'was '` costs it nothing.
    const { container } = renderWalk({
      hike: { ...WALKED, note: 'A good day out.' },
    })

    const text = (container.textContent ?? '').toLowerCase()
    for (const forbidden of [
      'behind',
      'ahead',
      'target',
      'was ',
      'streak',
      'goal',
      'short of',
      'faster',
      'slower',
      'personal best',
    ]) {
      expect(text).not.toContain(forbidden)
    }
  })

  it('offers nothing to bail out of, follow, or leave with somebody', () => {
    // There is nothing left to get off. Every one of those is a control about
    // a walk that has not happened yet, and on this screen it would be the
    // app misreading which tense it is in.
    renderWalk()

    expect(screen.queryByText(/If you need to get off/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Follow/i })).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /Leave this with/i }),
    ).not.toBeInTheDocument()
  })

  it('prints no walking time', () => {
    // The hiker walked it. Telling somebody how long the app thinks their own
    // finished walk took is the app arguing with them about their afternoon.
    const { container } = renderWalk()

    expect(container.textContent).not.toContain('walking')
    expect(container.textContent).not.toMatch(/≈/)
  })
})

describe('deleting one', () => {
  it('asks first, and does not delete on the asking', () => {
    const props = renderWalk()

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(props.onDelete).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Delete this walk' }))
    expect(props.onDelete).toHaveBeenCalledTimes(1)
  })

  it('lets the hiker keep it after all', () => {
    const props = renderWalk()

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    fireEvent.click(screen.getByRole('button', { name: 'Keep it' }))

    expect(props.onDelete).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument()
  })
})
