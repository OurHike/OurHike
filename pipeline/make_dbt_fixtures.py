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
    return {"answers": [_answer(FMST_KML_URL, body, {"forcekml": "1"}, "text/xml; charset=utf-8")]}


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


def closures_and_warnings_fixtures() -> dict[str, str]:
    """The closures and warnings family's fixture files, under conditions/: NWS, NYNJTC's WordPress, OurHike's Postgres,
    ATC's site, and the JSON API notice sources."""
    return {
        "conditions/nws_alerts.json": json.dumps(_nws_alerts()),
        "conditions/nynjtc_trail_alerts.json": json.dumps(_nynjtc_trail_alerts()),
        "conditions/ourhike_postgres.json": json.dumps(_ourhike_postgres()),
        "conditions/atc_trail_updates.json": json.dumps(_atc_trail_updates()),
        "weather/squares.json": json.dumps(_weather_squares(), separators=(",", ":")),
        **_json_api_fixtures(),
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
            "ContactOffice": "Fixture Project Office",
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
    }
    files = _trail_lines_network_fixtures(files)
    files = _trail_lines_at_fixtures(files)
    files = _points_of_interest_fixtures(files)
    files = _places_fixtures(files)
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
