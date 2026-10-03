"""parity.py: two copies of a family's file compared record by record, the way pipeline/ELT.md's shadow run asks."""

import json

import parity
from parity import Family, differences

FAMILY = Family(old=dict, records="episodes", key="spotify_id", ordered=True)


def _document(*episodes, source="reference/podcast_episodes.json"):
    return {"source": source, "episodes": [dict(e) for e in episodes]}


A = {"spotify_id": "a", "title": "One", "hikes": [], "at_miles": [[1.0, 2.0]]}
B = {"spotify_id": "b", "title": "Two", "hikes": ["h1"], "at_miles": []}


def test_the_same_records_in_another_key_order_and_spacing_agree():
    reordered = json.loads(
        json.dumps({"episodes": [dict(reversed(list(A.items()))), B], "source": "reference/podcast_episodes.json"})
    )
    assert differences(_document(A, B), reordered, FAMILY) == []


def test_a_changed_field_is_one_difference_naming_its_record():
    found = differences(_document(A, B), _document(A, {**B, "title": "Too"}), FAMILY)
    assert [what for what, _, _ in found] == ["spotify_id b"]
    assert '"title":"Two"' in found[0][1] and '"title":"Too"' in found[0][2]


def test_a_record_on_one_side_only_is_a_difference():
    assert differences(_document(A, B), _document(A), FAMILY) == [("spotify_id b", parity.canonical(B), None)] + [
        ("order", '["a","b"]', '["a"]')
    ]


def test_order_counts_for_an_ordered_family():
    assert differences(_document(A, B), _document(B, A), FAMILY) == [("order", '["a","b"]', '["b","a"]')]


def test_a_top_level_field_counts():
    assert differences(_document(A), _document(A, source="elsewhere"), FAMILY) == [
        ("field source", '"reference/podcast_episodes.json"', '"elsewhere"')
    ]


def test_ints_and_floats_print_apart():
    """1 and 1.0 are equal in Python and print differently in the file a phone reads, so they differ."""
    assert differences(_document(A), _document({**A, "at_miles": [[1, 2]]}), FAMILY) != []


def test_the_cli_exits_1_on_a_difference(tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(parity.FAMILIES, "fake", Family(old=lambda: _document(A), records="episodes", key="spotify_id"))
    new = tmp_path / "new.json"
    new.write_text(json.dumps(_document({**A, "title": "Changed"})))
    assert parity.main(["fake", "--new", str(new)]) == 1
    assert "spotify_id a" in capsys.readouterr().out
    new.write_text(json.dumps(_document(A)))
    assert parity.main(["fake", "--new", str(new)]) == 0


# --- --keys-only: what refresh-reference.yml uploads to a public artifact ---


def _feature(feature_id: str, name: str, lon: float, lat: float) -> dict:
    return {
        "type": "Feature",
        "properties": {"id": feature_id, "name": name},
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


KEPT = _feature("kept", "Kept Spring", -74.111111, 41.111111)
HELD_BACK = _feature("held", "Held Back Lean-to", -74.222222, 41.222222)
EXPLAINED = _feature("explained", "Explained Privy", -74.333333, 41.333333)
ADDED = _feature("added", "Added Shelter", -74.444444, 41.444444)
#: Text from the records' bodies. A result for upload holds none of it.
BODY_TEXT = ("Kept Spring", "Held Back", "Explained Privy", "Added Shelter", "74.1", "74.2", "74.3", "74.4", "41.")
EVERY_FIELD = ["geometry.coordinates", "geometry.type", "properties.id", "properties.name", "type"]


def _number_lists(value):
    """Every list of numbers inside `value`: a coordinate, or a ring of them."""
    if isinstance(value, dict):
        for inner in value.values():
            yield from _number_lists(inner)
    elif isinstance(value, list):
        if value and all(isinstance(inner, int | float) and not isinstance(inner, bool) for inner in value):
            yield value
        for inner in value:
            yield from _number_lists(inner)


def _features_family(old: dict) -> Family:
    return Family(
        old=lambda: old,
        records="features",
        key="properties.id",
        key_of=lambda feature: feature["properties"]["id"],
        explained=lambda old, new: {"properties.id explained": "moved by a decision"},
    )


def test_keys_only_writes_and_prints_no_record_body_or_geometry(tmp_path, monkeypatch, capsys):
    old = {"type": "FeatureCollection", "features": [KEPT, HELD_BACK, EXPLAINED]}
    moved = [_feature("kept", "Kept Spring", -74.111112, 41.111111), _feature("explained", "Explained Privy", -74.3, 41.3)]
    monkeypatch.setitem(parity.FAMILIES, "fake", _features_family(old))
    new = tmp_path / "new.geojson"
    new.write_text(json.dumps({"type": "FeatureCollection", "features": [*moved, ADDED]}))

    assert parity.main(["fake", "--new", str(new), "--json-dir", str(tmp_path / "results"), "--keys-only"]) == 1
    text = (tmp_path / "results" / "fake.json").read_text()
    result = json.loads(text)
    printed = capsys.readouterr().out

    entries = result["differences"] + result["explained"]
    assert all("old" not in entry and "new" not in entry for entry in entries)
    assert not list(_number_lists(result))
    assert [part for part in BODY_TEXT if part in text or part in printed] == []
    assert {entry["what"]: (entry["held_by"], entry["fields"]) for entry in entries} == {
        "properties.id added": (["new"], EVERY_FIELD),
        "properties.id held": (["old"], EVERY_FIELD),
        "properties.id kept": (["old", "new"], ["geometry.coordinates[]"]),
        "properties.id explained": (["old", "new"], ["geometry.coordinates[]"]),
    }

    # Without the flag the records stay, for a reviewer running parity.py by hand.
    assert parity.main(["fake", "--new", str(new), "--json-dir", str(tmp_path / "full")]) == 1
    full = json.loads((tmp_path / "full" / "fake.json").read_text())
    held = next(entry for entry in full["differences"] if entry["what"] == "properties.id held")
    assert held["old"] == parity.canonical(HELD_BACK)


def test_keys_only_holds_back_every_record_when_only_todays_exporter_writes_a_file(tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(parity.FAMILIES, "fake", _features_family({"features": [KEPT, HELD_BACK]}))
    argv = ["fake", "--new", str(tmp_path / "absent.geojson"), "--json-dir", str(tmp_path), "--keys-only"]

    assert parity.main(argv) == 1
    text = (tmp_path / "fake.json").read_text()
    result = json.loads(text)
    assert result["outcome"] == "one_side_writes"
    assert [(entry["what"], entry["held_by"]) for entry in result["differences"]] == [("file", ["old"])]
    assert not list(_number_lists(result))
    assert [part for part in BODY_TEXT if part in text or part in capsys.readouterr().out] == []
