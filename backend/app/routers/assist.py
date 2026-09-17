"""`/assist` - the four panels the wireframes draw, behind one gate.

See ../../../features/ORG_ONBOARDING.md's "Assist panels". `app/core/assist.py`
holds the call and the budget; this holds who may ask what.

**FOUR PANELS, AND ONLY ONE OF THEM IS PUBLIC.** The registry, add-a-trail and
coverage panels sit inside the console and need a seat at the organization.
The nominate panel is on the marketing site, has no account behind it, and is
the one anybody on the internet can reach - so it carries the smaller budget,
a per-address count, and a shorter prompt.

**THE PANELS NEVER DECIDE ANYTHING.** Each returns prose for a person to read
and act on. Nothing here writes a section, creates a role or registers a
source, and that is deliberate rather than unfinished: a registry is what
reaches a hiker's phone, and a model's reading of a GIS layer is a suggestion
to check rather than a change to apply. Every screen that shows one of these
puts the org's own button beside it.

**WHAT IS SENT IS WHAT THE SCREEN ALREADY SHOWS.** The coverage panel gets the
gap list an admin is looking at; the registry panel gets the source they
typed. Nothing reaches the API that the person asking could not already read
on their own screen, which is the smallest version of "what did you send
about us" an organization can be given.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.assist import (
    AssistBudgetSpent,
    AssistFailed,
    AssistUnavailable,
    ask,
    budget_for,
    spent_today,
)
from app.core.org_access import OrgAccess, require_org_admin
from app.db.session import get_db
from app.schemas.assist import AssistAsk, AssistOut, AssistPanel, NominateAsk

router = APIRouter(tags=["assist"])

# One system prompt per panel, so what the model is asked to be is in the
# repository rather than in a request body a client could rewrite.
#
# Every one of them ends the same way, and the ending is the point: these
# panels talk to people deciding what goes on a map a hiker walks by, so a
# guess presented as a reading is the failure mode. "Say what you cannot
# tell" is cheaper here than anywhere else in the product.
_HONESTY = (
    " Say plainly when you cannot tell something from what you were given, and never invent a "
    "name, a mileage or a count. A short answer that says 'I cannot tell from this' is more use "
    "than a confident one that is wrong, because somebody will publish it to a map."
)

SYSTEM_PROMPTS: dict[AssistPanel, str] = {
    "registry": (
        "You help a trail organization turn their own GIS files into sections hikers can read. "
        "Keep their section names exactly as they wrote them. Report what you found, what you "
        "could not resolve, and how many lines need a person rather than you." + _HONESTY
    ),
    "addtrail": (
        "You help a trail organization add ONE new trail to a registry they already publish. "
        "Nothing already published is being changed. Report only what would be added: how many "
        "sections, how many miles, and which existing junctions it touches." + _HONESTY
    ),
    "coverage": (
        "You help a trail organization read its own coverage report - sections with no role "
        "attached. Point at patterns they can act on, and suggest who might take a gap only from "
        "what you were given." + _HONESTY
    ),
    "nominate": (
        "You read a trail organization's public website the way a person would, looking for a "
        "maps page, a GIS server, a downloads link or a data portal. Report what you can see and "
        "what you cannot." + _HONESTY
    ),
}


def _answer(
    db: Session,
    *,
    panel: AssistPanel,
    prompt: str,
    club_id: str | None,
    address: str | None,
) -> AssistOut:
    """The three failures, each with the sentence that belongs to it."""
    try:
        result = ask(
            db,
            panel=panel,
            system=SYSTEM_PROMPTS[panel],
            prompt=prompt,
            club_id=club_id,
            client_address=address,
        )
    except AssistUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AssistBudgetSpent as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except AssistFailed as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    budget = budget_for(club_id)
    return AssistOut(
        panel=panel,
        answer=result.text,
        tokens_used=result.input_tokens + result.output_tokens,
        tokens_left_today=max(0, budget - spent_today(db, club_id=club_id, client_hash=None)) if club_id is not None else None,
    )


@router.post("/clubs/{slug}/assist", response_model=AssistOut)
def assist_org(
    slug: str,
    payload: AssistAsk,
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> AssistOut:
    """One of the three console panels, for somebody with a seat here.

    Admin rather than `can_manage_volunteers`, because all three read the
    registry - the thing that reaches a hiker - and because the budget is the
    organization's to spend. A supervisor who could spend it would be a
    supervisor who could exhaust it before an admin got to the screen.

    The panel is an enum, so the system prompt comes from this file's own
    table rather than from the request. A caller who could supply the system
    prompt could make this a general-purpose model endpoint on somebody
    else's key.
    """
    if payload.panel == "nominate":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The nominate panel is the public one - it is at POST /assist/nominate",
        )
    return _answer(
        db,
        panel=payload.panel,
        prompt=payload.question,
        club_id=access.club.id,
        address=None,
    )


@router.post("/assist/nominate", response_model=AssistOut)
def assist_nominate(
    payload: NominateAsk,
    request: Request,
    db: Session = Depends(get_db),
) -> AssistOut:
    """The one panel with no account behind it.

    **THE ONLY THING BETWEEN THIS AND ANYBODY ON THE INTERNET IS THE PUBLIC
    BUDGET**, counted per address over a rolling day. That is a weaker control
    than an account and is said here rather than discovered: it is the reason
    the public budget is two orders of magnitude smaller than an
    organization's, and the reason this panel takes a website and nothing
    else rather than free text.

    The address is hashed before it is stored - see `client_fingerprint`. What
    this table needs is a counter, not a record of who looked up which
    organization.
    """
    address = request.client.host if request.client else None
    return _answer(
        db,
        panel="nominate",
        prompt=f"Their website is {payload.website}. What can you tell about their trail data?",
        club_id=None,
        address=address,
    )
