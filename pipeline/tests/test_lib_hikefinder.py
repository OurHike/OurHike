"""lib/hikefinder.py - reading one exported hike page into facts (#1427).

Pages are BUILT HERE rather than checked in, in the shape measured against
the live export on 2026-09-15: a `<h1>`, a `card` per section with its `<h2>`,
and twelve `<strong>Label:</strong>` fields two to a row. A fixture that
builds its own page is self-documenting about what "the export's shape" means,
which a saved 20 KB of Bootstrap is not (TESTING.md).

What is pinned is what the maintainer asked to be kept - every field, and the
Features tags above all - plus the two judgements this module makes on its own:
that `N/A` is absent rather than a value, and that a coordinate off this ground
is refused rather than placed.
"""

from __future__ import annotations

from lib.hikefinder import (
    ParsedHike,
    hike_problems,
    listing_count,
    listing_ids,
    parse_coordinate,
    parse_gpx,
    parse_hike,
)

FIELDS = {
    "Length": "4.8 miles",
    "Difficulty": '<span class="badge bg-info">Moderate</span>',
    "Estimated Time": "3.0 hours",
    "Route Type": "Out and back",
    "Dogs": "Allowed on leash",
    "Park": "Harriman State Park",
    "Region": "Long Distance Trails",
    "Author": "Daniel Chazin",
    "GPS Coordinates": '41.244159,\n -74.286675 <br><small class="text-muted">(Parking location)</small>',
    "Features": '<span class="badge bg-secondary me-1 mb-1">Views</span><span class="badge bg-secondary me-1 mb-1">Birding</span>',
    "Publish Date": "July 11, 2013",
    "Last Updated": "N/A",
}

CARDS = {
    "Summary": "<p>A short walk to two rock outcrops.</p>",
    "Directions to Trailhead": '<div class="hike-description">Park in the gravel area.</div>',
    "Description": "<p>Follow the white blazes of the Appalachian Trail.</p><p>Turn left onto the Timp-Torne Trail.</p>",
}


def page(fields: dict | None = None, cards: dict | None = None, title: str = "A.T. North of Route 17A", gpx: bool = False) -> str:
    """One detail page in the export's own shape."""
    fields = FIELDS if fields is None else fields
    cards = CARDS if cards is None else cards
    rows = "".join(f'<div class="col-md-6"><strong>{label}:</strong> {value}</div>' for label, value in fields.items())
    blocks = "".join(
        f'<div class="card"><div class="card-header"><h2 class="h6">{name}</h2></div><div class="card-body">{body}</div></div>'
        for name, body in cards.items()
    )
    download = '<a href="download_gpx.php?id=7">Download GPX</a>' if gpx else ""
    return (
        f"<html><body><h1 class='display-5'>{title}</h1>"
        f'<div class="card"><div class="card-header"><h2 class="h5">Hike Information</h2></div>'
        f'<div class="card-body"><div class="row mb-3">{rows}</div></div></div>'
        f"{blocks}{download}"
        "<script>const routeCoordinates = [[1,2]];</script></body></html>"
    )


def parsed(**kwargs) -> ParsedHike:
    found = parse_hike(page(**kwargs), 7, "https://example.test/hike.php?id=7")
    assert found is not None
    return found


# --- the listing is this import's only index -----------------------------------


def test_listing_ids_are_unique_and_sorted_and_the_count_is_read_apart_from_them():
    """The two are kept apart on purpose: a listing whose printed total stops
    matching the links it carries has paginated or lost a row, and
    fetch_hikefinder.py refuses the run rather than caching the shorter
    answer as a complete export."""
    markup = 'Results (3 hikes found) <a href="hike.php?id=9">a</a><a href="hike.php?id=2">b</a><a href="hike.php?id=9">c</a>'
    assert listing_ids(markup) == [2, 9]
    assert listing_count(markup) == 3


def test_a_listing_that_prints_no_total_reads_as_none_rather_than_zero():
    assert listing_count('<a href="hike.php?id=1">a</a>') is None


# --- every field the page carries ----------------------------------------------


def test_every_labelled_field_is_read_by_its_label():
    hike = parsed()
    assert hike.id == 7
    assert hike.name == "A.T. North of Route 17A"
    assert hike.stated_miles == 4.8
    assert hike.difficulty == "Moderate"
    assert hike.estimated_hours == 3.0
    assert hike.route_type == "Out and back"
    assert hike.dogs == "Allowed on leash"
    assert hike.park == "Harriman State Park"
    assert hike.region == "Long Distance Trails"
    assert hike.author == "Daniel Chazin"
    assert hike.published_on == "July 11, 2013"


def test_the_features_badges_are_kept_in_page_order_and_unmapped():
    """The maintainer's "especially the tags". They are the facets the finder
    filters on, and a badge ships as the word the publisher printed - no
    vocabulary of this build's own sits between the two."""
    assert parsed().features == ["Views", "Birding"]


def test_every_labelled_value_is_also_kept_raw_so_a_field_nobody_has_used_yet_survives():
    raw = parsed().raw_fields
    assert raw["Route Type"] == "Out and back"
    assert set(FIELDS) - {"Last Updated"} <= set(raw)


def test_na_is_read_as_absent_rather_than_carried_as_the_string():
    """`N/A` is the export's own word for "there isn't one". Carrying it
    would print on a card as though it meant something."""
    assert parsed().updated_on is None


def test_the_free_text_cards_are_read_by_their_heading():
    hike = parsed()
    assert hike.summary == "A short walk to two rock outcrops."
    assert hike.description[0].startswith("Follow the white blazes")
    assert len(hike.description) == 2
    # The Directions card is a bare <div> with no paragraph element at all,
    # and it is the only text saying where to leave the car.
    assert hike.directions == ["Park in the gravel area."]


def test_a_missing_card_is_an_empty_list_rather_than_a_parse_failure():
    """Two of the 385 pages carry no Directions card. Refusing them would be
    this module inventing a completeness the export does not promise."""
    hike = parsed(cards={"Description": "<p>Walk.</p>"})
    assert hike.directions == []
    assert hike.summary is None
    assert hike.description == ["Walk."]


def test_a_page_with_no_title_is_not_understood():
    assert parse_hike("<html><body><p>nothing</p></body></html>", 7, "u") is None


# --- the one coordinate the export publishes -----------------------------------


def test_the_coordinate_carries_the_export_s_own_word_for_what_it_is():
    """ "Parking location" is not "trailhead", and a route built from it has to
    cross that gap knowingly."""
    start = parsed().start
    assert (start.lat, start.lon) == (41.244159, -74.286675)
    assert start.label == "Parking location"


def test_a_coordinate_off_this_ground_is_refused_rather_than_placed():
    """A pin in the ocean is a bug a reviewer can see; a transposed pair
    quietly placed 3,000 km away is not."""
    assert parse_coordinate("<div>-74.286675, 41.244159</div>") is None
    assert parse_coordinate("<div>0.0, 0.0</div>") is None


def test_a_page_with_no_coordinate_parses_and_says_so_in_its_problems():
    fields = {label: value for label, value in FIELDS.items() if label != "GPS Coordinates"}
    hike = parsed(fields=fields)
    assert hike.start is None
    assert any("nowhere to start from" in problem for problem in hike_problems(hike))


# --- which kind of page this is ------------------------------------------------


def test_the_gpx_link_is_what_says_a_page_carries_a_published_route():
    assert parsed().has_published_route is False
    routed = parsed(gpx=True)
    assert routed.has_published_route is True
    assert routed.gpx_url == "download_gpx.php?id=7"


# --- the published track -------------------------------------------------------

GPX = """<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
  <trk><name>Bear Mountain</name><trkseg>
    <trkpt lat="41.0000" lon="-74.0000"><ele>315.08</ele></trkpt>
    <trkpt lat="41.0100" lon="-74.0000"><ele>320.00</ele></trkpt>
    <trkpt lat="41.0200" lon="-74.0000"/>
  </trkseg></trk>
</gpx>"""


def test_a_track_keeps_its_points_its_name_and_its_metres():
    track = parse_gpx(GPX)
    assert track is not None
    assert track.name == "Bear Mountain"
    assert len(track.points) == 3
    assert track.points[0].ele_m == 315.08
    # 0.02 degrees of latitude is about 2.2 km, which is about 1.38 miles.
    assert 1.3 < track.length_miles < 1.45


def test_a_point_with_no_elevation_keeps_its_position_and_carries_none():
    """Absent means unmeasured. A zero here would be a sea-level claim about
    a summit."""
    assert parse_gpx(GPX).points[2].ele_m is None


def test_a_gpx_with_no_track_point_is_no_track_rather_than_an_empty_one():
    assert parse_gpx('<?xml version="1.0"?><gpx xmlns="http://www.topografix.com/GPX/1/1"></gpx>') is None


def test_unparseable_xml_is_no_track_rather_than_an_exception():
    assert parse_gpx("<gpx><trkpt") is None


def test_a_track_declaring_no_namespace_is_still_read():
    """gpx.studio writes GPX 1.1, but a file that declared none holds the same
    trkpt elements and there is no reason to refuse it."""
    plain = '<gpx><trk><trkseg><trkpt lat="41.0" lon="-74.0"/><trkpt lat="41.01" lon="-74.0"/></trkseg></trk></gpx>'
    track = parse_gpx(plain)
    assert track is not None and len(track.points) == 2


# --- what the cache tells a reviewer -------------------------------------------


def test_problems_name_what_is_missing_and_a_complete_page_has_none():
    assert hike_problems(parsed()) == []
    bare = parsed(fields={"Length": "", "Difficulty": "", "Route Type": "", "Features": "", "Author": ""}, cards={})
    problems = " ".join(hike_problems(bare))
    assert "nowhere to start from" in problems
    assert "nothing to build a route from" in problems
    assert "no Features tags" in problems
