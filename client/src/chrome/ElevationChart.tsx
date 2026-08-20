// The full elevation chart the desktop has room for (#135, WEBSITE.md §6).
//
// NOT the ribbon grown taller, and the difference is who it answers. The
// ribbon answers the field question - "what is ahead of ME" - so it needs a
// GPS fix and shows ten miles around it. A desk has no fix: this chart
// answers "what is this stretch of trail LIKE", so its resting view is the
// whole published profile and a fix is an optional extra (the you-are-here
// rule appears when one exists, on the profile's own axis).
//
// Interactions, and where each number comes from:
//   hover   the nearest sample's mile and elevation (lib/chartProfile.ts),
//           reported upward so the screen can put a dot on the map.
//   drag    selects a stretch. Distance shows live; gain, loss and the
//           ≈time appear when the drag settles, all from lib/route.ts's
//           legFigures - the route builder's own arithmetic, so this chart
//           and a route over the same miles can never disagree.
//   zoom    narrows the domain to the selection. Decimation is
//           lib/chartProfile.ts's min-max envelope, so a summit or a notch
//           survives at every zoom.
//
// Direction: gain and loss are direction-aware, and this surface has no fix
// to infer a direction from - so it states one. Figures read northbound
// until the toggle says otherwise, and the toggle re-walks the window
// through legFigures (reverse-then-count, never a swap of the two totals -
// see lib/elevationGain.ts's reverseProfileWindow for why those differ).
//
// The time is Naismith moving time: rounded to 5 minutes, prefixed ≈, never
// an arrival clock, no descent credit - WIREFRAMES.md's load-bearing values,
// unchanged up here. "walking" is appended so a desk reader is told it is
// moving time, per HIKE_PLANNING.md Finding 4's honesty requirement.

import { useCallback, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent, PointerEvent as ReactPointerEvent } from 'react'
import type { ElevationProfile } from '../lib/elevationProfile'
import {
  clampDomain,
  envelopeSamples,
  fullDomain,
  nearestMile,
  sampleAtMile,
  tickStep,
  ticks,
  type ChartDomain,
} from '../lib/chartProfile'
import { legFigures } from '../lib/route'
import { formatNaismithMinutes } from '../lib/naismith'
import { formatDistance, formatElevation, type UnitSystem } from '../lib/units'

const VIEW_W = 1000
const VIEW_H = 100

/** How far a pointer must travel, as a fraction of the chart's width, before
 *  a press reads as a drag rather than a click. Clicks clear the selection. */
const DRAG_THRESHOLD = 0.004

/** Zoom keeps this much slack either side of the selection, so the selected
 *  stretch reads in its surroundings rather than wall to wall. */
const ZOOM_PADDING = 0.08

/** One arrow-key step, as a fraction of the domain. */
const KEY_STEP = 0.01

export interface ChartStretch {
  startMile: number
  endMile: number
}

export interface ElevationChartProps {
  profile: ElevationProfile
  /** Where the hiker is on the PROFILE's axis, or null with no fix - which
   *  is the normal desktop state and costs only the you-are-here rule. */
  currentMile?: number | null
  units?: UnitSystem
  /** The hovered mile (profile axis), or null when the pointer leaves - for
   *  the dot on the map. */
  onHoverMile?: (mile: number | null) => void
  /** A settled selection (low mile first), or null when cleared - for the
   *  banded stretch on the map. */
  onSelectStretch?: (stretch: ChartStretch | null) => void
}

/** A mile POSITION, printed the way the position line, PoiCard and the
 *  detail sheets print one - "mi 705.6", en-US grouping, one decimal,
 *  whatever the units preference. Positions are identities on the trail's
 *  own axis; only lengths and heights convert. */
function formatMileMarker(mile: number): string {
  return mile.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
}

/** Axis ticks drop the forced decimal where the step is whole miles. */
function formatTick(mile: number, step: number): string {
  if (step >= 1) return mile.toLocaleString('en-US', { maximumFractionDigits: 0 })
  return formatMileMarker(mile)
}

interface DragState {
  anchorMile: number
  moved: boolean
}

export function ElevationChart({
  profile,
  currentMile = null,
  units = 'imperial',
  onHoverMile,
  onSelectStretch,
}: ElevationChartProps) {
  const [zoom, setZoom] = useState<ChartDomain | null>(null)
  const [hoverMile, setHoverMile] = useState<number | null>(null)
  const [liveSelection, setLiveSelection] = useState<ChartStretch | null>(null)
  const [settledSelection, setSettledSelection] = useState<ChartStretch | null>(null)
  const [southbound, setSouthbound] = useState(false)
  const dragRef = useRef<DragState | null>(null)
  const plotRef = useRef<HTMLDivElement | null>(null)

  const domain = useMemo(() => {
    if (zoom !== null) return zoom
    return fullDomain(profile)
  }, [zoom, profile])

  const drawn = useMemo(() => {
    if (domain === null) return null
    const samples = envelopeSamples(profile, domain)
    if (samples.length < 2) return null

    let minFt = Infinity
    let maxFt = -Infinity
    for (const s of samples) {
      if (s.elevationFt < minFt) minFt = s.elevationFt
      if (s.elevationFt > maxFt) maxFt = s.elevationFt
    }
    // A flat domain would divide by zero exactly as the ribbon's would; the
    // same flat-line-down-the-middle answer.
    const range = maxFt - minFt
    const span = domain.endMile - domain.startMile
    const xFor = (mile: number) => ((mile - domain.startMile) / span) * VIEW_W
    const yFor = (ft: number) =>
      range === 0 ? VIEW_H / 2 : VIEW_H - ((ft - minFt) / range) * VIEW_H

    const line = samples
      .map(
        (s, i) =>
          `${i === 0 ? 'M' : 'L'}${xFor(s.mile).toFixed(2)},${yFor(s.elevationFt).toFixed(2)}`,
      )
      .join(' ')

    const mileStep = tickStep(span)
    const ftStep = tickStep(range * 1.4)

    return {
      line,
      area: `${line} L${VIEW_W},${VIEW_H} L0,${VIEW_H} Z`,
      minFt,
      maxFt,
      span,
      xFor,
      yFor,
      mileStep,
      mileTicks: ticks(domain.startMile, domain.endMile, mileStep),
      ftTicks: ticks(minFt, maxFt, ftStep).filter(
        // A gridline through the very floor or ceiling doubles the frame.
        (ft) => ft > minFt + range * 0.04 && ft < maxFt - range * 0.04,
      ),
    }
  }, [profile, domain])

  const pctFor = useCallback(
    (mile: number) => {
      if (domain === null) return 0
      return ((mile - domain.startMile) / (domain.endMile - domain.startMile)) * 100
    },
    [domain],
  )

  const mileForClientX = useCallback(
    (clientX: number): number | null => {
      const plot = plotRef.current
      if (plot === null || domain === null) return null
      const rect = plot.getBoundingClientRect()
      if (rect.width === 0) return null
      const frac = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width))
      return domain.startMile + frac * (domain.endMile - domain.startMile)
    },
    [domain],
  )

  const reportHover = useCallback(
    (mile: number | null) => {
      setHoverMile(mile)
      onHoverMile?.(mile)
    },
    [onHoverMile],
  )

  const settleSelection = useCallback(
    (stretch: ChartStretch | null) => {
      // Settled endpoints snap to the profile's own samples, so the range
      // the figures row PRINTS is exactly the range legFigures MEASURES -
      // see lib/chartProfile.ts's nearestMile for the failure this closes.
      // The live drag stays unsnapped; only the claim gets the treatment.
      const snapped =
        stretch === null
          ? null
          : {
              startMile: nearestMile(profile, stretch.startMile) ?? stretch.startMile,
              endMile: nearestMile(profile, stretch.endMile) ?? stretch.endMile,
            }
      setLiveSelection(snapped)
      setSettledSelection(snapped)
      onSelectStretch?.(snapped)
    },
    [onSelectStretch, profile],
  )

  const handlePointerDown = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const mile = mileForClientX(event.clientX)
      if (mile === null) return
      dragRef.current = { anchorMile: mile, moved: false }
      try {
        // Without capture, a drag that leaves the element stops updating -
        // livable, which is why jsdom's absent/throwing implementation is
        // swallowed rather than guarded around.
        event.currentTarget.setPointerCapture?.(event.pointerId)
      } catch {
        /* jsdom */
      }
    },
    [mileForClientX],
  )

  const handlePointerMove = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const mile = mileForClientX(event.clientX)
      if (mile === null) return
      reportHover(mile)

      const drag = dragRef.current
      if (drag === null || domain === null) return
      const spanMoved =
        Math.abs(mile - drag.anchorMile) / (domain.endMile - domain.startMile)
      if (!drag.moved && spanMoved < DRAG_THRESHOLD) return
      drag.moved = true
      setLiveSelection({
        startMile: Math.min(drag.anchorMile, mile),
        endMile: Math.max(drag.anchorMile, mile),
      })
    },
    [mileForClientX, reportHover, domain],
  )

  const handlePointerUp = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const drag = dragRef.current
      dragRef.current = null
      if (drag === null) return
      if (!drag.moved) {
        // A press that never travelled is a click, and a click clears.
        settleSelection(null)
        return
      }
      const mile = mileForClientX(event.clientX)
      const end = mile ?? drag.anchorMile
      settleSelection({
        startMile: Math.min(drag.anchorMile, end),
        endMile: Math.max(drag.anchorMile, end),
      })
    },
    [mileForClientX, settleSelection],
  )

  const handlePointerLeave = useCallback(() => {
    if (dragRef.current === null) reportHover(null)
  }, [reportHover])

  const zoomToSelection = useCallback(() => {
    const stretch = settledSelection
    if (stretch === null) return
    const pad = (stretch.endMile - stretch.startMile) * ZOOM_PADDING
    setZoom(
      clampDomain(
        { startMile: stretch.startMile - pad, endMile: stretch.endMile + pad },
        profile,
      ),
    )
  }, [settledSelection, profile])

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>) => {
      if (domain === null) return
      const span = domain.endMile - domain.startMile
      const step = span * KEY_STEP

      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault()
        const delta = event.key === 'ArrowLeft' ? -step : step
        const from = hoverMile ?? (domain.startMile + domain.endMile) / 2
        const next = Math.min(domain.endMile, Math.max(domain.startMile, from + delta))
        if (event.shiftKey) {
          const anchor =
            settledSelection === null
              ? from
              : // Extend from whichever end the cursor is NOT at.
                Math.abs(settledSelection.startMile - from) <
                  Math.abs(settledSelection.endMile - from)
                ? settledSelection.endMile
                : settledSelection.startMile
          settleSelection({
            startMile: Math.min(anchor, next),
            endMile: Math.max(anchor, next),
          })
        }
        reportHover(next)
        return
      }
      if (event.key === 'Home' || event.key === 'End') {
        event.preventDefault()
        reportHover(event.key === 'Home' ? domain.startMile : domain.endMile)
        return
      }
      if (event.key === 'Enter' && settledSelection !== null) {
        event.preventDefault()
        zoomToSelection()
        return
      }
      if (event.key === 'Escape') {
        if (settledSelection !== null) {
          event.preventDefault()
          settleSelection(null)
        } else if (zoom !== null) {
          event.preventDefault()
          setZoom(null)
        }
      }
    },
    [
      domain,
      hoverMile,
      settledSelection,
      settleSelection,
      reportHover,
      zoomToSelection,
      zoom,
    ],
  )

  // Figures come from the SETTLED selection only. legFigures walks every
  // sample in the window, which is the whole point (gaps and seams break the
  // runs) and also why it must not run per pointermove across a
  // thousand-mile drag - distance is the one number cheap enough to live.
  const figures = useMemo(() => {
    if (settledSelection === null) return null
    const { startMile, endMile } = settledSelection
    return southbound
      ? legFigures(profile, endMile, startMile)
      : legFigures(profile, startMile, endMile)
  }, [settledSelection, southbound, profile])

  if (domain === null || drawn === null) return null

  const selection = liveSelection
  const hoverSample = hoverMile === null ? null : sampleAtMile(profile, hoverMile)
  const hoverPct = hoverMile === null ? null : pctFor(hoverMile)
  const herePct =
    currentMile !== null &&
    currentMile >= domain.startMile &&
    currentMile <= domain.endMile
      ? pctFor(currentMile)
      : null

  return (
    <div className="elevation-chart" data-testid="elevation-chart">
      <div className="elevation-chart__figures" aria-live="polite">
        {selection === null ? (
          <>
            <span className="elevation-chart__mono elevation-chart__figure--strong">
              mi {formatMileMarker(domain.startMile)} – {formatMileMarker(domain.endMile)}
            </span>
            <span className="elevation-chart__mono">
              {formatDistance(domain.endMile - domain.startMile, units)}
            </span>
            <span className="elevation-chart__hint">Drag to measure a stretch</span>
          </>
        ) : (
          <>
            <span className="elevation-chart__mono elevation-chart__figure--strong">
              mi {formatMileMarker(selection.startMile)} –{' '}
              {formatMileMarker(selection.endMile)}
            </span>
            <span className="elevation-chart__mono">
              {formatDistance(selection.endMile - selection.startMile, units)}
            </span>
            {figures !== null && liveSelection === settledSelection && (
              <>
                <span className="elevation-chart__mono">
                  ↑ {formatElevation(figures.ascentFt, units)}
                </span>
                <span className="elevation-chart__mono">
                  ↓ {formatElevation(figures.descentFt, units)}
                </span>
                <span className="elevation-chart__mono elevation-chart__figure--strong">
                  {formatNaismithMinutes(figures.minutes)} walking
                </span>
                <button
                  type="button"
                  className="elevation-chart__control"
                  onClick={() => setSouthbound((was) => !was)}
                  aria-label={`Figures read ${southbound ? 'southbound' : 'northbound'}; switch direction`}
                >
                  <svg
                    width="12"
                    height="12"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    aria-hidden="true"
                  >
                    <path d="M7 8h13m0 0-3.5-3.5M20 8l-3.5 3.5M17 16H4m0 0 3.5-3.5M4 16l3.5 3.5" />
                  </svg>
                  {southbound ? 'southbound' : 'northbound'}
                </button>
              </>
            )}
          </>
        )}
        <span className="elevation-chart__spacer" />
        {settledSelection !== null && (
          <>
            <button
              type="button"
              className="elevation-chart__control elevation-chart__control--primary"
              onClick={zoomToSelection}
            >
              Zoom to stretch
            </button>
            <button
              type="button"
              className="elevation-chart__control"
              onClick={() => settleSelection(null)}
            >
              Clear
            </button>
          </>
        )}
        {zoom !== null && (
          <button
            type="button"
            className="elevation-chart__control"
            onClick={() => setZoom(null)}
          >
            Whole trail
          </button>
        )}
      </div>

      <div
        ref={plotRef}
        className="elevation-chart__plot"
        role="application"
        aria-label="Elevation profile. Arrow keys move the cursor, Shift extends a selection, Enter zooms to it, Escape clears."
        tabIndex={0}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerLeave}
        onKeyDown={handleKeyDown}
      >
        <svg
          className="elevation-chart__svg"
          viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
          preserveAspectRatio="none"
          role="img"
          aria-label="Elevation profile"
        >
          {drawn.ftTicks.map((ft) => (
            <line
              key={`ft-${ft}`}
              className="elevation-chart__grid"
              x1={0}
              x2={VIEW_W}
              y1={drawn.yFor(ft)}
              y2={drawn.yFor(ft)}
            />
          ))}
          {drawn.mileTicks.map((mile) => (
            <line
              key={`mi-${mile}`}
              className="elevation-chart__grid"
              x1={drawn.xFor(mile)}
              x2={drawn.xFor(mile)}
              y1={0}
              y2={VIEW_H}
            />
          ))}

          {selection !== null && (
            <rect
              data-testid="chart-selection"
              className="elevation-chart__selection"
              x={drawn.xFor(selection.startMile)}
              y={0}
              width={Math.max(
                0,
                drawn.xFor(selection.endMile) - drawn.xFor(selection.startMile),
              )}
              height={VIEW_H}
            />
          )}

          <path
            data-testid="chart-area"
            className="elevation-chart__area"
            d={drawn.area}
          />
          <path className="elevation-chart__line" d={drawn.line} fill="none" />

          {selection !== null && (
            <>
              <line
                className="elevation-chart__selection-edge"
                x1={drawn.xFor(selection.startMile)}
                x2={drawn.xFor(selection.startMile)}
                y1={0}
                y2={VIEW_H}
              />
              <line
                className="elevation-chart__selection-edge"
                x1={drawn.xFor(selection.endMile)}
                x2={drawn.xFor(selection.endMile)}
                y1={0}
                y2={VIEW_H}
              />
            </>
          )}

          {herePct !== null && (
            <line
              data-testid="chart-you-are-here"
              className="elevation-chart__here"
              x1={(herePct / 100) * VIEW_W}
              x2={(herePct / 100) * VIEW_W}
              y1={0}
              y2={VIEW_H}
            />
          )}

          {hoverPct !== null && (
            <line
              data-testid="chart-cursor"
              className="elevation-chart__cursor"
              x1={(hoverPct / 100) * VIEW_W}
              x2={(hoverPct / 100) * VIEW_W}
              y1={0}
              y2={VIEW_H}
            />
          )}
          {hoverPct !== null && hoverSample !== null && (
            // A zero-length round-capped stroke, not a <circle>: this SVG is
            // stretched (preserveAspectRatio="none"), which would render a
            // circle as an ellipse. A non-scaling stroke keeps its shape.
            <path
              className="elevation-chart__cursor-dot"
              d={`M${((hoverPct / 100) * VIEW_W).toFixed(2)},${drawn
                .yFor(hoverSample.elevationFt)
                .toFixed(2)} l0.01,0`}
            />
          )}
        </svg>

        {hoverPct !== null && hoverSample !== null && (
          <div
            data-testid="chart-readout"
            className={
              hoverPct > 72
                ? 'elevation-chart__readout elevation-chart__readout--flipped'
                : 'elevation-chart__readout'
            }
            style={{ left: `${hoverPct}%` }}
          >
            mi {formatMileMarker(hoverSample.mile)} ·{' '}
            {formatElevation(hoverSample.elevationFt, units)}
          </div>
        )}

        <div className="elevation-chart__ylabels">
          <span className="elevation-chart__mono">
            {formatElevation(drawn.maxFt, units)}
          </span>
          <span className="elevation-chart__mono">
            {formatElevation(drawn.minFt, units)}
          </span>
        </div>
      </div>

      <div className="elevation-chart__axis">
        {drawn.mileTicks.map((mile) => (
          <span
            key={mile}
            className="elevation-chart__mono elevation-chart__tick"
            style={{ left: `${pctFor(mile)}%` }}
          >
            mi {formatTick(mile, drawn.mileStep)}
          </span>
        ))}
      </div>
    </div>
  )
}
