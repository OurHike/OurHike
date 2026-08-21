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
// So the ribbon now has FOUR things it can be showing, and exactly one of them
// is true at a time. The precedence, highest first, with what each is for:
//
//   planned-stretch  The route being built. The hiker is laying out this
//                    ground right now; nothing on screen is more relevant.
//   map-view         The trail inside the map's viewport, once the hiker has
//                    taken the map themselves. "Always in sync": if they
//                    panned to the Whites, the ribbon is the Whites.
//   ahead            The ten-mile field window. Outranked by the two above
//                    because both are things the hiker just DID, and
//                    outranking the fix is what makes the sync visible.
//   whole-trail      Everything else, including the ordinary case of a phone
//                    that has never had a fix. The desk's resting view, here.
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
}

/** Two samples is the least that has a shape; one is a dot and none is a blank
 *  ribbon reading as "no terrain here", which is a claim. */
const MIN_DRAWABLE_SAMPLES = 2

export interface RibbonInputs {
  profile: ElevationProfile | null
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
  planStretch,
  mapStretch,
  fixClientMile,
  fixPlanMile,
  fixWindow,
  direction,
}: RibbonInputs): RibbonView | undefined {
  if (profile === null || profile.distanceMi.length === 0) return undefined

  if (planStretch !== null) {
    return stretchView(profile, planStretch, fixPlanMile, 'planned-stretch')
  }
  if (mapStretch !== null) {
    return stretchView(profile, mapStretch, fixPlanMile, 'map-view')
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
  }
}
