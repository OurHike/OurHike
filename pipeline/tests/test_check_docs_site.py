"""check_docs_site.py: what the docs site at ourhike.org/data/ must hold, and must not (decision 10).

The sites here are small copies of the shape dbt 2.0.6's `dbt docs generate`
wrote for this project on 2026-10-03: `index.html`, `assets/`, and Parquet
under `info_schema/v1/`, where `dbt.unit_tests.parquet` carries `unique_id`,
`original_file_path`, `given` and `expect`, and `dbt_rt.invocations.parquet`
carries `invocation_id` and `vars_override`.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

import check_docs_site as cds

UNIT_TEST_YAML = "models/intermediate/trail_lines/_trail_lines__unit_tests.yml"
# index.html as dbt 2.0.6 wrote it on 2026-10-03, cut to the line that matters.
INDEX = (
    "<!doctype html><html><head><script>window.__DBT_DOCS__ = "
    '{"schema_version":1,"dbt_version":"2.0.6","duckdb_cdn_base":"https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.32.0",'
    '"data_dir":"info_schema/v1/","telemetry":{"enabled":TELEMETRY,"dbt_cloud_account_identifier":""}};</script>'
    '<script type="module" crossorigin src="./assets/index.js"></script></head><body><div id="root"></div></body></html>'
)


def _parquet(path: Path, rows: list[dict[str, str | None]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = list(rows[0])
    connection = duckdb.connect()
    connection.execute(f"CREATE TABLE t ({', '.join(f'{c} VARCHAR' for c in columns)})")
    connection.executemany(f"INSERT INTO t VALUES ({', '.join('?' for _ in columns)})", [list(r.values()) for r in rows])
    connection.execute("COPY t TO ? (FORMAT parquet)", [str(path)])


def _site(tmp_path: Path, *, models=None, unit_tests=None, invocations=None, index=INDEX.replace("TELEMETRY", "false")) -> Path:
    site = tmp_path / "site"
    (site / "assets").mkdir(parents=True)
    (site / "assets" / "index.js").write_text("console.log('docs')", encoding="utf-8")
    (site / "index.html").write_text(index, encoding="utf-8")
    v1 = site / "info_schema" / "v1"
    _parquet(
        v1 / "dbt.models.parquet",
        models or [{"unique_id": "model.ourhike.trail_lines", "raw_code": "select 1", "description": "The A.T."}],
    )
    _parquet(
        v1 / "dbt.unit_tests.parquet",
        unit_tests or [{"unique_id": "unit_test.ourhike.x", "original_file_path": UNIT_TEST_YAML, "given": "[]", "expect": "{}"}],
    )
    _parquet(
        v1 / "dbt_rt.invocations.parquet",
        invocations or [{"invocation_id": "01a0", "command": "compile", "vars_override": None}],
    )
    return site


def _project(tmp_path: Path, yaml_text: str) -> Path:
    project = tmp_path / "project"
    path = project / UNIT_TEST_YAML
    path.parent.mkdir(parents=True)
    path.write_text(yaml_text, encoding="utf-8")
    return project


def _run(site: Path, project: Path, capsys) -> tuple[int, str]:
    code = cds.main([str(site), "--project", str(project)])
    return code, capsys.readouterr().out


def test_a_complete_site_with_no_coordinates_passes(tmp_path, capsys):
    code, out = _run(_site(tmp_path), _project(tmp_path, "unit_tests: []"), capsys)
    assert code == 0, out
    assert "0 failure(s)" in out


@pytest.mark.parametrize(
    ("part", "message"),
    [("index.html", "index.html"), ("assets", "no file under"), ("parquet", "no Parquet file under")],
)
def test_a_site_missing_any_of_its_three_parts_fails(tmp_path, capsys, part, message):
    """On a preview a missing part is otherwise invisible: `_site/404.html` is the app shell."""
    site = _site(tmp_path)
    if part == "index.html":
        (site / "index.html").write_text("", encoding="utf-8")
    elif part == "assets":
        (site / "assets" / "index.js").unlink()
    else:
        for path in site.rglob("*.parquet"):
            path.unlink()
    code, out = _run(site, _project(tmp_path, ""), capsys)
    assert code == 1
    assert next(line for line in out.splitlines() if line.startswith("FAIL")).count(message) == 1, out


def test_a_site_directory_that_is_not_there_is_exit_2(tmp_path, capsys):
    assert cds.main([str(tmp_path / "never-built")]) == 2


@pytest.mark.parametrize(
    ("text", "shape"),
    [
        ("select ST_GeomFromText('POINT (-74.123456 41.123456)')", "WKT"),
        ("MULTILINESTRING Z ((-74.1 41.1 300, -74.2 41.2 310))", "WKT"),
        ('{"type":"Point","coordinates":[-74.123456,41.123456]}', "GeoJSON coordinates"),
        ('{"lat": 41.123456, "name": "a spring"}', "lat/lon value"),
        ("a spring at -74.123456, 41.123456 on the ridge", "decimal pair"),
    ],
)
def test_each_shape_in_a_model_fails_and_the_failure_does_not_print_it(tmp_path, capsys, text, shape):
    """A coordinate that should not be published should not reach a public CI log either."""
    site = _site(tmp_path, models=[{"unique_id": "model.ourhike.trail_lines", "raw_code": text, "description": "x"}])
    code, out = _run(site, _project(tmp_path, ""), capsys)
    assert code == 1
    assert f"raw_code of model.ourhike.trail_lines holds {shape}" in out
    assert "41.123456" not in out and "41.1 " not in out


def test_coordinates_in_a_text_file_fail(tmp_path, capsys):
    site = _site(tmp_path)
    (site / "assets" / "index.js").write_text('const p = {"coordinates": [-74.123456, 41.123456]}', encoding="utf-8")
    code, out = _run(site, _project(tmp_path, ""), capsys)
    assert code == 1
    assert "assets/index.js holds GeoJSON coordinates" in out


@pytest.mark.parametrize(
    ("index", "reason"),
    [
        (INDEX.replace("TELEMETRY", "true"), "do not say telemetry is off"),
        (INDEX.replace('"telemetry":{"enabled":TELEMETRY,"dbt_cloud_account_identifier":""}', '"x":1'), "do not say"),
        ("<html><body>docs</body></html>", "no readable window.__DBT_DOCS__"),
    ],
)
def test_a_page_that_does_not_say_telemetry_is_off_fails(tmp_path, capsys, index, reason):
    """The documented opt-out reaches the page as `telemetry.enabled: false`; a public page is not where to learn what `true` does."""
    code, out = _run(_site(tmp_path, index=index), _project(tmp_path, ""), capsys)
    assert code == 1
    assert reason in out


@pytest.mark.parametrize(
    "text",
    [
        "-- one that is not a LineString or MultiLineString ('not_a_line')",
        "The OSM node id, which names the point (`osm_water:<osm_id>`).",
    ],
)
def test_prose_that_names_a_geometry_type_passes(tmp_path, capsys, text):
    """Both read off this project's docs on 2026-10-03: a geometry type in words, with no number after it."""
    site = _site(tmp_path, models=[{"unique_id": "model.ourhike.x", "raw_code": text, "description": text}])
    code, out = _run(site, _project(tmp_path, ""), capsys)
    assert code == 0, out


def test_a_pair_of_numbers_outside_180_is_not_a_coordinate(tmp_path, capsys):
    """NWS grid units, which a unit test here carries: `564.1731999 833.6643387` is not a place."""
    site = _site(tmp_path, models=[{"unique_id": "model.ourhike.x", "raw_code": "-- 564.1731999 833.6643387", "description": ""}])
    code, out = _run(site, _project(tmp_path, ""), capsys)
    assert code == 0, out


def test_a_unit_test_row_whose_numbers_are_all_in_its_own_yaml_passes(tmp_path, capsys):
    given = '[{"rows":[{"geom_wkt":"LINESTRING (-74.12345678901 41.00000049999, -74.1234565 41.0000005)"}]}]'
    project = _project(
        tmp_path,
        "unit_tests:\n  - given:\n      - rows:\n          - {geom_wkt: 'LINESTRING (-74.12345678901 41.00000049999, -74.1234565 41.0000005)'}\n",
    )
    site = _site(
        tmp_path,
        unit_tests=[{"unique_id": "unit_test.ourhike.x", "original_file_path": UNIT_TEST_YAML, "given": given, "expect": "{}"}],
    )
    code, out = _run(site, project, capsys)
    assert code == 0, out
    assert "4 precise numbers in the coordinate-shaped cells of 1 tests" in out


def test_a_unit_test_row_with_a_number_its_yaml_does_not_hold_fails(tmp_path, capsys):
    """The case the exemption must not cover: a coordinate from somewhere other than the committed YAML."""
    given = '[{"rows":[{"geom_wkt":"POINT (-74.987654 41.987654)"}]}]'
    site = _site(
        tmp_path,
        unit_tests=[{"unique_id": "unit_test.ourhike.x", "original_file_path": UNIT_TEST_YAML, "given": given, "expect": "{}"}],
    )
    code, out = _run(site, _project(tmp_path, "unit_tests: []  # POINT (-74.0 41.0)"), capsys)
    assert code == 1
    assert "given of unit_test.ourhike.x holds WKT, decimal pair with 2 number(s) not in" in out
    assert "41.987654" not in out


def test_a_unit_test_declared_in_a_file_the_project_does_not_hold_fails(tmp_path, capsys):
    given = '[{"rows":[{"geom_wkt":"POINT (-74.987654 41.987654)"}]}]'
    site = _site(
        tmp_path,
        unit_tests=[
            {"unique_id": "unit_test.ourhike.x", "original_file_path": "models/elsewhere.yml", "given": given, "expect": "{}"}
        ],
    )
    code, out = _run(site, _project(tmp_path, ""), capsys)
    assert code == 1
    assert "(models/elsewhere.yml) is not under" in out


def test_the_exemption_covers_given_and_expect_only(tmp_path, capsys):
    """A unit test's description is prose a person wrote for the page, so it is searched like any other cell."""
    site = _site(
        tmp_path,
        unit_tests=[
            {
                "unique_id": "unit_test.ourhike.x",
                "original_file_path": UNIT_TEST_YAML,
                "given": "[]",
                "expect": "{}",
                "description": "the spring at POINT (-74.123456 41.123456)",
            }
        ],
    )
    code, out = _run(site, _project(tmp_path, "POINT (-74.123456 41.123456)"), capsys)
    assert code == 1
    assert "description of unit_test.ourhike.x holds WKT" in out


def test_a_vars_override_recorded_in_the_page_fails(tmp_path, capsys):
    """dbt_rt.invocations publishes `vars_override`, so a secret passed through --vars would ship."""
    site = _site(tmp_path, invocations=[{"invocation_id": "01a0", "command": "compile", "vars_override": "{token: abc}"}])
    code, out = _run(site, _project(tmp_path, ""), capsys)
    assert code == 1
    assert "records a --vars override" in out


def test_a_unit_test_path_that_climbs_out_of_the_project_is_not_the_projects_yaml(tmp_path, capsys):
    """The exemption is for the repository's own YAML, so `../` to a file holding the same numbers does not earn it."""
    given = '[{"rows":[{"geom_wkt":"POINT (-74.987654 41.987654)"}]}]'
    (tmp_path / "elsewhere.yml").write_text("POINT (-74.987654 41.987654)", encoding="utf-8")
    site = _site(
        tmp_path,
        unit_tests=[
            {"unique_id": "unit_test.ourhike.x", "original_file_path": "../elsewhere.yml", "given": given, "expect": "{}"}
        ],
    )
    code, out = _run(site, _project(tmp_path, ""), capsys)
    assert code == 1
    assert "(../elsewhere.yml) is not under" in out


SINGULAR_TEST = "tests/singular/assert_a_made_up_area.sql"


def _with_data_tests(site: Path, rows: list[dict[str, str | None]]) -> Path:
    _parquet(site / "info_schema" / "v1" / "dbt.data_tests.parquet", rows)
    return site


def test_a_singular_tests_made_up_wkt_passes_when_every_number_is_in_its_own_sql_file(tmp_path, capsys):
    code_text = "select st_geomfromtext('POLYGON ((-97 38.007, -96.993004 38.007004, -97 38.007))')"
    project = _project(tmp_path, "")
    (project / SINGULAR_TEST).parent.mkdir(parents=True)
    (project / SINGULAR_TEST).write_text(code_text, encoding="utf-8")
    site = _with_data_tests(
        _site(tmp_path),
        [{"unique_id": "test.ourhike.assert_a_made_up_area", "original_file_path": SINGULAR_TEST, "raw_code": code_text}],
    )
    code, out = _run(site, project, capsys)
    assert code == 0, out


def test_a_generic_tests_code_holding_wkt_still_fails(tmp_path, capsys):
    """Only a hand-written file under tests/singular/ is traced; a test a model's YAML declares is not."""
    code_text = "select 'POINT (-74.987654 41.987654)'"
    site = _with_data_tests(
        _site(tmp_path),
        [{"unique_id": "test.ourhike.not_null_x", "original_file_path": UNIT_TEST_YAML, "raw_code": code_text}],
    )
    code, out = _run(site, _project(tmp_path, code_text), capsys)
    assert code == 1
    assert "raw_code of test.ourhike.not_null_x holds WKT" in out
    assert "41.987654" not in out


def test_a_singular_tests_number_its_own_file_does_not_hold_fails(tmp_path, capsys):
    project = _project(tmp_path, "")
    (project / SINGULAR_TEST).parent.mkdir(parents=True)
    (project / SINGULAR_TEST).write_text("select 1", encoding="utf-8")
    site = _with_data_tests(
        _site(tmp_path),
        [
            {
                "unique_id": "test.ourhike.assert_a_made_up_area",
                "original_file_path": SINGULAR_TEST,
                "raw_code": "select 'POINT (-74.987654 41.987654)'",
            }
        ],
    )
    code, out = _run(site, project, capsys)
    assert code == 1
    assert "with 2 number(s) not in tests/singular/assert_a_made_up_area.sql" in out


# --- --served: the copy a workflow publishes loads no code from another origin (decision 93) ---

SELF_HOSTED = INDEX.replace("https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.32.0", "/data/duckdb/duckdb.js?")


def _served(tmp_path: Path, *, index: str = SELF_HOSTED.replace("TELEMETRY", "false"), module: bool = True) -> Path:
    site = _site(tmp_path, index=index)
    if module:
        (site / "duckdb").mkdir()
        (site / "duckdb" / "duckdb.js").write_text("export const selectBundle = () => null", encoding="utf-8")
    return site


def _run_served(site: Path, project: Path, capsys) -> tuple[int, str]:
    code = cds.main([str(site), "--project", str(project), "--served"])
    return code, capsys.readouterr().out


def test_a_served_page_that_loads_duckdb_wasm_from_jsdelivr_fails(tmp_path, capsys):
    """dbt 2.0.6's default: the page imports DuckDB-WASM's code from cdn.jsdelivr.net, on ourhike.org's origin (SEC-1)."""
    code, out = _run_served(_site(tmp_path), _project(tmp_path, ""), capsys)
    assert code == 1
    assert "index.html: the page loads DuckDB-WASM from https://cdn.jsdelivr.net, another origin" in out


def test_the_same_page_passes_when_it_is_not_the_copy_a_workflow_serves(tmp_path, capsys):
    """The fixture build's docs (pipeline-tests.yml, scripts/test.sh) are never served, and keep dbt's default."""
    code, out = _run(_site(tmp_path), _project(tmp_path, ""), capsys)
    assert code == 0, out


def test_a_served_page_that_loads_duckdb_wasm_from_its_own_site_passes(tmp_path, capsys):
    code, out = _run_served(_served(tmp_path), _project(tmp_path, ""), capsys)
    assert code == 0, out


def test_a_served_page_whose_duckdb_module_is_not_in_the_site_fails(tmp_path, capsys):
    """On a preview the missing module would be answered with 404.html, the app shell, and the page would hold no data."""
    code, out = _run_served(_served(tmp_path, module=False), _project(tmp_path, ""), capsys)
    assert code == 1
    assert "loads DuckDB-WASM from /data/duckdb/duckdb.js, which is not in the site" in out


@pytest.mark.parametrize(
    "base",
    ["//cdn.example.org/duckdb", "https:/cdn.example.org/duckdb", "data:text/javascript,export%20{}", "/elsewhere/duckdb.js?"],
)
def test_a_served_page_whose_duckdb_base_is_not_a_path_under_data_fails(tmp_path, capsys, base):
    index = SELF_HOSTED.replace("/data/duckdb/duckdb.js?", base).replace("TELEMETRY", "false")
    code, out = _run_served(_served(tmp_path, index=index), _project(tmp_path, ""), capsys)
    assert code == 1
    assert "the page loads DuckDB-WASM from" in out


@pytest.mark.parametrize(
    ("tag", "origin"),
    [
        ('<script type="module" src="https://cdn.example.org/app.js"></script>', "https://cdn.example.org"),
        ('<script src="//cdn.example.org/app.js"></script>', "//cdn.example.org"),
        ('<link rel="modulepreload" crossorigin href="https://cdn.example.org/chunk.js">', "https://cdn.example.org"),
        ('<link rel="preload" as="worker" href="https://cdn.example.org/worker.js">', "https://cdn.example.org"),
    ],
)
def test_a_served_html_file_that_loads_a_script_from_another_origin_fails(tmp_path, capsys, tag, origin):
    site = _served(tmp_path)
    index = SELF_HOSTED.replace("TELEMETRY", "false").replace("</head>", tag + "</head>")
    (site / "index.html").write_text(index, encoding="utf-8")
    code, out = _run_served(site, _project(tmp_path, ""), capsys)
    assert code == 1
    assert f"index.html loads a script from {origin}, another origin" in out, out


@pytest.mark.parametrize(
    "code_text",
    [
        'importScripts("https://cdn.example.org/duckdb-browser-eh.worker.js")',
        'new Worker("https://cdn.example.org/w.mjs")',
        "WebAssembly.instantiateStreaming(fetch('https://extensions.example.org/v1.4.3/wasm_eh/parquet.duckdb_extension.wasm'))",
        "import(`https://esm.example.org/npm/pkg@1.0.0/+esm`)",
    ],
)
def test_served_code_that_names_a_script_worker_or_wasm_file_on_another_origin_fails(tmp_path, capsys, code_text):
    site = _served(tmp_path)
    (site / "assets" / "index.js").write_text(code_text, encoding="utf-8")
    code, out = _run_served(site, _project(tmp_path, ""), capsys)
    assert code == 1
    assert "assets/index.js names a script, worker or WASM file on" in out


def test_served_code_that_links_to_another_site_passes(tmp_path, capsys):
    """The docs bundle links to dbt's own pages (measured 2026-10-06: docs.getdbt.com, github.com, react.dev); a link is no code."""
    site = _served(tmp_path)
    (site / "assets" / "index.js").write_text(
        'const a = "https://docs.getdbt.com/docs/introduction", b = "https://github.com/dbt-labs/dbt-core";', encoding="utf-8"
    )
    code, out = _run_served(site, _project(tmp_path, ""), capsys)
    assert code == 0, out
