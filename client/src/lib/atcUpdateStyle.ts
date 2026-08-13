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
// map. It is now 40px of ink, it carries a glow that fades out to nothing, and
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
 * `--space-10`, which is the SMALLEST step on the spacing scale that still
 * clears a waypoint pin. That is the derivation, and the word doing the work
 * in it is "smallest": this dot is drawn over every other mark on the map now
 * (map/style.ts), so it only has to out-read the pins it sits among - it does
 * not have to dominate them. Two passes tried to make size do more than that
 * and both looked like a wound on the map rather than a notice on the trail.
 *
 * Being covered was the larger half of the original fault and it is fixed by
 * the layer order, not by pixels. Size only has to carry the smaller half:
 * that a hiker's eye lands on the dot rather than on the shelter pin beside
 * it. Two pixels of clearance does that once nothing can be drawn on top.
 *
 * THIS IS THE FULL WIDTH OF THE INK, CASING INCLUDED, and measuring it that
 * way is the correction the second pass needed. MapLibre draws
 * `circle-stroke-width` OUTSIDE `circle-radius`, so a dot declared at 40
 * across actually covers 44 - the same 44 as the serious-warning pin it was
 * supposed to be staying under, which is why it still read a size too large
 * after being cut once. A pin's own 38px is its whole circle (`pinGeometry`
 * spends `rOuter` on the disc, its edge and its halo), so the two numbers are
 * only comparable when this one includes its edge too.
 *
 * THIS IS THE SIZE AT WALKING ZOOM, not at every zoom - see
 * {@link ATC_UPDATE_POINT_RADIUS_EXPRESSION}, which is where the third and
 * largest mistake in this sequence was. A number that is right in the hand is
 * absurd on a map of the whole corridor.
 */
export const ATC_UPDATE_POINT_DRAWN_WIDTH = 40

/**
 * What MapLibre is actually told, which is the ink minus its casing.
 *
 * Derived rather than declared, so the thing a reader can see on a screen -
 * the outer edge of the dot - is the number in the constant above, and the
 * spec value follows from it. Declared the other way round, the two drift the
 * moment the casing changes width.
 */
export const ATC_UPDATE_POINT_DIAMETER =
  ATC_UPDATE_POINT_DRAWN_WIDTH - CLOSURE_CASING_WIDTH * 2

/** Half of {@link ATC_UPDATE_POINT_DIAMETER}, which is what MapLibre wants. */
export const ATC_UPDATE_POINT_RADIUS = ATC_UPDATE_POINT_DIAMETER / 2

/**
 * The zooms the dot grows between, and what fraction of full size it is at
 * each.
 *
 * ONE SIZE AT EVERY ZOOM WAS THE REAL FAULT, and two rounds of shaving pixels
 * off the full-size number missed it because the number was never wrong in the
 * place it was chosen for. In the hand, walking, 40px of ink is a mark a hiker
 * can see and hit. On the whole-corridor view - Georgia to Maine on one screen,
 * around z5 - the same 40px is roughly the width of Maryland, and five notices
 * are five craters over four states. A screenshot of that is what settled it.
 *
 * The stops are read off the two things this dot shares a screen with:
 *
 *  - **z13 and up, full size.** Where map/poiLayers.ts stops interpolating and
 *    a waypoint pin is its whole 38px. This is the comparison every bound in
 *    src/test/atcAlertProminence.test.ts is about, so it has to be the zoom
 *    both are at full size.
 *  - **z12, 0.75.** `POI_PIN_MIN_ZOOM`, where waypoint pins first appear, and
 *    `POI_ICON_SIZE_EXPRESSION`'s own lower stop. Matching the fraction rather
 *    than picking one keeps the dot exactly its two pixels clear of a pin at
 *    every zoom where both are drawn, instead of only at the top. Both halves
 *    of this stop have moved since it was written: the zoom followed the seam
 *    from 9 to 12 when #593 measured it, and the fraction went 0.6 to 0.75 when
 *    the pins were asked to come up at the low end (#597's review). Neither can
 *    move here alone - src/test/atcAlertProminence.test.ts asserts this list
 *    equals POI_ICON_SIZE_EXPRESSION's stops, which is what stops the dot
 *    becoming the smaller mark at some middle zoom nobody screenshotted.
 *  - **z5, 0.4.** Below the pins entirely, where the only question is whether
 *    a hiker planning a week can see WHERE the ATC has posted something. About
 *    18px of ink answers that. It is deliberately NOT a further shrink to
 *    nothing: unlike the pins, this layer has no minzoom and never stops being
 *    drawn, and "zoomed out to plan" is exactly when someone wants to know.
 *
 * So this is the opposite of the choice map/warningLayers.ts makes for its pin
 * ("one size at every zoom, because a warning drawn small has stopped
 * outranking the pins around it"), and the difference is real rather than an
 * inconsistency. That argument is about a mark competing with OTHER MARKS,
 * which is a fixed contest at any zoom. The fault here was a mark competing
 * with THE GROUND IT IS DRAWN ON, and how much ground a pixel covers is
 * precisely what zoom means.
 */
export const ATC_UPDATE_POINT_ZOOM_STOPS: ReadonlyArray<[zoom: number, scale: number]> = [
  [5, 0.4],
  [12, 0.75],
  [13, 1],
]

/** A radius that grows with the camera, from a base at full size. */
function zoomScaledRadius(fullSize: number): unknown[] {
  return [
    'interpolate',
    ['linear'],
    ['zoom'],
    ...ATC_UPDATE_POINT_ZOOM_STOPS.flatMap(([zoom, scale]) => [zoom, fullSize * scale]),
  ]
}

/** What the circle layer is given instead of a number. */
export const ATC_UPDATE_POINT_RADIUS_EXPRESSION = zoomScaledRadius(
  ATC_UPDATE_POINT_RADIUS,
)

/**
 * How far the glow reaches past the dot, as a multiple of its radius.
 *
 * Half the dot's radius of fading red on every side - enough to catch an eye
 * that is not looking at that part of the screen, and short enough that five
 * of them on the whole-corridor view are five marks rather than one wash.
 *
 * It was 2, and that was the half of the first pass that actually read as too
 * big: a 96px circle of red around every notice is most of a phone's width
 * for one mile marker, and five of them on a 390px screen is a rash. The dot
 * is what says WHERE; the glow only has to say LOOK, and saying it louder
 * than the dot inverts the two.
 *
 * Measured off the radius rather than off the drawn width, so it tracks the
 * dot's own size: at 36 across the glow is 54, and it shrinks with the dot
 * rather than needing a second edit each time.
 */
export const ATC_UPDATE_HALO_SCALE = 1.5

export const ATC_UPDATE_HALO_RADIUS = ATC_UPDATE_POINT_RADIUS * ATC_UPDATE_HALO_SCALE

/** The glow on the same zoom ramp as the dot it surrounds.
 *
 *  Through the same helper rather than its own stops, so the two can never
 *  come apart - a glow that stayed put while the dot shrank would end up a
 *  translucent disc with a small mark in the middle of it, which is a
 *  different drawing entirely. */
export const ATC_UPDATE_HALO_RADIUS_EXPRESSION = zoomScaledRadius(ATC_UPDATE_HALO_RADIUS)

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
 * What is actually visible starts where the dot ends, at two thirds of the
 * radius, and the blur has already taken it to about a third of this by then -
 * fading to zero over the last ten pixels. Deliberately that faint: this layer
 * sits over the waypoint pins (map/style.ts), and a glow that hid a water
 * source to announce a bear warning two hundred feet away would have traded
 * one safety mark for another.
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
        'circle-radius': ATC_UPDATE_HALO_RADIUS_EXPRESSION as unknown as number,
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
    // for the reason ATC_UPDATE_POINT_DRAWN_WIDTH gives.
    //
    // Sized on a zoom ramp rather than fixed, which is the correction
    // ATC_UPDATE_POINT_ZOOM_STOPS records: the full size is right in the hand
    // and absurd on a map of the whole corridor, and no amount of shaving the
    // full-size number fixes a fault that is about the other end of the range.
    {
      id: ATC_UPDATE_POINT_LAYER_ID,
      type: 'circle',
      source: sourceId,
      paint: {
        'circle-color': ATC_UPDATE_COLOR,
        'circle-radius': ATC_UPDATE_POINT_RADIUS_EXPRESSION as unknown as number,
        'circle-stroke-color': ATC_UPDATE_CASING_COLOR,
        // Constant while the radius ramps, on purpose. The casing is what
        // holds the dot legible against pale paper and under red light, and a
        // 1px outline at corridor zoom would be a dot with no edge at exactly
        // the size where it needs one most.
        'circle-stroke-width': ATC_UPDATE_CASING_WIDTH,
      },
    },
  ]
}
