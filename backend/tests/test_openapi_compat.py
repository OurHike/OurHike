"""The API this build serves must not break a supported release's clients (#374).

RELEASING.md §8c, surface 2. Three parts, all load-bearing:

*The real check.* Every retained baseline against `app.openapi()`. This is the
one that fails during ordinary work, when somebody removes a response field
without noticing an old phone reads it.

*The synthetic cases.* One per rule, on hand-built documents. Without them the
real check is untestable: it passes today because the API is compatible with
itself, and it would pass exactly as loudly if `compare` returned `[]`
unconditionally. Each case below is a break the differ must find, and
`test_an_unchanged_document_is_clean` is the one it must not invent.

*The retention rule.* Which releases "supported" covers. A number in a
document is a wish; these are what make it enforced. The cases that matter
are the ones where a naive "keep the last three" gives the wrong answer - a
pinned app-store release older than the window, and a release superseded
after months of being current.

The asymmetry between request and response is the thing most likely to look
like a bug on first reading - see the module docstring in
scripts/check_openapi_compat.py. An old client WRITES requests and READS
responses, so the direction a change is safe in flips between them.
"""

import copy
import datetime as dt
import json

import pytest

from scripts.check_openapi_compat import (
    BASELINES_DIR,
    MANIFEST_PATH,
    compare,
    compare_all,
    current_document,
    load_baselines,
    load_manifest,
    retained,
)


def _document(schema: dict, *, role: str = "response") -> dict:
    """A minimal but structurally real OpenAPI document with one schema.

    `role` decides whether the schema hangs off a requestBody or a response,
    which is what selects the rule set being exercised.
    """
    reference = {"$ref": "#/components/schemas/Thing"}
    operation: dict = {"responses": {"200": {"content": {"application/json": {"schema": reference}}}}}
    if role == "request":
        operation = {
            "requestBody": {"content": {"application/json": {"schema": reference}}},
            "responses": {"204": {"description": "no content"}},
        }
    return {
        "openapi": "3.1.0",
        "paths": {"/things": {"post" if role == "request" else "get": operation}},
        "components": {"schemas": {"Thing": schema}},
    }


THING = {
    "type": "object",
    "properties": {"id": {"type": "string"}, "note": {"type": "string"}},
    "required": ["id"],
}


# --- The real check -------------------------------------------------------


def test_this_build_is_compatible_with_every_retained_release():
    assert compare_all(load_baselines(), current_document()) == []


def test_there_is_at_least_one_retained_baseline_and_it_is_substantial():
    """Guards the failure mode that would make every other test here a lie:
    no baselines, or an empty one, compares clean against anything.

    Same principle as tests/test_preferences_contract.py - "the one thing
    this must never do is pass because it failed to find the file."
    """
    baselines = load_baselines()

    assert baselines != []
    for release, document in baselines:
        assert len(document["paths"]) >= 15, release
        assert len(document["components"]["schemas"]) >= 30, release


def test_a_missing_manifest_raises_rather_than_passing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_baselines(directory=tmp_path)


def test_a_retained_release_whose_document_is_gone_raises(tmp_path):
    """The half a missing-file check usually forgets. An entry in the manifest
    with nothing on disk is a release we claim to support and never check -
    worse than not claiming it, because the claim is what stops anybody
    looking."""
    manifest = {
        "policy": {"supersededDays": 90, "floor": 3},
        "releases": [{"release": "v1.0.0", "document": "gone.json", "superseded": None, "pinned": False}],
    }

    with pytest.raises(FileNotFoundError):
        load_baselines(manifest, today=dt.date(2026, 8, 8), directory=tmp_path)


def test_every_document_in_the_directory_is_claimed_by_the_manifest():
    """The opposite drift: a baseline file nobody lists is a release either
    silently unsupported or silently forgotten, and the file's presence makes
    it look otherwise."""
    listed = {entry["document"] for entry in load_manifest()["releases"]}
    on_disk = {path.name for path in BASELINES_DIR.glob("*.json") if path.name != "retained.json"}

    assert on_disk == listed


def test_the_baselines_on_disk_are_what_the_writer_produces():
    """They are written by `--write`, so each must be byte-comparable to that
    output - otherwise a hand-edit could sit in a file undetected.

    The BYTES on disk against the writer's exact rendering, which is the
    assertion this docstring always described. The old body compared a parsed
    document to a round-trip of itself - true for every parseable file, a
    tampered one included - so the one hand-edit this test exists to catch
    was precisely what it could not see (#650). A legitimate surgical edit
    (the #641/#430 refreshes) passes exactly when it preserves the writer's
    format, which is the discipline those refreshes already followed."""
    for entry in load_manifest()["releases"]:
        path = BASELINES_DIR / entry["document"]
        document = json.loads(path.read_text())
        assert path.read_text() == json.dumps(document, indent=2, sort_keys=True) + "\n", (
            f"{entry['document']} is not byte-identical to the writer's rendering of its own content - "
            "a hand-edit that changed more than values, or a rewrite outside `--write`. See #650."
        )


# --- The retention rule: which releases "supported" means -----------------
#
# RELEASING.md §8c. DATA_RELEASES.md's retention rule with the same numbers
# and a different verb - there, dropping an entry deletes bytes from R2; here
# it stops the backend promising to answer that release's clients.


def _entry(release: str, superseded: str | None, *, pinned: bool = False) -> dict:
    return {
        "release": release,
        "document": f"{release}.json",
        "superseded": superseded,
        "pinned": pinned,
    }


def _manifest(*entries: dict) -> dict:
    return {"policy": {"supersededDays": 90, "floor": 3}, "releases": list(entries)}


TODAY = dt.date(2026, 8, 8)


def test_the_current_release_is_never_dropped():
    """`superseded: null` means nothing has taken over. No clock has started."""
    manifest = _manifest(_entry("v2.0.0", None))

    assert [entry["release"] for entry in retained(manifest, TODAY)] == ["v2.0.0"]


def test_the_three_most_recent_are_kept_however_old():
    """The floor. All three superseded well outside the 90-day window."""
    manifest = _manifest(
        _entry("v4.0.0", None),
        _entry("v3.0.0", "2025-01-01"),
        _entry("v2.0.0", "2024-01-01"),
        _entry("v1.0.0", "2023-01-01"),
    )

    kept = [entry["release"] for entry in retained(manifest, TODAY)]

    assert kept == ["v4.0.0", "v3.0.0", "v2.0.0"]


def test_a_fourth_release_outside_the_window_is_dropped():
    manifest = _manifest(
        _entry("v4.0.0", None),
        _entry("v3.0.0", "2026-08-01"),
        _entry("v2.0.0", "2026-07-01"),
        _entry("v1.0.0", "2020-01-01"),
    )

    kept = [entry["release"] for entry in retained(manifest, TODAY)]

    assert "v1.0.0" not in kept


def test_a_fourth_release_inside_the_window_is_kept():
    """The floor is a floor, not a ceiling. Four releases in quick succession
    means four supported, which is the point of measuring in days as well as
    in count."""
    manifest = _manifest(
        _entry("v4.0.0", None),
        _entry("v3.0.0", "2026-08-01"),
        _entry("v2.0.0", "2026-07-15"),
        _entry("v1.0.0", "2026-07-01"),
    )

    kept = [entry["release"] for entry in retained(manifest, TODAY)]

    assert kept == ["v4.0.0", "v3.0.0", "v2.0.0", "v1.0.0"]


def test_a_pinned_release_survives_any_age():
    """The escape hatch, and the reason the number alone is not the answer.
    An app-store build cannot be forced forward, and a thru-hike runs five to
    seven months against a ninety-day window. DATA_RELEASES.md names this in
    exactly those terms for the data side."""
    manifest = _manifest(
        _entry("v5.0.0", None),
        _entry("v4.0.0", "2026-08-01"),
        _entry("v3.0.0", "2026-07-01"),
        _entry("v2.0.0", "2025-01-01"),
        _entry("v1.0.0", "2024-01-01", pinned=True),
    )

    kept = [entry["release"] for entry in retained(manifest, TODAY)]

    # v1.0.0 is kept and v2.0.0 is not, though v2.0.0 is the newer of the two.
    # Pinning beats recency, which is the property an app-store build needs.
    assert kept == ["v5.0.0", "v4.0.0", "v3.0.0", "v1.0.0"]


def test_the_clock_runs_from_supersession_not_publication():
    """The subtle half, and the one a count-only rule gets wrong.

    v1.0.0 stayed current for two years and was replaced yesterday. Three
    quick releases follow it within a fortnight. Under a count-only rule
    every hiker who installed during those two years is out of support
    immediately; under this one v1.0.0 has 90 days from the day it was
    replaced. With RELEASING.md §14.5's cadence question still open -
    release-when-ready is on the table - this is not hypothetical.
    """
    manifest = _manifest(
        _entry("v4.0.0", None),
        _entry("v3.0.0", "2026-08-07"),
        _entry("v2.0.0", "2026-08-06"),
        _entry("v1.0.0", "2026-08-05"),
    )

    kept = [entry["release"] for entry in retained(manifest, TODAY)]

    assert "v1.0.0" in kept


def test_the_real_manifest_parses_and_names_a_current_release():
    manifest = load_manifest(MANIFEST_PATH)
    current = [entry for entry in manifest["releases"] if entry["superseded"] is None]

    assert manifest["policy"]["floor"] == 3
    assert manifest["policy"]["supersededDays"] == 90
    # Exactly one release can be the current one; two would mean a release
    # was added without marking what it took over from.
    assert len(current) == 1


# --- Checking every retained release, not just the oldest -----------------


def test_a_break_against_a_middle_release_is_still_found():
    """Why `compare_all` exists rather than a diff against the oldest.

    Compatibility is not transitive. `added_in_v2` is absent from v1's
    document, so a diff against v1 alone sees nothing - while every v2 client
    in the field reads it.
    """
    v1 = _document(THING)
    v2 = copy.deepcopy(v1)
    v2["components"]["schemas"]["Thing"]["properties"]["added_in_v2"] = {"type": "string"}
    current = _document(THING)

    assert compare(v1, current) == []

    found = compare_all([("v1.0.0", v1), ("v2.0.0", v2)], current)

    assert [(release, item.where) for release, item in found] == [("v2.0.0", "Thing.added_in_v2")]


# --- One synthetic case per rule ------------------------------------------


def test_an_unchanged_document_is_clean():
    """The differ must not invent breaks. Without this, a `compare` that
    returned a break for everything would pass every other test here."""
    assert compare(_document(THING), _document(THING)) == []


def test_a_removed_path_is_a_break():
    current = _document(THING)
    current["paths"] = {}

    breaks = compare(_document(THING), current)

    assert [item.rule for item in breaks] == ["path removed"]


def test_a_removed_operation_is_a_break():
    current = _document(THING)
    current["paths"]["/things"] = {"put": {"responses": {}}}

    breaks = compare(_document(THING), current)

    assert "operation removed" in [item.rule for item in breaks]


def test_a_newly_required_parameter_is_a_break():
    """#650's headline case: GET /reports gains a required ?bbox= and every
    retained client in the field 422s on every call - through a gate whose
    docstring says "every way" and which returned [] for this one."""
    old = _document(THING)
    new = copy.deepcopy(old)
    new["paths"]["/things"]["get"]["parameters"] = [
        {"name": "bbox", "in": "query", "required": True, "schema": {"type": "string"}}
    ]

    breaks = compare(old, new)

    assert [item.rule for item in breaks] == ["parameter newly required"]
    assert "query:bbox" in breaks[0].where


def test_a_parameter_required_all_along_is_not_a_break():
    old = _document(THING)
    old["paths"]["/things"]["get"]["parameters"] = [
        {"name": "bbox", "in": "query", "required": True, "schema": {"type": "string"}}
    ]

    assert compare(old, copy.deepcopy(old)) == []


def test_a_newly_optional_parameter_is_not_a_break():
    """The additive direction: an old client that never sends it is exactly
    what optional means."""
    old = _document(THING)
    new = copy.deepcopy(old)
    new["paths"]["/things"]["get"]["parameters"] = [
        {"name": "bbox", "in": "query", "required": False, "schema": {"type": "string"}}
    ]

    assert compare(old, new) == []


def test_a_newly_required_request_body_is_a_break():
    old = {"openapi": "3.1.0", "paths": {"/things": {"post": {"responses": {"204": {"description": "ok"}}}}}}
    new = copy.deepcopy(old)
    new["paths"]["/things"]["post"]["requestBody"] = {
        "required": True,
        "content": {"application/json": {"schema": {"type": "object"}}},
    }

    breaks = compare(old, new)

    assert [item.rule for item in breaks] == ["request body newly required"]


def test_a_response_stripped_of_its_content_is_a_break():
    """A 200-with-content becoming a 204, or losing its content, hands an old
    reader nothing - and takes the schema's RESPONSE role with it, so the
    field-level rules go quiet at exactly the wrong moment. The operation
    keeps existing, which is what kept this invisible to the removed-path and
    removed-operation rules (#650)."""
    old = _document(THING)
    new = copy.deepcopy(old)
    new["paths"]["/things"]["get"]["responses"] = {"200": {"description": "no body any more"}}

    breaks = compare(old, new)

    assert "response stripped" in [item.rule for item in breaks]
    assert any("GET /things 200" in item.where for item in breaks)


def test_a_removed_response_field_is_a_break():
    shrunk = copy.deepcopy(THING)
    del shrunk["properties"]["note"]

    breaks = compare(_document(THING), _document(shrunk))

    assert [item.rule for item in breaks] == ["response field removed"]
    assert breaks[0].where == "Thing.note"


def test_a_response_field_demoted_to_optional_is_a_break():
    """The same removal, spread over two releases. An old client that reads
    `id` unconditionally does not care that the server still sometimes sends
    it."""
    loosened = copy.deepcopy(THING)
    loosened["required"] = []

    breaks = compare(_document(THING), _document(loosened))

    assert [item.rule for item in breaks] == ["response field no longer guaranteed"]


def test_an_added_response_field_is_not_a_break():
    """An old client ignores what it does not know."""
    grown = copy.deepcopy(THING)
    grown["properties"]["added_later"] = {"type": "string"}

    assert compare(_document(THING), _document(grown)) == []


def test_a_newly_required_request_field_is_a_break():
    stricter = copy.deepcopy(THING)
    stricter["required"] = ["id", "note"]

    breaks = compare(_document(THING, role="request"), _document(stricter, role="request"))

    assert [item.rule for item in breaks] == ["request field newly required"]
    assert breaks[0].where == "Thing.note"


def test_a_newly_required_response_field_is_not_a_break():
    """The direction that flips. A server promising MORE about what it sends
    cannot break a reader."""
    stricter = copy.deepcopy(THING)
    stricter["required"] = ["id", "note"]

    assert compare(_document(THING), _document(stricter)) == []


def test_a_removed_request_enum_member_is_a_break():
    old = copy.deepcopy(THING)
    old["properties"]["kind"] = {"enum": ["blowdown", "trash", "thanks"]}
    new = copy.deepcopy(old)
    new["properties"]["kind"] = {"enum": ["blowdown", "trash"]}

    breaks = compare(_document(old, role="request"), _document(new, role="request"))

    assert [item.rule for item in breaks] == ["request enum member removed"]
    assert "thanks" in breaks[0].detail


def test_a_removed_response_enum_member_is_not_a_break():
    """Every enum this API returns is rendered through a client-side lookup
    with a fallback, so an unknown or absent member degrades to a neutral
    label rather than throwing."""
    old = copy.deepcopy(THING)
    old["properties"]["kind"] = {"enum": ["verified", "resolved", "dismissed"]}
    new = copy.deepcopy(old)
    new["properties"]["kind"] = {"enum": ["verified", "resolved"]}

    assert compare(_document(old), _document(new)) == []


def test_a_schema_reached_only_through_nesting_is_still_checked():
    """Roles resolve transitively. Stopping at the top level would exempt
    exactly the nested shapes most likely to change - `ReportOut` inside a
    moderation queue, for instance."""
    baseline = _document(THING)
    baseline["components"]["schemas"]["Thing"] = {
        "type": "object",
        "properties": {"inner": {"$ref": "#/components/schemas/Inner"}},
    }
    baseline["components"]["schemas"]["Inner"] = {
        "type": "object",
        "properties": {"kept": {"type": "string"}, "dropped": {"type": "string"}},
    }
    current = copy.deepcopy(baseline)
    del current["components"]["schemas"]["Inner"]["properties"]["dropped"]

    breaks = compare(baseline, current)

    assert [item.where for item in breaks] == ["Inner.dropped"]


def test_a_removed_schema_that_an_operation_used_is_a_break():
    current = _document(THING)
    current["components"]["schemas"] = {}

    breaks = compare(_document(THING), current)

    assert "schema removed" in [item.rule for item in breaks]


def test_an_orphaned_schema_is_not_part_of_the_contract():
    """A component no operation references is not on the wire, so removing
    it cannot break a client."""
    baseline = _document(THING)
    baseline["components"]["schemas"]["NeverReferenced"] = {"type": "object"}
    current = _document(THING)

    assert compare(baseline, current) == []
