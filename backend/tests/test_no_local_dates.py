"""Nothing under app/ reads the machine's calendar or an offset-less clock.

#1939 — Take backend dates from UTC, and fix two stale comments: this API
stores naive UTC (app/core/time.py's utc_now(); tests/test_column_conventions.py's
header), and ten `date.today()` calls in four routers and two schemas read the
calendar of whatever machine runs the process - a laptop in New York, a
container in Render's region, CI's runner - three different days for a few
hours every night. #1939 moved each to `utc_now().date()` and landed with no
test, so the next route written from an older route's shape brings
`date.today()` straight back. This file is the test that stops it;
test_routers_work_projects.py's
test_get_workdays_bounds_both_ends_of_its_window_by_utc_date_at_eleven_pm_new_york_time
holds one route's behaviour with a set clock.

WHAT IS SCANNED: every call in every .py under backend/app, read as syntax
(ast), so a comment or a docstring that names `date.today()` to say "never
this" does not count - two routers carry exactly that comment. Flagged: a
`.today()` or `.utcnow()` on a name ending in `date` or `datetime` (so an
alias such as `dt.date.today()` is caught), and a `datetime.now(...)` whose
zone, first argument or `tz=`, is not `timezone.utc` or `UTC` under any
module prefix - so `datetime.now()`, `datetime.now(tz=None)` and
`datetime.now(ZoneInfo("America/New_York"))` are all flagged. app/core/time.py is
the one module allowed, because its `datetime.now(timezone.utc)` is what
utc_now() is made of; the five schemas that call `datetime.now(timezone.utc)`
themselves (closure, field_note, report, trail_challenge, volunteer_hours,
counted 2026-11-04) pass on their argument, as an aware now is the same
instant wherever it runs.

OUT OF SCOPE, and said here rather than left to be found: backend/scripts/.
check_openapi_compat.py:508 reads `dt.date.today()` as the default for a
`--today` an operator may pass, and the scripts run under a person at a
terminal, not under a route a phone calls at 23:00 New York time. Whether a
script's calendar should be UTC too is a separate decision; this scan does
not make it.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
#: utc_now()'s own home - the one `datetime.now(timezone.utc)` every other module should read through.
ALLOWED = (APP / "core" / "time.py",)
#: The zones an aware now may name, as written: `timezone.utc`, `UTC`, or either under a module (`dt.timezone.utc`).
UTC_ZONES = ("timezone.utc", "UTC")


def _dotted(node: ast.expr) -> str | None:
    """`date.today`, `dt.datetime.now` - a call's callee as the dotted name it was written as, or None."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _names_utc(call: ast.Call) -> bool:
    """Whether a `datetime.now(...)` call's zone - its first argument, else its `tz=` - is UTC as written."""
    zone = call.args[0] if call.args else next((keyword.value for keyword in call.keywords if keyword.arg == "tz"), None)
    if zone is None:
        return False
    written = ast.unparse(zone)
    return any(written == name or written.endswith(f".{name}") for name in UTC_ZONES)


def local_reads(source: str) -> list[tuple[int, str]]:
    """Every (line, call) in `source` that reads the machine's calendar or a naive now, in line order."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        name = _dotted(node.func)
        if name is None or "." not in name:
            continue
        owner, method = name.rsplit(".", 1)
        owner = owner.rsplit(".", 1)[-1]
        if owner not in ("date", "datetime"):
            continue
        if method in ("today", "utcnow"):
            found.append((node.lineno, ast.unparse(node)))
        elif method == "now" and owner == "datetime" and not _names_utc(node):
            found.append((node.lineno, ast.unparse(node)))
    return sorted(found)


def _modules() -> list[Path]:
    return sorted(path for path in APP.rglob("*.py") if path not in ALLOWED)


def test_no_module_under_app_reads_date_today_or_a_naive_now():
    """Named per offender in the message, so a red run says which file and line to send through utc_now()."""
    modules = _modules()
    assert len(modules) > 50 and any(path.name == "work_projects.py" for path in modules), "the scan found no app"
    offenders = [
        f"{path.relative_to(APP.parent)}:{line}: {call}"
        for path in modules
        for line, call in local_reads(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], "read the date through app.core.time.utc_now() (#1939), not the machine's calendar"


def test_the_scan_catches_each_shape_and_lets_an_aware_now_through():
    """The rule held to itself, so a loosened scan cannot pass every module by passing everything."""
    flagged = "\n".join(
        [
            "today = date.today()",
            "then = dt.date.today()",
            "stamp = datetime.today()",
            "stamp = datetime.utcnow()",
            "stamp = datetime.now()",
            "stamp = dt.datetime.now(tz=None)",
            "stamp = datetime.now(ZoneInfo('America/New_York'))",
            "stamp = datetime.now(tz=eastern)",
            "stamp = datetime.now(not_utc.timezone)",
        ]
    )
    assert [call for _, call in local_reads(flagged)] == [
        "date.today()",
        "dt.date.today()",
        "datetime.today()",
        "datetime.utcnow()",
        "datetime.now()",
        "dt.datetime.now(tz=None)",
        "datetime.now(ZoneInfo('America/New_York'))",
        "datetime.now(tz=eastern)",
        "datetime.now(not_utc.timezone)",
    ]
    allowed = "\n".join(
        [
            "now = datetime.now(timezone.utc)",
            "now = datetime.now(tz=timezone.utc)",
            "now = datetime.now(UTC)",
            "now = datetime.now(tz=datetime.UTC)",
            "now = dt.datetime.now(dt.timezone.utc)",
            "today = utc_now().date()",
            "# utc_now().date(), never date.today(): the comment two routers carry",
            '"""A docstring that says date.today() to say never."""',
        ]
    )
    assert local_reads(allowed) == []
