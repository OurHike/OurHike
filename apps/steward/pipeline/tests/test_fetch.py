"""The fetcher against a fake session: robots.txt, paging, retries and refusals, with no network."""

from __future__ import annotations

import json
from urllib.parse import urlsplit

import pytest

from steward_analysis import fetch, sources


class FakeResponse:
    def __init__(self, status: int, body=None, text: str = ""):
        self.status_code = status
        self._body = body
        self.text = text if body is None else json.dumps(body)

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Answers by path. `robots` is the robots.txt answer for every host; `routes` maps a path to a
    response or a list of responses handed out in order."""

    def __init__(self, routes: dict, robots: FakeResponse | None = None):
        self.headers: dict = {}
        self.routes = routes
        self.robots = robots or FakeResponse(403, text="Invalid URL")
        self.calls: list[tuple[str, str, dict]] = []

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def request(self, method, url, **kwargs):
        path = urlsplit(url).path
        self.calls.append((method, path, kwargs.get("params") or kwargs.get("data") or {}))
        if path == "/robots.txt":
            return self.robots
        answer = self.routes[path]
        if isinstance(answer, list):
            return answer.pop(0)
        return answer(kwargs) if callable(answer) else answer


CSI_PATH = urlsplit(sources.CSI_LAYER).path


def csi_routes(rows: list[dict], reported: int | None = None) -> dict:
    def page(kwargs):
        params = kwargs["params"]
        if params.get("returnCountOnly"):
            return FakeResponse(200, {"count": len(rows) if reported is None else reported})
        start, size = params["resultOffset"], params["resultRecordCount"]
        chunk = rows[start : start + size]
        return FakeResponse(
            200, {"features": [{"attributes": r} for r in chunk], "exceededTransferLimit": start + size < len(rows)}
        )

    return {CSI_PATH: FakeResponse(200, {"editingInfo": {"dataLastEditDate": 1787239681299}}), f"{CSI_PATH}/query": page}


def test_every_request_carries_the_jobs_own_user_agent():
    session = FakeSession(csi_routes([{"OBJECTID": 1}]))
    fetch.Fetcher(session)
    assert session.headers["User-Agent"] == sources.USER_AGENT
    assert sources.USER_AGENT.startswith("CampsiteSteward/")


def test_a_4xx_robots_txt_means_no_rules_and_the_layer_is_read_in_pages(monkeypatch):
    monkeypatch.setattr(fetch, "PAGE_SIZE", 2)
    rows = [{"OBJECTID": i} for i in range(5)]
    got = fetch.fetch_csi(fetch.Fetcher(FakeSession(csi_routes(rows))))
    assert got["rows"] == rows
    assert got["data_last_edit_ms"] == 1787239681299


def test_the_job_never_asks_for_atcs_assessment_photos():
    session = FakeSession(csi_routes([{"OBJECTID": 1}]))
    fetch.fetch_csi(fetch.Fetcher(session))
    asked = [params["outFields"] for _, _, params in session.calls if "outFields" in params]
    assert asked and all("Site_Photo" not in fields for fields in asked)


def test_a_layer_that_returns_fewer_rows_than_it_counts_is_refused():
    with pytest.raises(RuntimeError, match="refusing to score a partial layer"):
        fetch.fetch_csi(fetch.Fetcher(FakeSession(csi_routes([{"OBJECTID": 1}], reported=2))))


def test_a_robots_txt_that_disallows_the_job_stops_it_before_any_query():
    session = FakeSession(csi_routes([]), robots=FakeResponse(200, text="User-agent: *\nDisallow: /\n"))
    with pytest.raises(fetch.RefusedByRobots):
        fetch.fetch_csi(fetch.Fetcher(session))
    assert [path for _, path, _ in session.calls] == ["/robots.txt"]


def test_a_robots_txt_that_cannot_be_read_refuses_the_host():
    session = FakeSession(csi_routes([]), robots=FakeResponse(503, text="busy"))
    with pytest.raises(fetch.RefusedByRobots, match="503"):
        fetch.fetch_csi(fetch.Fetcher(session))


def test_a_busy_server_is_retried_after_a_wait():
    waits = []
    routes = {CSI_PATH: [FakeResponse(503, text="busy"), FakeResponse(200, {"ok": True})]}
    body = fetch.Fetcher(FakeSession(routes), sleep=waits.append).request("GET", sources.CSI_LAYER)
    assert body == {"ok": True}
    assert waits == [fetch.RETRY_WAITS_S[0]]


def test_an_arcgis_error_inside_a_200_answer_is_raised_not_scored():
    routes = {CSI_PATH: FakeResponse(200, {"error": {"code": 400, "message": "Invalid query"}})}
    with pytest.raises(RuntimeError, match="Invalid query"):
        fetch.Fetcher(FakeSession(routes)).request("GET", sources.CSI_LAYER)


def test_padus_polygons_are_kept_once_however_many_batches_find_them(monkeypatch):
    monkeypatch.setattr(fetch, "PADUS_BATCH", 2)
    polygon = {"type": "Feature", "geometry": None, "properties": {"OBJECTID": 7}}
    routes = {urlsplit(sources.PADUS_LAYER).path + "/query": lambda kwargs: FakeResponse(200, {"features": [polygon]})}
    got = fetch.fetch_padus(fetch.Fetcher(FakeSession(routes)), [(0.0, 0.0), (0.1, 0.1), (0.2, 0.2)])
    assert [f["properties"]["OBJECTID"] for f in got["features"]] == [7]
