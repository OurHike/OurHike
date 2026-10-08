"""parity.py's old side on a monthly run's pin: the two water scans #1652 keeps are what today's exporter reads.

A monthly run pins fetch_osm_water.py's points and fetch_trail_water.py --derive's file at PINNED_OSM_WATER and
PINNED_SITE_WATER (extract/_geofabrik.py's SCANS). Without these, the old side read only the fixture's inputs and had
no OSM water and no site water on a live run, while the dbt side had both, so poi_water would read `differs` for a
reason that is parity's own.
"""

from __future__ import annotations

import json

import build_osm_water_reach as reach
import export_poi
import parity


def test_the_pinned_site_water_file_is_the_old_sides_trail_water(tmp_path, monkeypatch):
    pinned = tmp_path / parity.PINNED_SITE_WATER
    pinned.parent.mkdir(parents=True)
    pinned.write_text('{"sites": []}', encoding="utf-8")
    monkeypatch.setattr(export_poi, "RAW_DIR", tmp_path)
    parity._site_water_old.cache_clear()
    try:
        assert parity._site_water_old() == pinned
    finally:
        parity._site_water_old.cache_clear()


def test_without_a_pinned_scan_or_the_fixtures_inputs_there_is_no_site_water(tmp_path, monkeypatch):
    monkeypatch.setattr(export_poi, "RAW_DIR", tmp_path)
    parity._site_water_old.cache_clear()
    try:
        assert not parity._site_water_old().exists()
    finally:
        parity._site_water_old.cache_clear()


def test_the_pinned_osm_points_are_graded_against_live_epqs_and_name_their_own_path(tmp_path, monkeypatch):
    for name in ("centerline.geojson", "side_trails.geojson", "shelters.geojson", "campsites.geojson"):
        (tmp_path / name).write_text('{"type": "FeatureCollection", "features": []}', encoding="utf-8")
    pinned = tmp_path / parity.PINNED_OSM_WATER
    pinned.parent.mkdir(parents=True)
    pinned.write_text('{"type": "FeatureCollection", "features": []}', encoding="utf-8")
    monkeypatch.setattr(export_poi, "RAW_DIR", tmp_path)
    monkeypatch.setattr(parity, "_published_network", lambda: tmp_path / "network.geojson")
    live = reach.elevation_ft
    seen = {}

    def measure(con, quiet):
        seen["elevation_ft"] = reach.elevation_ft
        seen["points"] = (reach.RAW_DIR / "osm_water.geojson").resolve()
        return []

    monkeypatch.setattr(reach, "measure_distances", measure)
    monkeypatch.setattr(reach, "apply_grade_gate", lambda records, quiet: None)
    monkeypatch.setattr(reach, "write", lambda records, guard: reach.OUT_PATH.write_text(json.dumps([])))

    name, verdicts = parity._osm_water_old()

    assert name == parity.PINNED_OSM_WATER
    assert seen["points"] == pinned.resolve()
    assert seen["elevation_ft"] is live, "no fixture answers stand in for EPQS on a pinned scan"
    assert reach.elevation_ft is live
    assert json.loads(open(verdicts, encoding="utf-8").read()) == []


def _scan(tmp_path, monkeypatch, pinned: bool, records: list[dict]) -> list[str]:
    """_osm_water_old() over one stand-in scan: what it asked EPQS for and when, as a list of events."""
    import fetch_trail_water

    for name in ("centerline.geojson", "side_trails.geojson", "shelters.geojson", "campsites.geojson"):
        (tmp_path / name).write_text('{"type": "FeatureCollection", "features": []}', encoding="utf-8")
    points = tmp_path / (parity.PINNED_OSM_WATER if pinned else "osm_water/points.geojson")
    points.parent.mkdir(parents=True, exist_ok=True)
    points.write_text('{"type": "FeatureCollection", "features": []}', encoding="utf-8")
    if not pinned:
        (tmp_path / "osm_water" / "epqs_elevations.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(export_poi, "RAW_DIR", tmp_path)
    monkeypatch.setattr(parity, "_published_network", lambda: tmp_path / "network.geojson")
    events: list = []
    monkeypatch.setattr(reach, "measure_distances", lambda con, quiet: records)
    monkeypatch.setattr(fetch_trail_water, "prefetch_elevations", lambda wanted: events.append(("prefetch", list(wanted))))
    monkeypatch.setattr(reach, "apply_grade_gate", lambda records, quiet: events.append(("gate", None)))
    monkeypatch.setattr(reach, "write", lambda records, guard: reach.OUT_PATH.write_text("[]"))
    parity._osm_water_old.cache_clear()
    try:
        parity._osm_water_old()
    finally:
        parity._osm_water_old.cache_clear()
    return events


WALKS = [
    {"lat": 41.1, "lon": -74.1, "passes_distance": True, "walk_to": {"lat": 41.2, "lon": -74.2}},
    {"lat": 41.3, "lon": -74.3, "passes_distance": False, "walk_to": {"lat": 41.4, "lon": -74.4}},
    {"lat": 41.5, "lon": -74.5, "passes_distance": True, "passes_grade": True, "walk_to": {"lat": 41.6, "lon": -74.6}},
    {"lat": 41.7, "lon": -74.7, "passes_distance": True, "walk_to": {"lat": 41.8, "lon": -74.8}},
]


def test_a_pinned_scan_asks_epqs_for_both_ends_of_every_walk_the_gate_will_grade_before_it_grades(tmp_path, monkeypatch):
    """Four at a time, as step_osm_water_grade asks on the dbt side: one at a time, monthly run 23's grade asked EPQS
    for nearly three hours. A walk that failed on distance, or is graded already, is never asked about."""
    events = _scan(tmp_path, monkeypatch, pinned=True, records=WALKS)

    assert events == [
        ("prefetch", [(41.1, -74.1), (41.2, -74.2), (41.7, -74.7), (41.8, -74.8)]),
        ("gate", None),
    ]


def test_the_fixtures_scan_never_asks_epqs(tmp_path, monkeypatch):
    """CI reads make_dbt_fixtures.py's answers in place of EPQS, so nothing may reach the network there."""
    events = _scan(tmp_path, monkeypatch, pinned=False, records=WALKS)

    assert events == [("gate", None)]
