"""Tests for lib/nynjtc_long_path_guide.py - NYNJTC's Long Path section guide, read as waypoints.

Why this exists
---------------
Every failure guarded here is SILENT and most of them are on a safety path.
The module reads forty web pages of prose and decides which sentences
become pins on a hiker's map, and where; nothing about a wrong answer
crashes. The ones that would actually hurt somebody, in the order they
would happen:

1. **A season reads as a spring.** "In the spring, the hobblebush puts on a
   spectacular show" is a time of year; a water pin there is a hiker walking
   to a bush. The inverse is as bad and was the first version of this rule:
   an entry that mentions the season AND a spring lost the spring (section
   18, mile 5.00, "300 feet to a spring").
2. **A structure or a road reads as water.** A spring house is stone; Seven
   Springs Road is asphalt; "was the water source for the Kaatz mansion" is
   a demolished pond.
3. **A place a mile off the trail is pinned on it with nothing said.** The
   guide says "1.05 miles from the Long Path"; the pin has to say so too,
   or the map claims a lean-to on the summit.
4. **One shelter becomes four pins**, because the guide mentions it at four
   miles. That is not dangerous, it is the map crying wolf on a smaller
   scale - a hiker who learns that pins repeat stops reading them.
5. **A mile walks off the end of the line.** The layer's lines are shorter
   than the sections they draw (83-105%); raw metres would put section 18's
   last entry past the section's end.

Synthetic pages throughout, built in the real pages' skeleton (measured
2026-09-08: WordPress `<details><summary>NAME</summary>` blocks, entries as
`<strong>MILE</strong>` on `<br>` boundaries) so that a change in NYNJTC's
theme fails the parser's own strictness tests here rather than emptying a
build. Nothing here reads the network or the cached pages.
"""

from __future__ import annotations

import pytest

from lib import nynjtc_long_path_guide as guide
from lib.poi_schema import CONFIDENCE_HIGH, CONFIDENCE_LOW, POI_TYPES

# ---------------------------------------------------------------------------
# Page builder, in the real skeleton.


def entries_html(items: list[tuple[str, str]]) -> str:
    return (
        '<p class="wp-block-paragraph">' + "<br>".join(f"<strong>{mile}</strong>&nbsp; {text}" for mile, text in items) + "</p>"
    )


def block(name: str, inner: str) -> str:
    return f'<details class="wp-block-details" style="font-weight:700"><summary>{name}</summary>{inner}</details>'


def page(
    number: int = 18,
    title: str = "Denning Road to Wittenberg Mountain",
    distance: str = "8.4",
    parking: str = "",
    camping: str = "<p>None.<br></p>",
    description: str = "",
    extra_blocks: str = "",
    header: str | None = None,
) -> str:
    header = (
        header
        or f"<strong>Distance:</strong> {distance} miles<br><strong>Parks:</strong> Slide Mountain Wilderness<br><strong>Maps:</strong> LP Interactive Map"
    )
    return (
        "<html><body><header>site chrome</header>"
        '<main id="wp--skip-link--target">'
        f'<h1 class="wp-block-heading"><a href="/ldt-long-path">The Long Path</a> &#8211; Section {number}</h1>'
        f"<h2><strong>{title}</strong></h2>"
        f'<p class="wp-block-paragraph">{header}</p>'
        f"{block('Access', '<p>Take the New York State Thruway to Exit 16.</p>')}"
        f"{extra_blocks}"
        f"{block('Parking', parking)}"
        f"{block('Camping', camping)}"
        f"{block('Detailed Trail Description', description)}"
        "</main><footer>Privacy Policy</footer></body></html>"
    )


PARKING = entries_html(
    [
        (
            "0.00",
            "Parking area at end of Denning Road (1.2 miles along the Phoenicia-East Branch Trail from the beginning of this section) (41.96556°, -74.45248°).",
        ),
        (
            "8.40",
            "Woodland Valley State Campground (parking fee charged in season) (42.03576°, -74.36531). It is 2.75 miles along the Wittenberg-Cornell-Slide Trail (also called Burroughs Range Trail) from the Long Path to the campground.",
        ),
    ]
)
CAMPING = entries_html(
    [
        (
            "8.40",
            "Terrace Mountain Lean-to (1.05 miles from the Long Path on yellow-blazed Terrace Mountain Trail; no water), and Woodland Valley State Campground (fee charged), 2.75 miles from the Long Path.",
        ),
    ]
)
DESCRIPTION = entries_html(
    [
        (
            "0.00",
            "From the intersection of the Peekamoose-Table Trail proceed north on the yellow-blazed Phoenicia-East Branch Trail (a woods road).",
        ),
        ("0.55", "Pass a spring to the left of the trail."),
        ("4.30", "A sign marks the way to a spring, a dependable source of water, on the left side of the trail."),
        (
            "5.00",
            "Reach the low spot between Slide and Cornell Mountains. An unmarked trail leads right, about 300 feet to a spring. In the spring, the hobblebush puts on a spectacular show in this area.",
        ),
        (
            "7.25",
            "Reach the summit of Wittenberg Mountain, with a large open rock ledge that affords a tremendous view to the east.",
        ),
    ]
)


def straight_line(number: int, start: tuple[float, float], end: tuple[float, float], reverse: bool = False) -> dict:
    coords = [list(start), list(end)]
    if reverse:
        coords.reverse()
    return {"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords}, "properties": {"LP_Section": number}}


# A section running due north for one hundredth of a degree of latitude:
# 1,112 m on the ground. Section 18 at 8.4 stated miles over a line this
# short is exactly the "line shorter than its section" case, exaggerated.
LINE_18 = straight_line(18, (-74.4, 42.0), (-74.4, 42.01))


# ---------------------------------------------------------------------------
# 1. The index.


def test_the_index_lists_the_sections_it_links_in_order_and_once():
    markup = '<a href="/lp-section-2/">2</a> <a href="/lp-section-1">1</a> <a href="https://www.nynjtc.org/lp-section-2/">again</a> <a href="/lp-interactive-map/">map</a>'
    assert guide.parse_index(markup) == [(1, "https://www.nynjtc.org/lp-section-1/"), (2, "https://www.nynjtc.org/lp-section-2/")]


def test_an_index_that_links_no_sections_stops_the_fetch():
    with pytest.raises(ValueError, match="links to no"):
        guide.parse_index("<main><p>Welcome to the Long Path guide.</p></main>")


# ---------------------------------------------------------------------------
# 2. A section page, and what has to be there.


def test_a_page_parses_to_its_header_and_three_blocks():
    section = guide.parse_section(page(parking=PARKING, camping=CAMPING, description=DESCRIPTION), "u", 18)
    assert (section.number, section.title, section.distance_miles, section.parks) == (
        18,
        "Denning Road to Wittenberg Mountain",
        8.4,
        "Slide Mountain Wilderness",
    )
    assert [e.mile for e in section.parking] == [0.0, 8.4]
    assert [e.mile for e in section.camping] == [8.4]
    assert [e.mile for e in section.description] == [0.0, 0.55, 4.3, 5.0, 7.25]
    assert section.notes["camping"] == []


def test_the_parking_block_yields_nynjtcs_own_coordinates_latitude_first():
    section = guide.parse_section(page(parking=PARKING, description=DESCRIPTION), "u")
    first, second = section.parking
    assert (first.lat, first.lon) == (41.96556, -74.45248)
    # The second entry's longitude has no degree sign on the real page.
    assert (second.lat, second.lon) == (42.03576, -74.36531)


@pytest.mark.parametrize(
    "text,expected",
    [
        (
            "Parking area at end of Denning Road (1.2 miles along the Phoenicia-East Branch Trail from the beginning of this section).",
            1.2,
        ),
        (
            "It is 2.75 miles along the Wittenberg-Cornell-Slide Trail (also called Burroughs Range Trail) from the Long Path to the campground.",
            2.75,
        ),
        ("Terrace Mountain Lean-to (1.05 miles from the Long Path on yellow-blazed Terrace Mountain Trail; no water)", 1.05),
        ("Parking, 0.2 mile from the Long Path, along Route 9W in Alpine.", 0.2),
        (
            "There is a reliable spring on the Dutcher Notch Trail at 0.35 miles and about 500 vertical feet below this point.",
            0.35,
        ),
        # A junction is not the trail, and a distance AHEAD is not a distance off.
        ("End of paved portion of Shin Hollow Road, 0.35 miles south of the LP/SRT junction", None),
        ("The trail then veers to the east side of the ridge, passing a seasonal spring in about 0.1 mile.", None),
    ],
)
def test_the_three_off_trail_phrasings_are_read_and_the_two_lookalikes_are_not(text: str, expected: float | None):
    entries, _ = guide.parse_entries(f"1.00 {text}")
    assert entries[0].off_trail_miles == expected


def test_unlocated_is_nynjtcs_word_and_is_kept_as_such():
    entries, _ = guide.parse_entries("36.60 Northville-Placid Trail (NPT) trailhead in Northville. (unlocated)")
    assert entries[0].unlocated and entries[0].lat is None


def test_coordinates_outside_the_long_paths_extent_are_a_typo_not_a_position():
    entries, _ = guide.parse_entries("2.00 A lot with a dropped minus sign. (41.40448°, 74.61631°)")
    assert entries[0].lat is None and entries[0].coordinates_rejected


def test_lines_before_the_first_mile_are_notes_and_later_lines_continue_an_entry():
    text = "Ample parking along roads in Lake Desolation and Northville.\n18.90 Gravel operation about 200 ft before Older Mountain Road.\n(43.12503°, -73.95140°)\n24.10 Mulleyville snowmobile trail system."
    entries, notes = guide.parse_entries(text)
    assert notes == ["Ample parking along roads in Lake Desolation and Northville."]
    assert entries[0].lat == 43.12503, "the coordinates on the continuation line belong to the entry above them"
    assert [e.mile for e in entries] == [18.9, 24.1]


def test_a_photo_caption_inside_a_block_does_not_glue_itself_onto_the_next_mile():
    description = (
        "<p><strong>6.55</strong> The trail reaches the top of a rock ledge.</p>"
        '<figure><img src="x.jpg"><figcaption>View of Wittenberg, 2001 [Chong]</figcaption></figure>'
        "<p><strong>6.90</strong> Reach the col between Cornell and Wittenberg Mountains.</p>"
    )
    section = guide.parse_section(page(description=description), "u")
    assert [e.mile for e in section.description] == [6.55, 6.9]
    assert "Chong" not in section.description[1].text


def test_a_missing_block_names_itself_rather_than_parsing_to_nothing():
    markup = page(description=DESCRIPTION).replace("<summary>Camping</summary>", "<summary>Where to sleep</summary>")
    with pytest.raises(ValueError, match=r"\['Camping'\]"):
        guide.parse_section(markup, "https://www.nynjtc.org/lp-section-18/")


def test_an_extra_block_is_tolerated_because_section_22_has_one():
    markup = page(description=DESCRIPTION, extra_blocks=block("Winter Access", "<p>Route 214 is not plowed.</p>"))
    assert guide.parse_section(markup, "u").number == 18


def test_a_page_claiming_the_wrong_section_number_stops_the_parse():
    with pytest.raises(ValueError, match="says Section 18, expected 19"):
        guide.parse_section(page(description=DESCRIPTION), "u", expected_number=19)


def test_a_description_with_no_mile_entries_is_a_changed_layout_not_an_empty_section():
    with pytest.raises(ValueError, match="zero mile-marked"):
        guide.parse_section(page(description="<p>Prose without any miles at all.</p>"), "u")


def test_a_section_round_trips_through_its_dict():
    section = guide.parse_section(page(parking=PARKING, camping=CAMPING, description=DESCRIPTION), "u", 18)
    again = guide.Section.from_dict(section.to_dict())
    assert again == section


# ---------------------------------------------------------------------------
# 3. Water - the narrowest rule in the file.


@pytest.mark.parametrize(
    "text",
    [
        "Pass a spring to the left of the trail.",
        "A sign marks the way to a spring, a dependable source of water.",
        "Cross the stream (last sure water before Big Hill Shelter) and turn left.",
        "Cross the two streams of Hillyer Ravine, which provide the last sure source of water in this section.",
        "There is a reliable spring on the Dutcher Notch Trail at 0.35 miles, the only reliable water in this section.",
        "The trail passes a gas station (water, vending machines, food, phone) on the left.",
        "The State Line Lookout snack bar, with restrooms, food, water, phone, and bookstore, is on the right.",
        # The season AND a spring in one entry: the spring survives the season.
        "An unmarked trail leads right, about 300 feet to a spring. In the spring, the hobblebush puts on a spectacular show.",
        "It then crosses the outlet of a spring and continues along the valley.",
    ],
)
def test_water_said_in_the_water_sense_is_water(text: str):
    assert "water" in guide.classify(text)


@pytest.mark.parametrize(
    "text",
    [
        "In the spring, the hobblebush puts on a spectacular show in this area.",
        "The trail was relocated in spring 2025 through Altamont.",
        "Soon followed by an old spring house on the right.",
        "Reach paved Seven Springs Road, which is closed to vehicular traffic.",
        "To the left is a small artificial pond. It was the water source for the Kaatz mansion, demolished in the 1970s.",
        "The trail passes through the hamlet of Cold Spring and turns left.",
        # A stream is a thing to step over until the guide says it is a thing to drink from.
        "Cross a stream on a wooden bridge. The trail crosses the stream two more times.",
        "Reach the summit, with views of the Ashokan Reservoir far below.",
    ],
)
def test_what_merely_sounds_like_water_is_not(text: str):
    assert "water" not in guide.classify(text)


def test_reliability_is_read_in_the_cautious_direction():
    assert (
        guide.water_reliability("Pass a seasonal spring on left, which is reliable in all but the driest times.") == "unreliable"
    )
    assert guide.water_reliability("pass an undependable pipe spring 50 feet to the left") == "unreliable"
    assert guide.water_reliability("On the left is a reliable spring.") == "reliable"
    assert guide.water_reliability("Pass a spring to the left of the trail.") is None


# ---------------------------------------------------------------------------
# 4. The other types.


def test_a_lean_to_or_shelter_is_a_shelter_and_a_roof_that_is_not_for_sleeping_is_not():
    assert "shelter" in guide.classify("A trail leads left to the Bouton Memorial Lean-to.")
    assert "shelter" in guide.classify("Arrive at Big Hill Shelter. Built in 1927, this stone shelter has three fireplaces.")
    assert "shelter" not in guide.classify(
        "Reach a rock ledge with a large overhanging rock, a good temporary shelter, on the left."
    )
    assert "shelter" not in guide.classify(
        "The yellow-blazed Rock Shelter Trail leaves to the left, named for a large overhang known as Badman's Cave."
    )
    assert "shelter" not in guide.classify("This used to be a New York City homeless shelter, but it is being redeveloped.")
    assert "shelter" in guide.classify("Past the picnic shelter, a side trail leads to Cohasset Shelter."), (
        "a refused phrase must not hide a real one"
    )


def test_camping_block_entries_are_campsites_unless_they_say_what_else_they_are():
    assert guide.classify_camping("Mink Hollow Lean-to") == ["shelter"]
    assert guide.classify_camping("Campsites available at Catskill Mountains/Gilboa KOA Holiday Campground (fee charged).") == [
        "campsite"
    ]
    assert guide.classify_camping("Big Hill Shelter.") == ["shelter"]
    assert guide.classify_camping("A pleasant site by the brook.") == ["campsite"], "the block's own heading is the evidence"
    assert (
        guide.classify_camping("Camping is allowed in the state reforestation areas 150 feet from the trail and water.") == []
    ), "an area is not a point"


def test_a_viewpoint_is_named_or_praised_not_merely_mentioned():
    assert "viewpoint" in guide.classify("The Long Path reaches Rockefeller Lookout and its tremendous views.")
    assert "viewpoint" in guide.classify("a short side trail leads right, to a ledge with a spectacular lookout.")
    assert "viewpoint" in guide.classify("a large open rock ledge that affords a tremendous view to the east")
    assert "viewpoint" not in guide.classify("Views across the river include the Henry Hudson Bridge.")


def test_restrooms_are_privies():
    assert "privy" in guide.classify("Reach the park administration building on the right, where there are restroom facilities.")


def test_every_type_the_classifier_can_emit_is_one_the_schema_knows():
    text = "Lean-to, campsite, spring, lookout and restrooms, with a fine view."
    for poi_type in guide.classify(text):
        assert poi_type in POI_TYPES
    assert guide.classify(text) == [t for t in POI_TYPES if t in ("shelter", "campsite", "water", "viewpoint", "privy")], (
        "in POI_TYPES order"
    )


# ---------------------------------------------------------------------------
# 5. Names - found, never invented.


def test_a_place_is_named_only_by_a_word_for_its_own_type():
    text = "At the top of the ledge, there is a good viewpoint of Sugarloaf Mountain with Stoppel Point visible to the north."
    assert guide.place_name(text, "viewpoint") is None, "Stoppel Point is on the horizon, not under the pin"
    assert guide.place_name("A trail leads left to the Bouton Memorial Lean-to.", "shelter") == "Bouton Memorial Lean-to"
    assert guide.place_name("Pass Cohasset Shelter on the right.", "shelter") == "Cohasset Shelter"
    assert (
        guide.place_name("The Long Path reaches Rockefeller Lookout and its tremendous views.", "viewpoint")
        == "Rockefeller Lookout"
    )
    assert guide.place_name("Reach Phoenicia. Black Bear Campground is on the right.", "campsite") == "Black Bear Campground"
    assert guide.place_name("Pass a spring to the left of the trail.", "water") is None


def test_a_parking_entrys_name_is_its_first_clause_or_nothing():
    assert (
        guide.short_name("Fort Lee Historic Park, just south of the bridge (metered parking). (40.85181°, -73.96245°)")
        == "Fort Lee Historic Park"
    )
    assert (
        guide.short_name("Parking lot at the end of St. Mary's Road. (41.0°, -74.0°)")
        == "Parking lot at the end of St. Mary's Road"
    )
    assert guide.short_name("There is parking along NY Route 293 near Barnes Lake (0.2 mi)") is None
    assert guide.short_name("Parking. (41.0°, -74.0°)") is None


# ---------------------------------------------------------------------------
# 6. Geometry - one oriented line per section.


def test_pieces_are_chained_end_to_end_whichever_way_they_arrive():
    a = [(-74.0, 41.0), (-74.0, 41.01)]
    b = [(-74.0, 41.02), (-74.0, 41.01)]  # arrives backwards
    c = [(-74.0, 41.02), (-74.0, 41.03)]
    chain = guide.chain_parts([b, c, a])
    forward = [(-74.0, 41.0), (-74.0, 41.01), (-74.0, 41.02), (-74.0, 41.03)]
    # Either direction: which way a section runs is section_lines' decision.
    assert chain in (forward, list(reversed(forward)))


def test_a_piece_that_connects_to_nothing_stops_the_chain():
    with pytest.raises(ValueError, match="do not connect"):
        guide.chain_parts([[(-74.0, 41.0), (-74.0, 41.01)], [(-74.5, 41.5), (-74.5, 41.51)]])


def test_sections_are_oriented_south_to_north_by_continuity():
    # Section 1 arrives north-to-south; section 2 arrives pointing away from
    # section 1's end. Both must come out running the guide's way.
    one = straight_line(1, (-74.0, 41.0), (-74.0, 41.1), reverse=True)
    two = straight_line(2, (-74.0, 41.1), (-74.1, 41.2), reverse=True)
    lines = guide.section_lines([two, one])
    assert lines[1][0] == (-74.0, 41.0) and lines[1][-1] == (-74.0, 41.1)
    assert lines[2][0] == (-74.0, 41.1) and lines[2][-1] == (-74.1, 41.2)


def test_a_multi_part_section_is_one_line():
    feature = {
        "type": "Feature",
        "geometry": {
            "type": "MultiLineString",
            "coordinates": [[[-74.0, 41.0], [-74.0, 41.01]], [[-74.0, 41.01], [-74.0, 41.02]]],
        },
        "properties": {"LP_Section": 14},
    }
    assert len(guide.section_lines([feature])[14]) == 3


def test_a_mile_is_scaled_to_the_stated_distance_not_walked_as_raw_metres():
    line = guide.section_lines([LINE_18])[18]
    # 8.4 raw miles along a 1.1 km line would run off its end; scaled, the
    # last mile of the section is the last point of the line.
    assert guide.interpolate(line, 8.4, 8.4) == pytest.approx(line[-1])
    assert guide.interpolate(line, 4.2, 8.4)[1] == pytest.approx(42.005, abs=1e-6)
    assert guide.interpolate(line, 0.0, 8.4) == line[0]


def test_a_section_stating_no_distance_cannot_be_walked():
    with pytest.raises(ValueError):
        guide.interpolate([(-74.0, 41.0), (-74.0, 41.01)], 1.0, 0)


# ---------------------------------------------------------------------------
# 7. Records - what reaches the artifact, and what does not.


def parsed() -> guide.Section:
    return guide.parse_section(
        page(parking=PARKING, camping=CAMPING, description=DESCRIPTION), "https://www.nynjtc.org/lp-section-18/", 18
    )


def test_stated_coordinates_are_high_confidence_and_a_walked_mile_is_low():
    records, stats = guide.build_records([parsed()], [LINE_18])
    by_id = {r["source_feature_id"]: r for r in records}
    lot = by_id["s18-parking-0.00-0"]
    assert (lot["placement"], lot["confidence"], lot["lat"], lot["lon"]) == ("stated", CONFIDENCE_HIGH, 41.96556, -74.45248)
    assert "position_error_m" not in lot
    spring = [r for r in records if r["poi_type"] == "water" and r["section_mile"] == 0.55][0]
    assert (spring["placement"], spring["confidence"], spring["position_error_m"]) == (
        "interpolated",
        CONFIDENCE_LOW,
        guide.INTERPOLATION_ERROR_M,
    )
    assert stats["entries_placed"] == {"stated": 2, "interpolated": 5}


def test_every_record_carries_the_section_the_mile_and_the_page_and_never_the_at_mile():
    records, _ = guide.build_records([parsed()], [LINE_18])
    for record in records:
        assert record["trail_id"] == "LP"
        assert record["source"] == guide.SOURCE_KEY
        assert record["lp_section"] == 18
        assert record["source_url"] == "https://www.nynjtc.org/lp-section-18/"
        assert "mile" not in record, "the guide's miles restart every section; they are not NOBO miles from Springer"
        assert record["poi_type"] in POI_TYPES
    assert len({r["id"] for r in records}) == len(records), "ids are unique"


def test_ids_are_deterministic_across_runs():
    first, _ = guide.build_records([parsed()], [LINE_18])
    second, _ = guide.build_records([parsed()], [LINE_18])
    assert [r["id"] for r in first] == [r["id"] for r in second]


def test_the_prose_stays_on_nynjtcs_page():
    records, _ = guide.build_records([parsed()], [LINE_18])
    for record in records:
        for phrase in ("hobblebush", "Peekamoose", "woods road", "affords"):
            assert phrase not in (record.get("description") or "")
            assert phrase not in (record.get("name") or "")


def test_an_off_trail_place_is_pinned_at_its_mile_and_the_sentence_says_so():
    records, stats = guide.build_records([parsed()], [LINE_18])
    lean_to = [r for r in records if r["poi_type"] == "shelter"][0]
    assert lean_to["name"] == "Terrace Mountain Lean-to"
    assert lean_to["off_trail_miles"] == 1.05
    assert "1.05 mi off the Long Path" in lean_to["description"]
    assert "marks where the guide leaves the trail" in lean_to["description"]
    assert stats["off_trail"] >= 1


def test_the_season_and_the_spring_in_one_entry_keeps_the_spring():
    records, _ = guide.build_records([parsed()], [LINE_18])
    assert any(r["poi_type"] == "water" and r["section_mile"] == 5.0 for r in records)


def test_water_carries_what_the_guide_says_about_reliability():
    records, _ = guide.build_records([parsed()], [LINE_18])
    dependable = [r for r in records if r["poi_type"] == "water" and r["section_mile"] == 4.3][0]
    assert dependable["water_reliability"] == "reliable"
    assert "calls it reliable" in dependable["description"]
    plain = [r for r in records if r["poi_type"] == "water" and r["section_mile"] == 0.55][0]
    assert "water_reliability" not in plain


def test_unlocated_and_past_the_end_are_counted_not_drawn():
    parking = entries_html(
        [("36.60", "NPT trailhead in Northville. (unlocated)"), ("40.10", "NPT trailhead at Collins Gifford Valley Road.")]
    )
    section = guide.parse_section(page(number=40, distance="36.6", parking=parking, description=DESCRIPTION), "u", 40)
    line = straight_line(40, (-74.0, 43.0), (-74.0, 43.1))
    records, stats = guide.build_records([section], [line])
    assert not [r for r in records if r["poi_type"] == "parking"]
    assert stats["skipped"]["marked (unlocated) by NYNJTC"] == 1
    assert stats["skipped"]["mile past the section's stated distance"] == 1


def test_a_section_with_no_line_in_the_layer_places_nothing_and_says_so():
    records, stats = guide.build_records([parsed()], [])
    assert all(r["placement"] == "stated" for r in records)
    assert stats["skipped"]["section 18 has no line in the layer"] == 5


def test_one_shelter_said_at_four_miles_is_one_pin_from_the_camping_block():
    camping = entries_html([("5.65", "Big Hill Shelter.")])
    description = entries_html(
        [
            ("4.65", "Cross the stream (last sure water before Big Hill Shelter) and turn left."),
            ("5.45", "The Long Path and SBM continue jointly over ledges to climb up to Big Hill Shelter."),
            ("5.70", "Arrive at Big Hill Shelter. Built in 1927, this stone shelter has three fireplaces."),
        ]
    )
    section = guide.parse_section(page(number=5, distance="9.4", camping=camping, description=description), "u", 5)
    records, stats = guide.build_records([section], [straight_line(5, (-74.0, 41.0), (-74.0, 41.1))])
    shelters = [r for r in records if r["poi_type"] == "shelter"]
    assert len(shelters) == 1
    assert (shelters[0]["section_mile"], shelters[0]["source_feature_id"]) == (5.65, "s5-camping-5.65-0")
    assert stats["duplicates_merged"] == 3
    assert any(r["poi_type"] == "water" and r["section_mile"] == 4.65 for r in records), (
        "the water at 4.65 is not a duplicate of anything"
    )


def test_the_same_lot_on_both_sides_of_a_section_boundary_is_one_pin():
    end_of_24 = entries_html([("9.80", "Parking area at end of Big Hollow Road. (42.28932°, -74.11610°)")])
    start_of_25 = entries_html([("0.00", "Parking area at end of Big Hollow Road. (42.28932°, -74.11602°)")])
    s24 = guide.parse_section(page(number=24, distance="9.8", parking=end_of_24, description=DESCRIPTION), "u", 24)
    s25 = guide.parse_section(page(number=25, distance="8.55", parking=start_of_25, description=DESCRIPTION), "u", 25)
    records, stats = guide.build_records(
        [s24, s25], [straight_line(24, (-74.0, 42.2), (-74.1, 42.29)), straight_line(25, (-74.1, 42.29), (-74.2, 42.31))]
    )
    assert len([r for r in records if r["poi_type"] == "parking"]) == 1
    assert stats["duplicates_merged"] >= 1


def test_the_three_spellings_of_lean_to_are_one_name():
    assert (
        guide._normalised("Batavia Kill Lean-to")
        == guide._normalised("Batavia Kill Leanto")
        == guide._normalised("The Batavia Kill Lean To")
    )
