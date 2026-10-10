"""HTTP-mocked tests for lib/arcgis.py. No real network calls - requests_mock
raises on any unmocked request, which is the isolation guarantee this suite
relies on (see TESTING.md)."""

import pytest
import requests

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
    retry asks for the SAME offset at half the size, and every feature
    arrives exactly once. The size stays 500 to the end because the layer
    ends before arcgis.GROW_AFTER_PAGES pages have answered at it."""
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


# --- return_z: a layer whose elevation is why it is registered ----------------
#
# Measured 2026-10-03 on ATC's ATX_Ratings/FeatureServer/9 (hasZ true):
# `f=geojson&returnZ=true` answered 2-D coordinates; `f=json&returnZ=true`
# answered [x, y, z] on every vertex. These pages are that second shape, with
# invented coordinates.

Z_PATH = [[-68.92149, 45.90447, 1600.4792], [-68.92156, 45.90449, 1600.3816]]


def _esri_page(start: int, count: int) -> dict:
    return {
        "geometryType": "esriGeometryPolyline",
        "hasZ": True,
        "spatialReference": {"wkid": 4326},
        "features": [
            {"attributes": {"OBJECTID": start + i}, "geometry": {"paths": [[[x, y, z + start + i] for x, y, z in Z_PATH]]}}
            for i in range(count)
        ],
    }


def test_a_layer_read_with_return_z_keeps_every_vertex_elevation_that_geojson_would_drop(requests_mock):
    query_url = LAYER_URL + "/query"
    requests_mock.get(query_url, [{"json": _esri_page(1, 2)}, {"json": _esri_page(3, 1)}, {"json": {"features": []}}])

    pages = list(arcgis.iter_layer_pages(LAYER_URL, return_z=True))

    features = [feature for page in pages for feature in page]
    assert [feature["properties"]["OBJECTID"] for feature in features] == [1, 2, 3], "every page, in order"
    assert features[0] == {
        "type": "Feature",
        "properties": {"OBJECTID": 1},
        "geometry": {"type": "LineString", "coordinates": [[-68.92149, 45.90447, 1601.4792], [-68.92156, 45.90449, 1601.3816]]},
    }
    asked = requests_mock.request_history[0].qs
    assert asked["f"] == ["json"] and asked["returnz"] == ["true"]
    # Everything else about the query is what the default path sends, so the
    # loop is the same one: the offset advances by rows returned (2, then 3).
    assert set(asked) == {"where", "outfields", "outsr", "f", "resultoffset", "resultrecordcount", "returnz"}
    assert [r.qs["resultoffset"][0] for r in requests_mock.request_history] == ["0", "2", "3"]


def test_the_default_path_asks_exactly_what_the_loop_asked_before_return_z_and_paginate_existed(requests_mock):
    """The same whole-dict pin as the fetch_layer_geojson defaults above, on the generator the extract calls."""
    requests_mock.get(LAYER_URL + "/query", [{"json": {"features": []}}])

    assert list(arcgis.iter_layer_pages(LAYER_URL, return_z=False, paginate=True)) == []

    assert len(requests_mock.request_history) == 1, "no returnIdsOnly query on the paged path"
    assert requests_mock.request_history[0].method == "GET"
    assert requests_mock.request_history[0].qs == {
        "where": ["1=1"],
        "outfields": ["*"],
        "outsr": ["4326"],
        "f": ["geojson"],
        "resultoffset": ["0"],
        "resultrecordcount": ["1000"],
    }


def test_a_return_z_server_that_ignores_the_offset_is_still_refused(requests_mock):
    requests_mock.get(LAYER_URL + "/query", json=_esri_page(1, 1))
    with pytest.raises(RuntimeError, match="ignores resultOffset"):
        list(arcgis.iter_layer_pages(LAYER_URL, return_z=True))


@pytest.mark.parametrize(
    ("esri", "geojson"),
    [
        ({"x": -91.46, "y": 47.97, "z": 457.7}, {"type": "Point", "coordinates": [-91.46, 47.97, 457.7]}),
        ({"x": -91.46, "y": 47.97}, {"type": "Point", "coordinates": [-91.46, 47.97]}),
        ({"x": None, "y": None}, None),
        ({"x": "NaN", "y": "NaN"}, None),
        (
            {"points": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]},
            {"type": "MultiPoint", "coordinates": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]},
        ),
        (
            {"paths": [[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]]},
            {"type": "LineString", "coordinates": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]},
        ),
        (
            {"paths": [[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], [[7.0, 8.0, 9.0], [1.0, 1.0, 1.0]]]},
            {"type": "MultiLineString", "coordinates": [[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], [[7.0, 8.0, 9.0], [1.0, 1.0, 1.0]]]},
        ),
        ({"paths": []}, None),
        (None, None),
        ({}, None),
    ],
)
def test_an_esri_geometry_becomes_the_geojson_shape_f_geojson_answers_with_its_z_kept(esri, geojson):
    assert arcgis.esri_geometry_to_geojson(esri) == geojson


def test_an_esri_polygon_is_refused_rather_than_read_with_its_holes_wrong():
    with pytest.raises(ValueError, match="polygon"):
        arcgis.esri_geometry_to_geojson({"rings": [[[0, 0, 1], [0, 1, 1], [1, 1, 1], [0, 0, 1]]]})


# --- a server that refuses pagination -----------------------------------------
#
# cicgis.org's Chesapeake/CAJO/MapServer/0, measured 2026-10-03: metadata
# reads supportsPagination false, a paged query answers the error below, and
# returnIdsOnly lists 843 ids under FID, starting at 0. The ids and features
# here are invented.

PAGINATION_REFUSED = {"error": {"code": 400, "message": "Pagination is not supported.", "details": []}}


class UnpagedLayer:
    """A layer that refuses resultOffset and answers returnIdsOnly and objectIds, GET or POST."""

    def __init__(self, requests_mock, ids, *, ignores_object_ids=False, refuses_over=None):
        self.ids, self.ignores, self.refuses_over = list(ids), ignores_object_ids, refuses_over
        requests_mock.get(LAYER_URL + "/query", json=self.answer)
        requests_mock.post(LAYER_URL + "/query", json=self.answer)

    def answer(self, request, context):
        from urllib.parse import parse_qs

        asked = {key.lower(): value[0] for key, value in parse_qs(request.text or "").items()}
        asked.update({key.lower(): value[0] for key, value in request.qs.items()})
        if "resultoffset" in asked:
            return PAGINATION_REFUSED
        if asked.get("returnidsonly") == "true":
            return {"objectIdFieldName": "FID", "objectIds": list(reversed(self.ids))}
        wanted = [int(oid) for oid in asked["objectids"].split(",")]
        if self.refuses_over is not None and len(wanted) > self.refuses_over:
            return {"error": {"code": 500, "message": "Error performing query operation"}}
        if self.ignores:
            wanted = self.ids[: len(wanted)]
        if asked.get("f") == "json":
            return {"features": [{"attributes": {"FID": oid}, "geometry": {"x": -76.0, "y": 38.0, "z": 3.5}} for oid in wanted]}
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": oid,
                    "properties": {"FID": oid},
                    "geometry": {"type": "Point", "coordinates": [-76.0, 38.0]},
                }
                for oid in wanted
            ],
        }


def test_a_layer_that_refuses_pagination_is_read_by_object_id_in_batches_in_id_order(requests_mock):
    UnpagedLayer(requests_mock, ids=range(7))

    pages = list(arcgis.iter_layer_pages(LAYER_URL, paginate=False, page_size=3))

    assert [[f["id"] for f in page] for page in pages] == [[0, 1, 2], [3, 4, 5], [6]]
    assert not any("resultoffset" in r.qs for r in requests_mock.request_history), "never asks for a page by offset"
    from urllib.parse import parse_qs

    posted = [parse_qs(r.text)["objectIds"][0] for r in requests_mock.request_history if r.method == "POST"]
    assert posted == ["0,1,2", "3,4,5", "6"], "ascending, though returnIdsOnly listed them in reverse"


def test_the_paged_loop_fails_on_that_server_which_is_why_the_object_id_path_exists(requests_mock):
    UnpagedLayer(requests_mock, ids=range(3))
    with pytest.raises(RuntimeError, match="Pagination is not supported"):
        list(arcgis.iter_layer_pages(LAYER_URL))


def test_reading_by_object_id_keeps_z_when_asked(requests_mock):
    UnpagedLayer(requests_mock, ids=range(2))

    features = [f for page in arcgis.iter_layer_pages(LAYER_URL, paginate=False, return_z=True) for f in page]

    assert [f["geometry"] for f in features] == [{"type": "Point", "coordinates": [-76.0, 38.0, 3.5]}] * 2
    assert [f["properties"]["FID"] for f in features] == [0, 1]


def test_an_object_id_batch_the_server_refuses_is_asked_for_again_at_half_the_size(requests_mock):
    UnpagedLayer(requests_mock, ids=range(5), refuses_over=2)

    pages = list(arcgis.iter_layer_pages(LAYER_URL, paginate=False, page_size=4))

    assert [[f["id"] for f in page] for page in pages] == [[0, 1], [2, 3], [4]]


def test_a_server_that_ignores_object_ids_is_refused_rather_than_read_as_the_layer(requests_mock):
    UnpagedLayer(requests_mock, ids=range(4), ignores_object_ids=True)
    with pytest.raises(RuntimeError, match="ignores objectIds"):
        list(arcgis.iter_layer_pages(LAYER_URL, paginate=False, page_size=2))


def test_a_page_query_too_long_for_a_get_goes_as_a_post_form_and_a_short_one_stays_a_get(requests_mock):
    """ArcGIS Online answered 404 to a 2,622-character GET of WFIGS's perimeters, and 200 to the same as a POST."""
    query = "https://example.test/arcgis/rest/services/X/FeatureServer/0/query"
    requests_mock.get(query, json={"features": []})
    requests_mock.post(query, json={"features": []})
    short = {"where": "1=1", "outFields": "a,b", "f": "geojson"}
    long = {**short, "outFields": ",".join(f"field_number_{n}" for n in range(200))}

    arcgis.query_page(query, short)
    arcgis.query_page(query, long)

    get, post = requests_mock.request_history
    assert get.method == "GET" and get.qs["outfields"] == ["a,b"]
    assert post.method == "POST" and "field_number_199" in post.text and "?" not in post.url


def test_a_page_that_answers_500_is_halved_at_once_and_a_down_server_still_gets_its_retries(requests_mock, monkeypatch):
    """USFS's EDW_Wilderness_02 answered 500 to pages of 1,000 and 250 and 200 to 100 (2026-10-03)."""
    monkeypatch.setattr("lib.http_retry.time.sleep", lambda seconds: None)
    layer = "https://example.test/arcgis/rest/services/W/MapServer/0"

    def answer(request, context):
        count = int(request.qs["resultrecordcount"][0])
        offset = int(request.qs["resultoffset"][0])
        if count > 125:
            context.status_code = 500
            return {"error": "Error performing query operation"}
        return {"features": [{"properties": {"n": n}} for n in range(offset, min(offset + count, 300))]}

    requests_mock.get(layer + "/query", json=answer)

    pages = list(arcgis.iter_layer_pages(layer, backoff=(1, 1)))

    assert [len(page) for page in pages] == [125, 125, 50]
    sizes = [int(r.qs["resultrecordcount"][0]) for r in requests_mock.request_history]
    assert sizes[:4] == [1000, 500, 250, 125], "halved at once, never retried at a size that failed"

    requests_mock.reset_mock()
    requests_mock.get(layer + "/query", status_code=500, json={"error": "down"})
    with pytest.raises(requests.HTTPError):
        list(arcgis.iter_layer_pages(layer, page_size=4, backoff=(1, 1)))
    asks = [(int(r.qs["resultrecordcount"][0]), "geometryprecision" in r.qs) for r in requests_mock.request_history]
    assert asks == [(4, False), (2, False), (1, False), (1, True), (1, True), (1, True)], (
        "halved to one feature, then the rounded ask gets the caller's two retries before it raises"
    )


def test_a_5xx_burst_that_halves_the_first_page_to_one_feature_does_not_read_the_rest_of_the_layer_one_at_a_time(
    requests_mock,
):
    """Ten fast 503s on the first page halve 1,000 to 1 and round it; no page had answered yet to go back to.

    Before the fix the size went back to the last page that answered, which
    was that one rounded feature, so every later page asked for 1: a layer
    of N features cost N + 12 requests (review finding EXD-5).
    """
    layer = "https://example.test/arcgis/rest/services/T/MapServer/0"
    burst = {"left": 10}

    def answer(request, context):
        if burst["left"]:
            burst["left"] -= 1
            context.status_code = 503
            return {"error": "Service Unavailable"}
        count = int(request.qs["resultrecordcount"][0])
        offset = int(request.qs["resultoffset"][0])
        return {"features": [{"properties": {"n": n}} for n in range(offset, min(offset + count, 40))]}

    requests_mock.get(layer + "/query", json=answer)

    pages = list(arcgis.iter_layer_pages(layer, backoff=(1, 1)))

    assert [feature["properties"]["n"] for page in pages for feature in page] == list(range(40))
    sizes = [int(r.qs["resultrecordcount"][0]) for r in requests_mock.request_history]
    assert sizes == [1000, 500, 250, 125, 62, 31, 15, 7, 3, 1, 1, 1000, 1000], "back to the size the read began at"


def test_one_feature_no_page_can_hold_is_asked_once_at_six_decimals_and_only_it(requests_mock):
    """EDW_OtherNationalDesignatedArea_01's feature at offset 83 answered 500 alone and 200 at geometryPrecision=6."""
    layer = "https://example.test/arcgis/rest/services/D/MapServer/0"

    def answer(request, context):
        count = int(request.qs["resultrecordcount"][0])
        offset = int(request.qs["resultoffset"][0])
        rows = range(offset, min(offset + count, 10))
        if 6 in rows and "geometryprecision" not in request.qs:
            context.status_code = 500
            return {"error": "Error performing query operation"}
        return {"features": [{"properties": {"n": n}} for n in rows]}

    requests_mock.get(layer + "/query", json=answer)

    pages = list(arcgis.iter_layer_pages(layer, page_size=4, backoff=(1, 1)))

    assert [feature["properties"]["n"] for page in pages for feature in page] == list(range(10))
    rounded = [r for r in requests_mock.request_history if "geometryprecision" in r.qs]
    assert [(r.qs["resultoffset"][0], r.qs["geometryprecision"][0]) for r in rounded] == [("6", "6")]


#: ArcGIS Online's rate limit as Oregon Metro's trails answered it in monthly run 14: HTTP 200, the error in the body.
THROTTLED = {"error": {"code": 429, "message": "Unable to perform query. Too many requests.", "details": []}}


def test_a_page_answered_with_the_rate_limit_is_asked_again_at_the_same_size_after_a_wait(requests_mock, monkeypatch):
    """Monthly run 14's failure: the paged loop halved a throttled page down to one feature and gave up, stopping the
    whole extract. A throttled page is the same size asked again, after THROTTLE_WAITS_SECONDS' first wait."""
    waits = []
    monkeypatch.setattr("lib.arcgis.time.sleep", waits.append)
    requests_mock.get(LAYER_URL + "/query", [{"json": THROTTLED}, {"json": _page(3)}, {"json": {"features": []}}])

    fc = fetch_layer_geojson(LAYER_URL)

    assert len(fc["features"]) == 3
    assert [r.qs["resultrecordcount"][0] for r in _page_requests(requests_mock)] == ["1000", "1000", "1000"]
    assert waits == [arcgis.THROTTLE_WAITS_SECONDS[0]]


def test_a_rate_limit_that_never_lifts_fails_the_read_without_halving_the_page(requests_mock, monkeypatch):
    """Every wait spent and still throttled: the read fails with the server's words, never read as a page too large."""
    waits = []
    monkeypatch.setattr("lib.arcgis.time.sleep", waits.append)
    requests_mock.get(LAYER_URL + "/query", json=THROTTLED)

    with pytest.raises(RuntimeError, match="Too many requests"):
        fetch_layer_geojson(LAYER_URL)

    assert waits == list(arcgis.THROTTLE_WAITS_SECONDS)
    assert {r.qs["resultrecordcount"][0] for r in _page_requests(requests_mock)} == {"1000"}


def test_an_object_id_batch_answered_with_the_rate_limit_waits_and_keeps_its_size(requests_mock, monkeypatch):
    """The object-id loop the same way: a throttled batch is waited for, not halved."""
    waits = []
    monkeypatch.setattr("lib.arcgis.time.sleep", waits.append)
    layer = UnpagedLayer(requests_mock, ids=range(3))
    answers = iter([THROTTLED])

    def answer(request, context):
        if "objectIds" in (request.text or ""):
            throttled = next(answers, None)
            if throttled is not None:
                return throttled
        return layer.answer(request, context)

    requests_mock.post(LAYER_URL + "/query", json=answer)

    pages = list(arcgis.iter_layer_pages(LAYER_URL, paginate=False, page_size=4))

    assert [[f["id"] for f in page] for page in pages] == [[0, 1, 2]]
    assert waits == [arcgis.THROTTLE_WAITS_SECONDS[0]]


def _heavy_layer(total: int, heavy=range(0), heavy_limit: int = 1, cap: int | None = None, needs_rounding=()):
    """A paged layer of `total` features whose server answers 500 to a page holding a heavy feature when the page asks
    for more than `heavy_limit`, to any page asking for more than `cap`, and to a feature in `needs_rounding` asked
    without geometryPrecision: ParkServe's shapes (TPL's ParkServe_ProdNew/MapServer/2, 2026-10-09)."""

    def answer(request, context):
        count = int(request.qs["resultrecordcount"][0])
        offset = int(request.qs["resultoffset"][0])
        rows = range(offset, min(offset + count, total))
        refused = (cap is not None and count > cap) or (count > heavy_limit and any(n in heavy for n in rows))
        if not refused and "geometryprecision" not in request.qs and any(n in needs_rounding for n in rows):
            refused = True
        if refused:
            context.status_code = 500
            return {"error": {"code": 500, "message": "Error performing query operation"}}
        return {"features": [{"properties": {"n": n}} for n in rows]}

    return answer


def _asked(requests_mock) -> list[tuple[int, int]]:
    """Every page request as (offset, page size), in order."""
    return [(int(r.qs["resultoffset"][0]), int(r.qs["resultrecordcount"][0])) for r in requests_mock.request_history]


def test_a_page_size_halved_inside_a_heavy_range_grows_back_to_the_starting_size_once_the_range_is_behind_it(
    requests_mock,
):
    """Ten heavy features at offsets 2,000 to 2,009 halve the page from 1,000 to 1 there; past them the read is asked
    at 1,000 again, as it began, rather than one feature a request to the end."""
    layer = "https://example.test/arcgis/rest/services/P/MapServer/2"
    requests_mock.get(layer + "/query", json=_heavy_layer(12_000, heavy=range(2_000, 2_010)))

    pages = list(arcgis.iter_layer_pages(layer, backoff=(1, 1)))

    assert [feature["properties"]["n"] for page in pages for feature in page] == list(range(12_000))
    asked = _asked(requests_mock)
    assert min(size for offset, size in asked if 2_000 <= offset < 2_010) == 1, "it shrank inside the heavy range"
    assert [size for _, size in asked][-4:] == [1_000, 1_000, 1_000, 1_000], (
        "back at the size the read began at: pages of 1,000 to the empty page that ends the read"
    )


def test_a_layer_with_one_heavy_cluster_costs_dozens_of_requests_not_one_per_feature_after_it(requests_mock):
    """The crawl ParkServe's read fell into (2026-10-09), on a fake layer of 20,000 features with a heavy cluster at
    5,000 to 5,009 and one feature there that answers only at six decimals. The loop before this change asked 15,016
    pages for it, every feature after the cluster alone; this one asks 68 (both Measured with this test, 2026-10-09)."""
    layer = "https://example.test/arcgis/rest/services/P/MapServer/2"
    requests_mock.get(layer + "/query", json=_heavy_layer(20_000, heavy=range(5_000, 5_010), needs_rounding=(5_005,)))

    pages = list(arcgis.iter_layer_pages(layer, backoff=(1, 1)))

    assert [feature["properties"]["n"] for page in pages for feature in page] == list(range(20_000))
    asked = _asked(requests_mock)
    rounded = [r for r in requests_mock.request_history if "geometryprecision" in r.qs]
    assert [r.qs["resultoffset"][0] for r in rounded] == ["5005"], "the one feature is still asked at six decimals"
    assert len(asked) <= 100, f"{len(asked)} page requests for 20,000 features"


def test_a_size_the_server_always_refuses_is_asked_again_only_after_twice_as_many_pages_each_time(requests_mock):
    """A server that answers 500 to any page over 300, read after a heavy start halved the page to 7: the page grows
    back by doubling to 224, and 448 is asked again after 6, 12, 24 and 48 pages at 224, five tries in a read of
    30,000 features, rather than every 3 pages; the loop before this change never grew past 7."""
    layer = "https://example.test/arcgis/rest/services/P/MapServer/2"
    requests_mock.get(layer + "/query", json=_heavy_layer(30_000, heavy=range(0, 10), heavy_limit=7, cap=300))

    pages = list(arcgis.iter_layer_pages(layer, backoff=(1, 1)))

    assert [feature["properties"]["n"] for page in pages for feature in page] == list(range(30_000))
    sizes = [size for _, size in _asked(requests_mock)]
    assert [size for size in sizes if size > 300] == [1_000, 500] + [448] * 5, "five tries above 300 in the whole read"
    tries = [n for n, size in enumerate(sizes) if size == 448]
    assert [later - earlier - 1 for earlier, later in zip(tries, tries[1:])] == [6, 12, 24, 48], (
        "pages between one try at 448 and the next, twice as many each time"
    )
    assert set(sizes[tries[0] :]) == {224, 448}, "settled at 224, the largest size it reached that the server answers"
