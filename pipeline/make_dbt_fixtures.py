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
(2026-08-27), plus the structured `name_field`/`blaze_field`/`id_field`/
`public_field`/`asset_field`/`facility_field` keys, which are the same
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
carries both sides of its 5,822/3,000 split.

Refuses to write into a directory that already has one of its files:
this exists to fill an empty CI workspace, not to overwrite a real fetch.
"""

import argparse
import json
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
            {**common, "Name": "Fixture Ridge Trail", "Alt_Name": "Ridge", "Blaze": "Blue", "Map_Blaze": "Blue", "Miles": 1.4},
            {**common, "Name": "Fixture Loop Trail", "Alt_Name": None, "Blaze": "Red", "Map_Blaze": "Red", "Miles": 0.8},
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
    """
    return _features(
        [
            {
                "Name": "Fixture Spigot",
                "Facility": "Fixture State Park",
                "Asset": 7,
                "Sub_Asset": "Water Spigot",
                "ParksApp": "Y",
                "Public_": "Y",
            },
            {
                "Name": None,
                "Facility": "Fixture State Park",
                "Asset": 7,
                "Sub_Asset": "Drinking Fountain",
                "ParksApp": "N",
                "Public_": "Y",
            },
            {"Name": None, "Facility": "Fixture State Park", "Asset": 3, "Sub_Asset": "Lean-to", "ParksApp": "N", "Public_": "Y"},
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
    value at all - both shapes appear here."""
    common = {
        "General_Classification": "Trail",
        "Classification": "Foot",
        "Use_": "Hiking",
        "Surface": "Native",
        "Manager": "Mohonk Preserve",
    }
    return _features(
        [
            {**common, "Name": "Fixture Carriage Road", "Blaze": "Blue", "Mileage": 1.1, "Owner": "Mohonk Preserve"},
            {**common, "Name": "Fixture Ledge Path", "Blaze": "N/A", "Mileage": 0.6, "Owner": "Mohonk Preserve"},
            # No Blaze key at all - the 7-row shape, not an oversight.
            {**common, "Name": "Marakill Woods North", "Mileage": 0.4, "Owner": "NYS OPRHP/PIPC"},
        ],
        _line,
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
                "NAME": "Fixture Lean-to",
                "DESCRIP": "fixture row",
                "NOTES": "-99",
                "PHOTO_LINK": "M:\\DLF\\fixture.jpg",
                "PUBLICUSE": "Y",
            },
            {
                **common,
                "OBJECTID": 12,
                "NAME": "Fixture Brook Lean-to",
                "DESCRIP": None,
                "NOTES": None,
                "PHOTO_LINK": None,
                "PUBLICUSE": "Y",
            },
            {
                **common,
                "OBJECTID": 13,
                "NAME": "Fixture Maintenance Lean-to",
                "DESCRIP": None,
                "NOTES": None,
                "PHOTO_LINK": None,
                "PUBLICUSE": "N",
            },
        ],
        _point,
    )


def _dec_asset_layer(asset, names, publicuse=("Y",)):
    """The five other DEC per-type asset services.

    Six columns, and only six: sources.json records these layers' counts and
    their `id_field`/`name_field`/`asset_field`/`facility_field`/
    `public_field` plus a `freshness` field of UPDATED, and does NOT record a
    full field list the way it does for dec_lean_tos. dec_lean_tos' other
    columns are NOT assumed to carry across - a sibling service is evidence
    about itself, not about its siblings.
    """
    return _features(
        [
            {
                "OBJECTID": 100 + i,
                "NAME": name,
                "ASSET": asset,
                "FACILITY": "Fixture Wild Forest",
                "PUBLICUSE": publicuse[i % len(publicuse)],
                "UPDATED": "2026-08-18",
            }
            for i, name in enumerate(names)
        ],
        _point,
    )


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
        "external/dec_hiking_trails.geojson": _dec_hiking_trails_layer(),
        "external/dec_lean_tos.geojson": _dec_lean_tos_layer(),
        "external/dec_primitive_campsites.geojson": _dec_asset_layer(
            "PRIMITIVE TENT SITE", ["Fixture Tent Site 1", "Fixture Tent Site 2"]
        ),
        "external/dec_scenic_vistas.geojson": _dec_asset_layer("SCENIC VISTA", ["Fixture Vista"]),
        "external/dec_firetowers.geojson": _dec_asset_layer("FIRE TOWER", ["Fixture Mountain Firetower"]),
        "external/dec_viewing_areas.geojson": _dec_asset_layer("OBSERVATION PLATFORM", ["Fixture Viewing Area"]),
        "external/dec_parking_areas.geojson": _dec_asset_layer(
            "UNPAVED PARKING LOT", ["Fixture Trailhead Parking", "Fixture Hunter Parking"]
        ),
        # The one DEC layer that is NOT a POI layer: an asset inventory whose
        # largest value is CULVERT and whose PUBLICUSE flag splits it 7,645 Y
        # / 13,823 N on the live 21,468 rows. Both sides appear, and the
        # trailing-space ASSET value is the real hygiene wart sources.json
        # records ('FORD ' beside 'FORD'), not a typo here.
        "external/dec_backcountry_features.geojson": _dec_asset_layer(
            "PRIVY", ["Fixture Privy", "Fixture Culvert"], publicuse=("Y", "N")
        ),
    }
    existing = [name for name in files if (raw_dir / name).exists()]
    if existing:
        raise SystemExit(
            f"Refusing to overwrite {', '.join(existing)} in {raw_dir} - these look like "
            "real fetched layers, and this script only fills an empty CI workspace."
        )
    for name, content in files.items():
        path = raw_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return sorted(files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    args = parser.parse_args()
    for name in write_fixtures(args.raw_dir):
        print(f"  {args.raw_dir / name}")
