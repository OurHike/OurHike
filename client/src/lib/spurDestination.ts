// What to say about a blue-blazed spur when a hiker taps it.
//
// The pipeline resolves each spur's destination out to a loose 150 m and
// publishes how far the match actually was (pipeline/lib/spurs.py). Deciding
// whether that match is good enough to *name* is left here on purpose: 150 m
// captures 88% of spurs, 50 m captures 77% with far higher confidence, and
// which to believe is a judgement about real mismatches rather than a
// percentile. Keeping the call client-side means changing it costs a release
// rather than a re-export.
//
// THE DECISION THIS SUPPORTS is "is it worth walking down there, and how far
// back up?" - one a thru-hiker makes a dozen times a day. That is why the
// round trip is stated rather than left to be doubled mentally: the walk back
// up is the part that hurts, and spurs to water in particular tend to go down.
//
// NO LENGTH THRESHOLD, at either end. The median spur is 385 ft and the
// longest in ATC's data is 4.53 miles - a nine-mile round trip, which is
// precisely the case a hiker most needs told. Suppressing the numbers on short
// spurs would save nothing and make the sheet inconsistent. Any cutoff would
// be wrong on one side of itself.

import { naismithTime } from './naismith'
import { formatDistance, type UnitSystem } from './units'

/** How close the spur's far end must sit to a POI before that POI is named.
 *
 *  50 m, the confident end of the range. The failure modes are not
 *  symmetrical: an unnamed destination leaves a hiker exactly where the app
 *  left them before this feature existed, while a wrongly-named one sends
 *  someone down a hill expecting water that is somewhere else. Trading 11
 *  percentage points of coverage against that is worth it.
 *
 *  Raising this to 150 is a one-line change and needs no re-export - which is
 *  the whole reason the distance is published rather than thresholded away. */
export const NAME_DESTINATION_WITHIN_M = 50

const FEET_PER_MILE = 5280

export interface SpurRecord {
  name?: string | null
  length_ft?: number | null
  destination_poi_id?: string | null
  destination_distance_m?: number | null
  /** Where the spur joins the AT, in NOBO miles on the marker-calibrated
   *  axis every published mile shares (#136, pipeline/export_spurs.py's
   *  attach_junction_miles). Null when the pipeline could not tell the
   *  spur's two ends apart; absent when the release predates the field.
   *  Either way the sheet omits the line rather than guessing. */
  junction_mile?: number | null
}

export interface SpurDetail {
  /** The POI to name, or null when nothing confident enough was found. */
  destinationPoiId: string | null
  /** One-way distance in miles, or null when ATC published no length.
   *  The canonical number, unconverted - what a caller measures with. */
  distanceMi: number | null
  /** "0.2 mi each way" or "320 m each way", in the hiker's units, or null
   *  when there is no length to state. */
  distanceLabel: string | null
  /** "≈20m there and back", or null when there is no length. */
  roundTripLabel: string | null
}

/**
 * What the line-detail sheet can say about one spur.
 *
 * Every field is independently nullable because the underlying facts are
 * independently missing. A spur can have a surveyed length and no
 * destination, or a destination and no length, and the sheet shows whichever
 * lines it actually has.
 *
 * When nothing resolves, the sheet says nothing about a destination - not
 * "Unknown destination", which reads as a data error rather than the ordinary
 * situation it is for ~12% of spurs. Same restraint `describeStewards`
 * already applies to an unassigned trail section.
 */
export function describeSpur(
  spur: SpurRecord | undefined | null,
  units: UnitSystem = 'imperial',
  nameWithinM = NAME_DESTINATION_WITHIN_M,
): SpurDetail {
  const empty: SpurDetail = {
    destinationPoiId: null,
    distanceMi: null,
    distanceLabel: null,
    roundTripLabel: null,
  }
  if (!spur) return empty

  const distanceMi = usableLengthMi(spur.length_ft)

  return {
    destinationPoiId: namedDestination(spur, nameWithinM),
    distanceMi,
    distanceLabel:
      distanceMi === null
        ? null
        : `${formatDistance(distanceMi, units, 'fine')} each way`,
    roundTripLabel: distanceMi === null ? null : roundTrip(distanceMi),
  }
}

function namedDestination(spur: SpurRecord, nameWithinM: number): string | null {
  const { destination_poi_id: id, destination_distance_m: distance } = spur
  if (!id) return null
  // A resolved id with no distance cannot be judged, and an unjudgeable match
  // is not a confident one. Naming it anyway would mean trusting a link
  // precisely where the evidence for it went missing.
  if (typeof distance !== 'number' || Number.isNaN(distance)) return null
  return distance <= nameWithinM ? id : null
}

function usableLengthMi(lengthFt: number | null | undefined): number | null {
  // Zero-length is a real value in the raw data and is not a distance anyone
  // can walk, so it reads as "no length published" rather than as a spur you
  // are already standing at the end of.
  if (typeof lengthFt !== 'number' || !Number.isFinite(lengthFt) || lengthFt <= 0)
    return null
  return lengthFt / FEET_PER_MILE
}

function roundTrip(distanceMi: number): string {
  // ONE figure for both legs, not two.
  //
  // SPUR_TRAILS.md sketches this as "≈10 min down, ≈15 min back", which needs
  // the spur's own elevation profile. It does not exist: export_elevation.py
  // samples the centerline only, and sampling spurs too is explicitly not v1.
  // Without it, Naismith has no ascent to work with in either direction and
  // returns the identical number twice - so splitting the legs would print
  // "≈10m down, ≈10m back", which claims to have accounted for the climb back
  // up while doing nothing of the kind. Stating the round trip once is the
  // same information without the false implication.
  //
  // The doubling is still the point. The walk back up is what a hiker
  // under-counts, and it is worse on exactly the spurs that matter most -
  // water is downhill.
  //
  // naismithTime is reused rather than reimplemented because it already
  // refuses to give an arrival clock, which is precisely the false precision
  // to avoid here.
  return `${naismithTime({ distanceMi: distanceMi * 2, ascentFt: 0 })} there and back`
}
