"""Shared "did this run actually produce complete output" gate.

A safety audit found the same bug pattern independently in 5 pipeline
scripts: a script finishes and reports success without ever checking that
what it produced is actually complete - a source can silently fail, a cell
can silently get skipped, a POI type can silently come back empty, and the
script exits 0 anyway, so nothing downstream (CI, a human watching logs) has
any signal that the output is missing data.

Two scripts already got this right, independently, with near-duplicate
inline code: spike_raster_mosaic.py's main() collects `skipped_cells` (every
corridor-intersecting grid cell that produced no tile) and fetch_all.py's
main() collects `missing`/`failures` (every registered source that didn't
fetch) - both then print a summary and `sys.exit(1)` if that list is
non-empty, so a broken run fails loudly (a script/CI exit code) instead of
quietly (an easy-to-miss log line). This module extracts that gate into one
place so the next 5 scripts that need it (e.g. export_poi.py, checking that
every registered POI type produced at least one feature) call a shared
helper instead of re-writing - and re-debugging - the same
collect-problems-then-exit logic a sixth time.
"""

import sys


def fail_if_incomplete(problems, *, label="Incomplete"):
    """Print every problem in `problems` and `sys.exit(1)` if it's
    non-empty - the exact gate spike_raster_mosaic.py and fetch_all.py each
    already had inline (as `skipped_cells` and `missing`/`failures`
    respectively) before this was extracted. A no-op if `problems` is empty,
    so callers can run this unconditionally at the end of main() rather than
    wrapping it in their own `if problems:` check."""
    if not problems:
        return
    print(f"{label}: {len(problems)} problem(s):")
    for problem in problems:
        print(f"  {problem}")
    sys.exit(1)


def count_problems(counts, minimums=None, default_minimum=1):
    """Problem strings for any name in `counts` whose count is below its
    expected minimum - e.g. export_poi.py's per-poi_type feature counts,
    where every type must be non-empty (the default minimum of 1) except
    ones that are legitimately allowed to come back empty for the real AT
    corridor data (`minimums={"crossing": 0}`).

    `minimums` overrides `default_minimum` per name; a name absent from
    `minimums` falls back to `default_minimum`. Returns a list of strings
    formatted `f"{name}: {count}, expected >= {minimum}"`, suitable for
    passing straight into `fail_if_incomplete()` as `problems`."""
    if minimums is None:
        minimums = {}
    problems = []
    for name, count in counts.items():
        minimum = minimums.get(name, default_minimum)
        if count < minimum:
            problems.append(f"{name}: {count}, expected >= {minimum}")
    return problems
