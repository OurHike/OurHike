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
(2026-08-27), usfs_trails, usfs_rec_sites and nh_granit_trails
(2026-09-02), plus the structured `name_field`/`blaze_field`/`id_field`/
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


def _nh_granit_trails_layer():
    """nh_granit_trails' field list and value shapes as republished in
    September 2026, read live 2026-09-26 (#1646).

    THE POINT OF THIS FIXTURE IS THAT THE USE FLAGS SAY FOUR THINGS, NOT TWO.
    Every use column - HIKING, SNOWMACHIN, OHRV, ALPINESKI, PADDLE and the rest -
    reads 'Y', 'N', 'NA', 'UNKNOWN' or a blank STRING, and only 'Y' and 'N' are
    statements. HIKING is 'Y' on 8,312 of 15,791 rows, 'NA' on 4,022, blank on
    3,255, 'UNKNOWN' on 154 and 'N' on 48, and the A.T.'s own GRANIT rows are
    among the unrecorded - so a staging model that read HIKING as a boolean
    would delete them. The fixture carries one row of each shape the
    exporter's filter decides differently: flagged for hiking, unrecorded,
    a snowmobile corridor, a corridor ALSO flagged for hiking (kept), an alpine
    ski run and a paddle route.

    The 2026-09-02 version of this fixture carried BLAZE, PED, SNOWMBL and
    MAINTORG. GRANIT dropped all four; a fixture keeping them would let a
    staging model be written against columns the live layer does not have."""
    common = {
        "ACCURACY": "2",
        "TOWNNAME": "FIXTURE TOWNSHIP",
        "COUNTY": "COOS",
        "SEASONAL": "UNKNOWN",
        "SURFACE": "UNKNOWN",
        "MAINTAINED": " ",
        "PUBLICDOMA": "Y",
        "SOURCE": "GRANIT",
        "HIKING": "NA",
        "SNOWMACHIN": "NA",
        "OHRV": "NA",
        "SNOW_CORRI": "NA",
        "OHRV_CORRI": "NA",
        "ALPINESKI": "NA",
        "PADDLE": "NA",
    }
    return _features(
        [
            {**common, "TRAILNAME": "Fixture Ridge Path", "HIKING": "Y", "Shape_Length": 11616.0},
            # Unrecorded, and a hiking trail anyway - the shape the A.T.'s own
            # GRANIT rows take, and the one a HIKING == 'Y' filter would delete.
            {**common, "TRAILNAME": "APPALACHIAN TRL", "HIKING": " ", "Shape_Length": 16368.0},
            # A snowmobile corridor not flagged for hiking - dropped.
            {
                **common,
                "TRAILNAME": "FIXTURE CORRIDOR 11 TRL",
                "SNOWMACHIN": "Y",
                "SNOW_CORRI": "Y",
                "MAINTAINED": "FIXTURE SNOWMOBILE CLUB",
                "SOURCE": "DESC",
                "Shape_Length": 21120.0,
            },
            # The same flag on a row GRANIT also opens to hikers - kept.
            {**common, "TRAILNAME": "Fixture Woods Road", "HIKING": "Y", "SNOWMACHIN": "Y", "Shape_Length": 7392.0},
            {
                **common,
                "TRAILNAME": "FIXTURE SKI RUN",
                "HIKING": "UNKNOWN",
                "ALPINESKI": "Y",
                "SEASONAL": "WINTER_ONLY",
                "Shape_Length": 3168.0,
            },
            {**common, "TRAILNAME": "FIXTURE RIVER PADDLERS' TRAIL", "HIKING": "N", "PADDLE": "Y", "Shape_Length": 52800.0},
        ],
        _white_mountains_line,
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
        "external/usfs_trails.geojson": _usfs_trails_layer(),
        "external/usfs_rec_sites.geojson": _usfs_rec_sites_layer(),
        "external/nh_granit_trails.geojson": _nh_granit_trails_layer(),
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
