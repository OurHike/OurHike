"""Everything `app/` imports at module scope is in the lockfile that deploys it.

This exists because it had already failed. `app/core/assist.py` imports
`httpx` on line 55, `requirements.in` lists `httpx`, and
`requirements.txt` - the compiled file a deploy actually installs from - did
not, because the `.in` was edited and `uv pip compile` was never re-run. The
sandbox never noticed: `httpx` was absent there too, and nothing imports
`app.core.assist` until a request reaches the assist router.

**The failure mode is the worst shape available.** Not a red suite, not a
failing request: the process dies at import, so the whole API is down rather
than one endpoint, and it happens at deploy rather than in review.

A lockfile is exactly the file nobody re-reads, so the check is here rather
than in anybody's habits.
"""

import ast
import sys
from pathlib import Path

import pytest
import tomllib

BACKEND = Path(__file__).resolve().parent.parent
APP = BACKEND / "app"

# Top-level module name -> the distribution that provides it. Hand-kept on
# purpose, and kept honest by `test_every_third_party_import_is_mapped`
# below: adding a dependency whose import name differs from its package name
# fails that test until somebody writes the pair down here, which is one line
# and the only moment the difference is in anybody's head.
#
# `importlib.metadata.packages_distributions()` would build this
# automatically and is the wrong tool: it reports what is installed in the
# environment running the tests, and the whole defect this file catches is a
# package that is NOT installed anywhere it would be seen.
DISTRIBUTION_OF: dict[str, str] = {
    "alembic": "alembic",
    "boto3": "boto3",
    "botocore": "botocore",
    "dotenv": "python-dotenv",
    "fastapi": "fastapi",
    "httpx": "httpx",
    "jwt": "pyjwt",
    "psycopg": "psycopg",
    "pydantic": "pydantic",
    "pydantic_settings": "pydantic-settings",
    "sqlalchemy": "sqlalchemy",
    "starlette": "starlette",
    "uvicorn": "uvicorn",
}

# Imported by `app/` but supplied by the test environment rather than the
# runtime: nothing under `app/` may import these outside a TYPE_CHECKING
# block or a test helper.
NEVER_AT_RUNTIME = {"pytest"}


def _own_modules() -> set[str]:
    """`app`, plus anything else this repository ships at the same level."""
    return {"app", "tests", "alembic_migrations"}


def _top_level_imports(path: Path) -> set[str]:
    """The root module of every import in one file, however it is spelled.

    Every import, not only the module-scope ones. A function-level import
    still fails - later, on the first call, which is worse than at start-up
    rather than better.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            # `from . import x` has no module and needs nothing installed.
            if node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    return found


def third_party_imports() -> set[str]:
    """What `app/` needs from PyPI, with stdlib and our own packages removed."""
    needed: set[str] = set()
    for path in sorted(APP.rglob("*.py")):
        needed |= _top_level_imports(path)
    return needed - sys.stdlib_module_names - _own_modules() - NEVER_AT_RUNTIME


def locked_distributions() -> set[str]:
    """The pinned names in requirements.txt, normalised the way PyPI does.

    Extras are dropped - `psycopg[binary]==3.3.5` locks `psycopg` - and so is
    case and the -/_/. spelling, per PEP 503.
    """
    text = (BACKEND / "requirements.txt").read_text(encoding="utf-8")
    names: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        name = line.split("==")[0].split(";")[0].split("[")[0].strip()
        if name:
            names.add(name.lower().replace("_", "-").replace(".", "-"))
    return names


def test_every_third_party_import_is_mapped():
    """A new dependency writes its import-name/package-name pair down here.

    The pair is only obvious while you are adding it. `import jwt` giving you
    `pyjwt` is the standing example, and a year later it is a puzzle.
    """
    unmapped = sorted(name for name in third_party_imports() if name not in DISTRIBUTION_OF)
    assert not unmapped, (
        f"app/ imports {unmapped}, which DISTRIBUTION_OF in this file does not name. "
        "Add the import-name -> package-name pair, then the check below can do its job."
    )


@pytest.mark.parametrize("module", sorted(third_party_imports()))
def test_import_is_in_the_lockfile(module: str):
    """The deploy installs requirements.txt, so requirements.txt decides.

    Parametrised rather than one assertion over a set so a failure names the
    one package that is missing, in the test's own name - the 2 a.m. test in
    CLAUDE.md's plain-language section.
    """
    distribution = DISTRIBUTION_OF[module]
    normalised = distribution.lower().replace("_", "-").replace(".", "-")
    assert normalised in locked_distributions(), (
        f"app/ imports `{module}`, provided by `{distribution}`, which is not pinned in "
        "backend/requirements.txt. Add it to requirements.in and re-run "
        "`uv pip compile --universal --python-version 3.11 backend/requirements.in "
        "-o backend/requirements.txt`. Without it the process dies at import on deploy."
    )


def test_requirements_in_is_a_subset_of_the_lockfile():
    """Editing the `.in` without recompiling is the exact defect above.

    A direct dependency named in `requirements.in` and absent from
    `requirements.txt` means the compile step was skipped, whether or not
    anything imports it yet.
    """
    declared: set[str] = set()
    for line in (BACKEND / "requirements.in").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split("[")[0].split(">")[0].split("<")[0].split("=")[0].strip()
        if name:
            declared.add(name.lower().replace("_", "-").replace(".", "-"))
    missing = sorted(declared - locked_distributions())
    assert not missing, (
        f"requirements.in declares {missing} and requirements.txt does not pin them - "
        "the lockfile is stale. Re-run `uv pip compile`."
    )


def test_the_lockfile_names_the_command_that_regenerates_it():
    """So the fix is in the file rather than in somebody's shell history."""
    header = (BACKEND / "requirements.txt").read_text(encoding="utf-8")[:400]
    assert "uv pip compile" in header


def test_pyproject_python_version_matches_the_compile_target():
    """The lockfile is universal, but it is resolved for one floor version.

    If `requires-python` ever moves above the `--python-version` the header
    records, the lockfile is resolved for a Python the backend no longer
    claims to support, and the mismatch is invisible until a wheel is wrong.
    """
    pyproject = BACKEND / "pyproject.toml"
    if not pyproject.exists():
        pytest.skip("backend has no pyproject.toml to disagree with the lockfile")
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    requires = data.get("project", {}).get("requires-python")
    if not requires:
        pytest.skip("backend/pyproject.toml pins no requires-python")
    header = (BACKEND / "requirements.txt").read_text(encoding="utf-8")[:400]
    floor = requires.lstrip(">=~^ ").split(",")[0].strip()
    assert f"--python-version {floor}" in header, (
        f"pyproject.toml requires Python {requires} but the lockfile header was compiled "
        f"for a different floor: {header.splitlines()[1] if len(header.splitlines()) > 1 else header!r}"
    )
