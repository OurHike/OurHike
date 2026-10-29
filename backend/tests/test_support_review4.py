"""The fourth adversarial review of #1885, held (2026-10-29).

Three reviewers - security and privacy, money and data, the phone - read the
pull request at 73998bfa, after #1903 had landed, and wrote probes that
asserted the right behaviour and failed. Each finding below is one of those
probes, kept as the test that would fail again if the fix went. The phone's
are in client/src/screens/*.test.tsx; these are the backend's.

The three race tests are real races: the webhook runs in a second thread and
session, and arrives while the router holds the rows it read. Before the fix
the router read without a lock and wrote its stale reading over the payment
the webhook committed; now the webhook waits for the router's commit, and the
assertions are about the state both leave behind.
"""

import threading
import time
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

import app.core.account_deletion as deletion
import app.routers.support as support_router
from app.core import support as support_core
from app.core.analytics_report import build_report_data
from app.core.analytics_rollup import run
from app.core.mail import is_suppressed, record_delivery_failure, suppress
from app.core.support_providers import PROVIDERS
from app.core.time import utc_now
from app.models.analytics import AnalyticsEvent
from app.models.mail import EmailSend, MailState, SuppressionReason
from app.models.profile import Profile
from app.models.support import SupportCharge, SupportChoice, SupportMailPreference, SupportStatus
from tests.test_routers_support import (  # noqa: F401 - the fixtures are used by name
    _choice_id,
    _choose,
    _deliver,
    _ended_row,
    _fresh_total,
    _invoice,
    _me,
    _paying,
    _refund,
    _save_switches,
    _session,
    _stop,
    _subscription,
    _support_rows,
    configured,
    t0,
)
from tests.tokens import auth_headers

# ---- A duplicate payment never hides the one still charging ----


def test_a_stopped_duplicate_never_hides_the_payment_still_charging_or_says_nothing_more_will_be_charged(client, configured, t0):  # noqa: F811
    """Two tabs: the second payment is stopped, as designed. Your support still
    describes the first, which renews, with its Stop, and no email says
    "Nothing more will be charged"."""
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id))
    assert _deliver(client, _session(choice=choice, sub="sub_first", created=t0 - 120)).json() == {"result": "active"}
    assert _deliver(client, _session(choice=choice, sub="sub_second", created=t0 - 60)).json() == {"result": "unwanted"}
    _deliver(client, _subscription(sub="sub_second", created=t0, cancel_at_period_end=True))

    me = _me(client, user_id)

    assert (me["status"], me["can_stop"], me["supporting"]) == ("active", True, True)
    assert configured.to("hiker@example.com", about="Nothing more will be charged") == []


def test_a_strangers_payment_against_a_paid_choice_takes_neither_the_hikers_record_nor_their_address(
    client,
    configured,  # noqa: F811
    db_session,
    t0,  # noqa: F811
):
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id))
    _deliver(client, _session(choice=choice, sub="sub_hiker", created=t0 - 60))

    assert _deliver(client, _session(choice=choice, sub="sub_stranger", email="stranger@example.net", created=t0)).json() == {
        "result": "unwanted"
    }

    me = _me(client, user_id)
    assert (me["status"], me["email"]) == ("active", "hiker@example.com")
    export = client.get("/profiles/me/export", headers=auth_headers(user_id))
    assert export.status_code == 200 and "stranger@example.net" not in export.text


# ---- Races: the router locks what it reads ----


def _webhook_meanwhile(db_engine, envelope, mail):
    """Start the webhook's own code in a thread and session of its own, and
    give it time to reach the row the router has locked."""
    results: dict[str, str] = {}

    def deliver():
        with Session(db_engine) as other:
            other.execute(text("SET LOCAL lock_timeout = '10s'"))
            results["outcome"] = support_core.apply_delivery(other, PROVIDERS["stripe"], envelope, mail_provider=mail)
            other.commit()

    thread = threading.Thread(target=deliver)
    thread.start()
    time.sleep(0.5)
    return thread, results


def _stripe_asked_to_stop(stub, subscription: str) -> bool:
    return any(subscription in call["url"] for call in stub.api.calls)


def test_a_stop_pressed_while_the_payment_is_being_confirmed_still_stops_the_payment(client, configured, db_engine, monkeypatch):  # noqa: F811
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id))
    real = support_core.mark_stop
    started = []

    def confirmation_arrives(row, *, now):
        if not started:
            started.append(_webhook_meanwhile(db_engine, _session(choice=choice), configured.mail))
        return real(row, now=now)

    monkeypatch.setattr(support_router, "mark_stop", confirmation_arrives)

    _stop(client, user_id)
    thread, results = started[0]
    thread.join(15)

    # The Stop committed first, so the payment reads as one for a stopped
    # choice and is asked to stop - never left charging under "stopped".
    assert results["outcome"] == "unwanted"
    assert _stripe_asked_to_stop(configured, "sub_777")


def test_a_new_choice_made_while_the_payment_is_being_confirmed_leaves_the_payment_recorded(
    client,
    configured,  # noqa: F811
    db_engine,
    monkeypatch,
):
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id, amount_cents=6000))
    real = support_router._blocked
    started = []

    def confirmation_arrives(rows):
        if not started:
            started.append(_webhook_meanwhile(db_engine, _session(choice=choice, amount=6000), configured.mail))
        return real(rows)

    monkeypatch.setattr(support_router, "_blocked", confirmation_arrives)

    _choose(client, user_id, amount_cents=12000)
    thread, results = started[0]
    thread.join(15)

    with Session(db_engine) as check:
        row = check.get(SupportChoice, choice)
        assert (results["outcome"], row.status, row.provider_ref, row.amount_cents) == (
            "active",
            SupportStatus.active,
            "sub_777",
            6000,
        )


def test_an_account_deleted_while_its_payment_is_being_confirmed_has_that_payment_stopped(
    client,
    configured,  # noqa: F811
    db_engine,
    monkeypatch,
):
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id))
    real = deletion.secrets.token_urlsafe
    started = []

    def confirmation_arrives(n=None):
        if not started:
            started.append(_webhook_meanwhile(db_engine, _session(choice=choice), configured.mail))
        return real(n)

    monkeypatch.setattr(deletion.secrets, "token_urlsafe", confirmation_arrives)

    assert client.delete("/profiles/me", headers=auth_headers(user_id)).status_code == 200
    thread, results = started[0]
    thread.join(15)

    assert results["outcome"] == "unwanted"
    assert _stripe_asked_to_stop(configured, "sub_777")


def test_one_confirmation_delivered_twice_at_once_does_not_cancel_the_hikers_payment(client, configured, db_engine):  # noqa: F811
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id))
    envelope = _session(choice=choice)
    provider = PROVIDERS["stripe"]
    first_applied = threading.Event()
    results: dict[str, str] = {}

    def first():
        with Session(db_engine) as db:
            results["first"] = support_core.apply_delivery(db, provider, envelope, mail_provider=configured.mail)
            first_applied.set()
            time.sleep(1.0)  # the second is now waiting on the choice's lock
            db.commit()

    def second():
        first_applied.wait(5)
        with Session(db_engine) as db:
            db.execute(text("SET LOCAL lock_timeout = '10s'"))
            results["second"] = support_core.apply_delivery(db, provider, envelope, mail_provider=configured.mail)
            db.commit()

    threads = [threading.Thread(target=first), threading.Thread(target=second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(20)

    assert results["first"] == "active"
    assert configured.api.calls == []
    assert configured.to("founder@ourhike.org") == []


# ---- The published total ----


def test_a_refund_delivered_before_its_charge_still_comes_off_the_total(client, configured):  # noqa: F811
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id))
    _deliver(client, _session(choice=choice))
    assert _deliver(client, _refund(charge="ch_1", refunded=6000)).json() == {"result": "ignored_not_ours"}

    _deliver(client, _invoice(sub="sub_777", amount=6000))

    assert client.get("/support/total").json()["total_cents"] == 0


def test_the_published_total_is_never_below_zero(client, db_session, monkeypatch):
    """A December charge refunded on 2 January: the refund is dated when the
    money went back (the maintainer, 2026-10-29), and the page shows $0
    rather than minus $60."""
    for ref, cents, at in (("in_dec", 6000, datetime(2026, 12, 20)), ("refund:ch_dec", -6000, datetime(2027, 1, 2))):
        db_session.add(
            SupportCharge(
                provider="stripe",
                charge_ref=ref,
                subscription_ref="sub_dec",
                customer_ref="cus_dec",
                amount_cents=cents,
                currency="USD",
                charged_at=at,
            )
        )
    db_session.commit()
    monkeypatch.setattr("app.routers.support.utc_now", lambda: datetime(2027, 1, 3, 12, 0))

    assert client.get("/support/total").json()["total_cents"] == 0


def test_a_duplicate_payment_is_not_a_second_supporter(client, configured, t0):  # noqa: F811
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id))
    _deliver(client, _session(choice=choice, sub="sub_first", created=t0 - 120))
    _deliver(client, _invoice(sub="sub_first", amount=6000, invoice="in_first"))
    _deliver(client, _session(choice=choice, sub="sub_second", created=t0 - 60))
    _deliver(client, _invoice(sub="sub_second", amount=6000, invoice="in_second"))

    assert client.get("/support/total").json()["supporters"] == 1


# ---- What the purge keeps, and what it forgets ----


def test_the_purge_never_deletes_a_charge_of_a_payment_still_running(client, configured, db_session):  # noqa: F811
    """A charge delivered before a checkout that named no choice is joined to
    that checkout's row, so the sweep of unclaimed charges leaves it."""
    _deliver(client, _invoice(sub="sub_walk_in", amount=12000))
    _deliver(client, _session(sub="sub_walk_in", amount=12000, choice=None))

    support_core.purge_expired(db_session, now=utc_now() + support_core.RETENTION + timedelta(days=2))
    db_session.commit()

    assert db_session.query(SupportCharge).filter(SupportCharge.subscription_ref == "sub_walk_in").count() == 1


def test_a_deleted_accounts_cancellation_whose_last_event_was_lost_is_still_purged(client, db_session):
    gone = str(uuid.uuid4())
    _me(client, gone)
    db_session.query(Profile).filter(Profile.id == gone).update({Profile.deleted_at: utc_now()})
    db_session.commit()
    ancient = utc_now() - support_core.RETENTION - timedelta(days=30)
    row_id = _ended_row(db_session, profile_id=gone, ended=ancient, status=SupportStatus.cancel_scheduled)

    support_core.purge_expired(db_session)
    db_session.commit()

    assert db_session.get(SupportChoice, row_id) is None


def test_seven_years_after_a_deleted_accounts_payment_ended_its_address_and_amount_are_gone(client, configured, db_session):  # noqa: F811
    user_id = str(uuid.uuid4())
    _paying(client, user_id)  # the receipt: "You're giving OurHike $60 a year"
    assert client.delete("/profiles/me", headers=auth_headers(user_id)).status_code == 200
    _deliver(client, _subscription("customer.subscription.deleted", sub="sub_777", status="canceled"))
    db_session.expire_all()
    long_ago = utc_now() - support_core.RETENTION - timedelta(days=1)
    db_session.query(SupportChoice).update({SupportChoice.ended_at: long_ago, SupportChoice.status: SupportStatus.stopped})
    db_session.commit()

    assert support_core.purge_expired(db_session) == 1
    db_session.commit()

    assert db_session.query(EmailSend).filter(EmailSend.to_address == "hiker@example.com").count() == 0


def test_deleting_the_account_removes_the_address_of_a_choice_nobody_paid_for_from_the_mail_log(client, configured, db_session):  # noqa: F811
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, email="leaving@example.com")
    _choose(client, user_id, email="leaving@example.com", delivery="email")
    client.put("/support/me/mail", json={"support_emails": False}, headers=headers)
    client.put("/support/me/mail", json={"support_emails": True}, headers=headers)  # back on: nothing to honour

    assert client.delete("/profiles/me", headers=headers).status_code == 200

    db_session.expire_all()
    assert db_session.query(EmailSend).filter(EmailSend.to_address == "leaving@example.com").count() == 0
    assert db_session.get(SupportMailPreference, "leaving@example.com") is None


def test_deleting_the_account_keeps_an_email_switch_that_is_off(client, configured, db_session):  # noqa: F811
    """An opt-out outlives the account, or it is not honoured."""
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, email="leaving@example.com")
    _choose(client, user_id, email="leaving@example.com")
    client.put("/support/me/mail", json={"support_emails": False}, headers=headers)

    assert client.delete("/profiles/me", headers=headers).status_code == 200

    db_session.expire_all()
    assert db_session.get(SupportMailPreference, "leaving@example.com").off_at is not None


def test_choose_and_stop_in_a_loop_does_not_grow_the_table_without_bound(client, configured, db_session):  # noqa: F811
    user_id = str(uuid.uuid4())
    for _ in range(30):
        _choose(client, user_id)
        _stop(client, user_id)

    db_session.expire_all()
    assert db_session.query(SupportChoice).filter(SupportChoice.profile_id == user_id).count() == 1


# ---- The email switches ----


def test_an_address_typed_into_stripe_never_becomes_a_row_an_account_can_see(client, configured, db_session):  # noqa: F811
    """Stop a $12 choice (free), then pay its link with somebody else's
    address typed on Stripe's page. The duplicate row is under the hiker's
    verified address, so the hiker holds no link to that person's switches."""
    victim = "chair@club.example.org"
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id, amount_cents=1200))
    _stop(client, user_id)

    assert _deliver(client, _session(choice=choice, sub="sub_typed", amount=1200, email=victim)).json() == {"result": "unwanted"}

    assert db_session.query(SupportChoice).filter(SupportChoice.email == victim).count() == 0
    rows = client.get("/profiles/me/export", headers=auth_headers(user_id)).json()["what_you_give_ourhike"]
    assert rows and all("link_token" not in row for row in rows)


def test_a_complaint_after_an_unsubscribe_cannot_be_lifted_from_the_email_page(client, configured, monkeypatch, db_session):  # noqa: F811
    monkeypatch.setattr("app.core.support_mail.settings.api_public_url", "https://api.ourhike.org")
    _choose(client, str(uuid.uuid4()), delivery="email")
    token = db_session.query(SupportChoice).one().link_token
    [sent] = db_session.query(EmailSend).all()
    _save_switches(client, token, support=True, everything=False)
    record_delivery_failure(db_session, sent.provider_message_id, MailState.complained)
    db_session.commit()

    _save_switches(client, token, support=True, everything=True)

    db_session.expire_all()
    assert is_suppressed(db_session, "hiker@example.com")


def test_a_later_reason_replaces_an_unsubscribe_and_nothing_replaces_a_stronger_one(db_session):
    suppress(db_session, "a@example.org", SuppressionReason.unsubscribed)
    suppress(db_session, "a@example.org", SuppressionReason.complained)
    suppress(db_session, "a@example.org", SuppressionReason.unsubscribed)
    db_session.commit()

    assert is_suppressed(db_session, "a@example.org")
    from app.core.mail import suppression_reason

    assert suppression_reason(db_session, "a@example.org") == SuppressionReason.complained


def test_the_apps_email_switch_turns_off_the_mail_the_hiker_actually_gets(client, configured, t0):  # noqa: F811
    """Paid while signed in as old@; the sign-in address later became new@.
    The mail still goes to old@, and the app's switch reaches it."""
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id, email="old@example.com"))
    _deliver(client, _session(choice=choice, email="old@example.com"))

    off = client.put("/support/me/mail", json={"support_emails": False}, headers=auth_headers(user_id, email="new@example.com"))

    assert off.status_code == 200 and off.json()["support_emails"] is False


# ---- The paid count ----


def test_a_paid_counts_id_is_random_and_names_nothing(client, configured, db_session):  # noqa: F811
    _paying(client, str(uuid.uuid4()))

    [count] = _support_rows(db_session)

    assert uuid.UUID(count.id).version == 4
    assert db_session.query(SupportChoice).filter(SupportChoice.id == count.id).count() == 0


def test_a_paid_count_is_the_tier_and_not_the_amount_charged(client, configured, db_session):  # noqa: F811
    """A tax or a discount moves `amount_total`; the link's tier does not."""
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id, amount_cents=6000))
    envelope = _session(choice=choice, amount=6000)
    envelope["data"]["object"]["amount_total"] = 6390  # with a tax added at checkout

    _deliver(client, envelope)

    assert [row.support_cents for row in _support_rows(db_session)] == [6000]


def test_a_paid_count_is_dated_the_day_it_is_counted(client, configured, db_session, t0):  # noqa: F811
    """A confirmation Stripe resends a month later lands in an open month."""
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id))

    _deliver(client, _session(choice=choice, created=t0 - 40 * 86400))

    assert [row.local_date for row in _support_rows(db_session)] == [utc_now().date()]


def test_a_choice_made_with_usage_statistics_off_on_the_phone_is_never_counted(client, configured, db_session):  # noqa: F811
    user_id = str(uuid.uuid4())
    choice = _choice_id(_choose(client, user_id, usage_counts=False))

    _deliver(client, _session(choice=choice))

    assert _support_rows(db_session) == []


# ---- The report ----


def _events(db_session, n, **fields):
    for _ in range(n):
        db_session.add(
            AnalyticsEvent(
                id=str(uuid.uuid4()),
                local_date=date(2026, 10, 5),
                received_on=date(2026, 10, 5),
                event=fields.get("event", "map_screen_viewed"),
                platform=fields.get("platform", "android"),
                **{key: value for key, value in fields.items() if key not in ("event", "platform")},
            )
        )


def test_a_masked_support_level_cannot_be_read_back_from_the_reports_event_total(db_session):
    """The PR's own example month: 161, 58, 26 and three $120s. `events`
    counts the six other kinds only, so events less those kinds is 0 and
    gives no level back."""
    _events(db_session, 400, event="map_screen_viewed", month_first=True)
    _events(db_session, 60, event="app_installed")
    _events(db_session, 40, event="user_login")
    _events(db_session, 30, event="hike_plan_made", miles=5.0)
    _events(db_session, 30, event="hike_plan_completed", miles=5.0)
    _events(db_session, 200, event="session", pageviews=3, session_length="m1_to_5")
    for cents, n in ((0, 161), (1200, 58), (6000, 26), (12000, 3)):
        _events(db_session, n, event="support_chosen", platform="web" if cents else "ios", support_cents=cents)
    db_session.commit()

    run(db_session, today=date(2026, 10, 20))
    cell = build_report_data(db_session, environment="Test", today=date(2026, 10, 20))["cells"]["2026-10|*|*"]

    assert cell["support_chosen_12000"] is None
    kinds = ("installs", "logins", "plans_made", "plans_completed", "map_views", "sessions")
    assert cell["events"] - sum(cell[kind] for kind in kinds) == 0


def test_a_support_choice_arriving_after_its_month_closed_is_counted_apart(db_session):
    _events(db_session, 30, event="map_screen_viewed", month_first=True)
    _events(db_session, 30, event="support_chosen", platform="ios", support_cents=0)
    db_session.commit()
    run(db_session, today=date(2026, 11, 20))  # October closes
    _events(db_session, 2, event="support_chosen", platform="ios", support_cents=0)
    db_session.commit()

    run(db_session, today=date(2026, 11, 21))

    from app.models.analytics import AnalyticsMonthly

    def value(metric):
        row = db_session.get(AnalyticsMonthly, (date(2026, 10, 1), metric, "*", "*"))
        return None if row is None else row.value

    assert (value("support_chosen_0"), value("support_after_close"), value("events_after_close")) == (30.0, 2.0, 0.0)
