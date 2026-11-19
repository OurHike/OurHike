"""Run the usage data-quality checks once and record what they find (#1902).

    DATABASE_URL=... python scripts/analytics_quality.py [--today YYYY-MM-DD] [--verdict PATH]
        [--rollup-outcome success|failure|cancelled|skipped]
        [--archive-outcome success|failure|cancelled|skipped]

What is checked, and the thresholds, are app/core/analytics_quality.py's
docstring. This file is the command around it, run nightly by
.github/workflows/analytics-rollup.yml after the rollup - even when the
rollup step failed, which the workflow passes in as `--rollup-outcome` and
this records as a `rollup_failed` finding, so a broken job is news in the
tracking issue the same night rather than three days later when collection
pauses behind it. `--archive-outcome` does the same for the archive step
before the rollup (#1923), as `archive_failed` - except that `skipped` is no
finding there: the workflow skips the archive while its bucket is not
configured, which is a setting nobody has made yet, and says so in its own
warning.

IT PRINTS NO FIGURES. Actions logs and issues on this repository are public,
so what leaves this command names a check, the slice it is about, which way
it went and the day - "plans_made_per_session, version:1.5.2, low, 2026-11-03"
- and never a count or a rate. The figures are in `analytics_anomalies`, and
the usage report (scripts/usage_report.py) is where a person reads them.

`--verdict` writes the findings the public tracking issue may carry as JSON,
in the same no-figures shape: every finding but a statistical one on its
first night (`public_findings` - the log below marks those). Exit 0 whatever
was found: a finding is news about the data, not a failure of the job. Exit
1 only if the checks themselves could not run - said by names alone
(app/core/logs.py `describe_failure`), never with a traceback, whose text can
carry the values a failed statement was bound to.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.analytics_quality import public_findings, record, run_checks  # noqa: E402
from app.core.logs import describe_failure  # noqa: E402
from app.core.time import utc_now  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

# What GitHub Actions reports as a step's `outcome`.
STEP_OUTCOMES = ("success", "failure", "cancelled", "skipped")


# The most findings the public issue and this job's public log name, broken
# ones first; the rest are counted, and named in the usage report. A night of
# made-up versions once made 2,001 findings and a 364,684-character issue
# body, past what GitHub takes - so the issue stopped updating and the real
# faults behind them never reached it (#1903's second review). @unvalidated:
# forty is a screenful, which is a guess at what anybody reads.
MAX_PUBLIC_FINDINGS = 40


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        default=None,
        help="Check as if today were this date (YYYY-MM-DD). For catching up, and for tests.",
    )
    parser.add_argument("--verdict", type=Path, default=None, help="Write the public findings here as JSON.")
    parser.add_argument(
        "--rollup-outcome",
        choices=STEP_OUTCOMES,
        default=None,
        help="How tonight's rollup step ended, as the workflow saw it. Anything but success is a finding.",
    )
    parser.add_argument(
        "--archive-outcome",
        choices=STEP_OUTCOMES,
        default=None,
        help="How tonight's archive step ended. Failure or cancelled is a finding; skipped, an unconfigured bucket, is not.",
    )
    args = parser.parse_args(argv)
    today = args.today or utc_now().date()
    rollup_failed = args.rollup_outcome not in (None, "success")
    archive_failed = args.archive_outcome in ("failure", "cancelled")

    try:
        with SessionLocal() as db:
            checks = run_checks(db, today=today, rollup_failed=rollup_failed, archive_failed=archive_failed)
            findings = record(db, checks, today=today)
            public = public_findings(db, findings, today=today)
    except Exception as failure:
        # Caught rather than left to print its traceback: this log is public.
        print(f"The data-quality checks could not run: {describe_failure(failure)}", file=sys.stderr)
        return 1

    findings = sorted(findings, key=lambda f: (f.status != "broken", f.check_name, f.scope, f.day))
    public = sorted(public, key=lambda f: (f.status != "broken", f.check_name, f.scope, f.day))
    if findings:
        print(f"{len(findings)} finding(s) on {today:%Y-%m-%d}:")
        for finding in findings[:MAX_PUBLIC_FINDINGS]:
            waiting = "" if finding in public else "  (first night; the issue waits for a second)"
            print(f"  {finding.status:<6} {finding.check_name}  {finding.scope}  {finding.day:%Y-%m-%d}{waiting}")
        if len(findings) > MAX_PUBLIC_FINDINGS:
            print(f"  ...and {len(findings) - MAX_PUBLIC_FINDINGS} more, in the usage report.")
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
                        for finding in public[:MAX_PUBLIC_FINDINGS]
                    ],
                    "more": max(0, len(public) - MAX_PUBLIC_FINDINGS),
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
