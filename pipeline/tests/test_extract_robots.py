"""extract/_robots.py: each origin's robots.txt, read once a run and obeyed by every request the extract sends.

Review of PR #1805 — dlt → dbt re-platform as one go/no-go change, finding 2: robots.txt was read when a source was
registered and never again, except by extract/_geofabrik.py, so a Disallow or a longer Crawl-delay a host added later
was not obeyed. Every test here runs a reader's session through requests_mock under conftest.py's socket guard, and the
module is marked `robots_txt_read`, so its origins answer robots.txt through requests_mock rather than with
conftest.py's no-rules default. Each test fails on the code before extract/_robots.py but the decision-85 one, which
holds a ruling the rule must leave alone and passes either side of it.
"""

from __future__ import annotations

import json

import duckdb
import pytest
import requests

from extract import _kinds, _notices
from extract._run import make_pipeline, run_pipeline
from extract._warehouse import load_warehouse
from lib import http_retry
from tests.test_extract_run import AGOL, CLOSURES_URL, LINES_URL, FakeLayer, closures, feature, lines

pytestmark = pytest.mark.robots_txt_read

HOST = "https://trails.example.org"
ROBOTS = f"{HOST}/robots.txt"


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """A sources.json holding the two layers tests/test_extract_run.py mocks, in place of the real one."""
    path = tmp_path / "sources.json"
    layers = [{"key": "trails", "url": LINES_URL}, {"key": "closures_layer", "url": CLOSURES_URL}]
    path.write_text(json.dumps({"sources": layers}))
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()
    yield path
    _kinds._registry.cache_clear()


@pytest.fixture
def store(tmp_path):
    return {"bucket_url": (tmp_path / "raw-store").as_uri(), "pipelines_dir": str(tmp_path / "pipelines")}


def _robots():
    """extract/_robots.py, imported in each test, so a tree without it fails test by test rather than at collection."""
    from extract import _robots as module

    return module


def _asked(requests_mock) -> list[str]:
    return [request.url for request in requests_mock.request_history]


@pytest.fixture
def clock(monkeypatch):
    """The per-host gate's clock, moved only by its pauses, which are recorded; every host's gate starts unused."""
    now, paused = [1000.0], []

    def pause(seconds):
        paused.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(_notices, "_GATES", {})
    monkeypatch.setattr(_notices, "_now", lambda: now[0])
    monkeypatch.setattr(_notices, "_pause", pause)
    return paused


def test_a_url_robots_txt_disallows_is_refused_unsent_and_robots_txt_is_read_once_a_run(requests_mock):
    requests_mock.get(ROBOTS, text="User-agent: *\nDisallow: /private/\n")
    requests_mock.get(f"{HOST}/public/a", text="a")
    requests_mock.get(f"{HOST}/private/b", text="b")

    assert _kinds.session().get(f"{HOST}/public/a").text == "a"
    with pytest.raises(requests.RequestException, match="disallowed for OurHike"):
        _kinds.session().get(f"{HOST}/private/b")
    _kinds.session().get(f"{HOST}/public/a")

    assert _asked(requests_mock) == [ROBOTS, f"{HOST}/public/a", f"{HOST}/public/a"], "robots.txt once, /private/ never"
    _robots().forget()  # what run_pipeline() does as each run starts
    _kinds.session().get(f"{HOST}/public/a")
    assert _asked(requests_mock)[-2:] == [ROBOTS, f"{HOST}/public/a"], "the next run reads robots.txt again"


def test_disallow_star_question_mark_refuses_the_query_that_params_would_add(requests_mock):
    """A reader passes its query as `params`, which requests appends after the URL the session is handed, so the check
    has to read the URL requests will send. `Disallow: /*?` is foothillstrail.org's rule (extract/_notices.py's
    QUERY_DISALLOWED_HOSTS)."""
    requests_mock.get(ROBOTS, text="User-agent: *\nDisallow: /*?\n")
    requests_mock.get(f"{HOST}/events", text="listing")
    http = _kinds.session()

    assert http.get(f"{HOST}/events").text == "listing"
    with pytest.raises(requests.RequestException, match=r"/events\?page=2 is disallowed"):
        http_retry.request_with_retry(f"{HOST}/events", session=http, params={"page": 2})
    assert _asked(requests_mock) == [ROBOTS, f"{HOST}/events"], "refused at once: not retried, never sent"


@pytest.mark.parametrize(
    ("rules", "path", "allowed"),
    [
        (["Disallow: /", "Allow: /api/"], "/api/x", True),  # the longest rule wins, wherever it stands
        (["Allow: /api/", "Disallow: /"], "/api/x", True),
        (["Disallow: /api/x", "Allow: /api/"], "/api/x", False),
        (["Disallow: /page", "Allow: /page"], "/page", True),  # a tie goes to the Allow
        (["Disallow: /*.pdf$"], "/a.pdf", False),
        (["Disallow: /*.pdf$"], "/a.pdf?x=1", True),  # `$` anchors the end of the whole URL
        (["Disallow: /calendar/action*"], "/calendar/action/x", False),  # bmta.org's and foothillstrail.org's rule
        (["Disallow: /calendar/action*"], "/calendar/x", True),
        (["Disallow:"], "/anything", True),  # an empty Disallow is no rule
        (["Disallow: /"], "/robots.txt", True),  # robots.txt itself is always allowed
        (["Disallow: /caf%C3%A9"], "/café", False),  # compared octet for octet
        (["Disallow: /%7Euser/"], "/~user/a", False),  # an escaped unreserved character is that character
    ],
)
def test_rfc_9309_matching_gives_one_answer_whatever_the_interpreter(rules, path, allowed):
    """CPython 3.12.3's urllib.robotparser allowed `/page?x=1` under `Disallow: /*?` and let the first rule win, where
    3.13.14 did neither (measured 2026-10-09); the extract jobs run on 3.12 and this suite on 3.13 and 3.14."""
    robots = _robots()
    parsed, _ = robots.parse("\n".join(["User-agent: *", *rules]))

    assert robots.Robots(parsed).allows(f"{HOST}{path}") is allowed


def test_the_group_naming_our_agent_is_obeyed_over_the_star_group_and_every_group_naming_it_is_merged():
    robots = _robots()
    text = (
        "User-agent: *\nDisallow: /\n\n"
        "User-agent: OurHike\nDisallow: /a/\nCrawl-delay: 4\n\n"
        "User-agent: SomeoneElse\nDisallow: /b/\n\n"
        "user-agent: ourhike/2.0  # a version and a comment, matched without case\nDisallow: /c/\n"
    )
    parsed, delay = robots.parse(text)
    read = robots.Robots(parsed, delay)

    assert [read.allows(f"{HOST}{path}") for path in ("/a/1", "/b/1", "/c/1", "/d/1")] == [False, True, False, True]
    assert delay == 4


def test_a_group_naming_our_whole_product_token_is_obeyed_over_one_naming_only_its_prefix():
    """USER_AGENT's product token is `OurHike-pipeline`; a group for `OurHike` names this project too, less closely."""
    robots = _robots()
    parsed, _ = robots.parse("User-agent: OurHike\nDisallow: /a/\n\nUser-agent: OurHike-pipeline\nDisallow: /b/\n")
    read = robots.Robots(parsed)

    assert robots.PRODUCT_TOKEN == "OurHike-pipeline"
    assert [read.allows(f"{HOST}{path}") for path in ("/a/1", "/b/1")] == [True, False]


def test_an_unreachable_robots_txt_refuses_its_own_origin_for_the_run_and_a_404_is_no_rules(requests_mock, monkeypatch):
    """RFC 9309: a server error or no answer is unreachable, read as disallowing everything (2.3.1.4), and a 4xx is
    no rules (2.3.1.3), as extract/_geofabrik.py chose before it read through extract/_robots.py."""
    monkeypatch.setattr(http_retry.time, "sleep", lambda seconds: None)
    other = "https://other.example.org"
    requests_mock.get(ROBOTS, status_code=503)
    requests_mock.get(f"{other}/robots.txt", status_code=404)
    requests_mock.get(f"{HOST}/a", text="a")
    requests_mock.get(f"{other}/a", text="b")
    http = _kinds.session()

    with pytest.raises(requests.RequestException, match="answered 503, read as disallowing every URL"):
        http.get(f"{HOST}/a")
    with pytest.raises(requests.RequestException, match="answered 503"):
        http.get(f"{HOST}/b")
    assert http.get(f"{other}/a").text == "b"
    assert _asked(requests_mock) == [ROBOTS] * 3 + [f"{other}/robots.txt", f"{other}/a"], "retried, then read once a run"


def test_polite_keeps_a_robots_txt_crawl_delay_longer_than_the_one_its_caller_asked(requests_mock, clock):
    """The registry's `crawl_delay` is what somebody read when the row was registered; the host asks 10 now."""
    requests_mock.get(ROBOTS, text="User-agent: *\nCrawl-delay: 10\n")
    requests_mock.get(f"{HOST}/a", text="a")
    http = _notices.polite(_kinds.session(), 2.0)

    http.get(f"{HOST}/a")
    http.get(f"{HOST}/a")

    assert clock == [10.0, 10.0], "the first counted from the robots.txt fetch, the second from the first request"


def test_a_session_nobody_made_polite_keeps_the_crawl_delay_robots_txt_asks(requests_mock, clock):
    """An ArcGIS layer's session has no gap of its own (extract/_kinds.py's session()), so robots.txt's is the only one."""
    requests_mock.get(ROBOTS, text="User-agent: OurHike\nCrawl-delay: 5\n")
    requests_mock.get(f"{HOST}/a", text="a")

    _kinds.session().get(f"{HOST}/a")
    _kinds.session().get(f"{HOST}/a")

    assert clock == [5.0, 5.0]


def test_a_layer_robots_txt_comes_to_disallow_is_left_out_with_its_last_rows_and_the_rest_still_load(
    registry, store, requests_mock
):
    """A notices leg leaves an upstream that fails out on its own (extract/_run.py's read_each()), so the refusal is
    UNKNOWN: the closures layer keeps the rows it last loaded, and nothing is emptied."""
    FakeLayer(requests_mock, LINES_URL, [feature(1)])
    FakeLayer(requests_mock, CLOSURES_URL, [feature(10, "Bridge out")])
    agol_robots = AGOL.split("/orgid/")[0] + "/robots.txt"
    requests_mock.get(agol_robots, text="User-agent: *\nDisallow:\n")

    def leg():
        return run_pipeline(
            "notices_ua", store["bucket_url"], resources=[lines(), closures()], pipelines_dir=store["pipelines_dir"]
        )

    leg()
    first_run = len(requests_mock.request_history)
    requests_mock.get(agol_robots, text="User-agent: *\nDisallow: /orgid/arcgis/rest/services/Closures/\n")
    second = leg()

    assert set(second.isolated) == {closures().name} and "disallowed for OurHike" in second.isolated[closures().name]
    second_run = _asked(requests_mock)[first_run:]
    assert second_run[0] == agol_robots and not [url for url in second_run if url.startswith(CLOSURES_URL)]
    con = duckdb.connect()
    load_warehouse(con, make_pipeline("notices_ua", store["bucket_url"], store["pipelines_dir"]))
    assert con.execute("select name from raw.raw_testclub__closures_layer").fetchall() == [("Bridge out",)]


# --- What the rule leaves alone ---------------------------------------------------------------------------------


def test_decision_85_reads_nws_alerts_although_api_weather_govs_robots_txt_disallows_every_url(requests_mock):
    """The maintainer's poll of 2026-10-05: NWS documents the API for applications, so its host-wide `Disallow: /` is
    read as aimed at crawlers of the host (extract/_robots.py's RULED_HOSTS). Serious warnings ride on this read."""
    requests_mock.get("https://api.weather.gov/robots.txt", text="User-agent: *\nDisallow: /\n")
    requests_mock.get(_kinds.NWS_ALERTS_URL, json={"features": []})

    assert _kinds.session().get(_kinds.NWS_ALERTS_URL).json() == {"features": []}


def test_robots_txt_is_never_asked_where_conftest_answers_for_it(requests_mock, monkeypatch):
    """Every other test file and fixture mode answer each origin with no rules and no request (tests/conftest.py,
    extract/_fixtures.py), so their request histories hold their readers' requests alone."""
    monkeypatch.setattr(_robots(), "read_robots_txt", _robots().no_rules)
    requests_mock.get(f"{HOST}/a", text="a")

    _kinds.session().get(f"{HOST}/a")

    assert _asked(requests_mock) == [f"{HOST}/a"]
