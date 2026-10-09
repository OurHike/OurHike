"""The backend's one logger and its request id (#1759) - app/core/logs.py."""

import json
import logging

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.logs import REQUEST_ID_HEADER, JsonFormatter, RequestIdMiddleware, configure_logging, current_request_id
from app.core.registry_pr import RegistryPrRefused
from app.models.club import OrgState
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
def lines():
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


def test_a_403_and_a_200_are_not_logged(small_app, lines):
    small_app.get("/ok")
    small_app.get("/forbidden")

    assert [entry for entry in lines if entry["logger"] == "app.request"] == []


def test_the_real_app_exposes_the_id_header_to_a_browser(client):
    response = client.get("/health", headers={"Origin": "https://ourhike.org"})

    assert REQUEST_ID_HEADER.lower() in response.headers
    assert REQUEST_ID_HEADER in response.headers["access-control-expose-headers"]


def test_a_failed_account_deletion_logs_its_cause(client, db_session, monkeypatch, lines):
    import app.routers.profiles as router_module

    profile = make_profile(db_session)
    _furnish(db_session, profile.id)

    def explode(self):
        raise RuntimeError("a constraint the deletion did not expect")

    monkeypatch.setattr(router_module.Session, "commit", explode, raising=False)

    response = client.delete("/profiles/me", headers=auth_headers(profile.id))

    assert response.status_code == 500
    (line,) = [entry for entry in lines if entry["logger"] == "app.routers.profiles"]
    assert line["level"] == "ERROR"
    assert "a constraint the deletion did not expect" in line["exception"]
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
