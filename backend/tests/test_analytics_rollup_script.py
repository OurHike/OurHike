"""The nightly rollup command's output (#1902, scripts/analytics_rollup.py).

What it prints lands in a public Actions log. A month's name may be printed;
a count may not - a month's row count is its traffic - and neither may the
text of a database error, which ends in the values its statement was bound to.
"""

import importlib.util
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.time import utc_now

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analytics_rollup.py"
# Distinctive enough that finding it anywhere in the output means it leaked.
VISITS = 4242


@pytest.fixture()
def script(db_session, monkeypatch):
    spec = importlib.util.spec_from_file_location("analytics_rollup_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    @contextmanager
    def session():
        yield db_session

    monkeypatch.setattr(module, "SessionLocal", session)
    return module


def test_a_run_names_the_months_it_touched(script, capsys):
    assert script.main(["--today", "2026-10-20"]) == 0

    assert "Recomputed:               2026-10" in capsys.readouterr().out


def test_a_today_after_the_real_utc_date_is_refused_before_anything_runs(script, monkeypatch, capsys):
    """A future date closes months early and deletes rows retention still owes."""

    def must_not_run(db, **_):
        raise AssertionError("the rollup ran")

    monkeypatch.setattr(script, "run", must_not_run)
    tomorrow = utc_now().date() + timedelta(days=1)

    assert script.main(["--today", tomorrow.isoformat()]) == 2
    assert "Refused" in capsys.readouterr().err


def test_a_run_that_fails_is_named_by_its_class_and_its_values_are_not_printed(script, monkeypatch, capsys):
    def failing_run(db, **_):
        db.execute(text("select 1 / (:visits - :visits)"), {"visits": VISITS})

    monkeypatch.setattr(script, "run", failing_run)

    assert script.main(["--today", date(2026, 10, 20).isoformat()]) == 1

    out, err = capsys.readouterr()
    assert "DataError" in err, "the failure is named"
    assert str(VISITS) not in out + err
    assert "Traceback" not in err
