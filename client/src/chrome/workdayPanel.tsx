// The workday-pins feature, owned by one file instead of by App.tsx (#327).
//
// The volunteer workdays worth drawing on the map (#760), the tap that opens
// one, and the sheet over it. See chrome/atcNoticesPanel.tsx for why the hook
// returns a `Pick<MapScreenProps, …>` the shell spreads.

import { useMemo, useState } from 'react'
import type { MapScreenProps } from './MapScreen'
import { WorkdaySheet } from './WorkdaySheet'
import { opportunitiesUsable, upcomingWorkProjects } from '../lib/workProjects'
import type { WorkProjectSummary } from '../lib/workProjects'
import type { WorkdayPoint } from '../map/workdayLayers'

/** The `MapScreenProps` fields this feature owns. See atcNoticesPanel.tsx. */
export type WorkdayMapProps = Pick<
  MapScreenProps,
  'workdays' | 'onSelectWorkday' | 'workdaySheet'
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
  const pins = useMemo<readonly WorkdayPoint[]>(() => {
    if (projects === null || generatedAt === null) return []
    if (!opportunitiesUsable(generatedAt, now)) return []

    return upcomingWorkProjects(projects, now).flatMap((project) =>
      project.lat === null || project.lon === null
        ? []
        : [{ id: project.id, lat: project.lat, lon: project.lon }],
    )
  }, [projects, generatedAt, now])

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
    [pins, selected, gpsPlanMile],
  )

  return { mapScreen, sheetOpen: selectedId !== null }
}
