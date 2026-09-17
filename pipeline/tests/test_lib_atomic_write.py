"""lib/atomic_write.py - a reader sees the old file or the new one, never a prefix."""

from __future__ import annotations

import os

import pytest

from lib import atomic_write
from lib.atomic_write import write_text_atomically


def test_the_new_text_replaces_the_old_and_leaves_no_temporary_file(tmp_path):
    path = tmp_path / "cache.json"
    path.write_text("old")

    write_text_atomically(path, "new")

    assert path.read_text() == "new"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["cache.json"]


def test_a_missing_file_is_created(tmp_path):
    path = tmp_path / "cache.json"

    write_text_atomically(path, "first")

    assert path.read_text() == "first"


def test_a_failed_replace_leaves_the_old_text_and_no_temporary_file(tmp_path, monkeypatch):
    """The property the fetchers' docstrings claim: a write that dies leaves
    the previous cache, not a truncated one for `if: always()` to save."""
    path = tmp_path / "cache.json"
    path.write_text("old")

    def refuse(src, dst):
        raise OSError("disk went away")

    monkeypatch.setattr(atomic_write.os, "replace", refuse)
    with pytest.raises(OSError):
        write_text_atomically(path, "new")

    assert path.read_text() == "old"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["cache.json"]


def test_the_temporary_file_sits_beside_the_target(tmp_path, monkeypatch):
    """Same directory, so the rename cannot cross a filesystem and stop being
    one step."""
    seen = {}

    def record(src, dst):
        seen["src"], seen["dst"] = src, dst
        os.rename(src, dst)

    monkeypatch.setattr(atomic_write.os, "replace", record)
    path = tmp_path / "nested" / "cache.json"
    path.parent.mkdir()

    write_text_atomically(path, "text")

    assert seen["src"].parent == path.parent
    assert seen["dst"] == path
