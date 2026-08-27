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
// DAY BOUNDARIES (#971, wireframe 3a). Handed `boundaries`, the chart draws a
// plan's stops over the profile and lets a pointer take the ones the plan says
// may move. That is the one planning gesture a phone cannot offer - a ten-mile
// window has nothing to drag a day between - and it is why the Plan tab has a
// wide layout at all. Two rules keep it honest, and both are here rather than
// implied: this component NEVER writes a plan, it reports a mile and redraws
// from what comes back (lib/planBench.ts owns every rule about what a move may
// do); and every movable boundary is also a focusable slider, because a
// gesture with no keyboard equivalent is a feature half the people who need it
// cannot use.
//
// The selection and the direction are CONTROLLABLE (PR #885 review): while
// the route builder is open the shell derives both from the draft, so a
// stop typed into the builder selects here and a drag here re-stretches the
// route - one selection, two instruments. `selectionFromPlan` is how this
// component knows the selection is a route rather than a measurement: a
// plain click must not unmake a route the way it clears a measurement, so
// clearing is the builder's job and the Clear button steps aside. With the
// props absent the chart owns its own state, exactly as before.
//
// The time is moving time: rounded to 5 minutes, prefixed ≈, never an
// arrival clock, no descent credit - WIREFRAMES.md's load-bearing values,
// unchanged up here. "walking" is appended so a desk reader is told it is
// moving time, per HIKE_PLANNING.md Finding 4's honesty requirement. It is
// priced at the HIKER'S pace when one is set (#886, closing the gap #884
// and #885 opened by crossing), and then it cannot render without its
// baseline - paceEstimate welds the "was ... × standard" line to the text
// at the type level, exactly as the highlight sheet shows it.

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
import { legFigures, priceLeg } from '../lib/route'
import { STANDARD_PACE, type PaceProfile } from '../lib/pace'
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

/**
 * How close a pointer must come to a day boundary to take it, in CSS pixels.
 *
 * @unvalidated 10 px is picked, not measured. This is a mouse surface - the
 * chart only ever renders above desktop.css's breakpoint - so it is not the
 * 24 px WCAG 2.2 asks of a touch target, and it is not trying to be: the
 * keyboard handles below are the accessible path to the same edit, and they
 * are real focusable controls.
 *
 * WHAT IT CANNOT BE BOUNDED BY, since the number wants to look derivable and
 * is not: the spacing between boundaries. At 166 miles across a 1,000 px plot
 * one mile is 6 px, so a twelve-mile day is 72 px wide and a two-mile day is
 * 12 - narrower than two 10 px regions side by side. That overlap is resolved
 * by taking the NEAREST movable boundary rather than the first one in range,
 * so a tight pair still picks correctly; it just has to be aimed at within
 * 6 px. A slop small enough to never overlap would be about 5 px, which is
 * harder to hit than the miss it prevents.
 *
 * What would settle it: somebody dragging boundaries on a real plan at a real
 * width and reporting the misses. The direction it errs in is a grab that
 * needs a second try - a press outside every region starts a measurement,
 * which changes no plan and is visibly not a plan edit.
 */
const BOUNDARY_GRAB_PX = 10

/**
 * One arrow-key nudge of a day boundary, and the Shift version, in miles.
 *
 * MILES, not a fraction of the domain like `KEY_STEP` above, and that half is
 * reasoned: a fraction makes one keypress worth 1.7 mi on a 166-mile section
 * and 0.15 mi on a fifteen-mile one, so the same key does a different thing
 * depending on what the chart happens to be showing. A hiker moving a day
 * boundary is thinking in miles.
 *
 * WHY THERE ARE TWO, with the arithmetic, because the fine one is invisible at
 * the width this screen exists for: 166 miles across a 1,000-unit viewBox puts
 * 0.1 mi at 0.6 px. It still moves the plan and the figures still say so, but
 * nothing visibly slides - so Shift gets a step that does, at 6 px, and a hiker
 * placing a boundary precisely zooms first, where 0.1 mi is 60 px on a two-mile
 * domain. Neither number is small enough to be lost: `wasDistanceMi` records a
 * change past 0.05 mi (lib/planBench.ts), so even one fine nudge prints "was".
 *
 * @unvalidated The two figures themselves are picked. 0.1 mi is a tenth, which
 * is the precision every mile marker in this app is printed to; 1 mi is a round
 * number for crossing a section. Both are far coarser than the published
 * profile can resolve - `SAMPLE_INTERVAL_METERS = 25` in
 * pipeline/export_elevation.py is about 0.0155 mi - so neither is bounded by
 * the data. What would settle them: watching somebody place a boundary by
 * keyboard. Until then they err small, which for an edit to a plan means
 * correctable by another keypress.
 */
const BOUNDARY_KEY_STEP_MI = 0.1
const BOUNDARY_KEY_COARSE_MI = 1

export interface ChartStretch {
  startMile: number
  endMile: number
}

/**
 * One day boundary of a plan, drawn on the profile (#971).
 *
 * The chart NEVER decides which of these may move or how far - lib/planBench.ts
 * does, because those are rules about a plan (the walked prefix, pins, the
 * neighbouring stops) and this component knows nothing about plans. It draws
 * what it is handed and reports where a pointer let go.
 */
export interface ChartBoundary {
  /** Opaque to this component - handed straight back to `onMoveBoundary`. */
  stopIndex: number
  mile: number
  /** For the handle's accessible name: "Lost Mountain Shelter", "mi 486.2". */
  label: string
  /** Whether this one may be taken. A fixed boundary is still DRAWN - a
   *  section whose first and last edges were invisible would read as a plan
   *  running off both sides of the picture. */
  movable: boolean
  /** How far it may travel. Present only while `movable`. */
  minMile?: number
  maxMile?: number
  /**
   * Why a fixed boundary is fixed, in a sentence, or absent.
   *
   * A dashed line says "not this one" and nothing else, and #1049 is this
   * repository's own lesson about that: a refusal that does not say WHICH
   * absence it is sends a hiker looking for a fix that does not exist. Shown
   * as the line's `<title>`, which is the hover explanation a pointer surface
   * already has and costs nothing when nobody asks for it.
   */
  fixedReason?: string
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
  /**
   * The settled selection, when the SHELL owns it. Undefined leaves the
   * chart uncontrolled; null is a controlled "nothing selected". A drag in
   * progress still draws live either way - only the settled claim is
   * controlled.
   */
  selection?: ChartStretch | null
  /** Which way the figures read, when the shell owns it - the route's own
   *  direction, so the chart and the builder cannot disagree about the same
   *  walk. Undefined leaves the toggle uncontrolled. */
  southbound?: boolean
  onToggleSouthbound?: () => void
  /** True while the selection IS the route being built: a click no longer
   *  clears (a click is too cheap to unmake a route), Clear steps aside for
   *  the builder's own close, and the empty-state hint changes. */
  selectionFromPlan?: boolean
  /**
   * The chart's domain changed by an explicit zoom act - "Zoom to stretch"
   * (the padded, clamped domain) or "Whole trail" (null). The maintainer's
   * review on #885 asked for these to move the MAP too; the screen holds
   * the camera, so the act is reported rather than performed here.
   */
  onZoomDomain?: (domain: ChartDomain | null) => void
  /** Offered beside a settled measurement: hand this stretch to the route
   *  builder. Hidden while the selection already IS the route. */
  onPlanStretch?: () => void
  /** The hiker's own pace (#880), pricing the ≈time exactly as the route
   *  builder prices its legs - the two share a selection now, so they must
   *  not disagree about the same walk (#886). Standard when absent. */
  pace?: PaceProfile
  /**
   * Where the chart RESTS, when something narrower than the whole published
   * profile is the subject (#971): the plan's own miles on the bench, so a
   * 166-mile section fills the plot instead of being a sliver of 2,197.
   *
   * Clamped to the profile, and it is what "Whole trail" returns to - the
   * button is relabelled, because on this screen the whole trail is not what
   * zooming out means.
   */
  restingDomain?: ChartDomain | null
  /** The plan's day boundaries, drawn on the profile and - where the plan says
   *  they may move - draggable (#971). Absent leaves the chart exactly as it
   *  was before. */
  boundaries?: readonly ChartBoundary[]
  /** A boundary was dragged or nudged to a new mile. THE CHART NEVER WRITES
   *  THE PLAN: it reports the mile and redraws from the boundaries it gets
   *  back, so every rule about what a move is allowed to do lives in one
   *  place (lib/planBench.ts) rather than half here. */
  onMoveBoundary?: (stopIndex: number, mile: number) => void
  /**
   * What to invite with when nothing is selected, replacing "Drag to measure a
   * stretch" / "Drag to set the route's stretch".
   *
   * Exists because those two sentences are claims about what a drag DOES, and
   * on the plan bench neither is true: the selection there is a day the shell
   * owns, so a drag on empty plot settles nothing and the only thing a pointer
   * can move is a boundary. A hint that promised a measurement would be the
   * display outrunning what the surface actually does.
   */
  hint?: string
  /** What the controlled selection IS, for the chip beside its miles. "route"
   *  where the builder owns it, "day" on the bench - the same reason `hint`
   *  exists. Only shown while `selectionFromPlan`. */
  selectionLabel?: string
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

/** A boundary being dragged: which one, where it started, where it is now. */
interface BoundaryDrag {
  stopIndex: number
  fromMile: number
  mile: number
}

export function ElevationChart({
  profile,
  currentMile = null,
  units = 'imperial',
  onHoverMile,
  onSelectStretch,
  selection,
  southbound,
  onToggleSouthbound,
  selectionFromPlan = false,
  onZoomDomain,
  onPlanStretch,
  pace = STANDARD_PACE,
  restingDomain = null,
  boundaries,
  onMoveBoundary,
  hint,
  selectionLabel = 'route',
}: ElevationChartProps) {
  const [zoom, setZoom] = useState<ChartDomain | null>(null)
  const [hoverMile, setHoverMile] = useState<number | null>(null)
  /** The drag in flight, or null while every claim rests. */
  const [liveSelection, setLiveSelection] = useState<ChartStretch | null>(null)
  /** The chart's own settled selection and direction - read only while the
   *  matching prop is undefined (uncontrolled), written regardless so the
   *  handlers need not branch. */
  const [ownSelection, setOwnSelection] = useState<ChartStretch | null>(null)
  const [ownSouthbound, setOwnSouthbound] = useState(false)
  const dragRef = useRef<DragState | null>(null)
  /** The boundary drag in flight, or null. Held in a ref for the pointer
   *  handlers and mirrored into state for the picture - the same split the
   *  selection drag uses above. */
  const boundaryDragRef = useRef<BoundaryDrag | null>(null)
  const [liveBoundary, setLiveBoundary] = useState<BoundaryDrag | null>(null)
  const plotRef = useRef<HTMLDivElement | null>(null)

  const settled = selection !== undefined ? selection : ownSelection
  const sobo = southbound !== undefined ? southbound : ownSouthbound

  const resting = useMemo(() => {
    if (restingDomain === null) return fullDomain(profile)
    return clampDomain(restingDomain, profile)
  }, [restingDomain, profile])

  const domain = useMemo(() => {
    if (zoom !== null) return zoom
    return resting
  }, [zoom, resting])

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
      // A CONTROLLED selection arrives unsnapped and stays so: a route
      // stop at mi 31.7 must print 31.7, not the nearest sample to it.
      const snapped =
        stretch === null
          ? null
          : {
              startMile: nearestMile(profile, stretch.startMile) ?? stretch.startMile,
              endMile: nearestMile(profile, stretch.endMile) ?? stretch.endMile,
            }
      setLiveSelection(null)
      setOwnSelection(snapped)
      onSelectStretch?.(snapped)
    },
    [onSelectStretch, profile],
  )

  /** How far, in miles, `mile` may travel while dragging boundary `at`. */
  const boundaryLimits = useCallback(
    (at: number): { minMile: number; maxMile: number } | null => {
      const boundary = boundaries?.find((b) => b.stopIndex === at)
      if (boundary === undefined || !boundary.movable) return null
      return {
        minMile: boundary.minMile ?? boundary.mile,
        maxMile: boundary.maxMile ?? boundary.mile,
      }
    },
    [boundaries],
  )

  /**
   * The movable boundary nearest `clientX`, within the grab region, or null.
   *
   * NEAREST rather than first-in-range, which is what makes BOUNDARY_GRAB_PX
   * safe on a whole-section domain where two boundaries can be closer together
   * than the region is wide - see that constant.
   */
  const boundaryForClientX = useCallback(
    (clientX: number): ChartBoundary | null => {
      const plot = plotRef.current
      if (plot === null || domain === null || boundaries === undefined) return null
      const rect = plot.getBoundingClientRect()
      if (rect.width === 0) return null
      const span = domain.endMile - domain.startMile
      if (span === 0) return null

      let best: ChartBoundary | null = null
      let bestPx = BOUNDARY_GRAB_PX
      for (const boundary of boundaries) {
        if (!boundary.movable) continue
        const at = rect.left + ((boundary.mile - domain.startMile) / span) * rect.width
        const away = Math.abs(clientX - at)
        if (away <= bestPx) {
          bestPx = away
          best = boundary
        }
      }
      return best
    },
    [boundaries, domain],
  )

  /** Report a boundary's new mile, clamped to its own travel. Shared by the
   *  drag and the keyboard, so the two cannot disagree about the limits. */
  const settleBoundary = useCallback(
    (at: number, mile: number) => {
      const limits = boundaryLimits(at)
      if (limits === null) return
      onMoveBoundary?.(at, Math.min(limits.maxMile, Math.max(limits.minMile, mile)))
    },
    [boundaryLimits, onMoveBoundary],
  )

  const handlePointerDown = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const mile = mileForClientX(event.clientX)
      if (mile === null) return

      // A press that lands on a day boundary takes it, and takes nothing
      // else: no measurement starts, so a slip while aiming at a handle
      // cannot also unmake whatever was selected.
      const grabbed = boundaryForClientX(event.clientX)
      if (grabbed !== null) {
        // Starts where the BOUNDARY is, not where the pointer is: taking hold
        // of something must not move it, or a grab that changed its mind has
        // already edited the plan by up to BOUNDARY_GRAB_PX of trail.
        const held = {
          stopIndex: grabbed.stopIndex,
          fromMile: grabbed.mile,
          mile: grabbed.mile,
        }
        boundaryDragRef.current = held
        setLiveBoundary(held)
        try {
          event.currentTarget.setPointerCapture?.(event.pointerId)
        } catch {
          /* jsdom */
        }
        return
      }

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
    [mileForClientX, boundaryForClientX],
  )

  const handlePointerMove = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const mile = mileForClientX(event.clientX)
      if (mile === null) return
      reportHover(mile)

      const held = boundaryDragRef.current
      if (held !== null) {
        const limits = boundaryLimits(held.stopIndex)
        const at =
          limits === null
            ? mile
            : Math.min(limits.maxMile, Math.max(limits.minMile, mile))
        const moved = { ...held, mile: at }
        boundaryDragRef.current = moved
        setLiveBoundary(moved)
        return
      }

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
    [mileForClientX, reportHover, domain, boundaryLimits],
  )

  const handlePointerUp = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const held = boundaryDragRef.current
      if (held !== null) {
        boundaryDragRef.current = null
        setLiveBoundary(null)
        // A press on a handle that never travelled is not an edit. Reported
        // only when the boundary actually ended up somewhere else, so the
        // undo the screen offers always has something to undo.
        if (held.mile !== held.fromMile) settleBoundary(held.stopIndex, held.mile)
        return
      }

      const drag = dragRef.current
      dragRef.current = null
      if (drag === null) return
      if (!drag.moved) {
        // A press that never travelled is a click, and a click clears - a
        // measurement. A route it leaves alone: unmaking one is the
        // builder's close button, not a stray click on a chart.
        if (!selectionFromPlan) settleSelection(null)
        return
      }
      const mile = mileForClientX(event.clientX)
      const end = mile ?? drag.anchorMile
      settleSelection({
        startMile: Math.min(drag.anchorMile, end),
        endMile: Math.max(drag.anchorMile, end),
      })
    },
    [mileForClientX, settleSelection, selectionFromPlan, settleBoundary],
  )

  const handlePointerLeave = useCallback(() => {
    if (dragRef.current === null && boundaryDragRef.current === null) reportHover(null)
  }, [reportHover])

  const zoomToSelection = useCallback(() => {
    const stretch = settled
    if (stretch === null) return
    const pad = (stretch.endMile - stretch.startMile) * ZOOM_PADDING
    const domain = clampDomain(
      { startMile: stretch.startMile - pad, endMile: stretch.endMile + pad },
      profile,
    )
    if (domain === null) return
    setZoom(domain)
    // The same padded window the chart now shows, so the map's frame and
    // the profile's agree about what "the stretch" is.
    onZoomDomain?.(domain)
  }, [settled, profile, onZoomDomain])

  const zoomOut = useCallback(() => {
    setZoom(null)
    onZoomDomain?.(null)
  }, [onZoomDomain])

  const handleToggleDirection = useCallback(() => {
    // Controlled direction is the route's own: the toggle asks the shell to
    // turn the route around rather than letting the two drift apart.
    if (southbound !== undefined) {
      onToggleSouthbound?.()
      return
    }
    setOwnSouthbound((was) => !was)
  }, [southbound, onToggleSouthbound])

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
            settled === null
              ? from
              : // Extend from whichever end the cursor is NOT at.
                Math.abs(settled.startMile - from) < Math.abs(settled.endMile - from)
                ? settled.endMile
                : settled.startMile
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
      if (event.key === 'Enter' && settled !== null) {
        event.preventDefault()
        zoomToSelection()
        return
      }
      if (event.key === 'Escape') {
        // A route is not Escape's to clear either - see the click rule.
        if (settled !== null && !selectionFromPlan) {
          event.preventDefault()
          settleSelection(null)
        } else if (zoom !== null) {
          event.preventDefault()
          zoomOut()
        }
      }
    },
    [
      domain,
      hoverMile,
      settled,
      settleSelection,
      selectionFromPlan,
      reportHover,
      zoomToSelection,
      zoomOut,
      zoom,
    ],
  )

  // Figures come from the SETTLED selection only. legFigures walks every
  // sample in the window, which is the whole point (gaps and seams break the
  // runs) and also why it must not run per pointermove across a
  // thousand-mile drag - distance is the one number cheap enough to live.
  const figures = useMemo(() => {
    if (settled === null) return null
    const { startMile, endMile } = settled
    const walked = sobo
      ? legFigures(profile, endMile, startMile, pace)
      : legFigures(profile, startMile, endMile, pace)
    // The printed time and its baseline, welded together (#886) - and now
    // through priceLeg, which is where the descent term lives. This site
    // built the estimate from distance and ascent alone, so a hiker with a
    // descent penalty set (#900) read a figure legFigures did not agree with:
    // 19.3 min against 37.6 on a 1 mi / 1,000 ft drop at the control's
    // maximum, measured on the fixture route.test.ts now pins (#1040).
    return priceLeg(walked, pace)
  }, [settled, sobo, profile, pace])

  if (domain === null || drawn === null) return null

  // The drag in flight outranks the settled claim on screen; the figures
  // wait for it to settle (legFigures walks every sample in the window).
  const shown = liveSelection ?? settled
  /** The boundaries as they should be DRAWN: the one being dragged sits where
   *  the pointer has it, the rest where the plan has them. */
  const drawnBoundaries = (boundaries ?? []).map((boundary) =>
    liveBoundary !== null && liveBoundary.stopIndex === boundary.stopIndex
      ? { ...boundary, mile: liveBoundary.mile }
      : boundary,
  )
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
        {shown === null ? (
          <>
            <span className="elevation-chart__mono elevation-chart__figure--strong">
              mi {formatMileMarker(domain.startMile)} – {formatMileMarker(domain.endMile)}
            </span>
            <span className="elevation-chart__mono">
              {formatDistance(domain.endMile - domain.startMile, units)}
            </span>
            <span className="elevation-chart__hint">
              {hint ??
                (selectionFromPlan
                  ? "Drag to set the route's stretch"
                  : 'Drag to measure a stretch')}
            </span>
          </>
        ) : (
          <>
            <span className="elevation-chart__mono elevation-chart__figure--strong">
              mi {formatMileMarker(shown.startMile)} – {formatMileMarker(shown.endMile)}
            </span>
            {selectionFromPlan && liveSelection === null && (
              <span className="elevation-chart__hint">{selectionLabel}</span>
            )}
            <span className="elevation-chart__mono">
              {formatDistance(shown.endMile - shown.startMile, units)}
            </span>
            {figures !== null && liveSelection === null && (
              <>
                {/* A hole in the DEM prices as flat ground, so ascent,
                    descent and the time it buys would all be short (#1039).
                    The distance above is untouched by a hole and stays; the
                    direction control below stays too, because it belongs to
                    the selection rather than to these figures. */}
                {figures.unmeasuredMi > 0 ? (
                  <span className="elevation-chart__mono">
                    no climb measured for{' '}
                    {formatDistance(figures.unmeasuredMi, units, 'trimmed')} of this
                  </span>
                ) : (
                  <>
                    <span className="elevation-chart__mono">
                      ↑ {formatElevation(figures.ascentFt, units)}
                    </span>
                    <span className="elevation-chart__mono">
                      ↓ {formatElevation(figures.descentFt, units)}
                    </span>
                    <span className="elevation-chart__mono elevation-chart__figure--strong">
                      {figures.estimate.text} walking
                    </span>
                    {figures.estimate.relativeLine !== null && (
                      <span className="elevation-chart__pace">
                        {figures.estimate.relativeLine}
                      </span>
                    )}
                  </>
                )}
                <button
                  type="button"
                  className="elevation-chart__control"
                  onClick={handleToggleDirection}
                  aria-label={`Figures read ${sobo ? 'southbound' : 'northbound'}; switch direction`}
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
                  {sobo ? 'southbound' : 'northbound'}
                </button>
              </>
            )}
          </>
        )}
        <span className="elevation-chart__spacer" />
        {settled !== null && (
          <>
            {onPlanStretch !== undefined && !selectionFromPlan && (
              <button
                type="button"
                className="elevation-chart__control"
                onClick={onPlanStretch}
              >
                Plan this stretch
              </button>
            )}
            <button
              type="button"
              className="elevation-chart__control elevation-chart__control--primary"
              onClick={zoomToSelection}
            >
              Zoom to stretch
            </button>
            {!selectionFromPlan && (
              <button
                type="button"
                className="elevation-chart__control"
                onClick={() => settleSelection(null)}
              >
                Clear
              </button>
            )}
          </>
        )}
        {zoom !== null && (
          <button type="button" className="elevation-chart__control" onClick={zoomOut}>
            {/* What zooming out goes back TO. On the bench that is the plan's
                own miles, and calling it "Whole trail" there would promise
                2,197 miles and deliver 166. */}
            {restingDomain === null ? 'Whole trail' : 'Whole section'}
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

          {shown !== null && (
            <rect
              data-testid="chart-selection"
              className="elevation-chart__selection"
              x={drawn.xFor(shown.startMile)}
              y={0}
              width={Math.max(0, drawn.xFor(shown.endMile) - drawn.xFor(shown.startMile))}
              height={VIEW_H}
            />
          )}

          <path
            data-testid="chart-area"
            className="elevation-chart__area"
            d={drawn.area}
          />
          <path className="elevation-chart__line" d={drawn.line} fill="none" />

          {shown !== null && (
            <>
              <line
                className="elevation-chart__selection-edge"
                x1={drawn.xFor(shown.startMile)}
                x2={drawn.xFor(shown.startMile)}
                y1={0}
                y2={VIEW_H}
              />
              <line
                className="elevation-chart__selection-edge"
                x1={drawn.xFor(shown.endMile)}
                x2={drawn.xFor(shown.endMile)}
                y1={0}
                y2={VIEW_H}
              />
            </>
          )}

          {/* The plan's day boundaries, drawn over the profile and under the
              cursor (#971). Immovable ones are drawn too, dashed: an edge a
              hiker cannot take still tells them where a day ends, and the
              difference between the two has to be visible before they try. */}
          {drawnBoundaries.map((boundary) => (
            <line
              key={`boundary-${boundary.stopIndex}`}
              data-testid={`chart-boundary-${boundary.stopIndex}`}
              className={
                boundary.movable
                  ? 'elevation-chart__boundary'
                  : 'elevation-chart__boundary elevation-chart__boundary--fixed'
              }
              x1={drawn.xFor(boundary.mile)}
              x2={drawn.xFor(boundary.mile)}
              y1={0}
              y2={VIEW_H}
            >
              {!boundary.movable && boundary.fixedReason !== undefined && (
                <title>{boundary.fixedReason}</title>
              )}
            </line>
          ))}

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

        {/* THE KEYBOARD PATH TO THE SAME EDIT, and the reason it is a real
            control rather than another key on the plot: a drag on a chart is
            the one gesture in this app with no keyboard equivalent, and #971
            makes it the gesture the whole screen exists for. Each movable
            boundary is a slider - the role that already means "one value
            along a range", which is exactly what a day boundary is - carrying
            its own limits, so a screen reader is told how far it may go
            before it is moved rather than after. Immovable boundaries get no
            handle: a focus stop that refuses every key is worse than none. */}
        {drawnBoundaries
          .filter((boundary) => boundary.movable)
          .map((boundary) => (
            <button
              key={`handle-${boundary.stopIndex}`}
              type="button"
              data-testid={`chart-boundary-handle-${boundary.stopIndex}`}
              className="elevation-chart__boundary-handle"
              style={{ left: `${pctFor(boundary.mile)}%` }}
              role="slider"
              aria-label={`Day boundary at ${boundary.label}`}
              aria-valuemin={boundary.minMile ?? boundary.mile}
              aria-valuemax={boundary.maxMile ?? boundary.mile}
              aria-valuenow={boundary.mile}
              aria-valuetext={`mi ${formatMileMarker(boundary.mile)}`}
              onKeyDown={(event) => {
                if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
                event.preventDefault()
                // Stopped here rather than left to bubble: the plot's own
                // arrow keys move the hover cursor and extend selections,
                // and a boundary nudge must not do either as a side effect.
                event.stopPropagation()
                const step = event.shiftKey
                  ? BOUNDARY_KEY_COARSE_MI
                  : BOUNDARY_KEY_STEP_MI
                settleBoundary(
                  boundary.stopIndex,
                  boundary.mile + (event.key === 'ArrowLeft' ? -step : step),
                )
              }}
            />
          ))}

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
