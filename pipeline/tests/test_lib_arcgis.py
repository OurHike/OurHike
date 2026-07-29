"""HTTP-mocked tests for lib/arcgis.py. No real network calls - requests_mock
raises on any unmocked request, which is the isolation guarantee this suite
relies on (see TESTING.md)."""

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


def test_fetch_layer_geojson_paginates_until_short_page(requests_mock):
    query_url = LAYER_URL + "/query"
    page1 = {"features": [{"type": "Feature", "properties": {"id": i}, "geometry": None} for i in range(1000)]}
    page2 = {"features": [{"type": "Feature", "properties": {"id": 1000}, "geometry": None}]}
    requests_mock.get(query_url, [{"json": page1}, {"json": page2}])

    fc = fetch_layer_geojson(LAYER_URL)
    assert len(fc["features"]) == 1001
    assert fc["type"] == "FeatureCollection"


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
