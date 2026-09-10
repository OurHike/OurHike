// How an ATC trail update is drawn, and why it is not a second colour.
//
// The band's job is identical to a closure's - "do not walk down there, go
// around" - so it is drawn with identical weight: the same width, the same
// barrier tape, the same colour. Only the CADENCE differs, the identical tape
// at twice the scale, so that the two read as the same kind of thing from the
// same distance while still being distinguishable side by side.
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
// name, their date and a link to their page (chrome/OrgNoticeSheet.tsx).
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
// #1071 made the mark a burst of red spokes around an open centre at the same
// 40px, so the ground read through it.
//
// AND SINCE 2026-09-10 THE SHAPE IS THE HAZARD TRIANGLE, on the maintainer's
// call ("adopt the warning icon we made" - asked which mark was meant, the
// answer was map/warningPin.ts's triangle, for the ATC notice marks too). It
// is the serious-warning pin's own glyph drawn BARE - no disc, no halo - in
// the closure red at the same 40px, so what #1071 bought survives: the
// triangle is a band with an exclamation in an empty middle, and the ground
// reads through the hole (map/atcNoticeMark.ts, and its test measures the
// ink). What changed is the vocabulary: one triangle means "look", and the
// same triangle on a 44px disc means a person confirmed something serious
// here - two weights of one mark rather than a burst nothing else on the map
// shared a shape with.

import type { LayerSpecification } from '@maplibre/maplibre-gl-style-spec'
import {
  CLOSURE_CASING_COLOR,
  CLOSURE_CASING_WIDTH,
  CLOSURE_COLOR,
  CLOSURE_TAPE_CADENCE,
  CLOSURE_TAPE_WIDTH,
  type TapeCadence,
} from './closureStyle'

export const ATC_UPDATE_LAYER_ID = 'atc-update-band'

/** The ATC tape's own image id. A second image rather than a second colour,
 *  for the reason the header gives at length: the cadence is what separates
 *  the two feeds, and nothing about hue or weight may. */
export const ATC_TAPE_IMAGE_ID = 'atc-update-tape'
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
 *  - **Below z9, not drawn at all** - the maintainer's call of 2026-09-08
 *    that the opening camera shows trail lines only (#1292). There WAS a
 *    third stop here, 0.4 at z5, on the argument that a hiker planning a
 *    week wants to see where the ATC has posted something. On the
 *    whole-corridor camera that read as a rash of two dozen marks along the
 *    southern half (the built app against the production bucket, that day's
 *    conditions), indistinguishable at that scale from the waypoints #1135
 *    took off the view - and 18px of ink over a hundred trail miles said
 *    "somewhere here" and nothing a hiker could act on. The Trail notices
 *    list carries every notice at every zoom, and from the seam up the mark
 *    draws exactly as before.
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
  [9, 0.8],
  [13, 1],
]

/**
 * Where the notice point stops being drawn, going out: the pin seam
 * (map/poiLayers.ts's POI_PIN_MIN_ZOOM), since #1292 - below it the map
 * draws trail lines only. The number is repeated here rather than imported,
 * for the reason the 0.8 above gives: `lib/` does not depend on `map/`, and
 * src/test/atcAlertProminence.test.ts holds the two equal.
 */
export const ATC_UPDATE_POINT_MIN_ZOOM = 9

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
 * `radius / 15` is map/poiIcons.ts's own `edgeWidth`, the hairline every
 * waypoint pin on this map already carries, so this is the map's existing
 * edge treatment rather than a number invented for this mark: 1.33px at 40
 * across, and it scales with the mark rather than swamping it as the camera
 * pulls back.
 *
 * NOT the band's 2px `CLOSURE_CASING_WIDTH`, and the burst of #1071 is why
 * that is a constant under test rather than a detail: a casing runs down
 * BOTH sides of every edge, and with the band's casing the burst's first
 * render was a black disc with red spokes on it (1.7px of daylight between
 * spokes, measured 2026-08-27). The triangle has fewer edges than eight
 * spokes had, but its band is 3.7px of red at walking zoom and would lose
 * most of that to a 2px outline on each side for the same reason.
 */
export const ATC_NOTICE_CASING_RATIO = 1 / 15

export const ATC_NOTICE_CASING_WIDTH =
  (ATC_UPDATE_POINT_DRAWN_WIDTH / 2) * ATC_NOTICE_CASING_RATIO

/**
 * The square the glyph fills, in CSS pixels: the drawn width less a casing on
 * each side.
 *
 * Derived in that direction, so the number a reader can see on a screen - the
 * outer edge of the ink - stays {@link ATC_UPDATE_POINT_DRAWN_WIDTH} and this
 * follows from it. It is the same derivation the disc's diameter and the
 * burst's fill radius used, and for the same reason: declared the other way
 * round the two drift the moment the casing width moves. The triangle's
 * outer ring reaches 0.98 of its box (map/warningPin.ts), so the widest ink
 * with its casing is a hair under the drawn width, never over it -
 * src/test/atcAlertProminence.test.ts holds the sum, and
 * map/atcNoticeMark.test.ts measures the reach off the pixels.
 */
export const ATC_NOTICE_GLYPH_BOX =
  ATC_UPDATE_POINT_DRAWN_WIDTH - 2 * ATC_NOTICE_CASING_WIDTH

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
// WHY IT COULD NOT SIMPLY STAY. A 54px wash of red behind an open mark is the
// solid disc back again in a softer spelling - the ground inside the band
// would be washed exactly where the hole exists to let it through. Keeping
// both would have meant keeping neither.
//
// WHAT REPLACES IT IS SHAPE RATHER THAN AREA. Nothing else on this map is a
// bare glyph: every waypoint and the serious-warning pin are discs
// (map/poiIcons.ts), and every closure and ATC band is a line - the burst
// #1071 chose was unlike its neighbours for the same reason, and the bare
// hazard triangle that replaced it on 2026-09-10 is too, while sharing the
// serious-warning pin's glyph so the two read as one vocabulary. The mark
// keeps every other conspicuity property it had - the closure red, the 40px
// reach, being drawn over every other layer (map/style.ts), and
// `icon-allow-overlap` so the collision engine can never drop one.
//
// @unvalidated Nobody has watched a hiker find one of these on a phone, in sun,
// while walking. A specimen sheet rendered at z5/z9/z13 is what this decision
// was made on, and a specimen sheet cannot answer a question about peripheral
// vision. What would settle it is field use. If the triangle turns out to be
// harder to find than the disc was, the fix is a glow back on a ZOOM RAMP -
// strong at corridor zoom where the mark is 16px and there is no detail to
// lose, faint in the hand where the band is wide and the ground inside it is
// what a hiker came for - and not one strength everywhere, which is the
// shape of the fault this change is fixing.

/**
 * Wider stripes, further apart - literally the closure's tape at twice the
 * scale.
 *
 * DERIVED FROM THE CLOSURE'S CADENCE RATHER THAN PICKED, and multiplied on
 * both axes by the same factor, which is what makes "the same tape, slower"
 * true rather than merely intended: doubling only the pitch would thin the
 * ATC's band to a third of the closure's red and read as a softer claim, which
 * is the severity distinction this module exists to refuse. Scaling both keeps
 * tapeRedFraction identical for the two - the tests hold that equality rather
 * than these numbers.
 *
 * At a glance the two are one treatment, and only a close look separates them.
 * That is the intended reading order, since what a hiker must register
 * instantly is "barrier", and only then "whose".
 */
export const ATC_UPDATE_TAPE_SCALE = 2

export const ATC_UPDATE_TAPE_CADENCE: TapeCadence = {
  stripe: CLOSURE_TAPE_CADENCE.stripe * ATC_UPDATE_TAPE_SCALE,
  pitch: CLOSURE_TAPE_CADENCE.pitch * ATC_UPDATE_TAPE_SCALE,
}

/** Re-exported so a test can hold the equality rather than the numbers, and
 *  so the coupling to lib/closureStyle.ts is visible from this file. An ATC
 *  band that quietly drifted narrower than a closure band would be exactly
 *  the severity distinction this module refuses to draw. */
export const ATC_UPDATE_LINE_WIDTH = CLOSURE_TAPE_WIDTH
/** The old band casing, which nothing paints with now - see the constant's own
 *  note in lib/closureStyle.ts. Kept re-exported because ATC_NOTICE_CASING_WIDTH
 *  is asserted lighter than it, and a comparison needs both sides. */
export const ATC_UPDATE_CASING_WIDTH = CLOSURE_CASING_WIDTH
export const ATC_UPDATE_COLOR = CLOSURE_COLOR
export const ATC_UPDATE_CASING_COLOR = CLOSURE_CASING_COLOR

export function buildAtcUpdateLayers(sourceId: string): LayerSpecification[] {
  return [
    // ONE band layer, and no casing beneath it - see buildClosureLayers, which
    // makes the same shape for the same reason. A solid casing under tape with
    // transparent gaps shows through every one of them, which is the defect
    // both feeds just stopped having.
    //
    // THE GLOW THAT USED TO OPEN THIS LIST IS GONE, and it went for a reason
    // this change shares rather than contradicts. #1071 removed it with the
    // solid disc it surrounded: opaque ink covers the ground a mark is about,
    // and a translucent wash around it was the softer half of the same fault.
    // The burst below and the tape here are the same answer at two scales -
    // let the ground read through the mark instead of around it.
    {
      id: ATC_UPDATE_LAYER_ID,
      type: 'line',
      source: sourceId,
      layout: { 'line-cap': 'butt', 'line-join': 'round' },
      paint: {
        'line-pattern': ATC_TAPE_IMAGE_ID,
        'line-width': ATC_UPDATE_LINE_WIDTH,
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
      // The seam, like every other point mark on this map (#1292).
      minzoom: ATC_UPDATE_POINT_MIN_ZOOM,
      layout: {
        'icon-image': ATC_NOTICE_ICON_ID,
        'icon-size': ATC_UPDATE_POINT_SIZE_EXPRESSION as unknown as number,
        'icon-allow-overlap': true,
        'icon-padding': 2,
      },
    },
  ]
}
