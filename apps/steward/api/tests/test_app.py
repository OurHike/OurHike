import httpx
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from conftest import ORIGIN, bearer
from sqlalchemy import create_engine

from steward_api import limits
from steward_api.analysis import Analysis, AnalysisDirectory, AnalysisUnavailable, fetch_analysis, parse_sites
from steward_api.models import Base


def test_health_answers_without_sign_in_and_checks_the_database(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_health_is_503_when_the_database_does_not_answer(database_url):
    from fastapi.testclient import TestClient

    from steward_api.config import Settings
    from steward_api.main import create_app

    broken = Settings(database_url="postgresql+psycopg://nobody:nothing@127.0.0.1:1/none_test", supabase_url="https://p.example")
    response = TestClient(create_app(broken)).get("/health")
    assert response.status_code == 503


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


SITES = [
    {"rims_id": "a", "club": "Example Trail Club", "action": "close_restore"},
    {"rims_id": "b", "club": "Second Example Club", "action": "harden"},
    {"rims_id": "c", "club": None, "action": "adopt_note"},
]


def test_the_analysis_names_its_clubs_its_sites_and_the_ones_that_need_work():
    analysis = fetch_analysis("https://data.example/sites.json", _transport(json=SITES))
    assert analysis == Analysis(
        clubs=frozenset({"Example Trail Club", "Second Example Club"}),
        sites=frozenset({"a", "b", "c"}),
        workable=frozenset({"a", "b"}),
    )


@pytest.mark.parametrize(
    ("url", "transport"),
    [
        ("http://data.example/sites.json", _transport(json=SITES)),
        ("https://data.example/sites.json", _transport(status=404, json={})),
        ("https://data.example/sites.json", _transport(content=b"not json")),
        ("https://data.example/sites.json", _transport(json=[])),
        ("https://data.example/sites.json", _transport(json={"clubs": []})),
        ("https://data.example/sites.json", _transport(status=302, json={})),
    ],
)
def test_the_analysis_is_refused_unless_it_is_a_real_sites_file_over_https(url, transport):
    with pytest.raises(AnalysisUnavailable):
        fetch_analysis(url, transport)


def test_a_sites_file_past_the_size_cap_is_refused_as_it_arrives(monkeypatch):
    from steward_api import analysis

    monkeypatch.setattr(analysis, "MAX_SITES_BYTES", 100)
    with pytest.raises(AnalysisUnavailable):
        fetch_analysis("https://data.example/sites.json", _transport(json=SITES * 10))


def test_the_directory_keeps_its_last_good_copy_and_does_not_retry_at_once_after_a_failure():
    # The review's finding 4: a failing source used to be refetched by every
    # request, one at a time under a lock.
    now = [0.0]
    loads = []
    good = parse_sites(SITES)

    def load():
        loads.append(now[0])
        if len(loads) == 1:
            return good
        raise AnalysisUnavailable("down")

    directory = AnalysisDirectory(load, clock=lambda: now[0])
    assert directory.current() == good
    now[0] = 10_000
    for _ in range(5):
        assert directory.current() == good
    assert len(loads) == 2
    now[0] = 10_000 + 61
    directory.current()
    assert len(loads) == 3


def test_an_unset_sites_url_refuses_rather_than_accepting_anything():
    with pytest.raises(AnalysisUnavailable):
        AnalysisDirectory.from_url("").current()
