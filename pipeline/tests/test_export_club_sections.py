"""The exporter's publish contract (#659): its manifest must work from any
CWD and its main() must answer like its siblings.

The assembly logic itself is tested where it lives, in
test_lib_club_sections.py - this file covers only the seam publish.py
reads, which is where the audit found the faults: a relative manifest path
(every sibling stores absolute, and publish.py resolves the string against
its own CWD) and a main() returning the artifact body where every sibling
returns its manifest.
"""

import hashlib
import json
import os
from pathlib import Path

import export_club_sections


def test_the_manifest_path_is_absolute_and_main_returns_the_manifest(tmp_path, monkeypatch):
    out_path = tmp_path / "processed" / "club_sections.json"
    manifest_path = tmp_path / "processed" / "club_sections_manifest.json"
    monkeypatch.setattr(export_club_sections, "OUT_PATH", out_path)
    monkeypatch.setattr(export_club_sections, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(
        export_club_sections,
        "build_output",
        lambda: {"sources": {}, "clubs": [], "unattributed": []},
    )
    # Publishes happen from repo root, not pipeline/ - the CWD that made the
    # old relative path crash publish.py mid-collect.
    monkeypatch.chdir(tmp_path)

    returned = export_club_sections.main()

    manifest = json.loads(manifest_path.read_text())
    assert Path(manifest["path"]).is_absolute(), "a relative manifest path resolves against publish.py's CWD, not pipeline/"
    assert Path(manifest["path"]).exists(), "the path must reach the artifact from any CWD"
    assert manifest["sha256"] == hashlib.sha256(out_path.read_bytes()).hexdigest()
    assert returned == manifest, "main() answers with the manifest, like every sibling exporter"
    assert os.getcwd() != str(Path(export_club_sections.__file__).parent), (
        "fixture guard: this test must NOT run from pipeline/, or the CWD claim above proves nothing"
    )


# --- The source dates (#852) -----------------------------------------------
#
# The sheet could name which layer attributed a club and not say when that
# layer was edited, because the two dates lived in a docstring rather than in
# the artifact. These cover the reading of them: the conversion, and the
# several ways a date is legitimately absent.


def write_raw_manifest(raw_dir: Path, entries: dict) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "manifest.json").write_text(json.dumps(entries))


# The two numbers #594 measured by hand and #852 quotes, as ArcGIS gives them.
CENTERLINE_EDITED_MS = 1785801600000  # 2026-08-04
POLYGONS_EDITED_MS = 1723680000000  # 2024-08-15


def test_reads_both_dates_the_issue_measured_by_hand(tmp_path):
    """The whole point: nine days against two years, and the split shows it."""
    write_raw_manifest(
        tmp_path,
        {
            export_club_sections.CENTERLINE_KEY: {"data_last_edit_date": CENTERLINE_EDITED_MS},
            export_club_sections.POLYGONS_KEY: {"data_last_edit_date": POLYGONS_EDITED_MS},
        },
    )

    dates = export_club_sections.source_edit_dates(tmp_path)

    assert dates[export_club_sections.CENTERLINE_KEY] == "2026-08-04"
    assert dates[export_club_sections.POLYGONS_KEY] == "2024-08-15"


def test_a_layer_with_no_recorded_date_is_absent_rather_than_null(tmp_path):
    """fetch_all.py tolerates a failed dataLastEditDate lookup and records the
    layer with a null - lib/freshness_state.atc_sources calls that case out as
    real. Absent and null would render identically on the sheet, and one of
    them is a shape the client has to handle."""
    write_raw_manifest(
        tmp_path,
        {
            export_club_sections.CENTERLINE_KEY: {"data_last_edit_date": None},
            export_club_sections.POLYGONS_KEY: {"data_last_edit_date": POLYGONS_EDITED_MS},
        },
    )

    dates = export_club_sections.source_edit_dates(tmp_path)

    assert export_club_sections.CENTERLINE_KEY not in dates
    assert dates[export_club_sections.POLYGONS_KEY] == "2024-08-15"


def test_no_manifest_at_all_dates_nothing_rather_than_failing(tmp_path):
    """A raw directory somebody unpacked by hand knows nothing about when ATC
    last edited anything, and that is an answer rather than an error."""
    assert export_club_sections.source_edit_dates(tmp_path) == {}


def test_an_unreadable_manifest_dates_nothing_rather_than_crashing_the_export(tmp_path):
    (tmp_path / "manifest.json").write_text("{ not json")
    assert export_club_sections.source_edit_dates(tmp_path) == {}


def test_a_sentinel_epoch_publishes_no_date_rather_than_1969(tmp_path):
    """A layer on ATC's FeatureServer cannot have been edited at or before
    1970, so zero and negatives are corruption. "31 Dec 1969" on a sheet is a
    confident wrong claim standing where no claim was available."""
    for sentinel in (0, -1):
        write_raw_manifest(tmp_path, {export_club_sections.CENTERLINE_KEY: {"data_last_edit_date": sentinel}})
        assert export_club_sections.source_edit_dates(tmp_path) == {}


def test_a_date_that_is_not_a_number_publishes_nothing(tmp_path):
    for junk in ("2026-08-04", True, [], {"epoch": 1}):
        write_raw_manifest(tmp_path, {export_club_sections.CENTERLINE_KEY: {"data_last_edit_date": junk}})
        assert export_club_sections.source_edit_dates(tmp_path) == {}, junk


def test_the_dates_are_keyed_by_layer_so_a_shared_layer_carries_one_date(tmp_path):
    """Keyed by layer rather than by the role it plays. If `attribution` and
    `names` ever came from one layer, a role-keyed block would carry the same
    date twice and invite the copies to drift."""
    write_raw_manifest(
        tmp_path,
        {export_club_sections.CENTERLINE_KEY: {"data_last_edit_date": CENTERLINE_EDITED_MS}},
    )

    dates = export_club_sections.source_edit_dates(tmp_path)

    assert set(dates) <= {
        export_club_sections.CENTERLINE_KEY,
        export_club_sections.POLYGONS_KEY,
        export_club_sections.MILEPOSTS_KEY,
    }
    assert "attribution" not in dates and "names" not in dates


def test_the_published_sources_block_keeps_its_string_values(tmp_path, monkeypatch):
    """The compatibility promise, asserted rather than described.

    A phone can hold app code older than the artifact it just downloaded -
    artifacts update independently of the PWA - and that client reads
    `sources.attribution` as a string. Turning these into objects would parse
    to null there and drop the attribution line entirely.
    """
    monkeypatch.setattr(export_club_sections, "load_features", lambda path: [])
    monkeypatch.setattr(export_club_sections, "attribute_mileposts", lambda *a: [])
    monkeypatch.setattr(export_club_sections, "build_club_index", lambda features: None)
    monkeypatch.setattr(export_club_sections, "assemble", lambda *a: ([], []))
    monkeypatch.setattr(export_club_sections, "canonical_clubs", lambda features: {})
    write_raw_manifest(
        tmp_path,
        {export_club_sections.CENTERLINE_KEY: {"data_last_edit_date": CENTERLINE_EDITED_MS}},
    )

    output = export_club_sections.build_output(tmp_path)

    assert output["sources"] == {
        "attribution": export_club_sections.CENTERLINE_KEY,
        "names": export_club_sections.POLYGONS_KEY,
        "miles": export_club_sections.MILEPOSTS_KEY,
    }
    assert all(isinstance(v, str) for v in output["sources"].values())
    assert output["source_edited"] == {export_club_sections.CENTERLINE_KEY: "2026-08-04"}
