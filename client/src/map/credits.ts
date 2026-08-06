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
}: MapCreditsOptions): string[] {
  const credits = [OSM_CREDIT]

  if (hasRasterArchive) credits.push(USGS_TOPO_CREDIT)

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
