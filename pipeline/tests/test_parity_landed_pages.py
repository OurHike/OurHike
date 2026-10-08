"""parity.py's old side reads NYNJTC's two page-read sources as the extract landed them, which is what a pin carries.

The Long Path guide and the Hike Finder are web pages, and a monthly pin carries neither page: it carries the rows the
guide_pages and published_hikes kinds landed, each the page as lib/nynjtc_long_path_guide.py or lib/hikefinder.py
parses it. Monthly run 30 (refresh-reference.yml 37772454847) read the fixture's pages instead, so its old side placed
no guide waypoint (271 differences in nearby_poi, 111 in places) and could not run suggested_hikes at all. These hold
the reading to the shape the extract lands; tests/test_extract_fixtures.py holds it to what dlt really lands from
make_dbt_fixtures.py's pages.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest
import yaml

import export_nearby_poi
import parity
from lib import hikefinder
from lib import nynjtc_long_path_guide as guide

SOURCES = Path(__file__).parent.parent / "dbt" / "models" / "staging" / "nynjtc"


def _source_tables() -> set[str]:
    tables = set()
    for path in SOURCES.rglob("*__sources.yml"):
        for source in yaml.safe_load(path.read_text())["sources"]:
            tables |= {f"{source.get('schema', 'raw')}.{table['name']}" for table in source.get("tables", [])}
    return tables


def test_the_two_tables_are_the_ones_the_dbt_sources_read():
    assert {parity.GUIDE_TABLE, parity.HIKE_FINDER_TABLE} <= _source_tables()


def test_the_guide_fields_are_section_to_dict_and_its_nested_ones_are_what_lands_as_json():
    section = guide.Section(number=1, title="t", distance_miles=1.0, parks=None, url="u").to_dict()
    assert list(parity.GUIDE_FIELDS) == list(section)
    assert set(parity.GUIDE_JSON_FIELDS) == {name for name, value in section.items() if isinstance(value, list | dict)}


def test_the_hike_json_fields_are_as_cache_entrys_nested_values():
    hike = hikefinder.ParsedHike(id=1, name="n", source_url="u")
    entry = hikefinder.as_cache_entry(hike, "2026-10-08T00:00:00+00:00")
    nested = {name for name, value in entry.items() if isinstance(value, list | dict)}
    assert nested | {"start"} == set(parity.HIKE_JSON_FIELDS)


def _section(number: int) -> dict:
    """A section as parse_section() reads one and to_dict() writes it, which the guide_pages kind lands."""
    return guide.Section(
        number=number,
        title=f"Section {number}",
        distance_miles=5.5,
        parks="Fixture State Park",
        url=f"https://www.nynjtc.org/lp-section-{number}/",
        parking=[guide.Entry(mile=0.0, text="Lot", lat=41.0, lon=-74.0)],
        description=[guide.Entry(mile=1.25, text="Spring on the left", off_trail_miles=0.1)],
        notes={"Water": ["Treat it"]},
    ).to_dict()


def _guide_warehouse(path: Path, rows: list[dict]) -> Path:
    """A warehouse whose raw guide table holds `rows` as the guide_pages kind lands them: the nested values as JSON
    text, the page's sha256 beside them, and dlt's own columns."""
    with duckdb.connect(str(path)) as con:
        con.execute("create schema raw")
        con.execute(
            f"create table {parity.GUIDE_TABLE} (number bigint, title varchar, distance_miles double, parks varchar, "
            "url varchar, parking varchar, camping varchar, description varchar, notes varchar, page_sha256 varchar, "
            "_dlt_load_id varchar, _dlt_id varchar)"
        )
        for index, row in enumerate(rows):
            con.execute(
                f"insert into {parity.GUIDE_TABLE} values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    row["number"],
                    row["title"],
                    row["distance_miles"],
                    row["parks"],
                    row["url"],
                    *(json.dumps(row[name]) for name in parity.GUIDE_JSON_FIELDS),
                    "sha",
                    "load-1",
                    f"row-{index}",
                ],
            )
    return path


def test_the_landed_sections_read_back_as_the_fetchers_sections_json_in_section_order_one_per_section(tmp_path):
    """Landed out of order and with one page twice, as dlt may hold it: read in the index's order, once."""
    rows = [_section(2), _section(1), _section(2)]
    warehouse = _guide_warehouse(tmp_path / "w.duckdb", rows)

    sections = parity._landed_guide_sections(warehouse)

    assert sections == [_section(1), _section(2)]
    assert [guide.Section.from_dict(section).to_dict() for section in sections] == sections


def test_a_section_landed_twice_differently_is_refused(tmp_path):
    warehouse = _guide_warehouse(tmp_path / "w.duckdb", [_section(1), {**_section(1), "title": "Another"}])
    with pytest.raises(SystemExit, match="section 1 twice"):
        parity._landed_guide_sections(warehouse)


def test_no_guide_table_is_no_sections_and_no_warehouse_is_none_too(tmp_path):
    with duckdb.connect(str(tmp_path / "w.duckdb")) as con:
        con.execute("create schema raw")
    assert parity._landed_guide_sections(tmp_path / "w.duckdb") is None
    assert parity._landed_guide_sections(tmp_path / "absent.duckdb") is None


def test_the_old_side_writes_the_landed_sections_where_guide_records_reads_them(tmp_path, monkeypatch):
    warehouse = _guide_warehouse(tmp_path / "w.duckdb", [_section(1)])
    monkeypatch.setenv("OURHIKE_WAREHOUSE", str(warehouse))
    folder = parity._guide_sections_old()
    assert json.loads((folder / "sections.json").read_text()) == [_section(1)]


def test_a_guide_that_reaches_hikers_with_nothing_landed_refuses_the_old_side_as_main_refuses_it(tmp_path, monkeypatch):
    """export_nearby_poi.main() raises for a published guide with no cache, rather than publishing without it; the old
    side refuses the same input (old_side_refused), where it used to compare a file today's exporter never writes."""
    monkeypatch.setenv("OURHIKE_WAREHOUSE", str(tmp_path / "absent.duckdb"))
    monkeypatch.setattr(export_nearby_poi, "poi_sources", lambda registry: [])
    registry = export_nearby_poi.load_registry(export_nearby_poi.ROOT / "sources.json")
    assert export_nearby_poi.find_source(registry, guide.SOURCE_KEY)["reaches_hikers"]
    with pytest.raises(SystemExit, match="export_nearby_poi.py refuses this input"):
        parity._nearby_poi_old()


STAMP = datetime(2026, 10, 8, 11, 48, tzinfo=UTC).isoformat(timespec="seconds")
GPX = '<gpx><trk><trkseg><trkpt lat="41.0" lon="-74.0"></trkpt><trkpt lat="41.1" lon="-74.1"></trkpt></trkseg></trk></gpx>'


def _hike(hike_id: int, routed: bool) -> dict:
    """A cache entry as fetch_hikefinder.py writes one and the published_hikes kind lands one: as_cache_entry()."""
    hike = hikefinder.ParsedHike(
        id=hike_id,
        name=f"Hike {hike_id}",
        source_url=f"https://example.test/hike.php?id={hike_id}",
        stated_miles=3.5,
        start=hikefinder.Coordinate(lat=41.0, lon=-74.0, label="Parking location"),
        features=["Views"],
        description=["A walk."],
        has_published_route=routed,
        raw_fields={"Length": "3.5 miles"},
    )
    return hikefinder.as_cache_entry(hike, STAMP)


def _column_type(name: str, value) -> str:
    """The DuckDB type the extract lands a cache entry's value as: JSON text for a nested one (max_table_nesting 0)."""
    if name in parity.HIKE_JSON_FIELDS:
        return "varchar"
    return {bool: "boolean", int: "bigint", float: "double"}.get(type(value), "varchar")


def _hike_warehouse(path: Path, rows: list[tuple[dict, str | None]]) -> Path:
    """A warehouse whose raw Hike Finder table holds each (cache entry, gpx) as the published_hikes kind lands it."""
    first = rows[0][0]
    names = list(first)
    with duckdb.connect(str(path)) as con:
        con.execute("create schema raw")
        columns = ", ".join(f"{name} {_column_type(name, first[name])}" for name in names)
        con.execute(f"create table {parity.HIKE_FINDER_TABLE} ({columns}, gpx varchar, _dlt_id varchar)")
        for index, (entry, track) in enumerate(rows):
            values = [json.dumps(entry[name]) if name in parity.HIKE_JSON_FIELDS else entry[name] for name in names]
            con.execute(
                f"insert into {parity.HIKE_FINDER_TABLE} values ({', '.join('?' * (len(names) + 2))})",
                [*values, track, f"row-{index}"],
            )
    return path


def test_the_landed_hikes_read_back_as_the_fetchers_cache_with_each_published_track_stored(tmp_path):
    routed, plain = _hike(7, routed=True), _hike(3, routed=False)
    warehouse = _hike_warehouse(tmp_path / "w.duckdb", [(routed, GPX), (plain, None), (routed, GPX)])
    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()

    cache = parity._landed_hikes(warehouse, gpx_dir)

    assert list(cache) == ["3", "7"], "hike number order, the listing's, and a copy read once"
    assert cache["7"] == {**routed, "gpx_file": "7.gpx"}
    assert cache["3"] == {**plain, "gpx_file": None}
    assert (gpx_dir / "7.gpx").read_text() == GPX
    assert not (gpx_dir / "3.gpx").exists()


def test_a_hike_landed_twice_differently_is_refused_and_no_table_is_no_hike(tmp_path):
    hike = _hike(7, routed=False)
    warehouse = _hike_warehouse(tmp_path / "w.duckdb", [(hike, None), ({**hike, "name": "Renamed"}, None)])
    with pytest.raises(SystemExit, match="hike 7 twice"):
        parity._landed_hikes(warehouse, tmp_path)
    assert parity._landed_hikes(tmp_path / "absent.duckdb", tmp_path) == {}
