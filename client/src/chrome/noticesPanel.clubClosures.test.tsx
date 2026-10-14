// Which club closures the map crosses out, and the sheet a tap on one opens
// (the maintainer's S6, poll of 2026-10-11): every closure in
// conditions/trail_closures.json that closes the trail on the phone's own
// day - from the day before its own start - greyed in the list or not, and
// its own row of the planned-hike list in a sheet.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  act,
  cleanup,
  fireEvent,
  render,
  renderHook,
  screen,
  within,
} from '@testing-library/react'
import { useNoticesPanel } from './noticesPanel'
import { localDay } from '../lib/passedToday'
import { notCurrent } from '../lib/noticeCurrency'
import type { PublishedConditions, TrailClosure } from '../lib/publishedConditions'
import { validTrailClosure } from '../lib/publishedNotices'
import type { Stewards } from '../lib/stewards'
import { trailClosureRows } from '../../preview-shots/fixtures/clubClosures.mjs'

/** The middle of a day on the phone's own clock, so `localDay` is the same
 *  day in every zone the suite runs in. */
const NOW = new Date(2026, 9, 11, 12)

/** An invented steward for each invented source, so the sheet names it. */
const STEWARDS: Stewards = [
  ['ENF', 'Example National Forest', 'example_forest_closures'],
  ['ESP', 'Example State Parks', 'example_state_parks_status'],
  ['ETC', 'Example Trail Club', 'example_trail_club_alerts'],
  ['ECP', 'Example County Parks', 'example_county_parks_closures'],
].map(([provider, name, key]) => ({
  provider,
  name,
  trust: null,
  licence: null,
  attribution: null,
  terms: null,
  termsSource: null,
  layers: [],
  keys: [key],
  support: null,
  store: null,
}))

/** The ISO day `offset` days from NOW on the phone's own calendar. */
function day(offset: number): string {
  return localDay(new Date(NOW.getFullYear(), NOW.getMonth(), NOW.getDate() + offset, 12))
}

function read(row: unknown): TrailClosure {
  const closure = validTrailClosure(row)
  if (closure === null) throw new Error('the fixture row did not read')
  return closure
}

/** The hand-made file's five closures, and any more a test adds. */
function closureFile(...more: TrailClosure[]): PublishedConditions<TrailClosure> {
  return {
    generatedAt: new Date('2026-10-11T09:00:00Z'),
    items: [...Object.values(trailClosureRows()).map(read), ...more],
  }
}

/** A line closure whose own start is `offset` days from NOW. */
function startingIn(offset: number): TrailClosure {
  return read({
    ...trailClosureRows().line,
    notice_id: 'example_forest_closures:prescribed-burn',
    title: 'Example Ridge Trail prescribed burn (example)',
    starts_on: day(offset),
    ends_on: day(offset + 4),
    current_until: day(offset + 4),
  })
}

function panel(file: PublishedConditions<TrailClosure> | null, now = NOW) {
  return renderHook(
    ({ at }) =>
      useNoticesPanel({
        updates: [],
        orgNotices: [],
        reviewedAt: null,
        stewards: STEWARDS,
        trailIndex: null,
        bbox: { west: -101, south: 38, east: -100, north: 39 },
        now: at,
        closureFile: file,
      }),
    { initialProps: { at: now } },
  )
}

const drawnIds = (result: { current: ReturnType<typeof useNoticesPanel> }) =>
  (result.current.mapScreen.clubClosures ?? []).map((closure) => closure.notice_id)

// The fixture dates its closures around the browser's own today
// (preview-shots/fixtures/clubClosures.mjs), so the clock is NOW for it too:
// only `Date` is faked, and the timers testing-library waits on stay real.
beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(NOW)
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe('the club closures the map crosses out', () => {
  it('hands the map every closure in the file that closes the trail today, with no hike planned', () => {
    const { result } = panel(closureFile())
    expect(drawnIds(result)).toEqual(
      Object.values(trailClosureRows()).map((row) => row.notice_id),
    )
  })

  it('hands the map a closure the list greys exactly as any other, to draw at full strength', () => {
    // The maintainer's "B: same mark": the greyed row is in the list's grey
    // (notCurrent gives its line) and on the map like every other closure;
    // nothing about it reaches the map but its geometry and its id.
    const file = closureFile()
    const greyed = file.items[3]
    expect(notCurrent(greyed, day(0))?.line).toBe(
      'Its source gives no date. It may no longer apply.',
    )
    const { result } = panel(file)
    expect(result.current.mapScreen.clubClosures).toContain(greyed)
  })

  it('holds back a closure starting in 9 days, and draws it from the day before its own start', () => {
    // lib/noticeCurrency.ts's `obstructsOn`: never a day late, so from the
    // day before the start's UTC day, on the phone's own calendar.
    const upcoming = startingIn(9)
    const { result, rerender } = panel(closureFile(upcoming))
    expect(drawnIds(result)).not.toContain(upcoming.notice_id)

    rerender({ at: new Date(NOW.getFullYear(), NOW.getMonth(), NOW.getDate() + 7, 12) })
    expect(drawnIds(result)).not.toContain(upcoming.notice_id)

    rerender({ at: new Date(NOW.getFullYear(), NOW.getMonth(), NOW.getDate() + 8, 12) })
    expect(drawnIds(result)).toContain(upcoming.notice_id)
  })

  it('draws no club closure on a phone without the file, which is no answer rather than none', () => {
    const { result } = panel(null)
    expect(result.current.mapScreen.clubClosures).toEqual([])
    expect(result.current.mapScreen.clubClosureSheet).toBeNull()
  })
})

describe('the sheet a tap on a club closure opens', () => {
  it('opens the closure’s own row, greyed with its line where the list greys it, and closes again', async () => {
    const file = closureFile()
    const greyed = file.items[3]
    const { result } = panel(file)
    expect(result.current.sheetOpen).toBe(false)

    act(() => result.current.mapScreen.onSelectClubClosure?.(greyed.notice_id))
    expect(result.current.sheetOpen).toBe(true)
    const { rerender } = render(<>{result.current.mapScreen.clubClosureSheet}</>)

    // ClubClosureSheet arrives through import() (screens/deferred.ts).
    const sheet = await screen.findByRole(
      'dialog',
      { name: 'Closure notice' },
      { timeout: 5_000 },
    )
    const row = within(sheet).getByRole('listitem')
    expect(row).toHaveTextContent('Example Canyon Trail closed (example)')
    expect(row).toHaveTextContent('Example County Parks')
    expect(row).toHaveClass('notice--not-current')
    expect(
      within(row).getByText('Its source gives no date. It may no longer apply.'),
    ).toBeInTheDocument()

    fireEvent.click(within(sheet).getByRole('button', { name: 'Close' }))
    rerender(<>{result.current.mapScreen.clubClosureSheet}</>)
    expect(result.current.mapScreen.clubClosureSheet).toBeNull()
    expect(result.current.sheetOpen).toBe(false)
  })

  it('opens a closure in force with its Closure tag and its own dates, in full colour', async () => {
    const file = closureFile()
    const { result } = panel(file)
    act(() => result.current.mapScreen.onSelectClubClosure?.(file.items[0].notice_id))
    render(<>{result.current.mapScreen.clubClosureSheet}</>)

    const sheet = await screen.findByRole(
      'dialog',
      { name: 'Closure notice' },
      { timeout: 5_000 },
    )
    const row = within(sheet).getByRole('listitem')
    expect(row).not.toHaveClass('notice--not-current')
    expect(within(row).getByText('Closure')).toBeInTheDocument()
    expect(row).toHaveTextContent('Example Ridge Trail fire closure (example)')
    expect(row).toHaveTextContent('Example National Forest')
  })
})
