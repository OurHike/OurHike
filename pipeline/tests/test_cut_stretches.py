"""Tests for cut_stretches.py - the trail-derived stretch units (#556).

Synthetic everything, in the shape the suites already share: the centerline
and half-mile markers come from tests/synthetic.py (so the calibrated axis
is real, just short), and the source archive is built in test code with each
tile's payload encoding its own address - the test_extract_package.py idiom
that makes byte-identity assertions meaningful.

The fixture geography: CENTERLINE_COORDS runs ~8.6 real miles. Cut at
3-mile stretches that is three units (0: 0-3, 1: 3-6, 2: 6-8.6), small
enough to reason about by hand and large enough to have real seams.
"""

import json

import pytest
from pmtiles.reader import MmapSource, all_tiles
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import write
from pyproj import Transformer
from rasterio.warp import transform as warp_transform
from shapely.geometry import LineString

import cut_stretches
from lib.tiling import tile_range_for_bounds
from tests.synthetic import CENTERLINE_COORDS, write_centerline, write_half_mile_markers

MILE_M = 1609.344


def _merc(lon, lat):
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    return transformer.transform(lon, lat)


def _tile_at(lon, lat, z):
    """The z/x/y tile containing a lon/lat point."""
    x_merc, y_merc = _merc(lon, lat)
    x0, x1, y0, y1 = tile_range_for_bounds((x_merc, y_merc, x_merc, y_merc), z)
    return z, x0, y0


def _points_along_line(coords, every_mi):
    """Lon/lat points every `every_mi` along the line, plus both ends -
    walked in EPSG:5070 so the spacing is real miles, like the markers."""
    xs, ys = warp_transform("EPSG:4326", "EPSG:5070", [c[0] for c in coords], [c[1] for c in coords])
    line = LineString(zip(xs, ys))
    distances = [0.0]
    d = every_mi * MILE_M
    while d < line.length:
        distances.append(d)
        d += every_mi * MILE_M
    distances.append(line.length)
    points = [line.interpolate(d) for d in distances]
    lons, lats = warp_transform("EPSG:5070", "EPSG:4326", [p.x for p in points], [p.y for p in points])
    return list(zip(lons, lats)), [d / MILE_M for d in distances]


def payload(z, x, y):
    return f"{z}/{x}/{y}".encode()


def _build_source(path, tiles):
    header = {
        "tile_type": TileType.MVT,
        "tile_compression": Compression.GZIP,
        "min_lon_e7": int(-75 * 1e7),
        "min_lat_e7": int(40 * 1e7),
        "max_lon_e7": int(-73 * 1e7),
        "max_lat_e7": int(42 * 1e7),
        "center_lon_e7": int(-74 * 1e7),
        "center_lat_e7": int(41 * 1e7),
        "center_zoom": 0,
    }
    with write(str(path)) as writer:
        for z, x, y in sorted(set(tiles), key=lambda t: zxy_to_tileid(*t)):
            writer.write_tile(zxy_to_tileid(z, x, y), payload(z, x, y))
        writer.finalize(header, {"name": "source", "vector_layers": ["kept"]})
    return path


def read_all(path):
    with open(path, "rb") as f:
        return {zxy: data for zxy, data in all_tiles(MmapSource(f))}


@pytest.fixture()
def axis_files(tmp_path):
    centerline = tmp_path / "centerline.geojson"
    markers = tmp_path / "half_mile_points.geojson"
    write_centerline(centerline)
    write_half_mile_markers(markers)
    return centerline, markers


def _cut(tmp_path, axis_files, tiles, **kwargs):
    centerline, markers = axis_files
    source = _build_source(tmp_path / "source.pmtiles", tiles)
    out_dir = tmp_path / "out"
    manifest = cut_stretches.cut_stretches(
        source,
        "at_basemap",
        centerline_path=centerline,
        markers_path=markers,
        out_dir=out_dir,
        stretch_miles=kwargs.pop("stretch_miles", 3.0),
        margin_miles=kwargs.pop("margin_miles", 0.25),
        **kwargs,
    )
    return out_dir, manifest


def _trail_tiles(z=15):
    """One z15 tile (~0.76 mi across at this latitude) at every half mile of
    the synthetic line - the corridor archive in miniature - with the mile
    each sample sits at. z15 so tiles are meaningfully smaller than the
    3-mile test stretches; at z13 a tile is about a stretch wide and every
    assertion about seams goes mushy."""
    points, miles = _points_along_line(CENTERLINE_COORDS, 0.5)
    return [_tile_at(lon, lat, z) for lon, lat in points], miles


def test_every_tile_lands_in_the_stretch_its_miles_say(tmp_path, axis_files):
    tiles, miles = _trail_tiles()
    out_dir, _manifest = _cut(tmp_path, axis_files, tiles, margin_miles=0.0)

    for stretch_id, lo, hi in ((0, 0.0, 3.0), (1, 3.0, 6.0), (2, 6.0, 99.0)):
        cut = read_all(out_dir / f"at_basemap_stretch_{stretch_id:02d}.pmtiles")
        for tile, mile in zip(tiles, miles):
            if lo + 0.3 < mile < hi - 0.3:  # clear of the seams, where tile extent straddles
                assert tile in cut, f"tile at mile {mile:.1f} missing from stretch {stretch_id}"
                assert cut[tile] == payload(*tile), "tile bytes must be copied verbatim"


def test_a_seam_tile_rides_in_both_neighbours(tmp_path, axis_files):
    """SEAM_MARGIN_MILES is the data-side share of #552's 'a wrong answer
    must not cost map where somebody is walking': the tiles around a
    boundary mile belong to both sides of it."""
    tiles, miles = _trail_tiles()
    out_dir, _manifest = _cut(tmp_path, axis_files, tiles, margin_miles=0.5)

    seam_tile = next(tile for tile, mile in zip(tiles, miles) if abs(mile - 3.0) < 0.1)
    assert seam_tile in read_all(out_dir / "at_basemap_stretch_00.pmtiles")
    assert seam_tile in read_all(out_dir / "at_basemap_stretch_01.pmtiles")


def test_context_tiles_publish_once_not_per_stretch(tmp_path, axis_files):
    """#193 measured the context duplicated per package by construction;
    the stretch scheme's answer is one shared context artifact."""
    tiles, _miles = _trail_tiles()
    context_tile = _tile_at(*CENTERLINE_COORDS[0], 5)
    out_dir, manifest = _cut(tmp_path, axis_files, [*tiles, context_tile])

    context = read_all(out_dir / "at_basemap_context.pmtiles")
    assert context_tile in context
    for stretch_id in (0, 1, 2):
        assert context_tile not in read_all(out_dir / f"at_basemap_stretch_{stretch_id:02d}.pmtiles")
    assert "at_basemap_context.pmtiles" in manifest["artifacts"]


def test_an_empty_stretch_fails_the_cut(tmp_path, axis_files):
    """A stretch with no tiles means the axis and the archive disagree about
    where the trail is - shipping it would cover nothing and fail nobody."""
    tiles, miles = _trail_tiles()
    only_southern = [tile for tile, mile in zip(tiles, miles) if mile < 3.0]

    with pytest.raises(SystemExit, match="no tiles"):
        _cut(tmp_path, axis_files, only_southern)


def test_the_index_names_every_stretch_with_its_core_miles(tmp_path, axis_files):
    tiles, _miles = _trail_tiles()
    out_dir, manifest = _cut(tmp_path, axis_files, tiles)

    index = json.loads((out_dir / "at_basemap_stretches.json").read_text())
    assert index["stretch_miles"] == 3.0
    assert [s["id"] for s in index["stretches"]] == [0, 1, 2]
    assert index["stretches"][0]["miles"] == [0.0, 3.0]
    assert index["stretches"][1]["miles"] == [3.0, 6.0]
    lo, hi = index["stretches"][2]["miles"]
    assert lo == 6.0 and hi == pytest.approx(index["axis_top_mile"])
    # Core intervals tile the trail exactly - no gaps for a client to fall
    # into, no overlap for one to double-count. The margin is generosity in
    # the bytes, deliberately not a promise in the metadata.
    for earlier, later in zip(index["stretches"], index["stretches"][1:]):
        assert earlier["miles"][1] == later["miles"][0]

    for entry in index["stretches"]:
        assert entry["key"] in manifest["artifacts"]
        artifact = manifest["artifacts"][entry["key"]]
        assert artifact["size_bytes"] == (out_dir / entry["key"]).stat().st_size
        assert len(artifact["sha256"]) == 64


def test_the_cuts_keep_the_sources_metadata_and_format(tmp_path, axis_files):
    """vector_layers is what a style draws from; tile_type/compression are
    what makes verbatim byte copies readable. Losing either is an archive
    that downloads fine and renders nothing."""
    from pmtiles.reader import Reader

    tiles, _miles = _trail_tiles()
    out_dir, _manifest = _cut(tmp_path, axis_files, tiles)

    with open(out_dir / "at_basemap_stretch_01.pmtiles", "rb") as f:
        source = MmapSource(f)
        reader = Reader(source)
        assert reader.metadata()["vector_layers"] == ["kept"]
        header = reader.header()
        assert header["tile_type"] == TileType.MVT
        assert header["tile_compression"] == Compression.GZIP
