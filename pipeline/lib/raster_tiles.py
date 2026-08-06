"""Render web-mercator raster tiles directly from native-resolution USGS
quads - the warp-once core of issue #191.

WHY THIS EXISTS

The shipped raster chain resampled three times: quads (2.032 m/px native)
were bilinear-downsampled to an 11.13 m/px mosaic intermediate
(spike_raster_mosaic.py), bilinear-resampled again to the tile grid
(export_pmtiles.py), and then upscaled 2x on retina phones by the client's
tileSize declaration. Net ~88x below the source's pixel count, through a
2x2-tap kernel that is wrong for decimating 1-2 px contour and text ink.

Here each tile is produced by ONE warp: a WarpedVRT from the
neatline-cropped quad straight onto the tile's own EPSG:3857 grid, with the
resampling kernel chosen for what that zoom actually does to the pixels -
`average` where the warp decimates hard (correct for shrinking cartographic
ink; gdal2tiles' own default), `cubic` near native resolution, where a
smoothing kernel would blur ink the zoom can actually carry. Lanczos was
considered for the near-native case and rejected: it rings into the nodata
edge every corridor-clipped quad has, and a halo along every seam is a
worse artifact than cubic's slightly softer ink.

This module is deliberately pure geometry+raster: no fetching, no cell
manifest, no archive writing. render_cell_tiles.py drives it per fan-out
job and the tests drive it with synthetic quads.
"""

import math

import numpy as np
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from shapely.geometry import box

from lib.tiling import tile_bounds_merc, tile_range_for_bounds

MERC_CRS = "EPSG:3857"

TILE_PX = 512

# US Topo GeoTIFFs are 300-dpi renders of a 1:24,000 sheet: 24000 / 300dpi
# * 25.4mm = 2.032 m/px, verified against a real corridor quad in #191.
NATIVE_RES_M = 2.032

# The first zoom whose tiles are near the source's native resolution. At the
# corridor's latitudes (~34-46N, cos ~0.70-0.83) a z14 512px tile is
# 3.3-4.0 m/px - only 1.6-2.0x native, squarely where the kernel is shaping
# ink rather than summarising it. z13 is 6.6-7.9 m/px, 3.3-3.9x native:
# decimation territory. (Issue #191 quotes z14 as 4.78 m/px - that is the
# equatorial figure; meters_per_pixel below is the checkable arithmetic.)
NEAR_NATIVE_ZOOM = 14


def resampling_for(zoom: int) -> Resampling:
    """The kernel that matches what this zoom does to native pixels: average
    for heavy decimation, cubic near native. See the module docstring for
    why lanczos is deliberately not the near-native choice."""
    return Resampling.cubic if zoom >= NEAR_NATIVE_ZOOM else Resampling.average


def tile_transform(z: int, x: int, y: int, tile_px: int = TILE_PX):
    """The affine transform of one XYZ tile's tile_px-square EPSG:3857 grid."""
    from rasterio.transform import from_bounds

    west, south, east, north = tile_bounds_merc(z, x, y)
    return from_bounds(west, south, east, north, tile_px, tile_px)


def neatline_box_merc(neatline_4326):
    """A quad's USGS-metadata neatline - the true mapped area, inside the
    printed collar - as an EPSG:3857 polygon. Exact, not approximate: web
    mercator maps meridians and parallels to straight lines, so a lon/lat
    box IS a mercator box and needs no edge densification."""
    from rasterio.warp import transform_bounds

    return box(*transform_bounds("EPSG:4326", MERC_CRS, *neatline_4326))


def render_tile_from_quads(z, x, y, quads, tile_px: int = TILE_PX):
    """One tile from native quads: a single warp per quad onto the tile's own
    grid, composited first-wins.

    `quads` is a list of (dataset, neatline_merc) pairs: an open rasterio
    dataset in whatever CRS the quad natively carries (the per-quad UTM
    zones are exactly why the warp happens here per tile rather than once
    into a shared intermediate), and the quad's neatline as an EPSG:3857
    polygon, or None to skip collar removal.

    The neatline is applied AFTER the warp, on the tile's own grid, rather
    than by cropping the source: a lon/lat neatline is not axis-aligned in
    the quad's UTM grid, so a source-side window crop keeps collar slivers
    at the corners - printed border ink that would composite into
    neighbouring tiles as if it were map. spike_raster_mosaic's
    open_cropped_vrt avoids that by warping to a 4326 grid first, but at
    TARGET_RES_DEG - the 11 m degradation this module exists to drop - so
    the native path masks per tile instead, which is exact at every zoom.

    Returns a (3, tile_px, tile_px) uint8 array, or None when nothing real
    covers the tile. All-zero means nodata by this pipeline's standing
    convention (encode_webp documents the honest limitation).

    First-wins compositing matches rasterio.merge's default, which is what
    the cell mosaics did - so quad overlap keeps resolving the same way it
    always has, just at native resolution.
    """
    from rasterio.features import geometry_mask

    transform = tile_transform(z, x, y, tile_px)
    resampling = resampling_for(z)

    out = np.zeros((3, tile_px, tile_px), dtype="uint8")
    filled = np.zeros((tile_px, tile_px), dtype=bool)

    for dataset, neatline_merc in quads:
        with WarpedVRT(
            dataset,
            crs=MERC_CRS,
            transform=transform,
            width=tile_px,
            height=tile_px,
            resampling=resampling,
            # 0 is nodata end to end: the source quads carry it, and the
            # WebP encoder derives alpha from it.
            nodata=0,
        ) as vrt:
            data = vrt.read(indexes=[1, 2, 3])
        if neatline_merc is not None:
            outside = geometry_mask(
                [neatline_merc.__geo_interface__],
                out_shape=(tile_px, tile_px),
                transform=transform,
            )
            data[:, outside] = 0
        coverage = data.any(axis=0) & ~filled
        if not coverage.any():
            continue
        out[:, coverage] = data[:, coverage]
        filled |= coverage

    if not filled.any():
        return None
    return out


WEBP_QUALITY = 80


def encode_webp(arr, quality: int = WEBP_QUALITY) -> bytes:
    """RGBA WebP, alpha derived from the all-zero nodata convention - the
    same encoding (and the same honest limitation: a genuinely pure-black
    source pixel becomes transparent) export_pmtiles.py shipped, lifted here
    so the per-cell renderer and assemble share one encoder. Scanned topo
    ink is essentially never exactly 0 after resampling, and one see-through
    pixel is a far smaller wrong than the black continent an RGB encode of a
    mostly-empty corridor tile would be."""
    import io

    from PIL import Image

    rgb = np.moveaxis(arr, 0, -1)
    alpha = np.where(rgb.any(axis=-1), 255, 0).astype("uint8")
    img = Image.fromarray(np.dstack([rgb, alpha]), mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=quality)
    return buf.getvalue()


def tiles_intersecting_geom(geom_merc, zoom: int):
    """(x, y) of every tile at `zoom` whose bounds intersect the geometry."""
    x0, x1, y0, y1 = tile_range_for_bounds(geom_merc.bounds, zoom)
    return [
        (x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) if geom_merc.intersects(box(*tile_bounds_merc(zoom, x, y)))
    ]


def export_tiles(corridor_merc, band_merc, min_zoom: int, max_zoom: int, band_zoom: int):
    """Every (z, x, y) the archive should carry: corridor-wide below
    `band_zoom`, the near-trail band from there up (issue #191's tiered
    shape - z14 corridor-wide is ~4.6-4.9 GB where the 5-mile band a hiker
    actually walks in is ~1.8 GB with the z13 base).

    `band_merc` may be None when max_zoom never reaches band_zoom.
    """
    tiles = []
    for z in range(min_zoom, max_zoom + 1):
        region = corridor_merc if z < band_zoom else band_merc
        if region is None:
            raise ValueError(f"zoom {z} needs the near-trail band, and none was given")
        tiles.extend((z, x, y) for x, y in tiles_intersecting_geom(region, z))
    return tiles


def owns_tile(cell_bounds_4326, tile_bounds_4326) -> bool:
    """Whether a cell owns a tile: the tile's center falls inside the cell's
    half-open [west, east) x [south, north) box.

    Ownership is the fan-out's dedup rule - every tile is rendered by exactly
    one cell job, even at cell borders where the PIXELS need quads from both
    sides. (The job that owns a border tile fetches by tile footprint, so it
    holds the neighbour's quads too; ownership only decides who writes.)
    Half-open so a center sitting exactly on the shared edge belongs to one
    cell and not both - and tile centers at these zooms never coincide with
    whole-degree cell edges anyway, since tile edges are dyadic fractions of
    the mercator world, but the tie rule costs nothing to state.
    """
    west, south, east, north = cell_bounds_4326
    t_west, t_south, t_east, t_north = tile_bounds_4326
    cx = (t_west + t_east) / 2
    cy = (t_south + t_north) / 2
    return west <= cx < east and south <= cy < north


# The per-cell overview resolution, and the last zoom rendered from it.
#
# Overviews exist so assemble can draw the far-out zooms without every cell
# job's raw quads on one runner: each cell emits one small GeoTIFF, averaged
# in a single warp from native (still "warp once" - decimation happens once,
# with the right kernel). 24 m serves z0-10 honestly: a z10 pixel at the
# corridor's latitudes is ~55-66 m, at least 2.3x the overview's grid, so
# rendering from it is decimation, never upsampling. Everything nearer than
# z10 renders from the native quads directly (render_cell_tiles.py), which
# keeps every legibility-bearing zoom - z11 up, where contour and text ink
# resolves - on the native path.
OVERVIEW_RES_M = 24.0
OVERVIEW_MAX_ZOOM = 10
NATIVE_MIN_ZOOM = OVERVIEW_MAX_ZOOM + 1


def mask_outside(arr, geom_merc, z: int, x: int, y: int, tile_px: int = TILE_PX):
    """Zeroes every pixel outside `geom_merc` (nodata by this pipeline's
    all-zero convention). The native path needs this where the cell-mosaic
    path did not: quads are neatline-cropped, not corridor-clipped, so an
    edge tile would otherwise show ground beyond the 30-mile corridor that
    every other artifact honestly cuts at."""
    from rasterio.features import geometry_mask

    inside = ~geometry_mask(
        [geom_merc.__geo_interface__],
        out_shape=(tile_px, tile_px),
        transform=tile_transform(z, x, y, tile_px),
        invert=False,
    )
    arr[:, ~inside] = 0
    return arr


def render_overview(bounds_merc, quads, res_m: float = OVERVIEW_RES_M):
    """One cell's overview: every quad averaged straight from native onto a
    shared `res_m` EPSG:3857 grid over `bounds_merc`, first-wins composited
    with per-quad neatline masking - the same rules as the tile path, at the
    overview's resolution. Returns (array, transform); the caller owns
    writing and any corridor mask.

    Still "warp once": a native pixel that ends up in a z0-10 tile passes
    through exactly one decimation (here, with `average`) plus the
    final tile read from this grid - against the old chain's
    native->11m->tile double resample, and with the kernel that is right
    for shrinking ink at every step that shrinks it."""
    from rasterio.features import geometry_mask
    from rasterio.transform import from_bounds

    west, south, east, north = bounds_merc
    width = max(1, round((east - west) / res_m))
    height = max(1, round((north - south) / res_m))
    transform = from_bounds(west, south, east, north, width, height)

    out = np.zeros((3, height, width), dtype="uint8")
    filled = np.zeros((height, width), dtype=bool)
    for dataset, neatline_merc in quads:
        with WarpedVRT(
            dataset,
            crs=MERC_CRS,
            transform=transform,
            width=width,
            height=height,
            resampling=Resampling.average,
            nodata=0,
        ) as vrt:
            data = vrt.read(indexes=[1, 2, 3])
        if neatline_merc is not None:
            outside = geometry_mask(
                [neatline_merc.__geo_interface__],
                out_shape=(height, width),
                transform=transform,
            )
            data[:, outside] = 0
        coverage = data.any(axis=0) & ~filled
        if not coverage.any():
            continue
        out[:, coverage] = data[:, coverage]
        filled |= coverage

    return out, transform


def meters_per_pixel(zoom: int, latitude_deg: float, tile_px: int = TILE_PX) -> float:
    """Ground resolution of one tile pixel - the number the kernel choice and
    the size estimates are argued from, kept next to them so the argument is
    checkable."""
    world_m = 2 * math.pi * 6378137
    return world_m * math.cos(math.radians(latitude_deg)) / (2**zoom * tile_px)
