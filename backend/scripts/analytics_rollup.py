"""Run the usage rollup once: recompute open months, close the due ones, delete expired rows (#1902).

    DATABASE_URL=... python scripts/analytics_rollup.py

What a run does, and why in that order, is app/core/analytics_rollup.py's
docstring. This file is the command around it: it prints what was done as
month names - never a row, and never a count, because Actions logs on this
repository are public and a month's row count is its traffic - and exits 1
when a month past retention was refused deletion because it had not closed.
`run` closes every due month before it deletes anything, so that refusal
should be unreachable; it is the guard for the day somebody reorders the
steps or stretches the close window past retention, and it goes red rather
than deleting numbers nobody froze.

A run that FAILS exits 1 too, and says so by names alone
(app/core/logs.py `describe_failure`) - never a traceback, whose text can
carry the values a failed statement was bound to. And `--today` later than
the real UTC date is refused with exit 2 before anything runs: the date
decides which months close and which rows are past retention, so a future
one would close and delete for real.

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
from app.core.logs import describe_failure  # noqa: E402
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
        help="Run as if today were this date (YYYY-MM-DD), never later than the real one. For catching up, and for tests.",
    )
    args = parser.parse_args(argv)

    real_today = utc_now().date()
    if args.today is not None and args.today > real_today:
        print(
            f"Refused: --today {args.today} is after today's UTC date, {real_today}. A run dated ahead "
            "closes months early and deletes raw rows that retention has not finished with - for real, "
            "since this is the real database. Nothing was run.",
            file=sys.stderr,
        )
        return 2

    try:
        with SessionLocal() as db:
            result = run(db, today=args.today)
    except Exception as failure:
        # Caught rather than left to print its traceback: this log is public.
        print(f"The rollup did not run, and nothing was committed: {describe_failure(failure)}", file=sys.stderr)
        return 1

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
