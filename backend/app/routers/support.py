"""`/support` endpoints - a hiker's paid choice, Stop, the webhook, the total.

See app/core/support.py for the mechanism and features/SUPPORTING_OURHIKE.md
for the decisions (#1876). Nothing here gates anything: no other endpoint
reads this table, and none ever should (OurHikeValues.md #5).
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth import get_current_email, get_current_user
from app.core.mail import ses_client
from app.core.support import PROVIDER, apply_event, notify_stop, send_setup_link, signature_ok, year_total
from app.core.time import utc_now
from app.db.session import get_db
from app.models.profile import Profile
from app.models.support import SupportCadence, SupportChoice, SupportStatus
from app.schemas.support import (
    SupportChoiceIn,
    SupportChoiceReceipt,
    SupportOut,
    SupportTotalOut,
    WebhookAck,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/support", tags=["support"])


def _latest(db: Session, profile_id: str) -> SupportChoice | None:
    return (
        db.query(SupportChoice)
        .filter(SupportChoice.profile_id == profile_id)
        .order_by(SupportChoice.chosen_at.desc().nullslast(), SupportChoice.updated_at.desc())
        .first()
    )


@router.get("/me", response_model=SupportOut)
def get_my_support(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SupportOut:
    """The caller's latest paid choice, or `status: "none"`.

    200 with `none` rather than 404, unlike `/preferences/me`: "no paid
    choice" is an answer the app acts on (it may ask), not a missing thing.
    """
    return SupportOut.from_row(_latest(db, current_user.id))


@router.put("/me", response_model=SupportChoiceReceipt)
def choose_support(
    choice: SupportChoiceIn,
    current_user: Profile = Depends(get_current_user),
    email: str | None = Depends(get_current_email),
    db: Session = Depends(get_db),
) -> SupportChoiceReceipt:
    """Record a paid choice as `pending`, and say how to complete it.

    A pending choice is updated in place (a hiker who picked $10 and comes
    back for $100 has one choice, not two). An active one is refused with
    409: the amount of a running membership is changed on the provider's
    side, and Stop then a new choice is the way through this API.
    """
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Your sign-in carries no email address, so a payment could never be matched to it.",
        )
    if choice.delivery == "redirect" and not settings.buymeacoffee_checkout_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Support is not switched on here yet.",
        )

    now = utc_now()
    row = _latest(db, current_user.id)
    if row is not None and row.status in (SupportStatus.active, SupportStatus.stop_requested):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already give OurHike something. Stop it first to choose a different amount.",
        )
    if row is None or row.status == SupportStatus.stopped:
        row = SupportChoice(profile_id=current_user.id, provider=PROVIDER)
        db.add(row)

    row.email = email
    row.amount_cents = choice.amount_cents
    row.currency = "USD"
    row.cadence = SupportCadence.year
    row.status = SupportStatus.pending
    row.accounting_email = choice.accounting_email
    # The screen states the one move email as a term of the choice rather
    # than a box to tick; pressing on is when the hiker was told.
    row.migrate_notice_at = now
    row.chosen_at = now
    db.flush()

    emailed = False
    if choice.delivery == "email":
        emailed = send_setup_link(db, row, ses_client())

    db.commit()
    db.refresh(row)
    return SupportChoiceReceipt(
        support=SupportOut.from_row(row),
        checkout_url=settings.buymeacoffee_checkout_url if choice.delivery == "redirect" else None,
        emailed=emailed,
    )


@router.post("/me/stop", response_model=SupportOut)
def stop_support(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SupportOut:
    """Ask for the recurring payment to stop. One call, no reason asked.

    Marks the choice `stop_requested` and emails the founder to cancel it on
    Buy Me a Coffee by hand. Idempotent: a second press answers the same
    record without a second email. A choice with nothing running is 404.
    """
    row = _latest(db, current_user.id)
    if row is None or row.status == SupportStatus.stopped:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nothing is running to stop.")
    if row.status == SupportStatus.stop_requested:
        return SupportOut.from_row(row)

    row.status = SupportStatus.stop_requested
    row.stop_requested_at = utc_now()
    db.flush()
    if not notify_stop(db, row, ses_client()):
        # Recorded either way - the record is the promise, and it is on the
        # hiker's screen. The log line is what a maintainer reading the host's
        # logs finds when the notice could not go.
        log.warning("support: stop %s recorded but nobody was emailed to cancel it", row.id)
    db.commit()
    db.refresh(row)
    return SupportOut.from_row(row)


@router.get("/total", response_model=SupportTotalOut)
def support_total(db: Session = Depends(get_db)) -> SupportTotalOut:
    """This year's running total and supporter count, public, before fees.

    Counts and a sum only - no names, no amounts per person. A year with one
    supporter does say what that one person gives, which is the cost of
    publishing a total at all; it is the founder's commitment that the total
    is public (poll, 2026-10-23).
    """
    year = utc_now().year
    cents, supporters = year_total(db, year)
    return SupportTotalOut(year=year, total_cents=cents, supporters=supporters)


@router.post("/webhooks/buymeacoffee", response_model=WebhookAck)
async def buymeacoffee_webhook(request: Request, db: Session = Depends(get_db)) -> WebhookAck:
    """Buy Me a Coffee's signed delivery. See core/support.py.

    503 with no secret configured, 401 on a bad signature, 400 on a body that
    is not a JSON object, and 200 with a word for everything else - including
    events this server ignores, so Buy Me a Coffee does not retry them.
    """
    secret = settings.buymeacoffee_webhook_secret
    if not secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Webhook not configured.")
    raw = await request.body()
    if not signature_ok(raw, request.headers.get("x-signature-sha256"), secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad signature.")
    try:
        envelope = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Body is not JSON.") from None
    if not isinstance(envelope, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Body is not a JSON object.")

    result = apply_event(db, envelope)
    db.commit()
    return WebhookAck(result=result)
