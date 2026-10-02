"""HTTP-mocked tests for lib/arcgis.py. No real network calls - requests_mock
raises on any unmocked request, which is the isolation guarantee this suite
relies on (see TESTING.md)."""

import pytest

from lib import arcgis
from lib.arcgis import (
    fetch_layer_geojson,
    get_field_coded_domain,
    get_layer_edit_date,
    get_layer_max_field,
    get_service_etag,
)

LAYER_URL = "https://services1.arcgis.com/fake/arcgis/rest/services/Fake/FeatureServer/0"


def _page_requests(requests_mock) -> list:
    """The page requests only: every fetch now ends with one returnCountOnly
    query (#1730) that these tests are not counting."""
    return [r for r in requests_mock.request_history if "returncountonly" not in r.qs]


def test_get_layer_edit_date_returns_date_when_present(requests_mock):
    requests_mock.get(LAYER_URL, json={"editingInfo": {"dataLastEditDate": 1781785000304}})
    assert get_layer_edit_date(LAYER_URL) == 1781785000304


def test_get_layer_edit_date_returns_none_when_editing_info_absent(requests_mock):
    """Some ArcGIS services don't expose editingInfo at all - callers must
    treat this as "unknown," not crash, and fall back to always fetching."""
    requests_mock.get(LAYER_URL, json={"some_other_field": True})
    assert get_layer_edit_date(LAYER_URL) is None


def test_fetch_layer_geojson_paginates_until_empty_page(requests_mock):
    """A page shorter than PAGE_SIZE is not proof there's no more data - only
    an empty page is. Regression test: this used to treat any short page as
    the last page and stop right there, so a short-but-nonempty page must
    not end the loop early."""
    query_url = LAYER_URL + "/query"
    page1 = {"features": [{"type": "Feature", "properties": {"id": i}, "geometry": None} for i in range(1000)]}
    page2 = {"features": [{"type": "Feature", "properties": {"id": 1000}, "geometry": None}]}
    page3 = {"features": []}
    requests_mock.get(query_url, [{"json": page1}, {"json": page2}, {"json": page3}])

    fc = fetch_layer_geojson(LAYER_URL)

    assert len(fc["features"]) == 1001
    assert fc["type"] == "FeatureCollection"
    assert len(_page_requests(requests_mock)) == 3  # short page2 must not stop the loop early


def test_fetch_layer_geojson_handles_server_cap_below_page_size(requests_mock, monkeypatch):
    """Regression test for two compounding bugs: the loop used to stop as
    soon as a page came back shorter than PAGE_SIZE (mistaking "short" for
    "last"), and even without that early exit, the offset used to always
    advance by the fixed PAGE_SIZE rather than however many features
    actually came back - permanently skipping the gap between them on the
    next request. Simulates a server whose real per-request cap (500) is
    below PAGE_SIZE (1000), so every page comes back short while more
    features remain, and asserts every feature comes back exactly once, in
    order, with no gap and no premature stop."""
    monkeypatch.setattr(arcgis, "PAGE_SIZE", 1000)
    query_url = LAYER_URL + "/query"
    server_cap = 500
    total_features = 1500

    def responder(request, context):
        if "returncountonly" in request.qs:
            return {}
        offset = int(request.qs["resultoffset"][0])
        ids = range(offset, min(offset + server_cap, total_features))
        features = [{"type": "Feature", "properties": {"id": i}, "geometry": None} for i in ids]
        return {"type": "FeatureCollection", "features": features}

    requests_mock.get(query_url, json=responder)

    fc = arcgis.fetch_layer_geojson(LAYER_URL)

    assert [f["properties"]["id"] for f in fc["features"]] == list(range(total_features))
    assert len(_page_requests(requests_mock)) == 4  # three 500-item pages + one empty page to confirm the end


def test_get_field_coded_domain_returns_code_to_label_mapping_when_present(requests_mock):
    """Mirrors side_trails' real `Blaze` field: an esriFieldTypeInteger with a
    codedValue domain - fetched from the field metadata, not hand-coded."""
    requests_mock.get(
        LAYER_URL,
        json={
            "fields": [
                {"name": "OBJECTID", "type": "esriFieldTypeOID", "alias": "OBJECTID"},
                {
                    "name": "Blaze",
                    "type": "esriFieldTypeInteger",
                    "alias": "Blaze",
                    "domain": {
                        "type": "codedValue",
                        "name": "BlazeDomain",
                        "codedValues": [
                            {"name": "None", "code": 0},
                            {"name": "Blue", "code": 1},
                            {"name": "White", "code": 2},
                            {"name": "Other", "code": 9},
                        ],
                    },
                },
            ]
        },
    )
    assert get_field_coded_domain(LAYER_URL, "Blaze") == {0: "None", 1: "Blue", 2: "White", 9: "Other"}


def test_get_field_coded_domain_returns_none_when_domain_is_not_coded_value_type(requests_mock):
    requests_mock.get(
        LAYER_URL,
        json={
            "fields": [
                {
                    "name": "Width",
                    "type": "esriFieldTypeDouble",
                    "alias": "Width",
                    "domain": {"type": "range", "name": "WidthRange", "range": [0, 100]},
                },
                {"name": "Notes", "type": "esriFieldTypeString", "alias": "Notes", "domain": None},
            ]
        },
    )
    assert get_field_coded_domain(LAYER_URL, "Width") is None  # range domain, not coded-value
    assert get_field_coded_domain(LAYER_URL, "Notes") is None  # no domain at all


def test_get_field_coded_domain_returns_none_when_field_not_found(requests_mock):
    requests_mock.get(LAYER_URL, json={"fields": [{"name": "OBJECTID", "type": "esriFieldTypeOID"}]})
    assert get_field_coded_domain(LAYER_URL, "Blaze") is None


def test_fetch_layer_geojson_defaults_are_unchanged_by_the_new_parameters(requests_mock):
    """The twelve callers that pass nothing must send exactly what they sent
    before #1295 widened this signature. Pinned as a whole-dict comparison
    rather than field by field, so a parameter added later that leaks into
    the default query fails here rather than in a publish."""
    query_url = LAYER_URL + "/query"
    requests_mock.get(query_url, [{"json": {"features": []}}])

    fetch_layer_geojson(LAYER_URL)

    assert requests_mock.request_history[0].qs == {
        "where": ["1=1"],
        "outfields": ["*"],
        "outsr": ["4326"],
        "f": ["geojson"],
        "resultoffset": ["0"],
        "resultrecordcount": ["1000"],
    }
    # Absent rather than empty: a caller that wants full precision must not
    # send the parameter at all, because ArcGIS reads geometryPrecision=0 as
    # "round to whole degrees" rather than "do not round".
    assert "geometryprecision" not in requests_mock.request_history[0].qs


def test_fetch_layer_geojson_carries_the_callers_query_shape(requests_mock):
    """fetch_centerline.py's shape, which is why these parameters exist."""
    query_url = LAYER_URL + "/query"
    requests_mock.get(query_url, [{"json": {"features": []}}])

    fetch_layer_geojson(LAYER_URL, out_fields="", geometry_precision=5, page_size=2000)

    asked = requests_mock.request_history[0].qs
    assert asked["outfields"] == [""]
    assert asked["geometryprecision"] == ["5"]
    assert asked["resultrecordcount"] == ["2000"]


def test_page_size_resolves_against_the_module_constant_at_call_time(requests_mock, monkeypatch):
    """`page_size=None` must mean "whatever PAGE_SIZE is now", not "whatever
    it was when this function was defined". The existing server-cap test
    monkeypatches arcgis.PAGE_SIZE and would have gone on passing against a
    stale default bound in the signature, so the property is pinned directly
    - it is the same trap lib/http_retry.py documents for its `sleep`."""
    monkeypatch.setattr(arcgis, "PAGE_SIZE", 25)
    query_url = LAYER_URL + "/query"
    requests_mock.get(query_url, [{"json": {"features": []}}])

    arcgis.fetch_layer_geojson(LAYER_URL)

    assert requests_mock.request_history[0].qs["resultrecordcount"] == ["25"]


def test_a_custom_page_size_still_stops_only_on_an_empty_page(requests_mock):
    """The stop condition does not become the caller's along with the shape.

    This is the guarantee that let publish-conditions.yml's heredoc be
    deleted rather than ported: whatever page size it asks for, a short page
    is not the end.
    """
    query_url = LAYER_URL + "/query"
    requests_mock.get(
        query_url,
        [
            {"json": {"features": [{"id": i} for i in range(3)]}},  # far short of 2000
            {"json": {"features": [{"id": 3}]}},
            {"json": {"features": []}},
        ],
    )

    fc = fetch_layer_geojson(LAYER_URL, page_size=2000)

    assert len(fc["features"]) == 4
    assert len(_page_requests(requests_mock)) == 3


# --- a page the server refuses (#1790) ---------------------------------------
#
# What PASDA and CDTC answered on 2026-10-01 to the fetcher's 1,000-feature
# page, verbatim in shape: an HTML error page with HTTP 200 for f=geojson, and
# a JSON error object for f=json. Both servers answer smaller pages.

HTML_ERROR_PAGE = '\n\n<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"><html>Error</html>'
QUERY_ERROR = {"error": {"code": 500, "message": "Error performing query operation", "details": []}}


def _page(count: int, start: int = 0) -> dict:
    return {"features": [{"type": "Feature", "properties": {"id": start + i}, "geometry": None} for i in range(count)]}


def test_fetch_layer_geojson_halves_a_page_the_server_answers_with_an_html_error_page(requests_mock):
    """PASDA's shape: 1,000 features is an HTML page, 500 is GeoJSON. The
    retry asks for the SAME offset at half the size, keeps that size for
    the rest of the layer, and every feature arrives exactly once."""
    query_url = LAYER_URL + "/query"
    requests_mock.get(
        query_url,
        [
            {"text": HTML_ERROR_PAGE, "headers": {"Content-Type": "text/html"}},
            {"json": _page(500)},
            {"json": _page(184, start=500)},
            {"json": {"features": []}},
        ],
    )

    fc = fetch_layer_geojson(LAYER_URL)

    assert [f["properties"]["id"] for f in fc["features"]] == list(range(684))
    asked = [(r.qs["resultoffset"][0], r.qs["resultrecordcount"][0]) for r in _page_requests(requests_mock)]
    assert asked == [("0", "1000"), ("0", "500"), ("500", "500"), ("684", "500")]


def test_fetch_layer_geojson_halves_on_a_json_error_object_too(requests_mock):
    """The same servers' f=json shape - and what any ArcGIS server says when
    a query fails for a reason it will name. Halved like the HTML page: the
    caller cannot tell a byte cap from a count cap and does not need to."""
    query_url = LAYER_URL + "/query"
    requests_mock.get(
        query_url,
        [
            {"json": QUERY_ERROR},
            {"json": QUERY_ERROR},
            {"json": _page(3)},
            {"json": {"features": []}},
        ],
    )

    fc = fetch_layer_geojson(LAYER_URL)

    assert len(fc["features"]) == 3
    assert [r.qs["resultrecordcount"][0] for r in _page_requests(requests_mock)] == ["1000", "500", "250", "250"]


def test_fetch_layer_geojson_gives_up_at_a_page_of_one_with_the_servers_words(requests_mock):
    """A layer that is genuinely broken still fails, after the ten halvings
    from 1,000 to 1 - never a silent skip, and never forever. The error
    carries what the server said, so the fetch log names the cause."""
    query_url = LAYER_URL + "/query"
    requests_mock.get(query_url, json=QUERY_ERROR)

    with pytest.raises(RuntimeError, match="error 500: Error performing query operation at a page of 1 feature"):
        fetch_layer_geojson(LAYER_URL)

    assert [r.qs["resultrecordcount"][0] for r in _page_requests(requests_mock)] == [
        "1000",
        "500",
        "250",
        "125",
        "62",
        "31",
        "15",
        "7",
        "3",
        "1",
    ]


def test_an_answer_with_no_features_key_is_a_stop_and_not_a_refusal(requests_mock):
    """`{}` and `{"features": []}` both mean "nothing here" and end the loop
    on the first request; only an error object or an unparsable body is
    asked again smaller."""
    query_url = LAYER_URL + "/query"
    requests_mock.get(query_url, json={})

    assert fetch_layer_geojson(LAYER_URL)["features"] == []
    assert len(_page_requests(requests_mock)) == 1


# --- a layer the server says holds more than it handed over (#1730) ----------


def _pages_then_count(pages: list[dict], count_answer: dict) -> list:
    """Page answers in order, then the count query's answer last."""
    return [{"json": p} for p in pages] + [{"json": count_answer}]


def test_a_layer_shorter_than_the_servers_own_count_is_a_failed_fetch_not_a_small_layer(requests_mock):
    """The 200-with-an-early-empty-page shape: 3 features arrive, the count
    says 4. Written as a file, `fetch_all` would record the layer as up to
    date and never fetch it again."""
    requests_mock.get(LAYER_URL + "/query", _pages_then_count([_page(3), {"features": []}], {"count": 4}))

    with pytest.raises(RuntimeError, match="holds 4 features but 3 were fetched"):
        fetch_layer_geojson(LAYER_URL)


def test_a_layer_matching_the_servers_count_is_returned(requests_mock):
    requests_mock.get(LAYER_URL + "/query", _pages_then_count([_page(3), {"features": []}], {"count": 3}))

    assert len(fetch_layer_geojson(LAYER_URL)["features"]) == 3


def test_more_features_than_the_count_is_not_a_failure(requests_mock):
    """A layer edited between the pages and the count can move either way;
    an overshoot loses nothing, so only a shortfall raises."""
    requests_mock.get(LAYER_URL + "/query", _pages_then_count([_page(3), {"features": []}], {"count": 2}))

    assert len(fetch_layer_geojson(LAYER_URL)["features"]) == 3


@pytest.mark.parametrize(
    "count_answer",
    [QUERY_ERROR, {}, {"count": "4"}],
    ids=["error object", "no count key", "count that is not an integer"],
)
def test_a_count_that_cannot_be_read_skips_the_check_rather_than_failing_the_fetch(requests_mock, count_answer):
    """Whether every registered server supports returnCountOnly is unmeasured
    (@unvalidated in check_not_truncated), so an unreadable count is not a
    verdict either way."""
    requests_mock.get(LAYER_URL + "/query", _pages_then_count([_page(3), {"features": []}], count_answer))

    assert len(fetch_layer_geojson(LAYER_URL)["features"]) == 3


def test_a_count_request_that_fails_outright_skips_the_check(requests_mock):
    requests_mock.get(
        LAYER_URL + "/query",
        [{"json": _page(3)}, {"json": {"features": []}}, {"text": "not json", "headers": {"Content-Type": "text/html"}}],
    )

    assert len(fetch_layer_geojson(LAYER_URL)["features"]) == 3


# --- the substitute markers (#1311) -----------------------------------------

SERVICE_URL = "https://apps.fs.usda.gov/arcx/rest/services/EDW/Fake/MapServer?f=json"


def test_get_layer_max_field_asks_one_statistics_query_and_answers_a_string(requests_mock):
    requests_mock.get(LAYER_URL + "/query", json={"features": [{"attributes": {"marker": 1755475200000}}]})

    assert get_layer_max_field(LAYER_URL, "UPDATED") == "1755475200000"

    sent = requests_mock.last_request.qs
    assert "outstatistics" in sent
    assert "updated" in sent["outstatistics"][0].lower()
    assert requests_mock.call_count == 1


def test_get_layer_max_field_is_none_when_the_server_answers_no_row(requests_mock):
    """An empty answer is "no marker", never "unchanged" - the caller fetches."""
    requests_mock.get(LAYER_URL + "/query", json={"features": []})

    assert get_layer_max_field(LAYER_URL, "UPDATED") is None


def test_get_service_etag_reads_the_header_off_a_head(requests_mock):
    requests_mock.head(SERVICE_URL, headers={"ETag": 'W/"1a7709d0"'})

    assert get_service_etag(SERVICE_URL) == 'W/"1a7709d0"'
    assert requests_mock.last_request.method == "HEAD"


def test_get_service_etag_is_none_when_the_service_sends_none(requests_mock):
    requests_mock.head(SERVICE_URL, headers={})

    assert get_service_etag(SERVICE_URL) is None


def test_a_server_that_ignores_the_offset_is_refused_rather_than_read_forever(requests_mock):
    """A non-paginating server answers every resultOffset with page one; the loop stops only on an empty page."""
    page = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"OBJECTID": 1}, "geometry": None}]}
    requests_mock.get(LAYER_URL + "/query", json=page)
    with pytest.raises(RuntimeError, match="ignores resultOffset"):
        list(arcgis.iter_layer_pages(LAYER_URL))


def test_every_page_and_the_count_name_the_pipeline_to_the_server(requests_mock):
    """fetch_external_layers.py calls this with no session, so before
    lib/http_retry.py's `named()` every page and the count went out as
    `python-requests/<version>`."""
    from lib.user_agent import USER_AGENT

    query_url = LAYER_URL + "/query"
    page = {"features": [{"type": "Feature", "properties": {"id": 1}, "geometry": None}]}
    requests_mock.get(query_url, [{"json": page}, {"json": {"features": []}}, {"json": {"count": 1}}])
    requests_mock.get(LAYER_URL, json={"editingInfo": {"dataLastEditDate": 1}})

    fetch_layer_geojson(LAYER_URL)
    get_layer_edit_date(LAYER_URL)

    sent = [request.headers.get("User-Agent") for request in requests_mock.request_history]
    assert sent == [USER_AGENT] * 4
