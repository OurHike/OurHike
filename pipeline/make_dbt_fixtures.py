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
    return json.dumps({"type": "FeatureCollection", "features": features})


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
    "external/nyc_park_polygons.geojson": {"system": lambda i: f"fixture-system-{i}"},
    "external/nyc_cscl_paths.geojson": {"globalid": lambda i: f"{{fixture-cscl-{i}}}"},
    "external/nyc_park_drives.geojson": {"globalid": lambda i: f"{{fixture-drive-{i}}}"},
}


def _with_key_fields(content: str, fields: dict) -> str:
    collection = json.loads(content)
    for index, feature in enumerate(collection["features"]):
        feature["properties"] = {**(feature.get("properties") or {}), **{name: value(index) for name, value in fields.items()}}
    return json.dumps(collection)


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


def _north(lon: float, lat: float, degrees: float) -> dict:
    """A due-north LineString `degrees` of latitude long (0.3 is about 20.7 mi)."""
    return {"type": "LineString", "coordinates": [[lon, lat], [lon, round(lat + degrees, 6)]]}


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


def _trail_lines_network_fixtures(files: dict[str, str]) -> dict[str, str]:
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
        collection = json.loads(out[name])
        collection["features"] += added
        out[name] = json.dumps(collection)

    usfs = json.loads(out["external/usfs_trails.geojson"])
    for feature in usfs["features"]:
        properties = feature["properties"]
        if properties.get("trail_type") != "TERRA":
            continue
        if properties.get("trail_name") == "FIXTURE GREAT GULF":
            properties["terra_motorized"] = "N/A"
        elif properties.get("national_trail_designation") == 2:
            properties["terra_motorized"] = "Y"
        else:
            properties["terra_motorized"] = "N"
    out["external/usfs_trails.geojson"] = json.dumps(usfs)

    parks = json.loads(out["external/nyc_park_polygons.geojson"])
    parks["features"] += [
        {
            "type": "Feature",
            "properties": {"signname": name, "gispropnum": f"FIXTURE-{index}"},
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        }
        for index, (name, ring) in enumerate(NETWORK_PARK_BOUNDARIES.items())
    ]
    out["external/nyc_park_polygons.geojson"] = json.dumps(parks)

    mapping = json.loads((Path(__file__).parent / "reference" / "blaze_mapping.json").read_text(encoding="utf-8"))["sources"]
    entries = {entry["key"]: entry for entry in registry["sources"]}
    for name in files:
        key = Path(name).stem
        entry = entries.get(key, {})
        if not name.startswith("external/") or entry.get("kind") not in ("external_arcgis_layer", "socrata_geojson_layer"):
            continue
        if "blaze_field" not in entry and "blaze_default" not in entry:
            continue
        collection = json.loads(out[name])
        for index, feature in enumerate(collection["features"]):
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
        out[name] = json.dumps(collection)
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
    # 44 m from the fixture's third shelter, (-73.98, 41.02).
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
    # Two vertices a hundred-thousandth of a metre apart, which six decimals
    # would put on one point: the never-degenerate rule keeps full precision.
    _side_trail(
        "Short Stub",
        [[-73.9950001, 41.0040001], [-73.9950002, 41.0040002]],
        {"Type": "4", "Blaze": "5", "Length_Ft": 0.1},
    ),
]


def _trail_lines_at_fixtures(files: dict[str, str]) -> dict[str, str]:
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
    """
    out = dict(files)
    for name, added in (("centerline.geojson", []), ("side_trails.geojson", TRAIL_LINES_AT_SIDE_TRAILS)):
        collection = json.loads(out[name])
        collection["features"] += [json.loads(json.dumps(feature)) for feature in added]
        for index, feature in enumerate(collection["features"]):
            feature["properties"]["OBJECTID"] = index + 1
            feature["id"] = index + 1
        out[name] = json.dumps(collection)
    return out


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
    }
    files = _trail_lines_network_fixtures(files)
    files = _trail_lines_at_fixtures(files)
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
        else:
            path.write_text(content)
    return sorted(files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    args = parser.parse_args()
    for name in write_fixtures(args.raw_dir):
        print(f"  {args.raw_dir / name}")
