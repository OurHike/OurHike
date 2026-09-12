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
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from 'react'
import { mileMarker } from '../lib/planDisplay'
import type { MapPoint } from '../lib/legendContents'
import {
  WORKDAY_WINDOWS,
  type WorkdayRow,
  type WorkdayWindowId,
  workdayAwayLine,
} from '../lib/workProjects'
import '../screens/volunteer.css'
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
  /**
   * In the desktop's rail rather than a sheet over the map (#1374 review):
   * a region beside the canvas, wearing the persistent legend's frame, with
   * `head` - the rail's Legend / In view switch - where the title and close
   * would be. The phone's sheet was positioned against the whole window and
   * on a desktop covered the sidebar, the journal and the legend counting
   * the same points; docked, it is the legend rail's second face and the
   * map keeps every pixel it had.
   */
  docked?: boolean
  head?: ReactNode
  /**
   * Whether the map is drawing none of these pins at this zoom - the
   * corridor sketch below the pin floor (#1292), where the legend already
   * says "Waypoints appear from a closer zoom." The list still lists them,
   * so a hiker can read what the frame holds, but says so above the rows
   * rather than letting "In view" claim a pin nobody can see.
   */
  drawnNone?: boolean
  /**
   * The workdays in view (#1373, frame 14d), under the waypoints: the pinned
   * rows inside the viewport, the day window the pins are filtered to, and
   * the way to widen it. Undefined when the phone holds no workday in any
   * window, and then the section is absent rather than a heading over an
   * empty list. A row opens the pin's sheet, as a waypoint row opens its
   * card.
   */
  workdays?: {
    rows: readonly WorkdayRow[]
    window: WorkdayWindowId
    onChangeWindow: (window: WorkdayWindowId) => void
    onSelect: (id: string) => void
  }
}

function mileLabel(mile: number): string {
  return `mi ${mileMarker(mile)}`
}

/**
 * THE LIST IS WINDOWED (the maintainer's review of #1374, 2026-09-10).
 *
 * Measured on the preview at the opening camera with the default filters:
 * 5,736 rows; the pinned release publishes 29,848 waypoints in all. A row
 * is a button with a glyph, two lines and a border, and mounting thousands
 * of them on one tap is a second or two of jank on a phone and a list
 * nobody scrolls. The maintainer chose to keep every row and mount only the
 * ones on screen, so the rows are one fixed height and the list renders the
 * window the sheet is scrolled to, plus some overscan, between two spacers
 * that hold the rest's height.
 *
 * ONE HEIGHT PER ROW, in px, the same number the stylesheet pins the <li>
 * to (chrome.css `.in-view__rows > li`): a windowed list has to know where
 * row N sits without laying out rows 0..N-1. The row is PoiRow's 44 px
 * target plus its padding and border with the title and the meta each on
 * one line, which they were already made to be (poiRow.css ellipsises the
 * title; this stylesheet does the same to the meta here). Reasoned from
 * the row's own rules - 18 px title, 2 px gap, 17 px meta, 22 px padding,
 * 2 px border - rather than measured on a device: 61 px, and 62 leaves a
 * px for a theme's border. @unvalidated against a phone's larger type
 * settings - a row that grows past this clips its second line, which is
 * the failure to look for if it ever does.
 *
 * The scroller is the sheet or the rail itself (`.legend`, which scrolls on
 * both breakpoints), not the <ul>, so the workdays under the rows stay
 * reachable and the phone's one gesture keeps working. jsdom reports no
 * height at all, and a sheet not yet laid out reports none either; both
 * get a window sized as a phone screen would be, so a small list renders
 * whole and a test sees every row it made.
 */
export const IN_VIEW_ROW_PX = 62
const OVERSCAN_ROWS = 8
const VIEWPORT_FALLBACK_PX = 600

function rowsThatFit(viewport: number): number {
  return Math.ceil((viewport > 0 ? viewport : VIEWPORT_FALLBACK_PX) / IN_VIEW_ROW_PX)
}

function useWindowedRows(
  scroller: RefObject<HTMLElement | null>,
  list: RefObject<HTMLElement | null>,
  count: number,
): { first: number; last: number } {
  const [range, setRange] = useState(() => ({
    first: 0,
    last: Math.min(count, rowsThatFit(0) + OVERSCAN_ROWS),
  }))

  useEffect(() => {
    const element = scroller.current
    const measure = () => {
      const viewport = element?.clientHeight ?? 0
      const listTop =
        element === null || list.current === null
          ? 0
          : list.current.getBoundingClientRect().top -
            element.getBoundingClientRect().top +
            element.scrollTop
      const scrolled = Math.max(0, (element?.scrollTop ?? 0) - listTop)
      const topRow = Math.floor(scrolled / IN_VIEW_ROW_PX)
      const first = Math.max(0, topRow - OVERSCAN_ROWS)
      const last = Math.min(count, topRow + rowsThatFit(viewport) + OVERSCAN_ROWS)
      setRange((current) =>
        current.first === first && current.last === last ? current : { first, last },
      )
    }
    measure()
    element?.addEventListener('scroll', measure, { passive: true })
    const observer =
      typeof ResizeObserver === 'undefined' || element === null
        ? null
        : new ResizeObserver(measure)
    if (element !== null) observer?.observe(element)
    return () => {
      element?.removeEventListener('scroll', measure)
      observer?.disconnect()
    }
  }, [scroller, list, count])

  return range
}

export function InViewSheet(props: InViewSheetProps) {
  // Hooks live in the body, so the closed sheet can return before them.
  if (!props.open) return null
  return <InViewSheetBody {...props} />
}

function InViewSheetBody({
  points,
  total,
  currentMile = null,
  mileOf,
  stalenessFor,
  units,
  onSelectPoi,
  onClose,
  workdays,
  docked = false,
  head,
  drawnNone = false,
}: InViewSheetProps) {
  // Sorted once per viewport, not per render: thirty thousand rows sort in
  // tens of milliseconds, which is fine on a move and not on every tick.
  const rows = useMemo(
    () =>
      points
        .map((point) => ({ point, mile: mileOf?.(point.id) }))
        .sort((a, b) => {
          if (a.mile !== undefined && b.mile !== undefined) return a.mile - b.mile
          if (a.mile !== undefined) return -1
          if (b.mile !== undefined) return 1
          return (a.point.name ?? '').localeCompare(b.point.name ?? '')
        }),
    [points, mileOf],
  )
  const scrollerRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const { first, last } = useWindowedRows(scrollerRef, listRef, rows.length)

  const heading =
    total === undefined || total < points.length
      ? `In view · ${points.length}`
      : `In view · ${points.length} of ${total}`

  return (
    <div
      ref={scrollerRef}
      className={docked ? 'legend legend--persistent in-view' : 'legend in-view'}
      role={docked ? 'region' : 'dialog'}
      aria-label="In view"
    >
      {docked && head !== undefined ? (
        head
      ) : (
        <div className="legend__head">
          <h2 className="legend__title">{heading}</h2>
          {!docked && (
            <button type="button" className="legend__close" onClick={onClose}>
              <span className="visually-hidden">Close</span>
              <span aria-hidden="true">×</span>
            </button>
          )}
        </div>
      )}

      {rows.length === 0 ? (
        // The honest empty state names what to do next (the README's rule)
        // and never suggests signal - the pins are on the phone or nowhere.
        <p className="legend__empty">
          Nothing the map draws is in view. Zoom in, or pan to a stretch with waypoints.
        </p>
      ) : (
        <>
          {drawnNone && (
            <p className="legend__empty">
              The map draws none of these at this zoom &mdash; waypoints appear from a
              closer zoom.
            </p>
          )}
          <ul
            ref={listRef}
            className="in-view__rows"
            aria-label={`${rows.length} waypoints in view`}
          >
            {first > 0 && (
              <li
                className="in-view__spacer"
                aria-hidden="true"
                style={{ height: first * IN_VIEW_ROW_PX }}
              />
            )}
            {rows.slice(first, last).map(({ point, mile }, offset) => {
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
                <li
                  key={point.id}
                  aria-setsize={rows.length}
                  aria-posinset={first + offset + 1}
                >
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
            {last < rows.length && (
              <li
                className="in-view__spacer"
                aria-hidden="true"
                style={{ height: (rows.length - last) * IN_VIEW_ROW_PX }}
              />
            )}
          </ul>
        </>
      )}

      {workdays !== undefined && (
        <section className="in-view__workdays" aria-label="Workdays in view">
          <h3 className="legend__title">Workdays in view · {workdays.rows.length}</h3>
          {/* Three windows, real toggles (WhatsLeft's sort idiom): the
              fortnight the tab lists, the coming weekend, a month. */}
          <div className="in-view__windows" role="group" aria-label="Show workdays in">
            {WORKDAY_WINDOWS.map((option) => (
              <button
                key={option.id}
                type="button"
                className={
                  option.id === workdays.window
                    ? 'in-view__window in-view__window--on'
                    : 'in-view__window'
                }
                aria-pressed={option.id === workdays.window}
                onClick={() => workdays.onChangeWindow(option.id)}
              >
                {option.label}
              </button>
            ))}
          </div>
          {workdays.rows.length === 0 ? (
            <p className="legend__empty">
              No workdays in view in this window. Widen it, or pan to where a club is
              working.
            </p>
          ) : (
            <ul className="volunteer__workdays">
              {workdays.rows.map((row) => (
                <li key={row.id} className="volunteer__workday">
                  <button
                    type="button"
                    className="in-view__workday"
                    onClick={() => workdays.onSelect(row.id)}
                  >
                    <span className="volunteer__workday-title">{row.title}</span>
                    {/* The tab's own line, word for word: club, dates,
                        trail miles away only with a fix and a placed row,
                        room only where a cap was stated. */}
                    <span className="volunteer__workday-meta">
                      {[
                        row.club,
                        row.dates,
                        row.awayMi === null ? null : workdayAwayLine(row.awayMi),
                        row.capacity === null ? null : `room for ${row.capacity}`,
                      ]
                        .filter((part) => part !== null)
                        .join(' · ')}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  )
}
