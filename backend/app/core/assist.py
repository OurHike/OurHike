"""The one place this codebase calls a model, and the rules it calls under.

See ../../../features/ORG_ONBOARDING.md's "Assist panels" and #1540/#1541.

**THE MODEL IS READ FROM SETTINGS AND NEVER FROM A REQUEST.** That is the
whole abuse story in one sentence: a client that can name the model can name
the most expensive one, and the bill arrives at somebody who did not choose
it. `ask` takes no model argument, so there is no parameter for a caller to
reach even if a future router wanted to pass one through.

**THE BUDGET IS CHECKED BEFORE THE CALL AND RECORDED AFTER IT.** Checked
before, because a budget enforced afterwards is a bill already spent; and
recorded after with the token counts the API itself reported, because a
budget enforced against an estimate is wrong in whichever direction the
estimate is, and the expensive direction is the one estimates favour.

**THE BUDGET CAN BE OVERSHOT BY AT MOST ONE CALL, AND NOT TWICE.** A call's
cost is not knowable until it has been made, so the check is "have you
already passed the line" rather than "would this cross it". The alternative -
holding back a call that might cross it - would refuse a cheap question to an
organization with budget left, which is the worse of the two failures. The
ceiling on the overshoot is `MAX_OUTPUT_TOKENS` plus the question's own size.

**A DAY IS A ROLLING 24 HOURS, NOT A CALENDAR ONE.** A calendar day resets at
an hour somebody has to know, and gives anybody who finds the boundary two
budgets in two minutes. A rolling window has neither property and is one
`created_at >= now - 24h`.

**EVERY FAILURE IS A REFUSAL, NEVER A RETRY.** No backoff loop, no second
attempt on a timeout. A retry against a paid API is how one stuck request
becomes ten, and the panels are all a convenience over something an
organization can do by hand.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.core.time import utc_now
from app.models.assist import AssistUsage

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# How long one call may take before it is given up on. Short, because every
# panel is a convenience: an organization waiting thirty seconds for a
# suggestion has already been failed, and a long timeout on a paid call is a
# long time to hold a request open for a bill that is being spent anyway.
ASSIST_TIMEOUT_SECONDS = 25.0

# The ceiling on one answer. Every panel asks for a short structured reply,
# so this is a guard against a runaway generation rather than a limit anybody
# should hit - and it is what stops one call spending a day's budget.
MAX_OUTPUT_TOKENS = 1_500

BUDGET_WINDOW = timedelta(hours=24)


class AssistUnavailable(RuntimeError):
    """No key, or the deployment has not switched the panels on."""


class AssistBudgetSpent(RuntimeError):
    """This club, or this address, has spent its day."""


class AssistFailed(RuntimeError):
    """The call did not come back with an answer. Never retried."""


@dataclass(frozen=True)
class AssistAnswer:
    text: str
    input_tokens: int
    output_tokens: int


def client_fingerprint(address: str | None) -> str:
    """A caller's address as something to compare, never to read.

    Storing the address would build a log of who looked up which
    organization - a thing this project has no use for and would then have to
    protect. A missing address hashes like any other string rather than
    raising: a caller behind a proxy that strips it still gets counted, and
    counted together, which is the conservative direction.
    """
    return hashlib.sha256((address or "unknown").encode("utf-8")).hexdigest()


def spent_today(db: Session, *, club_id: str | None, client_hash: str | None) -> int:
    """Tokens this club or this address has spent in the last 24 hours."""
    since = utc_now() - BUDGET_WINDOW
    query = db.query(func.coalesce(func.sum(AssistUsage.input_tokens + AssistUsage.output_tokens), 0)).filter(
        AssistUsage.created_at >= since
    )
    if club_id is not None:
        query = query.filter(AssistUsage.club_id == club_id)
    else:
        query = query.filter(AssistUsage.client_hash == client_hash)
    return int(query.scalar() or 0)


def budget_for(club_id: str | None) -> int:
    """An organization's day, or the smaller public one.

    Two orders of magnitude apart on purpose: the public form is the only
    assist surface with no account behind it, so the number is the only thing
    between it and anybody on the internet.
    """
    return settings.assist_daily_token_budget if club_id is not None else settings.assist_public_daily_token_budget


def ask(
    db: Session,
    *,
    panel: str,
    system: str,
    prompt: str,
    club_id: str | None = None,
    client_address: str | None = None,
) -> AssistAnswer:
    """One question, one answer, one row of accounting.

    Raises rather than returning a sentinel, because every caller here has a
    different thing to say to the person on the other end: "not switched on"
    is a deployment note, "budget spent" is a fact about today, and "failed"
    is a shrug. Collapsing them into `None` would make all three read as the
    same shrug.
    """
    if not settings.assist_enabled or not settings.anthropic_api_key:
        raise AssistUnavailable("The assist panels are not switched on for this deployment.")

    client_hash = None if club_id is not None else client_fingerprint(client_address)
    already = spent_today(db, club_id=club_id, client_hash=client_hash)
    budget = budget_for(club_id)
    if already >= budget:
        raise AssistBudgetSpent(
            f"That is {already:,} of today's {budget:,} tokens. It resets 24 hours after each call, "
            "and everything these panels do can be done by hand in the meantime."
        )

    try:
        response = httpx.post(
            ANTHROPIC_URL,
            timeout=ASSIST_TIMEOUT_SECONDS,
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            json={
                # From settings, never from the caller. See the module header.
                "model": settings.assist_model,
                "max_tokens": MAX_OUTPUT_TOKENS,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
    except httpx.HTTPError as exc:
        # No retry. See the module header.
        raise AssistFailed("The assistant did not answer.") from exc

    if response.status_code >= 400:
        # The upstream body can carry a key fragment or an account detail, so
        # what reaches a caller is the status and nothing else.
        raise AssistFailed(f"The assistant refused the request ({response.status_code}).")

    try:
        body = response.json()
        blocks = body.get("content") or []
        text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        usage = body.get("usage") or {}
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
    except (ValueError, AttributeError, TypeError) as exc:
        raise AssistFailed("The assistant's answer could not be read.") from exc

    # Recorded whatever the answer looked like, including an empty one: the
    # tokens were spent either way, and a budget that only counted useful
    # answers would not be a budget.
    db.add(
        AssistUsage(
            club_id=club_id,
            client_hash=client_hash,
            panel=panel,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    )
    db.commit()

    if not text.strip():
        raise AssistFailed("The assistant answered with nothing.")

    return AssistAnswer(text=text, input_tokens=input_tokens, output_tokens=output_tokens)
