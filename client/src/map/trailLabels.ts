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
 * The zoom trail names start drawing at.
 *
 * Set to the zoom waypoint pins start at, which is the same threshold
 * map/poiLayers.ts calls "something a hiker reads a position off". Below it
 * the map's subject is the corridor or the park - features/NEARBY_TRAILS.md §8
 * is explicit that "at z7 Harriman is one green shape" and the below-seam
 * subject is the park, not forty short trails - so naming individual trails
 * there is answering a question nobody asked at that altitude.
 *
 * `@unvalidated` as a *display* choice rather than a safety one: it is picked
 * to match a threshold this map already uses, not measured against how a hiker
 * actually zooms. The issue (#930) names it as something the design should
 * settle rather than this module; borrowing the neighbouring constant is the
 * smallest defensible answer until it does, and it cannot drift from the pins
 * because it IS the pins' constant.
 */
export { POI_PIN_MIN_ZOOM as TRAIL_LABEL_MIN_ZOOM } from './poiLayers'

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
): LayerSpecification {
  return {
    id: TRAIL_LABEL_LAYER_ID,
    type: 'symbol',
    source: sourceId,
    minzoom,
    filter: TRAIL_LABEL_FILTER as never,
    layout: {
      'text-field': ['get', 'name'] as never,
      'text-font': FONT,
      // Along the line, not beside a point: a trail is a line and a name
      // floating off it belongs to nothing. `text-max-angle` is left at
      // MapLibre's default, which drops a label rather than bending it around
      // a switchback into something unreadable.
      'symbol-placement': 'line',
      // Repeated at intervals so a long trail is identifiable wherever a hiker
      // is looking, rather than once at a midpoint that may be off screen.
      'symbol-spacing': 250,
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
