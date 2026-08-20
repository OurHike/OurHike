// What the sheet says about a highlight (#858).
//
// The same division lineDetail.ts and clubDetail.ts keep: every sentence is
// decided here, testably and without a canvas, and chrome/HighlightSheet.tsx
// only lays them out.
//
// THE NUMBERS ARE DERIVED HERE, NOT PUBLISHED
//
// features/CORRIDOR_VIEW.md: "Length, ascent, descent and Naismith time are
// not stored. They are derived on the phone from the elevation profile it
// already has, which keeps one number in one place and means a better profile
// improves every stretch without a republish." This is that derivation.
//
// ONE Naismith call, over the summed distance and ascent - not a sum of
// per-leg times. The rule is linear in both inputs, so the two are exactly
// equal, and this way the 5-minute step and the `≈` happen once at the end.
// That is the property naismithMinutes exists to protect: rounding each leg
// and then summing would let the printed total drift from the printed legs by
// up to five minutes a leg.
//
// THE PROFILE IS THE A.T.'s, AND THAT LIMITS WHAT CAN BE CLAIMED
//
// export_elevation.py samples the A.T. centerline. A highlight may cross trails
// (the 2026-08-19 decision), and a leg on a side trail has no profile at all -
// so an ascent summed over only the A.T. legs would be a total that silently
// leaves out the climbing on the others.
//
// So: distance is always available, because it comes from the legs' own
// mileposts. Ascent and time are offered ONLY when every leg is measurable.
// Where one is not, the sheet shows the distance and says nothing about
// climbing - which is CLAUDE.md's "omit rather than guess" applied to the
// number a hiker would plan their evening around.
//
// WHAT IS STILL WRONG, AND KNOWN TO BE
//
// Naismith cannot see terrain. #851 is open about it, and it is not
// hypothetical here: Mahoosuc Arm is one of the ten entries #856 published and
// is the climb out of Mahoosuc Notch, where the rule reads badly low. Until
// that issue is decided, `cautionLine` is the hook - a field on the record and
// a line on the sheet - so whichever way it goes is a small change rather than
// a rewrite.

import { cumulativeGainOverProfile, type ProfileSample } from './elevationGain'
import { profileSamples, type ElevationProfile } from './elevationProfile'
import {
  NAMED,
  PUBLISHED,
  VISITED,
  highlightMiles,
  strongestBasis,
  type Highlight,
} from './highlights'
import { STANDARD_PACE, paceEstimate, type PaceProfile } from './pace'
import { formatDistance, formatElevation } from './units'
import type { UnitSystem } from './units'
import { walkedWithin, type MileRange } from './walkedMiles'

/** The trail the published elevation profile measures. Legs on anything else
 *  cannot be climbed-measured, which is what `derivedLine` turns on. */
export const PROFILED_TRAIL = 'AT'

export interface HighlightDetail {
  heading: string
  /** "Appalachian Trail · mi 705.6 – 709.1", or "Three trails · 8.9 mi". */
  subtitle: string
  /** "3.5 mi · 1,740 ft ascent · ≈2 h", or "3.5 mi" alone where the climbing
   *  cannot be measured. Never null: the distance comes from the legs' own
   *  mileposts, so there is always at least that much to say. */
  derivedLine: string
  /** Says the ascent and the time were worked out here rather than published.
   *  Null where they were not shown at all, since the distance above them does
   *  not come from the profile. */
  derivedSourceLine: string | null
  /**
   * "was ≈2h 10m · 1.3× standard" (#880/#851).
   *
   * Null at the standard pace, and null whenever no time is shown at all -
   * there is nothing to have adjusted. When it is non-null the sheet MUST
   * render it: an adjusted time without its baseline is the failure #851 is
   * about.
   */
  paceRelativeLine: string | null
  /** One per leg, and ONLY for a highlight with more than one - a single-leg
   *  highlight would just repeat its own subtitle. */
  legLines: string[]
  /** "On our list", "Listed by ATC" - the chip. Null where the record claims
   *  no basis this build can word. */
  basisLabel: string | null
  /** The sentence under it, in the voice that basis earns. */
  basisLine: string | null
  /** "OurHike, 20 Aug 2026". Null where the record carries no citation. */
  citationLine: string | null
  /** "Maintained by RATC." Null where no club is recorded. */
  clubLine: string | null
  /** "You have walked 1.2 mi of this." Null where they have walked none. */
  walkedLine: string | null
  /** A warning that the time estimate does not fit this ground (#851). Null
   *  until the record carries one - no highlight does today. */
  cautionLine: string | null
}

/** How each basis is worded. The whole of "the app never says popular
 *  flatly": each sentence names who is making the claim and how strong it is,
 *  and no two are ever shown at once (lib/highlights.ts's strongestBasis). */
const BASIS_LABELS: Record<string, string> = {
  [NAMED]: 'On our list',
  [PUBLISHED]: 'Listed by ATC',
  [VISITED]: 'Hikers have been here',
}

const BASIS_SENTENCES: Record<string, string> = {
  // Editorial, and it says so - the weakest claim, worded as one.
  [NAMED]: 'We put this on a list of well-known routes. Editorial, not a measurement.',
  // Attributable to ATC rather than to us, which is the whole point of the
  // basis being separate.
  [PUBLISHED]: 'The Appalachian Trail Conservancy lists this as a day hike.',
  // Carefully NOT "this is popular". It measures where hikers using this app
  // sent something, is biased toward where the app has users, and lags.
  [VISITED]: 'Hikers using OurHike have sent reports, photos or thanks from here.',
}

function formatMileMarker(mile: number): string {
  return mile.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
}

/** "20 Aug 2026" from an ISO day, or null for anything unparseable - never
 *  today's date, which would be a claim nobody made. */
function formatReviewed(iso: string): string | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null
  const [year, month, day] = iso.split('-').map(Number)
  const months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ]
  const name = months[month - 1]
  if (name === undefined) return null
  return `${day} ${name} ${year}`
}

/** Whether every leg sits on the trail the profile measures. */
export function everyLegIsProfiled(highlight: Highlight): boolean {
  return highlight.legs.every((leg) => leg.trail === PROFILED_TRAIL)
}

/**
 * Confirmed ascent over every leg, or null when it cannot be had honestly.
 *
 * Null rather than a partial sum: a highlight that leaves the A.T. would
 * otherwise report only the climbing it happens to have a profile for, which
 * is a smaller number presented as a total - wrong in the optimistic
 * direction, which FEATURES.md names as the dangerous one.
 */
export function highlightAscentFt(
  highlight: Highlight,
  profile: ElevationProfile | null,
): number | null {
  if (profile === null || !everyLegIsProfiled(highlight)) return null
  let total = 0
  for (const leg of highlight.legs) {
    const samples: ProfileSample[] = profileSamples(profile, {
      startMile: leg.startMile,
      endMile: leg.endMile,
    })
    // A leg the profile does not reach yields no samples, and a gain of zero
    // over real ground is a claim rather than an absence.
    if (samples.length === 0) return null
    total += cumulativeGainOverProfile(samples)
  }
  return total
}

function subtitleFor(highlight: Highlight, units: UnitSystem): string {
  const legs = highlight.legs
  if (legs.length === 1) {
    const leg = legs[0]
    const trail = leg.trail === PROFILED_TRAIL ? 'Appalachian Trail' : leg.trail
    return `${trail} · mi ${formatMileMarker(leg.startMile)} – ${formatMileMarker(leg.endMile)}`
  }
  const distance = formatDistance(highlightMiles(highlight), units)
  const trails = new Set(legs.map((leg) => leg.trail))
  // Several legs on ONE trail - two disjoint A.T. segments, or an out-and-back
  // recorded as two. Naming the trail beats counting it: "1 trails" is not a
  // sentence, and the mile range is still no good because the legs have a gap
  // between them that this would otherwise claim as walked.
  if (trails.size === 1) {
    const only = legs[0].trail
    return `${only === PROFILED_TRAIL ? 'Appalachian Trail' : only} · ${distance}`
  }
  // Mile markers are meaningless across trails - they are different scales -
  // so a cross-trail highlight leads with how many and how far, and the legs
  // themselves carry their own ranges below.
  return `${trails.size} trails · ${distance}`
}

function legLinesFor(highlight: Highlight, units: UnitSystem): string[] {
  if (highlight.legs.length < 2) return []
  return highlight.legs.map((leg) => {
    const trail = leg.trail === PROFILED_TRAIL ? 'Appalachian Trail' : leg.trail
    const miles = formatDistance(leg.endMile - leg.startMile, units)
    return `${trail} — ${miles}`
  })
}

/**
 * Everything the sheet can say about one highlight.
 *
 * Every field is independently nullable because the underlying facts are
 * independently missing, and each absent fact costs its own line rather than
 * the sheet - the shape describeSpur() and buildClubDetail() both keep.
 */
export function buildHighlightDetail(
  highlight: Highlight,
  profile: ElevationProfile | null,
  units: UnitSystem,
  walked: readonly MileRange[] = [],
  pace: PaceProfile = STANDARD_PACE,
): HighlightDetail {
  const distanceMi = highlightMiles(highlight)
  const ascentFt = highlightAscentFt(highlight, profile)

  const derived = (() => {
    const distance = formatDistance(distanceMi, units)
    if (ascentFt === null) {
      // Distance alone still needs the profile to have said nothing wrong -
      // it comes from the mileposts, so it is always honest. What is dropped
      // is the climbing and the time - and with the time, anything to say
      // about a pace, since there is no estimate to have adjusted.
      return { line: distance, relative: null }
    }
    // ONE call over the summed distance and ascent, not a sum of per-leg
    // times. The rule is linear in both inputs - and stays linear under the
    // hiker's own coefficients, which only replace its two constants - so the
    // two are exactly equal, and the 5-minute step and the `≈` happen once at
    // the end. The baseline rides along in the same object, so this sheet
    // cannot print an adjusted time and forget to say so.
    const estimate = paceEstimate({ distanceMi, ascentFt }, pace)
    return {
      line: `${distance} · ${formatElevation(ascentFt, units)} ascent · ${estimate.text}`,
      relative: estimate.relativeLine,
    }
  })()

  const basis = strongestBasis(highlight)
  const citation = basis === null ? undefined : highlight.citations[basis]
  const reviewed = citation === undefined ? null : formatReviewed(citation.reviewed)

  const walkedMiles = highlight.legs.reduce(
    (sum, leg) =>
      sum + walkedWithin(walked, { startMile: leg.startMile, endMile: leg.endMile }),
    0,
  )

  return {
    heading: highlight.name,
    subtitle: subtitleFor(highlight, units),
    derivedLine: derived.line,
    paceRelativeLine: derived.relative,
    // ONLY where the profile actually produced something. With the ascent
    // dropped, the line above is a distance summed from the legs' own
    // mileposts and the profile contributed nothing to it - so this sentence
    // would be provenance for a number it did not produce, which is the
    // display outrunning its source. Said whenever it IS true, because
    // "worked out here" is what makes the figure improve silently when the
    // profile does, and what stops it reading as one somebody published.
    derivedSourceLine:
      ascentFt === null ? null : 'Worked out on your phone from the elevation profile.',
    legLines: legLinesFor(highlight, units),
    basisLabel: basis === null ? null : (BASIS_LABELS[basis] ?? null),
    basisLine: basis === null ? null : (BASIS_SENTENCES[basis] ?? null),
    citationLine:
      citation === undefined || citation.by === ''
        ? null
        : reviewed === null
          ? citation.by
          : `${citation.by}, ${reviewed}`,
    clubLine: highlight.club === null ? null : `Maintained by ${highlight.club}.`,
    walkedLine:
      walkedMiles < 0.05
        ? null
        : `You have walked ${formatDistance(walkedMiles, units)} of this.`,
    cautionLine: highlight.caution === '' ? null : highlight.caution,
  }
}
