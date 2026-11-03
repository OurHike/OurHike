"""`scripts/analytics_keys.py`: publishing the public keys, and opening rows (#1902).

The opening's record is written and committed BEFORE anything is opened, and
publishing refuses to replace a month's key with a different secret's - the
two ways this script could quietly lose track of what was sealed and who read it.
"""

import importlib.util
import uuid
from datetime import date
from pathlib import Path

import pytest

from app.core.analytics_seal import month_label, month_public_key, new_secret, seal
from app.models.analytics import AnalyticsEvent, AnalyticsOpening, AnalyticsSealKey

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analytics_keys.py"
OCTOBER = date(2026, 10, 1)


@pytest.fixture(scope="module")
def keys():
    spec = importlib.util.spec_from_file_location("analytics_keys", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sealed_event(db_session, secret: bytes, payload: dict, *, user_key: str | None = None) -> AnalyticsEvent:
    event_id = str(uuid.uuid4())
    event = AnalyticsEvent(
        id=event_id,
        local_date=date(2026, 10, 3),
        received_on=date(2026, 10, 3),
        event="map_screen_viewed",
        platform="ios",
        user_key=user_key,
        has_fix=True,
        seal="sealed",
        sealed=seal(month_public_key(secret, "2026-10"), "2026-10", event_id, payload),
    )
    db_session.add(event)
    db_session.commit()
    return event


def test_a_secret_survives_being_written_down_and_read_back(keys):
    secret = new_secret()

    assert keys.decode_secret(keys.encode_secret(secret)) == secret


def test_something_that_is_not_a_secret_is_refused(keys):
    with pytest.raises(keys.KeysError):
        keys.decode_secret("hunter2")


def test_publishing_writes_each_months_public_key(db_session, keys):
    secret = new_secret()

    written = keys.publish(db_session, secret, OCTOBER, 3)

    assert written == [date(2026, 10, 1), date(2026, 11, 1), date(2026, 12, 1)]
    stored = db_session.get(AnalyticsSealKey, date(2026, 11, 1))
    assert bytes(stored.public_key) == month_public_key(secret, month_label(date(2026, 11, 1)))


def test_publishing_again_with_the_same_secret_is_a_no_op(db_session, keys):
    secret = new_secret()
    keys.publish(db_session, secret, OCTOBER, 2)

    assert keys.publish(db_session, secret, OCTOBER, 2) == []


def test_publishing_a_different_secret_over_a_month_is_refused(db_session, keys):
    keys.publish(db_session, new_secret(), OCTOBER, 1)

    with pytest.raises(keys.KeysError):
        keys.publish(db_session, new_secret(), OCTOBER, 1)


def test_opening_records_who_and_why_and_writes_the_rows_to_a_file(db_session, keys, tmp_path):
    secret = new_secret()
    event = _sealed_event(db_session, secret, {"account": "acct-1", "lat": 41.29871, "lon": -74.1881})
    out = tmp_path / "opened.csv"

    opened = keys.open_rows(
        db_session,
        secret,
        month=OCTOBER,
        opened_by="Test Maintainer",
        reason="checking the sealing works",
        event_id=event.id,
        key=None,
        out=out,
    )

    assert opened == 1
    assert "41.29871" in out.read_text() and "acct-1" in out.read_text()
    record = db_session.query(AnalyticsOpening).one()
    assert (record.opened_by, record.selector, record.rows_opened) == (
        "Test Maintainer",
        f"event {event.id}",
        1,
    )


def test_the_record_is_committed_even_when_opening_fails(db_session, keys, tmp_path):
    """A crash halfway must not leave an opening off the record."""
    secret = new_secret()
    _sealed_event(db_session, secret, {"lat": 41.3, "lon": -74.2})
    unwritable = tmp_path / "no-such-directory" / "opened.csv"

    with pytest.raises(OSError):
        keys.open_rows(
            db_session,
            secret,
            month=OCTOBER,
            opened_by="Test Maintainer",
            reason="a run that crashes",
            event_id=None,
            key=None,
            out=unwritable,
        )

    db_session.rollback()
    assert db_session.query(AnalyticsOpening).count() == 1


def test_an_opening_needs_a_reason(db_session, keys, tmp_path):
    with pytest.raises(keys.KeysError):
        keys.open_rows(
            db_session,
            new_secret(),
            month=OCTOBER,
            opened_by="Test Maintainer",
            reason="  ",
            event_id=None,
            key=None,
            out=tmp_path / "x.csv",
        )


def _open_into(db_session, keys, out: Path) -> int:
    return keys.open_rows(
        db_session,
        new_secret(),
        month=OCTOBER,
        opened_by="Test Maintainer",
        reason="checking where the file may go",
        event_id=None,
        key=None,
        out=out,
    )


def test_an_out_path_inside_the_repository_is_refused_before_anything_is_recorded(db_session, keys):
    inside = Path(__file__).resolve().parents[2] / "opened.csv"

    with pytest.raises(keys.KeysError):
        _open_into(db_session, keys, inside)

    assert not inside.exists()
    assert db_session.query(AnalyticsOpening).count() == 0


def test_an_existing_file_is_never_written_over(db_session, keys, tmp_path):
    out = tmp_path / "opened.csv"
    out.write_text("somebody's own notes\n")

    with pytest.raises(keys.KeysError):
        _open_into(db_session, keys, out)

    assert out.read_text() == "somebody's own notes\n"
    assert db_session.query(AnalyticsOpening).count() == 0


def test_the_opened_file_is_readable_by_its_owner_alone(db_session, keys, tmp_path):
    out = tmp_path / "opened.csv"

    _open_into(db_session, keys, out)

    assert out.stat().st_mode & 0o777 == 0o600


def test_the_command_refuses_an_out_inside_the_repository(db_session, keys, monkeypatch):
    monkeypatch.setattr(keys.getpass, "getpass", lambda prompt: keys.encode_secret(new_secret()))
    inside = Path(__file__).resolve().parents[2] / "opened.csv"
    argv = ["open", "--month", "2026-10", "--by", "Test", "--reason", "a test", "--whole-month", "--out", str(inside)]

    assert keys.main(argv) == 2
    assert not inside.exists()


def test_the_secret_is_read_at_the_hidden_prompt_and_never_from_the_environment(keys, monkeypatch):
    """A secret in a variable on the command line is a secret in shell history."""
    typed, exported = new_secret(), new_secret()
    monkeypatch.setenv("OURHIKE_ANALYTICS_SECRET", keys.encode_secret(exported))
    monkeypatch.setattr(keys.getpass, "getpass", lambda prompt: keys.encode_secret(typed))

    assert keys._read_secret() == typed
    assert "OURHIKE_ANALYTICS_SECRET=" not in keys.__doc__


def test_the_wrong_secret_opens_nothing(db_session, keys, tmp_path):
    _sealed_event(db_session, new_secret(), {"lat": 41.3, "lon": -74.2})
    out = tmp_path / "opened.csv"

    opened = keys.open_rows(
        db_session,
        new_secret(),
        month=OCTOBER,
        opened_by="Test Maintainer",
        reason="the wrong secret",
        event_id=None,
        key=None,
        out=out,
    )

    assert opened == 0
    assert "41.3" not in out.read_text()


# --- a month whose unlinked rows are in the usage archive (#1923) ------------------


@pytest.fixture()
def archived_october(db_session, keys):
    """October closed and archived: two unlinked sealed rows in a part in R2,
    one linked sealed row still in Postgres. Returns the secret, the store and the ids."""
    import boto3
    from moto import mock_aws

    from app.core import analytics_archive, analytics_rollup
    from app.core.analytics_archive import R2Store

    archive_script = importlib.util.module_from_spec(
        spec := importlib.util.spec_from_file_location("analytics_archive_script", SCRIPT.with_name("analytics_archive.py"))
    )
    spec.loader.exec_module(archive_script)
    secret = new_secret()
    unlinked = [_sealed_event(db_session, secret, {"lat": 41.3 + n / 10, "lon": -74.2}).id for n in range(2)]
    linked = _sealed_event(db_session, secret, {"account": "acct-9", "lat": 41.9, "lon": -74.9}, user_key="k" * 32).id
    analytics_rollup.run(db_session, today=date(2026, 11, 20))
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="ourhike-usage-test")
        store = R2Store(client, "ourhike-usage-test")
        analytics_archive.run(db_session, store, archive_script.write_parquet, today=date(2026, 11, 21))
        yield secret, store, unlinked, linked


def test_a_whole_month_opening_reads_its_archived_parts_beside_postgres(db_session, keys, archived_october, tmp_path):
    secret, store, unlinked, linked = archived_october
    out = tmp_path / "opened.csv"

    opened = keys.open_rows(
        db_session,
        secret,
        month=OCTOBER,
        opened_by="Test Maintainer",
        reason="checking an archived month opens",
        event_id=None,
        key=None,
        out=out,
        store=store,
    )

    assert opened == 3
    text = out.read_text()
    assert all(row_id in text for row_id in (*unlinked, linked))
    assert "41.4" in text and "acct-9" in text


def test_an_archived_row_opens_by_its_event_id(db_session, keys, archived_october, tmp_path):
    secret, store, unlinked, _ = archived_october
    out = tmp_path / "opened.csv"

    opened = keys.open_rows(
        db_session,
        secret,
        month=OCTOBER,
        opened_by="Test Maintainer",
        reason="one archived row",
        event_id=unlinked[1],
        key=None,
        out=out,
        store=store,
    )

    assert opened == 1 and unlinked[1] in out.read_text() and unlinked[0] not in out.read_text()


def test_a_part_that_is_not_the_file_the_archive_wrote_is_not_opened(db_session, keys, archived_october, tmp_path):
    """The record is still written first: an opening that stops halfway is on it."""
    secret, store, _, _ = archived_october
    store.put("2026-10/part-0001.parquet", b"not the file the archive wrote")

    with pytest.raises(keys.KeysError, match="not the file the archive wrote"):
        keys.open_rows(
            db_session,
            secret,
            month=OCTOBER,
            opened_by="Test Maintainer",
            reason="a tampered part",
            event_id=None,
            key=None,
            out=tmp_path / "opened.csv",
            store=store,
        )

    db_session.rollback()
    assert db_session.query(AnalyticsOpening).one().rows_opened is None


def test_an_archived_month_with_no_archive_settings_is_refused_before_the_record(
    db_session, keys, archived_october, tmp_path, monkeypatch
):
    secret, _, _, _ = archived_october
    for name in ("USAGE_ARCHIVE_R2_ENDPOINT_URL", "USAGE_ARCHIVE_R2_BUCKET", "USAGE_ARCHIVE_R2_ACCESS_KEY_ID"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(keys.KeysError, match="Nothing was recorded"):
        keys.open_rows(
            db_session,
            secret,
            month=OCTOBER,
            opened_by="Test Maintainer",
            reason="no token for the archive",
            event_id=None,
            key=None,
            out=tmp_path / "opened.csv",
        )

    assert db_session.query(AnalyticsOpening).count() == 0


def test_a_user_key_opening_never_reads_the_archive(db_session, keys, archived_october, tmp_path, monkeypatch):
    """A linked row is never archived, so `--user-key` needs no archive token."""
    secret, _, _, linked = archived_october
    monkeypatch.delenv("USAGE_ARCHIVE_R2_BUCKET", raising=False)
    out = tmp_path / "opened.csv"

    opened = keys.open_rows(
        db_session,
        secret,
        month=OCTOBER,
        opened_by="Test Maintainer",
        reason="one hiker's rows",
        event_id=None,
        key="k" * 32,
        out=out,
    )

    assert opened == 1 and linked in out.read_text()
