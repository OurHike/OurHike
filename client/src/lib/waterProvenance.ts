// Whether a published water distance is a measurement or a steward's estimate,
// and the one mark this app puts in front of an estimate (#1728).
//
// THE FIGURE ARRIVES WITH ITS PROVENANCE, AND THE DISPLAY MAY NOT OUTRUN IT.
// ATC's Campsite Sustainability Index states how far water is from each
// shelter and campsite and, beside each figure, how it arrived at it:
// `FarOut` (measured against a water waypoint in ATC's official app),
// `NHDP_HR_Stream` and `NHDP_HR_Pond` (against USGS hydrography), or
// `OSA_Field_Estimate` - a steward's round number, typically 250 or 300 ft.
// Measured 2026-09-30 against pipeline/reference/water_distance.json: 42 of
// the 305 published distances are estimates, 33 of them close enough to sit
// on a card's nearby line. Until #1728 every one reached the phone as
// "water 250 ft", in the same voice as a figure measured to the foot, and
// the synthesized water point's own sentence said "ATC measured" over all
// of them. The pipeline now publishes the provenance as
// `water_distance_source` (export_poi.py), lib/trailData.ts keeps it beside
// the figure, and this file is where it becomes something a hiker can see.
//
// A TILDE, BY THE MAINTAINER'S CHOICE. Polled 2026-09-30 from a mock of three
// frames: A, the word "about" on every surface; B, a tilde in front of the
// figure; C, figures unchanged and only the water point's sentence saying
// it was estimated. The maintainer chose B. One character in front of the
// figure, on every surface that prints a stated water distance - the card's
// nearby sentence, the water point's meta line and chip, a day hike's stop
// rows - so a hiker reads one figure in one voice wherever they meet it.
//
// THE CAUTIOUS DEFAULT RUNS ONE WAY, and the two directions are different
// claims. A provenance this build does not know reads as an estimate:
// pipeline/build_water_distance.py's allowlist admits nothing without a
// human reading what it derives from, so a new value reaching here means the
// pipeline learned one before this set did, and a tilde on a measurement
// costs a hiker a little confidence in a good number while a bare figure on
// an estimate is the defect #1728 closed. An ABSENT provenance gets no mark:
// a phone whose download predates the column has none for any row, and
// marking all of them would assert "estimate" about the 263 that were
// measured. Absent means unknown, and the figure prints as it always has.
//
// @unvalidated: how a screen reader voices the tilde - "tilde", "about", or
// nothing at all - and so whether a hiker who cannot see the chip hears the
// caveat. Nobody has listened. What would settle it is one pass over the
// chip and the nearby sentence with VoiceOver and TalkBack.

import { formatShortDistance, MIN_STATED_FEET, type UnitSystem } from './units'

/**
 * CSI's `Nearest_Water_Source` values that are a measurement against a
 * mapped point - the three of the four values the pipeline publishes that
 * are not `OSA_Field_Estimate`. Anything the pipeline learns to publish later
 * reads as an estimate until this set says otherwise (see the header).
 */
export const MEASURED_WATER_SOURCES: ReadonlySet<string> = new Set([
  'FarOut',
  'NHDP_HR_Stream',
  'NHDP_HR_Pond',
])

/** The mark in front of an estimated figure: "~250 ft". */
export const ESTIMATE_MARK = '~'

/**
 * Whether a stated water distance with this provenance is an estimate.
 * Unknown reads as one; absent does not - the header has the two reasons.
 */
export function waterDistanceIsEstimate(source: string | undefined): boolean {
  return source !== undefined && !MEASURED_WATER_SOURCES.has(source)
}

/** The mark before an estimated figure, and nothing before any other. */
export function estimateMark(source: string | undefined): string {
  return waterDistanceIsEstimate(source) ? ESTIMATE_MARK : ''
}

/**
 * A stated water distance as every surface prints it: floored at the metre
 * lib/units.ts floors every stated distance at (a hiker walks zero feet to
 * nothing), in the hiker's units, with the mark where the provenance earns
 * one - "~250 ft" for a steward's estimate, "339 ft" for a measurement.
 */
export function formatWaterDistance(
  feet: number,
  source: string | undefined,
  units: UnitSystem,
): string {
  return `${estimateMark(source)}${formatShortDistance(Math.max(MIN_STATED_FEET, feet), units)}`
}
