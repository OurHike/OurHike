"""extract/_pdf_content.py, decision 54 wave 4's PDF readers for the content types (section K), against mocked
servers and invented text layers.

A family's parser is run over a PdfFacts (extract/_notices.py's text layer and metadata dates) shaped like the live
document's (section K's reads of 2026-10-04, each sources.json row's `notes`), so these tests need no pypdf: the
reader's own read_pdf is swapped for one that hands back the invented layer. Nothing reaches the network:
conftest.py's socket guard stays on.

The cases are the ones a redrawn document and the per-file change check turn on: a layout the family was not
written for refuses rather than relabels, a scanned file with no text refuses, every row carries its document's
manifest and none of its metadata but the dates, a 304 to the file's own validator is FRESH, a file whose host
sends no validator is UNKNOWN, and one run reads each file once.
"""

import json

import pytest

from extract import _kinds, _notices, _pdf_content
from extract._notices import PdfFacts
from extract._pdf_content import (
    DOCUMENT_COLUMNS,
    PDF_FAMILIES,
    ContentPdf,
    PdfLayoutChanged,
    content_pdf,
)
from lib.freshness_state import Freshness

RMC = "https://randolphmountainclub.org/wp-content/uploads/Recommended-Hikes-1.pdf"

#: An invented text layer laid out as RMC's Recommended-Hikes-1.pdf is: groups, a name line, a statistics line, a
#: Trailhead line, a description; the peak routes one-way, a name that wraps, a route from a hut with no trailhead.
RMC_TEXT = (
    "Suggested Walks (see below for Suggested Routes to the Northern Peaks)\nFixture introduction.\nEASY WALKS\n"
    "Fixture Crossing\n0.5 mi round trip, 100-ft ascent, 30 min\nTrailhead: Fixture Lot\nFixture description.\n"
    "MODERATE WALKS\nFixture Ledge\n2.6 mi round trip, 1000-ft ascent, 1 hr 50 min\nTrailhead: Fixture Site\n"
    "Fixture description, 3.2 mi round trip, 500-ft ascent).\n",
    "STRENUOUS WALKS\nFixture Loop\n6.8 mi loop, 2500-ft ascent, 4 hr 40 min\nTrailhead: Fixture Lot\n"
    "Fixture description.\nSuggested Routes to the Northern Peaks\nFixture introduction, one-way to the summit.\n"
    "MT MADISON\nFixture Way, Fixture Trail\n4.3 mi, 4100-ft ascent, 4 hr 10 min\nTrailhead: Fixture Lot\n"
    "Fixture description.\nFixture Path from Fixture Hut\n0.5 mi, 550-ft ascent\nMT ADAMS\n"
    "Fixture Line, Fixture Cutoff, Fixture Ridge Path, Fixture\nRavine Trail\n4.6 mi, 4500-ft ascent, 4 hr 35 min\n"
    "Trailhead: Fixture Lot\nFixture description.\nMT JEFFERSON\nFixture Caps\n2.5 mi, 2700-ft ascent, 2 hr 35 min\n"
    "Trailhead: Fixture Road\n",
)


@pytest.fixture
def registry(tmp_path, monkeypatch):
    path = tmp_path / "sources.json"
    sources = [{"key": "rmc_recommended_hikes", "url": RMC, "kind": "published_hikes"}]
    path.write_text(json.dumps({"sources": sources}))
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    _kinds._registry.cache_clear()
    yield path
    _kinds._registry.cache_clear()


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    """No courtesy gap, and no test's kept answer reaches another."""
    monkeypatch.setattr(_notices, "_pause", lambda seconds: None)
    monkeypatch.setattr(_notices, "_ANSWERS", {})


@pytest.fixture
def text_layer(monkeypatch):
    """The reader's read_pdf, answering the invented layer for any bytes, so no pypdf is needed."""
    layer = {"facts": PdfFacts(texts=RMC_TEXT, modified=("D:20230220220832Z00'00'", "2023-02-20"))}
    monkeypatch.setattr(_pdf_content, "read_pdf", lambda body: layer["facts"])
    return layer


def rmc_rows(texts=RMC_TEXT) -> list[dict]:
    return PDF_FAMILIES["rmc_recommended_hikes"].read(PdfFacts(texts=texts), RMC)


def resource() -> ContentPdf:
    return content_pdf("rmc_recommended_hikes", club="rmc", type="suggested_hikes")


# --- RMC's Recommended Hikes ----------------------------------------------------------------------------------------


def test_rmcs_walks_land_their_group_numbers_trailhead_and_the_documents_own_time():
    rows = {row["name"]: row for row in rmc_rows()}

    crossing = rows["Fixture Crossing"]
    assert (crossing["section"], crossing["distance_mi"], crossing["elevation_gain_ft"]) == ("Easy Walks", 0.5, 100.0)
    assert (crossing["route_type"], crossing["place"], crossing["time_text"]) == ("round trip", "Fixture Lot", "30 min")
    assert rows["Fixture Loop"]["route_type"] == "loop"
    assert {row["section"] for row in rows.values()} == {
        "Easy Walks",
        "Moderate Walks",
        "Strenuous Walks",
        "Mt Madison",
        "Mt Adams",
        "Mt Jefferson",
    }


def test_a_peak_route_is_one_way_its_wrapped_name_joined_and_a_hut_route_has_no_trailhead():
    rows = {row["name"]: row for row in rmc_rows()}

    assert rows["Fixture Way, Fixture Trail"]["route_type"] == "one way", "the document: 'one-way to the summit'"
    assert "Fixture Line, Fixture Cutoff, Fixture Ridge Path, Fixture Ravine Trail" in rows
    hut = rows["Fixture Path from Fixture Hut"]
    assert (hut["place"], hut["time_text"]) == (None, None)


def test_a_statistics_line_under_no_group_refuses_rather_than_guessing_its_group():
    with pytest.raises(PdfLayoutChanged, match="under no group heading"):
        rmc_rows(("Fixture Walk\n1.0 mi round trip, 100-ft ascent, 30 min\n",))


def test_a_document_missing_one_of_its_groups_refuses():
    without_jefferson = (RMC_TEXT[0], RMC_TEXT[1].split("MT JEFFERSON")[0])
    with pytest.raises(PdfLayoutChanged, match="fall under"):
        rmc_rows(without_jefferson)


# --- The reader ------------------------------------------------------------------------------------------------------

HEADERS = {"Content-Type": "application/pdf", "Last-Modified": "Mon, 20 Feb 2023 22:09:17 GMT", "Content-Length": "9"}


def test_every_row_carries_its_documents_manifest_and_none_of_its_metadata_but_the_dates(registry, requests_mock, text_layer):
    requests_mock.get(RMC, content=b"%PDF-1.4\n", headers=HEADERS)
    proofs: dict = {}

    rows = list(resource().rows(proofs))

    assert proofs == {"raw_rmc__rmc_recommended_hikes": len(rows)} and len(rows) == 7
    first = rows[0]
    assert set(DOCUMENT_COLUMNS) <= set(first) and "author" not in json.dumps(rows).lower()
    assert (first["document_url"], first["document_bytes"], first["document_modified"]) == (RMC, 9, "2023-02-20")
    assert first["document_last_modified"] == HEADERS["Last-Modified"] and first["document_etag"] is None


def test_a_file_with_no_text_layer_refuses_as_one_only_a_person_can_read(registry, requests_mock, text_layer):
    requests_mock.get(RMC, content=b"%PDF-1.4\n", headers=HEADERS)
    text_layer["facts"] = PdfFacts(texts=("", " "))

    with pytest.raises(PdfLayoutChanged, match="no text layer"):
        list(resource().rows({}))


def test_the_check_is_the_files_own_last_modified_and_length_and_its_read_is_the_runs_one_read(
    registry, requests_mock, text_layer
):
    requests_mock.get(RMC, content=b"%PDF-1.4\n", headers=HEADERS)
    pdf = resource()

    verdict, marker = pdf.change_check(None)
    list(pdf.rows({}))

    assert verdict is Freshness.STALE
    assert marker == {"files": {RMC: {"last_modified": HEADERS["Last-Modified"], "content_length": "9"}}}
    assert requests_mock.call_count == 1, "the check's body is kept for the read"
    assert pdf.change_check(marker)[0] is Freshness.FRESH
    assert requests_mock.last_request.headers["If-Modified-Since"] == HEADERS["Last-Modified"]


def test_a_304_to_the_files_etag_is_fresh(registry, requests_mock):
    requests_mock.get(RMC, status_code=304, headers={"ETag": '"6aab-1"'})
    recorded = {"files": {RMC: {"etag": '"6aab-1"'}}}

    assert resource().change_check(recorded) == (Freshness.FRESH, recorded)
    assert requests_mock.last_request.headers["If-None-Match"] == '"6aab-1"'


def test_a_host_that_sends_no_validator_is_unknown_and_so_is_read_every_run(registry, requests_mock):
    requests_mock.get(RMC, content=b"%PDF-1.4\n", headers={"Content-Type": "application/pdf"})

    assert resource().change_check(None) == (Freshness.UNKNOWN, None)


def test_a_wall_in_front_of_the_file_is_unknown(registry, requests_mock):
    requests_mock.get(RMC, status_code=403)

    assert resource().change_check(None) == (Freshness.UNKNOWN, None)
    with pytest.raises(_notices.NoticeUnreadable, match="403"):
        list(resource().rows({}))


def test_a_family_that_is_not_registered_is_refused_at_import(registry):
    with pytest.raises(KeyError, match="no family"):
        content_pdf("rmc_recommended_hikes", family="no_such_family")


# --- The Wasatch Mountain Club's hike ratings table -----------------------------------------------------------------

WMC = "https://www.wasatchmountainclub.org/hike/WMCHikesCopyToWeb.pdf"
WMC_HEADER_TEXT = (
    "Name\nNew \nRating\nRT \nMiles\nEst \nHrs\nHiking \nTime\nTotal \nAscent\nTH \nElev\nMax \nElev\nOther \n"
    "Factors\nWilderness \nGroup Size \nLimit\nAvg Gain \nPer Mile Location\n1 =   Oneway   \n2 = Roundtrip\n"
)
#: An invented layer laid out as WMCHikesCopyToWeb.pdf is: a key page naming its compilers, then the table, its header
#: repeated on each page, one hike a line; one row with a cell empty, and two rows sharing a name.
WMC_TEXT = (
    "Trail Ratings\nNTD   =   0.1 ‐ 4.0  Not to Difficult\nInformation compiled by Fixture Compiler\n",
    WMC_HEADER_TEXT + "FIXTURE LAKE FROM FIXTURE TH 4.5 4.4 1.9 2.4 1,660 7536 8,976 None Yes 755 UTAH  COUNTY 2\n"
    "FIXTURE RIDGE (FIXTURE TO FIXTURE PASS) FROM FIXTURE 7.5 7.5 6.1 5.7 3,378 8765 10,795 BRS No 450 BIG  "
    "COTTONWOOD CANYON  1\n",
    WMC_HEADER_TEXT + "FIXTURE PEAK FROM FIXTURE MOUNTAIN. 6.6 8.3 5.0 2,774 6162 7,491 None No 668 FIXTURE CANYON 2\n"
    "FIXTURE PASS FROM FIXTURE LAKES TH. 3.9 4.6 2.0 2.3 1,344 8765 10,048 None No 292 BIG COTTONWOOD CANYON 2\n"
    "FIXTURE PASS FROM FIXTURE LAKES TH. 3.8 4.6 2.0 2.3 1,312 8765 10,040 None No 285 BIG COTTONWOOD CANYON 2\n",
)


def wmc_rows(texts=WMC_TEXT) -> list[dict]:
    return PDF_FAMILIES["wmc_hike_ratings"].read(PdfFacts(texts=texts), WMC)


def test_a_wasatch_row_lands_its_figures_and_its_way_and_never_its_pace_or_its_compilers():
    rows = wmc_rows()

    assert len(rows) == 5
    first, ridge = rows[0], rows[1]
    assert (first["name"], first["place"], first["distance_mi"], first["elevation_gain_ft"]) == (
        "FIXTURE LAKE FROM FIXTURE TH",
        "UTAH COUNTY",
        4.4,
        1660.0,
    )
    assert (first["difficulty"], first["route_type"], first["trailhead_elevation_ft"], first["max_elevation_ft"]) == (
        "4.5",
        "round trip",
        7536.0,
        8976.0,
    )
    assert (first["other_factors"], first["wilderness_group_limit"], first["gain_per_mile_ft"]) == (None, "Yes", 755.0)
    assert (ridge["route_type"], ridge["other_factors"]) == ("one way", "BRS")
    landed = json.dumps(rows)
    assert "Fixture Compiler" not in landed
    assert not {"1.9", "2.4"} & {str(value) for row in rows for value in row.values()}, "the hour estimates land nowhere"


def test_a_wasatch_row_with_a_cell_empty_lands_its_rating_and_miles_as_unknown():
    peak = next(row for row in wmc_rows() if row["name"].startswith("FIXTURE PEAK"))
    assert (peak["difficulty"], peak["distance_mi"], peak["distance_text"]) == (None, None, None)
    assert (peak["elevation_gain_ft"], peak["max_elevation_ft"]) == (2774.0, 7491.0), "the cells after are unambiguous"


def test_two_wasatch_rows_that_share_a_name_are_kept_apart_by_their_ascent():
    passes = [(row["name"], row["elevation_gain_text"]) for row in wmc_rows() if row["name"].startswith("FIXTURE PASS")]
    assert passes == [
        ("FIXTURE PASS FROM FIXTURE LAKES TH.", "1,344 Total Ascent"),
        ("FIXTURE PASS FROM FIXTURE LAKES TH.", "1,312 Total Ascent"),
    ]


def test_a_wasatch_line_that_is_neither_header_nor_row_refuses():
    broken = (WMC_TEXT[0], WMC_HEADER_TEXT + "FIXTURE LAKE FROM FIXTURE TH 4.5 4.4 1,660 7536 None Yes\n")
    with pytest.raises(PdfLayoutChanged, match="neither the table's header nor one of its rows"):
        wmc_rows(broken)
    with pytest.raises(PdfLayoutChanged, match="no 'Name' header"):
        wmc_rows(("Fixture page with no table\n",))
