// Trail names on the map (#930), and the rule that they dim with their lines.
//
// features/NEARBY_TRAILS.md §1 asks for two things and #783 could only build
// one of them. The ghosting landed; "labels dim with their lines — a
// full-strength name on a ghosted line points at the wrong thing" had nothing
// to bind to, because per-trail names had never been drawn on this map at all.
// Checked 2026-08-23: `text-field` appeared in map/ only on contour labels,
// peak labels and the OSM basemap's own name layers, none of which read the
// trails source. This is the missing layer.
//
// WHY THE A.T.-ONLY MAP NEVER NEEDED IT, AND WHY THAT IS NOW A RULE HERE
//
// One line worth naming, and the header already names it (`Appalachian Trail ·
// NY`), so a label on the line would have been the same fact twice. That stops
// being true the moment a second network draws: frame `1f` of the v2 wireframe
// export shows `A.T.`, `Long Path` and `Kakiat Tr.` beside their lines, because
// in a forty-line park a hiker at a junction cannot otherwise tell which line
// is which without tapping each one in turn.
//
// The side trails are the ones that need naming TODAY - nothing else on the
// screen says which blue-blazed line leads to the shelter. So this layer draws
// them and leaves the through-route alone; TRAIL_LABEL_FILTER carries that
// decision, the measurement behind it, and what would reverse it.
//
// THE TRAP THIS MODULE EXISTS TO GET RIGHT, AND IT IS INVERTED FROM THE LINES
//
// `line-sort-key` and `symbol-sort-key` run in OPPOSITE directions, and the
// two layers have to agree about which trail wins:
//
//   - `line-sort-key`: HIGHER draws later, so it draws ON TOP. map/style.ts
//     gives the through-route the higher key so a side trail can never cover
//     the line the map is about.
//   - `symbol-sort-key`: LOWER is placed FIRST, so it WINS the collision and
//     the loser is dropped entirely.
//
// Copying the line expression here would therefore have given the chosen
// trail's label the *worst* claim on space in a crowded junction - the one
// place the whole feature exists to help. The keys are inverted deliberately
// below, and trailLabels.test.ts pins the inversion rather than the numbers.

import type { LayerSpecification } from '@maplibre/maplibre-gl-style-spec'
import { nearbyTrailOpacityExpression, CHOSEN_SYSTEM_SOURCES } from './nearbyTrails'

export const TRAIL_LABEL_LAYER_ID = 'trail-label'

/**
 * The same layer over the nearby-trail source (#950).
 *
 * A second instance rather than a second implementation: MapLibre needs one
 * layer per source and ids must be unique, and that is the ONLY difference
 * between the two. Everything that decides how a name looks - the font, the
 * placement along the line, the sort key, and above all the opacity
 * expression §1 requires them to share - is built once in
 * buildTrailLabelLayer below and handed to both.
 */
export const NEARBY_TRAIL_LABEL_LAYER_ID = 'nearby-trail-label'

/** The bundled face every symbol layer in this app renders in (map/liveTopo.ts
 *  ships the ranges under `public/glyphs/`, precached by vite.config.ts so the
 *  offline sheet has them too). Restated rather than imported to keep this
 *  module off liveTopo's much larger surface. */
const FONT = ['Noto Sans Regular']

/**
 * Collision priority: the chosen trail's label is placed first, so it wins.
 *
 * Deliberately the INVERSE of map/style.ts's TRAIL_SORT_KEY_EXPRESSION - see
 * this file's header for why the same numbers would have meant the opposite
 * thing. Lower is better here.
 *
 * Only two tiers, matching the lines: within a tier, one label losing to
 * another is two labels of equal standing competing, which is honest. What
 * must never happen is a ghosted trail's name displacing the chosen trail's.
 */
export const CHOSEN_LABEL_SORT_KEY = 0
export const NEARBY_LABEL_SORT_KEY = 1

export const TRAIL_LABEL_SORT_KEY_EXPRESSION = [
  'case',
  ['in', ['get', 'source'], ['literal', [...CHOSEN_SYSTEM_SOURCES]]],
  CHOSEN_LABEL_SORT_KEY,
  NEARBY_LABEL_SORT_KEY,
]

/**
 * Sources drawn at the through-route width - map/style.ts's
 * PRIMARY_TRAIL_SOURCES, restated for the reason nearbyTrails.ts restates its
 * own list: `style.ts` imports THIS module, so importing it back would be a
 * cycle. trailLabels.test.ts imports both and fails if they drift.
 */
export const THROUGH_ROUTE_SOURCES: readonly string[] = ['centerline']

/**
 * Which lines get a name, and the one that deliberately does not.
 *
 * Two conditions, and the second is a decision rather than a mechanism:
 *
 * 1. A trail with no name draws no label. Absent, never "Unnamed" - the
 *    restraint lib/lineDetail.ts applies to a spur with no resolved
 *    destination.
 * 2. **The through-route draws no label either.** The header already says
 *    `Appalachian Trail · NY`, and lib/lineDetail.ts refuses to repeat ATC's
 *    formal name under a heading that already carries it - "the same fact
 *    twice". Printing it along the line is that same repetition, at every
 *    `symbol-spacing` interval down the whole corridor.
 *
 *    SINCE #1283 THIS IS ALSO THE BADGE RULE, and it is the reason the next
 *    reader must not "fix" it. A through-route says its name in exactly one
 *    place on the canvas: the badge map/trailBadges.ts draws once per line in
 *    view, with its registry mark. A trail either carries a badge or a name
 *    along its line, never both - the design handoff rejected the "both"
 *    direction (its frame `2c`) as saying the same name twice. So this
 *    exclusion and BADGE_SOURCES over there are two halves of one sentence,
 *    and trailBadges.test.ts holds them equal.
 *
 * WHAT MADE THIS CONCRETE, measured against the live bucket 2026-08-23: the
 * published `trails.geojson` names every one of its 4,221 features, and all
 * 3,025 centerline segments carry the same string - "Appalachian National
 * Scenic Trail", thirty-three characters, repeating every 250 px along the one
 * line the screen is already about. The 1,196 side trails are the labels worth
 * having ("Campbell Shelter Side Trail", "McAfee Knob Fire Rd Side Trail"),
 * because nothing else on the screen names those.
 *
 * THE REVISIT TRIGGER, NAMED. This is right for a map with ONE through-route
 * and stops being obviously right with two: the v2 wireframe export's frame
 * `1f` draws the A.T. labelled `A.T.` among Harriman's other lines, where the
 * through-route is one line in a thicket rather than the whole subject. When
 * nearby networks ship (#768), this suppression is the first thing to
 * re-argue - and the honest form of the frame's answer is a SHORT display
 * name, which the client cannot invent for itself: rewording a steward's own
 * value is what features/NEARBY_TRAILS.md §6 forbids, so a short name has to
 * arrive as data, from the org record features/SOURCE_REGISTRY.md defines.
 */
export const TRAIL_LABEL_FILTER: unknown[] = [
  'all',
  ['!=', ['to-string', ['get', 'name']], ''],
  [
    '!',
    ['in', ['to-string', ['get', 'source']], ['literal', [...THROUGH_ROUTE_SOURCES]]],
  ],
]

/**
 * The zoom trail names start drawing at: the overview band, not the pin band
 * (#1283).
 *
 * This was `POI_PIN_MIN_ZOOM` re-exported - the pins' z9, borrowed on the
 * reasoning that below the seam the subject is the park, not forty short
 * trails (features/NEARBY_TRAILS.md §8). The whole complaint #1283 answers
 * is that the opening camera names nothing, and borrowing the pins' floor
 * kept the names off exactly the screen that needed them. The design was
 * what #930 said should settle it, and did: labels start where the map
 * starts, and map/labelLadder.ts's tiers stage which labels win above this
 * floor. §8's worry is answered by the split rather than by a floor - a
 * park's forty trails are dotted and ghosted at z7, and a name on a dotted
 * line is context, not a subject.
 *
 * WHAT ACTUALLY DRAWS BELOW THE SEAM is less than this floor allows, and the
 * gap is the data's, not this module's. The nearby network below z9 is the
 * overview sketch (NETWORK_OVERVIEW_SOURCE_ID), which
 * export_nearby_trails.py's write_overview publishes with `source`,
 * `blaze_color` and `trail_status` only - no `name`, because it merges lines
 * by those three. So the Long Path is drawn dotted at the state camera and
 * cannot be named there until the overview artifact carries names, which is
 * a pipeline change and a publish (#1283 records it). The A.T.'s own side
 * trails are the only lines this floor names below z9 today.
 *
 * The value itself is the handoff's overview band, matched to the opening
 * camera (App.tsx fits the whole trail near z4.9). `@unvalidated` as a
 * display choice: picked against the prototype's four cameras, not measured
 * against how a hiker zooms.
 */
export const TRAIL_LABEL_MIN_ZOOM = 4

/**
 * How far apart a name repeats along its line, by zoom.
 *
 * 250 px is right at hiking zooms and far too dense at the overview, where a
 * long trail crossing the whole screen would print its name seven times
 * across it. Interpolated from 700 px at the overview floor down to 250 at
 * the seam, both measured on the handoff prototype's four cameras rather
 * than picked - the same `@unvalidated` caveat as the floor above.
 */
export const TRAIL_LABEL_SPACING_EXPRESSION: unknown[] = [
  'interpolate',
  ['linear'],
  ['zoom'],
  TRAIL_LABEL_MIN_ZOOM,
  700,
  9,
  250,
]

/**
 * The sharpest bend a name is allowed to follow, in degrees per glyph.
 *
 * MapLibre's default is 45. The overview geometry is full of switchbacks at
 * the pixel scale, and at 45 a name bends around them into something
 * unreadable; at 30 it is dropped instead, which is the right failure - a
 * name that cannot be read is worse than one that is not there, and the
 * next `symbol-spacing` interval along a straighter stretch places it.
 */
export const TRAIL_LABEL_MAX_ANGLE = 30

/**
 * The label layer for the trails source.
 *
 * What it labels and what it deliberately does not is TRAIL_LABEL_FILTER's,
 * argued there: an unnamed trail draws no label, and neither does the
 * through-route the header already names.
 *
 * A NAME THAT WILL NOT FIT IS DROPPED, and that is MapLibre's own behaviour
 * for `symbol-placement: line` rather than something configured here: a label
 * longer than the line it sits on is not placed. Left as the default
 * deliberately - the alternative (`text-allow-overlap`, or letting it run past
 * the geometry) puts a name where its trail is not, which at a junction is the
 * exact false statement this layer exists to prevent. #930 lists this as open;
 * the position taken here is that the default is already the right one.
 */
export function buildTrailLabelLayer(
  sourceId: string,
  color: string,
  haloColor: string,
  minzoom: number,
  layerId: string = TRAIL_LABEL_LAYER_ID,
): LayerSpecification {
  return {
    id: layerId,
    type: 'symbol',
    source: sourceId,
    minzoom,
    filter: TRAIL_LABEL_FILTER as never,
    layout: {
      'text-field': ['get', 'name'] as never,
      'text-font': FONT,
      // Along the line, not beside a point: a trail is a line and a name
      // floating off it belongs to nothing. `text-max-angle` drops a label
      // rather than bending it around a switchback into something
      // unreadable - tighter than MapLibre's default, see
      // TRAIL_LABEL_MAX_ANGLE.
      'symbol-placement': 'line',
      'text-max-angle': TRAIL_LABEL_MAX_ANGLE,
      // Repeated at intervals so a long trail is identifiable wherever a hiker
      // is looking, rather than once at a midpoint that may be off screen -
      // sparser at the overview, see TRAIL_LABEL_SPACING_EXPRESSION.
      'symbol-spacing': TRAIL_LABEL_SPACING_EXPRESSION as never,
      'text-size': 11,
      // Small, because this layer is orientation rather than subject. The map
      // is about the lines; the names say which line is which.
      'text-letter-spacing': 0.02,
      'symbol-sort-key': TRAIL_LABEL_SORT_KEY_EXPRESSION as never,
    },
    paint: {
      'text-color': color,
      'text-halo-color': haloColor,
      // Wide enough to stay legible where a name crosses its own line and the
      // topo contours under it - the same job the trail casing does for the
      // line itself.
      'text-halo-width': 1.5,
      // §1's requirement, and the whole reason this layer waited on #783: ONE
      // expression shared with the line's own opacity, so a label can never
      // drift away from the line it names. Not a copy of the rule - the rule.
      'text-opacity': nearbyTrailOpacityExpression() as never,
    },
  }
}
