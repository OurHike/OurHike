"""HTTP-mocked tests for lib/arcgis.py. No real network calls - requests_mock
raises on any unmocked request, which is the isolation guarantee this suite
relies on (see TESTING.md)."""

from lib import arcgis
from lib.arcgis import fetch_layer_geojson, get_field_coded_domain, get_layer_edit_date

LAYER_URL = "https://services1.arcgis.com/fake/arcgis/rest/services/Fake/FeatureServer/0"


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
    assert requests_mock.call_count == 3  # short page2 must not stop the loop early


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
        offset = int(request.qs["resultoffset"][0])
        ids = range(offset, min(offset + server_cap, total_features))
        features = [{"type": "Feature", "properties": {"id": i}, "geometry": None} for i in ids]
        return {"type": "FeatureCollection", "features": features}

    requests_mock.get(query_url, json=responder)

    fc = arcgis.fetch_layer_geojson(LAYER_URL)

    assert [f["properties"]["id"] for f in fc["features"]] == list(range(total_features))
    assert requests_mock.call_count == 4  # three 500-item pages + one empty page to confirm the end


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
