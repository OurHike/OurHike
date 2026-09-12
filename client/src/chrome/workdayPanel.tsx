// The workday-pins feature, owned by one file instead of by App.tsx (#327).
//
// The volunteer workdays worth drawing on the map (#760), the tap that opens
// one, and the sheet over it. See chrome/atcNoticesPanel.tsx for why the hook
// returns a `Pick<MapScreenProps, …>` the shell spreads.

import { useMemo, useState } from 'react'
import type { MapScreenProps } from './MapScreen'
import { WorkdaySheet } from './WorkdaySheet'
import {
  opportunitiesUsable,
  upcomingWorkProjects,
  workdayRow,
  type WorkdayRow,
  type WorkdayWindowId,
} from '../lib/workProjects'
import type { WorkProjectSummary } from '../lib/workProjects'
import type { WorkdayPoint } from '../map/workdayLayers'

/** The `MapScreenProps` fields this feature owns. See atcNoticesPanel.tsx. */
export type WorkdayMapProps = Pick<
  MapScreenProps,
  | 'workdays'
  | 'onSelectWorkday'
  | 'workdaySheet'
  | 'workdayRows'
  | 'workdaysHeld'
  | 'workdayWindow'
  | 'onChangeWorkdayWindow'
>

export interface WorkdayPanel {
  /** Spread into `<MapScreen>`. */
  mapScreen: WorkdayMapProps
  /** Whether the tapped-workday sheet is open - see AtcNoticesPanel.sheetOpen
   *  for why this is returned beside the props rather than among them. */
  sheetOpen: boolean
}

export interface WorkdayInput {
  /** The reviewed opportunities file, or null while it has not been read. */
  projects: readonly WorkProjectSummary[] | null
  /** When that file was generated, or null - the staleness gate's input. */
  generatedAt: Date | null
  now: Date
  /** The hiker's own mile on the planner's axis, or null. */
  gpsPlanMile: number | null
}

export function useWorkdayPanel({
  projects,
  generatedAt,
  now,
  gpsPlanMile,
}: WorkdayInput): WorkdayPanel {
  /** The workday pin a hiker tapped, or null (#760). Held by id rather than
   *  by row, so a re-fetch that drops a cancelled workday closes the sheet
   *  over it instead of leaving a stale invitation open. */
  const [selectedId, setSelectedId] = useState<string | null>(null)
  /**
   * The day window the pins and the map's list are filtered to (#1373,
   * frame 14d). The tab keeps its own fortnight; this is the map's, and it
   * starts on the same number so the two agree until a hiker asks
   * otherwise. Session state rather than a preference: which weekend a
   * hiker is looking at is not a setting.
   */
  const [window, setWindow] = useState<WorkdayWindowId>('fortnight')

  /**
   * The workdays worth drawing (#760), and the two gates in front of them.
   *
   * **Staleness first, and it is absolute.** Past `OPPORTUNITIES_STALE_MS`
   * the Volunteer tab replaces its list with an out-of-date notice rather
   * than decorating it, because "a hedged invitation still reads as an
   * invitation" - and a pin has no hedged form at all. So a stale feed draws
   * no pins, and the tab is where a hiker is told why in words.
   *
   * **Then the fourteen-day window**, the same `upcomingWorkProjects` the
   * tab lists, so the two surfaces cannot disagree about which workdays are
   * on. A row the reviewed file never placed has no coordinates and simply
   * is not drawn - a workday pinned at 0,0 would be a real place in the
   * Atlantic, which is the failure `describeLocation` already refuses on the
   * report form.
   */
  const usable =
    projects !== null && generatedAt !== null && opportunitiesUsable(generatedAt, now)
  /** The workdays in the window, once - the pins, the rows and the count
   *  below are three readings of this one list, not three passes. */
  const upcoming = useMemo<readonly WorkProjectSummary[]>(
    () => (usable ? upcomingWorkProjects(projects, now, window) : []),
    [usable, projects, now, window],
  )
  /** The pinned workdays as the map's list prints them (#1373, frame 14d):
   *  `workdayRow` is null exactly where a row has no coordinates, so the
   *  pins are the rows with their words dropped. */
  const rows = useMemo<readonly WorkdayRow[]>(
    () =>
      upcoming.flatMap((project) => {
        const row = workdayRow(project, gpsPlanMile)
        return row === null ? [] : [row]
      }),
    [upcoming, gpsPlanMile],
  )
  const pins = useMemo<readonly WorkdayPoint[]>(
    () => rows.map(({ id, lat, lon }) => ({ id, lat, lon })),
    [rows],
  )
  /** How many the widest window holds - the list is offered while any
   *  exist, so a hiker can widen the window to find them. */
  const held = useMemo(
    () =>
      usable
        ? upcomingWorkProjects(projects, now, 'month').filter(
            (project) => project.lat !== null && project.lon !== null,
          ).length
        : 0,
    [usable, projects, now],
  )

  /** The tapped workday itself, re-read from the live list every render: if a
   *  re-fetch drops it - cancelled, or out of the window - this goes null and
   *  the sheet closes rather than standing over a workday nobody is running. */
  const selected = useMemo(() => {
    if (selectedId === null || projects === null) return null
    return (
      projects.find(
        (project) =>
          project.id === selectedId && pins.some((pin) => pin.id === selectedId),
      ) ?? null
    )
  }, [selectedId, projects, pins])

  const mapScreen = useMemo<WorkdayMapProps>(
    () => ({
      workdays: pins,
      onSelectWorkday: setSelectedId,
      workdayRows: rows,
      workdaysHeld: held,
      workdayWindow: window,
      onChangeWorkdayWindow: setWindow,
      workdaySheet:
        selected === null ? null : (
          <WorkdaySheet
            project={selected}
            // The hiker's own mile on the planner's axis, which is the
            // one the tab's "trail mi away" already uses - two surfaces
            // measuring the same distance two ways is a hiker reading
            // two claims where there is one.
            gpsMile={gpsPlanMile}
            onClose={() => setSelectedId(null)}
          />
        ),
    }),
    [pins, selected, gpsPlanMile, rows, held, window],
  )

  return { mapScreen, sheetOpen: selectedId !== null }
}
