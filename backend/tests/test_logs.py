"""The backend's one logger and its request id (#1759) - app/core/logs.py."""

import json
import logging

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.logs import (
    REQUEST_ID_HEADER,
    DropUnloggedPaths,
    JsonFormatter,
    RequestIdMiddleware,
    configure_logging,
    current_request_id,
)
from app.core.registry_pr import RegistryPrRefused
from app.db.session import get_db
from app.main import app
from app.models.club import OrgState
from app.models.profile import Profile, Role
from tests.factories import make_admin, make_org, make_profile
from tests.test_account_deletion import _furnish
from tests.tokens import auth_headers


class _Collector(logging.Handler):
    """Holds formatted lines. caplog cannot: the `app` logger does not propagate."""

    def __init__(self):
        super().__init__()
        self.setFormatter(JsonFormatter())
        self.lines: list[dict] = []

    def emit(self, record):
        self.lines.append(json.loads(self.format(record)))


@pytest.fixture()
def lines(monkeypatch):
    # tests/test_migrations.py runs Alembic in this process, and
    # alembic/env.py's `fileConfig` sets `disabled` on every logger that
    # exists by then and that alembic.ini does not name - `app` and its
    # children included - so no record from them reaches any handler.
    # Measured 2026-10-20: with test_migrations.py first in the same process,
    # 4 of the 10 tests this file then held failed on an empty `lines`.
    # tests/test_report_photos.py meets the same trap by replacing the
    # logger's method, which would skip the JsonFormatter this file tests;
    # here the flag is cleared instead, and monkeypatch restores it.
    for name, existing in logging.root.manager.loggerDict.items():
        if isinstance(existing, logging.Logger) and (name == "app" or name.startswith("app.")):
            monkeypatch.setattr(existing, "disabled", False)
    collector = _Collector()
    logging.getLogger("app").addHandler(collector)
    yield collector.lines
    logging.getLogger("app").removeHandler(collector)


@pytest.fixture()
def small_app():
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/ok")
    def ok():
        return {"id": current_request_id()}

    @app.get("/denied")
    def denied():
        raise HTTPException(status_code=401)

    @app.get("/forbidden")
    def forbidden():
        raise HTTPException(status_code=403)

    @app.get("/boom")
    def boom():
        raise RuntimeError("boom")

    return TestClient(app, raise_server_exceptions=False)


def test_configure_logging_attaches_one_json_handler_however_often_it_is_called():
    configure_logging()
    configure_logging()

    handlers = [
        h for h in logging.getLogger("app").handlers if isinstance(h.formatter, JsonFormatter) and not isinstance(h, _Collector)
    ]
    assert len(handlers) == 1


def test_a_response_carries_the_id_the_handler_saw(small_app):
    response = small_app.get("/ok")

    assert response.headers[REQUEST_ID_HEADER] == response.json()["id"]
    assert len(response.json()["id"]) == 32


def test_a_caller_supplied_id_is_ignored(small_app):
    response = small_app.get("/ok", headers={REQUEST_ID_HEADER: "forged\nline"})

    assert response.headers[REQUEST_ID_HEADER] != "forged\nline"


def test_two_requests_get_two_ids(small_app):
    assert small_app.get("/ok").headers[REQUEST_ID_HEADER] != small_app.get("/ok").headers[REQUEST_ID_HEADER]


def test_a_401_is_logged_with_the_id_the_hiker_was_given(small_app, lines):
    response = small_app.get("/denied?token=secret-value")

    (line,) = [entry for entry in lines if entry["logger"] == "app.request"]
    assert line["message"] == "GET /denied -> 401"
    assert line["request_id"] == response.headers[REQUEST_ID_HEADER]
    assert "secret-value" not in json.dumps(line)


def test_an_unhandled_error_is_logged_as_a_500(small_app, lines):
    small_app.get("/boom")

    assert [entry["message"] for entry in lines if entry["logger"] == "app.request"] == ["GET /boom -> 500"]


def test_an_unhandled_error_s_500_carries_the_x_request_id_that_was_logged(small_app, lines):
    # Starlette's ServerErrorMiddleware writes this 500 from outside every
    # added middleware; before RequestIdMiddleware answered it itself, the
    # response had no X-Request-Id at all.
    response = small_app.get("/boom")

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
    (line,) = [entry for entry in lines if entry["logger"] == "app.request"]
    assert response.headers[REQUEST_ID_HEADER] == line["request_id"]


def test_the_real_app_s_crash_500_carries_x_request_id(monkeypatch, lines):
    # The real stack - CORS and the body limit inside RequestIdMiddleware,
    # ServerErrorMiddleware outside it - rather than small_app's one layer.
    def database_that_crashes():
        raise RuntimeError("an exception no handler expects")

    monkeypatch.setitem(app.dependency_overrides, get_db, database_that_crashes)
    crashing = TestClient(app, raise_server_exceptions=False)

    response = crashing.get("/closures")

    assert response.status_code == 500
    (line,) = [entry for entry in lines if entry["logger"] == "app.request"]
    assert line["message"] == "GET /closures -> 500"
    assert response.headers[REQUEST_ID_HEADER] == line["request_id"]


def test_a_403_and_a_200_are_not_logged(small_app, lines):
    small_app.get("/ok")
    small_app.get("/forbidden")

    assert [entry for entry in lines if entry["logger"] == "app.request"] == []


def test_the_real_app_exposes_the_id_header_to_a_browser(client):
    response = client.get("/health", headers={"Origin": "https://ourhike.org"})

    assert REQUEST_ID_HEADER.lower() in response.headers
    assert REQUEST_ID_HEADER in response.headers["access-control-expose-headers"]


def test_a_failed_account_deletion_logs_its_cause_by_class_and_not_its_text(client, db_session, monkeypatch, lines):
    import app.routers.profiles as router_module

    profile = make_profile(db_session)
    _furnish(db_session, profile.id)

    def explode(self):
        raise RuntimeError("free text nobody has read")

    monkeypatch.setattr(router_module.Session, "commit", explode, raising=False)

    response = client.delete("/profiles/me", headers=auth_headers(profile.id))

    assert response.status_code == 500
    (line,) = [entry for entry in lines if entry["logger"] == "app.routers.profiles"]
    assert line["level"] == "ERROR"
    assert line["message"] == "account deletion failed at commit; rolled back: RuntimeError"
    assert "free text nobody has read" not in json.dumps(line)
    assert line["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_a_failed_account_deletion_logs_the_constraint_and_not_the_row(client, db_session, monkeypatch, lines):
    """A real Postgres unique violation at commit, through the real handler.

    str() of the IntegrityError this raises carries `[parameters: ...]` - the
    colliding row's id and display name - and its psycopg cause carries
    `DETAIL: Key (id)=(...) already exists`. Neither may reach the line.
    """
    import app.routers.profiles as router_module

    profile = make_profile(db_session)
    _furnish(db_session, profile.id)
    taken = make_profile(db_session, display_name="Pat Q. Hiker")
    delete_for_real = router_module.delete_account

    def delete_then_collide(db, current_user, *args, **kwargs):
        summary = delete_for_real(db, current_user, *args, **kwargs)
        # Flushed by the handler's db.commit(), so it fails there.
        db.add(Profile(id=taken.id, role=Role.hiker, display_name="Pat Q. Hiker"))
        return summary

    monkeypatch.setattr(router_module, "delete_account", delete_then_collide)

    response = client.delete("/profiles/me", headers=auth_headers(profile.id))

    assert response.status_code == 500
    (line,) = [entry for entry in lines if entry["logger"] == "app.routers.profiles"]
    assert line["message"] == (
        "account deletion failed at commit; rolled back: "
        "IntegrityError UniqueViolation sqlstate=23505 constraint=profiles_pkey table=profiles"
    )
    assert "exception" not in line
    assert taken.id not in json.dumps(line)
    assert "Pat Q. Hiker" not in json.dumps(line)
    assert line["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_a_refused_registry_pull_request_is_logged_for_the_operator(client, db_session, monkeypatch, lines):
    def refuse(*args, **kwargs):
        raise RegistryPrRefused("GitHub refused PUT /repos/x (401).")

    monkeypatch.setattr("app.routers.org_registry.open_registry_pr", refuse)
    org = make_org(db_session, state=OrgState.claimed)
    people = [make_profile(db_session) for _ in range(3)]
    for person in people:
        make_admin(db_session, org, person, is_codeowner=True)
    for person in people:
        client.post(f"/clubs/{org.slug}/registry/signoff", headers=auth_headers(person.id))

    (line,) = [entry for entry in lines if entry["logger"] == "app.routers.org_registry"]
    assert line["level"] == "WARNING"
    assert "(401)" in line["message"]


# --- Uvicorn's access line ---------------------------------------------------------


def _access_record(path: str) -> logging.LogRecord:
    """An access record exactly as Uvicorn 0.54 makes one (h11_impl.py, httptools_impl.py)."""
    args = ("203.0.113.7:51234", "POST", path, "1.1", 202)
    return logging.LogRecord("uvicorn.access", logging.INFO, __file__, 0, '%s - "%s %s HTTP/%s" %d', args, None)


@pytest.mark.parametrize("path", ["/usage-events", "/usage-events?retry=1", "/usage-events/"])
def test_the_access_line_for_usage_events_is_dropped(path):
    """It opens with the client's address, which POST /usage-events promises
    never to keep beside a count."""
    assert DropUnloggedPaths().filter(_access_record(path)) is False


@pytest.mark.parametrize("path", ["/health", "/usage-events-elsewhere", "/profiles/me"])
def test_every_other_access_line_is_kept(path):
    assert DropUnloggedPaths().filter(_access_record(path)) is True


def test_a_record_of_another_shape_is_let_through():
    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 0, "Started", (), None)

    assert DropUnloggedPaths().filter(record) is True


def test_the_running_app_drops_the_line_on_uvicorns_own_logger(monkeypatch):
    """Through the logger Uvicorn writes to, as importing the app configures it.
    Alembic's fileConfig can disable that logger in this process (the `lines`
    fixture above has the story), and Uvicorn's own config is what sets INFO."""
    access = logging.getLogger("uvicorn.access")
    monkeypatch.setattr(access, "disabled", False)
    previous = access.level
    access.setLevel(logging.INFO)
    seen: list[str] = []

    class Seen(logging.Handler):
        def emit(self, record):
            seen.append(record.getMessage())

    handler = Seen()
    access.addHandler(handler)
    try:
        for path in ("/usage-events", "/health"):
            access.info('%s - "%s %s HTTP/%s" %d', "203.0.113.7:51234", "POST", path, "1.1", 202)
    finally:
        access.removeHandler(handler)
        access.setLevel(previous)

    assert seen == ['203.0.113.7:51234 - "POST /health HTTP/1.1" 202']
