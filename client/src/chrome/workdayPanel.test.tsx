import { describe, it, expect, afterEach } from 'vitest'
import { act, cleanup, renderHook } from '@testing-library/react'
import { useWorkdayPanel } from './workdayPanel'
import { OPPORTUNITIES_STALE_MS, type WorkProjectSummary } from '../lib/workProjects'

// #327 moved this feature out of App.tsx whole. What is tested here is the
// panel's own two decisions - which workdays get a pin, and what happens to
// an open sheet when the list underneath it changes. The window and staleness
// rules themselves belong to lib/workProjects.ts and are tested there.

const NOW = new Date('2026-08-13T12:00:00.000Z')
const FRESH = new Date(NOW.getTime() - 60 * 60 * 1000)

function project(overrides: Partial<WorkProjectSummary> = {}): WorkProjectSummary {
  return {
    id: 'nynjtc-bear-mountain-2026-08-15',
    club_name: 'New York–New Jersey Trail Conference',
    title: 'Bear Mountain stonework',
    description: null,
    lat: 41.312,
    lon: -73.988,
    mile: 1408.6,
    starts_on: '2026-08-15',
    ends_on: '2026-08-15',
    status: 'upcoming',
    capacity: null,
    signup_mode: 'contact',
    signup_contact: 'trails@nynjtc.org',
    ...overrides,
  }
}

function panel(
  projects: readonly WorkProjectSummary[] | null,
  generatedAt: Date | null = FRESH,
) {
  return renderHook(
    ({ rows }: { rows: readonly WorkProjectSummary[] | null }) =>
      useWorkdayPanel({ projects: rows, generatedAt, now: NOW, gpsPlanMile: null }),
    { initialProps: { rows: projects } },
  )
}

afterEach(cleanup)

describe('useWorkdayPanel', () => {
  it('pins an upcoming workday that the reviewed file placed', () => {
    const { result } = panel([project()])

    expect(result.current.mapScreen.workdays).toEqual([
      { id: 'nynjtc-bear-mountain-2026-08-15', lat: 41.312, lon: -73.988 },
    ])
  })

  it('draws nothing at all from a stale feed', () => {
    // Absolute, and the reason is in the module: the Volunteer tab can say
    // "this list is out of date" in words, and a pin has no hedged form. A
    // stale invitation drawn on the map still reads as an invitation.
    const stale = new Date(NOW.getTime() - OPPORTUNITIES_STALE_MS - 1)
    const { result } = panel([project()], stale)

    expect(result.current.mapScreen.workdays).toEqual([])
  })

  it('draws nothing before the file has been read', () => {
    const { result } = panel(null, null)

    expect(result.current.mapScreen.workdays).toEqual([])
  })

  it('leaves an unplaced workday off the map rather than at 0,0', () => {
    const { result } = panel([project({ lat: null, lon: null })])

    expect(result.current.mapScreen.workdays).toEqual([])
  })

  it('closes the sheet when a re-fetch drops the workday it was over', () => {
    // The failure this prevents: a cancelled workday leaves the list, and a
    // sheet still standing over it goes on inviting somebody to a workday
    // nobody is running.
    const { result, rerender } = panel([project()])

    act(() =>
      result.current.mapScreen.onSelectWorkday?.('nynjtc-bear-mountain-2026-08-15'),
    )
    expect(result.current.mapScreen.workdaySheet).not.toBeNull()
    expect(result.current.sheetOpen).toBe(true)

    rerender({ rows: [] })

    expect(result.current.mapScreen.workdaySheet).toBeNull()
  })

  it('draws no sheet for a workday that has no pin', () => {
    // The two are read together on purpose. A row the window still holds but
    // the map never placed has nothing to have been tapped, so a sheet over
    // it could only have come from a stale id.
    const { result } = panel([project({ lat: null, lon: null })])

    act(() =>
      result.current.mapScreen.onSelectWorkday?.('nynjtc-bear-mountain-2026-08-15'),
    )

    expect(result.current.mapScreen.workdaySheet).toBeNull()
  })
})
