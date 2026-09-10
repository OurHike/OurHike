// In view (#1373, frame 12a): what the map is drawing right now, as a list
// a hiker can scroll rather than a field of pins to hunt through.
//
// THE SAME LIST THE LEGEND COUNTS. `Legend` takes the viewport's points to
// say "Water · 4"; this takes the same points and names them, one PoiRow per
// waypoint - the map's own pin at row scale, so the shape a hiker learned on
// the map is the shape in the list, and a tap opens the same card a pin does.
//
// ORDERED BY THE TRAIL where the trail can order it: a waypoint with a mile
// sits in mile order and one without sits after them by name, so the list
// reads like the trail does and never invents an order for a point the
// download cannot place. "N away" is printed only where the hiker's own mile
// AND the waypoint's are known - a trail distance, never a straight line
// dressed as one - and the staleness words ride only where the pixels do
// (lib/stalenessDisplay.ts), exactly as the rail's do.
//
// THE HEIGHT IS NOT THE HIKER'S TO SET, though the frame says so: no sheet
// in this app drags (every one is a max-height cap, and a drag handle would
// be a fifth grammar for one gesture), so this one caps like the legend and
// scrolls inside. Said here rather than left as a difference somebody has
// to notice.

import { formatDistance, type UnitSystem } from '../lib/units'
import type { MapPoint } from '../lib/legendContents'
import type { StalenessTreatment } from '../lib/stalenessDisplay'
import { typeLabel } from './legendLabels'
import { PoiRow } from './PoiRow'

export interface InViewSheetProps {
  open: boolean
  /** Every waypoint the map is drawing in the viewport - the legend's own
   *  input, so the two agree about what "in view" means. */
  points: readonly MapPoint[]
  /** How many waypoints the phone holds in all, for "6 of 23". Omitted
   *  where the shell does not say, and then the heading counts only what
   *  is in view. */
  total?: number
  /** The hiker's own mile on the centerline, or null. */
  currentMile?: number | null
  /** A waypoint's mile on the same axis, or undefined where the download
   *  cannot place it. */
  mileOf?: (poiId: string) => number | undefined
  stalenessFor?: (
    poiId: string,
    poiType: string,
  ) => { treatment: StalenessTreatment; words: string } | null
  units: UnitSystem
  onSelectPoi: (id: string) => void
  onClose: () => void
}

function mileLabel(mile: number): string {
  return `mi ${mile.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}`
}

export function InViewSheet({
  open,
  points,
  total,
  currentMile = null,
  mileOf,
  stalenessFor,
  units,
  onSelectPoi,
  onClose,
}: InViewSheetProps) {
  if (!open) return null

  const rows = points
    .map((point) => ({ point, mile: mileOf?.(point.id) }))
    .sort((a, b) => {
      if (a.mile !== undefined && b.mile !== undefined) return a.mile - b.mile
      if (a.mile !== undefined) return -1
      if (b.mile !== undefined) return 1
      return (a.point.name ?? '').localeCompare(b.point.name ?? '')
    })

  const heading =
    total === undefined || total < points.length
      ? `In view · ${points.length}`
      : `In view · ${points.length} of ${total}`

  return (
    <div className="legend in-view" role="dialog" aria-label="In view">
      <div className="legend__head">
        <h2 className="legend__title">{heading}</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      {rows.length === 0 ? (
        // The honest empty state names what to do next (the README's rule)
        // and never suggests signal - the pins are on the phone or nowhere.
        <p className="legend__empty">
          Nothing the map draws is in view. Zoom in, or pan to a stretch with waypoints.
        </p>
      ) : (
        <ul className="in-view__rows">
          {rows.map(({ point, mile }) => {
            const staleness = stalenessFor?.(point.id, point.type) ?? null
            const meta = [
              typeLabel(point.type).toLowerCase(),
              mile === undefined ? null : mileLabel(mile),
              mile !== undefined && currentMile !== null
                ? `${formatDistance(Math.abs(mile - currentMile), units)} away`
                : null,
              staleness?.words ?? null,
            ]
              .filter((part) => part !== null && part !== '')
              .join(' · ')
            return (
              <li key={point.id}>
                <PoiRow
                  kind={point.type}
                  title={point.name ?? typeLabel(point.type)}
                  meta={meta}
                  confidence={point.confidence}
                  onOpen={() => onSelectPoi(point.id)}
                />
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
