// How an ATC trail update is drawn, and why it is not a second colour.
//
// The band's job is identical to a closure's - "do not walk down there, go
// around" - so it is drawn with identical weight: the same width, the same
// hard casing, the same colour. Only the RHYTHM differs, longer bars with
// longer gaps, so that the two read as the same kind of thing from the same
// distance while still being distinguishable side by side.
//
// THE COLOUR IS DELIBERATELY NOT DIFFERENT, and this is the decision worth
// recording because the obvious move is to make it different. #461 asks that
// an ATC update "must not look like an OurHike closure", and the temptation
// is to answer that on the canvas. It would be the wrong place. A second
// barrier colour on a safety map does not read as "a different organisation
// said this" - it reads as "a different severity", and a hiker who learns
// that one shade of barrier is softer than the other has learned something
// false. Both mean the trail is shut. Provenance is a question about WHO
// says so, and it is answered where a hiker can actually read an answer: the
// banner names the ATC first (lib/atcUpdates.ts) and the sheet carries their
// name, their date and a link to their page (chrome/AtcUpdateSheet.tsx).
//
// The same reasoning lib/closureStyle.ts applies to blazes applies here in
// miniature: the distinction that matters is structural rather than
// chromatic, because colour is the first thing to go in greyscale, in direct
// sun, and for a red-green colour-blind hiker.
//
// WHAT CHANGED, AND WHY IT IS NOT A SECOND SEVERITY EITHER. The point notice
// used to be a 10px dot drawn under the waypoint pins, which made the ATC's
// own word about the trail the smallest and most easily covered mark on the
// map. It is now 48px, it carries a glow that fades out to nothing, and
// map/style.ts draws this whole group last of all so nothing can sit on top
// of it. All three are SIZE and ORDER, not hue: the band and the dot are
// still the closure's exact red, so none of it says "this barrier is harder
// than that one". What it says is "there is something here" - which is the
// one thing a mark can say that a hiker cannot act on if they never see it.

import type { LayerSpecification } from '@maplibre/maplibre-gl-style-spec'
import {
  CLOSURE_CASING_COLOR,
  CLOSURE_CASING_WIDTH,
  CLOSURE_COLOR,
  CLOSURE_LINE_WIDTH,
} from './closureStyle'

export const ATC_UPDATE_LAYER_ID = 'atc-update-band'
export const ATC_UPDATE_CASING_LAYER_ID = 'atc-update-casing'
export const ATC_UPDATE_POINT_LAYER_ID = 'atc-update-point'
export const ATC_UPDATE_HALO_LAYER_ID = 'atc-update-halo'

/**
 * The diameter of a point notice, in CSS pixels.
 *
 * A POINT IS NOT A SHORT BAND, and this layer exists because it was drawn as
 * one. `trailSlice` widens a zero-length range to the two centerline vertices
 * that bracket it, so a shelter at mile 1,503.6 became a few dozen feet of
 * line - which at any zoom a hiker actually uses is nothing at all. Most of
 * what ATC publishes is like this: of the seven placeable updates live on
 * 2026-08-12, five were a single mile marker and one of the two ranges was
 * over the band ceiling. Drawn only as bands, the feature was invisible.
 *
 * IT WAS FIRST SIZED TO THE BAND'S WIDTH - a 10px dot, "a barrier seen end-on"
 * - and that was still too quiet by a long way. The dot came out SMALLER than
 * every pin it competes with on the same screen: a waypoint pin is 38px
 * (`POI_PIN_SIZE`, itself `--space-9`) and a serious-warning pin is 44px, so
 * the one mark on the map carrying the trail's own maintainer's word about the
 * trail was the smallest thing on it, and drawn UNDER both of them besides
 * (map/style.ts).
 *
 * `--space-12`, which is the next step up the spacing scale from the biggest
 * pin on the map rather than a number picked to win. That derivation is the
 * whole content of the size: an ATC notice must outrank a shelter and a
 * warning pin, and one step is what outranking costs.
 *
 * THIS DOES DEMOTE THE WARNING PIN from "the biggest thing on the map", which
 * poiIcons.ts's POI_PIN_SIZE comment and WIREFRAMES.md both state as a rule.
 * Recorded rather than smoothed over: the rule was written when nothing else
 * on the canvas was a safety mark, and it should be re-read now that two are.
 */
export const ATC_UPDATE_POINT_DIAMETER = 48

/** Half of {@link ATC_UPDATE_POINT_DIAMETER}, which is what MapLibre wants. */
export const ATC_UPDATE_POINT_RADIUS = ATC_UPDATE_POINT_DIAMETER / 2

/**
 * How far the glow reaches past the dot, as a multiple of its radius.
 *
 * Two, so the halo is the dot's own width of fading red on every side of it -
 * enough to catch an eye that is not looking at that part of the screen, and
 * short enough that five of them on the whole-corridor view are five marks
 * rather than one wash. The fade is what keeps that true: see
 * {@link ATC_UPDATE_HALO_BLUR}.
 */
export const ATC_UPDATE_HALO_SCALE = 2

export const ATC_UPDATE_HALO_RADIUS = ATC_UPDATE_POINT_RADIUS * ATC_UPDATE_HALO_SCALE

/**
 * Fully blurred, which in MapLibre means a gradient rather than an edge.
 *
 * `circle-blur: 1` is defined as "only the centerpoint is full opacity" - the
 * alpha ramps from the centre to nothing at the circle's edge. So this layer
 * has NO rim: what a hiker sees is red bleeding outward from under the dot and
 * dissolving, which is the point. A hard-edged translucent disc would read as
 * a second, softer barrier - a claim about an area ATC did not make.
 */
export const ATC_UPDATE_HALO_BLUR = 1

/**
 * The glow's opacity at its centre, which is under the dot and never seen.
 *
 * What is actually visible starts where the dot ends, at half the radius, and
 * the blur has already taken it to about half of this - roughly a quarter
 * opacity fading to zero. Deliberately that faint: this layer sits over the
 * waypoint pins (map/style.ts), and a glow that hid a water source to announce
 * a bear warning two hundred feet away would have traded one safety mark for
 * another.
 */
export const ATC_UPDATE_HALO_OPACITY = 0.55

/**
 * Long bars, long gaps - the same barrier tape at a slower cadence.
 *
 * In line-width units, like every MapLibre dasharray, and deliberately a
 * multiple of the closure rhythm's scale rather than an unrelated pattern: at
 * a glance the two are the same treatment, and only a close look separates
 * them. That is the intended reading order, since what a hiker must register
 * instantly is "barrier", and only then "whose".
 */
export const ATC_UPDATE_BAR_RHYTHM: [number, number] = [1.5, 0.75]

/** Re-exported so a test can hold the equality rather than the numbers, and
 *  so the coupling to lib/closureStyle.ts is visible from this file. An ATC
 *  band that quietly drifted narrower than a closure band would be exactly
 *  the severity distinction this module refuses to draw. */
export const ATC_UPDATE_LINE_WIDTH = CLOSURE_LINE_WIDTH
export const ATC_UPDATE_CASING_WIDTH = CLOSURE_CASING_WIDTH
export const ATC_UPDATE_COLOR = CLOSURE_COLOR
export const ATC_UPDATE_CASING_COLOR = CLOSURE_CASING_COLOR

export function buildAtcUpdateLayers(sourceId: string): LayerSpecification[] {
  return [
    // The glow, first and therefore underneath everything else here.
    //
    // Under the band and its casing on purpose. The halo is a soft claim -
    // "look over here" - and the band is a hard one - "you cannot walk down
    // there". Painting the soft one over the hard one would wash a barrier in
    // translucent red exactly where the two coincide, which is where the
    // barrier most needs to be crisp.
    //
    // It draws only around points, because a `circle` layer ignores lines. A
    // band needs no glow: it is already hundreds of pixels of barred red.
    {
      id: ATC_UPDATE_HALO_LAYER_ID,
      type: 'circle',
      source: sourceId,
      paint: {
        'circle-color': ATC_UPDATE_COLOR,
        'circle-radius': ATC_UPDATE_HALO_RADIUS,
        'circle-opacity': ATC_UPDATE_HALO_OPACITY,
        'circle-blur': ATC_UPDATE_HALO_BLUR,
        // No stroke, and that is the whole difference between a glow and a
        // disc. A stroked circle has an edge, and an edge here would draw a
        // boundary around ground ATC said nothing about.
      },
    },
    {
      id: ATC_UPDATE_CASING_LAYER_ID,
      type: 'line',
      source: sourceId,
      layout: { 'line-cap': 'butt', 'line-join': 'round' },
      paint: {
        'line-color': ATC_UPDATE_CASING_COLOR,
        'line-width': ATC_UPDATE_LINE_WIDTH + ATC_UPDATE_CASING_WIDTH * 2,
      },
    },
    {
      id: ATC_UPDATE_LAYER_ID,
      type: 'line',
      source: sourceId,
      layout: { 'line-cap': 'butt', 'line-join': 'round' },
      paint: {
        'line-color': ATC_UPDATE_COLOR,
        'line-width': ATC_UPDATE_LINE_WIDTH,
        'line-dasharray': ATC_UPDATE_BAR_RHYTHM,
      },
    },
    // Points, from the same source. A `line` layer ignores Point features and
    // a `circle` layer ignores lines, so one source can carry both geometries
    // and the tap has one place to look - which is why this is a third layer
    // rather than a second source.
    //
    // A circle rather than an icon, deliberately: an icon is an image to
    // register and a sprite to keep in step, and both are failure modes
    // (map/warningLayers.ts carries that cost for the warning pin). A dot in
    // the band's colour, with the band's casing as its stroke, is the same
    // treatment at a single mile - only much larger than the band is wide,
    // for the reason ATC_UPDATE_POINT_DIAMETER gives.
    //
    // One size at every zoom, like the warning pin and unlike the waypoints,
    // which interpolate down to 0.6 as they approach their minzoom. Zoomed out
    // to plan a week is exactly when someone wants to know where the ATC has
    // posted something, and a dot drawn small there has stopped outranking the
    // pins around it - which is the same argument warningLayers.ts makes, and
    // it does not weaken for being made twice.
    {
      id: ATC_UPDATE_POINT_LAYER_ID,
      type: 'circle',
      source: sourceId,
      paint: {
        'circle-color': ATC_UPDATE_COLOR,
        'circle-radius': ATC_UPDATE_POINT_RADIUS,
        'circle-stroke-color': ATC_UPDATE_CASING_COLOR,
        'circle-stroke-width': ATC_UPDATE_CASING_WIDTH,
      },
    },
  ]
}
