"""The monthly lane's freeze: extract/_run.py's as-landed copy and cross-lane inputs, extract/_warehouse.py's pin.

refresh-reference.yml extracts with --as-landed and --cross-lane-inputs and
pins the run's raw inputs to `<steps>/raw_inputs/<raw_run>/`; build-reference.yml
builds the warehouse from the pin alone, and its parity job hands today's
exporters the pin's as-landed files at today's fetchers' paths. Each test runs real dlt
into a `file://` raw store under tmp_path, with the ArcGIS layers
tests/test_extract_run.py mocks; conftest.py's socket guard stays on.

The cases are the ones a promotion or the gate's parity turns on: a pin
holds what a build of its raw_run read and nothing a later run loaded; it is
written once and read back unchanged; a missing or altered pin refuses
rather than reading current raw; a refused run is never pinned; the
as-landed copy appears only for a load that committed.
"""

import json
from pathlib import Path

import duckdb
import pytest

from extract import _kinds, _run, _warehouse
from extract._kinds import ArcgisLayer, OpentrailFeed, SocrataDataset
from extract._run import ExtractRefused, as_landed_feature, make_pipeline, run_pipeline
from extract._warehouse import BuildRefused, load_pinned, load_warehouse, pin_raw_inputs
from lib import http_retry
from tests.test_extract_run import (
    CLOSURES_URL,
    LINES_URL,
    FakeLayer,
    closures,
    feature,
    lines,
    month,
    monthly_lines,
    monthly_points,
)


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """A sources.json holding the two layers tests/test_extract_run.py mocks, in place of the real one."""
    path = tmp_path / "sources.json"
    path.write_text(
        json.dumps({"sources": [{"key": "trails", "url": LINES_URL}, {"key": "closures_layer", "url": CLOSURES_URL}]})
    )
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()
    yield path
    _kinds._registry.cache_clear()


@pytest.fixture
def store(tmp_path):
    return {"bucket_url": (tmp_path / "raw-store").as_uri(), "pipelines_dir": str(tmp_path / "pipelines")}


def run(store, *resources, **options):
    return run_pipeline("hourly", store["bucket_url"], resources=list(resources), pipelines_dir=store["pipelines_dir"], **options)


def pipeline_of(store):
    return make_pipeline("hourly", store["bucket_url"], store["pipelines_dir"])


@pytest.fixture
def steps(tmp_path):
    return (tmp_path / "steps").as_uri()


def landed_root(store) -> Path:
    from urllib.parse import urlparse

    return Path(urlparse(store["bucket_url"]).path) / _run.AS_LANDED_PREFIX


def tables_of(con) -> dict[str, list]:
    names = [
        row[0] for row in con.execute("select table_name from information_schema.tables where table_schema = 'raw'").fetchall()
    ]
    return {
        name: sorted(map(repr, con.execute(f'select * exclude (_dlt_id) from raw."{name}"').fetchall()))
        for name in sorted(names)
        if name != _run.RUNS_TABLE
    }


def test_the_as_landed_copy_is_each_layer_as_its_fetcher_writes_it_without_person_fields(registry, store, requests_mock):
    FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2, ranger="R. Smith")])
    FakeLayer(requests_mock, CLOSURES_URL, [feature(10, "Bridge out")])

    report = run(store, lines(), closures(), as_landed=True)

    assert report.as_landed == {
        "raw_testclub__closures_layer": "closures_layer.geojson",
        "raw_testclub__trails": "trails.geojson",
    }
    root = landed_root(store) / report.load_id
    assert json.loads((root / _run.AS_LANDED_INDEX).read_text()) == report.as_landed
    trails = json.loads((root / "trails.geojson").read_text())
    assert trails["type"] == "FeatureCollection"
    assert [item["properties"]["OBJECTID"] for item in trails["features"]] == [1, 2], "the server's order"
    assert all("RANGER" not in item["properties"] for item in trails["features"]), "a person field never lands"
    assert trails["features"][0]["geometry"] == {"type": "Point", "coordinates": [-74.0, 42.0]}
    assert [item["id"] for item in trails["features"]] == [1, 2], "the GeoJSON id ArcGIS writes is its objectIdField's value"
    assert "_loaded_at" not in trails["features"][0]["properties"], "no fetcher writes the load stamp"


def test_without_as_landed_a_run_writes_no_copy(registry, store, requests_mock):
    FakeLayer(requests_mock, LINES_URL, [feature(1)])

    report = run(store, lines())

    assert report.as_landed == {}
    assert not landed_root(store).exists()


def test_a_refused_run_uploads_no_as_landed_copy(registry, store, requests_mock):
    FakeLayer(requests_mock, LINES_URL, [feature(1)])
    FakeLayer(requests_mock, CLOSURES_URL, [], count_fails=True)

    with pytest.raises(ExtractRefused, match="no upstream count"):
        run(store, lines(), closures(), as_landed=True)

    assert not landed_root(store).exists(), "a copy of a load that never committed is not an input anybody may read"


def test_a_leg_uploads_no_as_landed_copy_of_a_table_it_refused_on_its_own(registry, store, requests_mock):
    """A leg refuses a club's table on its own and extracts the rest again (_run.py's _extract_and_load), and the
    copy starts again with that second extract: the refused closures layer's first-pass file, an empty
    FeatureCollection, must never be uploaded as if that layer had loaded empty, and no row is copied twice."""
    FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2)])
    FakeLayer(requests_mock, CLOSURES_URL, [], count_fails=True)

    report = run_pipeline(
        "notices_ua",
        store["bucket_url"],
        resources=[lines(), closures()],
        pipelines_dir=store["pipelines_dir"],
        as_landed=True,
    )

    assert set(report.isolated) == {closures().name}
    assert report.as_landed == {"raw_testclub__trails": "trails.geojson"}
    root = landed_root(store) / report.load_id
    assert json.loads((root / _run.AS_LANDED_INDEX).read_text()) == report.as_landed
    assert not (root / "closures_layer.geojson").exists()
    trails = json.loads((root / "trails.geojson").read_text())
    assert [item["properties"]["OBJECTID"] for item in trails["features"]] == [1, 2]


def test_only_and_cross_lane_inputs_together_are_a_usage_error(store):
    with pytest.raises(SystemExit) as exit_:
        _run.main(
            [
                "--lane",
                "monthly",
                "--bucket-url",
                store["bucket_url"],
                "--only",
                "raw_registry__sources",
                "--cross-lane-inputs",
            ]
        )

    assert exit_.value.code == 2


def test_socrata_and_opentrail_ids_go_back_where_their_fetchers_files_hold_them():
    socrata = SocrataDataset(key="greenways", club="testclub", type="trail_lines")
    row = {"name": "Greenway", "_socrata_id": "row-7", "geometry": '{"type":"Point","coordinates":[1,2]}'}
    assert as_landed_feature(socrata, row) == {
        "type": "Feature",
        "id": "row-7",
        "geometry": {"type": "Point", "coordinates": [1, 2]},
        "properties": {"name": "Greenway"},
    }
    opentrail = OpentrailFeed(key="at", club="opentrail", type="points_of_interest")
    assert as_landed_feature(opentrail, {"feature_id": None, "kind": "water", "geometry": None}) == {
        "type": "Feature",
        "geometry": None,
        "properties": {"kind": "water"},
    }
    assert _run.as_landed_path(opentrail) == "opentrail_at.geojson"


def test_as_landed_feature_writes_an_arcgis_rows_object_id_as_its_geojson_id_and_keeps_the_property():
    """ArcGIS writes a layer's object id field as each GeoJSON feature's `id` (34 of 34 features of 18 layers, read
    live 2026-10-09), and today's exporters publish that id where a layer has no GlobalID: NYNJTC's Long Path as
    `nynjtc_long_path:<FID>`. The copy without it numbered those lines by place on parity's old side."""
    long_path = ArcgisLayer(key="nynjtc_long_path", club="nynjtc", type="trail_lines")
    row = {"FID": 85, "Trail_Name": "Long Path", "geometry": '{"type":"LineString","coordinates":[[1,2],[3,4]]}'}

    assert as_landed_feature(long_path, row, "FID") == {
        "type": "Feature",
        "id": 85,
        "geometry": {"type": "LineString", "coordinates": [[1, 2], [3, 4]]},
        "properties": {"FID": 85, "Trail_Name": "Long Path"},
    }


def test_as_landed_feature_invents_no_arcgis_id_without_a_named_field_or_a_value_in_it():
    layer = ArcgisLayer(key="trails", club="testclub", type="trail_lines")
    row = {"OBJECTID": 7, "NAME": "Trail", "geometry": None}

    assert "id" not in as_landed_feature(layer, row, None), "no field named by the metadata, so no id"
    assert "id" not in as_landed_feature(layer, {**row, "OBJECTID": None}, "OBJECTID"), "a null object id is no id"
    assert "id" not in as_landed_feature(layer, row, "FID"), "the named field is not in the row"


def test_named_object_id_field_reads_the_oid_typed_field_where_the_metadata_names_no_objectidfield(registry, requests_mock):
    """9 of the 18 layers read on 2026-10-09 leave `objectIdField` out, all off ArcGIS Online; pasda_dcnr_trails'
    esriFieldTypeOID field is OBJECTID_1, beside an OBJECTID that is not its object id."""
    fields = [
        {"name": "OBJECTID", "type": "esriFieldTypeInteger"},
        {"name": "OBJECTID_1", "type": "esriFieldTypeOID"},
        {"name": "NAME", "type": "esriFieldTypeString"},
    ]
    requests_mock.get(LINES_URL, json={"fields": fields})
    assert _run.named_object_id_field(lines()) == "OBJECTID_1"

    requests_mock.get(LINES_URL, json={"objectIdField": "FID", "fields": fields})
    assert _run.named_object_id_field(lines()) == "FID", "the metadata's own objectIdField wins"

    requests_mock.get(LINES_URL, json={"fields": fields[:1]})
    assert _run.named_object_id_field(lines()) is None, "no field named or typed as the object id, so no guess"


def test_named_object_id_field_is_none_and_warns_when_the_metadata_does_not_answer(registry, requests_mock, capsys):
    requests_mock.get(LINES_URL, status_code=500)

    assert _run.named_object_id_field(lines()) is None
    assert len([request for request in requests_mock.request_history if request.url.startswith(LINES_URL)]) == 1, (
        "one request and no retry ladder: the copy is parity's input, not the load"
    )
    assert "no feature carries an id" in capsys.readouterr().out


def test_the_as_landed_copy_writes_the_object_id_its_layers_metadata_types_as_oid(registry, store, requests_mock):
    """A server that names no objectIdField (9 of the 18 layers read 2026-10-09) still gets its ids, from the field its
    metadata types esriFieldTypeOID (tests/test_extract_run.py's FIELDS: OBJECTID)."""
    layer = FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2)])
    as_served = layer.metadata

    def metadata_without_objectidfield(request, context):
        answer = as_served(request, context)
        return None if answer is None else {name: value for name, value in answer.items() if name != "objectIdField"}

    requests_mock.get(LINES_URL, json=metadata_without_objectidfield)

    report = run(store, lines(), as_landed=True)

    trails = json.loads((landed_root(store) / report.load_id / "trails.geojson").read_text())
    assert [item["id"] for item in trails["features"]] == [1, 2]


def test_an_external_layer_lands_at_fetch_external_layers_own_path(registry, monkeypatch):
    monkeypatch.setattr(_run, "is_external_source", lambda entry: entry["key"] == "trails")

    assert _run.as_landed_path(lines()) == "external/trails.geojson"
    assert _run.as_landed_path(closures()) == "closures_layer.geojson"


def test_a_pin_builds_the_same_warehouse_as_the_committed_loads_it_froze(registry, store, steps, requests_mock):
    FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2), feature(3)])
    FakeLayer(requests_mock, CLOSURES_URL, [feature(10)])
    report = run(store, lines(), closures(), as_landed=True)

    manifest, wrote = pin_raw_inputs(pipeline_of(store), store["bucket_url"], steps, report.run_id)

    assert wrote
    assert {table: entry["rows"] for table, entry in manifest["tables"].items()} == {
        "raw_testclub__closures_layer": 1,
        "raw_testclub__trails": 3,
    }
    assert set(manifest["as_landed"]) == {"trails.geojson", "closures_layer.geojson"}
    from_loads, from_pin = duckdb.connect(), duckdb.connect()
    load_warehouse(from_loads, pipeline_of(store))
    load_pinned(from_pin, pipeline_of(store), steps, report.run_id)
    assert tables_of(from_pin) == tables_of(from_loads)
    runs = from_pin.execute(f'select count(*) from raw."{_run.RUNS_TABLE}"').fetchone()[0]
    assert runs == 2


def test_a_pin_still_reads_what_its_raw_run_read_after_a_later_run_replaced_the_table(registry, store, steps, requests_mock):
    """The reason the pin exists: on plain Parquet a `replace` deletes the files the earlier build read (ELT.md, "Storage
    tiers", the raw_inputs row), so without the copy a promotion would build from whatever the next extract left."""
    trails = FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2)])
    first = run(store, lines(), as_landed=True)
    manifest, _ = pin_raw_inputs(pipeline_of(store), store["bucket_url"], steps, first.run_id)
    trails.features, trails.etag = [feature(1), feature(2), feature(3)], "v2"
    second = run(store, lines(), as_landed=True)

    current, pinned = duckdb.connect(), duckdb.connect()
    assert load_warehouse(current, pipeline_of(store)) == {"raw_testclub__trails": 3}
    assert load_pinned(pinned, pipeline_of(store), steps, first.run_id) == {"raw_testclub__trails": 2}
    assert manifest["tables"]["raw_testclub__trails"]["load_id"] == first.load_id != second.load_id
    assert pinned.execute(f'select count(*) from raw."{_run.RUNS_TABLE}"').fetchone()[0] == 1, "the run log stops at the raw_run"


def test_a_raw_run_whose_files_a_later_replace_removed_cannot_be_pinned_after_the_fact(registry, store, steps, requests_mock):
    trails = FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2)])
    first = run(store, lines())
    trails.features, trails.etag = [feature(1), feature(2), feature(3)], "v2"
    run(store, lines())

    with pytest.raises(BuildRefused, match="no committed file from load"):
        pin_raw_inputs(pipeline_of(store), store["bucket_url"], steps, first.run_id)


def test_a_layer_left_out_as_fresh_is_pinned_from_the_load_that_last_read_it(registry, store, steps, requests_mock):
    FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2)])
    first = run(store, lines(), as_landed=True)
    second = run(store, lines(), as_landed=True)
    assert second.verdicts == {"raw_testclub__trails": "fresh"} and second.as_landed == {}

    manifest, _ = pin_raw_inputs(pipeline_of(store), store["bucket_url"], steps, second.run_id)

    assert manifest["tables"]["raw_testclub__trails"]["load_id"] == first.load_id
    assert manifest["as_landed"]["trails.geojson"]["load_id"] == first.load_id


def test_a_layer_whose_as_landed_upload_failed_after_the_run_log_is_read_again_by_the_next_as_landed_run(
    registry, store, steps, requests_mock, monkeypatch, tmp_path
):
    """The load is logged `loaded` before the upload, so the layer answers FRESH next month and no copy is made."""
    FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2)])

    def r2_hiccup(*args, **kwargs):
        raise OSError("R2 503 on put_file")

    with monkeypatch.context() as scoped:
        scoped.setattr(_run, "upload_as_landed", r2_hiccup)
        with pytest.raises(OSError):
            run(store, lines(), as_landed=True)

    second = run(store, lines(), as_landed=True)

    assert second.verdicts == {"raw_testclub__trails": "unknown"}
    assert second.as_landed == {"raw_testclub__trails": "trails.geojson"}
    written = _warehouse.materialize_committed(
        pipeline_of(store), store["bucket_url"], second.run_id, tmp_path / "raw", landed_tables={"raw_testclub__trails"}
    )
    assert written == ["trails.geojson"]
    assert run(store, lines()).verdicts == {"raw_testclub__trails": "fresh"}, "a run without --as-landed asks for no copy"


def test_a_table_whose_load_wrote_no_as_landed_file_refuses_the_pin_and_the_as_landed_step_by_name(
    registry, store, steps, requests_mock, tmp_path, monkeypatch
):
    FakeLayer(requests_mock, LINES_URL, [feature(1)])
    report = run(store, lines())  # no --as-landed, so no copy
    expected = {"raw_testclub__trails"}

    with pytest.raises(BuildRefused, match="raw_testclub__trails: load .* wrote no as-landed file"):
        _warehouse.materialize_committed(
            pipeline_of(store), store["bucket_url"], report.run_id, tmp_path / "raw", landed_tables=expected
        )
    with pytest.raises(BuildRefused, match="raw_testclub__trails: load .* wrote no as-landed file"):
        pin_raw_inputs(pipeline_of(store), store["bucket_url"], steps, report.run_id, landed_tables=expected)
    monkeypatch.setattr(_warehouse, "as_landed_tables", lambda: expected)
    store_args = ["--lane", "hourly", "--bucket-url", store["bucket_url"], "--pipelines-dir", store["pipelines_dir"]]
    with pytest.raises(BuildRefused, match="raw_testclub__trails"):
        _warehouse.main(["as-landed", *store_args, "--steps-url", steps, "--raw-run", report.run_id, "--raw-dir", str(tmp_path)])


def test_a_pin_is_written_once_and_a_second_pin_reads_the_first_back(registry, store, steps, requests_mock, tmp_path):
    FakeLayer(requests_mock, LINES_URL, [feature(1)])
    report = run(store, lines(), as_landed=True)
    index = tmp_path / "tile_index.json"
    index.write_text('{"n42w075": "https://example.org/a.tif"}')
    first, wrote = pin_raw_inputs(
        pipeline_of(store), store["bucket_url"], steps, report.run_id, {"elevation/tile_index.json": index}
    )
    index.write_text('{"n42w075": "https://example.org/b.tif"}')

    again, wrote_again = pin_raw_inputs(
        pipeline_of(store), store["bucket_url"], steps, report.run_id, {"elevation/tile_index.json": index}
    )

    assert wrote and not wrote_again
    assert again == first, "the first attempt's pin is the answer, whatever a rerun brings"


def test_a_raw_run_with_no_pin_refuses_rather_than_reading_current_raw(registry, store, steps, requests_mock):
    FakeLayer(requests_mock, LINES_URL, [feature(1)])
    report = run(store, lines())

    with pytest.raises(BuildRefused, match="no pinned raw inputs"):
        load_pinned(duckdb.connect(), pipeline_of(store), steps, report.run_id)


def test_a_pin_whose_file_changed_after_it_was_written_refuses(registry, store, steps, requests_mock):
    FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2)])
    report = run(store, lines())
    manifest, _ = pin_raw_inputs(pipeline_of(store), store["bucket_url"], steps, report.run_id)
    from urllib.parse import urlparse

    pinned = Path(urlparse(steps).path) / "raw_inputs" / report.run_id / manifest["tables"]["raw_testclub__trails"]["file"]
    pinned.write_bytes(pinned.read_bytes() + b"\0")

    with pytest.raises(BuildRefused, match="does not match the sha256"):
        load_pinned(duckdb.connect(), pipeline_of(store), steps, report.run_id)


def test_a_refused_run_is_never_pinned(registry, store, steps, requests_mock):
    FakeLayer(requests_mock, LINES_URL, [feature(1)])
    FakeLayer(requests_mock, CLOSURES_URL, [], count_fails=True)
    with pytest.raises(ExtractRefused):
        run(store, lines(), closures())
    refused = [row["run_id"] for row in _run.run_log_rows(pipeline_of(store)) if row["outcome"] == "refused"]

    with pytest.raises(BuildRefused, match="ended refused"):
        pin_raw_inputs(pipeline_of(store), store["bucket_url"], steps, refused[0])


def test_a_monthly_run_that_left_one_layer_out_is_pinned_with_that_layers_last_month(
    registry, store, steps, requests_mock, monkeypatch
):
    """Monthly run 16 (refresh-reference.yml 37210020925): the layers it left out logged `refused`, and the pin
    refused the whole run on their rows, though the rest had loaded and the run check had passed them."""
    monkeypatch.setattr(http_retry.time, "sleep", lambda seconds: None)
    trails = FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2)])
    FakeLayer(requests_mock, CLOSURES_URL, [feature(10), feature(11)])
    month(store, monthly_lines(), monthly_points())
    trails.features, trails.etag = [feature(1), feature(2), feature(3)], "v2"
    requests_mock.get(CLOSURES_URL, status_code=403)
    partial = month(store, monthly_lines(), monthly_points())
    assert set(partial.isolated) == {"raw_otherclub__closures_layer"}

    monthly = make_pipeline("monthly", store["bucket_url"], store["pipelines_dir"])
    manifest, wrote = pin_raw_inputs(monthly, store["bucket_url"], steps, partial.run_id)
    counts = load_pinned(duckdb.connect(), monthly, steps, partial.run_id)

    assert wrote
    assert counts == {"raw_testclub__trails": 3, "raw_otherclub__closures_layer": 2}
    assert manifest["tables"]["raw_otherclub__closures_layer"]["load_id"] != partial.load_id


def test_a_proven_zero_is_pinned_without_a_file_and_loads_as_its_hinted_empty_table(registry, store, steps, requests_mock):
    FakeLayer(requests_mock, CLOSURES_URL, [])
    report = run(store, closures())

    manifest, _ = pin_raw_inputs(pipeline_of(store), store["bucket_url"], steps, report.run_id)
    con = duckdb.connect()
    counts = load_pinned(con, pipeline_of(store), steps, report.run_id)

    assert manifest["tables"]["raw_testclub__closures_layer"]["file"] is None
    assert counts == {"raw_testclub__closures_layer": 0}
    columns = {row[0] for row in con.execute('describe raw."raw_testclub__closures_layer"').fetchall()}
    assert {"objectid", "globalid", "name", "geometry", "_loaded_at"} <= columns


def test_the_pins_as_landed_files_and_extras_come_back_at_todays_fetchers_paths(registry, store, steps, requests_mock, tmp_path):
    FakeLayer(requests_mock, LINES_URL, [feature(1)])
    report = run(store, lines(), as_landed=True)
    index = tmp_path / "tile_index.json"
    index.write_text('{"n42w075": "https://example.org/a.tif"}')
    pin_raw_inputs(pipeline_of(store), store["bucket_url"], steps, report.run_id, {"elevation/tile_index.json": index})

    raw_dir = tmp_path / "data" / "raw"
    written = _warehouse.materialize_pinned(pipeline_of(store), steps, report.run_id, raw_dir)

    assert written == ["elevation/tile_index.json", "trails.geojson"]
    assert json.loads((raw_dir / "trails.geojson").read_text())["features"][0]["properties"]["OBJECTID"] == 1
    assert (raw_dir / "elevation" / "tile_index.json").read_text() == index.read_text()


def test_a_fresh_working_directory_reads_a_pin_with_no_dlt_state_of_its_own(registry, store, steps, requests_mock, tmp_path):
    FakeLayer(requests_mock, CLOSURES_URL, [])
    report = run(store, closures())
    pin_raw_inputs(pipeline_of(store), store["bucket_url"], steps, report.run_id)

    fresh = make_pipeline("hourly", store["bucket_url"], str(tmp_path / "another-runner"))
    counts = load_pinned(duckdb.connect(), fresh, steps, report.run_id)

    assert counts == {"raw_testclub__closures_layer": 0}, (
        "a build job starts with no dlt directory, and a proven zero still builds"
    )


def test_the_step_cache_keeps_a_first_store_refuses_a_torn_one_and_fetches_by_name(
    registry, store, steps, requests_mock, tmp_path
):
    FakeLayer(requests_mock, LINES_URL, [feature(1)])
    run(store, lines())
    one, two = tmp_path / "warehouse.duckdb", tmp_path / "manifest.json"
    one.write_text("first")
    two.write_text("{}")
    pipeline = pipeline_of(store)

    assert len(_warehouse.store_once(pipeline, store["bucket_url"], steps, "dbt_warehouse/ua/r1", [one, two])) == 2
    one.write_text("second")
    assert _warehouse.store_once(pipeline, store["bucket_url"], steps, "dbt_warehouse/ua/r1", [one, two]) == []
    fetched = _warehouse.fetch_stored(pipeline, steps, "dbt_warehouse/ua/r1", ["warehouse.duckdb"], tmp_path / "out")
    assert fetched[0].read_text() == "first", "write-once: a rerun's file never replaces the first"
    with pytest.raises(BuildRefused, match="refusing to complete it"):
        _warehouse.store_once(pipeline, store["bucket_url"], steps, "dbt_warehouse/ua/r1", [one, tmp_path / "sources.json"])
    with pytest.raises(BuildRefused, match="not in the step cache"):
        _warehouse.fetch_stored(pipeline, steps, "dbt_warehouse/ua/r1", ["run_results.json"], tmp_path / "out")


def test_the_step_cache_must_share_the_raw_stores_bucket(registry, store, requests_mock):
    FakeLayer(requests_mock, LINES_URL, [feature(1)])
    report = run(store, lines())

    with pytest.raises(ValueError, match="not in the raw store's bucket"):
        pin_raw_inputs(pipeline_of(store), store["bucket_url"], "s3://another-bucket/steps", report.run_id)


def test_cross_lane_inputs_read_the_named_resource_of_another_lane_and_only_it(registry, store, requests_mock, monkeypatch):
    FakeLayer(requests_mock, LINES_URL, [feature(1)])
    FakeLayer(requests_mock, CLOSURES_URL, [feature(10)])
    monthly_lines = ArcgisLayer(key="trails", club="testclub", type="trail_lines")
    monkeypatch.setattr(_run, "ALSO_READS", {"monthly": {"raw_testclub__closures_layer": "a test"}})

    plain = run_pipeline(
        "monthly", store["bucket_url"], resources=[monthly_lines, closures()], pipelines_dir=store["pipelines_dir"]
    )
    crossed = run_pipeline(
        "monthly",
        store["bucket_url"],
        resources=[monthly_lines, closures()],
        pipelines_dir=store["pipelines_dir"],
        cross_lane=True,
    )

    assert set(plain.verdicts) == {"raw_testclub__trails"}
    assert set(crossed.verdicts) == {"raw_testclub__trails", "raw_testclub__closures_layer"}


def test_cross_lane_inputs_naming_no_resource_refuse_rather_than_reading_less(registry, store, monkeypatch):
    monkeypatch.setattr(_run, "ALSO_READS", {"monthly": {"raw_nobody__gone": "a test"}})

    with pytest.raises(ValueError, match="raw_nobody__gone"):
        run_pipeline(
            "monthly", store["bucket_url"], resources=[closures()], pipelines_dir=store["pipelines_dir"], cross_lane=True
        )


def test_the_real_cross_lane_inputs_name_resources_the_extract_has():
    from extract._contract import all_resources, discover, discover_shared

    resources = all_resources(discover() + discover_shared())
    for lane, wanted in _run.ALSO_READS.items():
        found = {resource.name: resource for resource in resources if resource.name in wanted}
        assert set(found) == set(wanted), f"{lane}: ALSO_READS names {sorted(set(wanted) - set(found))}, which no resource is"
        assert all(resource.cadence not in _run.LANES[lane] for resource in found.values()), "already this lane's own"


def test_the_report_json_names_the_raw_run_and_says_refused_when_the_run_refused(
    registry, store, requests_mock, tmp_path, monkeypatch
):
    FakeLayer(requests_mock, CLOSURES_URL, [], count_fails=True)
    monkeypatch.setattr(_run, "discover", list)
    monkeypatch.setattr(_run, "discover_shared", list)
    monkeypatch.setattr(_run, "all_resources", lambda files: [closures()])
    path = tmp_path / "report.json"

    with pytest.raises(ExtractRefused):
        _run.main(
            [
                "--lane",
                "hourly",
                "--bucket-url",
                store["bucket_url"],
                "--pipelines-dir",
                store["pipelines_dir"],
                "--report-json",
                str(path),
            ]
        )

    assert json.loads(path.read_text())["outcome"] == "refused"
