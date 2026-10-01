"""parity.py: two copies of a family's file compared record by record, the way pipeline/ELT.md's shadow run asks."""

import json

import parity
from parity import Family, differences

FAMILY = Family(old=dict, records="episodes", key="spotify_id", ordered=True, volatile=("generated_at",))


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


def test_volatile_keys_are_dropped():
    assert differences(_document({**A, "generated_at": 1}), _document({**A, "generated_at": 2}), FAMILY) == []


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
