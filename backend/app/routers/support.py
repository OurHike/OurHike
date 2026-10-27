"""`/support` endpoints - a hiker's paid choice, Stop, the webhooks, the total.

See app/core/support.py for the mechanism, app/core/support_providers/ for
everything provider-shaped, and features/SUPPORTING_OURHIKE.md for the
decisions (#1876). Nothing here gates anything: no other endpoint reads these
tables, and none ever should (OurHikeValues.md #5).
"""

import json
import logging
from datetime import datetime, timedelta
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import Session

from app.core.auth import get_current_email, get_current_user
from app.core.mail import ses_client, suppress
from app.core.support import (
    BLOCKS_CHOICE,
    STOPPABLE,
    apply_delivery,
    mark_stop,
    notify_stop,
    record_failed_delivery,
    retry_stop_requests,
    settle_lapsed,
    summary_row,
    year_total,
)
from app.core.support_mail import manage_url, send_setup_link
from app.core.support_providers import current_provider, provider_for
from app.core.time import utc_now
from app.db.session import get_db
from app.models.mail import SuppressionReason
from app.models.profile import Profile
from app.models.support import SUPPORT_TERMS_VERSION, SupportCadence, SupportChoice, SupportStatus
from app.schemas.support import (
    SupportChoiceIn,
    SupportChoiceReceipt,
    SupportOut,
    SupportTotalOut,
    WebhookAck,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/support", tags=["support"])


def _rows(db: Session, profile_id: str) -> list[SupportChoice]:
    return db.query(SupportChoice).filter(SupportChoice.profile_id == profile_id).all()


def _blocked(rows: list[SupportChoice]) -> bool:
    current = current_provider()
    return current is not None and any(row.provider == current.key and row.status in BLOCKS_CHOICE for row in rows)


def _summary(db: Session, profile_id: str) -> SupportOut:
    return SupportOut.from_row(summary_row(db, profile_id), blocked=_blocked(_rows(db, profile_id)))


@router.get("/me", response_model=SupportOut)
def get_my_support(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SupportOut:
    """The caller's support, or `status: "none"`.

    200 with `none` rather than 404, unlike `/preferences/me`: "no paid
    choice" is an answer the app acts on (it may ask), not a missing thing.

    Two writes ride on this read, both idempotent: a scheduled cancellation
    whose end has passed becomes `stopped`, and a Stop whose request never
    reached anybody is asked again (at most every `RETRY_EVERY`). Nothing is
    claimed by email - a payment reaches an account only by the choice id it
    was made from (core/support.py).
    """
    settle_lapsed(db, current_user.id)
    retry_stop_requests(db, mail_provider=ses_client(), profile_id=current_user.id)
    db.commit()
    return _summary(db, current_user.id)


@router.put("/me", response_model=SupportChoiceReceipt)
def choose_support(
    choice: SupportChoiceIn,
    current_user: Profile = Depends(get_current_user),
    email: str | None = Depends(get_current_email),
    db: Session = Depends(get_db),
) -> SupportChoiceReceipt:
    """Record a paid choice as `pending`, and say how to complete it.

    A pending choice is updated in place (a hiker who picked $60 and comes
    back for $120 has one choice, not two). A payment still charging on the
    current provider is refused with 409: its amount is changed on the
    provider's side, or by Stop and a new choice. One on ANOTHER provider is
    not refused - that is a supporter moving, and the new choice names the
    old one so it is asked to stop once the new one starts.
    """
    provider = current_provider()
    if provider is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Support is not switched on here yet.")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Your sign-in carries no email address, so a payment could never be matched to it.",
        )

    now = utc_now()
    rows = _rows(db, current_user.id)
    if _blocked(rows):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already give OurHike something. Stop it first to choose a different amount.",
        )
    pending = [row for row in rows if row.provider == provider.key and row.status == SupportStatus.pending]
    row = max(pending, key=lambda r: r.chosen_at or datetime.min) if pending else None
    if row is None:
        row = SupportChoice(profile_id=current_user.id, provider=provider.key)
        db.add(row)
    moving_from = [r for r in rows if r.provider != provider.key and r.status in BLOCKS_CHOICE]
    row.replaces_choice_id = max(moving_from, key=lambda r: r.started_at or datetime.min).id if moving_from else None

    row.email = email
    row.amount_cents = choice.amount_cents
    row.chosen_amount_cents = choice.amount_cents
    row.currency = "USD"
    row.cadence = SupportCadence.year
    row.status = SupportStatus.pending
    row.accounting_email = choice.accounting_email
    row.accounting_email_at = now if choice.accounting_email else None
    # The screen states the one move email as a term of the choice rather
    # than a box to tick; pressing on is when the hiker was told, in the
    # words `terms_version` names.
    row.migrate_notice_at = now
    row.terms_version = SUPPORT_TERMS_VERSION
    row.delivery = choice.delivery
    row.chosen_at = now
    db.flush()

    checkout = provider.checkout_url(row)
    if checkout is not None and not checkout.startswith("https://"):
        checkout = None
    if choice.delivery == "redirect" and checkout is None:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Support is not switched on here yet.")

    emailed = False
    if choice.delivery == "email":
        emailed = send_setup_link(
            db,
            row,
            checkout_url=checkout,
            provider_label=provider.label,
            mail_provider=ses_client(),
            now=now,
        )

    db.commit()
    return SupportChoiceReceipt(
        support=_summary(db, current_user.id),
        checkout_url=checkout if choice.delivery == "redirect" else None,
        emailed=emailed,
    )


@router.post("/me/stop", response_model=SupportOut)
def stop_support(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SupportOut:
    """Stop everything the caller gives. One call, no reason asked.

    A pending choice has nothing to cancel and is `stopped` at once. A payment
    still charging becomes `stop_requested`, which is committed BEFORE
    whoever cancels it is asked - Stripe's API, or an email to the founder
    when that cannot be reached - so a provider's confirmation arriving
    during that call finds the Stop already recorded (the third #1885
    review). A second press re-asks only where the first did not reach
    anybody, at most every `RETRY_EVERY`. Nothing running and nothing waiting
    is 404.
    """
    rows = _rows(db, current_user.id)
    if not any(row.status in STOPPABLE or row.status == SupportStatus.stop_requested for row in rows):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nothing is running to stop.")

    now = utc_now()
    ask = [row for row in rows if row.status in STOPPABLE and mark_stop(row, now=now)]
    db.commit()

    mail_provider = ses_client()
    for row in ask:
        notify_stop(db, row, mail_provider=mail_provider, now=now)
    retry_stop_requests(db, mail_provider=mail_provider, profile_id=current_user.id, now=now)
    db.commit()
    return _summary(db, current_user.id)


# The total is a public, unauthenticated read over every support row, so it
# is computed at most this often per process rather than on every request.
TOTAL_CACHE_FOR = timedelta(hours=1)
_total_cache: dict[int, tuple[datetime, SupportTotalOut]] = {}


def clear_total_cache() -> None:
    _total_cache.clear()


@router.get("/total", response_model=SupportTotalOut)
def support_total(response: Response, db: Session = Depends(get_db)) -> SupportTotalOut:
    """This year's running total and supporter count, public, before fees.

    Counts and a sum only - no names, no amounts per person. A year with one
    supporter does say what that one person gives, which is the cost of
    publishing a total at all; it is the founder's commitment that the total
    is public (poll, 2026-10-23). Up to `TOTAL_CACHE_FOR` old.
    """
    now = utc_now()
    cached = _total_cache.get(now.year)
    if cached is None or now - cached[0] >= TOTAL_CACHE_FOR:
        cents, supporters = year_total(db, now.year)
        cached = (now, SupportTotalOut(year=now.year, total_cents=cents, supporters=supporters))
        _total_cache[now.year] = cached
    response.headers["Cache-Control"] = f"public, max-age={int(TOTAL_CACHE_FOR.total_seconds())}"
    return cached[1]


async def _raw_body(request: Request) -> bytes:
    """The body exactly as it arrived, which is what a signature covers."""
    return await request.body()


@router.post("/webhooks/{provider_key}", response_model=WebhookAck)
def provider_webhook(
    provider_key: str,
    request: Request,
    raw: bytes = Depends(_raw_body),
    db: Session = Depends(get_db),
) -> WebhookAck:
    """One provider's signed delivery. See core/support.py.

    404 for a provider this server does not know, 503 with that provider not
    configured, 401 on a bad signature, 400 on a body that is not a JSON
    object, 503 when the database itself is unreachable (so the provider
    retries - Stripe does for three days), and 200 with a word for everything
    else - including events this server ignores, and an event whose handling
    raised, which is kept as `failed` to replay rather than refused into the
    provider's retry loop.

    A plain `def`, so FastAPI runs it in a worker thread: the database calls
    and the mail below would otherwise block every other request on the loop.
    """
    provider = provider_for(provider_key)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such provider.")
    if not provider.webhook_configured():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Webhook not configured.")
    if not provider.verify(request.headers, raw):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad signature.")
    try:
        envelope = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Body is not JSON.") from None
    if not isinstance(envelope, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Body is not a JSON object.")

    mail_provider = ses_client()
    try:
        try:
            result = apply_delivery(db, provider, envelope, mail_provider=mail_provider)
            db.commit()
        except (OperationalError, InterfaceError):
            raise
        except Exception as exc:  # kept to replay; see the docstring
            db.rollback()
            log.error("support: a %s delivery failed and was kept to replay: %s", provider.key, type(exc).__name__)
            record_failed_delivery(db, provider, envelope, exc)
            db.commit()
            return WebhookAck(result="failed")
    except (OperationalError, InterfaceError) as exc:
        # Nothing was recorded, so acknowledging would lose the event.
        db.rollback()
        log.error("support: database unreachable for a %s delivery: %s", provider.key, type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Try again.") from None

    try:
        # Committed whether or not any went: a failed try still records when
        # it was made, which is what spaces the next one out.
        retry_stop_requests(db, mail_provider=mail_provider)
        db.commit()
    except Exception as exc:  # best effort; the delivery itself is recorded
        db.rollback()
        log.warning("support: retrying stop requests failed: %s", type(exc).__name__)
    return WebhookAck(result=result)


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OurHike email</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:32rem;margin:3rem auto;padding:0 1rem}}
button{{font:inherit;padding:.6rem 1.2rem}}</style></head>
<body>{body}</body></html>"""


def _choice_for_token(db: Session, token: str) -> SupportChoice:
    row = None
    if 0 < len(token) <= 64:
        row = db.query(SupportChoice).filter(SupportChoice.link_token == token).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This link is not one of ours.")
    return row


@router.get("/mail/stop/{token}", response_class=HTMLResponse)
def unsubscribe_page(token: str, db: Session = Depends(get_db)) -> HTMLResponse:
    """A button, not an action: mail scanners follow GET links, and a GET
    that unsubscribed would unsubscribe whoever's inbox a scanner sits in."""
    _choice_for_token(db, token)
    return HTMLResponse(
        _PAGE.format(
            body="<h1>Stop OurHike's emails about your support?</h1>"
            "<p>This stops every email OurHike sends to this address. It does not stop a payment - "
            f'that is <a href="{escape(manage_url())}">More → Your support → Stop</a> in the app.</p>'
            '<form method="post"><button type="submit">Stop the emails</button></form>'
        )
    )


@router.post("/mail/stop/{token}", response_class=HTMLResponse)
def unsubscribe(token: str, db: Session = Depends(get_db)) -> HTMLResponse:
    """RFC 8058's one-click unsubscribe, and the page's button. Writes the
    address to app/core/mail.py's one suppression list, which nothing this
    project sends steps around."""
    row = _choice_for_token(db, token)
    suppress(db, row.email, SuppressionReason.unsubscribed, note="support email link")
    db.commit()
    return HTMLResponse(_PAGE.format(body="<h1>Done.</h1><p>OurHike won't email this address again.</p>"))
