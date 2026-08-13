"""lib/club_pdfs.py - the GATC water-sources parser.

Fixtures are strings shaped exactly like pypdf's plain extraction of the real
PDF (measured 2026-08-13): rows as single lines, title/header furniture on
page one, a page footer on each page, and the mile sequence restarting where
the approach-trail list hands over to the A.T.'s. No PDF library anywhere in
these tests - the parser takes text on purpose, so the strictness that
matters (unknown lines, moved headers, a second mile restart) is testable
against ten-line strings instead of a binary fixture.
"""

from __future__ import annotations

import pytest

from lib.club_pdfs import PARSERS, TRAIL_APPROACH, TRAIL_AT, parse_gatc_water_sources

PAGE_1 = """Water Sources in Georgia
Approach Trail & Appalachian Trail
Mile Point Source Name Distance Off AT
0.8 Stream - approach trail On Trail
7.3 Black Gap Shelter - approach trail Downhill, .1 W, Across AT from Shelter
0.2 Springer Mountain Shelter Piped Spring beyond lower bear cables
2.8 Stover Creek Shelter Typically very low or dry. Use creek at MP 2.9
Page 1 of 2"""

PAGE_2 = """38.0 Whitley Gap Shelter Blue Blaze behind shelter, 1.3 E from AT
80.7 Next possible water in NC, Stream
Page 2 of 2"""


def test_rows_carry_mile_entry_and_which_trail():
    rows = parse_gatc_water_sources([PAGE_1, PAGE_2])

    assert [row["mile"] for row in rows] == [0.8, 7.3, 0.2, 2.8, 38.0, 80.7]
    # The mile restart (7.3 -> 0.2) is the approach-trail handover.
    assert [row["trail"] for row in rows] == [TRAIL_APPROACH] * 2 + [TRAIL_AT] * 4
    # Name and off-trail directions stay one field - the PDF's text layer
    # holds no boundary between the printed columns, and a guessed split
    # would be wrong on rows like Stover Creek's dry-season note.
    assert rows[3]["entry"] == "Stover Creek Shelter Typically very low or dry. Use creek at MP 2.9"


def test_without_a_mile_restart_every_row_is_the_at():
    """A future re-export without the approach-trail block should not strand
    every row under a label that only means "before the restart"."""
    rows = parse_gatc_water_sources(
        ["Mile Point Source Name Distance Off AT\n1.6 Davis Creek On-Trail\n2.3 Small Stream On-Trail"]
    )

    assert [row["trail"] for row in rows] == [TRAIL_AT, TRAIL_AT]


def test_a_missing_header_stops_the_parse():
    """The header's presence is the proof this is still the document the
    parser was written for - build_shelter_capacity.py's posture, applied to
    a PDF."""
    with pytest.raises(ValueError, match="no longer carries the header"):
        parse_gatc_water_sources(["1.6 Davis Creek On-Trail"])


def test_an_unrecognised_line_is_an_error_not_a_skip():
    """The enumerated furniture is the leniency; anything outside it means
    the layout changed, and a silent skip is how a mile column quietly
    becomes an elevation column somewhere downstream."""
    with pytest.raises(ValueError, match="Unrecognised line"):
        parse_gatc_water_sources(["Mile Point Source Name Distance Off AT\nSprings of North Georgia, revised edition"])


def test_a_second_mile_restart_is_a_shape_this_parser_refuses():
    page = "Mile Point Source Name Distance Off AT\n5.0 A On-Trail\n1.0 B On-Trail\n8.0 C On-Trail\n2.0 D On-Trail"
    with pytest.raises(ValueError, match="falls more than once"):
        parse_gatc_water_sources([page])


def test_zero_rows_is_an_error():
    with pytest.raises(ValueError, match="zero rows"):
        parse_gatc_water_sources(["Mile Point Source Name Distance Off AT\nPage 1 of 1"])


def test_the_parser_registry_names_the_registered_source_key():
    """fetch_club_pdfs.py dispatches by sources.json key; a parser registered
    under a drifted name is a PDF fetched forever and parsed never."""
    assert PARSERS["gatc_water_sources"] is parse_gatc_water_sources
