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


def _mart(name="podcasts", version=None, columns=None, enforced=True, deprecation_date=None):
    columns = columns or {"spotify_id": "varchar", "title": "varchar", "minutes": "bigint"}
    node_id = f"model.ourhike.{name}" + (f".v{version}" if version is not None else "")
    return node_id, {
        "resource_type": "model",
        "package_name": "ourhike",
        "name": name,
        "version": version,
        "latest_version": version,
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


def _manifest(*nodes, exposures=()):
    return {"nodes": dict(nodes), "exposures": dict(exposures)}


def _check(base, head, today=TODAY):
    report = ccv.Report()
    if base is not None:
        ccv.compare(base, head, ccv.datetime.fromisoformat(today).replace(tzinfo=ccv.timezone.utc), report)
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


def test_without_a_base_only_the_writers_rules_run(tmp_path, capsys):
    head = _write(tmp_path, "head.json", _manifest(_mart(version=1)))
    assert ccv.main(["--head", str(head)]) == 0
    assert "no base manifest, so only the writers' own rules ran" in capsys.readouterr().out


def test_a_manifest_that_is_not_there_exits_2(tmp_path):
    assert ccv.main(["--head", str(tmp_path / "absent.json")]) == 2


def test_a_manifest_that_is_not_json_exits_2(tmp_path):
    path = tmp_path / "head.json"
    path.write_text("not json")
    with pytest.raises(SystemExit) as raised:
        ccv.main(["--head", str(path)])
    assert raised.value.code == 2
