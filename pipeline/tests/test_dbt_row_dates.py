"""Every mart carries when each row was first seen and when it last changed, from a snapshot of its own.

Decision 57 (the maintainer, poll, 2026-10-03, amending decision 52): one
snapshot per mart, built in the intermediate layer, holding every contracted
column; the mart reads its current rows and their two dates from it. Only
marts carry `_first_seen_at` and `_changed_at`; intermediates are not asked
to. macros/row_history.sql has the shape:

    int_<mart>__final -> int_<mart>__history (snapshots/<mart>/) -> <mart>

This file holds it without a warehouse, by reading the SQL and the YAML;
tests/test_dbt_row_dates_builds.py drives dbt through builds and a restore.

- every mart file selects both dates: a mart through row_history_mart(), a
  later version (points_of_interest_v2, say) by naming them;
- every mart's contract is enforced and declares both `timestamptz`, each
  with a not_null test that warns rather than fails only when
  OURHIKE_ROW_HISTORY is off (a conditions leg built without its history,
  build_marts.py's --history-on-failure degrade);
- every mart reads int_<mart>__history and int_<mart>__final under its own
  key, the snapshot's body is row_history_snapshot('int_<mart>__final')
  under that key (with a `skip=[...]` list, for a column that changes on
  every run while the row does not), and the final model exists in the
  mart's intermediate folder;
- no snapshot exists but these.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

DBT = Path(__file__).resolve().parent.parent / "dbt"
MODELS = DBT / "models"
MARTS = MODELS / "marts"
SNAPSHOTS = DBT / "snapshots"
DATES = ("_first_seen_at", "_changed_at")
MART_CALL = re.compile(r"row_history_mart\(\s*'int_(\w+)__history',\s*'int_(\w+)__final',\s*(\[[^\]]*\]|'\w+')\s*\)", re.S)
SNAPSHOT_BODY = re.compile(
    r"\{%\s*snapshot\s+(\w+)\s*%\}.*?config\(\s*unique_key=(\[[^\]]*\]|'\w+')\s*\).*?"
    r"row_history_snapshot\(\s*'(\w+)'\s*(?:,\s*skip=\[[^\]]*\]\s*)?\).*?\{%\s*endsnapshot\s*%\}",
    re.S,
)
#: What the not_null tests on the two dates must say, so a degraded conditions leg's null dates warn.
SEVERITY = "{{ 'warn' if env_var('OURHIKE_ROW_HISTORY', 'on') == 'off' else 'error' }}"


def _keys(text: str) -> list[str]:
    return re.findall(r"'(\w+)'", text)


def _without_comments(sql: str) -> str:
    sql = re.sub(r"\{#.*?#\}", "", sql, flags=re.S)
    return re.sub(r"--[^\n]*", "", sql)


def _mart_models() -> dict[str, dict]:
    found = {}
    for path in sorted(MARTS.rglob("_*.yml")):
        for model in (yaml.safe_load(path.read_text()) or {}).get("models") or []:
            found[model["name"]] = model
    return found


def _defined_in(model: dict, version: dict) -> str:
    """The SQL file a model version is built from: its `defined_in`, else dbt's default, <model>_v<v>."""
    return version.get("defined_in") or f"{model['name']}_v{version['v']}"


def _columns(entry: dict) -> dict[str, dict]:
    return {column["name"]: column for column in entry.get("columns") or [] if isinstance(column, dict) and "name" in column}


def _version_columns(model: dict, defined_in: str) -> dict[str, dict]:
    """The columns of the version a mart file defines: the model's, less a version's `exclude`, plus its own."""
    columns = _columns(model)
    for version in model.get("versions") or []:
        if _defined_in(model, version) != defined_in:
            continue
        listed = version.get("columns")
        if listed is None:
            return columns
        chosen = {}
        for column in listed:
            if isinstance(column, dict) and "include" in column:
                include = column["include"]
                names = set(columns) if include in ("all", "*") else set(include)
                names -= set(column.get("exclude") or [])
                chosen.update({name: columns[name] for name in names if name in columns})
            elif isinstance(column, dict) and "name" in column:
                chosen[column["name"]] = {**columns.get(column["name"], {}), **column}
        return chosen
    return columns


def _mart_entry(name: str, models: dict[str, dict]) -> tuple[dict, dict[str, dict]] | None:
    for model in models.values():
        if name == model["name"] or name in [_defined_in(model, version) for version in model.get("versions") or []]:
            return model, _version_columns(model, name)
    return None


def _not_null_test(column: dict) -> dict | str | None:
    for test in column.get("data_tests") or []:
        if test == "not_null" or (isinstance(test, dict) and "not_null" in test):
            return test
    return None


def problems(path: Path, models: dict[str, dict]) -> list[str]:
    """Why the mart file at `path` does not carry the row dates; [] when it does."""
    sql = _without_comments(path.read_text())
    found = []
    if not (MART_CALL.search(sql) or all(column in sql for column in DATES)):
        found.append("its SQL neither calls row_history_mart() nor selects both dates")
    entry = _mart_entry(path.stem, models)
    if entry is None:
        return [*found, "no YAML entry"]
    model, columns = entry
    if not ((model.get("config") or {}).get("contract") or {}).get("enforced"):
        found.append("its contract is not enforced")
    for column in DATES:
        if column not in columns:
            found.append(f"its contract does not declare {column}")
            continue
        if str(columns[column].get("data_type", "")).lower() not in ("timestamptz", "timestamp with time zone"):
            found.append(f"{column} is not declared timestamptz")
        test = _not_null_test(columns[column])
        if test is None:
            found.append(f"{column} has no not_null test")
        elif not isinstance(test, dict) or ((test["not_null"] or {}).get("config") or {}).get("severity") != SEVERITY:
            found.append(f"{column}'s not_null test does not warn, rather than fail, only with OURHIKE_ROW_HISTORY off")
    return found


MART_FILES = sorted(MARTS.rglob("*.sql"))
MODELS_YAML = _mart_models()


def _snapshots() -> dict[str, tuple[list[str], str]]:
    """{snapshot: (unique_key, the model its body reads)} for every snapshot file."""
    found = {}
    for path in sorted(SNAPSHOTS.rglob("*.sql")):
        match = SNAPSHOT_BODY.search(path.read_text())
        assert match, f"{path.relative_to(DBT)} is not one row_history_snapshot() block"
        name, key, final = match.groups()
        assert name == path.stem, f"{path.relative_to(DBT)} defines {name}"
        found[name] = (_keys(key), final)
    return found


def test_there_are_marts_to_check():
    assert len(MART_FILES) >= 14


@pytest.mark.parametrize("path", MART_FILES, ids=[path.stem for path in MART_FILES])
def test_each_mart_carries_both_row_dates_in_its_contract(path):
    assert problems(path, MODELS_YAML) == [], f"{path.stem} must carry _first_seen_at and _changed_at (decision 57)"


@pytest.mark.parametrize("path", MART_FILES, ids=[path.stem for path in MART_FILES])
def test_each_mart_reads_its_own_snapshot_of_its_own_final_model_under_one_key(path):
    match = MART_CALL.search(_without_comments(path.read_text()))
    if match is None:
        assert re.search(r"ref\('\w+', v=\d+\)", path.read_text()), f"{path.stem} is neither a mart nor a later version"
        pytest.skip(f"{path.stem} is a later version of a mart, and carries that mart's dates")
    history, final, key = match.groups()
    mart = path.parent.name
    assert history == final == mart, f"{path.stem} reads int_{history}__history and int_{final}__final"
    snapshots = _snapshots()
    assert f"int_{mart}__history" in snapshots, f"no snapshots/{mart}/int_{mart}__history.sql"
    snapshot_key, reads = snapshots[f"int_{mart}__history"]
    assert reads == f"int_{mart}__final" and snapshot_key == _keys(key), f"int_{mart}__history keys on {snapshot_key}"
    assert (MODELS / "intermediate" / mart / f"int_{mart}__final.sql").exists()


def test_every_snapshot_is_a_marts_row_history():
    marts = {match.group(1) for path in MART_FILES if (match := MART_CALL.search(_without_comments(path.read_text())))}
    assert set(_snapshots()) == {f"int_{mart}__history" for mart in marts}


def test_the_check_refuses_a_mart_without_the_dates_or_with_a_test_that_would_fail_a_degraded_leg(tmp_path):
    """The check run against marts it must refuse and pass, so a loosened rule cannot pass everything."""
    mart = tmp_path / "trail_things.sql"
    mart.write_text("{{ row_history_mart('int_trail_things__history', 'int_trail_things__final', 'thing_id') }}\n")
    good_test = {"not_null": {"config": {"severity": SEVERITY}}}
    good = {"name": "trail_things", "config": {"contract": {"enforced": True}}}
    good["columns"] = [{"name": name, "data_type": "timestamptz", "data_tests": [good_test]} for name in DATES]
    strict = {**good, "columns": [{"name": name, "data_type": "timestamptz", "data_tests": ["not_null"]} for name in DATES]}
    bare = tmp_path / "trail_bare.sql"
    bare.write_text("select a from {{ ref('int_x__y') }} -- _first_seen_at _changed_at\n")

    assert problems(mart, {"trail_things": good}) == []
    assert len(problems(mart, {"trail_things": strict})) == 2
    assert problems(bare, {"trail_bare": {**good, "name": "trail_bare"}}) == [
        "its SQL neither calls row_history_mart() nor selects both dates"
    ]


def test_a_versions_columns_follow_its_include_and_exclude():
    model = {
        "name": "things",
        "columns": [{"name": "a"}, {"name": "b"}, *({"name": column} for column in DATES)],
        "versions": [{"v": 1, "defined_in": "things"}, {"v": 2, "columns": [{"include": "all", "exclude": ["a"]}]}],
    }

    assert set(_version_columns(model, "things")) == {"a", "b", *DATES}
    assert set(_version_columns(model, "things_v2")) == {"b", *DATES}


def test_the_hook_for_removed_features_is_there_for_the_later_decision():
    """Decision 57 leaves how removed features merge back to a later decision; row_history_removed() is where."""
    assert "macro row_history_removed(history_name, key)" in (DBT / "macros" / "row_history.sql").read_text()
