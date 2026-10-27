"""The nightly data-quality command's output (#1902, scripts/analytics_quality.py).

What it prints lands in a public Actions log, and its verdict becomes the body
of a public issue. The promise pinned here is that neither carries a figure:
a check's name, its slice, which way it went and the day - never a count.
"""

import importlib.util
import json
import re
import uuid
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.models.analytics import AnalyticsEvent

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analytics_quality.py"
TODAY = date(2026, 11, 20)
# Distinctive enough that finding it anywhere in the output means it leaked.
THROWN_AWAY = 37


@pytest.fixture()
def script(db_session, monkeypatch):
    spec = importlib.util.spec_from_file_location("analytics_quality_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    @contextmanager
    def session():
        yield db_session

    monkeypatch.setattr(module, "SessionLocal", session)
    return module


def _unsealed_rows(db_session, count: int) -> None:
    day = TODAY - timedelta(days=2)
    for _ in range(count):
        db_session.add(
            AnalyticsEvent(
                id=str(uuid.uuid4()),
                local_date=day,
                received_on=day,
                event="map_screen_viewed",
                platform="ios",
                seal="no_key",
            )
        )
    db_session.commit()


def test_a_finding_is_named_and_its_figure_is_not(script, db_session, tmp_path, capsys):
    _unsealed_rows(db_session, THROWN_AWAY)
    verdict = tmp_path / "verdict.json"

    assert script.main(["--today", TODAY.isoformat(), "--verdict", str(verdict)]) == 0

    printed = capsys.readouterr().out
    written = verdict.read_text()
    assert "rows_unsealed_no_key" in printed and "rows_unsealed_no_key" in written
    for text in (printed, written):
        assert str(THROWN_AWAY) not in re.sub(r"\d{4}-\d{2}-\d{2}(T[\d:]+Z)?", "", text)
    finding = json.loads(written)["open"][0]
    assert set(finding) == {"key", "check", "scope", "status", "day"}


def test_a_quiet_night_writes_an_empty_verdict(script, tmp_path, capsys):
    verdict = tmp_path / "verdict.json"

    assert script.main(["--today", TODAY.isoformat(), "--verdict", str(verdict)]) == 0

    assert json.loads(verdict.read_text())["open"] == []
    assert "Nothing out of the ordinary" in capsys.readouterr().out
