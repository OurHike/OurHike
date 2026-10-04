"""The points_of_interest family's SQL answers what today's three exporters answer, on the same rows (#1793, stage 3).

export_poi.py, export_nearby_poi.py and export_retired_poi.py moved to SQL
(pipeline/ELT.md's ledger rows PO01-PO38), and until stage 5 deletes the Python
both are live. parity.py compares the ten phone files on the fixture warehouse
in CI; this holds what the fixtures never reach, by running today's Python over
each dbt unit test's own rows (models/intermediate/points_of_interest/
_points_of_interest__unit_tests.yml) and holding every expected row to the
Python's answer:

- each unit test's mocked seeds are the seed files, row for row, and its
  registry entries are sources.json's own on every key a rule reads;
- the seeds and vars the rules read are the Python's constants;
- every expected row is what the Python function the unit test is named after
  answers on the same rows, except where DELIBERATE says the SQL differs on
  purpose and why, and except decision 65's typed taps (DECISION_65_VALUE_TYPES),
  which the Python is given before it answers;
- the one kind of difference parity.py explains on the fixtures (an exact copy
  that staging removes) is named in DELIBERATE, so emptying it turns this red.

dbt runs the other half: each unit test holds the SQL to those expectations.
The answer functions here are also what the expectations were generated from,
so a unit test row whose expectation the Python does not give fails here.
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Iterable, Iterator
from pathlib import Path
from unittest import mock

import duckdb
import numpy as np
import pytest
import shapely
import yaml
from shapely.geometry import LineString

import build_osm_water_reach
import export_elevation
import export_nearby_poi
import export_poi
import fetch_trail_water
import make_dbt_fixtures
import parity
from lib import atc_notes, corridor, photo_screen, poi_description, poi_identity, poi_sites, spurs

PIPELINE = Path(__file__).parent.parent
DBT = PIPELINE / "dbt"
UNIT_TESTS = DBT / "models" / "intermediate" / "points_of_interest" / "_points_of_interest__unit_tests.yml"

DESCRIBED = "int_points_of_interest__described_says_what_lib_poi_description_says"
COMPOSED = "int_points_of_interest__described_composes_what_compose_description_composes"
STREAMS = "int_points_of_interest__described_says_what_describe_stream_point_says"
SITES = "int_points_of_interest__sites_groups_like_lib_poi_sites"
CLASSIFIED = "int_points_of_interest__classified_types_and_refuses_like_the_exporters"
PUBLISHABLE = "int_points_of_interest__publishable_keeps_and_rates_like_public_verdict"
IN_CORRIDOR = "int_points_of_interest__in_corridor_keeps_what_the_corridor_and_the_ring_keep"
NO_NETWORK = "int_points_of_interest__in_corridor_applies_no_ring_without_a_network"
LONG_LINES = "int_points_of_interest__in_corridor_asks_a_long_line_segment_by_segment"
TRAILHEADS = "int_points_of_interest__trailheads_marks_like_mark_closed_trailheads"
NO_SIDE_TRAILS = "int_points_of_interest__trailheads_marks_nothing_without_the_side_trails"
TRAILHEAD_SEGMENTS = "int_points_of_interest__trailheads_counts_a_line_once_when_asked_by_segment"
MILES = "int_points_of_interest__miles_reads_the_axis_like_attach_miles"
IDENTIFIED = "int_points_of_interest__identified_applies_the_ledger_like_apply_ledger_ids"
RETIRED = "int_points_of_interest__retired_resolves_like_lib_poi_identity"
WATER = "int_points_of_interest__water_attaches_and_synthesizes_like_export_poi"
HELD_WATER = "int_points_of_interest__water_holds_a_point_whose_id_the_ledger_retired"
ENRICHED = "int_points_of_interest__enriched_attaches_capacity_and_nearby_like_export_poi"
OSM_DESCRIBED = "int_points_of_interest__described_says_what_describe_water_says"
OSM_REACH = "int_points_of_interest__osm_water_reach_measures_like_measure_distances"
REACHED = "int_points_of_interest__reached_gates_and_marks_like_export_poi"
DEDUPLICATED = "int_points_of_interest__deduplicated_drops_twins_like_dedupe_water"
PHOTOS = "int_points_of_interest__photos_gates_and_attaches_like_export_poi"

# The differences between the SQL and today's Python that a decision or an
# improvement explains, by where they are. Emptying a list turns a test red,
# because the difference is still there.
DELIBERATE = {
    # parity.py's one explained difference on the fixture warehouse
    # (POI_REASONS["exact_copy"], decision 40): dec_primitive_campsites' row
    # with OBJECTID 103 is an exact copy of OBJECTID 102 in every column but
    # OBJECTID, and staging keeps one.
    "nearby_poi": {"properties.id dec_primitive_campsites:103": "exact_copy"},
    # The miles unit test's point on a junction, where two pieces tie at
    # distance 0.
    "miles": {"atc_shelters:m-04-on-the-junction": "junction_tie"},
}


def _decision_65_value_types() -> dict[tuple[str, str], str]:
    """The value-map rows the dbt path adds to export_nearby_poi.py's, read from layer_rules' plumbed_water rows.

    Decision 65 (2026-10-04) ships a plumbed tap whose layer records no shutoff season as unconfirmed water with a
    season caution. For a layer typed per row by TYPED_LAYERS (NY Parks'), that means the poi_value_types seed types
    the tap water, where today's exporter names it a water holdback. Read from the one home of the decision's rows, so
    the seed and the caution cannot name different taps.
    """
    with (DBT / "seeds" / "layer_rules.csv").open(newline="") as handle:
        rules = [row for row in csv.DictReader(handle) if row["rule"] == "plumbed_water"]
    return {(row["source_key"], row["matches"]): "water" for row in rules if row["source_key"] in export_nearby_poi.TYPED_LAYERS}


DECISION_65_VALUE_TYPES = _decision_65_value_types()


def _with_decision_65(key: str):
    """export_nearby_poi.py's folded value maps with decision 65's rows for `key` added, for one build_records()."""
    field, folded = export_nearby_poi.TYPED_LAYERS_FOLDED.get(key, (None, None))
    if folded is None:
        return mock.patch.dict(export_nearby_poi.TYPED_LAYERS_FOLDED, {})
    added = {value.casefold(): poi_type for (source_key, value), poi_type in DECISION_65_VALUE_TYPES.items() if source_key == key}
    return mock.patch.dict(export_nearby_poi.TYPED_LAYERS_FOLDED, {key: (field, {**folded, **added})})


#: Why each deliberate difference is one.
WHY = {
    "exact_copy": parity.POI_REASONS["exact_copy"],
    "junction_tie": (
        "expected by the trail_lines family's tie rule (macros/axis_mile.sql, the lead's call of 2026-10-02): where one "
        "piece ends and the next begins, the SQL reads the point on the piece it does not end on, then on the lower "
        "piece_id, while shapely's STRtree breaks a tie by its own visiting order, which its docstring calls possibly "
        "nondeterministic. On this unit test's three pieces STRtree picks piece 0, the one the point ends; at the one "
        "live junction the trail_lines family measured it picked the one not ended on, as the SQL does. @unvalidated "
        "for POIs: nobody has counted how many published POIs sit at a tie, and what would settle it is that count on "
        "a live release"
    ),
}

# ATC's field names as lib/poi_description.py's describers and lib/atc_notes.py
# read them. The warehouse holds them lower-cased (dlt's sql_ci_v1 naming), so a
# unit test's rows hold them so, and the Python is handed them back in ATC's
# case. test_the_describers_read_no_field_this_list_lacks keeps it complete.
ATC_DESCRIPTION_FIELDS = (
    "ADA_Space",
    "Chimneys",
    "Comments",
    "Deck_Lengt",
    "Enclosure",
    "Exterior_M",
    "Food_Boxe",
    "Food_Cabl",
    "Food_Pole",
    "Left_Beari",
    "Location",
    "Metal_Fir",
    "Mortared",
    "Parking_S",
    "Right_Bear",
    "Site_Num",
    "Stories",
    "Surface",
    "Tent_Pads",
    "Tent_Plat",
    "Type",
    "Year_Built",
)


# --- reading the unit tests -------------------------------------------------------


def _document() -> dict:
    return yaml.safe_load(UNIT_TESTS.read_text())


def _unit_test(name: str) -> dict:
    return next(test for test in _document()["unit_tests"] if test["name"] == name)


def _given(test: dict, model: str) -> list[dict] | str:
    """One given input's rows: a list of dicts, or the SQL text of a `format: sql` input."""
    return next(given["rows"] for given in test["given"] if given["input"] == f"ref('{model}')")


def _given_or_none(test: dict, model: str) -> list[dict] | str | None:
    """One given input's rows, or None where the unit test gives no such input."""
    return next((given["rows"] for given in test["given"] if given["input"] == f"ref('{model}')"), None)


def _expected(test: dict, key: str) -> dict[str, dict]:
    return {row[key]: row for row in test["expect"]["rows"]}


def _seed_file(name: str) -> list[dict]:
    """A seed CSV as dbt loads it, an empty cell as null."""
    with (DBT / "seeds" / f"{name}.csv").open(newline="") as handle:
        return [{key: (value if value != "" else None) for key, value in row.items()} for row in csv.DictReader(handle)]


def _text(value) -> str | None:
    """A YAML or CSV scalar, as the text dbt would cast it from."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _member(field: str) -> str:
    """The JSON member a source field lands under (macros/poi_field_member.sql)."""
    return "_socrata_id" if field == ":id" else field.lower()


def _restored(landed: dict, spellings: Iterable[str | None]) -> dict:
    """A landed row's properties under the names the Python reads them by."""
    names = {_member(name): name for name in spellings if name}
    return {names.get(key, key): value for key, value in landed.items() if key != "feature_id"}


def _geometry(wkt: str | None) -> dict | None:
    """A unit test's WKT as the GeoJSON geometry a raw file holds."""
    return None if wkt is None else json.loads(shapely.to_geojson(shapely.from_wkt(wkt)))


def _feature(row: dict, spellings: Iterable[str | None]) -> dict:
    landed = json.loads(row["properties"])
    feature = {"type": "Feature", "geometry": _geometry(row.get("geom")), "properties": _restored(landed, spellings)}
    if landed.get("feature_id") is not None:
        feature["id"] = landed["feature_id"]
    return feature


def _collection(features: list[dict]) -> str:
    return json.dumps({"type": "FeatureCollection", "features": features})


def _lines_file(path: Path, rows: list[dict], status: bool = False) -> Path:
    """Line rows as a GeoJSON file the Python reads: `geom` as WKT or `geom_geojson` as GeoJSON."""
    features = []
    for row in rows:
        geometry = json.loads(row["geom_geojson"]) if "geom_geojson" in row else _geometry(row.get("geom"))
        properties = {"trail_status": row.get("trail_status")} if status else {"name": row.get("name")}
        features.append({"type": "Feature", "geometry": geometry, "properties": properties})
    path.write_text(_collection(features))
    return path


def _spatial() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    return con


def _at_spellings(source_key: str) -> tuple[str, ...]:
    if source_key == export_poi.OPENTRAIL_SOURCE:
        return (*export_poi.OPENTRAIL_FIELD_MAP_BASE.values(), "icon")
    field_map = next(field_map for stem, _, _, field_map in export_poi.DIRECT_SOURCES if stem == source_key)
    return (field_map["id_field"], field_map["name_field"], *ATC_DESCRIPTION_FIELDS)


def _nearby_spellings(entry: dict) -> tuple[str | None, ...]:
    return (
        entry.get("id_field", "OBJECTID"),
        entry.get("name_field", "NAME"),
        entry.get("asset_field"),
        entry.get("facility_field"),
        entry.get("public_field"),
        export_nearby_poi.TYPED_LAYERS.get(entry["key"], (None, None))[0],
    )


AT_STEMS = (*(stem for stem, _, _, _ in export_poi.DIRECT_SOURCES), export_poi.OPENTRAIL_SOURCE)


# --- the Python's answer to each unit test, keyed as its expected rows are --------


def described_answers(test: dict) -> dict[str, dict]:
    """export_poi.attach_descriptions() and compose_description() on the given rows (PO19, PO20)."""
    rows = _given(test, "int_points_of_interest__enriched")
    guide = {row["id"]: row["description"] for row in _given_or_none(test, "stg_derived__long_path_guide") or []}
    answers = {}
    for row in rows:
        landed = json.loads(row["properties"]) if row.get("properties") else {}
        if row["phone_files"] == "poi_by_type":
            record = {
                "poi_type": row["poi_type"],
                "capacity": row.get("capacity"),
                export_poi.RAW_PROPERTIES_KEY: _restored(landed, ATC_DESCRIPTION_FIELDS),
            }
            export_poi.attach_descriptions([record])
            answers[row["poi_id"]] = {"description": record.get("description")}
        elif row["poi_id"] in guide:
            # export_nearby_poi.py's guide_records(): the record's own sentence, as build_records() composed it.
            answers[row["poi_id"]] = {"description": guide[row["poi_id"]]}
        else:
            source = {"asset_field": "ASSET", "facility_field": "FACILITY"}
            description = export_nearby_poi.compose_description(
                source, {"ASSET": row.get("asset"), "FACILITY": row.get("facility")}
            )
            answers[row["poi_id"]] = {"description": description}
    return answers


def sites_answers(test: dict) -> dict[str, dict]:
    """lib/poi_sites.py's group_sites() and group_place_sites(), in record order (PO18, PO35)."""
    rows = sorted(_given(test, "int_points_of_interest__identified"), key=lambda row: (row["file_order"], row["source_row"]))
    records = {
        files: [
            {"id": row["poi_id"], "poi_type": row["poi_type"], "name": row["name"], "lat": row["lat"], "lon": row["lon"]}
            for row in rows
            if row["phone_files"] == files
        ]
        for files in ("poi_by_type", "nearby_poi")
    }
    properties = poi_sites.site_properties(poi_sites.group_sites(records["poi_by_type"]))
    properties.update(poi_sites.site_properties(poi_sites.group_place_sites(records["nearby_poi"])))
    return {
        row["poi_id"]: {name: properties.get(row["poi_id"], {}).get(name) for name in ("site_id", "site_role", "site_name")}
        for row in rows
    }


def classified_answers(test: dict, workdir: Path) -> dict[str, dict]:
    """unify_all_sources() over raw files written from the A.T. rows, and build_records() on each other row (PO01-PO04, PO30-PO32, PO37).

    Only what the Python decides: the published id, type, confidence, name and
    trail id of a row that ships, and the reason one does not, where the Python
    says it (`skipped` for 'no geometry'; build_records()' tally for the rest).
    An icon that publishes nothing is skipped uncounted, so its row is the one
    neither list names.
    """
    rows = sorted(_given(test, "int_points_of_interest__unioned"), key=lambda row: (row["source_key"], row["source_row"]))
    registry = {row["source_key"]: json.loads(row["entry"]) for row in _given(test, "stg_registry__sources")}
    raw = workdir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    files: dict[str, list[dict]] = {stem: [] for stem in AT_STEMS}
    for row in rows:
        if row["source_key"] in files:
            files[row["source_key"]].append(_feature(row, _at_spellings(row["source_key"])))
    for stem, features in files.items():
        (raw / f"{stem}.geojson").write_text(_collection(features))
    skipped: list[str] = []
    with mock.patch.object(export_poi, "RAW_DIR", raw), mock.patch.object(export_poi, "TRAIL_WATER_PATH", raw / "absent.json"):
        unified = {record["id"]: record for record in export_poi.unify_all_sources(skipped=skipped)}

    answers = {}
    for row in rows:
        if row["source_key"] in files:
            landed = json.loads(row["properties"])
            spellings = _at_spellings(row["source_key"])
            properties = _restored(landed, spellings)
            source = next((s for stem, _, s, _ in export_poi.DIRECT_SOURCES if stem == row["source_key"]), row["source_key"])
            id_field = spellings[0]
            derived = f"{source}:{properties.get(id_field) if properties.get(id_field) is not None else landed.get('feature_id')}"
            if derived in unified:
                record = unified[derived]
                answers[row["poi_key"]] = {
                    "derived_id": record["id"],
                    "source_feature_id": str(record["source_feature_id"]),
                    "trail_id": record["trail_id"],
                    "name": record["name"],
                    "poi_type": record["poi_type"],
                    "family_confidence": record["confidence"],
                    "drop_reason": None,
                }
            elif derived in skipped:
                answers[row["poi_key"]] = {"derived_id": derived, "drop_reason": "no geometry"}
            else:
                answers[row["poi_key"]] = {"derived_id": derived, "drop_reason": "icon not published"}
            continue
        entry = registry[row["source_key"]]
        feature = _feature(row, _nearby_spellings(entry))
        with _with_decision_65(row["source_key"]):
            records, stats = export_nearby_poi.build_records(entry, [feature])
        if records:
            (record,) = records
            answers[row["poi_key"]] = {
                "derived_id": record["id"],
                "source_feature_id": str(record["source_feature_id"]),
                "trail_id": record["trail_id"],
                "name": record["name"],
                "poi_type": record["poi_type"],
                "family_confidence": None,
                "asset": export_nearby_poi.clean(feature["properties"].get(entry.get("asset_field"))),
                "facility": export_nearby_poi.clean(feature["properties"].get(entry.get("facility_field"))),
                "drop_reason": None,
            }
        else:
            (reason,) = stats["dropped"]
            answers[row["poi_key"]] = {"drop_reason": reason}
    return answers


def publishable_answers(test: dict) -> dict[str, dict | None]:
    """public_verdict() and confidence_for() on each other organization's row, then may_publish (PO27-PO29).

    An A.T.-family row reads no public flag (export_poi.py), so it ships at the
    confidence classification gave it. may_publish is the SQL's own gate, which
    publish.py's reaches_hikers hold-back answers for the Python, so a row whose
    source may not publish ships in neither. None is a row that does not ship.
    """
    publication = {row["source_key"]: row["may_publish"] for row in _given(test, "int_sources__publication")}
    answers: dict[str, dict | None] = {}
    for row in _given(test, "int_points_of_interest__classified"):
        if row["phone_files"] == "poi_by_type":
            keep, confidence = True, row["family_confidence"]
        else:
            entry = json.loads(row["registry_entry"])
            properties = _restored(json.loads(row["properties"]), _nearby_spellings(entry))
            keep, confidence = export_nearby_poi.public_verdict(entry, properties)
            confidence = export_nearby_poi.confidence_for(entry, confidence)
        ships = keep and bool(publication.get(row["source_key"]))
        answers[row["poi_key"]] = {"confidence": confidence} if ships else None
    return answers


def in_corridor_answers(test: dict, workdir: Path) -> dict[str, dict | None]:
    """lib/corridor.py's build_corridor() and export_poi.clip_to_corridor() on the A.T. rows, clip_to_network() on the rest (PO05, PO33)."""
    workdir.mkdir(parents=True, exist_ok=True)
    rows = _given(test, "int_points_of_interest__publishable")
    centerline = _lines_file(workdir / "centerline.geojson", _given(test, "stg_atc__centerline_segments"))
    network = _lines_file(workdir / "nearby_trails.geojson", _given(test, "int_trail_lines__network_published"), status=True)
    boundaries = workdir / "nyc_park_polygons.geojson"
    boundaries.write_text(
        _collection(
            [
                {"type": "Feature", "geometry": _geometry(row["geom"]), "properties": {}}
                for row in _given(test, "base_nycparks__nyc_park_polygons")
            ]
        )
    )

    con = _spatial()
    corridor.build_corridor(con, centerline, network)
    trail = [{"id": row["poi_key"], "lat": row["lat"], "lon": row["lon"]} for row in rows if row["phone_files"] == "poi_by_type"]
    kept = {record["id"] for record in export_poi.clip_to_corridor(con, trail)}

    others = [
        {"id": row["poi_key"], "poi_type": row["poi_type"], "source": row["source_key"], "lat": row["lat"], "lon": row["lon"]}
        for row in rows
        if row["phone_files"] == "nearby_poi"
    ]
    boundary_paths = {
        row["source_key"]: workdir / f"{row['boundary_source']}.geojson" for row in rows if row.get("boundary_source")
    }
    clipped, _ = export_nearby_poi.clip_to_network(others, network, boundary_paths)
    kept |= {record["id"] for record in clipped}
    return {row["poi_key"]: ({"source_key": row["source_key"]} if row["poi_key"] in kept else None) for row in rows}


def trailheads_answers(test: dict, workdir: Path) -> dict[str, dict]:
    """mark_closed_trailheads() against the unit test's network and A.T. lines (PO34).

    An A.T. layer the unit test gives no rows is a file the Python cannot find.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    network = _lines_file(workdir / "nearby_trails.geojson", _given(test, "int_trail_lines__network_published"), status=True)
    at_paths = []
    for model, stem in (("stg_atc__centerline_segments", "centerline"), ("stg_atc__side_trails", "side_trails")):
        rows = _given(test, model)
        at_paths.append(_lines_file(workdir / f"{stem}.geojson", rows) if rows else workdir / f"{stem}.absent.geojson")
    records = [
        {"id": row["poi_id"], "poi_type": row["poi_type"], "lon": row["lon"], "lat": row["lat"]}
        for row in _given(test, "int_points_of_interest__identified")
        if row["phone_files"] == "nearby_poi"
    ]
    export_nearby_poi.mark_closed_trailheads(records, network, tuple(at_paths))
    return {
        record["id"]: {"trails_closed_within_m": record.get(export_nearby_poi.TRAILS_CLOSED_PROPERTY)}
        for record in records
        if record["poi_type"] == "trailhead"
    }


def _axis(test: dict, con: duckdb.DuckDBPyConnection) -> list[export_elevation.CalibratedPart]:
    """The unit test's mocked int_trail_lines__mile_axis, as export_elevation.calibrated_trail_axis() returns it.

    The input is `format: sql` (its anchors are lists), so DuckDB runs it.
    """
    pieces = con.execute(
        f"select piece_id, st_astext(geom_5070), anchor_along_mi, anchor_mile from ({_given(test, 'int_trail_lines__mile_axis')}) "
        "order by piece_id"
    ).fetchall()
    assert [piece[0] for piece in pieces] == list(range(len(pieces))), "piece_id is the axis list's index, from 0"
    return [
        export_elevation.CalibratedPart(LineString(shapely.from_wkt(wkt).coords), np.array(alongs), np.array(miles))
        for _, wkt, alongs, miles in pieces
    ]


def miles_answers(test: dict) -> dict[str, dict]:
    """export_poi.attach_miles() on the given POIs, the axis being the unit test's own (PO10, PO11)."""
    con = _spatial()
    axis = _axis(test, con)
    rows = [row for row in _given(test, "int_points_of_interest__enriched") if row["phone_files"] == "poi_by_type"]
    records = [
        {
            "id": row["poi_id"],
            "lon": row["lon"],
            "lat": row["lat"],
            **({export_poi.NOT_ON_AT_KEY: row["not_on_at"]} if row.get("not_on_at") else {}),
        }
        for row in rows
    ]
    with mock.patch.object(export_poi, "calibrated_trail_axis", lambda *_: axis):
        export_poi.attach_miles(con, records, Path("centerline"), Path("markers"))
    return {record["id"]: {"mile": record["mile"]} for record in records if record.get("mile") is not None}


def _ledger(rows: list[dict]) -> dict:
    """base_ourhike__poi_identity's rows as reference/poi_identity.json's `pois`, a null left out as the file leaves it."""
    keys = ("name", "poi_type", "source", "source_feature_id", "retired", "superseded_by")
    pois = {}
    for row in rows:
        pois[row["poi_id"]] = {key: row[key] for key in keys if row.get(key) is not None}
        if row.get("latitude") is not None:
            pois[row["poi_id"]].update(lat=row["latitude"], lon=row["longitude"])
    return pois


def identified_answers(test: dict, workdir: Path) -> dict[str, dict]:
    """apply_ledger_ids() on the A.T. rows; the other organizations' rows keep their derived ids, unledgered (PO23)."""
    workdir.mkdir(parents=True, exist_ok=True)
    ledger = workdir / "poi_identity.json"
    ledger.write_text(json.dumps({"pois": _ledger(_given(test, "base_ourhike__poi_identity"))}))
    rows = _given(test, "int_points_of_interest__deduplicated")
    records = {
        row["poi_key"]: {"id": row["derived_id"], "source": row["source"], "source_feature_id": row["source_feature_id"]}
        for row in rows
    }
    export_poi.apply_ledger_ids([records[row["poi_key"]] for row in rows if row["phone_files"] == "poi_by_type"], ledger)
    return {key: {"poi_id": record["id"]} for key, record in records.items()}


def _point_collection(path: Path, rows: list[dict], properties) -> Path:
    path.write_text(
        _collection(
            [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
                    "properties": properties(row),
                }
                for row in rows
            ]
        )
    )
    return path


def osm_water_reach_answers(test: dict, workdir: Path) -> dict[str, dict | None]:
    """build_osm_water_reach.measure_distances() over the unit test's lines, sites and OSM points (PO06).

    The script reads data/raw/ and the published network file, so the unit
    test's rows are written as those files in `workdir`. Its network keys are
    the registry's shipped ones (shipped_network_keys()), here the mocked
    registry rows' `reaches_hikers`.
    """
    import build_osm_water_reach as reach

    workdir.mkdir(parents=True, exist_ok=True)
    _lines_file(workdir / "centerline.geojson", _given(test, "stg_atc__centerline_segments"))
    _lines_file(workdir / "side_trails.geojson", _given(test, "stg_atc__side_trails"))
    network = workdir / "nearby_trails.geojson"
    network.write_text(
        _collection(
            [
                {"type": "Feature", "geometry": json.loads(row["geom_geojson"]), "properties": {"source": row["source_key"]}}
                for row in _given(test, "int_trail_lines__network_published")
            ]
        )
    )
    sites = _given(test, "int_points_of_interest__water_sites")
    for layer in ("shelters", "campsites"):
        _point_collection(
            workdir / f"{layer}.geojson",
            [row for row in sites if row["layer"] == layer],
            lambda row: {"GlobalID": row["global_id"], "Name": row["name"]},
        )
    points = [row for row in _given(test, "int_points_of_interest__in_corridor") if row["source_key"] == "osm_water"]
    _point_collection(workdir / "osm_water.geojson", points, lambda row: {"osm_id": row["source_feature_id"], "kind": "spring"})
    shipped = {row["source_key"] for row in _given(test, "stg_registry__sources") if row["reaches_hikers"]}

    live = (reach.RAW_DIR, reach.NETWORK_LINES_PATH, reach.shipped_network_keys)
    reach.RAW_DIR, reach.NETWORK_LINES_PATH, reach.shipped_network_keys = workdir, network, lambda: shipped
    try:
        records = {record["osm_id"]: record for record in reach.measure_distances(_spatial(), quiet=True)}
    finally:
        reach.RAW_DIR, reach.NETWORK_LINES_PATH, reach.shipped_network_keys = live
    answers: dict[str, dict | None] = {}
    for row in points:
        record = records.get(row["source_feature_id"])
        if record is None:
            answers[row["poi_key"]] = None
            continue
        walk = record.get("walk_to")
        answers[row["poi_key"]] = {
            "osm_id": record["osm_id"],
            "nearest": record["nearest"],
            "nearest_source": record.get("nearest_source"),
            "nearest_m": None if record["nearest_m"] is None else f"{record['nearest_m']:.2f}",
            "walk_key": None if walk is None else f"{walk['lat']:.6f},{walk['lon']:.6f}",
            "passes_distance": record["passes_distance"],
            "reason": record.get("reason"),
        }
    return answers


def reached_answers(test: dict) -> dict[str, dict | None]:
    """export_poi.py's gate_osm_water_reach() and mark_off_trail_records() on the corridor's rows (PO08, PO10)."""
    rows = _given(test, "int_points_of_interest__in_corridor")
    judged = _given(test, "int_points_of_interest__osm_water_verdicts")
    # A row the step wrote no verdict for is absent from the Python's verdict file.
    verdicts = {row["osm_id"]: row["reachable"] for row in judged if row["has_verdict"]}
    anchors = {
        row["osm_id"]: row["nearest_source"] for row in judged if row.get("nearest_source") and verdicts.get(row["osm_id"])
    }
    records = [
        {
            "id": row["poi_key"],
            "poi_type": row["poi_type"],
            "source": row["source"],
            "source_feature_id": row["source_feature_id"],
        }
        for row in rows
    ]
    kept = export_poi.gate_osm_water_reach(records, verdicts)
    export_poi.mark_off_trail_records(kept, anchors)
    answers: dict[str, dict | None] = {row["poi_key"]: None for row in rows}
    for record in kept:
        answers[record["id"]] = {"not_on_at": record.get(export_poi.NOT_ON_AT_KEY)}
    return answers


def photos_answers(test: dict) -> dict[str, dict | None]:
    """photo_screen.gate_photos() on the Commons rows, `{**commons, **atc}`, then export_poi.attach_photos() (PO24, PO38).

    Each row becomes the photo record its outcome file holds: the credit
    fields, the digest where the row has one, and a screen where the row was
    screened, with one face where it was flagged.
    """
    rows = sorted(_given(test, "stg_derived__poi_photos"), key=lambda row: row["photo_index"])
    lists: dict[str, dict[str, list[dict]]] = {"commons": {}, "atc": {}}
    decisions = {}
    for row in rows:
        photo = {field: row.get(field) for field in export_poi.PHOTO_FIELDS}
        if row.get("digest") is not None:
            photo["digest"] = row["digest"]
        if row["screened"]:
            photo["screen"] = {"faces": 1 if row["flagged"] else 0}
        lists[row["source"]].setdefault(row["poi_id"], []).append(photo)
        if row.get("decision") and row.get("digest"):
            decisions[row["digest"]] = {"decision": row["decision"]}
    commons, _ = photo_screen.gate_photos(lists["commons"], decisions)
    records = [{"id": poi_id} for poi_id in dict.fromkeys(row["poi_id"] for row in rows)]
    export_poi.attach_photos(records, {**commons, **lists["atc"]})
    columns = ("photo_key", *(f"photo_{field}" for field in export_poi.PHOTO_FIELDS), "photos")
    return {
        record["id"]: ({column: record.get(column) for column in columns} if "photo_key" in record else None)
        for record in records
    }


def deduplicated_answers(test: dict) -> dict[str, dict | None]:
    """export_poi.py's dedupe_water() on the reached rows (PO09)."""
    rows = _given(test, "int_points_of_interest__reached")
    records = [
        {"id": row["poi_key"], "poi_type": row["poi_type"], "source": row["source"], "lat": row["lat"], "lon": row["lon"]}
        for row in rows
    ]
    kept = {record["id"] for record in export_poi.dedupe_water(records)}
    return {row["poi_key"]: ({"source": row["source"]} if row["poi_key"] in kept else None) for row in rows}


def retired_answers(test: dict) -> dict[str, dict]:
    """lib/poi_identity.py's retired_rows() and resolve() (PO26)."""
    pois = _ledger(_given(test, "base_ourhike__poi_identity"))
    return {
        poi_id: {"superseded_by": row.get("superseded_by"), "resolves_to": poi_identity.resolve(pois, poi_id)}
        for poi_id, row in poi_identity.retired_rows(pois).items()
    }


def _order(row: dict) -> int:
    """A row's place in export_poi.py's record list: the water model's record_order, or file_order then source_row."""
    if row.get("record_order") is not None:
        return row["record_order"]
    return row["file_order"] * 1_000_000_000 + (row.get("source_row") or 0)


def _site_records(rows: list[dict]) -> list[dict]:
    """Given rows as export_poi.py's records, a site property present only where it is set."""
    records = []
    for row in rows:
        record = {
            "id": row["poi_id"],
            "poi_type": row["poi_type"],
            "source": row["source"],
            "source_feature_id": row["source_feature_id"],
            "trail_id": row["trail_id"],
            "name": row["name"],
            "lat": row["lat"],
            "lon": row["lon"],
            "confidence": row.get("confidence"),
            export_poi.RAW_PROPERTIES_KEY: _restored(json.loads(row.get("properties") or "{}"), ATC_DESCRIPTION_FIELDS),
        }
        for name in ("site_id", "site_role", "site_name", "water_distance_ft", "water_distance_source"):
            if row.get(name) is not None:
                record[name] = row[name]
        records.append(record)
    return records


WATER_COLUMNS = (
    "poi_type",
    "source",
    "name",
    "confidence",
    "site_id",
    "site_role",
    "site_name",
    "water_distance_ft",
    "water_distance_source",
)


def _water_records(test: dict, workdir: Path) -> list[dict]:
    """attach_water_distance(), synthesize_csi_water() and the ledger's second pass, as build_enriched_records() runs them (PO14-PO16): the records, the A.T.'s first."""
    workdir.mkdir(parents=True, exist_ok=True)
    distances = workdir / "water_distance.json"
    distances.write_text(
        json.dumps(
            {
                "sites": [
                    {key: row.get(key) for key in ("layer", "atc_global_id", "distance_ft", "provenance")}
                    for row in _given(test, "base_atc__water_distance")
                ]
            }
        )
    )
    ledger = workdir / "poi_identity.json"
    ledger.write_text(json.dumps({"pois": _ledger(_given(test, "base_ourhike__poi_identity"))}))
    rows = sorted(_given(test, "int_points_of_interest__sites"), key=_order)
    records = _site_records(rows)
    trail = [record for record, row in zip(records, rows) if row["phone_files"] == "poi_by_type"]
    others = [record for record, row in zip(records, rows) if row["phone_files"] != "poi_by_type"]
    export_poi.attach_water_distance(trail, export_poi.load_water_distances(distances))
    export_poi.synthesize_csi_water(trail)
    export_poi.apply_ledger_ids(trail, ledger)
    return trail + others


def water_answers(test: dict, workdir: Path) -> dict[str, dict]:
    """_water_records()' answer for each record, in the water model's columns (PO14-PO16)."""
    answers = {}
    for record in _water_records(test, workdir):
        answer = {name: record.get(name) for name in WATER_COLUMNS}
        synthesized = record.get("source") == export_poi.CSI_WATER_SOURCE
        answer["synthesized_description"] = record.get("description") if synthesized else None
        answers[record["id"]] = answer
    return answers


def enriched_answers(test: dict, workdir: Path) -> dict[str, dict]:
    """load_capacities() and attach_capacity(), then attach_nearby(), on records in record order (PO13, PO21)."""
    workdir.mkdir(parents=True, exist_ok=True)
    capacities = workdir / "shelter_capacity.json"
    capacities.write_text(
        json.dumps(
            {
                "shelters": [
                    {"poi_id": row["poi_id"], "capacity": row.get("capacity")}
                    for row in _given(test, "base_greenbelly__shelter_capacity")
                ]
            }
        )
    )
    rows = sorted(_given(test, "int_points_of_interest__water"), key=_order)
    records = _site_records(rows)
    trail = [record for record, row in zip(records, rows) if row["phone_files"] == "poi_by_type"]
    export_poi.attach_capacity(trail, export_poi.load_capacities(capacities))
    export_poi.attach_nearby(trail)
    return {
        record["id"]: {
            "capacity": record.get("capacity"),
            "nearby": json.loads(record["nearby"]) if record.get("nearby") is not None else None,
        }
        for record in records
    }


# --- the seeds, the vars and the mocked rows are the Python's own ------------------


def _mocked_seeds() -> Iterator[tuple[str, str, list[dict]]]:
    seeds = {path.stem for path in (DBT / "seeds").glob("*.csv")}
    for test in _document()["unit_tests"]:
        for given in test["given"]:
            name = given["input"].removeprefix("ref('").removesuffix("')")
            if name in seeds:
                yield test["name"], name, given["rows"]


@pytest.mark.parametrize(
    ("test_name", "seed", "rows"), list(_mocked_seeds()), ids=lambda value: value if isinstance(value, str) else ""
)
def test_each_mocked_seed_is_the_seed_file(test_name, seed, rows):
    def text(table: list[dict]) -> list[dict]:
        return [{key: _text(value) for key, value in row.items()} for row in table]

    assert text(rows) == text(_seed_file(seed)), f"{test_name} mocks {seed} with rows the seed file does not hold"


def test_the_unit_tests_registry_entries_are_sources_json_own():
    """Each unit test's registry entry carries only keys sources.json's entry has, with sources.json's values."""
    real = {source["key"]: source for source in json.loads((PIPELINE / "sources.json").read_text())["sources"]}
    checked = 0
    for test in _document()["unit_tests"]:
        for given in test["given"]:
            if given["input"] == "ref('stg_registry__sources')":
                for row in given["rows"]:
                    if "entry" not in row:
                        # The reach's unit test mocks `reaches_hikers` alone. Every network
                        # line source reaches hikers today, so the one that does not is a
                        # key sources.json does not have, named `unit_` to say so.
                        if row["source_key"].startswith("unit_"):
                            assert row["reaches_hikers"] is False, row["source_key"]
                        else:
                            assert row["reaches_hikers"] == real[row["source_key"]]["reaches_hikers"], row["source_key"]
                        checked += 1
                        continue
                    entry = json.loads(row["entry"])
                    assert entry == {key: real[row["source_key"]][key] for key in entry}, row["source_key"]
                    checked += 1
            if given["input"] == "ref('int_points_of_interest__classified')":
                for row in given["rows"]:
                    if row.get("registry_entry"):
                        entry = json.loads(row["registry_entry"])
                        assert entry == {key: real[row["source_key"]][key] for key in entry}, row["source_key"]
                        checked += 1
    assert checked, "no unit test mocks a registry entry"


def _site_water_layer(tmp_path: Path) -> tuple[str, str, str, str, str]:
    """load_trail_water()'s inline field map, read back off one record it unifies: (source, id field, name field, type, confidence)."""
    path = tmp_path / "trail_water.json"
    water = {"lat": 41.0, "lon": -74.0, "sources": ["nhd"], "name": "Fixture Brook", "flow": None, "flow_source": None}
    path.write_text(json.dumps({"sites": [{"atc_global_id": "g-1", "water": {**water, "stream_id": "s-1"}}]}))
    (record,) = export_poi.load_trail_water(path)
    assert record["id"] == f"{export_poi.NHD_STREAM_SOURCE}:g-1"
    assert record["name"] == "Fixture Brook"
    return record["source"], "site_global_id", "name", record["poi_type"], record["confidence"]


def test_the_poi_sources_seed_is_the_exporters_layer_list(tmp_path):
    """poi_sources: export_poi.py's DIRECT_SOURCES, opentrail, OSM water and site water, then export_nearby_poi.py's poi_sources(), in reading order."""
    rows = _seed_file("poi_sources")
    at = [
        (stem, source, field_map["id_field"], field_map["name_field"], None, None)
        for stem, _, source, field_map in export_poi.DIRECT_SOURCES
    ]
    at.append(
        (
            export_poi.OPENTRAIL_SOURCE,
            export_poi.OPENTRAIL_SOURCE,
            export_poi.OPENTRAIL_FIELD_MAP_BASE["id_field"],
            export_poi.OPENTRAIL_FIELD_MAP_BASE["name_field"],
            None,
            None,
        )
    )
    # load_osm_water() and load_trail_water() type every point `water`, so the
    # seed carries the type and the confidence on the layer.
    at.append(
        (
            export_poi.OSM_WATER_SOURCE,
            export_poi.OSM_WATER_SOURCE,
            export_poi.OSM_WATER_FIELD_MAP["id_field"],
            export_poi.OSM_WATER_FIELD_MAP["name_field"],
            "water",
            export_poi.OSM_WATER_FIELD_MAP["confidence"],
        )
    )
    source, id_field, name_field, poi_type, confidence = _site_water_layer(tmp_path)
    at.append((source, source, id_field, name_field, poi_type, confidence))
    assert [
        (r["source_key"], r["source"], r["id_field"], r["name_field"], r["poi_type"], r["confidence"])
        for r in rows
        if r["phone_files"] == "poi_by_type"
    ] == at
    assert {(r["poi_type"], r["confidence"]) for r in rows if r["phone_files"] == "nearby_poi"} == {(None, None)}
    assert {r["trail_id"] for r in rows if r["phone_files"] == "poi_by_type"} == {export_poi.TRAIL_ID}

    registry = export_nearby_poi.load_registry(PIPELINE / "sources.json")
    nearby = export_nearby_poi.poi_sources(registry)
    others = [r for r in rows if r["phone_files"] == "nearby_poi"]
    # main() appends the Long Path guide's records after every layer (guide_records()).
    *layers, guide_row = others
    assert [r["source_key"] for r in layers] == [source["key"] for source in nearby]
    for row, source in zip(layers, nearby):
        assert row["source"] == source["key"]
        assert row["trail_id"] == export_nearby_poi.TRAIL_IDS[source["provider"]], source["key"]
        assert row["type_field"] == export_nearby_poi.TYPED_LAYERS.get(source["key"], (None, None))[0], source["key"]
    from lib import nynjtc_long_path_guide

    assert (guide_row["source_key"], guide_row["source"], guide_row["trail_id"]) == (
        export_nearby_poi.GUIDE_KEY,
        nynjtc_long_path_guide.SOURCE_KEY,
        nynjtc_long_path_guide.TRAIL_ID,
    )
    assert {r["source_key"] for r in rows if r["unified"] == "true"} == {export_nearby_poi.GUIDE_KEY}
    assert [int(r["file_order"]) for r in rows] == list(range(1, len(rows) + 1))


def test_the_value_types_seed_is_the_three_type_maps():
    """The three maps, plus decision 65's typed taps and nothing else."""
    rows = {(r["source_key"], r["value"]): r["poi_type"] for r in _seed_file("poi_value_types")}
    expected = {
        (key, value): poi_type
        for key, (_, mapping) in export_nearby_poi.TYPED_LAYERS.items()
        for value, poi_type in mapping.items()
    }
    assert rows == {**expected, **DECISION_65_VALUE_TYPES}


def test_decision_65_types_only_taps_todays_exporter_holds_back_by_name():
    """Each tap decision 65 types is a value today's exporter names as a water holdback, never one it publishes."""
    assert DECISION_65_VALUE_TYPES == {
        ("oprhp_facilities", "Water Spigot"): "water",
        ("oprhp_facilities", "Drinking Fountain"): "water",
    }
    for key, value in DECISION_65_VALUE_TYPES:
        assert value not in export_nearby_poi.TYPED_LAYERS[key][1], (key, value)
        assert "oprhp_water_holdback" in export_nearby_poi.NAMED_EXCLUSIONS[value], (key, value)


def test_the_named_exclusions_seed_is_named_exclusions():
    assert {r["value"]: r["reason"] for r in _seed_file("poi_named_exclusions")} == export_nearby_poi.NAMED_EXCLUSIONS


def test_the_poi_types_seed_is_lib_poi_schema():
    from lib import poi_schema

    rows = _seed_file("poi_types")
    assert [r["poi_type"] for r in rows if r["state"] == "published"] == list(poi_schema.POI_TYPES)
    assert {r["poi_type"] for r in rows if r["state"] == "withdrawn"} == set(poi_schema.WITHDRAWN_POI_TYPES)
    assert {r["poi_type"] for r in rows if r["may_be_empty"] == "true" and r["state"] == "published"} == set(
        poi_schema.ALLOWED_EMPTY_POI_TYPES
    )


def test_the_water_claims_seed_is_water_provenance_claims():
    rows = {r["provenance"]: r["claim"] for r in _seed_file("poi_water_claims")}
    assert rows == {**export_poi.WATER_PROVENANCE_CLAIMS, "*": export_poi.UNKNOWN_WATER_PROVENANCE_CLAIM}


def test_the_description_terms_seed_is_lib_poi_description_vocabularies():
    rows: dict[str, dict[str, str]] = {}
    for row in _seed_file("poi_description_terms"):
        rows.setdefault(row["vocabulary"], {})[row["code"]] = row["phrase"]
    expected = {
        "storeys": {str(code): phrase for code, phrase in poi_description.STOREYS.items()},
        "exterior_material": poi_description.EXTERIOR_MATERIALS,
        "parking_surface": poi_description.PARKING_SURFACES,
        "privy_type": poi_description.PRIVY_TYPES,
        "vista_location": poi_description.VISTA_LOCATIONS,
        "stream_source": poi_description.STREAM_SOURCES,
        "stream_claim": poi_description.STREAM_CLAIMS,
        "stream_flow": poi_description.FLOW_WORDS,
        "water_kind": poi_description.WATER_KINDS,
    }
    for vocabulary, phrases in expected.items():
        assert rows.pop(vocabulary) == {str(code): phrase for code, phrase in phrases.items()}, vocabulary
    assert rows == {}, f"vocabularies the Python does not have: {sorted(rows)}"


def test_the_vars_are_the_python_constants():
    variables = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]
    assert variables["poi_corridor_buffer_miles"] == corridor.BUFFER_MILES
    assert variables["mile_axis_metres_per_mile"] == corridor.METERS_PER_MILE
    assert variables["poi_metres_per_degree"] == spurs.METERS_PER_DEGREE
    assert variables["poi_metres_per_foot"] == export_poi.M_PER_FT == corridor.METERS_PER_FOOT
    assert variables["poi_site_name_radius_m"] == poi_sites.NAME_MATCH_RADIUS_M
    assert variables["poi_site_proximity_radius_m"] == poi_sites.PROXIMITY_RADIUS_M
    assert variables["poi_site_max_radius_m"] == poi_sites.MAX_SITE_RADIUS_M
    assert variables["poi_place_site_radius_m"] == poi_sites.PLACE_PROXIMITY_RADIUS_M
    assert variables["poi_nearby_min_part_ft"] == poi_description.MIN_PART_FT
    assert set(variables["poi_null_sentinels"]) == export_nearby_poi.DIRT - {""}
    assert variables["poi_network_ring_feet"] == corridor.NETWORK_BUFFER_FEET
    assert set(variables["poi_network_ring_exempt_types"]) == export_nearby_poi.NETWORK_RING_EXEMPT_TYPES
    assert variables["poi_trailhead_trail_radius_m"] == export_nearby_poi.TRAILHEAD_TRAIL_RADIUS_M
    assert variables["poi_description_earliest_year"] == poi_description.EARLIEST_PLAUSIBLE_YEAR
    assert variables["poi_description_latest_year"] == poi_description.LATEST_PLAUSIBLE_YEAR
    assert variables["poi_vista_panorama_degrees"] == poi_description.PANORAMA_DEGREES
    assert variables["poi_vista_arc_rounding_degrees"] == poi_description.ARC_ROUNDING_DEGREES
    assert tuple(variables["poi_compass_points"]) == poi_description.COMPASS_POINTS
    assert set(variables["poi_note_empty_values"]) == atc_notes.EMPTY_VALUES
    assert tuple(variables["poi_note_internal_patterns"]) == atc_notes.INTERNAL_PATTERNS
    assert variables["poi_water_match_radius_ft"] == fetch_trail_water.MATCH_RADIUS_FT
    assert variables["poi_metres_per_foot"] == fetch_trail_water.M_PER_FT
    assert variables["poi_osm_water_measure_ceiling_m"] == build_osm_water_reach.MEASURE_CEILING_M
    assert variables["poi_water_dedup_radius_m"] == export_poi.WATER_DEDUP_RADIUS_M


def test_the_base_name_macro_strips_type_words():
    macro = (DBT / "macros" / "poi_distance_m.sql").read_text()
    (words,) = re.findall(r"'\( \(([a-z|]+)\|\[0-9\]\+\)\)\+\$'", macro)
    assert set(words.split("|")) == poi_sites.TYPE_WORDS


def test_the_describers_read_no_field_this_list_lacks():
    """Every ATC field a describer reads is one the unit tests hand back in ATC's case.

    ATC's fields are capitalised; the lower-case ones are describe_water()'s OSM
    tags, which OSM_DESCRIBED's unit test hands the describer as
    fetch_osm_water.py names them (only fixture mode lands OSM water until
    #1652), and the site water step_site_water.py lands, which STREAMS' unit
    test hands it under the names load_trail_water() writes.
    """
    source = (PIPELINE / "lib" / "poi_description.py").read_text()
    read = set(re.findall(r'(?:_count|_coded)\(\w+, "(\w+)"\)', source)) | set(re.findall(r'properties\.get\("(\w+)"\)', source))
    assert {name for name in read if name[0].isupper()} - set(ATC_DESCRIPTION_FIELDS) == set()
    assert export_poi.ATC_NOTE_FIELD in ATC_DESCRIPTION_FIELDS


# --- each unit test's expected rows are the Python's answer ---------------------------


def _held(expected: dict[str, dict], answers: dict[str, dict | None], deliberate: dict[str, str] | None = None) -> None:
    """Every row the Python ships is an expected row with the Python's values, and no other row is expected."""
    deliberate = deliberate or {}
    shipped = {key for key, answer in answers.items() if answer is not None}
    assert set(expected) - set(deliberate) == shipped - set(deliberate), "rows the SQL and the Python disagree on shipping"
    for key in sorted(shipped - set(deliberate)):
        for column, value in answers[key].items():
            assert expected[key].get(column) == value, (
                f"{key}.{column}: SQL expects {expected[key].get(column)!r}, Python {value!r}"
            )


def test_descriptions_are_what_the_describers_compose():
    for name in (DESCRIBED, COMPOSED, STREAMS, OSM_DESCRIBED):
        test = _unit_test(name)
        _held(_expected(test, "poi_id"), described_answers(test))


def test_sites_are_what_lib_poi_sites_groups():
    test = _unit_test(SITES)
    _held(_expected(test, "poi_id"), sites_answers(test))


def test_classification_is_what_the_exporters_read(tmp_path):
    test = _unit_test(CLASSIFIED)
    expected = _expected(test, "poi_key")
    answers = classified_answers(test, tmp_path)
    assert set(expected) == set(answers)
    for key, answer in answers.items():
        for column, value in answer.items():
            assert expected[key].get(column) == value, (
                f"{key}.{column}: SQL expects {expected[key].get(column)!r}, Python {value!r}"
            )


def test_classification_reaches_every_refusal():
    reasons = {row["drop_reason"] for row in _unit_test(CLASSIFIED)["expect"]["rows"]}
    assert {"no geometry", "no usable point geometry", "icon not published", "not a published POI type"} <= reasons
    assert any(reason and reason.startswith("excluded: ") for reason in reasons)


def test_public_flags_keep_and_rate_as_public_verdict_does():
    test = _unit_test(PUBLISHABLE)
    _held(_expected(test, "poi_key"), publishable_answers(test))


@pytest.mark.parametrize("name", [IN_CORRIDOR, NO_NETWORK, LONG_LINES])
def test_the_corridor_and_the_ring_keep_what_the_python_keeps(name, tmp_path):
    test = _unit_test(name)
    _held(_expected(test, "poi_key"), in_corridor_answers(test, tmp_path))


@pytest.mark.parametrize("name", [LONG_LINES, TRAILHEAD_SEGMENTS])
def test_the_segment_unit_tests_change_only_the_part_size(name):
    """Each segment unit test splits every part past two vertices, and every other var it must restate is the project's own.

    dbt 2.0.6 replaces a unit test's vars rather than merging them, so these
    tests restate the radii and the corridor's width; a restated value that
    drifted from dbt_project.yml would test a different rule.
    """
    overridden = dict(_unit_test(name)["overrides"]["vars"])
    project = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]
    assert overridden.pop("poi_network_ring_part_max_vertices") == 2
    assert overridden == {var: project[var] for var in overridden}


def test_the_trailhead_segment_test_is_the_trailhead_test_split():
    """The trailheads' segment unit test gives and expects exactly what the whole-line one does."""
    whole, split = _unit_test(TRAILHEADS), _unit_test(TRAILHEAD_SEGMENTS)
    assert split["given"] == whole["given"]
    assert split["expect"] == whole["expect"]


@pytest.mark.parametrize("name", [TRAILHEADS, NO_SIDE_TRAILS, TRAILHEAD_SEGMENTS])
def test_trailheads_are_marked_as_mark_closed_trailheads_marks(name, tmp_path):
    test = _unit_test(name)
    _held(_expected(test, "poi_id"), trailheads_answers(test, tmp_path))


def test_the_trailhead_rule_is_put_both_ways():
    """A trailhead beside an open A.T. side trail and a closed line is not marked; one whose every line is closed is."""
    expected = _unit_test(TRAILHEADS)["expect"]["rows"]
    assert any(row["closed_lines_within_radius"] > 0 and row["trails_closed_within_m"] is None for row in expected)
    assert any(row["trails_closed_within_m"] == export_nearby_poi.TRAILHEAD_TRAIL_RADIUS_M for row in expected)
    assert any(row["lines_within_radius"] == 0 and row["trails_closed_within_m"] is None for row in expected)


def test_miles_are_what_attach_miles_reads():
    """The mile as text is the double Python's round(mile, 3) gives, to the bit."""
    test = _unit_test(MILES)
    answers = miles_answers(test)
    expected = _expected(test, "poi_id")
    assert set(expected) == set(answers)
    for poi_id, answer in answers.items():
        if poi_id in DELIBERATE["miles"]:
            assert float(expected[poi_id]["mile"]) != answer["mile"], f"{poi_id} is no longer a deliberate difference"
            continue
        assert float(expected[poi_id]["mile"]) == answer["mile"], poi_id


def test_the_ledger_is_applied_as_apply_ledger_ids_applies_it(tmp_path):
    test = _unit_test(IDENTIFIED)
    _held(_expected(test, "poi_key"), identified_answers(test, tmp_path))


def test_osm_water_is_measured_as_measure_distances_measures(tmp_path):
    test = _unit_test(OSM_REACH)
    expected = _expected(test, "poi_key")
    answers = osm_water_reach_answers(test, tmp_path)
    assert None not in answers.values(), "a unit test point outside the Python's own corridor"
    _held(expected, answers)


def test_the_reach_unit_test_reaches_every_branch():
    rows = _unit_test(OSM_REACH)["expect"]["rows"]
    assert {row["nearest"] for row in rows} == {"centerline", "side_trail", "network_trail", "shelter", "campsite", None}
    assert {row["passes_distance"] for row in rows} == {True, False}
    assert any(row["reason"] and row["reason"].startswith("no trail") for row in rows)
    assert any(row["reason"] and row["reason"].startswith("the nearest") for row in rows)


def test_osm_water_is_gated_and_marked_as_export_poi_does():
    test = _unit_test(REACHED)
    answers = reached_answers(test)
    _held(_expected(test, "poi_key"), answers)
    assert any(answer and answer["not_on_at"] for answer in answers.values()), "no point is marked"
    assert sum(answer is None for answer in answers.values()) >= 2, "no verdict and an unreachable one both drop"


def test_osm_twins_of_opentrail_water_are_dropped_as_dedupe_water_drops_them():
    test = _unit_test(DEDUPLICATED)
    answers = deduplicated_answers(test)
    _held(_expected(test, "poi_key"), answers)
    assert None in answers.values(), "no twin"


def test_photos_are_gated_and_attached_as_export_poi_does():
    test = _unit_test(PHOTOS)
    answers = photos_answers(test)
    _held(_expected(test, "poi_id"), answers)
    assert sum(answer is None for answer in answers.values()) >= 4, "held, refused, digestless and overruled all show none"


def test_tombstones_resolve_as_lib_poi_identity_resolves():
    test = _unit_test(RETIRED)
    _held(_expected(test, "poi_id"), retired_answers(test))


def test_water_is_attached_and_synthesized_as_export_poi_does(tmp_path):
    test = _unit_test(WATER)
    _held(_expected(test, "poi_id"), water_answers(test, tmp_path))


#: The properties a poi_<type>.geojson feature carries that the water model and export_poi.py's records both hold.
WATER_FEATURE_PROPERTIES = (
    "poi_type",
    "source",
    "source_feature_id",
    "name",
    "confidence",
    "site_id",
    "site_role",
    "site_name",
    "water_distance_ft",
    "water_distance_source",
    "description",
)


def _water_feature(record: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [record["lon"], record["lat"]]},
        "properties": {"id": record["id"], **{name: record.get(name) for name in WATER_FEATURE_PROPERTIES}},
    }


def test_a_point_held_on_a_retired_id_differs_from_export_poi_only_as_parity_explains(tmp_path):
    """HELD_WATER's rows through today's Python, and as the SQL is held to answer, written as the poi files.

    The Python publishes the two atc_csi ids the unit test's ledger retired and makes the shelter that was in no
    site its own site's anchor; parity._held_csi_water_reasons() explains exactly those three features and the water
    file's order, and every other feature, the live-row, no-row and other-id cases among them, is equal.
    """
    test = _unit_test(HELD_WATER)
    pois = _ledger(_given(test, "base_ourhike__poi_identity"))
    sites = {row["source_feature_id"]: row for row in _given(test, "int_points_of_interest__sites")}
    old_records = _water_records(test, tmp_path)
    new_records = [
        {
            "id": row["poi_id"],
            **{name: row.get(name) for name in WATER_FEATURE_PROPERTIES},
            "description": row["synthesized_description"],
            "lat": sites[row["source_feature_id"]]["lat"],
            "lon": sites[row["source_feature_id"]]["lon"],
        }
        for row in test["expect"]["rows"]
    ]
    explained = {}
    for poi_type in ("shelter", "campsite", "water", "privy"):
        family = parity.FAMILIES[f"poi_{poi_type}"]
        assert family.explained is parity._held_csi_water_reasons
        old = {"features": [_water_feature(record) for record in old_records if record["poi_type"] == poi_type]}
        new = {"features": [_water_feature(record) for record in new_records if record["poi_type"] == poi_type]}
        reasons = parity._held_csi_water_reasons(old, new, pois)
        assert {what for what, _, _ in parity.differences(old, new, family)} == set(reasons), poi_type
        explained[poi_type] = set(reasons)
    assert explained == {
        "shelter": {"properties.id atc_shelters:H1"},
        "campsite": set(),
        "water": {"properties.id atc_csi:H1", "properties.id atc_csi:H2", "order"},
        "privy": set(),
    }


def test_capacity_and_nearby_are_attached_as_export_poi_does(tmp_path):
    test = _unit_test(ENRICHED)
    expected = _expected(test, "poi_id")
    for row in expected.values():
        row["nearby"] = json.loads(row["nearby"]) if row.get("nearby") is not None else None
    _held(expected, enriched_answers(test, tmp_path))


# --- the deliberate differences --------------------------------------------------------


def _exact_copies_removed(features: list[dict], id_field: str) -> list[dict]:
    """decision 40's staging dedupe: of the rows equal in every column but the server's row id, the lowest id."""

    def body(feature: dict) -> str:
        properties = {name: value for name, value in feature["properties"].items() if name != id_field}
        return parity.canonical({"geometry": feature.get("geometry"), "properties": properties})

    kept: dict[str, dict] = {}
    for feature in features:
        current = kept.get(body(feature))
        if current is None or feature["properties"].get(id_field) < current["properties"].get(id_field):
            kept[body(feature)] = feature
    survivors = {id(feature) for feature in kept.values()}
    return [feature for feature in features if id(feature) in survivors]


def test_every_deliberate_nearby_poi_difference_is_an_exact_copy_on_the_fixtures(tmp_path):
    """The fixture warehouse's nearby_poi differences are exactly DELIBERATE's, each parity.py's explained reason.

    build_records() on every layer as the fixtures write it (today's file), and on
    the same layers after decision 40's dedupe (what staging hands dbt): what
    parity._exact_copy_reasons() explains between the two is what DELIBERATE
    names, so a new exact copy in the fixtures, or an emptied list, is red.
    """
    make_dbt_fixtures.write_fixtures(tmp_path)
    registry = export_nearby_poi.load_registry(PIPELINE / "sources.json")
    old: list[dict] = []
    new: list[dict] = []
    for source in export_nearby_poi.poi_sources(registry):
        path = tmp_path / "external" / f"{source['key']}.geojson"
        features = json.loads(path.read_text()).get("features", []) if path.exists() else []
        old += export_nearby_poi.build_records(source, features)[0]
        new += export_nearby_poi.build_records(source, _exact_copies_removed(features, source.get("id_field", "OBJECTID")))[0]
    reasons = parity._exact_copy_reasons(export_nearby_poi.records_to_geojson(old), export_nearby_poi.records_to_geojson(new))
    assert reasons == {what: WHY[case] for what, case in DELIBERATE["nearby_poi"].items()}


def test_every_deliberate_case_has_a_reason():
    for differences in DELIBERATE.values():
        for case in differences.values():
            assert WHY[case].startswith("expected by "), case


def _poi_feature(poi_id: str, source: str) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-74.0, 41.0]},
        "properties": {"id": poi_id, "source": source, "source_feature_id": poi_id.split(":", 1)[1]},
    }


def test_a_poi_from_a_layer_no_exporter_reads_is_explained_as_decision_31s_new_data():
    """nearby_poi's parity explains a record from one of decision 54's wave 1 point layers as new data, never a record
    of a layer export_nearby_poi.py reads, and never a record today's file already holds."""
    shared = _poi_feature("dec_lean_tos:1", "dec_lean_tos")
    old = {"features": [shared]}
    new = {
        "features": [
            shared,
            _poi_feature("ncta_points:{NC-1}", "ncta_points"),
            # A layer today's exporter reads, adding a record: still a difference.
            _poi_feature("dec_lean_tos:2", "dec_lean_tos"),
        ]
    }
    reasons = parity._nearby_poi_reasons(old, new)
    assert reasons == {"properties.id ncta_points:{NC-1}": parity.POI_REASONS["new_source"]}
    assert reasons["properties.id ncta_points:{NC-1}"].startswith(parity.NEW_DATA_REASON)
    assert parity.FAMILIES["nearby_poi"].explained is parity._nearby_poi_reasons


def test_a_seasonal_tap_of_a_layer_todays_exporter_reads_is_explained_by_decision_65():
    """nearby_poi's parity explains a NY Parks tap decision 65 ships, and only as decision 65 ships it: water, low
    confidence, the season caution. The same layer's tap without the caution, or rated high, is still a difference."""
    shared = _poi_feature("dec_lean_tos:1", "dec_lean_tos")

    def tap(poi_id: str, **properties) -> dict:
        feature = _poi_feature(poi_id, "oprhp_facilities")
        feature["properties"].update(poi_type="water", **properties)
        return feature

    new = {
        "features": [
            shared,
            tap("oprhp_facilities:18", confidence="low", water_caution="no_shutoff_season"),
            tap("oprhp_facilities:19", confidence="low"),
            tap("oprhp_facilities:20", confidence="high", water_caution="no_shutoff_season"),
        ]
    }
    reasons = parity._nearby_poi_reasons({"features": [shared]}, new)
    assert reasons == {"properties.id oprhp_facilities:18": parity.POI_REASONS["seasonal_tap"]}
    assert "oprhp_facilities" in parity._plumbed_water_sources()


def test_no_wave_1_point_layer_is_one_export_nearby_poi_reads():
    """The new-data reason reaches only layers today's exporter never reads: no wave 1 row carries `poi_type` or sits
    in TYPED_LAYERS, which is what would put it in export_nearby_poi.py's export."""
    import make_dbt_staging

    wave_1 = {table.key for table in make_dbt_staging.tables() if table.type == "points_of_interest"}
    assert wave_1, "no wave 1 point layer is staged"
    assert not wave_1 & parity._today_poi_sources()


#: A ledger for the held-water explanation: GlobalID R's derived id retired (held); L's retired beside a live row
#: for L under another id (not held: the point takes L-now); V's live; and a retired shelter.
HELD_LEDGER = {
    "atc_csi:R": {"source": "atc_csi", "source_feature_id": "R", "retired": "2026-08-19"},
    "atc_csi:L": {"source": "atc_csi", "source_feature_id": "L", "retired": "2026-08-19"},
    "atc_csi:L-now": {"source": "atc_csi", "source_feature_id": "L"},
    "atc_csi:V": {"source": "atc_csi", "source_feature_id": "V"},
    "atc_shelters:T": {"source": "atc_shelters", "source_feature_id": "T", "retired": "2026-08-19"},
}


def _shelter(poi_id: str, *, site: bool, **changed) -> dict:
    """An A.T. shelter as a poi_shelter.geojson feature: its own site's anchor where `site`, else in no site."""
    name = f"Fixture {poi_id}"
    properties = {
        "id": poi_id,
        "poi_type": "shelter",
        "source": "atc_shelters",
        "source_feature_id": poi_id.split(":", 1)[1],
        "name": name,
        "water_distance_ft": 120,
        "water_distance_source": "FarOut",
        "site_id": poi_id if site else None,
        "site_role": "anchor" if site else None,
        "site_name": name if site else None,
    }
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-74.0, 41.0]},
        "properties": {**properties, **changed},
    }


def test_only_held_csi_water_ids_are_the_ledgers_retired_ones_with_no_live_row():
    assert parity._held_csi_water_ids(HELD_LEDGER) == {"atc_csi:R"}


def test_a_missing_csi_water_point_is_explained_only_when_the_ledger_retired_its_id():
    """poi_water: today's atc_csi:R (held) is explained as verify_release.py's rule, and so is the order once it is
    left out; a point under a live row's id, one with no ledger row, and a retired id from another source are not."""
    kept = _poi_feature("opentrail_at:1", "opentrail_at")
    carried = _poi_feature("atc_csi:L-now", "atc_csi")
    carried["properties"]["source_feature_id"] = "L"
    old = {
        "features": [
            _poi_feature("atc_csi:R", "atc_csi"),
            carried,
            _poi_feature("atc_csi:V", "atc_csi"),
            _poi_feature("atc_csi:N", "atc_csi"),
            _poi_feature("atc_shelters:T", "atc_shelters"),
            kept,
        ]
    }
    reason = parity.POI_REASONS["retired_csi_water"]
    assert parity._held_csi_water_reasons(old, {"features": [kept]}, HELD_LEDGER) == {"properties.id atc_csi:R": reason}
    held_only = {"features": [_poi_feature("atc_csi:R", "atc_csi"), kept]}
    assert parity._held_csi_water_reasons(held_only, {"features": [kept]}, HELD_LEDGER) == {
        "properties.id atc_csi:R": reason,
        "order": reason,
    }
    # The dbt writer publishing the held id after all is never explained, nor is a point it adds.
    assert parity._held_csi_water_reasons({"features": [kept]}, held_only, HELD_LEDGER) == {}
    assert reason.startswith("expected by verify_release.py's check_poi_identity()")
    assert "RETIRED ledger row" in reason


def test_an_anchor_is_explained_only_for_the_site_its_held_point_made():
    """poi_shelter: a shelter whose would-be point is held is explained where today's file made it its own site's
    anchor and the new file leaves it in no site, and nowhere it differs in anything else."""
    reason = parity.POI_REASONS["retired_csi_water"]

    def reasons(old: dict, new: dict) -> dict[str, str]:
        return parity._held_csi_water_reasons({"features": [old]}, {"features": [new]}, HELD_LEDGER)

    assert reasons(_shelter("atc_shelters:R", site=True), _shelter("atc_shelters:R", site=False)) == {
        "properties.id atc_shelters:R": reason
    }
    # The same site change where the point would take a live row's id (L's carried one, V's own), or one the ledger
    # does not know: not this reason.
    for poi_id in ("atc_shelters:L", "atc_shelters:V", "atc_shelters:N"):
        assert reasons(_shelter(poi_id, site=True), _shelter(poi_id, site=False)) == {}, poi_id
    # A site change and anything else besides; a site that was not its own; a site the new file kept.
    assert reasons(_shelter("atc_shelters:R", site=True), _shelter("atc_shelters:R", site=False, water_distance_ft=90)) == {}
    other_site = _shelter("atc_shelters:R", site=True, site_id="atc_shelters:other")
    assert reasons(other_site, _shelter("atc_shelters:R", site=False)) == {}
    assert reasons(_shelter("atc_shelters:R", site=True), _shelter("atc_shelters:R", site=True, site_name="Renamed")) == {}
