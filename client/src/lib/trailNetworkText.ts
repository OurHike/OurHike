// What the app says about not having the junction graph (#1049).
//
// ONE HOME FOR A SENTENCE TWO SCREENS PRINT. chrome/PlanKindSheet.tsx and
// screens/PlanHome.tsx both refuse a day hike when there is no network to
// route on, and screens/PlanHome.tsx's own comment used to say its copy was
// "PlanKindSheet's sentence, verbatim - and a test pins the two copies
// together so one cannot be reworded without the other". A pinning test is
// what you write when two copies exist; one function is what you write
// instead, and it cannot drift at all.
//
// EVERY SENTENCE HERE IS TRUE OF EXACTLY THE ABSENCE IT IS ABOUT, which is
// the whole reason this module exists. There used to be one sentence for all
// five, ending "It arrives with the next data sync." Four of the five never
// resolve by waiting - a build with no bucket, a release with no graph in it,
// a manifest naming no hash, bytes that fail it - and on production none of
// them does: #1048 is the graph published to UA and never promoted, so every
// hiker who tapped that door was told to wait for something that was never
// coming.
//
// That is #312's bug, which lib/positionLine.ts exists to have fixed, one
// surface over: one string covering six situations, most of which never
// resolve, telling somebody to keep waiting.
//
// SO NONE OF THESE PROMISES A TIME. Where an absence really is curable, the
// sentence says what cures it. Where it is not, the sentence stops rather
// than reaching for a reassuring clause - CLAUDE.md's rule about preferring
// the weaker true sentence to the stronger plausible one, applied to the four
// words that were doing the lying.

import type { TrailNetworkState } from './trailGraphData'

/**
 * Why a day hike cannot be built, in a sentence the hiker reading it can act
 * on - or, where they cannot, one that does not pretend they can.
 *
 * Takes the state minus `ready` rather than the whole union: there is no
 * sentence for having a graph, and a caller reaching for one has confused
 * this with a status line.
 */
export function trailNetworkRefusal(
  network: Exclude<TrailNetworkState, { kind: 'ready' }>,
): string {
  // The first moments of every launch, and a state of its own: "there isn't
  // one" over a door that is about to open reads as a door that never will.
  if (network.kind === 'looking') return 'Looking for the trail network…'

  switch (network.because) {
    case 'unconfigured':
      // A developer's build with no bucket in it. Named plainly rather than
      // dressed up as a hiker-facing state, because whoever sees this is the
      // person who can fix it.
      return 'This build has no data source, so there is nothing to build a day hike on.'
    case 'unreachable':
      // The one absence a connection cures, and the only one anything offers
      // a retry for.
      return 'The trail network has not downloaded yet, and it needs a connection.'
    case 'not-in-release':
      // NO PROMISE ABOUT WHEN. The graph arrives when somebody publishes one,
      // which is not something this phone can wait for (#1048).
      return 'This release does not include the trail network, so there is nothing to build a day hike on.'
    case 'unverifiable':
    case 'not-a-graph':
      // A refusal, said as one. lib/trailGraphData.ts will not route on
      // topology it cannot verify - "a route down a trail that is not there,
      // or a junction that does not exist" - and "not downloaded yet" over
      // that would tell a hiker the opposite of what happened.
      return 'The trail network this phone downloaded does not check out, so it is not being used.'
  }
}

/**
 * Whether this absence is one a hiker can do something about right now.
 *
 * The single question a "Try again" control should be asked. Derived from the
 * state rather than restated, so a control cannot appear beside a sentence
 * that says waiting will not help.
 */
export function canRetryTrailNetwork(network: TrailNetworkState): boolean {
  return network.kind === 'absent' && network.because === 'unreachable'
}
