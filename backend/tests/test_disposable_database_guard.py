"""The suite refuses to wipe a database that is not named as disposable.

`conftest.py`'s isolation model is "drop every table in whatever database
DATABASE_URL names, before and after each test". The test database differs
from the dev default in `app/config.py` by four characters, so one stray
export is all that separates a test run from emptying `ourhike_dev` (#320).
The `_test` naming convention is the only marker of disposability, and
`_require_disposable_database` is the guard that makes the convention load-
bearing. These tests are what keep the guard from silently becoming a no-op.
"""

from __future__ import annotations

import pytest

from tests.conftest import _require_disposable_database

SERVER = "postgresql+psycopg://ourhike:ourhike@localhost:5432"


def test_the_test_database_passes():
    """The name every setup path produces - local script, CI service, default."""
    _require_disposable_database(f"{SERVER}/ourhike_test")


def test_the_dev_default_is_refused():
    """The database app/config.py defaults to is the one stray export away.

    This is the concrete accident the guard exists for, so it is pinned by
    name rather than left to the generic case below.
    """
    with pytest.raises(RuntimeError, match="_test"):
        _require_disposable_database(f"{SERVER}/ourhike_dev")


def test_an_arbitrary_database_is_refused():
    with pytest.raises(RuntimeError, match="_test"):
        _require_disposable_database(f"{SERVER}/production")


def test_a_url_naming_no_database_is_refused():
    """No name means connecting to whatever the server defaults to.

    That database is by definition not one anybody marked disposable, so the
    guard treats absent the same as wrong rather than letting it through.
    """
    with pytest.raises(RuntimeError, match="_test"):
        _require_disposable_database(f"{SERVER}/")


def test_the_refusal_says_what_to_set_instead():
    """A guard that only says no strands whoever hits it.

    The message must name the variable and a working value - that is the
    "about three lines" plus the part #320 actually asked for.
    """
    with pytest.raises(RuntimeError, match="DATABASE_URL") as excinfo:
        _require_disposable_database(f"{SERVER}/ourhike_dev")
    assert "ourhike_test" in str(excinfo.value)
    assert "local-postgres.sh" in str(excinfo.value)
