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
# below - not a style preference, a worked-around DuckDB/duckdb-engine gap
# in the same spirit as the ones backend/README.md already documents:
# fetching a `TIMESTAMPTZ` column back through duckdb-engine requires the
# optional `pytz` package (`InvalidInputException: Required module 'pytz'
# failed to import`), which isn't otherwise a dependency of this backend.
# Storing naive UTC (`DateTime(timezone=True)` -> plain `DateTime`, with
# tzinfo stripped before insert) sidesteps that entirely and is portable to
# Postgres too, since every value going in is already UTC by construction.


class Role(str, enum.Enum):
    hiker = "hiker"
    maintainer = "maintainer"
    club_admin = "club_admin"


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True)

    # native_enum=False renders as VARCHAR + CHECK constraint rather than a
    # dialect-native `CREATE TYPE ... AS ENUM` - portable across both the
    # DuckDB-local and Postgres-CI/production engines this backend runs
    # against (see backend/README.md's "DuckDB locally, Postgres in CI and
    # production" section for the general reasoning), rather than relying on
    # DuckDB's PostgreSQL-derived compiler to handle a Postgres-native type
    # the same way Postgres itself would.
    role = Column(Enum(Role, native_enum=False, length=20), nullable=False, default=Role.hiker)

    display_name = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)
