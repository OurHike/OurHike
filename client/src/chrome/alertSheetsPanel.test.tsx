// The closure tape's and the warning pin's sheets, opened from a tap
// (#1373, F12; the inventory's P32).

import { describe, expect, it } from 'vitest'
import { act, render, renderHook, screen } from '@testing-library/react'

import type { ClosureSummary, ReportSummary } from '../lib/api'
import { useAlertSheets, type AlertSheetsInput } from './alertSheetsPanel'

const CLOSURE: ClosureSummary = {
  id: 'c1',
  reason_type: 'storm_damage',
  note: 'Bridge is gone.',
  status: 'reroute_available',
  start_mile_marker: 1347.2,
  end_mile_marker: 1351.8,
  reported_at: '2026-08-12T00:00:00Z',
  verified_at: '2026-08-13T00:00:00Z',
  closed_since: '2026-08-12T00:00:00Z',
  expected_reopen: null,
  reroute_url: 'https://example.org/reroute',
}

const REPORT: ReportSummary = {
  id: 'r1',
  type: 'bad_hikers',
  reporter_type: 'thru',
  status: 'verified',
  severity: 'serious',
  lat: 41.2,
  lon: -74.5,
  mile: null,
  poi_id: null,
  note: 'Followed two hikers north after dark.',
  timestamp: '2026-08-29T00:00:00Z',
  verified_at: '2026-08-29T12:00:00Z',
}

const INPUT: AlertSheetsInput = {
  closures: [CLOSURE],
  reports: [REPORT],
  placedWarnings: [{ id: 'r1', type: 'bad_hikers', severity: 'serious', mile: 1382.4 }],
  lastSyncedAt: new Date('2026-09-07T12:00:00Z'),
  now: new Date('2026-09-10T12:00:00Z'),
}

describe('a tapped closure', () => {
  it('opens the closure sheet with the dates the wire carries, and the sync age', () => {
    const { result } = renderHook(() => useAlertSheets(INPUT))
    expect(result.current.sheetOpen).toBe(false)

    act(() => result.current.mapScreen.onSelectClosure('c1'))
    expect(result.current.sheetOpen).toBe(true)
    render(<>{result.current.mapScreen.closureSheet}</>)

    expect(screen.getByRole('dialog', { name: /closure/i })).toBeInTheDocument()
    expect(screen.getByText('Storm damage')).toBeInTheDocument()
    expect(screen.getByText(/Closed since August 12/)).toBeInTheDocument()
    // Expected reopening is omitted rather than guessed (D13).
    expect(screen.queryByText(/Expected to reopen/)).toBeNull()
    expect(screen.getByText(/Your copy of this closure is 3d ago/)).toBeInTheDocument()
  })

  it('opens nothing for a band whose closure the list no longer holds', () => {
    const { result } = renderHook(() => useAlertSheets(INPUT))
    act(() => result.current.mapScreen.onSelectClosure('gone'))
    expect(result.current.mapScreen.closureSheet).toBeNull()
    expect(result.current.sheetOpen).toBe(false)
  })
})

describe('a tapped warning', () => {
  it('opens the warning sheet at the mile the pin was drawn, dated by the moderator', () => {
    const { result } = renderHook(() => useAlertSheets(INPUT))
    act(() => result.current.mapScreen.onSelectWarning('r1'))
    render(<>{result.current.mapScreen.warningSheet}</>)

    expect(screen.getByRole('dialog', { name: 'Serious warning' })).toBeInTheDocument()
    expect(
      screen.getByText(/Confirmed by club moderators · August 29/),
    ).toBeInTheDocument()
    expect(screen.getByText('mi 1,382.4')).toBeInTheDocument()
    expect(screen.getByText(/Followed two hikers/)).toBeInTheDocument()
  })

  it('shows one sheet at a time - the newer tap replaces the older', () => {
    const { result } = renderHook(() => useAlertSheets(INPUT))
    act(() => result.current.mapScreen.onSelectClosure('c1'))
    act(() => result.current.mapScreen.onSelectWarning('r1'))
    expect(result.current.mapScreen.closureSheet).toBeNull()
    expect(result.current.mapScreen.warningSheet).not.toBeNull()
  })
})
