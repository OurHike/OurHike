"""Make a manifest's "path" name the same file regardless of which job wrote
it (#1265, split from #838 direction 2).

Every export script builds its output path from its own `Path(__file__).parent`
(absolute, for a directly-run script, since Python 3.9), then writes that
absolute string into its manifest. `publish.py` reads it back to open the
file. That only works when the writer and the reader share a filesystem -
true today only because build and publish are one GitHub Actions job.
`publish-vector-data.yml`'s header calls splitting them "a trap rather than
a design" for exactly that reason.

The fix is not "store it relative" on its own - export_club_sections.py
tried that once, and a relative path resolved against publish.py's CWD *at
invocation time* crashed any publish not started from pipeline/, mid-loop,
leaving a partial flat-key state published (#659). The fix is resolving
against `Path(__file__)`'s own directory instead of the process's CWD, the
same idiom `lib/fetch_receipts.py` already carries for receipts and
`check_output_quality.py`'s `_resolve_topo_local_path` for topo quads:
relative to PIPELINE_ROOT when the path is under it - every exporter's
output is - falling back to absolute otherwise, rather than a third,
differently-behaved variant of the same problem.
"""

from __future__ import annotations

from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parent.parent


def to_manifest_path(path: Path | str) -> str:
    """Write side. Relative to PIPELINE_ROOT (as_posix, matching
    fetch_receipts' recorded_path) when path is under it, else the absolute
    path unchanged."""
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(PIPELINE_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def from_manifest_path(path: str) -> Path:
    """Read side. A relative path - the convention above - resolves against
    this process's own pipeline/, so a manifest built by one job means the
    same file to another regardless of either one's CWD. An absolute path
    (the fallback above, or a manifest entry built directly rather than
    through to_manifest_path() - today only test fixtures) passes through
    unchanged."""
    p = Path(path)
    return p if p.is_absolute() else PIPELINE_ROOT / p
