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
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import Session

from app.core.auth import get_current_email, get_current_user
from app.core.mail import lift_unsubscribe, ses_client, suppress, suppression_reason
from app.core.support import (
    BLOCKS_CHOICE,
    STOPPABLE,
    apply_delivery,
    mark_stop,
    notify_stop,
    purge_expired,
    record_failed_delivery,
    retry_stop_requests,
    settle_lapsed,
    summary_row,
    year_total,
)
from app.core.support_mail import manage_url, send_setup_link, set_support_mail, support_mail_on
from app.core.support_providers import current_provider, provider_for
from app.core.time import utc_now
from app.db.session import get_db
from app.models.mail import SuppressionReason
from app.models.profile import Profile
from app.models.support import SUPPORT_TERMS_VERSION, SupportCadence, SupportChoice, SupportStatus
from app.schemas.support import (
    SupportChoiceIn,
    SupportChoiceReceipt,
    SupportMailIn,
    SupportOut,
    SupportTotalOut,
    WebhookAck,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/support", tags=["support"])


def _rows(db: Session, profile_id: str, *, lock: bool = False) -> list[SupportChoice]:
    """The caller's rows. `lock` holds them until the commit, so a Stop, a
    new choice or a deletion cannot read a choice as unpaid while a payment
    confirmation is committing it as paid, then write its stale reading over
    it - the fourth #1885 review measured a Stop leaving a $60 subscription
    charging under a row that said "stopped"."""
    query = db.query(SupportChoice).filter(SupportChoice.profile_id == profile_id)
    if lock:
        query = query.order_by(SupportChoice.id).with_for_update().populate_existing()
    return query.all()


def _blocked(rows: list[SupportChoice]) -> bool:
    current = current_provider()
    return current is not None and any(row.provider == current.key and row.status in BLOCKS_CHOICE for row in rows)


def _summary(db: Session, profile_id: str) -> SupportOut:
    row = summary_row(db, profile_id)
    rows = _rows(db, profile_id)
    return SupportOut.from_row(
        row,
        blocked=_blocked(rows),
        stoppable=any(r.status in STOPPABLE for r in rows),
        support_emails=support_mail_on(db, row.email if row is not None else None),
    )


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
    rows = _rows(db, current_user.id, lock=True)
    if _blocked(rows):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already give OurHike something. Stop it first to choose a different amount.",
        )
    pending = [row for row in rows if row.provider == provider.key and row.status == SupportStatus.pending]
    row = max(pending, key=lambda r: r.chosen_at or datetime.min) if pending else None
    if row is None:
        # A choice stopped before anything was paid is taken up again rather
        # than a new row made: choose-and-Stop in a loop added a row each
        # time, for good (the fourth #1885 review). Its id stays recognisable
        # to a link still waiting to be paid.
        unpaid = [
            r
            for r in rows
            if r.provider == provider.key
            and r.status == SupportStatus.stopped
            and r.provider_ref is None
            and r.started_at is None
            and r.duplicate_of is None
        ]
        row = max(unpaid, key=lambda r: r.chosen_at or datetime.min) if unpaid else None
        if row is not None:
            row.stop_requested_at = row.stop_notified_at = row.stop_attempted_at = None
            row.stop_confirmed_at = row.ended_at = None
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
    row.uncounted = not choice.usage_counts
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


@router.put("/me/mail", response_model=SupportOut)
def set_my_support_mail(
    choice: SupportMailIn,
    current_user: Profile = Depends(get_current_user),
    email: str | None = Depends(get_current_email),
    db: Session = Depends(get_db),
) -> SupportOut:
    """The app's "Emails about my support" switch, for the verified address
    on the caller's token and every address their support rows are under -
    the one the emails actually go to, which an earlier sign-in address may
    still be (the fourth #1885 review: the switch read back off and stopped
    nothing)."""
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Your sign-in carries no email address.",
        )
    addresses = {email, *(row.email for row in _rows(db, current_user.id) if row.email)}
    for address in sorted(addresses):
        set_support_mail(db, address, choice.support_emails)
    db.commit()
    return _summary(db, current_user.id)


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
    rows = _rows(db, current_user.id, lock=True)
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
        cached = (
            now,
            SupportTotalOut(
                year=now.year,
                total_cents=max(0, cents),
                supporters=supporters,
                accepting=current_provider() is not None,
            ),
        )
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
        # Nothing here runs on a schedule, so the seven-year purge rides on
        # deliveries too, a few rows at a time.
        purge_expired(db)
        db.commit()
    except Exception as exc:  # best effort; the delivery itself is recorded
        db.rollback()
        log.warning("support: retrying stop requests failed: %s", type(exc).__name__)
    return WebhookAck(result=result)


_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>OurHike email</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:32rem;margin:3rem auto;padding:0 1rem;color:#1d2a22}}
button{{font:inherit;padding:.6rem 1.2rem}}
.switch{{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.9rem 0;border-top:1px solid #d9d2c3}}
.switch small{{display:block;color:#5b6b60}}
.switch input{{appearance:none;flex:none;width:3rem;height:1.75rem;border-radius:1rem;background:#c9c2b4;position:relative;cursor:pointer}}
.switch input::after{{content:"";position:absolute;top:.2rem;left:.2rem;width:1.35rem;height:1.35rem;border-radius:50%;background:#fff;transition:left .15s}}
.switch input:checked{{background:#2f5a3a}} .switch input:checked::after{{left:1.45rem}}
.switch input:disabled{{opacity:.5;cursor:not-allowed}}
.switch input:focus-visible{{outline:3px solid #b5651d;outline-offset:2px}}</style></head>
<body>{body}</body></html>"""


def _choice_for_token(db: Session, token: str) -> SupportChoice:
    row = None
    if 0 < len(token) <= 64:
        row = db.query(SupportChoice).filter(SupportChoice.link_token == token).first()
    if row is None or not row.email:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This link is not one of ours.")
    return row


def _switches_page(db: Session, row: SupportChoice, *, saved: bool = False) -> HTMLResponse:
    """The two switches, set to what is true now (the maintainer's choice,
    poll 2026-10-27: switches the hiker controls, not buttons)."""
    support_on = support_mail_on(db, row.email)
    reason = suppression_reason(db, row.email)
    everything_on = reason is None
    # Only the hiker's own unsubscribe can be undone here; a bounce or a
    # refusal is not theirs to switch back.
    locked = reason is not None and reason != SuppressionReason.unsubscribed
    note = (
        "<p><small>This address can't get OurHike email right now: mail to it was returned or refused. "
        "Write to hello@ourhike.org if that's wrong.</small></p>"
        if locked
        else ""
    )
    body = (
        "<h1>Your email from OurHike</h1>"
        f"<p>For {escape(row.email)}. Turning these off doesn't stop a payment - that's "
        f'<a href="{escape(manage_url())}">More → Your support → Stop</a> in the app.</p>'
        + ('<p role="status"><strong>Saved.</strong></p>' if saved else "")
        + '<form method="post"><input type="hidden" name="form" value="1">'
        '<label class="switch"><span>Emails about my support<small>When it starts and when it stops. Payment receipts still come.</small></span>'
        f'<input type="checkbox" role="switch" name="support"{" checked" if support_on else ""}></label>'
        '<label class="switch"><span>Every other email from OurHike<small>Including a setup link you ask for</small></span>'
        f'<input type="checkbox" role="switch" name="everything"{" checked" if everything_on else ""}'
        f"{' disabled' if locked else ''}></label>"
        f"{note}"
        '<p><button type="submit">Save</button></p></form>'
    )
    return HTMLResponse(_PAGE.format(body=body))


@router.get("/mail/stop/{token}", response_class=HTMLResponse)
def unsubscribe_page(token: str, db: Session = Depends(get_db)) -> HTMLResponse:
    """The switches, as they stand. A page, not an action: mail scanners
    follow GET links, and a GET that changed anything would change it for
    whoever's inbox a scanner sits in."""
    return _switches_page(db, _choice_for_token(db, token))


@router.post("/mail/stop/{token}", response_class=HTMLResponse)
def unsubscribe(token: str, raw: bytes = Depends(_raw_body), db: Session = Depends(get_db)) -> HTMLResponse:
    """RFC 8058's one-click unsubscribe, and the page's Save.

    A mail app's one-click (`List-Unsubscribe=One-Click`) turns off emails
    about support only - the narrow default the maintainer chose. The page's
    form sets both switches as the hiker left them: "Every other email" off
    writes the address to app/core/mail.py's one suppression list, and on
    lifts only an unsubscribe the hiker made themselves.
    """
    row = _choice_for_token(db, token)
    fields = parse_qs(raw.decode("utf-8", "replace"), keep_blank_values=True)
    if "form" not in fields:
        set_support_mail(db, row.email, False)
        db.commit()
        return _switches_page(db, row, saved=True)
    set_support_mail(db, row.email, "support" in fields)
    if "everything" in fields:
        lift_unsubscribe(db, row.email)
    else:
        suppress(db, row.email, SuppressionReason.unsubscribed, note="support email switches")
    db.commit()
    return _switches_page(db, row, saved=True)
