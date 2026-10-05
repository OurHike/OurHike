"""extract/_pages_content.py, decision 54 wave 5's page readers for the content types (section K), against mocked
servers.

Each site parser is run over invented markup shaped like the live page it was written from (section K's reads of
2026-10-04, each sources.json row's `notes`), and the reader around them over requests_mock. Nothing reaches the
network: conftest.py's socket guard stays on.

The cases are the ones decision 55 and a changed page turn on: a row carries facts and the link and nothing else, a
figure the page states ambiguously lands as its text with no number, a page that no longer has its parser's shape
refuses rather than landing what still matched, a page that lists nothing is a changed shape and never an empty
list, the reader never leaves its host or asks a query string its site's robots.txt was not read for, and one run
reads each page once.
"""

import json

import pytest

from extract import _kinds, _notices, _pages_content
from extract._contract import all_resources, discover
from extract._pages_content import (
    MAX_FACT_CHARS,
    SITE_PARSERS,
    TYPE_COLUMNS,
    ContentPages,
    LayoutChanged,
    Page,
    SiteParser,
    blocks,
    content_pages,
    feet,
    labelled,
    miles,
    number,
    parse_html,
    sections,
)
from lib.freshness_state import Freshness

MAZAMAS = "https://mazamas.org/hikelist/"
TAHOE = "https://tahoerimtrail.org/day-hiking/"
TAHOE_THEME = "https://tahoerimtrail.org/day-hiking/alpine-lakes/"
SITE = "https://club.example.org/hikes/"


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """A sources.json holding one entry per site, in place of the real one."""
    path = tmp_path / "sources.json"
    sources = [
        {"key": "mazamas_hike_list", "url": MAZAMAS, "kind": "published_hikes"},
        {"key": "tahoe_rim_day_hikes", "url": TAHOE, "kind": "published_hikes"},
        {"key": "club_hikes", "url": SITE, "kind": "published_hikes"},
        {"key": "club_hikes_query", "url": SITE + "?page=2", "kind": "published_hikes"},
    ]
    path.write_text(json.dumps({"sources": sources}))
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()
    yield path
    _kinds._registry.cache_clear()


@pytest.fixture(autouse=True)
def no_gap(monkeypatch):
    """No host is asked anything, so the readers' courtesy gaps are 0 here, and no test's kept answer reaches another."""
    monkeypatch.setattr(_notices, "_pause", lambda seconds: None)
    monkeypatch.setattr(_notices, "_ANSWERS", {})


@pytest.fixture
def club_parser(monkeypatch):
    """A site parser for club.example.org whose rows the test sets, so the reader is tested apart from any site."""
    found: dict = {"rows": [{"name": "Fixture Hike", "link": SITE}], "follow": None}

    def read(page: Page, fetch):
        if found["follow"]:
            fetch(found["follow"])
        return [dict(row) for row in found["rows"]]

    monkeypatch.setitem(SITE_PARSERS, "club_hikes", SiteParser(read))
    return found


def mazamas_page(items: dict[str, list[str]]) -> str:
    blocks_html = "".join(
        f'<article class="block-richtextblock block"><h3 class="block--title">{region}</h3>'
        '<div class="rte"><p><strong>List includes: hike name, hike distance, hike elevation, appx. driving '
        "distance, trailhead fee</strong></p><ul>" + "".join(f"<li>{line}</li>" for line in lines) + "</ul></div></article>"
        for region, lines in items.items()
    )
    details = '<article class="block-richtextblock block"><h3 class="block--title">Hike Details</h3><ul><li>x</li></ul></article>'
    return f"<html><body><main>{details}{blocks_html}</main></body></html>"


MAZAMAS_ITEMS = {
    "Columbia River Gorge Hikes": [
        "Fixture Butte 7.0 miles 1,500 feet 84 miles, no",
        "Fixture Mountain-Dog 11.0 miles 1.300 feet 130 miles, yes",
    ],
    "Mt. Hood": ["Fixture Ranch varies varies 194 miles, no", "Fixture Loop Trail 37.6 miles 9,800 feet varies, yes"],
    "Clackamas River": ["Fixture Creek 4.6 miles 1,400 feet 90 miles,no"],
    "Oregon Coast": [
        "Fixture Linear Trail (1-way) 19 miles 400 feet 50 miles, no",
        "Fixture Head 3.4 miles 1,100 feet 182 miles*, no",
    ],
}


def mazamas_rows(items=MAZAMAS_ITEMS) -> list[dict]:
    return SITE_PARSERS["mazamas_hike_list"].read(Page(MAZAMAS, parse_html(mazamas_page(items))), None)


# --- The facts' patterns -------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [("1,540", 1540.0), ("4.6", 4.6), (".5", 0.5), ("19", 19.0), ("1.300", None), ("0.125", 0.125), ("varies", None)],
)
def test_a_number_is_read_only_where_the_page_writes_one_plainly(text, expected):
    assert number(text) == expected


def test_a_distance_and_a_height_keep_the_words_they_were_read_from():
    assert miles("a 4½-mile St. Moritz loop") == (4.5, "4½-mile")
    assert miles("Distance: 12 miles round trip") == (12.0, "12 miles")
    assert miles("2.6 mi round trip") == (2.6, "2.6 mi")
    assert feet("1,540 feet of gain") == (1540.0, "1,540 feet")
    assert miles("no distance") == (None, None)


def test_a_section_is_a_heading_and_the_blocks_up_to_the_next_heading_of_its_level():
    root = parse_html("<h2>A</h2><p>Distance: 1 mile</p><h3>A.1</h3><p>x</p><h2>B</h2><p>Classification: Easy</p>")
    found = sections(blocks(root), 2)
    assert [(heading.text, [b.text for b in body]) for heading, body in found] == [
        ("A", ["Distance: 1 mile", "A.1", "x"]),
        ("B", ["Classification: Easy"]),
    ], "a lower heading sits inside its section; the next h2 ends it"
    assert labelled(found[0][1]) == {"distance": "1 mile"}


def test_an_unclosed_list_item_closes_at_the_next_one():
    root = parse_html("<ul><li>One<li>Two</ul>")
    assert [node.text() for node in root.find_all("li")] == ["One", "Two"]


# --- The Mazamas' Hike List View -----------------------------------------------------------------------------------


def test_the_mazamas_list_lands_one_row_a_hike_with_its_numbers_and_their_words():
    rows = {row["name"]: row for row in mazamas_rows()}

    assert len(rows) == 7
    butte = rows["Fixture Butte"]
    assert (butte["distance_mi"], butte["elevation_gain_ft"], butte["driving_mi"]) == (7.0, 1500.0, 84.0)
    assert (butte["section"], butte["route_type"], butte["trailhead_fee"]) == ("Columbia River Gorge Hikes", "round trip", False)
    assert butte["driving_from"] == "Gateway P&R (I-84 Exit 7)" and butte["link"] == MAZAMAS
    assert rows["Fixture Linear Trail (1-way)"]["route_type"] == "one way", "the page says round trip unless noted"
    assert rows["Fixture Head"]["driving_from"] == "Durham P&R (I-5 Exit 290)", "an asterisk names the other start"
    assert rows["Fixture Linear Trail (1-way)"]["driving_from"] == "Tanasborne (185th & Hwy. 26)"


def test_a_figure_the_list_states_ambiguously_lands_as_its_text_with_no_number():
    rows = {row["name"]: row for row in mazamas_rows()}

    assert (rows["Fixture Mountain-Dog"]["elevation_gain_ft"], rows["Fixture Mountain-Dog"]["elevation_gain_text"]) == (
        None,
        "1.300 feet",
    )
    ranch = rows["Fixture Ranch"]
    assert (ranch["distance_mi"], ranch["distance_text"], ranch["elevation_gain_ft"]) == (None, "varies", None)
    assert rows["Fixture Loop Trail"]["driving_mi"] is None


def test_a_reworded_mazamas_item_refuses_rather_than_landing_what_still_matches():
    items = {**MAZAMAS_ITEMS, "Mt. Hood": ["Fixture Ranch is about seven miles from the trailhead"]}
    with pytest.raises(LayoutChanged, match="not 'name miles feet drive, fee'"):
        mazamas_rows(items)


def test_a_mazamas_region_that_disappears_or_appears_refuses():
    missing = {region: lines for region, lines in MAZAMAS_ITEMS.items() if region != "Oregon Coast"}
    with pytest.raises(LayoutChanged, match="regions are now"):
        mazamas_rows(missing)
    with pytest.raises(LayoutChanged, match="not one of the regions"):
        mazamas_rows({**MAZAMAS_ITEMS, "Fixture Region": ["Fixture Peak 1.0 miles 100 feet 10 miles, no"]})


# --- The Tahoe Rim Trail's day hikes --------------------------------------------------------------------------------


def tahoe_theme(hikes: int = 2, footer: bool = True) -> str:
    body = "".join(
        f"<h3><img src='x.jpg'/><strong>Fixture Lake {n} Hike</strong></h3>"
        f"<p><strong>Classification</strong>: Moderate</p><p><strong>Distance:</strong> {n}.5 miles round trip</p>"
        "<p><strong>Highlights:</strong> Fixture highlights from the association.</p>"
        "<p><strong>Location:</strong> Fixture trailhead</p><p><strong>Bikes Allowed:</strong> No</p>"
        "<p><strong>Access from</strong>: Fixture Shore</p><p><strong>Description:</strong> Fixture turn-by-turn.</p>"
        for n in range(1, hikes + 1)
    )
    tail = "<h3>Office</h3><p>128 Fixture Street</p>" if footer else ""
    return f"<html><body><h1>Alpine Lakes</h1>{body}{tail}</body></html>"


TAHOE_INDEX = f'<html><body><h1>Day Hiking</h1><a href="{TAHOE_THEME}"><h4>Alpine Lakes</h4></a></body></html>'


def test_tahoe_rims_index_leads_to_each_theme_page_and_a_hike_lands_its_facts_never_its_prose(registry, requests_mock):
    requests_mock.get(TAHOE, text=TAHOE_INDEX)
    requests_mock.get(TAHOE_THEME, text=tahoe_theme())

    rows = list(content_pages("tahoe_rim_day_hikes", club="tahoe_rim", type="suggested_hikes").rows({}))

    assert [row["name"] for row in rows] == ["Fixture Lake 1 Hike", "Fixture Lake 2 Hike"], "the footer's h3s are no hike"
    first = rows[0]
    assert (first["difficulty"], first["distance_mi"], first["route_type"], first["place"]) == (
        "Moderate",
        1.5,
        "round trip",
        "Fixture trailhead",
    )
    assert (first["section"], first["bikes_allowed"], first["access_from"], first["link"]) == (
        "Alpine Lakes",
        "No",
        "Fixture Shore",
        TAHOE_THEME,
    )
    assert "Fixture highlights" not in json.dumps(rows) and "turn-by-turn" not in json.dumps(rows)


def test_a_tahoe_theme_page_with_no_hike_left_on_it_refuses(registry, requests_mock):
    requests_mock.get(TAHOE, text=TAHOE_INDEX)
    requests_mock.get(TAHOE_THEME, text=tahoe_theme(hikes=0))

    with pytest.raises(LayoutChanged, match="no h3 with a Distance"):
        list(content_pages("tahoe_rim_day_hikes", club="tahoe_rim", type="suggested_hikes").rows({}))


# --- The reader ------------------------------------------------------------------------------------------------------


def club(key: str = "club_hikes") -> ContentPages:
    return content_pages(key, club="testclub", type="suggested_hikes")


def test_a_row_carries_every_column_of_its_type_and_the_count_is_its_proof(registry, requests_mock, club_parser):
    requests_mock.get(SITE, text="<html><body><p>Fixture</p></body></html>")
    proofs: dict = {}

    (row,) = list(club().rows(proofs))

    assert set(row) == set(TYPE_COLUMNS["suggested_hikes"]) and row["name"] == "Fixture Hike"
    assert proofs == {"raw_testclub__club_hikes": 1} and club().exact_proof


def test_a_column_outside_the_types_allowlist_refuses_so_no_description_can_land(registry, requests_mock, club_parser):
    requests_mock.get(SITE, text="<p>Fixture</p>")
    club_parser["rows"] = [{"name": "Fixture Hike", "description": "Fixture prose."}]

    with pytest.raises(ValueError, match="outside suggested_hikes's columns"):
        list(club().rows({}))


def test_a_fact_as_long_as_a_paragraph_refuses_as_prose(registry, requests_mock, club_parser):
    requests_mock.get(SITE, text="<p>Fixture</p>")
    club_parser["rows"] = [{"name": "x" * (MAX_FACT_CHARS + 1)}]

    with pytest.raises(ValueError, match="prose rather than a fact"):
        list(club().rows({}))


def test_a_page_that_lists_nothing_is_a_changed_shape_never_an_empty_list(registry, requests_mock, club_parser):
    requests_mock.get(SITE, text="<p>Fixture</p>")
    club_parser["rows"] = []

    with pytest.raises(LayoutChanged, match="lists no item"):
        list(club().rows({}))
    assert club().change_check(None) == (Freshness.UNKNOWN, None)


def test_the_change_checks_read_is_the_runs_one_read_and_the_same_rows_are_fresh(registry, requests_mock, club_parser):
    requests_mock.get(SITE, text="<p>Fixture</p>")
    resource = club()

    verdict, marker = resource.change_check(None)
    rows = list(resource.rows({}))

    assert verdict is Freshness.STALE and len(rows) == 1
    assert requests_mock.call_count == 1, "the check's read is kept for the read"
    assert resource.change_check(marker)[0] is Freshness.FRESH
    club_parser["rows"] = [{"name": "Fixture Hike, renamed", "link": SITE}]
    assert resource.change_check(marker)[0] is Freshness.STALE


def test_a_wall_is_unknown_and_never_read_past(registry, requests_mock, club_parser):
    requests_mock.get(SITE, status_code=403)

    assert club().change_check(None) == (Freshness.UNKNOWN, None)
    with pytest.raises(_notices.NoticeUnreadable, match="403"):
        list(club().rows({}))


def test_a_link_off_the_sites_host_or_with_a_query_string_is_never_followed(registry, requests_mock, club_parser):
    requests_mock.get(SITE, text="<p>Fixture</p>")
    club_parser["follow"] = "https://elsewhere.example.org/hike/"
    with pytest.raises(LayoutChanged, match="which is not read"):
        list(club().rows({}))
    club_parser["follow"] = SITE + "?page=2"
    with pytest.raises(LayoutChanged, match="query string"):
        list(club().rows({}))
    assert not [r for r in requests_mock.request_history if "elsewhere" in r.url or "page=2" in r.url]


def test_a_registry_url_with_a_query_string_is_refused_at_import(registry, club_parser, monkeypatch):
    monkeypatch.setitem(SITE_PARSERS, "club_hikes_query", SITE_PARSERS["club_hikes"])
    with pytest.raises(ValueError, match="query string"):
        content_pages("club_hikes_query")


def test_a_site_with_no_parser_is_refused_at_import(registry):
    with pytest.raises(KeyError, match="no parser"):
        content_pages("club_hikes")


# --- Every registered site, over its fixture's markup ---------------------------------------------------------------


def registered_pages() -> list[ContentPages]:
    return [r for r in all_resources(discover()) if isinstance(r, ContentPages)]


@pytest.mark.parametrize("resource", registered_pages(), ids=lambda r: r.key)
def test_every_site_parser_reads_its_fixture_markup_into_the_rows_fixture_mode_lands(resource, requests_mock):
    """The real registry row and its parser over make_dbt_fixtures.py's invented pages (the markup measured live), so
    a parser and its fixture cannot drift apart without this saying which. No prose word of a fixture lands."""
    import make_dbt_fixtures

    for url, content_type, body in make_dbt_fixtures._k_pages_documents()[resource.key]:
        requests_mock.get(url, text=body, headers={"Content-Type": content_type})

    rows = list(resource.rows({}))

    assert len(rows) == make_dbt_fixtures.K_PAGES_ROWS[resource.key]
    landed = json.dumps(rows, ensure_ascii=False).lower()
    assert not [word for word in ("fixture prose", "fixture description", "fixture directions", "fixture paragraph",
                                  "fixture highlights", "fixture note", "fixture water prose", "descripción",
                                  "fixture supervisor", "fixture@example.org", "555.0100", "fixture credit",
                                  "fixture explanation", "fixture camp", "34.9", "36.72036")
                if word in landed], resource.key  # fmt: skip


# --- The sites' own refusals ----------------------------------------------------------------------------------------


def nc_parks(registry_path, monkeypatch):
    """nc_parks_trails over a registry holding only it."""
    registry_path.write_text(json.dumps({"sources": [{"key": "nc_parks_trails", "url": NC_INDEX}]}))
    _kinds._registry.cache_clear()
    return content_pages("nc_parks_trails", club="nc_dpr", type="suggested_hikes")


NC_INDEX = "https://www.ncparks.gov/state-parks"
NC_TABLE = (
    "<table><tr><th>Trail Name</th><th>Blaze</th><th>Length</th><th>Difficulty</th><th>Trail Use</th><th>Accessible</th>"
    "</tr><tr><td>Fixture Trail</td><td>red</td><td>0.8-mile one way</td><td>Strenuous</td><td>Hiking only</td>"
    "<td>No</td></tr></table>"
)


def test_a_park_with_no_trails_page_has_no_row_and_stops_nothing(registry, requests_mock, monkeypatch):
    requests_mock.get(NC_INDEX, text='<a href="/state-parks/fixture-park">x</a><a href="/state-parks/fixture-area">y</a>')
    requests_mock.get(f"{NC_INDEX}/fixture-park/trails", text=f"<title>Fixture: Trails | NC State Parks</title>{NC_TABLE}")
    requests_mock.get(f"{NC_INDEX}/fixture-area/trails", status_code=404)

    (row,) = list(nc_parks(registry, monkeypatch).rows({}))

    assert (row["name"], row["place"], row["distance_mi"], row["route_type"]) == ("Fixture Trail", "Fixture", 0.8, "one way")


def test_a_park_table_with_a_column_nobody_has_read_refuses(registry, requests_mock, monkeypatch):
    requests_mock.get(NC_INDEX, text='<a href="/state-parks/fixture-park">x</a>')
    changed = NC_TABLE.replace("<th>Accessible</th>", "<th>Fixture Column</th>")
    requests_mock.get(f"{NC_INDEX}/fixture-park/trails", text=f"<title>Fixture: Trails | NC State Parks</title>{changed}")

    with pytest.raises(LayoutChanged, match="NC_PARKS_COLUMNS does not read"):
        list(nc_parks(registry, monkeypatch).rows({}))


def test_a_foothills_paragraph_continues_a_label_only_in_that_labels_shape():
    found = blocks(
        parse_html(
            "<p>Difficulty: A1 to A2 – strenuous</p><p>A11 to A10 easy to moderate</p><p>Trail Head: A1 Fixture Park</p>"
            "<p>A2 Fixture Mountain</p><p>*Campers are asked to fill out a registration envelope.</p><p>Features:</p>"
        )
    )
    facts = _pages_content._foothills_facts(found)
    assert facts == {
        "difficulty": ["A1 to A2 – strenuous", "A11 to A10 easy to moderate"],
        "trail head": ["A1 Fixture Park", "A2 Fixture Mountain"],
    }, "a note for campers is the conservancy's prose, not a trailhead"


FOOTHILLS_INDEX = "https://foothillstrail.org/section-by-section-2/"
FOOTHILLS_SECTION = "https://foothillstrail.org/portfolio/fixture-s1/"
# Two trailheads shaped like the S1 spur's, which monthly run 20 (2026-10-05) refused: 'S1 Sassafras Mountain, SC Hwy
# 178, F Van Clayton Memorial Hw…', 167 characters for both ends joined. These are 90 and 86 characters, 178 joined.
FOOTHILLS_LONG_HEADS = [
    "S1 Fixture Mountain, SC Hwy 178, Fixture Memorial Highway, 4.5 miles north of Rocky Bottom",
    "S2 Fixture Gorge Access, SC Hwy 130, Fixture Lake Road, 2.0 miles south of Fixture Gap",
]


def foothills(registry_path, requests_mock, trail_heads: list[str]) -> ContentPages:
    """foothills_sections over a registry holding only it: an index linking one section whose Trail Head lines are these."""
    registry_path.write_text(json.dumps({"sources": [{"key": "foothills_sections", "url": FOOTHILLS_INDEX}]}))
    _kinds._registry.cache_clear()
    requests_mock.get(FOOTHILLS_INDEX, text=f'<h1>Section By Section</h1><a href="{FOOTHILLS_SECTION}"></a><h2>Fixture S1</h2>')
    heads = f"<p>Trail Head: {trail_heads[0]}</p>" + "".join(f"<p>{head}</p>" for head in trail_heads[1:])
    requests_mock.get(
        FOOTHILLS_SECTION,
        text=f"<h1>Fixture Mountain (S1) To Fixture Gorge (S2)</h1><p>Distance: 3.5 miles</p>{heads}<p>Features:</p>",
    )
    return content_pages("foothills_sections", club="foothills", type="suggested_hikes")


def test_a_foothills_section_whose_two_trailheads_join_past_the_fact_cap_lands_both_ends_joined(registry, requests_mock):
    """Each trailhead is one fact under MAX_FACT_CHARS; joined by '; ' they are two facts, not a paragraph."""
    assert all(len(head) <= MAX_FACT_CHARS for head in FOOTHILLS_LONG_HEADS)
    assert len("; ".join(FOOTHILLS_LONG_HEADS)) > MAX_FACT_CHARS

    (row,) = list(foothills(registry, requests_mock, FOOTHILLS_LONG_HEADS).rows({}))

    assert row["place"] == "; ".join(FOOTHILLS_LONG_HEADS)
    assert (row["name"], row["distance_mi"]) == ("Fixture Mountain (S1) To Fixture Gorge (S2)", 3.5)


def test_a_foothills_trailhead_longer_than_the_fact_cap_on_its_own_still_refuses_as_prose(registry, requests_mock):
    one_paragraph = "S1 " + "fixture paragraph " * 9
    assert len(one_paragraph.strip()) > MAX_FACT_CHARS

    with pytest.raises(ValueError, match="place is 164 characters, prose rather than a fact"):
        list(foothills(registry, requests_mock, [one_paragraph, FOOTHILLS_LONG_HEADS[1]]).rows({}))


def test_a_tuscarora_section_with_no_elevation_line_refuses():
    lines = "<p>Section 1: Fixture Gap</p><p>Fixture Road to Fixture Gap, 12 miles.</p><p>Highlights: x</p>"
    pages = {"https://www.hikethetuscarora.org/section-1-3": Page("x", parse_html(lines))}
    home = Page("https://www.hikethetuscarora.org/", parse_html('<a href="/section-1-3">Section 1-3</a>'))
    with pytest.raises(LayoutChanged, match="states no 'Max Elevation"):
        SITE_PARSERS["patc_tuscarora_sections"].read(home, pages.get)


def test_a_bold_line_with_no_county_after_it_is_not_a_kta_hike():
    page = Page(
        "https://www.kta-hike.org/favorite-hikes-in-pennsylvania.html",
        parse_html(
            "<h2>Favorite Fixture Hikes - Fixture</h2><div class='paragraph'><strong>In order of beginner to most "
            "strenuous</strong><br/><strong>Fixture Trail</strong><br/>Fixture County<br/>https://fixture.example.org/"
            "</div>"
        ),
    )
    (row,) = SITE_PARSERS["kta_favorite_hikes"].read(page, None)
    assert (row["name"], row["place"], row["section"]) == ("Fixture Trail", "Fixture County", "Favorite Fixture Hikes")


def test_a_passage_end_lands_the_coordinates_the_page_states_signed_by_hemisphere():
    assert _pages_content._coordinates("GPS Coordinates: 31.33367° N, 110.28276° W") == (31.33367, -110.28276)
    assert _pages_content._coordinates("no coordinates") == (None, None)


def test_an_amc_card_that_links_off_the_itineraries_is_not_a_trip():
    page = Page(
        "https://www.outdoors.org/resources/itineraries/",
        parse_html(
            "<h2>Region</h2><h5>Fixture Trip</h5><p>Easy | 1 Day</p>"
            '<a href="https://www.outdoors.org/resources/itineraries/fixture/">x</a>'
            '<h5>Shop Fixture Maps</h5><a href="https://amcstore.outdoors.org/collections/books-maps">y</a>'
        ),
    )
    (row,) = SITE_PARSERS["amc_itineraries"].read(page, None)
    assert (row["name"], row["difficulty"], row["duration"]) == ("Fixture Trip", "Easy", "1 Day")


def test_a_distance_with_two_figures_lands_as_its_words_and_no_number():
    single = _pages_content.single_miles
    assert single("1.8 miles, one way") == (1.8, "1.8 miles, one way")
    assert single(".53 miles") == (0.53, ".53 miles")
    assert single("4 ½-mile loop") == (4.5, "4 ½-mile loop")
    for text in ("Pink trail, 2 to 4 miles", "0.6 miles, 0.4 paved", "11.5 miles in 2 loops", "27+ miles"):
        assert single(text) == (None, text), text
    assert single(None) == (None, None)


def test_a_florida_map_whose_tooltips_do_not_match_its_stated_count_refuses():
    tip = '<span class="uael-tooltip-text"><p><strong>Fixture Trail</strong></p><p>Length: 1 mile</p></span>'
    page = Page(
        "https://floridatrail.org/day-hike/",
        parse_html(
            f'<h3>Grab-And-Go FT Hikes:</h3><div class="uael-hotspot-container" data-length="2">{tip}</div>'
            f'<h3>Other Trail Hikes:</h3><div class="uael-hotspot-container" data-length="1">{tip}</div>'
        ),
    )
    with pytest.raises(LayoutChanged, match="states 2 hikes and holds 1"):
        SITE_PARSERS["fta_day_hikes"].read(page, None)


def test_a_florida_shape_lands_only_where_the_line_names_one():
    assert _pages_content._fta_route("4.8 mile loop") == "loop"
    assert _pages_content._fta_route("3.6 miles round trip") == "round trip"
    for text in ("8.1 miles linear", "10.2 miles loop/linear", "1.7 mile loop + 1.2 mile spur", "11.2 miles loop and linear"):
        assert _pages_content._fta_route(text) is None, text


def test_a_wisconsin_trail_heading_with_no_length_lands_no_row():
    found = parse_html(
        "<h1>Hiking</h1><h2>Fixture State Park</h2><h3>Fixture trail (Pink trail, 2 to 4 miles)</h3>"
        "<h3>Fixture Ridge Trail — 0.55 miles</h3><h3>Fixture Hollow trail</h3><h3>Trail safety</h3>"
    )
    pages = {"https://dnr.wisconsin.gov/topic/parks/fixture/recreation/hiking": Page("https://dnr.wisconsin.gov/x", found)}
    index = Page(
        "https://dnr.wisconsin.gov/sitemap.xml",
        parse_html("<sitemapindex><sitemap><loc>https://dnr.wisconsin.gov/sitemap.xml?page=1</loc></sitemap></sitemapindex>"),
    )
    listing = Page(
        "https://dnr.wisconsin.gov/sitemap.xml?page=1",
        parse_html("<urlset><url><loc>https://dnr.wisconsin.gov/topic/parks/fixture/recreation/hiking</loc></url></urlset>"),
    )
    pages["https://dnr.wisconsin.gov/sitemap.xml?page=1"] = listing

    rows = SITE_PARSERS["wi_dnr_hiking"].read(index, pages.get)

    assert [(r["name"], r["distance_mi"], r["distance_text"]) for r in rows] == [
        ("Fixture trail", None, "Pink trail, 2 to 4 miles"),
        ("Fixture Ridge Trail", 0.55, "0.55 miles"),
    ]


def test_an_ozark_ascent_written_with_a_prime_is_read_and_n_a_lands_as_text():
    assert _pages_content._ota_feet("4200′") == (4200.0, "4200′")
    assert _pages_content._ota_feet("N/A") == (None, "N/A")


def test_a_buckeye_section_reads_its_miles_and_counties_and_never_its_supervisor():
    section = Page(
        "https://buckeyetrail.org/sections/fixture",
        parse_html(
            '<h1>Fixture</h1><dl class="facts-table"><dt>Miles</dt><dd>66.1total miles / 45.2 off-road miles (68%)</dd>'
            "<dt>Section supervisor</dt><dd>Fixture Supervisor</dd><dt>Counties</dt><dd>Fixture, Fixture Two</dd></dl>"
        ),
    )
    index = Page("https://buckeyetrail.org/sections", parse_html('<a href="/sections/fixture">Fixture</a>'))

    (row,) = SITE_PARSERS["buckeye_sections"].read(index, {section.url: section}.get)

    assert (row["distance_mi"], row["off_road_mi"], row["place"]) == (66.1, 45.2, "Fixture, Fixture Two")
    assert "Fixture Supervisor" not in json.dumps(row)


def test_an_estimated_four_thousand_footer_keeps_its_asterisk_beside_its_number():
    index = Page(
        "https://www.amc4000footer.org/the-lists-we-recognize.html",
        parse_html(
            '<a href="whitemountainfourk.html">The White Mountain Four Thousand Footers</a>'
            '<a href="newenglandfourk.html">The New England Four Thousand Footers</a>'
            '<a href="newenglandhundredhighest.html">The New England Hundred Highest*</a>'
        ),
    )
    table = "<table><tr><td>Rank</td><td>Name</td><td>Elev</td></tr><tr><td>4</td><td>Fixture</td><td>5384*</td></tr></table>"
    pages = {f"https://www.amc4000footer.org/{tail}": Page(f"https://www.amc4000footer.org/{tail}", parse_html(table))
             for tail in _pages_content._AMC_LISTS}  # fmt: skip

    rows = SITE_PARSERS["amc_four_thousand_footer_lists"].read(index, pages.get)

    assert {(r["challenge"], r["elevation_ft"], r["elevation_text"], r["elevation_estimated"]) for r in rows} == {
        ("The White Mountain Four Thousand Footers", 5384.0, "5384*", True),
        ("The New England Four Thousand Footers", 5384.0, "5384*", True),
        ("The New England Hundred Highest", 5384.0, "5384*", True),
    }


def test_a_four_thousand_footer_index_missing_a_list_refuses():
    index = Page("https://www.amc4000footer.org/x.html", parse_html('<a href="whitemountainfourk.html">The White</a>'))
    with pytest.raises(LayoutChanged, match="not the three list pages"):
        SITE_PARSERS["amc_four_thousand_footer_lists"].read(index, None)


def test_a_georgia_peak_lands_its_land_area_and_trails_and_never_its_notes():
    page = Page(
        "https://georgia-atclub.org/x/",
        parse_html(
            "<h5>Fixture Knob - 4,643 ft.</h5><p>Land Area: Fixture Wilderness</p><p>Trail (s): Bushwhack</p>"
            "<p>Notes: Fixture note, elev may be overstated</p><h5>Fixture Bald - 4,458 ft.</h5><p>Trail(s): AT</p>"
        ),
    )
    first, second = SITE_PARSERS["gatc_georgia_4000"].read(page, None)
    assert (first["name"], first["elevation_ft"], first["place"], first["trails"]) == (
        "Fixture Knob",
        4643.0,
        "Fixture Wilderness",
        "Bushwhack",
    )
    assert (second["place"], second["trails"]) == (None, "AT")
    assert "overstated" not in json.dumps([first, second])


def test_every_content_page_resource_rides_its_types_monthly_lane_with_a_parser_for_its_type():
    pages = [r for r in all_resources(discover()) if isinstance(r, ContentPages)]
    assert pages, "the club folders declare no content page reader, so this checked nothing"
    for resource in pages:
        assert resource.cadence == "monthly", resource.key
        assert resource.type in TYPE_COLUMNS, resource.key
        assert (resource.site or resource.key) in _pages_content.SITE_PARSERS, resource.key
