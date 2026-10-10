"""check_contract_versions.py: the refusal dbt 2.0.6 does not make (decision 44).

The manifests here are written in the shape dbt 2.0.6 gives a versioned model,
read off a scratch copy of this project on 2026-10-02 with the podcasts mart
at `versions: [{v: 1}, {v: 2}]`: one node per version
(`model.ourhike.podcasts.v1`, `.v2`), `version` an integer, `deprecation_date`
an ISO datetime such as `2027-01-01T00:00:00+00:00`, and each column's
`data_type` and `constraints` under `columns`.
"""

from __future__ import annotations

import copy
import json

import pytest

import check_contract_versions as ccv

TODAY = "2026-10-02"


def _mart(name="podcasts", version=None, columns=None, enforced=True, deprecation_date=None, latest=None):
    columns = columns or {"spotify_id": "varchar", "title": "varchar", "minutes": "bigint"}
    node_id = f"model.ourhike.{name}" + (f".v{version}" if version is not None else "")
    return node_id, {
        "resource_type": "model",
        "package_name": "ourhike",
        "name": name,
        "version": version,
        "latest_version": latest if latest is not None else version,
        "deprecation_date": deprecation_date,
        "config": {"materialized": "table", "contract": {"enforced": enforced}},
        "columns": {
            column: {
                "name": column,
                "data_type": data_type,
                "constraints": [{"type": "not_null"}] if column == "spotify_id" else [],
            }
            for column, data_type in columns.items()
        },
        "refs": [],
        "depends_on": {"nodes": []},
    }


def _writer(name="pub_podcasts_episodes", reads=(("podcasts", 1),), pinned=True):
    """A phone_file writer and the refs it compiles from. `reads` is
    (model, version) pairs; version None for an unversioned model."""
    node_id = f"model.ourhike.{name}"
    return node_id, {
        "resource_type": "model",
        "package_name": "ourhike",
        "name": name,
        "version": None,
        "config": {"materialized": "phone_file", "contract": {"enforced": True}, "location": f"{name}.json"},
        "columns": {"episodes": {"name": "episodes", "data_type": "json[]", "constraints": []}},
        "refs": [
            {"name": model, "package": None, "version": (version if pinned else None) if version is not None else None}
            for model, version in reads
        ],
        "depends_on": {
            "nodes": [f"model.ourhike.{model}" + (f".v{version}" if version is not None else "") for model, version in reads]
        },
    }


def _exposure(writer_id, keys, name="podcasts_episodes_json"):
    return f"exposure.ourhike.{name}", {
        "config": {"meta": {"r2_keys": list(keys)}},
        "depends_on": {"nodes": [writer_id]},
    }


def _reader(name="int_podcasts__latest", resource_type="model", reads=(("podcasts", 1),), pinned=True):
    """A node that is not a writer and reads `reads` as _writer's do: an intermediate table, or a data test."""
    node_id = f"{resource_type}.ourhike.{name}"
    return node_id, {
        "resource_type": resource_type,
        "package_name": "ourhike",
        "name": name,
        "version": None,
        "config": {"materialized": "table" if resource_type == "model" else "test"},
        "refs": [
            {"name": model, "package": None, "version": (version if pinned else None) if version is not None else None}
            for model, version in reads
        ],
        "depends_on": {
            "nodes": [f"model.ourhike.{model}" + (f".v{version}" if version is not None else "") for model, version in reads]
        },
    }


def _unit_test(*inputs, model="int_podcasts__latest", name="int_podcasts__latest_keeps_one_row"):
    """A unit test as dbt 2.0.6 keeps it: each given's `input` is the text of its call, and `refs` names only the model
    under test (read off this project's manifest, 2026-10-09)."""
    return f"unit_test.ourhike.{model}.{name}", {
        "resource_type": "unit_test",
        "package_name": "ourhike",
        "name": name,
        "model": model,
        "refs": [{"name": model, "package": "ourhike", "version": None}],
        "given": [{"input": text, "rows": []} for text in inputs],
    }


def _manifest(*nodes, exposures=(), unit_tests=()):
    return {"nodes": dict(nodes), "exposures": dict(exposures), "unit_tests": dict(unit_tests)}


def _check(base, head, today=TODAY):
    report = ccv.Report()
    if base is not None:
        ccv.compare(base, head, ccv.datetime.fromisoformat(today).replace(tzinfo=ccv.timezone.utc), report)
    ccv.check_pins(head, report)
    ccv.check_writers(head, report)
    return report


# --- types ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("one", "other"),
    [
        ("varchar", "TEXT"),
        ("varchar", "varchar(255)"),
        ("integer", "INT"),
        ("bigint", "int8"),
        ("double", "FLOAT8"),
        ("boolean", "bool"),
        ("timestamptz", "TIMESTAMP WITH TIME ZONE"),
        ("map(varchar, varchar)", "MAP(VARCHAR,VARCHAR)"),
        ("double[][]", "DOUBLE [] []"),
        ("varchar[]", "text[]"),
    ],
)
def test_one_duckdb_type_spelled_two_ways_is_the_same_type(one, other):
    assert ccv.normalize_type(one) == ccv.normalize_type(other)


@pytest.mark.parametrize(("one", "other"), [("varchar", "json"), ("bigint", "integer"), ("double", "real"), ("json[]", "json")])
def test_different_types_stay_different(one, other):
    assert ccv.normalize_type(one) != ccv.normalize_type(other)


def test_a_struct_field_named_like_a_type_is_not_respelled():
    assert ccv.normalize_type("struct(text varchar)") == "struct(text varchar)"


# --- against the base ---------------------------------------------------------


def test_an_unchanged_contract_passes():
    manifest = _manifest(_mart(version=1))
    report = _check(manifest, copy.deepcopy(manifest))
    assert report.failures == []
    assert report.compared == 1


def test_a_removed_column_fails():
    base = _manifest(_mart(version=1))
    head = _manifest(_mart(version=1, columns={"spotify_id": "varchar", "minutes": "bigint"}))
    assert _check(base, head).failures == [
        "ourhike.podcasts v1: column `title` is removed (or renamed); ship the change as a new version"
    ]


def test_a_changed_type_fails():
    base = _manifest(_mart(version=1))
    head = _manifest(_mart(version=1, columns={"spotify_id": "varchar", "title": "varchar", "minutes": "double"}))
    (failure,) = _check(base, head).failures
    assert "column `minutes` changed type, bigint -> double" in failure


def test_a_respelled_type_passes():
    base = _manifest(_mart(version=1))
    head = _manifest(_mart(version=1, columns={"spotify_id": "TEXT", "title": "varchar", "minutes": "INT8"}))
    assert _check(base, head).failures == []


def test_an_added_column_passes():
    """A phone ignores a field it does not know, so this is not a new version."""
    base = _manifest(_mart(version=1))
    head = _manifest(
        _mart(version=1, columns={"spotify_id": "varchar", "title": "varchar", "minutes": "bigint", "show": "varchar"})
    )
    assert _check(base, head).failures == []


def test_a_change_shipped_as_a_new_version_passes():
    base = _manifest(_mart(version=1))
    head = _manifest(_mart(version=1), _mart(version=2, columns={"spotify_id": "varchar", "minutes": "bigint"}))
    report = _check(base, head)
    assert report.failures == []
    assert report.new == 1


def test_a_change_made_to_v1_beside_a_new_v2_still_fails():
    base = _manifest(_mart(version=1))
    head = _manifest(
        _mart(version=1, columns={"spotify_id": "varchar", "minutes": "bigint"}),
        _mart(version=2, columns={"spotify_id": "varchar", "minutes": "bigint"}),
    )
    (failure,) = _check(base, head).failures
    assert failure.startswith("ourhike.podcasts v1: column `title` is removed")


def test_a_version_dropped_with_no_deprecation_date_fails():
    base = _manifest(_mart(version=1), _mart(version=2))
    head = _manifest(_mart(version=2))
    assert _check(base, head).failures == ["ourhike.podcasts v1: the version is gone, and the base gave it no deprecation_date"]


def test_a_version_dropped_before_its_deprecation_date_fails():
    base = _manifest(_mart(version=1, deprecation_date="2027-01-01T00:00:00+00:00"), _mart(version=2))
    head = _manifest(_mart(version=2))
    assert _check(base, head, today="2026-12-31").failures == [
        "ourhike.podcasts v1: the version is gone before its deprecation_date, 2027-01-01"
    ]


def test_a_version_dropped_once_its_deprecation_date_has_passed_passes():
    base = _manifest(_mart(version=1, deprecation_date="2027-01-01T00:00:00+00:00"), _mart(version=2))
    head = _manifest(_mart(version=2))
    assert _check(base, head, today="2027-01-01").failures == []


def test_an_unversioned_mart_that_gains_versions_is_compared_through_its_v1():
    base = _manifest(_mart(version=None))
    assert _check(base, _manifest(_mart(version=1))).failures == []
    head = _manifest(_mart(version=1, columns={"spotify_id": "varchar", "minutes": "bigint"}))
    (failure,) = _check(base, head).failures
    assert "column `title` is removed" in failure


def test_an_unversioned_mart_deleted_outright_fails():
    base = _manifest(_mart(version=None))
    assert _check(base, _manifest()).failures == [
        "ourhike.podcasts: the version is gone, and the base gave it no deprecation_date"
    ]


def test_a_contract_switched_off_fails():
    base = _manifest(_mart(version=1))
    head = _manifest(_mart(version=1, enforced=False))
    assert _check(base, head).failures == ["ourhike.podcasts v1: its contract is no longer enforced"]


def test_a_lost_not_null_is_a_warning_and_not_a_failure():
    base = _manifest(_mart(version=1))
    head = copy.deepcopy(base)
    head["nodes"]["model.ourhike.podcasts.v1"]["columns"]["spotify_id"]["constraints"] = []
    report = _check(base, head)
    assert report.failures == []
    assert report.warnings == [
        "ourhike.podcasts v1: column `spotify_id` lost its not_null constraint (dbt Core counts that as breaking)"
    ]


def test_a_model_with_no_contract_in_the_base_is_not_compared():
    base = _manifest(_mart(name="int_podcasts__checked", version=None, enforced=False))
    report = _check(base, _manifest())
    assert report.failures == []
    assert report.compared == 0


def test_a_writers_own_contract_is_a_phone_file_shape_and_is_compared():
    """A removed column in a pub_ writer is a field gone from the file itself."""
    writer_id, writer = _writer(reads=(("podcasts", None),))
    base = _manifest((writer_id, writer), _mart(version=None))
    shrunk = copy.deepcopy(writer)
    shrunk["columns"] = {}
    head = _manifest((writer_id, shrunk), _mart(version=None))
    (failure,) = _check(base, head).failures
    assert failure.startswith("ourhike.pub_podcasts_episodes: column `episodes` is removed")


# --- the writers, in the head alone -------------------------------------------


def test_a_pinned_v1_writer_on_todays_keys_passes():
    writer_id, writer = _writer()
    head = _manifest(_mart(version=1), (writer_id, writer), exposures=[_exposure(writer_id, ["podcasts/episodes.json"])])
    assert _check(None, head).failures == []


def test_a_writer_reading_a_versioned_mart_without_pinning_it_fails():
    writer_id, writer = _writer(pinned=False)
    head = _manifest(_mart(version=1), (writer_id, writer), exposures=[_exposure(writer_id, ["podcasts/episodes.json"])])
    (failure,) = _check(None, head).failures
    assert "reads `podcasts` without a version; pin it, ref('podcasts', v=1)" in failure


def test_a_writer_reading_an_unversioned_mart_needs_no_pin():
    """Every family not yet versioned (decision 44 versions the marts that feed
    a phone file as each one lands)."""
    writer_id, writer = _writer(reads=(("trail_lines", None),))
    head = _manifest(_mart(name="trail_lines"), (writer_id, writer), exposures=[_exposure(writer_id, ["nearby_trails.geojson"])])
    assert _check(None, head).failures == []


# --- rule 5 beyond the writers ------------------------------------------------


def test_an_intermediate_reading_a_versioned_mart_without_pinning_it_fails():
    """The review of PR #1805 (dlt → dbt re-platform as one go/no-go change), 2026-10-09: seven intermediates read
    points_of_interest or trail_lines unpinned, and rule 5 looked only at the writers. int_trail_lines__spur_destinations
    alone feeds trail_lines v1, and through it three writers, each of which pins."""
    reader_id, reader = _reader(pinned=False)
    (failure,) = _check(None, _manifest(_mart(version=1), (reader_id, reader))).failures
    assert failure.startswith("model.ourhike.int_podcasts__latest: reads `podcasts` without a version")
    assert "pin it, ref('podcasts', v=1)" in failure


def test_a_pinned_intermediate_passes():
    reader_id, reader = _reader()
    assert _check(None, _manifest(_mart(version=1), (reader_id, reader))).failures == []


def test_a_data_test_reading_a_versioned_mart_without_pinning_it_fails():
    """A test that moved to v2 at a bump would test a file nobody publishes yet, and pass or fail on its columns."""
    test_id, data_test = _reader(name="assert_every_episode_may_publish", resource_type="test", pinned=False)
    (failure,) = _check(None, _manifest(_mart(version=1), (test_id, data_test))).failures
    assert failure.startswith("test.ourhike.assert_every_episode_may_publish: reads `podcasts` without a version")


def test_a_node_reading_an_unversioned_model_needs_no_pin():
    reader_id, reader = _reader(reads=(("trail_lines", None),))
    assert _check(None, _manifest(_mart(name="trail_lines"), (reader_id, reader))).failures == []


def test_a_unit_test_given_without_a_version_fails():
    """A given must name the relation its model reads; unpinned, it follows the latest version away from a model
    that pins (pub_trail_graph_profile read elevation v1 under a given of plain ref('elevation'), 2026-10-09)."""
    unit_id, unit_test = _unit_test("ref('podcasts')", "ref('int_sources__publication')")
    (failure,) = _check(None, _manifest(_mart(version=1), unit_tests=[(unit_id, unit_test)])).failures
    assert failure.startswith(f"{unit_id}'s given: reads `podcasts` without a version; pin it, ref('podcasts', v=1)")


@pytest.mark.parametrize(
    "given",
    ["ref('podcasts', v=1)", 'ref("podcasts", version=1)', "ref('ourhike', 'podcasts', v=1)", "source('raw', 'podcasts')"],
)
def test_a_pinned_given_or_a_source_given_passes(given):
    unit_id, unit_test = _unit_test(given)
    assert _check(None, _manifest(_mart(version=1), unit_tests=[(unit_id, unit_test)])).failures == []


def test_a_given_naming_its_package_is_still_read_for_its_model():
    unit_id, unit_test = _unit_test("ref('ourhike', 'podcasts')")
    (failure,) = _check(None, _manifest(_mart(version=1), unit_tests=[(unit_id, unit_test)])).failures
    assert "reads `podcasts` without a version" in failure


def test_the_pin_asked_for_is_the_version_an_unpinned_ref_reads_today():
    """Pinning the latest version changes nothing a build reads today; only the next bump stops moving it."""
    reader_id, reader = _reader(reads=(("podcasts", 2),), pinned=False)
    head = _manifest(_mart(version=1, latest=2), _mart(version=2, latest=2), (reader_id, reader))
    (failure,) = _check(None, head).failures
    assert "pin it, ref('podcasts', v=2)" in failure


def test_a_declared_latest_version_wins_over_the_highest_one():
    """A prerelease v2 beside `latest_version: 1` leaves unpinned refs on v1, so the pin asked for is v1."""
    reader_id, reader = _reader(pinned=False)
    v1_id, v1 = _mart(version=1, latest=1)
    v2_id, v2 = _mart(version=2)
    v2["latest_version"] = None
    for order in ([(v2_id, v2), (v1_id, v1)], [(v1_id, v1), (v2_id, v2)]):
        (failure,) = _check(None, _manifest(*order, (reader_id, reader))).failures
        assert "pin it, ref('podcasts', v=1)" in failure


@pytest.mark.parametrize("key", ["v2/stewards.json", "conditions/v2/closures.json", "podcasts/v2/episodes.json"])
def test_a_v2_writer_names_v2_where_elt_md_puts_it(key):
    writer_id, writer = _writer(reads=(("podcasts", 2),))
    head = _manifest(_mart(version=1), _mart(version=2), (writer_id, writer), exposures=[_exposure(writer_id, [key])])
    assert _check(None, head).failures == []


def test_a_v2_writer_publishing_to_v1s_key_fails():
    writer_id, writer = _writer(reads=(("podcasts", 2),))
    head = _manifest(_mart(version=2), (writer_id, writer), exposures=[_exposure(writer_id, ["podcasts/episodes.json"])])
    (failure,) = _check(None, head).failures
    assert "podcasts/episodes.json names no version, and model.ourhike.pub_podcasts_episodes writes v2" in failure


def test_a_v1_writer_on_a_versioned_key_fails():
    """v1 is today's keys exactly: a `v1/` segment would be a new key no
    installed app reads (pipeline/R2_LAYOUT.md: a published key is permanent)."""
    writer_id, writer = _writer()
    head = _manifest(_mart(version=1), (writer_id, writer), exposures=[_exposure(writer_id, ["v1/stewards.json"])])
    (failure,) = _check(None, head).failures
    assert "v1/stewards.json names v1" in failure
    assert "whose keys carry no version segment" in failure


def test_a_writer_reading_two_versions_fails():
    writer_id, writer = _writer(reads=(("podcasts", 1), ("podcasts", 2)))
    head = _manifest(_mart(version=1), _mart(version=2), (writer_id, writer))
    (failure,) = _check(None, head).failures
    assert "reads versions 1, 2 at once" in failure


# --- which writer writes which key ----------------------------------------------


def _poi_writers(*locations):
    return {
        f"model.ourhike.pub_{location.split('.')[0]}": {"config": {"materialized": "phone_file", "location": location}}
        for location in locations
    }


def _shared(nodes, keys):
    return {"config": {"meta": {"r2_keys": keys}}, "depends_on": {"nodes": ["model.ourhike.points_of_interest", *nodes]}}


def test_one_writer_writes_every_key_its_exposure_names():
    writer_id, writer = _writer()
    exposure = _exposure(writer_id, ["podcasts/episodes.json"])[1]
    assert ccv.keys_by_writer(exposure, {writer_id: writer}) == {writer_id: ["podcasts/episodes.json"]}


def test_writers_sharing_an_exposure_each_write_the_key_named_for_their_file():
    """poi_by_type_geojson: eight writers, eight keys, one exposure."""
    nodes = _poi_writers("poi_shelter.geojson", "poi_water.geojson")
    paired = ccv.keys_by_writer(_shared(nodes, ["poi_water.geojson", "v2/poi_shelter.geojson"]), nodes)
    assert paired == {
        "model.ourhike.pub_poi_shelter": ["v2/poi_shelter.geojson"],
        "model.ourhike.pub_poi_water": ["poi_water.geojson"],
    }


@pytest.mark.parametrize(
    ("keys", "message"),
    [
        (["poi_shelter.geojson", "poi_water.geojson", "poi_privy.geojson"], "poi_privy.geojson is not the file of any"),
        (["poi_shelter.geojson"], "write no key their exposure names"),
    ],
)
def test_a_shared_exposure_that_does_not_pair_up_is_refused(keys, message):
    nodes = _poi_writers("poi_shelter.geojson", "poi_water.geojson")
    with pytest.raises(ValueError, match=message):
        ccv.keys_by_writer(_shared(nodes, keys), nodes)


def test_an_exposure_with_no_writer_names_no_writer_keys():
    exposure = {
        "config": {"meta": {"r2_keys": ["conditions/weather_alerts.json"]}},
        "depends_on": {"nodes": ["model.ourhike.warnings"]},
    }
    assert ccv.keys_by_writer(exposure, {}) == {}


def test_an_exposure_that_does_not_pair_up_fails_the_check():
    nodes = _poi_writers("poi_shelter.geojson", "poi_water.geojson")
    head = {"nodes": nodes, "exposures": {"exposure.ourhike.poi_by_type_geojson": _shared(nodes, ["poi_shelter.geojson"])}}
    (failure,) = _check(None, head).failures
    assert failure.startswith("exposure.ourhike.poi_by_type_geojson: ")


# --- where a version lives in a key -------------------------------------------


@pytest.mark.parametrize(
    ("v1_key", "v2_key"),
    [
        ("stewards.json", "v2/stewards.json"),
        ("nearby_trails.geojson", "v2/nearby_trails.geojson"),
        ("conditions/closures.json", "conditions/v2/closures.json"),
        ("podcasts/episodes.json", "podcasts/v2/episodes.json"),
    ],
)
def test_version_in_key_reads_2_from_the_v2_segment_and_none_from_the_v1_key(v1_key, v2_key):
    assert ccv.version_in_key(v1_key) is None
    assert ccv.version_in_key(v2_key) == 2


@pytest.mark.parametrize("key", ["v2.json", "trail_graph_cell_v2.json", "conditions/v2.json", "photos/v2/abc.jpg"])
def test_a_v_in_a_file_name_is_not_a_version(key):
    assert ccv.version_in_key(key) is None


# --- the command line ---------------------------------------------------------


def _write(tmp_path, name, manifest):
    path = tmp_path / name
    path.write_text(json.dumps(manifest))
    return path


def test_the_command_exits_0_when_nothing_breaks(tmp_path, capsys):
    manifest = _manifest(_mart(version=1))
    code = ccv.main(
        ["--head", str(_write(tmp_path, "head.json", manifest)), "--base", str(_write(tmp_path, "base.json", manifest))]
    )
    assert code == 0
    assert "1 contracted model version(s) compared with the base, 0 new; 0 failure(s)" in capsys.readouterr().out


def test_the_command_exits_1_and_names_each_failure(tmp_path, capsys):
    base = _write(tmp_path, "base.json", _manifest(_mart(version=1)))
    head = _write(tmp_path, "head.json", _manifest(_mart(version=1, columns={"spotify_id": "varchar"})))
    assert ccv.main(["--head", str(head), "--base", str(base), "--today", TODAY]) == 1
    out = capsys.readouterr().out
    assert out.count("FAIL ") == 2


def test_without_a_base_only_the_heads_own_rules_run(tmp_path, capsys):
    head = _write(tmp_path, "head.json", _manifest(_mart(version=1)))
    assert ccv.main(["--head", str(head)]) == 0
    assert "no base manifest, so only the head's own rules (5-7) ran" in capsys.readouterr().out


def test_without_a_base_an_unpinned_intermediate_still_fails_the_command(tmp_path, capsys):
    """Rule 5 needs no base: CI's step runs the head alone when the base predates this script."""
    reader_id, reader = _reader(pinned=False)
    head = _write(tmp_path, "head.json", _manifest(_mart(version=1), (reader_id, reader)))
    assert ccv.main(["--head", str(head)]) == 1
    assert "model.ourhike.int_podcasts__latest: reads `podcasts` without a version" in capsys.readouterr().out


def test_a_manifest_that_is_not_there_exits_2(tmp_path):
    assert ccv.main(["--head", str(tmp_path / "absent.json")]) == 2


def test_a_manifest_that_is_not_json_exits_2(tmp_path):
    path = tmp_path / "head.json"
    path.write_text("not json")
    with pytest.raises(SystemExit) as raised:
        ccv.main(["--head", str(path)])
    assert raised.value.code == 2
