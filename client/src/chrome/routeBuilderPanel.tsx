// The route builder, owned by one file instead of by App.tsx (#991).
//
// #937's third cluster: its own state, twenty-odd handlers and memos, and the
// ~100 lines of JSX behind three MapScreenProps fields. See
// chrome/atcNoticesPanel.tsx for why the hook returns a `Pick<MapScreenProps,
// ...>` the shell spreads.
//
// WHY THIS ONE WAS WORTH MOVING, beyond the conflict argument #327 makes for
// the file as a whole: three of the six defects #987 fixed lived in these
// handlers, and each was a rule stated in one place and broken a few hundred
// lines away - `handleChartSouth` bypassing `withStops`, `handleRouteCancel`
// forgetting `editorRefusedTap`, `handleTapToBuild` dropping `fixedEnd`. None
// of the three is subtle at this size. All three were invisible at 4,588
// lines.
//
// THE SEAM WITH THE ELEVATION CHART is the only part that is not a straight
// move, and it is narrow on purpose (#991). The chart's own cluster stays in
// the shell; what crosses is `draftStretch` - which the chart reads as its
// selection while a draft is open - and the three route-state mutations its
// handlers used to make inline, which are callbacks here now. Moving both
// clusters at once would have been a 1,400-line diff in the file this
// repository is worst at reviewing.
//
// NOTHING HERE CHANGES BEHAVIOUR. The suite is the contract: it passes
// untouched across this move, and a test needing an edit would have been
// evidence the extraction changed something.

import { useCallback, useMemo, useState } from 'react'
import type { MapScreenProps } from './MapScreen'
import { RouteEntranceSheet, type EntranceEnd } from './RouteEntranceSheet'
import { RouteStopsPanel, type RouteLegDisplay } from './RouteStopsPanel'
import { RouteStopPicker, type RouteStopChoice } from './RouteStopPicker'
import { RouteMapPickBar } from './RouteMapPickBar'
import type { ChartStretch } from './ElevationChart'
import { mileMarker, stopLabel } from '../lib/planDisplay'
import type { UnitSystem } from '../lib/units'
import {
  anchoredClientMile,
  anchoredMile,
  insertRoutePoint,
  legFigures,
  mileAtWalkingMinutes,
  restretchStops,
  routeDirection,
  routeLegs,
  type MileAnchor,
} from '../lib/route'
import { DEFAULT_WALKING_HOURS, nearestStopBeyond } from '../lib/dayPlanner'
import { nearestStop } from '../lib/cascade'
import {
  locateOnTrail,
  trailPointAtMile,
  trailSlice,
  type TrailIndex,
} from '../lib/trailPosition'
import type { RouteDrawing } from '../map/routeLayers'
import type { StoredPoi } from '../lib/trailData'
import type { ElevationProfile } from '../lib/elevationProfile'
import type { PaceProfile } from '../lib/pace'
import type { HikePiece, PlaceRef } from '../lib/hikes'

/** The `MapScreenProps` fields this feature owns. See atcNoticesPanel.tsx. */
export type RouteBuilderMapProps = Pick<
  MapScreenProps,
  'routeDrawing' | 'onRouteTap' | 'routeSheet'
>

interface RouteDraftStop {
  mile: number
  /** Null for a stop no tap and no anchor could place on the client scale -
   *  it still plans and prices honestly (those run on `mile`), it just
   *  cannot be drawn. */
  clientMile: number | null
  name?: string
  poiId?: string
}

/**
 * The route builder's two screens (the chosen "route by destination" flow):
 * the ENTRANCE asks where from and how far or how long; "Use this stretch"
 * lands the resolved pair on the EDITOR, where every stop is a field and
 * destinations join between the ends. The draft survives tab switches -
 * the Plan tab reopens the editor rather than tolling the entrance again -
 * and dies only at the close button or when a plan is laid out of it.
 */
type RouteDraftState =
  | {
      phase: 'entrance'
      start: RouteDraftStop | null
      /** The far end when the hiker NAMED one (#804). With both ends fixed
       *  the entrance stops asking how far and states it. */
      fixedEnd: RouteDraftStop | null
      ask: 'far' | 'long'
      miles: number
      days: number
      south: boolean
    }
  | {
      phase: 'editor'
      stops: RouteDraftStop[]
      /**
       * Previous stop lists, newest last - the ↺ the wireframe puts beside
       * the map (#973).
       *
       * IT EXISTS BECAUSE TAPPING IS CHEAP AND MIS-TAPPING IS CERTAIN. A
       * point dropped a mile off where a thumb meant it is not an error the
       * app can detect, so the only honest recovery is to let the hiker take
       * it back - and "remove the last stop" would be the wrong verb, since
       * least-added-distance insertion means the last stop TAPPED is often
       * not the last stop in the list.
       *
       * Bounded at ROUTE_HISTORY_MAX: a route is a dozen stops, not a
       * document, and an unbounded stack on a phone that keeps a draft
       * across tab switches is a leak nobody would notice.
       */
      history: RouteDraftStop[][]
    }

/** Whether two stop lists are the same route. Position and mile are what a
 *  leg is computed from, so they are what "changed" means here. */
function sameStops(a: readonly RouteDraftStop[], b: readonly RouteDraftStop[]): boolean {
  return a.length === b.length && a.every((stop, i) => stop.mile === b[i].mile)
}

/** How many steps back the route builder can go. Deep enough to undo a run
 *  of mis-taps, shallow enough that the stack is never the reason a draft
 *  costs memory. */
const ROUTE_HISTORY_MAX = 20

/**
 * A new editor state with `stops` replaced and the old list remembered.
 *
 * Every editor mutation goes through here so undo cannot silently miss one -
 * the failure mode of a history stack is not that it breaks loudly, it is
 * that one path forgets to record and ↺ jumps two edits back.
 */
function withStops(
  draft: Extract<RouteDraftState, { phase: 'editor' }>,
  stops: RouteDraftStop[],
): RouteDraftState {
  // BY CONTENT, not by reference (#986). insertRoutePoint returns a fresh
  // array even when it refuses a re-tap on a mile already in the route, so a
  // reference check recorded a no-op edit - and the hiker's next ↺ press
  // spent itself undoing nothing, which reads as undo being broken.
  if (sameStops(stops, draft.stops)) return draft
  return {
    ...draft,
    stops,
    history: [...draft.history, draft.stops].slice(-ROUTE_HISTORY_MAX),
  }
}

/** Which slot of the draft a picked stop lands in. */
/** A place the app already knows, as a stop the route builder can open on.
 *  The client mile is re-derived from the anchors rather than carried,
 *  because a PlaceRef only ever holds the pipeline's axis (lib/hikes.ts). */
function draftStopFor(place: PlaceRef, anchors: readonly MileAnchor[]): RouteDraftStop {
  return {
    mile: place.mile,
    clientMile: anchoredClientMile(place.mile, anchors),
    ...(place.name === undefined ? {} : { name: place.name }),
    ...(place.poiId === undefined ? {} : { poiId: place.poiId }),
  }
}

/** A draft's stops as the shell's shape: the pipeline mile and the names,
 *  without the client mile, which is drawing's business and nobody else's. */
function viaStops(stops: readonly RouteDraftStop[]): ViaStopLike[] {
  return stops.map(({ mile, name, poiId }) => ({
    mile,
    ...(name === undefined ? {} : { name }),
    ...(poiId === undefined ? {} : { poiId }),
  }))
}

type StopSlot =
  | { kind: 'start' }
  | { kind: 'end' }
  | { kind: 'replace'; index: number }
  | { kind: 'add' }

/** The stop picker, when it is up: the slot being filled, whether the hiker
 *  went on to the map to fill it, and whether the last map tap was refused
 *  (off the corridor - cleared by the next accepted tap). */
type StopPickState = { slot: StopSlot; onMap: boolean; refusedTap: boolean }

export interface RouteBuilderInput {
  /** The centerline index a tap snaps against, or null before trail data. */
  trailIndex: TrailIndex | null
  /** The POI anchors that carry a client mile onto the pipeline's axis. */
  mileAnchors: readonly MileAnchor[]
  pois: readonly StoredPoi[]
  elevation: ElevationProfile | null
  pace: PaceProfile
  units: UnitSystem
  /** The stops the picker offers, already shaped by the shell. */
  routeStopChoices: readonly RouteStopChoice[]
  /** The hiker's own mile on the planner's axis, or null with no fix. */
  gpsPlanMile: number | null
  /** The fix's mile on the CLIENT index's scale, or null with no fix. Both
   *  facts in one value: the entrance's "start from here" door is offered
   *  only when it is non-null, and the stop it makes needs the number. */
  gpsClientMile: number | null
  /** The trail's length, for the entrance's distance slider ceiling. */
  trailMiles: number | null
  /**
   * Whether the break-into-days sheet is up over the builder (#758).
   *
   * THE BOOLEAN AND NOT THE SHEET. That sheet is the shell's - the shell
   * renders it over `mapScreen.routeSheet` - and the only thing the builder
   * needs to know is that something is covering the surface that would
   * explain a map tap, so it stops interpreting taps. Taking the node
   * instead would have made this panel the thing that renders the shell's
   * sheet, and would have closed a definition cycle in App.tsx: the sheet is
   * built from a handler that closes this builder.
   */
  targetOpen: boolean
  setTargetRequest: (value: { route: ViaStopLike[] } | null) => void
  /** Keep this stretch as ground already walked (#789). The stops cross
   *  rather than the draft: writing to the trip store is the shell's job,
   *  and knowing what a draft is is not. */
  onRecordWalked: (stops: readonly ViaStopLike[]) => void
  /** The one-thing-open-at-a-time sweep the shell owns. */
  onOpenBuilder: () => void
  /** Clear the chart's free measurement when a draft takes over. */
  clearFreeChartStretch: () => void
}

/** What `setTargetRequest` carries - the shell owns the shape. */
export interface ViaStopLike {
  mile: number
  name?: string
  poiId?: string
}

export interface RouteBuilderPanel {
  /** Spread into `<MapScreen>`. */
  mapScreen: RouteBuilderMapProps
  draftStretch: ChartStretch | null
  draftLive: boolean
  draftSouth: boolean | null
  openRouteBuilder: () => void
  handlePlanGap: (gap: Extract<HikePiece, { kind: 'gap' }>) => void
  handlePlanFrom: (from: PlaceRef, toward: PlaceRef) => void
  /** The draft is spent - a plan was laid out of it (#758's re-target door
   *  lands here too). Distinct from the close button only in who pressed it. */
  closeRouteBuilder: () => void
  openFromMiles: (startMile: number, endMile: number, south: boolean) => void
  /**
   * The three chart seams. Each is a no-op with no draft open, and the
   * SHELL decides which world it is in by reading `draftLive` - they do not
   * report it back. An earlier draft of this file had them return whether
   * they had acted, read straight after the `setRouteDraft` call; React runs
   * an updater at render, so that flag was false every time and the chart
   * would have flipped its free measurement while also turning the route
   * around. `draftLive` is the same fact, known a render earlier.
   */
  restretchToMiles: (startMile: number, endMile: number) => void
  toggleDraftDirection: () => void
}

export function useRouteBuilderPanel({
  trailIndex,
  mileAnchors,
  pois,
  elevation,
  pace,
  units,
  routeStopChoices,
  gpsPlanMile,
  gpsClientMile,
  trailMiles,
  targetOpen,
  setTargetRequest,
  onRecordWalked,
  onOpenBuilder,
  clearFreeChartStretch,
}: RouteBuilderInput): RouteBuilderPanel {
  /**
   * The route being built (#755), or null when the builder is closed. Held
   * here and not persisted: a draft is a sketch, and the thing worth keeping
   * - the plan - is what "Break into days" produces from it (#756).
   */
  const [routeDraft, setRouteDraft] = useState<RouteDraftState | null>(null)
  /** The last trail tap the entrance refused as too far off the corridor -
   *  cleared by the next accepted one (#801). */
  const [entranceRefusedTap, setEntranceRefusedTap] = useState(false)
  /** The same, for the editor's own tap (#973). Its own flag rather than one
   *  shared with the entrance: the two are never on screen together, and one
   *  flag would carry a refusal from one phase into the other, where the
   *  sentence explaining it belongs to a control the hiker has left behind. */
  const [editorRefusedTap, setEditorRefusedTap] = useState(false)
  /** The stop picker over the draft, or null while every field rests. */
  const [stopPick, setStopPick] = useState<StopPickState | null>(null)
  const entranceEnd = useMemo(() => {
    if (routeDraft === null || routeDraft.phase !== 'entrance') return null
    if (routeDraft.start === null) return null
    const { start, ask, miles, days, south } = routeDraft

    const raw =
      ask === 'long' && elevation !== null
        ? mileAtWalkingMinutes(
            elevation,
            start.mile,
            days * DEFAULT_WALKING_HOURS * 60,
            south ? 'SOBO' : 'NOBO',
            pace,
          )
        : start.mile + (south ? -miles : miles)
    const reachMi = Math.abs(raw - start.mile)

    const snapped = nearestStopBeyond(pois, start.mile, raw)
    if (snapped !== null) {
      return {
        reachMi,
        kind: snapped.kind === 'terminus' ? undefined : snapped.kind,
        stop: {
          mile: snapped.mile,
          clientMile: anchoredClientMile(snapped.mile, mileAnchors),
          ...(snapped.name === undefined ? {} : { name: snapped.name }),
          ...(snapped.poiId === undefined ? {} : { poiId: snapped.poiId }),
        } satisfies RouteDraftStop,
      }
    }

    let low = Infinity
    let high = -Infinity
    for (const choice of routeStopChoices) {
      if (choice.mile < low) low = choice.mile
      if (choice.mile > high) high = choice.mile
    }
    if (low > high) return null
    const clamped = Math.min(high, Math.max(low, raw))
    if (clamped === start.mile) return null
    return {
      reachMi,
      kind: undefined,
      stop: {
        mile: clamped,
        clientMile: anchoredClientMile(clamped, mileAnchors),
      } satisfies RouteDraftStop,
    }
  }, [routeDraft, elevation, pois, routeStopChoices, mileAnchors, pace])

  /**
   * A door's answer lands in the slot being filled. The one resolver every
   * door funnels through: a stop born from arithmetic (a snap, a distance)
   * arrives without a client mile and gets one from the inverse anchor
   * here, so the drawing below never has to know where a stop came from.
   */
  const applyPickedStop = useCallback(
    (picked: {
      mile: number
      clientMile?: number | null
      name?: string
      poiId?: string
    }) => {
      if (stopPick === null) return
      const slot = stopPick.slot
      const stop: RouteDraftStop = {
        mile: picked.mile,
        clientMile: picked.clientMile ?? anchoredClientMile(picked.mile, mileAnchors),
        ...(picked.name === undefined ? {} : { name: picked.name }),
        ...(picked.poiId === undefined ? {} : { poiId: picked.poiId }),
      }
      setRouteDraft((draft) => {
        if (draft === null) return draft
        if (slot.kind === 'start') {
          return draft.phase === 'entrance' ? { ...draft, start: stop } : draft
        }
        if (slot.kind === 'end') {
          return draft.phase === 'entrance' ? { ...draft, fixedEnd: stop } : draft
        }
        if (draft.phase !== 'editor') return draft
        if (slot.kind === 'add') {
          // Trail order IS least-added-distance order on a monotonic route,
          // so the tap builder's placement rule serves the add row unchanged
          // - between the ends when the stop is between them, extending the
          // route when it is past one.
          return withStops(draft, insertRoutePoint(draft.stops, stop))
        }
        // A replacement that lands exactly on another stop's mile would fold
        // two stops into a zero-length leg - refused the way insertRoutePoint
        // refuses a re-tap: nothing changes.
        if (draft.stops.some((s, i) => i !== slot.index && s.mile === stop.mile)) {
          return draft
        }
        return withStops(
          draft,
          draft.stops.map((s, i) => (i === slot.index ? stop : s)),
        )
      })
      setStopPick(null)
    },
    [stopPick, mileAnchors],
  )

  // A map tap while the picker's map door is open (and only then - one tap,
  // one interpreter). Snapped by the centerline index - the one job
  // locateOnTrail keeps under HIKE_PLANNING.md Finding 2 - then carried onto
  // the pipeline's axis by the nearest anchor, so every figure slices the
  // profile at miles that mean what the display says. A tap the index
  // refuses (>3 mi off the corridor) sets a flag the bar explains, rather
  // than silently doing nothing.
  // eslint-disable-next-line react-hooks/exhaustive-deps -- listed below
  const handleStopMapTap = useCallback(
    (at: { lon: number; lat: number }) => {
      if (trailIndex === null) return
      // NO BUTTON FIRST (#801). With the entrance open and no picker over
      // it, a tap on the trail sets the START - there is nothing else this
      // screen is choosing, so nothing needs disambiguating, and a start
      // already set is moved rather than a question being asked.
      if (stopPick === null) {
        if (routeDraft === null) return

        // THE EDITOR'S OWN TAP (#973, wireframe 2a frame 1). The canvas has
        // been in route-tap mode here the whole time - `onRouteTap` is set
        // for any open draft - and this handler was the only thing declining
        // to act on it.
        //
        // No mode and no button, which is #801's rule one phase over and the
        // frame's own annotation: "First tap is the start, last is the end, a
        // new point inserts where it adds the least distance." All three fall
        // out of insertRoutePoint, so the tap places a point and says nothing
        // about which kind it is.
        if (routeDraft.phase === 'editor') {
          const located = locateOnTrail(trailIndex, at)
          if (located === null) {
            setEditorRefusedTap(true)
            return
          }
          setEditorRefusedTap(false)
          const clientMile = located.mile
          const mile = anchoredMile(clientMile, mileAnchors) ?? clientMile
          // Named where a real stop is close enough to name it - the same
          // courtesy the entrance's tap does, so a route built by tapping
          // reads as places rather than as mile markers where it can.
          const snapped = nearestStop(pois, mile)
          const stop: RouteDraftStop = {
            mile: snapped?.mile ?? mile,
            clientMile,
            ...(snapped?.name === undefined ? {} : { name: snapped.name }),
            ...(snapped?.poiId === undefined ? {} : { poiId: snapped.poiId }),
          }
          setRouteDraft((draft) =>
            draft === null || draft.phase !== 'editor'
              ? draft
              : withStops(draft, insertRoutePoint(draft.stops, stop)),
          )
          return
        }

        if (routeDraft.phase !== 'entrance') return
        const located = locateOnTrail(trailIndex, at)
        if (located === null) {
          setEntranceRefusedTap(true)
          return
        }
        setEntranceRefusedTap(false)
        const clientMile = located.mile
        const snapped = nearestStop(
          pois,
          anchoredMile(clientMile, mileAnchors) ?? clientMile,
        )
        setRouteDraft((draft) =>
          draft === null || draft.phase !== 'entrance'
            ? draft
            : {
                ...draft,
                start: {
                  mile:
                    snapped?.mile ?? anchoredMile(clientMile, mileAnchors) ?? clientMile,
                  clientMile,
                  ...(snapped?.name === undefined ? {} : { name: snapped.name }),
                  ...(snapped?.poiId === undefined ? {} : { poiId: snapped.poiId }),
                },
              },
        )
        return
      }
      if (!stopPick.onMap) return
      const located = locateOnTrail(trailIndex, at)
      if (located === null) {
        setStopPick({ ...stopPick, refusedTap: true })
        return
      }
      const clientMile = located.mile
      // The ?? is totality, not a path: without anchors the entrance has
      // already refused, so no tap reaches here to need the fallback.
      applyPickedStop({
        mile: anchoredMile(clientMile, mileAnchors) ?? clientMile,
        clientMile,
      })
    },
    [stopPick, trailIndex, mileAnchors, applyPickedStop, routeDraft, pois],
  )

  const handleRouteCancel = useCallback(() => {
    setRouteDraft(null)
    setStopPick(null)
    // The refusal belongs to the draft, not to the app (#986). Left set, it
    // greeted the NEXT route the hiker started with an accusation about a tap
    // they never made, in a panel with nothing in it to explain.
    setEditorRefusedTap(false)
  }, [])

  // What the canvas draws for the draft: the centerline's own geometry
  // between consecutive stops (trailSlice never bridges a part gap), and
  // the stops snapped back onto the line. Client miles throughout - this is
  // the drawing, and the drawing is the one consumer that scale exists for.
  // On the entrance the stretch grows as the slider moves: start alone,
  // then start to the resolved end.
  const routeDrawing: RouteDrawing | null = useMemo(() => {
    if (routeDraft === null || trailIndex === null) return null
    const stops: RouteDraftStop[] =
      routeDraft.phase === 'editor'
        ? routeDraft.stops
        : routeDraft.start === null
          ? []
          : entranceEnd === null
            ? [routeDraft.start]
            : [routeDraft.start, entranceEnd.stop]
    return {
      legs: stops.slice(1).flatMap((to, i) => {
        const from = stops[i]
        if (from.clientMile === null || to.clientMile === null) return []
        return [trailSlice(trailIndex, from.clientMile, to.clientMile)]
      }),
      points: stops.flatMap((stop, i) => {
        if (stop.clientMile === null) return []
        const at = trailPointAtMile(trailIndex, stop.clientMile)
        if (at === null) return []
        const role: 'start' | 'via' | 'end' =
          i === 0 ? 'start' : i === stops.length - 1 ? 'end' : 'via'
        // A MILE MARKER, never converted (#986). It reads as the same
        // quantity as a distance and is not one: mile 470.8 is a name for a
        // place, and `formatDistance` would render it "757.7 km" to a metric
        // hiker while the stop row beside it still said "mi 470.8". One
        // place, two numbers, neither of which names it.
        return [{ lon: at[0], lat: at[1], role, label: `mi ${mileMarker(stop.mile)}` }]
      }),
    }
  }, [routeDraft, entranceEnd, trailIndex])

  // The editor's figures, on the pipeline miles. Null climb and time on a
  // download with no profile: the distance is still a fact, and the surface
  // says why the rest is missing rather than printing a time that quietly
  // ignored every climb (see RouteLegDisplay).
  const routeLegDisplays: RouteLegDisplay[] = useMemo(() => {
    if (routeDraft === null || routeDraft.phase !== 'editor') return []
    // Distance only, and the panel already renders that state: no profile
    // downloaded, or a leg the DEM never measured (#1039). The second used
    // to price the hole as flat ground and hand back a climb and a time that
    // were both short, which is the direction that gets somebody caught out
    // after dark - so it takes the same branch the missing profile does.
    const unpriced = ({
      from,
      to,
    }: {
      from: { mile: number }
      to: { mile: number }
    }) => ({
      distanceMi: Math.abs(to.mile - from.mile),
      ascentFt: null,
      descentFt: null,
      minutes: null,
    })
    return routeLegs(routeDraft.stops).map((leg) => {
      if (elevation === null) return unpriced(leg)
      const figures = legFigures(elevation, leg.from.mile, leg.to.mile, pace)
      return figures.unmeasuredMi > 0 ? unpriced(leg) : figures
    })
  }, [routeDraft, elevation, pace])

  // Opening the builder is a map act: it lands on the trail tab with
  // everything else closed - the same one-thing-open-at-a-time rule the
  // legend, the search and the waypoint card already keep between them.
  // A draft already in progress reopens where it stood - the entrance is
  // for starting, never a toll gate on the way back to your own route.
  const openRouteBuilderFrom = useCallback(
    (start: RouteDraftStop | null, south?: boolean) => {
      onOpenBuilder()
      // The chart's selection now mirrors the draft; a measurement left
      // behind here would resurface the moment the builder closed.
      clearFreeChartStretch()
      setRouteDraft((draft) => {
        if (draft === null) {
          return {
            phase: 'entrance',
            start,
            fixedEnd: null,
            // The mockup's own opening answers - a mid-length section,
            // walked the way most of this trail is walked. Both are one
            // drag from anything else.
            ask: 'far',
            miles: 45,
            days: 3,
            south: south ?? false,
          }
        }
        // A suggested start fills an entrance that has none yet, and never
        // overwrites a route the hiker is already editing: their own draft
        // outranks a starting point this app proposed.
        if (start === null || draft.phase !== 'entrance') return draft
        return { ...draft, start, ...(south === undefined ? {} : { south }) }
      })
    },
    [onOpenBuilder, clearFreeChartStretch],
  )

  const openRouteBuilder = useCallback(
    () => openRouteBuilderFrom(null),
    [openRouteBuilderFrom],
  )

  /**
   * Start a route at the beginning of a stretch nobody has walked (#790's
   * gap row).
   *
   * The gap's low end and nothing else: how far, which way and where it
   * really ends are the entrance's questions, and answering them from the
   * gap's own length would put a 554-mile "trip" in front of a hiker who
   * asked to plan a week. Choosing WHICH gap and how much of it fits the
   * days somebody has is **#791 - What's left**.
   */
  const handlePlanGap = useCallback(
    (gap: Extract<HikePiece, { kind: 'gap' }>) => {
      // A gap row starts at its low end, walking on up the trail. "What's
      // left" (#791) is where BOTH ends are offered, because that is the
      // screen where choosing between them is the question being asked.
      openRouteBuilderFrom(draftStopFor(gap.from, mileAnchors), false)
    },
    [openRouteBuilderFrom, mileAnchors],
  )

  /**
   * Plan from one end of a gap, walking toward the other (#791).
   *
   * The direction is DERIVED from the pair rather than stored anywhere: a
   * hiker who picked the high end is walking south, which is exactly what
   * the entrance's own toggle means. Nothing new is kept, and a
   * flip-flopper's third trip going the other way needs no new concept.
   */
  const handlePlanFrom = useCallback(
    (start: PlaceRef, toward: PlaceRef) => {
      openRouteBuilderFrom(draftStopFor(start, mileAnchors), toward.mile < start.mile)
    },
    [openRouteBuilderFrom, mileAnchors],
  )

  /** One field of the entrance changes; everything else stands. */
  const patchEntrance = useCallback(
    (patch: Partial<Extract<RouteDraftState, { phase: 'entrance' }>>) => {
      setRouteDraft((draft) =>
        draft !== null && draft.phase === 'entrance' ? { ...draft, ...patch } : draft,
      )
    },
    [],
  )

  const handlePickStart = useCallback(
    (door: 'gps' | 'search' | 'map') => {
      if (door === 'gps') {
        if (gpsClientMile === null || gpsPlanMile === null) return
        const start: RouteDraftStop = { mile: gpsPlanMile, clientMile: gpsClientMile }
        setRouteDraft((draft) =>
          draft !== null && draft.phase === 'entrance' ? { ...draft, start } : draft,
        )
        return
      }
      setStopPick({ slot: { kind: 'start' }, onMap: door === 'map', refusedTap: false })
    },
    [gpsClientMile, gpsPlanMile],
  )

  const handleUseStretch = useCallback(() => {
    if (routeDraft === null || routeDraft.phase !== 'entrance') return
    if (routeDraft.start === null) return
    // A named end wins over a resolved one: the hiker said where they are
    // going, so nothing snaps it to whatever the "how far" answer reached
    // (#804).
    const end = routeDraft.fixedEnd ?? entranceEnd?.stop ?? null
    if (end === null) return
    setRouteDraft({ phase: 'editor', stops: [routeDraft.start, end], history: [] })
  }, [routeDraft, entranceEnd])

  const handleEditStop = useCallback((index: number) => {
    setStopPick({ slot: { kind: 'replace', index }, onMap: false, refusedTap: false })
  }, [])

  const handleAddStop = useCallback(() => {
    setStopPick({ slot: { kind: 'add' }, onMap: false, refusedTap: false })
  }, [])

  /** ↺ - back one edit. Nothing when the stack is empty, and the button is
   *  absent then rather than dead. */
  const handleUndoRoute = useCallback(() => {
    setEditorRefusedTap(false)
    setRouteDraft((draft) => {
      if (draft === null || draft.phase !== 'editor') return draft
      const previous = draft.history[draft.history.length - 1]
      if (previous === undefined) return draft
      return { ...draft, stops: previous, history: draft.history.slice(0, -1) }
    })
  }, [])

  /**
   * The entrance's second door (#973): straight to an empty editor, where
   * tapping the trail builds the route.
   *
   * The entrance is not replaced by this. It answers "how far can I get",
   * which is a real question and the one #804 built it for; this answers "I
   * know where I want to go", which the frame draws and which had no door at
   * all. A start already tapped on the entrance carries through rather than
   * being thrown away - having placed it is the same act either way.
   */
  const handleTapToBuild = useCallback(() => {
    setEditorRefusedTap(false)
    setRouteDraft((draft) =>
      draft === null || draft.phase !== 'entrance'
        ? draft
        : {
            phase: 'editor',
            // Both ends the hiker named, not just the start (#986). Naming an
            // end on the entrance is the same act as naming a start, and
            // dropping it silently made the second door cost work.
            stops: [draft.start, draft.fixedEnd].filter(
              (stop): stop is RouteDraftStop => stop !== null,
            ),
            history: [],
          },
    )
  }, [])

  // Only a destination between the ends can be removed - a route needs its
  // ends, and either end is changed by picking a different stop instead.
  const handleRemoveStop = useCallback(() => {
    if (stopPick === null || stopPick.slot.kind !== 'replace') return
    const index = stopPick.slot.index
    setRouteDraft((draft) => {
      if (draft === null || draft.phase !== 'editor') return draft
      if (index <= 0 || index >= draft.stops.length - 1) return draft
      return withStops(
        draft,
        draft.stops.filter((_, i) => i !== index),
      )
    })
    setStopPick(null)
  }, [stopPick])

  /** The stop before the slot being filled - what the picker's distance
   *  door measures from. The add row measures from the current end,
   *  extending the route the way "and then on to..." extends a hike;
   *  a stop the least-added-distance placement then puts BETWEEN the ends
   *  lands there instead, same rule either way. */
  const pickPrevious = useMemo(() => {
    if (stopPick === null || routeDraft === null) return null
    // The entrance's own two slots measure from nothing: a start has no
    // previous stop, and a named end is a destination rather than a
    // distance from one (#804).
    if (stopPick.slot.kind === 'start' || stopPick.slot.kind === 'end') return null
    if (routeDraft.phase !== 'editor') return null
    const stops = routeDraft.stops
    const anchor =
      stopPick.slot.kind === 'add'
        ? stops[stops.length - 1]
        : stopPick.slot.index > 0
          ? stops[stopPick.slot.index - 1]
          : null
    if (anchor === null || anchor === undefined) return null
    return { mile: anchor.mile, label: stopLabel(anchor) }
  }, [stopPick, routeDraft])

  /** Which way the distance door walks: the draft's own direction. */
  const pickSouth = useMemo(() => {
    if (routeDraft === null) return false
    if (routeDraft.phase === 'entrance') return routeDraft.south
    return routeDirection(routeDraft.stops) === 'SOBO'
  }, [routeDraft])

  const handleBreakIntoDays = useCallback(() => {
    if (routeDraft === null || routeDraft.phase !== 'editor') return
    if (routeDraft.stops.length < 2) return
    setTargetRequest({ route: viaStops(routeDraft.stops) })
  }, [routeDraft, setTargetRequest])

  /**
   * "I already walked this" (#789). The same two ends said in the past
   * tense, so it leaves by the same door: the stops cross to the shell,
   * which owns the trip store, and the draft that described them is spent.
   */
  const handleRecordWalked = useCallback(() => {
    if (routeDraft === null || routeDraft.phase !== 'editor') return
    if (routeDraft.stops.length < 2) return
    onRecordWalked(viaStops(routeDraft.stops))
    setRouteDraft(null)
    setStopPick(null)
  }, [routeDraft, onRecordWalked])

  // --- The desktop chart and the route: one selection (PR #885 review) -----

  /**
   * The draft's stretch on the chart's own axis, or null while the draft
   * has no two ends yet. The entrance's span is start-to-resolved-end - the
   * same pair routeDrawing draws - so the chart tracks the "how far" slider
   * live; the editor's span is its ends.
   */
  const draftStretch = useMemo<ChartStretch | null>(() => {
    if (routeDraft === null) return null
    let a: number
    let b: number
    if (routeDraft.phase === 'editor') {
      if (routeDraft.stops.length < 2) return null
      a = routeDraft.stops[0].mile
      b = routeDraft.stops[routeDraft.stops.length - 1].mile
    } else {
      const end = routeDraft.fixedEnd ?? entranceEnd?.stop ?? null
      if (routeDraft.start === null || end === null) return null
      a = routeDraft.start.mile
      b = end.mile
    }
    if (a === b) return null
    return { startMile: Math.min(a, b), endMile: Math.max(a, b) }
  }, [routeDraft, entranceEnd])

  /** A profile-axis mile as a route stop: unnamed - a chart mile has no name
   *  - and drawable through the same anchor carry every distance-derived stop
   *  uses. Lives here rather than with the chart because what it builds is a
   *  route stop (#991). */
  const chartStop = useCallback(
    (mile: number): RouteDraftStop => ({
      mile,
      clientMile: anchoredClientMile(mile, mileAnchors),
    }),
    [mileAnchors],
  )

  /**
   * The chart's drag, when a draft is already open: re-stretch it. The ends
   * move, destinations still inside survive, the walk's direction stands
   * (lib/route.ts's restretchStops). On the entrance it answers both of that
   * screen's questions at once, so it lands straight on the editor the way
   * "Use this stretch" does.
   */
  const restretchToMiles = useCallback(
    (startMile: number, endMile: number) => {
      const lo = chartStop(startMile)
      const hi = chartStop(endMile)
      if (lo.mile === hi.mile) return
      setRouteDraft((draft) => {
        if (draft === null) return draft
        if (draft.phase === 'editor')
          return withStops(draft, restretchStops(draft.stops, lo, hi))
        return { phase: 'editor', stops: draft.south ? [hi, lo] : [lo, hi], history: [] }
      })
      // The picker's slot may name a stop the re-stretch just removed.
      setStopPick(null)
    },
    [chartStop],
  )

  /** The chart's direction toggle, while a draft is open: turn the ROUTE
   *  around, which is what walking it the other way means.
   *
   *  THROUGH withStops like every other editor edit - this was the path that
   *  did not, and #987 is the bug it caused. */
  const toggleDraftDirection = useCallback(() => {
    setRouteDraft((draft) => {
      if (draft === null) return draft
      if (draft.phase === 'entrance') return { ...draft, south: !draft.south }
      return withStops(draft, [...draft.stops].reverse())
    })
  }, [])

  /** "Plan this stretch": the chart's settled measurement becomes a route. */
  const openFromMiles = useCallback(
    (startMile: number, endMile: number, south: boolean) => {
      const lo = chartStop(startMile)
      const hi = chartStop(endMile)
      if (lo.mile === hi.mile) return
      setRouteDraft({ phase: 'editor', stops: south ? [hi, lo] : [lo, hi], history: [] })
    },
    [chartStop],
  )

  return {
    mapScreen: {
      routeDrawing,
      // Defined for the whole builder session so a stray tap can never
      // fall through to a waypoint card underneath - but the handler
      // only ACTS while the picker's map door is open (one tap, one
      // interpreter). Suppressed while the target sheet is up: the
      // sheet covers the surface that would explain the tap.
      onRouteTap: routeDraft === null || targetOpen ? undefined : handleStopMapTap,
      routeSheet: targetOpen ? null : stopPick !== null && stopPick.onMap ? (
        <RouteMapPickBar
          refusedTap={stopPick.refusedTap}
          units={units}
          onCancel={() => setStopPick({ ...stopPick, onMap: false, refusedTap: false })}
        />
      ) : stopPick !== null ? (
        <RouteStopPicker
          choices={routeStopChoices}
          pois={pois}
          previous={pickPrevious}
          south={pickSouth}
          removable={
            stopPick.slot.kind === 'replace' &&
            routeDraft !== null &&
            routeDraft.phase === 'editor' &&
            stopPick.slot.index > 0 &&
            stopPick.slot.index < routeDraft.stops.length - 1
          }
          units={units}
          onPick={applyPickedStop}
          onMapPick={() => setStopPick({ ...stopPick, onMap: true })}
          onRemove={handleRemoveStop}
          onClose={() => setStopPick(null)}
        />
      ) : routeDraft === null ? null : routeDraft.phase === 'entrance' ? (
        <RouteEntranceSheet
          start={routeDraft.start}
          ask={routeDraft.ask}
          miles={routeDraft.miles}
          days={routeDraft.days}
          south={routeDraft.south}
          end={
            entranceEnd === null
              ? null
              : ({
                  mile: entranceEnd.stop.mile,
                  ...(entranceEnd.stop.name === undefined
                    ? {}
                    : { name: entranceEnd.stop.name }),
                  ...(entranceEnd.kind === undefined ? {} : { kind: entranceEnd.kind }),
                } satisfies EntranceEnd)
          }
          reachMi={routeDraft.ask === 'long' ? (entranceEnd?.reachMi ?? null) : null}
          hoursTarget={DEFAULT_WALKING_HOURS}
          daysUsable={elevation !== null}
          gpsUsable={gpsClientMile !== null && gpsPlanMile !== null}
          refused={routeStopChoices.length === 0}
          units={units}
          onAsk={(ask) => patchEntrance({ ask })}
          onMiles={(miles) => patchEntrance({ miles })}
          onDays={(days) => patchEntrance({ days })}
          onSouth={(south) => patchEntrance({ south })}
          onPickStart={handlePickStart}
          onPickEnd={() =>
            setStopPick({ slot: { kind: 'end' }, onMap: false, refusedTap: false })
          }
          onClearEnd={() =>
            setRouteDraft((draft) =>
              draft !== null && draft.phase === 'entrance'
                ? { ...draft, fixedEnd: null }
                : draft,
            )
          }
          fixedEnd={routeDraft.fixedEnd}
          refusedTap={entranceRefusedTap}
          trailMiles={trailMiles}
          onUse={handleUseStretch}
          onTapToBuild={handleTapToBuild}
          onClose={handleRouteCancel}
        />
      ) : (
        <RouteStopsPanel
          stops={routeDraft.stops}
          legs={routeLegDisplays}
          direction={routeDirection(routeDraft.stops)}
          units={units}
          onEditStop={handleEditStop}
          onAddStop={handleAddStop}
          onUndo={routeDraft.history.length === 0 ? null : handleUndoRoute}
          refusedTap={editorRefusedTap}
          // Which of the two reasons the legs carry no times (#1039): the
          // panel cannot tell from the nulls, and the two send a hiker
          // looking for different things.
          unpriced={elevation === null ? 'no-profile' : 'unmeasured'}
          onBreakIntoDays={handleBreakIntoDays}
          onRecordWalked={handleRecordWalked}
          onClose={handleRouteCancel}
        />
      ),
    },
    draftStretch,
    draftLive: routeDraft !== null,
    draftSouth: routeDraft === null ? null : draftDirectionSouth(routeDraft),
    openRouteBuilder,
    handlePlanGap,
    handlePlanFrom,
    // The same three setters "close" means anywhere else. The two beyond
    // `routeDraft` are no-ops on this path - a plan can only be laid out from
    // the stops panel, which renders only with no picker over it - and are
    // here so that "the builder is closed" is one statement rather than two
    // that can drift.
    closeRouteBuilder: handleRouteCancel,
    openFromMiles,
    restretchToMiles,
    toggleDraftDirection,
  }
}

/** SOBO when the draft runs toward smaller miles, asked one way of both
 *  phases so the chart and the panel cannot disagree about direction. */
function draftDirectionSouth(draft: RouteDraftState): boolean {
  if (draft.phase === 'entrance') return draft.south
  return routeDirection(draft.stops) === 'SOBO'
}
