import httpx
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from conftest import ANALYSIS, ORIGIN, bearer
from sqlalchemy import create_engine, text

from steward_api import limits
from steward_api.analysis import Analysis, AnalysisDirectory, AnalysisUnavailable, fetch_analysis, parse_sites
from steward_api.models import Base


def test_health_answers_without_sign_in_and_checks_the_database(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_health_is_503_when_the_database_schema_is_behind_this_code(settings, monkeypatch):
    # The re-check's N3: code shipped before its migration answered healthy
    # while every signed-in request was a 500. No reuse of an answer here, so
    # the schema's change shows on the very next probe.
    from fastapi.testclient import TestClient

    from steward_api.main import create_app

    monkeypatch.setattr(limits, "HEALTH_CHECK_SECONDS", 0)
    app = create_app(settings, analysis=AnalysisDirectory.fixed(ANALYSIS))
    client = TestClient(app)
    with app.state.engine.begin() as connection:
        head = connection.execute(text("select version_num from alembic_version")).scalar()
        connection.execute(text("update alembic_version set version_num = '0002'"))
    try:
        response = client.get("/health")
        assert response.status_code == 503 and "run the migrations" in response.json()["status"]
    finally:
        with app.state.engine.begin() as connection:
            connection.execute(text("update alembic_version set version_num = :v"), {"v": head})
    assert client.get("/health").status_code == 200


class TestCachedCheck:
    """main.CachedCheck: the third pass's N6, an unauthenticated flood of
    /health probes answered 105 of 600 with 503 while the database was fine."""

    def test_reuses_its_answer_for_the_period_and_checks_again_after(self):
        from steward_api.main import CachedCheck

        now = [100.0]
        checks = []
        cached = CachedCheck(lambda: checks.append(1) or (200, "ok"), seconds=5, clock=lambda: now[0])
        assert [cached() for _ in range(50)] == [(200, "ok")] * 50
        assert len(checks) == 1
        now[0] += 5
        cached()
        assert len(checks) == 2

    def test_a_probe_during_a_slow_check_gets_the_last_answer_without_waiting(self):
        import threading

        from steward_api.main import CachedCheck

        now = [100.0]
        release = threading.Event()
        answers = iter([(200, "ok"), (503, "database unreachable")])

        def check():
            answer = next(answers)
            if answer[0] == 503:
                release.wait(5)
            return answer

        cached = CachedCheck(check, seconds=5, clock=lambda: now[0])
        assert cached() == (200, "ok")
        now[0] += 10
        slow = threading.Thread(target=cached)
        slow.start()
        while not cached._lock.locked():
            pass
        # The slow check holds the lock; this probe neither waits nor counts as down.
        assert cached() == (200, "ok")
        release.set()
        slow.join()
        assert cached() == (503, "database unreachable")

    def test_a_flood_of_probes_through_the_app_costs_one_query_and_never_a_503(self, app):
        from concurrent.futures import ThreadPoolExecutor

        from fastapi.testclient import TestClient

        client = TestClient(app)
        with ThreadPoolExecutor(max_workers=50) as pool:
            codes = list(pool.map(lambda _: client.get("/health").status_code, range(300)))
        assert set(codes) == {200}


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


def test_an_unexpected_error_while_loading_does_not_stop_later_loads():
    # The re-check's N4: anything but AnalysisUnavailable left the refresh flag
    # up for good, so nothing loaded again until a restart.
    now = [0.0]
    loads = []

    def load():
        loads.append(now[0])
        if len(loads) == 1:
            raise RecursionError("maximum recursion depth exceeded")
        return parse_sites(SITES)

    directory = AnalysisDirectory(load, clock=lambda: now[0])
    with pytest.raises(AnalysisUnavailable):
        directory.current()
    now[0] = 61
    assert directory.current().sites == {"a", "b", "c"}


def test_a_deeply_nested_sites_file_is_unavailable_not_a_crash():
    nested = "[" * 100_000 + "]" * 100_000
    with pytest.raises(AnalysisUnavailable):
        fetch_analysis("https://data.example/sites.json", _transport(content=nested.encode()))


def test_an_unset_sites_url_refuses_rather_than_accepting_anything():
    with pytest.raises(AnalysisUnavailable):
        AnalysisDirectory.from_url("").current()
