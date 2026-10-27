"""Row locks that make a count-then-insert cap hold under concurrent requests.

Every per-account cap here is "count the rows, then insert one": lists per
account, weights changes per day, sites held at once. Two requests that count
at the same moment both pass. The adversarial review (2026-10-27, finding 8)
proved it: 12 parallel weights changes against a cap of 3 got more than 3
through in 6 runs of 7. Locking the caller's own row first makes their requests
take turns; nobody else's are slowed.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from steward_api.models import StewardUser


def lock_user(db: Session, user_id: str) -> None:
    """Hold the caller's row until this transaction ends."""
    db.execute(select(StewardUser.id).where(StewardUser.id == user_id).with_for_update())
