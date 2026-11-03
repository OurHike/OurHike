"""The one secret behind usage-event sealing, and the only way to open a sealed row (#1902).

Three commands, run by the maintainer on their own machine and never by CI:

    python scripts/analytics_keys.py new-secret
        Prints a fresh 32-byte secret once. It goes into your password
        manager and nowhere else - not a file, not a CI secret, not the
        backend's environment. Nothing in this repository stores it.

    DATABASE_URL=... python scripts/analytics_keys.py publish --from 2026-11 --months 24
        Asks for the secret at a hidden prompt, derives each month's key pair
        from it and the month's name, and writes only the PUBLIC half into
        `analytics_seal_keys`. Until a month has one, `POST /usage-events`
        seals nothing for that month - it throws the fix and the account id
        away and stores the row as `no_key`. So publish well ahead: the
        nightly checks raise `seal_keys_running_out` when fewer than three
        months are left (app/core/analytics_quality.py).

    DATABASE_URL=... python scripts/analytics_keys.py open \\
            --month 2026-10 --by "Your name" --reason "why, in a sentence" \\
            (--event-id ID | --user-key KEY | --whole-month) --out ~/opened.csv
        Asks for the secret at a hidden prompt, writes an `analytics_openings`
        row naming you, the month, what was asked for and why, COMMITS IT,
        and only then opens the rows and writes them to the CSV file you
        named - a new file, readable by you alone, outside this repository.
        It never prints a position or an account to the terminal, because a
        terminal's scrollback is a copy nobody remembers making.

THE SECRET IS ONLY EVER TYPED, OR PASTED, AT THE PROMPT. Not passed in a
variable on the command line, which shell history keeps - the copy of the
secret nobody remembers making, as scrollback is for the rows.

Opening needs a connection that can read `sealed`. The rollup's role cannot,
deliberately (features/EVENTING.md, the role's grants), so this runs with the
database owner's URL.

A CLOSED MONTH'S UNLINKED ROWS ARE IN R2 (#1923, app/core/analytics_archive.py),
not in Postgres, once the nightly archive has run. For `--event-id` and
`--whole-month` on such a month, `open` also reads the month's parts with your
own read token for the environment's archive bucket - the USAGE_ARCHIVE_R2_*
variables the nightly job is given - and needs pyarrow
(`pip install -r backend/requirements-archive.txt`). It checks both before it
records anything, and checks each part against the SHA-256 the archive
recorded before it opens a row of it. `--user-key` never reads the archive:
a linked row is never archived.

What the month in the key buys, and what it does not, is
app/core/analytics_seal.py's docstring: an opening for October derives
October's key and no other month's, but the secret can derive any of them
again, so this is not crypto-shredding. Retention rests on the rollup deleting
rows.
"""

from __future__ import annotations

import argparse
import base64
import csv
import getpass
import hashlib
import importlib.util
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.dialects.postgresql import insert  # noqa: E402

from app.core.analytics_archive import ArchiveError, R2Store  # noqa: E402
from app.core.analytics_rollup import add_months  # noqa: E402
from app.core.analytics_seal import (  # noqa: E402
    SealError,
    month_label,
    month_private_key,
    month_public_key,
    new_secret,
    open_sealed,
)
from app.core.time import utc_now  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.analytics import AnalyticsArchivePart, AnalyticsEvent, AnalyticsOpening, AnalyticsSealKey  # noqa: E402

# Opened rows are positions and accounts: never written inside this
# repository, where a commit would publish them for good (CONTRIBUTING.md,
# "Data does not go in commits") - scripts/usage_report.py's refusal, here.
REPOSITORY = Path(__file__).resolve().parents[2]


class KeysError(RuntimeError):
    """A refusal this script explains rather than a crash."""


def encode_secret(secret: bytes) -> str:
    return base64.urlsafe_b64encode(secret).decode("ascii")


def decode_secret(text: str) -> bytes:
    try:
        secret = base64.urlsafe_b64decode(text.strip().encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise KeysError("that is not a secret new-secret printed") from exc
    if len(secret) != 32:
        raise KeysError("that is not a secret new-secret printed (it decodes to the wrong length)")
    return secret


def _read_secret() -> bytes:
    """The secret, from a hidden prompt and nowhere else (the module docstring says why)."""
    return decode_secret(getpass.getpass("Analytics secret (input hidden): "))


def _refuse_out(out: Path) -> None:
    """Refuse, before anything is recorded, a place the opened rows must not go."""
    if out.resolve().is_relative_to(REPOSITORY):
        raise KeysError(f"{out} is inside the repository. Opened rows are positions and accounts; write them elsewhere.")
    if out.exists():
        raise KeysError(f"{out} already exists. Opened rows are never written over a file; name a new one.")


def _month(text: str) -> date:
    try:
        return date.fromisoformat(f"{text}-01")
    except ValueError as exc:
        raise argparse.ArgumentTypeError("a month is YYYY-MM") from exc


def publish(db, secret: bytes, first: date, months: int) -> list[date]:
    """Write the public key for each of `months` months from `first`.

    Refuses a month that already holds a DIFFERENT key: that means the secret
    changed, and overwriting would leave the month's earlier rows sealed to a
    key nothing publishes any more - still openable with the old secret, but
    silently orphaned. A month already holding this secret's key is left as
    it is, so publishing is safe to repeat.
    """
    written: list[date] = []
    existing = {row.month: bytes(row.public_key) for row in db.query(AnalyticsSealKey).all()}
    for offset in range(months):
        month = add_months(first, offset)
        public = month_public_key(secret, month_label(month))
        if month in existing:
            if existing[month] != public:
                raise KeysError(
                    f"{month:%Y-%m} already has a different public key. The secret is not the one that "
                    "published it; nothing was written."
                )
            continue
        db.execute(
            insert(AnalyticsSealKey.__table__)
            .values(month=month, public_key=public, published_at=utc_now())
            .on_conflict_do_nothing(index_elements=["month"])
        )
        written.append(month)
    db.commit()
    return written


def _archive_reader():
    """`read_parquet` from scripts/analytics_archive.py, which needs pyarrow - asked for only
    when a month has archived parts, so opening a month that has none needs nothing new."""
    try:
        import pyarrow  # noqa: F401
    except ImportError as exc:
        raise KeysError(
            "this month has rows in the usage archive, which needs pyarrow to read: "
            "pip install -r backend/requirements-archive.txt. Nothing was recorded."
        ) from exc
    spec = importlib.util.spec_from_file_location("analytics_archive_script", Path(__file__).with_name("analytics_archive.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.read_parquet


def _archived_rows(store: R2Store, parts: list[AnalyticsArchivePart], read_parquet) -> list[dict]:
    """Every row of the month's live parts, each part checked against the SHA-256 the archive recorded."""
    rows: list[dict] = []
    for part in parts:
        body = store.get(part.object_key)
        if hashlib.sha256(body).hexdigest() != part.sha256:
            raise KeysError(f"{part.object_key} is not the file the archive wrote. Nothing in it was opened.")
        rows.extend(read_parquet(body))
    return rows


def open_rows(
    db,
    secret: bytes,
    *,
    month: date,
    opened_by: str,
    reason: str,
    event_id: str | None,
    key: str | None,
    out: Path,
    store: R2Store | None = None,
) -> int:
    """Record the opening, commit the record, then open and write the rows.

    The file is created new, readable and writable by its owner alone
    (`O_EXCL`, mode 0600), so an opening can neither replace a file nor be
    read by another account on the machine. A file that appears between the
    check below and the write is refused there too, after the record - which
    is the record doing its job.

    A month with archived parts is read from Postgres and from R2 together
    (#1923). `store` is the archive bucket, made from the environment when
    not given; what an opening needs to read it is checked before the record.
    """
    if not reason.strip() or not opened_by.strip():
        raise KeysError("an opening needs a name and a reason; that is the whole of the record")
    _refuse_out(out)
    selector = f"event {event_id}" if event_id else f"user_key {key}" if key else "whole month"

    parts: list[AnalyticsArchivePart] = []
    read_parquet = None
    if not key:
        parts = (
            db.query(AnalyticsArchivePart)
            .filter(AnalyticsArchivePart.month == month, AnalyticsArchivePart.deleted_at.is_(None))
            .order_by(AnalyticsArchivePart.part)
            .all()
        )
    if parts:
        read_parquet = _archive_reader()
        if store is None:
            try:
                store = R2Store.from_env()
            except ArchiveError as exc:
                raise KeysError(
                    f"{month:%Y-%m} has rows in the usage archive, and {exc}. Set them to a token that may read "
                    "the archive bucket. Nothing was recorded."
                ) from exc

    opening = AnalyticsOpening(opened_by=opened_by.strip(), reason=reason.strip(), month=month, selector=selector)
    db.add(opening)
    db.commit()

    query = db.query(AnalyticsEvent).filter(
        AnalyticsEvent.local_date >= month,
        AnalyticsEvent.local_date < add_months(month, 1),
        AnalyticsEvent.sealed.isnot(None),
    )
    if event_id:
        query = query.filter(AnalyticsEvent.id == event_id)
    if key:
        query = query.filter(AnalyticsEvent.user_key == key)
    rows = [
        {
            "id": event.id,
            "local_date": event.local_date,
            "event": event.event,
            "user_key": event.user_key,
            "sealed": event.sealed,
        }
        for event in query.all()
    ]
    if parts:
        rows += [
            row
            for row in _archived_rows(store, parts, read_parquet)
            if row["sealed"] is not None and (not event_id or row["id"] == event_id)
        ]

    label = month_label(month)
    private = month_private_key(secret, label)
    opened = 0
    descriptor = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "local_date", "event", "user_key", "account", "lat", "lon", "accuracy_m"])
        for row in sorted(rows, key=lambda row: (row["local_date"], row["id"])):
            try:
                payload = open_sealed(private, label, row["id"], bytes(row["sealed"]))
            except SealError:
                writer.writerow([row["id"], row["local_date"].isoformat(), row["event"], row["user_key"], "", "", "", ""])
                continue
            writer.writerow(
                [
                    row["id"],
                    row["local_date"].isoformat(),
                    row["event"],
                    row["user_key"] or "",
                    payload.get("account", ""),
                    payload.get("lat", ""),
                    payload.get("lon", ""),
                    payload.get("accuracy_m", ""),
                ]
            )
            opened += 1

    opening.rows_opened = opened
    db.commit()
    return opened


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("new-secret", help="Print a fresh secret, once, for your password manager.")

    publish_parser = commands.add_parser("publish", help="Write the public keys for a run of months.")
    publish_parser.add_argument("--from", dest="first", type=_month, required=True, help="First month, YYYY-MM.")
    publish_parser.add_argument("--months", type=int, default=24, help="How many months (default 24).")

    open_parser = commands.add_parser("open", help="Record an opening, then open sealed rows into a CSV.")
    open_parser.add_argument("--month", type=_month, required=True, help="The month to open, YYYY-MM.")
    open_parser.add_argument("--by", required=True, help="Who is opening, by name.")
    open_parser.add_argument("--reason", required=True, help="Why, in a sentence. Stored as written.")
    which = open_parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--event-id")
    which.add_argument("--user-key")
    which.add_argument("--whole-month", action="store_true")
    open_parser.add_argument(
        "--out", type=Path, required=True, help="A new CSV file to write, outside this repository. Never stdout."
    )

    args = parser.parse_args(argv)

    try:
        if args.command == "new-secret":
            print(encode_secret(new_secret()))
            print(
                "Put this in your password manager now. It is printed once, stored nowhere, and "
                "asked for again at a hidden prompt by `publish` and `open`.",
                file=sys.stderr,
            )
            return 0

        secret = _read_secret()
        with SessionLocal() as db:
            if args.command == "publish":
                written = publish(db, secret, args.first, args.months)
                print(f"Published {len(written)} month(s): " + (", ".join(f"{m:%Y-%m}" for m in written) or "none new"))
                return 0
            opened = open_rows(
                db,
                secret,
                month=args.month,
                opened_by=args.by,
                reason=args.reason,
                event_id=args.event_id,
                key=args.user_key,
                out=args.out,
            )
            print(f"Opened {opened} row(s) into {args.out}. The opening is recorded in analytics_openings.")
            return 0
    except KeysError as refusal:
        print(f"Refused: {refusal}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
