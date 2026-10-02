"""The closures and warnings family's SQL refuses and reads what today's Python does, on the same rows (#1793, stage 3).

ATC's reviewed Trail Updates, NYNJTC's Trail Alerts and NWS's relay moved to
SQL (pipeline/ELT.md's ledger, CL01-CL06, WN01-WN08), and until stage 5
deletes the Python both are live. parity.py compares the phone files in CI,
on the real reference/atc_updates.json and on fixture mode's answers for the
rest; this holds what those inputs never exercise, because almost all of it
is a refusal:

- dbt_project.yml's vars are lib/atc_updates.py's constants, and
  python_html_unescape's tables are Python's html module's;
- lib/atc_updates.py's file_problems(), run over int_closures__atc_checked's
  unit-test rows, refuses the same rows in the same words;
- lib/nynjtc_alerts.py's parse_alert(), over int_closures__nynjtc_checked's
  unit-test posts, reads the same titles, localities and dates and refuses
  the same posts;
- export_weather_alerts.py's relayed(), over int_warnings__nws_relayed's
  unit-test alerts, relays the same ones;
- export_atc_updates.py's main(), over the files int_closures__gate's unit
  tests stand for, publishes where the gate passes;

except where a DELIBERATE set below names a row the SQL treats otherwise on
purpose. Each such row must still differ, so emptying a set turns its test red.
"""

import html
import html.entities
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

import export_atc_updates
import export_weather_alerts
import fetch_nynjtc_alerts
import parity
from lib import atc_updates, nynjtc_alerts

DBT = Path(__file__).parent.parent / "dbt"
CLOSURES = DBT / "models" / "intermediate" / "closures" / "_closures__intermediate.yml"
WARNINGS = DBT / "models" / "intermediate" / "warnings" / "_warnings__intermediate.yml"
UNESCAPE = DBT / "macros" / "python_html_unescape.sql"

# ATC rows the SQL refuses and file_problems() passes: row 36, a source_url
# with a leading space. urlparse() strips it before reading the scheme, and
# the phone would then open the link with the space still in it, so the SQL
# reads the scheme as written, as int_podcasts__checked reads a link.
DELIBERATE_ATC_ROWS = {36}

# NYNJTC posts the SQL reads otherwise, each on purpose:
#   n09  `&frac34;`, a name python_html_unescape does not know, is left as
#        written, where html.unescape() writes "¾" (the macro's header);
#   n14, n15  one slug on two posts: the cache is a dict by slug, so the
#        second silently replaces the first, and the SQL refuses both rather
#        than drop one;
#   n16  a title that is not a string: _text_of() publishes str(5), and the
#        SQL refuses it as a payload whose shape has changed.
DELIBERATE_NYNJTC_POSTS = {"n09", "n14", "n15", "n16"}


def _unit_tests(path: Path) -> dict[str, dict]:
    return {test["name"]: test for test in yaml.safe_load(path.read_text())["unit_tests"]}


def _given(test: dict, model: str) -> dict:
    return next(given for given in test["given"] if given["input"] == f"ref('{model}')")


def _same_words(message: str | None) -> str | None:
    """A message with Python's repr and JSON told apart only by quotes, spaces and the names of true and null."""
    if message is None:
        return None
    return re.sub(r"\s+", "", message.replace("'", '"')).replace("True", "true").replace("None", "null")


# --- The constants ------------------------------------------------------------


def test_the_atc_vars_are_lib_atc_updates_constants():
    variables = yaml.safe_load((DBT / "dbt_project.yml").read_text())["vars"]
    assert variables["atc_trail_mile_min"] == atc_updates.TRAIL_MILE_MIN
    assert variables["atc_trail_mile_max"] == atc_updates.TRAIL_MILE_MAX
    assert variables["atc_update_categories"] == sorted(atc_updates.CATEGORIES)


def _macro_map(name: str) -> dict:
    """The keys and values of the one `map([...], [...])` a python_html_unescape helper macro returns."""
    body = re.search(r"\{% macro " + name + r"\(\) -%\}(.*?)\{%- endmacro %\}", UNESCAPE.read_text(), re.S).group(1)
    keys, values = re.findall(r"\[([^\]]*)\]", body)
    return dict(zip(json.loads(f"[{keys.replace(chr(39), chr(34))}]"), json.loads(f"[{values}]"), strict=True))


def test_every_entity_name_the_unescape_knows_is_pythons_spelling_and_character():
    names = _macro_map("_html_names")
    assert names, "no names parsed out of _html_names()"
    for name, code_point in names.items():
        assert html.entities.html5.get(name) == chr(code_point), name


def test_the_replaced_code_points_are_htmls_own_table():
    """html._invalid_charrefs: U+0000, U+000D and U+0080-U+009F, which the HTML5 spec reads otherwise."""
    assert _macro_map("_html_replaced") == {number: ord(text) for number, text in html._invalid_charrefs.items()}


# --- ATC's reviewed rows --------------------------------------------------------


def test_file_problems_refuses_what_the_atc_unit_test_expects():
    test = _unit_tests(CLOSURES)["int_closures__atc_checked_finds_what_file_problems_finds"]
    rows = sorted(_given(test, "base_atc__atc_trail_updates")["rows"], key=lambda row: row["file_row"])
    expected = {row["file_row"]: row["problem"] for row in test["expect"]["rows"]}
    updates = [json.loads(row["atc_update"]) for row in rows]
    assert [row["file_row"] for row in rows] == list(range(len(updates))) and set(expected) == set(range(len(updates)))
    for n in range(len(updates)):
        # file_problems() appends each row's problems in order, so row n's are what its first n + 1 rows add.
        before = atc_updates.file_problems({"updates": updates[:n]})
        python = " | ".join(atc_updates.file_problems({"updates": updates[: n + 1]})[len(before) :]) or None
        if n in DELIBERATE_ATC_ROWS:
            assert python is None and expected[n] is not None, f"row {n} is no longer a deliberate difference"
            continue
        assert _same_words(python) == _same_words(expected[n]), f"row {n}: Python {python!r}, SQL {expected[n]!r}"


def _bake(tmp_path, monkeypatch, document: dict):
    """export_atc_updates.py's main() over one reviewed file: its manifest, None, or the SystemExit it refuses with."""
    reviewed = tmp_path / "atc_updates.json"
    reviewed.write_text(json.dumps(document))
    monkeypatch.setattr(export_atc_updates, "REVIEWED_PATH", reviewed)
    monkeypatch.setattr(export_atc_updates, "OUT_DIR", tmp_path / "conditions")
    monkeypatch.setattr(export_atc_updates, "OUT_PATH", tmp_path / "conditions" / "atc_updates.json")
    monkeypatch.setattr(export_atc_updates, "MANIFEST_PATH", tmp_path / "atc_updates_manifest.json")
    monkeypatch.setattr(export_atc_updates, "CACHE_PATH", tmp_path / "no_cache.json")
    try:
        return export_atc_updates.main()
    except SystemExit as refused:
        return refused


GOOD_ROW = json.loads(
    _given(_unit_tests(CLOSURES)["int_closures__atc_checked_finds_what_file_problems_finds"], "base_atc__atc_trail_updates")[
        "rows"
    ][0]["atc_update"]
)

# The file each of int_closures__gate's ATC unit tests stands for. The gate
# reads the review from the file landed whole (base_atc__atc_updates), so an
# empty reviewed file passes, as export_atc_updates.py publishes it.
GATE_FILES = {
    "int_closures__gate_holds_back_one_bad_atc_row_and_nothing_else": {
        "reviewed_at": "2026-08-24",
        "updates": [GOOD_ROW, {key: value for key, value in GOOD_ROW.items() if key != "obstructs_trail"} | {"atc_id": "a01"}],
    },
    "int_closures__gate_holds_back_an_unreviewed_atc_file": {"reviewed_at": "  ", "updates": [GOOD_ROW]},
    "int_closures__gate_passes_an_empty_reviewed_atc_file_and_holds_back_an_unverified_closure": {
        "reviewed_at": "2026-08-24",
        "updates": [],
    },
    "int_closures__gate_holds_back_an_atc_file_whose_updates_is_not_a_list": {
        "reviewed_at": "2026-08-24",
        "updates": {"a01": GOOD_ROW},
    },
}


@pytest.mark.parametrize("name", sorted(GATE_FILES))
def test_the_gate_holds_back_what_export_atc_updates_does_not_publish(name, tmp_path, monkeypatch):
    test = _unit_tests(CLOSURES)[name]
    (atc,) = [row for row in test["expect"]["rows"] if row["source_key"] == "atc_trail_updates"]
    python_publishes = isinstance(_bake(tmp_path, monkeypatch, GATE_FILES[name]), dict)
    assert python_publishes == atc["passed"], name


# --- NYNJTC's Trail Alerts ------------------------------------------------------


def _wordpress(test: dict) -> tuple[dict[str, dict], dict]:
    """The unit test's base rows as the WordPress posts and vocabularies they were landed from."""
    payloads: dict[str, list] = {taxonomy: [] for taxonomy in nynjtc_alerts.PLACE_TAXONOMIES}
    for term in _given(test, "base_nynjtc__nynjtc_trail_alerts_terms")["rows"]:
        payloads[term["taxonomy"]].append({"id": term["term_id"], "name": term["term_name"], "slug": term["slug"]})
    vocabularies = {taxonomy: nynjtc_alerts.parse_terms(payload) for taxonomy, payload in payloads.items()}
    posts = {}
    for row in _given(test, "base_nynjtc__nynjtc_trail_alerts")["rows"]:
        modified = row["modified_at"]
        posts[row["trail_alert_key"]] = {
            "id": row["post_id"],
            "slug": row["slug"],
            "link": row["link"],
            "title": json.loads(row["title_json"]),
            # dlt read WordPress's offset-free `modified` as UTC, so the landed value is that text read as UTC.
            "modified": modified[:19].replace(" ", "T") if modified is not None else None,
            **{taxonomy: json.loads(row[f"{taxonomy}_term_ids"]) for taxonomy in nynjtc_alerts.PLACE_TAXONOMIES},
        }
    return posts, vocabularies


def test_parse_alert_reads_what_the_nynjtc_unit_test_expects():
    test = _unit_tests(CLOSURES)["int_closures__nynjtc_checked_reads_each_post_as_parse_alert_does"]
    posts, vocabularies = _wordpress(test)
    expected = test["expect"]["rows"]
    assert len(expected) == len(posts)
    now = datetime.now(timezone.utc)
    for (key, post), row in zip(posts.items(), expected, strict=True):
        alert = nynjtc_alerts.parse_alert(post, vocabularies)
        python = None
        if alert is not None:
            entry = fetch_nynjtc_alerts.as_cache_entry(alert, now)
            (python,) = nynjtc_alerts.published_rows({alert.slug: entry})
        agrees = (python is None) == (row["problem"] is not None) and (
            python is None
            or (python["notice_id"], python["title"], python["locality"], python["updated_at"])
            == (row["notice_id"], row["title"], row["locality"], row["updated_at"])
        )
        if key in DELIBERATE_NYNJTC_POSTS:
            assert not agrees, f"{key} is no longer a deliberate difference"
            continue
        assert agrees, f"{key}: Python {python!r}, SQL {row!r}"


# --- NWS's relay ----------------------------------------------------------------

ALERT_VALUES = re.compile(r"\('([^']*)', (null|'[^']*'), (null|'[^']*'), '[^']*'\)")


def test_relayed_relays_what_the_nws_unit_test_expects():
    test = _unit_tests(WARNINGS)["int_warnings__nws_relayed_test_messages_and_cancellations_are_not_relayed"]
    given = ALERT_VALUES.findall(_given(test, "base_nws__alerts")["rows"])
    assert len(given) == 10, "the unit test's VALUES rows were not all read"

    def text(value: str) -> str | None:
        return None if value == "null" else value.strip("'")

    relayed = {
        f"nws_alerts:{alert_id}"
        for alert_id, status, message_type in given
        if export_weather_alerts.relayed({"properties": {"status": text(status), "messageType": text(message_type)}})
    }
    assert relayed == {row["notice_id"] for row in test["expect"]["rows"]}


# --- parity.py's run stamps -------------------------------------------------------


def test_a_run_stamp_is_held_to_its_form_and_not_its_value():
    family = parity.Family(old=dict, records="closures", key="id", stamps=("generated_at",))
    old = {"generated_at": "2026-10-02T03:08:16.614949Z", "closures": []}
    assert parity.differences(old, {**old, "generated_at": "2026-10-02T04:00:00Z"}, family) == []
    assert parity.differences(old, {**old, "generated_at": "2026-10-02T04:00:00+00:00"}, family) != []
    assert parity.differences(old, {"closures": []}, family) != []
