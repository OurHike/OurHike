"""Run the usage data-quality checks once and record what they find (#1902).

    DATABASE_URL=... python scripts/analytics_quality.py [--today YYYY-MM-DD] [--verdict PATH]

What is checked, and the thresholds, are app/core/analytics_quality.py's
docstring. This file is the command around it, run nightly by
.github/workflows/analytics-rollup.yml after the rollup.

IT PRINTS NO FIGURES. Actions logs and issues on this repository are public,
so what leaves this command names a check, the slice it is about, which way
it went and the day - "plans_made_per_session, version:1.5.2, low, 2026-11-03"
- and never a count or a rate. The figures are in `analytics_anomalies`, and
the usage report (scripts/usage_report.py) is where a person reads them.

`--verdict` writes the open findings as JSON for the workflow's tracking-issue
step, in the same no-figures shape. Exit 0 whatever was found: a finding is
news about the data, not a failure of the job. Exit 1 only if the checks
themselves could not run - said by names alone (app/core/logs.py
`describe_failure`), never with a traceback, whose text can carry the values
a failed statement was bound to.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.analytics_quality import record, run_checks  # noqa: E402
from app.core.logs import describe_failure  # noqa: E402
from app.core.time import utc_now  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        default=None,
        help="Check as if today were this date (YYYY-MM-DD). For catching up, and for tests.",
    )
    parser.add_argument("--verdict", type=Path, default=None, help="Write the open findings here as JSON.")
    args = parser.parse_args(argv)
    today = args.today or utc_now().date()

    try:
        with SessionLocal() as db:
            findings = record(db, run_checks(db, today=today), today=today)
    except Exception as failure:
        # Caught rather than left to print its traceback: this log is public.
        print(f"The data-quality checks could not run: {describe_failure(failure)}", file=sys.stderr)
        return 1

    findings = sorted(findings, key=lambda f: (f.status != "broken", f.check_name, f.scope, f.day))
    if findings:
        print(f"{len(findings)} finding(s) on {today:%Y-%m-%d}:")
        for finding in findings:
            print(f"  {finding.status:<6} {finding.check_name}  {finding.scope}  {finding.day:%Y-%m-%d}")
    else:
        print(f"Nothing out of the ordinary on {today:%Y-%m-%d}.")

    if args.verdict is not None:
        args.verdict.write_text(
            json.dumps(
                {
                    "checked_at": utc_now().isoformat(timespec="seconds") + "Z",
                    "open": [
                        {
                            "key": f"{finding.check_name}|{finding.scope}",
                            "check": finding.check_name,
                            "scope": finding.scope,
                            "status": finding.status,
                            "day": finding.day.isoformat(),
                        }
                        for finding in findings
                    ],
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
