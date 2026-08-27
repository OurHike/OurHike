// What the phone's elevation ribbon is showing, and why (#910).
//
// The ribbon began as one thing: a field instrument, ten miles around a GPS
// fix, answering "what is ahead of ME" (features/ELEVATION_PROFILE.md). A desk
// asks a different question with the same shape - "what is this stretch of
// trail LIKE" - which is why the desktop chart (#135) needs no fix and rests on
// the whole trail. A hiker planning at their kitchen table on the phone they
// will carry is asking the desk's question, and until this module existed the
// phone answered it with nothing at all.
//
// So the ribbon now has FIVE things it can be showing, and exactly one of them
// is true at a time. The precedence, highest first, with what each is for:
//
//   planned-stretch  The route being built. The hiker is laying out this
//                    ground right now; nothing on screen is more relevant.
//   map-view         The trail inside the map's viewport, once the hiker has
//                    taken the map themselves. "Always in sync": if they
//                    panned to the Whites, the ribbon is the Whites.
//   todays-walk      Today end to end - the whole route on a day hike being
//                    followed, camp to camp on a trip (#1045). Below the two
//                    above because those are gestures the hiker just made and
//                    this is a mode they are in.
//   ahead            The ten-mile field window. Outranked by the three above
//                    because the first two are things the hiker just DID, and
//                    outranking the fix is what makes the sync visible.
//   whole-trail      Everything else, including the ordinary case of a phone
//                    that has never had a fix. The desk's resting view, here.
//
// **A FOLLOWED DAY HIKE STOPS THE FALL-THROUGH, and that half is a bug fix
// rather than a feature.** Before #1045 nothing in this module knew a day hike
// was being followed, so a hiker walking a Harriman loop - where the A.T. runs
// through the same woods, so `fix.mile` is a real number - got the A.T.'s
// ten-mile `ahead` window under a header about their loop. That is a picture
// of a different walk, announced as "ahead", on the band a hiker reads to
// judge daylight. #1041 chose "no ribbon at all" as the honest state and this
// keeps that promise: where today's walk is a route off the trail and there is
// no profile to draw it from, the ribbon is absent rather than borrowed.
//
// A TRIP DAY FALLS THROUGH AND A DAY HIKE DOES NOT, which is the one asymmetry
// here worth reading twice. Both are "today". But a trip day is a stretch of
// the SAME trail the fix window is cut from, so `ahead` under a trip is a
// different window of the hiker's own ground, correctly labelled - honest, if
// less useful. A day hike is different ground entirely, and there `ahead` is
// not a worse answer but a wrong one.
//
// **Only the fix window carries the upcoming-climb callout, and that is a
// definition rather than a preference.** upcomingClimb() finds the next >=300 ft
// ascent INSIDE THE WINDOW and clamps its start to the hiker's current mile,
// because the callout is a claim about work not yet done. On a planned stretch
// there is no walker, so there is no "not yet". On a map-driven or whole-trail
// domain there may be a walker but the domain is not their ground - at whole
// trail a 300 ft climb is under a pixel (see TrailRibbon.tsx's arithmetic for
// the same span), so a callout would caption terrain nobody can see.
//
// `todays-walk` carries none either, and for a third reason again: on a day
// hike the samples are the WALK's own, so upcomingClimb() - which reads the
// A.T. profile against an A.T. mile - has nothing to say about them, and
// saying it anyway would caption one walk with another's climb.
//
// What no domain carries: distance, climb or a time. Those belong to
// RouteStopsPanel and RouteEntranceSheet, which price the walk at the hiker's
// own pace through lib/route.ts's legFigures. A second figure derived a second
// way is the disagreement one source of truth exists to prevent. The ribbon
// contributes the shape.

import type {
  ElevationSample,
  RibbonSubject,
  UpcomingClimb,
} from '../chrome/ElevationRibbon'
import type { HikeDirection } from '../chrome/Header'
import type { ElevationProfile, MileWindow } from './elevationProfile'
import { ribbonSamples } from './elevationProfile'
import { envelopeSamples, type ChartDomain } from './chartProfile'
import { upcomingClimb } from './upcomingClimb'
/**
 * One waypoint as the next-up rail takes it (chrome/NextUpRail.tsx, #1054).
 *
 * This shape used to live in lib/waypointLanes.ts and gained `name` when the
 * three lanes became the rail: a lane pin was a glyph positioned by
 * percentage and never needed one, while a rail card names the place. The
 * name is optional because both source lists can hold a POI whose name is
 * empty upstream - the card falls back to the type's label rather than a
 * blank.
 */
export interface Waypoint {
  id: string
  type: string
  mile: number
  name?: string
}

/**
 * Which of the four the ribbon settled on. Carried out so the screen can say
 * so - the buttons differ, and a hiker who panned away from themselves needs a
 * way back.
 *
 * It IS ElevationRibbon's `RibbonSubject` rather than a parallel enum, because
 * what the ribbon shows and what it calls itself are one fact. Two enums let a
 * whole-trail ribbon go on announcing itself as a planned stretch, which is
 * precisely the bug this alias was written to close.
 */
export type RibbonSource = RibbonSubject

export interface RibbonView {
  samples: ElevationSample[]
  currentMile: number | null
  upcomingClimb?: UpcomingClimb
  source: RibbonSource
  /** What the ribbon is drawing, for the buttons that frame it on the map. */
  domain: ChartDomain
  /**
   * WHICH RULER `domain` AND `currentMile` ARE MEASURED WITH, which is not
   * decidable from `source` and is the reason this field exists.
   *
   * `trail` is a mile on the published centerline - what every POI in this
   * app carries and what four of the five subjects are cut from. `walk` is
   * miles from the hiker's first step on a route of their own (#1045), where
   * "mile 2" is a place in Harriman and has nothing to do with the A.T.'s
   * mile 2 in Georgia.
   *
   * `todays-walk` is BOTH, depending on which shape of today it is, so a
   * consumer reading the source alone would place a pin from Georgia under a
   * Harriman loop - see {@link ribbonLanes}, which is exactly where that would
   * have happened.
   */
  axis: 'trail' | 'walk'
}

/** Two samples is the least that has a shape; one is a dot and none is a blank
 *  ribbon reading as "no terrain here", which is a claim. */
const MIN_DRAWABLE_SAMPLES = 2

/**
 * Today's walk, when the hiker is on one - the domain #1045 asks the ribbon to
 * prefer over its ten-mile sliding window, in the two shapes "today" comes in.
 *
 * `trail` is a stretch of the published centerline on the PIPELINE axis: a
 * trip day, camp to camp, which `lib/plan.ts` already computes. It needs no
 * new data - the profile the ribbon has always drawn is the right one, cut at
 * the right two miles instead of at a window whose edges are arbitrary and can
 * hide the climb that decides whether somebody makes the shelter before dark.
 *
 * `route` is a day hike, on ITS OWN axis - miles from the hiker's first step
 * rather than from Springer - and carries its samples with it, because no cut
 * of the A.T. profile is a picture of a Harriman loop.
 *
 * **`samples: null` is a real state and the load-bearing one.** It means the
 * hiker is following a walk this phone cannot draw: no `trail_graph_profile.
 * json`, or an edge of the route the DEM never covered. The ribbon then draws
 * nothing at all rather than falling through to the A.T., which is what makes
 * the fall-through stop.
 */
export type TodaysWalk =
  | { kind: 'trail'; domain: ChartDomain }
  | {
      kind: 'route'
      samples: ElevationSample[] | null
      /** Miles walked so far, on the samples' own axis, or null when this
       *  phone does not know where the hiker is on their route. */
      alongMi: number | null
    }

export interface RibbonInputs {
  profile: ElevationProfile | null
  /** Today's walk, or null when the hiker is not on one. See {@link
   *  TodaysWalk} - and note that a `route` with null samples is NOT the same
   *  as no walk, because it suppresses the fix window and no walk does not. */
  todaysWalk: TodaysWalk | null
  /** The route draft's stretch, on the PIPELINE axis (#753) - the axis the
   *  profile and every route stop's `mile` share. */
  planStretch: ChartDomain | null
  /** The trail inside the map's viewport, PIPELINE axis, or null when the
   *  hiker has not taken the map (or nothing of the centerline is in view). */
  mapStretch: ChartDomain | null
  /**
   * The fix on the CLIENT index's axis, which is what the field window has
   * always been built from, and is deliberately unchanged here.
   *
   * It is the wrong axis in principle - HIKE_PLANNING.md Finding 1 - and the
   * fault predates this module: `ribbonWindow` slices a pipeline-axis profile
   * at a client-axis mile. Left exactly as it was rather than quietly
   * corrected, because correcting it moves the window under every hiker on the
   * trail and that is a change that deserves its own issue and its own before
   * and after, not a line in a ribbon refactor. Inside the fix window the two
   * agree with each other, which is why nobody can see it.
   */
  fixClientMile: number | null
  /** The fix on the PIPELINE axis, for the you-are-here rule on every OTHER
   *  domain - those are pipeline-axis spans, so a client mile would put the
   *  rule a few tenths off the ground it claims. */
  fixPlanMile: number | null
  /**
   * The field window, already computed by the shell.
   *
   * Passed in rather than derived here because the WAYPOINT LANES draw against
   * the same window and the two are one visual block: a hiker reads a pin as
   * sitting under the part of the profile it belongs to, which is only true
   * while both are windowing the same stretch. One window, computed once,
   * makes that true by construction instead of by two call sites agreeing.
   */
  fixWindow: MileWindow | null
  /** Which way the hiker is walking, or undefined until lib/hikeDirection.ts
   *  has enough movement to say. Only the climb callout reads it, and it
   *  declines to guess without one. */
  direction?: HikeDirection
}

/**
 * The one ribbon the phone should draw, or undefined when there is nothing
 * honest to draw at all - no profile in this download, or a domain that is
 * entirely DEM coverage gap.
 *
 * Undefined rather than an empty ribbon, because MapScreen omits the block
 * entirely on undefined and an empty ribbon reads as "no terrain here".
 */
export function ribbonView({
  profile,
  todaysWalk,
  planStretch,
  mapStretch,
  fixClientMile,
  fixPlanMile,
  fixWindow,
  direction,
}: RibbonInputs): RibbonView | undefined {
  // A followed day hike answers before the profile is even consulted, because
  // it does not need one: its samples came off the walk's own edges. A phone
  // with no A.T. profile in its download can still draw a Harriman loop.
  if (todaysWalk?.kind === 'route') return routeView(todaysWalk)

  if (profile === null || profile.distanceMi.length === 0) return undefined

  if (planStretch !== null) {
    return stretchView(profile, planStretch, fixPlanMile, 'planned-stretch')
  }
  if (mapStretch !== null) {
    return stretchView(profile, mapStretch, fixPlanMile, 'map-view')
  }

  if (todaysWalk !== null) {
    // A trip day, on the trail the profile measures. Falling through to the
    // fix window where this cannot be drawn is deliberate - see the header's
    // asymmetry paragraph.
    const today = stretchView(profile, todaysWalk.domain, fixPlanMile, 'todays-walk')
    if (today !== undefined) return today
  }

  if (fixClientMile !== null && fixWindow !== null) {
    // The field instrument, unchanged: the shell's asymmetric ten miles, its
    // own samples (no decimation - 640 samples is already about one per
    // pixel), and the climb callout that only exists here.
    const window = fixWindow
    const samples = ribbonSamples(profile, window)
    // A window that is entirely DEM gap. Rare, and the honest state is the
    // same as having no profile at all.
    if (samples.length < MIN_DRAWABLE_SAMPLES) return undefined

    const climb = upcomingClimb(profile, window, fixClientMile, direction)
    return {
      samples,
      currentMile: fixClientMile,
      ...(climb === undefined ? {} : { upcomingClimb: climb }),
      source: 'ahead',
      domain: { startMile: window.startMile, endMile: window.endMile },
      axis: 'trail',
    }
  }

  return stretchView(
    profile,
    {
      startMile: profile.distanceMi[0],
      endMile: profile.distanceMi[profile.distanceMi.length - 1],
    },
    fixPlanMile,
    'whole-trail',
  )
}

/**
 * A followed day hike, drawn from the samples the walk brought with it.
 *
 * The domain is the walk end to end - zero to its last sample - because that
 * is what "today" means here and what the storyboard asked for: "the whole
 * route on a day hike". No decimation and no envelope: lib/walkProfile.ts
 * explains why (~390 samples over six miles is already about one per device
 * pixel, which is the density the chart's envelope exists to reduce TO).
 *
 * Undefined on null samples, and that is the bug fix rather than a degraded
 * state - see the header. Undefined too on a single sample, which is a dot.
 */
function routeView(walk: {
  samples: ElevationSample[] | null
  alongMi: number | null
}): RibbonView | undefined {
  const samples = walk.samples
  if (samples === null || samples.length < MIN_DRAWABLE_SAMPLES) return undefined

  const endMile = samples[samples.length - 1].mile
  if (endMile <= 0) return undefined

  return {
    samples,
    // Only where this phone knows. Off-route, or before the first fix, the
    // rule would otherwise clamp to an edge and read as "you are at the start
    // of your walk" - the confident wrong answer about somebody's position
    // that stretchView refuses for the same reason.
    currentMile:
      walk.alongMi !== null && walk.alongMi >= 0 && walk.alongMi <= endMile
        ? walk.alongMi
        : null,
    source: 'todays-walk',
    domain: { startMile: 0, endMile },
    axis: 'walk',
  }
}

/**
 * Any domain that is not the fix window: drawn from its own span, with the
 * hiker marked only if they are genuinely standing on it.
 *
 * Decimated through the CHART's min-max envelope at the chart's own bucket
 * count. A thru-hike span is ~141,000 samples and a path with a hundred points
 * per pixel is decided by paint order rather than by terrain (lib/chartProfile.ts
 * has the reasoning, and why it is min-max rather than an average). The bucket
 * count is not re-tuned for the phone: 1,200 was sized for ~1,200 device pixels
 * and a 390 px phone at 3x is ~1,170 of them - the same order, so a second
 * constant here would be a number nobody measured. If a phone ribbon ever looks
 * visibly coarse, the fix is a measurement, not a guess. Short spans keep their
 * real samples; envelopeSamples only decimates past two per bucket.
 */
function stretchView(
  profile: ElevationProfile,
  stretch: ChartDomain,
  hereMile: number | null,
  source: RibbonSource,
): RibbonView | undefined {
  const startMile = Math.min(stretch.startMile, stretch.endMile)
  const endMile = Math.max(stretch.startMile, stretch.endMile)
  if (endMile <= startMile) return undefined

  const samples = envelopeSamples(profile, { startMile, endMile })
  if (samples.length < MIN_DRAWABLE_SAMPLES) return undefined

  return {
    samples,
    // Only where the hiker is genuinely on this ground. Outside it there is no
    // rule to draw: clamped to an edge by the SVG viewport it would read as
    // "you are at the start of this", a wrong claim about somebody's position
    // rather than an absent one.
    currentMile:
      hereMile !== null && hereMile >= startMile && hereMile <= endMile ? hereMile : null,
    source,
    domain: { startMile, endMile },
    axis: 'trail',
  }
}

/**
 * A POI as the lanes need it: `StoredPoi` and `SearchablePoi` both narrowed to
 * the three fields that place a pin. Optional `mile` is the load-bearing one -
 * a download published before #753 carries no pipeline mile, and a POI the
 * centerline index could not place carries no client one.
 */
export interface LanePoi {
  id: string
  name?: string
  type: string
  mile?: number
}

export interface RibbonLanes {
  points: Waypoint[]
  startMile: number
  endMile: number
}

/**
 * The widest domain the lanes still say something individual about.
 *
 * REASONED, from the one figure this repository already stands behind: AT
 * shelters average about eight miles apart (features/ELEVATION_PROFILE.md
 * Decision 1, which sizes the fix window's nine-mile look-ahead on it). A pill
 * swallows `COLLAPSE_THRESHOLD_PCT` of whatever window it is drawn in, so over
 * a span of S miles it stands for 0.015 x S miles of trail. Where that reaches
 * a lane's own spacing, that lane is all pills: it has stopped naming places
 * and started drawing density, which is a different picture and one nothing
 * here asked for. 8 / 0.015 is about 533 miles.
 *
 * This is what keeps the WHOLE-TRAIL domain from wearing three rows of pills -
 * 1.5% of the AT is 33 miles, and a pill standing for thirty-three miles of
 * trail is not a waypoint, it is a histogram bar.
 *
 * Two things it is not. It is not a claim that a 500-mile domain reads well; a
 * pill standing for seven miles of trail is coarse, and this only says where
 * the lanes stop being lanes at all. And eight miles is the ONLY lane spacing
 * this repository has a figure for: WATER, the lane a hiker planning an
 * evening is likeliest to be reading, has no census here, and published counts
 * (pipeline/README.md) suggest it is sparser than the shelters rather than
 * denser - which would make a tighter bound the right one. Until somebody
 * measures it off the published POI export (`export_poi.py`'s `attach_miles`,
 * #753) this is deliberately the generous end.
 */
export const MAX_LANE_SPAN_MI = 8 / 0.015

/**
 * The POIs along whatever the ribbon settled on, for the three lanes beneath
 * it (WIREFRAMES.md §1.4).
 *
 * #910 drew the lanes only under the fix window and dropped them under every
 * other domain, on arithmetic that is not in dispute: over a 60-mile plan a
 * pill swallows 0.9 mi. That is the reason the fix window is ten miles and not
 * forty - but on those other domains the alternative it was weighed against
 * does not exist. Nobody is choosing between a ten-mile lane and a sixty-mile
 * one; the choice is between a coarse lane and AN EMPTY STRIP under the
 * profile, which a hiker laying out an evening reads as "there is nothing
 * along here". A pill saying "3 water" over nine tenths of a mile is coarse
 * and true; silence about water is neither.
 *
 * **Which mile places a pin depends on which domain won, and that rule lives
 * here because it is the one thing about these lanes that can silently go
 * wrong.** `ahead` is windowed on the CLIENT index's axis (RibbonInputs says
 * why that is still so), and its lanes have always been placed from the same
 * index. Every other domain is a pipeline-axis span (#753), so its pins come
 * from the POI's own published mile. Crossing them puts a pin a few tenths off
 * the climb it is meant to sit under - HIKE_PLANNING.md Finding 1, on the one
 * surface where both axes are drawn at once.
 *
 * The window is the view's own `domain` rather than its samples' ends, and
 * that distinction is not academic: the profile is sampled every 25 m, so the
 * last sample at or before a domain's end falls short of it, and windowing on
 * samples dropped the stop a route was walking TO out of the SLEEP lane.
 *
 * Undefined - never empty lanes - when the pins cannot be placed honestly:
 *
 *   - No ribbon. There is nothing to sit under.
 *   - A ribbon on the WALK's own axis (#1045). Every POI this app holds
 *     carries a mile on the published centerline, and a followed day hike's
 *     domain is miles from the hiker's first step - so "mile 2" of a Harriman
 *     loop would collect the POIs at mile 2 of the A.T., in Georgia. Nothing
 *     about the loop would look wrong; the pins would just be from a
 *     different state. What would fix it is placing a walk's own POIs on its
 *     own axis, which lib/dayHikeCard.ts's bail-out arithmetic already
 *     demonstrates for junctions and which is its own issue.
 *   - A domain past MAX_LANE_SPAN_MI, where the lanes stop naming places.
 *   - A POI set with no usable mile in it at all: a download published before
 *     #753 on the pipeline side, a centerline index that placed nothing on the
 *     client side. Empty lanes there would report "nothing along here" about
 *     POIs the app cannot place anywhere, which is a claim. A set that HAS
 *     miles and genuinely holds nothing in the window draws empty lanes,
 *     because that emptiness is a fact about the trail.
 */
export function ribbonLanes(
  view: RibbonView | undefined,
  pois: { onPipelineAxis: readonly LanePoi[]; onClientAxis: readonly LanePoi[] },
): RibbonLanes | undefined {
  if (view === undefined) return undefined
  if (view.axis === 'walk') return undefined

  const { startMile, endMile } = view.domain
  if (endMile - startMile > MAX_LANE_SPAN_MI) return undefined

  const onAxis = view.source === 'ahead' ? pois.onClientAxis : pois.onPipelineAxis

  const points: Waypoint[] = []
  let anyPlaced = false

  for (const poi of onAxis) {
    if (poi.mile === undefined) continue
    anyPlaced = true
    if (poi.mile < startMile || poi.mile > endMile) continue
    points.push({ id: poi.id, type: poi.type, mile: poi.mile, name: poi.name })
  }

  return anyPlaced ? { points, startMile, endMile } : undefined
}
