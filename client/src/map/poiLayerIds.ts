// The waypoint source's id, its two layers' ids, the property a pin carries
// its POI id in, and the two zooms the shell reads - and nothing that builds
// a layer.
//
// A LEAF, ON PURPOSE, for features/LAUNCH_BUDGET.md §4.4's rule: a constant
// the shell reads out of a screen-sized module belongs in a module of its
// own. Before this file, App.tsx (both zooms), lib/useDrawnPoiCounts.ts,
// map/trailBadges.ts, map/poiTaps.ts, map/drawnPois.ts and map/poiPinProbe.ts
// each imported one or two of these from map/poiLayers.ts, so every launch
// parsed the whole pin layer builder - its ring compositing, its icon and
// sort expressions, its filter - on a Today screen that mounts no map.
// map/poiLayers.ts re-exports every one of them, the way map/style.ts
// re-exports map/styleIds.ts (#1591), so a reader that imported an id from
// there still does. scripts/check-build-output.mjs refuses a string only the
// builder holds in any eager chunk, so it cannot drift back in.
//
// The comments below travelled with the constants they describe. Two that
// pointed at code which stayed in map/poiLayers.ts now name it.

export const POI_SOURCE_ID = 'pois'
export const POI_LAYER_ID = 'poi-pins'

/**
 * Where a pin carries its POI id, so a tap on it can be turned back into the
 * POI the app holds (poiTaps.ts).
 *
 * A property rather than the GeoJSON feature id, which is where an id belongs
 * and which cannot hold this one: MapLibre runs a string feature id through
 * `parseInt` (FeatureWrapper, maplibre-gl 6), and every id the pipeline
 * publishes - "atc_shelters:<guid>", "opentrail_at:1234" - comes back NaN. The
 * feature id map/poiLayers.ts's poiFeatureCollection writes is still set,
 * because it is the honest place for it and because a numeric-id release
 * would then work; nothing reads it.
 */
export const POI_ID_PROPERTY = 'poi_id'

/**
 * The seam. Below this the map is the corridor view and carries no waypoints
 * at all; above it every waypoint draws, as a pin or as a dot.
 *
 * A DAY'S HIKE, AND THE GROUND EITHER SIDE OF IT, HAS TO FIT ON THE SCREEN.
 * That is the whole criterion. A day on the A.T. is 16-24 miles; a 390x700
 * phone map covers 50.9 miles of ground at z9 and 25.5 at z10. So z9 is the
 * tightest zoom that shows a hiker the day they are about to walk AND where
 * it sits, which is the moment this map is for.
 *
 * The doubling is the point rather than slack. z10 fits a 24-mile day edge to
 * edge and nothing else, so every question that starts "and then what" costs
 * a pan. z9 puts the day in the middle of as much ground again.
 *
 * MEASURED at that zoom rather than hoped for - pipeline/spike_poi_seam.py,
 * 2026-08-13, against the live ATC service with lib/poi_sites.py's own folding
 * applied. What reaches a PIN at z9: shelters 83%, privies 69%, campsites 59%,
 * parking 14%, viewpoints 2%. The things a day is planned around are mostly
 * pins; the vistas are almost entirely dots, which is the right way round and
 * is what the dot rank is for.
 *
 * IT WAS z12, THEN z10, BOTH ON THE SAME DAY, and both corrections are worth
 * recording because the arithmetic was never what was wrong.
 *
 * z12 came from asking "at what zoom does the screen stop being oversubscribed
 * with pins" - a pin-legibility test, when under two ranks an overfull screen
 * costs DOTS rather than deletions and legibility is a comfort question.
 *
 * z10 came from fixing that and then sizing the window to exactly one day,
 * which is a day with no context around it.
 *
 * It replaces a floor of 9 - the same number, reached from the opposite
 * direction. That floor's docstring argued that eight hundred POIs on a
 * corridor view "is not a map, it is a texture", and it was right about the
 * texture and wrong about what to do: it drew nothing rather than drawing the
 * texture honestly. The dot rank is that texture, labelled.
 */
export const POI_PIN_MIN_ZOOM = 7

// IT IS 7.5 SINCE 2026-09-18 (#1585), AND THE DOCSTRING ABOVE IS KEPT WHOLE
// BECAUSE ITS ARGUMENT IS STILL THE ONE THAT DECIDES THIS NUMBER - the seam is
// the widest view that is still about a walk rather than about a region. What
// changed is which walk. A day is 16-24 miles and z9 fits it doubled; a
// thru-hiker plans one RESUPPLY at a time, five or six days at twenty miles,
// and that is 100-120 trail miles.
//
// MEASURED 2026-09-17 on the calibrated mile axis the app's own mile numbers
// come from (pipeline/export_elevation.py's calibrated_trail_axis, ATC's
// centerline and half-mile markers): every window of 100, 110 and 120 trail
// miles from Springer to Katahdin, stepped every two miles, fitted the way
// App.tsx fits a stretch (fitBounds into a 390x700 map, FIT_PADDING 24).
//
//     window   phone fit zoom p10 / median / p90   straight-line span, median
//     100 mi   7.82 / 8.39 / 8.95                  54 mi
//     110 mi   7.73 / 8.26 / 8.77                  59 mi
//     120 mi   7.61 / 8.14 / 8.59                  65 mi
//
// The median carry fits at z8.1-8.4 and fewer than one window in ten fits at
// z9, so z9 was a seam a section hiker could never see their section from.
// (On a desktop the map tab frames the same section at z9.6 and needed
// nothing; this is a phone answer.)
//
// 7.5 RATHER THAN THE MEDIAN 8, on the maintainer's pick of 2026-09-18 from
// three drawn options: nine in ten 120-mile windows fit at z7.61 or nearer, so
// 7.5 is the floor at which essentially EVERY carry fits rather than half of
// them. The cost was drawn beside it and taken knowingly - a z7.5 screen is
// 80 x 144 miles and holds a median 64 waypoints against room for about 26
// pins, so a smaller share of them wear one and the rest are dots. Which is
// exactly what the dot rank is for, and why the floor could move at all.
//
// THE PIN'S SIZE DID NOT MOVE WITH IT, also the maintainer's pick from the
// same three options: POI_PIN_MIN_SCALE stays 0.8, the value #617 measured as
// the difference between a mark you can identify and one you can only locate.
// A 0.6 ramp was drawn and offered - it fits about a quarter more pins - and
// was not taken.
//
// IT IS 7 SINCE 2026-09-20, AND THE SEAM IS A SEAM AGAIN. The maintainer,
// having seen the z7.8 carry frames drawn from the live preview: "We can keep
// a seam, and make it at zoom 7. Yes the POI's can be hidden above there" -
// above meaning further out, which they confirmed against two drawn frames
// before any of this was written. So below z7 the map carries no waypoints at
// all, and 7 rather than 7.5 is their number rather than a derivation: the
// measured table above says nine in ten 120-mile windows fit at z7.61 or
// nearer, so 7 clears every carry with room to spare.
//
// WHAT THE SEAM STILL NEVER DECIDES IS *WHICH*, and the first attempt at
// #1585 got exactly that wrong: it put a type gate below the seam - shelters,
// water and towns only - and a hiker at z8 saw no campsite, no privy, no
// parking and no crossing, with nothing on the screen to say they existed.
// The maintainer's rule of 2026-09-18 stands unchanged over the top of the
// new seam: "Don't auto hide the POIs ever. It's a safety thing, hikers need
// to know that info." So from z7 up, every category the hiker has switched on
// is drawn, and map/poiLayers.ts's poiFilter carries no zoom term at all.
// poiLayers.test.ts's "the map never hides a category of its own accord"
// block is that rule, pinned, and it now runs at every zoom from the seam up.
//
// AND THE HIKER CAN SEE THE SEAM WORKING, which is what makes it a seam
// rather than a silence: the legend's Showing picker runs from "All types"
// down to "None", and that gate turns itself on the first time a hiker
// crosses z7 inward in a given map view, never again overriding a state they
// chose themselves (lib/showPoints.ts). It floated over the map as a "Show
// points" pill for one day before the maintainer moved it into the picker.

/**
 * The closest one tap of the map's locate button brings the camera from
 * below the seam (#1581).
 *
 * The seam itself, so "where am I" from the corridor view lands on the
 * closest view that also shows what is around the hiker. Derived rather than
 * chosen, which is why it is this constant and not a number - and the same
 * cap the old GeolocateControl carried as its `fitBoundsOptions.maxZoom`
 * (#315). From above the seam the camera keeps the zoom it has, the way
 * App.tsx's handleBackToMe already leaves it alone: locate is a claim about
 * where the map is centred, not about how far in the hiker wanted to be.
 *
 * HERE, AND NOT BESIDE THE BUTTON. App.tsx reads it, and map/mapChrome.ts
 * imports maplibre-gl - a shell import reaching the engine statically puts
 * a megabyte of MapLibre into the eager chunk (map/mapEngineLoader.ts,
 * #1300), which scripts/check-build-output.mjs caught on this constant's
 * first draft. A second draft in map/positionLayers.ts kept the engine out
 * and pulled the mark's rasteriser in instead, for 626 bytes of headroom
 * under features/LAUNCH_BUDGET.md's 256,000. This module is already in the
 * eager chunk for POI_PIN_MIN_ZOOM's sake, so a constant here costs it
 * nothing.
 */
export const LOCATE_MIN_ZOOM = 9

// 9 IS NOW ITS OWN NUMBER, AND THAT IS THE CHANGE (#1585). It was
// POI_PIN_MIN_ZOOM, on the reasoning above: "the closest view that also shows
// what is around the hiker". That reasoning held while the seam was the zoom a
// DAY fits. The seam is a planning number now - the zoom a five-day resupply
// carry fits, 80 x 144 miles of ground - and "where am I" is not a planning
// question. Following it would have answered a hiker's tap with a screen a
// hundred and forty miles tall.
//
// So this keeps the value it has always had, for the reason it always had it:
// 28 x 51 miles is a day's ground with the waypoints around it, which is what
// somebody asking where they are wants to see. It is a camera choice and never
// a filter - every waypoint is drawn at every zoom either way.

/** The dot rank: every waypoint, at its real coordinates, always drawn. */
export const POI_DOT_LAYER_ID = 'poi-dots'
