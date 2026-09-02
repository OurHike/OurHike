// What the downloaded archive can actually draw, and where the app has to
// account for the fact that it cannot draw everything.
//
// The corridor archive is a strip of tiles over a zoom range, not a map of
// everywhere at every scale. Two edges follow from that and both were being
// walked off silently (#216):
//
//   - Below the archive's own lowest tier there is nothing to draw, so
//     map/style.ts's paper backdrop shows through. The app OPENS on the whole
//     trail, which fits at roughly z3.8 on a phone - and every archive built
//     before 2026-08-05 starts at z6. A complete 314 MB download therefore
//     rendered as blank paper on every single launch.
//   - Panning off the 30-mile strip does the same thing horizontally. That
//     one is `coverageAt` below (#557): the footprints come from the cells a
//     phone holds (lib/coverageCells.ts, whose bounds are computable from
//     each cell's own name) and from a whole-sheet archive's header
//     (map/archiveZooms.ts's readArchiveFootprint), so the map, the status
//     strip and the download window all ask this one module and cannot
//     disagree about where the download ends.
//
// The pipeline now exports from z0 (pipeline/assemble_raster.py), so archives
// built from here on have no floor worth speaking of. This module exists for
// the ones already on phones, and because a client that trusts a number
// compiled into a different language in a different half of the repo is one
// pipeline change away from being wrong again. Everything here reads the
// archive's OWN header instead - see map/archiveZooms.ts.

/** The zoom range an archive's PMTiles header declares. */
export interface ArchiveZooms {
  minZoom: number
  maxZoom: number
}

/**
 * How far the CAMERA zoom sits from the TILE zoom for the raster source.
 *
 * map/style.ts declares the archive `tileSize: 256` (the @2x convention,
 * #191): MapLibre then requests tiles one level deeper than the camera, so
 * a camera at z5 is drawing z6 tiles - and an archive whose header floor is
 * 6 covers it. The header speaks in tile zooms, every caller here speaks in
 * camera zooms, and this constant is the one place the difference lives. If
 * the tileSize declaration ever changes, this must change with it - the
 * style test that asserts the pairing is what makes that a build failure
 * rather than an off-by-one nobody can see.
 */
export const CAMERA_ZOOM_TILE_OFFSET = 1

/**
 * Whether the archive has tiles to draw at this camera zoom.
 *
 * Only the floor is asked about, and that asymmetry is real rather than an
 * oversight. Above `maxZoom` MapLibre overzooms a raster - the top tier's
 * tiles are stretched, which is blurry and is still a map. Below `minZoom`
 * there is no tile at all and the paper shows through.
 *
 * Unknown coverage answers `true`. The app cannot read the header until the
 * archive exists, and "we have not found out yet" must not be rendered as
 * "your download does not reach here" - that is the same conflation of
 * not-looked-yet with definitely-absent that made #216 hard to see in the
 * first place.
 */
export function archiveCoversZoom(zooms: ArchiveZooms | null, zoom: number): boolean {
  return zooms === null || zoom + CAMERA_ZOOM_TILE_OFFSET >= zooms.minZoom
}

/**
 * The zoom to move the opening camera to, or `null` to leave it alone.
 *
 * Deliberately takes the zoom the map has ALREADY settled on rather than a
 * bounding box and a viewport size: the caller is MapView, which can simply
 * ask the live map what fitting the box produced. Working it out here would
 * mean reimplementing how MapLibre fits a box to a screen, and then owning
 * the difference between that reimplementation and the real thing forever.
 *
 * `null` whenever the archive already reaches the view, whenever there is no
 * archive to consult, and - by the caller's own guard - whenever the live
 * sheet is what is being drawn, since that covers every zoom.
 */
export function openingZoomFloor(
  zooms: ArchiveZooms | null,
  fittedZoom: number,
): number | null {
  if (zooms === null || archiveCoversZoom(zooms, fittedZoom)) return null
  // The shallowest CAMERA zoom with tiles behind it, not the header's own
  // number - see CAMERA_ZOOM_TILE_OFFSET.
  return zooms.minZoom - CAMERA_ZOOM_TILE_OFFSET
}

/** A rectangle of ground an archive on this phone was built for: a cell's
 *  core bounds, or a whole-sheet archive's declared header bounds. */
export interface Footprint {
  west: number
  south: number
  east: number
  north: number
}

export type Coverage = 'covered' | 'outside' | 'unknown'

/**
 * Whether the ground at a point is inside what this phone downloaded - the
 * horizontal edge, answered the way `archiveCoversZoom` answers the vertical
 * one.
 *
 * `null` is "not established yet" and answers `unknown`, for exactly the
 * reason that function answers `true`: not-looked-yet must never render as
 * your-download-does-not-reach-here. An EMPTY set answers `unknown` too - a
 * phone holding nothing has no edge to be outside of, and that phone's flags
 * already exist (lib/backgroundHealth.ts's `nothing-to-draw`).
 *
 * So `outside` is claimed only when something is held and the point is in
 * none of it, which makes the claim conservative in the one direction that
 * matters. Inside a footprint but off the thin band its tiles actually cover,
 * this says nothing - the same silence the app kept before cells existed. A
 * false "outside" would send a hiker to town for a download they have, and
 * #352 already shipped the neighbouring mistake once: a hiker past the edge
 * of their package, offline, told their download was damaged.
 */
export function coverageAt(
  footprints: readonly Footprint[] | null,
  lon: number,
  lat: number,
): Coverage {
  if (footprints === null || footprints.length === 0) return 'unknown'
  const inside = footprints.some(
    ({ west, south, east, north }) =>
      lon >= west && lon < east && lat >= south && lat < north,
  )
  return inside ? 'covered' : 'outside'
}
