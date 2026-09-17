"""The hourly fetchers write their caches in one step (lib/atomic_write.py).

publish-conditions.yml saves each cache `if: always() && hashFiles(...) != ''`,
so a file truncated by the step's timeout is not lost - it is cached and
restored into every later run. Each fetcher's docstring promised an atomic
write; these hold them to it.
"""

from __future__ import annotations

import json

import pytest

import fetch_atc_updates
import fetch_centerline
import fetch_nynjtc_alerts
from lib import atomic_write


@pytest.mark.parametrize("write_cache", [fetch_atc_updates.write_cache, fetch_nynjtc_alerts.write_cache])
def test_a_cache_write_that_dies_leaves_the_previous_cache(tmp_path, monkeypatch, write_cache):
    path = tmp_path / "raw" / "cache.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"fetched_at": "yesterday", "updates": {"kept": True}}))

    def refuse(src, dst):
        raise OSError("killed at the timeout")

    monkeypatch.setattr(atomic_write.os, "replace", refuse)
    with pytest.raises(OSError):
        write_cache(path, {"fetched_at": "now", "updates": {}})

    assert json.loads(path.read_text()) == {"fetched_at": "yesterday", "updates": {"kept": True}}
    assert sorted(p.name for p in path.parent.iterdir()) == ["cache.json"]


@pytest.mark.parametrize("write_cache", [fetch_atc_updates.write_cache, fetch_nynjtc_alerts.write_cache])
def test_a_cache_write_lands_whole_with_a_trailing_newline(tmp_path, write_cache):
    path = tmp_path / "raw" / "cache.json"

    write_cache(path, {"fetched_at": "now", "listed": 2})

    assert path.read_text().endswith("}\n")
    assert json.loads(path.read_text()) == {"fetched_at": "now", "listed": 2}


def test_the_centerline_fetch_writes_through_the_same_helper():
    """fetch_centerline.py's write is inline in main(), behind a live ArcGIS
    call this suite never makes; the helper it binds is the one tested above."""
    assert fetch_centerline.write_text_atomically is atomic_write.write_text_atomically
