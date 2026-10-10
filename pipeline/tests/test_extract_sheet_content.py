"""extract/_sheet_content.py, the workbook readers for section K's hand-back, against mocked servers and invented cells.

Each family's parser runs over cells laid out as the live workbook's were on 2026-10-10 (SMHC's 900 Miler list, an
.xls; WMC's hike ratings, an .xlsx), with invented names and numbers. sheet_cells() and the reader open .xlsx files
this module writes with openpyxl. No test writes an .xls, because nothing pinned here writes the old binary format:
the .xls path was read against SMHC's live file by hand on 2026-10-10 (157 trails, 238 sections, summing to the
sheet's 796.73 mi), and is otherwise covered only by xlrd's own tests (@unvalidated here: a test .xls written by
another tool, or a reviewed tiny one, would settle it). Nothing reaches the network: conftest.py's socket guard
stays on.

The cases are the ones a reworked sheet and a person's data turn on: a header that moved refuses rather than
relabels, a sheet that is not the family's is never read (WMC's cover sheet names its compilers), a member's own
column never lands, an empty cell lands as unknown, the sheet's own total is checked, and every row carries the
workbook's manifest and no document property. And openpyxl parses through defusedxml here, as in the extract job,
so a workbook whose XML declares an entity is refused.
"""

import io
import json
import zipfile

import openpyxl
import pytest

from extract import _kinds, _notices
from extract._sheet_content import (
    SHEET_DOCUMENT_COLUMNS,
    SHEET_FAMILIES,
    WMC_HEADER,
    SheetLayoutChanged,
    content_sheet,
    sheet_cells,
)

WMC = "https://www.wasatchmountainclub.org/hike/WMCHikesCopyToWeb.xlsx"
SMHC = "https://smhclub.org/resources/Documents/900%20Mile%20Spreadsheet.xls"
WAY = "1 =   Oneway    2 = Roundtrip"


def workbook(sheets: dict[str, list[list]], creator: str | None = None) -> bytes:
    """An .xlsx holding `sheets` in order, written with openpyxl; `creator` sets the file's own author property."""
    book = openpyxl.Workbook()
    book.remove(book.active)
    for name, rows in sheets.items():
        sheet = book.create_sheet(name)
        for row in rows:
            sheet.append(row)
    if creator:
        book.properties.creator = creator
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def wmc_row(name, miles=4.4, ascent=1660, way=2, rating=4.489, location="FIXTURE CANYON"):
    """One Hikes row in the live sheet's 19 columns, invented values."""
    return [name, "FIXTURE LAKE", "FIXTURE TH", rating, miles, 1.9, 2.35, ascent, 7536, 8976, "None", "Yes", 754.5,
            1.32, 1.66, 1.51, 0, location, way]  # fmt: skip


WMC_CELLS = [
    [*WMC_HEADER, WAY],
    wmc_row("FIXTURE LAKE FROM FIXTURE TH"),
    wmc_row("FIXTURE PEAK FROM FIXTURE MOUNTAIN", miles=None, rating=None, way=1),
    wmc_row("FIXTURE PASS FROM FIXTURE TH", ascent=1312),
]


def smhc_cells() -> list[list]:
    """SMHC's sheet as read 2026-10-10: three header rows, a one-section trail, a trail of two sections, and the
    total twice at the foot. Column F is a member's date and G their notes, filled in here as a member's copy is."""
    return [
        ["Fixture National Park", None, None, None, None, None, None],
        ["Trails", None, None, "Section Miles", "Trail Totals", None, None],
        ["Displayed on fixture map", None, "Primary source data (feet)", "Mileages from fixture maps", None,
         "Date Completed", "Notes"],
        ["Fixture Falls Trail", None, 5280.0, None, 1.0, "2024-05-01", "a member's note"],
        ["Fixture Ridge Trail", None, None, None, 2.5, None, None],
        [None, "Fixture Gap - Fixture Knob", 7920.0, 1.5, None, None, None],
        [None, "Fixture Knob - Fixture Bald", 5280.0, 1.0, None, None, None],
        [None, None, None, None, None, None, None],
        [None, None, None, None, 3.5, None, None],
        [None, None, None, None, 3.5, None, None],
    ]  # fmt: skip


@pytest.fixture
def registry(tmp_path, monkeypatch):
    path = tmp_path / "sources.json"
    sources = [{"key": "wmc_hike_ratings", "url": WMC, "kind": "published_hikes"}]
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


# --- Opening a workbook ----------------------------------------------------------------------------------------------


def test_only_the_familys_own_sheet_is_read_never_a_cover_sheet_naming_its_compilers():
    body = workbook({"CoverSheet": [["Information compiled by A Fixture Person"]], "Hikes": WMC_CELLS})

    cells = sheet_cells(body, "Hikes", WMC)

    assert cells[0][:3] == ["Name", "Destination", "Start Location"]
    assert "A Fixture Person" not in json.dumps(cells, default=str)


def test_a_file_in_neither_workbook_format_is_refused_by_its_first_bytes_not_its_name():
    with pytest.raises(SheetLayoutChanged, match="neither an .xls nor an .xlsx"):
        sheet_cells(b"<!doctype html><title>Moved</title>", "Hikes", WMC)


def test_a_workbook_without_the_familys_sheet_is_refused():
    with pytest.raises(SheetLayoutChanged, match="no sheet 'Hikes'"):
        sheet_cells(workbook({"Sheet1": [["Name"]]}), "Hikes", WMC)


def test_openpyxl_parses_through_defusedxml_in_this_environment():
    """openpyxl guards against quadratic-blowup and billion-laughs XML only when defusedxml can be imported (its
    documentation; openpyxl/xml/__init__.py's DEFUSEDXML). The extract job parses .xlsx files fetched from club
    websites while it holds the raw store's write keys, so requirements-extract.in pins defusedxml and
    requirements-dev.in the same version: an environment that loses it fails here rather than parsing unguarded."""
    import openpyxl.xml

    assert openpyxl.xml.DEFUSEDXML is True


def test_a_workbook_whose_sheet_xml_declares_an_entity_is_refused_before_any_cell_is_read():
    """What defusedxml changes, shown: the same workbook with one entity declared in its sheet's XML. openpyxl wraps
    defusedxml's refusal in its own ValueError; unguarded, it would read the sheet as if nothing were there."""
    from defusedxml import EntitiesForbidden

    body = workbook({"Hikes": WMC_CELLS})
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    (sheet,) = [name for name in parts if name.startswith("xl/worksheets/sheet")]
    parts[sheet] = b'<!DOCTYPE worksheet [<!ENTITY fixture "fixture">]>' + parts[sheet]
    poisoned = io.BytesIO()
    with zipfile.ZipFile(poisoned, "w") as archive:
        for name, data in parts.items():
            archive.writestr(name, data)

    with pytest.raises(ValueError) as refused:
        sheet_cells(poisoned.getvalue(), "Hikes", WMC)

    assert isinstance(refused.value.__cause__, EntitiesForbidden)


def test_an_empty_cell_comes_back_as_none_and_text_is_stripped():
    cells = sheet_cells(workbook({"Hikes": [["  Fixture  ", None, "   "]]}), "Hikes", WMC)

    assert cells == [["Fixture", None, None]]


# --- WMC's hike ratings ----------------------------------------------------------------------------------------------


def wmc(cells=WMC_CELLS) -> list[dict]:
    return SHEET_FAMILIES["wmc_hike_ratings"].read(cells, WMC)


def test_wmc_lands_each_hikes_miles_ascent_way_and_its_rating_at_the_decimal_the_club_printed():
    lake = wmc()[0]

    assert (lake["name"], lake["distance_mi"], lake["elevation_gain_ft"]) == ("FIXTURE LAKE FROM FIXTURE TH", 4.4, 1660.0)
    assert (lake["route_type"], lake["difficulty"], lake["place"]) == ("round trip", "4.5", "FIXTURE CANYON")
    assert (lake["distance_text"], lake["elevation_gain_text"]) == ("4.4 RT Miles", "1660 Total Ascent")
    assert lake["link"] == lake["source_url"] == WMC


def test_wmc_lands_an_empty_cell_as_unknown_never_zero():
    peak = wmc()[1]

    assert (peak["distance_mi"], peak["distance_text"], peak["difficulty"], peak["route_type"]) == (
        None,
        None,
        None,
        "one way",
    )


def test_wmc_reads_neither_hour_estimate_nor_the_ratings_parts():
    assert not {"est_hrs", "hiking_time", "mileage_rating", "ascent_rating"} & set(wmc()[0])


def test_wmc_refuses_a_sheet_whose_header_moved_rather_than_relabelling_it():
    moved = [[WMC_HEADER[1], WMC_HEADER[0], *WMC_HEADER[2:], WAY], *WMC_CELLS[1:]]

    with pytest.raises(SheetLayoutChanged, match="header reads"):
        wmc(moved)


def test_wmc_refuses_a_way_that_is_neither_one_nor_two():
    with pytest.raises(SheetLayoutChanged, match="neither 1 nor 2"):
        wmc([WMC_CELLS[0], wmc_row("FIXTURE LAKE FROM FIXTURE TH", way=3)])


def test_wmc_refuses_a_gap_in_the_table_with_hikes_after_it():
    gap = [*WMC_CELLS[:2], [None] * 19, WMC_CELLS[3]]

    with pytest.raises(SheetLayoutChanged, match="names no hike"):
        wmc(gap)


# --- SMHC's 900 Miler list -------------------------------------------------------------------------------------------


def smhc(cells=None) -> list[dict]:
    return SHEET_FAMILIES["smhc_900_miler_trails"].read(cells if cells is not None else smhc_cells(), SMHC)


def test_smhc_lands_one_item_per_trail_its_sections_feet_summed_and_counted():
    falls, ridge = smhc()

    assert (falls["name"], falls["distance_mi"], falls["length_ft"], falls["sections"]) == ("Fixture Falls Trail", 1.0, 5280.0, 0)
    assert (ridge["name"], ridge["distance_mi"], ridge["length_ft"], ridge["sections"]) == (
        "Fixture Ridge Trail",
        2.5,
        13200.0,
        2,
    )
    assert {row["challenge"] for row in (falls, ridge)} == {"900 Miler Club"}


def test_smhc_never_lands_a_members_date_completed_or_notes():
    landed = json.dumps(smhc())

    assert "2024-05-01" not in landed and "a member's note" not in landed


def test_smhc_refuses_a_sheet_whose_trails_do_not_sum_to_its_own_total():
    cells = smhc_cells()
    cells[-1][4] = cells[-2][4] = 4.5

    with pytest.raises(SheetLayoutChanged, match="sum to 3.50 mi"):
        smhc(cells)


def test_smhc_refuses_a_section_under_no_trail_and_a_header_that_moved():
    cells = smhc_cells()
    with pytest.raises(SheetLayoutChanged, match="not under a trail"):
        smhc([*cells[:3], cells[5], *cells[3:]])
    cells[1][4] = "Totals"
    with pytest.raises(SheetLayoutChanged, match="header cell 2:5"):
        smhc(cells)


# --- The reader ------------------------------------------------------------------------------------------------------

HEADERS = {"Last-Modified": "Thu, 15 Jun 2023 10:44:42 GMT"}


def test_every_row_carries_the_workbooks_manifest_and_no_document_property(registry, requests_mock):
    body = workbook({"CoverSheet": [["A Fixture Person"]], "Hikes": WMC_CELLS}, creator="A Fixture Person")
    requests_mock.get(WMC, content=body, headers={**HEADERS, "Content-Length": str(len(body))})
    proofs: dict = {}

    rows = list(content_sheet("wmc_hike_ratings", club="wmc", type="suggested_hikes").rows(proofs))

    assert proofs == {"raw_wmc__wmc_hike_ratings": 3} and len(rows) == 3
    assert set(SHEET_DOCUMENT_COLUMNS) <= set(rows[0])
    assert (rows[0]["document_sheet"], rows[0]["document_bytes"]) == ("Hikes", len(body))
    assert "A Fixture Person" not in json.dumps(rows), "neither the cover sheet nor the author property lands"


def test_a_304_to_the_workbooks_own_validator_is_fresh_and_a_host_that_sends_none_is_unknown(registry, requests_mock):
    from lib.freshness_state import Freshness

    resource = content_sheet("wmc_hike_ratings", club="wmc", type="suggested_hikes")
    recorded = {"files": {WMC: {"last_modified": HEADERS["Last-Modified"], "content_length": "9"}}}
    requests_mock.get(WMC, status_code=304)
    assert resource.change_check(recorded)[0] is Freshness.FRESH

    requests_mock.get(WMC, content=b"PK\x03\x04", headers={})
    assert resource.change_check(recorded)[0] is Freshness.UNKNOWN


def test_a_family_with_no_registered_key_fails_at_import():
    with pytest.raises(KeyError, match="no family"):
        content_sheet("no_such_family")
