"""The real dbt_utils, for SQLFluff: each macro rendered from the installed package's own files.

SQLFluff lints with its jinja templater (pipeline/.sqlfluff says why it cannot
use the dbt one on dbt 2), and the jinja templater knows no package macros. A
model calling `dbt_utils.generate_surrogate_key` fails to render without help.
This module is that help, and it copies nothing from dbt_utils. `library_path`
in pipeline/.sqlfluff makes this file the `dbt_utils` namespace, and each
attribute looks up the macro of that name in `dbt_packages/dbt_utils/macros/`,
the package `dbt deps` installed from packages.yml. It then renders the
package's own source with jinja2. So the SQL SQLFluff lints is the SQL dbt
compiles: measured 2026-10-01, every staging model's key line rendered here
equal, character for character, to dbt 2.0.6's compiled output.

The maintainer, on the hand-written stand-in this file used to be: "Get the
actual dbt_utils package. Dont reinvent the wheel." The package is the wheel.
What is left here is dbt's side of the axle, the four built-ins dbt_utils'
macros call and dbt supplies at run time:

    adapter.dispatch    the project's macros first, as dbt_project.yml's
                        dispatch block orders it (duckdb__deduplicate is
                        there), then dbt_utils' duckdb__ and default__
    dbt.type_string     TEXT, dbt's string type on DuckDB
    dbt.hash, dbt.concat  md5(cast(... as TEXT)) and ||, as dbt writes them

`var` reads dbt_project.yml's `vars:`. A macro raising through `return()` is
caught the way dbt catches it. Generic tests (the `{% test %}` tag, dbt's own)
are skipped, because no model calls one.

It needs the packages installed: lint runs after `dbt deps`, in CI and in
scripts/test.sh. Without them, every model fails to render with this file's
message rather than with a jinja one.
"""

from pathlib import Path

import jinja2
import yaml

DBT_DIR = Path(__file__).resolve().parent.parent
PACKAGE_MACROS = DBT_DIR / "dbt_packages" / "dbt_utils" / "macros"
PROJECT_MACROS = DBT_DIR / "macros"


class _Return(Exception):
    """dbt's `return()`: a macro hands back a value by raising it."""

    def __init__(self, value):
        self.value = value


def _return(value):
    raise _Return(value)


class _Dbt:
    """dbt's cross-database built-ins, as dbt 2.0.6 renders them on DuckDB."""

    @staticmethod
    def type_string():
        return "TEXT"

    @staticmethod
    def hash(field):
        return f"md5(cast({field} as TEXT))"

    @staticmethod
    def concat(fields):
        return " || ".join(fields)


class _Macros:
    """Every macro in the project and in dbt_utils, rendered on demand."""

    def __init__(self):
        if not PACKAGE_MACROS.is_dir():
            raise RuntimeError(
                f"{PACKAGE_MACROS} is missing: run `dbt deps` in pipeline/dbt before SQLFluff, "
                "which renders dbt_utils from the installed package"
            )
        project = yaml.safe_load((DBT_DIR / "dbt_project.yml").read_text())
        self.vars = {k: v for k, v in (project.get("vars") or {}).items() if not isinstance(v, dict)}
        self.env = jinja2.Environment(extensions=["jinja2.ext.do"])
        self.project, self.package = self._load(PROJECT_MACROS), self._load(PACKAGE_MACROS)

    def _load(self, folder: Path) -> dict:
        found = {}
        context = {"adapter": self, "dbt": _Dbt(), "var": self.var, "return": _return}
        for path in sorted(folder.rglob("*.sql")):
            text = path.read_text()
            if "{% test " in text or "{%- test " in text:
                continue
            module = self.env.from_string(text).make_module(context)
            found.update({name: getattr(module, name) for name in dir(module) if not name.startswith("_")})
        return found

    def var(self, name, default=None):
        return self.vars.get(name, default)

    def dispatch(self, name, macro_namespace=None):
        """dbt's search: the project's adapter macro, then the package's, then the package's default."""
        for macros, candidate in (
            (self.project, f"duckdb__{name}"),
            (self.package, f"duckdb__{name}"),
            (self.package, f"default__{name}"),
        ):
            if candidate in macros:
                return lambda *args, **kwargs: self.call(macros[candidate], *args, **kwargs)
        raise AttributeError(f"dbt_utils has no {name} for DuckDB, and no default")

    @staticmethod
    def call(macro, *args, **kwargs):
        try:
            return str(macro(*args, **kwargs))
        except _Return as returned:
            return returned.value


_MACROS = None


def __getattr__(name):
    global _MACROS
    if name.startswith("__"):
        raise AttributeError(name)
    if _MACROS is None:
        _MACROS = _Macros()
    if name not in _MACROS.package:
        raise AttributeError(f"dbt_utils has no macro {name!r}")
    return lambda *args, **kwargs: _MACROS.call(_MACROS.package[name], *args, **kwargs)
