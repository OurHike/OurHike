"""Run the usage rollup once: recompute open months, close the due ones, delete expired rows (#1902).

    DATABASE_URL=... python scripts/analytics_rollup.py

What a run does, and why in that order, is app/core/analytics_rollup.py's
docstring. This file is the command around it: it prints what was done as
month names - never a row, and never a count, because Actions logs on this
repository are public and a month's row count is its traffic - and exits 1
when a month past
retention was refused deletion because it had not closed. `run` closes every
due month before it deletes anything, so that refusal should be unreachable;
it is the guard for the day somebody reorders the steps or stretches the close
window past retention, and it goes red rather than deleting numbers nobody
froze.

Run nightly by .github/workflows/analytics-rollup.yml. Safe to run by hand
and to run twice: every step is idempotent, and a run that finds nothing to
do says so.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.analytics_rollup import closes_on, retention_start, run  # noqa: E402
from app.core.time import utc_now  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def _months(months) -> str:
    return ", ".join(month.strftime("%Y-%m") for month in months) or "none"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        default=None,
        help="Run as if today were this date (YYYY-MM-DD). For catching up, and for tests.",
    )
    args = parser.parse_args(argv)

    with SessionLocal() as db:
        result = run(db, today=args.today)

    today = args.today or utc_now().date()
    print(f"Recomputed:               {_months(result.recomputed)}")
    print(f"Closed this run:          {_months(result.closed)}")
    print(f"Late rows counted for:    {_months(result.late_counted)}")
    for month in sorted(result.deleted):
        print(f"Deleted the raw rows for {month:%Y-%m} (past retention, closed)")
    print(f"Raw rows are kept from {retention_start(today):%Y-%m-%d}.")
    if result.recomputed:
        latest = max(result.recomputed)
        print(f"{latest:%Y-%m} closes on {closes_on(latest):%Y-%m-%d}.")

    if result.refused:
        print(
            f"REFUSED to delete {_months(result.refused)}: past retention but not closed. "
            "Nothing was lost - the rows are still there, held longer than six months. A run "
            "closes every due month before it deletes, so this means the steps or the close "
            "window in app/core/analytics_rollup.py changed; fix that rather than the data.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
