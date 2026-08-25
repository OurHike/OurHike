// Tests for screens/DayHikeCard.tsx - the finished day hike (#980).
//
// Two kinds of pin. The positive ones check the sourced blocks render from
// the LIVE resolution, org names from the steward join and never raw source
// keys. The negative ones are the point of the card's scope: nothing here may
// print a figure whose source does not exist yet - no ±ft, no parking, no
// "Chip in" - because a block invented to fill the frame is the exact failure
// CLAUDE.md's evidence standard names.
//
// ≈time moved sides. It is printed when it is HANDED one (lib/dayHikeTime.ts
// prices a walk that lies on the A.T. centerline) and absent when it is not,
// so the tests below pin both halves: the number when there is one, and
// silence rather than a placeholder when there is not.

import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DayHikeCard } from './DayHikeCard'
import type { BailOut, ResolvedDayHike } from '../lib/dayHikeCard'
import type { DayHike } from '../lib/dayHikes'
import type { Stewards } from '../lib/stewards'

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
    name: 'NY–NJ Trail Conference',
    trust: null,
    licence: null,
    attribution: null,
    layers: [],
    keys: ['nynjtc_long_path'],
  },
]

const HIKE: DayHike = {
  id: 'hike-1',
  name: 'Pine Meadow day hike',
  date: '2026-08-29',
  segments: [
    [
      { coord: [-74.095, 41.25], poiId: null },
      { coord: [-74.085, 41.25], poiId: null },
    ],
  ],
  // The stale cache: 5 miles, one leg. A card leaning on the live resolution
  // must never print these numbers.
  figures: {
    miles: 5,
    legs: [
      {
        name: 'Pine Meadow Trail',
        source: 'oprhp_trails',
        blaze_color: 'blue',
        miles: 5,
      },
    ],
  },
  looped: true,
  recorded: 'planned',
}

const RESOLVED: ResolvedDayHike = {
  segments: [],
  miles: 6.4,
  looped: true,
  legs: [
    {
      name: 'Pine Meadow Trail',
      source: 'oprhp_trails',
      blaze_color: 'blue',
      trail_id: 'oprhp_trails:1',
      miles: 2.1,
    },
    {
      name: 'Seven Hills Trail',
      source: 'nynjtc_long_path',
      blaze_color: 'white',
      trail_id: 'nynjtc_long_path:2',
      miles: 4.3,
    },
  ],
}

const BAIL_OUTS: BailOut[] = [
  { miles: 3.2, name: 'Kakiat Trail', blaze_color: 'white', source: 'nynjtc_long_path' },
]

function renderCard(overrides: Partial<Parameters<typeof DayHikeCard>[0]> = {}) {
  return render(
    <DayHikeCard
      hike={HIKE}
      resolved={RESOLVED}
      bailOuts={BAIL_OUTS}
      stewards={STEWARDS}
      units="imperial"
      networkAvailable={true}
      // Unpriced by default, which is the state most saved hikes are in:
      // lib/dayHikeTime.ts answers null for any walk with a step off the
      // A.T. centerline, and this fixture's legs are Harriman trails.
      walkingMinutes={null}
      mode="saved"
      onClose={vi.fn()}
      onDelete={vi.fn()}
      {...overrides}
    />,
  )
}

describe('the sourced blocks', () => {
  it('prints the live figures, the legs with their orgs, and the LOOP badge', () => {
    renderCard()

    expect(screen.getByText(/6\.4 mi · 2 legs/)).toBeInTheDocument()
    expect(screen.getByText('LOOP')).toBeInTheDocument()
    expect(screen.getByText('sat 29 aug')).toBeInTheDocument()
    expect(screen.getByText('Seven Hills Trail')).toBeInTheDocument()
    // Per-leg miles, back since #1002 priced them at the walked metres.
    expect(screen.getByText('2.1 mi')).toBeInTheDocument()
    expect(screen.getByText('4.3 mi')).toBeInTheDocument()
    // The steward join's names, never the export's raw keys.
    expect(screen.getByText('NYS Parks')).toBeInTheDocument()
    expect(screen.queryByText(/oprhp_trails/)).not.toBeInTheDocument()
    // Both orgs counted, in the frame's own sentence.
    expect(
      screen.getByText(/Two organizations keep this loop walkable/),
    ).toBeInTheDocument()
  })

  it('prints the walking time when the walk can be priced, as moving time', () => {
    // 135 minutes is 2h 15m. The ≈ and the 5-minute rounding are
    // lib/naismith.ts's display rule, reached through the builder bar's
    // `walkingTime` so the estimate a hiker read while building and the one
    // on the finished card cannot drift apart.
    renderCard({ walkingMinutes: 135 })

    expect(screen.getByText(/≈2h 15m walking/)).toBeInTheDocument()
  })

  it('never turns the estimate into a time of day', () => {
    // Moving time, not an arrival clock - lib/naismith.ts refuses one and
    // HIKER_SAFETY.md's posture forbids it. The word "walking" is what keeps
    // the number readable as a duration.
    renderCard({ walkingMinutes: 135 })

    expect(document.body.textContent).not.toMatch(/\d{1,2}:\d{2}/)
    expect(document.body.textContent).not.toMatch(/back by|arrive|expect me/i)
  })

  it('prints a way off with its mile, name and blaze', () => {
    renderCard()

    expect(screen.getByText('If you need to get off')).toBeInTheDocument()
    // A walked length, so it converts for a metric hiker - not the A.T.'s
    // "mi 3.2" marker voice, which names a point that never converts.
    expect(screen.getByText('at 3.2 mi')).toBeInTheDocument()
    expect(screen.getByText(/Kakiat Trail \(white\)/)).toBeInTheDocument()
  })

  it('says so when no marked trail leaves the route, rather than omitting the block', () => {
    renderCard({ bailOuts: [] })

    expect(screen.getByText(/No marked trail leaves this loop/)).toBeInTheDocument()
  })
})

describe('the honest absences', () => {
  it('prices nothing and promises nothing it has no source for', () => {
    renderCard()

    // No time, because this walk has none to print: its legs are Harriman
    // trails and no elevation is published for them, so lib/dayHikeTime.ts
    // hands the card a null and the card says nothing. A ≈ here would be an
    // invented figure wearing an honest prefix. (A walk that CAN be priced
    // prints one, two tests up - the absence is a property of the evidence,
    // not a property of this card.)
    expect(screen.queryByText(/≈/)).not.toBeInTheDocument()
    expect(screen.queryByText(/walking\b/)).not.toBeInTheDocument()
    // No climb figures, no parking block, no donate link - each waits on a
    // source that does not exist yet (#981, #931, the registry).
    expect(screen.queryByText(/ft\b/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Parking/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Chip in/)).not.toBeInTheDocument()
  })

  it('falls back to the stored cache with the no-network sentence', () => {
    renderCard({ resolved: null, networkAvailable: false })

    // The cache's own numbers, under a sentence saying that is what they are.
    expect(screen.getByText(/5\.0 mi · 1 leg\b/)).toBeInTheDocument()
    expect(screen.getByText(/hasn.t got the trail network yet/)).toBeInTheDocument()
    // No ways-off section at all: nothing honest to put in it.
    expect(screen.queryByText('If you need to get off')).not.toBeInTheDocument()
  })

  it('says when the current map cannot place the walk, which is a different sentence', () => {
    renderCard({ resolved: null, networkAvailable: true })

    expect(
      screen.getByText(/current trail map can.t place this walk/),
    ).toBeInTheDocument()
  })

  it('credits no organization on a walk whose legs nobody attributed', () => {
    renderCard({
      resolved: {
        ...RESOLVED,
        legs: [
          {
            name: 'Old Woods Road',
            source: null,
            blaze_color: null,
            trail_id: null,
            miles: 6.4,
          },
        ],
      },
    })

    expect(screen.queryByText(/organizations? keeps?/)).not.toBeInTheDocument()
  })
})

describe('the two modes', () => {
  it('review offers Save as the one primary, and no delete', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    renderCard({ mode: 'review', onSave })

    await user.click(screen.getByRole('button', { name: 'Save this day hike' }))
    expect(onSave).toHaveBeenCalledOnce()
    expect(screen.queryByText(/Delete/)).not.toBeInTheDocument()
  })

  it('saved deletes in two taps, and Keep it disarms', async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn()
    renderCard({ onDelete })

    await user.click(screen.getByRole('button', { name: 'Delete this day hike' }))
    expect(onDelete).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Keep it' }))
    expect(screen.queryByText('Delete this day hike?')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Delete this day hike' }))
    await user.click(screen.getByRole('button', { name: 'Delete' }))
    expect(onDelete).toHaveBeenCalledOnce()
  })
})

describe('the #1008 additions', () => {
  it('offers the date as a field the hiker sets, and clearing it clears the date', async () => {
    const user = userEvent.setup()
    const onSetDate = vi.fn()
    renderCard({ onSetDate })

    const field = screen.getByLabelText('When') as HTMLInputElement
    expect(field.value).toBe('2026-08-29')

    await user.clear(field)
    expect(onSetDate).toHaveBeenLastCalledWith(null)
  })

  it('shows no date field at all when the shell offers no way to keep one', () => {
    renderCard()
    expect(screen.queryByLabelText('When')).not.toBeInTheDocument()
  })

  it('draws a gap as a gap: straight-line miles and the refusal to route it', () => {
    renderCard({
      hike: {
        ...HIKE,
        looped: false,
        segments: [
          [
            { coord: [-74.095, 41.25], poiId: null },
            { coord: [-74.09, 41.25], poiId: null },
          ],
          [
            { coord: [-74.085, 41.25], poiId: null },
            { coord: [-74.08, 41.25], poiId: null },
          ],
        ],
      },
      // The cache path: a multi-segment loop refuses resolution anyway.
      resolved: null,
    })

    expect(
      screen.getByText(/with no trail under it, straight across/),
    ).toBeInTheDocument()
    expect(screen.getByText(/that stretch is yours/)).toBeInTheDocument()
  })

  it('a single-segment walk shows no gap row - nothing to be honest about', () => {
    renderCard()
    expect(screen.queryByText(/no trail under it/)).not.toBeInTheDocument()
  })

  it('saved mode opens Leave this with someone in the same sheet frame', async () => {
    const user = userEvent.setup()
    renderCard()

    await user.click(screen.getByRole('button', { name: 'Leave this with someone' }))
    expect(
      screen.getByRole('dialog', { name: 'Leave this with someone' }),
    ).toBeInTheDocument()
    // The card's own blocks stepped aside; the close returns to them.
    expect(screen.queryByText('Legs')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.getByText('Legs')).toBeInTheDocument()
  })

  it('review mode offers no leave door - Save stays the one primary', () => {
    renderCard({ mode: 'review', onSave: vi.fn() })
    expect(
      screen.queryByRole('button', { name: 'Leave this with someone' }),
    ).not.toBeInTheDocument()
  })
})
