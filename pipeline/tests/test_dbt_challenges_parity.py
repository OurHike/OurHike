"""The int_challenges__ models find what export_challenges.py and lib/challenges.py find, on the same rows (#1793, stage 3).

The challenges family moved to SQL (pipeline/ELT.md's ledger rows CH01-CH13),
and until stage 5 deletes the Python both are live: export_challenges.py
still uploads, and parity.py compares the dbt writer's challenges.json with
its output. Two copies of one rule drift unless something holds them
together, and this is that something, in three parts:

- the vars the models read are lib/challenges.py's and export_challenges.py's
  constants, and every unit test that overrides vars overrides them with
  dbt_project.yml's own, the build date aside (dbt 2.0.6 gives a unit test's
  model only the vars its `overrides` names, so each names them all);
- today's Python, run over each unit test's own given rows, answers every row
  the unit test expects, except the rows DELIBERATE lists, where the SQL
  answers otherwise on purpose;
- each DELIBERATE row still differs, so a reason cannot outlive its case, and
  emptying DELIBERATE turns this file red.

dbt runs the other half: the unit tests in
models/intermediate/challenges/_challenges__unit_tests.yml hold the SQL to
those expectations.

THE STATED DIFFERENCES NO ROW EXERCISES, in macros/challenges/python_repr.sql:
a refusal message prints an object, or a list inside a list, as its JSON
text where Python prints its repr, and prints a non-printable character
other than tab, newline and carriage return raw where Python escapes it. No
reviewed file puts such a value where a message quotes it, and only the
message, never a published field, would change.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path

import duckdb
import pytest
import yaml

import export_challenges
import parity
from lib import challenges
from lib.poi_schema import POI_TYPES

DBT = Path(__file__).parent.parent / "dbt"
UNIT_TESTS = DBT / "models" / "intermediate" / "challenges" / "_challenges__unit_tests.yml"

PUBLISHERS = "int_challenges__publishers_follow_publisher_scope"
ITEMS = "int_challenges__items_resolve_as_resolve_item_resolves"
LIB = "test_lib_challenges"

#: (unit test, row key) -> why the SQL's answer is not the Python's. Each is an
#: improvement, class (b) in pipeline/ELT.md's parity terms.
DELIBERATE = {
    (PUBLISHERS, "13"): (
        "a publishers.json row whose org is a list: publisher_scope() refuses it, and then publisher_domains() "
        "raises TypeError (export_challenges.py's `org not in scope` on an unhashable list), so main() stops and "
        "nothing publishes; the SQL refuses the row with publisher_scope()'s words and carries on"
    ),
    (ITEMS, f"{LIB}::TestItems::test_an_item_id_with_a_trailing_newline_is_refused_here:1"): (
        "an item id with a trailing newline: _id_ok()'s re.match `$` matches before it, so the Python publishes "
        "the id, newline and all, as the key every tag of it is stored under; challenges_id_ok() refuses it"
    ),
    (ITEMS, "ch04::a_place_beside_a_sparse_stretch_is_measured_to_the_line:1"): (
        "CH04: a place 100 m from the line and 224 m from its nearest vertex, beside a 0.006-degree gap between "
        "vertices. trail_distance_index() measures to the nearest vertex and refuses it at 150 m; the SQL "
        "measures to the line as well and admits it"
    ),
    (ITEMS, f"{LIB}::TestTrailDistanceIndex::test_a_point_more_than_a_cell_from_every_vertex_is_infinitely_far:1"): (
        "CH04: a place a degree from every vertex. Both refuse it; trail_distance_index() reads it as infinitely "
        "far, past its 3x3 grid search, so the Python's message prints 'inf m', where the SQL prints its distance "
        "to the line"
    ),
}


def _unit_tests() -> dict[str, dict]:
    return {test["name"]: test for test in yaml.safe_load(UNIT_TESTS.read_text(encoding="utf-8"))["unit_tests"]}


def _given(test: dict, name: str) -> list[dict]:
    return next(given["rows"] for given in test["given"] if given["input"] == f"ref('{name}')")


def _project_vars() -> dict:
    project = yaml.safe_load((DBT / "dbt_project.yml").read_text(encoding="utf-8"))
    return {name: value for name, value in project["vars"].items() if name.startswith("challenges_")}


def _parsed(row: dict) -> dict:
    """A row with its JSON text columns read, so two rows compare as values rather than as spellings."""
    return {name: json.loads(value) if name in JSON_COLUMNS and value is not None else value for name, value in row.items()}


JSON_COLUMNS = {"published_item", "place_distances", "sections_published"}


# --- the vars ---------------------------------------------------------------------------------


def test_the_vars_are_the_pythons_constants():
    variables = _project_vars()
    assert tuple(variables["challenges_match_kinds"]) == challenges.MATCH_KINDS
    assert tuple(variables["challenges_reward_kinds"]) == challenges.REWARD_KINDS
    assert tuple(variables["challenges_statuses"]) == challenges.STATUSES
    assert {kind: variables[f"challenges_default_radius_m_{kind}"] for kind in challenges.DEFAULT_RADIUS_M} == (
        challenges.DEFAULT_RADIUS_M
    )
    assert variables["challenges_min_radius_m"] == challenges.MIN_RADIUS_M
    assert variables["challenges_max_radius_m"] == challenges.MAX_RADIUS_M
    assert variables["challenges_default_min_fraction"] == challenges.DEFAULT_MIN_FRACTION
    assert variables["challenges_id_max_chars"] == challenges.ID_MAX_CHARS
    assert variables["challenges_id_pattern"] == challenges._ID.pattern
    assert variables["challenges_domain_pattern"] == export_challenges._DOMAIN.pattern
    assert tuple(variables["challenges_poi_types"]) == POI_TYPES
    # Unset: the build's UTC date, as main() defaults `today`.
    assert variables["challenges_build_date"] is None


def test_every_unit_test_that_sets_vars_sets_dbt_project_ymls_own():
    expected = {name: value for name, value in _project_vars().items() if name != "challenges_build_date"}
    overriding = [test for test in _unit_tests().values() if "overrides" in test]
    assert overriding, "the items unit tests set the build date"
    for test in overriding:
        variables = dict(test["overrides"]["vars"])
        date.fromisoformat(str(variables.pop("challenges_build_date")))
        assert variables == expected, test["name"]


# --- the Python's answer for each unit test's given rows ------------------------------------


def _publishers_answers(test: dict) -> dict[str, dict]:
    """publisher_scope() and publisher_domains() over the rows read so far, one row at a time, as the model
    reads publishers.json: whether each row is its organization's scope, why not, and its domain."""
    (document,) = _given(test, "base_ourhike__challenges_publishers")
    rows = json.loads(document["file_json"])["publishers"]
    organizations = {
        row["steward_id"]: {"provider": row["provider"] or "", "name": row["org_name"] or ""}
        for row in _given(test, "stg_registry__organizations")
    }
    # The model does not read the POIs (int_challenges__publisher_trails does), so every trail is carried.
    trails = {trail for row in rows if isinstance(row, dict) and isinstance(row.get("trails"), list) for trail in row["trails"]}
    pois = [{"id": f"p:{trail}", "trail_id": trail} for trail in trails if isinstance(trail, str)]
    answers = {}
    for position in range(1, len(rows) + 1):
        _, before = export_challenges.publisher_scope(rows[: position - 1], organizations, pois)
        _, after = export_challenges.publisher_scope(rows[:position], organizations, pois)
        problem = after[-1] if len(after) > len(before) else None
        row = rows[position - 1]
        try:
            domains = export_challenges.publisher_domains(rows[:position], organizations, pois)
        except TypeError as error:
            answers[str(position)] = {"raises": f"TypeError: {error}"}
            continue
        org = row.get("org") if isinstance(row, dict) else None
        answers[str(position)] = {
            "publisher_position": position,
            "accepted": problem is None,
            "problem": problem,
            "org_domain": domains.get(org) if problem is None else None,
        }
    return answers


def _publisher_trails_answers(test: dict) -> dict[str, dict]:
    """publisher_scope()'s last step for accepted rows: each trail in scope when a published POI carries it."""
    accepted = [(row["org"], json.loads(row["trails_json"])) for row in _given(test, "int_challenges__publishers")]
    rows = [{"org": org, "trails": trails, "why": "x", "domain": f"{org}.org"} for org, trails in accepted]
    organizations = {f"org:{org}": {"provider": org.upper(), "name": org} for org, _ in accepted}
    pois = [{"id": row["poi_id"], "trail_id": row["trail_id"]} for row in _given(test, "int_challenges__published_pois")]
    scope, refused = export_challenges.publisher_scope(rows, organizations, pois)
    refused = iter(refused)
    answers = {}
    for position, (org, trails) in enumerate(accepted, 1):
        for trail_position, trail in enumerate(trails, 1):
            in_scope = isinstance(trail, str) and trail in scope[org]
            answers[f"{position}.{trail_position}"] = {
                "publisher_trail_id": f"{position}.{trail_position}",
                "in_scope": in_scope,
                "problem": None if in_scope else next(refused),
            }
    assert next(refused, None) is None
    return answers


def _scope(test: dict) -> tuple[dict, dict, dict]:
    """org_trails, organizations and org_domains as the given publishers and their trails give them."""
    publishers = [row for row in _given(test, "int_challenges__publishers") if row["accepted"]]
    organizations = {f"org:{row['org']}": {"provider": row["org_short"], "name": row["org_name"]} for row in publishers}
    domains = {row["org"]: row["org_domain"] for row in publishers}
    trails = {row["org"]: set(json.loads(row["trails_json"])) for row in publishers}
    return trails, organizations, domains


def _files_answers(test: dict) -> dict[str, dict]:
    """build_output() over each file alone, with no POIs and no centerline: its placing checks, then
    resolve_challenge()'s refusals before the items, and where it publishes its window and sections."""
    _, organizations, domains = _scope(test)
    org_trails: dict[str, set[str]] = {}
    for row in _given(test, "int_challenges__publisher_trails"):
        if row["in_scope"]:
            org_trails.setdefault(row["org"], set()).add(row["trail"])
    answers = {}
    for row in _given(test, "int_challenges__unioned"):
        raw = None if row["file_json"] is None else json.loads(row["file_json"])
        output, resolution = export_challenges.build_output(
            [(Path(row["file_folder"]) / row["file_name"], raw)],
            org_trails=org_trails,
            organizations=organizations,
            pois=[],
            centerline=None,
            today=date(2026, 9, 30),
            org_domains=domains,
        )
        record = output["challenges"][0] if output["challenges"] else None
        (label, why), *more = resolution.dropped or [(record["id"] if record else row["file_stem"], None)]
        assert not more, row["challenge_file_key"]
        misplaced = why if why and why.startswith(("file is under ", "saved by ")) else None
        answers[row["challenge_file_key"]] = {
            "challenge_file_key": row["challenge_file_key"],
            "misplaced_problem": misplaced,
            "challenge_problem": None if misplaced else why,
            "report_label": label,
            "window_opens": record["window"]["opens"] if record else None,
            "window_closes": record["window"]["closes"] if record else None,
            "sections_published": record["sections"] if record else None,
        }
    return answers


def _item_outcomes(
    items: list, *, org, trail, section_ids, org_trails, pois, distance, today
) -> list[tuple[str | None, dict | None]]:
    """(problem, published item) for each item by position, as resolve_challenge() resolves the items of a
    challenge that holds them on `trail` and is otherwise test_lib_challenges.challenge()'s, so nothing but its
    items can refuse it; each cross-checked against resolve_challenge()'s own lists."""
    raw = {
        "id": "summer-list",
        "org": org,
        "trail": trail,
        "name": "Summer List",
        "status": "draft",
        "window": {"opens": None, "closes": None},
        "sections": [{"id": section, "title": section} for section in section_ids],
        "items": items,
        "reviewed": "2026-09-30",
    }
    poi_types = tuple(t for t in POI_TYPES if any(p.get("poi_type") == t for p in pois))
    by_id = {p["id"]: p for p in pois}
    kwargs = {"poi_types": poi_types, "pois": by_id, "trail_distance_m": distance}
    record, dropped, why = challenges.resolve_challenge(raw, org_trails=org_trails, today=today, **kwargs)
    assert why == "", why
    drops, resolved = iter(dropped), iter(record["items"])
    section_ids = {section["id"] for section in raw["sections"]}
    out, seen = [], set()
    for raw_item in raw["items"]:
        item_id = raw_item.get("id") if isinstance(raw_item, Mapping) else None
        if not challenges._id_ok(item_id) or item_id in seen:
            label, problem = next(drops)
            assert label == ("<no id>" if not challenges._id_ok(item_id) else item_id)
            out.append((problem, None))
            continue
        seen.add(item_id)
        single, problem = challenges.resolve_item(
            raw_item, trail=raw["trail"], section_ids=section_ids, known_orgs=set(org_trails), today=today, **kwargs
        )
        if single is None:
            assert next(drops) == (item_id, problem)
            out.append((problem, None))
        else:
            assert next(resolved) == single
            out.append((None, single))
    assert next(drops, None) is None and next(resolved, None) is None
    return out


def _place_distances(raw_item, *, pois, distance) -> list[str | None] | None:
    """The model's place_distances by the Python's measure: each place's metres to 3 places, null where the
    radius check does not measure it (off_trail, a walked section's end, no such POI, no centerline)."""
    match = raw_item.get("match") if isinstance(raw_item, Mapping) else None
    if not isinstance(match, Mapping) or match.get("kind") not in ("place", "places_all", "section_walked"):
        return None
    kind = match["kind"]
    if kind == "place":
        ids = [match.get("poi")]
    elif kind == "places_all":
        ids = match.get("pois")
        if not isinstance(ids, list) or not ids:
            return None
    else:
        ids = [match.get("from_poi"), match.get("to_poi")]
    by_id = {p["id"]: p for p in pois}
    texts = []
    for poi_id in ids:
        poi = by_id.get(poi_id) if isinstance(poi_id, str) else None
        measured = kind != "section_walked" and match.get("off_trail") is not True and poi is not None
        texts.append(f"{distance(poi['lon'], poi['lat']):.3f}" if measured and poi["lat"] is not None and distance else None)
    return texts


def _items_answers(test: dict) -> dict[str, dict]:
    """Each file's items resolved as one challenge of test_lib_challenges.challenge()'s shape holding them,
    against the given POIs and centerline, on the unit test's build date."""
    org_trails, _, _ = _scope(test)
    pois = [
        {"id": row["poi_id"], **{name: row[name] for name in ("trail_id", "poi_type", "name", "mile", "lat", "lon")}}
        for row in _given(test, "int_challenges__published_pois")
    ]
    lines = [
        [tuple(vertex) for vertex in json.loads(row["geom_geojson"])["coordinates"]]
        for row in _given(test, "int_challenges__centerline")
    ]
    distance = challenges.trail_distance_index(lines) if lines else None
    today = date.fromisoformat(str(test["overrides"]["vars"]["challenges_build_date"]))
    answers = {}
    for row in _given(test, "int_challenges__files"):
        items = json.loads(row["items_json"])
        outcomes = _item_outcomes(
            items,
            org="atc",
            trail=row["trail"],
            section_ids=json.loads(row["section_ids"]),
            org_trails=org_trails,
            pois=pois,
            distance=distance,
            today=today,
        )
        for position, ((problem, published), raw_item) in enumerate(zip(outcomes, items, strict=True), 1):
            item_id = raw_item.get("id") if isinstance(raw_item, Mapping) else None
            key = f"{row['challenge_file_key']}:{position}"
            answers[key] = {
                "item_key": key,
                "report_label": item_id if challenges._id_ok(item_id) else "<no id>",
                "problem": problem,
                "sealed": published is not None and "sealed_title" in published,
                "place_distances": _place_distances(raw_item, pois=pois, distance=distance),
                "published_item": published,
            }
    return answers


def _resolved_pois(test: dict) -> list[dict]:
    """The POIs the given items publish places at, each as the published place carries it, on its file's trail."""
    trail_of = {row["challenge_file_key"]: row["trail"] for row in _given(test, "int_challenges__files")}
    pois = {}
    for row in _given(test, "int_challenges__items"):
        if row["published_item"] is None:
            continue
        for place in json.loads(row["published_item"])["match"].get("places") or []:
            pois[place["poi"]] = {"id": place["poi"], "trail_id": trail_of[row["challenge_file_key"]], **place}
    return list(pois.values())


def _resolved_answers(test: dict) -> dict[str, dict]:
    """build_output() over every given file at once, in list_position order, so resolve()'s duplicate check
    reads them as one run, as the model does; and each file's given items, held to the Python's own answer."""
    org_trails, organizations, domains = _scope(test)
    files = sorted(_given(test, "int_challenges__files"), key=lambda row: row["list_position"])
    pois = _resolved_pois(test)
    today = date(2026, 9, 30)
    given_items = {(row["challenge_file_key"], row["item_position"]): row for row in _given(test, "int_challenges__items")}
    for row in files:
        raw = json.loads(row["file_json_text"])
        outcomes = _item_outcomes(
            raw["items"],
            org=raw["org"],
            trail=raw["trail"],
            section_ids=[section["id"] for section in raw["sections"]],
            org_trails=org_trails,
            pois=pois,
            distance=None,
            today=today,
        )
        for position, (problem, published) in enumerate(outcomes, 1):
            item = given_items.pop((row["challenge_file_key"], position))
            assert (item["problem"], _parsed(item)["published_item"]) == (problem, published), (
                row["challenge_file_key"],
                position,
            )
    assert not given_items, "every given item belongs to a given file"
    output, resolution = export_challenges.build_output(
        [(Path(row["club"]) / f"{row['file_stem']}.json", json.loads(row["file_json_text"])) for row in files],
        org_trails=org_trails,
        organizations=organizations,
        pois=pois,
        centerline=None,
        today=today,
        org_domains=domains,
    )
    published, dropped, seen = iter(output["challenges"]), iter(resolution.dropped), set()
    upcoming = next(published, None)
    answers = {}
    for row in files:
        challenge_id = json.loads(row["file_json_text"])["id"]
        record = None
        if upcoming is not None and upcoming["id"] == challenge_id and challenge_id not in seen:
            record, upcoming = upcoming, next(published, None)
            seen.add(challenge_id)
            label, why = record["id"], None
        else:
            label, why = next(dropped)
        answers[row["challenge_file_key"]] = {
            "challenge_file_key": row["challenge_file_key"],
            "problem": why,
            "report_label": label,
            "drop_step": None if why is None else 2,
            "finish_count": record["finish"]["count"] if record and record["finish"] else None,
            "finish_label": record["finish"]["label"] if record and record["finish"] else None,
            "reward_kind": record["reward"]["kind"] if record and record["reward"] else None,
            "reward_rules_url": record["reward"]["rules_url"] if record and record["reward"] else None,
            "reward_art": record["reward"]["art"] if record and record["reward"] else None,
            "takes_entries": record["takes_entries"] if record else None,
            "photo": record["photo"] if record else None,
            "reviewed": record["reviewed"] if record else None,
            "item_count": len(record["items"]) if record else None,
            "org_name": record["org_name"] if record else None,
            "org_short": record["org_short"] if record else None,
            "org_domain": record["org_domain"] if record else None,
        }
    assert upcoming is None and next(dropped, None) is None
    return answers


ANSWERS = {
    "int_challenges__publishers": ("publisher_position", _publishers_answers),
    "int_challenges__publisher_trails": ("publisher_trail_id", _publisher_trails_answers),
    "int_challenges__files": ("challenge_file_key", _files_answers),
    "int_challenges__items": ("item_key", _items_answers),
    "int_challenges__resolved": ("challenge_file_key", _resolved_answers),
}


def _cases() -> list[tuple[str, str, dict, dict]]:
    """(unit test, row key, the row the unit test expects, the Python's answer) for every row ANSWERS covers."""
    found = []
    for name, test in _unit_tests().items():
        if test["model"] not in ANSWERS:
            continue
        key, answer = ANSWERS[test["model"]]
        answers = answer(test)
        expected = {str(row[key]): row for row in test["expect"]["rows"]}
        assert expected.keys() == answers.keys(), name
        found += [(name, row_key, expected[row_key], answers[row_key]) for row_key in expected]
    return found


CASES = _cases()


def test_every_unit_test_but_the_report_is_answered_here():
    """A new unit test needs an answer here, or its rows are held to nothing but themselves."""
    models = {test["model"] for test in _unit_tests().values()}
    assert models == set(ANSWERS) | {"int_challenges__refusals"}


@pytest.mark.parametrize(("test_name", "row_key", "expected", "python"), CASES, ids=[f"{t}:{k}" for t, k, _, _ in CASES])
def test_each_unit_test_row_is_the_pythons_answer(test_name, row_key, expected, python):
    if (test_name, row_key) in DELIBERATE:
        pytest.skip("deliberate: test_each_deliberate_row_still_differs holds it")
    assert _parsed(expected) == {name: python[name] for name in expected}


def test_each_deliberate_row_still_differs():
    by_key = {(test_name, row_key): (expected, python) for test_name, row_key, expected, python in CASES}
    for key, reason in DELIBERATE.items():
        expected, python = by_key[key]
        assert _parsed(expected) != {name: python.get(name) for name in expected}, f"{key} answers alike now: {reason}"


def test_the_trailing_newline_is_the_only_id_the_sql_refuses_and_the_python_publishes():
    """The newline row's answers, side by side: the Python publishes the id the SQL refuses."""
    by_key = {(test_name, row_key): (expected, python) for test_name, row_key, expected, python in CASES}
    expected, python = by_key[(ITEMS, f"{LIB}::TestItems::test_an_item_id_with_a_trailing_newline_is_refused_here:1")]
    assert expected["report_label"] == "<no id>" and expected["published_item"] is None
    assert python["problem"] is None and python["published_item"]["id"].endswith("\n")


def test_the_list_org_is_the_row_the_python_cannot_answer():
    by_key = {(test_name, row_key): python for test_name, row_key, _, python in CASES}
    assert by_key[(PUBLISHERS, "13")]["raises"].startswith("TypeError: ")


# --- the report ------------------------------------------------------------------------------

#: The sandbox int_challenges__refusals_report_as_main_reports is a translation
#: of: one of each refusal export_challenges.main() reports.
REPORT_PUBLISHERS = [
    {"org": "atc", "trails": ["AT", "LP"], "why": "x", "domain": "appalachiantrail.org"},
    {"org": "nobody", "trails": ["AT"], "why": "x"},
]


def _report_challenge(**fields) -> dict:
    base = {
        "org": "atc",
        "trail": "AT",
        "name": "Summer List",
        "status": "draft",
        "window": {"opens": "2027-05-15", "closes": "2027-09-01"},
        "finish": None,
        "reward": None,
        "sections": [
            {"id": "experience", "title": "Experience the A.T.", "short": "Anywhere"},
            {"id": "mystery", "title": "Mystery Items", "short": "Mystery"},
        ],
        "items": [{"id": "self-report", "section": "experience", "title": "Do a thing.", "match": {"kind": "self_report"}}],
        "reviewed": "2026-09-30",
    }
    return {**base, **fields}


def test_the_report_is_main_s(tmp_path, monkeypatch, capsys):
    """main() over the sandbox prints the lines the unit test expects, in its order, and every problem the
    given rows carry is one main() reported."""
    test = _unit_tests()["int_challenges__refusals_report_as_main_reports"]
    knob = next(
        row for row in _given(_unit_tests()[ITEMS], "int_challenges__published_pois") if row["poi_id"] == "atc_viewpoints:knob"
    )
    place = {
        "id": "mcafee-knob",
        "section": "experience",
        "title": "Hike to McAfee Knob.",
        "match": {"kind": "place", "poi": knob["poi_id"]},
    }
    gone = {
        "id": "gone",
        "section": "experience",
        "title": "Somewhere gone.",
        "match": {"kind": "place", "poi": "atc_viewpoints:gone"},
    }
    files = [
        ("atc", _report_challenge(id="a-trail", trail="LP")),
        ("nynjtc", _report_challenge(id="b-misplaced")),
        ("atc", _report_challenge(id="c-resolves", items=[place, gone])),
        ("atc", _report_challenge(id="d-finish", items=[gone], finish={"count": 1})),
    ]
    processed, reference = tmp_path / "processed", tmp_path / "challenges"
    for folder in ("atc", "nynjtc"):
        (reference / folder).mkdir(parents=True)
    (processed / "poi").mkdir(parents=True)
    organizations = {
        "org:atc": {"provider": "ATC", "name": "Appalachian Trail Conservancy"},
        "org:nynjtc": {"provider": "NYNJTC", "name": "New York-New Jersey Trail Conference"},
    }
    (tmp_path / "sources.json").write_text(json.dumps({"organizations": {"orgs": organizations}}))
    (reference / "publishers.json").write_text(json.dumps({"publishers": REPORT_PUBLISHERS}))
    poi = {"id": knob["poi_id"], **{name: knob[name] for name in ("trail_id", "poi_type", "name", "mile", "lat", "lon")}}
    (processed / "poi" / "viewpoint.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": poi}]})
    )
    for folder, raw in files:
        (reference / folder / f"{raw['id']}.json").write_text(json.dumps(raw))
    for name, value in {
        "POI_DIR": processed / "poi",
        "TRAILS_PATH": processed / "trails.geojson",
        "OUT_PATH": processed / "challenges.json",
        "MANIFEST_PATH": processed / "challenges_manifest.json",
        "REFERENCE_DIR": reference,
        "PUBLISHERS_PATH": reference / "publishers.json",
        "SOURCES_PATH": tmp_path / "sources.json",
    }.items():
        monkeypatch.setattr(export_challenges, name, value)
    export_challenges.main(today=date(2026, 9, 30))
    lines = [line[2:] for line in capsys.readouterr().err.splitlines() if line.startswith("  ")]
    expected = [row["report_line"] for row in sorted(test["expect"]["rows"], key=lambda row: row["refusal_order"])]
    assert expected == lines
    problems = [row["problem"] for given in test["given"] for row in given["rows"] if row.get("problem")]
    assert problems and all(any(problem in line for line in lines) for problem in problems)


# --- parity.py's one explained difference ---------------------------------------------------


def _warehouse(path: Path, *, source_row: dict | None, resolved: dict) -> Path:
    """A warehouse holding the two relations parity.py's held-back check reads, one row each at most."""
    with duckdb.connect(str(path)) as con:
        con.execute("create schema intermediate")
        con.execute("create table intermediate.int_sources__publication (source_key varchar, may_publish boolean)")
        if source_row is not None:
            con.execute(
                "insert into intermediate.int_sources__publication values (?, ?)",
                [source_row["source_key"], source_row["may_publish"]],
            )
        columns = ", ".join(f"{name} varchar" for name in resolved)
        con.execute(f"create table intermediate.int_challenges__resolved ({columns})")
        con.execute(
            f"insert into intermediate.int_challenges__resolved values ({', '.join('?' for _ in resolved)})",
            list(resolved.values()),
        )
    return path


RESOLVED_ROW = {
    "challenge_id": "summer-list",
    "source_key": "reference/challenges/atc",
    "problem": None,
    "org": "atc",
    "trail": "AT",
    "name": "Summer List",
    "status": "draft",
    "challenge_summary": None,
    "window_opens": "2027-05-15",
    "window_closes": None,
    "finish_count": None,
    "finish_label": None,
    "reward_kind": None,
    "reward_rules_url": None,
    "reward_art": None,
    "takes_entries": None,
    "photo": None,
    "sections_published": '[{"id":"experience","title":"Experience the A.T.","short":"Anywhere"}]',
    "items_published": "[]",
    "reviewed": "2026-09-30",
    "org_name": "Appalachian Trail Conservancy",
    "org_short": "ATC",
    "org_domain": "appalachiantrail.org",
}
#: The same challenge as today's file carries it. takes_entries is null in the
#: varchar stand-in table, and None here, so the two agree field for field.
OLD_RECORD = {
    "id": "summer-list",
    "org": "atc",
    "trail": "AT",
    "name": "Summer List",
    "status": "draft",
    "summary": None,
    "window": {"opens": "2027-05-15", "closes": None},
    "finish": None,
    "reward": None,
    "takes_entries": None,
    "photo": None,
    "sections": [{"id": "experience", "title": "Experience the A.T.", "short": "Anywhere"}],
    "items": [],
    "reviewed": "2026-09-30",
    "org_name": "Appalachian Trail Conservancy",
    "org_short": "ATC",
    "org_domain": "appalachiantrail.org",
}
OLD = {"source": "reference/challenges", "challenges": [OLD_RECORD]}
NEW = {"source": "reference/challenges", "challenges": []}


def test_a_challenge_whose_source_has_no_publication_row_is_explained_as_held_back(tmp_path):
    warehouse = _warehouse(tmp_path / "w.duckdb", source_row=None, resolved=RESOLVED_ROW)
    reasons = parity._held_back_reasons(OLD, NEW, warehouse)
    assert reasons == {"id summer-list": parity.CHALLENGE_REASONS["held_back"], "order": parity.CHALLENGE_REASONS["held_back"]}
    # Every reason parity.py names is held to this case.
    assert set(reasons.values()) == set(parity.CHALLENGE_REASONS.values())


def test_a_challenge_whose_source_may_publish_is_not_explained(tmp_path):
    source = {"source_key": "reference/challenges/atc", "may_publish": True}
    warehouse = _warehouse(tmp_path / "w.duckdb", source_row=source, resolved=RESOLVED_ROW)
    assert parity._held_back_reasons(OLD, NEW, warehouse) == {}


def test_a_held_back_challenge_that_resolved_otherwise_is_not_explained(tmp_path):
    warehouse = _warehouse(tmp_path / "w.duckdb", source_row=None, resolved={**RESOLVED_ROW, "name": "Another List"})
    assert parity._held_back_reasons(OLD, NEW, warehouse) == {}


def test_the_writer_and_parity_build_a_record_from_the_same_fields():
    """_resolved_challenge() is pub_challenges' json_object read back: the same keys, in its order."""
    writer = (DBT / "models" / "publish" / "pub_challenges.sql").read_text(encoding="utf-8")
    record = writer[writer.index("json_object(") : writer.index(") as record")]
    top_level = re.findall(r"^            '(\w+)',", record, flags=re.MULTILINE)
    assert top_level == list(parity._resolved_challenge(RESOLVED_ROW))
