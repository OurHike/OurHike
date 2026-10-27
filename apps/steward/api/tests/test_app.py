import httpx
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from conftest import ORIGIN, bearer
from sqlalchemy import create_engine

from steward_api import limits
from steward_api.clubs import ClubDirectory, ClubsUnavailable, fetch_clubs
from steward_api.models import Base


def test_health_answers_without_sign_in(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_no_interactive_docs_or_schema_are_served(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_the_web_app_s_origin_may_call_the_api_and_another_origin_may_not(client):
    allowed = client.options(
        "/lists",
        headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization"},
    )
    assert allowed.headers.get("access-control-allow-origin") == ORIGIN
    refused = client.options("/lists", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in refused.headers


def test_a_body_past_the_limit_is_refused_before_it_is_read(client):
    response = client.post(
        "/lists", content=b"x" * (limits.MAX_BODY_BYTES + 1), headers={**bearer("a"), "Content-Type": "application/json"}
    )
    assert response.status_code == 413


def test_the_migrations_build_exactly_the_tables_the_models_describe(database_url):
    engine = create_engine(database_url)
    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata)
    engine.dispose()
    assert differences == []


def _transport(status=200, json=None, content=None):
    return httpx.MockTransport(lambda request: httpx.Response(status, json=json, content=content))


def test_fetch_clubs_reads_the_club_names_from_the_summary():
    summary = {"clubs": [{"club": "Example Trail Club"}, {"club": None}, {"club": "Second Example Club"}]}
    assert fetch_clubs("https://data.example/summary.json", _transport(json=summary)) == {
        "Example Trail Club",
        "Second Example Club",
    }


@pytest.mark.parametrize(
    ("url", "transport"),
    [
        ("http://data.example/summary.json", _transport(json={"clubs": [{"club": "x"}]})),
        ("https://data.example/summary.json", _transport(status=404, json={})),
        ("https://data.example/summary.json", _transport(content=b"not json")),
        ("https://data.example/summary.json", _transport(json={"clubs": []})),
        ("https://data.example/summary.json", _transport(status=302, json={})),
    ],
)
def test_fetch_clubs_refuses_anything_but_a_real_summary_over_https(url, transport):
    with pytest.raises(ClubsUnavailable):
        fetch_clubs(url, transport)


def test_the_club_directory_keeps_its_last_good_list_when_a_refresh_fails():
    now = [0.0]
    answers = [frozenset({"A"})]

    def load():
        if not answers:
            raise ClubsUnavailable("down")
        return answers.pop()

    directory = ClubDirectory(load, clock=lambda: now[0])
    assert directory.names() == {"A"}
    now[0] = 10_000
    assert directory.names() == {"A"}


def test_an_unset_summary_url_refuses_rather_than_accepting_any_club():
    with pytest.raises(ClubsUnavailable):
        ClubDirectory.from_url("").names()
