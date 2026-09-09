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
