"""Write the usage dashboard as one self-contained HTML file (#1902).

    DATABASE_URL=... python scripts/usage_report.py --out usage-report.html

The dashboard the maintainer chose on 2026-10-27: a Python script that writes
a single HTML file, in OurHike's style, filterable by date and by club. It
reads `analytics_months`, `analytics_monthly`, `analytics_users`,
`analytics_anomalies`, the newest `analytics_seal_keys` month, and - for the
data-quality panel's daily series - plain columns of `analytics_events`
(app/core/analytics_quality.py `load_arrivals`). Never `sealed`, so the
rollup's role, which can read every usage column but that one, is enough to
run it.

Every figure is masked before it is written into the file
(app/core/analytics_report.py): a count of fewer than 25 people is absent
from the HTML, not hidden by its script, so a copy forwarded to a club cannot
be read past the mask.

Write the file somewhere that is not this repository. It is a report about
real hikers, and a committed copy would be a permanent publication of it
(CONTRIBUTING.md, "Data does not go in commits").
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.analytics_report import DEFAULT_MONTHS, build_report_data  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

TEMPLATE = Path(__file__).resolve().with_name("usage_report.html")
PLACEHOLDER = "/*__USAGE_DATA__*/"


def render(data: dict) -> str:
    """The page with `data` in its JSON block.

    `</` is escaped so no value can close the script element early - a club id
    cannot contain one (app/schemas/analytics.py), and this does not rely on it.
    """
    payload = json.dumps(data, separators=(",", ":"), sort_keys=True).replace("</", "<\\/")
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count(PLACEHOLDER) != 1:
        raise RuntimeError(f"{TEMPLATE.name} must hold the data placeholder exactly once")
    return template.replace(PLACEHOLDER, payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True, help="The HTML file to write.")
    parser.add_argument(
        "--environment",
        default="Production",
        help="Which database this is, for the page's header (default: Production).",
    )
    parser.add_argument("--months", type=int, default=DEFAULT_MONTHS, help=f"How many months back (default {DEFAULT_MONTHS}).")
    args = parser.parse_args(argv)

    repository = Path(__file__).resolve().parents[2]
    if args.out.resolve().is_relative_to(repository):
        print(
            f"Refused: {args.out} is inside the repository. This file describes real hikers; write it elsewhere.",
            file=sys.stderr,
        )
        return 2

    with SessionLocal() as db:
        data = build_report_data(db, environment=args.environment, months=args.months)
    args.out.write_text(render(data), encoding="utf-8")
    print(f"Wrote {args.out} ({len(data['months'])} months, {len(data['clubs'])} clubs).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
