"""The release gate must start with three pure-Python packages (#845).

`verify_release.py` reads a published release over plain HTTPS, holds no
credentials, and `.github/workflows/verify-release.yml` installs exactly
`requests pyyaml pmtiles` for it. That is deliberate and its own docstring
says so: it "reads a bucket over HTTP and must run with three pure-Python
packages installed".

WHY THIS TEST EXISTS RATHER THAN THE RULE BEING LEFT AS PROSE

The rule has now been broken twice, by two different constants, and the
failure is total both times - the gate does not run a single check, it dies
on an import before `main()` is entered.

  #514  `DROP_THRESHOLD` was read from check_output_quality.py, which has
        DuckDB and GDAL behind it. Fixed by moving the constant to
        lib/completeness.py, "a module whose only import is `sys`".

  #845  `COMPRESSIBLE_TYPES` was read from publish.py, which imports boto3
        because uploading is its job. `smoke_published.py` imported it and
        `verify_release.py` imports `smoke_published`, so the gate inherited
        boto3 transitively. Every dispatch failed with `ModuleNotFoundError:
        No module named 'boto3'` from the moment that landed until this.

Both were one constant reached through a heavy module, and neither was
caught by any suite: the pipeline suite installs everything, so the import
resolves there and the gate is the only place it does not. A test that
installs everything can never catch this, which is why this one takes the
dependencies away instead.

HOW IT WORKS, AND ITS ONE LIMIT

A `None` entry in `sys.modules` makes `import x` raise ImportError, so the
subprocess below imports the gate with the heavy packages made unavailable
without needing a second virtualenv. It runs in a subprocess because the
import graph is cached per-process and this suite has already imported most
of it by the time this file runs.

The limit, stated rather than discovered later: the blocklist is a list of
the heavy packages this pipeline actually uses, not a proof that only the
three installed packages are reachable. A module importing some fourth
third-party package that happens to be installed here would pass this and
still fail the gate. Deriving the allowed set from the workflow instead
would need a resolver for what is pure-Python, which is a bigger thing than
the failure warrants - the blocklist catches both real recurrences and any
that go through the same modules.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PIPELINE = Path(__file__).resolve().parents[1]

# What the gate cannot have, because the workflow does not install it. Every
# one of these is imported at module scope by something in this directory.
HEAVY = ("boto3", "botocore", "duckdb", "rasterio", "pyproj", "shapely", "numpy", "pandas")

# The modules the gate's workflow actually runs, and the one it imports.
# `smoke_published` is listed in its own right because it is where #845's
# import landed - verify_release only inherited it.
GATE_MODULES = ("verify_release", "smoke_published")


def _import_without_heavy(module: str) -> subprocess.CompletedProcess:
    script = f"import sys\nfor name in {HEAVY!r}:\n    sys.modules[name] = None\nimport {module}\n"
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=PIPELINE,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("module", GATE_MODULES)
def test_the_gate_imports_without_the_heavy_packages(module):
    result = _import_without_heavy(module)

    assert result.returncode == 0, (
        f"`import {module}` needs a package the release gate does not have.\n\n"
        f"{result.stderr.strip()}\n\n"
        ".github/workflows/verify-release.yml installs only `requests pyyaml pmtiles`, so this "
        "import failure means `verify_release.py` cannot start at all and no check runs - the "
        "same total failure as #514 and #845. Move whatever is being imported into a pure module "
        "under lib/ (lib/completeness.py and lib/content_types.py are the two that already exist "
        "for exactly this) rather than adding the package to the workflow: the gate holds no "
        "credentials on purpose, and boto3 is how it would get them."
    )


def test_the_guard_would_actually_fail():
    """Proves the blocking works, rather than the test passing because
    `sys.modules[name] = None` quietly does nothing - which would make every
    assertion above vacuous."""
    result = _import_without_heavy("publish")

    assert result.returncode != 0, "publish.py imports boto3, so blocking boto3 must make it fail"
    assert "boto3" in result.stderr
