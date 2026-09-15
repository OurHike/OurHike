"""HTTP-mocked tests for lib/socrata.py. No real network calls - requests_mock
raises on any unmocked request, which is the isolation guarantee this suite
relies on (see TESTING.md).

The paging tests here are lib/test_lib_arcgis.py's, deliberately: the two
fetchers page over different parameters against different servers, and they
can get the SAME two things wrong - stopping on a short page, and advancing
the offset by what was asked for rather than by what arrived. New York City's
datasets both fit in one page today (7,059 and 3,039 rows against a 50,000
ceiling), so nothing in production exercises this loop and nothing in
production would notice it breaking. That is exactly the case worth pinning.
"""

from lib import socrata
from lib.socrata import (
    dataset_url,
    fetch_dataset_geojson,
    get_dataset_updated_at,
)

DOMAIN = "data.example.gov"
DATASET = "abcd-1234"
RESOURCE_URL = f"https://{DOMAIN}/resource/{DATASET}.geojson"
VIEWS_URL = f"https://{DOMAIN}/api/views/{DATASET}.json"


def _features(start: int, count: int) -> list[dict]:
    return [{"type": "Feature", "properties": {"n": start + i}, "geometry": None} for i in range(count)]


def test_dataset_url_assembles_the_soda_resource_address():
    assert dataset_url(DOMAIN, DATASET) == RESOURCE_URL
    assert dataset_url(DOMAIN, DATASET, "json") == f"https://{DOMAIN}/resource/{DATASET}.json"


def test_get_dataset_updated_at_returns_row_timestamp_when_present(requests_mock):
    """Seconds, not milliseconds - the units differ from ArcGIS's
    dataLastEditDate, which is why fetch_external_layers.py records the
    marker's kind beside its value rather than a bare number."""
    requests_mock.get(VIEWS_URL, json={"rowsUpdatedAt": 1788000000, "viewLastModified": 1787000000})
    assert get_dataset_updated_at(DOMAIN, DATASET) == 1788000000


def test_get_dataset_updated_at_returns_none_when_absent(requests_mock):
    """A portal that answers no rowsUpdatedAt must read as "unknown" and send
    the caller back to fetching, never as "unchanged" - the same posture
    get_layer_edit_date takes for a service with no editingInfo."""
    requests_mock.get(VIEWS_URL, json={"name": "Some dataset"})
    assert get_dataset_updated_at(DOMAIN, DATASET) is None


def test_fetch_dataset_geojson_paginates_until_empty_page(requests_mock):
    """A page shorter than the requested limit is not proof there is no more
    data - only an empty page is. The failure lib/arcgis.py's own regression
    test exists for, guarded here before it can happen a second time."""
    requests_mock.get(
        RESOURCE_URL,
        [
            {"json": {"type": "FeatureCollection", "features": _features(0, 50000)}},
            {"json": {"type": "FeatureCollection", "features": _features(50000, 7)}},
            {"json": {"type": "FeatureCollection", "features": []}},
        ],
    )

    fc = fetch_dataset_geojson(DOMAIN, DATASET)

    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 50007
    assert requests_mock.call_count == 3  # the short second page must not stop the loop


def test_fetch_dataset_geojson_advances_by_what_arrived(requests_mock, monkeypatch):
    """A portal whose real cap sits below the requested limit returns short
    pages the whole way through. The offset must advance by however many rows
    actually came back, never by the size asked for - otherwise every page
    boundary silently swallows the gap between the two numbers.

    Asserts the features come back exactly once each and IN ORDER, which is
    what catches a skip that happens to leave the count right.
    """
    monkeypatch.setattr(socrata, "PAGE_SIZE", 1000)
    cap, total = 400, 1000
    seen: list[int] = []

    def paged(request, context):
        offset = int(request.qs["$offset"][0])
        batch = _features(offset, min(cap, max(0, total - offset)))
        seen.append(offset)
        return {"type": "FeatureCollection", "features": batch}

    requests_mock.get(RESOURCE_URL, json=paged)

    fc = fetch_dataset_geojson(DOMAIN, DATASET)

    assert [f["properties"]["n"] for f in fc["features"]] == list(range(total))
    assert seen == [0, 400, 800, 1000]  # by arrival, not by 1000 at a time


def test_fetch_dataset_geojson_always_orders_by_row_id(requests_mock):
    """`$order=:id` is load-bearing, not tidiness. SoQL gives no ordering
    guarantee without it, so `$offset` against an unordered result set can
    repeat one row and skip another - the same page-boundary corruption as
    above, arriving through a different door and invisible in the count."""
    requests_mock.get(RESOURCE_URL, json={"type": "FeatureCollection", "features": []})

    fetch_dataset_geojson(DOMAIN, DATASET)

    assert requests_mock.last_request.qs["$order"] == [":id"]


def test_fetch_dataset_geojson_sends_the_filter_to_the_portal(requests_mock):
    """The greenway filter is the reason nyc_dot_greenways is defensible at
    all - 3,039 walkable rows out of 29,695, the rest being bike lanes in
    traffic. Filtering AT THE PORTAL means the excluded rows are never
    fetched and never on disk to be drawn by mistake, so this asserts the
    predicate actually leaves the machine rather than being applied after."""
    requests_mock.get(RESOURCE_URL, json={"type": "FeatureCollection", "features": []})
    where = "status='Current' AND grnwy='Greenway' AND onoffst='OFF'"

    fetch_dataset_geojson(DOMAIN, DATASET, where=where)

    assert requests_mock.last_request.qs["$where"] == [where.lower()]


def test_fetch_dataset_geojson_sends_no_filter_when_none_is_registered(requests_mock):
    """An entry with no `where` must fetch the whole dataset rather than an
    empty string, which SoQL would reject."""
    requests_mock.get(RESOURCE_URL, json={"type": "FeatureCollection", "features": []})

    fetch_dataset_geojson(DOMAIN, DATASET)

    assert "$where" not in requests_mock.last_request.qs


def test_fetch_dataset_geojson_asks_for_the_row_id_and_promotes_it(requests_mock):
    """A Socrata feature carries no `id` member, so without this every NYC
    segment falls onto lib/feature_id.py's `generated-{index}` - an id that
    renumbers when rows are inserted, which silently re-points anything keyed
    on a line id after the next publish. The query must ask for `:id`, and the
    result must land where feature_id.py looks."""
    requests_mock.get(
        RESOURCE_URL,
        [
            {
                "json": {
                    "type": "FeatureCollection",
                    "features": [{"type": "Feature", "properties": {"n": 1, ":id": "row-6p7c_bcx9.in7u"}, "geometry": None}],
                }
            },
            {"json": {"type": "FeatureCollection", "features": []}},
        ],
    )

    fc = fetch_dataset_geojson(DOMAIN, DATASET)
    feature = fc["features"][0]

    assert requests_mock.request_history[0].qs["$select"] == ["*,:id"]
    assert feature["id"] == "row-6p7c_bcx9.in7u"
    # The leading-colon key is Socrata's syntax, not a column - it must not
    # reach the warehouse or any exported property bag.
    assert ":id" not in feature["properties"]


def test_a_feature_with_no_row_id_is_left_alone(requests_mock):
    """The loud generated-id warning is the signal that the promotion above
    stopped working, so it must still be reachable rather than papered over."""
    requests_mock.get(
        RESOURCE_URL,
        [
            {"json": {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"n": 1}, "geometry": None}]}},
            {"json": {"type": "FeatureCollection", "features": []}},
        ],
    )

    feature = fetch_dataset_geojson(DOMAIN, DATASET)["features"][0]

    assert "id" not in feature


def test_fetch_dataset_to_file_writes_geojson_and_counts(requests_mock, tmp_path):
    requests_mock.get(
        RESOURCE_URL,
        [
            {"json": {"type": "FeatureCollection", "features": _features(0, 3)}},
            {"json": {"type": "FeatureCollection", "features": []}},
        ],
    )
    out = tmp_path / "nested" / "nyc_parks_trails.geojson"

    count = socrata.fetch_dataset_to_file(DOMAIN, DATASET, out)

    assert count == 3
    import json

    written = json.loads(out.read_text())
    assert written["type"] == "FeatureCollection"
    assert len(written["features"]) == 3
