"""prune_raw_store.py, the raw store's retention step, end to end on a local raw store: real dlt, real pins and the
as-landed files they copy, stored warehouses, row-history saves, and each environment's latest.json on a local public
bucket.

Five monthly runs land two ArcGIS layers as the monthly lane lands them (tests/test_extract_run.py's FakeLayer, under
conftest.py's socket guard). `trails` changes every month, so each run loads it again; `owned` never changes after the
first, so every later run answers it FRESH and every pin copies its first landing. Each run is pinned. UA serves the
fourth (MONTH 3); the fifth is newer than anything served, as a month whose build failed would be. So the rules keep
pins 2 (one step back), 3 (served) and 4 (newer), and delete pins 0 and 1, whole.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb
import pytest

import prune_raw_store as prune
from extract import _kinds
from extract._warehouse import has_pin, load_pinned
from lib import data_env
from tests.test_extract_run import LINES_URL, FakeLayer, feature
from tests.test_purge_person_fields import OWNED, OWNED_URL, TRAILS, Bucket, write_registry

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / ".github" / "workflows"
#: A raw_run with the shape of an extract run's id and no pin.
UNPINNED = "20260101T000000.000000Z"


class Store(Bucket):
    """The purge tests' raw bucket, beside a public bucket holding each environment's latest.json."""

    def __init__(self, tmp_path: Path):
        super().__init__(tmp_path)
        self.public = tmp_path / "public"
        self.public_url = self.public.as_uri()
        self.months = []

    def serve(self, environment: str, release: str, raw_run: str | None = None) -> None:
        latest = {"version": "v", "release": release, "artifacts": {}}
        if raw_run is not None:
            latest["raw_run"] = raw_run
        path = self.public / data_env.scope_key(environment, "latest.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(latest))

    def raw_run(self, month: int) -> str:
        return self.months[month].run_id

    def load(self, month: int) -> str:
        return self.months[month].load_id

    def argv(self, *flags: str) -> list[str]:
        return [
            "--bucket-url",
            self.url,
            "--data-base-url",
            self.public_url,
            "--pipelines-dir",
            str(self.tmp_path / "prune-dlt"),
            *flags,
        ]

    def prune(self, *flags: str) -> int:
        return prune.main(self.argv(*flags))

    def decide(self, **named: str) -> prune.Plan:
        return prune.decide(
            self.url, str(self.tmp_path / "prune-dlt"), self.public_url, {env: [run] for env, run in named.items()}
        )

    def under(self, prefix: str) -> set[str]:
        return {key for key in self.keys() if key.startswith(prefix)}


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """sources.json with the two layers' rows, as tests/test_purge_person_fields.py writes it."""
    path = tmp_path / "sources.json"
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    write_registry(path, fixed=True)
    yield path
    _kinds._registry.cache_clear()


@pytest.fixture
def months(tmp_path, registry, requests_mock):
    """Five monthly runs, each pinned; production serves no pin (its release names none), and UA's release, from
    before latest.json's raw_run existed, names none either."""
    lines = FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2)])
    FakeLayer(requests_mock, OWNED_URL, [feature(10), feature(11)])
    store = Store(tmp_path)
    for month in range(5):
        lines.etag = f"v{month + 1}"
        lines.features = [feature(1, f"Trail, month {month}"), feature(2)]
        store.months.append(store.month())
        store.pin(store.raw_run(month))
    assert [report.verdicts[OWNED] for report in store.months] == ["stale", "fresh", "fresh", "fresh", "fresh"]
    assert {report.verdicts[TRAILS] for report in store.months} == {"stale"}
    store.serve(data_env.PRODUCTION, "2026-09-24-2")
    store.serve(data_env.UA, "2026-10-10-2")
    return store


def deleted_lines(out: str) -> list[str]:
    return [line.removeprefix("deleted ") for line in out.splitlines() if line.startswith("deleted ")]


def pin(store: Store, month: int) -> str:
    return f"steps/raw_inputs/{store.raw_run(month)}/"


def landed(store: Store, month: int) -> str:
    return f"raw/dlt/monthly/as_landed/{store.load(month)}/"


# --- Nothing goes without --delete, or while what is served is not known ---


def test_listing_only_deletes_nothing_and_names_every_unit_with_why(months, capsys, tmp_path):
    before = months.keys()
    summary = tmp_path / "summary.md"

    status = months.prune("--keep-raw-run", f"ua={months.raw_run(3)}", "--summary", str(summary))

    out = capsys.readouterr().out
    assert status == 0 and months.keys() == before
    assert f"KEEP      {months.raw_run(3)}: " in out and "(ua serves it)" in out
    assert f"KEEP      {months.raw_run(2)}: " in out and "one step back" in out
    assert f"KEEP      {months.raw_run(4)}: " in out and "newer than every served pin" in out
    assert f"DELETE    {months.raw_run(0)}: " in out and f"DELETE    {months.raw_run(1)}: " in out
    assert "production: release 2026-09-24-2, latest.json names no raw_run: serves no pin" in out
    assert "Listing only, nothing deleted. A dispatch with retention=delete deletes the" in out
    page = summary.read_text()
    assert "## Retention step" in page and "### Pins: would delete" in page
    assert "| before |" in page and "| after |" in page


def test_nothing_is_deleted_while_ua_names_no_raw_run_and_none_is_given(months, capsys):
    """UA's releases from before latest.json's raw_run existed name none, so --keep-raw-run is required until one does."""
    before = months.keys()

    status = months.prune("--delete")

    out = capsys.readouterr().out
    assert status == 1 and months.keys() == before and not deleted_lines(out)
    assert "ua's latest.json names no raw_run, and no --keep-raw-run ua=<raw_run> was given" in out
    assert "::error title=The retention step could not decide::" in out
    assert "not decided: what each environment serves is not known" in out


def test_a_latest_json_that_cannot_be_read_refuses_every_delete(months, capsys):
    (months.public / "latest.json").unlink()  # production's
    before = months.keys()

    status = months.prune("--delete", "--keep-raw-run", f"ua={months.raw_run(3)}")

    out = capsys.readouterr().out
    assert status == 1 and months.keys() == before
    assert "production: NOT KNOWN, its latest.json could not be read" in out


def test_a_served_raw_run_with_no_pin_refuses_every_delete(months, capsys):
    """A mistyped raw_run, or a pin a purge removed: a person looks first, either way."""
    before = months.keys()

    status = months.prune("--delete", "--keep-raw-run", f"ua={UNPINNED}")

    out = capsys.readouterr().out
    assert status == 1 and months.keys() == before
    assert f"ua serves raw_run {UNPINNED}, which has no finished pin" in out


@pytest.mark.parametrize("spec", ["dev=20261009T223039.840094Z", "ua=20261009T223039Z", "ua", "staging=x"])
def test_keep_raw_run_names_an_environment_this_step_reads_and_an_extract_runs_id(spec, capsys):
    with pytest.raises(SystemExit):
        prune.main(["--bucket-url", "file:///nowhere", "--keep-raw-run", spec])
    assert "is not ENVIRONMENT=RAW_RUN" in capsys.readouterr().err


# --- Pins ---


def test_uas_pin_one_step_back_and_every_newer_pin_stay_and_the_rest_go_whole_record_first(months, capsys):
    kept = {month: months.under(pin(months, month)) for month in (2, 3, 4)}
    gone = months.under(pin(months, 0)) | months.under(pin(months, 1))

    status = months.prune("--delete", "--keep-raw-run", f"ua={months.raw_run(3)}")

    out = capsys.readouterr().out
    deleted = deleted_lines(out)
    assert status == 0, out
    assert gone <= set(deleted) and not months.under(pin(months, 0)) and not months.under(pin(months, 1))
    for month, keys in kept.items():
        assert months.under(pin(months, month)) == keys, f"pin {month} is whole"
    for month in (0, 1):
        record = f"{pin(months, month)}raw_inputs.json"
        rest = [deleted.index(key) for key in deleted if key.startswith(pin(months, month)) and key != record]
        assert deleted.index(record) < min(rest), "a pin cut short must never read as finished"
    with duckdb.connect() as con:
        assert load_pinned(con, months.pipeline(), months.steps_url, months.raw_run(3)) == {TRAILS: 2, OWNED: 2}
    assert not has_pin(months.pipeline(), months.steps_url, months.raw_run(1))


def test_uas_latest_json_raw_run_is_kept_as_the_flag_would_keep_it(months, capsys):
    """From the first build that publishes after this change, latest.json names its pin and no flag is needed."""
    months.serve(data_env.UA, "2026-11-03", raw_run=months.raw_run(3))

    status = months.prune("--delete")

    assert status == 0, capsys.readouterr().out
    assert {key.split("/")[2] for key in months.under("steps/raw_inputs/")} == {months.raw_run(m) for m in (2, 3, 4)}


def test_a_mistyped_older_raw_run_keeps_that_pin_too_and_never_costs_uas_one_step_back(months):
    """latest.json names month 3 and the dispatcher month 1: both are served, and one step back is still month 2."""
    months.serve(data_env.UA, "2026-11-03", raw_run=months.raw_run(3))

    plan = months.decide(ua=months.raw_run(1))

    verdicts = {unit.name: unit.keep for unit in plan.of(prune.PIN)}
    assert verdicts == {months.raw_run(m): m != 0 for m in range(5)}


def test_a_pin_folder_whose_name_is_not_an_extract_runs_id_is_kept(months):
    months.put("steps/raw_inputs/by-hand/raw_inputs.json", b"{}")

    plan = months.decide(ua=months.raw_run(3))

    (odd,) = [unit for unit in plan.of(prune.PIN) if unit.name == "by-hand"]
    assert odd.keep and "no rule places it" in odd.why


# --- Stored warehouses ---


def test_only_the_warehouse_of_the_raw_run_ua_serves_stays_and_one_goes_warehouse_file_first(months, capsys):
    for month in (1, 3, 4):
        for name in ("warehouse.duckdb", "manifest.json", "run_results.json"):
            months.put(f"steps/dbt_warehouse/ua/{months.raw_run(month)}/{name}", b"x" * 10)

    status = months.prune("--delete", "--keep-raw-run", f"ua={months.raw_run(3)}")

    deleted = deleted_lines(capsys.readouterr().out)
    assert status == 0
    assert {key.split("/")[3] for key in months.under("steps/dbt_warehouse/")} == {months.raw_run(3)}
    for month in (1, 4):
        unit = f"steps/dbt_warehouse/ua/{months.raw_run(month)}/"
        assert deleted.index(f"{unit}warehouse.duckdb") < deleted.index(f"{unit}manifest.json")


# --- As-landed files ---


def test_as_landed_keeps_each_tables_current_load_and_what_the_kept_pins_were_copied_from(months, capsys):
    """`owned` landed once, in month 0's load, and every pin since copied it: that file and its index stay, month 0's
    `trails` goes, month 1's load goes whole, index first, and months 2 to 4's loads stay for the pins kept."""
    first = landed(months, 0)
    kept = {key for month in (2, 3, 4) for key in months.under(landed(months, month))}

    status = months.prune("--delete", "--keep-raw-run", f"ua={months.raw_run(3)}")

    deleted = deleted_lines(capsys.readouterr().out)
    assert status == 0
    assert months.under(first) == {f"{first}index.json", f"{first}owned.geojson"}
    assert not months.under(landed(months, 1)), "month 1's load goes whole"
    assert deleted.index(f"{landed(months, 1)}index.json") < deleted.index(f"{landed(months, 1)}trails.geojson")
    assert kept <= months.keys()


def test_after_the_delete_the_next_month_still_reads_owned_fresh_and_pins(months, requests_mock):
    """What the rules keep is what the next run reads: fresh_but_unserved() finds `owned` in month 0's index, and
    pin_raw_inputs() copies month 0's owned.geojson. Had either gone, the run would read `owned` again or refuse."""
    assert months.prune("--delete", "--keep-raw-run", f"ua={months.raw_run(3)}") == 0

    FakeLayer(requests_mock, LINES_URL, [feature(1, "Trail, month 5"), feature(2)], etag="v6")
    after = months.month()
    months.pin(after.run_id)

    assert after.verdicts == {TRAILS: "stale", OWNED: "fresh"}
    assert has_pin(months.pipeline(), months.steps_url, after.run_id)


def test_as_landed_files_beside_no_committed_load_refuse_rather_than_read_as_nothing_current(months, capsys):
    for path in Path(months.root, "raw/dlt/monthly/raw/_dlt_loads").iterdir():
        path.unlink()
    before = months.keys()

    status = months.prune("--delete", "--keep-raw-run", f"ua={months.raw_run(3)}")

    out = capsys.readouterr().out
    assert status == 1 and months.keys() == before
    assert "the monthly lane records no committed load: which loads are current is not known" in out


# --- Row-history saves ---


def put_saves(store: Store, name: str, folder: str, ids: list[str]) -> None:
    for save_id in ids:
        store.put(f"history/{name}/{folder}/{save_id}/int_trails__history.parquet", b"PAR1" + b"x" * 100)


def test_the_monthly_store_keeps_its_newest_three_saves_and_every_save_its_pointers_name(months, capsys):
    """The monthly store keeps 3 saves. elementary.json was pointed back at s2 by hand: a save a pointer names is kept, as
    row_history.py's own _prune() keeps the save a save was built on."""
    ids = [f"s{number}" for number in range(1, 7)]
    put_saves(months, "monthly", "saves", ids)
    put_saves(months, "monthly", "elementary", ids)
    months.put("history/monthly/history.json", json.dumps({"save_id": "s6", "previous_save_id": "s5"}).encode())
    months.put("history/monthly/elementary.json", json.dumps({"save_id": "s2", "previous_save_id": "s1"}).encode())

    status = months.prune("--delete", "--keep-raw-run", f"ua={months.raw_run(3)}")

    assert status == 0, capsys.readouterr().out
    assert {key.split("/")[3] for key in months.under("history/monthly/saves/")} == {"s4", "s5", "s6"}
    assert {key.split("/")[3] for key in months.under("history/monthly/elementary/")} == {"s1", "s2", "s4", "s5", "s6"}
    assert months.under("history/monthly/history.json") and months.under("history/monthly/elementary.json")


def test_an_hourly_store_keeps_every_save_here_and_the_listing_says_how_many_are_past_its_24(months, capsys):
    """Its writers run outside raw-lake-monthly and prune it on every save (row_history.py's KEEP_SAVES, 24)."""
    ids = [f"20261015T{hour:02d}0000000000Z-aaaaaa" for hour in range(26)]
    put_saves(months, "conditions_ua", "saves", ids)
    months.put("history/conditions_ua/history.json", json.dumps({"save_id": ids[-1], "previous_save_id": ids[-2]}).encode())
    before = months.under("history/conditions_ua/")

    status = months.prune("--delete", "--keep-raw-run", f"ua={months.raw_run(3)}")

    out = capsys.readouterr().out
    assert status == 0 and months.under("history/conditions_ua/") == before
    assert "history/conditions_ua/saves/ holds 26 saves against its 24" in out
    assert "KEEP      conditions_ua/saves/*: 26 objects" in out and "26 saves against its 24, 2 past it" in out


# --- Everything else ---


def test_everything_else_is_listed_by_area_with_its_bytes_and_never_deleted(months, capsys):
    others = {
        "browse/ourhike.duckdb": 1000,
        "raw/dlt/monthly/current/osm/vermont-latest.osm.pbf": 2000,
        "steps/dem_samples/abc/samples.parquet": 3000,
        "history/conditions_ua/checks/hand_off.json": 40,
    }
    for key, size in others.items():
        months.put(key, b"x" * size)

    status = months.prune("--delete", "--keep-raw-run", f"ua={months.raw_run(3)}")

    out = capsys.readouterr().out
    assert status == 0 and set(others) <= months.keys()
    assert "   browse: 1 object, 1.0 KB" in out and "   steps/dem_samples: 1 object, 3.0 KB" in out
    assert "   raw/dlt/monthly/current: 1 object" in out and "   history/conditions_ua: 1 object" in out


def test_a_key_deleted_and_listed_again_afterwards_is_a_problem(months, capsys, monkeypatch):
    """purge_person_fields.py's delete(): the bucket is listed again and every deleted key checked gone."""
    from fsspec.implementations.local import LocalFileSystem

    stuck = f"{pin(months, 0)}raw_inputs.json"
    real = LocalFileSystem.rm_file

    def keeps_one(self, path):
        if not str(path).endswith(stuck):
            real(self, path)

    monkeypatch.setattr(LocalFileSystem, "rm_file", keeps_one)

    status = months.prune("--delete", "--keep-raw-run", f"ua={months.raw_run(3)}")

    out = capsys.readouterr().out
    assert status == 1
    assert f"::error title=A delete did not take::{stuck}: deleted, and listed again afterwards" in out


# --- The arithmetic, and the names other files hold ---


def test_the_cost_is_r2s_price_past_the_free_10_gb_month():
    """The maintainer's 233.23 GB: (233.23 - 10) x $0.015 = $3.35 a month, the poll's figure."""
    assert prune._cost(233_230_000_000) == pytest.approx(3.34845)
    assert prune._cost(5_000_000_000) == 0.0


def test_the_names_are_the_ones_the_workflows_and_publish_write():
    """PRUNED_STORES is the store build-reference.yml's build job saves to, LANE the prefix refresh-reference.yml's
    extract writes, and LATEST publish.py's pointer."""
    import publish

    build = (WORKFLOWS / "build-reference.yml").read_text()
    refresh = (WORKFLOWS / "refresh-reference.yml").read_text()
    stores = set(re.findall(r'--history-url "s3://\$R2_RAW_BUCKET/history/([a-z_]+)"', build))

    assert stores == set(prune.PRUNED_STORES)
    assert f'--bucket-url "s3://$R2_RAW_BUCKET/raw/dlt/{prune.LANE}"' in refresh and "--as-landed" in refresh
    assert prune.LATEST == publish.MANIFEST_KEY


def test_every_module_the_retention_step_imports_is_in_the_extracts_pins():
    """build-reference.yml's maintain job installs requirements-extract.txt and nothing else, as the purge's job does,
    so the step and every local module it reaches (purge_person_fields.py's helpers, row_history.py's count) may import
    nothing more (tests/test_extract_layout.py's walk, from this file)."""
    from importlib.metadata import packages_distributions

    from tests.test_extract_layout import PIPELINE_DIR, _import_closure

    reached, imported = _import_closure([PIPELINE_DIR / "prune_raw_store.py"])
    providers = packages_distributions()

    def canonical(name: str) -> str:
        return re.sub(r"[-_.]+", "-", name).lower()

    pinned = {
        canonical(match[1])
        for line in (PIPELINE_DIR / "requirements-extract.txt").read_text().splitlines()
        if (match := re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==", line))
    }
    assert PIPELINE_DIR / "purge_person_fields.py" in reached and PIPELINE_DIR / "row_history.py" in reached
    unpinned = sorted(name for name in imported if not any(canonical(d) in pinned for d in providers.get(name, [name])))
    assert not unpinned, f"imported by the retention step and not in requirements-extract.txt: {unpinned}"
