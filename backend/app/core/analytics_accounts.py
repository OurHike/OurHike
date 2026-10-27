"""Finding one account's usage rows, for the three things that need them (#1902).

Account deletion (app/core/account_deletion.py), the export
(app/core/account_export.py) and unlinking (app/routers/preferences.py) all
have to find the usage rows an account linked by saying yes. No row names the
account: each carries a `user_key`, the account id hashed under a secret
(app/core/analytics_seal.py), so the only way to find them is to recompute
that key - under every secret it could have been made with, because rotating
the secret leaves the old rows under the old one (app/config.py).

THE CASE THAT MUST NOT PASS QUIETLY

With no secret configured at all, no key can be recomputed. If no linked row
exists either, that is a deployment that never linked anything, and there is
nothing to find. But if linked rows exist - the secret was set once, and has
since been unset - then "found nothing" would be a lie: deleting an account
would report its usage gone while it stayed, still linked, in the table. That
case raises `LinkedUsageUnreachable`, and deletion refuses rather than
half-happen.
"""

from __future__ import annotations

from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.core.analytics_seal import user_key
from app.models.analytics import AnalyticsEvent, AnalyticsUser, SealState


class LinkedUsageUnreachable(RuntimeError):
    """Linked usage rows exist, and no secret is configured to find an account's among them."""


def account_user_keys(account_id: str) -> list[str]:
    """Every `user_key` this account's rows could be stored under: the current secret's first."""
    return list(dict.fromkeys(user_key(secret, account_id) for secret in settings.analytics_user_key_secrets))


def linked_usage_exists(db: Session) -> bool:
    """Whether any usage row is linked to any account at all."""
    return bool(
        db.scalar(select(exists().where(AnalyticsUser.user_key.isnot(None))))
        or db.scalar(select(exists().where(AnalyticsEvent.user_key.isnot(None))))
    )


def keys_or_refuse(db: Session, account_id: str) -> list[str]:
    """This account's possible keys, or `LinkedUsageUnreachable` when there are none and there should be.

    An empty list is an honest answer only when nothing is linked anywhere.
    """
    keys = account_user_keys(account_id)
    if not keys and linked_usage_exists(db):
        raise LinkedUsageUnreachable()
    return keys


def forget_link(db: Session, account_id: str) -> int:
    """Unlink this account's usage: its User-table rows go, and its events lose their key and their seal.

    The events stay, counted like any row a hiker sent without saying yes,
    each with its 0.1-degree square. The sealed blob goes too, because it
    holds the account id beside the exact fix and this server cannot open it
    to take the account out alone (app/core/analytics_seal.py). Leaving it
    would keep the account readable to the maintainer's `open` for up to
    seven months after the hiker said no - and out of reach of a later
    account deletion, which finds rows by their key. So the exact fix is
    lost with it, and the row says `unlinked` rather than `sealed`.
    Does not commit. Returns how many events were unlinked.
    """
    keys = keys_or_refuse(db, account_id)
    if not keys:
        return 0
    db.query(AnalyticsUser).filter(AnalyticsUser.user_key.in_(keys)).delete(synchronize_session=False)
    # The seal first: the next statement takes away the key this one finds the rows by.
    db.execute(
        update(AnalyticsEvent)
        .where(AnalyticsEvent.user_key.in_(keys), AnalyticsEvent.seal == SealState.sealed)
        .values(sealed=None, seal=SealState.unlinked)
        .execution_options(synchronize_session=False)
    )
    return db.execute(
        update(AnalyticsEvent)
        .where(AnalyticsEvent.user_key.in_(keys))
        .values(user_key=None)
        .execution_options(synchronize_session=False)
    ).rowcount
