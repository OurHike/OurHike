"""support choices and support events

Revision ID: c5a8e2d4f913
Revises: 897b71ad5fff
Create Date: 2026-10-23 01:00:00.000000

What a hiker chose to give OurHike, paid choices only (#1876): a $0 answer
stays on the phone and never reaches a table. See app/models/support.py for
the life of a row, what is kept for a provider move, and why the email is
stored here when core/auth.py's own rule is that nothing stores it.

Edited in place on 2026-10-26, before any release carried it, with the #1885
review's fixes: the provider ids and dates a move needs, the ordering guard's
`last_event_at`, the stop-request retry's `stop_notified_at`, the two new
statuses, one row per provider payment (`uq_support_choices_provider_ref`),
and the `support_events` log. Edited again on 2026-10-27, still unreleased,
with the third review's: the `payment_failed` status, `provider_status`,
the Stop's `stop_attempted_at` (retry backoff) and `stop_confirmed_at` (the
hiker told once), and `support_charges`, one row per provider charge, which
the published total sums and whose unique key stops a charge being counted
twice. And once more that day, still unreleased, for the maintainer's
answers: `support_charges.customer_ref` (how a refund is recognised) and
`support_mail_preferences` (the "Emails about my support" switch).

Indexed on `profile_id` (the signed-in "my support" read), `email` and
`provider_ref` (the keys a webhook can match on), `status`, `link_token` (the
unsubscribe link's lookup), on the event log's `event_id` and
`choice_id`, and on the charges' `subscription_ref` (joining a charge that
arrived before its checkout), `choice_id` and `charged_at` (the year's sum). Plain `ix_<table>_<column>` names, as the models declare them,
so the drift check compares like with like.

RLS is enabled on all four tables because this revision adds them (b3d1c7a94e02's
rule, tests/test_migration_rls.py's union): PostgREST would otherwise serve
every supporter's email and amount to anyone holding the anon key.

Additive and reversible: downgrade drops the four tables and nothing else.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5a8e2d4f913"
down_revision: Union[str, Sequence[str], None] = "897b71ad5fff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The tables this revision locks - see b3d1c7a94e02 for the mechanism.
RLS_TABLES: tuple[str, ...] = ("support_choices", "support_events", "support_charges", "support_mail_preferences")


def rls_statements(dialect_name: str, *, enable: bool) -> list[str]:
    """Same shape as b3d1c7a94e02's, for the same testability reason."""
    if dialect_name != "postgresql":
        return []
    verb = "ENABLE" if enable else "DISABLE"
    return [f"ALTER TABLE public.{table} {verb} ROW LEVEL SECURITY" for table in RLS_TABLES]


def upgrade() -> None:
    """Create the tables, and lock them before anything can reach them."""
    op.create_table(
        "support_choices",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("profile_id", sa.String(), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("provider_ref", sa.String(length=100), nullable=True),
        sa.Column("customer_ref", sa.String(length=100), nullable=True),
        sa.Column("psp_ref", sa.String(length=100), nullable=True),
        sa.Column("plan_ref", sa.String(length=100), nullable=True),
        sa.Column("chosen_amount_cents", sa.Integer(), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "cadence",
            sa.Enum("year", "month", name="supportcadence", native_enum=False, length=10),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "active",
                "payment_failed",
                "paused",
                "cancel_scheduled",
                "stop_requested",
                "stopped",
                name="supportstatus",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("terms_version", sa.String(length=40), nullable=True),
        sa.Column("delivery", sa.String(length=10), nullable=True),
        sa.Column("migrate_notice_at", sa.DateTime(), nullable=True),
        sa.Column("accounting_email", sa.Boolean(), nullable=False),
        sa.Column("accounting_email_at", sa.DateTime(), nullable=True),
        sa.Column("chosen_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("period_end", sa.DateTime(), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=True),
        sa.Column("stop_requested_at", sa.DateTime(), nullable=True),
        sa.Column("provider_status", sa.String(length=30), nullable=True),
        sa.Column("stop_notified_at", sa.DateTime(), nullable=True),
        sa.Column("stop_attempted_at", sa.DateTime(), nullable=True),
        sa.Column("stop_confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("last_event_at", sa.DateTime(), nullable=True),
        sa.Column("replaces_choice_id", sa.String(), nullable=True),
        sa.Column("link_token", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"]),
        sa.ForeignKeyConstraint(["replaces_choice_id"], ["support_choices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "provider_ref", name="uq_support_choices_provider_ref"),
    )
    op.create_index("ix_support_choices_profile_id", "support_choices", ["profile_id"])
    op.create_index("ix_support_choices_email", "support_choices", ["email"])
    op.create_index("ix_support_choices_provider_ref", "support_choices", ["provider_ref"])
    op.create_index("ix_support_choices_status", "support_choices", ["status"])
    op.create_index("ix_support_choices_link_token", "support_choices", ["link_token"], unique=True)

    op.create_table(
        "support_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("choice_id", sa.String(), nullable=True),
        sa.Column("outcome", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["choice_id"], ["support_choices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_support_events_event_id", "support_events", ["event_id"])
    op.create_index("ix_support_events_choice_id", "support_events", ["choice_id"])

    op.create_table(
        "support_charges",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("charge_ref", sa.String(length=100), nullable=False),
        sa.Column("subscription_ref", sa.String(length=100), nullable=True),
        sa.Column("choice_id", sa.String(), nullable=True),
        sa.Column("customer_ref", sa.String(length=100), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("charged_at", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["choice_id"], ["support_choices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "charge_ref", name="uq_support_charges_provider_ref"),
    )
    op.create_index("ix_support_charges_subscription_ref", "support_charges", ["subscription_ref"])
    op.create_index("ix_support_charges_choice_id", "support_charges", ["choice_id"])
    op.create_index("ix_support_charges_charged_at", "support_charges", ["charged_at"])
    op.create_index("ix_support_charges_customer_ref", "support_charges", ["customer_ref"])

    op.create_table(
        "support_mail_preferences",
        sa.Column("address", sa.String(length=320), nullable=False),
        sa.Column("off_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("address"),
    )

    for statement in rls_statements(op.get_bind().dialect.name, enable=True):
        op.execute(statement)


def downgrade() -> None:
    """Unlock, then drop - the reverse of upgrade, and only these tables."""
    for statement in rls_statements(op.get_bind().dialect.name, enable=False):
        op.execute(statement)
    op.drop_table("support_mail_preferences")
    op.drop_index("ix_support_charges_customer_ref", table_name="support_charges")
    op.drop_index("ix_support_charges_charged_at", table_name="support_charges")
    op.drop_index("ix_support_charges_choice_id", table_name="support_charges")
    op.drop_index("ix_support_charges_subscription_ref", table_name="support_charges")
    op.drop_table("support_charges")
    op.drop_index("ix_support_events_choice_id", table_name="support_events")
    op.drop_index("ix_support_events_event_id", table_name="support_events")
    op.drop_table("support_events")
    op.drop_index("ix_support_choices_link_token", table_name="support_choices")
    op.drop_index("ix_support_choices_status", table_name="support_choices")
    op.drop_index("ix_support_choices_provider_ref", table_name="support_choices")
    op.drop_index("ix_support_choices_email", table_name="support_choices")
    op.drop_index("ix_support_choices_profile_id", table_name="support_choices")
    op.drop_table("support_choices")
