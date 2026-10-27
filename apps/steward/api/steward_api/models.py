"""The API's tables (PLAN.md §8, the phase 2 rows).

No email and no name from the identity provider is stored: Supabase owns the
address, as it does for backend/ (app/core/auth.py). A person here is their
Supabase user id and, if they choose one, a display name.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid, func
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
