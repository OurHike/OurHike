"""Tests for archive_nynjtc_sheet_extents.py - the one-time read of each paper
sheet's footprint off the Avenza Map Store (#1574).

Synthetic product pages, written here in the shape Avenza's carry
(`data-bounds="[{'lat': …, 'lng': …}, …]"`). The real store is read by a
person dispatching archive-nynjtc-sheets.yml, never by a test: the whole
point of the archive is that the source will not be there for ever.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

import archive_nynjtc_sheet_extents as archive
from lib.r2_keys import validate_key

BOUNDS_118 = (
    "[{'lat': 41.11147651488203, 'lng': -74.23560636507692}, "
    "{'lat': 41.25342144853717, 'lng': -74.23560636507692}, "
    "{'lat': 41.25342144853717, 'lng': -73.98676765703402}, "
    "{'lat': 41.11147651488203, 'lng': -73.98676765703402}]"
)


def page(bounds: str | None, title: str = "Harriman-Bear Mountain (South - Map 118) : 2023 : Trail Conference") -> str:
    attribute = "" if bounds is None else f' data-bounds="{bounds}"'
    return f'<html><head><title>{title}</title></head><body><div id="map" class="product__map"{attribute}></div></body></html>'


class TestParseBounds:
    def test_reads_the_four_corners_as_lon_lat(self):
        ring = archive.parse_bounds(page(BOUNDS_118))

        assert ring == [
            (-74.23560636507692, 41.11147651488203),
            (-74.23560636507692, 41.25342144853717),
            (-73.98676765703402, 41.25342144853717),
            (-73.98676765703402, 41.11147651488203),
        ]

    def test_a_page_with_no_data_bounds_is_no_footprint(self):
        assert archive.parse_bounds(page(None)) is None

    def test_unescapes_html_entities_in_the_attribute(self):
        escaped = BOUNDS_118.replace("'", "&#39;")

        assert archive.parse_bounds(page(escaped)) is not None

    def test_a_footprint_outside_nynjtcs_region_is_refused(self):
        elsewhere = "[{'lat': 0.0, 'lng': 0.0}, {'lat': 1.0, 'lng': 0.0}, {'lat': 1.0, 'lng': 1.0}, {'lat': 0.0, 'lng': 1.0}]"

        assert archive.parse_bounds(page(elsewhere)) is None

    def test_garbage_in_the_attribute_is_no_footprint_rather_than_a_crash(self):
        assert archive.parse_bounds(page("[{'lat': 'north'}]")) is None
        assert archive.parse_bounds(page("not a list at all")) is None
        assert archive.parse_bounds(page("[{'lat': 41.2, 'lng': -74.1}]")) is None


def reference(*products: dict) -> dict:
    return {"maps": list(products)}


class TestBuildArchive:
    def test_writes_every_listed_sheet_and_no_footprint_for_one_avenza_does_not_sell(self):
        fetched: list[str] = []

        def fetch(handle: str) -> str:
            fetched.append(handle)
            return page(BOUNDS_118)

        document = archive.build_archive(
            reference(
                {"handle": "harriman-bear-mountain-trails-map", "sheets": ["118", "145"], "avenza": {"118": "a118", "145": None}}
            ),
            fetch=fetch,
            now=dt.datetime(2026, 9, 17, 14, 0, tzinfo=dt.UTC),
        )

        assert fetched == ["a118"]
        assert document["sheets"]["118"]["bounds"] is not None
        assert document["sheets"]["118"]["product"] == "harriman-bear-mountain-trails-map"
        assert document["sheets"]["145"] == {
            "product": "harriman-bear-mountain-trails-map",
            "avenza_handle": None,
            "bounds": None,
            "edition_year": None,
        }
        assert document["generated_at"] == "2026-09-17T14:00:00Z"

    def test_carries_the_edition_year_the_avenza_title_names(self):
        document = archive.build_archive(
            reference({"handle": "h", "sheets": ["118"], "avenza": {"118": "a118"}}),
            fetch=lambda handle: page(BOUNDS_118, title="Harriman-Bear Mountain (South - Map 118) : 2023 : Trail Conference"),
        )

        assert document["sheets"]["118"]["edition_year"] == 2023

    def test_refuses_a_sheet_two_products_both_list(self):
        with pytest.raises(SystemExit, match="sheet 118 is listed by two products"):
            archive.build_archive(
                reference(
                    {"handle": "one", "sheets": ["118"], "avenza": {"118": "a"}},
                    {"handle": "two", "sheets": ["118"], "avenza": {"118": "b"}},
                ),
                fetch=lambda handle: page(BOUNDS_118),
            )

    def test_the_key_it_writes_is_legal_and_under_the_archive_prefix(self):
        assert archive.ARCHIVE_KEY.startswith("archive/")
        assert validate_key(archive.ARCHIVE_KEY) is None


class TestUpload:
    def test_refuses_to_upload_unless_writing_is_switched_on(self, tmp_path, monkeypatch):
        monkeypatch.delenv(archive.WRITE_ENABLED_ENV_VAR, raising=False)
        path = tmp_path / "nynjtc_map_sheets.json"
        path.write_text("{}")

        with pytest.raises(SystemExit, match=archive.WRITE_ENABLED_ENV_VAR):
            archive.upload(path)

    def test_refuses_a_key_the_layout_would_refuse(self, tmp_path, monkeypatch):
        monkeypatch.setenv(archive.WRITE_ENABLED_ENV_VAR, "true")
        path = tmp_path / "x.json"
        path.write_text("{}")

        with pytest.raises(SystemExit):
            archive.upload(path, key="archive/Final_v2.json")


class TestTheReviewedTable:
    """What reference/nynjtc_paper_maps.json says today, dated, so a hand edit
    that drops a sheet or doubles one is a red test rather than a quiet
    change in what the phone can match."""

    @staticmethod
    def real() -> dict:
        return json.loads(archive.REFERENCE_PATH.read_text(encoding="utf-8"))

    def test_every_sheet_belongs_to_exactly_one_product(self):
        rows = archive.sheets_to_archive(self.real())

        # 2026-09-17: twelve products, 43 sheets between them.
        assert len(rows) == 43

    def test_the_two_sheets_avenza_does_not_sell_are_recorded_as_such(self):
        rows = archive.sheets_to_archive(self.real())
        without = sorted(sheet for sheet, row in rows.items() if row["avenza_handle"] is None)

        # Catskill 145 and 146, 2026-09-17. A third here is a table edit
        # somebody should have meant.
        assert without == ["145", "146"]
