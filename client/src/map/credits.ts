// What the map corner credits - one atom per source, assembled per screen.
//
// Every entry here is a licence or terms condition rather than a courtesy:
// ODbL for the OpenStreetMap data, OpenFreeMap's own terms for hosting the
// vector sheet, the AWS Terrain Tiles requirement (tilezen/joerd) for the
// elevation the hillshade and contours are derived from. USGS US Topo is
// public domain and carries no requirement, but a map that draws someone
// else's survey says whose it is.
//
// This used to be two hand-composed strings in style.ts, and both were wrong
// in the same way: they named every source the app COULD draw rather than the
// ones it IS drawing. On a fresh install with the default background the
// corner read
//
//   USGS US Topo · © OpenStreetMap contributors · OpenFreeMap © OpenMapTiles
//   · © OpenStreetMap contributors · Elevation: USGS 3DEP via AWS Terrain Tiles
//
// - five clauses, one of them printed twice, the first of them crediting a
// 314 MB archive that is not on the phone and cannot be drawing anything.
// Three wrapped lines of small type across the bottom of a phone map, and the
// part a hiker could check was the part that was false. Attribution that names
// sources which are not on screen is not a stricter reading of the licence; it
// is the same category of quiet inaccuracy value #4 exists to prevent, and it
// costs map height to make.
//
// So the corner is assembled from atoms instead. Each constant below is the
// credit for exactly one source and is what that source declares in the style
// (style.ts, liveTopo.ts, terrain.ts), so a source cannot be added in one file
// and go uncredited in another; mapCredits() picks the ones actually on screen
// and dedupes. The rendering half - what is shown at a glance and what is one
// tap away - is chrome/MapAttribution.tsx, deliberately not decided here.

import type { BackgroundSource } from '../lib/userPreferences'
import { ELEVATION_ATTRIBUTION } from './terrain'

/**
 * ODbL's condition, spelled out in full.
 *
 * WIREFRAMES.md's map-corner mockup shows the shorthand "© OSM", but its own
 * Assets section states the full form is required - the abbreviation does not
 * satisfy the licence, so the full form is what ships.
 */
export const OSM_CREDIT = '© OpenStreetMap contributors'

/** The downloaded corridor raster. Public domain; credited as good practice. */
export const USGS_TOPO_CREDIT = 'USGS US Topo'

/**
 * NYS OPRHP's attribution, and it is a CONDITION rather than a courtesy (#950).
 *
 * Their item's terms say it in as many words: "Any maps, reports, or other
 * materials created using OPRHP data must include proper credit and
 * attribution to the NY State Office of Parks, Recreation and Historic
 * Preservation (OPRHP)." A map drawing their 3,618 trail lines is a map
 * created using OPRHP data, so this is what makes drawing them permitted.
 *
 * SPELLED IN FULL, not as "NYS OPRHP". The abbreviation is what their own
 * `tags` field uses and would fit the corner better, but the terms ask for
 * "proper credit" and OSM_CREDIT above already records this project's reading
 * that an abbreviation does not satisfy a licence that asks for a name.
 */
export const OPRHP_CREDIT =
  'NY State Office of Parks, Recreation and Historic Preservation'

/**
 * NYNJTC's attribution.
 *
 * NOT a condition - NYNJTC state no terms at all, and their data ships on the
 * maintainer's authorisation (pipeline/sources.json's `nynjtc_licence`). It is
 * here because a map that draws a club's trails and does not say so is exactly
 * the "quiet inaccuracy" this file's header objects to, and because the
 * project's whole posture is that the clubs who maintain the trails are named.
 */
export const NYNJTC_CREDIT = 'New York-New Jersey Trail Conference'

/**
 * Mohonk Preserve's attribution.
 *
 * NOT a condition - Mohonk Preserve states no terms at all, and their data
 * ships on the maintainer's authorisation (pipeline/sources.json's
 * `mohonk_licence`), the same footing NYNJTC_CREDIT above is on. Present for
 * the same reason: a map that draws a steward's trails and does not say so is
 * the "quiet inaccuracy" this file's header objects to.
 */
export const MOHONK_CREDIT = 'Mohonk Preserve'

/** OpenFreeMap's own terms for hosting the vector sheet - see liveTopo.ts. */
export const OPENFREEMAP_CREDIT = 'OpenFreeMap © OpenMapTiles'

export interface MapCreditsOptions {
  /** Which background is actually DRAWN - the outcome, not the preference. */
  background: BackgroundSource
  /**
   * Whether a finished corridor raster archive is on this phone.
   *
   * The raster source is in the style either way (style.ts stacks the live
   * sheet over it rather than branching on connectivity), so the style alone
   * cannot answer this - without an archive that source resolves to nothing
   * and draws nothing, which is exactly the state that had the corner
   * crediting USGS on a phone holding no USGS tiles.
   */
  hasRasterArchive?: boolean
  /**
   * Whether the other organizations' trail lines are actually on the map
   * (#950) - lib/nearbyTrailData.ts handed the shell an artifact, and it is
   * not empty.
   *
   * Its own flag rather than something read off the style, for the reason
   * `hasRasterArchive` is one: the source is in the style whether or not the
   * fetch succeeded, so the style cannot answer this. Crediting OPRHP on a
   * phone drawing none of their data would be the same false corner this
   * module was written to fix - and here it would be false about a licence
   * condition, which is worse than false about a courtesy.
   */
  hasNearbyTrails?: boolean
}

/**
 * Every source on screen, in the order the corner should say them.
 *
 * OpenStreetMap leads in every state, and that is two decisions at once. It is
 * the one credit required no matter what is drawn - the POI source is partly
 * OSM-derived and is on the map with every background - and it is the licence
 * with the strictest prominence requirement, so it is the line that survives
 * any collapsing the chrome does. Keeping it first also means the summary line
 * does not reshuffle when a download lands or the background flips, which on a
 * strip this small would read as flicker rather than as information.
 *
 * The rest follow the map's own draw order, bottom to top: the downloaded
 * raster, then the live sheet over it, then the elevation the sheet's relief
 * and contours come from.
 */
export function mapCredits({
  background,
  hasRasterArchive = false,
  hasNearbyTrails = false,
}: MapCreditsOptions): string[] {
  const credits = [OSM_CREDIT]

  if (hasRasterArchive) credits.push(USGS_TOPO_CREDIT)

  // Before the background credits, not after: these two name whose TRAILS are
  // drawn, and the trails are the subject of the map. OPRHP's is a licence
  // condition besides, so it should not be the clause that falls off the end
  // of a small strip - see chrome/MapAttribution.tsx for what collapsing does.
  if (hasNearbyTrails) credits.push(OPRHP_CREDIT, NYNJTC_CREDIT, MOHONK_CREDIT)

  if (background === 'hiking_topo_live') {
    credits.push(OPENFREEMAP_CREDIT, ELEVATION_ATTRIBUTION)
  }

  // Deduped structurally rather than by knowing the atoms above are distinct.
  // The duplicate this replaces was not a typo - it came of composing two
  // strings that each independently, and correctly, named OpenStreetMap. Any
  // later credit that overlaps another will do the same thing, and should
  // cost nothing.
  return [...new Set(credits)]
}
