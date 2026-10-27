"""The one secret behind usage-event sealing, and the only way to open a sealed row (#1902).

Three commands, run by the maintainer on their own machine and never by CI:

    python scripts/analytics_keys.py new-secret
        Prints a fresh 32-byte secret once. It goes into your password
        manager and nowhere else - not a file, not a CI secret, not the
        backend's environment. Nothing in this repository stores it.

    OURHIKE_ANALYTICS_SECRET=... DATABASE_URL=... python scripts/analytics_keys.py publish --from 2026-11 --months 24
        Derives each month's key pair from the secret and the month's name, and
        writes only the PUBLIC half into `analytics_seal_keys`. Until a month
        has one, `POST /usage-events` seals nothing for that month - it throws
        the fix and the account id away and stores the row as `no_key`. So
        publish well ahead, and the report's data-health line says when the
        published months are running out.

    OURHIKE_ANALYTICS_SECRET=... DATABASE_URL=... python scripts/analytics_keys.py open \\
            --month 2026-10 --by "Your name" --reason "why, in a sentence" \\
            (--event-id ID | --user-key KEY | --whole-month) --out opened.csv
        Writes an `analytics_openings` row naming you, the month, what was
        asked for and why, COMMITS IT, and only then opens the rows and
        writes them to the CSV file you named. It never prints a position or an
        account to the terminal, because a terminal's scrollback is a copy
        nobody remembers making.

Opening needs a connection that can read `sealed`. The rollup's role cannot,
deliberately (features/EVENTING.md, the role's grants), so this runs with the
database owner's URL.

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
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.dialects.postgresql import insert  # noqa: E402

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
from app.models.analytics import AnalyticsEvent, AnalyticsOpening, AnalyticsSealKey  # noqa: E402

SECRET_VARIABLE = "OURHIKE_ANALYTICS_SECRET"


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
    text = os.environ.get(SECRET_VARIABLE) or getpass.getpass("Analytics secret (input hidden): ")
    return decode_secret(text)


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
) -> int:
    """Record the opening, commit the record, then open and write the rows."""
    if not reason.strip() or not opened_by.strip():
        raise KeysError("an opening needs a name and a reason; that is the whole of the record")
    selector = f"event {event_id}" if event_id else f"user_key {key}" if key else "whole month"

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

    label = month_label(month)
    private = month_private_key(secret, label)
    opened = 0
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "local_date", "event", "user_key", "account", "lat", "lon", "accuracy_m"])
        for event in query.order_by(AnalyticsEvent.local_date, AnalyticsEvent.id).all():
            try:
                payload = open_sealed(private, label, event.id, bytes(event.sealed))
            except SealError:
                writer.writerow([event.id, event.local_date.isoformat(), event.event, event.user_key, "", "", "", ""])
                continue
            writer.writerow(
                [
                    event.id,
                    event.local_date.isoformat(),
                    event.event,
                    event.user_key or "",
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
    open_parser.add_argument("--out", type=Path, required=True, help="The CSV file to write. Never stdout.")

    args = parser.parse_args(argv)

    try:
        if args.command == "new-secret":
            print(encode_secret(new_secret()))
            print(
                "Put this in your password manager now. It is printed once, stored nowhere, and "
                f"read back from {SECRET_VARIABLE} or a hidden prompt by `publish` and `open`.",
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
