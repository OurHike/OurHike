"""parity.py compares the line ids a phone joins on: nearby_trails' `id` and each graph edge's `trail_id`.

A phone finds a line's climb by joining the graph cell's edges to the tile's line, `edge.trail_id === line.id`
(client/src/lib/lineClimb.ts), and keeps cells from more than one release. So an id the dbt writers publish for a line
must be the id today's exporters publish for it, or a phone holding cells from both sides of the cutover loses the
climb row and its note on that line (client/src/lib/lineDetail.ts).

THE FINDING THESE HOLD, measured 2026-10-15 on UA's release 2026-10-10-2: every line of eight layers whose GlobalID is
spelled other than `GlobalID` carried another id in the dbt writer's trail_graph.json than in the 779 graph cells
phones read, which today's exporters cut. None of the cells' 51,663 USFS, 5,228 DEC, 11,701 NJ statewide or 3,138
NJDEP trail_ids was in it. At 36c5ca96 neither family could see that: nearby_trails explained each such pair as the
GlobalID read in any case (NETWORK_ID_REASONS' retired `globalid_in_any_case`, which pipeline/ELT.md's TL05 counts at
72,618 lines of six layers on monthly run 30), and trail_graph built its old side from the dbt writer's own
nearby_trails.geojson, so both of its sides carried the dbt writer's ids (Reasoned from parity.py at 36c5ca96).

The lines here are shaped like those four layers' rows: the GlobalID spelled as sources.json's `global_id_field`
declares it, beside the OBJECTID that ArcGIS writes as the feature's GeoJSON `id`. Today's id is resolve_feature_id()'s;
the dbt writer's, as it stood at 36c5ca96, read the GlobalID in any case.
"""

import json

import build_trail_graph
import parity
from lib.feature_id import resolve_feature_id

#: Each layer's GlobalID field as the layer spells it (sources.json's `global_id_field`), and the first object id of a
#: dense run like USFS's (pipeline/ELT.md, "Stable upstream keys").
FOUR_LAYERS = {
    "usfs_trails": "globalid",
    "dec_hiking_trails": "GLOBALID",
    "nj_statewide_trails": "GLOBALID",
    "njdep_park_trails": "GLOBALID",
}
FIRST_OBJECT_ID = 9168450
NO_TRAILS = {"type": "FeatureCollection", "features": []}


def _line(line_id: str, source: str, name: str, coordinates: list) -> dict:
    """A nearby_trails.geojson feature, with the properties records_to_geojson() writes for a network line."""
    return {
        "type": "Feature",
        "properties": {
            "id": line_id,
            "source": source,
            "name": name,
            "blaze_color": "Unknown",
            "length_miles": 0.69,
            "trail_status": "open",
        },
        "geometry": {"type": "LineString", "coordinates": coordinates},
    }


def _four_layer_files() -> tuple[dict, dict]:
    """(today's nearby_trails.geojson, the dbt writer's at 36c5ca96): one line of each of FOUR_LAYERS, far apart."""
    today, dbt = [], []
    for place, (key, spelling) in enumerate(FOUR_LAYERS.items()):
        object_id = FIRST_OBJECT_ID + place
        properties = {spelling: f"{{0000000{place}-0000-4000-8000-000000000001}}", "OBJECTID": object_id}
        feature = {"type": "Feature", "id": object_id, "properties": properties}
        coordinates = [[-72.0 + place, 44.0], [-72.0 + place, 44.01]]
        name = f"Fixture {key} line"
        today.append(_line(f"{key}:{resolve_feature_id(key, feature, properties, place)}", key, name, coordinates))
        dbt.append(_line(f"{key}:{properties[spelling]}", key, name, coordinates))
    return {"type": "FeatureCollection", "features": today}, {"type": "FeatureCollection", "features": dbt}


def _graph_beside(tmp_path, lines: dict):
    """trail_graph.json as build_trail_graph.build() makes it of `lines`, written with them beside it, as the dbt
    writers leave their files: the graph's path, for parity's `--new`."""
    (tmp_path / build_trail_graph.INPUT_NAME).write_text(json.dumps(lines))
    (tmp_path / build_trail_graph.TRAILS_NAME).write_text(json.dumps(NO_TRAILS))
    graph, _ = build_trail_graph.build(lines, NO_TRAILS)
    for edge in graph["edges"]:
        edge.pop("geometry")
    new = tmp_path / build_trail_graph.ARTIFACT_NAME
    new.write_text(json.dumps(graph))
    return new, graph


def test_the_four_layers_ids_differ_between_the_writers_as_they_did_on_ua():
    """The premise: today's exporter publishes each line under its OBJECTID, the dbt writer did under its GlobalID."""
    today, dbt = _four_layer_files()
    assert [feature["properties"]["id"] for feature in today["features"]] == [
        f"{key}:{FIRST_OBJECT_ID + place}" for place, key in enumerate(FOUR_LAYERS)
    ]
    assert all(":{" in feature["properties"]["id"] for feature in dbt["features"])


def test_nearby_trails_reports_a_line_whose_id_alone_differs_and_explains_none_of_them(tmp_path, monkeypatch):
    today, dbt = _four_layer_files()
    monkeypatch.setattr(parity, "_network_old", lambda name: today)
    new = tmp_path / "nearby_trails.geojson"
    new.write_text(json.dumps(dbt))

    exit_code = parity.main(["nearby_trails", "--new", str(new), "--json-dir", str(tmp_path / "results")])

    result = json.loads((tmp_path / "results" / "nearby_trails.json").read_text())
    assert (exit_code, result["outcome"], result["explained"]) == (1, "differences", [])
    reported = {entry["what"] for entry in result["differences"]}
    every_id = {f"properties.id {feature['properties']['id']}" for feature in today["features"] + dbt["features"]}
    assert reported == every_id
    # Each line is paired with its twin under the other id, so the gate reads a changed id, not a lost trail.
    assert all(entry["fields"] == ["properties.id"] for entry in result["differences"])


def test_trail_graph_compares_each_edges_trail_id_with_the_id_todays_file_publishes_the_line_under(tmp_path, monkeypatch):
    """The graph's old side still reads the dbt writers' own lines, so a difference stays the graph's rules alone, but
    each edge carries the id today's nearby_trails.geojson publishes its line under: a phone joins cells cut from
    today's graph to its lines by that id."""
    today, dbt = _four_layer_files()
    new, graph = _graph_beside(tmp_path, dbt)
    monkeypatch.setattr(parity, "_network_old", lambda name: today)

    exit_code = parity.main(["trail_graph", "--new", str(new), "--json-dir", str(tmp_path / "results")])

    result = json.loads((tmp_path / "results" / "trail_graph.json").read_text())
    assert (exit_code, result["outcome"]) == (1, "differences")
    assert len(result["differences"]) == len(graph["edges"]) == len(FOUR_LAYERS)
    assert {tuple(entry["fields"]) for entry in result["differences"]} == {("trail_id",)}


def test_trail_graph_matches_when_the_dbt_writer_publishes_todays_ids(tmp_path, monkeypatch):
    """The same graph, its lines under today's ids on both sides: nothing differs, so the comparison above is the ids'."""
    today, _ = _four_layer_files()
    new, _ = _graph_beside(tmp_path, today)
    monkeypatch.setattr(parity, "_network_old", lambda name: today)

    assert parity.main(["trail_graph", "--new", str(new), "--json-dir", str(tmp_path / "results")]) == 0


def test_trail_graph_keeps_the_dbt_writers_id_where_nearby_trails_explains_the_pair(tmp_path, monkeypatch):
    """Today's file numbering a line by its place where the dbt writer publishes its object id is the old side's input,
    an as-landed copy with no GeoJSON id (AS_LANDED_ID_REASON), and nearby_trails explains it. The graph keeps the dbt
    writer's id for that line, so the old side's input is never read as a difference in the graph."""
    today, _ = _four_layer_files()
    numbered = json.loads(json.dumps(today))
    for place, feature in enumerate(numbered["features"]):
        feature["properties"]["id"] = f"{feature['properties']['source']}:generated-{place}"
    new, _ = _graph_beside(tmp_path, today)
    monkeypatch.setattr(parity, "_network_old", lambda name: numbered)

    assert set(parity._network_id_reasons(numbered, today).values()) == {parity.AS_LANDED_ID_REASON}
    assert parity.main(["trail_graph", "--new", str(new), "--json-dir", str(tmp_path / "results")]) == 0
