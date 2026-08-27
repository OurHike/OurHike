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
// map. It is now 40px of ink and map/style.ts draws this whole group last of
// all so nothing can sit on top of it. Both are SIZE and ORDER, not hue: the
// band and the burst are still the closure's exact red, so none of it says
// "this barrier is harder than that one". What it says is "there is something
// here" - which is the one thing a mark can say that a hiker cannot act on if
// they never see it.
//
// AND THE 40px WAS THEN SPENT AS A SOLID DISC, WHICH IS #1071. Every pixel of
// it was opaque, so the mark hid whatever it was drawn on - and a point notice
// is placed ON the centerline (map/atcUpdateLayers.ts), so what it hid was the
// trail the notice is about plus the shelter, ford or crossing the notice is
// about. Two earlier passes read that as a number to shave and both were
// shaving the wrong number: at ANY findable size, opaque ink covers ground.
// The mark is now a burst of red spokes around an open centre at the same
// 40px, so the ground reads through it - see ATC_NOTICE_BURST below, and
// the note below ATC_UPDATE_POINT_SIZE_EXPRESSION for the layer that went
// with it.

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

/**
 * The image id the point layer's `icon-image` resolves to.
 *
 * DECLARED HERE RATHER THAN BESIDE THE RASTERISER, which is the reverse of how
 * map/warningPin.ts does it, and the reason is the dependency direction. The
 * layer is built in this file and `lib/` does not import from `map/` - the same
 * constraint ATC_UPDATE_POINT_ZOOM_STOPS records for POI_PIN_MIN_SCALE. So the
 * id and the geometry live here, where the drawing decisions already are, and
 * map/atcNoticeMark.ts imports them to turn them into pixels.
 */
export const ATC_NOTICE_ICON_ID = 'atc-notice'

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
 * {@link ATC_UPDATE_POINT_SIZE_EXPRESSION}, which is where the third and
 * largest mistake in this sequence was. A number that is right in the hand is
 * absurd on a map of the whole corridor.
 *
 * IT SURVIVED #1071 UNCHANGED, deliberately. What was wrong with the disc was
 * that all 1,257 px² of it were opaque, not that it reached 40px - the reach is
 * what makes an eye land here rather than on the shelter pin beside it, and
 * src/test/atcAlertProminence.test.ts holds it against both pins.
 */
export const ATC_UPDATE_POINT_DRAWN_WIDTH = 40

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
 *  - **z9, 0.8.** Where waypoint pins first appear (`POI_PIN_MIN_ZOOM`), at
 *    the fraction they are drawn at there (`POI_PIN_MIN_SCALE`). Matching the
 *    pin's own scale is what keeps this dot its couple of pixels clear at
 *    every zoom where both are drawn, rather than only at the top.
 *
 *    **It was 0.6 and that briefly became a real regression** (#617). The seam
 *    moved out to z9 and pins were raised to 0.8 to stay legible there; a dot
 *    left at 0.6 is 24 px against a 30.4 px pin, so ATC's own safety notice
 *    would have been the SMALLER mark - the exact fault
 *    src/test/atcAlertProminence.test.ts was written to catch, and it caught
 *    it. Raising it to 0.8 also makes notices bigger across z5-z9 rather than
 *    smaller anywhere, which is the only direction this layer may move.
 *
 *    The number is repeated here rather than imported: `lib/` does not depend
 *    on `map/`, and the relationship is enforced by that test file, which
 *    exists precisely because neither half of the comparison can be made where
 *    either side lives.
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
  [9, 0.8],
  [13, 1],
]

/**
 * What the symbol layer is given instead of a number.
 *
 * `icon-size` rather than the `circle-radius` this used to be, so the numbers
 * are the zoom stops themselves rather than a radius multiplied through them.
 * The image is rasterised once at full size (map/atcNoticeMark.ts) and MapLibre
 * samples it down, which is exactly what map/poiLayers.ts already does to every
 * waypoint pin on the same ramp.
 */
export const ATC_UPDATE_POINT_SIZE_EXPRESSION = [
  'interpolate',
  ['linear'],
  ['zoom'],
  ...ATC_UPDATE_POINT_ZOOM_STOPS.flatMap(([zoom, scale]) => [zoom, scale]),
]

/**
 * The dark edge round the red, as a fraction of the mark's drawn radius.
 *
 * NOT the band's 2px `CLOSURE_CASING_WIDTH`, which is what the disc carried,
 * and the first render of the burst is why. A casing runs down BOTH sides of
 * every spoke, so 2px of it eats 4px out of each gap - and eight spokes inside
 * 40px have only about 7px of gap to spend in the first place. What came out
 * was a black disc with red spokes drawn on it: precisely the thing being
 * replaced.
 *
 * Two measurements, because the spokes were re-cut after that render and only
 * the first belongs to the picture: at the half-width that failed, the band's
 * casing left **1.7px** of daylight; at the shipped half-width below it would
 * still leave only **2.9px**, against **4.5px** with this hairline. So the
 * fatter casing is not survivable at either geometry, which is why the ratio is
 * a constant under test rather than a detail.
 *
 * `radius / 15` is map/poiIcons.ts's own `edgeWidth`, the hairline every
 * waypoint pin on this map already carries, so this is the map's existing edge
 * treatment rather than a number invented to make the gaps work. 1.33px at 40
 * across, and it scales with the mark rather than swamping it as the camera
 * pulls back.
 */
export const ATC_NOTICE_CASING_RATIO = 1 / 15

export const ATC_NOTICE_CASING_WIDTH =
  (ATC_UPDATE_POINT_DRAWN_WIDTH / 2) * ATC_NOTICE_CASING_RATIO

/**
 * The radius the RED reaches, which is the drawn radius less its casing.
 *
 * Derived in that direction, so the number a reader can see on a screen - the
 * outer edge of the ink - stays {@link ATC_UPDATE_POINT_DRAWN_WIDTH} and this
 * follows from it. It is the same derivation the disc's diameter used, and for
 * the same reason: declared the other way round the two drift the moment the
 * casing width moves.
 */
export const ATC_NOTICE_FILL_RADIUS =
  ATC_UPDATE_POINT_DRAWN_WIDTH / 2 - ATC_NOTICE_CASING_WIDTH

/** The shape of a point notice, as polar geometry rather than as a polygon. */
export interface AtcNoticeBurst {
  /** How many spokes radiate from the centre. */
  spokes: number
  /** Bearing of the first spoke, in radians. */
  phase: number
  /** Where a spoke starts, as a fraction of {@link ATC_NOTICE_FILL_RADIUS}. */
  innerRadius: number
  /** The centre dot's radius, as the same fraction. */
  hubRadius: number
  /** A spoke's angular half-width at `innerRadius`, in radians. */
  innerHalfWidth: number
  /** A spoke's angular half-width at the rim, in radians. */
  tipHalfWidth: number
}

/**
 * An open-centre burst: eight spokes round a ring of clear ground, with a small
 * dot on the coordinate itself.
 *
 * POLAR RATHER THAN A POLYGON, and that is what makes the casing exact. A
 * spoke's lateral half-width at radius `r` is an ANGLE, so adding `casing / r`
 * to it adds the same number of PIXELS of outline all the way along the spoke.
 * A scaled-up copy of the outline - the obvious way to do this with the polygon
 * rasteriser map/poiIcons.ts already has - would give an edge that was thin at
 * the hub and fat at the tip.
 *
 * THE NUMBERS, and what each is answering:
 *
 *  - **8 spokes.** The count is a trade between the two ends of the zoom ramp
 *    and it was picked off rendered specimens, not reasoned: eleven spokes look
 *    better in the hand and close up at z5, where the whole mark is 16px. Eight
 *    is the largest count whose gaps survive the bottom of the ramp.
 *  - **`innerRadius` 0.5.** Half the mark is the open ring. This is the whole
 *    point of the shape - what a notice is drawn ON (a shelter pin, the
 *    centerline, a ford) sits in that hole and stays readable.
 *  - **`hubRadius` 0.13.** A 2.4px dot, small enough to leave the hole open and
 *    large enough to say WHERE. Without it the mark is a ring, and a ring reads
 *    as drawn AROUND something rather than as marking it.
 *  - **`tipHalfWidth` 0.2 rad against a 0.785 rad pitch**, so a spoke covers
 *    just over half the pitch at the rim and the gap covers the rest. Measured
 *    on the shipped geometry at walking zoom: 7.5px of red against 4.5px of
 *    clear ground once the casing has taken its bite out of both sides.
 *    map/atcNoticeMark.test.ts computes both rather than trusting this comment.
 *  - **`innerHalfWidth` 0.13 rad**, narrower than the tip, so each spoke tapers
 *    outward. A parallel-sided spoke reads as a cog; a tapered one reads as
 *    radiating, which is the thing being said.
 *
 * Together these put 760.1px² of ink on the map where the disc put 1,256.6px²
 * - 60.5%, measured 2026-08-27 off the rendered alpha of the shipped image
 * rather than off this arithmetic. map/atcNoticeMark.test.ts re-measures it.
 */
export const ATC_NOTICE_BURST: AtcNoticeBurst = {
  spokes: 8,
  // Straight up. Any phase draws the same mark rotated, but a fixed one means
  // every notice on the map is the identical image rather than eight of them.
  phase: -Math.PI / 2,
  innerRadius: 0.5,
  hubRadius: 0.13,
  innerHalfWidth: 0.13,
  tipHalfWidth: 0.2,
}

/**
 * How wide a spoke and the clear ground beside it are at the rim, in CSS pixels.
 *
 * The property this whole change is bought with is a number of TRANSPARENT
 * pixels, so it is computed rather than asserted in prose - the first render of
 * the burst carried the band's 2px casing, which left 1.7px of daylight between
 * neighbouring spokes and produced a dark disc with red spokes on it. That
 * failure was invisible in the geometry and obvious in the picture, and this is
 * what lets a test see it too: put `CLOSURE_CASING_WIDTH` back and
 * lib/atcUpdateStyle.test.ts goes red on 2.9px, measured 2026-08-27.
 *
 * Takes a drawn width rather than reading the constant, so a caller can ask the
 * same question at the bottom of the zoom ramp - which is where the gaps are
 * scarce and where a spoke count is really decided.
 */
export function atcNoticeRimWidths(drawnWidth: number = ATC_UPDATE_POINT_DRAWN_WIDTH): {
  spoke: number
  gap: number
} {
  const casing = (drawnWidth / 2) * ATC_NOTICE_CASING_RATIO
  const rim = drawnWidth / 2 - casing
  const pitch = (Math.PI * 2) / ATC_NOTICE_BURST.spokes

  return {
    spoke: 2 * ATC_NOTICE_BURST.tipHalfWidth * rim,
    // Both sides of the gap lose a hairline to the casing of the spoke beside
    // it, which is the term the first pass left out.
    gap: (pitch - 2 * ATC_NOTICE_BURST.tipHalfWidth) * rim - 2 * casing,
  }
}

// THE GLOW IS GONE (#1071), and this note is the receipt. It is a comment
// rather than a constant because nothing is left to name - but a layer that
// simply vanishes from a diff takes its reasoning with it, and the reasoning is
// the part a later pass needs.
//
// There used to be a fourth layer here: a fully-blurred circle at 1.5x the
// dot's radius and 55% opacity, whose job was to catch an eye that is NOT
// looking at that part of the screen. It is deleted rather than dimmed, and the
// honest way to put that is that real conspicuity was given up.
//
// WHY IT COULD NOT SIMPLY STAY. A 54px wash of red behind an open burst is the
// solid disc back again in a softer spelling - the ground between the spokes
// would be washed exactly where the burst exists to let it through. Keeping
// both would have meant keeping neither.
//
// WHAT REPLACES IT IS SHAPE RATHER THAN AREA. Nothing else on this map is a
// radial burst: every waypoint and the serious-warning pin are discs
// (map/poiIcons.ts), and every closure and ATC band is a line. So the mark is
// still unlike its neighbours at a glance, and it keeps every other conspicuity
// property it had - the closure red, the 40px reach, being drawn over every
// other layer (map/style.ts), and `icon-allow-overlap` so the collision engine
// can never drop one.
//
// @unvalidated Nobody has watched a hiker find one of these on a phone, in sun,
// while walking. A specimen sheet rendered at z5/z9/z13 is what this decision
// was made on, and a specimen sheet cannot answer a question about peripheral
// vision. What would settle it is field use. If the burst turns out to be
// harder to find than the disc was, the fix is a glow back on a ZOOM RAMP -
// strong at corridor zoom where the mark is 16px and there is no detail to
// lose, faint in the hand where the spokes are large and the ground under them
// is what a hiker came for - and not one strength everywhere, which is the
// shape of the fault this change is fixing.

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
    // a `symbol` layer ignores lines, so one source can carry both geometries
    // and the tap has one place to look - which is why this is a third layer
    // rather than a second source.
    //
    // AN ICON, WHERE THIS FILE USED TO ARGUE FOR A CIRCLE. The old comment was
    // right about the cost - "an icon is an image to register and a sprite to
    // keep in step, and both are failure modes" - and map/atcUpdateLayers.ts
    // now carries that cost, the same one map/warningLayers.ts already carries
    // for the warning pin. What changed is that the cost bought nothing before
    // and buys the whole feature now: a `circle` cannot have a hole in it, and
    // the hole is the fix for #1071. There is no paint property that makes the
    // middle of a MapLibre circle transparent.
    //
    // `icon-allow-overlap`, for map/warningLayers.ts's reason exactly: a notice
    // dropped because a shelter pin got to that spot first is a notice nobody
    // was shown, and a hiker cannot tell that from there being none. It still
    // takes part in placement FOR everything else (`icon-ignore-placement`
    // stays at its default of false), so it pushes waypoints aside rather than
    // being pushed - which is the standing this layer already had as a circle,
    // since circles do not take part in collision at all.
    //
    // Sized on a zoom ramp rather than fixed, which is the correction
    // ATC_UPDATE_POINT_ZOOM_STOPS records: the full size is right in the hand
    // and absurd on a map of the whole corridor, and no amount of shaving the
    // full-size number fixes a fault that is about the other end of the range.
    {
      id: ATC_UPDATE_POINT_LAYER_ID,
      type: 'symbol',
      source: sourceId,
      layout: {
        'icon-image': ATC_NOTICE_ICON_ID,
        'icon-size': ATC_UPDATE_POINT_SIZE_EXPRESSION as unknown as number,
        'icon-allow-overlap': true,
        'icon-padding': 2,
      },
    },
  ]
}
