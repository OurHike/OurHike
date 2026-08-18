// Tests for the hike zoom and its ribbon (#790).
//
// Two things here are load-bearing rather than cosmetic. The GAP ROWS: a
// zoom that lists a hike's pieces while omitting the unwalked ones is a
// list of achievements, which is the thing this project has repeatedly
// decided a plan must not become. And the NEGATIVE assertion the Plan tab
// already carries, extended to these new surfaces - they show far more of a
// plan than the timeline does, so they are where a score would arrive.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { HikeZoom } from './HikeZoom'
import { recordedPlan, type Hike } from '../lib/hikes'
import { buildPlan, type HikePlan } from '../lib/plan'
import { tripRowHeight } from '../lib/planDisplay'
import type { StoredPoi } from '../lib/trailData'
import type { Trip } from '../lib/trips'

/** `days` even days from `from` to `to`, walked or not. The ends keep their
 *  names because a gap beside them is named from them. */
function plan(from: number, to: number, days: number, walked: boolean): HikePlan {
  const stops = Array.from({ length: days + 1 }, (_, index) => {
    const mile = from + ((to - from) * index) / days
    return {
      mile,
      ...(index === 0 || index === days ? { name: `Stop ${mile}` } : {}),
      resupply: false,
    }
  })
  const built = buildPlan(stops, { miles: (to - from) / days })
  if (walked) built.days.forEach((day) => (day.walked = true))
  return built
}

const HIKE: Hike = {
  id: 'h1',
  name: 'Virginia, over a few years',
  type: 'section',
  start: { name: 'Damascus', mile: 0 },
  end: { name: 'Rockfish Gap', mile: 100 },
  tripIds: ['a', 'b'],
}

const TRIPS: Trip[] = [
  { id: 'a', name: 'Spring section', plan: plan(0, 30, 3, true) },
  { id: 'b', name: 'Grayson week', plan: plan(60, 80, 2, false) },
]

const PROPS = {
  hike: HIKE,
  trips: TRIPS,
  pois: [] as readonly StoredPoi[],
  units: 'imperial' as const,
  gpsMile: null,
  openTripId: null,
  onOpenTrip: vi.fn(),
  onPlanGap: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

/** The row for a piece, told apart from the ribbon band that names the same
 *  trip - the list is the rows, the ribbon is not in it. */
function row(text: RegExp | string) {
  const found = screen
    .getAllByRole('listitem')
    .find((item) =>
      typeof text === 'string'
        ? item.textContent?.includes(text)
        : text.test(item.textContent ?? ''),
    )
  if (found === undefined) throw new Error(`no row matching ${String(text)}`)
  return found
}

describe('the hike zoom', () => {
  it('lists trips and the gaps between them, in trail order', () => {
    render(<HikeZoom {...PROPS} />)

    const rows = screen.getAllByRole('listitem')
    // trip, gap, trip, gap: the hike starts where the first trip does and
    // runs on past the second, and the ground between them belongs to
    // neither.
    expect(rows).toHaveLength(4)
    expect(rows[0].textContent).toContain('Spring section')
    expect(rows[1].textContent).toContain('not walked')
    expect(rows[2].textContent).toContain('Grayson week')
    expect(rows[3].textContent).toContain('not walked')
  })

  it('names a gap by both of its ends, not only by its length', () => {
    // "30.0 mi not walked" is a number; "Stop 30 → Stop 60" is a piece of
    // trail somebody can decide about.
    render(<HikeZoom {...PROPS} />)

    expect(screen.getByText('30.0 mi not walked')).toBeInTheDocument()
    expect(screen.getByText(/Stop 30 → Stop 60/)).toBeInTheDocument()
  })

  it('shows the ground past the last trip as a gap too', () => {
    render(<HikeZoom {...PROPS} />)
    // 80 → Rockfish Gap at 100, and nothing pretends the hike ends early.
    expect(screen.getByText(/Stop 80 → Rockfish Gap/)).toBeInTheDocument()
  })

  it('offers to plan a gap, handing back the gap it was asked about', async () => {
    const user = userEvent.setup()
    render(<HikeZoom {...PROPS} />)

    await user.click(
      within(row(/Stop 30 → Stop 60/)).getByRole('button', { name: 'Plan this stretch' }),
    )
    expect(PROPS.onPlanGap).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: 'gap',
        span: { from: 30, to: 60 },
        // The ends as references, so the builder opens where the row said.
        from: { name: 'Stop 30', mile: 30 },
      }),
    )
  })

  it('says which trips are walked and which are only planned', () => {
    render(<HikeZoom {...PROPS} />)

    expect(screen.getByText('walked')).toBeInTheDocument()
    expect(screen.getByText('planned')).toBeInTheDocument()
  })

  it('makes a trip row as tall as its days', () => {
    // The day timeline's encoding one zoom out: a long summer reads long
    // before a single number has been read.
    render(<HikeZoom {...PROPS} />)

    const spring = within(row('Spring section')).getByRole('button')
    const grayson = within(row('Grayson week')).getByRole('button')
    expect(spring.style.height).toBe(`${tripRowHeight(3)}px`)
    expect(grayson.style.height).toBe(`${tripRowHeight(2)}px`)
  })

  it('gives a recorded stretch neither a day count nor a height off one', () => {
    // 470 miles remembered years later is not "1 day" and must not be drawn
    // as one either (#789).
    const recorded: Trip = {
      id: 'r',
      name: 'Springer → Damascus',
      recorded: true,
      plan: recordedPlan([
        { mile: 0, name: 'Springer', resupply: false },
        { mile: 90, name: 'Damascus', resupply: false },
      ]),
    }
    render(<HikeZoom {...PROPS} hike={{ ...HIKE, tripIds: ['r'] }} trips={[recorded]} />)

    const recordedRow = within(row('Springer → Damascus')).getByRole('button')
    expect(recordedRow.textContent).toContain('90.0 mi')
    expect(recordedRow.textContent).not.toMatch(/\bday\b/)
    expect(recordedRow.style.height).toBe(`${tripRowHeight(0)}px`)
  })

  it('opens a trip by tapping its row', async () => {
    const user = userEvent.setup()
    render(<HikeZoom {...PROPS} />)

    await user.click(within(row('Spring section')).getByRole('button'))
    expect(PROPS.onOpenTrip).toHaveBeenCalledWith('a')
  })

  it('says when the figures rest on a reference this download has lost', () => {
    render(<HikeZoom {...PROPS} hike={{ ...HIKE, start: { poiId: 'gone', mile: 0 } }} />)
    expect(
      screen.getByText(/points at a place this download doesn’t have/),
    ).toBeInTheDocument()
  })

  it('never turns a hike into a score', () => {
    const { container } = render(<HikeZoom {...PROPS} />)

    expect(container.textContent).not.toMatch(
      /%|behind|ahead of|on track|streak|complete/i,
    )
  })
})

describe('the ribbon above the rows', () => {
  it('draws a band for every piece, named in words', () => {
    // At roughly seven miles to the pixel the drawing alone is not
    // readable, and hatching says nothing to a screen reader.
    render(<HikeZoom {...PROPS} />)

    expect(
      screen.getByRole('button', { name: 'Spring section, walked' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Grayson week, planned' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Not walked: Stop 30 to Stop 60' }),
    ).toBeInTheDocument()
  })

  it('positions a band by where it sits in the hike', () => {
    render(<HikeZoom {...PROPS} />)

    const band = screen.getByRole('button', { name: 'Spring section, walked' })
    expect(band.style.left).toBe('0%')
    expect(band.style.width).toBe('30%')
  })

  it('scrubs the rows to a tapped band', async () => {
    const user = userEvent.setup()
    render(<HikeZoom {...PROPS} />)

    const band = screen.getByRole('button', { name: 'Grayson week, planned' })
    expect(band).toHaveAttribute('aria-pressed', 'false')

    await user.click(band)
    expect(band).toHaveAttribute('aria-pressed', 'true')
    // The row, not the band, is what the hiker then reads.
    expect(row('Grayson week')).toHaveClass('hike-zoom__row--picked')
  })

  it('says miles walked and miles left, and nothing that can be fallen behind', () => {
    render(<HikeZoom {...PROPS} />)

    // The planned trip closes no gap: 30 walked of 100.
    expect(screen.getByText('30.0 mi walked · 70.0 mi to go')).toBeInTheDocument()
  })

  it('marks where the hiker is, and only when they are inside this hike', () => {
    const { rerender } = render(<HikeZoom {...PROPS} gpsMile={50} />)
    expect(screen.getByRole('img', { name: 'Where you are' })).toBeInTheDocument()

    rerender(<HikeZoom {...PROPS} gpsMile={1400} />)
    expect(screen.queryByRole('img', { name: 'Where you are' })).toBeNull()
  })
})
