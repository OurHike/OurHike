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

    # When this account was deleted at the hiker's own request, or null for
    # a live account (#895, features/ACCOUNT_SYNC.md phase E).
    #
    # WHY THE ROW SURVIVES ITS OWN DELETION, WHICH LOOKS BACKWARDS
    #
    # `DELETE FROM profiles` is what "delete my account" sounds like, and it
    # is the one thing this table cannot do. Five other tables hold a NOT
    # NULL foreign key to this id on rows that are somebody else's business
    # as much as the hiker's - a closure other hikers are routing around, a
    # condition report, a photo under an irrevocable CC BY-SA 4.0 grant
    # (#577), an hour a club already stood behind. Deleting the row means
    # either taking those with it or leaving a dangling key.
    #
    # Nulling the links instead was tried on paper and does not survive
    # contact with `poi_photos`: its R2 object key is DERIVED from
    # `contributor_id` (core/photos.py `poi_photo_key`), so a null there
    # makes the photograph we just promised to keep unreachable, and its
    # `uq_poi_photos_poi_contributor` unique constraint means a shared
    # "deleted hiker" sentinel row would collide the moment two deleted
    # accounts had photographed the same shelter.
    #
    # So what is deleted is the PERSON, not the key. After
    # `core/account_deletion.py` runs, this row holds an id, a creation
    # date and this stamp: no trail name, no role, nothing that says who it
    # was, and `core/auth.py` refuses to let anyone sign back into it. The
    # published rows keep pointing at an account that no longer belongs to
    # anybody. That is what "the link goes, the contribution stays,
    # unattributed" can actually mean given the keys above.
    #
    # The honest limit, stated because it is invisible from here: this
    # backend cannot delete the Supabase Auth user itself. That needs a
    # service-role key, and app/config.py has none - only the anon key and
    # the JWKS. See features/AUTHENTICATION.md.
    deleted_at = Column(DateTime, nullable=True)
