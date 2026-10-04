"""extract/_pages_points.py, decision 54's wave 5 (section S): the points clubs print on their own pages, against
mocked servers.

Each parser is handed a page shaped like the one it was written against (read live on 2026-10-04, each
sources.json row's `notes`); every name and number here is invented. requests_mock answers the reads and
conftest.py's socket guard stays on.

The cases are the ones a hiker's safety turns on or a page was measured to get wrong: a page that changed
shape must refuse rather than relabel, a point with no fix must land with no geometry rather than a guessed
one, a coordinate written three ways on one page (AMC Berkshire's), a list item never closed, a nested list
whose facts belong to another area, a longitude printed with no sign (the Foothills Trail's), a wall or a
redirect to another host, and a change check that must never answer FRESH while the points moved.
"""

import json

import pytest

from extract import _kinds, _notices
from extract._pages_points import (
    PAGE_PARSERS,
    PageLayoutChanged,
    PagePoints,
    html_lines,
    north_america,
    page_points,
    parse_amc_berkshire_at_parking,
    parse_foot_trail_shelters,
    parse_foothills_gps_coordinates,
    parse_mdhta_trail_guide,
)
from lib import http_retry
from lib.freshness_state import Freshness
from tests.test_extract_run import lane, warehouse

GUIDE_URL = "https://guide.example.org/trail-guide/"
SHELTERS_PAGE = "https://club.example.org/hiker-info/trail-shelters/"
SHELTERS_REST = "https://club.example.org/wp-json/wp/v2/pages/326"
PARKING_URL = "https://chapter.example.org/documents-more.cgi?id=112"
COORDINATES_REST = "https://conservancy.example.org/wp-json/wp/v2/pages/603"


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """A sources.json holding one row per parser, each under the key its parser is registered for."""
    path = tmp_path / "sources.json"
    sources = [
        {"key": "mdhta_trail_guide_points", "url": GUIDE_URL},
        {"key": "foot_trail_shelters", "url": SHELTERS_PAGE, "read_url": SHELTERS_REST, "crawl_delay": 10},
        {"key": "amc_wma_at_parking_points", "url": PARKING_URL},
        {"key": "foothills_gps_coordinates", "url": "https://conservancy.example.org/maps/", "read_url": COORDINATES_REST},
    ]
    path.write_text(json.dumps({"sources": sources}))
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()
    yield path
    _kinds._registry.cache_clear()


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    """No host is asked anything, so the per-host gate and the retry ladder never sleep."""
    monkeypatch.setattr(_notices, "_pause", lambda seconds: None)
    monkeypatch.setattr(http_retry.time, "sleep", lambda seconds: None)


@pytest.fixture
def store(tmp_path):
    return {"bucket_url": (tmp_path / "raw-store").as_uri(), "pipelines_dir": str(tmp_path / "pipelines")}


def anchor(kind: str, slug: str, title: str, lat: str | None = "46.9", lon: str | None = "-103.5") -> str:
    coordinates = (f' data-lat="{lat}"' if lat is not None else "") + (f' data-long="{lon}"' if lon is not None else "")
    return f'<a href="https://guide.example.org/{kind}/{slug}/" data-slug="{slug}" data-title="{title}" data-type="{kind}"{coordinates}></a>'


def guide_page(*anchors: str) -> str:
    line = (
        '<a href="https://guide.example.org/trails/fixture/" data-slug="fixture" data-title="Fixture Trail" '
        'data-type="trails" data-geojson="https://guide.example.org/fixture.geojson"></a>'
    )
    return f"<html><body><div>{line}{''.join(anchors)}</div></body></html>"


def rest_page(rendered: str, modified: str = "2025-11-11T21:30:44") -> str:
    return json.dumps({"id": 326, "modified_gmt": modified, "content": {"rendered": rendered}, "title": {"rendered": "Fixture"}})


SHELTER_LIST = (
    "<h2>Fixture Shelters</h2><ul>"
    "<li><strong><u>FIXTURE GARDEN</u></strong><strong> – MM 9.4 N34 46.387 / W94 51.799 </strong></li>"
    "<li><strong><u>FIXTURE MOUNTAIN SHELTER</u></strong><strong> – 57.8 N34 41.437 / W94 18.624 </strong></li>"
    "<li><strong><u>FIXTURE CREEK SHELTER at MM 122.6</u></strong></li>"
    "</ul><p>Fixture thanks.</p>"
)


# --- the parsers ---------------------------------------------------------------------------------------------------


def test_the_trail_guide_lands_each_plotted_point_and_never_a_trail_line():
    rows = parse_mdhta_trail_guide(
        guide_page(anchor("waterboxes", "box", "Fixture Box &#8217;s"), anchor("campgrounds", "camp", "Fixture Camp")), GUIDE_URL
    )

    assert [(row["kind"], row["name"]) for row in rows] == [("waterboxes", "Fixture Box ’s"), ("campgrounds", "Fixture Camp")]
    assert rows[0]["geometry"] == {"type": "Point", "coordinates": [-103.5, 46.9]}
    assert rows[0]["link"] == "https://guide.example.org/waterboxes/box/"


def test_a_trail_guide_anchor_with_one_coordinate_refuses_the_page_rather_than_landing_half_a_point():
    with pytest.raises(PageLayoutChanged, match="data-lat and data-long"):
        parse_mdhta_trail_guide(
            guide_page(anchor("trailheads", "th", "Fixture TH"), anchor("waterboxes", "box", "Fixture", lon=None)), GUIDE_URL
        )


def test_a_trail_guide_with_no_trailhead_campground_or_waterbox_left_is_refused_as_a_changed_page():
    with pytest.raises(PageLayoutChanged, match="no trailhead"):
        parse_mdhta_trail_guide(guide_page(anchor("river-crossings", "ford", "Fixture Ford")), GUIDE_URL)


def test_a_shelter_with_a_fix_lands_its_point_and_one_with_only_a_mile_lands_with_no_geometry():
    rows = parse_foot_trail_shelters(SHELTER_LIST, SHELTERS_PAGE)

    assert [(row["name"], row["mile_marker"]) for row in rows] == [
        ("FIXTURE GARDEN", 9.4),
        ("FIXTURE MOUNTAIN SHELTER", 57.8),
        ("FIXTURE CREEK SHELTER", 122.6),
    ]
    lon, lat = rows[0]["geometry"]["coordinates"]
    assert (round(lat, 5), round(lon, 5)) == (34.77312, -94.86332)
    assert rows[2]["geometry"] is None  # a mile marker is not a place, and nothing is looked up from the name


def test_a_shelter_entry_in_neither_measured_shape_refuses_the_list():
    retyped = SHELTER_LIST.replace("at MM 122.6", "near mile 122.6")
    with pytest.raises(PageLayoutChanged, match="neither measured shape"):
        parse_foot_trail_shelters(retyped, SHELTERS_PAGE)


def parking_area(name: str, *items: str) -> str:
    return (
        f'<h3 style="margin-top:24px;"><strong>{name}:</strong> Fixture access.</h3><ul class="bullets02">{"".join(items)}</ul>'
    )


PARKING = (
    "<h1>Fixture Parking</h1><h2>Parking Areas</h2>"
    + parking_area(
        "Fixture Rd",
        "<li>Capacity: 8 vehicles, busy on weekends.</li>",
        "<li>Plowed in winter.</li>",
        "<li>Suitable for overnight parking.</li>",
        "<li>Map kiosk: no.</li>",
        "<li>Lat/Lon: 42.69936, -73.15358.</li>",
    )
    + parking_area(
        "Fixture Summit",
        "<li>Capacity: 50 vehicles.</li>",
        "<li>Fee required.</li>",
        "<li>Lat.Lon: 42.63798, -73.16646</li>",
        '<li>Other day use parking:<ul class="bullets02"><li><strong>Fixture Pull-off:</strong><ul class="bullets02">'
        "<li>Capacity 4 vehicles.</li><li>Not plowed in winter.</li></ul></li></ul></li>",
    )
    + "<h3><strong>Fixture Ave:</strong> No official parking area.</h3>"
    + parking_area(
        "Fixture St",
        "<li>Capacity: 20 vehicles (no campers).",
        "<li>Not recommended for overnight use.</li>",
        "<li>Lon/Lat: 42.40944, -73.14981.</li>",
    )
)


def test_each_parking_area_lands_its_facts_from_the_pages_own_phrases_and_nothing_else():
    rows = {row["name"]: row for row in parse_amc_berkshire_at_parking(PARKING, PARKING_URL)}

    assert rows["Fixture Rd"] == {
        "name": "Fixture Rd",
        "capacity_vehicles": 8,
        "overnight": "suitable",
        "winter_plowing": "plowed",
        "map_kiosk": False,
        "fee_required": None,
        "geometry": {"type": "Point", "coordinates": [-73.15358, 42.69936]},
    }
    # The nested pull-off's capacity and plowing are its own, not the Summit's.
    assert (rows["Fixture Summit"]["capacity_vehicles"], rows["Fixture Summit"]["winter_plowing"]) == (50, None)
    assert rows["Fixture Summit"]["fee_required"] is True
    assert rows["Fixture Ave"]["geometry"] is None


def test_a_parking_coordinate_labelled_lon_lat_is_still_placed_north_and_west():
    rows = {row["name"]: row for row in parse_amc_berkshire_at_parking(PARKING, PARKING_URL)}

    assert rows["Fixture St"]["geometry"]["coordinates"] == [-73.14981, 42.40944]
    assert rows["Fixture St"]["capacity_vehicles"] == 20  # the item the page never closed
    assert rows["Fixture St"]["overnight"] == "not_recommended"


def test_a_parking_area_that_states_two_coordinates_refuses_the_page():
    doubled = PARKING.replace("<li>Map kiosk: no.</li>", "<li>Lat/Lon: 42.1, -73.1.</li>")
    with pytest.raises(PageLayoutChanged, match="states 2 coordinates"):
        parse_amc_berkshire_at_parking(doubled, PARKING_URL)


COORDINATE_TABLE = (
    "<h2>GPS Coordinates</h2><table><tbody>"
    "<tr><td><div>Fixture St Park Access</div></td><td><div>34 51.807</div></td><td><div>83 05.880</div></td></tr>"
    "<tr><td><div>Fixture Boat Access</div></td><td><div>35 03.923</div></td><td><div>82 53.430</div></td></tr>"
    "</tbody></table>"
)


def test_an_unsigned_longitude_is_read_west_and_each_access_point_lands_its_fix():
    rows = parse_foothills_gps_coordinates(COORDINATE_TABLE, "https://conservancy.example.org/maps/")

    assert [row["name"] for row in rows] == ["Fixture St Park Access", "Fixture Boat Access"]
    assert rows[0]["geometry"]["coordinates"] == [-83.098, 34.86345]


def test_a_coordinates_row_with_a_cell_missing_refuses_the_table():
    broken = COORDINATE_TABLE.replace("<td><div>83 05.880</div></td>", "")
    with pytest.raises(PageLayoutChanged, match="2 cells"):
        parse_foothills_gps_coordinates(broken, "https://conservancy.example.org/maps/")


def test_a_point_south_of_the_equator_or_east_of_greenwich_is_refused_not_repaired():
    with pytest.raises(PageLayoutChanged):
        north_america(-34.8, -83.1, "fixture")
    assert north_america(34.8, 83.1, "fixture")["coordinates"] == [-83.1, 34.8]  # unsigned, read west


def test_html_lines_drop_scripts_and_break_at_blocks():
    assert html_lines("<p>One <b>two</b></p><script>var x = 1;</script><li>Three</li>") == ["One two", "Three"]


# --- the resource ----------------------------------------------------------------------------------------------------


def resource(key: str) -> PagePoints:
    return PagePoints(key=key, club="testclub", type="points_of_interest")


def test_a_wordpress_page_is_read_through_its_rest_route_and_each_row_links_the_page_and_carries_its_date(
    registry, requests_mock
):
    requests_mock.get(SHELTERS_REST, text=rest_page(SHELTER_LIST), headers={"Content-Type": "application/json"})
    proofs = {}

    rows = list(resource("foot_trail_shelters").rows(proofs))

    assert len(rows) == 3 and proofs == {"raw_testclub__foot_trail_shelters": 3}
    assert {row["source_url"] for row in rows} == {SHELTERS_PAGE}
    assert {row["page_modified_gmt"] for row in rows} == {"2025-11-11T21:30:44"}
    assert requests_mock.call_count == 1 and requests_mock.last_request.headers["User-Agent"] == _kinds.USER_AGENT


def test_the_change_check_is_the_read_and_its_answer_is_reused_so_a_page_costs_one_request_a_run(registry, requests_mock):
    requests_mock.get(GUIDE_URL, text=guide_page(anchor("trailheads", "th", "Fixture TH")), headers={"Content-Type": "text/html"})
    points = resource("mdhta_trail_guide_points")

    verdict, marker = points.change_check(None)
    rows = list(points.rows({}))

    assert verdict is Freshness.STALE and marker["rows"] == 1
    assert len(rows) == 1 and requests_mock.call_count == 1


def test_the_change_check_is_fresh_only_while_the_points_hash_as_the_last_load_did(registry, requests_mock):
    requests_mock.get(GUIDE_URL, text=guide_page(anchor("trailheads", "th", "Fixture TH")), headers={"Content-Type": "text/html"})
    points = resource("mdhta_trail_guide_points")
    _, marker = points.change_check(None)

    assert points.change_check(marker)[0] is Freshness.FRESH
    requests_mock.get(
        GUIDE_URL, text=guide_page(anchor("trailheads", "th", "Fixture TH", lat="46.95")), headers={"Content-Type": "text/html"}
    )
    assert points.change_check(marker)[0] is Freshness.STALE


@pytest.mark.parametrize(
    "answer",
    [
        {"status_code": 403, "text": "Forbidden"},
        {"status_code": 200, "text": "<html>Just a moment...</html>", "headers": {"cf-mitigated": "challenge"}},
    ],
    ids=["a 403", "a challenge"],
)
def test_a_wall_is_unknown_in_the_check_and_raises_in_the_read_never_an_empty_page(registry, requests_mock, answer):
    requests_mock.get(GUIDE_URL, **answer)
    points = resource("mdhta_trail_guide_points")

    assert points.change_check(None) == (Freshness.UNKNOWN, None)
    with pytest.raises(_notices.NoticeUnreadable):
        list(points.rows({}))


def test_a_page_that_now_redirects_to_another_host_is_refused(registry, requests_mock):
    requests_mock.get(GUIDE_URL, status_code=301, headers={"Location": "https://elsewhere.example.com/guide/"})
    requests_mock.get(
        "https://elsewhere.example.com/guide/",
        text=guide_page(anchor("trailheads", "th", "X")),
        headers={"Content-Type": "text/html"},
    )

    with pytest.raises(_notices.NoticeUnreadable, match="another host"):
        list(resource("mdhta_trail_guide_points").rows({}))


def test_a_pdf_served_where_the_page_was_is_refused_as_a_changed_page(registry, requests_mock):
    requests_mock.get(GUIDE_URL, content=b"%PDF-1.7", headers={"Content-Type": "application/pdf"})

    with pytest.raises(PageLayoutChanged, match="not HTML"):
        list(resource("mdhta_trail_guide_points").rows({}))


def test_points_land_through_the_lane_and_a_point_with_no_fix_lands_with_no_geometry(registry, store, requests_mock):
    requests_mock.get(SHELTERS_REST, text=rest_page(SHELTER_LIST), headers={"Content-Type": "application/json"})
    points = PagePoints(
        key="foot_trail_shelters", club="testclub", type="points_of_interest", cadence_override="hourly", cadence_reason="a test"
    )

    report = lane(store, points)

    assert report.outcome == "loaded"
    assert report.rows == {"raw_testclub__foot_trail_shelters": 3}
    con, counts = warehouse(store)
    con.execute("INSTALL spatial; LOAD spatial;")
    placed = con.execute(
        "select name, st_astext(st_geomfromgeojson(geometry::varchar)) from raw.raw_testclub__foot_trail_shelters "
        "where geometry is not null order by name"
    ).fetchall()
    assert [name for name, _ in placed] == ["FIXTURE GARDEN", "FIXTURE MOUNTAIN SHELTER"]
    (unplaced,) = con.execute("select count(*) from raw.raw_testclub__foot_trail_shelters where geometry is null").fetchone()
    assert unplaced == 1


def test_a_key_with_no_parser_or_a_query_string_its_host_forbids_is_refused_at_import(registry, tmp_path, monkeypatch):
    with pytest.raises(KeyError, match="no parser"):
        PAGE_PARSERS.pop("no_such_parser", None)
        sources = json.loads(registry.read_text())["sources"] + [{"key": "no_such_parser", "url": GUIDE_URL}]
        registry.write_text(json.dumps({"sources": sources}))
        _kinds._registry.cache_clear()
        page_points("no_such_parser")
    sources = [{"key": "foothills_gps_coordinates", "url": "https://foothillstrail.org/maps/?page=2"}]
    registry.write_text(json.dumps({"sources": sources}))
    _kinds._registry.cache_clear()
    with pytest.raises(KeyError, match="query string"):
        page_points("foothills_gps_coordinates")


def test_a_page_honours_its_rows_crawl_delay_and_the_default_gap_where_it_asks_none(registry):
    assert resource("foot_trail_shelters").crawl_delay == 10
    assert resource("mdhta_trail_guide_points").crawl_delay == _notices.DEFAULT_HOST_GAP_SECONDS
    assert resource("mdhta_trail_guide_points").part == "points"
