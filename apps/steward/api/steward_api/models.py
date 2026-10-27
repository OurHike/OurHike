"""The API's tables (PLAN.md §8, the phase 2 rows).

No email and no name from the identity provider is stored: Supabase owns the
address, as it does for backend/ (app/core/auth.py). A person here is their
Supabase user id and, if they choose one, a display name.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from steward_api import limits


class Base(DeclarativeBase):
    pass


class StewardUser(Base):
    __tablename__ = "steward_user"

    #: Supabase's `sub`, a UUID string.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(limits.DISPLAY_NAME_MAX))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SiteList(Base):
    __tablename__ = "site_list"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[str] = mapped_column(ForeignKey("steward_user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(limits.LIST_NAME_MAX))
    #: SHA-256 of the share token, hex. The token itself is shown once, to the
    #: owner, and never stored: a copy of this table opens no list.
    share_token_sha256: Mapped[str | None] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items: Mapped[list[SiteListItem]] = relationship(
        back_populates="site_list", cascade="all, delete-orphan", order_by="SiteListItem.added_at"
    )


class SiteListItem(Base):
    __tablename__ = "site_list_item"

    list_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("site_list.id", ondelete="CASCADE"), primary_key=True)
    #: ATC's RIMS_ID. Not checked against the analysis: a site that leaves ATC's
    #: inventory stays in the lists that saved it, and the app says it is gone.
    rims_id: Mapped[str] = mapped_column(String(limits.RIMS_ID_MAX), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    site_list: Mapped[SiteList] = relationship(back_populates="items")


class ClubWeights(Base):
    """One set of a club's ranking weights. Append-only: a change is a new row, so
    the history is the table and undo is restoring an earlier row (PLAN.md §8)."""

    __tablename__ = "club_weights"
    __table_args__ = (
        Index("ix_club_weights_club_changed_at", "club", "changed_at"),
        *(
            CheckConstraint(f"{name} between 0 and {limits.WEIGHT_MAX}", name=f"ck_club_weights_{name}_range")
            for name in limits.WEIGHT_NAMES
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    club: Mapped[str] = mapped_column(String(limits.CLUB_MAX))
    deficit: Mapped[int] = mapped_column(Integer)
    water: Mapped[int] = mapped_column(Integer)
    trail: Mapped[int] = mapped_column(Integer)
    cluster: Mapped[int] = mapped_column(Integer)
    restricted: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(limits.NOTE_MAX))
    #: The row this one copied, when the change was "restore an earlier set".
    restored_from: Mapped[int | None] = mapped_column(ForeignKey("club_weights.id", ondelete="SET NULL"))
    #: SET NULL rather than CASCADE: a person leaving must not rewrite a club's
    #: ranking history, so their changes stay and lose only the name.
    changed_by: Mapped[str | None] = mapped_column(ForeignKey("steward_user.id", ondelete="SET NULL"), index=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --- Claims (phase 3, #1910; PLAN.md §6) --------------------------------------------

#: The states a claim moves through. "released" is reached by a claimer letting
#: go or by the clock running out, and is final.
CLAIM_STATES = ("claimed", "in_progress", "submitted", "verified", "released")
#: The states that hold a site: at most one claim per site is in one of these.
HOLDING_STATES = ("claimed", "in_progress", "submitted")


class Claim(Base):
    __tablename__ = "claim"
    __table_args__ = (
        CheckConstraint(f"state in {CLAIM_STATES!r}", name="ck_claim_state"),
        # One live claim per site, held by the database rather than by a check
        # two requests could both pass.
        Index(
            "uq_claim_one_live_per_site",
            "rims_id",
            unique=True,
            postgresql_where=text(f"state in {HOLDING_STATES!r}"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rims_id: Mapped[str] = mapped_column(String(limits.RIMS_ID_MAX), index=True)
    #: SET NULL: a claimer who deletes their account leaves the site's history.
    claimer_id: Mapped[str | None] = mapped_column(ForeignKey("steward_user.id", ondelete="SET NULL"), index=True)
    state: Mapped[str] = mapped_column(String(20))
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    steps_done: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    notes: Mapped[str | None] = mapped_column(String(limits.NOTES_MAX))
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("steward_user.id", ondelete="SET NULL"))
    review_note: Mapped[str | None] = mapped_column(String(limits.REVIEW_NOTE_MAX))
    #: SHA-256 of the crew invite token, as for list share links.
    invite_token_sha256: Mapped[str | None] = mapped_column(String(64), unique=True)

    members: Mapped[list[ClaimMember]] = relationship(cascade="all, delete-orphan", order_by="ClaimMember.joined_at")
    photos: Mapped[list[Photo]] = relationship(cascade="all, delete-orphan", order_by="Photo.created_at")
    hours: Mapped[list[Hours]] = relationship(cascade="all, delete-orphan")


class ClaimMember(Base):
    """The crew, the claimer included."""

    __tablename__ = "claim_member"

    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claim.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("steward_user.id", ondelete="CASCADE"), primary_key=True, index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Photo(Base):
    """One photo of a claimed site. The bytes are in R2 under photos.photo_key(),
    derived from these ids and never stored, as backend/app/core/photos.py keys
    report photos: the row is authoritative and the object disposable."""

    __tablename__ = "photo"
    __table_args__ = (
        CheckConstraint("phase in ('before', 'after', 'extra')", name="ck_photo_phase"),
        CheckConstraint("(phase = 'extra') = (point is null)", name="ck_photo_point_only_on_points"),
        # One before and one after per photo point; a new one replaces it.
        Index("uq_photo_point", "claim_id", "phase", "point", unique=True, postgresql_where=text("point is not null")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claim.id", ondelete="CASCADE"), index=True)
    phase: Mapped[str] = mapped_column(String(10))
    point: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(20))
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("steward_user.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Hours(Base):
    """One person's volunteer hours on one claim: claimed at submission,
    verified when a reviewer verifies the claim (PLAN.md §6)."""

    __tablename__ = "hours"
    __table_args__ = (CheckConstraint(f"tenths > 0 and tenths <= {limits.HOURS_MAX * 10}", name="ck_hours_range"),)

    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claim.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("steward_user.id", ondelete="CASCADE"), primary_key=True, index=True)
    #: Tenths of an hour, so 2.5 hours is 25 and no float is ever summed.
    tenths: Mapped[int] = mapped_column(Integer)
    verified: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
