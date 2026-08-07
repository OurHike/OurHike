"""The `profile` table - a local row keyed by the Supabase Auth user id.

See ../../../features/AUTHENTICATION.md (the `User` model Supabase Auth
itself owns - email, password hash, MFA state, linked providers) and
../../../features/IDENTITY_AND_PRIVACY.md (trail name / `display_name`).
This table deliberately does not duplicate anything Supabase Auth already
stores; it exists only to hold the OurHike-specific state that has to live
next to *this* backend's own data:

- `role` - a real gap in AUTHENTICATION.md (no role field exists there at
  all). A flat `hiker | maintainer | club_admin` enum is "at least enough to
  identify a reporter and a moderator" (TECHNICAL_ARCHITECTURE.md's Backend
  section) - no multi-club modeling.
- `display_name` - the trail name (ONBOARDING.md), nullable because it's
  set later, once onboarding links a device-local trail name to this
  account, not at profile-provisioning time.

`id` is the Supabase user id itself (a UUID, stored as a plain string) -
never a locally-generated id. It's the join key back to Supabase Auth's own
`auth.users` table, so a second surrogate key would just be a second id for
the same person.
"""

import enum

from sqlalchemy import Column, DateTime, Enum, String

from app.core.time import utc_now
from app.db.base import Base

# A tz-aware `datetime` gets stored as a naive UTC one (tzinfo stripped)
# below - `DateTime`, not `DateTime(timezone=True)` - and every model here
# follows it. The convention is uniform and safe because every value going
# in is already UTC by construction (app.core.time.utc_now), and because the
# UTC designator is stamped back on at the API boundary rather than being
# lost (see app/core/time.py, which explains what a naive timestamp does to
# a browser if it escapes unmarked).
#
# It was adopted for a reason that no longer exists: fetching `TIMESTAMPTZ`
# back through duckdb-engine needed the optional `pytz` package, and the
# backend ran on DuckDB locally. That path is gone - dev, CI and production
# are all Postgres now (backend/scripts/local-postgres.sh) - so `TIMESTAMPTZ`
# is available if it is ever wanted. Changing it is a schema migration plus a
# sweep of every read path, not a comment edit, and nothing currently needs
# it: left as an open call rather than quietly rewritten as if it had always
# been the plan.


class Role(str, enum.Enum):
    hiker = "hiker"
    maintainer = "maintainer"
    club_admin = "club_admin"


# The roles the moderation queue is gated to, and the roles that see a report's
# `reporter_id`. ONE constant, because those two rules must not drift apart: a
# moderator who can act on a report but cannot see who filed it, or worse the
# reverse, is a permission model that only looks like one.
#
# Here rather than in core/auth.py so app/schemas/report.py can import it
# without pulling the auth stack into a schema module.
MODERATOR_ROLES: tuple[str, ...] = (Role.maintainer.value, Role.club_admin.value)


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True)

    # native_enum=False keeps this out of Postgres's `CREATE TYPE ... AS
    # ENUM`, which is the one column type whose values cannot simply be
    # altered later: adding a role means ALTER TYPE ... ADD VALUE, which
    # cannot be undone in a transaction. Worth keeping now that Postgres is
    # the only engine, for that reason rather than the portability one it
    # was originally chosen for.
    #
    # What it actually renders is a bare VARCHAR(20) - *not* VARCHAR + a
    # CHECK constraint, which is what a comment here claimed until the
    # migration was first inspected on a real Postgres. SQLAlchemy has
    # defaulted `create_constraint` to False since 1.4. So the allowed values
    # are enforced in Python (this Enum on the way in and out, plus the
    # pydantic schemas at the API boundary) and not by the database. Adding
    # the constraint is a migration and a decision, not a keyword: see the
    # note in backend/README.md's Migrations section.
    role = Column(Enum(Role, native_enum=False, length=20), nullable=False, default=Role.hiker)

    display_name = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)
