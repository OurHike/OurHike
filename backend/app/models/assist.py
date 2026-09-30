"""What the assist panels have spent, so a budget is a fact rather than a hope.

See ../../../features/ORG_ONBOARDING.md's "Assist panels", and
`app/routers/assist.py` for the endpoint that writes these rows.

**A ROW PER CALL, WITH THE TOKENS THE API ACTUALLY REPORTED.** Not an
estimate, not a character count divided by four: the `usage` block Anthropic
returns. A budget enforced against a guess is a budget that is wrong in one
direction or the other, and the direction it is usually wrong in is the
expensive one.

**THE PUBLIC SURFACE IS COUNTED BY A HASH OF THE CALLER'S ADDRESS.** The
nominate form has no account behind it, so per-IP is the only handle there
is - and storing the address itself would build a log of who looked at which
organization, which is a thing this project has no use for and would then
have to protect. `client_hash` is a SHA-256 and is never reversed; it exists
to be compared, not read.

**NOTHING HERE STORES THE PROMPT OR THE ANSWER.** An organization's GIS
layout, their section names and whatever an admin typed into the box are
theirs. What this table needs to do its job is a club, a day and a number,
and it holds exactly those - so the accounting cannot quietly become a
transcript.
"""

import uuid

from sqlalchemy import Column, DateTime, Integer, String

from app.core.time import utc_now
from app.db.base import Base


class AssistUsage(Base):
    """One assist call's cost, for the budget check and for nothing else."""

    __tablename__ = "assist_usage"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # Null for the public nominate form, which has no organization yet - that
    # is the case it exists to serve.
    club_id = Column(String, nullable=True, index=True)
    # SHA-256 of the caller's address, for the public surface only. Null for
    # an authenticated call, where the club is the handle.
    client_hash = Column(String, nullable=True, index=True)
    # Which panel spent it, so the first ten real reads can answer what a
    # registry read actually costs.
    panel = Column(String, nullable=False)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
