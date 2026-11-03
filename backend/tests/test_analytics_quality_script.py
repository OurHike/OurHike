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
from sqlalchemy import text as sql

from app.models.analytics import AnalyticsEvent
from tests.test_analytics_quality import _rows, _steady

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


def _verdict_keys(script, tmp_path, today, *extra) -> set[str]:
    verdict = tmp_path / f"verdict-{today}.json"
    assert script.main(["--today", today.isoformat(), "--verdict", str(verdict), *extra]) == 0
    return {finding["key"] for finding in json.loads(verdict.read_text())["open"]}


def test_a_statistical_finding_reaches_the_verdict_on_its_second_night_and_the_log_on_its_first(
    script, db_session, tmp_path, capsys
):
    """One odd night costs nobody an email, and late uploads get a night to
    resolve it - but the log, which nobody is notified by, says it at once."""
    _steady(db_session, until=TODAY - timedelta(days=2))
    for back in (2, 1):
        _rows(db_session, TODAY - timedelta(days=back), {"session": 60, "map_screen_viewed": 40})

    first_night = _verdict_keys(script, tmp_path, TODAY)
    printed = capsys.readouterr().out
    second_night = _verdict_keys(script, tmp_path, TODAY + timedelta(days=1))

    assert "plans_made|*" not in first_night
    assert "plans_made" in printed and "first night" in printed
    assert "plans_made|*" in second_night


def test_a_failed_rollup_reaches_the_verdict_the_same_night(script, tmp_path):
    assert "rollup_failed|*" in _verdict_keys(script, tmp_path, TODAY, "--rollup-outcome", "failure")


def test_a_rollup_that_succeeded_is_not_a_finding(script, tmp_path):
    assert "rollup_failed|*" not in _verdict_keys(script, tmp_path, TODAY, "--rollup-outcome", "success")


def test_a_failed_archive_reaches_the_verdict_the_same_night(script, tmp_path):
    """#1923: the archive step's fault would otherwise show only once rows piled up."""
    assert "archive_failed|*" in _verdict_keys(script, tmp_path, TODAY, "--archive-outcome", "failure")


def test_an_archive_skipped_for_want_of_a_bucket_is_not_a_finding(script, tmp_path):
    """The workflow skips the archive until its bucket is configured, and says so itself."""
    assert "archive_failed|*" not in _verdict_keys(script, tmp_path, TODAY, "--archive-outcome", "skipped")


def test_checks_that_cannot_run_are_named_by_class_and_their_values_are_not_printed(script, monkeypatch, capsys):
    """The text of a database error ends in the values its statement was
    bound to; a traceback here would publish them."""

    def failing_checks(db, **_):
        db.execute(sql("select 1 / (:visits - :visits)"), {"visits": THROWN_AWAY})

    monkeypatch.setattr(script, "run_checks", failing_checks)

    assert script.main(["--today", TODAY.isoformat()]) == 1

    out, err = capsys.readouterr()
    assert "DataError" in err
    assert str(THROWN_AWAY) not in out + err
    assert "Traceback" not in err


def test_a_quiet_night_writes_an_empty_verdict(script, tmp_path, capsys):
    verdict = tmp_path / "verdict.json"

    assert script.main(["--today", TODAY.isoformat(), "--verdict", str(verdict)]) == 0

    assert json.loads(verdict.read_text())["open"] == []
    assert "Nothing out of the ordinary" in capsys.readouterr().out


def test_the_verdict_names_at_most_its_cap_and_counts_the_rest(script, tmp_path, monkeypatch):
    """A night of made-up versions once made 2,001 findings and an issue body
    GitHub would not take, so the real faults never reached the issue
    (#1903's second review)."""
    from app.core.analytics_quality import Finding

    many = [Finding(TODAY, "rows_refused", f"version:9.9.{n}", "warn", 1.0, 0.05) for n in range(script.MAX_PUBLIC_FINDINGS + 5)]
    monkeypatch.setattr(script, "run_checks", lambda db, **_: many)
    verdict = tmp_path / "verdict.json"

    assert script.main(["--today", TODAY.isoformat(), "--verdict", str(verdict)]) == 0

    written = json.loads(verdict.read_text())
    assert (len(written["open"]), written["more"]) == (script.MAX_PUBLIC_FINDINGS, 5)
