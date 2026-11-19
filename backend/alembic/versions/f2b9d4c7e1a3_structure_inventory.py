"""structure inventory

Revision ID: f2b9d4c7e1a3
Revises: e4b8d2a7c391
Create Date: 2026-11-04 06:00:05.183354

#1983 — The structure inventory's five tables land in one revision, locked
by RLS, with every enum as VARCHAR + CHECK: the six tables in one revision -
`inventory_enrollments`, `inventory_structures`, `inventory_observations`,
`inventory_passes`, `inventory_claims` and the one-row-per-club
`inventory_club_settings`. app/models/inventory.py is the reasoning, and
features/STRUCTURE_INVENTORY.md's "Data model" is the design.

Every enum is `native_enum=False` with a length, so Postgres holds a plain
VARCHAR and no type: a value added later is a model change and needs no
migration (field_note.py's `trash`). There is no CHECK constraint behind
them, which is how the rest of this schema stands too - see the model
module's header for the measurement.

RLS is enabled here rather than in a later revision because this revision
adds the tables, 619320d2b4a9's rule: a table added later brings its own
lock, and tests/test_migration_rls.py unions every revision's RLS_TABLES.

Indexes on what the first readers filter by - a club's observations by
review state for the queue, a section's claims by day for the areas query,
and every foreign key a router will look up by. c3a8f1d6e2b7's reasoning:
cheap while the tables are empty, which is when adding them is a line
rather than an incident.

Revises e4b8d2a7c391 because that is the head of the chain on `main` at
0b902c39; revising anything else would be a second head, and two heads
cannot migrate.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2b9d4c7e1a3"
down_revision: Union[str, Sequence[str], None] = "e4b8d2a7c391"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RLS_TABLES: tuple[str, ...] = (
    "inventory_club_settings",
    "inventory_enrollments",
    "inventory_passes",
    "inventory_claims",
    "inventory_structures",
    "inventory_observations",
)


def rls_statements(dialect_name: str, *, enable: bool) -> list[str]:
    """Same shape as b3d1c7a94e02's, for the same testability reason."""
    if dialect_name != "postgresql":
        return []
    verb = "ENABLE" if enable else "DISABLE"
    return [f"ALTER TABLE public.{table} {verb} ROW LEVEL SECURITY" for table in RLS_TABLES]


def upgrade() -> None:
    """Create the six tables, and lock them before anything can reach them."""
    op.create_table(
        "inventory_club_settings",
        sa.Column("club_id", sa.String(), nullable=False),
        sa.Column("waiver_text", sa.Text(), nullable=True),
        sa.Column("waiver_version", sa.String(), nullable=True),
        sa.Column("claim_days_ahead", sa.Integer(), nullable=False),
        sa.Column("coverage_window_days", sa.Integer(), nullable=False),
        sa.Column("coverage_min_records", sa.Integer(), nullable=False),
        sa.Column("stale_days", sa.Integer(), nullable=False),
        sa.Column("publish_locations", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
        ),
        sa.PrimaryKeyConstraint("club_id"),
    )
    op.create_table(
        "inventory_enrollments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("club_id", sa.String(), nullable=False),
        sa.Column("person_id", sa.String(), nullable=False),
        sa.Column("waiver_version", sa.String(), nullable=False),
        sa.Column("waiver_signed_at", sa.DateTime(), nullable=False),
        sa.Column("typed_name", sa.Text(), nullable=False),
        sa.Column("training_completed_at", sa.DateTime(), nullable=True),
        sa.Column("field_day_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["person_id"],
            ["profiles.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("club_id", "person_id", name="uq_inventory_enrollments_club_person"),
    )
    op.create_index(op.f("ix_inventory_enrollments_club_id"), "inventory_enrollments", ["club_id"], unique=False)
    op.create_index(op.f("ix_inventory_enrollments_person_id"), "inventory_enrollments", ["person_id"], unique=False)
    op.create_table(
        "inventory_passes",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("club_id", sa.String(), nullable=False),
        sa.Column("volunteer_id", sa.String(), nullable=False),
        sa.Column("trail_id", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("from_lat", sa.Float(), nullable=True),
        sa.Column("from_lon", sa.Float(), nullable=True),
        sa.Column("to_lat", sa.Float(), nullable=True),
        sa.Column("to_lon", sa.Float(), nullable=True),
        sa.Column("ended_early", sa.Boolean(), nullable=False),
        sa.Column("state", sa.Enum("in_progress", "completed", "abandoned", name="passstate", native_enum=False), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["trail_id"],
            ["org_trails.id"],
        ),
        sa.ForeignKeyConstraint(
            ["volunteer_id"],
            ["profiles.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inventory_passes_club_id"), "inventory_passes", ["club_id"], unique=False)
    op.create_index(op.f("ix_inventory_passes_volunteer_id"), "inventory_passes", ["volunteer_id"], unique=False)
    op.create_table(
        "inventory_claims",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("club_id", sa.String(), nullable=False),
        sa.Column("volunteer_id", sa.String(), nullable=False),
        sa.Column("section_id", sa.String(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(), nullable=False),
        sa.Column("walk_on", sa.Date(), nullable=False),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["section_id"],
            ["org_sections.id"],
        ),
        sa.ForeignKeyConstraint(
            ["volunteer_id"],
            ["profiles.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inventory_claims_club_id"), "inventory_claims", ["club_id"], unique=False)
    op.create_index("ix_inventory_claims_section_walk_on", "inventory_claims", ["section_id", "walk_on"], unique=False)
    op.create_index(op.f("ix_inventory_claims_volunteer_id"), "inventory_claims", ["volunteer_id"], unique=False)
    op.create_table(
        "inventory_structures",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("club_id", sa.String(), nullable=False),
        sa.Column("trail_id", sa.String(), nullable=True),
        sa.Column("section_id", sa.String(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "bridge",
                "puncheon",
                "shelter",
                "privy",
                "campsite",
                "water",
                "blaze",
                "sign",
                "kiosk",
                "parking",
                "steps",
                "other",
                name="structurekind",
                native_enum=False,
                length=10,
            ),
            nullable=False,
        ),
        sa.Column("subkind", sa.String(), nullable=True),
        sa.Column("code", sa.String(), nullable=True),
        sa.Column("external_ids", sa.JSON(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("mile", sa.Float(), nullable=True),
        sa.Column("off_line_ft", sa.Float(), nullable=True),
        sa.Column("poi_id", sa.String(), nullable=True),
        sa.Column(
            "status", sa.Enum("active", "removed", "merged", name="structurestatus", native_enum=False, length=8), nullable=False
        ),
        sa.Column("merged_into_id", sa.String(), nullable=True),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["profiles.id"],
        ),
        sa.ForeignKeyConstraint(
            ["merged_into_id"],
            ["inventory_structures.id"],
        ),
        sa.ForeignKeyConstraint(
            ["section_id"],
            ["org_sections.id"],
        ),
        sa.ForeignKeyConstraint(
            ["trail_id"],
            ["org_trails.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("club_id", "code", name="uq_inventory_structures_club_code"),
    )
    op.create_index(op.f("ix_inventory_structures_club_id"), "inventory_structures", ["club_id"], unique=False)
    op.create_index(op.f("ix_inventory_structures_section_id"), "inventory_structures", ["section_id"], unique=False)
    op.create_index(op.f("ix_inventory_structures_trail_id"), "inventory_structures", ["trail_id"], unique=False)
    op.create_table(
        "inventory_observations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("structure_id", sa.String(), nullable=False),
        sa.Column("club_id", sa.String(), nullable=False),
        sa.Column("pass_id", sa.String(), nullable=True),
        sa.Column("volunteer_id", sa.String(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("offline", sa.Boolean(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("accuracy_m", sa.Float(), nullable=False),
        sa.Column("readings_count", sa.Integer(), nullable=False),
        sa.Column("readings_seconds", sa.Integer(), nullable=False),
        sa.Column("readings", sa.JSON(), nullable=False),
        sa.Column("fix_source", sa.Enum("sampled", "marked_from_here", name="fixsource", native_enum=False), nullable=False),
        sa.Column("gps_lock", sa.Boolean(), nullable=True),
        sa.Column("satellites", sa.Integer(), nullable=True),
        sa.Column(
            "connection", sa.Enum("cellular", "wifi", "none", "unknown", name="connection", native_enum=False), nullable=False
        ),
        sa.Column("same_as_structure_id", sa.String(), nullable=True),
        sa.Column("condition", sa.Enum("good", "fair", "poor", "unsafe", name="condition", native_enum=False), nullable=False),
        sa.Column("problems", sa.JSON(), nullable=False),
        sa.Column(
            "repair", sa.Enum("leave", "minor", "major", "replace", "remove", name="repair", native_enum=False), nullable=False
        ),
        sa.Column(
            "timing",
            sa.Enum("now", "this_season", "next_year", "five_years", name="repairtiming", native_enum=False),
            nullable=True,
        ),
        sa.Column("size_bucket", sa.String(), nullable=True),
        sa.Column("size_measured", sa.Float(), nullable=True),
        sa.Column("size_unit", sa.String(), nullable=True),
        sa.Column("size_method", sa.Enum("bucket", "tape", name="sizemethod", native_enum=False), nullable=True),
        sa.Column("counts", sa.JSON(), nullable=True),
        sa.Column("railings", sa.Boolean(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("photo_count", sa.Integer(), nullable=False),
        sa.Column(
            "review_state",
            sa.Enum("submitted", "accepted", "returned", "merged", "not_ours", name="reviewstate", native_enum=False),
            nullable=False,
        ),
        sa.Column("reviewed_by", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("report_id", sa.String(), nullable=True),
        sa.Column("mile", sa.Float(), nullable=True),
        sa.Column("off_line_ft", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["club_id"],
            ["clubs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["pass_id"],
            ["inventory_passes.id"],
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["reports.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["profiles.id"],
        ),
        sa.ForeignKeyConstraint(
            ["same_as_structure_id"],
            ["inventory_structures.id"],
        ),
        sa.ForeignKeyConstraint(
            ["structure_id"],
            ["inventory_structures.id"],
        ),
        sa.ForeignKeyConstraint(
            ["volunteer_id"],
            ["profiles.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inventory_observations_club_id"), "inventory_observations", ["club_id"], unique=False)
    op.create_index(
        "ix_inventory_observations_club_review_state", "inventory_observations", ["club_id", "review_state"], unique=False
    )
    op.create_index(op.f("ix_inventory_observations_pass_id"), "inventory_observations", ["pass_id"], unique=False)
    op.create_index(op.f("ix_inventory_observations_structure_id"), "inventory_observations", ["structure_id"], unique=False)
    op.create_index(op.f("ix_inventory_observations_volunteer_id"), "inventory_observations", ["volunteer_id"], unique=False)
    for statement in rls_statements(op.get_context().dialect.name, enable=True):
        op.execute(statement)


def downgrade() -> None:
    """Drop the six tables, children first; each lock goes with its table, and so does every record."""
    op.drop_index(op.f("ix_inventory_observations_volunteer_id"), table_name="inventory_observations")
    op.drop_index(op.f("ix_inventory_observations_structure_id"), table_name="inventory_observations")
    op.drop_index(op.f("ix_inventory_observations_pass_id"), table_name="inventory_observations")
    op.drop_index("ix_inventory_observations_club_review_state", table_name="inventory_observations")
    op.drop_index(op.f("ix_inventory_observations_club_id"), table_name="inventory_observations")
    op.drop_table("inventory_observations")
    op.drop_index(op.f("ix_inventory_structures_trail_id"), table_name="inventory_structures")
    op.drop_index(op.f("ix_inventory_structures_section_id"), table_name="inventory_structures")
    op.drop_index(op.f("ix_inventory_structures_club_id"), table_name="inventory_structures")
    op.drop_table("inventory_structures")
    op.drop_index(op.f("ix_inventory_claims_volunteer_id"), table_name="inventory_claims")
    op.drop_index("ix_inventory_claims_section_walk_on", table_name="inventory_claims")
    op.drop_index(op.f("ix_inventory_claims_club_id"), table_name="inventory_claims")
    op.drop_table("inventory_claims")
    op.drop_index(op.f("ix_inventory_passes_volunteer_id"), table_name="inventory_passes")
    op.drop_index(op.f("ix_inventory_passes_club_id"), table_name="inventory_passes")
    op.drop_table("inventory_passes")
    op.drop_index(op.f("ix_inventory_enrollments_person_id"), table_name="inventory_enrollments")
    op.drop_index(op.f("ix_inventory_enrollments_club_id"), table_name="inventory_enrollments")
    op.drop_table("inventory_enrollments")
    op.drop_table("inventory_club_settings")
