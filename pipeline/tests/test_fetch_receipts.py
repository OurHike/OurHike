"""What a fetcher's receipt has to be worth (#542).

The whole point of a receipt is to be believed by something that did not
watch the fetch happen, so the properties worth pinning are the ones that
decide whether packaging can trust it: it is written only after the
fetcher's own gate, it survives being read on a different machine, and it
notices when the bytes it describes have moved on without it.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lib import fetch_receipts


@pytest.fixture
def root(tmp_path):
    """A pretend pipeline/ directory. Every helper takes `root` precisely so
    the suite never writes into the real data/ tree.

    A subdirectory of tmp_path rather than tmp_path itself, so a test can
    still put a file OUTSIDE the pretend root and have somewhere to put it."""
    root = tmp_path / "pipeline"
    (root / "data" / "raw").mkdir(parents=True)
    return root


def write(root, relative: str, text: str = "{}"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


# --- recording ---------------------------------------------------------------


def test_a_receipt_records_every_output_it_was_given(root):
    a = write(root, "data/raw/manifest.json", '{"a": 1}')
    b = write(root, "data/raw/centerline.geojson", '{"type": "FeatureCollection"}')

    receipt = fetch_receipts.record("fetch_all", [a, b], root=root)

    assert receipt["fetcher"] == "fetch_all"
    assert [entry["path"] for entry in receipt["outputs"]] == [
        "data/raw/manifest.json",
        "data/raw/centerline.geojson",
    ]
    assert receipt["outputs"][0]["bytes"] == len('{"a": 1}')


def test_paths_are_recorded_relative_to_the_pipeline_root(root):
    """The export manifests record absolute paths, and publish-vector-data.yml
    keeps building and publishing in one job because of it - they "only agree
    on one filesystem", which that workflow calls a trap. A receipt is meant
    to be restored onto a different runner, so it must not carry the trap."""
    path = write(root, "data/raw/opentrail_at.geojson")

    receipt = fetch_receipts.record("fetch_opentrail", [path], root=root)

    recorded = receipt["outputs"][0]["path"]
    assert not recorded.startswith("/")
    assert str(root) not in recorded


def test_recording_an_output_that_is_not_there_raises(root):
    """A fetcher calling record() is asserting it just wrote these files. If
    one is missing at that moment the fetcher is broken, and the one thing
    that must not happen is a receipt saying the fetch succeeded."""
    with pytest.raises(FileNotFoundError):
        fetch_receipts.record("fetch_all", [root / "data/raw/never-written.json"], root=root)

    assert fetch_receipts.load("fetch_all", root=root) is None


def test_each_fetcher_gets_its_own_file(root):
    """One shared receipts.json would be read-modify-written by every
    fetcher, so two running independently - the entire point of #542 - would
    race on it. Separate files mean a fetcher can only damage its own."""
    a = write(root, "data/raw/manifest.json")
    b = write(root, "data/raw/opentrail_at.geojson")

    fetch_receipts.record("fetch_all", [a], root=root)
    fetch_receipts.record("fetch_opentrail", [b], root=root)

    written = sorted(p.name for p in fetch_receipts.receipts_dir(root).iterdir())
    assert written == ["fetch_all.json", "fetch_opentrail.json"]


def test_recording_twice_replaces_rather_than_appends(root):
    path = write(root, "data/raw/manifest.json", "first")
    fetch_receipts.record("fetch_all", [path], root=root)
    path.write_text("second")

    fetch_receipts.record("fetch_all", [path], root=root)

    receipt = fetch_receipts.load("fetch_all", root=root)
    assert len(receipt["outputs"]) == 1
    assert fetch_receipts.verify(receipt, root=root) == []


def test_no_temp_file_is_left_behind(root):
    """Written through a temp file and os.replace, like the outputs it
    describes. A stray .tmp would be read by nothing but would sit in the
    cache being restored forever."""
    path = write(root, "data/raw/manifest.json")
    fetch_receipts.record("fetch_all", [path], root=root)

    assert [p.name for p in fetch_receipts.receipts_dir(root).iterdir()] == ["fetch_all.json"]


# --- reading -----------------------------------------------------------------


def test_an_output_outside_the_pipeline_tree_is_recorded_absolutely(root, tmp_path):
    """The degraded form, and it must degrade rather than raise. Refusing
    would turn "a caller put its output somewhere unusual" into a fetch that
    reports failure - a far worse answer than a path that is merely not
    portable. In the real pipeline this never happens; in the suite it is
    every test that redirects a fetcher's OUT_PATH to tmp_path."""
    outside = tmp_path / "elsewhere" / "out.json"
    outside.parent.mkdir(parents=True)
    outside.write_text("{}")

    receipt = fetch_receipts.record("fetch_all", [outside], root=root)

    assert receipt["outputs"][0]["path"] == str(outside)
    assert fetch_receipts.verify(receipt, root=root) == []


def test_an_absolutely_recorded_output_is_still_checked(root, tmp_path):
    outside = tmp_path / "elsewhere" / "out.json"
    outside.parent.mkdir(parents=True)
    outside.write_text("as fetched")
    receipt = fetch_receipts.record("fetch_all", [outside], root=root)

    outside.write_text("changed underneath")

    assert fetch_receipts.verify(receipt, root=root) != []


def test_a_fetcher_that_never_ran_loads_as_none(root):
    assert fetch_receipts.load("fetch_elevation", root=root) is None


def test_a_corrupt_receipt_raises_rather_than_reading_as_missing(root):
    """A fetch that never happened and a record of one that is corrupt are
    different problems. Collapsing them into one None would let a torn file
    be reported as an absent fetch, which points the reader at the wrong
    thing entirely."""
    fetch_receipts.receipts_dir(root).mkdir(parents=True, exist_ok=True)
    fetch_receipts.receipt_path("fetch_all", root).write_text("{not json")

    with pytest.raises(json.JSONDecodeError):
        fetch_receipts.load("fetch_all", root=root)


# --- verifying ---------------------------------------------------------------


def test_a_receipt_matching_the_bytes_on_disk_has_no_problems(root):
    path = write(root, "data/raw/manifest.json", "stable")
    receipt = fetch_receipts.record("fetch_all", [path], root=root)

    assert fetch_receipts.verify(receipt, root=root) == []


def test_an_output_deleted_after_the_fetch_is_a_problem(root):
    path = write(root, "data/raw/manifest.json")
    receipt = fetch_receipts.record("fetch_all", [path], root=root)
    path.unlink()

    problems = fetch_receipts.verify(receipt, root=root)

    assert len(problems) == 1
    assert "not on disk" in problems[0]


def test_an_output_edited_after_the_fetch_is_a_problem(root):
    """The case a same-process check can never catch: between the fetch and
    the package, a file can be truncated by a full disk, half-restored from a
    cache, or edited. Re-hashing is the only thing that notices."""
    path = write(root, "data/raw/manifest.json", "as fetched")
    receipt = fetch_receipts.record("fetch_all", [path], root=root)
    path.write_text("something else entirely")

    problems = fetch_receipts.verify(receipt, root=root)

    assert len(problems) == 1
    assert "changed since it was fetched" in problems[0]


def test_a_truncated_output_is_caught_even_at_the_same_size(root):
    """Size alone would wave this through - hashing is what makes the check
    real."""
    path = write(root, "data/raw/manifest.json", "aaaa")
    receipt = fetch_receipts.record("fetch_all", [path], root=root)
    path.write_text("bbbb")

    assert fetch_receipts.verify(receipt, root=root) != []


def test_every_bad_output_is_reported_not_just_the_first(root):
    a = write(root, "data/raw/one.geojson", "one")
    b = write(root, "data/raw/two.geojson", "two")
    receipt = fetch_receipts.record("fetch_all", [a, b], root=root)
    a.unlink()
    b.write_text("changed")

    assert len(fetch_receipts.verify(receipt, root=root)) == 2


def test_a_receipt_claiming_no_outputs_is_a_problem(root):
    """An empty outputs list would otherwise verify clean, which is the worst
    possible answer: a receipt that proves nothing while looking satisfied."""
    problems = fetch_receipts.verify({"fetcher": "fetch_all", "outputs": []}, root=root)

    assert len(problems) == 1
    assert "no outputs" in problems[0]


def test_a_receipt_entry_with_no_path_is_a_problem(root):
    problems = fetch_receipts.verify({"fetcher": "fetch_all", "outputs": [{"sha256": "x"}]}, root=root)

    assert len(problems) == 1
    assert "no path" in problems[0]


# --- age ---------------------------------------------------------------------


def test_age_is_measured_from_the_recorded_completion(root):
    path = write(root, "data/raw/manifest.json")
    fetched_at = datetime(2026, 8, 1, tzinfo=timezone.utc)
    receipt = fetch_receipts.record("fetch_all", [path], root=root, now=fetched_at)

    days = fetch_receipts.age_days(receipt, now=fetched_at + timedelta(days=7, hours=12))

    assert days == pytest.approx(7.5)


def test_a_naive_timestamp_is_read_as_utc(root):
    """Nothing in this pipeline writes one, but a receipt restored from an
    older cache might, and a crash on tz-naive arithmetic inside a gate is a
    worse outcome than assuming the only timezone this project records in."""
    receipt = {"completed_at": "2026-08-01T00:00:00"}

    days = fetch_receipts.age_days(receipt, now=datetime(2026, 8, 3, tzinfo=timezone.utc))

    assert days == pytest.approx(2.0)


@pytest.mark.parametrize("stamp", [None, "", "not a date"])
def test_an_unreadable_timestamp_reports_no_age_rather_than_raising(stamp):
    """Reported as unknown by the gate above. A receipt whose outputs still
    hash correctly is doing its main job; a mangled date is not worth failing
    a release over, and definitely not worth a traceback."""
    assert fetch_receipts.age_days({"completed_at": stamp}) is None


# --- the required set --------------------------------------------------------


def test_the_two_always_required_fetchers_need_no_flag():
    """export_poi.py reads both - the ArcGIS layers via fetch_all.py and
    opentrail's output directly (export_poi.py:108). That is a fact about the
    code rather than about a particular run, so it is not something a caller
    should be able to forget to pass."""
    assert fetch_receipts.expected_fetchers() == ["fetch_all", "fetch_opentrail"]


def test_a_run_that_asked_for_elevation_expects_its_receipt_too():
    expected = fetch_receipts.expected_fetchers(["fetch_elevation"])

    assert expected == ["fetch_all", "fetch_opentrail", "fetch_elevation"]


def test_naming_an_always_required_fetcher_does_not_duplicate_it():
    assert fetch_receipts.expected_fetchers(["fetch_all"]) == ["fetch_all", "fetch_opentrail"]


#: Every fetcher the vector publish depends on, and the script that is it.
#: fetch_topo_quads.py is deliberately absent - it belongs to the raster
#: pipeline and a different workflow, and #542 is scoped to the vector
#: fetchers. Adding it here is how that gets revisited.
VECTOR_FETCHERS = (
    "fetch_all",
    "fetch_opentrail",
    "fetch_atc_photos",
    "fetch_poi_images",
    "fetch_elevation",
)


@pytest.mark.parametrize("fetcher", VECTOR_FETCHERS)
def test_every_vector_fetcher_records_a_receipt_under_its_own_name(fetcher):
    """The wiring, checked at the source rather than by driving five main()s
    through their network mocks.

    The failure this guards is quiet and total: a fetcher that stops calling
    record() - or calls it with a name that no longer matches the one
    expected_fetchers() asks for - makes the gate report "this run needs it
    and it never finished" on every single run. A check that is always red is
    one nobody reads, which is how the pipeline ends up back where #542 found
    it."""
    source = (Path(__file__).resolve().parents[1] / f"{fetcher}.py").read_text(encoding="utf-8")

    # \s* because ruff format wraps a long call onto the next line, and this
    # test must pin the wiring rather than the formatter's line-breaking.
    assert re.search(rf'fetch_receipts\.record\(\s*"{fetcher}"', source)


def test_the_contracts_named_fetchers_are_all_real_scripts():
    """REQUIRED_FETCHERS and ADVISORY_FETCHERS are strings, so a typo in
    either would silently ask for a receipt nothing will ever write."""
    for fetcher in fetch_receipts.REQUIRED_FETCHERS + fetch_receipts.ADVISORY_FETCHERS:
        assert fetcher in VECTOR_FETCHERS


def test_commons_is_the_only_advisory_fetcher():
    """fetch_poi_images.py's step carries continue-on-error because Commons
    "is a third-party API this project has no relationship with". ATC photos
    deliberately do not: that step reads the same ATC data the export is
    built from, so an outage there means "the release has bigger problems
    than missing photos" - the workflow's own words. Pinned here because the
    two are one line apart and easy to conflate."""
    assert fetch_receipts.ADVISORY_FETCHERS == ("fetch_poi_images",)
    assert "fetch_atc_photos" not in fetch_receipts.ADVISORY_FETCHERS
