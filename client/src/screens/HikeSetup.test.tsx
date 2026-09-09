// Setting up a long hike (#1317).
//
// Two tests carry the design: the leg lines read per-leg direction (so a
// flip-flop reads both ways), and the total is the WALKING rather than the
// ground, which is the pair of figures a there-and-back makes necessary.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { HikeSetup } from './HikeSetup'
// Lifted into the lib so the screen can stay deferred (#1302) - see its
// header there.
import { setupRefusal } from '../lib/hikeText'
import type { Hike } from '../lib/hikes'
import type { StoredPoi } from '../lib/trailData'
import type { Trip } from '../lib/trips'

function hike(over: Partial<Hike> = {}): Hike {
  return {
    id: 'h1',
    name: 'A new long hike',
    type: 'section',
    trailId: 'AT',
    points: [
      { name: 'Springer', mile: 0 },
      { name: 'Katahdin', mile: 2197.4 },
    ],
    status: 'planning',
    tripIds: [],
    ...over,
  }
}

const PROPS = {
  onRename: vi.fn(),
  hike: hike(),
  recorded: [] as readonly Trip[],
  pois: [] as readonly StoredPoi[],
  units: 'imperial' as const,
  totalMiles: 2197.4,
  onEditPoint: vi.fn(),
  onAddPoint: vi.fn(),
  onUndo: null,
  onRecordStretch: vi.fn(),
  onOpenRecorded: vi.fn(),
  onStart: vi.fn(),
  onCancel: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('setting up a long hike', () => {
  it('counts its points and its legs, and says two ends is the whole requirement', () => {
    render(<HikeSetup {...PROPS} />)

    expect(screen.getByText(/Its points · 2 points · 1 leg/)).toBeInTheDocument()
    expect(screen.getByText(/Two ends is the whole requirement/)).toBeInTheDocument()
  })

  it('gives each point its mile, and says plainly when it has no date', () => {
    // A point with no date is normal, not incomplete - so it says so rather
    // than leaving a gap that reads as something unfinished.
    render(
      <HikeSetup
        {...PROPS}
        hike={hike({
          points: [
            { name: 'Springer', mile: 0, date: '2024-03-14' },
            { name: 'Katahdin', mile: 2197.4 },
          ],
        })}
      />,
    )

    expect(screen.getByText('mi 0.0 · 14 Mar')).toBeInTheDocument()
    expect(screen.getByText('mi 2,197.4 · no date')).toBeInTheDocument()
  })

  it('reads northbound on one leg and southbound on the next', () => {
    // Direction belongs to the leg. There is no hike-level answer that is
    // true of both halves of a flip-flop.
    render(
      <HikeSetup
        {...PROPS}
        hike={hike({
          points: [{ mile: 1023.4 }, { mile: 2197.4 }, { mile: 0 }],
        })}
      />,
    )

    expect(screen.getByText(/1,174\.0 mi · northbound/)).toBeInTheDocument()
    expect(screen.getByText(/2,197\.4 mi · southbound/)).toBeInTheDocument()
  })

  it('totals the walking, not the ground', () => {
    // A there-and-back over the same 1,023 miles is 2,046 miles of walking.
    // Both numbers are true of it; this screen is where a hiker asks how far
    // they will walk.
    render(
      <HikeSetup
        {...PROPS}
        hike={hike({ points: [{ mile: 0 }, { mile: 1023.4 }, { mile: 0 }] })}
      />,
    )

    expect(screen.getByText('2,046.8 mi across 2 legs')).toBeInTheDocument()
  })

  it('refuses to start below two points, and says why rather than going quiet', () => {
    render(<HikeSetup {...PROPS} hike={hike({ points: [{ mile: 0 }] })} />)

    expect(screen.getByRole('button', { name: 'Start this long hike' })).toBeDisabled()
    expect(screen.getByText(/needs two ends/i)).toBeInTheDocument()
  })

  it('refuses a point past the end of the trail rather than rounding it down', () => {
    // plannedHike()'s rule: a corrected value is a number the hiker never
    // entered, presented as though they had.
    render(
      <HikeSetup
        {...PROPS}
        hike={hike({ points: [{ mile: 0 }, { mile: 2400 }] })}
        totalMiles={2197.4}
      />,
    )

    expect(
      screen.getByText(/mi 2,400\.0 is past the end of the trail/),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start this long hike' })).toBeDisabled()
  })

  it('refuses nothing for being too far along when the download cannot say', () => {
    // An unknown bound is not a bound.
    expect(setupRefusal(hike({ points: [{ mile: 0 }, { mile: 9999 }] }), null)).toBeNull()
  })

  it('refuses a trail this build has no mile axis for', () => {
    expect(setupRefusal(hike({ trailId: 'LP' }), 2197.4)).toMatch(
      /only measure a hike on the Appalachian Trail/,
    )
  })

  it('opens the picker on a point, and offers one on the way', async () => {
    const user = userEvent.setup()
    const onEditPoint = vi.fn()
    const onAddPoint = vi.fn()
    render(<HikeSetup {...PROPS} onEditPoint={onEditPoint} onAddPoint={onAddPoint} />)

    // By its mile, not its name: the "add a stretch you remember" door's
    // example also says Springer, and a query that matched both would be
    // testing whichever the DOM happened to order first.
    await user.click(screen.getByRole('button', { name: /mi 0\.0/ }))
    expect(onEditPoint).toHaveBeenCalledWith(0)

    await user.click(screen.getByRole('button', { name: /Add a point on the way/ }))
    expect(onAddPoint).toHaveBeenCalled()
  })

  it('prints no percentage, nothing behind and nothing on track', () => {
    // The standing guard, with ONE exemption written out rather than the
    // regex quietly loosened: the note ends "nothing falls behind", which is
    // the promise this guard exists to keep and not a claim about the hiker.
    // Removing that sentence and then applying the guard in full is the
    // honest version - a `/behind(?! )/`-style dodge would also stop
    // catching "you are behind", which is the whole point.
    const { container } = render(<HikeSetup {...PROPS} />)
    const said = (container.textContent ?? '').replace(
      'days get planned as you walk them, and nothing falls behind.',
      '',
    )

    expect(said).not.toMatch(/%|behind|ahead of|on track|streak/i)
    // And the exempted sentence really is the only "behind" on the screen.
    expect((container.textContent ?? '').match(/behind/gi)).toHaveLength(1)
  })
})
