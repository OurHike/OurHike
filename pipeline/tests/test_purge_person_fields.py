"""purge_person_fields.py, decision 56's purge, end to end on a local raw store: real dlt, real pins, a stored warehouse.

Each test builds the store as the monthly lane built ours. A run under the rule as it stood before aafa7296, when
nothing was left out, lands two layers holding a person field: `RANGER`, named in PERSON_FIELDS, and `DataOwner`,
named only in its sources.json row's `person_fields`, as Alaska Trails' is. That run's as-landed copy, its pin, a
warehouse stored from the pin and a browse copy follow. Then the fix lands, and for most tests the next run re-reads
both layers without the fields and is pinned too. conftest.py's socket guard stays on; requests_mock answers as an
ArcGIS Online layer does (tests/test_extract_run.py's FakeLayer).

SENTINEL stands in for a person's name and e-mail address: no line the purge prints, and nothing it writes to the
summary, may ever hold it.
"""

from __future__ import annotations

import io
import json
import re
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import hand_off
import purge_person_fields as purge
from extract import _kinds
from extract._kinds import ArcgisLayer, ConditionsQuery, PodcastFeed
from extract._run import make_pipeline, run_pipeline
from extract._warehouse import has_pin, load_pinned, pin_raw_inputs, store_once
from tests.test_extract_run import AGOL, FIELDS, LINES_URL, FakeLayer, feature

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / ".github" / "workflows"
OWNED_URL = f"{AGOL}/Owned/FeatureServer/0"
SENTINEL = "SENTINEL_PERSON_56"
TRAILS = "raw_testclub__trails"
OWNED = "raw_alaska__owned"


class OwnedLayer(FakeLayer):
    """An ArcGIS Online layer whose `DataOwner` names who supplied each segment, as Alaska Trails' does."""

    def metadata(self, request, context):
        if request.headers.get("If-None-Match") == self.etag:
            context.status_code = 304
            return None
        context.headers["ETag"] = self.etag
        return {"objectIdField": "OBJECTID", "fields": [*FIELDS, {"name": "DataOwner", "type": "esriFieldTypeString"}]}


def owned_feature(oid: int) -> dict:
    row = feature(oid, "Segment")
    row["properties"]["DataOwner"] = f"{SENTINEL}@example.org"
    return row


def trails() -> ArcgisLayer:
    return ArcgisLayer(key="trails", club="testclub", type="trail_lines")


def owned() -> ArcgisLayer:
    return ArcgisLayer(key="owned", club="alaska", type="trail_lines")


def write_registry(path: Path, *, fixed: bool) -> None:
    """sources.json with the two layers; after the fix, the owned layer's row names `DataOwner` in `person_fields`."""
    owned_row = {"key": "owned", "url": OWNED_URL}
    if fixed:
        owned_row["person_fields"] = ["DataOwner"]
    path.write_text(json.dumps({"sources": [{"key": "trails", "url": LINES_URL}, owned_row]}))
    _kinds._registry.cache_clear()


@pytest.fixture
def registry(tmp_path, monkeypatch):
    path = tmp_path / "sources.json"
    monkeypatch.setattr(_kinds, "REGISTRY_PATH", path)
    write_registry(path, fixed=True)
    yield path
    _kinds._registry.cache_clear()


@contextmanager
def before_the_fix(monkeypatch, registry: Path):
    """The extract as it stood before aafa7296: no PERSON_FIELDS, no person-shaped backstop, no row `person_fields`."""
    write_registry(registry, fixed=False)
    with monkeypatch.context() as before:
        before.setattr(_kinds, "PERSON_FIELDS", frozenset())
        before.setattr(_kinds, "PERSON_SHAPED", re.compile(r"(?!)"))
        yield
    write_registry(registry, fixed=True)


class Bucket:
    """A raw bucket on disk, laid out as R2's: the monthly lane under raw/dlt/monthly, the step cache under steps/."""

    def __init__(self, tmp_path: Path):
        self.root = tmp_path / "bucket"
        self.root.mkdir()
        self.url = self.root.as_uri()
        self.lane_url = f"{self.url}/raw/dlt/monthly"
        self.steps_url = f"{self.url}/steps"
        self.pipelines_dir = str(tmp_path / "pipelines")
        self.tmp_path = tmp_path

    def month(self):
        return run_pipeline(
            "monthly", self.lane_url, resources=[trails(), owned()], pipelines_dir=self.pipelines_dir, as_landed=True
        )

    def pipeline(self):
        return make_pipeline("monthly", self.lane_url, self.pipelines_dir)

    def pin(self, raw_run: str) -> None:
        pin_raw_inputs(self.pipeline(), self.lane_url, self.steps_url, raw_run)

    def store_warehouse(self, raw_run: str) -> Path:
        """A warehouse built from the pin, stored under build-reference.yml's key beside a manifest; returns its file."""
        local = self.tmp_path / f"build-{raw_run}"
        local.mkdir()
        with duckdb.connect(str(local / "warehouse.duckdb")) as con:
            load_pinned(con, self.pipeline(), self.steps_url, raw_run)
            con.execute("create schema base")
            con.execute(f"create table base.base_testclub__trails as select * from raw.{TRAILS}")
        (local / "manifest.json").write_text('{"nodes": {}}')
        store_once(
            self.pipeline(),
            self.lane_url,
            self.steps_url,
            f"dbt_warehouse/ua/{raw_run}",
            [local / "warehouse.duckdb", local / "manifest.json"],
        )
        return local / "warehouse.duckdb"

    def put(self, key: str, data: bytes) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def keys(self) -> set[str]:
        return {str(path.relative_to(self.root)) for path in self.root.rglob("*") if path.is_file()}

    def run(self, *flags: str, summary: Path | None = None) -> int:
        argv = ["--bucket-url", self.url, "--pipelines-dir", str(self.tmp_path / "purge-dlt"), *flags]
        if summary is not None:
            argv += ["--summary", str(summary)]
        return purge.main(argv, resources=[trails(), owned()])

    def find(self) -> purge.Answer:
        scratch = self.tmp_path / "scratch"
        scratch.mkdir(exist_ok=True)
        return purge.find(self.url, str(self.tmp_path / "purge-dlt"), scratch, resources=[trails(), owned()])


def parquet_bytes(table: pa.Table) -> bytes:
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink)
    return sink.getvalue().to_pybytes()


@pytest.fixture
def bucket(tmp_path, registry, requests_mock, monkeypatch):
    """The store as decision 56 found it: a month landed before the fix, pinned, built and stored, and copied to browse/.

    Beside it, objects every bucket of ours holds that hold no person field: the Geofabrik mirror (a PBF this script
    does not read, and its index) and a row-history save of a mart's snapshot.
    """
    FakeLayer(requests_mock, LINES_URL, [feature(1), feature(2, ranger=SENTINEL), feature(3, ranger=SENTINEL)])
    OwnedLayer(requests_mock, OWNED_URL, [owned_feature(10), owned_feature(11)])
    store = Bucket(tmp_path)
    with before_the_fix(monkeypatch, registry):
        store.before = store.month()
    store.pin(store.before.run_id)
    warehouse = store.store_warehouse(store.before.run_id)
    store.put("browse/ourhike.duckdb", warehouse.read_bytes())
    store.put("raw/dlt/monthly/current/osm/vermont-latest.osm.pbf", b"\x00\x00\x00\x0dOSMHeader")
    store.put("raw/dlt/monthly/current/index.json", b'{"osm/vermont-latest.osm.pbf": {"sha256": "ab", "size": 15}}')
    store.put("history/monthly/history.json", b'{"current": "s1"}')
    store.put(
        "history/monthly/saves/s1/int_trails__history.parquet",
        parquet_bytes(pa.table({"trail_key": ["a"], "name": ["Long Trail"]})),
    )
    return store


@pytest.fixture
def reread(bucket):
    """The month after the fix: both layers read again without the fields (their definitions moved), and pinned."""
    bucket.after = bucket.month()
    assert set(bucket.after.verdicts.values()) == {"stale"}, "a change to the person rule reads every layer again"
    bucket.pin(bucket.after.run_id)
    return bucket


def lines_of(capsys) -> str:
    out = capsys.readouterr().out
    assert SENTINEL not in out, "the purge printed a person's value"
    return out


def test_before_the_reread_a_delete_refuses_names_each_table_and_field_and_deletes_nothing(bucket, capsys, tmp_path):
    """The current tables still hold the fields, so a pin made tomorrow would copy them again: nothing may go yet."""
    before = bucket.keys()
    summary = tmp_path / "summary.md"

    status = bucket.run("--delete", summary=summary)

    out = lines_of(capsys)
    assert status == 1
    assert bucket.keys() == before, "a refused delete deletes nothing"
    assert f"{TRAILS}: ranger (PERSON_FIELDS): 2 of 3 rows with a value" in out
    assert f"{OWNED}: dataowner (owned's person_fields): 2 of 2 rows with a value" in out
    assert "a resource still lands it, and lands it without the field when it next reads it" in out
    assert "Refused: a current table still holds a person field" in out
    assert SENTINEL not in summary.read_text()


def test_listing_only_before_the_reread_says_a_delete_would_refuse_and_ends_0(bucket, capsys):
    status = bucket.run()

    out = lines_of(capsys)
    assert status == 0
    assert "::warning title=A current table still holds a person field::" in out
    assert "would refuse" in out


def test_after_the_reread_exactly_the_copies_that_hold_a_field_are_listed(reread):
    answer = reread.find()

    assert answer.clean_now and answer.complete
    before, after = reread.before.run_id, reread.after.run_id
    doomed = {stored.key for stored in answer.doomed}
    pin_a = {key for key in reread.keys() if key.startswith(f"steps/raw_inputs/{before}/")}
    warehouse_a = {key for key in reread.keys() if key.startswith(f"steps/dbt_warehouse/ua/{before}/")}
    landed_a = {
        f"raw/dlt/monthly/as_landed/{reread.before.load_id}/trails.geojson",
        f"raw/dlt/monthly/as_landed/{reread.before.load_id}/owned.geojson",
    }
    assert pin_a and warehouse_a and pin_a | warehouse_a | landed_a | {"browse/ourhike.duckdb"} == doomed
    assert not {key for key in doomed if after in key or reread.after.load_id in key}, "nothing of the clean month"
    by_key = {stored.key: stored for stored in answer.store.objects}
    assert by_key[f"steps/raw_inputs/{before}/tables/{TRAILS}.parquet"].fields["ranger"].with_value == 2
    assert by_key[f"steps/raw_inputs/{before}/tables/{OWNED}.parquet"].fields["dataowner"].listed_by == "owned's person_fields"
    landed = by_key[f"raw/dlt/monthly/as_landed/{reread.before.load_id}/owned.geojson"].fields
    assert landed["DataOwner"].rows == 2 and landed["DataOwner"].with_value == 2, "the upstream's own spelling, in the JSON"
    browse = by_key["browse/ourhike.duckdb"].fields
    assert {"raw.raw_testclub__trails.ranger", "raw.raw_alaska__owned.dataowner", "base.base_testclub__trails.ranger"} <= set(
        browse
    ), "a model is read too: base_ carries every column of its raw table"
    assert by_key["raw/dlt/monthly/current/osm/vermont-latest.osm.pbf"].kind == purge.UNREAD
    assert by_key["history/monthly/saves/s1/int_trails__history.parquet"].read
    assert not by_key["history/monthly/saves/s1/int_trails__history.parquet"].holds


def test_a_reread_table_keeps_the_fields_column_empty_and_the_purge_keeps_it(reread, capsys):
    """dlt keeps every column its schema has seen, so the month after the fix still writes `ranger` and `dataowner`,
    with no value in any row, and so does its pin: a column is not a copy of anybody, so neither refuses nor goes."""
    answer = reread.find()

    current = {stored.table: stored for stored in answer.store.objects if stored.current}
    assert current[TRAILS].fields["ranger"].rows == 3 and current[TRAILS].fields["ranger"].with_value == 0
    assert current[OWNED].fields["dataowner"].with_value == 0
    pin_b = [stored for stored in answer.store.objects if stored.unit == f"steps/raw_inputs/{reread.after.run_id}/"]
    assert any(stored.empty_columns for stored in pin_b) and not any(stored.holds for stored in pin_b)
    assert reread.run() == 0
    out = lines_of(capsys)
    assert "2 tables keep a listed field's column with no value in any row" in out
    assert "Clean: no current table holds a person field." in out


def test_a_pins_record_and_a_warehouses_file_go_before_the_rest_of_their_unit(reread, capsys):
    status = reread.run("--delete")

    out = lines_of(capsys)
    assert status == 0
    deleted = [line.removeprefix("deleted ") for line in out.splitlines() if line.startswith("deleted ")]
    before = reread.before.run_id
    pin = [key for key in deleted if key.startswith(f"steps/raw_inputs/{before}/")]
    assert pin[0] == f"steps/raw_inputs/{before}/raw_inputs.json", "a pin cut short must never read as finished"
    store = [key for key in deleted if key.startswith(f"steps/dbt_warehouse/ua/{before}/")]
    assert store[0] == f"steps/dbt_warehouse/ua/{before}/warehouse.duckdb"
    firsts = {pin[0], store[0]}
    assert set(deleted[: len(firsts)]) == firsts, "every unit's record before any other object"


def test_the_delete_removes_exactly_what_was_listed_and_the_clean_months_pin_still_builds(reread, capsys, tmp_path):
    listed = {stored.key for stored in reread.find().doomed}
    kept = reread.keys() - listed
    summary = tmp_path / "summary.md"

    status = reread.run("--delete", summary=summary)

    out = lines_of(capsys)
    assert status == 0
    assert reread.keys() == kept, "exactly the listed objects are gone, and nothing else"
    assert {line.removeprefix("deleted ") for line in out.splitlines() if line.startswith("deleted ")} == listed
    assert f"Deleted {len(listed):,} objects; 0 problems." in out
    assert not has_pin(reread.pipeline(), reread.steps_url, reread.before.run_id)
    with duckdb.connect() as con:
        loaded = load_pinned(con, reread.pipeline(), reread.steps_url, reread.after.run_id)
        (rangers,) = con.execute(f"select count(ranger) from raw.{TRAILS}").fetchone()
    assert loaded == {TRAILS: 3, OWNED: 2} and rangers == 0, "the clean month's pin builds, its column empty"
    assert SENTINEL not in summary.read_text()
    assert reread.find().doomed == [], "a second purge finds nothing left"


@pytest.fixture
def two_clean_pins(reread):
    """A second pin of the clean month: FRESH, nothing re-read, so it copies the same loads' as-landed files."""
    reread.pin(reread.after.run_id)  # already pinned: written once, so nothing changes
    reread.second = reread.month()
    assert set(reread.second.verdicts.values()) == {"fresh"}
    reread.pin(reread.second.run_id)
    return reread


def test_a_pinned_as_landed_file_whose_recorded_sha256_matches_another_is_read_once(two_clean_pins):
    """Two pins of the same clean month copy the same as-landed bytes, and each pin's record says so."""
    answer = two_clean_pins.find()

    copies = [stored for stored in answer.store.objects if stored.copy_of is not None]
    assert {Path(stored.key).name for stored in copies} == {"trails.geojson", "owned.geojson"}
    assert all(stored.read and not stored.holds for stored in copies)


def test_a_pinned_copy_whose_twin_would_not_read_is_read_itself(two_clean_pins, monkeypatch):
    """A copy is kept on its twin's answer only when there is one: no object is kept on a read that failed."""
    read_json = purge.read_json
    broken = f"steps/raw_inputs/{two_clean_pins.after.run_id}/as_landed/trails.geojson"

    def refuses_one(store, stored, rule):
        if stored.key == broken:
            raise OSError("a read cut off in transit")
        return read_json(store, stored, rule)

    monkeypatch.setattr(purge, "read_json", refuses_one)

    answer = two_clean_pins.find()

    by_key = {stored.key: stored for stored in answer.store.objects}
    twin = by_key[f"steps/raw_inputs/{two_clean_pins.second.run_id}/as_landed/trails.geojson"]
    assert by_key[broken].error and not answer.complete
    assert twin.read and twin.copy_of is None, "read itself, not on the broken twin's answer"


def test_an_object_that_cannot_be_read_stops_the_delete_and_is_named(reread, capsys):
    reread.put("steps/odd/broken.parquet", b"PAR1 this is not a parquet file")
    before = reread.keys()

    status = reread.run("--delete")

    out = lines_of(capsys)
    assert status == 1
    assert reread.keys() == before
    assert "steps/odd/broken.parquet:" in out and "Incomplete" in out


def test_an_object_deleted_between_the_listing_and_its_read_is_gone_not_unreadable(reread, monkeypatch):
    """The hourly legs run outside raw-lake-monthly, and their own runs trim served copies and replace table files
    while a purge reads: an object that vanished holds nothing, and must not make the answer incomplete."""
    read_parquet = purge.read_parquet
    vanished = "history/monthly/saves/s1/int_trails__history.parquet"

    def trimmed_meanwhile(store, stored, rule):
        if stored.key == vanished:
            raise FileNotFoundError(stored.path)
        return read_parquet(store, stored, rule)

    monkeypatch.setattr(purge, "read_parquet", trimmed_meanwhile)

    answer = reread.find()

    assert [stored.key for stored in answer.store.objects if stored.gone] == [vanished]
    assert answer.complete and vanished not in {stored.key for stored in answer.doomed}


def test_a_table_a_leg_no_longer_reads_is_listed_alone_and_does_not_refuse(tmp_path, registry, requests_mock, monkeypatch):
    """A leg's store keeps every table it ever loaded (extract/_warehouse.py's load_warehouse()): one whose resource
    moved to the other job is frozen there, read by no build, and read again by no run, so it is deleted, not waited on."""
    FakeLayer(requests_mock, LINES_URL, [feature(1, ranger=SENTINEL)])
    store = Bucket(tmp_path)
    leg_url = f"{store.url}/raw/dlt/notices_ua"
    moved = ArcgisLayer(key="trails", club="testclub", type="closures")
    with before_the_fix(monkeypatch, registry):
        report = run_pipeline("notices_ua", leg_url, resources=[moved], pipelines_dir=store.pipelines_dir)
    scratch = tmp_path / "scratch"
    scratch.mkdir()

    answer = purge.find(store.url, str(tmp_path / "purge-dlt"), scratch, resources=[trails()])

    assert answer.clean_now, "a table the leg's job no longer reads is not current"
    (frozen,) = [stored.key for stored in answer.doomed]
    assert frozen.startswith(f"raw/dlt/notices_ua/raw/{TRAILS}/{report.load_id}.")


#: Where publish-conditions.yml's UA leg hands its warehouse to check-conditions.yml (hand_off.py's FOLDER, under the
#: leg's history store).
HAND_OFF = f"history/conditions_ua/{hand_off.FOLDER}/"


def hand_off_a_warehouse(bucket: Bucket, ranger: str | None) -> None:
    """An hourly build's warehouse, handed off by hand_off.py's own `put`: one raw table whose `ranger` is `ranger`."""
    local = bucket.tmp_path / "hourly-build" / "warehouse.duckdb"
    local.parent.mkdir()
    with duckdb.connect(str(local)) as con:
        con.execute("create schema raw")
        con.execute(f"create table raw.{TRAILS} (objectid integer, ranger varchar)")
        con.execute(f"insert into raw.{TRAILS} values (1, ?), (2, null)", [ranger])
    hand_off.put(f"{bucket.url}/history/conditions_ua", local, run="593")


def test_an_hourly_hand_off_holding_a_field_is_unpacked_read_and_deleted_whole_pointer_first(reread, capsys):
    """hand_off.py's checks/warehouse.duckdb.gz holds every raw table its leg read, gzipped. Before PR #1805's security
    review of 2026-10-09 the purge listed it under "NOT READ", which never refuses a delete, so a purge could end
    "Deleted ... 0 problems" with the field still in the last hand-off."""
    hand_off_a_warehouse(reread, SENTINEL)

    answer = reread.find()
    status = reread.run("--delete")

    out = lines_of(capsys)
    packed = {stored.key: stored for stored in answer.store.objects}[f"{HAND_OFF}warehouse.duckdb.gz"]
    assert (packed.kind, packed.read) == (purge.DUCKDB, True), "read as a DuckDB file, not passed over"
    assert packed.fields[f"raw.{TRAILS}.ranger"].with_value == 1
    assert f"{HAND_OFF} (an hourly hand-off, 2 objects" in out
    deleted = [line.removeprefix("deleted ") for line in out.splitlines() if line.startswith("deleted ")]
    assert status == 0
    assert deleted.index(f"{HAND_OFF}hand_off.json") < deleted.index(f"{HAND_OFF}warehouse.duckdb.gz"), (
        "the pointer first, so a checks run cut in finds nothing handed off rather than a torn upload"
    )
    assert not {key for key in reread.keys() if key.startswith(HAND_OFF)}


def test_an_hourly_hand_off_built_from_clean_tables_is_read_and_kept(reread):
    """A build after the re-read hands off the field's column empty, as every re-read table keeps it: read, and kept."""
    hand_off_a_warehouse(reread, None)

    answer = reread.find()

    packed = {stored.key: stored for stored in answer.store.objects}[f"{HAND_OFF}warehouse.duckdb.gz"]
    assert packed.read and not packed.holds and packed.empty_columns
    assert not [stored.key for stored in answer.doomed if stored.key.startswith(HAND_OFF)]
    assert answer.complete


@pytest.mark.parametrize("chunk", [7, 64, 1 << 20])
def test_every_key_is_counted_once_however_the_stream_is_cut(monkeypatch, chunk):
    """json_keys() reads JSON_CHUNK at a time; a key cut by a chunk's edge is found once, from the carry."""
    monkeypatch.setattr(purge, "JSON_CHUNK", chunk)
    monkeypatch.setattr(purge, "JSON_OVERLAP", 600)
    document = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": None, "properties": {"Creator": None if oid % 3 else "x", "NAME": "y" * oid}}
            for oid in range(40)
        ],
    }
    data = json.dumps(document, separators=(",", ":")).encode()

    counts = purge.json_keys(io.BytesIO(data))

    assert counts[(b"Creator", b"")] == 14 and counts[(b"Creator", b"n")] == 26
    assert counts[(b"NAME", b"")] == 39 and counts[(b"NAME", b'""')] == 1, "an empty string is no value"
    assert counts[(b"properties", b"")] == 40


def test_a_key_inside_a_string_value_is_not_a_key():
    """A property whose value is JSON text, as a WordPress `yoast_head_json` can be, never yields its inner keys."""
    data = json.dumps({"properties": {"blob": json.dumps({"Creator": "x", "Editor": None}), "NAME": "a"}}).encode()

    keys = {key for key, _ in purge.json_keys(io.BytesIO(data))}

    assert keys == {b"properties", b"blob", b"NAME"}


def test_each_tables_rule_is_the_extracts_own_lists(registry):
    """PERSON_FIELDS everywhere; a table's own row's person_fields; a podcast's PERSON_TAGS; the conditions queries'
    WITHHELD_COLUMNS; and a table no resource lands any more ruled by its row, found by its name."""
    podcast = PodcastFeed(key="show", club="testclub", type="podcasts")
    query = ConditionsQuery(key="closures", club="ourhike", type="closures")
    rules = purge.FieldRules([trails(), owned(), podcast, query])

    assert rules(TRAILS).listed_by("CREATOR") == "PERSON_FIELDS"
    assert rules(TRAILS).listed_by("dataowner") is None, "another row's person_fields are not this table's"
    assert rules(OWNED).listed_by("dataowner") == "owned's person_fields"
    assert rules("raw_alaska__owned_gone").listed_by("dataowner") is None
    assert rules("raw_somewhere__owned").listed_by("dataowner") == "owned's person_fields", "a table no resource lands"
    assert rules(podcast.table).listed_by("itunes_owner") == "PERSON_TAGS"
    assert rules(query.table).listed_by("reported_by") == "WITHHELD_COLUMNS"
    assert rules(None).listed_by("last_edited_user") == "PERSON_FIELDS"
    assert rules(None).listed_by("last_edited_date") is None, "a date is never a person, and no list names it"


def test_the_prefixes_are_the_ones_the_workflows_write():
    """The purge places a pin, a stored warehouse and a row-history save by the prefixes refresh-reference.yml,
    build-reference.yml and publish-conditions.yml hand the code; a prefix renamed there would leave units unplaced."""
    refresh = (WORKFLOWS / "refresh-reference.yml").read_text()
    build = (WORKFLOWS / "build-reference.yml").read_text()
    conditions = (WORKFLOWS / "publish-conditions.yml").read_text()

    assert f'--steps-url "s3://$R2_RAW_BUCKET/{purge.STEPS_PREFIX}"' in refresh
    assert f'--key "{purge.WAREHOUSE_PREFIX}/ua/$RAW_RUN"' in build
    assert f'--history-url "s3://$R2_RAW_BUCKET/{purge.HISTORY_PREFIX}/monthly"' in build
    assert f'--history-url "s3://$R2_RAW_BUCKET/{purge.HISTORY_PREFIX}/conditions_$ENVIRONMENT"' in conditions
    assert re.search(
        rf'hand_off\.py put\s+--url "s3://\$R2_RAW_BUCKET/{purge.HISTORY_PREFIX}/conditions_\$ENVIRONMENT"', conditions
    )
    assert '--bucket-url "s3://$R2_RAW_BUCKET/raw/dlt/monthly"' in refresh


def test_the_bucket_is_named_bare_or_refused(capsys):
    with pytest.raises(ValueError, match="not a bucket name"):
        purge.main(["--raw-bucket", "our-hike-raw/raw"])


def test_place_puts_each_kind_of_object_where_the_code_writes_it():
    assert purge.place("steps/raw_inputs/R/raw_inputs.json", "", 0).first
    assert purge.place("steps/raw_inputs/R/tables/raw_a__b.parquet", "", 0).table == "raw_a__b"
    assert purge.place("steps/raw_inputs/R/as_landed/x.geojson", "", 0).unit == "steps/raw_inputs/R/"
    assert purge.place("raw/dlt/notices_ua/served/R/manifest.json", "", 0).first
    assert purge.place("raw/dlt/notices_ua/served/R/tables/raw_a__b.parquet", "", 0).unit == "raw/dlt/notices_ua/served/R/"
    assert purge.place("raw/dlt/monthly/raw/_dlt_loads/x.jsonl", "", 0).kind == purge.DLT
    assert purge.place("raw/dlt/monthly/raw/init", "", 0).kind == purge.DLT
    dataset = purge.place("raw/dlt/monthly/raw/raw_a__b/1759.5.abc.parquet", "", 0)
    assert (dataset.lane, dataset.table, dataset.load_id, dataset.unit) == ("monthly", "raw_a__b", "1759.5", None)
    assert purge.place("raw/dlt/monthly/as_landed/1759.5/index.json", "", 0).kind == purge.RECORD
    assert purge.place("raw/dlt/monthly/as_landed/1759.5/external/x.geojson", "", 0).kind == purge.JSON_ROWS
    assert purge.place("steps/dbt_warehouse/ua/R/manifest.json", "", 0).kind == purge.RECORD
    assert purge.place("history/monthly/saves/s/x.parquet", "", 0).unit == "history/monthly/saves/s/"
    assert purge.place("history/monthly/history.json", "", 0).kind == purge.RECORD
    assert purge.place("browse/ourhike.duckdb", "", 0).kind == purge.DUCKDB
    packed = purge.place("history/conditions_ua/checks/warehouse.duckdb.gz", "", 0)
    assert (packed.kind, packed.unit, packed.first) == (purge.DUCKDB, "history/conditions_ua/checks/", False)
    pointer = purge.place("history/conditions_ua/checks/hand_off.json", "", 0)
    assert (pointer.kind, pointer.unit, pointer.first) == (purge.RECORD, "history/conditions_ua/checks/", True)
