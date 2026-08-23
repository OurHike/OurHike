// Ghosting: which trail the map is about, when the map holds more than one
// system's trails (#783, features/NEARBY_TRAILS.md §1).
//
// WIREFRAMES.md §3 gave this map two channels and map/style.ts builds both:
// HUE says which blaze, WIDTH says which line the map is about (through-route
// 4.5 px, side trail 2.5 px, through-route sorted last so nothing covers it).
// Those two were enough while every line on screen belonged to one system.
//
// They stop being enough in a park. The #771 spike's measurement is the
// reason: half the A.T.'s length in Harriman runs within 150 m of a different
// marked trail (NEARBY_TRAILS.md §7), so the chosen trail is no longer the
// only thing near the hiker's dot - it is one line in a thicket of them, and
// width alone leads by 2 px in a forty-line park.
//
// This module adds the third channel NEARBY_TRAILS.md §1 specifies - OPACITY -
// and nothing else. Every existing rule survives unchanged: lines stay solid
// (no dash rhythms), the chosen trail stays widest and last-drawn, and hue
// still comes from the reviewed blaze mapping. Ghosting is deliberately an
// opacity fact rather than a hue fact, and that is the argument that beat the
// alternatives: under red-light mode every blaze collapses to one hue
// (MAP_STYLE_SPEC.md), so a halo or a hue shift would have erased the
// distinction in exactly the light where a hiker most needs it. An opacity
// difference survives red light, greyscale (WIREFRAMES.md `9d`), glare and
// colour vision deficiency alike.
//
// WHY THIS FILE OWNS THE SOURCE LIST AND style.ts IMPORTS IT
//
// One direction only, so there is no cycle: `style.ts` imports the expression
// built here; nothing here imports `style.ts`. That leaves two source lists in
// the tree that must agree - this file's CHOSEN_SYSTEM_SOURCES and style.ts's
// PRIMARY_TRAIL_SOURCES - which is the same shape lib/lineDetail.ts already
// lives with, and it is pinned the same way: nearbyTrails.test.ts imports both
// and fails if a through-route is ever missing from the chosen system.

/**
 * How much of its own colour a nearby trail keeps.
 *
 * `@unvalidated` — picked from the drawn comparison on the v2 wireframe
 * canvas, not from a measurement: chosen so the hue stays *identifiable*
 * (a hiker can still tell the blue trail from the yellow one) while the
 * chosen trail is *unmistakable*. Nobody has looked at it outdoors.
 *
 * What would settle it: the outdoor usability pass **#105 — Outdoor usability
 * pass — sunlight glare and gloved, one-handed use**, in sunlight, on both the
 * light and dark sheets. That pass owes the rest of the chrome the same
 * answer, so this rides along with it rather than needing its own field trip.
 *
 * The wireframe canvas deliberately exposes this as a knob rather than a
 * drawn-in constant, and the export's own closing note says so: "it's a tweak
 * on this canvas so it can be argued with, not a value these frames decide."
 * Treat a number arrived at here as a starting point a reviewer may move.
 */
export const NEARBY_TRAIL_OPACITY = 0.45

/** What the chosen trail draws at. Full strength, stated rather than implied,
 *  so the contrast the constant above is picked against is one number away. */
export const CHOSEN_TRAIL_OPACITY = 1

/**
 * The sources that make up the trail system a hiker chose.
 *
 * A ROLE, like map/style.ts's PRIMARY_TRAIL_SOURCES, and a superset of it: the
 * A.T.'s through-route (`centerline`) plus the side trails and spurs hanging
 * off it (`side_trails`), which are ATC's own and are part of the same system.
 *
 * THE DECISION HERE, AND IT IS A REAL ONE - a spur off the chosen trail draws
 * at FULL opacity, not ghosted:
 *
 *   NEARBY_TRAILS.md §1 is headed "The chosen trail and the others", which
 *   read strictly would dim an A.T. blue-blaze spur along with everything
 *   else. It is not read strictly here, for two reasons a reviewer can
 *   disagree with on the merits:
 *
 *   1. features/SPUR_TRAILS.md §3 makes a spur decision-support FOR the
 *      chosen trail's hiker - "is it worth walking down there, and how far
 *      back up?" - and the sheet, the round-trip figure and the junction mile
 *      all exist to answer that. Dimming the line those answers are about
 *      works against the feature two files over.
 *   2. It keeps the shipped v1 map pixel-identical. On an A.T.-only build
 *      every drawn source is in this list, so `nearbyTrailOpacity()` returns
 *      full opacity for every line and nothing changes for a hiker who has
 *      downloaded no network ground. A visual regression on the launched map
 *      is a high price for a reading of a heading.
 *
 * The alternative reading is legitimate and is what a reviewer should push
 * back with if they hold it: in Harriman the A.T.'s own spurs are as much
 * "not the trail I am walking" as the Suffern-Bear Mountain is. What would
 * settle it is the same #105 pass the opacity constant waits on - whether a
 * hiker reads two full-strength widths as one system or as two trails.
 *
 * This list is static today because a hiker cannot yet choose a different
 * trail; **#558 — Let a hiker take the stretch they are walking, without
 * picking it off a list** is where the choice arrives, and this becomes a
 * lookup against the chosen system rather than a constant when it does.
 */
export const CHOSEN_SYSTEM_SOURCES: readonly string[] = ['centerline', 'side_trails']

/**
 * Whether one line is ghosted, from the `source` attribute the pipeline
 * publishes on every trail feature (export_trails.py).
 *
 * Keyed off `source` rather than off a steward id because `steward_id` does
 * not exist on a feature yet - features/SOURCE_REGISTRY.md's field map is what
 * introduces it (the v2 export draws it as frame `1o`'s "steward_id constant ·
 * org:nysp"), and nothing publishes it today. `source` is already on every
 * feature and is already what width and sort-key key off, so ghosting joins
 * the two channels that exist rather than inventing a third vocabulary.
 *
 * A source this build has never heard of GHOSTS. That is the conservative
 * direction of the two: an unrecognised line drawn at full strength competes
 * with the chosen trail for the one thing this channel exists to say, while an
 * unrecognised line drawn dim is merely context - which is what it is until
 * somebody adds it to the list above deliberately. It matches the neighbouring
 * default in style.ts, where an unknown source takes the side-trail width
 * rather than claiming the through-route tier.
 */
export function isNearbyTrail(source: string | null | undefined): boolean {
  if (source === null || source === undefined || source === '') return false
  return !CHOSEN_SYSTEM_SOURCES.includes(source)
}

/**
 * The opacity one line draws at.
 *
 * A missing `source` draws at full strength rather than ghosted, and that is
 * the one place this file does NOT take the conservative-looking option. A
 * feature with no source attribute at all is a pipeline fault, not a nearby
 * trail, and the failure modes are not symmetric: a fault drawn dim is a
 * trail quietly de-emphasised on a safety surface, which is the "display
 * outruns its source" failure CLAUDE.md names. Drawn full-strength it is at
 * worst an over-prominent line, and it is visible - which is how it gets
 * fixed.
 */
export function nearbyTrailOpacity(source: string | null | undefined): number {
  return isNearbyTrail(source) ? NEARBY_TRAIL_OPACITY : CHOSEN_TRAIL_OPACITY
}

/**
 * The same rule as a MapLibre data-driven expression, for the paint property.
 *
 * Built from CHOSEN_SYSTEM_SOURCES rather than written out, so admitting a
 * source to the chosen system cannot change the function above and leave the
 * paint disagreeing with it. nearbyTrails.test.ts evaluates this expression's
 * logic against `nearbyTrailOpacity()` over the same inputs, which is the only
 * way the two stay pinned without a canvas.
 *
 * THE SHAPE IS "GHOST ONLY WHEN WE ARE SURE", AND IT IS THAT WAY BECAUSE THE
 * OBVIOUS SHAPE WAS WRONG. Written first as the direct reading -
 *
 *     ['case', ['in', source, CHOSEN], full, ghosted]
 *
 * - which puts GHOSTED in the default branch, so every feature the condition
 * cannot answer for falls into it. A feature carrying no `source` at all
 * returns null from `['get','source']`, `['in', null, [...]]` is false, and the
 * line paints dim: a pipeline fault silently de-emphasised on a safety
 * surface, which is the exact direction `nearbyTrailOpacity()` above refuses
 * to round in. nearbyTrails.test.ts caught it by evaluating both against the
 * same inputs, which is the only reason the two are safe as two.
 *
 * So the condition is inverted: FULL opacity is the default, and a line is
 * ghosted only when its source is a real, non-empty value that is genuinely
 * not in the chosen system. `to-string` is what makes that testable in one
 * step - MapLibre converts null to `""`, so the missing case and the empty
 * case collapse into one comparison instead of needing a `has` guard that
 * would still let a null-valued property through.
 */
export function nearbyTrailOpacityExpression(): unknown[] {
  const source = ['to-string', ['get', 'source']]
  return [
    'case',
    [
      'all',
      ['!=', source, ''],
      ['!', ['in', source, ['literal', [...CHOSEN_SYSTEM_SOURCES]]]],
    ],
    NEARBY_TRAIL_OPACITY,
    CHOSEN_TRAIL_OPACITY,
  ]
}

// LABELS: THE ONE PART OF §1 THIS DOES NOT BUILD, SAID PLAINLY
//
// NEARBY_TRAILS.md §1 also requires "Labels dim with their lines — a
// full-strength name on a ghosted line points at the wrong thing", and the v2
// export draws exactly that in frame `1f` ("A.T.", "Long Path", "Kakiat Tr."
// beside their lines).
//
// Nothing here implements it, because there is no trail-name label layer in
// this client to dim. Checked 2026-08-23: `text-field` appears in map/ only in
// liveTopo.ts, on contour labels, peak labels and the OSM basemap's own name
// layers - none of which read the trails source. Per-trail names have never
// been drawn on this map.
//
// So the rule has nothing to bind to yet, and an expression exported for a
// layer that does not exist would read as "labels are handled" to the next
// person who greps for it. When a trail-label layer is built, it takes
// `nearbyTrailOpacityExpression()` for its `text-opacity` unchanged - the rule
// is the line's own, and one expression for both is what keeps a label from
// drifting away from the line it names.
