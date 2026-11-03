"""One progress line for a long step that runs with its stdout redirected: the elapsed time and the memory so far.

parity_lane.py sends each family's console to a file, so nothing a family prints reaches the job log. Build-reference
run 5's `graph` group (38971424159) printed nothing for 60 minutes and then the runner was lost, with no line saying
which step it was in or how much memory it held. These lines go to the process's own stdout (sys.__stdout__), past
any redirect, and carry what tells a slow step from one exhausting the machine, as export_nearby_trails.py's
_progress() does for its own passes.
"""

from __future__ import annotations

import resource
import sys
import time
from pathlib import Path

STARTED = time.monotonic()


def rss_mb() -> float | None:
    """This process's resident memory now, in MB, from /proc; None where there is no /proc."""
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        return None
    return None


def line(step: str) -> str:
    """`step` with the time since this module was imported, the resident memory now, this process's peak, and the
    largest peak of any child process it has waited for (ru_maxrss is KiB on Linux)."""
    now = rss_mb()
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    children = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
    rss = "unknown" if now is None else f"{now:,.0f} MB"
    return f"[{time.monotonic() - STARTED:7.1f}s] {step} (rss {rss}, peak {peak:,.0f} MB, child peak {children:,.0f} MB)"


def report(step: str) -> None:
    """line(step) on the process's own stdout, whatever sys.stdout has been redirected to."""
    out = sys.__stdout__ or sys.stdout
    print(line(step), file=out, flush=True)
