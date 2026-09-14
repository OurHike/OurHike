import { describe, it, expect, vi, afterEach } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PlanStart, type PlanStartProps } from './PlanStart'
import { STANDARD_PACE } from '../lib/pace'
import type { SuggestedHike } from '../lib/suggestedHikes'

// Step 1 of the spine (#1373, frame 3e): one screen where "Find a hike" and
// "What are you planning?" stood, the kind read off the mode and never asked,
// every door routing, and a refusal that is a sentence with a way out.

afterEach(() => cleanup())

const NJ = { lon: -74.6, lat: 41.2 }
const walk = (name: string): SuggestedHike => ({
  id: name,
  name,
  miles: 5.2,
  difficulty: 'moderate',
  author: { kind: 'club', name: 'NY-NJ Trail Conference' },
  segments: [
    [
      { coord: [NJ.lon, NJ.lat], poiId: null },
      { coord: [NJ.lon + 0.01, NJ.lat], poiId: null },
    ],
  ],
})

function props(overrides: Partial<PlanStartProps> = {}): PlanStartProps {
  return {
    mode: 'day',
    network: { kind: 'ready' } as PlanStartProps['network'],
    hasFix: true,
    hikes: [walk('Pine Meadow Lake loop'), walk('Almost Perpendicular')],
    near: NJ,
    units: 'imperial',
    pace: STANDARD_PACE,
    onNamePlace: vi.fn(),
    onWhereIAm: vi.fn(),
    onPickOnMap: vi.fn(),
    onDraw: vi.fn(),
    onFindHike: vi.fn(),
    onOpenSuggestedHike: vi.fn(),
    onRecordWalked: vi.fn(),
    onCancel: vi.fn(),
    ...overrides,
  }
}

describe('step 1 - where do you want to go', () => {
  it('prints the mode’s answer on the rail and never asks the kind again', () => {
    const { rerender } = render(<PlanStart {...props()} />)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Where do you want to go?',
    )
    const rail = screen.getByRole('navigation', { name: 'Planning steps' })
    expect(rail).toHaveTextContent('Day hike')
    expect(screen.queryByText(/what are you planning/i)).toBeNull()

    rerender(<PlanStart {...props({ mode: 'long' })} />)
    expect(screen.getByRole('navigation', { name: 'Planning steps' })).toHaveTextContent(
      'Long hike',
    )
    // A volunteer plans as a day hiker.
    rerender(<PlanStart {...props({ mode: 'volunteer' })} />)
    expect(screen.getByRole('navigation', { name: 'Planning steps' })).toHaveTextContent(
      'Day hike',
    )
  })

  it('every door routes: the field, where I am, the map, the pen', async () => {
    const user = userEvent.setup()
    const p = props()
    render(<PlanStart {...p} />)

    await user.click(screen.getByRole('button', { name: /a shelter, a summit, a town/i }))
    expect(p.onNamePlace).toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Where I am' }))
    expect(p.onWhereIAm).toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Pick on the map' }))
    expect(p.onPickOnMap).toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Draw it myself' }))
    expect(p.onDraw).toHaveBeenCalled()
    // No "Route it" under an empty field: nothing to route yet (D10).
    expect(screen.queryByRole('button', { name: /route it/i })).toBeNull()
  })

  it('offers "Where I am" only with a fix, and the pen only to a day hiker', () => {
    render(<PlanStart {...props({ hasFix: false, mode: 'long' })} />)

    expect(screen.queryByRole('button', { name: 'Where I am' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Draw it myself' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Pick on the map' })).toBeInTheDocument()
  })

  it('with no junction graph on the phone, the doors are a sentence and a retry - never greyed buttons (R5, D10)', async () => {
    const onRetryNetwork = vi.fn()
    const user = userEvent.setup()
    render(
      <PlanStart
        {...props({
          network: {
            kind: 'absent',
            because: 'unreachable',
          } as PlanStartProps['network'],
          onRetryNetwork,
        })}
      />,
    )

    expect(screen.queryByRole('button', { name: 'Pick on the map' })).toBeNull()
    expect(screen.getByRole('note')).toHaveTextContent(/trail network/i)
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetryNetwork).toHaveBeenCalled()
    // A long hike needs no junction graph: its doors stay.
    cleanup()
    render(
      <PlanStart
        {...props({
          mode: 'long',
          network: {
            kind: 'absent',
            because: 'unreachable',
          } as PlanStartProps['network'],
        })}
      />,
    )
    expect(screen.getByRole('button', { name: 'Pick on the map' })).toBeInTheDocument()
  })

  it('carries the published shelf as a doorway: the count into the finder, chips with the facet on, cards that open', async () => {
    const user = userEvent.setup()
    const p = props()
    render(<PlanStart {...p} />)

    const published = screen.getByRole('region', { name: 'Published hikes' })
    await user.click(within(published).getByRole('button', { name: '2 hikes ›' }))
    expect(p.onFindHike).toHaveBeenLastCalledWith()
    await user.click(within(published).getByRole('button', { name: 'Near me' }))
    expect(p.onFindHike).toHaveBeenLastCalledWith({ sort: 'nearest' })
    await user.click(within(published).getByRole('button', { name: 'No car' }))
    expect(p.onFindHike).toHaveBeenLastCalledWith({ transitOnly: true })
    await user.click(within(published).getByRole('button', { name: 'Easy' }))
    expect(p.onFindHike).toHaveBeenLastCalledWith({ difficulty: ['easy'] })
    await user.click(
      within(published).getByRole('button', { name: /Pine Meadow Lake loop/ }),
    )
    expect(p.onOpenSuggestedHike).toHaveBeenCalledWith('Pine Meadow Lake loop')
  })

  it('has no shelf and no "N hikes" with nothing published', () => {
    render(<PlanStart {...props({ hikes: [] })} />)

    expect(screen.queryByRole('region', { name: 'Published hikes' })).toBeNull()
  })

  it('keeps the walk-already-done door for a day hiker, and cancels', async () => {
    const user = userEvent.setup()
    const p = props()
    const { rerender } = render(<PlanStart {...p} />)

    await user.click(screen.getByRole('button', { name: /already done/i }))
    expect(p.onRecordWalked).toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(p.onCancel).toHaveBeenCalled()

    rerender(<PlanStart {...props({ mode: 'long' })} />)
    expect(screen.queryByRole('button', { name: /already done/i })).toBeNull()
  })
})
