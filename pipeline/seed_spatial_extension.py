"""Put DuckDB's spatial extension where `INSTALL spatial` looks, from PyPI.

`INSTALL spatial` is a live fetch from extensions.duckdb.org, and it is the one
standing exception to TESTING.md's "tests never touch the network" (#321). Two
places pay for that:

  - **CI**, on every cold runner. An extension-repo outage fails the pipeline
    suite and the dbt job for a reason that has nothing to do with the change
    under test - the definition of red-means-the-ecosystem rather than
    red-means-code that #321 was filed against.
  - **Web sessions**, where the sandbox proxy 403s that host outright, so the
    fetch cannot succeed at all.

DuckDB treats an already-installed extension as satisfying INSTALL, so copying
the build DuckDB publishes on PyPI into `~/.duckdb/extensions/...` means the
INSTALL never reaches the network. PyPI is reachable in both places; the
extension repo is unreliable in one and blocked in the other.

WHY THIS IS A FILE RATHER THAN A STEP IN EACH CALLER. It started as an inline
heredoc in `.claude/hooks/session-start.sh` and was about to be pasted into two
CI jobs. The logic is small but not obvious - it has to find the bundled
`.duckdb_extension` inside an installed distribution, ask DuckDB for its own
platform triple, and write to a path keyed by the exact DuckDB version - and
all three of those move when the duckdb pin moves. Three copies would drift on
the next bump; this is the one home CONTRIBUTING.md asks for.

**The version is not a parameter.** Extensions are ABI-locked to the exact
DuckDB build, so the only correct answer is whatever `import duckdb` reports in
the interpreter doing the seeding - not what a requirements file says, which is
the same number only while nothing has overridden it. Callers install
`duckdb-extension-spatial` at the matching version; this script then verifies
they agree rather than assuming it.

Run:  python seed_spatial_extension.py
"""

from __future__ import annotations

import pathlib
import shutil
import sys
from importlib.metadata import PackageNotFoundError, distribution

import duckdb

PACKAGE = "duckdb-extension-spatial"
EXTENSION_FILE = "spatial.duckdb_extension"


def bundled_extension() -> pathlib.Path:
    """The `.duckdb_extension` inside the installed PyPI distribution."""
    try:
        dist = distribution(PACKAGE)
    except PackageNotFoundError:
        raise SystemExit(
            f"{PACKAGE} is not installed, so there is nothing to seed from. "
            f"Install it at duckdb's own version ({duckdb.__version__}) first - "
            "extensions are ABI-locked to the exact build."
        ) from None
    for entry in dist.files or ():
        if entry.name == EXTENSION_FILE:
            return pathlib.Path(dist.locate_file(entry))
    raise SystemExit(f"{PACKAGE} {dist.version} contains no {EXTENSION_FILE}")


def destination() -> pathlib.Path:
    """Where this DuckDB build looks before it reaches the network.

    The platform triple is asked of DuckDB rather than derived from
    `sys.platform`: it encodes libc and architecture in DuckDB's own spelling
    (`linux_amd64_gcc4` and friends), and a guess that is close but wrong
    produces a path INSTALL silently ignores - a seeding that reports success
    and changes nothing.
    """
    platform = duckdb.connect().execute("PRAGMA platform").fetchone()[0]
    return pathlib.Path.home() / ".duckdb/extensions" / f"v{duckdb.__version__}" / platform / EXTENSION_FILE


def seed() -> pathlib.Path:
    """Copy the bundled extension into place if it is not already there."""
    source = bundled_extension()
    target = destination()
    if not target.exists() or target.stat().st_size != source.stat().st_size:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return target


def verify() -> None:
    """Prove the seeding worked, rather than reporting that it ran.

    #822's lesson applied one file over: a provisioning step that exits 0
    without having achieved anything is how both of this repository's silent
    dependency outages happened. Loading the extension and running a spatial
    function is cheap and is the only thing that actually answers the question.
    """
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("SELECT ST_Point(0, 0)")


def main() -> int:
    installed = distribution(PACKAGE).version if _installed() else None
    if installed is not None and installed != duckdb.__version__:
        # Not fatal on its own - DuckDB may still accept it - but it is the
        # first thing to look at if the verify below fails, so it is said
        # before rather than guessed at afterwards.
        print(f"warning: {PACKAGE} {installed} against duckdb {duckdb.__version__} - these are meant to match")
    target = seed()
    verify()
    print(f"spatial loads offline for duckdb {duckdb.__version__} ({target})")
    return 0


def _installed() -> bool:
    try:
        distribution(PACKAGE)
    except PackageNotFoundError:
        return False
    return True


if __name__ == "__main__":
    sys.exit(main())
