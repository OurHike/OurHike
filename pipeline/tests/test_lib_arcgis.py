"""HTTP-mocked tests for lib/arcgis.py. No real network calls - requests_mock
raises on any unmocked request, which is the isolation guarantee this suite
relies on (see TESTING.md)."""
from lib.arcgis import fetch_layer_geojson, get_layer_edit_date

LAYER_URL = "https://services1.arcgis.com/fake/arcgis/rest/services/Fake/FeatureServer/0"


def test_get_layer_edit_date_returns_date_when_present(requests_mock):
    requests_mock.get(LAYER_URL, json={"editingInfo": {"dataLastEditDate": 1781785000304}})
    assert get_layer_edit_date(LAYER_URL) == 1781785000304


def test_get_layer_edit_date_returns_none_when_editing_info_absent(requests_mock):
    """Some ArcGIS services don't expose editingInfo at all - callers must
    treat this as "unknown," not crash, and fall back to always fetching."""
    requests_mock.get(LAYER_URL, json={"some_other_field": True})
    assert get_layer_edit_date(LAYER_URL) is None


def test_fetch_layer_geojson_paginates_until_short_page(requests_mock):
    query_url = LAYER_URL + "/query"
    page1 = {"features": [{"type": "Feature", "properties": {"id": i}, "geometry": None} for i in range(1000)]}
    page2 = {"features": [{"type": "Feature", "properties": {"id": 1000}, "geometry": None}]}
    requests_mock.get(query_url, [{"json": page1}, {"json": page2}])

    fc = fetch_layer_geojson(LAYER_URL)
    assert len(fc["features"]) == 1001
    assert fc["type"] == "FeatureCollection"
