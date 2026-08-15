// How the drought bands are drawn (#720).
//
// A wash, not a warning. The whole reason this layer is allowed to exist is
// pipeline/WATER_CONDITIONS.md's argument that a tint across a REGION says
// "this region", which is exactly what the U.S. Drought Monitor knows and the
// most a hiker may honestly read off it. It says nothing about the spring at
// the next shelter, and the drawing has to keep it incapable of seeming to.
//
// WHY THIS IS NOT THE U.S. DROUGHT MONITOR'S OWN PALETTE
//
// Theirs runs pale yellow to dark red, and the dark end lands on top of
// lib/closureStyle.ts's `#b2321f` - the colour this map already spends on
// "do not walk down there", and on the serious-warning pin beside it. Two
// unrelated meanings in one register is the failure #720 was opened naming:
// a drought tint that reads as a hazard band is worse than no tint, because
// it spends a hiker's alarm on something that is not an alarm.
//
// So the ramp here is dry ground rather than danger - pale sand through to
// baked ochre, and it never reaches red. It is deliberately the least
// insistent thing on the map: under the trail, under every pin, and at an
// opacity chosen so contour lines and the trail's own casing read straight
// through it.
//
// ONE HONEST WEAKNESS, STATED RATHER THAN DESIGNED AROUND
//
// WIREFRAMES.md §3 and §7 hold that safety-carrying distinctions must not
// rely on hue alone, because hue is the channel that fails in greyscale, in
// direct sun and for a colour-blind hiker. This layer leans on hue and
// opacity together - two channels, but both weak ones, and no third. That is
// a deliberate limit rather than an oversight: the bands are informational,
// they are off by default, and the number a hiker would act on is written in
// words in the legend and on the sheet ("205.8 miles at severe"). Nothing
// here is load-bearing enough to need the closure band's structural
// treatment, and giving it one would be the overclaim this file exists to
// avoid. If that ever stops being true - if a drought band starts driving a
// decision rather than colouring a map - it needs a third channel before it
// earns the promotion.

import type { LayerSpecification } from '@maplibre/maplibre-gl-style-spec'

export const DROUGHT_LAYER_ID = 'drought-band'

/** The property each band carries its class in, straight from the artifact. */
export const DROUGHT_CLASS_PROPERTY = 'dm'

/**
 * NDMC's five classes, and the ramp this map draws them in.
 *
 * Sand to baked ochre. The steps are spaced in lightness as well as in
 * saturation so the order survives a greyscale screenshot even though the
 * layer does not promise it will - see the note above about what this does
 * and does not carry.
 */
export const DROUGHT_COLORS: Record<number, string> = {
  0: '#e6d8ae',
  1: '#dcc172',
  2: '#c99b45',
  3: '#a9741f',
  4: '#7d4f0a',
}

/**
 * How strongly the wash sits on the sheet, per appearance.
 *
 * Lighter under a dark sheet, and that is not symmetry for its own sake: an
 * ochre wash at day opacity over `night_hike`'s near-black ground is the
 * brightest thing on the screen, which is precisely backwards for a layer
 * this far down the hierarchy - and for a hiker who chose that sheet to keep
 * their dark adaptation.
 */
export const DROUGHT_FILL_OPACITY: Record<'day' | 'night', number> = {
  day: 0.28,
  night: 0.16,
}

/** The severity ramp as a MapLibre `match`, the pattern MAP_OPTIONS.md uses
 *  for blaze colours and road walkability - normalize in the data, match in
 *  the style, so a class this build does not know draws as the palest band
 *  rather than as nothing at all. */
export function droughtColorExpression(): unknown {
  return [
    'match',
    ['get', DROUGHT_CLASS_PROPERTY],
    0,
    DROUGHT_COLORS[0],
    1,
    DROUGHT_COLORS[1],
    2,
    DROUGHT_COLORS[2],
    3,
    DROUGHT_COLORS[3],
    4,
    DROUGHT_COLORS[4],
    DROUGHT_COLORS[0],
  ]
}

/**
 * The one fill layer.
 *
 * `visibility` rather than adding and removing the layer, because the toggle
 * has to be instant and a hiker may flip it repeatedly while reading the map:
 * re-adding a layer re-parses the source, and the flicker is visible. The
 * source stays attached with the bands in it either way - they are 14 KB.
 */
export function buildDroughtLayer(
  sourceId: string,
  night: boolean,
  visible: boolean,
): LayerSpecification {
  return {
    id: DROUGHT_LAYER_ID,
    type: 'fill',
    source: sourceId,
    layout: { visibility: visible ? 'visible' : 'none' },
    paint: {
      'fill-color': droughtColorExpression() as string,
      'fill-opacity': night ? DROUGHT_FILL_OPACITY.night : DROUGHT_FILL_OPACITY.day,
      // No outline. An outlined band reads as a boundary somebody surveyed,
      // and a Drought Monitor edge is a weekly judgement call drawn at county
      // scale - the one thing this layer must not imply is precision at the
      // scale a hiker is standing at.
      'fill-outline-color': 'rgba(0,0,0,0)',
    },
  }
}
