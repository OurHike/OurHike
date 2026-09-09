// The "which long hike?" sheet (#1317).
//
// The load-bearing test is the last one: the sheet says out loud that
// closing it puts the mode back, because a mode control that silently
// reverts is one a hiker stops trusting.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { HikePickSheet } from './HikePickSheet'
import type { Hike } from '../lib/hikes'
import type { StoredPoi } from '../lib/trailData'
import type { Trip } from '../lib/trips'
import { buildPlan } from '../lib/plan'

const TODAY = '2026-09-09'

function hike(over: Partial<Hike> = {}): Hike {
  return {
    id: 'h1',
    name: 'Springer → Katahdin',
    type: 'thru',
    trailId: 'AT',
    points: [
      { name: 'Springer', mile: 0 },
      { name: 'Katahdin', mile: 2197.4 },
    ],
    status: 'walking',
    tripIds: [],
    ...over,
  }
}

function walkedTrip(id: string, from: number, to: number): Trip {
  const plan = buildPlan(
    [
      { mile: from, resupply: false },
      { mile: to, resupply: false },
    ],
    { miles: 10 },
  )
  return {
    id,
    name: 'A section',
    plan: { ...plan, days: plan.days.map((day) => ({ ...day, walked: true })) },
  }
}

const POIS: readonly StoredPoi[] = []

const PROPS = {
  hikes: [] as readonly Hike[],
  trips: [] as readonly Trip[],
  pois: POIS,
  units: 'imperial' as const,
  today: TODAY,
  onPick: vi.fn(),
  onNew: vi.fn(),
  onClose: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the pick sheet', () => {
  it('offers a new hike even when there are none to pick', () => {
    render(<HikePickSheet {...PROPS} />)

    expect(screen.getByRole('dialog', { name: 'Which long hike?' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /A new long hike/ })).toBeInTheDocument()
  })

  it('says what closing it does, on the screen and not only in the code', async () => {
    // The one place a mode tap is not instantaneous. A revert that arrived
    // as a surprise afterwards would teach a hiker the control lies.
    const user = userEvent.setup()
    const onClose = vi.fn()
    render(<HikePickSheet {...PROPS} onClose={onClose} />)

    expect(screen.getByText(/back on Day hike/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(onClose).toHaveBeenCalled()
  })

  it('names each hike by its sections and its two figures', () => {
    const withTrips = hike({ tripIds: ['a'] })
    render(
      <HikePickSheet {...PROPS} hikes={[withTrips]} trips={[walkedTrip('a', 0, 412)]} />,
    )

    const door = screen.getByRole('button', { name: /Springer → Katahdin/ })
    expect(door).toHaveTextContent('1 section')
    expect(door).toHaveTextContent('412.0 mi walked')
    expect(door).toHaveTextContent('1,785.4 mi to go')
  })

  it('says where a paused hike stopped, and how long ago, instead of its figures', () => {
    // What a hiker choosing between hikes is actually distinguishing by -
    // "the one I stopped in August" - and its figures have not moved since.
    render(
      <HikePickSheet
        {...PROPS}
        hikes={[hike({ status: 'paused', pausedAtMile: 104, pausedOn: '2025-10-11' })]}
      />,
    )

    const door = screen.getByRole('button', { name: /Springer → Katahdin/ })
    expect(door).toHaveTextContent('paused at mi 104.0')
    expect(door).toHaveTextContent('11 months ago')
  })

  it('refuses a hike too short to walk with the reason, never a dead control', () => {
    // LineSheet's rule: a door that cannot open is a sentence.
    render(<HikePickSheet {...PROPS} hikes={[hike({ points: [{ mile: 0 }] })]} />)

    const door = screen.getByRole('button', { name: /Springer → Katahdin/ })
    expect(door).toBeDisabled()
    expect(door).toHaveTextContent('Needs two ends')
  })

  it('becomes a switch where a hike is already active, and says so', () => {
    // #1329: one sheet for both moments, because they are one question -
    // which of these hikes am I on. What varies is the title, the last
    // sentence of the lede and a mark on the one you are on.
    render(
      <HikePickSheet
        {...PROPS}
        hikes={[hike(), hike({ id: 'h2', name: 'Virginia, over a few years' })]}
        activeHikeId="h2"
      />,
    )

    expect(
      screen.getByRole('heading', { name: 'Which hike are you on?' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Virginia, over a few years/ }),
    ).toHaveTextContent('you\u2019re on this one')
    expect(
      screen.getByRole('button', { name: /Springer → Katahdin/ }),
    ).not.toHaveTextContent('you\u2019re on this one')
  })

  it('does not promise a revert to Day hike when there is a hike to stay on', () => {
    // THE LOAD-BEARING PAIR. `handleCancelHikePick` reverts the mode only
    // where `activeHikeId` is null, so a sheet opened as a switch and closed
    // leaves the hiker exactly where they were. Saying "you're back on Day
    // hike" there would be false, and a mode that behaves differently from
    // what the screen said is the thing this sentence exists to prevent.
    const { container, rerender } = render(<HikePickSheet {...PROPS} hikes={[hike()]} />)
    expect(container.textContent).toMatch(/back on Day hike/)

    rerender(<HikePickSheet {...PROPS} hikes={[hike()]} activeHikeId="h1" />)
    expect(container.textContent).not.toMatch(/back on Day hike/)
    expect(container.textContent).toMatch(/the one you leave stays exactly as it is/i)
  })

  it('leaves the list in one order, whichever hike you are on', () => {
    // A switch whose list re-orders itself under the finger is a switch that
    // picks the wrong hike. The one you are on is MARKED, never moved.
    const order = () =>
      screen
        .getAllByRole('button')
        .map((node) => node.textContent ?? '')
        .map((text) =>
          text.startsWith('Springer')
            ? 'springer'
            : text.startsWith('Virginia')
              ? 'virginia'
              : null,
        )
        .filter((name) => name !== null)

    const hikes = [hike(), hike({ id: 'h2', name: 'Virginia, over a few years' })]
    render(<HikePickSheet {...PROPS} hikes={hikes} />)
    expect(order()).toEqual(['springer', 'virginia'])
    cleanup()

    render(<HikePickSheet {...PROPS} hikes={hikes} activeHikeId="h2" />)
    expect(order()).toEqual(['springer', 'virginia'])
  })

  it('prints no percentage, nothing behind and nothing on track', () => {
    // The standing guard, on a new surface. OurHikeValues.md #1.
    const { container } = render(
      <HikePickSheet
        {...PROPS}
        hikes={[hike({ tripIds: ['a'] })]}
        trips={[walkedTrip('a', 0, 412)]}
      />,
    )

    expect(container.textContent).not.toMatch(/%|behind|ahead of|on track|streak/i)
  })
})
