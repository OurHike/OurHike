"""Tiny synthetic raw layers for the CI dbt job (pipeline/DBT.md's CI plan).

CI has no fetched data and must not fetch any (TESTING.md: no real network,
no large data), so the dbt build there runs against a handful of
code-generated features shaped like the real layers - the same field names
load_raw.py and the staging models read off the real fetch
(GlobalID/Name for ATC's ANST_Facilities family, dbid/title/icon for
opentrail). Every documented opentrail icon appears once, so the
accepted_values test on the raw column and the seed join both exercise
their whole domain.

WHERE THE NON-A.T. FIELD NAMES COME FROM, since nothing here can reach the
live services: every column below is a name sources.json records as MEASURED
against the live layer, with a date - the `notes` field lists for
nynjtc_long_path and nynjtc_highlands_trail (2026-08-24), mohonk_trails
(2026-08-25), oprhp_trails (2026-08-18), oprhp_facilities and the DEC layers
(2026-08-27), usfs_trails and usfs_rec_sites (2026-09-02), plus the
structured `name_field`/`blaze_field`/`id_field`/`public_field`/
`asset_field`/`facility_field` keys, which are the same
measurements in machine-readable form. Nothing here is invented, and where a
layer's fields are NOT recorded the fixture carries none rather than a guess
- `oprhp_park_polygons` is that case and is deliberately property-free.

The VALUES follow the same rule where a domain was measured, because a
fixture that only ever shows the happy case proves nothing about the dirt:
DEC's MARKER carries a blank and the undeclared 'ORANGE AND RED' that
sources.json records on the live 5,286 rows; DEC's FOOT carries both Y and
M; PUBLICUSE carries an N so the flag the staging models pass through has
something to say; Mohonk's Blaze includes the 'N/A' string and a row with no
Blaze key at all (7 such rows measured on the live 304); NYNJTC's Long Path
Blaze is the lowercase 'aqua' all 43 real rows read; and OPRHP's ParksApp
carries both sides of its 5,822/3,000 split. NH GRANIT's BLAZE is the
sharpest case of the rule: it is a blank STRING on 7,574 of the live 7,643
Whites rows - because the Whites largely are not blazed, not because the
column is unpopulated - so most of that fixture's rows carry `' '` rather
than a colour, and the one that does carry White is the A.T. USFS's
`trail_type` carries SNOW beside TERRA for the same reason, and its
`national_trail_designation` spreads 1/2/3 across a single named trail
because that is what CRAWFORD PATH really does.

Refuses to write into a directory that already has one of its files:
this exists to fill an empty CI workspace, not to overwrite a real fetch.
"""

import argparse
import functools
import json
import math
import struct
from pathlib import Path

from load_raw import RAW_DIR

# One waypoint per documented icon code (fetch_opentrail.ICON_LEGEND's
# domain, held to it by tests/test_make_dbt_fixtures.py) - so the dbt-side
# accepted_values test and the seed join see every case, mapped and
# deliberately-unmapped alike.
OPENTRAIL_ICONS = ("c", "s", "o", "j", "w", "t", "r", "a")


def _feature_collection(features):
    """A GeoJSON FeatureCollection as a dict; write_fixtures() dumps it, so the transforms below edit it in place."""
    return {"type": "FeatureCollection", "features": features}


def _point(i):
    return {"type": "Point", "coordinates": [-74.0 + i * 0.01, 41.0 + i * 0.01]}


def _line(i):
    return {
        "type": "LineString",
        "coordinates": [[-74.0 + i * 0.01, 41.0 + i * 0.01], [-74.0 + i * 0.01, 41.005 + i * 0.01]],
    }


def _polygon(i):
    x, y = -74.0 + i * 0.01, 41.0 + i * 0.01
    return {"type": "Polygon", "coordinates": [[[x, y], [x + 0.005, y], [x + 0.005, y + 0.005], [x, y]]]}


def _atc_layer(name_prefix, count, extra=None, geometry=_point):
    """The ANST_Facilities shape: GlobalID/Name plus whatever per-layer
    columns the staging model reads, spelled exactly as upstream spells
    them (verified against the loaded warehouse 2026-08-18)."""
    return _feature_collection(
        [
            {
                "type": "Feature",
                "properties": {
                    "GlobalID": f"{name_prefix.lower().replace(' ', '-')}-{i}",
                    "Name": f"{name_prefix} {i}",
                    **{k: (v(i) if callable(v) else v) for k, v in (extra or {}).items()},
                },
                "geometry": geometry(i),
            }
            for i in range(count)
        ]
    )


def _communities_layer():
    # The one facilities-family departure: NAME, not Name.
    return _feature_collection(
        [
            {
                "type": "Feature",
                "properties": {"GlobalID": f"community-{i}", "NAME": f"Trail Town {i}"},
                "geometry": _point(i),
            }
            for i in range(2)
        ]
    )


def _club_sections_layer():
    return _feature_collection(
        [
            {
                "type": "Feature",
                "properties": {
                    "GlobalID": f"club-section-{i}",
                    "TRAIL_CLUB": f"Test Trail Club {i}",
                    "ACROYNM": f"TTC{i}",
                    "REGION": "New England",
                },
                "geometry": _polygon(i),
            }
            for i in range(2)
        ]
    )


def _half_mile_layer():
    return _feature_collection(
        [
            {
                "type": "Feature",
                "properties": {"Point_ID": i, "Measure": i * 0.5, "MeasureM": i * 804.672},
                "geometry": _point(i),
            }
            for i in range(4)
        ]
    )


# --- elevation, the A.T. half (#1793, stage 3) -------------------------------
#
# step_dem_sampling.py and today's export_elevation.py both read the DEM
# through a tile index (fetch_elevation.py's data/raw/elevation/
# tile_index.json), and CI fetches no tile. So the fixtures carry one: the
# smallest tile export_elevation.ElevationSampler reads the way it reads a
# real 3DEP cell - a single-band float32 GeoTIFF in EPSG:4269 with a declared
# nodata - over the two fixture centerline segments (`_line(0)`, `_line(1)`),
# plus the index naming it. Written byte by byte here rather than through
# rasterio, because CI's dbt job runs this file on requirements-dbt.txt,
# which has no rasterio.
#
# THE TILE HAS BOTH KINDS OF HOLE a profile meets, so parity reaches the null
# path (EL09): rows ELEVATION_FIXTURE_NODATA_ROWS are nodata across the
# tile, which the first segment crosses, and the tile stops short of the
# second segment's northern end, so the samples past it have no tile at all.
# Its edges sit half a pixel off both segments' longitudes, so no sample
# lands on a pixel boundary, where a last-bit difference between two ways of
# placing a point could read a neighbouring pixel.

#: Where the tile and its index land under the raw directory.
ELEVATION_FIXTURE_TILE = "elevation/fixture_n42w074.tif"
ELEVATION_FIXTURE_INDEX = "elevation/tile_index.json"
#: The tile's grid: its north-west corner, pixel size in degrees, and shape.
ELEVATION_FIXTURE_WEST = -74.0021
ELEVATION_FIXTURE_NORTH = 41.01365
ELEVATION_FIXTURE_PIXEL_DEG = 0.0002
ELEVATION_FIXTURE_WIDTH = 72
ELEVATION_FIXTURE_HEIGHT = 78
ELEVATION_FIXTURE_NODATA = -9999.0
ELEVATION_FIXTURE_NODATA_ROWS = (53, 54)
#: A Last-Modified, so the index pins the tile's edition and the sampler's
#: cache treats it as it treats a stamped 3DEP cell.
ELEVATION_FIXTURE_LAST_MODIFIED = "Thu, 01 Oct 2026 00:00:00 GMT"


def _elevation_fixture_metres(row: int, col: int) -> float:
    """The fixture ground: rising to the north, with a ripple, so feet carry real decimals."""
    if row in ELEVATION_FIXTURE_NODATA_ROWS:
        return ELEVATION_FIXTURE_NODATA
    return 200.0 + 1.3 * (ELEVATION_FIXTURE_HEIGHT - row) + 0.4 * col + 1.7 * math.sin(0.9 * col + 0.4 * row)


def _geotiff(width: int, height: int, pixels: list[float], west: float, north: float, pixel_deg: float, nodata: float) -> bytes:
    """A little-endian, uncompressed, one-strip, single-band float32 GeoTIFF in EPSG:4269 (NAD83, 3DEP's datum)."""
    data = struct.pack(f"<{width * height}f", *pixels)
    nodata_text = f"{nodata:g}".encode() + b"\0"
    geokeys = (1, 1, 0, 3, 1024, 0, 1, 2, 1025, 0, 1, 1, 2048, 0, 1, 4269)  # geographic, pixel-is-area, EPSG:4269
    # (tag, TIFF type, values): type 2 ASCII, 3 SHORT, 4 LONG, 12 DOUBLE.
    entries = [
        (256, 4, (width,)),
        (257, 4, (height,)),
        (258, 3, (32,)),
        (259, 3, (1,)),
        (262, 3, (1,)),
        (273, 4, (0,)),  # StripOffsets, filled in below
        (277, 3, (1,)),
        (278, 4, (height,)),
        (279, 4, (len(data),)),
        (284, 3, (1,)),
        (339, 3, (3,)),  # SampleFormat: IEEE float
        (33550, 12, (pixel_deg, pixel_deg, 0.0)),  # ModelPixelScale
        (33922, 12, (0.0, 0.0, 0.0, west, north, 0.0)),  # ModelTiepoint: pixel (0, 0) is (west, north)
        (34735, 3, geokeys),
        (42113, 2, nodata_text),  # GDAL_NODATA
    ]
    formats = {2: "s", 3: "H", 4: "I", 12: "d"}
    ifd_size = 2 + 12 * len(entries) + 4
    extra_offset = 8 + ifd_size
    extra = b""
    encoded = []
    for tag, kind, values in entries:
        count = len(values)
        payload = struct.pack(f"<{count}s", values) if kind == 2 else struct.pack(f"<{count}{formats[kind]}", *values)
        encoded.append((tag, kind, count, payload))
        if len(payload) > 4:
            extra += payload + b"\0" * (len(payload) % 2)
    data_offset = extra_offset + len(extra)
    ifd = struct.pack("<H", len(entries))
    cursor = extra_offset
    for tag, kind, count, payload in encoded:
        if tag == 273:
            payload = struct.pack("<I", data_offset)
        if len(payload) > 4:
            ifd += struct.pack("<HHII", tag, kind, count, cursor)
            cursor += len(payload) + len(payload) % 2
        else:
            ifd += struct.pack("<HHI", tag, kind, count) + payload.ljust(4, b"\0")
    ifd += struct.pack("<I", 0)
    return b"II" + struct.pack("<HI", 42, 8) + ifd + extra + data


def _elevation_fixtures(raw_dir: Path) -> dict[str, str | bytes]:
    """The DEM fixture's tile and the tile index naming it, by path under raw_dir.

    The index names the tile by its absolute path, as export_elevation's
    _gdal_source hands a local entry to GDAL, so the step and the exporter
    find it from any working directory."""
    pixels = [
        _elevation_fixture_metres(row, col) for row in range(ELEVATION_FIXTURE_HEIGHT) for col in range(ELEVATION_FIXTURE_WIDTH)
    ]
    tile = _geotiff(
        ELEVATION_FIXTURE_WIDTH,
        ELEVATION_FIXTURE_HEIGHT,
        pixels,
        ELEVATION_FIXTURE_WEST,
        ELEVATION_FIXTURE_NORTH,
        ELEVATION_FIXTURE_PIXEL_DEG,
        ELEVATION_FIXTURE_NODATA,
    )
    bounds = [
        ELEVATION_FIXTURE_WEST,
        ELEVATION_FIXTURE_NORTH - ELEVATION_FIXTURE_HEIGHT * ELEVATION_FIXTURE_PIXEL_DEG,
        ELEVATION_FIXTURE_WEST + ELEVATION_FIXTURE_WIDTH * ELEVATION_FIXTURE_PIXEL_DEG,
        ELEVATION_FIXTURE_NORTH,
    ]
    index = [
        {
            "url": (raw_dir / ELEVATION_FIXTURE_TILE).resolve().as_posix(),
            "bounds": bounds,
            "last_modified": ELEVATION_FIXTURE_LAST_MODIFIED,
        }
    ]
    return {ELEVATION_FIXTURE_TILE: tile, ELEVATION_FIXTURE_INDEX: json.dumps(index)}


def _opentrail_layer():
    return _feature_collection(
        [
            {
                "type": "Feature",
                "properties": {"dbid": i, "title": f"Waypoint {icon}", "icon": icon},
                "geometry": {"type": "Point", "coordinates": [-73.9 + i * 0.01, 41.1]},
            }
            for i, icon in enumerate(OPENTRAIL_ICONS)
        ]
    )


# --- The non-A.T. organizations' layers (Phase D, #100) --------------------
#
# fetch_external_layers.py writes these under data/raw/external/, and
# load_raw.py reads them from there - so the fixtures live in the same
# subdirectory rather than flattening a boundary that exists on disk.


def _features(rows, geometry):
    """One FeatureCollection from a list of property dicts.

    A row may omit a key entirely, which is a real upstream shape rather than
    a shortcut here: Mohonk publishes 7 of its 304 segments with no Blaze
    value at all, and a fixture that always writes every key could not
    exercise the null branch of a staging model.
    """
    return _feature_collection([{"type": "Feature", "properties": row, "geometry": geometry(i)} for i, row in enumerate(rows)])


def _oprhp_trails_layer():
    """oprhp_trails' measured field list (sources.json notes, 2026-08-18).

    `Blaze` and `Map_Blaze` are the two blaze columns sources.json names.
    GlobalID is the key (decision 40): unique on 16,641 of 16,641 rows,
    measured 2026-10-01.
    The notes say the layer carries "up to three Blaze colours" but spell
    only one of them, so only the spelled one is here - two invented column
    names would be two staging columns nothing upstream answers for.
    """
    common = {
        "Unit": "Palisades",
        "Surface": "Native",
        "Status": "Open",
        "Public_": "Y",
        "Foot": "Y",
        "Bike": "N",
        "Horse": "N",
        "XC": "N",
        "SS": "N",
        "Snowmb": "N",
    }
    return _features(
        [
            {
                **common,
                "GlobalID": "{00000000-0000-4000-8000-000000000401}",
                "Name": "Fixture Ridge Trail",
                "Alt_Name": "Ridge",
                "Blaze": "Blue",
                "Map_Blaze": "Blue",
                "Miles": 1.4,
            },
            {
                **common,
                "GlobalID": "{00000000-0000-4000-8000-000000000402}",
                "Name": "Fixture Loop Trail",
                "Alt_Name": None,
                "Blaze": "Red",
                "Map_Blaze": "Red",
                "Miles": 0.8,
            },
        ],
        _line,
    )


def _oprhp_trail_closures_layer():
    """Only `Name` and `Descript`, which are all sources.json evidences.

    The entry records a count (4 features on 2026-08-18) and a last-edit
    date, and names these two through `reason_field`/`place_field`. Nothing
    records the rest of the schema, so nothing else is here. The layer also
    declares `may_be_empty`, so an honest fixture is small.
    """
    return _features(
        [{"Name": "Bridge out", "Descript": "Fixture State Park, upper loop"}],
        _polygon,
    )


def _oprhp_facilities_layer():
    """oprhp_facilities: Name/Facility/Asset/Sub_Asset/ParksApp/Public_.

    `Public_` reads Y on all 8,823 real rows and discriminates nothing;
    `ParksApp` is the field that splits 5,822/3,000, and both sides appear
    here because export_nearby_poi.py reads the N side as low confidence
    rather than dropping it. `Asset` is the coded integer 1-17 whose domain
    the service does not publish - carried as the integer it is, undecoded.
    GlobalID is the key (decision 40): unique on 8,823 of 8,823 rows,
    measured 2026-10-01, where the registry's `id_field` still says OBJECTID.
    """
    return _features(
        [
            {
                "GlobalID": "{00000000-0000-4000-8000-000000000501}",
                "Name": "Fixture Spigot",
                "Facility": "Fixture State Park",
                "Asset": 7,
                "Sub_Asset": "Water Spigot",
                "ParksApp": "Y",
                "Public_": "Y",
            },
            {
                "GlobalID": "{00000000-0000-4000-8000-000000000502}",
                "Name": None,
                "Facility": "Fixture State Park",
                "Asset": 7,
                "Sub_Asset": "Drinking Fountain",
                "ParksApp": "N",
                "Public_": "Y",
            },
            {
                "GlobalID": "{00000000-0000-4000-8000-000000000503}",
                "Name": None,
                "Facility": "Fixture State Park",
                "Asset": 3,
                "Sub_Asset": "Lean-to",
                "ParksApp": "N",
                "Public_": "Y",
            },
        ],
        _point,
    )


def _oprhp_park_polygons_layer():
    """Geometry and nothing else, deliberately.

    sources.json records a count (858 boundary polygons, 2026-08-18) and a
    last-edit date for this layer and NOT ONE FIELD NAME. Writing properties
    here would be inventing a schema, and a staging model built on invented
    columns is worse than no staging model - so this layer loads to raw and
    stops there. DBT.md's Phase D section records the exclusion.
    """
    return _features([{}], _polygon)


def _nynjtc_long_path_layer():
    """The measured field list, 2026-08-24. Blaze is the lowercase 'aqua'
    all 43 real rows read - a plain string with no coded domain, which is
    why nothing decodes it here or downstream."""
    common = {"Trail_Name": "Long Path", "Blaze": "aqua", "Maintainer": "NYNJTC", "Source": "NYNJTC"}
    return _features(
        [
            {**common, "Mileage": 3.2, "Comments": "fixture row", "LP_Section": "1", "GuideURL": "https://example.invalid/lp/1"},
            {**common, "Mileage": 2.7, "Comments": None, "LP_Section": "2", "GuideURL": "https://example.invalid/lp/2"},
        ],
        _line,
    )


def _nynjtc_highlands_trail_layer():
    """Trail_Name/Section_Name/Source/MapOrder, measured 2026-08-24.

    NO BLAZE KEY, and that absence is the fixture's point: sources.json
    records that this layer publishes no blaze at all, and the staging model
    must have no blaze column to match. A fixture that quietly supplied one
    would let a column exist that upstream cannot fill.
    """
    return _features(
        [
            {"Trail_Name": "Highlands", "Section_Name": "NJ 2", "Source": "NYNJTC", "MapOrder": 2},
            {"Trail_Name": "Highlands", "Section_Name": "NJ 3", "Source": "NYNJTC", "MapOrder": 3},
        ],
        _line,
    )


def _mohonk_trails_layer():
    """Measured 2026-08-25. Blaze is a genuine coded field whose live values
    include the literal string 'N/A' (124 of 304 rows) and, on 7 rows, no
    value at all - both shapes appear here. GlobalID is the key (decision 40):
    unique on 304 of 304 rows, measured 2026-10-01."""
    common = {
        "General_Classification": "Trail",
        "Classification": "Foot",
        "Use_": "Hiking",
        "Surface": "Native",
        "Manager": "Mohonk Preserve",
    }
    return _features(
        [
            {
                **common,
                "GlobalID": "{00000000-0000-4000-8000-000000000301}",
                "Name": "Fixture Carriage Road",
                "Blaze": "Blue",
                "Mileage": 1.1,
                "Owner": "Mohonk Preserve",
            },
            {
                **common,
                "GlobalID": "{00000000-0000-4000-8000-000000000302}",
                "Name": "Fixture Ledge Path",
                "Blaze": "N/A",
                "Mileage": 0.6,
                "Owner": "Mohonk Preserve",
            },
            # No Blaze key at all - the 7-row shape, not an oversight.
            {
                **common,
                "GlobalID": "{00000000-0000-4000-8000-000000000303}",
                "Name": "Marakill Woods North",
                "Mileage": 0.4,
                "Owner": "NYS OPRHP/PIPC",
            },
        ],
        _line,
    )


def _white_mountains_line(i):
    """A LineString in the Whites rather than in the Hudson Valley.

    The other builders here sit at -74/41 because that is where every layer
    before them was. These three are White Mountain National Forest layers
    (#1207), and a fixture claiming to be a WMNF trail at the latitude of
    Harriman would be the one thing in this file that is not shaped like what
    it stands for. Nothing reads the coordinates today - no staging model
    exists for these yet - so this buys correctness for the day one does
    rather than fixing a live defect."""
    return {
        "type": "LineString",
        "coordinates": [[-71.3 + i * 0.01, 44.2 + i * 0.01], [-71.3 + i * 0.01, 44.205 + i * 0.01]],
    }


def _white_mountains_point(i):
    return {"type": "Point", "coordinates": [-71.3 + i * 0.01, 44.2 + i * 0.01]}


def _usfs_trails_layer():
    """usfs_trails' measured field list and value shapes, 2026-09-02.

    Three measured shapes that a happy-case fixture would miss:

    - `trail_type` SNOW alongside TERRA. 549 of the live 2,093 WMNF rows are
      snowmobile and water corridors, so a fixture with only TERRA would let a
      staging model forget that this layer needs filtering at all.
    - `hiker_pedestrian_managed` absent on those rows. It is a SEASON STRING
      ('01/01-12/31' on the hiking rows), not a boolean, and 642 live rows
      carry none - the shape any "is this walkable" logic has to survive.
    - `national_trail_designation` carrying 1, 2 AND 3 across rows of one
      named trail. That is the live behaviour of CRAWFORD PATH and it is the
      evidence behind sources.json's @unvalidated warning that code 3 is not
      an A.T. filter; a fixture where each trail had one code would quietly
      support the reading the registry warns against.
    """
    common = {"admin_org": "092204", "managing_org": "092204", "trail_class": "3"}
    return _features(
        [
            # One named trail across three designation codes - Crawford Path's live shape.
            {
                **common,
                "trail_name": "FIXTURE CRAWFORD PATH",
                "trail_no": "1234",
                "trail_type": "TERRA",
                "national_trail_designation": 3,
                "gis_miles": 2.4,
                "segment_length": 2.4,
                "hiker_pedestrian_managed": "01/01-12/31",
            },
            {
                **common,
                "trail_name": "FIXTURE CRAWFORD PATH",
                "trail_no": "1234",
                "trail_type": "TERRA",
                "national_trail_designation": 1,
                "gis_miles": 1.1,
                "segment_length": 1.1,
                "hiker_pedestrian_managed": "01/01-12/31",
            },
            {
                **common,
                "trail_name": "FIXTURE CRAWFORD PATH",
                "trail_no": "1234",
                "trail_type": "TERRA",
                "national_trail_designation": 2,
                "gis_miles": 0.8,
                "segment_length": 0.8,
                "hiker_pedestrian_managed": "01/01-12/31",
            },
            # Not the A.T., and carrying code 3 anyway - the GREAT GULF shape.
            {
                **common,
                "trail_name": "FIXTURE GREAT GULF",
                "trail_no": "5678",
                "trail_type": "TERRA",
                "national_trail_designation": 3,
                "gis_miles": 5.2,
                "segment_length": 5.2,
                "hiker_pedestrian_managed": "01/01-12/31",
            },
            # A snowmobile corridor: no hiker season key at all, not a null one.
            {
                **common,
                "trail_name": "FIXTURE BROOK SNOMO",
                "trail_no": "9012",
                "trail_type": "SNOW",
                "national_trail_designation": 1,
                "gis_miles": 1.15,
                "segment_length": 1.15,
            },
        ],
        _white_mountains_line,
    )


def _usfs_rec_sites_layer():
    """usfs_rec_sites' measured field list and site_type census, 2026-09-02.

    One row per site_type this pipeline has a verdict about, so the fixture
    covers the whole of sources.json's `poi_coverage` answer for USFS rather
    than its useful half: TRAILHEAD (7,358 live nationwide, the parking
    verdict), CAMPGROUND (4,183, the campsite verdict and its car-campground
    caveat), OBSERVATION SITE (636, viewpoint) and LOOKOUT/CABIN (815, the
    `unsuitable` shelter verdict).

    AND ONE ROW THAT EXISTS TO STAY OUT. 'CAMPING AREA' is the layer's largest
    type at 10,783 nationwide, it is dispersed camping, and it is held back
    (sources.json's usfs_dispersed_camping_holdback). A fixture without it
    could not catch the regression that matters most here - somebody widening
    USFS_SITE_TYPES and publishing 10,783 dispersed campsites - so the row is
    present with the live development_scale 0 and a road-reference name, and
    tests/test_export_nearby_poi.py asserts it does not come out the far end.

    `fee_charged` and `total_capacity` are carried because the live layer has
    them - they were never profiled, so no value here is a claim about their
    distribution."""
    common = {"managing_org": "092204", "recarea_name": "Fixture Recreation Area"}
    return _features(
        [
            {**common, "site_name": "Fixture Notch Trailhead", "site_type": "TRAILHEAD", "fee_charged": "N"},
            {
                **common,
                "site_name": "Fixture Brook Campground",
                "site_type": "CAMPGROUND",
                "fee_charged": "Y",
                "total_capacity": 48,
            },
            {**common, "site_name": "Fixture Ledge Overlook", "site_type": "OBSERVATION SITE", "fee_charged": "N"},
            {**common, "site_name": "Fixture Summit Lookout", "site_type": "LOOKOUT/CABIN", "fee_charged": "Y"},
            # Dispersed camping - held back, and here so a test can prove it.
            # The name shape and development_scale are the live ones.
            {**common, "site_name": "RD 614 SITE 13", "site_type": "CAMPING AREA", "development_scale": "0", "fee_charged": "N"},
        ],
        _white_mountains_point,
    )


def _njdep_park_trails_layer():
    """njdep_park_trails' measured field list and value shapes, 2026-09-09.

    THE POINT OF THIS FIXTURE IS THE THREE COLOUR FIELDS, because the layer
    publishes TRL_COLOR, ALT_TRL_COLOR and PBN_COLOR and only one of them is
    the blaze. sources.json records the judgement and reference/
    blaze_mapping.json's njdep_park_trails table records why: on the live
    3,305 rows PBN_COLOR reads 'Unmarked' on 340 against TRL_COLOR's 228 and
    otherwise tracks it, and ALT_TRL_COLOR is the literal string 'NA' on
    2,611 (79%) - a second colour where two trails share tread. So the rows
    here carry all three, disagreeing the way the live layer disagrees, and a
    staging model that reached for the wrong one would be visibly wrong here.

    TRL_COLOR's values are the live vocabulary's four shapes: a palette
    colour, the compound 'Black/White' (37 rows upstream, deferred in the
    mapping table because the client draws one paint per line), a paint the
    closed palette has no member for ('Gray', 236 rows), and 'Unmarked' (228)
    - which maps to None/'Unblazed' rather than Unknown, because BLAZE_TYPE
    says 'Unmarked' on 856 rows and NJDEP therefore records unmarked tread
    deliberately.

    HIKING_TRL and MOTO_TRL are the clean Yes/No pair that makes this layer
    easier than nh_granit_trails' PED: 'Yes' 3,226, 'No' 75, null 4 - so the
    fixture carries a No row and a null-free majority. The 35 MOTO_TRL 'Yes'
    rows are the motorized corridor a filter should drop, and one is here."""
    common = {"PARK_NAME": "Fixture State Park", "SITE_NAME": "Fixture Site", "OWNERSHIP": "NJDEP"}
    return _features(
        [
            {
                **common,
                "TRAIL_NAME": "Fixture Ridge Trail",
                "TRL_COLOR": "Blue",
                "ALT_TRL_COLOR": "NA",
                "PBN_COLOR": "Blue",
                "BLAZE_TYPE": "Painted Blaze",
                "BLAZE_DESC": "Blue rectangle",
                "TRL_TYPE_S": "Official",
                "TRL_DIFF": "Moderate",
                "HIKING_TRL": "Yes",
                "MOTO_TRL": "No",
                "TRL_LENGTH": 2.4,
            },
            # Two trails on one tread: TRL_COLOR compound, ALT_TRL_COLOR the
            # second paint, PBN_COLOR collapsed to one - the shape that makes
            # picking a colour field a decision rather than a lookup.
            {
                **common,
                "TRAIL_NAME": "Fixture Shared Tread Trail",
                "TRL_COLOR": "Black/White",
                "ALT_TRL_COLOR": "White",
                "PBN_COLOR": "Black",
                "BLAZE_TYPE": "Painted Blaze",
                "TRL_TYPE_S": "Official",
                "TRL_DIFF": "Easy to Moderate",
                "HIKING_TRL": "Yes",
                "MOTO_TRL": "No",
                "TRL_LENGTH": 1.1,
            },
            # A real paint the closed palette has no member for; renders neutral.
            {
                **common,
                "TRAIL_NAME": "Fixture Gray Trail",
                "TRL_COLOR": "Gray",
                "ALT_TRL_COLOR": "NA",
                "PBN_COLOR": "Gray",
                "BLAZE_TYPE": "Carsonite Post",
                "TRL_TYPE_S": "Connector",
                "TRL_DIFF": "Easy",
                "HIKING_TRL": "Yes",
                "MOTO_TRL": "No",
                "TRL_LENGTH": 0.6,
            },
            # Unmarked tread, recorded as such by NJDEP in both fields.
            {
                **common,
                "TRAIL_NAME": "Fixture Woods Road",
                "TRL_COLOR": "Unmarked",
                "ALT_TRL_COLOR": "NA",
                "PBN_COLOR": "Unmarked",
                "BLAZE_TYPE": "Unmarked",
                "TRL_TYPE_S": "Official",
                "TRL_DIFF": "Unknown",
                "HIKING_TRL": "Yes",
                "MOTO_TRL": "No",
                "TRL_LENGTH": 3.0,
            },
            # The two rows a hiking filter should drop, one each way.
            {
                **common,
                "TRAIL_NAME": "Fixture ORV Route",
                "TRL_COLOR": "Orange",
                "ALT_TRL_COLOR": "NA",
                "PBN_COLOR": "Orange",
                "BLAZE_TYPE": "Metal Blaze",
                "TRL_TYPE_S": "Official",
                "TRL_DIFF": "Difficult",
                "HIKING_TRL": "No",
                "MOTO_TRL": "Yes",
                "TRL_LENGTH": 5.2,
            },
        ],
        _line,
    )


def _nj_statewide_trails_layer():
    """nj_statewide_trails' measured field list and value shapes, 2026-09-09.

    THE POINT OF THIS FIXTURE IS THAT MOST OF THE LAYER KNOWS NOTHING, which
    its own description predicts ("a first iteration and in no way complete",
    compiled as-is from 166 managing agencies). On the live 13,296 rows
    BLAZE_COLOR is 'Unknown' on 7,953 and 'None' on 1,443 - 71% between them
    - and TRAIL_DIFFICULTY is 'Unknown' on 12,483. So the majority of rows
    here carry those values rather than colours, and the two are kept APART
    deliberately: 'Unknown' maps to Unknown ('Blaze not recorded') and 'None'
    to None ('Unblazed'), which is the distinction client/src/lib/blaze.ts
    exists to draw and the reason this layer is worth having as a fixture.

    HIKING's 'U' is the trap and is here: 4,825 live rows read it, so a
    `HIKING == 'Y'` filter would delete a third of the layer - the same
    mistake nh_granit_trails' PED records one state over. What the entry's
    foot_comment specifies as the filter is TRAIL_TYPE, and this fixture
    carries the four shapes that matter: off-road (11,735 live), on-road
    (1,085), sidewalk (50) and water (19, which are paddling trails and not
    walkable at all).

    MANAGING_AGENCY is the field that makes this layer the answer to the
    New Jersey county question - 166 distinct values live, led by Morris
    County Park Commission at 2,489 - so the rows here are attributed to
    three different agencies including the literal 'Unknown' (2,334)."""
    return _features(
        [
            {
                "TRAIL_NAME_SEGMENT": "Fixture County Loop",
                "TRAIL_NAME_LONG": "Fixture Long Distance Trail",
                "BLAZE_COLOR": "Red",
                "BLAZE_DESCRIPTION": "Red disc",
                "TRAIL_TYPE": "off-road",
                "TRAIL_DIFFICULTY": "Easy",
                "HIKING": "Y",
                "MOTORIZED_USE_ALLOWED": "N",
                "PARK_NAME": "Fixture County Reservation",
                "MANAGING_AGENCY": "Fixture County Park Commission",
                "COUNTY": "Fixture",
                "SOURCE_METHOD": "GPS",
                "GIS_SEGMENT_LENGTH_MI": 1.8,
            },
            # The majority shape: the compiling agency recorded no blaze and
            # no difficulty. 'Unknown' is not 'None' and must not become it.
            {
                "TRAIL_NAME_SEGMENT": "Fixture Township Path",
                "BLAZE_COLOR": "Unknown",
                "TRAIL_TYPE": "off-road",
                "TRAIL_DIFFICULTY": "Unknown",
                "HIKING": "U",
                "MOTORIZED_USE_ALLOWED": "U",
                "PARK_NAME": "Fixture Township Open Space",
                "MANAGING_AGENCY": "Unknown",
                "COUNTY": "Fixture",
                "SOURCE_METHOD": "Unknown",
                "GIS_SEGMENT_LENGTH_MI": 0.4,
            },
            # A trail the agency confirms is unblazed - the other half of the
            # distinction above.
            {
                "TRAIL_NAME_SEGMENT": "Fixture Unblazed Connector",
                "BLAZE_COLOR": "None",
                "TRAIL_TYPE": "connector",
                "TRAIL_DIFFICULTY": "Unknown",
                "HIKING": "Y",
                "MOTORIZED_USE_ALLOWED": "N",
                "MANAGING_AGENCY": "State of New Jersey",
                "COUNTY": "Fixture",
                "SOURCE_METHOD": "Digitized from aerials",
                "GIS_SEGMENT_LENGTH_MI": 0.2,
            },
            # Not a trail a hiker walks: on-road, and the sidewalk and water
            # rows below. TRAIL_TYPE is the filter, not HIKING.
            {
                "TRAIL_NAME_SEGMENT": "Fixture Road Route",
                "BLAZE_COLOR": "Unknown",
                "TRAIL_TYPE": "on-road",
                "TRAIL_DIFFICULTY": "Unknown",
                "HIKING": "U",
                "MOTORIZED_USE_ALLOWED": "Y",
                "MANAGING_AGENCY": "Municipal",
                "COUNTY": "Fixture",
                "SOURCE_METHOD": "Unknown",
                "GIS_SEGMENT_LENGTH_MI": 0.9,
            },
            {
                "TRAIL_NAME_SEGMENT": "Fixture River Water Trail",
                "BLAZE_COLOR": "None",
                "TRAIL_TYPE": "water",
                "TRAIL_DIFFICULTY": "Unknown",
                "HIKING": "N",
                "MOTORIZED_USE_ALLOWED": "U",
                "MANAGING_AGENCY": "National Park Service",
                "COUNTY": "Fixture",
                "SOURCE_METHOD": "Digitized from aerials",
                "GIS_SEGMENT_LENGTH_MI": 6.5,
            },
        ],
        _line,
    )


def _nyc_parks_trails_layer():
    """nyc_parks_trails' measured field list and value shapes, 2026-09-15.

    THE POINT OF THIS FIXTURE IS THAT THE BLAZE IS IN THE NAME AND NOTHING
    DECODES IT. This layer has no blaze column: `trailmarkersinstalled` is a
    plain Yes/No (4,017/3,042 on the live 7,059 rows) saying only WHETHER a
    marker exists, while the colour - where there is one - sits inside
    `trail_name` as 'Blue Trail', 'Orange Trail' and so on (1,494 rows across
    five colours). The entry registers `blaze_default: Unknown` rather than
    parsing those strings, so the rows here carry both shapes and a staging
    model that started inferring a colour from the name would have to do it
    in the open.

    HALF THE LAYER HAS NO NAME and that is the majority shape, so it is the
    majority here too: 'Unnamed Official Trail' is 3,448 live rows, with
    'Name TBD' and 'TBD' another 327 between them. A model that assumes
    `trail_name` is a name would pass its tests on a tidier fixture.

    `date_collected` SPANS TWELVE YEARS and the fixture says so, because the
    dataset's own freshness and a segment's survey date are different facts:
    68% of live rows were last surveyed in 2013-2015 while the file itself
    refreshes monthly.
    """
    return _features(
        [
            {
                "park_name": "Fixture Ridge Park",
                "trail_name": "Blue Trail",
                "class": "Class II : Simple/Minor Developed",
                "surface": "Dirt",
                "gen_topog": "Sloped",
                "difficulty": "2: flat terrain, uneven treadway, slight elevation change",
                "width_ft": "2 feet to less than 4 feet",
                "parkid": "X001",
                "trailmarkersinstalled": "Yes",
                "date_collected": "2026-08-18T13:17:48.000",
            },
            # The majority shape: no name, and a marker nobody recorded a
            # colour for. 'Unnamed Official Trail' is not a name.
            {
                "park_name": "Fixture Ridge Park",
                "trail_name": "Unnamed Official Trail",
                "class": "Class III : Developed/Improved",
                "surface": "Wood Chips",
                "gen_topog": "Level",
                "difficulty": "1: flat and smooth",
                "width_ft": "4 feet to less than 6 feet",
                "parkid": "X001",
                "trailmarkersinstalled": "No",
                "date_collected": "2014-06-16T21:28:14.000",
            },
            # A paved city park path, surveyed twelve years ago - the pairing
            # this layer is full of and the reason its age is worth carrying.
            {
                "park_name": "Fixture Central Park",
                "trail_name": "Name TBD",
                "class": "Class V : Fully Developed",
                "surface": "Paved",
                "gen_topog": "Level",
                "difficulty": "1: flat and smooth",
                "width_ft": "Over 8 feet",
                "parkid": "X002",
                "trailmarkersinstalled": "No",
                "date_collected": "2013-10-17T17:47:05.000",
            },
            # A row with no difficulty at all (18 live) - the null branch.
            {
                "park_name": "Fixture Shore Park",
                "trail_name": "Red Trail",
                "class": "Class I : Minimal/Undeveloped",
                "surface": "Sand",
                "gen_topog": "Level",
                "parkid": "X003",
                "trailmarkersinstalled": "Yes",
                "date_collected": "2021-11-16T21:58:49.000",
            },
        ],
        _line,
    )


def _nyc_park_polygons_layer():
    """Two boundaries, and BOTH CARRY THE FIELDS sources.json NAMES.

    The opposite call from `_oprhp_park_polygons_layer`, and the difference is
    the registry rather than a preference: that entry records not one field
    name, so a property here would be an invented schema. This one declares
    `signname` and `gispropnum`, so a fixture without them would describe a
    layer that cannot exist.

    `gispropnum` matters beyond being present. It is the borough-letter
    property number `nyc_drinking_fountains` also carries, which is what makes
    the two layers joinable at all (#1493) - the clip is spatial rather than
    keyed on it, but a fixture that dropped the column would stop a later
    change noticing the join is there.

    The POLYGONS THEMSELVES ARE NOT NEW YORK, and that is `_polygon`'s own
    convention rather than sloppiness: every fixture in this file draws its
    geometry from the same synthetic helpers, so nothing here can be mistaken
    for measured ground truth. What the fixture asserts is the SCHEMA.
    """
    return _features(
        [
            {"signname": "Fixture Park", "gispropnum": "M010"},
            {"signname": "Fixture Playground", "gispropnum": "B123"},
        ],
        _polygon,
    )


def _nyc_cscl_paths_layer():
    """nyc_cscl_paths' measured field list, 2026-09-17.

    EVERY ROW HERE ALREADY PASSES THE FILTER, the same shape the greenway
    fixture above is built on: the registry entry filters at the portal, so a
    row that would be excluded describes a file that cannot exist. What that
    means concretely here is that `status` is '2' (Constructed) on every row,
    and every row is one of the three pedestrian `rw_type` classes NYC's own
    data dictionary names - or the fourth clause's doubly-asserted street.

    ONE ROW PER CLAUSE, because the clauses are what a reader doubts. 6 is
    Path/Trail and is 5,990 of the live 6,498; 7 is StepStreet; 5 is Boardwalk;
    and the last row is the `rw_type='1'` case that only ships because THREE
    columns agree - trafdir NV, no posted speed, no travel lanes. `trafdir='NV'`
    alone is 580 live rows of which 119 carry a posted speed, so a fixture that
    left the speed and lane columns off that row would not exercise the clause
    that matters.
    """
    return _features(
        [
            {
                "stname_label": "FIXTURE BRIDLE PATH",
                "rw_type": "6",
                "status": "2",
                "trafdir": "TW",
                "physicalid": "900001",
                "boroughcode": "1",
            },
            {
                "stname_label": "FIXTURE HILL STEP ST",
                "rw_type": "7",
                "status": "2",
                "trafdir": "NV",
                "physicalid": "900002",
                "boroughcode": "2",
            },
            {
                "stname_label": "FIXTURE BEACH BOARDWALK",
                "rw_type": "5",
                "status": "2",
                "trafdir": "NV",
                "physicalid": "900003",
                "boroughcode": "3",
            },
            # The fourth clause: a STREET that ships only because the city
            # calls it non-vehicular AND posts no speed AND records no travel
            # lanes. Both nulls are written rather than omitted, because their
            # absence is the assertion.
            {
                "stname_label": "FIXTURE PARK PROMENADE",
                "rw_type": "1",
                "status": "2",
                "trafdir": "NV",
                "posted_speed": None,
                "number_travel_lanes": None,
                "physicalid": "900004",
                "boroughcode": "4",
            },
        ],
        _line,
    )


def _nyc_park_drives_layer():
    """nyc_park_drives' measured field list, 2026-09-17.

    THE ONE FIXTURE IN THIS FILE WHOSE ROWS CONTRADICT THEMSELVES, and it is
    faithful rather than sloppy. CSCL still models Central Park's and Prospect
    Park's drives as vehicular streets - the live EAST DR reads trafdir FT with
    posted_speed 20 and one travel lane - because the street file has not caught
    up with their 2018 closure to cars. The entry ships them anyway on the
    maintainer's decision, so the fixture carries the speed limit and the lane
    count rather than quietly cleaning them off; a fixture that dropped them
    would describe a dataset that agrees with us, and none does.

    The geometry is NOT clipped to a park here. `export_nearby_trails`'
    `boundary_source` does that cut against NYC Parks' own polygons at export
    time, and this fixture is what the FETCH writes - which is the portal's
    answer to the name-and-borough filter, leak included.
    """
    return _features(
        [
            {
                "stname_label": "EAST DR",
                "rw_type": "1",
                "status": "2",
                "trafdir": "FT",
                "posted_speed": "20",
                "number_travel_lanes": "1",
                "physicalid": "910001",
                "boroughcode": "1",
            },
            {
                "stname_label": "WEST DR",
                "rw_type": "1",
                "status": "2",
                "trafdir": "TF",
                "posted_speed": "25",
                "number_travel_lanes": "1",
                "physicalid": "910002",
                "boroughcode": "3",
            },
        ],
        _line,
    )


def _nyc_dot_greenways_layer():
    """nyc_dot_greenways' measured field list, 2026-09-15.

    EVERY ROW HERE ALREADY PASSES THE FILTER, and that is the fixture's whole
    shape. The registry entry fetches with a SoQL `where` -
    status='Current' AND grnwy='Greenway' AND onoffst='OFF' - applied at the
    portal, so the 26,656 rows it excludes never reach disk and a fixture
    carrying one would describe a file that cannot exist. The three columns
    are still written on every row because they are in the fetched GeoJSON
    and a staging model can read them.

    `street` IS THE NAME COLUMN and on greenway rows it carries a path's name
    rather than a road's ('BRONX RIVER GREENWAY'), which is why the entry
    registers it as `name_field`. `gwsystem` is the coarser grouping and
    `gwyjuris` the owner - DPR 2,095 of the live current greenway rows
    against DOT's 3,667, so a tenth of this layer is somebody else's ground
    and two of the rows here say so.
    """
    common = {"status": "Current", "grnwy": "Greenway", "onoffst": "OFF"}
    return _features(
        [
            {
                **common,
                "street": "FIXTURE RIVER GREENWAY",
                "gwsystem": "Fixture River",
                "gwyjuris": "DPR",
                "boro": "2",
                "facilitycl": "I",
                "segmentid": "100001",
                "instdate": "2019-06-01T00:00:00.000",
            },
            {
                **common,
                "street": "FIXTURE WATERFRONT ESPLANADE",
                "gwsystem": "Fixture Waterfront",
                "gwyjuris": "DOT",
                "boro": "1",
                "facilitycl": "I",
                "segmentid": "100002",
                "instdate": "2022-09-14T00:00:00.000",
            },
            # Federal ground inside a city layer - Gateway NRA is the live
            # case, 87 rows, and a model keying on "the city owns this"
            # would be wrong about it.
            {
                **common,
                "street": "FIXTURE BAY TRAIL",
                "gwsystem": "Fixture Bay",
                "gwyjuris": "NPS",
                "boro": "4",
                "facilitycl": "I",
                "segmentid": "100003",
            },
            # No system name (the live layer has rows with none) - the null
            # branch for the grouping a screen would most want to use.
            {
                **common,
                "street": "FIXTURE CONNECTOR PATH",
                "gwyjuris": "DOT",
                "boro": "3",
                "facilitycl": "I",
                "segmentid": "100004",
            },
        ],
        _line,
    )


def _nyc_public_restrooms_layer():
    """nyc_public_restrooms' measured field list, 2026-09-15.

    EVERY ROW IS OPERATIONAL, because the registry entry filters at the portal
    (status='Operational', 975 of 1,066) and the 91 it excludes never reach
    disk. The column is still written on every row: it is in the fetched
    GeoJSON, a staging model can read it, and it is the column that makes this
    layer shippable at all - the contrast POI_COVERAGE_SURVEY.md §10 draws
    against the drinking fountains, whose status column says the same thing
    about every row.

    `operator` and `location_type` VARY ON PURPOSE. The maintainer's call of
    2026-09-15 was to ship every operator, so a fixture carrying only NYC
    Parks would describe a narrower file than the one that exists - live:
    NYC Parks 728, NYPL 91, Parks Concessionaire 71, QPL 63, BPL 62, and a
    tail of conservancies and business improvement districts.
    """
    return _features(
        [
            {
                "facility_name": "Fixture Park Comfort Station",
                "location_type": "Park",
                "operator": "NYC Parks",
                "status": "Operational",
                "changing_stations": "Yes",
                "latitude": "40.704410",
                "longitude": "-74.015900",
            },
            {
                "facility_name": "Fixture Branch Library",
                "location_type": "Library",
                "operator": "NYPL",
                "status": "Operational",
                "changing_stations": "No",
                "latitude": "40.752700",
                "longitude": "-73.982300",
            },
        ],
        _point,
    )


def _nyc_drinking_fountains_layer():
    """nyc_drinking_fountains' measured field list, 2026-09-15.

    EVERY ROW PASSES THE ALLOWLIST, for the reason the greenway fixture gives:
    the `where` is applied at the portal, so the 654 excluded rows never reach
    disk and a fixture carrying an `Indoor Drinking Fountain` would describe a
    file that cannot exist.

    `featuresta` READS `Active` ON BOTH ROWS, and that is the fixture being
    accurate rather than lazy. It reads Active on all 3,849 live rows - zero
    variance - which is the whole reason nyc_drinking_fountains carries
    `confidence_floor: low`. A fixture that invented a second value would
    describe a column this source does not have and would make the floor look
    unnecessary to whoever read it next.

    `fountainty` carries a decoded letter on one row and a spelled-out type on
    the other, because the live column mixes both and the allowlist has to
    hold both kinds.
    """
    return _features(
        [
            {
                "fountainty": "A",
                "featuresta": "Active",
                "propertyna": "Fixture Park",
                "gispropnum": "B999",
                "borough": "B",
                "fountainco": "1",
            },
            {
                "fountainty": "Bottle Filler High Low",
                "featuresta": "Active",
                "propertyna": "Fixture Waterfront Park",
                "gispropnum": "M999",
                "borough": "M",
                "fountainco": "2",
            },
        ],
        _point,
    )


def _dec_hiking_trails_layer():
    """dec_hiking_trails' measured field list, 2026-08-25.

    MARKER carries a blank and the 'ORANGE AND RED' value DEC's own domain
    does not declare, both of which sources.json records on the live 5,286
    rows; FOOT carries Y and M, the only two values measured. DEC spells the
    id column GLOBALID where lib/feature_id.py looks for GlobalID, which is
    why the real export falls back to OBJECTID - both columns are here so
    that fact stays visible in the warehouse.
    """
    common = {
        "UNIT": "AFP",
        "FACILITY": "Fixture Wild Forest",
        "PUBLICUSE": "Y",
        "UPDATED": "2026-08-20",
        "HORSE": "N",
        "BIKE": "N",
        "XC": "N",
        "SNOWMB": "N",
        "ATV": "N",
        "MOTORV": "N",
        "ADMIN": "N",
        "ACCESSIBLE": "N",
        "MAPPWD": "Y",
    }
    return _features(
        [
            {
                **common,
                "OBJECTID": 1,
                "GLOBALID": "{dec-trail-1}",
                "NAME": "Fixture Brook Trail",
                "ASSET": "FOOT TRAIL",
                "MILES": 2.1,
                "DESCRIP": "fixture row",
                "MARKER": "Blue",
                "FOOT": "Y",
            },
            {
                **common,
                "OBJECTID": 2,
                "GLOBALID": "{dec-trail-2}",
                "NAME": "Fixture Snowmobile Corridor",
                "ASSET": "SNOWMOBILE TRAIL",
                "MILES": 4.0,
                "DESCRIP": None,
                "MARKER": "",
                "FOOT": "M",
            },
            {
                **common,
                "OBJECTID": 3,
                "GLOBALID": "{dec-trail-3}",
                "NAME": "Fixture Ridge Trail",
                "ASSET": "FOOT TRAIL",
                "MILES": 1.2,
                "DESCRIP": None,
                "MARKER": "ORANGE AND RED",
                "FOOT": "Y",
            },
        ],
        _line,
    )


def _dec_lean_tos_layer():
    """dec_lean_tos' measured field list, 2026-08-27 - the one DEC asset
    service whose whole schema sources.json spells out.

    NO CAPACITY COLUMN, which is the finding rather than an omission here:
    nothing in this layer states how many a shelter sleeps, so nothing
    downstream may. NOTES carries DEC's '-99' null sentinel on some rows and
    PHOTO_LINK points at a drive that resolves only inside DEC; both are
    reproduced so a staging model cannot be written as though they were
    useful. One row reads PUBLICUSE 'N' so the flag has something to say.
    """
    common = {"UNIT": "AFP", "FACILITY": "Fixture Wild Forest", "ASSET": "LEAN-TO", "ACCESSIBLE": "N", "UPDATED": "2026-08-18"}
    return _features(
        [
            {
                **common,
                "OBJECTID": 11,
                "ASSET_UID": 5011,
                "NAME": "Fixture Lean-to",
                "DESCRIP": "fixture row",
                "NOTES": "-99",
                "PHOTO_LINK": "M:\\DLF\\fixture.jpg",
                "PUBLICUSE": "Y",
            },
            {
                **common,
                "OBJECTID": 12,
                "ASSET_UID": 5012,
                "NAME": "Fixture Brook Lean-to",
                "DESCRIP": None,
                "NOTES": None,
                "PHOTO_LINK": None,
                "PUBLICUSE": "Y",
            },
            {
                **common,
                "OBJECTID": 13,
                "ASSET_UID": 5013,
                "NAME": "Fixture Maintenance Lean-to",
                "DESCRIP": None,
                "NOTES": None,
                "PHOTO_LINK": None,
                "PUBLICUSE": "N",
            },
        ],
        _point,
    )


def _dec_asset_layer(asset, names, publicuse=("Y",), asset_uids=None, places=None):
    """The five other DEC per-type asset services.

    Seven columns, and only seven: sources.json records these layers' counts
    and their `id_field`/`name_field`/`asset_field`/`facility_field`/
    `public_field` plus a `freshness` field of UPDATED, and does NOT record a
    full field list the way it does for dec_lean_tos. dec_lean_tos' other
    columns are NOT assumed to carry across - a sibling service is evidence
    about itself, not about its siblings.

    ASSET_UID is the seventh, and the key (decision 40, pipeline/ELT.md "One
    key per table"): measured on all seven DEC point services on 2026-10-01,
    unique on four of them and NOT unique on three. Primitive campsites hold
    four ids that two different sites share, at different places and mostly
    under different names, plus one exact duplicate record; parking areas
    hold one id two lots share. So `asset_uids` and `places` let a fixture
    reuse an id at another place, and repeat a row exactly (same id, same
    place, a new OBJECTID), which are the two shapes the key and the staging
    dedupe must get right. `places[i]` is the index of the point row i sits
    at; by default every row has its own.
    """
    asset_uids = asset_uids or [900 + i for i in range(len(names))]
    places = places or list(range(len(names)))
    return _feature_collection(
        [
            {
                "type": "Feature",
                "properties": {
                    "OBJECTID": 100 + i,
                    "ASSET_UID": asset_uids[i],
                    "NAME": name,
                    "ASSET": asset,
                    "FACILITY": "Fixture Wild Forest",
                    "PUBLICUSE": publicuse[i % len(publicuse)],
                    "UPDATED": "2026-08-18",
                },
                "geometry": _point(places[i]),
            }
            for i, name in enumerate(names)
        ]
    )


def _registered_trail_lines_layer(key: str, name_field: str | None):
    """A trail-line fixture for one of #1778's seventeen registrations.

    ONE BUILDER FOR SEVENTEEN, where every other external layer here has its
    own, and the reason is what these rows are rather than a shortcut. Each of
    the seventeen declares at most ONE column to sources.json - a `name_field`,
    or nothing where the trail's name is the layer (pcta_centerline,
    cdtc_centerline, wi_ice_age_trail, which carry `name_constant` instead).
    `missing_declared_fields` checks exactly the columns an entry declares, so
    a fixture carrying the declared name column and a geometry exercises
    everything the registry claims about these layers. A bespoke builder each
    would be sixteen copies of this one with the column renamed.

    WHAT IT DELIBERATELY DOES NOT REPRODUCE, said because these are real layers
    with real shapes and a reader will look: the live column lists run from 2
    fields (PCTA) to 51 (Washington RCO), and nothing here writes the other
    forty-nine. A fixture that did would be asserting a schema this project has
    not measured column by column - the #1778 probe read counts, CRS and field
    NAMES, never per-column values - and the staging models read the declared
    column and the geometry. When one of these rows grows a `blaze_field` or a
    `status_field`, this fixture grows with it or `missing_declared_fields`
    fails the export, which is the guard working.

    The three with no name column get rows with no name key at all, which is
    their real shape and the one `declared_name`'s `name_constant` branch is
    for.
    """
    rows = []
    for index in range(2):
        row = {"OBJECTID": index + 1}
        if name_field is not None:
            row[name_field] = f"Fixture {key.replace('_', ' ').title()} {index + 1}"
        rows.append(row)
    return _features(rows, _line)


# Each layer's KEY columns, for the base models that key and dedupe it (pipeline/ELT.md, "One key per
# table", decision 40). The NAMES are measured: each is the column ELT.md's key table records as
# unique on the live layer, 2026-10-01, spelled as the upstream spells it. The VALUES are not: they
# are placeholders that keep each row's key distinct, of a type nobody measured, and say so by
# starting with "fixture". Applied after each layer's own builder, so no builder changes shape.
KEY_FIELDS = {
    "external/wa_rco_trails.geojson": {"GlobalID": lambda i: f"{{fixture-wa-rco-{i}}}"},
    "external/ncta_trail.geojson": {"GlobalID": lambda i: f"{{fixture-ncta-{i}}}"},
    "external/azgeo_arizona_trail.geojson": {"GlobalID": lambda i: f"{{fixture-azgeo-{i}}}"},
    "external/tahoe_rim_trail.geojson": {"GlobalID": lambda i: f"{{fixture-tahoe-rim-{i}}}"},
    "external/duluth_superior_hiking_trail.geojson": {"GlobalID": lambda i: f"{{fixture-duluth-{i}}}"},
    "external/massgis_long_distance_trails.geojson": {"GLOBALID": lambda i: f"{{fixture-massgis-{i}}}"},
    "external/njdep_park_trails.geojson": {"GLOBALID": lambda i: f"{{fixture-njdep-{i}}}"},
    "external/nj_statewide_trails.geojson": {"GLOBALID": lambda i: f"{{fixture-nj-statewide-{i}}}"},
    "external/usfs_trails.geojson": {"globalid": lambda i: f"{{fixture-usfs-trail-{i}}}"},
    "external/usfs_rec_sites.geojson": {"globalid": lambda i: f"{{fixture-usfs-site-{i}}}"},
    "external/nps_trails.geojson": {"GEOMETRYID": lambda i: f"{{fixture-nps-{i}}}"},
    "external/utah_sgid_trails.geojson": {"Unique_ID": lambda i: f"fixture-utah-{i}"},
    "external/pasda_dcnr_trails.geojson": {"TRAILID": lambda i: f"fixture-pasda-{i}"},
    "external/cotrex_trails.geojson": {"feature_id": lambda i: f"fixture-cotrex-{i}"},
    "external/ct_deep_blue_blazed.geojson": {"Par_Name": lambda i: f"Fixture Park {i}"},
    "external/nc_mst_trail.geojson": {"TRAILNAME": lambda i: f"Fixture MST Trail {i}"},
    # TrailType is null on 126 of the live 1,595 rows (ELT.md), so one fixture row carries none.
    "external/alaska_trails.geojson": {"TrailType": lambda i: None if i else "fixture-type"},
    "external/cdtc_centerline.geojson": {"STATE": lambda i: f"fixture-state-{i}"},
    "external/blm_trails.geojson": {
        "BLM_MILES": lambda i: 1.5 + i,
        "ROUTE_PLAN_ID": lambda i: f"fixture-plan-{i}",
        "DEF_FET2": lambda i: "fixture-feature",
        "PLAN_SEASON_RSTRCT_CODE": lambda i: "fixture-season",
        "ROUTE_PRMRY_NM": lambda i: f"Fixture BLM Route {i}",
    },
    "external/nyc_drinking_fountains.geojson": {"system": lambda i: f"fixture-system-{i}"},
    # nyc_park_polygons needs no entry: its key, gispropnum, is already in _nyc_park_polygons_layer's
    # rows. It used to get a `system` here, which the live layer does not have (Socrata enfh-gkve
    # declares 33 columns, none of them `system`, read 2026-10-03), so CI passed on a key the
    # monthly lane's first live build could not bind (refresh-reference.yml run 37109384156).
    "external/nyc_cscl_paths.geojson": {"globalid": lambda i: f"{{fixture-cscl-{i}}}"},
    "external/nyc_park_drives.geojson": {"globalid": lambda i: f"{{fixture-drive-{i}}}"},
}


def _with_key_fields(collection: dict, fields: dict) -> dict:
    for index, feature in enumerate(collection["features"]):
        feature["properties"] = {**(feature.get("properties") or {}), **{name: value(index) for name, value in fields.items()}}
    return collection


# --- The points_of_interest family (#1793, stage 3) ------------------------
#
# What the POI family's shadow-run parity needs from these fixtures, added to
# the layers above rather than written into their builders, so no other
# family's rows change:
#
# - THE ID FIELDS export_nearby_poi.py reads. sources.json declares OBJECTID
#   for oprhp_facilities and objectid for usfs_rec_sites, and NYC's Socrata
#   rows are identified by `:id`, which lib/socrata.py moves onto each
#   feature's `id` (extract/_fixtures.py answers a fixture feature's own `id`
#   as that). Without them export_nearby_poi.py cannot run on these files.
# - ATC'S REAL SHELTERS AND CAMPSITES, by GlobalID and name. Their water
#   distances (reference/water_distance.json) and capacities
#   (reference/shelter_capacity.json) are reviewed files in git that fixture
#   mode loads whole, and both join on ATC's GlobalID, so a fixture with real
#   ids is what lets parity hold the real figures, the 42 steward estimates
#   among them, through both pipelines. Their PLACES are invented: a grid
#   (_poi_site_point) inside the fixture centerline's 30-mile corridor, every
#   site at least 300 m from the next, so no two group into a site. 21 sites
#   are left out: the ledger has retired the water point export_poi.py would
#   synthesize at each (`atc_csi:<GlobalID>`), because a real water point
#   folds into each of them on the live corridor, and these fixtures have
#   none to fold.
# - ATC'S INVENTORY COLUMNS, the ones lib/poi_description.py composes a
#   sentence from and lib/atc_notes.py cleans, varied by row (_POI_INVENTORY),
#   on those real shelters and campsites and on vistas, parking areas and
#   privies of their own (_POI_FACILITIES), so the describers' branches run
#   through both pipelines rather than only through unit tests. Each is a
#   value ATC writes on the live layers per the Python's own docstrings; the
#   facilities sit on a grid of their own north of the sites, 400 m apart,
#   inside the corridor and too far from any shelter or campsite to join a
#   site.
# - ONE DEC BACKCOUNTRY PRIVY THAT PUBLISHES. The layer's three rows above
#   are typed PRIVY, which DEC_ASSET_TYPES does not name, so the layer kept
#   nothing and export_nearby_poi.py's completeness gate refused the run; a
#   `PIT PRIVY` row is the layer's commonest real value (356, per the map's
#   own comment).
# - SITE WATER'S TWO INPUTS (PO07, PO17): each site's candidate stream
#   reaches and the EPQS answers, as site_water/candidates.json and
#   site_water/epqs_elevations.json (_site_water_fixtures), which
#   step_site_water.py reads in place of the hydrography and the network, so
#   fetch_trail_water.py's gates run on the grid's own sites in CI.
# - OSM WATER'S POINTS AND ANSWERS (PO03, PO06, PO08, PO09): a dozen points in
#   fetch_osm_water.py's shape and the EPQS answers for their walks
#   (_osm_water_fixtures), which step_osm_water.py and step_osm_water_grade.py
#   read, and one opentrail water waypoint beside a grid site for the dedupe
#   to find a twin of.
# - THE PHOTO MANIFESTS (PO24, PO38): Commons and ATC outcome records and a
#   decisions ledger for grid sites (_poi_photo_fixtures), which
#   step_poi_photos.py lands, reaching every branch of the face gate and the
#   attachment. Labels hashed into digests, never bytes.
# - THE LONG PATH GUIDE'S PAGES (PO36): five section pages and the index in
#   the real skeleton (_long_path_guide_fixtures), which extract/_fixtures.py
#   serves to the guide_pages kind, so the extract's own parser lands them.
POI_REFERENCE_DIR = Path(__file__).parent / "reference"

# Shelter, campsite, vista, parking and privy inventory, one tuple of values
# per row, cycled: every value one of the shapes the Python's tests and
# docstrings name (a code, a free-text near-miss, a blank, an implausible year).
_POI_INVENTORY = {
    "shelters": [
        {"Stories": 2, "Exterior_M": "2", "Chimneys": 1, "Metal_Fir": 1, "Deck_Lengt": 24, "Year_Built": 1915},
        {"Stories": 1, "Exterior_M": "5", "Chimneys": 0, "Metal_Fir": 0, "Deck_Lengt": 0, "Year_Built": 1954},
        {"Stories": 1, "Exterior_M": "10", "Food_Boxe": 1, "Year_Built": 0, "Comments": "Has a loft"},
        {"Stories": 3, "Exterior_M": "12", "Food_Cabl": 2, "Mortared": 1, "Comments": "Not sure about spatial info"},
        {
            "Exterior_M": "6",
            "Food_Pole": 1,
            "Year_Built": 2101,
            "Comments": "Log and mortar exterior. Majority of structure is log. Please see photos.",
        },
        {"Stories": 1, "Year_Built": 1799, "Comments": "GIS CS629-CS635; Shiplap siding"},
        {"Stories": 2, "Exterior_M": "4", "Deck_Lengt": 12, "Comments": "816/15"},
        {"Stories": 1, "Exterior_M": "8", "Year_Built": 2003, "Comments": "Exterior - shiplap ;skylight"},
        {},
    ],
    "campsites": [
        {"Type": "0", "Site_Num": 3, "Food_Boxe": 1},
        {"Type": "1", "Site_Num": 6, "Tent_Pads": 8, "Metal_Fir": 1},
        {"Type": "0", "Site_Num": 3, "Tent_Pads": 1, "Tent_Plat": 6},
        {"Type": "0"},
        {"Type": "1", "Comments": "One group campsite."},
        {"Type": "0", "Site_Num": 1, "Comments": "Not sure about spatial info"},
    ],
}

# The vistas, parking areas and privies, each a full row of its own.
_POI_FACILITIES = {
    "viewpoints.geojson": [
        {"Name": "Fixture Vista East", "Left_Beari": 40, "Right_Bear": 220, "Location": "Mtn/Ridge/Outcrop"},
        {"Name": "Fixture Vista Wolf", "Left_Beari": 280, "Right_Bear": 10},
        {"Name": "Fixture Vista Summit", "Left_Beari": 10, "Right_Bear": 350, "Location": "Summit"},
        {"Name": "Fixture Vista Horizon", "Left_Beari": 90, "Right_Bear": 90},
        {"Name": "Fixture Vista Unsurveyed", "Left_Beari": 0, "Right_Bear": 0, "Location": "Summit; Lookout Tower"},
        {"Name": "Fixture Vista Narrow", "Left_Beari": 90, "Right_Bear": 92, "Location": "TBD"},
        {"Name": "Fixture Vista Eighty", "Left_Beari": 40, "Right_Bear": 120, "Location": "Open Area - Natural"},
        {"Name": "Fixture Vista Sixty", "Left_Beari": 90, "Right_Bear": 152, "Comments": "No view beyond foreground; bald rock"},
        {"Name": "Fixture Vista Note", "Location": "TBD", "Comments": "No view beyond foreground"},
        {"Name": "Fixture Vista Silent", "Location": "Side Trail"},
    ],
    "parking.geojson": [
        {"Name": "Fixture Lot Gravel", "Type": "0", "Surface": "3", "Parking_S": 7, "ADA_Space": 0},
        {"Name": "Fixture Lot One", "Type": "0", "Surface": "3", "Parking_S": 1},
        {"Name": "Fixture Lot Accessible", "Type": "0", "Surface": "0", "Parking_S": 7, "ADA_Space": 2},
        {"Name": "Fixture Shoulder", "Type": "Roadside/Shoulder", "Surface": "3", "Parking_S": 7},
        {"Name": "Fixture Lot Unknown", "Type": "Unknown", "Surface": "Unknown"},
        {"Name": "Fixture Lot Pavers", "Type": "0", "Surface": "2", "Parking_S": 12, "Comments": "Gate locked at dusk."},
    ],
    "privies.geojson": [
        {"Name": "Fixture Privy Moldering", "Type": "1", "Enclosure": "1", "Year_Built": 2003},
        {"Name": "Fixture Privy Multi", "Type": "1", "Enclosure": "2", "Year_Built": 2003},
        {"Name": "Fixture Privy Open", "Type": "3", "Enclosure": "0"},
        {"Name": "Fixture Privy Cool", "Type": "Cool Composting", "Year_Built": 2003},
        {"Name": "Fixture Privy Plain", "Type": "5", "Enclosure": "3"},
        {"Name": "Fixture Privy Vault", "Type": "4", "Enclosure": "1", "Comments": "Please see photos"},
    ],
}


def _poi_site_point(index: int) -> dict:
    return {"type": "Point", "coordinates": [-74.30 + (index % 25) * 0.004, 41.20 + (index // 25) * 0.004]}


# Site water (PO07, PO17): step_site_water.py's two fixture inputs, in place
# of the hydrography and EPQS, which CI may not fetch. Each scenario is a
# shelter or campsite of the grid above, by its place in `kept`, and the
# stream reaches near it: (hydrography, stream id, name, flow, OSM's NHD
# lineage, metres east of the site; a negative number is west), each a reach
# running north and south past the site, so its nearest point is level with
# it. Then the EPQS answers at the site and at each reach's nearest point, in
# feet; a point with no answer is one EPQS would not give. Together they
# reach every branch fetch_trail_water.py's resolve_site() and
# nearest_stream() have: water inside both gates, two hydrographies merged
# within SITE_WATER_MERGE_M and two too far apart to merge, a reach past
# MATCH_RADIUS_FT, a walk steeper than MAX_GRADE, a walk shorter than
# MIN_GRADE_RUN_FT that the grade does not judge, an elevation EPQS would not
# give, every flow class and none. Every other site has no stream near it.
_SITE_WATER_SCENARIOS = [
    # (site index, reaches, site elevation, {reach index: water elevation})
    (0, [("nhd", "fixture-nhd-0", "Fixture Brook", "perennial", None, 20.0)], 1000.0, {0: 995.0}),
    (
        1,
        [
            ("nhd", "fixture-nhd-1", None, "intermittent", None, 20.0),
            ("osm", "fixture-osm-1", "Fixture Run", None, False, 25.0),
        ],
        1200.0,
        {0: 1197.0, 1: 1196.5},
    ),
    (2, [("osm", "fixture-osm-2", "Fixture Spring Run", "intermittent", True, 15.0)], 900.0, {0: 899.0}),
    (3, [("nhd", "fixture-nhd-3", "Fixture Far Brook", "perennial", None, 50.0)], 1000.0, {}),
    (4, [("nhd", "fixture-nhd-4", "Fixture Gorge Brook", "perennial", None, 20.0)], 1000.0, {0: 970.0}),
    (5, [("nhd", "fixture-nhd-5", "Fixture Trickle", "perennial", None, 2.0)], 1000.0, {0: 997.0}),
    (6, [("nhd", "fixture-nhd-6", "Fixture Brook Six", "perennial", None, 20.0)], 1000.0, {}),
    (7, [("nhd", "fixture-nhd-7", "Fixture Creek", None, None, 25.0)], 800.0, {0: 798.0}),
    (
        8,
        [
            ("nhd", "fixture-nhd-8", "Fixture East Brook", "perennial", None, 30.0),
            ("osm", "fixture-osm-8", "Fixture West Brook", None, False, -60.0),
        ],
        700.0,
        {0: 696.0, 1: 690.0},
    ),
    (
        9,
        [
            ("osm", "fixture-osm-9", "Fixture Rill", None, False, 10.0),
            ("nhd", "fixture-nhd-9", None, "ephemeral", None, 12.0),
        ],
        650.0,
        {0: 649.0, 1: 648.8},
    ),
]
#: fetch_trail_water.py's metres in a degree of latitude, which its distances are measured in.
_SITE_WATER_M_PER_DEG_LAT = 111_132.0


def _site_water_fixtures(sites: list[dict]) -> dict[str, str]:
    """site_water/candidates.json and site_water/epqs_elevations.json for these scenarios over `sites`, the grid's sites in order."""
    candidates: dict[str, list[dict]] = {}
    elevations: dict[str, float] = {}
    for index, reaches, site_feet, water_feet in _SITE_WATER_SCENARIOS:
        site = sites[index]
        lon, lat = _poi_site_point(index)["coordinates"]
        metres_per_degree_east = _SITE_WATER_M_PER_DEG_LAT * math.cos(math.radians(lat))
        elevations[f"{lat:.6f},{lon:.6f}"] = site_feet
        for position, (source, stream_id, name, flow, osm_from_nhd, east_m) in enumerate(reaches):
            x = round(lon + east_m / metres_per_degree_east, 6)
            candidates.setdefault(site["atc_global_id"], []).append(
                {
                    "source": source,
                    "stream_id": stream_id,
                    "name": name,
                    "flow": flow,
                    "osm_from_nhd": osm_from_nhd,
                    "paths": [[[x, round(lat - 0.001, 6)], [x, round(lat + 0.001, 6)]]],
                }
            )
            if position in water_feet:
                elevations[f"{lat:.6f},{x:.6f}"] = water_feet[position]
    return {
        "site_water/candidates.json": json.dumps(candidates, indent=1),
        "site_water/epqs_elevations.json": json.dumps(elevations, indent=1),
    }


# OSM water (PO03, PO06, PO08, PO09): step_osm_water.py's points, in
# fetch_osm_water.py's feature() shape, and the EPQS answers
# step_osm_water_grade.py reads in place of the network, keyed "lat,lon" at
# 6 dp as fetch_trail_water.py's cache keys them. They live under osm_water/
# rather than at data/raw/osm_water.geojson, where export_poi.py would read
# them and then refuse to run without build_osm_water_reach.py's verdicts.
#
# Each point is placed so the far end of its walk is a vertex or a site,
# which ST_ClosestPoint returns exactly, so its answer has a key: past the
# south end of the centerline's first segment, (-74.0, 41.0); past the far end
# of the "Viewpoint Spur" side trail, (-74.004, 41.006); past the south end of
# the Long Path's first piece in the fixture network, (-74.3, 41.5); or north
# of a shelter or campsite of the grid above. Together they reach every
# branch of build_osm_water_reach.py's gate and export_poi.py's handling:
# reachable from the centerline, a site and another organization's trail
# (which withholds the mile); past MATCH_RADIUS_FT; nothing within the 5-mile
# ceiling; outside the corridor; steeper than MAX_GRADE; a walk shorter than
# MIN_GRADE_RUN_FT the grade does not judge; an elevation EPQS would not
# give; no geometry; and a twin of an opentrail water point within
# WATER_DEDUP_RADIUS_M beside a neighbour that is not one. The tags vary so
# describe_water()'s clauses all compose.
_OSM_WATER_TWIN_DBID = 9001


def _osm_water_fixtures(kept: list[dict]) -> tuple[dict[str, dict | str], dict]:
    """osm_water/points.geojson and osm_water/epqs_elevations.json over the grid's sites, and the opentrail waypoint the twin pairs with."""

    def site(layer: str, nth: int) -> tuple[float, float]:
        """The nth site of a layer past the ten the site water scenarios use."""
        indices = [index for index, row in enumerate(kept) if row["layer"] == layer and index >= len(_SITE_WATER_SCENARIOS)]
        lon, lat = _poi_site_point(indices[nth])["coordinates"]
        return lon, lat

    def key(lon: float, lat: float) -> str:
        return f"{lat:.6f},{lon:.6f}"

    shelter = site("shelters", 20)
    campsite = site("campsites", 20)
    twin_site = site("campsites", 30)
    no_answer_site = site("shelters", 30)
    features, elevations = [], {}

    def point(osm_id, kind, coordinates, water_feet=None, walk=None, walk_feet=None, **tags):
        features.append(
            {
                "type": "Feature",
                "geometry": None if coordinates is None else {"type": "Point", "coordinates": list(coordinates)},
                "properties": {"osm_id": osm_id, "kind": kind, **tags},
            }
        )
        if water_feet is not None:
            elevations[key(*coordinates)] = water_feet
        if walk_feet is not None:
            elevations[key(*walk)] = walk_feet

    # Reachable from the centerline: 22 m south of its first vertex, 2 ft of rise.
    point("9100000001", "spring", (-74.0, 40.9998), 1000.0, (-74.0, 41.0), 1002.0, name="Fixture Spring", intermittent="yes")
    # Reachable from a shelter, tagged not drinking water.
    lon, lat = shelter
    point("9100000002", "water_tap", (lon, round(lat + 0.0002, 6)), 1500.0, shelter, 1503.0, drinking_water="no")
    # Past the side trail's far end, 20 ft below it over about 91 ft: too steep.
    point("9100000003", "water_tap", (-74.0042, 41.0062), 980.0, (-74.004, 41.006), 1000.0)
    # Reachable only from the Long Path, so it carries no A.T. mile.
    point(
        "9100000004",
        "spring",
        (-74.3, 41.4998),
        1200.0,
        (-74.3, 41.5),
        1201.0,
        name="Fixture Long Path Spring",
        intermittent="yes",
        seasonal="yes",
    )
    # About 59 m east of the centerline: past the 100 ft gate.
    point("9100000005", "drinking_water", (-73.9993, 41.0025))
    # In the corridor, and more than 5 miles from anything a hiker walks.
    point("9100000006", "water_well", (-74.0, 41.3))
    # Outside the corridor and every network line's ring: clipped before it is judged.
    point("9100000007", "spring", (-80.0, 35.5))
    # A walk of about 7 ft, too short for the grade to judge.
    lon, lat = campsite
    point("9100000008", "spring", (lon, round(lat + 0.00002, 6)), 997.0, campsite, 1000.0, seasonal="yes")
    # EPQS gives the shelter's elevation and not the water's.
    lon, lat = no_answer_site
    point("9100000009", "spring", (lon, round(lat + 0.0002, 6)), None, no_answer_site, 1100.0)
    # No geometry: skipped, as export_poi.py's has_geometry() skips it.
    point("9100000010", "spring", None, name="Fixture Spring With No Point")
    # Beside an opentrail water point: 11 m from it, a twin; 37 m from it, not.
    lon, lat = twin_site
    point("9100000011", "spring", (lon, round(lat + 0.00015, 6)), 1300.0, twin_site, 1301.0)
    point("9100000012", "drinking_water", (round(lon + 0.0003, 6), lat), 1300.5, twin_site, 1301.0, name="Fixture Fountain")
    waypoint = {
        "type": "Feature",
        "properties": {"dbid": _OSM_WATER_TWIN_DBID, "title": "Fixture Spring Waypoint", "icon": "w"},
        "geometry": {"type": "Point", "coordinates": [lon, round(lat + 0.00025, 6)]},
    }
    files = {
        "osm_water/points.geojson": _feature_collection(features),
        "osm_water/epqs_elevations.json": json.dumps(elevations, indent=1),
    }
    return files, waypoint


# Photos (PO24, PO38): the two outcome files export_poi.py attaches photos
# from, in the shapes their fetchers write them (fetch_poi_images.py's one
# `photo` per POI, fetch_atc_photos.py's `photos` list), and a decisions
# ledger in reference/photo_screen_decisions.json's shape. They live under
# poi_photos/ rather than at data/raw/poi_images.json, where export_poi.py
# reads them, so a run picks them up only when told to (step_poi_photos.py
# under build_marts.py --fixtures, parity.py's old side); and not under
# photos/, which is the fetchers' cache of the bytes. The digests name no
# bytes anywhere: they are sha256 of a label, so nothing here is a picture of
# anybody. Each POI is a grid site the scenario names; together they reach
# every branch of gate_photos() and attach_photos().
def _poi_photo_fixtures(kept: list[dict]) -> dict[str, str]:
    """poi_photos/poi_images.json, poi_photos/poi_images_atc.json and poi_photos/photo_screen_decisions.json over the grid's sites."""
    import hashlib

    def poi_id(layer: str, nth: int) -> str:
        sites = [site for site in kept if site["layer"] == layer]
        return f"atc_{layer}:{sites[nth]['atc_global_id']}"

    def digest(label: str) -> str:
        return hashlib.sha256(f"fixture-photo-{label}".encode()).hexdigest()

    # A field overridden with `...` is left out of the record, as a fetcher leaves out what it never wrote.
    def commons(label: str, faces: object = 0, **override) -> dict:
        photo = {
            "title": f"File:Fixture {label}.jpg",
            "dist": 42.0,
            "url": f"https://upload.wikimedia.org/fixture/{label}.jpg",
            "page_url": f"https://commons.wikimedia.org/wiki/File:Fixture_{label}.jpg",
            "author": f"Fixture Photographer {label}",
            "license": "CC BY-SA 4.0",
            "taken": "2024-06-01",
            "digest": digest(label),
            "screen": {"faces": faces, "screener": "haar_frontalface_default", "on": "2026-08-20"},
        }
        photo.update(override)
        return {k: v for k, v in photo.items() if v is not ...}

    def atc(label: str, **override) -> dict:
        photo = {
            "page_url": f"https://atc.fixture/photos/{label}",
            "author": "Appalachian Trail Conservancy",
            "license": "ATC facility inventory",
            "taken": "2023-09-15",
            "digest": digest(label),
        }
        photo.update(override)
        return {k: v for k, v in photo.items() if v is not ...}

    def found(photo=None, photos=None) -> dict:
        record = {"status": "found", "checked": "2026-09-01"}
        if photo is not None:
            record["photo"] = photo
        if photos is not None:
            record["photos"] = photos
        return record

    shelter = [poi_id("shelters", 40 + n) for n in range(10)]
    campsite = [poi_id("campsites", 40 + n) for n in range(2)]
    commons_pois = {
        shelter[0]: found(commons("screened-clear")),
        shelter[1]: found(commons("flagged-undecided", faces=2)),
        shelter[2]: found(commons("flagged-cleared", faces=1)),
        shelter[3]: found(commons("refused")),
        shelter[4]: found(commons("unscreened", screen=...)),
        shelter[5]: found(commons("undecodable", faces=None)),
        shelter[6]: found(commons("no-digest", digest=...)),
        shelter[7]: found(commons("overruled-by-atc")),
        shelter[9]: found(commons("beside-digestless-atc")),
        campsite[0]: {"status": "none", "checked": "2026-09-01"},
        "atc_shelters:fixture-not-published": found(commons("orphan")),
        "osm_water:9100000001": found(commons("spring")),
    }
    atc_pois = {
        shelter[7]: found(photos=[atc("gallery-1"), atc("gallery-2", author=None)]),
        shelter[8]: found(photos=[atc("no-digest-first", digest=...), atc("second-is-the-card")]),
        shelter[9]: found(photos=[atc("digestless", digest=...)]),
        # ATC's own shoot is not gated: a screen or a refusal on its digest changes nothing.
        campsite[1]: found(photos=[{**atc("atc-with-a-face"), "screen": {"faces": 3}}]),
    }
    decisions = {
        digest("flagged-cleared"): {"decision": "cleared", "on": "2026-08-21"},
        digest("refused"): {"decision": "refused", "on": "2026-08-21"},
        digest("atc-with-a-face"): {"decision": "refused", "on": "2026-08-21"},
    }
    return {
        "poi_photos/poi_images.json": json.dumps({"pois": commons_pois}, indent=1),
        "poi_photos/poi_images_atc.json": json.dumps({"pois": atc_pois}, indent=1),
        "poi_photos/photo_screen_decisions.json": json.dumps(
            {
                "_README": "make_dbt_fixtures.py's decisions, in reference/photo_screen_decisions.json's shape.",
                "decisions": decisions,
            },
            indent=1,
        ),
    }


# The Long Path guide (PO36): NYNJTC's section pages in their real skeleton
# (tests/test_nynjtc_long_path_guide.py's page builder, measured 2026-09-08:
# WordPress <details><summary> blocks, entries as <strong>MILE</strong> on
# <br> boundaries), which extract/_fixtures.py serves to the guide_pages
# kind at the URLs it asks for, from guide_pages/<key>/pages.json. The
# sections sit on the fixture Long Path layer's own LP_Section lines (1: the
# 0.35 mile line beside the centerline, 3 and 4: the 20 mile lines at -74.3),
# and their entries reach build_records()' branches: NYNJTC's coordinates and
# a typo outside the trail's extent, interpolated springs, a lookout, a privy
# and a lean-to with water, an off-trail spring, the season that is not
# water, a camping area that is no pin, an unlocated campsite, a mile past
# the section's end, a section with no distance and one with no line, and
# the same lean-to, lot and campsite said twice.
_GUIDE_URL = "https://www.nynjtc.org/long-path-end-to-end-section-guide/"


def _long_path_guide_fixtures() -> dict[str, str]:
    """guide_pages/nynjtc_long_path_guide/: the index, five section pages, and pages.json mapping each URL to its file."""

    def entries(items):
        return (
            '<p class="wp-block-paragraph">'
            + "<br>".join(f"<strong>{mile}</strong>&nbsp; {text}" for mile, text in items)
            + "</p>"
        )

    def block(name, inner):
        return f'<details class="wp-block-details"><summary>{name}</summary>{inner}</details>'

    def page(number, title, distance, parking, camping, description):
        header = (
            f"<strong>Distance:</strong> {distance} miles<br>" if distance else ""
        ) + "<strong>Parks:</strong> Fixture State Park"
        return (
            "<html><body><header>site chrome</header>"
            '<main id="wp--skip-link--target">'
            f'<h1 class="wp-block-heading"><a href="/ldt-long-path">The Long Path</a> &#8211; Section {number}</h1>'
            f"<h2><strong>{title}</strong></h2>"
            f'<p class="wp-block-paragraph">{header}</p>'
            f"{block('Access', '<p>Take the fixture road to the fixture lot.</p>')}"
            f"{block('Parking', parking)}"
            f"{block('Camping', camping)}"
            f"{block('Detailed Trail Description', description)}"
            "</main><footer>Privacy Policy</footer></body></html>"
        )

    none = "<p>None.<br></p>"
    pages = {
        1: page(
            1,
            "Fixture Park to Fixture Ridge",
            "0.4",
            entries(
                [
                    ("0.00", "Fixture Park lot, at the trailhead (41.00010°, -74.00020°)."),
                    ("0.20", "Roadside pull-off (14.00000°, -74.00000°)."),
                    ("0.40", "Ridge Road lot (41.00495°, -74.00002°)."),
                ]
            ),
            none,
            entries(
                [
                    ("0.00", "Start at the park gate and follow the aqua blazes north."),
                    ("0.10", "Pass a spring, a dependable source of water, on the left."),
                    ("0.25", "Reach Fixture Lookout, with a tremendous view to the east."),
                    ("0.30", "A seasonal spring is 0.2 mile from the Long Path on a side path."),
                    ("0.38", "The trail passes a privy beside the road."),
                    ("0.90", "Reach a lean-to well past the end of the section."),
                ]
            ),
        ),
        3: page(
            3,
            "Fixture Hollow",
            "20.7",
            entries(
                [("0.00", "Section 3 trailhead lot (41.50000°, -74.30010°)."), ("20.70", "Boundary lot (41.80000°, -74.30010°).")]
            ),
            entries(
                [
                    ("5.13", "Fixture Hollow Lean-to, with a spring nearby."),
                    ("8.00", "Camping is allowed in the state forest between mile 8.0 and 9.0."),
                    ("10.00", "A campsite by the brook (unlocated)."),
                ]
            ),
            entries(
                [
                    ("0.00", "Leave the lot and climb north."),
                    ("5.10", "Arrive at Fixture Hollow Lean-to."),
                    ("12.00", "In the spring, the hobblebush puts on a spectacular show."),
                    ("15.00", "A sign marks the way to Fixture Spring, the only reliable water in this section."),
                ]
            ),
        ),
        4: page(
            4,
            "Fixture Hollow to Fixture Notch",
            "20.7",
            entries([("0.00", "Boundary lot (41.80003°, -74.30012°).")]),
            none,
            entries(
                [
                    ("0.00", "Continue north from the lot."),
                    ("3.00", "Reach a campsite on the left."),
                    ("3.02", "The campsite is near the trail."),
                ]
            ),
        ),
        5: page(5, "Fixture Notch", None, none, none, entries([("2.00", "Pass a spring at the notch.")])),
        6: page(
            6,
            "Beyond the Fixture Layer",
            "4.0",
            entries([("0.00", "Far lot (42.50000°, -74.50000°).")]),
            none,
            entries([("1.00", "Pass a spring beside the trail.")]),
        ),
    }
    index = (
        "<html><body><main><h1>Long Path End-to-End Section Guide</h1>"
        + "".join(f'<p><a href="/lp-section-{number}/">Section {number}</a></p>' for number in pages)
        + "</main></body></html>"
    )
    folder = "guide_pages/nynjtc_long_path_guide"
    files = {f"{folder}/index.html": index}
    urls = {_GUIDE_URL: "index.html"}
    for number, markup in pages.items():
        files[f"{folder}/lp-section-{number}.html"] = markup
        urls[f"https://www.nynjtc.org/lp-section-{number}/"] = f"lp-section-{number}.html"
    files[f"{folder}/pages.json"] = json.dumps(urls, indent=1)
    return files


# The two ends of reference/highlights.json's first highlight, by ATC's real
# GlobalIDs and the names the identity ledger records for them, so
# highlights.json publishes one record on these fixtures and its parity line
# compares it. Every other highlight drops, as it does today, because its ends
# are not here. The places are invented: beside the fixture centerline's two
# segments, so the two ends take different miles (the facilities grid above
# all projects onto one mile, and a leg whose ends share a mile drops).
_HIGHLIGHT_END_LAYERS = {"atc_parking": "parking.geojson", "atc_viewpoints": "viewpoints.geojson"}
_HIGHLIGHT_END_POINTS = ([-74.0005, 41.001], [-73.9905, 41.014])


def _highlight_end_fixtures(files: dict) -> dict:
    highlight = json.loads((POI_REFERENCE_DIR / "highlights.json").read_text(encoding="utf-8"))["highlights"][0]
    ledger = json.loads((POI_REFERENCE_DIR / "poi_identity.json").read_text(encoding="utf-8"))["pois"]
    (leg,) = highlight["legs"]
    changed = {}
    for poi_id, point in zip((leg["from_poi"], leg["to_poi"]), _HIGHLIGHT_END_POINTS, strict=True):
        row = ledger[poi_id]
        name = _HIGHLIGHT_END_LAYERS[row["source"]]
        collection = changed.get(name, files[name])
        collection["features"].append(
            {
                "type": "Feature",
                "properties": {"GlobalID": row["source_feature_id"], "Name": row["name"]},
                "geometry": {"type": "Point", "coordinates": point},
            }
        )
        changed[name] = collection
    return changed


def _points_of_interest_fixtures(files: dict) -> dict:
    """The POI family's additions to `files`: id fields, ATC's real shelters and campsites with inventory, facilities, a DEC privy, site and OSM water's inputs, photo manifests, the Long Path guide's pages."""
    files = dict(files)
    id_fields = {
        "external/oprhp_facilities.geojson": ("OBJECTID", lambda i: 5501 + i),
        "external/usfs_rec_sites.geojson": ("objectid", lambda i: 3388401 + i),
    }
    for name, (field, value) in id_fields.items():
        for index, feature in enumerate(files[name]["features"]):
            feature["properties"][field] = value(index)
    for name, prefix in (
        ("external/nyc_public_restrooms.geojson", "row-fixture-restroom"),
        ("external/nyc_drinking_fountains.geojson", "row-fixture-fountain"),
    ):
        for index, feature in enumerate(files[name]["features"]):
            feature["id"] = f"{prefix}-{index}"

    sites = json.loads((POI_REFERENCE_DIR / "water_distance.json").read_text(encoding="utf-8"))["sites"]
    pois = json.loads((POI_REFERENCE_DIR / "poi_identity.json").read_text(encoding="utf-8"))["pois"]
    retired_water = {row["source_feature_id"] for row in pois.values() if row["source"] == "atc_csi" and "retired" in row}
    kept = sorted(
        (site for site in sites if site["atc_global_id"] not in retired_water),
        key=lambda site: (site["layer"], site["atc_global_id"]),
    )
    for name, layer in (("shelters.geojson", "shelters"), ("campsites.geojson", "campsites")):
        collection = files[name]
        inventory = _POI_INVENTORY[layer]
        appended = 0
        for index, site in enumerate(kept):
            if site["layer"] == layer:
                collection["features"].append(
                    {
                        "type": "Feature",
                        "properties": {
                            "GlobalID": site["atc_global_id"],
                            "Name": site["atc_name"],
                            **inventory[appended % len(inventory)],
                        },
                        "geometry": _poi_site_point(index),
                    }
                )
                appended += 1
    files.update(_site_water_fixtures(kept))
    osm_water, waypoint = _osm_water_fixtures(kept)
    files.update(osm_water)
    files.update(_poi_photo_fixtures(kept))
    files.update(_long_path_guide_fixtures())
    files["opentrail_at.geojson"]["features"].append(waypoint)

    for row, (name, facilities) in enumerate(_POI_FACILITIES.items()):
        collection = files[name]
        stem = name.removesuffix(".geojson")
        for index, properties in enumerate(facilities):
            collection["features"].append(
                {
                    "type": "Feature",
                    "properties": {"GlobalID": f"fixture-{stem}-{index}", **properties},
                    "geometry": {"type": "Point", "coordinates": [-74.30 + index * 0.005, 41.30 + row * 0.004]},
                }
            )
    files.update(_highlight_end_fixtures(files))

    files["external/dec_backcountry_features.geojson"]["features"].append(
        {
            "type": "Feature",
            "properties": {
                "OBJECTID": 103,
                "ASSET_UID": 228017,
                "NAME": "Fixture Pit Privy",
                "ASSET": "PIT PRIVY",
                "FACILITY": "Fixture Wild Forest",
                "PUBLICUSE": "Y",
                "UPDATED": "2026-08-18",
            },
            "geometry": _point(3),
        }
    )
    return files


# --------------------------------------------------------------------------
# The closures and warnings family (#1793, stage 3): the hourly lane's three
# upstreams that are not layer files. extract/_fixtures.py serves each the way
# its upstream answers: NWS's /alerts/active body, NYNJTC's WordPress routes,
# and the rows OurHike's Postgres returns for each of export_conditions.py's
# queries. The FIELD NAMES are measured: NWS's are the 30 properties
# extract/_kinds.py's NWS_TEXT_PROPERTIES and NWS_JSON_PROPERTIES list (read
# off 353 live alerts, 2026-10-01); NYNJTC's post fields and its place terms'
# ids, names and slugs were read from its REST API on 2026-10-02; the Postgres
# columns are the queries' own select lists. The VALUES are synthetic, chosen
# so each branch the closures and warnings models take has a row: a Cancel and
# a Test message NWS lands and the relay drops, an alert placed by polygon and
# one by zone, null `ends` and `instruction`; NYNJTC titles carrying the two
# entities measured on its live 18 (`&#8211;` twice, `&amp;` once) and a tag
# inside a title; closures of each status; reports of both severities.


def _nws_alert(number: int, event: str, status: str, message_type: str, geometry=None, **properties) -> dict:
    alert_id = f"urn:oid:2.49.0.1.840.0.fixture.{number}"
    return {
        "id": f"https://api.weather.gov/alerts/{alert_id}",
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "@id": f"https://api.weather.gov/alerts/{alert_id}",
            "@type": "wx:Alert",
            "id": alert_id,
            "areaDesc": "Rockland, NY; Orange, NY",
            "geocode": {"SAME": ["036087", "036071"], "UGC": ["NYZ069", "NYZ067"]},
            "affectedZones": [
                "https://api.weather.gov/zones/forecast/NYZ069",
                "https://api.weather.gov/zones/forecast/NYZ067",
            ],
            "references": [],
            "sent": "2026-10-01T15:22:00-04:00",
            "effective": "2026-10-01T15:22:00-04:00",
            "onset": "2026-10-01T15:22:00-04:00",
            "expires": "2026-10-01T16:15:00-04:00",
            "ends": "2026-10-01T16:15:00-04:00",
            "status": status,
            "messageType": message_type,
            "category": "Met",
            "severity": "Severe",
            "certainty": "Observed",
            "urgency": "Immediate",
            "event": event,
            "sender": "w-nws.webmaster@noaa.gov",
            "senderName": "NWS Upton NY",
            "headline": f"{event} issued October 1 at 3:22PM EDT by NWS Upton NY",
            "description": f"Fixture {event.lower()}.\n\n* WHAT...Fixture text, relayed as written.",
            "instruction": "Fixture instruction.",
            "response": "Shelter",
            "parameters": {"NWSheadline": [f"FIXTURE {event.upper()}"]},
            "scope": "Public",
            "code": "IPAWSv1.0",
            "language": "en-US",
            "web": "http://www.weather.gov",
            "eventCode": {"SAME": ["SVR"], "NationalWeatherService": ["SVW"]},
            **properties,
        },
    }


def _nws_alerts() -> dict:
    """/alerts/active's body: five alerts the relay keeps and the two kinds it drops.

    Of the five, conditions/weather_alerts.json places three on a trail square,
    one by its polygon and two by their zones, and leaves out two: one whose
    zones reach no trail square, and one drawn where no trail square is.
    """
    storm_cell = {
        "type": "Polygon",
        "coordinates": [[[-74.12, 41.20], [-74.02, 41.20], [-74.02, 41.30], [-74.12, 41.30], [-74.12, 41.20]]],
    }
    return {
        "type": "FeatureCollection",
        "updated": "2026-10-01T19:30:00+00:00",
        "features": [
            _nws_alert(1, "Severe Thunderstorm Warning", "Actual", "Alert", storm_cell),
            # Placed by zone: no polygon, and NWS gave it no end and no instruction.
            _nws_alert(2, "Flood Watch", "Actual", "Update", None, ends=None, instruction=None, severity="Moderate"),
            # Dropped by the relay (WN01): a cancellation, and a message that is not Actual.
            _nws_alert(3, "Severe Thunderstorm Warning", "Actual", "Cancel", storm_cell),
            _nws_alert(4, "Tornado Warning", "Test", "Alert", storm_cell),
            # Null where NWS sends null: no headline, no onset.
            _nws_alert(5, "Special Weather Statement", "Actual", "Alert", None, headline=None, onset=None, ends=None),
            # Placed by zone (WN03), on none: a zone the pinned files never heard of, which
            # conditions/weather_alerts.json reports, and a marine zone, in no state, which it does not.
            _nws_alert(
                6,
                "Flood Warning",
                "Actual",
                "Alert",
                None,
                affectedZones=["https://api.weather.gov/zones/forecast/NYZ999", "https://api.weather.gov/zones/forecast/ANZ335"],
            ),
            # Drawn far from any trail square, while the zones it lists (the default two) reach
            # several: a polygon is an alert's whole placement, so it reaches none (WN03).
            _nws_alert(
                7,
                "Flash Flood Warning",
                "Actual",
                "Alert",
                {"type": "Polygon", "coordinates": [[[-77.5, 39.0], [-77.0, 39.0], [-77.0, 39.3], [-77.5, 39.3], [-77.5, 39.0]]]},
            ),
        ],
    }


# The NBM weather squares build_weather_squares.py writes as squares.json, for
# the A.T. through Harriman, where the alerts above sit (WN03). The SQUARES are
# real: the squares lib/nbm_grid.py puts six points on the trail in, Bear
# Mountain's published waypoint (712, 2007) among them, filled into cells by
# build_weather_squares.py's own squares_by_cell() (computed 2026-10-02;
# tests/test_dbt_conditions_parity.py holds them to it). The zone files are
# the ones that script pins. Which zone overlaps which square is synthetic,
# shaped like the real Rockland and Orange zones, because only NWS's
# shapefiles can say, and they are not fixtures.
WEATHER_SQUARE_POINTS = {
    "Arden": ((-74.15, 41.19), (718, 2002)),
    "Fingerboard Mountain": ((-74.10, 41.22), (717, 2003)),
    "Island Pond": ((-74.06, 41.24), (716, 2005)),
    "Black Mountain": ((-74.03, 41.27), (714, 2006)),
    "West Mountain": ((-73.99, 41.29), (713, 2007)),
    "Bear Mountain (published waypoint)": ((-73.9884, 41.3120), (712, 2007)),
}


def _weather_squares() -> dict:
    """squares.json, in build_weather_squares.py's schema 4, for the squares above."""
    rockland = [[712, 2007], [713, 2007], [714, 2006], [716, 2005]]
    orange = [[717, 2003], [718, 2002]]
    return {
        "schema": 4,
        "environment": "fixture",
        "release": "2026-09-25",
        "built_at": "2026-10-02T00:00:00Z",
        "grid": {
            "proj4": "+proj=lcc +lat_0=25 +lon_0=-95 +lat_1=25 +lat_2=25 +x_0=0 +y_0=0 +R=6371200 +units=m +no_defs",
            "origin": [-3272421.4573371694, 3790842.106035436],
            "square_m": 2539.703,
        },
        "cells": {"n41w074": [[712, 2007], [713, 2007]], "n41w075": [[714, 2006], [716, 2005], [717, 2003], [718, 2002]]},
        "borrowed": [],
        "water_kept": [],
        "outside_grid": [],
        "zone_files": {"forecast": "z_16ap26.zip", "fire": "fz16ap26.zip", "county": "c_16ap26.zip"},
        "zones": {
            "forecast/NYZ069": rockland,
            "forecast/NYZ067": orange,
            "county/NYC087": rockland,
            "county/NYC071": orange,
            # The same id as a forecast zone, a different outline (export_weather_alerts.py's zone_keys()).
            "fire/NYZ069": [[716, 2005]],
        },
        "known_zones": {
            "forecast": ["NYZ067", "NYZ068", "NYZ069", "NYZ070"],
            "fire": ["NYZ067", "NYZ069"],
            "county": ["NYC071", "NYC087"],
        },
    }


# NYNJTC's place terms as its REST API served them on 2026-10-02: real ids,
# names and slugs, one region name carrying `&amp;` as the live one does.
NYNJTC_TERMS = {
    "trail": [
        {"id": 40, "name": "Appalachian Trail", "slug": "appalachian-trail", "count": 9},
        {"id": 68, "name": "Ramapo-Dunderberg Trail", "slug": "ramapo-dunderberg-trail", "count": 1},
    ],
    "park": [
        {"id": 213, "name": "Harriman-Bear Mountain State Parks", "slug": "harriman-bear-mountain-state-parks", "count": 5},
        {"id": 210, "name": "Mount Beacon Park", "slug": "mount-beacon-park", "count": 0},
    ],
    "region": [
        {"id": 284, "name": "Harriman-Bear Mountain", "slug": "harriman-bear-mountain", "count": 4},
        {"id": 282, "name": "Delaware Water Gap &amp; Kittatinny", "slug": "delaware-water-gap-kittatinny", "count": 3},
    ],
    "state": [
        {"id": 66, "name": "New York", "slug": "new-york", "count": 16},
        {"id": 67, "name": "New Jersey", "slug": "new-jersey", "count": 15},
    ],
}


def _nynjtc_post(post_id: int, slug: str, title: str, modified: str, **tags) -> dict:
    """One post as the posts route serves it, with the fields WordPress adds that the extract drops (WP_DROPPED)."""
    return {
        "id": post_id,
        "date": "2026-03-01T09:00:00",
        "date_gmt": "2026-03-01T14:00:00",
        "guid": {"rendered": f"https://www.nynjtc.org/?p={post_id}"},
        "modified": modified,
        "modified_gmt": "2026-04-20T22:38:04",
        "slug": slug,
        "status": "publish",
        "type": "post",
        "link": f"https://www.nynjtc.org/trail-alerts/{slug}/",
        "title": {"rendered": title},
        "content": {"rendered": "<p>Fixture body text, which never reaches a phone.</p>", "protected": False},
        "excerpt": {"rendered": "<p>Fixture excerpt.</p>", "protected": False},
        "author": 9,
        "featured_media": 0,
        "comment_status": "closed",
        "ping_status": "open",
        "sticky": False,
        "template": "",
        "format": "standard",
        "meta": {"_acf_changed": False, "footnotes": ""},
        "categories": [6],
        "tags": [],
        "trail": tags.get("trail", []),
        "park": tags.get("park", []),
        "region": tags.get("region", []),
        "state": tags.get("state", []),
        "class_list": [f"post-{post_id}", "post"],
        "yoast_head": "<meta name='author' content='Fixture Person'>",
        "yoast_head_json": {"author": "Fixture Person"},
        "_links": {"self": [{"href": f"https://www.nynjtc.org/wp-json/wp/v2/posts/{post_id}"}]},
    }


def _nynjtc_trail_alerts() -> dict:
    """The category lookup, the Trail Alerts posts and the four place taxonomies, as nynjtc.org's REST API answers them."""
    return {
        "categories": [{"id": 6, "slug": "trail-alerts"}],
        "posts": [
            _nynjtc_post(
                9001,
                "fixture-detour-in-harriman",
                "Fixture Detour &#8211; Harriman",
                "2026-04-20T18:38:04",
                trail=[40, 68],
                park=[213],
                region=[284],
                state=[66],
            ),
            _nynjtc_post(
                9002,
                "fixture-closures-and-advisories",
                "Fixture Closures &amp; Advisories (Updated: 11/21/25)",
                "2026-05-04T10:25:39",
                park=[213, 210],
            ),
            # A literal en dash, as one live title carries, a tag inside the title, and no place tags at all.
            _nynjtc_post(
                9003, "fixture-reroute-in-progress", "<em>Fixture</em> Reroute in Progress – March", "2025-06-24T15:33:28"
            ),
            # A region whose name carries an entity, and a term id the vocabulary does not hold (dropped, not faked).
            _nynjtc_post(
                9004,
                "fixture-winter-closures",
                "Fixture Winter Closures",
                "2025-12-15T11:12:19",
                region=[282, 999],
                state=[67, 66],
            ),
        ],
        "terms": NYNJTC_TERMS,
    }


def _ourhike_postgres() -> dict:
    """What OurHike's Postgres answers for each of export_conditions.py's queries: the columns and their types, then the rows.

    The rows are the QUERY's answer, after its predicate and window: fixture
    mode stands in for the connection, not for the SQL (extract/_fixtures.py
    says what that leaves unexercised). Timestamps are naive UTC, as the
    columns are `timestamp without time zone` (backend/app/models/).
    """
    return {
        "closures": {
            "columns": [
                ["id", "varchar"],
                ["reported_at", "timestamp"],
                ["trail_id", "varchar"],
                ["start_mile_marker", "float8"],
                ["end_mile_marker", "float8"],
                ["reason_type", "varchar"],
                ["note", "text"],
                ["status", "varchar"],
                ["moderation_status", "varchar"],
                ["verified_at", "timestamp"],
                ["closed_since", "timestamp"],
                ["expected_reopen", "timestamp"],
                ["reroute_url", "varchar"],
                ["start_lat", "float8"],
                ["start_lon", "float8"],
                ["end_lat", "float8"],
                ["end_lon", "float8"],
            ],
            "rows": [
                # In PUBLIC_CLOSURES_SQL's ORDER BY start_mile_marker, id: the stand-in
                # connection returns the rows as written here, and sorts nothing.
                {
                    "id": "00000000-0000-4000-8000-00000000c003",
                    "reported_at": "2026-08-10T10:00:00",
                    "trail_id": "AT",
                    "start_mile_marker": 476.6,
                    "end_mile_marker": 485.8,
                    "reason_type": "flooding",
                    "note": "Fixture: reopened after the water went down.",
                    "status": "open",
                    "moderation_status": "verified",
                    "verified_at": "2026-08-10T12:00:00",
                    "closed_since": "2026-08-09T00:00:00",
                    "expected_reopen": None,
                    "reroute_url": None,
                    "start_lat": None,
                    "start_lon": None,
                    "end_lat": None,
                    "end_lon": None,
                },
                {
                    "id": "00000000-0000-4000-8000-00000000c002",
                    "reported_at": "2026-09-01T08:00:00",
                    "trail_id": "AT",
                    "start_mile_marker": 1026.7,
                    "end_mile_marker": 1026.7,
                    "reason_type": "maintenance",
                    "note": None,
                    "status": "reroute_available",
                    "moderation_status": "verified",
                    "verified_at": "2026-09-01T09:30:00",
                    "closed_since": None,
                    "expected_reopen": "2026-11-01T00:00:00",
                    "reroute_url": "https://example.org/fixture-reroute",
                    # Filed before #674 added the endpoints, so none.
                    "start_lat": None,
                    "start_lon": None,
                    "end_lat": None,
                    "end_lon": None,
                },
                {
                    "id": "00000000-0000-4000-8000-00000000c001",
                    "reported_at": "2026-09-20T13:05:00",
                    "trail_id": "AT",
                    "start_mile_marker": 1385.2,
                    "end_mile_marker": 1386.0,
                    "reason_type": "storm_damage",
                    "note": "Fixture blowdown across the treadway.",
                    "status": "closed",
                    "moderation_status": "verified",
                    "verified_at": "2026-09-20T15:00:00.250000",
                    "closed_since": "2026-09-19T00:00:00",
                    "expected_reopen": None,
                    "reroute_url": None,
                    "start_lat": 41.2671,
                    "start_lon": -74.0893,
                    "end_lat": 41.2702,
                    "end_lon": -74.0811,
                },
            ],
        },
        "reports": {
            "columns": [
                ["id", "varchar"],
                ["type", "varchar"],
                ["poi_id", "varchar"],
                ["lat", "float8"],
                ["lon", "float8"],
                ["mile", "float8"],
                ["reporter_type", "varchar"],
                ["timestamp", "timestamp"],
                ["note", "text"],
                ["follow_up", "json"],
                ["status", "varchar"],
                ["visibility", "varchar"],
                ["severity", "varchar"],
                ["verified_at", "timestamp"],
            ],
            "rows": [
                {
                    "id": "00000000-0000-4000-8000-00000000a001",
                    "type": "blowdown",
                    "poi_id": None,
                    "lat": 41.2671,
                    "lon": -74.0893,
                    "mile": 1385.4,
                    "reporter_type": "day",
                    "timestamp": "2026-09-21T11:00:00",
                    "note": "Fixture tree down, passable.",
                    "follow_up": None,
                    "status": "verified",
                    "visibility": "public",
                    "severity": "normal",
                    "verified_at": "2026-09-21T12:00:00",
                },
                {
                    "id": "00000000-0000-4000-8000-00000000a002",
                    "type": "animals",
                    "poi_id": "atc_shelters:fixture",
                    "lat": 41.30,
                    "lon": -74.02,
                    "mile": None,
                    "reporter_type": "thru",
                    "timestamp": "2026-09-22T07:45:30.500000",
                    "note": "Fixture bear at the shelter.",
                    "follow_up": {"answers": {"still_there": "yes"}},
                    "status": "verified",
                    "visibility": "public",
                    "severity": "serious",
                    "verified_at": "2026-09-22T08:00:00",
                },
                {
                    "id": "00000000-0000-4000-8000-00000000a003",
                    "type": "flooding",
                    "poi_id": None,
                    "lat": 41.22,
                    "lon": -74.10,
                    "mile": 1380.0,
                    "reporter_type": "section",
                    "timestamp": "2026-09-23T16:20:00",
                    "note": None,
                    "follow_up": None,
                    "status": "resolved",
                    "visibility": "public",
                    "severity": "serious",
                    "verified_at": None,
                },
            ],
        },
        "notes": {
            "columns": [
                ["id", "varchar"],
                ["poi_id", "varchar"],
                ["lat", "float8"],
                ["lon", "float8"],
                ["mile", "float8"],
                ["observation", "varchar"],
                ["note", "text"],
                ["observed_at", "timestamp"],
                ["reporter_type", "varchar"],
            ],
            "rows": [
                {
                    "id": "00000000-0000-4000-8000-00000000d001",
                    "poi_id": "atc_springs:fixture",
                    "lat": None,
                    "lon": None,
                    "mile": None,
                    "observation": "flowing",
                    "note": "Fixture: running well.",
                    "observed_at": "2026-09-25T09:00:00",
                    "reporter_type": "day",
                },
            ],
        },
        "disputes": {
            "columns": [["poi_id", "varchar"], ["accounts", "int8"], ["latest_at", "timestamp"], ["maintainer_said", "bool"]],
            "rows": [
                {"poi_id": "atc_springs:fixture-dry", "accounts": 2, "latest_at": "2026-09-24T18:00:00", "maintainer_said": False}
            ],
        },
    }


# --- ATC's Trail Updates, as their website serves them (#1793, stage 3) -------
#
# extract/_kinds.py's AtcTrailUpdatePages reads ATC's trail-updates sitemap and
# each update's page from this file, and parity.py serves the same file's
# listing pages to today's fetch_atc_updates.py, so both paths parse the same
# pages. The pages are shaped like ATC's real ones (read 2026-10-02) around
# exactly what lib/atc_scrape.py reads: the <title> ending " - Appalachian
# Trail Conservancy", JSON-LD's dateModified with the -04:00 offset all 86 live
# pages carried, the navigation ending at "Privacy Policy", the chip under the
# headline ("VA | Closure") followed by its "N DAYS AGO", and the newsletter
# block from "Stay Connected". The sitemap's lastmod is the same instant in
# UTC, as the live one's is. Every slug and title is a fixture's, apart from
# one reviewed slug, and each body is one sentence carrying the mile, never
# ATC's prose. The URLs are written out because this script imports nothing
# the CI step that runs it lacks; tests/test_extract_atc_trail_update_pages.py
# holds them to lib/atc_scrape.py's and the resource's own.
#
# reference/atc_updates.json was reviewed on 2026-08-24, so each page is placed
# against that day: three publish without a person (a point, a range written
# with thousands separators, ending on a whole mile that json.dumps() prints
# 1510.0, and edited late on 2026-09-12 Eastern, which is 2026-09-13 in UTC,
# and one mile stated twice), and each other page is refused
# by one branch of lib/atc_updates.py's auto_publish_refusal(), in its order.
# Two branches no page can reach, so int_closures__atc_automatic's unit test
# holds them instead: "no title" (parse_update() refuses a page with an empty
# headline, which refuses the whole read) and "no states on the page" (a page
# with no chip has no category either, and the category is checked first).
ATC_TRAIL_UPDATES_URL = "https://appalachiantrail.org/trail-updates/"
ATC_TRAIL_UPDATES_SITEMAP_URL = "https://appalachiantrail.org/trail-updates-sitemap.xml"

#: (slug, title, chip or None, dateModified, body).
ATC_FIXTURE_UPDATES = (
    (
        "fixture-shelter-closed-for-repairs",
        "Fixture VA: Shelter Closed for Repairs",
        "VA | Closure",
        "2026-09-03T15:54:14-04:00",
        "The fixture shelter is closed for repairs (NOBO mile 670.2).",
    ),
    (
        "fixture-spring-dry-water-carry",
        "Fixture CT: Spring Dry, Carry Water",
        "CT | Water",
        "2026-09-12T23:30:00-04:00",
        "Carry water from NOBO mile 1,503.6 to 1,510, where the fixture spring is dry.",
    ),
    (
        "fixture-footbridge-detour",
        "Fixture MD/WV: Footbridge Detour",
        "MD, WV | Detour",
        "2026-09-20T10:00:00-04:00",
        "The fixture footbridge (NOBO mile 1,026.7) is closed. Last year: the footbridge at NOBO mile 1,026.7 closed too.",
    ),
    # Refused: a person's row always wins (a real slug in the reviewed file).
    (
        "harpers-ferry-footbridge-closure",
        "Fixture: Footbridge Closure, Edited After Its Review",
        "MD, WV | Detour",
        "2026-09-25T09:00:00-04:00",
        "An edit to a reviewed update, at NOBO mile 1,026.7.",
    ),
    # Refused: last edited before the review.
    (
        "fixture-bear-activity-before-the-review",
        "Fixture NC/TN: Bear Activity",
        "NC, TN | Animal",
        "2026-08-01T12:00:00-04:00",
        "Fixture bear activity near NOBO mile 195.8.",
    ),
    # Refused: edited on the review's own day (strictly after, never on).
    (
        "fixture-parking-closed-on-the-review-day",
        "Fixture PA: Parking Closed",
        "PA | Parking",
        "2026-08-24T10:00:00-04:00",
        "The fixture lot at NOBO mile 1,138.0 is closed.",
    ),
    # Refused: a category this build does not know.
    (
        "fixture-flash-flood-emergency",
        "Fixture VA: Flash Flood",
        "VA | Emergency",
        "2026-09-15T08:00:00-04:00",
        "Fixture flooding at NOBO mile 700.1.",
    ),
    # Refused: no chip, so no category (checked before states).
    (
        "fixture-update-with-no-chip",
        "Fixture: An Update With No Chip",
        None,
        "2026-09-16T08:00:00-04:00",
        "Fixture notice at NOBO mile 800.4.",
    ),
    # Refused: no mile at all, a region-wide advisory.
    (
        "fixture-trail-wide-advisory",
        "Fixture NH: Trail-Wide Advisory",
        "NH | Hiking Safety",
        "2026-09-17T08:00:00-04:00",
        "A fixture advisory for the whole state, with no mile.",
    ),
    # Refused: two mile references that do not agree.
    (
        "fixture-gap-reroute-history",
        "Fixture NC/TN: Gap Reroute",
        "NC, TN | Relocation",
        "2026-09-18T08:00:00-04:00",
        "Rerouted from NOBO mile 360.6 to 364.8; earlier, a closure at NOBO mile 361.2.",
    ),
    # Refused: a mile off the end of the trail.
    (
        "fixture-mile-past-katahdin",
        "Fixture ME: Mile Typo",
        "ME | Alert",
        "2026-09-19T08:00:00-04:00",
        "Fixture notice at NOBO mile 2,207.5.",
    ),
    # Refused: a range that runs backwards.
    (
        "fixture-range-written-backwards",
        "Fixture VA: Burn Ban",
        "VA | Fire",
        "2026-09-21T08:00:00-04:00",
        "A fixture burn ban from NOBO mile 485.8 to 476.6.",
    ),
)


def _atc_page(title: str, chip: str | None, modified: str, body: str) -> str:
    """One update page, in the shape of ATC's live ones and of tests/test_lib_atc_scrape.py's page()."""
    chip_html = f"<span>{chip}</span>" if chip else ""
    return (
        '<!DOCTYPE html><html lang="en-US"><head>'
        f"<title>{title} - Appalachian Trail Conservancy</title>"
        '<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"WebPage",'
        f'"datePublished":"2026-08-01T09:00:00-04:00","dateModified":"{modified}"}}]}}</script>'
        "</head><body><main>"
        "<nav><a>Hike the Trail</a><a>Maine</a><a>Virginia</a></nav>"
        "<a>Terms, Conditions, &amp; Policies</a><a>Privacy Policy</a>"
        f"<h1>{title}</h1>{chip_html}<span>4 DAYS AGO</span>"
        f"<p>{body}</p>"
        '<h2>Stay Connected</h2><form><input name="email"></form>'
        "</main></body></html>"
    )


def _atc_listing_page(updates: tuple) -> str:
    """One listing page, each update linked as the live listing links it: `aria-label="View <title> update"`."""
    anchors = "".join(
        f'<a href="{ATC_TRAIL_UPDATES_URL}{slug}/" aria-label="View {title} update">{title}</a>' for slug, title, *_ in updates
    )
    return f"<!DOCTYPE html><html><head><title>Trail Updates - Appalachian Trail Conservancy</title></head><body><main>{anchors}</main></body></html>"


def _atc_sitemap(updates: tuple) -> str:
    """The trail-updates sitemap: each update's page and its lastmod in UTC, newest first, as All in One SEO writes it."""
    from datetime import datetime, timezone

    entries = sorted(
        ((slug, datetime.fromisoformat(modified).astimezone(timezone.utc).isoformat()) for slug, _, _, modified, _ in updates),
        key=lambda entry: entry[1],
        reverse=True,
    )
    urls = "".join(
        f"\n\t<url>\n\t\t<loc><![CDATA[{ATC_TRAIL_UPDATES_URL}{slug}/]]></loc>\n\t\t<lastmod><![CDATA[{lastmod}]]></lastmod>"
        "\n\t\t<changefreq><![CDATA[weekly]]></changefreq>\n\t\t<priority><![CDATA[0.7]]></priority>\n\t</url>"
        for slug, lastmod in entries
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<!-- A fixture of the sitemap All in One SEO generates. -->\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}\n</urlset>\n'
    )


def _atc_trail_updates() -> dict:
    """ATC's answers by URL: the sitemap, two listing pages (the second links nothing, which ends the walk) and each page."""
    html = "text/html; charset=UTF-8"
    answers = {
        ATC_TRAIL_UPDATES_SITEMAP_URL: {"content_type": "text/xml; charset=UTF-8", "body": _atc_sitemap(ATC_FIXTURE_UPDATES)},
        ATC_TRAIL_UPDATES_URL: {"content_type": html, "body": _atc_listing_page(ATC_FIXTURE_UPDATES)},
        f"{ATC_TRAIL_UPDATES_URL}page/2/": {"content_type": html, "body": _atc_listing_page(())},
    }
    for slug, title, chip, modified, body in ATC_FIXTURE_UPDATES:
        answers[f"{ATC_TRAIL_UPDATES_URL}{slug}/"] = {"content_type": html, "body": _atc_page(title, chip, modified, body)}
    return {"answers": answers}


# --- the JSON API notice sources (extract/_json_apis.py, decision 53 phase B) --
#
# One file per registry key under conditions/json_apis/, each a list of the
# answers its upstream gives: a URL without its query, the query parameters
# that answer needs, and the body as served. Every field name is one the
# decision 53 inventory read off the live answer on 2026-10-03 (sources.json's
# `notes` for each key); every value is invented, and no real alert, advisory,
# page or segment is copied. The person fields a live answer carries are here
# with invented values, so the readers' rules that keep them out are run.

NPS_ALERTS_URL = "https://developer.nps.gov/api/v1/alerts"
NPS_ROAD_EVENTS_URL = "https://developer.nps.gov/api/v1/roadevents"
DCNR_ADVISORY_URL = "https://services.dcnr.pa.gov/ParkAddresses/api/ParkAdvisory/get"
USGS_VOLCANOES_URL = "https://volcanoes.usgs.gov/hans-public/api/volcano/getElevatedVolcanoes"
TEHCC_WIKI_API = "https://tehcc.org/clubwiki/api.php"
FOOT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_3_u_8gtQSoiFSgzVAf3uGwPMj_nqQ25/export"
FMST_KML_URL = "https://www.google.com/maps/d/kml"
JSON = "application/json; charset=utf-8"


def _answer(url: str, body, query: dict | None = None, content_type: str = JSON) -> dict:
    return {
        "url": url,
        "query": query or {},
        "content_type": content_type,
        "body": body if isinstance(body, str) else json.dumps(body),
    }


def _nps_alert(number: int, park: str, category: str, title: str, indexed: str, road_events=()) -> dict:
    return {
        "id": f"00000000-0000-4000-8000-{number:012d}",
        "url": f"https://www.nps.gov/{park}/planyourvisit/conditions.htm" if number % 2 else "",
        "title": title,
        "parkCode": park,
        "description": f"Fixture description {number}.",
        "category": category,
        "relatedRoadEvents": list(road_events),
        "lastIndexedDate": f"{indexed} 00:00:00.0",
    }


def _nps_alerts_answers() -> dict:
    """Three alerts across three codes the entry lists, each category but Danger, and one road event linked."""
    road = {"title": "Fixture Road closed", "id": "00000000-0000-4000-9000-000000000001", "type": "roadevent", "url": ""}
    alerts = [
        _nps_alert(1, "semo", "Park Closure", "Fixture Visitor Center Closed", "2026-08-13"),
        _nps_alert(2, "grsm", "Caution", "Fixture Trail Washout", "2026-09-20", road_events=[road]),
        _nps_alert(3, "iatr", "Information", "Reroute in Effect - Fixture Segment", "2026-09-30"),
    ]
    return {"answers": [_answer(NPS_ALERTS_URL, {"total": "3", "limit": "500", "start": "0", "data": alerts})]}


def _nps_road_events_answers() -> dict:
    """Two WZDx events, a line and a multi-line, under a header whose contact fields must never land."""
    sources = [
        {
            "data_source_id": "fixture-source-1",
            "organization_name": "Fixture National Park",
            "update_date": "2026-09-01T00:00:00Z",
            "contact_name": "Fixture Park",
            "contact_email": "fixture-superintendent@example.invalid",
        }
    ]

    def event(number, event_type, geometry, **extra):
        return {
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "core_details": {
                    "name": f"Fixture Road event {number}",
                    "data_source_id": "fixture-source-1",
                    "event_type": event_type,
                    "road_names": ["Fixture Road"],
                    "direction": "eastbound",
                    "description": f"Fixture road event {number}.",
                },
                "start_date": "2026-09-24T01:00:00Z",
                "location_method": "unknown",
                "vehicle_impact": "all-lanes-closed",
                "is_start_date_verified": False,
                "is_end_date_verified": False,
                "is_start_position_verified": False,
                "is_end_position_verified": False,
                "beginning_accuracy": "estimated",
                "ending_accuracy": "estimated",
                "start_date_accuracy": "estimated",
                "end_date_accuracy": "estimated",
                "Id": f"00000000-0000-4000-a000-{number:012d}",
                "_id": number - 1,
                **extra,
            },
        }

    body = {
        "road_event_feed_info": {
            "publisher": "National Park Service",
            "version": "4.1",
            "update_date": "2026-10-01T00:00:00Z",
            "contact_name": "Fixture Publisher",
            "contact_email": "fixture-publisher@example.invalid",
            "data_sources": sources,
        },
        "type": "FeatureCollection",
        "features": [
            event(1, "incident", _line(0), end_date="2027-01-01T07:59:59Z", types_of_incident=[{"incident_type": "fire"}]),
            event(
                2,
                "work-zone",
                {"type": "MultiLineString", "coordinates": [_line(1)["coordinates"], _line(2)["coordinates"]]},
                types_of_work=[{"type_name": "surface-work"}],
            ),
        ],
    }
    return {"answers": [_answer(NPS_ROAD_EVENTS_URL, body)]}


def _dcnr_advisories_answers() -> dict:
    """Laurel Ridge's id with a statewide item and a lead-contamination alert shaped like the live one; Tioga's empty.

    The wording is invented. The shape is the 2026-10-03 one that matters: an
    IsAlert item naming two LHHT mile-markers, lead, and "drinking water", as
    HTML with a non-breaking space, which a reader must carry through whole.
    """
    laurel = [
        {"IsAlert": False, "Message": "<p><strong>Fixture Restrictions:</strong> A statewide fixture advisory.</p>"},
        {
            "IsAlert": True,
            "Message": (
                "<p>The fixture stream between mile-marker 31 and 32 has been contaminated by lead.&nbsp; "
                "Do not use it as a drinking water source.</p>\r\n<p></p>"
            ),
        },
    ]
    return {
        "answers": [
            _answer(DCNR_ADVISORY_URL, laurel, {"id": "6219"}),
            _answer(DCNR_ADVISORY_URL, [], {"id": "8116"}),
        ]
    }


def _usgs_volcanoes_answers() -> dict:
    """Two volcanoes sharing one observatory notice, as three AVO volcanoes did on 2026-10-03."""

    def volcano(vnum, name, color, level):
        notice = "DOI-USGS-FIX-2026-10-02T00:00:00+00:00"
        return {
            "obs_fullname": "Fixture Volcano Observatory",
            "obs_abbr": "fix",
            "volcano_name": name,
            "vnum": vnum,
            "notice_type_cd": "WU",
            "notice_identifier": notice,
            "sent_utc": "2026-10-02 00:00:00",
            "sent_unixtime": 1790899200,
            "color_code": color,
            "alert_level": level,
            "notice_url": f"https://volcanoes.usgs.gov/hans-public/notice/{notice}",
            "notice_data": f"https://volcanoes.usgs.gov/hans-public/api/notice/getNotice/{notice}",
        }

    body = [volcano("900001", "Fixture Peak", "YELLOW", "ADVISORY"), volcano("900002", "Fixture Cone", "ORANGE", "WATCH")]
    return {"answers": [_answer(USGS_VOLCANOES_URL, body)]}


def _tehcc_wiki_answers() -> dict:
    """The template's own page, the listing with revisions, and the listing alone, most specific first."""
    pages = [
        {"pageid": 9001, "ns": 0, "title": "Fixture Shelter", "touched": "2026-09-22T01:06:28Z", "lastrevid": 101, "length": 64},
        {
            "pageid": 9002,
            "ns": 10,
            "title": "Template:Fixture Bear Closure",
            "touched": "2026-07-28T11:08:02Z",
            "lastrevid": 102,
            "length": 48,
        },
    ]
    for page in pages:
        page["fullurl"] = f"https://tehcc.org/clubwiki/index.php?title={page['title'].replace(' ', '_')}"
    revisions = {
        9001: "{{Announcement|Fixture: a bear has been seen near the shelter.}}\nFixture page text.",
        9002: "{{Announcement|Fixture bear closure.}}",
    }
    with_revisions = [
        {
            **page,
            "revisions": [
                {
                    "revid": page["lastrevid"],
                    "parentid": page["lastrevid"] - 1,
                    "timestamp": page["touched"],
                    "slots": {
                        "main": {"contentmodel": "wikitext", "contentformat": "text/x-wiki", "content": revisions[page["pageid"]]}
                    },
                }
            ],
        }
        for page in pages
    ]
    template = {"batchcomplete": True, "query": {"pages": [{"pageid": 9000, "ns": 10, "title": "Template:Announcement"}]}}
    return {
        "answers": [
            _answer(TEHCC_WIKI_API, template, {"titles": "Template:Announcement"}),
            _answer(TEHCC_WIKI_API, {"batchcomplete": True, "query": {"pages": with_revisions}}, {"prop": "info|revisions"}),
            _answer(TEHCC_WIKI_API, {"batchcomplete": True, "query": {"pages": pages}}, {"prop": "info"}),
        ]
    }


def _foot_sheet_answers() -> dict:
    """A condition report shaped like FoOT's: a date row, two titled tables, the two person columns, a legend.

    The person columns hold invented names so the reader's allow list is what
    keeps them out; the second table's header has no Shelter Distance, as the
    live sheet's lower tables do not.
    """
    header = "Sect,Ranger District,Begin,End,Description,Miles,Adopted by,Last Condition Report Submitted,"
    rows = [
        ",,,,10/1/2026,,,,,,",
        "Fixture Trail CONDITION REPORT,,,,,,,,,,",
        header + '"Source of Last  Condition Report \n",Comments,"Shelter\nDistance"',
        "1,Fixture District,0.0,2.4,Fixture TH to Fixture Vista,2.4,Fixture Adopter One,10/25,Fixture Reporter One,,",
        "1,Fixture District,2.4,5.8,Fixture Vista to FR 1,3.4,Fixture Adopter Two,9/25,Fixture Reporter Two,Down tree removed,6.2",
        ",,,,,,,,,,",
        "Fixture Loop CONDITION REPORT,,,,,,,,,,",
        header + "Source of Last  Condition Report,Comments,",
        "FL,Fixture District,0.0,1.5,Fixture Loop start to campsite,1.5,Fixture Adopter Three,11/23,Fixture Reporter Three,,",
        ",Color Codes:,,Green=trail is clear,,,,,,,",
    ]
    return {"answers": [_answer(FOOT_SHEET_URL, "\n".join(rows) + "\n", {"format": "csv"}, "text/csv; charset=utf-8")]}


def _fmst_kml_answers() -> dict:
    """Three lines in one folder, open, closed and detour, each status in its description and its style, as FMST's map."""

    def placemark(name, status, style, i):
        coordinates = " ".join(f"{x},{y},0" for x, y in _line(i)["coordinates"])
        description = (
            f"{name}    <br>       <br>   Segment   4    <br>   Name   {name}    <br>   Length   1.0    <br>"
            f"   Trail Status   {status}"
        )
        return (
            f"<Placemark><name>{name}</name><description><![CDATA[{description}]]></description>"
            f"<styleUrl>#line-{style}-4000</styleUrl><LineString><tessellate>1</tessellate>"
            f"<coordinates>{coordinates}</coordinates></LineString></Placemark>"
        )

    body = (
        '<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        "<name>Fixture Recovery Status</name><Folder><name>Fixture Route</name>"
        + placemark("Fixture Gap to Fixture Ford", "Open", "38A800", 0)
        + placemark("Fixture Ford to Fixture Road", "CLOSED", "FF0000", 1)
        + placemark("Fixture River Detour", "Temporary detour", "FFA500", 2)
        + "</Folder></Document></kml>"
    )
    # The mid as well as forcekml: every Google My Maps export shares FMST_KML_URL, and an answer matching on forcekml
    # alone would serve this map for section G's My Maps too (extract/_fixtures.py takes the first answer that matches).
    return {
        "answers": [
            _answer(FMST_KML_URL, body, {"mid": "1oSH-JQQpOan3r5Km7lJSVDDopenkW6k", "forcekml": "1"}, "text/xml; charset=utf-8")
        ]
    }


def _json_api_fixtures() -> dict[str, str]:
    return {
        f"conditions/json_apis/{key}.json": json.dumps(document)
        for key, document in (
            ("nps_alerts", _nps_alerts_answers()),
            ("nps_road_events", _nps_road_events_answers()),
            ("pa_dcnr_park_advisories", _dcnr_advisories_answers()),
            ("usgs_elevated_volcanoes", _usgs_volcanoes_answers()),
            ("tehcc_wiki_announcements", _tehcc_wiki_answers()),
            ("foot_trail_condition_report", _foot_sheet_answers()),
            ("fmst_helene_status", _fmst_kml_answers()),
        )
    }


# --- the clubs' notice pages, feeds and WordPress posts (decision 53 phase B) ------
#
# PAGES AND FEEDS. One file per registry key under conditions/notices/, each the answers the key's
# reader asks for: `{"answers": {url: {"content_type", "body"}}, "rows": n}`, served by exact URL
# (extract/_fixtures.py's text_answers()), where `rows` is what the reader lands from them: one for a
# page, one an item for a feed. The URL is the registry row's, or, for a WordPress page read through
# REST, `/wp-json/wp/v2/pages/<id>` at its origin. THE SHAPES ARE MEASURED: each page's region, its
# title's place and its stated date's wording, WordPress's REST page and post (`title.rendered`,
# `content.rendered`, `modified_gmt`), and RSS 2.0 as WordPress, Drupal and Weebly serve it, are what
# decision 53's inventory and phase B's live reads found on 2026-10-03 (each row's sources.json `notes`
# says which). EVERY VALUE IS INVENTED and starts with 'Fixture': no real notice, name, title, post or
# number is copied. Each feed item carries a `dc:creator` and a `description`, so the reader's rule
# that neither lands is run. The two phase B batches wrote their halves separately: folders a to m in
# NOTICE_FIXTURES (numbered pages, feeds and REST pages), folders n to z and _shared/ in
# _notice_pages_n_to_z() (each page shaped like its own live one).
#
# Not here: the four PDFs (bmta_alerts_pdf, foot_hiker_alert_mm195, tatc_ridgerunner_reports and
# trustees_hunting_designations), which PageNotice reads through pypdf (extract/_notices.py's
# read_pdf), and the pipeline and dbt jobs do not install pypdf (requirements.in's note); fixture mode
# leaves them out the way it leaves GATC's water PDF out, as any resource with no fixture file.
#
# POSTS. One WordPress document per registry key under conditions/, the shape NYNJTC's uses: the
# category lookup by slug, the posts, the terms, and a custom post type's route under `types` (GMC's
# `alert`), each post with the fields its live posts route served, so WordpressPosts' change check,
# WP_DROPPED and the row's person_fields run.

NOTICE_HTML = "text/html; charset=UTF-8"
NOTICE_REST = "application/json; charset=UTF-8"
NOTICE_RSS = "application/rss+xml; charset=UTF-8"
FIXTURE_DAY = "September 21, 2026"


def _notice_page(h1: str, dated: str | None = f"Updated {FIXTURE_DAY}", region: str = "main") -> str:
    """An HTML page shaped like the live one: the notice in `region`, a menu and a footer the reader leaves out."""
    date_line = f"<p>{dated}</p>" if dated else ""
    title = f"<title>{h1}</title>"
    inner = f"<h1>{h1}</h1>{date_line}<p>Fixture notice: a trail section is closed for repairs.</p>"
    if region == "main":
        body = f"<nav>Fixture menu</nav><main>{inner}</main><footer>Fixture footer</footer>"
    elif region == "article":
        body = f"<nav>Fixture menu</nav><article>{inner}</article><footer>Fixture footer</footer>"
    else:
        body = f"<nav>Fixture menu</nav><div>{inner}</div><footer>Fixture footer</footer>"
    return f'<!doctype html><html><head><meta charset="utf-8">{title}</head><body>{body}</body></html>'


def _usfs_alerts_page(unit: str, alerts: bool = True) -> str:
    """A forest's alerts page: <main> whose <h1> is 'Alerts', the legend, and one alert card with its own start date
    or, for the Nez Perce trail's empty page, the page's own 'There are no alerts listed.'"""
    card = (
        f'<li class="usa-card wfs-alert-flag critical"><h3><a href="/{unit}/alerts/fixture-trail-closure">'
        f"<span>Fixture Trail Closure</span></a></h3><p>Alert Start Date: {FIXTURE_DAY}</p></li>"
        if alerts
        else "<li>There are no alerts listed.</li>"
    )
    legend = "".join(
        f'<li class="usa-card wfs-alert-flag {level}"><h3>{level}</h3></li>'
        for level in ("critical", "fire-restriction", "caution", "information")
    )
    return (
        '<!doctype html><html><head><meta charset="utf-8"><title>Alerts | US Forest Service</title></head><body>'
        f"<nav>Fixture menu</nav><main><h1>Alerts</h1><ul>{legend}</ul><ul>{card}</ul></main><footer>Fixture footer</footer>"
        "</body></html>"
    )


def _wp_rest_page(page_id: int, title: str) -> str:
    """A WordPress page as its REST route serves it: the fields PageNotice reads, and the ones it ignores."""
    return json.dumps(
        {
            "id": page_id,
            "date_gmt": "2026-01-05T14:00:00",
            "modified_gmt": "2026-09-21T14:13:20",
            "slug": "fixture-page",
            "status": "publish",
            "type": "page",
            "link": "https://fixture.example.org/fixture-page/",
            "title": {"rendered": title},
            "content": {
                "rendered": f"<h2>Fixture closure</h2><p>Updated {FIXTURE_DAY}</p><ul><li>Fixture bridge out.</li></ul>",
                "protected": False,
            },
        }
    )


USFS_ALERT_UNITS = (
    "r08/cherokee", "r08/gwj", "r08/northcarolina", "r08/alabama", "r08/chattahoochee-oconee", "r08/ouachita",
    "r09/whitemountain", "r09/gmfl", "r02/psicc", "r02/blackhills", "r04/uinta-wasatch-cache", "r10/chugach",
    "r01/dpg", "r05/lospadres",
)  # fmt: skip
#: Registry key -> the OTA section page's WordPress id (ota/closures.py's SECTION_PAGES).
OTA_SECTION_PAGES = {
    "ota_current_river_conditions": 42254, "ota_upper_current_river_conditions": 42332, "ota_eleven_point_conditions": 2678,
    "ota_victory_conditions": 42311, "ota_wappapello_conditions": 42312, "ota_north_fork_conditions": 42309,
    "ota_between_the_rivers_conditions": 42223, "ota_blair_creek_conditions": 2639, "ota_karkaghne_conditions": 42294,
    "ota_taum_sauk_conditions": 42300, "ota_middle_fork_conditions": 42308, "ota_courtois_conditions": 42207,
    "ota_trace_creek_conditions": 42310, "ota_marble_creek_conditions": 42307,
}  # fmt: skip


def _notice_pages_n_to_z() -> dict[str, tuple[str, str, str]]:
    """Registry key -> (URL a PageNotice asks, content type, body)."""
    pages = {
        f"usfs_{unit.replace('/', '_').replace('-', '_')}_alerts": (
            f"https://www.fs.usda.gov/{unit}/alerts",
            NOTICE_HTML,
            _usfs_alerts_page(unit),
        )
        for unit in USFS_ALERT_UNITS
    }
    pages["usfs_nez_perce_nht_alerts"] = (
        "https://www.fs.usda.gov/trails/nez-perce-nht/alerts",
        NOTICE_HTML,
        _usfs_alerts_page("trails/nez-perce-nht", alerts=False),
    )
    html = {
        "nps_natr_road_site_status": (
            "https://www.nps.gov/natr/planyourvisit/road-and-site-status.htm",
            _notice_page("Road and Site Status", f"Last updated: {FIXTURE_DAY}", region="body"),
        ),
        "nchpta_open_trails": (
            "https://nchighpeaks.org/2024Hikes",
            _notice_page("Fixture Trails Currently Open", "Update 9/21/2026", region="article"),
        ),
        "ncta_trail_alerts_page": (
            "https://northcountrytrail.org/the-trail/trail-alerts/",
            _notice_page("Fixture Trail Alerts", None, region="article"),
        ),
        "nysdec_adk_backcountry": (
            "https://dec.ny.gov/things-to-do/hiking/adirondack-backcountry/backcountry-information-for-adirondack-park",
            _notice_page("Fixture Backcountry Information", "New this week (9/21/2026)"),
        ),
        "palmetto_trail_closures": (
            "https://www.palmettotrail.org/updates/post/trail-closures-updated-2-5-26",
            _notice_page("Fixture Current Trail Closures", None),
        ),
        "palmetto_hunting_season": (
            "https://www.palmettotrail.org/updates/post/hunting-season",
            _notice_page("Fixture Hunting Season", None),
        ),
        "pa_dcnr_tioga_advisories": (
            "https://www.pa.gov/agencies/dcnr/recreation/where-to-go/state-forests/find-a-forest/tioga/advisories",
            _notice_page("Advisories", None),
        ),
        "patc_trails_banner": ("https://www.patc.net/trails", _notice_page("Fixture Trails", None, region="body")),
        "patc_tuscarora_updates": (
            "https://www.hikethetuscarora.org/updates",
            _notice_page("Fixture Tuscarora Trail Updates", None),
        ),
        "pnta_trail_alerts": (
            "https://www.pnt.org/pnta/know-before-you-go/plan-your-trip/trail-alerts/",
            _notice_page("Fixture Trail Alerts", f"Last Updated: {FIXTURE_DAY}"),
        ),
        "pnta_trail_conditions": (
            "https://www.pnt.org/pnta/know-before-you-go/plan-your-trip/trail-conditions/",
            _notice_page("Fixture Trail Conditions", "Last Updated: August 1, 2025"),
        ),
        "ebrpd_alerts_closures": (
            "https://www.ebparks.org/alerts-closures",
            _notice_page("Fixture Alerts and Closures", f"Updated {FIXTURE_DAY}"),
        ),
        "sbts_trail_conditions": (
            "https://www.yubaexpeditions.com/trail-conditions",
            _notice_page("Fixture Trails and Conditions", "Updated 9/21/26"),
        ),
        "sta_alerts": ("https://sheltoweetrace.org/alerts", _notice_page("Fixture Alerts and Conditions", None)),
        "sstc_trail_alerts": ("https://www.standingstonetrail.org/trail-alerts", _notice_page("Fixture Trail Alerts", None)),
        "sstc_trail_relocation_notice": (
            "https://www.standingstonetrail.org/copy-of-trail-relocation-notice",
            _notice_page("Fixture Trail Relocation Notice", None),
        ),
        "sstc_trail_closure_notice": (
            "https://www.standingstonetrail.org/trail-closure-notice",
            _notice_page("Fixture Temporary Trail Relocation", None),
        ),
        "trta_trail_conditions": (
            "https://tahoerimtrail.org/current-trail-conditions/",
            _notice_page("Fixture Current Trail Conditions", f"Updated {FIXTURE_DAY}", region="body"),
        ),
        "tehcc_recent_maintenance": (
            "https://tehcc.org/trail-maintenance/recent-at-maintenance/",
            _notice_page("Fixture Recent AT Maintenance", None),
        ),
        "trustees_hunting": (
            "https://thetrustees.org/content/hunting-on-trustees-properties/",
            _notice_page("Fixture Hunting on Properties", None, region="body"),
        ),
        "tpwd_davis_mountains_alerts": (
            "https://tpwd.texas.gov/state-parks/davis-mountains/alert",
            _notice_page("Park Alerts", None),
        ),
        "tpwd_mckinney_falls_alerts": ("https://tpwd.texas.gov/state-parks/mckinney-falls/alert", _notice_page("Alerts", None)),
        "hills_to_sea_closures": ("https://www.hillstosea.org/closures", _notice_page("Fixture Closures", None)),
        "wta_signpost": ("https://www.wta.org/news/signpost", _notice_page("Fixture Signpost Blog", None, region="article")),
        "portland_parks_trail_closures": (
            "https://www.portland.gov/parks/nature/trail-closures-and-delays",
            _notice_page("Fixture Trail Closures and Delays", f"This page was updated on {FIXTURE_DAY}."),
        ),
        "alaska_state_parks_conditions": (
            "https://dnr.alaska.gov/parks/asp/curevnts.htm",
            _notice_page("Fixture Division of Parks", f"Last Update: {FIXTURE_DAY}"),
        ),
        "in_dnr_knobstone_conditions": (
            "https://www.in.gov/dnr/forestry/properties/knobstone-trail-conditions-reroutes-maps/",
            _notice_page("Fixture Knobstone Trail Conditions", f"Knobstone Trail conditions Update: {FIXTURE_DAY}"),
        ),
    }
    pages.update({key: (url, NOTICE_HTML, body) for key, (url, body) in html.items()})
    # Mount Mitchell: the alert carousel sits in the page header, before <main>, which is why the resource's region is <body>.
    pages["nc_parks_mount_mitchell_alerts"] = (
        "https://www.ncparks.gov/state-parks/mount-mitchell-state-park",
        NOTICE_HTML,
        '<!doctype html><html><head><meta charset="utf-8"><title>Mount Mitchell State Park | NC State Parks</title></head><body>'
        '<header><div id="block-ncalertsblock"><div class="carousel-item alert-item warning"><div class="message" role="alert">'
        '<strong class="alert-type">Fixture alert: a road north of the park is closed.</strong></div></div></div></header>'
        "<main><h1>Mount Mitchell State Park</h1><p>Fixture park text.</p></main><footer>Fixture footer</footer></body></html>",
    )
    # Fragments with no title of their own, read with registry_title: NBATC's items open with their own ISO dates.
    pages["nbatc_announcements"] = (
        "https://home.nbatc.org/cgi-bin/nbatcNews.cgi?ACTION=getPosts&OFFSET=0&TYPE=updates&ROLES=",
        "text/html;",
        "<h3>2026-09-21 Fixture trail update</h3><p>Fixture body.</p><h3>2026-08-01 Fixture club news</h3><p>Fixture body.</p>",
    )
    pages["ma_dcr_blue_hills_alerts"] = (
        "https://www.mass.gov/alerts/page/14961",
        NOTICE_HTML,
        '<ul class="ma__header-alerts__container"><li><section class="ma__action-step">'
        '<span class="ma__action-step__title-text">Fixture notice</span>'
        '<span class="ma__action-step__title-suffix">Updated Sep. 21, 2026, 9:00 am</span></section></li></ul>',
    )
    rest = {
        "ohta_trail_alerts": ("https://ozarkhighlandstrail.com", 2987),
        "shta_trail_conditions": ("https://superiorhiking.org", 73),
    }
    rest.update({key: ("https://ozarktrail.com", page_id) for key, page_id in OTA_SECTION_PAGES.items()})
    for key, (origin, page_id) in rest.items():
        pages[key] = (f"{origin}/wp-json/wp/v2/pages/{page_id}", NOTICE_REST, _wp_rest_page(page_id, f"Fixture {key}"))
    return pages


def _wp_category_post(site: str, post_id: int, category: int, title: str, modified_gmt: str) -> dict:
    """One post as a WordPress posts route serves it, `content` and `excerpt` included so the row's person_fields drop them."""
    return {
        "id": post_id,
        "date": "2026-03-01T09:00:00",
        "date_gmt": "2026-03-01T14:00:00",
        "guid": {"rendered": f"{site}/?p={post_id}"},
        "modified": modified_gmt.replace("T14", "T10"),
        "modified_gmt": modified_gmt,
        "slug": f"fixture-post-{post_id}",
        "status": "publish",
        "type": "post",
        "link": f"{site}/fixture-post-{post_id}/",
        "title": {"rendered": title},
        "content": {"rendered": "<p>Fixture body, with a fixture number that never loads: 555-0100.</p>", "protected": False},
        "excerpt": {"rendered": "<p>Fixture excerpt.</p>", "protected": False},
        "author": 3,
        "featured_media": 0,
        "comment_status": "closed",
        "ping_status": "closed",
        "sticky": False,
        "template": "",
        "format": "standard",
        "meta": {"footnotes": ""},
        "categories": [category],
        "tags": [],
        "class_list": [f"post-{post_id}", "post"],
        "_links": {"self": [{"href": f"{site}/wp-json/wp/v2/posts/{post_id}"}]},
    }


#: Registry key -> (site origin, category id, category slug), as the live categories route answered on 2026-10-03.
WP_CATEGORY_POSTS = {
    "ohta_trail_alerts_posts": ("https://ozarkhighlandstrail.com", 18, "trailalerts"),
    "pnta_trail_conditions_posts": ("https://www.pnt.org", 188, "trail-conditions"),
    "tehcc_at_posts": ("https://tehcc.org", 3, "appalachian-trail"),
    "tko_oct_trail_conditions": ("https://trailkeepersoforegon.org", 10, "trail-conditions"),
}


def _notice_fixtures_n_to_z() -> dict[str, str]:
    """Decision 53 phase B's page notices and WordPress posts for folders n to z and _shared/ (the comment above)."""
    files = {
        f"conditions/notices/{key}.json": json.dumps({"answers": {url: {"content_type": content_type, "body": body}}, "rows": 1})
        for key, (url, content_type, body) in _notice_pages_n_to_z().items()
    }
    for key, (site, category, slug) in WP_CATEGORY_POSTS.items():
        posts = [
            _wp_category_post(
                site, 9100 + n, category, f"Fixture notice {n} &#8211; trail closed", f"2026-09-{20 + n:02d}T14:13:20"
            )
            for n in (1, 2)
        ]
        files[f"conditions/{key}.json"] = json.dumps(
            {"categories": [{"id": category, "slug": slug}], "posts": posts, "terms": {}}
        )
    return files


#: Registry key -> (shape, the URL its reader asks). Shapes: "html" a page, "wp" a
#: WordPress page or post through its REST route, "feed" RSS, "region:<css>" a page
#: whose notice is the one element the resource names.
NOTICE_FIXTURES = {
    "amc_net_closures_notices": ("wp", "https://newenglandtrail.org/wp-json/wp/v2/pages/27"),
    "amc_facility_conditions": ("html", "https://www.outdoors.org/weather-trail-conditions/"),
    "amc_wma_at_parking": ("html", "https://www.amc-wma.org/documents-more.cgi?id=112"),
    "amc_wma_at_campsites": ("html", "https://www.amc-wma.org/documents-more.cgi?id=13"),
    "amcdv_bear_safety": ("wp", "https://amcdv.org/wp-json/wp/v2/posts/5079"),
    "ttc_butler_trail_detours": ("wp", "https://thetrailconservancy.org/wp-json/wp/v2/pages/5616"),
    "blm_alerts": ("html", "https://www.blm.gov/alerts"),
    "bmecc_fluorescent_orange": ("html", "https://www.bmecc.org/appalachian-trail/fluorescent-orange"),
    "bmecc_appalachian_trail": ("html", "https://www.bmecc.org/appalachian-trail"),
    "bmta_alert_bar": ("region:alert-bar__content", "https://bmta.org/"),
    "catamount_section_31": ("wp", "https://catamounttrail.org/wp-json/wp/v2/pages/12414"),
    "cfpa_trail_notices": ("html", "https://ctwoodlands.org/trail-notices/"),
    "cfpa_trail_notices_feed": ("feed", "https://ctwoodlands.org/trail-notices/feed/"),
    "cohos_trail_changes": ("wp", "https://www.cohostrail.org/wp-json/wp/v2/pages/66"),
    "cohos_trouble_spots": ("wp", "https://www.cohostrail.org/wp-json/wp/v2/pages/168"),
    "ct_deep_parks_emergency_message": ("html", "https://portal.ct.gov/deep/state-parks/emergency-message---parks"),
    "cvatc_news": ("feed", "https://www.cvatclub.org/news/feed"),
    "duluth_parks_news": ("html", "https://duluthmn.gov/parks/"),
    "foothills_trail_conditions": ("wp", "https://foothillstrail.org/wp-json/wp/v2/pages/25"),
    "gatc_alerts": ("feed", "https://georgia-atclub.org/alerts/feed/"),
    "gatc_news_feed": ("feed", "https://georgia-atclub.org/feed/"),
    "lsht_thru_hike_notes": ("html", "https://lonestartrail.org/content.aspx?page_id=22&club_id=738078&module_id=678717"),
    "lsht_news": ("html", "https://lonestartrail.org/content.aspx?page_id=3&club_id=738078"),
    "matc_kennebec_ferry": ("wp", "https://www.matc.org/wp-json/wp/v2/pages/474"),
    "mcomd_club_news_feed": ("feed", "https://www.mcomd.org/category/club-news-and-announcements/feed/"),
    "mohonk_alerts": ("wp", "https://www.mohonkpreserve.org/wp-json/wp/v2/pages/13789"),
    "mohonk_peregrine_updates": ("wp", "https://www.mohonkpreserve.org/wp-json/wp/v2/pages/1502"),
    "mratc_trail_alerts": ("html", "https://www.mratc.org/"),
    "mratc_blog_feed": ("feed", "https://www.mratc.org/blog-feed.xml"),
    "msgtc_trail_conditions": ("wp", "https://www.msgtc.org/wp-json/wp/v2/pages/24"),
}
NOTICE_FIXTURES.update(
    {
        f"fta_closures_nth_{part}": ("feed", f"https://floridatrail.org/category/{slug}/feed/")
        for part, slug in (
            ("general", "closures-notice-to-hikers-general"),
            ("panhandle", "closures-and-nth-panhandle"),
            ("north", "closures-and-nth-north"),
            ("central", "closures-and-nth-central"),
            ("south", "closures-and-nth-south"),
        )
    }
)
NOTICE_FIXTURES.update(
    {
        f"blm_press_{state}": ("feed", f"https://www.blm.gov/press-release/{state.replace('_', '-')}/rss")
        for state in (
            "national_office", "alaska", "arizona", "california", "colorado", "eastern_states", "idaho",
            "montana_dakotas", "nevada", "new_mexico", "oregon_washington", "utah", "wyoming",
        )
    }
)  # fmt: skip
NOTICE_FIXTURES.update(
    {
        f"blm_fire_restrictions_{state}": ("html", f"https://www.blm.gov/programs/{path}/fire-restrictions")
        for state, path in (
            ("alaska_fire_service", "fire-and-aviation/regional-info/alaska-fire-service"),
            ("arizona", "public-safety-and-fire/fire/regional-info/arizona"),
            ("california", "fire/regional-info/california"),
            ("colorado", "fire/regional-info/colorado"),
            ("idaho", "fire/regional-info/idaho"),
            ("montana", "fire/regional-info/montana"),
            ("new_mexico", "fire/regional-info/new-mexico"),
            ("north_dakota", "fire/regional-info/north-dakota"),
            ("oregon_washington", "fire/regional-info/oregon-washington"),
            ("south_dakota", "fire/regional-info/south-dakota"),
            ("utah", "fire/regional-info/utah"),
            ("wyoming", "fire/regional-info/wyoming"),
        )
    }
)
NOTICE_FIXTURES.update(
    {
        f"bta_section_{section}": ("html", f"https://buckeyetrail.org/sections/{section.replace('_', '-')}")
        for section in (
            "burton", "mogadore", "massillon", "bowerston", "belle_valley", "stockport", "road_fork", "whipple",
            "new_straitsville", "old_mans_cave", "scioto_trail", "sinking_spring", "shawnee", "west_union",
            "williamsburg", "loveland", "caesar_creek", "troy", "st_marys", "delphos", "defiance", "pemberville",
            "norwalk", "medina", "akron", "bedford",
        )
    }
)  # fmt: skip
NOTICE_FIXTURES.update(
    {
        f"msta_{section}": ("html", f"https://hike-mst.org/index.php/the-trail/section-updates/{article}-{section.replace('_', '-')}")
        for section, article in (
            ("section_1", 134), ("section_2", 135), ("section_3", 136), ("section_4", 137), ("section_5", 138),
            ("section_6", 139), ("section_7", 140), ("section_8", 143), ("section_9", 144), ("section_10", 145),
            ("section_11", 147), ("section_12", 148), ("section_13", 149), ("section_14", 150), ("section_15", 151),
            ("section_16", 152), ("section_17", 153), ("section_18", 168), ("section_19", 155), ("section_20", 156),
            ("section_a", 157), ("section_b", 158), ("section_c", 229),
        )
    }
)  # fmt: skip


def _numbered_notice_page(n: int, region: str | None = None) -> str:
    """A page as its site serves it: <title>, a menu and a footer the reader leaves out, and the notice in <main>."""
    notice = f"<h1>Fixture Notice Page {n}</h1><p>Updated September 21, 2026</p><p>Fixture notice text {n}.</p>"
    if region:
        notice = f'<div class="{region}"><a href="/fixture.pdf">Fixture alert bar text {n}.</a></div>'
    return (
        f"<!DOCTYPE html><html><head><title>Fixture Site {n}</title>"
        '<script type="application/ld+json">{"@type": "WebPage", "dateModified": "2026-09-20T12:00:00Z"}</script></head>'
        f"<body><nav><a href='/'>Fixture menu</a></nav><main>{notice}</main>"
        "<footer>Fixture footer. This page last updated: 2026-04-14</footer></body></html>"
    )


def _notice_wp(n: int, url: str) -> str:
    """A WordPress page or post through its REST route, the fields PageNotice reads and some it does not."""
    return json.dumps(
        {
            "id": n,
            "date_gmt": "2025-01-02T10:00:00",
            "modified_gmt": "2026-09-21T14:13:20",
            "slug": f"fixture-page-{n}",
            "link": url,
            "title": {"rendered": f"Fixture Notice Page {n}"},
            "content": {"rendered": f"<p>Fixture notice text {n}.</p><p>Fixture second paragraph.</p>", "protected": False},
            "author": 9,
            "yoast_head": "<meta name='author' content='Fixture Person'>",
        }
    )


def _notice_feed(n: int, url: str) -> str:
    """RSS 2.0 with two items, each with a guid, a link, a pubDate, a category, a creator and prose that never land."""
    site = url.split("/")[2]
    items = "".join(
        f"<item><title>Fixture Notice {n}.{i}</title><link>https://{site}/fixture-notice-{n}-{i}/</link>"
        f"<dc:creator><![CDATA[Fixture Person]]></dc:creator><pubDate>Mon, 2{i} Sep 2026 14:00:00 +0000</pubDate>"
        f'<category>Fixture Category</category><guid isPermaLink="false">https://{site}/?p={n * 10 + i}</guid>'
        f"<description><![CDATA[<p>Fixture prose {n}.{i}.</p>]]></description></item>"
        for i in (1, 2)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"<channel><title>Fixture Feed {n}</title><link>https://{site}/</link>{items}</channel></rss>"
    )


def _notice_fixtures() -> dict[str, str]:
    files = {}
    for n, (key, (shape, url)) in enumerate(sorted(NOTICE_FIXTURES.items()), 1):
        if shape == "feed":
            answer, rows = {"content_type": NOTICE_RSS, "body": _notice_feed(n, url)}, 2
        elif shape == "wp":
            answer, rows = {"content_type": NOTICE_REST, "body": _notice_wp(n, url)}, 1
        else:
            region = shape.split(":", 1)[1] if shape.startswith("region:") else None
            answer, rows = {"content_type": NOTICE_HTML, "body": _numbered_notice_page(n, region)}, 1
        files[f"conditions/notices/{key}.json"] = json.dumps({"answers": {url: answer}, "rows": rows})
    return files


def _club_wp_post(post_id: int, site: str, categories: list[int], **taxonomies) -> dict:
    """One post as a club's posts route serves it, with the fields WP_DROPPED leaves out (author, Yoast, Spectra)."""
    return {
        "id": post_id,
        "date_gmt": "2026-08-30T16:04:07",
        "modified_gmt": "2026-09-04T18:52:05",
        "slug": f"fixture-notice-{post_id}",
        "status": "publish",
        "link": f"https://{site}/fixture-notice-{post_id}/",
        "title": {"rendered": f"Fixture Notice {post_id}"},
        "content": {"rendered": "<p>Fixture body text, which never reaches a phone.</p>", "protected": False},
        "excerpt": {"rendered": "<p>Fixture excerpt.</p>", "protected": False},
        "author": 9,
        "categories": categories,
        "tags": [],
        **taxonomies,
        "class_list": [f"post-{post_id}"],
        "yoast_head": "<meta name='author' content='Fixture Person'>",
        "yoast_head_json": {"author": "Fixture Person"},
        "uagb_author_info": {"display_name": "Fixture Person"},
        "_links": {"self": [{"href": f"https://{site}/wp-json/wp/v2/posts/{post_id}"}]},
    }


def _club_wordpress_fixtures() -> dict[str, str]:
    """The category lookup and posts of the three club WordPress sources phase B registered, or GMC's `alert` type.

    Field names are the ones each site's posts route served on 2026-10-03
    (sources.json's `notes`); ATA's category 251 carries a passage term beside
    it, as its live posts do; MATC's category is 157; GMC's posts sit in no
    category and carry `alert-category` terms.
    """
    ata, gmc, matc = "aztrail.org", "greenmountainclub.org", "www.matc.org"
    documents = {
        "ata_closures_reroutes": {
            "categories": [{"id": 251, "slug": "closures-reroutes"}],
            "posts": [_club_wp_post(8001, ata, [251, 140]), _club_wp_post(8002, ata, [251])],
            "terms": {},
        },
        "gmc_trail_alerts": {
            "categories": [],
            "posts": [],
            "terms": {},
            "types": {"alert": [_club_wp_post(8101, gmc, [], **{"alert-category": [3]})]},
        },
        "matc_hazard_posts": {
            "categories": [{"id": 157, "slug": "hazard"}],
            "posts": [_club_wp_post(8201, matc, [157]), _club_wp_post(8202, matc, [157])],
            "terms": {},
        },
    }
    return {f"conditions/{key}.json": json.dumps(document) for key, document in documents.items()}


def closures_and_warnings_fixtures() -> dict[str, str]:
    """The closures and warnings family's fixture files, under conditions/: NWS, NYNJTC's WordPress, OurHike's Postgres,
    ATC's site, the JSON API notice sources, and the clubs' notice pages, feeds and WordPress posts."""
    return {
        "conditions/nws_alerts.json": json.dumps(_nws_alerts()),
        "conditions/nynjtc_trail_alerts.json": json.dumps(_nynjtc_trail_alerts()),
        "conditions/ourhike_postgres.json": json.dumps(_ourhike_postgres()),
        "conditions/atc_trail_updates.json": json.dumps(_atc_trail_updates()),
        "weather/squares.json": json.dumps(_weather_squares(), separators=(",", ":")),
        **_json_api_fixtures(),
        **_notice_fixtures(),
        **_notice_fixtures_n_to_z(),
        **_club_wordpress_fixtures(),
    }


# --- closures and warnings: the ArcGIS layers decision 53 registers (phase B) ---------
#
# One file per layer under external/, where extract/_fixtures.py's fixture_file() finds it
# by registry key, so fixture mode runs each layer through ArcgisLayer's own change check,
# pager, hints and count proof. THE NAMES ARE MEASURED: every property is a field name the
# layer's live ?f=json lists, read in decision 53's phase A inventory on 2026-10-03 (the
# session's scratchpad, never committed). THE VALUES ARE INVENTED and start with 'Fixture'
# wherever they are text. Fixture mode answers every query with every row, whatever its
# `where`, so each row carries a status value the layer's own filter keeps. No person field
# appears: those never reach the raw store (pipeline/ELT.md, 'Who may publish', rule 8).

#: Epoch milliseconds, the way ArcGIS sends a date: 2026-09-21T14:13:20Z.
FIXTURE_DATE_MS = 1790000000000

#: Registry key -> (geometry builder, the one row's properties).
NOTICE_LAYERS = {
    "usfs_rec_opportunities_status": (
        _point,
        {
            "objectid": 1,
            "recareaid": 1,
            "recareaname": "Fixture Recreation Area",
            "forestname": "Fixture National Forest",
            "forestorgcode": "0811",
            "openstatus": "temporarily closed",
            "recareaurl": "https://www.fs.usda.gov/recarea/fixture",
        },
    ),
    "usfs_r03_fire_restrictions": (
        _polygon,
        {
            "objectid": 1,
            "forestname": "Fixture National Forest",
            "ordername": "Fixture Stage 1 Fire Restrictions",
            "ordernum": "03-00-00-26-01",
            "ordertype": "Fire Restriction",
            "startdate": FIXTURE_DATE_MS,
            "enddate": FIXTURE_DATE_MS,
            "rescinddate": None,
            "hyperlink": "https://www.fs.usda.gov/fixture-order.pdf",
        },
    ),
    "usfs_r03_forest_orders": (
        _point,
        {
            "objectid": 1,
            "forestname": "Fixture National Forest",
            "ordername": "Fixture Area Closure",
            "ordernum": "03-00-00-26-02",
            "ordertype": "Closure",
            "startdate": FIXTURE_DATE_MS,
            "enddate": None,
            "rescinddate": None,
            "hyperlink": "https://www.fs.usda.gov/fixture-closure.pdf",
        },
    ),
    "usfs_r04_forest_orders": (
        _polygon,
        {
            "objectid": 1,
            "forestname": "Fixture-Wasatch-Cache National Forest",
            "ordername": "Fixture Trail Closures",
            "ordernum": "04-19-26-001",
            "ordertype": "Safety Closure",
            "startdate": FIXTURE_DATE_MS,
            "enddate": FIXTURE_DATE_MS,
            "rescinddate": None,
            "hyperlink": "https://www.fs.usda.gov/fixture-r4-order.pdf",
            "pub_date": FIXTURE_DATE_MS,
        },
    ),
    "usfs_r06_fire_closure_points": (
        _point,
        {
            "OBJECTID": 1,
            "ForestUnit": "Fixture National Forest",
            "District": "Fixture Ranger District",
            "FireName": "Fixture Fire",
            "ClosureOrderName": "Fixture Fire Area Closure",
            "ClosureOrderNumber": "06-00-00-26-01",
            "ClosureStatus": "Active",
            "ClosureStartDate": FIXTURE_DATE_MS,
            "ClosureEndDate": None,
            "ClosureURLlink": "https://www.fs.usda.gov/fixture-r6-order",
            "GlobalID": "{fixture-usfs-r06-fire-closure-points-1}",
        },
    ),
    "usfs_r06_fire_closure_lines": (
        _line,
        {
            "OBJECTID": 1,
            "ForestUnit": "Fixture National Forest",
            "District": "Fixture Ranger District",
            "FireName": "Fixture Fire",
            "ClosureOrderName": "Fixture Fire Area Closure",
            "ClosureOrderNumber": "06-00-00-26-02",
            "ClosureStatus": "Active",
            "ClosureStartDate": FIXTURE_DATE_MS,
            "ClosureEndDate": None,
            "ClosureURLlink": "https://www.fs.usda.gov/fixture-r6-order",
            "RouteName": "FIXTURE BUTTE",
            "RouteNum": "400",
            "GlobalID": "{fixture-usfs-r06-fire-closure-lines-1}",
        },
    ),
    "usfs_r06_fire_closure_areas": (
        _polygon,
        {
            "OBJECTID": 1,
            "ForestUnit": "Fixture National Forest",
            "District": "Fixture Ranger District",
            "FireName": "Fixture Fire",
            "ClosureOrderName": "Fixture Fire Area Closure",
            "ClosureOrderNumber": "06-00-00-26-03",
            "ClosureStatus": "Active",
            "ClosureStartDate": FIXTURE_DATE_MS,
            "ClosureEndDate": None,
            "ClosureURLlink": "https://www.fs.usda.gov/fixture-r6-order",
            "GlobalID": "{fixture-usfs-r06-fire-closure-areas-1}",
        },
    ),
    "usfs_r09_superior_closures": (
        _point,
        {
            "OBJECTID": 1,
            "SITE_NAME": "Fixture Lake Campsite",
            "SITE_ID": 1.0,
            "Closure_Type": "Campsite Closure",
            "Posted_Date": FIXTURE_DATE_MS,
            "ExpireDate": None,
            "ClosureOrderNumber": "09-09-26-01",
            "WebSite": "https://www.fs.usda.gov/superior/fixture",
            "GlobalID": "{fixture-usfs-r09-superior-closures-1}",
        },
    ),
    "usfs_r01_bmwc_trail_closures": (
        _line,
        {
            "OBJECTID": 1,
            "Trail_Status": "Closed",
            "Field_Season": "2026",
            "ID": "BMWC-1",
            "NAME": "FIXTURE CREEK",
            "GIS_MILES": 4.2,
        },
    ),
    "usfs_r01_kootenai_inaccessible": (
        _line,
        {
            "OBJECTID": 1,
            "Status": "Inaccessible",
            "ID": "FIXTURE-7",
            "Comments": "Fixture washout",
            "PlannedWorkDate": None,
            "Miles": 1.3,
            "GlobalID": "{fixture-usfs-r01-kootenai-inaccessible-1}",
        },
    ),
    "usfs_forest_closure_area": (_polygon, {"OBJECTID": 1, "Name": "Fixture Closure Area", "Acres": 120.5}),
    "usfs_baer_assessments": (
        _polygon,
        {
            "objectid": 1,
            "baer_name": "FIXTURE FIRE",
            "incident_name": "Fixture Fire",
            "ig_date": FIXTURE_DATE_MS,
            "gis_acres": 1520.0,
            "forest_names": "Fixture National Forest",
            "etl_modified_date": FIXTURE_DATE_MS,
        },
    ),
    "usfs_r08_prescribed_burns": (
        _polygon,
        {
            "OBJECTID": 1,
            "ADMIN_FOREST_CODE": "03",
            "ORG": "Fixture Ranger District",
            "BURN_BLOCK_NAME": "Fixture Block 7",
            "BURN_STATUS": "Planned for 1-10 days",
            "BURN_TYPE": "Broadcast",
            "DATE_COMPLETED": None,
            "GlobalID": "{fixture-usfs-r08-prescribed-burns-1}",
        },
    ),
    "nps_grca_closures": (
        _polygon,
        {
            "FID": 1,
            "name": "Fixture Trail",
            "status": "Closed",
            "dates": "Until further notice",
            "notes": "Fixture note",
            "last_edi_1": FIXTURE_DATE_MS,
            "globalid": "{fixture-grca-1}",
            "IRMA_URL": "https://irma.nps.gov/fixture",
        },
    ),
    "nps_seki_closures": (
        _line,
        {
            "OBJECTID": 1,
            "FullName": "Fixture Trail",
            "UnitName": "Sequoia and Kings Canyon National Parks",
            "LastEditDate": FIXTURE_DATE_MS,
            "IsPublic": "Yes",
            "IsVisible": "Yes",
            "Closure_Type": "Administrative",
            "Closure_Desc": "Fixture closure",
            "GlobalID": "{fixture-nps-seki-closures-1}",
        },
    ),
    "nps_yose_trail_closures": (
        _line,
        {
            "OBJECTID": 1,
            "trail": "Fixture Trail",
            "starttime": FIXTURE_DATE_MS,
            "endtime": FIXTURE_DATE_MS,
            "EditDate": FIXTURE_DATE_MS,
            "GlobalID": "{fixture-nps-yose-trail-closures-1}",
        },
    ),
    "nps_yose_fire_restrictions": (
        _polygon,
        {
            "OBJECTID": 1,
            "MAPLABEL": "Fixture Zone",
            "Zone": "Fixture",
            "RESTRICTSTAGE": "Stage 1",
            "RESTRICTDESC": "Fixture restriction",
            "PUBLICDISPLAY": "Yes",
            "EDITDATE": FIXTURE_DATE_MS,
            "GlobalID": "{fixture-nps-yose-fire-restrictions-1}",
        },
    ),
    "nps_yell_bear_management_areas": (
        _polygon,
        {
            "OBJECTID": 1,
            "CLOSED": "Yes",
            "NAME": "Fixture BMA",
            "Status": "Closed",
            "ClosureDate_Begin": FIXTURE_DATE_MS,
            "ClosureDate_End": FIXTURE_DATE_MS,
            "Expected_OpenDate": None,
            "GlobalID": "{fixture-nps-yell-bear-management-areas-1}",
        },
    ),
    "nps_appa_helene_status": (_line, {"OBJECTID": 1, "HeleneStatus": "Closed", "AssessmentComplete": "Yes"}),
    "grsm_trails_access": (
        _line,
        {
            "OBJECTID": 1,
            "TRAILNAME": "Fixture Creek Trail",
            "TRAILSTATUS": "Existing",
            "ACCESS": "Closed",
            "NOTES": "Fixture closed beyond the first mile",
            "EditDate": FIXTURE_DATE_MS,
            "GlobalID": "{fixture-grsm-trails-access-1}",
        },
    ),
    "blm_shooting_points": (
        _point,
        {
            "FID": 1,
            "STATE": "UT",
            "CURRENT_STATUS": "Authorized",
            "DISTRICT": "Fixture District",
            "NAME": "Fixture Shooting Range",
            "TYPE_OF_RANGE_": "Rifle",
        },
    ),
    "blm_or_rec_site_status": (
        _point,
        {
            "OBJECTID": 1,
            "Status__District": "Fixture District",
            "Status__RecSiteName": "Fixture Campground",
            "Status__RecreationSiteType": "Campground",
            "Status__CurrentRecSiteStatus": "Closed",
            "Status__CurrentStatusNotes": "Fixture note",
            "Status__WebLink": "https://www.blm.gov/fixture",
            "OregonRecreationSitesStatus_GLO": "{fixture-blm-or-rec-site-status-1}",
        },
    ),
    "fws_hunt_units": (
        _polygon,
        {
            "OBJECTID": 1,
            "Hunt_Unit_Name": "Fixture Unit A",
            "Huntable": "Yes",
            "Organization_Name": "Fixture NWR",
            "Hunting_Website": "https://www.fws.gov/refuge/fixture",
            "State": "MD",
            "GlobalID": "{fixture-fws-hunt-units-1}",
        },
    ),
    "usace_garrison_hunting_restrictions": (
        _polygon,
        {
            "OBJECTID": 1,
            "Section": "Fixture",
            "Restriction": "No Hunting or Trapping",
            "AreaID": "FX-1",
            "AreaName": "Fixture Recreation Area",
            "GlobalID": "{fixture-usace-garrison-hunting-restrictions-1}",
        },
    ),
    "usace_sam_closed_rec_areas": (
        _polygon,
        {
            "OBJECTID": 1,
            "GlobalID": "{fixture-usace-sam-closed-rec-areas-1}",
            "district": "Fixture District",
            "featureName": "Fixture Trail Section",
            "projectAreaStatus": "Closed",
            "recProjectSiteName": "Fixture Lake",
            "last_edited_date": FIXTURE_DATE_MS,
        },
    ),
    "usgs_pwfdf_assessments": (
        _point,
        {
            "OBJECTID": 1,
            "fire": "Fixture Fire",
            "location": "Fixture County, CA",
            "size": 1200.0,
            "status": "Complete",
            "Fire_ID": "FX2026",
            "start_date": FIXTURE_DATE_MS,
            "assessment_date": FIXTURE_DATE_MS,
            "download_url": "https://landslides.usgs.gov/fixture.zip",
        },
    ),
    "nifc_wfigs_current_perimeters": (
        _polygon,
        {
            "OBJECTID": 1,
            "poly_IncidentName": "Fixture Fire",
            "poly_GISAcres": 1500.5,
            "poly_DateCurrent": FIXTURE_DATE_MS,
            "attr_UniqueFireIdentifier": "2026-FXFIX-000001",
            "attr_PercentContained": 40.0,
            "attr_ModifiedOnDateTime_dt": FIXTURE_DATE_MS,
            "GlobalID": "{fixture-nifc-wfigs-current-perimeters-1}",
        },
    ),
    "odfw_orham_alert_areas": (
        _polygon,
        {
            "OBJECTID": 1,
            "WMU_Name": "Fixture WMU",
            "tract": "Fixture Tract",
            "access_period_text": "Fixture season",
            "alert_enabled": 1,
            "alert_title": "Fixture alert",
            "alert_start": FIXTURE_DATE_MS,
            "alert_end": None,
            "GlobalID": "{fixture-odfw-orham-alert-areas-1}",
            "last_edited_date": FIXTURE_DATE_MS,
        },
    ),
    "cdpr_park_unit_status": (
        _point,
        {
            "ObjectId": 1,
            "globalid": "{fixture-cdpr-park-unit-status-1}",
            "UNITNAME": "Fixture State Park",
            "UNITNUM": 1,
            "Status": "Full Closure",
            "closure_reason": "Fire",
            "StatusReopenDate": FIXTURE_DATE_MS,
            "status_notes_pub": "Fixture public note",
            "total_milestrail": 20,
            "closed_milestrail": 20,
            "EditDate": FIXTURE_DATE_MS,
        },
    ),
    "king_county_parks_alerts_points": (
        _point,
        {
            "OBJECTID": 1,
            "AlertType": "Full Closure",
            "Description": "Fixture closure",
            "StartDate": FIXTURE_DATE_MS,
            "EndDate": None,
            "GlobalID": "{fixture-king-county-parks-alerts-points-1}",
            "EditDate": FIXTURE_DATE_MS,
            "Title": "Fixture Trail closed",
            "URL": "https://kingcounty.gov/fixture",
        },
    ),
    "king_county_parks_alerts_lines": (
        _line,
        {
            "OBJECTID": 1,
            "AlertType": "Full Closure",
            "Description": "Fixture closure",
            "StartDate": FIXTURE_DATE_MS,
            "EndDate": None,
            "GlobalID": "{fixture-king-county-parks-alerts-lines-1}",
            "EditDate": FIXTURE_DATE_MS,
            "Title": "Fixture Trail closed",
            "URL": "https://kingcounty.gov/fixture",
        },
    ),
    "king_county_parks_alerts_areas": (
        _polygon,
        {
            "OBJECTID": 1,
            "AlertType": "Full Closure",
            "Description": "Fixture closure",
            "StartDate": FIXTURE_DATE_MS,
            "EndDate": None,
            "GlobalID": "{fixture-king-county-parks-alerts-areas-1}",
            "EditDate": FIXTURE_DATE_MS,
            "Title": "Fixture Trail closed",
            "URL": "https://kingcounty.gov/fixture",
        },
    ),
    "midpen_preserve_access": (
        _polygon,
        {
            "OBJECTID": 1,
            "UNIQUEID": "FX-1",
            "PRESERVE": "Fixture Preserve",
            "ACCESS": "Closed",
            "CLOSETYPE": "Temporary",
            "ACREAGE": 12.5,
            "last_edited_date": FIXTURE_DATE_MS,
            "GlobalID": "{fixture-midpen-preserve-access-1}",
        },
    ),
    "scc_parks_closed_areas": (
        _polygon,
        {
            "OBJECTID": 1,
            "park_name": "Fixture County Park",
            "unopened": "Yes",
            "undeveloped": "No",
            "closure_type": "long-term",
            "GlobalID": "{fixture-scc-parks-closed-areas-1}",
            "acres": 40.0,
            "last_edited_date": FIXTURE_DATE_MS,
        },
    ),
    "ma_dcr_park_alerts": (
        _point,
        {
            "OBJECTID": 1,
            "FACILITY_APPROVAL_STATUS": "Published",
            "FACILITY_ASSETCODE": "Fixture Loop Trail",
            "FACILITY_LAT": 42.1,
            "FACILITY_LONG": -71.7,
            "PARK_SITE": "Fixture State Park",
            "PAdv_StartDT": "2026-10-01",
            "PAdv_EndDT": "",
            "PAdv_HeaderText": "Fixture trail closed",
            "ParkAlertType": "Closure",
            "UNIQUEIDSHAREPOINT": "4614",
        },
    ),
    "ma_dcr_blue_hills_hunt_areas": (
        _polygon,
        {
            "OBJECTID": 1,
            "YrHuntArea": 2026,
            "Acres": 300.0,
            "AreaName": "Fixture Hunt Area",
            "GlobalID": "{fixture-ma-dcr-blue-hills-hunt-areas-1}",
        },
    ),
    "wa_dnr_wildfire_danger": (
        _polygon,
        {
            "OBJECTID": 1,
            "FIREDANGER_AREA_NM": "Fixture Area",
            "FIRE_DANGER_LEVEL_NM": "Moderate",
            "FIRE_DANGER_LEVEL_CD": 2,
            "BURN_BAN_LEVEL_CD": 1,
            "BURN_BAN_LEVEL_NM": "Rule burns banned",
            "NOTES_TXT": "Fixture note",
            "DNR_REGION_NAME": "Fixture Region",
        },
    ),
    "wa_dnr_ifpl": (
        _polygon,
        {
            "OBJECTID": 1,
            "ZONE": "Fixture 600",
            "FIRE_PRECAUTION_LEVEL": 1.0,
            "FIRE_PRECAUTION_EFFECTIVE_DT": FIXTURE_DATE_MS,
            "EDIT_DT": FIXTURE_DATE_MS,
            "NOTES_TXT": "Fixture note",
        },
    ),
    "wsprc_winter_rec_closures": (
        _line,
        {"OBJECTID": 1, "Name": "Fixture Sno-Park Trail", "GlobalID": "{fixture-wsprc-winter-rec-closures-1}"},
    ),
    "utah_ffsl_fire_restrictions": (
        _polygon,
        {
            "OBJECTID": 1,
            "OrderNum": "FIXCLO2601",
            "Agency": "1-FFSL",
            "EffectiveDate": "2026-07-01",
            "RescindedDate": None,
            "RestrictionType": "Stage 1",
            "Status": "Active",
            "Short_AreaDescription": "Fixture County",
            "Link": "https://ffsl.utah.gov/fixture.pdf",
        },
    ),
    "tdec_trail_closures": (
        _line,
        {
            "OBJECTID": 1,
            "TSP_UID": "TSP-0000",
            "TR_NAME": "Fixture Trail",
            "SEGMNT_NAM": "Fixture Section",
            "TRSTAT": "Temporarily Closed",
            "SEGLEN": 3.9,
            "GlobalID": "{fixture-tdec-trail-closures-1}",
            "EditDate": FIXTURE_DATE_MS,
            "Notes": "Fixture note",
        },
    ),
    "portland_parks_closed_assets": (
        _point,
        {
            "OBJECTID": 1,
            "Website": "https://www.portland.gov/parks/fixture",
            "Short_Desc": "Fixture closed",
            "Name": "Fixture Park Wading Pool",
            "PropertyID": 1,
        },
    ),
    "ctsst_public_hazards_closures": (
        _point,
        {
            "OBJECTID": 1,
            "Location": "Fixture Gorge",
            "Hazard": "Bridge out",
            "Info": "Fixture note",
            "Lat": 36.1,
            "Long": -84.9,
            "H_C": "C",
        },
    ),
    "alaska_trails_obstacles": (
        _point,
        {"OBJECTID": 1, "Name": "Fixture Creek", "Type": "BridgeNeeded(Impassable)", "Cost": "Fixture"},
    ),
    "alaska_trails_seward_obstacles": (
        _point,
        {"OBJECTID": 1, "Name": "Fixture Creek", "Type": "No Crossing", "Notes": "Fixture note"},
    ),
    "iata_trail_conditions": (
        _point,
        {
            "ObjectId": 1,
            "globalid": "{fixture-iata-trail-conditions-1}",
            "heading": "Fixture reroute",
            "segment_name": "Fixture Segment",
            "posted": "yes",
            "date_posted": FIXTURE_DATE_MS,
            "date_updated": FIXTURE_DATE_MS,
            "hyperlink": "https://www.iceagetrail.org/fixture",
        },
    ),
    "iata_hunting_closures": (
        _line,
        {
            "OBJECTID": 1,
            "GlobalID": "{fixture-iata-hunting-closures-1}",
            "Segment": "Fixture Segment",
            "GunDeer": "Closed",
            "OtherSeason": None,
            "OtherDesc": None,
            "Comments": "Fixture comment",
        },
    ),
    "iata_lands_hunting_regs": (
        _polygon,
        {"OBJECTID": 1, "County": "Fixture", "Hunting_Reg": "No hunting", "Display_Name": "Fixture Preserve", "Public_Access": 1},
    ),
    "fltc_temporary_notices": (
        _point,
        {
            "OBJECTID": 1,
            "tn_id": 2735.0,
            "Map": "B3",
            "Lat": 42.4,
            "Lon": -76.5,
            "Notice": "Fixture: trail closed",
            "Link": "https://fltmap.cc/alerts/0",
            "Status": "Active",
            "GlobalID": "{fixture-fltc-temporary-notices-1}",
            "EditDate_1": FIXTURE_DATE_MS,
        },
    ),
    "fltc_seasonal_closures": (
        _line,
        {"FID": 1, "Id": 1, "Descrip": "Fixture hunting closure", "Miles": 2.1, "Date_Modif": FIXTURE_DATE_MS, "Map": "M12"},
    ),
    "fltc_hunting_bypasses": (
        _line,
        {"FID": 1, "Id": 1, "Descrip": "Fixture bypass", "Miles": 1.4, "Date_Modif": FIXTURE_DATE_MS},
    ),
    "fta_fnst_closed_segments": (
        _line,
        {
            "FID": 1,
            "Trail_ID": "FX-1",
            "Trail_Name": "Fixture Segment",
            "Manager_Na": "Fixture Forest",
            "Open_Statu": "Closed",
            "Comments": "Fixture closure",
            "Last_Edi_1": FIXTURE_DATE_MS,
            "GlobalID": "{fixture-fta-fnst-closed-segments-1}",
        },
    ),
    "cdtc_alert_points": (
        _point,
        {
            "OBJECTID": 1,
            "Name": "Fixture Alert",
            "Type": "Closure",
            "Active": "Yes",
            "GlobalID": "{fixture-cdtc-alert-points-1}",
            "Milepost": 101.5,
            "Website2": "https://cdtcoalition.org/fixture",
        },
    ),
    "cdtc_alert_lines": (
        _line,
        {
            "OBJECTID": 1,
            "Name": "Fixture Alert",
            "Type": "Alert",
            "Active": "Yes",
            "GlobalID": "{fixture-cdtc-alert-lines-1}",
            "Website2": "https://cdtcoalition.org/fixture",
            "Length": 2.5,
        },
    ),
    "cdtc_area_closures": (
        _polygon,
        {"OBJECTID": 1, "Name": "Fixture Area Closure", "Date": None, "Active": "Yes", "Comments": "Fixture comment"},
    ),
    "cdtc_reroutes": (
        _line,
        {
            "OBJECTID": 1,
            "GlobalID": "{fixture-cdtc-reroutes-1}",
            "Name": "Fixture Reroute",
            "Active": "Yes",
            "last_edited_date": FIXTURE_DATE_MS,
            "Notes": "Fixture note",
            "Website2": "https://cdtcoalition.org/fixture",
        },
    ),
    "cdtc_national_defense_area": (_polygon, {"OBJECTID": 1, "Name": "National Defense Area"}),
    "ncta_trail_alerts": (
        _point,
        {
            "FID": 1,
            "Id": 1,
            "Date": FIXTURE_DATE_MS,
            "Location": "Fixture Road to Fixture Beach",
            "desc_": "Fixture alert text",
            "label": "Trail Alert: Fixture Road to Fixture Beach",
        },
    ),
    "ncta_ice_storm_impacts": (_polygon, {"OBJECTID": 1, "name": "Fixture impact area", "alert": "Fixture blowdown"}),
    "pcta_fires_and_closures": (
        _point,
        {
            "OBJECTID": 1,
            "Year": 2026,
            "Closure_Name": "Fixture Fire Closure",
            "PCTA_Region": "Fixture Region",
            "Type": "Wildfire",
            "Agency_Unit": "Fixture National Forest",
            "Miles_of_PCT_in_Closure_Area": 12.0,
            "GlobalID": "{fixture-pcta-fires-and-closures-1}",
        },
    ),
    "pcta_closure_lines": (
        _line,
        {
            "OBJECTID": 1,
            "Type": "Crossed out line",
            "CMS_ID": "fixtureCmsId0001",
            "Notes": "Fixture rock",
            "Label_Text": "PCT CLOSED",
        },
    ),
    "mohonk_deer_zones": (
        _polygon,
        {
            "OBJECTID": 1,
            "Zone_Number": 1,
            "Zone_Name": "Fixture Zone",
            "Area_Acres": 200.0,
            "GlobalID": "{fixture-mohonk-deer-zones-1}",
        },
    ),
    "nysdec_hab_reports": (
        _point,
        {
            "objectid": 1,
            "globalid": "{fixture-nysdec-hab-reports-1}",
            "date_time": FIXTURE_DATE_MS,
            "county": "Fixture",
            "data_provider": "Public",
            "water_name": "Fixture Lake",
            "extent_bloom": "Small localized",
            "HAB_STATUS": "Confirmed",
            "STATUS_DATE": FIXTURE_DATE_MS,
            "Weblink": "https://dec.ny.gov/fixture",
        },
    ),
    "nysdec_big_game_seasons": (
        _polygon,
        {
            "OBJECTID_1": 1,
            "UNIT": "3A",
            "earlybowdeer": "Oct. 1 - Nov. 20",
            "regseasondeer": "Nov. 21 - Dec. 13",
            "bearregular": "Nov. 21 - Dec. 13",
        },
    ),
    "oprhp_hunting_areas": (
        _polygon,
        {
            "OBJECTID": 1,
            "Unit": "Fixture State Park",
            "Facility": "Fixture",
            "Hunting": 2,
            "WMU": "3A",
            "Name": "Fixture Safety Zone",
            "Description": "Restricted Area/Safety Zone",
            "Website": "https://parks.ny.gov/fixture",
            "GlobalID": "{fixture-oprhp-hunting-areas-1}",
            "MasterAreaID": 1,
            "last_edited_date": FIXTURE_DATE_MS,
        },
    ),
    "njdep_park_status": (
        _point,
        {
            "OBJECTID": 1,
            "Region": "Fixture",
            "ParkName": "Fixture State Forest",
            "Status": "Closed",
            "Park_Hours": "Dawn to dusk",
            "Facility_URL": "https://dep.nj.gov/parksandforests/fixture",
            "GlobalID": "{fixture-njdep-park-status-1}",
            "EditDate": FIXTURE_DATE_MS,
        },
    ),
    "njdep_wma_restrictions": (
        _polygon,
        {
            "OBJECTID": 1,
            "WMA": "Fixture WMA",
            "TYPE": "Closed",
            "CATEGORY": "No Access",
            "DESCRIPT": "Fixture",
            "SDATE": FIXTURE_DATE_MS,
            "EDATE": FIXTURE_DATE_MS,
            "GLOBALID": "{fixture-njdep-wma-restrictions-1}",
        },
    ),
    "njdep_fire_danger": (
        _polygon,
        {
            "OBJECTID": 1,
            "DIVISION": "B",
            "DIVISION_LABEL": "Fixture Division",
            "FIRE_DANGER": "Low",
            "RECFIRE_RESTRICTION": "N",
            "BUILDUP": 10,
            "KBDI": 200,
            "GLOBALID": "{fixture-njdep-fire-danger-1}",
            "EditDate": FIXTURE_DATE_MS,
        },
    ),
    "njdep_rx_burn_notifications": (
        _point,
        {
            "OBJECTID": 1,
            "GIS_PARCEL": "Fixture Parcel",
            "MGMT_AGENCY": "Fixture",
            "FFS_DIVISION": "B",
            "COUNTY": "Fixture",
            "MUN": "Fixture Township",
            "NOTIFY_STATUS": "Notified",
            "BURN_DATE": FIXTURE_DATE_MS,
            "GLOBALID": "{fixture-njdep-rx-burn-notifications-1}",
        },
    ),
    "wi_dnr_park_closures": (
        _point,
        {
            "FID": 1,
            "Property": "Fixture State Forest",
            "CreationDate": FIXTURE_DATE_MS,
            "EditDate": FIXTURE_DATE_MS,
            "Closure_Name": "Fixture Trail Section Closed",
            "Reason": "Downed trees",
            "GlobalID": "{fixture-wi-dnr-park-closures-1}",
            "Impact": "High",
            "Active_Flag": "Yes",
            "End_Date_Indefinite_Flag": "No",
            "Exp_End_Date": FIXTURE_DATE_MS,
            "PDF_URL": "https://dnr.wisconsin.gov/fixture.pdf",
        },
    ),
    "wi_dnr_fire_danger": (
        _polygon,
        {
            "OBJECTID": 1,
            "COUNTY_NAME": "Fixture",
            "DANGER_RATING_CODE": 1.0,
            "DANGER_RATING_NAME": "Low",
            "NO_BURN_FLAG": "N",
            "PERMIT_RESTRICTIONS": "Fixture",
            "LAST_CHANGED_DATE": FIXTURE_DATE_MS,
        },
    ),
    "ct_deep_property_access_status": (
        _point,
        {
            "OBJECTID": 1,
            "DEP_ID": 1,
            "ACCESS_ID": 1,
            "PROPERTY": "Fixture State Park",
            "ACCSS_NAME": "Fixture Lot",
            "ACCSS_TOWN": "Fixture",
            "STATUS": "Closed",
            "LINK": "https://portal.ct.gov/fixture",
            "HIKING": "Y",
        },
    ),
    "wa_rco_trailhead_status": (
        _point,
        {
            "OBJECTID": 1,
            "trailhead_name": "Fixture Trailhead",
            "trailhead_status": "closed",
            "county": "Fixture",
            "management_area": "Fixture",
            "potable_water": "No",
            "information_url": "https://rco.wa.gov/fixture",
            "management_agency": "Fixture",
            "GlobalID": "{fixture-wa-rco-trailhead-status-1}",
        },
    ),
    "cotrex_seasonal_closures": (
        _polygon,
        {
            "OBJECTID_1": 1,
            "SC_ID": "FX_1",
            "Agency": "City of Fixture",
            "Designation": "Natural Area",
            "Name": "Fixture Seasonal Wildlife Closure",
            "Type": "Seasonal",
            "Closure_Period": "Dec 1 - Feb 28",
            "Start_Date": "2025-12-01",
            "End_Date": "2026-02-28",
            "Restricted_Use_Types": "All",
            "URL": "https://fixture.gov/closure",
        },
    ),
    "cpw_bear_conflict_areas": (
        _polygon,
        {
            "FID": 1,
            "ACTIVITYCO": "Fixture",
            "INPUT_DATE": FIXTURE_DATE_MS,
            "EDIT_DATE": FIXTURE_DATE_MS,
            "GlobalID": "{fixture-cpw-bear-conflict-areas-1}",
        },
    ),
    "cpw_lion_conflict_areas": (
        _polygon,
        {
            "FID": 1,
            "ACTIVITYCO": "Fixture",
            "INPUT_DATE": FIXTURE_DATE_MS,
            "EDIT_DATE": FIXTURE_DATE_MS,
            "GlobalID": "{fixture-cpw-lion-conflict-areas-1}",
        },
    ),
}


def notice_layers_fixtures() -> dict[str, dict]:
    """One external/<key>.geojson per NOTICE_LAYERS entry, each holding its one row."""
    return {f"external/{key}.geojson": _features([row], geometry) for key, (geometry, row) in NOTICE_LAYERS.items()}


# --- trail_lines, the network half (#1793, stage 3) --------------------------
#
# The network's dbt models (pipeline/dbt/models/intermediate/trail_lines/
# int_trail_lines__network_*) and today's export_nearby_trails.py both read
# these layers, and parity.py compares the two files they write. That needs
# fixtures today's exporter accepts: on the files above it stops at its first
# registry check, because usfs_trails carries no `terra_motorized` and no park
# polygon is named for the drives' boundary.

#: The two boundaries sources.json's nyc_park_drives entry names in
#: `boundary_names`. Central Park's box holds the drives fixture's EAST DR line
#: (`_line(0)`), so that row is kept; Prospect Park's sits away from WEST DR
#: (`_line(1)`), so that row is dropped as outside the boundary. Boxes, not
#: NYC: the same synthetic-geometry convention as `_polygon`.
NETWORK_PARK_BOUNDARIES = {
    "Central Park": [[-74.001, 40.999], [-73.999, 40.999], [-73.999, 41.006], [-74.001, 41.006], [-74.001, 40.999]],
    "Prospect Park": [[-73.95, 40.95], [-73.94, 40.95], [-73.94, 40.96], [-73.95, 40.96], [-73.95, 40.95]],
}


def _box(west: float, south: float, east: float, north: float) -> list[list[float]]:
    """A closed rectangular ring, counter-clockwise from its south-west corner."""
    return [[west, south], [east, south], [east, north], [west, north], [west, south]]


#: NYS Parks closed areas over the network's fixture lines, one per branch of
#: export_nearby_trails.py's apply_area_closures() (#964), appended after the
#: closures layer's own triangle, which touches the lon -74.0 lines at one
#: corner and closes nothing. In file order, each (reason, ring):
#: - across the two lon -73.97 lines (lat 41.03 to 41.035) from lat 41.032,
#:   so each splits into a closed and an open section;
#: - around the five lon -73.98 lines (41.02 to 41.025), wholly closing them
#:   and stopping short of the A.T. spur ending at (-73.9805, 41.0199);
#: - two over the long-term closed Fixture Closed Ridge Trail (lon -74.2,
#:   41.2 to 41.25), 0.005 and 0.02 degrees of it: two closed pieces, three
#:   open ones still long-term closed, and the reason of the second, the
#:   larger overlap;
#: - two nested around the whole 1777 East Trail (lon -74.25, 41.2 to
#:   41.21), which ties them, so the first in the file gives the reason;
#: - one whose west edge is the lon -71.3 USFS line (44.2 to 44.205), with a
#:   blank reason: a trail on the boundary is inside (the function's own
#:   docstring), and a section with no reason publishes none.
NETWORK_CLOSED_AREAS = [
    ("Fixture Closure: bridge washed out", _box(-73.975, 41.032, -73.965, 41.04)),
    ("Fixture Closure: rockfall", _box(-73.982, 41.01995, -73.978, 41.0255)),
    ("Fixture Closure: the short stretch", _box(-74.205, 41.205, -74.195, 41.21)),
    ("Fixture Closure: the long stretch", _box(-74.205, 41.22, -74.195, 41.24)),
    ("Fixture Closure: the outer area", _box(-74.258, 41.195, -74.242, 41.215)),
    ("Fixture Closure: the inner area", _box(-74.254, 41.198, -74.246, 41.212)),
    ("   ", _box(-71.3, 44.199, -71.296, 44.206)),
]


def _north(lon: float, lat: float, degrees: float) -> dict:
    """A due-north LineString `degrees` of latitude long (0.3 is about 20.7 mi)."""
    return {"type": "LineString", "coordinates": [[lon, lat], [lon, round(lat + degrees, 6)]]}


#: Five metres and ten metres of latitude, near enough at 41.6 degrees north
#: (111,320 m a degree); every graph assertion measures the built graph
#: rather than trusting these.
_FIVE_M = 0.0000449
_TEN_M = 0.0000898


def _line_geometry(*coordinates) -> dict:
    return {"type": "LineString", "coordinates": [list(point) for point in coordinates]}


#: OPRHP lines west of everything else (around -74.6, 41.6), one per branch
#: of build_trail_graph.py's noding that the stacked fixture lines never
#: reach, as (GlobalID, name, Alt_Name, Blaze, Status, Foot, geometry) rows
#: for _network_rows' OPRHP list:
#: - a main line with a bump, so other lines' envelopes meet it;
#: - a stub ending 5 m short of it (joined within the 8 m tolerance, which
#:   cuts the main line and welds the two) and one ending 10 m short (left
#:   open);
#: - a line beside it, 28 m off at its nearest end, its envelope meeting the
#:   main line's (compared, never welded);
#: - a MultiLineString whose first part crosses the main line and whose
#:   second stands alone (one routable line per part);
#: - a stub whose end lies on the main line (a touch is a crossing);
#: - a 0.3 m line, a loop shorter than the node grid (never an edge);
#: - two lines whose ends stop 0.3 m apart, the second doubling back
#:   south-west under the first (two welds, and one node);
#: - a stub ending 5 m short of a straight east-west line, whose envelope
#:   meets the stub's only because EPSG:5070 tilts the line (joined);
#: - two lines in line, east-west, the second starting 5 m east of the
#:   first's end: their envelopes do not meet, so node_lines() never
#:   compares them and the 5 m gap stays open (two nodes, no weld).
NETWORK_GRAPH_LINES = [
    (
        "{00000000-0000-4000-8000-000000000421}",
        "Fixture Graph Main",
        None,
        "Red",
        "Open",
        "Y",
        _line_geometry((-74.60, 41.60), (-74.59, 41.6005), (-74.58, 41.60)),
    ),
    (
        "{00000000-0000-4000-8000-000000000422}",
        "Fixture Graph Near Stub",
        None,
        "Blue",
        "Open",
        "Y",
        _line_geometry((-74.585, 41.590), (-74.585, round(41.60025 - _FIVE_M, 7))),
    ),
    (
        "{00000000-0000-4000-8000-000000000423}",
        "Fixture Graph Far Stub",
        None,
        "Blue",
        "Open",
        "Y",
        _line_geometry((-74.583, 41.590), (-74.583, round(41.60015 - _TEN_M, 7))),
    ),
    (
        "{00000000-0000-4000-8000-000000000424}",
        "Fixture Graph Beside",
        None,
        "Yellow",
        "Open",
        "Y",
        _line_geometry((-74.597, 41.6007), (-74.59, 41.6008), (-74.583, 41.6004)),
    ),
    (
        "{00000000-0000-4000-8000-000000000425}",
        "Fixture Graph Two Parts",
        None,
        "Green",
        "Open",
        "Y",
        {
            "type": "MultiLineString",
            "coordinates": [[[-74.595, 41.599], [-74.595, 41.6015]], [[-74.62, 41.61], [-74.61, 41.61]]],
        },
    ),
    (
        "{00000000-0000-4000-8000-000000000426}",
        "Fixture Graph Touching Stub",
        None,
        "Orange",
        "Open",
        "Y",
        _line_geometry((-74.59, 41.595), (-74.59, 41.6005)),
    ),
    (
        "{00000000-0000-4000-8000-000000000427}",
        "Fixture Graph Speck",
        None,
        "Red",
        "Open",
        "Y",
        _line_geometry((-74.63, 41.62), (-74.63, 41.6200027)),
    ),
    (
        "{00000000-0000-4000-8000-000000000428}",
        "Fixture Graph West Half",
        None,
        "Red",
        "Open",
        "Y",
        _line_geometry((-74.64, 41.62), (-74.636, 41.62)),
    ),
    (
        "{00000000-0000-4000-8000-000000000429}",
        "Fixture Graph East Half",
        None,
        "Red",
        "Open",
        "Y",
        _line_geometry((-74.6359964, 41.62), (-74.6362, 41.6195)),
    ),
    (
        "{00000000-0000-4000-8000-000000000430}",
        "Fixture Graph Straight",
        None,
        "White",
        "Open",
        "Y",
        _line_geometry((-74.65, 41.63), (-74.64, 41.63)),
    ),
    (
        "{00000000-0000-4000-8000-000000000431}",
        "Fixture Graph Stub Below The Straight",
        None,
        "White",
        "Open",
        "Y",
        _line_geometry((-74.645, 41.62), (-74.645, round(41.63 - _FIVE_M, 7))),
    ),
    (
        "{00000000-0000-4000-8000-000000000432}",
        "Fixture Graph In Line West",
        None,
        "Purple",
        "Open",
        "Y",
        _line_geometry((-74.66, 41.64), (-74.656, 41.64)),
    ),
    (
        "{00000000-0000-4000-8000-000000000433}",
        "Fixture Graph In Line East",
        None,
        "Purple",
        "Open",
        "Y",
        _line_geometry((-74.65594, 41.64), (-74.652, 41.6401)),
    ),
]


def _network_rows() -> dict[str, list[dict]]:
    """Rows added to two network layers so parity reaches the rules the builders
    above never exercise, each named for the rule it is there for.

    nynjtc_long_path gains three ~20.7 mi sections chained end to end, about 62
    mi of one Long Path: the overview's through-route rule (TL12, 50 mi). OPRHP
    gains the statuses and names its filters decide on: a `Closed` trail long
    enough to clear the overview's 1-pixel floor (the safety row: it ships
    closed, closure_kind long_term), a `Proposed` one (dropped), a `Foot` 'N'
    one (dropped), its own copies of the two owned routes (suppressed, TL11),
    and a trail the A.T. runs along under `Alt_Name` (kept)."""
    oprhp = {
        "Unit": "Palisades",
        "Surface": "Native",
        "Public_": "Y",
        "Bike": "N",
        "Horse": "N",
        "XC": "N",
        "SS": "N",
        "Snowmb": "N",
        "Map_Blaze": "Red",
        "Miles": 3.4,
    }
    rows = [
        (
            "{00000000-0000-4000-8000-000000000411}",
            "Fixture Closed Ridge Trail",
            None,
            "Red",
            "Closed",
            "Y",
            _north(-74.2, 41.2, 0.05),
        ),
        (
            "{00000000-0000-4000-8000-000000000412}",
            "Fixture Proposed Connector",
            None,
            "Red",
            "Proposed",
            "Y",
            _north(-74.21, 41.2, 0.01),
        ),
        ("{00000000-0000-4000-8000-000000000413}", "Fixture Bike Path", None, "Blue", "Open", "N", _north(-74.22, 41.2, 0.01)),
        ("{00000000-0000-4000-8000-000000000414}", "Long Path", None, "Aqua", "Open", "Y", _north(-74.23, 41.2, 0.01)),
        ("{00000000-0000-4000-8000-000000000415}", "Appalachian Trail", None, "White", "Open", "Y", _north(-74.24, 41.2, 0.01)),
        (
            "{00000000-0000-4000-8000-000000000416}",
            "1777 East Trail",
            "Appalachian Trail",
            "Red",
            "Open",
            "Y",
            _north(-74.25, 41.2, 0.01),
        ),
        *NETWORK_GRAPH_LINES,
    ]
    long_path = {"Trail_Name": "Long Path", "Blaze": "aqua", "Maintainer": "NYNJTC", "Source": "NYNJTC", "Comments": None}
    return {
        "external/oprhp_trails.geojson": [
            {
                "type": "Feature",
                "properties": {
                    **oprhp,
                    "GlobalID": gid,
                    "Name": name,
                    "Alt_Name": alt,
                    "Blaze": colour,
                    "Status": status,
                    "Foot": foot,
                },
                "geometry": geometry,
            }
            for gid, name, alt, colour, status, foot, geometry in rows
        ],
        "external/nynjtc_long_path.geojson": [
            {
                "type": "Feature",
                "properties": {
                    **long_path,
                    "Mileage": 20.7,
                    "LP_Section": str(section),
                    "GuideURL": f"https://example.invalid/lp/{section}",
                },
                "geometry": _north(-74.3, round(41.5 + 0.3 * n, 6), 0.3),
            }
            for n, section in enumerate((3, 4, 5))
        ],
    }


def _trail_lines_network_fixtures(files: dict[str, dict | str | bytes]) -> dict[str, dict | str | bytes]:
    """`files` with the rows `_network_rows` adds, and three things the live
    layers have and these fixtures lacked.

    - usfs_trails' `terra_motorized`, the column the registry's
      `excluded_when` reads (#1711, measured live 2026-09-28: 'N' 45,151 TERRA
      rows, 'Y' 23,195, 'N/A' 9,810). The TERRA rows read 'N', except GREAT
      GULF, which reads 'N/A' and ships, and one CRAWFORD PATH row, which
      reads 'Y' and is dropped as motorized. Without the column
      export_nearby_trails.py refuses the layer as renamed (#1646), and so
      does int_trail_lines__network_sources' test.
    - nyc_park_polygons' two boundaries, NETWORK_PARK_BOUNDARIES. Without a
      polygon of either name the exporter refuses nyc_park_drives, because
      every row would be dropped.
    - oprhp_trail_closures' NETWORK_CLOSED_AREAS, after its own triangle, so
      parity reaches every branch of apply_area_closures().
    - each network line feature's own `id`, which the live servers write and
      the builders above leave off: an ArcGIS layer's is its OBJECTID, where
      the fixture carries one, and a Socrata layer's is the row id
      lib/socrata.py promotes onto the feature, `row-<n>` in the order
      extract/_fixtures.py's adapter numbers them. lib/feature_id.py falls
      back to that `id` where a layer has no `GlobalID`, so without it every
      such row's published id would be positional. That ArcGIS's GeoJSON
      `id` is the OBJECTID is Reasoned from the REST API and @unvalidated
      here; one live fetch comparing the two settles it.

    The extract lands none of these ids (its rows are a feature's properties
    and geometry), so the warehouse is unchanged by them.
    """
    registry = json.loads((Path(__file__).parent / "sources.json").read_text(encoding="utf-8"))
    kinds = {entry["key"]: entry.get("kind") for entry in registry["sources"]}
    out = dict(files)

    for name, added in _network_rows().items():
        out[name]["features"] += added

    for feature in out["external/usfs_trails.geojson"]["features"]:
        properties = feature["properties"]
        if properties.get("trail_type") != "TERRA":
            continue
        if properties.get("trail_name") == "FIXTURE GREAT GULF":
            properties["terra_motorized"] = "N/A"
        elif properties.get("national_trail_designation") == 2:
            properties["terra_motorized"] = "Y"
        else:
            properties["terra_motorized"] = "N"

    out["external/nyc_park_polygons.geojson"]["features"] += [
        {
            "type": "Feature",
            "properties": {"signname": name, "gispropnum": f"FIXTURE-{index}"},
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        }
        for index, (name, ring) in enumerate(NETWORK_PARK_BOUNDARIES.items())
    ]

    out["external/oprhp_trail_closures.geojson"]["features"] += [
        {
            "type": "Feature",
            "properties": {"Name": reason, "Descript": "Fixture State Park"},
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        }
        for reason, ring in NETWORK_CLOSED_AREAS
    ]

    mapping = json.loads((Path(__file__).parent / "reference" / "blaze_mapping.json").read_text(encoding="utf-8"))["sources"]
    entries = {entry["key"]: entry for entry in registry["sources"]}
    for name in files:
        key = Path(name).stem
        entry = entries.get(key, {})
        if not name.startswith("external/") or entry.get("kind") not in ("external_arcgis_layer", "socrata_geojson_layer"):
            continue
        if "blaze_field" not in entry and "blaze_default" not in entry:
            continue
        for index, feature in enumerate(out[name]["features"]):
            properties = feature.setdefault("properties", {})
            if kinds[key] == "socrata_geojson_layer":
                feature["id"] = f"row-{index}"
            elif properties.get("OBJECTID") is not None:
                feature["id"] = properties["OBJECTID"]
            # A field the registry declares and no builder above writes (#1778's
            # builder writes the name column alone, and two of its layers have
            # since declared a blaze field). The exporter refuses a layer missing
            # a declared column, so each gets one: the blaze field the first
            # value its reviewed table maps, then null; a foot field the first
            # value it allows; a status field 'Open'; an exclusion field null.
            if entry.get("blaze_field") and entry["blaze_field"] not in properties:
                table = sorted((mapping.get(key) or {}).get("mapped") or {})
                properties[entry["blaze_field"]] = table[0] if table and index == 0 else None
            if entry.get("foot_field") and entry["foot_field"] not in properties:
                properties[entry["foot_field"]] = (entry.get("foot_allowed") or ["Y"])[0]
            if entry.get("status_field") and entry["status_field"] not in properties:
                properties[entry["status_field"]] = "Open"
            for field in entry.get("excluded_when") or {}:
                properties.setdefault(field, None)
    return out


def _side_trail(name: str, coordinates, properties: dict, geometry_type: str = "LineString") -> dict:
    """One side_trails feature, its GlobalID spelled as `_atc_layer` spells the others'."""
    return {
        "type": "Feature",
        "properties": {"GlobalID": name.lower().replace(" ", "-"), "Name": name, "Status": "Existing", **properties},
        "geometry": None if coordinates is None else {"type": geometry_type, "coordinates": coordinates},
    }


# Side trails beside the fixture centerline, which runs north at lon -74.0
# (lat 41.0 to 41.005) and -73.99 (41.01 to 41.015), each reaching a branch of
# the trail_lines family's A.T. rules that the two `_atc_layer` side trails,
# both coded "Side Trail" and "Blue" (neither a domain code), never reach.
# Distances are lib/spurs.py's equirectangular metres at 41 degrees north.
TRAIL_LINES_AT_SIDE_TRAILS = [
    # A spur by its code, blazed by code 1: its first end 14 m from the
    # centerline's vertex at (-73.99, 41.015) is the junction, its far end
    # 43 m from the fixture's third shelter, (-73.98, 41.02), which spurs.json
    # names as its destination.
    _side_trail(
        "Spur To Shelter",
        [[-73.9901, 41.0151], [-73.985, 41.018], [-73.9805, 41.0199]],
        {"Type": "3", "Blaze": "1", "Length_Ft": 3456.5},
    ),
    # A spur by its domain name, blazed by a word the domain does not hold:
    # decoded to "Unknown", with nothing within 150 m of its far end.
    _side_trail(
        "Viewpoint Spur",
        [[-74.0001, 41.0049], [-74.002, 41.0055], [-74.004, 41.006]],
        {"Type": "Spur (eg View, Camp)", "Blaze": "Blue", "Length_Ft": 1200.25},
    ),
    # An access trail in two parts and no blaze at all.
    _side_trail(
        "Access Trail",
        [[[-73.9995, 41.001], [-73.997, 41.001]], [[-73.997, 41.001], [-73.995, 41.0012]]],
        {"Type": "0", "Blaze": None, "Length_Ft": 800.0},
        geometry_type="MultiLineString",
    ),
    # The misspelt literal 60 live side trails carry for code 2, blazed white.
    _side_trail(
        "Significant Non-Blaze Trail",
        [[-73.9905, 41.0105], [-73.9895, 41.012]],
        {"Type": "Signficant Non-Blaze", "Blaze": "2", "Length_Ft": 600.0},
    ),
    # Coded a spur, with both ends within lib/spurs.py's ON_TRAIL_M 25 m of the
    # centerline: an alternate route, so no junction and no destination.
    _side_trail(
        "Gold Loop",
        [[-73.99, 41.0101], [-73.9895, 41.0125], [-73.99, 41.0149]],
        {"Type": "3", "Blaze": "Gold", "Length_Ft": 1700.0},
    ),
    # More than the corridor's 30 miles from the centerline: clipped out.
    _side_trail(
        "Far Side Trail",
        [[-80.0, 35.0], [-80.0, 35.01]],
        {"Type": "0", "Blaze": "1", "Length_Ft": 3600.0},
    ),
    # No geometry: skipped with a warning, never published.
    _side_trail("Trail With No Line", None, {"Type": "1", "Blaze": "3", "Length_Ft": None}),
    # Two vertices 1.4 cm apart, which six decimals would put on one point:
    # the never-degenerate rule keeps full precision.
    _side_trail(
        "Short Stub",
        [[-73.9950001, 41.0040001], [-73.9950002, 41.0040002]],
        {"Type": "4", "Blaze": "5", "Length_Ft": 0.1},
    ),
]

# Club polygons for lib/club_sections.py's rules (TL24-TL26), which the base
# fixture's TTC0 and TTC1 polygons reach only in part: one naming the first
# centerline segment's club, TTC, padded with whitespace and with no
# TRAIL_CLUB, so the name falls back to the acronym; and one whose acronym is
# a digit code, never a club.
TRAIL_LINES_AT_CLUB_POLYGONS = [
    {
        "type": "Feature",
        "properties": {"GlobalID": f"club-section-{key}", "TRAIL_CLUB": club, "ACROYNM": acronym, "REGION": "Mid-Atlantic"},
        "geometry": {"type": "Polygon", "coordinates": [[[-74.0, 41.0], [-73.995, 41.0], [-73.995, 41.005], [-74.0, 41.0]]]},
    }
    for key, club, acronym in (("ttc", "", " TTC "), ("coded", "11", "11"))
]


def _trail_lines_at_fixtures(files: dict[str, dict | str | bytes]) -> dict[str, dict | str | bytes]:
    """`files` with the A.T. line layers carrying what the live ones carry.

    - Every centerline and side trail feature gets an OBJECTID, served as the
      feature's own GeoJSON `id` too, as ArcGIS serves them: on the live layers
      the `id` equals the OBJECTID on 3,025 of 3,025 centerline features and
      1,197 of 1,197 side trails (measured 2026-10-02). The staging key falls
      back to the OBJECTID where a row has no GlobalID, so the column has to
      land.
    - TRAIL_LINES_AT_SIDE_TRAILS joins the side trails, so CI's parity run of
      export_trails.py and export_spurs.py against the dbt writers reaches
      spurs, coded blazes and the clip. Only side trails are added: the
      centerline and the half-mile markers, which every family's mile axis
      reads, are left as they are.
    - For CI's parity run of export_club_sections.py, the second centerline
      segment's Acronym becomes " TTC1 ", a club change the strip has to
      take, which the TTC1 polygon spells; and TRAIL_LINES_AT_CLUB_POLYGONS
      joins the polygons. Only the Acronym changes, which nothing but the
      club sections reads, so the mile axis is untouched.
    """
    out = dict(files)
    for name, added in (("centerline.geojson", []), ("side_trails.geojson", TRAIL_LINES_AT_SIDE_TRAILS)):
        collection = out[name]
        collection["features"] += [json.loads(json.dumps(feature)) for feature in added]
        for index, feature in enumerate(collection["features"]):
            feature["properties"]["OBJECTID"] = index + 1
            feature["id"] = index + 1
        if name == "centerline.geojson":
            collection["features"][1]["properties"]["Acronym"] = " TTC1 "
    out["trail_club_sections.geojson"]["features"] += [
        json.loads(json.dumps(feature)) for feature in TRAIL_LINES_AT_CLUB_POLYGONS
    ]
    return out


# --- suggested_hikes, NYNJTC's Hike Finder export -----------------------------
#
# The suggested_hikes family's models (pipeline/dbt/models/**/suggested_hikes/,
# stage 3 of #1793 — Rebuild the data platform as dlt → dbt: seven contracted
# marts, a monthly refresh, published docs, and lighter phone downloads)
# read raw_nynjtc__nynjtc_hike_finder, which the extract's PublishedHikes
# resource lands from a listing, one page per hike and a GPX per routed hike.
# extract/_fixtures.py serves the files below at those three URLs, so every
# row is the real parse's (lib/hikefinder.py's parse_hike, as_cache_entry and
# parse_gpx). The pages are in the shape tests/test_lib_hikefinder.py builds,
# the one measured against the live export on 2026-09-15: a `<h1>`, the twelve
# `<strong>Label:</strong>` fields, and a `card` per free-text section.
#
# Each hike is here for a rule, named beside it. Ids 1, 4 and 11 have a
# confirmed photograph in the real reference/nynjtc_hike_photos.json, which
# fixture mode loads as it is, so the photo join (SH09) has rows to match and
# rows to miss. The coordinates sit beside the fixture Long Path
# (`_network_rows`, a due-north line at longitude -74.3), so a route can form
# once the trail_network family's edges are built from the fixture lines.
HIKEFINDER_DIR = "hikefinder"

#: (id, title, labelled fields, cards, track): `track` is a list of
#: (lat, lon, ele_m) points for a page with a published GPX, "" for a page
#: that links a GPX holding no point, and None for a page with no GPX at all.
_HIKEFINDER_HIKES = (
    (
        1,
        "Fixture Long Path Ramble",
        # A generated route (no GPX), a confirmed photograph, an author, two tags.
        {
            "Length": "4.8 miles",
            "Difficulty": '<span class="badge bg-info">Moderate</span>',
            "Estimated Time": "3.0 hours",
            "Route Type": "Circuit",
            "Dogs": "Allowed on leash",
            "Park": "Harriman State Park",
            "Region": "Lower Hudson",
            "Author": "Daniel Chazin",
            "GPS Coordinates": '41.600000,\n -74.300500 <br><small class="text-muted">(Parking location)</small>',
            "Features": '<span class="badge bg-secondary me-1 mb-1">Views</span>'
            '<span class="badge bg-secondary me-1 mb-1">Historic feature</span>',
            "Publish Date": "July 11, 2013",
            "Last Updated": "N/A",
        },
        {
            "Summary": "<p>A ramble along the Long Path.</p>",
            "Directions to Trailhead": '<div class="hike-description">Park in the gravel area.</div>',
            "Description": "<p>Follow the aqua-blazed Long Path north.</p>"
            "<p>Turn left onto the red-blazed Fixture Ridge Trail and return on the Long Path.</p>",
            "Public Transportation": "<p>Short Line buses stop at the gate.</p>",
        },
        None,
    ),
    (
        4,
        "Fixture Long Path Out and Back",
        # A published track that closes on itself, the one difficulty with no
        # slug of its own (SH07), and no author, so no publication block (SH10).
        {
            "Length": "2.1 miles",
            "Difficulty": '<span class="badge bg-info">Very Strenuous</span>',
            "Estimated Time": "1.5 hours",
            "Route Type": "Out and back",
            "Dogs": "Not allowed",
            "Park": "Harriman State Park",
            "Region": "Lower Hudson",
            "Author": "N/A",
            "GPS Coordinates": '41.620000,\n -74.300100 <br><small class="text-muted">(Parking location)</small>',
            "Features": '<span class="badge bg-secondary me-1 mb-1">Waterfall</span>',
            "Publish Date": "May 2, 2015",
            "Last Updated": "March 3, 2024",
        },
        {
            "Summary": "<p>North to the falls and back.</p>",
            "Directions to Trailhead": '<div class="hike-description">Park at the trailhead lot.</div>',
            "Description": "<p>Follow the aqua-blazed Long Path north to the falls, then return the same way.</p>",
        },
        [(round(41.62 + 0.001 * step, 6), -74.3, 300.0 + 0.25 * step) for step in range(16)]
        + [(round(41.635 - 0.001 * step, 6), -74.3, 303.75 - 0.25 * step) for step in range(1, 16)],
    ),
    (
        7,
        "Fixture Long Path Shuttle",
        # An open walk (Shuttle), an author, no tags, and a page revised since.
        {
            "Length": "6.0 miles",
            "Difficulty": '<span class="badge bg-info">Easy To Moderate</span>',
            "Estimated Time": "3.5 hours",
            "Route Type": "Shuttle",
            "Dogs": "Allowed on leash",
            "Park": "Sterling Forest State Park",
            "Region": "Lower Hudson",
            "Author": "Jane Daniels",
            "GPS Coordinates": '41.700000,\n -74.300200 <br><small class="text-muted">(Parking location)</small>',
            "Features": "",
            "Publish Date": "June 1, 2019",
            "Last Updated": "August 9, 2025",
        },
        {
            "Summary": "<p>One way along the Long Path, with a car at each end.</p>",
            "Directions to Trailhead": '<div class="hike-description">Leave a car at each end.</div>',
            "Description": "<p>Follow the aqua-blazed Long Path north to the second road crossing.</p>",
        },
        None,
    ),
    (
        9,
        "Fixture Hike Off The Map",
        # A coordinate outside the NYNJTC box, refused by the parse (SH01), so
        # the page lands with no start; a difficulty with no slot (SH07); no
        # stated length.
        {
            "Length": "N/A",
            "Difficulty": '<span class="badge bg-info">Extreme</span>',
            "Estimated Time": "N/A",
            "Route Type": "Lollipop",
            "Dogs": "N/A",
            "Park": "N/A",
            "Region": "N/A",
            "Author": "Daniel Chazin",
            "GPS Coordinates": '0.000000,\n 0.000000 <br><small class="text-muted">(Parking location)</small>',
            "Features": '<span class="badge bg-secondary me-1 mb-1">Cliffs</span>',
            "Publish Date": "N/A",
            "Last Updated": "N/A",
        },
        {"Description": "<p>Follow the Long Path to the cliffs.</p>"},
        None,
    ),
    (
        11,
        "Fixture Empty Track",
        # A page that links a GPX holding no point: the extract lands its gpx
        # as null, so its published route is refused as fewer than two points.
        {
            "Length": "3.0 miles",
            "Difficulty": '<span class="badge bg-info">Easy</span>',
            "Estimated Time": "2.0 hours",
            "Route Type": "Circuit",
            "Dogs": "Allowed on leash",
            "Park": "Harriman State Park",
            "Region": "Lower Hudson",
            "Author": "Daniel Chazin",
            "GPS Coordinates": '41.650000,\n -74.300300 <br><small class="text-muted">(Parking location)</small>',
            "Features": '<span class="badge bg-secondary me-1 mb-1">Woods</span>',
            "Publish Date": "April 4, 2016",
            "Last Updated": "N/A",
        },
        {"Description": "<p>A circuit on the Long Path.</p>"},
        "",
    ),
    (
        12,
        "Fixture No Route Type",
        # No Route Type and no Description card: two of hike_problems()'s
        # review notes (SH02), on a hike with a coordinate.
        {
            "Length": "3.5 miles",
            "Difficulty": '<span class="badge bg-info">Strenuous</span>',
            "Estimated Time": "2.5 hours",
            "Route Type": "N/A",
            "Dogs": "Allowed on leash",
            "Park": "Bear Mountain State Park",
            "Region": "Lower Hudson",
            "Author": "Daniel Chazin",
            "GPS Coordinates": '41.750000,\n -74.300100 <br><small class="text-muted">(Parking location)</small>',
            "Features": '<span class="badge bg-secondary me-1 mb-1">Views</span>',
            "Publish Date": "October 10, 2020",
            "Last Updated": "N/A",
        },
        {"Summary": "<p>A climb to a view.</p>"},
        None,
    ),
)


def _hikefinder_page(hike_id: int, title: str, fields: dict, cards: dict, track) -> str:
    """One Hike Finder page in the export's shape (tests/test_lib_hikefinder.py's `page`)."""
    rows = "".join(f'<div class="col-md-6"><strong>{label}:</strong> {value}</div>' for label, value in fields.items())
    blocks = "".join(
        f'<div class="card"><div class="card-header"><h2 class="h6">{name}</h2></div><div class="card-body">{body}</div></div>'
        for name, body in cards.items()
    )
    download = f'<a href="download_gpx.php?id={hike_id}">Download GPX</a>' if track is not None else ""
    return (
        f"<html><body><h1 class='display-5'>{title}</h1>"
        f'<div class="card"><div class="card-header"><h2 class="h5">Hike Information</h2></div>'
        f'<div class="card-body"><div class="row mb-3">{rows}</div></div></div>'
        f"{blocks}{download}"
        "<script>const routeCoordinates = [[1,2]];</script></body></html>"
    )


def _hikefinder_gpx(title: str, points) -> str:
    """A GPX as gpx.studio writes one: a named track, each point with an `<ele>` in metres."""
    trkpts = "".join(f'<trkpt lat="{lat}" lon="{lon}"><ele>{ele}</ele></trkpt>' for lat, lon, ele in points)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="https://gpx.studio">'
        f"<metadata><name>{title}</name></metadata><trk><name>{title}</name><trkseg>{trkpts}</trkseg></trk></gpx>"
    )


def suggested_hikes_fixtures() -> dict[str, str]:
    """The suggested_hikes family's fixture files, under hikefinder/: the listing, each page, each GPX.

    extract/_fixtures.py serves `hikes.html` at the export's `hikes.php`,
    `hike-<id>.html` at `hike.php?id=<id>` and `track-<id>.gpx` at
    `download_gpx.php?id=<id>`.
    """
    links = "".join(f'<a href="hike.php?id={hike_id}">{title}</a>' for hike_id, title, _, _, _ in _HIKEFINDER_HIKES)
    files = {f"{HIKEFINDER_DIR}/hikes.html": f"<html><body>Results ({len(_HIKEFINDER_HIKES)} hikes found) {links}</body></html>"}
    for hike_id, title, fields, cards, track in _HIKEFINDER_HIKES:
        files[f"{HIKEFINDER_DIR}/hike-{hike_id}.html"] = _hikefinder_page(hike_id, title, fields, cards, track)
        if track is not None:
            files[f"{HIKEFINDER_DIR}/track-{hike_id}.gpx"] = _hikefinder_gpx(title, track or [])
    return files


# --- places (#1793, stage 3) -------------------------------------------------
#
# The places family's dbt models (pipeline/dbt/models/intermediate/places/) and
# today's export_places.py both read NYS OPRHP's park polygons, and parity.py
# compares the two places.json files they write.


def _park(global_id: str, name, unit, category, ring) -> dict:
    """One OPRHP park polygon, in the four fields export_places.py reads."""
    properties = {"GlobalID": global_id, "Name": name, "MasterAreaID": unit, "Category": category}
    geometry = {"type": "Polygon", "coordinates": [ring]} if ring else None
    return {"type": "Feature", "properties": properties, "geometry": geometry}


def _places_fixtures(files: dict[str, dict | str | bytes]) -> dict[str, dict | str | bytes]:
    """`files` with OPRHP's park layer given the four fields export_places.py reads, one polygon per rule.

    The fields are the ones the layer's sources.json entry declares
    (`name_field` Name, `id_field` GlobalID, `unit_field` MasterAreaID) plus
    `Category`, which export_places.py reads as PARK_CATEGORY_FIELD. All four
    were read off the live layer on 2026-10-02 (858 polygons, last edited
    2026-08-21): GlobalID unique and never null, MasterAreaID a small integer
    null on one row, Category one of ten words. That makes
    `_oprhp_park_polygons_layer()` above, written before the entry declared
    any field, the layer's shape no longer, and this replaces its output.

    Each polygon is there for one rule of load_parks() (PL02, PL03), and the
    boxes sit on the network fixture's lines so the measured miles are not all
    zero:
    - unit 127, "Fixture Harriman", two parcels: one over the stacked network
      lines at -74.0, one over the Closed Ridge Trail at -74.2 (one row per
      unit, the miles summed);
    - a parcel with no MasterAreaID named "Fixture Harriman" over the Long
      Path at -74.3, which joins unit 127, the one unit wearing its name;
    - unit 270, two of its three parcels "Fixture Robert Moses" and one
      "Captree/Fixture Robert Moses" (the majority name), away from any line
      (a measured 0.0);
    - unit 271, also "Fixture Robert Moses" (two parks sharing a name stay
      two rows), and a parcel with no unit by that name, which stands alone
      under its GlobalID because two units wear the name;
    - "Fixture Lone Preserve", no unit, over the 1777 East Trail at -74.25;
    - unit 300, "Fixture Bowtie Park", a ring that crosses itself, which
      ST_MakeValid turns into two triangles before anything is measured
      (PL03), and which carries no Category;
    - a blank name and a null geometry, neither of which is a place.

    ATC's two fixture Communities also get the STATE column the live layer
    carries (read 2026-10-02: all 59 rows have the field, 14 of them null),
    so the towns places.json lists reach both answers of state_code()
    (PL04): "Virginia" reads as VA, and "Virgnia", a misspelling one live row
    still carries on 2026-10-02, is no state, so that town has none, ATC's
    organization declaring none either. Nothing else
    reads the column: export_poi.py publishes a town's name, never its
    state.
    """
    parks = [
        _park("{00000000-0000-4000-8000-000000000501}", "Fixture Harriman", 127, "State Park", _box(-74.003, 40.998, -73.987, 41.009)),
        _park("{00000000-0000-4000-8000-000000000502}", "Fixture Harriman", 127, "State Park", _box(-74.205, 41.21, -74.195, 41.24)),
        _park("{00000000-0000-4000-8000-000000000503}", "Fixture Harriman", None, "State Park Preserve", _box(-74.305, 41.6, -74.295, 41.65)),
        _park("{00000000-0000-4000-8000-000000000504}", "Captree/Fixture Robert Moses", 270, "State Park", _box(-73.52, 40.6, -73.51, 40.61)),
        _park("{00000000-0000-4000-8000-000000000505}", "Fixture Robert Moses", 270, "State Park", _box(-73.5, 40.6, -73.49, 40.61)),
        _park("{00000000-0000-4000-8000-000000000506}", "Fixture Robert Moses", 270, "State Park", _box(-73.48, 40.6, -73.47, 40.61)),
        _park("{00000000-0000-4000-8000-000000000507}", "Fixture Robert Moses", 271, "State Park", _box(-73.4, 40.6, -73.39, 40.61)),
        _park("{00000000-0000-4000-8000-000000000508}", "Fixture Robert Moses", None, "Other", _box(-73.3, 40.6, -73.29, 40.61)),
        _park("{00000000-0000-4000-8000-000000000509}", "Fixture Lone Preserve", None, "Conservation Easement", _box(-74.255, 41.195, -74.245, 41.205)),
        _park(
            "{00000000-0000-4000-8000-000000000510}",
            "Fixture Bowtie Park",
            300,
            None,
            # Bottom and top triangles meeting at (-73.98, 41.0225): the network
            # lines at x -73.98 run 41.02 to 41.025, through both.
            [[-73.985, 41.018], [-73.975, 41.027], [-73.985, 41.027], [-73.975, 41.018], [-73.985, 41.018]],
        ),
        _park("{00000000-0000-4000-8000-000000000511}", "  ", 400, "State Park", _box(-73.2, 40.6, -73.19, 40.61)),
        _park("{00000000-0000-4000-8000-000000000512}", "Fixture Ghost", 401, "State Park", None),
    ]  # fmt: skip
    for feature, state in zip(files["communities.geojson"]["features"], ("Virginia", "Virgnia"), strict=True):
        feature["properties"]["STATE"] = state
    return {**files, "external/oprhp_park_polygons.geojson": _feature_collection(parks)}


# --- Decision 54, wave 1: the clubs' elevation products ----------------------
#
# Six layers registered 2026-10-03 (pipeline/ELT.md, "Loading everything the
# clubs publish"). The FIELD NAMES are each live layer's own, read off its
# metadata that day and listed in its sources.json `notes`; the VALUES are
# invented, shaped like what the live rows hold, and carry the dirt the live
# read found: ATX's rows with no geometry that repeat a segment, NCTA's point
# out of mileage order, PCTA's labels with a minus sign (U+2212) rather than a
# hyphen. Every elevation is in the unit its row's `elevation_unit` records,
# so a model that converts it the wrong way reads fixture values 3.28 times
# off, not plausible ones.


def _z_line(i: int, z: float) -> dict:
    """A two-vertex line whose vertices carry a Z, as a `return_z` layer's rows land."""
    x, y = -74.0 + i * 0.01, 41.0 + i * 0.01
    return {"type": "LineString", "coordinates": [[x, y, z], [x, y + 0.005, z + 12.5]]}


def _atc_atx_centerline_layer() -> dict:
    """ATC's ATX Ratings centerline: Z in metres on the geometry, and a row with no geometry repeating a segment.

    N_end_mileage and S_end_mileage are null on every live row, and notes on
    all but 18 of 697 (measured 2026-10-03), so the fixture's are null too.
    """
    rows = []
    for index in range(2):
        rows.append(
            {
                "OBJECTID": index + 1,
                "ORIG_SEQ": index + 1,
                "N_end_desc": f"Fixture North End {index + 1}",
                "S_end_desc": f"Fixture South End {index + 1}",
                "N_end_lat": 41.005 + index * 0.01,
                "N_end_long": -74.0 + index * 0.01,
                "S_end_lat": 41.0 + index * 0.01,
                "S_end_long": -74.0 + index * 0.01,
                "N_end_mileage": None,
                "S_end_mileage": None,
                "tot_miles": 0.35 + index,
                "label_current": f"Zone {index + 2}: Fixture segment {index + 1}",
                "label_desired": f"Zone {index + 2}: Fixture segment {index + 1}",
                "current_rating": 2.5 + index,
                "desired_rating": 2.5,
                "trail_club": "0",
                "club_acro": "0",
                "club_sec_ID": "01",
                "club_subsec_ID": "01",
                "seg_ID": f"0{index + 1}",
                "full_ID": f"01-01-0{index + 1}",
                "state": "23",
                "notes": None,
                "GlobalID": f"{{fixture-atx-{index + 1}}}",
                "Shape__Length": 560.0 + index,
            }
        )
    geometries = [_z_line(0, 330.5), _z_line(1, 1149.9), None]
    # OBJECTID 681-698 on the live layer: segment 25-01-03 again, every attribute but the id, and no geometry.
    rows.append({**rows[1], "OBJECTID": 3, "GlobalID": "{fixture-atx-3}", "Shape__Length": None})
    return _feature_collection(
        [{"type": "Feature", "properties": row, "geometry": geometry} for row, geometry in zip(rows, geometries, strict=True)]
    )


def _ncta_kek_mileage_elev_layer() -> dict:
    """NCTA's Kekekabic mileage index: Z is an attribute in feet, and one point is out of mileage order."""
    rows = [
        {"Id": 0, "mile_point": 0.0, "Z": 1501.65, "OBJECTID": 1},
        {"Id": 0, "mile_point": 0.1, "Z": 1501.18, "OBJECTID": 2},
        {"Id": 0, "mile_point": 20.69, "Z": 1898.65, "OBJECTID": 3},
    ]
    return _features(rows, _point)


def _pcta_band_rows() -> list[dict]:
    """The first two of PCTA's fourteen bands, labelled as the live layers label them: a hyphen, then a minus sign."""
    labels = ("0 - 1000 ft", "1000−2000 ft")
    return [{"OBJECTID": i + 1, "Id": i + 1, "gridcode": i + 1, "Elevation_Range": label} for i, label in enumerate(labels)]


def _pcta_per_thousand_ft_layer() -> dict:
    rows = [
        {
            **row,
            "FID_PCTA_Centerline": 1,
            "FID_DEM_Classed_Per_Thousand_Ft": row["gridcode"],
            "PCT_Miles": 12.2 + row["gridcode"],
            "Shape__Length": 28160.5 + row["gridcode"],
        }
        for row in _pcta_band_rows()
    ]
    return _features(rows, _line)


def _pcta_corridor_elevation_ranges_layer() -> dict:
    rows = [{**row, "Shape__Area": 48238797.4 + row["gridcode"], "Shape__Length": 96166.7} for row in _pcta_band_rows()]
    return _features(rows, _polygon)


def _nj_high_elevation_points_layer() -> dict:
    rows = [
        {
            "OBJECTID": i + 1,
            "COUNTY": f"Fixture County {i + 1}",
            "ELEVATION": elevation,
            "EASTING": 447747.5 + i,
            "NORTHING": 906178.4 + i,
            "GLOBALID": f"{{fixture-nj-high-{i + 1}}}",
        }
        for i, elevation in enumerate((1803, 62))
    ]
    return _features(rows, _point)


def _pasda_county_max_elevations_layer() -> dict:
    rows = [
        {
            "OBJECTID_1": i + 1,
            "OBJECTID": i + 1,
            "POINTID": i + 1,
            "Lat": 41.0 + i * 0.01,
            "Long": -74.0 + i * 0.01,
            "County": f"Fixture County {i + 1}",
            "Max_Elevat": elevation,
        }
        for i, elevation in enumerate((2234, 445))
    ]
    return _features(rows, _point)


ELEVATION_PRODUCT_FIXTURES = {
    "external/atc_atx_centerline.geojson": _atc_atx_centerline_layer,
    "external/ncta_kek_mileage_elev.geojson": _ncta_kek_mileage_elev_layer,
    "external/pcta_per_thousand_ft.geojson": _pcta_per_thousand_ft_layer,
    "external/pcta_corridor_elevation_ranges.geojson": _pcta_corridor_elevation_ranges_layer,
    "external/nj_high_elevation_points.geojson": _nj_high_elevation_points_layer,
    "external/pasda_county_max_elevations.geojson": _pasda_county_max_elevations_layer,
}


# Decision 54's wave 1 places layers (pipeline/ELT.md, "Loading everything the
# clubs publish"): every `club_arcgis_layer` row a club's places.py claims,
# registered 2026-10-03. Each fixture carries what its sources.json row
# declares as read off the live layer that day - the key (`id_field`, or
# `id_fields` for a pair), `name_field` and `category_field` - and an
# OBJECTID, and nothing else, because no model reads these tables yet
# (decision 52's base models are phase C). The values are invented: no real
# feature is copied. Two rows each, in the row's own `geometry_kind`.
CLUB_PLACES_KEYS = (
    "fltc_map_sheet_index",
    "dec_lands",
    "dec_conservation_easements",
    "dec_wildlife_management_areas",
    "dec_adirondack_park_boundary",
    "dec_catskill_park_boundary",
    "mohonk_preserve_boundary",
    "nj_state_open_space",
    "nj_state_natural_areas",
    "nj_parks_points",
    "nj_place_names",
    "ct_deep_property",
    "ct_deep_greenways",
    "massgis_openspace",
    "dcnr_state_park_boundaries",
    "dcnr_state_forest_boundaries",
    "pasda_dcnr_wild_natural_areas",
    "pasda_dcnr_local_parks",
    "nps_park_boundaries",
    "nps_legislated_wilderness",
    "grsm_municipal_boundaries",
    "grsm_park_boundary_lines",
    "pohe_trail_regions",
    "blm_national_monuments_ncas",
    "blm_wilderness_areas",
    "blm_wilderness_study_areas",
    "blm_recreation_areas",
    "blm_recreation_site_polygons",
    "blm_public_lands_access_lines",
    "pcta_trail_towns",
    "pcta_letter_sections",
    "pcta_centerline_regions",
    "pcta_permit_areas",
    "pcta_wilderness_areas",
    "pcta_sheriffs_offices",
    "aklt_communities",
    "aklt_story_map_pins",
    "duluth_park_boundaries",
    "azt_gateway_communities",
    "azt_passage_areas",
    "azt_land_ownership",
    "iat_trail_communities",
    "iata_properties",
    "iata_land_ownership",
    "fta_gateway_communities",
    "fta_managed_conservation_areas",
    "amc_properties_and_landscapes",
    "amc_chapter_boundaries",
    "spnhf_public_access_properties",
    "trustees_properties",
    "mtsg_heritage_area_boundary",
    "sbts_trail_town_amenities",
    "fpc_ancient_forest_preserve",
    "usfws_refuge_boundaries",
    "nc_state_park_boundaries",
    "tn_state_park_boundaries",
    "nh_conservation_lands",
    "nh_recreation_areas",
    "usfs_forest_boundaries",
    "usfs_ranger_districts",
    "usfs_wilderness_areas",
    "usfs_national_grasslands",
    "usfs_other_designated_areas",
    "usfs_special_interest_areas",
    "ttc_management_areas",
    "cdtc_gateway_communities",
    "cdtc_trail_sections",
    "trta_special_management_areas",
    "trta_desolation_wilderness_zones",
    "trta_trail_sections",
    "cpw_managed_properties",
    "cpw_property_centroids",
    "wa_public_lands_inventory",
    "wa_recreation_areas",
    "ugrc_municipal_boundaries",
    "ugrc_state_park_boundaries",
    "ugrc_state_park_points",
    "ugrc_cities_towns",
    "ugrc_local_parks",
    "wdnr_managed_properties",
    "patc_lands_compilation",
    "buckeye_retail_map_outlines",
    "usgs_gnis_populated_places",
)
# The keys the live layers type as numbers (read 2026-10-03), so the fixture's
# column is typed as the live one is; every other key column is a string.
CLUB_PLACES_NUMERIC_KEYS = {
    "dec_conservation_easements": {"LANDS_UID": int},
    "nj_parks_points": {"PARK_ID": int},
    "nj_place_names": {"FEATURE_ID": float},
    "azt_land_ownership": {"OWNER": int},
    "nh_recreation_areas": {"NHRECPOL_": int},
    "ugrc_local_parks": {"ACRES": float},
    "usgs_gnis_populated_places": {"incounty_id": int},
}
# An ArcGIS date lands as epoch milliseconds (extract/_kinds.py's ESRI_TYPES),
# so each field a row lists in `date_fields` gets an invented one: 2025-10-01
# UTC, a day apart per feature. pipeline/make_dbt_staging.py's base models
# cast exactly these columns, so the fixture build exercises the cast.
CLUB_PLACES_DATE_MS = 1759276800000


def _multipoint(i):
    return {"type": "MultiPoint", "coordinates": [_point(i)["coordinates"]]}


CLUB_PLACES_GEOMETRY = {"polygon": _polygon, "point": _point, "line": _line, "multipoint": _multipoint}


def _club_places_fixtures() -> dict[str, dict]:
    """One `<key>.geojson` per CLUB_PLACES_KEYS row, with the columns its registry row declares.

    The key's columns are `id_fields` (or `id_field`) and, where phase C measured a key the row did not
    have, the attribute columns of its `key_fields` (`geometry` there is the shape, which every fixture
    feature has). Each `date_fields` column carries an epoch-millisecond date.
    """
    sources = {s["key"]: s for s in json.loads((Path(__file__).parent / "sources.json").read_text())["sources"]}
    files = {}
    for key in CLUB_PLACES_KEYS:
        entry = sources[key]
        numeric = CLUB_PLACES_NUMERIC_KEYS.get(key, {})
        id_fields = list(entry.get("id_fields") or ([entry["id_field"]] if entry.get("id_field") else []))
        id_fields += [field for field in entry.get("key_fields") or [] if field != "geometry" and field not in id_fields]
        features = []
        for i in range(2):
            properties = {"OBJECTID": i + 1}
            for field in id_fields:
                properties[field] = numeric[field](100 + i) if field in numeric else f"fixture-{key}-{i}"
            for field in entry.get("date_fields") or []:
                properties[field] = CLUB_PLACES_DATE_MS + i * 86_400_000
            if entry.get("name_field") and entry["name_field"] not in properties:
                properties[entry["name_field"]] = f"Fixture {entry['title']} {i}"
            if entry.get("category_field") and entry["category_field"] not in properties:
                properties[entry["category_field"]] = "Fixture category"
            features.append(
                {"type": "Feature", "properties": properties, "geometry": CLUB_PLACES_GEOMETRY[entry["geometry_kind"]](i)}
            )
        files[f"{key}.geojson"] = _feature_collection(features)
    return files


# --- Decision 54, wave 1: the clubs' trail lines ------------------------------
#
# 98 layers registered 2026-10-03 (pipeline/ELT.md, "Loading everything the
# clubs publish"). Each entry is the live layer's own field list, in its own
# order, read off its metadata that day, with each field's type as a code:
# o object id, i integer, d double, t date (epoch ms), g GlobalID or GUID,
# s string. The VALUES are invented, two rows per layer, each key column
# distinct per row, and person fields carry an invented account name so CI
# exercises the drop the row's `person_fields` asks for. Nothing here is a
# real feature. A layer whose row says `return_z` gets lines whose vertices
# carry a Z, as its Esri JSON pages land.
CLUB_TRAIL_LINE_FIELDS = {
    "nps_oregon_nht": "OBJECTID:o Id:i DateSent:t GlobalID:g CreationDate:t Creator:s EditDate:t Editor:s",
    "nps_california_nht": "OBJECTID:o Id:i DateSent:t GlobalID:g",
    "nps_old_spanish_nht": "OBJECTID:o Id:i DateSent:t Miles:d GlobalID:g",
    "nps_el_camino_tejas_nht": "OBJECTID:o Id:i DateSent:t GlobalID:g",
    "nps_pony_express_nht": "OBJECTID:o Id:i DateSent:t GlobalID:g CreationDate:t Creator:s EditDate:t Editor:s",
    "nps_mormon_pioneer_nht": "OBJECTID:o Id:i DateSent:t mile_check:d GlobalID:g CreationDate:t Creator:s EditDate:t Editor:s",
    "nps_santa_fe_nht": (
        "OBJECTID:o TRNAME:s TRALTNAME:s TRNUMBER:s TRTYPE:s TYPEROUTE:s ADMINORG:s MANAGINGORG:s "
        "NATTRDESIGNATION:s NHTNSTADMINISTRATOR:s NHTPUBLICUSESEGMENT:s SHAREDSYSTEM:s ROADSYSTEM:s STATE:s "
        "COUNTY:s EDITDATE:t MAPMETHOD:s XYACCURACY:s AGENCYDATASOURCE:s NOTES:s FEATUREID:s GEOMETRYID:s "
        "PUBLICDISPLAY:s DATAACCESS:s UNITCODE:s UNITNAME:s GROUPCODE:s GROUPNAME:s REGIONCODE:s CREATEDATE:t "
        "CREATEUSER:s EDITUSER:s MAPSOURCE:s SOURCEDATE:t ROUTENAME:s Shape__Length:d GlobalID:g"
    ),
    "nps_trail_of_tears_nht": (
        "OBJECTID:o TRNAME:s TRALTNAME:s MAPLABEL:s TRNUMBER:s TRTYPE:s TRSURFACE:s TRCLASS:s TRUSE:s "
        "TYPEOFROUTE:s MAINTAINER:s AGENCY_UNIT:s DESIGNEDUSE:s MANAGEDUSE:s ADMINORG:s MANAGINGORG:s "
        "NATTRDESIGNATION:s NHTNSTNUMBER:s NHTNSTADMINISTRATOR:s HISTSIGNIFICANCE:s NHTCERTSTATUS:s "
        "NRHPCRITERIA:s SHAREDSYSTEM:s ROADSYSTEM:s STATE:s COUNTY:s MAPMETHOD:s MAPSOURCE:s XYACCURACY:s "
        "SRC_SCALE:s AGENCYDATASOURCE:s YYYYMMDDIMPORTED:i GEOMETRYID:s PUBLICDISPLAY:s DATAACCESS:s "
        "ACCESSNOTES:s ORIGINATOR:s UNITCODE:s UNITNAME:s UNITTYPE:s GROUPCODE:s GROUPNAME:s REGIONCODE:s "
        "SOURCEDATE:t CREATEDATE:t CREATEUSER:s EDITDATE:t EDITUSER:s LINETYPE:s OBSERVABLE:s ISEXTANT:s "
        "OPENTOPUBLIC:s QUAD24K:s QUAD100K:s GlobalID:g Shape__Length:d"
    ),
    "nps_el_camino_tierra_adentro_nht": (
        "OBJECTID:o TRNAME:s NATTRDESIGNATION:s NHTNSTADMINISTRATOR:s STATE:s MAPMETHOD:s XYACCURACY:s "
        "AGENCYDATASOURCE:s PUBLICDISPLAY:s DATAACCESS:s UNITCODE:s UNITNAME:s GROUPCODE:s GROUPNAME:s "
        "REGIONCODE:s CREATEDATE:t MAPSOURCE:s SOURCEDATE:t GlobalID:g Shape__Length:d"
    ),
    "nps_butterfield_overland_nht": (
        "OBJECTID:o GlobalID:g TRNAME:s TRTYPE:s TRSURFACE:s TRCLASS:s TRUSE:s TYPEOFROUTE:s NATTRDESIGNATION:s "
        "NHTNSTADMINISTRATOR:s STATE:s COUNTY:s MAPMETHOD:s COMMENTS:s MAPSOURCE:s SOURCEDATE:t XYACCURACY:s "
        "SRC_SCALE:s AGENCYDATASOURCE:s PUBLICDISPLAY:s DATAACCESS:s ORIGINATOR:s UNITCODE:s UNITNAME:s "
        "UNITTYPE:s GROUPCODE:s GROUPNAME:s REGIONCODE:s CREATEDATE:t CREATEUSER:s EDITDATE:t EDITUSER:s "
        "LINETYPE:s Shape__Length:d"
    ),
    "nps_butterfield_srs_route": "OBJECTID:o Id:i DateSent:t GlobalID:g Shape__Length:d",
    "nps_star_spangled_banner_nht": "OBJECTID:o Unit_Name:s Shape__Length:d",
    "nps_captain_john_smith_nht": "FID:o TRAIL_NAME:s TRAIL_TYPE:s CNCT_NAME:s Shape_Le_1:d Shape__Length:d",
    "nps_lewis_clark_nht": (
        "FID:o OBJECTID:i Source:s Exped_Seg:s DIST_MILE:d DIST_TOTAL:d TRIP_TYPE:s TRAIL_TYPE:s LEADER:s "
        "JOURNEY:s Shape_Leng:d Shape__Length:d"
    ),
    "nps_lewis_clark_water_trails": "OBJECTID:o Trail_Name:s Web_URL:s Trail_Org:s Designations:s Shape__Length:d",
    "nps_overmountain_victory_nht": "OBJECTID:o TrailName:s TrailWebsi:s Shape__Length:d",
    "nps_washington_rochambeau_nht": "FID:o OBJECTID:i Name:s Descr:s Shape_Leng:d Shape__Length:d",
    "nps_ala_kahakai_kohala_hema": "FID:o Length_mil:d Shape_Leng:d Shape__Length:d",
    "nps_ala_kahakai_alanui_aupuni": "OBJECTID:o Trail_Name:s Shape__Length:d",
    "nps_ala_kahakai_kaawaloa": "OBJECTID:o Trail_name:s Shape__Length:d",
    "nps_ala_kahakai_kiholo_puako": "OBJECTID:o Trail_Name:s Shape__Length:d",
    "nps_anza_recreation_trails": (
        "OBJECTID:o TRNAME:s TRALTNAME:s MAPLABEL:s TRNUMBER:s TRTYPE:s TRSURFACE:s TRCLASS:s TRUSE:s "
        "TYPEOFROUT:s DESIGNEDUS:s MANAGEDUSE:s ADMINORG:s MANAGINGOR:s NATTRDESIG:s NHTNSTNUMB:s NHTNSTADMI:s "
        "HISTSIGNIF:s NHTCERTSTA:s NHTCONDCAT:s NHTHIGHPOT:s NHTPUBLICU:s NRHPCRITER:s SHAREDSYST:s ROADSYSTEM:s "
        "STATE:s EDITDATE:t MAPMETHOD:s XYACCURACY:s AGENCYDATA:s YYYYMMDDIM:i NOTES:s FEATUREID:s GEOMETRYID:s "
        "PUBLICDISP:s DATAACCESS:s ACCESSNOTE:s ORIGINATOR:s UNITCODE:s UNITNAME:s UNITTYPE:s GROUPCODE:s "
        "GROUPNAME:s REGIONCODE:s CREATEDATE:t CREATEUSER:s EDITUSER:s LINETYPE:s MAPSOURCE:s SOURCEDATE:t "
        "OBSERVABLE:s ISEXTANT:s OPENTOPUBL:s CR_ID:s RESNAME:s BND_TYPE:s BND_OTHER:s EXTANT_OTH:s CONTRIBRES:s "
        "RESTRICT_:s SRC_SCALE:s VERT_ERROR:s SRC_COORD:s MAP_MTH_OT:s CONSTRANT:s CR_NOTES:s NRIS_Refnu:s "
        "NPGalleryI:s Hyper:s Link:s TRLFEATTYP:s SEASONAL:s SEASDESC:s SMA_OWNERS:s COUNTY:s TRLSTATUS:s "
        "QUAD24K:s QUAD100K:s GIS_Notes:s Shape_Leng:d GlobalID:g CreationDate:t Creator:s EditDate_1:t Editor:s "
        "Planning_Notes:s Shape__Length:d"
    ),
    "nps_anza_nht": (
        "FID:o TRNAME:s TRALTNAME:s MAPLABEL:s TRNUMBER:s TRTYPE:s TRSURFACE:s TRCLASS:s TRUSE:s TYPEOFROUT:s "
        "MAINTAINER:s DESIGNEDUS:s MANAGEDUSE:s ADMINORG:s MANAGINGOR:s NATTRDESIG:s NHTNSTNUMB:s NHTNSTADMI:s "
        "HISTSIGNIF:s NHTCERTSTA:s NHTCONDCAT:s NHTHIGHPOT:s NHTPUBLICU:s NRHPCRITER:s SHAREDSYST:s ROADSYSTEM:s "
        "STATE:s COUNTY:s MAPMETHOD:s MAPSOURCE:s SOURCEDATE:t XYACCURACY:s SRC_SCALE:s AGENCYDATA:s YYYYMMDDIM:i "
        "NOTES:s FEATUREID:s GEOMETRYID:s PUBLICDISP:s DATAACCESS:s ACCESSNOTE:s ORIGINATOR:s UNITCODE:s "
        "UNITNAME:s UNITTYPE:s GROUPCODE:s GROUPNAME:s REGIONCODE:s CREATEDATE:t CREATEUSER:s EDITDATE:t "
        "EDITUSER:s LINETYPE:s OBSERVABLE:s ISEXTANT:s OPENTOPUBL:s ALTLANGNAM:s ALTLANG:s SEASONAL:s SEASDESC:s "
        "TRLFEATTYP:s TRLSTATUS:s RESNAME:s CONTRIBRES:s RESTRICT_:s CR_NOTES:s QUAD24K:s QUAD100K:s Hyper:s "
        "GIS_Notes:s Shape_Leng:d Shape__Length:d"
    ),
    "blm_old_spanish_nht_trails": (
        "OBJECTID:o Trail_Surface_Type:s Trail_Name:s Trail_Type:s SiteMgmtCo:s SiteMgmtCo_Link:s Creator:s "
        "Editor:s Creation_Date:t Edition_Date:t Shape__Length:d GlobalID:g"
    ),
    "blm_old_spanish_nht_alignment": (
        "OBJECTID:o LAND_PLAN:s NAT_TR_DES:s TR_NAME:s ROUTE_NAME:s NHTNST_ADM:s GROUPCODE:s UNITCODE:s NOTES:s "
        "RESTRICTIO:s EDITDATE:t Shape__Len:d GlobalID:s CreationDate:t Creator:s EditDate_1:t Editor:s "
        "Shape__Length:d GlobalID_2:g"
    ),
    "blm_iditarod_nht": "OBJECTID_1:o TrailName:s Website:s Shape__Length:d",
    "usfs_pacific_northwest_trail": (
        "FID:o Layer:s RTE_NAME:s SEGMENT:s COMMENT:s ROUTE_ID:s MILES:d PNT_Sectio:s State:s TableLink:i Shape_Leng:d"
    ),
    "ata_arizona_trail": "Passage:s Miles:d Name:s Weblink:s MP_Name:s OBJECTID:o Sort:i Shape_Leng:d GlobalID:g Shape__Length:d",
    "ata_mountain_bike_passages": "OBJECTID:o type:s ident:s desc_:s link:s Length_mi:d Shape_Leng:d GlobalID:g Shape__Length:d",
    "ttc_butler_trail": (
        "OBJECTID:o ASSET_MGMT_ID:s STATION_ID:s PARK_NAME:s ASSET_NAME:s TRAIL_SYSTEM_NAME:s SHARED_NAME:s "
        "SYSTEM_TYPE:s CITY_MUNICIPAL:s COUNTY:s STATE:s ASSET_STATUS:s YEAR_BUILT:i ASSET_SIZE:d "
        "UNIT_OF_MEASUREMENT:s ASSET_SURFACE:s SURFACE_COMMENT:s WIDTH_FT:i DIFFICULTY_RATING:s DESIGN_USE:s "
        "USE_COMMENT:s ACCESSIBLITY_STATUS:s ACCESS_TYPE:s MOTORIZED_USE:s HIKE:s ROAD_BIKE:s MOUNTAIN_BIKE:s "
        "EQUESTRIAN:s DOG_SLED:s SNOWMOBILE:s SNOWSHOE:s CROSS_COUNTRY_SKI:s WATERCRAFT_MOTORIZED:s "
        "WATERCRAFT_NONMOTORIZED:s PORTAGE:s ATV:s FOUR_WD:s MOTORCYCLE:s PARK_TRAIL:s ON_STREET_BIKE:s "
        "MANAGING_NAME:s MANAGING_TYPE:s MAINTENANCE_LITTER:s MAINTENANCE_VEGETATION:s MAINTENANCE_SURFACE:s "
        "SERVICE_AREA:s COUNCIL_DISTRICT:s COUNCIL_DISTRICT_AREAS:s MXASSETNUM:s MXLOCATION:s MXSITEID:s "
        "MXCREATIONSTATE:i MXSTATUS:s MXCONDITIONCODE:s MXPRIORITY:i MXLOADID:s GLOBALID:g CREATED_BY:s "
        "CREATED_DATE:t MODIFIED_BY:s MODIFIED_DATE:t Shape__Length:d GlobalID_2:g CreationDate:t Creator:s "
        "EditDate:t Editor:s Shape__Length_2:d"
    ),
    "austin_pard_trails": (
        "OBJECTID:o ASSET_MGMT_ID:s PARK_NAME:s ASSET_NAME:s TRAIL_SYSTEM_NAME:s SHARED_NAME:s SYSTEM_TYPE:s "
        "CITY_MUNICIPAL:s COUNTY:s STATE:s ASSET_STATUS:s YEAR_BUILT:i ASSET_SIZE:d UNIT_OF_MEASUREMENT:s "
        "ASSET_SURFACE:s SURFACE_COMMENT:s WIDTH_FT:i DIFFICULTY_RATING:s DESIGN_USE:s USE_COMMENT:s "
        "ACCESSIBLITY_STATUS:s ACCESS_TYPE:s MOTORIZED_USE:s HIKE:s ROAD_BIKE:s MOUNTAIN_BIKE:s EQUESTRIAN:s "
        "DOG_SLED:s SNOWMOBILE:s SNOWSHOE:s CROSS_COUNTRY_SKI:s WATERCRAFT_MOTORIZED:s WATERCRAFT_NONMOTORIZED:s "
        "PORTAGE:s ATV:s FOUR_WD:s MOTORCYCLE:s PARK_TRAIL:s ON_STREET_BIKE:s MANAGING_NAME:s MANAGING_TYPE:s "
        "MAINTENANCE_LITTER:s MAINTENANCE_VEGETATION:s MAINTENANCE_SURFACE:s SERVICE_AREA:s COUNCIL_DISTRICT:i "
        "COUNCIL_DISTRICT_AREAS:s MXASSETNUM:s MXLOCATION:s MXPARENT:s MXSITEID:s MXCREATIONSTATE:i MXSTATUS:s "
        "MXCONDITIONCODE:s MXPRIORITY:i MXLOADID:s GLOBALID:g CREATED_BY:s CREATED_DATE:t MODIFIED_BY:s "
        "MODIFIED_DATE:t Shape__Length:d"
    ),
    "dcr_blue_hills_trails": (
        "FID:o SOURCE:s TYPE:s MAP_SYMBOL:s STATUS:s ILLEGAL:s COMMENTS:s SURFACE:s WIDTH:s CONDITION:s "
        "VEHICACCES:s TRAIL_MARK:s NAME:s LOOP1:s LOOP2:s LOOP3:s BLAZECOLOR:s HEALTHY_HT:s USE_HIKE:s USE_RUN:s "
        "USE_MTBIKE:s USE_BIKE:s USE_ATV:s USE_MCYCLE:s USE_EQUEST:s USE_DHSKI:s USE_XCSKI:s USE_GROOM:s "
        "USE_SNOMO:s USE_WINTER:s USE_DOGS:s UA_HIKE:s PLANNING:s SLOPE_AVG:d SLOPE_MAX:d FACIL_CODE:s "
        "SHAPEFILEN:s GPS_DATE:s GPS_TIME:s LENGTH_MI:d LENGTH_FT:d Shape_Leng:d GlobalID:s created_us:s "
        "created_da:t last_edite:s last_edi_1:t UNIQUE_ID:i Shape__Length:d GlobalID_2:g"
    ),
    "dcr_roads_and_trails": (
        "OBJECTID:o TYPE:s ILLEGAL:s SURFACE:s WIDTH:s CONDITION:s VEHICACCES:s TRAIL_MARK:s COMMENTS:s "
        "GPS_DATE:t GPS_TIME:s NAME:s MILES:d METERS:d GlobalID:g"
    ),
    "chesapeake_cajo_complete": (
        "FID:o COM_ID:i RCH_CODE:s RCH_DATE:s LEVEL:i METERS:d GNIS_ID:s STRAHLER:i SHREVE:i WBODY:i SHORE:i "
        "NAME:s TRAIL_NAME:s LOCATION_S:s CANOEING_O:s MAP_AND_GU:s HISTORICAL:s NATURAL_AR:s WILDLIFE_V:s "
        "CAMPING:s FISHING:s SHAPE_Leng:d"
    ),
    "chesapeake_baywide_trails": (
        "OBJECTID:o State:s Trail_Name:s Alt_Name:s Type:s Surface:s MILES:d STATUS:s MAINTENANC:s MANAGEME_1:s "
        "MANAGING_A:s Management:s LandUnit:s Owner:s Owner_2:s COUNTY:s direction:s TRACK:s on_road:s "
        "Managed_Us:s Designed_U:s Public:s ATV:s HORSE:s BIKE:s XC:s SS:s ER:s MOTORV:s SNOWMB:s MotorBoat:s "
        "PaddleBoat:s Dog:s Hike:s Interp:s Off_Road:s Four_Wheel:s Rort:s Railine:s backpack:s xcski:s fitness:s "
        "water:s ohv:s dirtbike:s nationalTr:s ada:s UTV:s RIM_BICYCL:s RIM_BICY_2:s WT_NAME:s notes:s Desc_:s "
        "source:s sourceData:s DATE_COMPL:t DATE_UPGRA:t sharedSegm:s sharedSe_2:s multiSegme:i ecg_review:s "
        "spine:s signed:s Trail_Widt:i LENGTH:d Shape_Length:d"
    ),
    "des_moines_trails": (
        "OBJECTID:o Name:s RegionalName:s Status:s SurfaceType:s LengthMile:d FacilityType:s "
        "FacilityDescription:s Structure:s Hyperlink:s GlobalID:g created_user:s created_date:t "
        "last_edited_user:s last_edited_date:t Classification:s Location:s OwnershipJurisdiction:s "
        "MaintenanceJurisdiction:s FacilitySubtype:s WidthFeet:i ConstructionYear:i RehabilitationYear:i "
        "WinterMaintenance:s FacilityContext:s EquestrianPermitted:s SkiPermitted:s SnowmobilePermitted:s "
        "TotalCost:d CostPerMile:d CostDescription:s Comments:s ExtID:d Shape__Length:d"
    ),
    "iowa_dnr_state_park_trails": (
        "OBJECTID:o Type:s Use_type:s Surface:s Descrip:s Width:i Bike:s Horse:s Ski:s Skate:s Snowmobile:s "
        "Hike:s Rec_uses:s Source:s HC_Access:s Seasonal:s Length_m:d idStPark:s idAdminB:s Trail_Name:s Owner:s "
        "Mtn_Bike:s created_user:s created_date:t last_edited_user:s last_edited_date:t GlobalID:g "
        "Shape.STLength():d Length_mi:d ADA_access:s Mt_Bike:s"
    ),
    "tdec_state_park_trails_2024": (
        "OBJECTID:o TSP_UID:s TR_NAME:s SEGMNT_NAME:s SEGTYP:s RATING:i BLZCLR:s BLZMAT:s BLZDSC:s TRSTAT:s "
        "TRLUSE:s TRSURF:s MANAGE:s OWNERS:s SEGLEN:d TRLLEN:d PRIMARY_NAME__LONG_:s SECONDARY_NAME__LONG_:s "
        "USE_TYPE:s GlobalID:g"
    ),
    "tdec_public_trails_view": (
        "OBJECTID:o Trail_UID:s Park_ID:s Trail_Name:s Segment_Name__if_Applicable_:s Segment_Type:s Park_Name:s "
        "GlobalID:g Park:s State_Natural_Area:s TRSTAT:s MAX_BLZCLR:s TAIDataYN:s AccessibilityPageLink:s "
        "GradeTypical:d GradeMax:d CrossSlopeTypical:d CrossSlopeMax:d TreadWidthTypical:d TreadWidthMin:d "
        "TAISurfaceDesc:s TAIObstructions:s TAIElevGain:d TAIElevLoss:d State_Natural_Area_1:s Promoted_Mileage:d "
        "GIS_Trail_Route_Type:s Trail_Description:s Surf_Paved:s Surf_Gravel:s Surf_Natural:s Surf_Mulch:s "
        "Surf_Water:s Surf_Riverbed:s Use_Hike:s Use_Bike:s Use_MtnBike:s Use_Paddle:s Use_Equestrian:s "
        "Use_Climb:s Use_Fitness:s Use_Wheelchair:s Use_AllTerrain_Wheelchair:s Use_Storybook:s Node_ID:s "
        "TrailCardsYN:s GIS_Trail_Length:d Difficulty:s Last_Assessed_Date:s"
    ),
    "tdec_public_trails": (
        "OBJECTID:o TSP_UID:s TR_NAME:s SEGMNT_NAME:s SEGTYP:s RATING:i BLZCLR:s BLZMAT:s BLZDSC:s TRSTAT:s "
        "TRLUSE:s TRLVIN:s TRSURF:s MANAGE:s OWNERS:s SEGLEN:d TRLLEN:d SOURCE:s COLMET:s CREATED_BY:s "
        "CREATED_DATE:t EDITED_BY:s EDITED_DATE:t PRIMARY_NAME__LONG_:s SECONDARY_NAME__LONG_:s USE_TYPE:s "
        "PRIMARY_DESIGNATION:s SECONDARY_DESIGNATION:s Shape__Length:d GlobalID:g"
    ),
    "ctsst_open_ct_trail_2020": (
        "OBJECTID:o Park_Name:s Trail_Name:s Trail_Statue:s Trail_Discription:s Trail_Mileage:d sequence:d Shape__Length:d"
    ),
    "ctsst_comp_trails_2020": "OBJECTID:o Trail_Name:s Location:s Trail_Useage:s Mileage:d Status:s State:s Shape__Length:d",
    "ctsst_road_walks_2020": "OBJECTID:o Name:s Existing:s Miles:d Type:s Shape__Length:d",
    "ctsst_overall_route_2023": (
        "OBJECTID:o Park_Name:s Trail_Name:s Trail_Statue:s Trail_Discription:s Trail_Mileage:d County:s Year:d "
        "Order_:d Shape__Length:d"
    ),
    "ctsst_glyph_parkway": "OBJECTID_1:o OBJECTID:i Name:s Mileage:d Shape__Length:d",
    "ctsst_duskin_piney_trail": (
        "OBJECTID:o Park_Name:s Trail_Name:s Trail_Statue:s Trail_Discription:s Trail_Mileage:d County:s Shape__Length:d"
    ),
    "ctsst_newby_piney_trail": "OBJECTID:o Name:s Mileage:d SHAPE__Length:d",
    "fltc_flt_main": (
        "FID:o OBJECTID:i LABEL:s NOTES:s Len_Meters:d Len_Miles:d Data_Type:s PassOvrCol:s BrochurCol:s "
        "Mod_Date:t Shape_Leng:d Point_Coun:i Shape__Length:d"
    ),
    "fltc_non_flt_trails": (
        "FID:o OBJECTID:i BlazeColor:s Symbol:s LABEL:s Jurisdict:s Maps:s Data_Type:s NOTES:s Len_Meters:d "
        "Len_Miles:d Date_Modif:t Shape_Leng:d Shape__Length:d"
    ),
    "portland_parks_trails": (
        "OBJECTID:o PROPERTYID:d Local_Name:s TYPE:s STATUS:s Manager:s SURFACE:s WIDTH_FT:i SOURCE:s "
        "Regional_trail:s Columbia_Slough:s Forty_Mile_Loop:s I_205:s Marine_Drive:s MARQUAM:s Springwater:s "
        "Willamette_Greenway:s Notes:s Red_Electric:s Hillsdale_Lake_Oswego:s Fanno_Creek_Greenway:s MILES:d "
        "Shape_Length:d Fire_access:s"
    ),
    "ppr_trails": (
        "OBJECTID:o PROPERTYID:d NAME:s TYPE:s STATUS:s DT_OPEN:t DT_IMPROVED:t DT_CLOSED:t MANAGE:s SURFACE:s "
        "SURFPROP:s WIDTH_FT:i INTER_LINE:s COND:i CONDYEAR:i CONDINIT:s SOURCE:s SOURC_GEN:s USERPED:s "
        "USERHORSE:s USERADA:s USERROLL:s BIKEMTN:s BIKEROAD:s REGIONAL:s COL_SLOUGH:s FORTY_MILE:s I_205:s "
        "MARINEDRTR:s MARQUAM:s SPRINGH2O:s WILL_GRNWY:s SW_TRAILS:s PLANNED:s SWTRAIL1:s RED_LECTRC:s SWTRAIL3:s "
        "SWTRAIL4:s SWTRAIL5:s SWTRAIL6:s SWTRAIL7:s HLLSDL_LO:s FANNO_CRK:s MILES:d Fire_access:s GlobalID:g"
    ),
    "oregon_metro_trails": (
        "FID:o TRAILNAME:s SYSTEMNAME:s SHAREDNAME:s SYSTEMTYPE:s STATUS:s TRLSURFACE:s WIDTH:s ACCESSIBLE:s "
        "HIKE:s ROADBIKE:s MTNBIKE:s EQUESTRIAN:s WCRAFT_NON:s AGENCYNAME:s MILEAGE:d TRAILID:i WILRIVGNWY:s "
        "FORTYMLOOP:s REGPLAN:s AGENCYTYPE:s LAST_EDIT:t LENGTH:d Shape__Length:d SYMB_CAT:s"
    ),
    "gmc_trail_master": (
        "FID:o TrailName:s MaintName:s TrailType:s Division:s Maint_code:s Maint_ID:s FeatureID:s Feat_Code:s "
        "AT:s Length_mi:d Length_ft:d Source:s Sourcedate:s Notes:s LastEdDate:t LastEdBy:s AF_CONF:i "
        "Shape__Length:d GlobalID:g"
    ),
    "in_dnr_open_trails": (
        "objectid:o segcode:d segmiles:d segname:s status:s reportedsegdistance:d trailtype:s surface:s "
        "managingentity:s yropen:i geogsource:s hike:s exercise:s intrp:s roadbike:s mtnbike:s horse:s ski:s "
        "whlchr:s snowbile:s atv:s mocycle:s fwdrive:s canoe:s skate:s otheruse:s multiuse:s property:s "
        "entitytype:s railtrail:s entityaddress:s entityphone:s entityemail:s county:s trailcode:i "
        "reportedtraildistance:d globalid:g creationdate:t creator:s editdate:t editor:s entityweb:s trailname:s "
        "SHAPE__Length:d"
    ),
    "ncta_spurs": "OBJECTID:o seg_name:s prop_name:s len_miles:d updated:t owner:s source:s public_map:s Shape__Length:d",
    "ncta_nearby_trails": (
        "OBJECTID:o seg_name:s prop_name:s state:s chapter:s len_miles:d updated:t owner:s source:s public_map:s "
        "Max_Slope:d Avg_Slope:d Shape__Length:d"
    ),
    "ncta_superior_hiking_trail": (
        "OBJECTID:o seg_name:s trail_stat:s trail_type:s trail_surf:s len_miles:d built_on:t bike:s horse:s "
        "camping:s opn_camp:s closure:s cls_date:s prop_name:s ownership:s mng_auth:s state:s chapter:s "
        "data_type:s cert_stat:s updated:t seg_id:s cert_doc:s ncta_region:s easement_id:s easement_type:s "
        "cong_dist:s source:s public_map:s special_regs:s Shape__Length:d"
    ),
    "ncta_finger_lakes_trail": (
        "OBJECTID:o seg_name:s trail_stat:s trail_type:s trail_surf:s len_miles:d built_on:t bike:s horse:s "
        "camping:s opn_camp:s closure:s cls_date:s prop_name:s ownership:s mng_auth:s state:s chapter:s "
        "data_type:s cert_stat:s updated:t seg_id:s cert_doc:s source:s public_map:s special_regs:s "
        "created_user:s created_date:t last_edited_user:s last_edited_date:t Shape__Length:d"
    ),
    "octa_hastings_cutoff_route": "FID:o Title:s Source:s Latitude:d Longitude:d ident:s rident:s Shape__Length:d",
    "octa_naches_pass_trail": (
        "FID:o Name:s SName:s Comment:s Symbol:i Points:i LatN:d LatS:d LonE:d LonW:d Class:s TrailSys:s ResStat:s"
    ),
    "octa_natcon_boardman_tracks_2016": (
        "FID:o Name:s SName:s Comment:s Symbol:i Points:i LatN:d LatS:d LonE:d LonW:d Class:s TrailSys:s ResStat:s"
    ),
    "octa_corral_springs_tracks_2015": (
        "FID:o Name:s SName:s Comment:s Symbol:i Points:i LatN:d LatS:d LonE:d LonW:d Class:s TrailSys:s ResStat:s SubTrail:s"
    ),
    "octa_whitman_longsegs_2020": (
        "FID:o Name:s SName:s Comment:s Symbol:i Points:i LatN:d LatS:d LonE:d LonW:d Class:s TrailSys:s ResStat:s"
    ),
    "octa_polylines_oregon_trail_kml": (
        "OBJECTID:o Name:s FolderPath:s SymbolID:i AltMode:i Base:d Clamped:i Extruded:i Snippet:s PopupInfo:s Shape__Length:d"
    ),
    "octa_lockhart_trail_route": "FID:o Id:i Shape__Length:d",
    "octa_barlow_road_62": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_barlow_road_63": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_barlow_road_64": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_barlow_road_65": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_barlow_road_86": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_molalla_young_trail_62": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_molalla_young_trail_63": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_klamath_fremont_trail_65": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_klamath_fremont_trail_71": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_meek_trail_65": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_meek_trail_71": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_meek_trail_86": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_oregon_trail_71": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_oregon_trail_81": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_oregon_trail_85": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_oregon_trail_86": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_oregon_trail_87": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_oregon_trail_88": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_oregon_trail_89": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "octa_bonneville_trail_1834_86": "OBJECTID:o InLine_FID:i MaxSimpTol:d MinSimpTol:d Shape__Length:d",
    "onda_odt_tracks": (
        "creator:s stroke_opacity:i stroke_width:i title:s fill:s class:s updated:d stroke:s fill_opacity:d "
        "folderId:s gpstype:s ObjectId:o Shape__Length:d"
    ),
    "patc_trails_master": (
        "OBJECTID:o TrailName:s TrailType:s MapMethod:s MapSource:s SurveyDate:s District:s Maintainer:s "
        "GuidebookSection:s Easement:s Comments:s SegmentLengthMiles:d MapFootprint:s SegmentFrom:s SegmentTo:s "
        "Legacy_SegmentName:s Legacy_Segment_ID:s GlobalID:g Shape__Length:d CreationDate:t Creator:s EditDate:t "
        "Editor:s"
    ),
    "ridgetrail_official_route": (
        "OBJECTID:o Section_Number:i Section_Name:s Section_Status:s Trail_Type:s BRT_Web_Mileage:d "
        "Calculated_Mileage:d Park_Managers:s Region:s County:s Segment_Name:s AllTrails_Link:s BRT_Website:s "
        "Outerspacial:s Hike_Miles:d Biker_Miles:d Equestrian_Miles:d Partner_Website:s Dog_Permissions:s "
        "Dog_Notes:s Bike_Permissions:s Bike_Notes:s Horse_Permissions:s Horse_Notes:s Restrooms:s "
        "Restroom_Notes:s Parking_Fee:s Picnic_Tables:s Picnic_Table_Notes:s Camping:s Camp_Type:s Camp_Name:s "
        "Camp_Website:s Peaks:s Ocean_Views:s Inland_Views:s Lakes_Ponds:s Shady:s Family_Friendly:s Easy_Grade:s "
        "Highest_Elevation:s Shape__Length:d CreationDate:t Creator:s EditDate:t Editor:s DedicationYear:i "
        "BRT_Website_Embed:s ElevationGainLoss:s Segment_ID:s"
    ),
    "sbts_maintained": "OBJECTID:o Name:s Forest:s Type:s ProjectName:s Trail_Number:s Miles:d Shape__Length:d",
    "shta_line_2025": (
        "FID:o OBJECTID:i OBJECTID_1:i altname:s maintrail:i details:s isNew:i status:i meters:d miles:d "
        "Shape_Leng:d Length_FT:d SectionSou:i MileMarker:i Shape_Le_1:d Shape_Le_2:d Shape__Length:d"
    ),
    "shta_spurs_and_loops": (
        "FID:o OBJECTID:i altname:s maintrail:i details:s isNew:i status:i meters:d miles:d Shape_Leng:d "
        "Length_FT:d SectionSou:i Shape__Length:d"
    ),
    "shta_spirit_mountain_spur_2025": (
        "FID:o OBJECTID:i altname:s maintrail:i details:s isNew:i status:i meters:d miles:d Shape_Leng:d "
        "Length_FT:d SectionSou:i Field:d newmiles:d Shape__Length:d"
    ),
    "lake_county_superior_hiking_trail": "OBJECTID:o COLLECTOR:s SHT_TYPE:s MILES:d LENGTH:d Shape_Leng:d Shape__Length:d",
    "tko_oregon_coast_trail": (
        "OCT_Section_Name:s OBJECTID:o FENAME:s COMMENTS:s Section:s GapName:s TrailStatus:s TrailType:s OCT_ID:s "
        "HRA_Recommendation:s Section_Name:s Shape__Length:d"
    ),
    "tpwd_state_park_trails": "OBJECTID:o ParkName:s Official:s Name1:s TrailUse:s LengthMI:d GlobalID:g Shape_Length:d",
    "usace_mobile_trails": (
        "OBJECTID:o GlobalID:g featureDescription:s featureName:s isInterpretive:s isNatureTrail:s mediaId:s "
        "metadataId:s officialLength:d officialLengthUom:s recreationalTrailUse:s recreationTrailIdpk:s rpnid:s "
        "rpsuid:i rpuid:s sdsId:g created_user:s created_date:t last_edited_user:s last_edited_date:t "
        "difficultyRating:s managedBy:s status:s Shape__Length:d"
    ),
    "usace_tulsa_trails": (
        "featureDescription:s featureName:s isInterpretive:s isNatureTrail:s mediaId:s metadataId:s "
        "officialLength:d officialLengthUom:s propertyIdCode:s recreationalTrailUse:s recreationTrailIdpk:s "
        "rpnid:s rpsuid:i rpuid:s sdsId:g GlobalID:g created_user:s created_date:t last_edited_user:s "
        "last_edited_date:t dataSource:s dataYear:s OBJECTID:o Shape__Length:d"
    ),
    "usfws_trail_segments": (
        "OBJECTID:o ORGCODE:s ORGNAME:s TRNAME:s TRALTNAME:s TRNUMBER:s SECNUMBER:s TRTYPE:s TRSURFACE:s "
        "TRSURFACEFWS:s TRSURFACEOTHER:s TRCLASS:s TRCONDITION:s TYPEROUTE:s SHAREDSYSTEM:s DESIGNEDUSE:s "
        "MANAGEDUSE:s TRUSE:s ADMINORG:s MANAGINGORG:s OWNER:s OWNERNAME:s MAINTAINER:s MAINTAINERNAME:s "
        "NATTRDESIGNATION:s NHTNSTNUMBER:s NHTNSTADMINISTRATOR:s MAPMETHOD:s XYACCURACY:s AGENCYDATASOURCE:s "
        "YYYYMMDDIMPORTED:i FEATUREID:s GEOMETRYID:s CYCLEID:d GPSDATE:t REGION:i STATE:s LOCATION:s ASSETCODE:s "
        "WIDTH:i MAXSLOPE:i AVGSLOPE:i AVGXSLOPE:i SECLENGTHFT:i TRAILFT:i SECLENGTHMI:d TRAILMI:d STARTLAT:d "
        "STARTLONG:d ENDLAT:d ENDLONG:d STARTDESCRIPTION:s ENDDESCRIPTION:s ACCESSIBILITYINFO:s INFOTYPE:s "
        "BICYCLES:s DOGS:s DATAACCESS:s PUBLICDISPLAY:s SEASONAL:s SEASONALDESC:s NOTES:s CREATEUSER:s "
        "CREATEDATE:t EDITUSER:s EDITDATE:t GlobalID:g RelateGUID:g Shape__Length:d"
    ),
}
CLUB_TRAIL_LINES_WITH_Z = frozenset({"ata_arizona_trail"})


def _club_value(key: str, name: str, code: str, i: int):
    if code in ("o", "i"):
        return i + 1
    if code == "d":
        return 1.5 + i
    if code == "t":
        return 1759000000000 + i * 86_400_000
    if code == "g":
        return f"{{fixture-{key}-{i + 1}}}"
    return f"fixture {name} {i + 1}"


def _club_trail_lines_fixtures() -> dict[str, dict]:
    """One fixture per decision 54 trail-line layer, from CLUB_TRAIL_LINE_FIELDS."""
    files = {}
    for key, spec in CLUB_TRAIL_LINE_FIELDS.items():
        columns = [tuple(item.rsplit(":", 1)) for item in spec.split()]
        features = []
        for i in range(2):
            geometry = _z_line(i, 5505.0 + i * 100) if key in CLUB_TRAIL_LINES_WITH_Z else _line(i)
            properties = {name: _club_value(key, name, code, i) for name, code in columns}
            features.append({"type": "Feature", "properties": properties, "geometry": geometry})
        files[f"external/{key}.geojson"] = _feature_collection(features)
    return files


# --- Decision 54, wave 1: the clubs' point layers ---------------------------
#
# The points_of_interest layers registered 2026-10-03 as club_arcgis_layer
# (pipeline/ELT.md, "Loading everything the clubs publish"), one fixture each.
# The FIELD NAMES are each live layer's own, every one of them, read off its
# metadata that day; the VALUES are invented, two rows a layer: the measured
# key kept distinct, the type column carrying two of the values its live
# grouping found, and every other column null, so nothing is claimed about a
# column nobody profiled. Each person field the row or PERSON_FIELDS names
# carries an invented value, so CI's fixture build shows it never lands. No
# staging model reads these tables yet; phase C adds them.


def _club_point_layer(fields: tuple[str, ...], values: dict[str, tuple]) -> dict:
    """Two invented points carrying a club layer's own live field list: `values` gives the declared columns' two values each."""
    rows = [{name: values.get(name, (None, None))[index] for name in fields} for index in range(2)]
    return _features(rows, _point)


CLUB_POINT_FIXTURES = {
    "external/ncta_points.geojson": (
        (
            "state",
            "chapter",
            "wptType",
            "owner",
            "updated",
            "lat",
            "lon",
            "source",
            "public_map",
            "OBJECTID",
            "google_maps_ulr",
            "waypointID",
            "waypointName",
            "iconSet",
            "descriptionText",
            "alternateCoordinates",
            "iconSet2",
            "iconSet3",
            "iconSet4",
            "iconSet5",
            "wptTypeOld",
            "farout_app",
            "created_user",
            "created_date",
            "last_edited_user",
            "last_edited_date",
            "year_built",
            "minor_struc_type",
            "dimensions",
            "material",
            "GlobalID",
        ),
        {
            "OBJECTID": (1, 2),
            "GlobalID": ("{fixture-ncta_points-0}", "{fixture-ncta_points-1}"),
            "waypointName": ("Fixture ncta points 0", "Fixture ncta points 1"),
            "wptType": ("POI", "Parking"),
            "source": ("fixture person", "fixture person"),
            "created_user": ("fixture person", "fixture person"),
            "last_edited_user": ("fixture person", "fixture person"),
            "descriptionText": ("fixture person", "fixture person"),
        },
    ),
    "external/fltc_waypoints.geojson": (
        (
            "OBJECTID",
            "Category",
            "MapName",
            "Name",
            "Description",
            "Symbol_Name",
            "Lat",
            "Lon",
            "Lat_Lon",
            "Revision_Date",
            "ViewLink",
        ),
        {
            "OBJECTID": (1, 2),
            "Name": ("Fixture fltc waypoints 0", "Fixture fltc waypoints 1"),
            "Category": ("Parking/Access", "PointsOfInterest"),
            "Description": ("fixture person", "fixture person"),
        },
    ),
    "external/iata_water.geojson": (
        ("OBJECTID", "Potability", "Feature_Type", "Reliability", "Description", "Comment"),
        {"OBJECTID": (1, 2), "Description": ("Fixture iata water 0", "Fixture iata water 1"), "Feature_Type": (1, 11)},
    ),
    "external/iata_camping.geojson": (
        ("OBJECTID", "Camp_Type", "Num_Sites", "Water", "Toilet", "Showers", "Comment", "Description", "Prop_Nm"),
        {"OBJECTID": (1, 2), "Description": ("Fixture iata camping 0", "Fixture iata camping 1"), "Camp_Type": (3, 2)},
    ),
    "external/iata_parking.geojson": (
        (
            "OBJECTID",
            "Parking_Type",
            "Description",
            "Fee",
            "Lat_Long",
            "Latitude",
            "Longitude",
            "Overnight_Park",
            "Parking_Notes",
            "Prop_Nm",
        ),
        {"OBJECTID": (1, 2), "Description": ("Fixture iata parking 0", "Fixture iata parking 1"), "Parking_Type": (0, 1)},
    ),
    "external/gmc_overnight_sites.geojson": (
        (
            "FID",
            "Name",
            "OSType",
            "Division",
            "Maint_Code",
            "Maint_ID",
            "Feat_Code",
            "FeatureID",
            "Land_Name",
            "Prot_Type",
            "Landowner",
            "Wilderness",
            "Latitude",
            "Longitude",
            "SOURCE",
            "DATE",
            "NOTES",
            "Elev_M",
            "Elev_ft",
            "CT_Range",
            "Year_built",
            "SH_cap",
            "Tent_cap",
            "Group_",
            "Fee",
            "Water",
            "Food_Store",
            "Privy_ID",
            "Privy_Type",
            "SHtype_Mgr",
            "SHtype_Use",
            "Water_Srce",
            "Water_Note",
            "LastEdDate",
            "LastEdBy",
            "Protect",
            "PublicMap",
            "OSType_Lng",
            "Privy_Lng",
            "Caretaker",
            "Photo1",
            "Photo2",
            "Photo3",
            "Photo4",
            "Photo5",
            "GlobalID",
        ),
        {
            "FID": (1, 2),
            "GlobalID": ("{fixture-gmc_overnight_sites-0}", "{fixture-gmc_overnight_sites-1}"),
            "Name": ("Fixture gmc overnight sites 0", "Fixture gmc overnight sites 1"),
            "OSType": ("SH", "LO"),
            "SOURCE": ("fixture person", "fixture person"),
            "LastEdBy": ("fixture person", "fixture person"),
            "Comment": ("fixture person", "fixture person"),
            "Parking_Notes": ("fixture person", "fixture person"),
            "NOTES": ("fixture person", "fixture person"),
        },
    ),
    "external/gmc_parking.geojson": (
        (
            "FID",
            "Name",
            "TRAILNAME",
            "ParkinType",
            "Division",
            "Maint_code",
            "Maint_ID",
            "Feat_code",
            "FeatureID",
            "Surface",
            "Capacity",
            "Year_built",
            "Plowed",
            "ADA",
            "Owner",
            "Publish",
            "Latitude",
            "Longitude",
            "Elev_ft",
            "Elev_M",
            "NOTES",
            "Source",
            "SourceDate",
            "LastEdDate",
            "LastEdBy",
            "Protect",
            "FWD_Access",
            "PublicMap",
            "GlobalID",
        ),
        {
            "FID": (1, 2),
            "GlobalID": ("{fixture-gmc_parking-0}", "{fixture-gmc_parking-1}"),
            "Name": ("Fixture gmc parking 0", "Fixture gmc parking 1"),
            "ParkinType": ("ML", "EL"),
            "Source": ("fixture person", "fixture person"),
            "LastEdBy": ("fixture person", "fixture person"),
        },
    ),
    "external/gmc_privies.geojson": (
        (
            "FID",
            "ET_ID",
            "Name",
            "PrivyType",
            "Division",
            "Maint_Code",
            "Maint_ID",
            "Feat_Code",
            "FeatureID",
            "Land_Name",
            "Prot_Type",
            "Landowner",
            "Wilderness",
            "SOURCE",
            "DATE",
            "NOTES",
            "Elev_m",
            "Elev_ft",
            "Latitude",
            "Longitude",
            "CT_Range",
            "Year_built",
            "LastEdDate",
            "LastEdBy",
            "Protect",
            "GlobalID",
        ),
        {
            "FID": (1, 2),
            "GlobalID": ("{fixture-gmc_privies-0}", "{fixture-gmc_privies-1}"),
            "Name": ("Fixture gmc privies 0", "Fixture gmc privies 1"),
            "PrivyType": ("MO", "BB"),
            "SOURCE": ("fixture person", "fixture person"),
            "LastEdBy": ("fixture person", "fixture person"),
        },
    ),
    "external/gmc_viewpoints.geojson": (
        (
            "FID",
            "Name",
            "TRAILNAME",
            "VSTYPE",
            "Division",
            "Maint_Code",
            "Maint_ID",
            "Feat_Code",
            "FeatureID",
            "Latitude",
            "Longitude",
            "ELEV_FT",
            "ELEV_M",
            "Source",
            "Sourcedate",
            "VISTA",
            "SUMMIT",
            "TOWER",
            "NOTES",
            "GlobalID",
        ),
        {
            "FID": (1, 2),
            "GlobalID": ("{fixture-gmc_viewpoints-0}", "{fixture-gmc_viewpoints-1}"),
            "Name": ("Fixture gmc viewpoints 0", "Fixture gmc viewpoints 1"),
            "VISTA": (1, 0),
            "Source": ("fixture person", "fixture person"),
        },
    ),
    "external/gmc_map_features.geojson": (
        ("FID", "TRAILNAME", "POINAME", "NOTES", "LastEdDate", "LastEdBy", "GlobalID"),
        {
            "FID": (1, 2),
            "GlobalID": ("{fixture-gmc_map_features-0}", "{fixture-gmc_map_features-1}"),
            "POINAME": ("Fixture gmc map features 0", "Fixture gmc map features 1"),
            "LastEdBy": ("fixture person", "fixture person"),
        },
    ),
    "external/tahoe_rim_water_sources.geojson": (
        ("OBJECTID", "NAME", "RELIABILITY"),
        {
            "OBJECTID": (1, 2),
            "NAME": ("Fixture tahoe rim water sources 0", "Fixture tahoe rim water sources 1"),
            "RELIABILITY": ("Reliable", "Seasonal"),
        },
    ),
    "external/tahoe_rim_campgrounds.geojson": (
        ("OBJECTID", "Name", "Campground_Type", "Fee", "GlobalID"),
        {
            "OBJECTID": (1, 2),
            "GlobalID": ("{fixture-tahoe_rim_campgrounds-0}", "{fixture-tahoe_rim_campgrounds-1}"),
            "Name": ("Fixture tahoe rim campgrounds 0", "Fixture tahoe rim campgrounds 1"),
            "Campground_Type": ("No Fee LTNSP Campground", "Fee USFS Campground"),
        },
    ),
    "external/tahoe_rim_points_of_interest.geojson": (
        ("OBJECTID", "Name", "Type", "Notes", "PhotoURL"),
        {
            "OBJECTID": (1, 2),
            "Name": ("Fixture tahoe rim points of interest 0", "Fixture tahoe rim points of interest 1"),
            "Type": ("Vista", "Lake"),
        },
    ),
    "external/tahoe_rim_trailheads.geojson": (
        ("Name", "Toilet", "Water", "Number_of_Parking_Stalls", "Biking_Allowed", "Picnic_Tables", "x", "y", "ObjectId"),
        {"ObjectId": (1, 2), "Name": ("Fixture tahoe rim trailheads 0", "Fixture tahoe rim trailheads 1")},
    ),
    "external/cdtc_water_caches.geojson": (
        ("OBJECTID", "Name", "State", "X", "Y", "Website"),
        {"OBJECTID": (1, 2), "Name": ("Fixture cdtc water caches 0", "Fixture cdtc water caches 1")},
    ),
    "external/cdtc_bootheel_water_caches.geojson": (
        ("OBJECTID", "Name", "X", "Y", "Website"),
        {"OBJECTID": (1, 2), "Name": ("Fixture cdtc bootheel water caches 0", "Fixture cdtc bootheel water caches 1")},
    ),
    "external/cdtc_parking.geojson": (
        ("OBJECTID", "FID", "NAME", "PRKTYPE", "SURFTYPE", "PRKSPACES", "STATE", "JURISDICTI", "NOTE"),
        {
            "OBJECTID": (1, 2),
            "NAME": ("Fixture cdtc parking 0", "Fixture cdtc parking 1"),
            "PRKTYPE": ("Engineered parking area", "<Null>"),
        },
    ),
    "external/cdtc_trailheads_and_mail.geojson": (
        (
            "OBJECTID",
            "FID",
            "NAME",
            "DESC_",
            "WP_Type",
            "Label",
            "PARKING",
            "IMG",
            "HORSEPKNG",
            "PRKTYPE",
            "SURFTYPE",
            "PRKSPACES",
            "STATE",
            "JURISDICTI",
            "MAIL_L1",
            "MAIL_L2",
            "MAIL_L3",
            "MAIL_L4",
            "NOTE",
        ),
        {
            "OBJECTID": (1, 2),
            "NAME": ("Fixture cdtc trailheads and mail 0", "Fixture cdtc trailheads and mail 1"),
            "WP_Type": ("TH", "AP"),
        },
    ),
    "external/pcta_halfmile_water_sources.geojson": (
        ("OBJECTID", "Name", "SymbolID", "PopupInfo"),
        {
            "OBJECTID": (1, 2),
            "Name": ("Fixture pcta halfmile water sources 0", "Fixture pcta halfmile water sources 1"),
            "SymbolID": (7, 3),
        },
    ),
    "external/pcta_halfmile_campsites.geojson": (
        ("OBJECTID", "Name", "SymbolID", "PopupInfo", "HasLabel", "LabelID"),
        {
            "OBJECTID": (1, 2),
            "Name": ("Fixture pcta halfmile campsites 0", "Fixture pcta halfmile campsites 1"),
            "SymbolID": (8, 3),
        },
    ),
    "external/pcta_trailheads.geojson": (
        (
            "OBJECTID",
            "accessRoad",
            "amenities_bathroom",
            "amenities_picnicTable",
            "amenities_roadAccess",
            "amenities_trash",
            "amenities_unknown",
            "createdAt",
            "external_allServices",
            "external_elevation",
            "external_halfmileRecordId",
            "external_inPermitDatabase",
            "external_link",
            "external_namePermitDatabase",
            "external_nameSalesforce",
            "external_objectId",
            "external_origName",
            "external_pctMile21",
            "external_salesforceId",
            "external_trailheadManager",
            "external_trailheadOrAccessPoint",
            "id",
            "link",
            "mile",
            "parking_equestrian",
            "parking_exists",
            "parking_overnight",
            "parking_paid",
            "parking_unknown",
            "region__status",
            "region_slug",
            "region_title",
            "slug",
            "title",
            "updatedAt",
        ),
        {
            "OBJECTID": (1, 2),
            "id": ("fixture-pcta_trailheads-0", "fixture-pcta_trailheads-1"),
            "title": ("Fixture pcta trailheads 0", "Fixture pcta trailheads 1"),
            "external_trailheadOrAccessPoint": ("Trailhead", "Access Point"),
        },
    ),
    "external/fta_campsites.geojson": (
        (
            "OBJECTID",
            "Campsite_ID",
            "Campsite_Name",
            "Campsite_Type",
            "Trail_Type",
            "Dist2Trail_ft",
            "Dist2Water_ft",
            "Fees",
            "NumOfSites",
            "Picnic_Tables",
            "Bench",
            "Swimming",
            "FireRing",
            "Comments",
            "Source",
            "SourceDate",
            "Created_User",
            "Created_Date",
            "Last_Edited_User",
            "Last_Edited_Date",
            "GlobalID",
        ),
        {
            "OBJECTID": (1, 2),
            "GlobalID": ("{fixture-fta_campsites-0}", "{fixture-fta_campsites-1}"),
            "Campsite_Name": ("Fixture fta campsites 0", "Fixture fta campsites 1"),
            "Campsite_Type": ("Campsite", "Designated Campsite"),
            "Created_User": ("fixture person", "fixture person"),
            "Last_Edited_User": ("fixture person", "fixture person"),
        },
    ),
    "external/fta_trailheads.geojson": (
        (
            "OBJECTID",
            "Trailhead_Name",
            "Connection_Type",
            "FTA_Kiosk",
            "Dist2Trail",
            "Capacity",
            "Fee",
            "Trailhead_Status",
            "Comments",
            "GlobalID",
        ),
        {
            "OBJECTID": (1, 2),
            "GlobalID": ("{fixture-fta_trailheads-0}", "{fixture-fta_trailheads-1}"),
            "Trailhead_Name": ("Fixture fta trailheads 0", "Fixture fta trailheads 1"),
            "Connection_Type": ("On Trail", "On Spur Trail"),
        },
    ),
    "external/cfpa_overnight_sites.geojson": (
        (
            "OBJECTID",
            "TYPE",
            "NUM_CAMPSITES",
            "NAME",
            "RESERVATION_REQ",
            "RES_LINK",
            "MAINT_ORG",
            "STATUS",
            "SHOW_PUBLIC",
            "AT",
            "NET",
            "NOTES",
            "GlobalID",
            "SITE_LOCATION",
        ),
        {
            "OBJECTID": (1, 2),
            "GlobalID": ("{fixture-cfpa_overnight_sites-0}", "{fixture-cfpa_overnight_sites-1}"),
            "NAME": ("Fixture cfpa overnight sites 0", "Fixture cfpa overnight sites 1"),
            "TYPE": ("campsite", "shelter"),
        },
    ),
    "external/cfpa_parking.geojson": (
        ("OBJECTID", "TYPE", "SPACES", "LOCATION", "DIR_LINK", "STATUS", "SHOW_PUBLIC", "AT", "NET", "NOTES", "GlobalID"),
        {
            "OBJECTID": (1, 2),
            "GlobalID": ("{fixture-cfpa_parking-0}", "{fixture-cfpa_parking-1}"),
            "LOCATION": ("Fixture cfpa parking 0", "Fixture cfpa parking 1"),
            "TYPE": ("shoulder", "lot"),
        },
    ),
    "external/amc_lodging.geojson": (
        (
            "FID",
            "Name",
            "Longitude",
            "Latitude",
            "Region",
            "Lodging_Ty",
            "Descriptio",
            "Amenities",
            "More_Info_",
            "Booking_Li",
            "Photo_Link",
            "Booking_Text",
            "Full_Description",
            "Lodging_Type",
            "Full_Amenities",
            "How_to_Access",
            "State",
        ),
        {"FID": (1, 2), "Name": ("Fixture amc lodging 0", "Fixture amc lodging 1"), "Lodging_Type": ("Campsite", "Hut")},
    ),
    "external/amc_destinations.geojson": (
        ("FID", "NAME", "TYPE", "ACCESS", "NOTES", "LAYER", "FEATUREID", "ELEV", "STAT", "SEASON", "TYPE_LABEL", "SHORT_NAME"),
        {
            "FID": (1, 2),
            "NAME": ("Fixture amc destinations 0", "Fixture amc destinations 1"),
            "TYPE": ("Tentsite - Primitive Camp", "Shelter"),
            "NOTES": ("fixture person", "fixture person"),
        },
    ),
    "external/amc_trailheads_and_parking.geojson": (
        (
            "FID",
            "OID_",
            "FolderPath",
            "Trail_Name",
            "Category",
            "Staff",
            "HandicapP",
            "Name",
            "Amenities",
            "Tread_Obst",
            "Obstrcut",
            "Signage",
            "Tr_Manager",
            "Tr_Website",
            "Comments",
            "Info",
            "Trail_Info",
            "Address",
        ),
        {
            "FID": (1, 2),
            "Name": ("Fixture amc trailheads and parking 0", "Fixture amc trailheads and parking 1"),
            "Category": ("Parking Lot", "Trailhead"),
            "Staff": ("fixture person", "fixture person"),
        },
    ),
    "external/amc_net_points_of_interest.geojson": (
        ("OBJECTID_1", "ObjectID", "TrailID", "ID", "Type", "Descriptio", "Easting", "Northing"),
        {
            "OBJECTID_1": (1, 2),
            "TrailID": ("Fixture trail 0", "Fixture trail 1"),
            "ID": (1, 2),
            "Descriptio": ("Fixture amc net points of interest 0", "Fixture amc net points of interest 1"),
            "Type": ("View", "Point of Interest"),
        },
    ),
    "external/amc_net_parking.geojson": (
        ("OBJECTID", "Trail", "Sub_Trail", "Location", "Spaces", "Directions", "Type", "Notes", "POINT_X", "POINT_Y"),
        {
            "OBJECTID": (1, 2),
            "Location": ("Fixture amc net parking 0", "Fixture amc net parking 1"),
            "Type": ("Road Shoulder", "Parking Lot"),
        },
    ),
    "external/alaska_trails_cabins_and_campsites.geojson": (
        ("OBJECTID", "Name", "Type", "Location", "LINK", "Carto_Show", "Region", "Route_Name", "SourceLink"),
        {
            "OBJECTID": (1, 2),
            "Name": ("Fixture alaska trails cabins and campsites 0", "Fixture alaska trails cabins and campsites 1"),
            "Type": ("Campground", "Cabin/Hut/Yurt"),
        },
    ),
    "external/alaska_trails_access_points.geojson": (
        (
            "OBJECTID",
            "Name",
            "Status",
            "Camping",
            "ParkingLot",
            "Fee",
            "FeePrice",
            "Kiosk",
            "Source1",
            "Source2",
            "Toilet",
            "Notes",
            "Park",
            "Community",
            "SeasonalType",
            "NeedsUpgrade",
            "Source1Name",
            "Source2Name",
            "OvernightParking",
            "AccessType",
            "MaxStay",
            "Route_Name",
        ),
        {
            "OBJECTID": (1, 2),
            "Name": ("Fixture alaska trails access points 0", "Fixture alaska trails access points 1"),
            "AccessType": ("Trailhead", "Parking Lot"),
        },
    ),
    "external/blm_recreation_sites.geojson": (
        (
            "OBJECTID",
            "FET_NAME",
            "DESCRIPTION",
            "FET_TYPE",
            "FET_SUBTYPE",
            "UNIT_NAME",
            "ADMIN_ST",
            "ADM_UNIT_CD",
            "WEB_LINK",
            "PHOTO_TEXT",
            "PHOTO_LINK",
            "PHOTO_THUMB",
            "LAT",
            "LONG",
            "SOURCE",
            "GlobalID",
            "Original_GlobalID",
        ),
        {
            "OBJECTID": (1, 2),
            "GlobalID": ("{fixture-blm_recreation_sites-0}", "{fixture-blm_recreation_sites-1}"),
            "FET_NAME": ("Fixture blm recreation sites 0", "Fixture blm recreation sites 1"),
            "FET_TYPE": (3, 4),
        },
    ),
    "external/nps_grsm_backcountry_shelters.geojson": (
        (
            "OBJECTID",
            "LOC_NAME",
            "IMARS_NAME",
            "RESERV",
            "ACCESS",
            "SHELTER_RESTRICTION",
            "CAPACITY",
            "BEARCABLES",
            "PULLEYPERSYSTEM",
            "TYPE",
            "TRAIL",
            "RANGER_DISTRICT",
            "PARKDISTRICT",
            "FACILITYTYPE",
            "FMSS_LOC",
            "NOTES",
            "ELEV_M",
            "ELEV_FT",
            "X_COORD",
            "Y_COORD",
            "LAT",
            "LON",
            "DMS_LAT",
            "DMS_LON",
            "DDM_LAT",
            "DDM_LON",
            "DATAACCESS",
            "MAPMETHOD",
            "SOURCEDATE",
            "XYACCURACY",
            "VALID_RESULT",
            "GlobalID",
        ),
        {
            "OBJECTID": (1, 2),
            "GlobalID": ("{fixture-nps_grsm_backcountry_shelters-0}", "{fixture-nps_grsm_backcountry_shelters-1}"),
            "LOC_NAME": ("Fixture nps grsm backcountry shelters 0", "Fixture nps grsm backcountry shelters 1"),
            "TYPE": ("Trail Shelter", "Trail Shelter"),
        },
    ),
    "external/nps_points_of_interest.geojson": (
        (
            "OBJECTID",
            "POINAME",
            "POIALTNAME",
            "MAPLABEL",
            "POITYPE",
            "POISTATUS",
            "PUBLICDISPLAY",
            "DATAACCESS",
            "ACCESSNOTES",
            "ORIGINATOR",
            "UNITCODE",
            "UNITNAME",
            "UNITTYPE",
            "GROUPCODE",
            "GROUPNAME",
            "REGIONCODE",
            "CREATEDATE",
            "EDITDATE",
            "POINTTYPE",
            "MAPMETHOD",
            "MAPSOURCE",
            "SOURCEDATE",
            "XYACCURACY",
            "GEOMETRYID",
            "FEATUREID",
            "FACLOCID",
            "FACASSETID",
            "IMLOCID",
            "OBSERVABLE",
            "ISEXTANT",
            "OPENTOPUBLIC",
            "ALTLANGNAME",
            "ALTLANG",
            "SEASONAL",
            "SEASDESC",
            "MAINTAINER",
            "NOTES",
        ),
        {
            "OBJECTID": (1, 2),
            "GEOMETRYID": ("fixture-nps_points_of_interest-0", "fixture-nps_points_of_interest-1"),
            "POINAME": ("Fixture nps points of interest 0", "Fixture nps points of interest 1"),
            "POITYPE": ("Parking Lot", "Campsite"),
        },
    ),
    "external/nj_open_space_points_of_interest.geojson": (
        (
            "OBJECTID",
            "FEATURE_NAME",
            "FEATURE_TYPE",
            "FEATURE_CLASS",
            "SITE_NAME",
            "FACILITY",
            "FACILITY_LABEL",
            "LAND_MANAGER",
            "LON_DMS",
            "LAT_DMS",
            "LON_DD",
            "LAT_DD",
            "X",
            "Y",
            "OWNERSHIP",
            "MAP_DISPLAY",
            "DISPLAY_SCALE",
            "AGO_SYMBOL",
            "PHOTO",
            "SCRCE_TYPE",
            "SCRCE_DATE",
            "OPNS_STAT",
            "GLOBALID",
        ),
        {
            "OBJECTID": (1, 2),
            "GLOBALID": ("{fixture-nj_open_space_points_of_interest-0}", "{fixture-nj_open_space_points_of_interest-1}"),
            "FEATURE_NAME": ("Fixture nj open space points of interest 0", "Fixture nj open space points of interest 1"),
            "FEATURE_TYPE": ("Parking", "Unpaved Parking"),
        },
    ),
    "external/pasda_state_park_buildings.geojson": (
        (
            "OBJECTID",
            "YEAR_BUILT",
            "BUILDING_NUMBER",
            "TYPE1",
            "CONDITION",
            "USE1",
            "USE2",
            "USE3",
            "USE4",
            "USE5",
            "COMMON_NAME",
            "ICSORG",
            "LATITUDE",
            "LONGITUDE",
            "COUNTY_NAME",
            "COUNTY_NUMBER",
            "MUNICIPALITY",
            "NUMBER_OF_FLOORS",
            "MONTHS_USE",
            "NUMBER_OF_ELEVATORS",
            "TOTAL_SQUARE_FEET",
            "CONSTRUCTION_COST",
            "CONTENT_VALUE",
            "REPLACEMENT_VALUE",
            "EXTERIOR_CONSTRUCTION",
            "ROOF_TYPE",
            "ROOF_PITCH",
            "ROOF_SQUARE_FEET",
            "PROJ_ROOF_REPLACEMENT_DATE",
            "HAS_ELECTRIC",
            "ELECTRIC_AMPS",
            "ELECTRIC_VOLTS",
            "ELECTRIC_PHASE",
            "HEATING_SYSTEM_TYPE_1",
            "HEATING_SYSTEM_TYPE_2",
            "HEATING_SYSTEM_TYPE_3",
            "WATER_TYPE1",
            "WATER_TYPE2",
            "WATER_TYPE3",
            "SEWAGE_TYPE1",
            "SEWAGE_TYPE2",
            "SEWAGE_TYPE3",
            "COMMENTS",
            "IS_PARK_MAINTAINED",
            "IS_PARK_OWNED",
            "IS_LEASED_OUT",
            "IS_ADA_ACCESSIBLE",
            "IN_A_FLOODPLAIN",
            "IS_HISTORIC_ELIGIBLE",
            "ON_HISTORIC_REGISTRY",
            "HAS_BACKUP_POWER",
            "HAS_INTERNET",
            "HAS_FIRE_DETECTION",
            "HAS_FIRE_ALARM",
            "HAS_SPRINKLERS",
            "HAS_SECURITY_SYSTEM",
            "EXPOSURE_TO_OTHER_STRUCTURES",
            "Park",
            "A_C_SOURCE_TYPE_1",
            "A_C_SOURCE_TYPE_2",
            "A_C_SOURCE_TYPE_3",
            "A_C_SYSTEM_TYPE_1",
            "A_C_SYSTEM_TYPE_2",
            "A_C_SYSTEM_TYPE_3",
            "ALTERNATIVE_ENERGY_TYPE",
            "LAST_BUILDING_REN_DATE",
            "DED_ELEC_METERS",
            "CONDITIONED_SQ_FT",
            "CONSTRUCTION_TYPE",
            "HEATING_SOURCE_TYPE_1",
            "HEATING_SOURCE_TYPE_2",
            "HEATING_SOURCE_TYPE_3",
            "LAND_BUILD_STATUS",
            "OCC_PERMIT",
            "UNCOND_SQ_FT",
            "Flagged",
            "Check_Field",
            "Status",
            "OWNER",
            "ROOF_INSTALL_YEAR",
            "A_C_THERMOSTAT_1",
            "A_C_THERMOSTAT_2",
            "A_C_THERMOSTAT_3",
            "HEATING_THERMOSTAT_1",
            "HEATING_THERMOSTAT_2",
            "HEATING_THERMOSTAT_3",
            "TYPE2",
            "TYPE3",
            "TYPE4",
            "TYPE5",
            "COMP_METHOD",
            "COMP_TIME",
            "COMP_TRAVEL",
            "PROJ_ROOF_REPLACEMENT_YEAR",
            "Address_911",
            "Address911_L1",
            "Address911_L2",
            "Address911_City",
            "Address911_Zip",
            "Mail_Address",
            "MailAdd_L1",
            "MailAdd_L2",
            "MailAdd_City",
            "MailAdd_Zip",
            "GlobalID",
            "Round1QAQCStatus",
            "Round1QAQCBy",
            "Round1QAQCComments",
            "Round1QAQCDate",
            "Round2QAQCStatus",
            "Round2QAQCBy",
            "Round2QAQCComments",
            "Round2QAQCDate",
            "CreatedBy",
            "CreatedDate",
            "LastEditedBy",
            "LastEditedDate",
            "Archived",
            "VisiblePublic",
            "ArchivedReason",
            "SubmittedBy",
            "SubmittedDate",
            "OPS_Visible",
            "CampingMap_Visible",
        ),
        {
            "OBJECTID": (1, 2),
            "GlobalID": ("{fixture-pasda_state_park_buildings-0}", "{fixture-pasda_state_park_buildings-1}"),
            "COMMON_NAME": ("Fixture pasda state park buildings 0", "Fixture pasda state park buildings 1"),
            "USE1": ("Cabin – Rustic", "Restroom"),
            "Round1QAQCBy": ("fixture person", "fixture person"),
            "Round2QAQCBy": ("fixture person", "fixture person"),
            "SubmittedBy": ("fixture person", "fixture person"),
            "Round1QAQCComments": ("fixture person", "fixture person"),
            "Round2QAQCComments": ("fixture person", "fixture person"),
            "COMMENTS": ("fixture person", "fixture person"),
        },
    ),
    "external/pasda_state_forest_campsites.geojson": (
        (
            "OBJECTID",
            "Name",
            "DistrictNumber",
            "Source",
            "Type",
            "ADA",
            "FireRing",
            "PicnicTables",
            "TrailerAccess",
            "NumberVehicles",
            "Permit",
            "Water",
            "HitchingPost",
            "Notes",
            "Latitude",
            "Longitude",
            "CreatedBy",
            "CreatedDate",
            "LastEditedBy",
            "LastEditedDate",
            "GlobalID",
            "Latrines",
            "CampingArea",
            "Description",
            "GroupCamping",
            "ShowOnPublicMap",
            "ParkResForestName",
            "ParkRes_ParkID",
            "ParkRes_SiteID",
        ),
        {
            "OBJECTID": (1, 2),
            "GlobalID": ("{fixture-pasda_state_forest_campsites-0}", "{fixture-pasda_state_forest_campsites-1}"),
            "Name": ("Fixture pasda state forest campsites 0", "Fixture pasda state forest campsites 1"),
            "Type": ("Motorized", "Primitive"),
        },
    ),
    "external/pasda_explore_pa_trail_access.geojson": (
        (
            "OBJECTID_1",
            "OBJECTID",
            "NAME01",
            "NAME02",
            "NAME03",
            "COUNTY",
            "ADA_ACCESS",
            "UPDATE_",
            "COMMENTS",
            "SUBTYPE_CO",
            "ACCT_ID",
            "LATITUDE",
            "LONGITUDE",
            "TRAILID",
        ),
        {
            "OBJECTID_1": (1, 2),
            "NAME01": ("Fixture pasda explore pa trail access 0", "Fixture pasda explore pa trail access 1"),
            "SUBTYPE_CO": (1, 9),
            "COMMENTS": ("fixture person", "fixture person"),
        },
    ),
    "external/pasda_state_park_amenities.geojson": (
        (
            "OBJECTID_1",
            "OBJECTID",
            "ICSORG",
            "PARK_WEB_L",
            "PARK_DOWNL",
            "PARK_MAP_L",
            "COUNTY",
            "NAVIGATION",
            "NAVIGATI_1",
            "NAVIGATI_2",
            "HAS_FACEBO",
            "HAS_TWITTE",
            "FACEBOOK_L",
            "TWITTER_LI",
            "MOBILE_FAC",
            "MOBILE_TWI",
            "FLICKR_LIN",
            "GROVES",
            "PAVILIONS",
            "CAMPING",
            "PET_CAMPIN",
            "ORG_GROUP_",
            "ORGANIZED_",
            "YURTS",
            "WALLED_TEN",
            "CABINS",
            "CAMPING_CO",
            "DUMP_STATI",
            "EDUCATIONA",
            "ORIENTEERI",
            "SIGHTSEEIN",
            "HISTORIC_P",
            "NATURAL_AR",
            "SCENIC_VIE",
            "WILDLIFE_W",
            "THEATERS",
            "AMPHITHEAT",
            "BIG_TREES",
            "FISHING",
            "ICE_FISHIN",
            "ICE_BOATIN",
            "ICE_SKATIN",
            "CROSS_COUN",
            "DOWNHILL_S",
            "SNOWMOBILE",
            "SLEDDING",
            "SCUBA_DIVI",
            "SWIMMING",
            "PICNICKING",
            "HUNTING",
            "SAILING",
            "BOATING",
            "BOAT_MOORI",
            "ELECTRIC_B",
            "MOTOR_BOAT",
            "WHITE_WATE",
            "BOAT_LAUNC",
            "BOAT_RENTA",
            "CANOE_KAYA",
            "ROLLER_BLA",
            "GOLF",
            "DISC_GOLF",
            "HIKING",
            "BACKPACKIN",
            "ROCK_CLIMB",
            "HORSEBACK_",
            "BIKING",
            "MOUNTAIN_B",
            "BIKE_RENTA",
            "ADA_CAMPIN",
            "ADA_LODGIN",
            "ADA_BACKPA",
            "ADA_ORGANI",
            "ADA_ORGA_1",
            "ADA_PICNIC",
            "ADA_PICN_1",
            "ADA_HUNTIN",
            "ADA_FISHIN",
            "ADA_DISC_G",
            "ADA_GOLFIN",
            "ADA_EDUCAT",
            "ADA_HIKING",
            "ADA_SWIMMI",
            "ADA_BOATIN",
            "ADA_WILDLI",
            "ADA_SITE_S",
            "ADA_THEATE",
            "ADA_AMPHIT",
            "ADA_HISTOR",
            "ADA_DOWNHI",
            "GIS_ACRES",
            "WEB_DESCRI",
            "ADDRESS",
            "CITY",
            "STATE",
            "ZIP",
            "PHONE",
            "EMAIL",
            "MANAGER",
            "PARK_REGIO",
            "GEOCACHE",
            "GEOCACHE_L",
            "PARK_NAME",
            "CW_STREAM",
            "CW_LAKE",
            "WW_STREAM",
            "WW_LAKE",
            "ADA_FISH_1",
            "SWIM_BEACH",
            "SWIM_POOL",
            "WEDDING_OU",
            "WEDDING_IN",
            "PICNICKI_1",
            "PAVILIONS_",
            "AWO_ID",
            "WE_PARK",
        ),
        {
            "OBJECTID_1": (1, 2),
            "ICSORG": ("fixture-pasda_state_park_amenities-0", "fixture-pasda_state_park_amenities-1"),
            "PARK_NAME": ("Fixture pasda state park amenities 0", "Fixture pasda state park amenities 1"),
        },
    ),
    "external/pasda_geoheritage_features.geojson": (
        (
            "OBJECTID",
            "SiteName",
            "Description",
            "GeneralDescription",
            "ScientificName",
            "CommonName",
            "ScientificNameSecondary",
            "CommonNameSecondary",
            "RationalForDesignation",
            "SocialSignificance",
            "Bedrock",
            "EG7",
            "TrailOfGeology",
            "ParkGuide",
            "PublicLand",
            "References",
        ),
        {"OBJECTID": (1, 2), "SiteName": ("Fixture pasda geoheritage features 0", "Fixture pasda geoheritage features 1")},
    ),
    "external/ct_deep_trail_access.geojson": (
        (
            "OBJECTID",
            "TRAILSYSID",
            "SITENAME",
            "SITEADDR",
            "TOWNNO",
            "PARKING",
            "TRAILRPKNG",
            "RESTROOM",
            "FOOD",
            "WATER",
            "OPENWHEN",
            "PARKINGNUM",
        ),
        {
            "OBJECTID": (1, 2),
            "SITENAME": ("Fixture ct deep trail access 0", "Fixture ct deep trail access 1"),
            "PARKING": ("Non Parking", "Parking Lot"),
        },
    ),
    "external/ct_deep_trail_interest.geojson": (
        ("OBJECTID", "TRAILSYSID", "INTEREST", "MAPLABEL"),
        {
            "OBJECTID": (1, 2),
            "MAPLABEL": ("Fixture ct deep trail interest 0", "Fixture ct deep trail interest 1"),
            "INTEREST": ("Point of Interest", "Scenic View"),
        },
    ),
    "external/ma_dcr_blue_hills_parking.geojson": (
        (
            "FID",
            "DISPLAY",
            "NAME",
            "TYPE",
            "COMMENTS",
            "PRKNGSURF",
            "PRKNGCOND",
            "PRKNGCURBM",
            "PRKNGDTYPE",
            "PRKNGHANDI",
            "PRKNGBOAT",
            "PRKNGCAPAC",
            "PRKNGESIZE",
            "PRKNGCURBS",
            "PRKNGLINED",
            "PRKNGSWALE",
            "PRKNGMNT_P",
            "PRKNGMNT_C",
            "RTRNOLENGT",
            "RTRNOWIDTH",
            "RTRNOSURF",
            "RTRNALENGT",
            "RTRNAWIDTH",
            "RTRNASURF",
            "SOURCE",
            "RMP_Name",
            "FACIL_CODE",
            "LONGITUDE",
            "LATITUDE",
            "tempID",
            "Section",
            "Elev_m_Li",
            "Elev_ft_Li",
            "GPS_DATE",
            "GPS_TIME",
            "UNIQUE_ID",
            "GlobalID",
        ),
        {
            "FID": (1, 2),
            "GlobalID": ("{fixture-ma_dcr_blue_hills_parking-0}", "{fixture-ma_dcr_blue_hills_parking-1}"),
            "NAME": ("Fixture ma dcr blue hills parking 0", "Fixture ma dcr blue hills parking 1"),
            "TYPE": ("Parking Area", "Road Turn Out"),
        },
    ),
    "external/ma_dcr_blue_hills_intersections.geojson": (
        (
            "FID",
            "Int_2020Ma",
            "INT_NUMBER",
            "Int_1984Ma",
            "Int_2016Ma",
            "Int_2018Ma",
            "IntNumSign",
            "Int_GPS",
            "Int_LoniAn",
            "COMMENTS",
            "BH_Section",
            "Subsection",
            "Num_Source",
            "Loc_Source",
            "Snapped",
            "Status",
            "FieldCheck",
            "TYPE",
            "NUM",
            "INTSIGNAGE",
            "INTSIGNDIR",
            "FACIL_CODE",
            "LONGITUDE",
            "LATITUDE",
            "GPS_DATE",
            "GPS_TIME",
            "UNIQUE_ID",
            "SOURCE",
            "Loc_Descr",
            "Int_199xMa",
            "Elev_ft_Li",
            "Int_2019Ma",
            "USNG_1m",
            "UTM_19T_X",
            "UTM_19T_Y",
            "GlobalID",
        ),
        {
            "FID": (1, 2),
            "GlobalID": ("{fixture-ma_dcr_blue_hills_intersections-0}", "{fixture-ma_dcr_blue_hills_intersections-1}"),
            "INT_NUMBER": ("Fixture ma dcr blue hills intersections 0", "Fixture ma dcr blue hills intersections 1"),
            "TYPE": ("Intersection", "Trailhead"),
        },
    ),
    "external/tn_state_parks_hiking_assets.geojson": (
        ("OBJECTID", "Park", "Asset_Type", "Name", "GlobalID"),
        {
            "OBJECTID": (1, 2),
            "GlobalID": ("{fixture-tn_state_parks_hiking_assets-0}", "{fixture-tn_state_parks_hiking_assets-1}"),
            "Name": ("Fixture tn state parks hiking assets 0", "Fixture tn state parks hiking assets 1"),
            "Asset_Type": ("Parking", "Trailhead"),
        },
    ),
    "external/tn_state_parks_campgrounds.geojson": (
        (
            "OBJECTID",
            "CAMPGRND_NAME",
            "CAMPGRND_TYPE",
            "CAMPGROUND_UID",
            "TSP_UID_1",
            "ORIG_FID",
            "ItinioID",
            "Status",
            "Reservable",
            "Website_Show",
            "GlobalID",
        ),
        {
            "OBJECTID": (1, 2),
            "GlobalID": ("{fixture-tn_state_parks_campgrounds-0}", "{fixture-tn_state_parks_campgrounds-1}"),
            "CAMPGRND_NAME": ("Fixture tn state parks campgrounds 0", "Fixture tn state parks campgrounds 1"),
            "CAMPGRND_TYPE": ("Backcountry Camping", "Mixed RV Tent"),
        },
    ),
    "external/tn_state_parks_campsites.geojson": (
        (
            "OBJECTID",
            "TSP_CMPSTE_UID",
            "TSP_CMPGRD_UID",
            "SITE_NO",
            "SITE_NAME",
            "ITINIO_ID",
            "TSP_UID",
            "PARK_NAME",
            "GlobalID",
            "CAMPGRND_TYPE",
        ),
        {
            "OBJECTID": (1, 2),
            "GlobalID": ("{fixture-tn_state_parks_campsites-0}", "{fixture-tn_state_parks_campsites-1}"),
            "SITE_NAME": ("Fixture tn state parks campsites 0", "Fixture tn state parks campsites 1"),
            "CAMPGRND_TYPE": ("Backcountry Campsite", "Primitive"),
        },
    ),
    "external/cumberland_trail_trailheads.geojson": (
        (
            "OBJECTID",
            "Name",
            "Ownership",
            "Address",
            "Capacity",
            "Surface",
            "Dimension",
            "Status",
            "County",
            "LatDD",
            "LongDD",
            "Sequence",
            "Information",
        ),
        {
            "OBJECTID": (1, 2),
            "Name": ("Fixture cumberland trail trailheads 0", "Fixture cumberland trail trailheads 1"),
            "Status": ("Trailhead Open", "Non CT Trailhead"),
            "Ownership": ("fixture person", "fixture person"),
        },
    ),
    "external/cumberland_trail_campsites.geojson": (
        ("OBJECTID_1", "Name", "Location", "LatDD", "LongDD", "Comments", "SignUp", "sequence"),
        {"OBJECTID_1": (1, 2), "Name": ("Fixture cumberland trail campsites 0", "Fixture cumberland trail campsites 1")},
    ),
    "external/cumberland_trail_natural_features.geojson": (
        ("OBJECTID", "Name", "County", "LatDD", "LongDD", "Comments"),
        {
            "OBJECTID": (1, 2),
            "Name": ("Fixture cumberland trail natural features 0", "Fixture cumberland trail natural features 1"),
        },
    ),
    "external/usfws_refuge_property_points.geojson": (
        (
            "OBJECTID",
            "CCCODE",
            "Lit",
            "OrgCode",
            "Cmplx_Name",
            "OrgName",
            "Dvsn_Name",
            "Unit_Name",
            "Subunit_Name",
            "RSL_Type",
            "StateAbbr",
            "Region",
            "Int_Region",
            "Origin",
            "Prop_Name",
            "Prop_Type",
            "Owner",
            "Public_Use",
            "Han_Access",
            "Condition",
            "Assess_Dt",
            "Asset_Num",
            "Comp_Num",
            "Comments",
            "Status",
            "Public_View",
            "GlobalID",
            "CreationDate",
            "Creator",
            "EditDate",
            "Editor",
            "GSAnum",
            "ShowHunt",
        ),
        {
            "OBJECTID": (1, 2),
            "GlobalID": ("{fixture-usfws_refuge_property_points-0}", "{fixture-usfws_refuge_property_points-1}"),
            "Prop_Name": ("Fixture usfws refuge property points 0", "Fixture usfws refuge property points 1"),
            "Prop_Type": ("40660100", "40750700"),
            "Creator": ("fixture person", "fixture person"),
            "Editor": ("fixture person", "fixture person"),
        },
    ),
    "external/usfws_refuge_access_points.geojson": (
        (
            "OBJECTID",
            "CCCODE",
            "Lit",
            "OrgCode",
            "Cmplx_Name",
            "OrgName",
            "Dvsn_Name",
            "Unit_Name",
            "Subunit_Name",
            "RSL_Type",
            "StateAbbr",
            "Region",
            "Int_Region",
            "Origin",
            "Gate_Name",
            "Owner",
            "Acc_Type",
            "Public_Use",
            "Gate_Type",
            "Condition",
            "Assess_Dt",
            "Asset_Num",
            "Comp_Num",
            "Comments",
            "Status",
            "Public_View",
            "Asset_Code",
            "GlobalID",
            "CreationDate",
            "Creator",
            "EditDate",
            "Editor",
        ),
        {
            "OBJECTID": (1, 2),
            "GlobalID": ("{fixture-usfws_refuge_access_points-0}", "{fixture-usfws_refuge_access_points-1}"),
            "Gate_Name": ("Fixture usfws refuge access points 0", "Fixture usfws refuge access points 1"),
            "Acc_Type": ("Trailhead", "Field Approach"),
            "Creator": ("fixture person", "fixture person"),
            "Editor": ("fixture person", "fixture person"),
        },
    ),
    "external/usgs_structures_campgrounds.geojson": (
        (
            "OBJECTID",
            "PERMANENT_IDENTIFIER",
            "SOURCE_FEATUREID",
            "SOURCE_DATASETID",
            "SOURCE_DATADESC",
            "SOURCE_ORIGINATOR",
            "LOADDATE",
            "FTYPE",
            "FCODE",
            "NAME",
            "POINTLOCATIONTYPE",
            "ADMINTYPE",
            "ADDRESSBUILDINGNAME",
            "ADDRESS",
            "CITY",
            "STATE",
            "ZIPCODE",
            "GNIS_ID",
            "GLOBALID",
        ),
        {
            "OBJECTID": (1, 2),
            "PERMANENT_IDENTIFIER": ("fixture-usgs_structures_campgrounds-0", "fixture-usgs_structures_campgrounds-1"),
            "GLOBALID": ("{fixture-usgs_structures_campgrounds-0}", "{fixture-usgs_structures_campgrounds-1}"),
            "NAME": ("Fixture usgs structures campgrounds 0", "Fixture usgs structures campgrounds 1"),
        },
    ),
    "external/usgs_structures_trailheads.geojson": (
        (
            "OBJECTID",
            "PERMANENT_IDENTIFIER",
            "SOURCE_FEATUREID",
            "SOURCE_DATASETID",
            "SOURCE_DATADESC",
            "SOURCE_ORIGINATOR",
            "LOADDATE",
            "FTYPE",
            "FCODE",
            "NAME",
            "POINTLOCATIONTYPE",
            "ADMINTYPE",
            "ADDRESSBUILDINGNAME",
            "ADDRESS",
            "CITY",
            "STATE",
            "ZIPCODE",
            "GNIS_ID",
            "GLOBALID",
        ),
        {
            "OBJECTID": (1, 2),
            "PERMANENT_IDENTIFIER": ("fixture-usgs_structures_trailheads-0", "fixture-usgs_structures_trailheads-1"),
            "GLOBALID": ("{fixture-usgs_structures_trailheads-0}", "{fixture-usgs_structures_trailheads-1}"),
            "NAME": ("Fixture usgs structures trailheads 0", "Fixture usgs structures trailheads 1"),
        },
    ),
    "external/usgs_structures_cabins.geojson": (
        (
            "OBJECTID",
            "PERMANENT_IDENTIFIER",
            "SOURCE_FEATUREID",
            "SOURCE_DATASETID",
            "SOURCE_DATADESC",
            "SOURCE_ORIGINATOR",
            "LOADDATE",
            "FTYPE",
            "FCODE",
            "NAME",
            "POINTLOCATIONTYPE",
            "ADMINTYPE",
            "ADDRESSBUILDINGNAME",
            "ADDRESS",
            "CITY",
            "STATE",
            "ZIPCODE",
            "GNIS_ID",
            "GLOBALID",
        ),
        {
            "OBJECTID": (1, 2),
            "PERMANENT_IDENTIFIER": ("fixture-usgs_structures_cabins-0", "fixture-usgs_structures_cabins-1"),
            "GLOBALID": ("{fixture-usgs_structures_cabins-0}", "{fixture-usgs_structures_cabins-1}"),
            "NAME": ("Fixture usgs structures cabins 0", "Fixture usgs structures cabins 1"),
        },
    ),
    "external/usgs_structures_shelters.geojson": (
        (
            "OBJECTID",
            "PERMANENT_IDENTIFIER",
            "SOURCE_FEATUREID",
            "SOURCE_DATASETID",
            "SOURCE_DATADESC",
            "SOURCE_ORIGINATOR",
            "LOADDATE",
            "FTYPE",
            "FCODE",
            "NAME",
            "POINTLOCATIONTYPE",
            "ADMINTYPE",
            "ADDRESSBUILDINGNAME",
            "ADDRESS",
            "CITY",
            "STATE",
            "ZIPCODE",
            "GNIS_ID",
            "GLOBALID",
        ),
        {
            "OBJECTID": (1, 2),
            "PERMANENT_IDENTIFIER": ("fixture-usgs_structures_shelters-0", "fixture-usgs_structures_shelters-1"),
            "GLOBALID": ("{fixture-usgs_structures_shelters-0}", "{fixture-usgs_structures_shelters-1}"),
            "NAME": ("Fixture usgs structures shelters 0", "Fixture usgs structures shelters 1"),
        },
    ),
    "external/usgs_structures_ranger_stations.geojson": (
        (
            "OBJECTID",
            "PERMANENT_IDENTIFIER",
            "SOURCE_FEATUREID",
            "SOURCE_DATASETID",
            "SOURCE_DATADESC",
            "SOURCE_ORIGINATOR",
            "LOADDATE",
            "FTYPE",
            "FCODE",
            "NAME",
            "POINTLOCATIONTYPE",
            "ADMINTYPE",
            "ADDRESSBUILDINGNAME",
            "ADDRESS",
            "CITY",
            "STATE",
            "ZIPCODE",
            "GNIS_ID",
            "GLOBALID",
        ),
        {
            "OBJECTID": (1, 2),
            "PERMANENT_IDENTIFIER": ("fixture-usgs_structures_ranger_stations-0", "fixture-usgs_structures_ranger_stations-1"),
            "GLOBALID": ("{fixture-usgs_structures_ranger_stations-0}", "{fixture-usgs_structures_ranger_stations-1}"),
            "NAME": ("Fixture usgs structures ranger stations 0", "Fixture usgs structures ranger stations 1"),
        },
    ),
    "external/usgs_gnis_springs.geojson": (
        (
            "OBJECTID",
            "gaz_id",
            "gaz_name",
            "gaz_featureclass",
            "fcode",
            "state_alpha",
            "county_name",
            "objectid_1",
            "isunknowncoords",
        ),
        {
            "OBJECTID": (1, 2),
            "gaz_id": (1, 2),
            "county_name": ("Fixture County 0", "Fixture County 1"),
            "gaz_name": ("Fixture usgs gnis springs 0", "Fixture usgs gnis springs 1"),
        },
    ),
    "external/nc_state_parks_points.geojson": (
        ("FID", "PK_TYPE", "NAME", "ABBR", "FullName", "add1", "add2", "city", "county", "email", "ophone", "zip", "Website"),
        {
            "FID": (1, 2),
            "NAME": ("Fixture nc state parks points 0", "Fixture nc state parks points 1"),
            "PK_TYPE": ("SPA", "SNA"),
            "ophone": ("fixture person", "fixture person"),
        },
    ),
    "external/ridgetrail_campsites.geojson": (
        (
            "COUNTY",
            "LATITUDE",
            "LONGITUDE",
            "CAMP",
            "TYPE",
            "MANAGER",
            "PARK",
            "ADDRESS",
            "WEBSITE",
            "NOTES",
            "FID",
            "STATUS",
            "GlobalID",
        ),
        {
            "FID": (1, 2),
            "GlobalID": ("{fixture-ridgetrail_campsites-0}", "{fixture-ridgetrail_campsites-1}"),
            "CAMP": ("Fixture ridgetrail campsites 0", "Fixture ridgetrail campsites 1"),
            "TYPE": ("Group", "Campground"),
        },
    ),
    "external/sbts_connected_community_trailheads.geojson": (
        (
            "OBJECTID_1",
            "title",
            "TH__",
            "TH_Name",
            "TH_Category",
            "Land_Ownership",
            "Location",
            "Lat",
            "Lon",
            "Amenities_Existing",
            "Additional_Suggested_Amenities",
            "Site_Visit_Conducted",
            "Design_Mockup",
            "Comments",
            "Signage_Design",
            "ObjectID",
        ),
        {
            "OBJECTID_1": (1, 2),
            "TH_Name": ("Fixture sbts connected community trailheads 0", "Fixture sbts connected community trailheads 1"),
            "TH_Category": ("backcountry TH, motorized", "Downtown TH, non motorized"),
            "Comments": ("fixture person", "fixture person"),
        },
    ),
    "external/cotrex_trailheads.geojson": (
        (
            "FID",
            "feature_id",
            "place_id",
            "name",
            "alt_name",
            "type",
            "bathrooms",
            "fee",
            "water",
            "manager",
            "INPUT_DATE",
            "EDIT_DATE",
            "winter_act",
            "GlobalID",
        ),
        {
            "FID": (1, 2),
            "feature_id": ("fixture-cotrex_trailheads-0", "fixture-cotrex_trailheads-1"),
            "GlobalID": ("{fixture-cotrex_trailheads-0}", "{fixture-cotrex_trailheads-1}"),
            "name": ("Fixture cotrex trailheads 0", "Fixture cotrex trailheads 1"),
            "type": ("Trailhead", "Interpretive Trailhead"),
        },
    ),
    "external/cpw_facilities.geojson": (
        (
            "FID",
            "PROPNAME",
            "PROP_TYPE",
            "PARK_ID",
            "FAC_ID",
            "FAC_TYPE",
            "TYPE_DETAI",
            "HANDI_ACCE",
            "FAC_NAME",
            "CONDITION",
            "SITE_COUNT",
            "COUNT_TYPE",
            "PHOTO",
            "MGMT_AUTH",
            "WINTER_STA",
            "ST_ADDRESS",
            "SOURCE",
            "COMMENTS",
            "EDIT_DATE",
            "RuleID",
            "RuleID_1",
            "RuleID_2",
            "RuleID_HC",
            "SYM_CHAR",
            "COLL_DATE",
            "ORG_OID",
            "TempDetail",
            "Input_Date",
            "GlobalID",
            "d_PROP_TYP",
            "d_FAC_TYPE",
            "d_TYPE_DET",
            "d_HANDI_AC",
            "d_CONDITIO",
            "d_MGMT_AUT",
            "d_WINTER_S",
            "d_SOURCE",
            "d_SYM_CHAR",
            "GlobalID_2",
        ),
        {
            "FID": (1, 2),
            "GlobalID_2": ("{fixture-cpw_facilities-0}", "{fixture-cpw_facilities-1}"),
            "FAC_NAME": ("Fixture cpw facilities 0", "Fixture cpw facilities 1"),
            "d_FAC_TYPE": ("Parking", "Info Source"),
            "COMMENTS": ("fixture person", "fixture person"),
        },
    ),
    "external/utah_trailheads.geojson": (
        (
            "OBJECTID",
            "PrimaryName",
            "TrailheadID",
            "Features",
            "PrimaryMaintenance",
            "SeasonalRestriction",
            "InfoURL",
            "Comments",
            "DataSource",
            "LastUpdate",
        ),
        {"OBJECTID": (1, 2), "PrimaryName": ("Fixture utah trailheads 0", "Fixture utah trailheads 1")},
    ),
    "external/utah_state_park_campsites.geojson": (
        ("OBJECTID", "Park_ID", "Park_Name", "Site_ID", "Site_Code", "Site_Name", "Latitude", "Longitude", "x", "y"),
        {
            "OBJECTID": (1, 2),
            "Site_ID": ("fixture-utah_state_park_campsites-0", "fixture-utah_state_park_campsites-1"),
            "Site_Name": ("Fixture utah state park campsites 0", "Fixture utah state park campsites 1"),
        },
    ),
    "external/utah_highest_peaks.geojson": (
        ("OBJECTID", "NAME", "TYPE", "ELEVATION", "QUAD_NAME", "RANK", "COMBINED", "COUNTY"),
        {"OBJECTID": (1, 2), "NAME": ("Fixture utah highest peaks 0", "Fixture utah highest peaks 1")},
    ),
    "external/black_hills_trailheads.geojson": (
        ("OBJECTID", "NAME"),
        {"OBJECTID": (1, 2), "NAME": ("Fixture black hills trailheads 0", "Fixture black hills trailheads 1")},
    ),
    "external/black_hills_parking.geojson": (
        ("OBJECTID", "LOCATION"),
        {"OBJECTID": (1, 2), "LOCATION": ("Fixture black hills parking 0", "Fixture black hills parking 1")},
    ),
}


# --- decision 54 wave 3, section C: the clubs' content feeds and APIs (2026-10-04) --------------------
#
# Podcast feeds (extract/_content.py's PodcastEpisodes), NPS's content lists (NpsContent) and the TEHCC wiki's
# hike and challenge templates (MediawikiTemplatePages) are answered from conditions/json_apis/<key>.json, as
# the JSON API notice sources are; the WordPress hike sources from conditions/<key>.json, as the clubs'
# WordPress notices are. THE NAMES ARE MEASURED: every tag, field and route is one the live source served to
# section C's reads of 2026-10-04 (each row's sources.json `notes`). EVERY VALUE IS INVENTED and starts with
# 'Fixture'. Each feed item carries the person tags PodcastEpisodes leaves out (itunes:author, RSS <author>,
# dc:creator, podcast:person), and a row whose sources.json `person_fields` lists prose carries a fixture
# number in it, so the tests can see neither land.

SOURCES_PATH = Path(__file__).parent / "sources.json"
RSS = "application/rss+xml; charset=utf-8"


@functools.cache
def _registry_entries() -> dict[str, dict]:
    return {entry["key"]: entry for entry in json.loads(SOURCES_PATH.read_text())["sources"]}


def _registry_entry(key: str) -> dict:
    """A sources.json row by key; StopIteration for a key the registry does not hold, as next() would raise."""
    if key not in _registry_entries():
        raise StopIteration(key)
    return _registry_entries()[key]


def _split(url: str) -> tuple[str, dict]:
    """A URL as fixture mode's router matches it: the address without its query, and the query's parameters."""
    base, _, query = url.partition("?")
    return base, dict(part.split("=", 1) for part in query.split("&") if part)


#: The podcast_feed rows PodcastEpisodes reads (extract/_content.py), each answered with CONTENT_FEED_ITEMS items.
CONTENT_FEED_KEYS = (
    "dec_does_what_podcast",
    "mohonk_walk_back_in_time_podcast",
    "nycparks_covid_oral_history_podcast",
    "njdep_discover_dep_podcast",
    "usfs_forest_focus_podcast",
    "usfs_forestcast_podcast",
    "blm_on_the_ground_podcast",
    "cpw_colorado_outdoors_podcast",
    "wdnr_wild_wisconsin_podcast",
    "silvicast_podcast",
    "amc_unlikely_stories_podcast",
    "something_wild_podcast",
    "trustees_on_the_coast_podcast",
    "sbts_dirt_magic_podcast",
    "audible_mount_diablo_podcast",
    "shta_blazing_trail_podcast",
    "usgs_outstanding_in_the_field_podcast",
    "nps_park_postcards_goga_podcast",
    "usfws_future_of_conservation_podcast",
)
CONTENT_FEED_ITEMS = 2


def _podcast_feed(key: str) -> str:
    """RSS 2.0 as the podcast hosts served it on 2026-10-04: iTunes, content, Dublin Core and Podcasting 2.0 tags."""
    items = "".join(
        f"<item><title>Fixture Episode {i}</title><itunes:title>Fixture Episode {i}</itunes:title>"
        f'<guid isPermaLink="false">fixture-{key}-{i}</guid><link>https://fixture.example.org/{key}/{i}/</link>'
        f"<pubDate>Mon, 2{i} Sep 2026 14:00:00 +0000</pubDate>"
        f"<description><![CDATA[<p>Fixture notes {i}, with a fixture number that never loads where the row's "
        f"person_fields list the prose: 555-0100.</p>]]></description>"
        f"<content:encoded><![CDATA[<p>Fixture notes {i}.</p>]]></content:encoded>"
        f"<itunes:summary>Fixture notes {i}.</itunes:summary>"
        f'<enclosure url="https://fixture.example.org/{key}/{i}.mp3" length="{1000 + i}" type="audio/mpeg"/>'
        f"<itunes:duration>00:3{i}:00</itunes:duration><itunes:episode>{i}</itunes:episode>"
        f'<itunes:explicit>false</itunes:explicit><itunes:image href="https://fixture.example.org/{key}/{i}.jpg"/>'
        f"<itunes:author>Fixture Person, Fixture Guest</itunes:author><author>fixture.person@example.org</author>"
        f'<dc:creator>Fixture Person</dc:creator><podcast:person role="guest">Fixture Guest</podcast:person></item>'
        for i in range(1, CONTENT_FEED_ITEMS + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" '
        'xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:content="http://purl.org/rss/1.0/modules/content/" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:podcast="https://podcastindex.org/namespace/1.0">'
        f"<channel><title>Fixture Show {key}</title><link>https://fixture.example.org/{key}/</link>"
        f"<copyright>Fixture copyright</copyright>{items}</channel></rss>"
    )


def _content_feed_fixtures() -> dict[str, str]:
    files = {}
    for key in CONTENT_FEED_KEYS:
        base, query = _split(_registry_entry(key)["url"])
        files[f"conditions/json_apis/{key}.json"] = json.dumps({"answers": [_answer(base, _podcast_feed(key), query, RSS)]})
    return files


#: The TEHCC wiki templates MediawikiTemplatePages reads, and how many pages each fixture lists.
CONTENT_WIKI_TEMPLATES = {"tehcc_wiki_trails": 2, "tehcc_wiki_hikes": 2, "tehcc_wiki_challenge_items": 1}


def _wiki_template_answers(key: str, pages: int) -> dict:
    """The template's own page and the embeddedin listing, with and without revisions, each asked by its template."""
    template = _registry_entry(key)["template"]
    listed = [
        {
            "pageid": 9300 + 10 * len(key) + n,
            "ns": 0,
            "title": f"Fixture {template.split(':')[1]} Page {n}",
            "touched": "2026-09-22T01:06:28Z",
            "lastrevid": 300 + n,
            "length": 120,
            "fullurl": f"https://tehcc.org/clubwiki/index.php?title=Fixture_Page_{n}",
        }
        for n in range(1, pages + 1)
    ]
    text = {
        "Template:Trail": "{{Trail\n|Park=Fixture Park\n|Trail Distance=2.3 mi\n|Difficulty Rating=Medium\n}}\nFixture route.",
        "Template:Hike": "{{Infobox Trail\n| City = Fixture City\n| Distance = 3\n}}\nFixture hike.",
        "Template:Challenge Item": "Fixture challenge.\n{{#display_map: 35.76, -82.26~Fixture Summit}}",
    }[template]
    with_revisions = [
        {
            **page,
            "revisions": [
                {
                    "revid": page["lastrevid"],
                    "parentid": page["lastrevid"] - 1,
                    "timestamp": page["touched"],
                    "slots": {"main": {"contentmodel": "wikitext", "contentformat": "text/x-wiki", "content": text}},
                }
            ],
        }
        for page in listed
    ]
    found = {"batchcomplete": True, "query": {"pages": [{"pageid": 9299, "ns": 10, "title": template}]}}
    return {
        "answers": [
            _answer(TEHCC_WIKI_API, found, {"titles": template}),
            _answer(
                TEHCC_WIKI_API,
                {"batchcomplete": True, "query": {"pages": with_revisions}},
                {"prop": "info|revisions", "geititle": template},
            ),
            _answer(TEHCC_WIKI_API, {"batchcomplete": True, "query": {"pages": listed}}, {"prop": "info", "geititle": template}),
        ]
    }


def _content_wiki_fixtures() -> dict[str, str]:
    return {
        f"conditions/json_apis/{key}.json": json.dumps(_wiki_template_answers(key, pages))
        for key, pages in CONTENT_WIKI_TEMPLATES.items()
    }


def _content_wp_post(site: str, post_id: int, *, post_type: str = "post", categories=(), **extra) -> dict:
    """A post, page or custom post type entry as the clubs' WordPress REST routes served them on 2026-10-04."""
    return {
        "id": post_id,
        "date": "2026-03-01T09:00:00",
        "date_gmt": "2026-03-01T14:00:00",
        "guid": {"rendered": f"https://{site}/?p={post_id}"},
        "modified": "2026-09-21T10:13:20",
        "modified_gmt": "2026-09-21T14:13:20",
        "slug": f"fixture-hike-{post_id}",
        "status": "publish",
        "type": post_type,
        "link": f"https://{site}/fixture-hike-{post_id}/",
        "title": {"rendered": f"Fixture Hike {post_id}"},
        "content": {"rendered": "<p>Fixture route, 4.2 miles, with a fixture number: 555-0100.</p>", "protected": False},
        "excerpt": {"rendered": "<p>Fixture excerpt.</p>", "protected": False},
        "author": 7,
        "featured_media": 0,
        "template": "",
        "meta": {"_acf_changed": False},
        "categories": list(categories),
        "class_list": [f"post-{post_id}"],
        "acf": [],
        "yoast_head": "<meta name='author' content='Fixture Person'>",
        "yoast_head_json": {"author": "Fixture Person"},
        "_links": {"self": [{"href": f"https://{site}/wp-json/wp/v2/posts/{post_id}"}]},
        **extra,
    }


def _wp_terms(*names: str) -> list[dict]:
    return [{"id": 700 + n, "name": f"Fixture {name}", "slug": f"fixture-{name}", "count": 1} for n, name in enumerate(names)]


def _content_wordpress_documents() -> dict[str, dict]:
    """One WordPress document per registry key, each route its reader asks: a custom post type under `types`, child
    pages under `types['pages']`, a category's lookup and posts, and the hike types' taxonomies under `terms`."""
    gmc, mtsg, ridge, nmvfo, tko, pnt = (
        "greenmountainclub.org",
        "mtsgreenway.org",
        "ridgetrail.org",
        "nmvfo.org",
        "trailkeepersoforegon.org",
        "www.pnt.org",
    )
    gmc_taxonomies = ("difficulty", "distance", "hike-feature", "hike-status", "hike-type", "region")
    hikes = [
        _content_wp_post(
            gmc,
            9201 + n,
            post_type="hikes",
            **{taxonomy: [700] for taxonomy in gmc_taxonomies},
            uagb_author_info={"display_name": "Fixture Person"},
            uagb_excerpt="Fixture excerpt.",
        )
        for n in range(2)
    ]
    return {
        "gmc_hikes": {
            "categories": [],
            "posts": [],
            "types": {"hikes": hikes},
            "terms": {taxonomy: _wp_terms(taxonomy) for taxonomy in gmc_taxonomies},
        },
        "mtsg_itineraries": {
            "categories": [],
            "posts": [],
            "types": {
                "itinerary": [
                    _content_wp_post(
                        mtsg, 9211 + n, post_type="itinerary", itinerary_tag=[], itinerary_type=[700], cm_priority_areas=[700]
                    )
                    for n in range(2)
                ]
            },
            "terms": {taxonomy: _wp_terms(taxonomy) for taxonomy in ("itinerary_tag", "itinerary_type", "cm_priority_areas")},
        },
        "ridgetrail_trail_sections": {
            "categories": [],
            "posts": [],
            "types": {"trail-section": [_content_wp_post(ridge, 9221 + n, post_type="trail-section") for n in range(2)]},
            "terms": {},
        },
        "ridgetrail_curated_adventures": {
            "categories": [{"id": 21, "slug": "curated-adventures"}],
            "posts": [
                _content_wp_post(
                    ridge,
                    9231 + n,
                    categories=[21],
                    author_info={"display_name": "Fixture Person", "author_link": "https://ridgetrail.org/author/fixture/"},
                    jetpack_publicize_connections=[],
                )
                for n in range(2)
            ],
            "terms": {},
        },
        "nmvfo_hike_new_mexico": {
            "categories": [],
            "posts": [],
            "types": {"pages": [_content_wp_post(nmvfo, 9241 + n, post_type="page", parent=2040) for n in range(2)]},
            "terms": {},
        },
        "tko_spring_fundraiser_hike_posts": {
            "categories": [{"id": 40, "slug": "oregon-hikers-spring-fundraiser"}],
            "posts": [_content_wp_post(tko, 9251 + n, categories=[40]) for n in range(2)],
            "terms": {},
        },
        "pnta_day_hikes_posts": {
            "categories": [{"id": 117, "slug": "day-hikes"}],
            "posts": [_content_wp_post(pnt, 9261 + n, categories=[117]) for n in range(2)],
            "terms": {},
        },
    }


def _wp_site(key: str) -> str:
    """The REST root a WordPress row's reader asks, as extract/_kinds.py's _wp_api() makes it: the url's origin."""
    url = _registry_entry(key)["url"]
    return "/".join(url.split("/")[:3])


def _content_wordpress_fixtures(files: dict) -> dict:
    """Section C's WordPress documents, merged with any other key's document for the same site.

    Fixture mode serves one document per REST root (extract/_fixtures.py keeps the last resource's), and three of
    these sites already have a notice document: GMC's `alert` type, TKO's and PNTA's condition categories. So each
    document for a site holds every route any key on that site asks, merged: the categories and posts listed once
    by id, the terms and the types by route. Each reader still reads only its own route, category or type.
    """
    files = dict(files)
    mine = {**_content_wordpress_documents(), **_k_wordpress_documents()}
    by_site: dict[str, list[str]] = {}
    for key in mine:
        by_site.setdefault(_wp_site(key), []).append(key)
    for name, content in files.items():
        if name.startswith("conditions/") and name.count("/") == 1 and name.endswith(".json"):
            key = name[len("conditions/") : -len(".json")]
            try:
                entry = _registry_entry(key)
            except StopIteration:
                continue
            site = "/".join(entry.get("url", "").split("/")[:3])
            if site in by_site and key not in mine:
                document = json.loads(content)
                if isinstance(document, dict) and "posts" in document and "categories" in document:
                    mine[key] = document
                    by_site[site].append(key)
    for keys in by_site.values():
        merged = {"categories": [], "posts": [], "terms": {}, "types": {}}
        for key in keys:
            document = mine[key]
            for field in ("categories", "posts"):
                seen = {item["id"] for item in merged[field]}
                merged[field] += [item for item in document.get(field, []) if item["id"] not in seen]
            for field in ("terms", "types"):
                merged[field].update(document.get(field) or {})
        for key in keys:
            files[f"conditions/{key}.json"] = json.dumps(merged)
    return files


def _nps_park(code: str) -> dict:
    return {"states": "XX", "parkCode": code, "designation": "Fixture Designation", "fullName": f"Fixture Park {code}",
            "url": f"https://www.nps.gov/{code}/index.htm", "name": f"Fixture {code}"}  # fmt: skip


def _nps_content_rows(key: str) -> list[dict]:
    """Two rows of one NPS list, each field one its endpoint served on 2026-10-04, every value invented."""
    ids = [f"00000000-0000-4000-a000-{1000 * len(key) + n:012d}" for n in (1, 2)]
    if key == "nps_multimedia_audio":
        return [
            {"id": i, "permalinkUrl": f"https://www.nps.gov/media/video/view.htm?id={i}", "title": f"Fixture Audio {n}",
             "description": f"Fixture audio description {n}.", "splashImage": {"url": ""}, "relatedParks": [_nps_park("semo")],
             "tags": ["fixture"], "latitude": None, "longitude": None, "geometryPoiId": "", "durationMs": 60000 * n,
             "credit": "Fixture Collection", "transcript": f"Fixture transcript {n}, a person's own words, which never load.",
             "callToAction": "", "callToActionUrl": "",
             "versions": [{"fileSize": 1000.0, "fileType": "audio/mp3", "url": f"https://www.nps.gov/fixture/{n}.mp3"}]}
            for n, i in enumerate(ids, 1)
        ]  # fmt: skip
    if key == "nps_gallery_assets":
        return [
            {"id": i, "permalinkUrl": f"https://www.nps.gov/media/photo/gallery-item.htm?id={i}", "title": f"Fixture Photo {n}",
             "description": f"Fixture photo description {n}.", "altText": f"Fixture alt text {n}",
             "fileInfo": {"url": f"https://www.nps.gov/npgallery/GetAsset/{i}", "fileType": "image/jpeg", "widthPixels": 100,
                          "heightPixels": 80, "fileSizeKb": 12},
             "relatedParks": [_nps_park("lecl")], "tags": [], "credit": "NPS photo",
             # Each photo its own licence: 12 of the first 500 live rows (2026-10-04) were the second constraint.
             "constraintsInfo": {"constraint": "Public domain", "grantingRights": "Full"} if n == 1 else
             {"constraint": "Restrictions apply on use and/or reproduction (Copyrighted material)", "grantingRights": "Partial"},
             "copyright": "Fixture copyright line.", "ordinal": n}
            for n, i in enumerate(ids, 1)
        ]  # fmt: skip
    if key == "nps_passport_stamp_locations":
        return [{"id": i, "label": f"Fixture Visitor Center {n}", "parks": [_nps_park("semo")], "type": "visitorcenters"}
                for n, i in enumerate(ids, 1)]  # fmt: skip
    if key == "nps_things_to_do":
        return [
            {"id": i, "url": f"https://www.nps.gov/thingstodo/fixture-{n}.htm", "title": f"Fixture Hike {n}",
             "shortDescription": f"Fixture short description {n}.", "images": [{"url": "https://www.nps.gov/fixture.jpg",
             "credit": "NPS / Fixture Photographer", "altText": "", "title": "", "description": "", "caption": "", "crops": []}],
             "relatedParks": [_nps_park("natr")], "relatedOrganizations": [], "tags": ["hiking"], "latitude": "35.5",
             "longitude": "-82.5", "geometryPoiId": "", "amenities": [], "location": "", "seasonDescription": "",
             "accessibilityInformation": "", "isReservationRequired": "false", "ageDescription": "", "petsDescription": "",
             "timeOfDayDescription": "", "feeDescription": "", "age": "", "arePetsPermittedWithRestrictions": "false",
             "activities": [{"id": "BFF8C027-7C8F-480B-A5F8-CD8CE490BFBA", "name": "Hiking"}], "activityDescription": "",
             "locationDescription": "", "doFeesApply": "false", "longDescription": f"<p>Fixture long description {n}.</p>",
             "reservationDescription": "", "season": [], "topics": [], "durationDescription": "", "arePetsPermitted": "false",
             "timeOfDay": [], "duration": "1-2 Hours", "credit": "", "relevanceScore": 1.0}
            for n, i in enumerate(ids, 1)
        ]  # fmt: skip
    if key == "nps_tours":
        return [
            {"id": i, "title": f"Fixture Tour {n}", "description": f"Fixture tour description {n}.",
             "park": _nps_park("trte"), "images": [], "durationMin": "1", "durationMax": "2", "durationUnit": "h",
             "type": "Standard", "relevanceScore": 1.0,
             "activities": [{"id": "fixture", "name": "Hiking"}], "topics": [{"id": "fixture", "name": "Fixture"}], "tags": [],
             "stops": [{"id": "s1", "ordinal": "1", "directionsToNextStop": "Fixture directions.", "assetId": "a1",
                        "assetName": "Fixture Stop", "assetType": "Places", "audioFileUrl": "", "audioTranscript": "",
                        "significance": "Fixture significance."}]}
            for n, i in enumerate(ids, 1)
        ]  # fmt: skip
    raise KeyError(key)


#: The NPS content rows NpsContent reads (extract/_content.py), each answered with two rows in one page.
CONTENT_NPS_KEYS = ("nps_multimedia_audio", "nps_gallery_assets", "nps_passport_stamp_locations", "nps_things_to_do", "nps_tours")


def _content_nps_fixtures() -> dict[str, str]:
    files = {}
    for key in CONTENT_NPS_KEYS:
        entry = _registry_entry(key)
        query = {"limit": "500", "start": "0"}
        if entry.get("park_codes_from"):
            query["parkCode"] = ",".join(sorted(_registry_entry(entry["park_codes_from"])["park_codes"]))
        rows = _nps_content_rows(key)
        body = {"total": str(len(rows)), "limit": "500", "start": "0", "data": rows}
        files[f"conditions/json_apis/{key}.json"] = json.dumps({"answers": [_answer(entry["url"], body, query)]})
    return files


def content_fixtures(files: dict) -> dict:
    """Section C's fixture files, added to `files`, the WordPress documents merged per site with what is there."""
    files = {**files, **_content_feed_fixtures(), **_content_wiki_fixtures(), **_content_nps_fixtures()}
    return _content_wordpress_fixtures(files)


# --- decision 54, waves 2 and 3: GIS files and the geographic APIs (extract/_gis_files.py, extract/_ogc.py) ---
#
# One answers document per registry key under conditions/json_apis/, the shape the JSON API notice sources use,
# because fixture mode serves extract/_gis_files.py's GisFile and extract/_ogc.py's JsonFeatures and OgcFeatures
# from that folder (extract/_fixtures.py's JSON_API_KINDS). THE NAMES ARE MEASURED: every folder, element,
# ExtendedData name, GeoJSON property, CSV header and JSON field below is one the live file or API carried when it
# was read for registration on 2026-10-04 (each sources.json row's `notes`). THE VALUES ARE INVENTED, start with
# 'Fixture' wherever they are text, and sit on the fixture grid (_point, _line) so every region box holds them; no
# real placemark, waypoint, line or place is copied. A zipped file (a KMZ, Catamount's GPX download) is served as
# text, so it is built from stored members and padded until every byte is ASCII (_ascii_zip): the routed answers
# carry a body as text and nothing else here changes that. That holds one member per zip: two members' central
# directory runs past 127 bytes, so Catamount's KML twin and macOS resource fork, which the reader skips, are left
# to tests/test_extract_gis_files.py.

MY_MAPS_KML_URL = "https://www.google.com/maps/d/kml"
KML_CONTENT = "text/xml; charset=utf-8"


def _kml_coordinates(geometry: dict) -> str:
    points = [geometry["coordinates"]] if geometry["type"] == "Point" else geometry["coordinates"]
    return " ".join(f"{x},{y},0" for x, y in points)


def _placemark(name: str, geometry: dict, description: str = "", data: dict | None = None, style: str = "#icon-1") -> str:
    shape = "Point" if geometry["type"] == "Point" else "LineString"
    extended = ""
    if data:
        extended = (
            "<ExtendedData>" + "".join(f'<Data name="{k}"><value>{v}</value></Data>' for k, v in data.items()) + "</ExtendedData>"
        )
    return (
        f"<Placemark><name>{name}</name><description><![CDATA[{description}]]></description><styleUrl>{style}</styleUrl>"
        f"{extended}<{shape}><coordinates>{_kml_coordinates(geometry)}</coordinates></{shape}></Placemark>"
    )


def _kml(name: str, folders: dict[str, list[str]], loose: list[str] = ()) -> str:
    """A KML document: each folder's placemarks, then any outside a folder."""
    inner = "".join(f"<Folder><name>{folder}</name>{''.join(marks)}</Folder>" for folder, marks in folders.items())
    return (
        '<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        f"<name>{name}</name>{inner}{''.join(loose)}</Document></kml>"
    )


def _gpx(waypoints: list[tuple[str, dict, dict]] = (), tracks: list[tuple[str, list[dict]]] = ()) -> str:
    """A GPX 1.1 document: (name, point, extra child elements) waypoints and (name, segments) tracks."""
    body = ""
    for name, point, extra in waypoints:
        x, y = point["coordinates"]
        children = "".join(f"<{k}>{v}</{k}>" for k, v in extra.items())
        body += f'<wpt lat="{y}" lon="{x}"><name>{name}</name>{children}</wpt>'
    for name, segments in tracks:
        trksegs = "".join(
            "<trkseg>"
            + "".join(f'<trkpt lat="{y}" lon="{x}"><ele>{100 + n}.0</ele></trkpt>' for n, (x, y) in enumerate(s["coordinates"]))
            + "</trkseg>"
            for s in segments
        )
        body += f"<trk><name>{name}</name>{trksegs}</trk>"
    return f'<?xml version="1.0" encoding="UTF-8"?><gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="fixture">{body}</gpx>'


def _ascii_zip(members: dict[str, str]) -> str:
    """A zip of stored (uncompressed) members whose every byte is ASCII, returned as text.

    Fixture mode serves a routed answer's body as UTF-8 text, so a zip only arrives whole if no byte of it is 0x80 or
    above. Stored members of ASCII text, a 1980-01-01 timestamp and DOS attributes leave three numbers per member to
    chance, each a little-endian field: its CRC-32, its size and the offset of what follows it. So each member in turn
    gets an XML comment appended, the first that brings all three under 0x80 byte by byte (about one try in 64), and
    the finished archive is checked whole.
    """
    import io
    import zipfile
    import zlib

    chosen, offset = {}, 0
    for name in members:
        for pad in range(20000):
            # The comment's length moves the size and the offsets, its number the CRC.
            data = (members[name] + f"<!-- {pad // 128} {'x' * (pad % 128)} -->").encode("ascii")
            following = offset + 30 + len(name.encode("ascii")) + len(data)
            fields = struct.pack("<3I", zlib.crc32(data), len(data), following)
            if all(byte < 0x80 for byte in fields):
                chosen[name], offset = data, following
                break
        else:
            raise RuntimeError(f"no padding made {name} ASCII in the fixture zip")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for name, data in chosen.items():
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            # DOS's archive bit: writestr() replaces an attribute of 0 with Unix mode 0600, whose bytes are not ASCII.
            info.create_system, info.external_attr = 0, 0x20
            archive.writestr(info, data)
    body = buffer.getvalue()
    if any(byte >= 0x80 for byte in body):
        raise RuntimeError("the fixture zip's central directory is not ASCII; rename a member")
    return body.decode("ascii")


def _geojson_text(features: list[dict], crs84: bool = False) -> str:
    document = {"type": "FeatureCollection", "features": features}
    if crs84:
        document["crs"] = {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}}
    return json.dumps(document)


def _feature(properties: dict, geometry: dict, feature_id=None) -> dict:
    feature = {"type": "Feature", "properties": properties, "geometry": geometry}
    if feature_id is not None:
        feature["id"] = feature_id
    return feature


def _my_map(mid: str, body: str) -> dict:
    return {"answers": [_answer(MY_MAPS_KML_URL, body, {"mid": mid, "forcekml": "1"}, KML_CONTENT)]}


def _files(*answers: tuple[str, str, str]) -> dict:
    return {"answers": [_answer(url, body, None, content_type) for url, body, content_type in answers]}


def _gis_file_documents() -> dict[str, dict]:
    kml_type = "application/vnd.google-earth.kml+xml"
    gpx_type = "application/gpx+xml"
    nez_perce_data = {
        "description": "Photo: ",
        "Meaning": "Fixture meaning",
        "More Context": "Fixture context",
        "Auto Tour Route": "1",
        "Trail Foundation": "https://example.org/",
        "longitude": "-74.0",
        "latitude": "41.0",
        "More Web Info": "https://example.org/",
        "About": "Fixture about",
        "Photo": "",
    }
    bmecc_data = {
        "description": "",
        "Type": "Shelter",
        "Club": "BMECC",
        "Name": "Fixture Shelter",
        "Latitude": "41.0",
        "Longitude": "-74.0",
    }
    documents = {
        "usfs_nez_perce_nht_my_map": _my_map(
            "1rdJCOzX2Wh3yt7E-nVDfrz0CbSc",
            _kml(
                "Fixture Historic Trail",
                {
                    "Auto Tour Stops": [
                        _placemark("Fixture Stop One", _point(0), "", nez_perce_data),
                        _placemark("Fixture Stop Two", _point(1), "", nez_perce_data),
                    ],
                    "Suggested Travel Routes": [
                        _placemark("Fixture Travel Route", _line(0), "description: Fixture directions", style="#line-1")
                    ],
                    "Adventure Routes": [
                        _placemark("Fixture Adventure Route", _line(1), "description: Fixture directions", style="#line-2")
                    ],
                },
            ),
        ),
        "rmfi_project_map": _my_map(
            "1JYWuK-xRDI4gA8zuREE894PcnZEtMUk",
            _kml(
                "Fixture Project Map",
                {
                    "RMFI Project Past , Present and Ongoing": [
                        _placemark("Fixture Open Space", _point(2)),
                        _placemark("Fixture Canyon", _point(3)),
                    ]
                },
            ),
        ),
        "fpc_forest_park_trailheads": _my_map(
            "1lykYs7fUx9AXn8VZlywlQGo-8fmYJHQ",
            _kml(
                "Fixture Trailheads",
                {"Trail Heads": [_placemark("Fixture Trailhead: Fixture Drive", _point(4), "Fixture trailhead")]},
            ),
        ),
        "ota_trail_map": _my_map(
            "1k4nsYuKHFtLk05shVlUX-L9tb-clI7iX",
            _kml(
                "FixtureTrailMap",
                {
                    "Trailhead": [
                        _placemark(
                            "Fixture Parking",
                            _point(5),
                            "Fixture Parking <br>Elevation = 413.40 ft <br>Coordinates = N41.0, W074.0 <br>Type = Trailhead",
                        )
                    ],
                    "Main Trail": [_placemark("Fixture Section", _line(2), "Fixture Section", style="#line-1")],
                    "Road - White": [_placemark("Fixture Road", _line(3), "Fixture Road", style="#line-2")],
                },
            ),
        ),
        "bartram_trail_markers_map": _my_map(
            "1ek21kngs9TQ-bAbmjDWtpFWGvLw-Cwre",
            _kml(
                "Fixture Markers",
                {
                    "Bartram Trail": [_placemark("Fixture Path", _line(4), style="#line-1")],
                    "Just Bartram Markers with Text Support.csv": [
                        _placemark(
                            "Point 1",
                            _point(6),
                            "Part Of Trail: Yes",
                            {
                                "Part Of Trail": "Yes",
                                "Location Description": "Fixture Marina",
                                "Lat. Lng.": "41.06, -73.94",
                                "Marker Text": "Fixture text",
                                "State": "NY",
                                "Country": "USA",
                                "ID": "1",
                                "Supporting  Text": "Fixture support",
                            },
                        )
                    ],
                },
            ),
        ),
        "bartram_trail_map": {
            "answers": [
                _answer(
                    MY_MAPS_KML_URL,
                    _kml(
                        "Fixture Bartram Trail",
                        {
                            "Bartram Sites": [_placemark("Fixture Fort", _point(7), "Fixture site")],
                            "Markers": [
                                _placemark(
                                    "Fixture Marker",
                                    _point(8),
                                    "",
                                    {"Latitude": "41.08", "Longitude": "-73.92", "Description": "Fixture", "Icon": "1"},
                                )
                            ],
                            "Federal_Road": [_placemark("Fixture Road", _line(5), style="#line-1")],
                        },
                    ),
                    {"mid": "z-XY_0WikHLg.kpJrukA3Genw", "forcekml": "1"},
                    KML_CONTENT,
                )
            ]
        },
        "bmecc_trail_section_map": _my_map(
            "1AhhnnzcYgmH6WVNvJeqcjtgiZRgSd8wg",
            _kml(
                "Fixture Trail Section",
                {
                    "Shelters": [_placemark("Fixture Shelter", _point(9), "description: <br>Type: Shelter", bmecc_data)],
                    "Springs": [
                        _placemark(
                            "Fixture Spring",
                            _point(10),
                            "description: <br>Type: Spring",
                            {**bmecc_data, "Type": "Spring", "Name": "Fixture Spring"},
                        )
                    ],
                    "Hospital Emergency Rooms": [_placemark("Fixture Hospital", _point(11), "1 Fixture Street, Fixture, PA")],
                    "BMECC Northern Section": [_placemark("Fixture Northern Section", _line(6), style="#line-1")],
                },
            ),
        ),
        "ohta_website_track": _my_map(
            "1T9D3RqcVbXKh8XFmVGrJFF7C6c7wH00",
            _kml(
                "Fixture Website Track",
                {"OHT Website Track": [_placemark("Fixture Mountains", _line(7), "Fixture Mountains", style="#line-1")]},
            ),
        ),
        "phta_trails_map": _my_map(
            "1jTNQ94C3mkIAbXihNPY2Wk4j1_W9fPV8",
            _kml(
                "Fixture Trails",
                {
                    "Fixture Heritage Trail": [
                        _placemark(
                            "Start of Fixture Track",
                            _point(12),
                            "Saturday, October 26, 2013 9:53 AM EDT<br>Elevation: 164 feet",
                            style="#icon-61",
                        ),
                        # The live map's 3 exact copies: one placemark repeated in place.
                        _placemark(
                            "Fixture Track", _line(8), "Statistics computed from imported data", style="#line-0288D1-5000"
                        ),
                        _placemark(
                            "Fixture Track", _line(8), "Statistics computed from imported data", style="#line-0288D1-5000"
                        ),
                    ]
                },
            ),
        ),
        "nbatc_trails": _files(
            (
                "https://home.nbatc.org/MapData/NBATC_Trails_015.kml",
                # The live file's undeclared `xsi` prefix, which the reader must tolerate.
                _kml(
                    "Fixture Trails", {"Tracks": [_placemark("Fixture Side Trail", _line(9), style="#lineStyleTrailWhite_n")]}
                ).replace("<Document>", '<Document xsi:schemaLocation="http://earth.google.com/kml/2.1 kml21.xsd">', 1),
                kml_type,
            )
        ),
        "nbatc_trail_features": _files(
            (
                "https://home.nbatc.org/MapData/NBATC_Trail_Features_01.kmz",
                _ascii_zip(
                    {
                        "doc.kml": _kml(
                            "Fixture Features",
                            {},
                            [_placemark("Fixture Foot Bridge", _point(13)), _placemark("Fixture Gap Parking", _point(14))],
                        )
                    }
                ),
                "application/vnd.google-earth.kmz",
            )
        ),
        "nbatc_shelters": _files(
            (
                "https://home.nbatc.org/MapData/NBATC_Shelters_000.kml",
                _kml("Fixture Shelters", {}, [_placemark("Fixture Shelter", _point(15))]),
                kml_type,
            )
        ),
        "nbatc_trail_info": _files(
            (
                "https://home.nbatc.org/MapData/NBATC_TrailInfo_002.kml",
                _kml("Fixture Trail Info", {}, [_placemark("Fixture Loop", _point(16), "Fixture info")]),
                kml_type,
            )
        ),
        "catamount_main_trail": _files(
            (
                "https://catamounttrail.org/CTA_TrailMap/data/CTA_MAINTRAIL_MASTER_WEBMAP.geojson",
                # Two features that repeat a line and its SURFACE under new ids: the live file's 4 exact copies.
                _geojson_text(
                    [
                        _feature({"OBJECTID": 1, "SURFACE": "Ungroomed", "Shape_Length": 0.01}, _line(10), 1),
                        _feature({"OBJECTID": 2, "SURFACE": "Snowmobile", "Shape_Length": 0.01}, _line(11), 2),
                        _feature({"OBJECTID": 3, "SURFACE": "Snowmobile", "Shape_Length": 0.01}, _line(11), 3),
                    ]
                ),
                "application/geo+json",
            )
        ),
        "catamount_side_trails": _files(
            (
                "https://catamounttrail.org/CTA_TrailMap/data/CTA_SIDETRAILS_MASTER_WEBMAP.geojson",
                _geojson_text([_feature({"SURFACE": "Groomed Nordic"}, _line(12))], crs84=True),
                "application/geo+json",
            )
        ),
        "catamount_full_route": _files(
            (
                "https://catamounttrail.org/wp-content/uploads/CT_fullRoute_gpxKML_122022.zip",
                _ascii_zip(
                    {
                        "untitled folder/Catamount_Trail_Route.gpx": _gpx(
                            tracks=[("CT", [_line(13)]), ("OLD CT - Fixture", [_line(14)])]
                        ),
                    }
                ),
                "application/zip",
            )
        ),
        "catamount_sections": _files(
            (
                "https://catamounttrail.org/CTA_TrailMap/data/CTA_SECTIONS_WEBMAP.geojson",
                _geojson_text([_feature({"Section": "1"}, _polygon(0)), _feature({"Section": "2"}, _polygon(1))], crs84=True),
                "application/geo+json",
            )
        ),
        "catamount_access_points": _files(
            (
                "https://catamounttrail.org/CTA_TrailMap/data/CTA_ACCESS_MASTER_WEBMAP.csv",
                'LOCATION,LONGITUDE,LATITUDE,PRIMARY\nFixture Road,-74.0,41.0,Yes\n"Fixture Route, Fixture Town",-73.99,41.01,No\n',
                "text/csv",
            )
        ),
        "catamount_businesses": _files(
            (
                "https://catamounttrail.org/CTA_TrailMap/data/CTA_POI_MASTER_WEBMAP.csv",
                "NAME,URL,LATITUDE,LONGITUDE,ABSTRACT,LODGING,FOOD,NORDIC,ALPINE,SPONSOR\nFixture Inn,https://example.org,41.02,-73.98,Fixture abstract.,Yes,Yes,No,No,No\n",
                "text/csv",
            )
        ),
        "catamount_backcountry_zones": _files(
            (
                "https://catamounttrail.org/CTA_TrailMap/data/CTA_BACKCOUNTRY_MASTER_WEBMAP.csv",
                "NAME,URL,LATITUDE,LONGITUDE,ABSTRACT\nFixture Forest,https://example.org,41.03,-73.97,Fixture zone.\n",
                "text/csv",
            )
        ),
        "fmst_primary_trailheads": {
            "answers": [
                _answer(
                    "https://docs.google.com/spreadsheets/d/1RQYQ9d0uYc4tiw3kDoANY7ZgQuXDSuj4AyW44Kv7-xQ/export",
                    '"Fixture sheet: use it as you like.",,,,,,Current as of:,1/1/2026,,,,,\n'
                    "Eastbound Segment,EB Mile,Westbound Segment,WB Mile,Trailhead 1,Latitude,Longitude,"
                    "Trailhead 1 Notes,,Trailhead 2,Latitude,Longitude,Length\n"
                    "1,0.0,1,2.0,Fixture Gap Trailhead,35.8,-80.0,,,Fixture Knob Overlook,35.81,-79.9,2.0\n"
                    ",,,,,,,,,,,,\n"
                    "1,2.0,1,0.0,Fixture Knob Overlook,35.81,-79.9,Transit only; no trail parking,,,,,\n",
                    {"format": "csv"},
                    "text/csv",
                )
            ]
        },
        "hhc_tecumseh_waypoints": _files(
            (
                "https://hoosierhikerscouncil.org/assets/Tecumseh_Trail_POI_Waypts.gpx",
                _gpx(
                    waypoints=[
                        ("01_Fixture_Parking", _point(17), {"sym": "RED MAP PIN"}),
                        ("Fixture_Shelter", _point(18), {"sym": "RED MAP PIN"}),
                    ]
                ),
                gpx_type,
            )
        ),
        "hhc_tecumseh_track": _files(
            (
                "https://hoosierhikerscouncil.org/assets/2023_TecumsehTrailTrack.gpx",
                _gpx(tracks=[("Fixture_Trail", [_line(15), _line(16)])]),
                gpx_type,
            )
        ),
        "condor_trail_2020": _files(
            *(
                (
                    f"https://www.condortrail.com/wp-content/uploads/kml/CT2020_{county}County.kml",
                    _kml(
                        f"Fixture {county}",
                        {f"CondorTrail{county}County": [_placemark(f"Fixture {county} Segment", _line(17 + n), style="#line-1")]},
                    ),
                    kml_type,
                )
                for n, county in enumerate(("Ventura", "SantaBarbara", "SanLuisObispo", "Monterey"))
            )
        ),
        "nchpta_trails": _files(
            (
                "https://nchighpeaks.org/interactivemaps/TrailSunday3.xml",
                _kml("Fixture Trails", {}, [_placemark("179-Fixture Crest Trail", _line(21), style="#line-1")]),
                "application/xml",
            )
        ),
        "mdhta_trail_guide": _files(
            *(
                (
                    url,
                    json.dumps(
                        {
                            "type": "Feature",
                            "properties": {"name": f"Fixture Track {n}", "type": "track"},
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [[x, y, 700.0 + n] for x, y in _line(22 + n)["coordinates"]],
                            },
                        }
                        if n == 0
                        else {
                            "type": "FeatureCollection",
                            "features": [
                                {
                                    "type": "Feature",
                                    "properties": {"name": f"fixture-connector-{n}"},
                                    "geometry": {
                                        "type": "LineString",
                                        "coordinates": [[x, y, 700.0 + n] for x, y in _line(22 + n)["coordinates"]],
                                    },
                                }
                            ],
                        }
                    ),
                    "application/geo+json",
                )
                for n, url in enumerate(_registry_entry("mdhta_trail_guide")["files"])
            )
        ),
        "ocvt_at_tracks": _files(
            *(
                (url, _gpx(tracks=[(f"Fixture Shelter to Fixture Road {n}", [_line(41 + n)])]), gpx_type)
                for n, url in enumerate(_registry_entry("ocvt_at_tracks")["files"])
            )
        ),
    }
    return documents


def _geo_api_documents() -> dict[str, dict]:
    def location(n: int, lat: float, lng: float, icon: str) -> dict:
        return {
            "id": 900000 + n,
            "modified_gmt": "2026-09-21T14:13:20",
            "slug": f"fixture-location-{n}",
            "link": f"https://mtsgreenway.org/location/fixture-location-{n}/",
            "title": {"rendered": f"Fixture Location {n}"},
            "location": {"lat": lat, "lng": lng} if lat is not None else None,
            "cat": {"ids": [1], "slugs": [icon]},
            "icon": icon,
            "popup": {
                "img": False,
                "description": "Fixture description.",
                "link": f"https://mtsgreenway.org/location/fixture-location-{n}/",
            },
        }

    def nps_item(n: int, route: str) -> dict:
        common = {
            "id": f"00000000-0000-4000-8000-{900 + n:012d}",
            "latitude": str(41.0 + n * 0.01),
            "longitude": str(-74.0 + n * 0.01),
            "url": "https://www.nps.gov/",
        }
        if route == "places":
            # The person fields a live place carries (`images`, a photographer's credit), invented, so the reader's rule runs.
            return {
                **common,
                "title": f"Fixture Place {n}",
                "relatedParks": [{"parkCode": "fixt"}],
                "tags": ["fixture"],
                "isOpenToPublic": "1",
                "images": [{"credit": "Fixture Photographer"}],
            }
        return {
            **common,
            "name": f"Fixture Campground {n}",
            "parkCode": "fixt",
            "amenities": {"potableWater": ["Yes - year round"]},
            "contacts": {"phoneNumbers": []},
        }

    nps = {
        route: {
            "answers": [
                _answer(
                    f"https://developer.nps.gov/api/v1/{route}",
                    {"total": "2", "limit": "500", "start": "0", "data": [nps_item(0, route), nps_item(1, route)]},
                    {"start": "0"},
                )
            ]
        }
        for route in ("places", "campgrounds")
    }
    return {
        "mtsg_map_locations": {
            "answers": [
                _answer(
                    "https://mtsgreenway.org/wp-json/wp/v2/cm-map-location",
                    # A location with no coordinate, as 3 of the live 185 are: it lands with no geometry.
                    [
                        location(1, 41.04, -73.96, "campgrounds"),
                        location(2, 41.05, -73.95, "trails"),
                        location(3, None, None, "uncategorized"),
                    ],
                    {"page": "1"},
                )
            ]
        },
        "nps_api_places": nps["places"],
        "nps_api_campgrounds": nps["campgrounds"],
    }


def gis_file_and_geo_api_fixtures() -> dict[str, str]:
    """Decision 54's waves 2 and 3 (section G): one answers document per registered GIS file and geographic API."""
    documents = {**_gis_file_documents(), **_geo_api_documents()}
    return {f"conditions/json_apis/{key}.json": json.dumps(document) for key, document in documents.items()}


# --- decision 54, waves 4 and 5, section S: the points read off club pages (extract/_pages_points.py) -------------
#
# One document per registry key under conditions/page_points/, `{"answers": {url: {"content_type", "body"}},
# "rows": n}`, served by exact URL (extract/_fixtures.py's PAGE_POINTS_DIR), so each page's own parser reads a
# page shaped like the live one: MDHTA's trail guide anchors (`data-type`, `data-slug`, `data-title`,
# `data-lat`, `data-long`, and a trail line's `data-geojson`), FoOT's shelter list through WordPress page 326's
# REST answer (`modified_gmt`, `content.rendered`, `<li>` entries in both of the page's shapes), AMC Berkshire's
# `<h3>` parking areas with their `bullets02` lists (the three ways the page writes a coordinate, a nested day-use
# list, an unclosed `<li>` and a heading with no list), the Foothills Trail's GPS Coordinates table through
# page 603's REST answer, BRBTC's and the Palmetto Trail's sitemaps with two section or passage pages each (the
# menu's own "Section 1" `<h5>`, a bare length, the map script's `addMarker` and `addSegment` calls, a 'NULL'
# marker type, and a sitemap entry outside the page prefix), and OHTA's trail page through page 15's REST answer
# (a trailhead listed under two segments, a "Parking at" and an "approximately" lead). THE SHAPES ARE MEASURED (read 2026-10-04, each row's sources.json `notes`); THE VALUES
# ARE INVENTED, every name starts with 'Fixture', and every point sits on the fixture grid (_point), inside each
# source's region box. `rows` is what the parser must land.
#
# AMC Berkshire's parking page is also the notice amc_wma_at_parking (decision 53), which fixture mode answers by
# the same URL, so the notices document for that key is written here too, with this body: one page, as the site
# serves it, for both of its readers. Its <h1> is the page notice's title.
#
# Not here: wave 4's PDFs (extract/_pdf_points.py), which need pypdf, and the pipeline and dbt jobs install none
# (requirements.in's note): fixture mode leaves them out, as it leaves GATC's water PDF and the notice PDFs out.

PAGE_HTML = "text/html; charset=UTF-8"
PAGE_REST = "application/json; charset=UTF-8"


def _ddm(value: float, hemisphere: str = "") -> str:
    """A fixture coordinate as degrees and decimal minutes, the way FoOT and the Foothills Trail print theirs."""
    degrees = int(abs(value))
    return f"{hemisphere}{degrees} {(abs(value) - degrees) * 60:06.3f}"


def _mdhta_trail_guide_page() -> str:
    anchors = [
        '<a href="https://mdhta.com/trails/fixture-trail/" data-slug="fixture-trail" data-title="Fixture Trail" '
        'data-type="trails" data-geojson="https://mdhta.com/wp-content/uploads/fixture-trail.geojson"></a>'
    ]
    for n, (kind, title) in enumerate(
        [
            ("trailheads", "Fixture Trailhead"),
            ("campgrounds", "Fixture Campground"),
            ("waterboxes", "Fixture Water Box &#8217;s"),
            ("river-crossings", "Fixture Crossing"),
            ("points-of-interest", "Fixture Overlook"),
            # A planned trailhead, its status only in its slug, as the live guide's Crying Butte is: layer_rules'
            # drop_where_contains on `slug` holds it back.
            ("trailheads", "Fixture Butte (expected to open)"),
        ]
    ):
        x, y = _point(n)["coordinates"]
        slug = f"fixture-{kind}-{n}" if "expected" not in title else "fixture-butte-expected-to-open-in-late-2099"
        anchors.append(
            f'<a href="https://mdhta.com/{kind}/{slug}/" data-slug="{slug}" data-title="{title}" data-type="{kind}" '
            f'data-lat="{y}" data-long="{x}"></a>'
        )
    return (
        "<!DOCTYPE html><html><head><title>Fixture Trail Guide</title></head><body><nav>Fixture menu</nav>"
        f'<div class="map">{"".join(anchors)}</div><footer>Fixture footer</footer></body></html>'
    )


def _foot_shelters_rest() -> str:
    items = []
    for n in range(3):
        x, y = _point(n)["coordinates"]
        items.append(
            f"<li><strong><u>FIXTURE SHELTER {n}</u></strong><strong> – MM {10 + n}.4 "
            f"{_ddm(y, 'N')} / {_ddm(x, 'W')} </strong></li>"
        )
    items.append("<li><strong><u>FIXTURE MILE SHELTER at MM 120.5</u></strong></li>")
    rendered = (
        '<h2 style="text-align: center;"><strong>Fixture Shelters</strong></h2>'
        '<h4>To download Shelter Guide click <a href="https://www.friendsoftheouachita.org/fixture.pdf">HERE</a></h4>'
        f"<ul>{''.join(items)}</ul><p><strong>Fixture thanks.</strong></p>"
    )
    return json.dumps(
        {
            "id": 326,
            "modified_gmt": "2026-09-21T14:13:20",
            "link": "https://www.friendsoftheouachita.org/hiker-info/trail-shelters/",
            "title": {"rendered": "Trail Shelters"},
            "content": {"rendered": rendered, "protected": False},
        }
    )


def _amc_parking_page() -> str:
    def area(n: int, items: str, label: str = "Lat/Lon") -> str:
        """One parking area: its <h3>, then its list, the coordinate last. 'Lon/Lat:' still prints the latitude first."""
        x, y = _point(n)["coordinates"]
        return (
            f'<h3 style="margin-top:24px;"><strong>Fixture Rd {n}, Fixture Town:</strong> Fixture access.</h3>'
            f'<ul class="bullets02">{items}<li>{label}: {y:.5f}, {x:.5f}.</li></ul>'
        )

    # A nested list of day-use pull-offs inside an area, as Mt Greylock Summit's; its facts are not the area's.
    nested = (
        '<li>Other day use parking areas near the A.T.<ul class="bullets02"><li><strong>Fixture Pull-off:</strong> '
        'Fixture access.<ul class="bullets02"><li>Capacity 4 vehicles.</li></ul></li></ul></li>'
    )
    body = "".join(
        [
            area(
                0,
                "<li>Capacity: 8 vehicles, busy on weekends.</li><li>Plowed in winter.</li>"
                "<li>Suitable for overnight parking.</li><li>Map kiosk: no.</li>",
            ),
            area(
                1,
                "<li>Capacity 6 vehicles.</li><li>Short term overnight use.</li><li>Not plowed in winter.</li>"
                "<li>Map kiosk: yes.</li>",
                "Lon/Lat",
            ),
            area(
                2,
                f"<li>Capacity: 50 vehicles.</li><li>Fee required.</li><li>Day use only. NO OVERNIGHT PARKING.</li>{nested}",
                "Lat.Lon",
            ),
            "<h3><strong>Fixture Ave, Fixture Town:</strong> No official parking area.</h3>",
            # School St's unclosed item: the next <li> ends it.
            area(
                3,
                "<li>Capacity: 20 vehicles (no campers).<li>Not recommended for overnight use.</li>"
                "<li>Plowed in winter (mostly).</li>",
            ),
        ]
    )
    return (
        "<!DOCTYPE html><html><head><title>Fixture Site</title></head><body><div id='wrapper'>"
        "<h1>Fixture A.T. Parking Areas</h1><div class='subtext-h1'>Fixture Committee<br>11&#8209;Jan&#8209;2025<br></div>"
        f"<h2>Parking Areas</h2>{body}<h2>Fixture More</h2><p>Fixture text.</p></div></body></html>"
    )


def _foothills_coordinates_rest() -> str:
    rows = []
    for n in range(3):
        x, y = _point(n)["coordinates"]
        rows.append(
            f'<tr><td valign="top"><div>Fixture Access {n}</div></td><td valign="top"><div>{_ddm(y)}</div></td>'
            f'<td valign="top"><div>{_ddm(x)}</div></td></tr>'
        )
    rendered = f'<h2>GPS Coordinates</h2><table border="0"><tbody>{"".join(rows)}</tbody></table>'
    return json.dumps(
        {
            "id": 603,
            "modified_gmt": "2024-01-27T16:07:54",
            "link": "https://foothillstrail.org/maps-coordinates-2/",
            "title": {"rendered": "Maps &amp; Coordinates"},
            "content": {"rendered": rendered, "protected": False},
        }
    )


#: Registry key -> (the URL its reader asks, content type, body, rows the parser lands).
PAGE_POINTS_FIXTURES = {
    "mdhta_trail_guide_points": ("https://mdhta.com/trail-guide/", PAGE_HTML, _mdhta_trail_guide_page, 6),
    "foot_trail_shelters": ("https://www.friendsoftheouachita.org/wp-json/wp/v2/pages/326", PAGE_REST, _foot_shelters_rest, 4),
    "amc_wma_at_parking_points": ("https://www.amc-wma.org/documents-more.cgi?id=112", PAGE_HTML, _amc_parking_page, 5),
    "foothills_gps_coordinates": (
        "https://foothillstrail.org/wp-json/wp/v2/pages/603",
        PAGE_REST,
        _foothills_coordinates_rest,
        3,
    ),
}


def _sitemap(*urls: str) -> str:
    entries = "".join(f"<url><loc>{url}</loc><lastmod>2026-03-19T15:51:29+00:00</lastmod></url>" for url in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entries}</urlset>'


BRBTC_SITEMAP = "https://blueridgebartram.org/crb_trail-sitemap.xml"
BRBTC_PAGES = ("https://blueridgebartram.org/trail/fixture-one/", "https://blueridgebartram.org/trail/fixture-two/")


def _brbtc_section(n: int) -> str:
    """A section page: the menu's own "Section 1" <h5>, then the section's <h5> over its <h1>, its length, its fix."""
    x, y = _point(n)["coordinates"]
    length = "9.3 miles" if n == 1 else "10.8"  # two of the live pages state a bare number
    return (
        "<html><body><nav><h5>Section 1</h5></nav><div class='intro-home-text'>"
        f"<h5>\n        Section {n}    </h5>\n<h1><span class='neue-haas'>Fixture Gap {n}</span> to "
        f"<span class='neue-haas'>Fixture Bald {n}</span></h1></div><div><h4>\n Length\n </h4>\n {length}\t</div>"
        f"<div><h4>Fixture Gap {n} Trailhead</h4>\n<p>{y}, {x}</p><a href='https://maps.app.goo.gl/fixture'>Get "
        "Directions</a></div><p>Fixture prose about the road in.</p></body></html>"
    )


def _brbtc_answers() -> dict[str, tuple[str, str]]:
    return {
        BRBTC_SITEMAP: ("application/xml; charset=UTF-8", _sitemap(*BRBTC_PAGES, "https://blueridgebartram.org/fixture-page/")),
        **{url: (PAGE_HTML, _brbtc_section(n)) for n, url in enumerate(BRBTC_PAGES, 1)},
    }


PALMETTO_SITEMAP = "https://www.palmettotrail.org/sitemap.xml"
PALMETTO_PAGES = (
    "https://www.palmettotrail.org/trails/trail/fixture-passage",
    "https://www.palmettotrail.org/trails/trail/fixture-two-passage",
)


def _palmetto_passage(n: int) -> str:
    """A passage page as its map script draws it: typed addMarker calls (one 'NULL') and the line's addSegment."""
    markers = "".join(
        f"trailPage.helper.addMarker({_point(i)['coordinates'][1]}, {_point(i)['coordinates'][0]}, '{kind}', '', []);\n"
        for i, kind in enumerate(("Parking", "Trail Head", "Water Launch", "NULL"), 4 * n)
    )
    vertices = json.dumps([{"lng": str(x), "lat": str(y)} for x, y in _line(n)["coordinates"]], separators=(",", ":"))
    return (
        f"<html><body><h1>Fixture Passage {n}</h1><p>Fixture prose.</p><script>\nloadjs.ready('mapDisplay', {{\n"
        f"trailPage.helper.init({{lat: 41.0, lng: -74.0, zoom: 14}});\n{markers}"
        f"trailPage.helper.addSegment('Fixture Segment {n}', {vertices}, []);\ntrailPage.helper.run();\n}});\n</script>"
        "</body></html>"
    )


def _palmetto_answers() -> dict[str, tuple[str, str]]:
    return {
        PALMETTO_SITEMAP: ("application/xml", _sitemap("https://www.palmettotrail.org/updates", *PALMETTO_PAGES)),
        **{url: (PAGE_HTML, _palmetto_passage(n)) for n, url in enumerate(PALMETTO_PAGES, 1)},
    }


def _ohta_trail_rest() -> str:
    def item(n: int, label: str) -> str:
        x, y = _point(n)["coordinates"]
        return f"<li>{label}: {y:.5f}, {x:.5f}. Fixture sentence after the fix.</li>"

    rendered = (
        "<h3>FIXTURE MOUNTAINS</h3><p>Fixture prose.</p><h4>Major trail heads</h4><ul>"
        + item(0, "Fixture Lake (mile 0)")
        + item(1, "Fixture Ford (mile 16.4)").replace(": ", ": Parking at ", 1)
        + "</ul><h3>FIXTURE LAKE</h3><h4>Major trail heads</h4><ul>"
        + item(1, "Fixture Ford (mile 16.4)")
        + item(2, "Fixture Ridge (LBW) access").replace(": ", ": approximately ", 1)
        + "</ul>"
    )
    return json.dumps(
        {
            "id": 15,
            "modified_gmt": "2026-09-10T21:26:38",
            "link": "https://ozarkhighlandstrail.com/trail/",
            "content": {"rendered": rendered},
        }
    )


TUSCARORA_PAGES = tuple(
    f"https://www.hikethetuscarora.org/{page}"
    for page in ("section-1-3", "section-4-6", "section-7-10", "section-11-13", "section-14-16", "section-17-19", "section-20-22")
)


def _tuscarora_section_page(n: int) -> str:
    """A Wix section page as hikethetuscarora.org's are: the menu, then a <p> of spans per paragraph, one section
    a page here: an Access fix with a parking lead, and a Camping list of a shelter, a name with no fix, and on the
    first page a campground; the advisory and the footer are prose that lands nowhere."""
    x, y = _point(30 + 2 * n)["coordinates"]
    sx, sy = _point(31 + 2 * n)["coordinates"]
    camping = f"Fixture Ridge Shelter {n} ({sy:.3f},{sx:.3f}), Fixture State Park."
    if n == 1:
        camping = f"Fixture Creek Campground ({sy + 0.002:.3f}, {sx:.3f}), " + camping
    # The last section's access sits off the trail, as the live Skyline Drive one does: its distance lands.
    approach = ", 0.4 mi SB on Fixture Trail to the junction." if n == 7 else "."
    paragraphs = (
        f"Section {n}: Fixture Gap {n}",
        f"Fixture Gap {n} to Fixture Road {n}, 9.{n} miles.",
        "Max Elevation: 1999 ft. Min Elevation: 999 ft.",
        "<span>Access:</span> The trail can be accessed by road from both termini of this section:",
        f"Fixture Gap {n}: Parking at Fixture Lot ({y:.3f}, {x:.3f}){approach}",
        "<span>Advisory:</span> Fixture prose about the road shoulder.",
        f"<span>Camping:&#160;</span> {camping}",
    )
    body = "".join(f'<p class="font_7"><span class="wixui-rich-text__text">{text}</span></p>' for text in paragraphs)
    return (
        "<html><body><nav><p>Section 1-3</p><p>Section 4-6</p></nav>"
        f"{body}<p>Fixture disclaimer.</p><p>&#169; 2017 by Fixture Club.</p></body></html>"
    )


#: Registry key -> (its answers, {url: (content type, body)}, and the rows its parser lands), for the sources a
#: sitemap lists pages for, or a row's `pages` list.
PAGE_POINTS_SITE_FIXTURES = {
    "brbtc_section_trailheads": (_brbtc_answers, 2),
    "palmetto_trail_passages": (_palmetto_answers, 10),
    "ohta_major_trailheads": (
        lambda: {"https://ozarkhighlandstrail.com/wp-json/wp/v2/pages/15": (PAGE_REST, _ohta_trail_rest())},
        4,
    ),
    "patc_tuscarora_points": (
        lambda: {url: (PAGE_HTML, _tuscarora_section_page(n)) for n, url in enumerate(TUSCARORA_PAGES, 1)},
        15,
    ),
}


def page_points_fixtures() -> dict[str, str]:
    """Decision 54's waves 4 and 5 (section S): one answers document per club page read for its points."""
    files = {}
    for key, (url, content_type, body, rows) in PAGE_POINTS_FIXTURES.items():
        answer = {"content_type": content_type, "body": body()}
        files[f"conditions/page_points/{key}.json"] = json.dumps({"answers": {url: answer}, "rows": rows})
        if key == "amc_wma_at_parking_points":
            files["conditions/notices/amc_wma_at_parking.json"] = json.dumps({"answers": {url: answer}, "rows": 1})
    for key, (answers, rows) in PAGE_POINTS_SITE_FIXTURES.items():
        served = {url: {"content_type": content_type, "body": body} for url, (content_type, body) in answers().items()}
        files[f"conditions/page_points/{key}.json"] = json.dumps({"answers": served, "rows": rows})
    return files


# --- decision 54, waves 4 and 5: the content types' pages and posts (section K, extract/_pages_content.py) ---
#
# One answers document per registry key under conditions/json_apis/, as section C's and G's are, because fixture
# mode serves extract/_pages_content.py's ContentPages from that folder (extract/_fixtures.py's JSON_API_KINDS): each
# page an answer by its exact URL, so the site's own parser reads it. THE MARKUP IS MEASURED: every element, class,
# heading level and label below is one the live page carried when it was read for registration on 2026-10-04 (each
# sources.json row's `notes`). THE VALUES ARE INVENTED and start with 'Fixture'; no real hike is copied. The PDFs of
# extract/_pdf_content.py get no document here, because fixture mode's Python need not have pypdf: their base models
# read no rows (dbt/macros/raw_or_empty.sql), and tests/test_extract_pdf_content.py runs their families over invented
# text layers instead. Section K's WordPress
# post types ride section C's documents (_k_wordpress_documents(), merged by _content_wordpress_fixtures()).

HTML = "text/html; charset=UTF-8"


def _k_page(title: str, body: str) -> str:
    return f"<!DOCTYPE html><html><head><title>{title}</title></head><body><main>{body}</main></body></html>"


def _mazamas_hike_list_page() -> str:
    """The Hike List View's markup: a Hike Details block, then one rich-text block a region, an h3 above a list."""
    details = (
        '<article class="col-xs-12 block-richtextblock block"><h3 class="block--title">Hike Details</h3>'
        '<div class="richtextblock--content rte"><ul><li>Fixture mileage note.</li></ul></div></article>'
    )
    regions = []
    for n, region in enumerate(("Columbia River Gorge Hikes", "Mt. Hood", "Clackamas River", "Oregon Coast")):
        star = "*" if region == "Oregon Coast" else ""
        regions.append(
            f'<article class="col-xs-12 block-richtextblock block"><h3 class="block--title">{region}</h3>'
            '<div class="richtextblock--content rte"><p><strong>List includes: hike name, hike distance, hike '
            "elevation, appx. driving distance, trailhead fee</strong></p><ul>"
            f"<li>Fixture Hike {n}A 4.6 miles 1,540 feet 42 miles, no</li>"
            f"<li>Fixture Hike {n}B varies varies 84 miles{star}, yes</li></ul></div></article>"
        )
    return _k_page("hiking | Mazamas", "<h1>Hike List View</h1>" + details + "".join(regions))


def _tahoe_rim_pages() -> list[tuple[str, str, str]]:
    """The day-hiking index's cards (an <a> around an <h4>) and one theme page's h3 hikes with bold-labelled facts."""
    index_url, theme_url = "https://tahoerimtrail.org/day-hiking/", "https://tahoerimtrail.org/day-hiking/alpine-lakes/"
    index = _k_page(
        "Day Hiking - Tahoe Rim Trail Association",
        f'<h1>Day Hiking</h1><h2>Day Hike Itineraries</h2><a href="{theme_url}"><h4>Alpine Lakes</h4></a>',
    )
    hikes = "".join(
        f"<h3><img src='https://tahoerimtrail.org/fixture.jpg'/><strong>Fixture Lake {n} Hike</strong></h3>"
        f"<p><strong>Classification</strong>: Moderate</p><p><strong>Distance:</strong> {n}.5 miles round trip</p>"
        "<p><strong>Highlights:</strong> Fixture highlights.</p><p><strong>Location:</strong> Fixture trailhead</p>"
        "<p><strong>Bikes Allowed:</strong> No</p><p><strong>Access from</strong>: Fixture Shore</p>"
        "<p><strong>Description:</strong> Fixture description, 2 miles in.</p>"
        for n in (1, 2)
    )
    theme = _k_page("Alpine Lakes", f"<h1>Alpine Lakes</h1>{hikes}<h3>Office</h3><p>Fixture address</p>")
    return [(index_url, HTML, index), (theme_url, HTML, theme)]


def _nc_parks_pages() -> list[tuple[str, str, str]]:
    """The parks index's link and one park's trails table. A park whose /trails page answers 404 is the unit tests':
    fixture mode answers every routed URL 200."""
    base = "https://www.ncparks.gov/state-parks"
    index = _k_page(
        "State Parks | NC State Parks",
        '<a href="/state-parks/fixture-mountain-state-park">Fixture Mountain</a>',
    )
    table = (
        "<table><tr><th>\ufeffTrail Name</th><th>Blaze</th><th>Length</th><th>Difficulty</th><th>Trail Use</th>"
        "<th>ADA Accessible</th><th>Description</th></tr>"
        "<tr><td>Fixture Loop Trail</td><td>orange circles</td><td>1.5-mile loop</td><td>Easy</td><td>Hiking only</td>"
        "<td>No</td><td>Fixture description.</td></tr>"
        "<tr><td>Fixture Spur Trail</td><td>white diamonds</td><td>0.2-mile one way</td><td>Moderate</td>"
        "<td>Hiking only</td><td>No</td><td>Fixture description.</td></tr></table>"
    )
    trails = _k_page("Fixture Mountain: Trails | NC State Parks", f"<h1>Trails</h1>{table}")
    return [(base, HTML, index), (f"{base}/fixture-mountain-state-park/trails", HTML, trails)]


def _cvatc_page() -> str:
    hikes = "".join(
        f"<p>Hike To Fixture Rock {n} - {n + 4} miles, out and back, moderate. Fixture directions 2 miles in.</p>" for n in (1, 2)
    )
    return _k_page("Fall Foliage Hikes", f"<h2>Great Fall Foliage Hikes In South Central PA</h2>{hikes}")


def _foothills_pages() -> list[tuple[str, str, str]]:
    index_url = "https://foothillstrail.org/section-by-section-2/"
    section_url = "https://foothillstrail.org/portfolio/fixture-a1/"
    index = _k_page("Section By Section", f'<h1>Section By Section</h1><a href="{section_url}"></a><h2>Fixture A1 to A2</h2>')
    section = _k_page(
        "Fixture A1 to A2",
        "<h1>Fixture Park (A1) To Fixture Mountain (A2)</h1><p>Foothills Trail Guide p. 1</p>"
        "<p>Distance: 9.7 miles</p><p>Difficulty: A1 to A2 – strenuous</p><p>A2 to A1 – moderate</p>"
        "<p>Blazes: White</p><p>Trail Head: A1 Fixture Park, SC Hwy 1</p><p>A2 Fixture Mountain, SC Hwy 2</p>"
        "<p>*Fixture note for campers.</p><p>Features:</p><ul><li>Fixture Falls</li></ul><h3>Contact Us</h3>",
    )
    return [(index_url, HTML, index), (section_url, HTML, section)]


def _cohos_page() -> str:
    rows = "".join(f"<tr><td>Fixture Trail {n}</td><td>Fixture Road</td><td>Easy</td><td>Waterfall</td></tr>" for n in (1, 2))
    table = f"<table><tr><td>Trail or Destination</td><td>Where</td><td>Rank</td><td>Feature</td></tr>{rows}</table>"
    return _k_page("Day Hikes", f"<h1>Day Hikes</h1><p>Fixture Favourite</p><p>Fixture prose.</p>{table}")


def _tuscarora_pages() -> list[tuple[str, str, str]]:
    home_url, page_url = "https://www.hikethetuscarora.org/", "https://www.hikethetuscarora.org/section-1-3"
    home = _k_page("Tuscarora Trail", f'<a href="{page_url}">Section 1-3</a>')
    sections = "".join(
        f"<p>Section {n}: Fixture Gap {n}</p><p>Fixture Road to Fixture Gap {n}, {n}.5 miles.</p><p>\u200b</p>"
        "<p>PATC Map J, Guide to the North Half of the Tuscarora Trail</p>"
        f"<p>Max Elevation: 1,620 ft. Min Elevation: 930 ft.</p><p>Highlights: Fixture overlook.</p>"
        "<p>Camping: Fixture Shelter (40.001, -77.001)</p>"
        for n in (1, 2)
    )
    return [(home_url, HTML, home), (page_url, HTML, _k_page("Section 1-3", sections))]


def _kta_page() -> str:
    hike = (
        '<span style="font-weight:700">Fixture Trail {n}</span><br /><span>Fixture County</span><br />'
        '<a href="https://fixture.example.org/{n}">https://fixture.example.org/{n}</a><br />'
        "<span>Fixture description, 2.2-mile loop.</span><br /><br /><em>Descripción.</em><br /><br />"
    )
    body = (
        "<h2>Favorite Beginner's Hikes - Fixture</h2>"
        f'<div class="paragraph">{hike.format(n=1)}{hike.format(n=2)}</div>'
        "<h2>Sign up for our newsletter:</h2>"
    )
    return _k_page("Favorite Hikes", body)


def _amc_page() -> str:
    trip = (
        "<h5>Fixture Traverse {n}</h5><p><strong>Strenuous | 3-4 Days</strong></p>"
        '<a href="https://www.outdoors.org/resources/itineraries/fixture-{n}/"><img src="x.jpg"/></a>'
        "<p>Fixture paragraph.</p>"
    )
    return _k_page("Itineraries", f"<h1>Outdoor Itineraries</h1><h2>Explore Fixture</h2>{trip.format(n=1)}{trip.format(n=2)}")


def _ata_pages() -> list[tuple[str, str, str]]:
    index_url = "https://aztrail.org/explore/passages/"
    passage_url = "https://aztrail.org/explore/passages/passage-1-fixture-mountains/"
    passage = _k_page(
        "Passage 1",
        "<h1>Passage 1: Fixture Mountains</h1><h3>Location</h3><p>Fixture Border to Fixture Trailhead</p>"
        "<h3>Length</h3><p>20.3 miles</p><h3>Southern Trailhead: Fixture Border</h3>"
        "<p>GPS Coordinates: 31.33367° N, 110.28276° W</p><h3>Northern Access Point: Fixture Trailhead</h3>"
        "<p>GPS Coordinates: 31.41946° N, 110.44206° W</p><h3>Difficulty</h3><p>Moderate.</p>"
        "<h3>Season(s)</h3><p>Spring and Fall</p><h3>Water</h3><p>Fixture water prose.</p>",
    )
    return [(index_url, HTML, _k_page("Passages", f'<a href="{passage_url}">Passage 1</a>')), (passage_url, HTML, passage)]


def _k_pages_documents() -> dict[str, list[tuple[str, str, str]]]:
    """Each ContentPages key's answers, as (url, content type, body)."""
    return {
        "mazamas_hike_list": [("https://mazamas.org/hikelist/", HTML, _mazamas_hike_list_page())],
        "tahoe_rim_day_hikes": _tahoe_rim_pages(),
        "nc_parks_trails": _nc_parks_pages(),
        "cvatc_foliage_hikes": [
            ("https://www.cvatclub.org/some-great-fall-foliage-hikes-in-south-central-pa.html", HTML, _cvatc_page())
        ],
        "foothills_sections": _foothills_pages(),
        "cohos_day_hikes": [("https://www.cohostrail.org/day-hike/", HTML, _cohos_page())],
        "patc_tuscarora_sections": _tuscarora_pages(),
        "kta_favorite_hikes": [("https://www.kta-hike.org/favorite-hikes-in-pennsylvania.html", HTML, _kta_page())],
        "amc_itineraries": [("https://www.outdoors.org/resources/itineraries/", HTML, _amc_page())],
        "ata_passages": _ata_pages(),
    }


#: What each fixture page's parser must land, which tests/test_extract_fixtures.py holds the warehouse to.
K_PAGES_ROWS = {
    "mazamas_hike_list": 8,
    "tahoe_rim_day_hikes": 2,
    "nc_parks_trails": 2,
    "cvatc_foliage_hikes": 2,
    "foothills_sections": 1,
    "cohos_day_hikes": 2,
    "patc_tuscarora_sections": 2,
    "kta_favorite_hikes": 2,
    "amc_itineraries": 2,
    "ata_passages": 1,
}


def _k_wordpress_documents() -> dict[str, dict]:
    """Section K's WordPress post types, in section C's document shape (_content_wordpress_documents())."""
    cdtc = "cdtcoalition.org"
    return {
        "cdtc_hike_suggestions": {
            "categories": [],
            "posts": [],
            "types": {
                "hike_suggestion": [
                    _content_wp_post(cdtc, 9301 + n, post_type="hike_suggestion", hike_suggestion_category=[700])
                    for n in range(2)
                ]
            },
            "terms": {"hike_suggestion_category": _wp_terms("hike_suggestion_category")},
        },
    }


def section_k_fixtures() -> dict[str, str]:
    """Section K's page answers, one conditions/json_apis/ document a key."""
    files = {}
    for key, answers in _k_pages_documents().items():
        document = {"answers": [_answer(url, body, None, content_type) for url, content_type, body in answers]}
        files[f"conditions/json_apis/{key}.json"] = json.dumps(document)
    return files


def write_fixtures(raw_dir: Path) -> list[str]:
    files = {
        "shelters.geojson": _atc_layer("Shelter", 3),
        "campsites.geojson": _atc_layer("Campsite", 2),
        "viewpoints.geojson": _atc_layer("Viewpoint", 2),
        "parking.geojson": _atc_layer("Parking", 2),
        "privies.geojson": _atc_layer("Privy", 2),
        "communities.geojson": _communities_layer(),
        "bridges.geojson": _atc_layer("Bridge", 2, extra={"Status": "Existing", "Type": "Foot Bridge", "Super_Stru": "Timber"}),
        "centerline.geojson": _atc_layer(
            "Centerline Segment",
            2,
            extra={
                "Status": "Existing",
                "Surface": "Native",
                "Reg_Acro": "NE",
                "Acronym": "TTC",
                "Length_Ft": lambda i: 500.0 + i,
            },
            geometry=_line,
        ),
        "side_trails.geojson": _atc_layer(
            "Side Trail",
            2,
            extra={
                "Status": "Existing",
                "Type": "Side Trail",
                "Blaze": "Blue",
                "Length_Ft": lambda i: 300.0 + i,
            },
            geometry=_line,
        ),
        "trail_club_sections.geojson": _club_sections_layer(),
        "half_mile_points_from_springer.geojson": _half_mile_layer(),
        **_elevation_fixtures(raw_dir),
        "at_treadway.geojson": _atc_layer(
            "Treadway",
            2,
            extra={
                "Status": "Existing",
                "Length_Ft": lambda i: 800.0 + i,
                "Year_Built": 1998,
                "Comments": "fixture row",
            },
            geometry=_line,
        ),
        "opentrail_at.geojson": _opentrail_layer(),
        # The non-A.T. organizations, under fetch_external_layers.py's own
        # subdirectory (Phase D). Every registered ArcGIS layer needs a
        # fixture or load_raw.py reports it skipped and the staging model
        # that reads it fails the build - tests/test_make_dbt_fixtures.py
        # asserts nothing is skipped, which is what keeps this list complete
        # as the registry grows.
        "external/oprhp_trails.geojson": _oprhp_trails_layer(),
        "external/oprhp_trail_closures.geojson": _oprhp_trail_closures_layer(),
        "external/oprhp_facilities.geojson": _oprhp_facilities_layer(),
        "external/oprhp_park_polygons.geojson": _oprhp_park_polygons_layer(),
        "external/nynjtc_long_path.geojson": _nynjtc_long_path_layer(),
        "external/nynjtc_highlands_trail.geojson": _nynjtc_highlands_trail_layer(),
        "external/mohonk_trails.geojson": _mohonk_trails_layer(),
        "external/usfs_trails.geojson": _usfs_trails_layer(),
        "external/usfs_rec_sites.geojson": _usfs_rec_sites_layer(),
        "external/njdep_park_trails.geojson": _njdep_park_trails_layer(),
        "external/nj_statewide_trails.geojson": _nj_statewide_trails_layer(),
        "external/nyc_parks_trails.geojson": _nyc_parks_trails_layer(),
        "external/nyc_park_polygons.geojson": _nyc_park_polygons_layer(),
        "external/nyc_dot_greenways.geojson": _nyc_dot_greenways_layer(),
        "external/nyc_cscl_paths.geojson": _nyc_cscl_paths_layer(),
        "external/nyc_park_drives.geojson": _nyc_park_drives_layer(),
        "external/nyc_public_restrooms.geojson": _nyc_public_restrooms_layer(),
        "external/nyc_drinking_fountains.geojson": _nyc_drinking_fountains_layer(),
        "external/dec_hiking_trails.geojson": _dec_hiking_trails_layer(),
        "external/dec_lean_tos.geojson": _dec_lean_tos_layer(),
        # Two sites under one ASSET_UID at two places, and one record repeated
        # exactly: the two shapes the live layer has (measured 2026-10-01).
        "external/dec_primitive_campsites.geojson": _dec_asset_layer(
            "PRIMITIVE TENT SITE",
            ["Fixture Tent Site 1", "Fixture Tent Site 2", "Fixture Tent Site 3", "Fixture Tent Site 3"],
            asset_uids=[15723, 15723, 3640, 3640],
            places=[0, 1, 2, 2],
        ),
        "external/dec_scenic_vistas.geojson": _dec_asset_layer("SCENIC VISTA", ["Fixture Vista"]),
        "external/dec_firetowers.geojson": _dec_asset_layer("FIRE TOWER", ["Fixture Mountain Firetower"]),
        "external/dec_viewing_areas.geojson": _dec_asset_layer("OBSERVATION PLATFORM", ["Fixture Viewing Area"]),
        # Two lots under one ASSET_UID, differing only by place (measured 2026-10-01).
        "external/dec_parking_areas.geojson": _dec_asset_layer(
            "UNPAVED PARKING LOT", ["Fixture Trailhead Parking", "Fixture Hunter Parking"], asset_uids=[3048, 3048]
        ),
        # The one DEC layer that is NOT a POI layer: an asset inventory whose
        # largest value is CULVERT at 4,290 features and whose PUBLICUSE flag
        # splits it 7,645 Y / 13,823 N on the live 21,468 rows (sources.json
        # carries all three figures). Both sides of the flag appear here,
        # which is the property the models are exercised against.
        #
        # WHAT THIS FIXTURE DOES NOT REPRODUCE, said plainly because a reader
        # who has just read sources.json will look for it: the whitespace
        # wart. `ASSET` upstream is free text with 234 values as stored and
        # 223 after trimming - 'FORD ' beside 'FORD', and a bare ' ' on 86
        # rows - and every row this script writes carries a clean value. A
        # fixture that trips the trimming would have to be built on purpose,
        # and nothing here does.
        #
        # `Fixture Culvert` is a NAME, not a type: both rows below are typed
        # PRIVY. The name is there to read as an inventory, and a model that
        # keyed on it rather than on `ASSET` would pass this fixture wrongly.
        #
        # The third row shares the first one's ASSET_UID and place under another
        # name: one group on the live layer does exactly that (measured
        # 2026-10-01), which is why this layer's key adds NAME.
        "external/dec_backcountry_features.geojson": _dec_asset_layer(
            "PRIVY",
            ["Fixture Privy", "Fixture Culvert", "Fixture Privy (renamed)"],
            publicuse=("Y", "N"),
            asset_uids=[228015, 228016, 228015],
            places=[0, 1, 0],
        ),
        # #1778's seventeen, each with the one column its registry row declares
        # spelled the way sources.json spells it - so a rename fails here
        # rather than in a dbt build, which is what this whole file is for.
        "external/nps_trails.geojson": _registered_trail_lines_layer("nps_trails", "TRLNAME"),
        "external/blm_trails.geojson": _registered_trail_lines_layer("blm_trails", None),
        "external/cotrex_trails.geojson": _registered_trail_lines_layer("cotrex_trails", "name"),
        "external/wa_rco_trails.geojson": _registered_trail_lines_layer("wa_rco_trails", "trail_name"),
        "external/utah_sgid_trails.geojson": _registered_trail_lines_layer("utah_sgid_trails", "PrimaryName"),
        "external/ncta_trail.geojson": _registered_trail_lines_layer("ncta_trail", "seg_name"),
        "external/alaska_trails.geojson": _registered_trail_lines_layer("alaska_trails", "TrailName"),
        "external/pasda_dcnr_trails.geojson": _registered_trail_lines_layer("pasda_dcnr_trails", "NAME01"),
        "external/ct_deep_blue_blazed.geojson": _registered_trail_lines_layer("ct_deep_blue_blazed", "TrailName"),
        "external/nc_mst_trail.geojson": _registered_trail_lines_layer("nc_mst_trail", "SYSTEMNAME"),
        "external/azgeo_arizona_trail.geojson": _registered_trail_lines_layer("azgeo_arizona_trail", "Name"),
        "external/tahoe_rim_trail.geojson": _registered_trail_lines_layer("tahoe_rim_trail", "Name"),
        "external/duluth_superior_hiking_trail.geojson": _registered_trail_lines_layer("duluth_superior_hiking_trail", "Name"),
        "external/massgis_long_distance_trails.geojson": _registered_trail_lines_layer("massgis_long_distance_trails", "NAME"),
        "external/pcta_centerline.geojson": _registered_trail_lines_layer("pcta_centerline", None),
        "external/cdtc_centerline.geojson": _registered_trail_lines_layer("cdtc_centerline", None),
        "external/wi_ice_age_trail.geojson": _registered_trail_lines_layer("wi_ice_age_trail", None),
        **{name: build() for name, build in ELEVATION_PRODUCT_FIXTURES.items()},
        **closures_and_warnings_fixtures(),
        **notice_layers_fixtures(),
        **suggested_hikes_fixtures(),
        **_club_places_fixtures(),
        **_club_trail_lines_fixtures(),
        **{name: _club_point_layer(*spec) for name, spec in CLUB_POINT_FIXTURES.items()},
        **gis_file_and_geo_api_fixtures(),
        **page_points_fixtures(),
        **section_k_fixtures(),
    }
    files = _trail_lines_network_fixtures(files)
    files = _trail_lines_at_fixtures(files)
    files = _points_of_interest_fixtures(files)
    files = _places_fixtures(files)
    files = content_fixtures(files)
    existing = [name for name in files if (raw_dir / name).exists()]
    if existing:
        raise SystemExit(
            f"Refusing to overwrite {', '.join(existing)} in {raw_dir} - these look like "
            "real fetched layers, and this script only fills an empty CI workspace."
        )
    for name, content in files.items():
        if name in KEY_FIELDS:
            content = _with_key_fields(content, KEY_FIELDS[name])
        path = raw_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)  # the elevation fixture's GeoTIFF (_elevation_fixtures)
        elif isinstance(content, dict):
            path.write_text(json.dumps(content))  # a _feature_collection(), dumped once here
        else:
            path.write_text(content)
    return sorted(files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    args = parser.parse_args()
    for name in write_fixtures(args.raw_dir):
        print(f"  {args.raw_dir / name}")
