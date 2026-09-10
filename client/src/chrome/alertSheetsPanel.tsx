// The two safety sheets the map drew marks for and never opened (#1373,
// F12; the inventory's P32): a tapped closure band and a tapped serious
// warning pin, each answered by the sheet built for it.
//
// #232 (PR #309) mounted the tape and the pins and explicitly left both
// sheets for the tap that would come (#245, #292); the tap never came, and
// test/reachability.test.ts carried the two files in its ledger of modules
// built before their door. This is the door. It is the one path in the
// review's four - "in front of something dangerous" - where a mark a hiker
// can see and cannot ask about is the failure: barrier tape with no answer
// invites the guess that the app knows a way round, and chrome/ClosureSheet.tsx
// exists to say it does not.
//
// THE PATTERN IS useNoticesPanel's, deliberately: state for which mark was
// tapped, the sheet rendered here where the data is, and a `mapScreen` bag
// spread into <MapScreen>, which draws the marks and does not know what a
// sheet is. One sheet at a time - a warning tapped over an open closure
// sheet replaces it, because two safety sheets stacked is two claims a hiker
// has to reconcile with a thumb.
//
// WHAT EACH SHEET IS HANDED, AND WHAT IT IS NOT. A closure's dates and
// reroute link are on the wire (#245) and optional on the published baseline
// a phone may be reading (lib/api.ts's ClosureSummary): absent reads as
// unknown, and the sheet omits the line rather than guessing (D13). A
// warning's mile is the one the pin was drawn at - `placeAll`'s snap of the
// report's fix, which is also what the "N warnings on your route" count
// walks - and its confirmation date is `verified_at`, stamped when a
// moderator escalated it; a warning the wire carries no date for prints the
// badge without one rather than a date nobody stamped.

import { useCallback, useMemo, useState, type ReactNode } from 'react'

import type { ClosureSummary, ReportSummary } from '../lib/api'
import type { WarningReport } from '../lib/seriousWarnings'
import { ClosureSheet } from './ClosureSheet'
import { SeriousWarningSheet } from './SeriousWarningSheet'

export interface AlertSheetsInput {
  /** Every closure the app holds, as placed (App's `placedClosures`). */
  closures: readonly ClosureSummary[] | null
  /** Every report the app holds - the serious ones are the pins. */
  reports: readonly ReportSummary[] | null
  /** The serious warnings as placed on the trail (lib/seriousWarnings.ts's
   *  `placeAll`), for the mile the pin was drawn at. */
  placedWarnings: readonly WarningReport[] | null
  lastSyncedAt: Date | null
  now: Date
  /** Called as a sheet opens, before it does: the shell closes the waypoint
   *  card and the legend there, so a tap on the tape after a tap on a pin
   *  leaves one thing up. */
  onOpen?: () => void
}

export interface AlertSheetsMapProps {
  onSelectClosure: (id: string) => void
  closureSheet: ReactNode
  onSelectWarning: (id: string) => void
  warningSheet: ReactNode
}

export interface AlertSheetsPanel {
  /** Spread into `<MapScreen>`. */
  mapScreen: AlertSheetsMapProps
  /** Whether either sheet is open - the shell's app-update guard reads it,
   *  as it reads the notices panel's. */
  sheetOpen: boolean
  /** Close whichever is open - what the shell calls when a waypoint card
   *  opens, so the lower third holds one answer at a time. */
  close: () => void
}

type Tapped = { kind: 'closure'; id: string } | { kind: 'warning'; id: string } | null

/** An ISO date as a Date, or null for absent, null or unreadable. */
function dateOf(iso: string | null | undefined): Date | null {
  if (iso === undefined || iso === null) return null
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? null : date
}

export function useAlertSheets({
  closures,
  reports,
  placedWarnings,
  lastSyncedAt,
  now,
  onOpen,
}: AlertSheetsInput): AlertSheetsPanel {
  const [tapped, setTapped] = useState<Tapped>(null)
  const close = useCallback(() => setTapped(null), [])
  const onSelectClosure = useCallback(
    (id: string) => {
      onOpen?.()
      setTapped({ kind: 'closure', id })
    },
    [onOpen],
  )
  const onSelectWarning = useCallback(
    (id: string) => {
      onOpen?.()
      setTapped({ kind: 'warning', id })
    },
    [onOpen],
  )

  const closureSheet = useMemo<ReactNode>(() => {
    if (tapped?.kind !== 'closure') return null
    const closure = closures?.find((candidate) => candidate.id === tapped.id)
    // A band whose closure the list no longer holds - reopened between the
    // draw and the tap - gets no sheet: nothing honest is left to say.
    if (closure === undefined) return null
    return (
      <ClosureSheet
        closure={{
          id: closure.id,
          reason_type: closure.reason_type,
          note: closure.note,
          status: closure.status,
          start_mile_marker: closure.start_mile_marker,
          end_mile_marker: closure.end_mile_marker,
          closed_since: dateOf(closure.closed_since),
          expected_reopen: dateOf(closure.expected_reopen),
          reroute_url: closure.reroute_url ?? null,
        }}
        lastSyncedAt={lastSyncedAt}
        now={now}
        onClose={close}
      />
    )
  }, [tapped, closures, lastSyncedAt, now, close])

  const warningSheet = useMemo<ReactNode>(() => {
    if (tapped?.kind !== 'warning') return null
    const report = reports?.find((candidate) => candidate.id === tapped.id)
    if (report === undefined) return null
    const placed = placedWarnings?.find((candidate) => candidate.id === tapped.id)
    return (
      <SeriousWarningSheet
        warning={{
          id: report.id,
          type: report.type,
          note: report.note ?? '',
          mile: placed?.mile ?? report.mile,
          confirmedAt: dateOf(report.verified_at),
        }}
        onClose={close}
      />
    )
  }, [tapped, reports, placedWarnings, close])

  const mapScreen = useMemo<AlertSheetsMapProps>(
    () => ({ onSelectClosure, closureSheet, onSelectWarning, warningSheet }),
    [onSelectClosure, closureSheet, onSelectWarning, warningSheet],
  )

  return {
    mapScreen,
    sheetOpen: closureSheet !== null || warningSheet !== null,
    close,
  }
}
