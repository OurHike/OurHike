// Every height and distance the app puts in front of a hiker, in the system
// they chose (features/UX_CUSTOMIZATION.md, "Metric units").
//
// THE RULE THIS MODULE EXISTS TO ENFORCE: nothing outside this file writes a
// unit. Not a ` ft`, not a ` mi`, not a conversion factor - a screen that
// formats its own numbers is a screen that keeps its own units, and a hiker
// reading 240 m of climbing on the ribbon and 790 ft in the callout beside it
// has to work out which one is lying. src/test/unitDisplay.test.ts fails the
// build over a new one, because a convention nobody can check is a convention
// that lasts until the next screen.
//
// STORAGE IS NOT DISPLAY. The published artifacts are imperial where the ATC's
// own data is imperial (mile markers, `elevation_ft`) and metric where the
// USGS 3DEP data is (the DEM is metres, whoever is reading it). Both stay
// exactly as they are: a converted number that reaches IndexedDB is a number
// that will be re-converted by the next build that reads it. Every function
// here takes the canonical unit and returns a string, which is the only shape
// that cannot be stored by accident.
//
// MILE MARKERS ARE NOT DISTANCES, and this module deliberately has no function
// for one. `mi 1,407.2` is WHERE somebody is on the Appalachian Trail - the
// reference every guidebook, shelter register and shuttle driver shares, and
// the number a hiker says out loud when a ranger asks. Converting it to
// `km 2,265.0` would hand a metric hiker a coordinate nobody else on the trail
// can read. features/UX_CUSTOMIZATION.md flagged this as an open call and
// Settings has been answering it in the app's own copy since the row was first
// drawn: mile markers stay in miles either way. The distance BETWEEN two of
// them is an ordinary distance and converts like any other.

import type { UnitSystem } from './userPreferences'

/** Re-exported so a display module takes its formatter and the type of the
 *  thing it formats from one import. The type itself belongs to the
 *  preferences model, which is where the backend's enum is mirrored - this is
 *  a convenience, never a second definition. */
export type { UnitSystem }

const FEET_PER_METRE = 3.280839895
const KM_PER_MILE = 1.609344
const METRES_PER_KM = 1000

/**
 * How precise a distance is stated, which is a decision about the underlying
 * fact rather than about arithmetic.
 *
 * - `tenths` - the default, and what a hiker paces in: "2.1 mi ahead". Always
 *   one decimal, including on a whole number, because these sit in a banner
 *   that re-renders as somebody walks and a figure that changes width every
 *   tenth of a mile draws the eye to nothing.
 * - `whole` - for spans big enough that a decimal invents precision the source
 *   does not have. ATC's Helene advisory runs 398 miles; "398.4" reads as a
 *   surveyed figure.
 * - `fine` - for the short ones, where a tenth rounds the fact away. The
 *   median blue-blazed spur is 385 ft, and one decimal makes it "0.1 mi".
 * - `trimmed` - one decimal at most, and none on a round number. For a figure
 *   computed from what a hiker typed: somebody who entered mile 100 and mile
 *   142 gets "42 mi" back, and the ".0" would be arithmetic they did not ask
 *   for shown as precision they did not claim.
 */
export type DistancePrecision = 'tenths' | 'whole' | 'fine' | 'trimmed'

interface Digits {
  min: number
  max: number
}

function group(value: number, { min, max }: Digits = { min: 0, max: 0 }): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: min,
    maximumFractionDigits: max,
  })
}

/**
 * A height, or an amount of climbing, from the canonical feet.
 *
 * Whole units in both systems. A metre is close enough to three feet that the
 * decimal a conversion produces is noise on a figure the DEM samples every
 * ~30 m anyway, and "+378.2 m" claims a survey nobody did.
 */
export function formatElevation(feet: number, units: UnitSystem): string {
  if (units === 'metric') return `${group(Math.round(feet / FEET_PER_METRE))} m`
  return `${group(Math.round(feet))} ft`
}

/**
 * A distance along the ground, from the canonical miles.
 *
 * Metric drops to metres below a kilometre rather than printing "0.08 km",
 * which is a number no walker says. Rounded to the nearest 10 m, because the
 * underlying fact - a spur length from ATC's inventory, a gap between two
 * mileposts - is not surveyed finer than that and a bare "84 m" would imply it
 * was.
 *
 * Imperial keeps miles all the way down, which is what the imperial hiker
 * already had and is deliberately unchanged by this module: the same numbers,
 * from one place. Feet below a tenth of a mile would read more naturally to
 * some, and it is a copy change to argue on its own evidence rather than one
 * to smuggle in under a metric switch.
 */
export function formatDistance(
  miles: number,
  units: UnitSystem,
  precision: DistancePrecision = 'tenths',
): string {
  if (units === 'metric') {
    const km = miles * KM_PER_MILE
    if (km < 1 && precision !== 'whole') {
      return `${group(Math.round((km * METRES_PER_KM) / 10) * 10)} m`
    }
    return `${group(km, digitsFor(km, precision))} km`
  }
  return `${group(miles, digitsFor(miles, precision))} mi`
}

/**
 * A RANGE of distances - "55-80 mi" - with one unit label for the pair.
 *
 * ROUNDED OUTWARD in the display's own unit: the low down, the high up.
 * `formatDistance`'s nearest-rounding is right for a measured distance and
 * wrong for the edges of an estimate, where narrowing the interval would be
 * the display claiming precision the samples do not have. Whole units
 * throughout, because a tenth of a mile on the edge of a 25-mile spread is
 * noise dressed as a figure.
 */
export function formatDistanceRange(
  lowMi: number,
  highMi: number,
  units: UnitSystem,
): string {
  const scale = units === 'metric' ? KM_PER_MILE : 1
  const suffix = units === 'metric' ? 'km' : 'mi'
  const digits: Digits = { min: 0, max: 0 }
  const low = Math.floor(lowMi * scale)
  const high = Math.ceil(highMi * scale)
  if (low >= high) return `${group(high, digits)} ${suffix}`
  return `${group(low, digits)}–${group(high, digits)} ${suffix}`
}

function digitsFor(value: number, precision: DistancePrecision): Digits {
  if (precision === 'whole') return { min: 0, max: 0 }
  if (precision === 'trimmed') return { min: 0, max: 1 }
  // Two decimals only where one would round the fact away entirely.
  if (precision === 'fine' && value < 0.1) return { min: 2, max: 2 }
  return { min: 1, max: 1 }
}

/**
 * A short distance across the ground, from the canonical feet: how far off the
 * blazes somebody has wandered, how far a pin sits from the trail.
 *
 * Its own function rather than `formatDistance` at a small value, because the
 * quantity arrives in feet - GPS displacement, a published offset - and
 * dividing by 5,280 on the way in only to multiply back out is a rounding trip
 * for nothing. Same output shape as `formatElevation` and a deliberately
 * different name: a call site asking for one wants "how far", and the reader
 * of that call site should not have to ask which.
 */
export function formatShortDistance(feet: number, units: UnitSystem): string {
  return formatElevation(feet, units)
}

/**
 * What the system is called, for a control that has to name it.
 *
 * Feet and metres rather than "imperial" and "metric": the hiker chose the
 * unit they read, and the system it belongs to is trivia. This is also the
 * question a hiker actually has - "can I get this in metres?" - and answering
 * it with a word from a customs schedule is how a setting goes unfound.
 */
export function unitSystemLabel(units: UnitSystem): string {
  return units === 'metric' ? 'Metres' : 'Feet'
}
