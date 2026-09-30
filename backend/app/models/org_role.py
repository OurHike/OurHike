"""Roles an organization defines, and the invitations that grant them.

See ../../../features/ORG_ONBOARDING.md's data model and permissions table,
and #1169, whose first three problems this answers for org-scoped roles.

**Why a role is a row here and not a value in `Profile.role`.** #1169
decided on 2026-08-28 that `Profile.role` should become a set, because "a
club admin who also coordinates invasives has to pick, will pick
`club_admin`, and the next person to hit the wall widens some gate to
unblock themselves." That reasoning is right and it points somewhere this
model goes further: **almost every role in this design is a fact about a
person *and an organization*, not about a person.** Somebody is a supervisor
at Ramapo and a maintainer at Hudson Highlands, and no set of global enum
values can say that without inventing a value per organization.

So: `Profile.role` stays what it is - the platform role that gates
moderation - and org-scoped permission lives here and in `club_admins`. The
part of #1169 this does **not** close is that global column, and its problem
4 (two different things called `maintainer`) is untouched because what the
self-declared one should be renamed to is not decided.

**A retired role keeps its holders' history; only an unheld role is
deletable.** `retired_at` rather than a delete is the same rule
`MaintainerAssignment` already follows: the questions that matter are
historical - who held this in June, who should hear about a report written
three weeks ago - and a deleted row destroys the answer every time.
"""

import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, false

from app.core.time import utc_now
from app.db.base import Base


class RoleCategory(str, enum.Enum):
    """The three groupings the design's Roles screen sorts by.

    They are the organization's own vocabulary rather than ours - NYNJTC
    sorts its volunteer roles this way - and they are an enum rather than
    free text because the screen groups by them and a fourth spelling of
    "Trail maintenance" would silently split a group in two.
    """

    trail_maintenance = "trail_maintenance"
    stewards = "stewards"
    environmental = "environmental"


class OrgRole(Base):
    """One job an organization defines, optionally tied to one section."""

    __tablename__ = "org_roles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    club_id = Column(String, ForeignKey("clubs.id"), nullable=False, index=True)

    name = Column(String, nullable=False)
    category = Column(Enum(RoleCategory, native_enum=False, length=30), nullable=False)

    # The reporting line, as a self-reference. Null means the role reports to
    # nobody inside the org's volunteer structure - a trails chair, usually.
    reports_to_role_id = Column(String, ForeignKey("org_roles.id"), nullable=True)

    # A role can be tied to one section (maintainer of Pine Meadow North) or
    # to none (sawyer, who goes wherever the saw is needed). Nullable is the
    # common case rather than the exception.
    section_id = Column(String, ForeignKey("org_sections.id"), nullable=True, index=True)

    # A mandate the org inherits rather than chose - ATC requiring corridor
    # monitors of its member clubs is the real case. `required_by` names who
    # requires it, so the console can say "required by the ATC" rather than
    # showing a bare flag nobody can act on.
    required = Column(Boolean, nullable=False, default=False)
    required_by = Column(String, nullable=True)

    retired_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class RoleInvite(Base):
    """A grant waiting for somebody who has not signed in yet.

    #1169's problem 3, and its decided answer: **OurHike cannot create a
    user, deliberately.** `core/auth.py`'s `_get_or_create_profile`
    provisions a row from the JWT's `sub`, and minting a Supabase Auth user
    needs a service-role key `app/config.py` pointedly does not hold - "a
    credential that can act as any user", per AUTHENTICATION.md. So the
    pattern is invite, not create.

    An org loads a roster of two hundred people, most of whom have never
    opened OurHike. Each becomes a row here keyed by email, and the grant is
    applied the moment that person first signs in and a profile row is
    created for them.

    **Email-matching is sound only because the provider verifies it.**
    AUTHENTICATION.md already treats a provider-verified email as "a Provider
    fact to trust", and Google/Apple both verify. It would not hold for a
    self-hosted provider that skips verification, which is a constraint on
    where this backend may be deployed rather than a bug here.

    The email is stored lowercased (`accepted_email` on the way in) because
    an address is case-insensitive in practice and a roster upload will
    contain both spellings of the same person.
    """

    __tablename__ = "role_invites"
    __table_args__ = (UniqueConstraint("club_id", "email", "role_id", name="uq_role_invites_club_email_role"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    club_id = Column(String, ForeignKey("clubs.id"), nullable=False, index=True)

    # Indexed because the hot query is the one every first sign-in runs:
    # "is there anything waiting for this address?"
    email = Column(String, nullable=False, index=True)

    role_id = Column(String, ForeignKey("org_roles.id"), nullable=True)

    # Their name as the org knows it, so a roster can show a person before
    # they have ever set a trail name. Overwritten by nothing: once they sign
    # in, `Profile.display_name` is theirs and this stays as the org's label.
    full_name = Column(String, nullable=True)
    note = Column(Text, nullable=True)

    invited_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    invited_at = Column(DateTime, nullable=False, default=utc_now)

    # Set when the invite was applied to a real profile. A claimed invite is
    # kept rather than deleted: it is the audit row saying where a person's
    # role came from, which is the question an org asks when somebody turns
    # out to hold something they should not.
    claimed_at = Column(DateTime, nullable=True)
    claimed_by = Column(String, ForeignKey("profiles.id"), nullable=True)

    # WHETHER THIS INVITE OFFERS A SEAT AT THE ORGANIZATION. Explicit since
    # #1635 - The organization console's new endpoints trust self-registered
    # orgs with maintainer powers, seats and mail. Before it, "no `role_id`"
    # meant "admin invitation", and `invite_volunteer` (reachable by a
    # supervisor) and `sync_roster` (an unmatched role name) both wrote that
    # shape, so an invitation meant as "a volunteer whose role is not decided
    # yet" arrived as a seat. Only `routers/clubs.py`'s admin paths set this.
    grants_admin_seat = Column(Boolean, nullable=False, default=False, server_default=false())


class RosterSyncRun(Base):
    """One roster load, and what it was allowed to do.

    The audit row ORG_ONBOARDING.md's roster decision requires: roster and
    assignments write over HTTP under RLS, **with an audit row for every sync
    run - who, when, what changed.**

    **`deactivations_held` is the guardrail, and it is the one column here
    that does real work.** A run that would deactivate more than
    `DEACTIVATION_HOLD_FRACTION` of an org's active assignments applies its
    additions and holds its deactivations for an admin to look at. A changed
    API field at 4am must not release three hundred roles and blank the
    coverage report before anyone wakes up.
    """

    __tablename__ = "roster_sync_runs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    club_id = Column(String, ForeignKey("clubs.id"), nullable=False, index=True)

    # Who ran it. Null for a scheduled pull from an org's own endpoint, which
    # is the case the hold exists for.
    run_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    source = Column(String, nullable=False)

    added = Column(String, nullable=False, default="0")
    updated = Column(String, nullable=False, default="0")
    deactivated = Column(String, nullable=False, default="0")
    deactivations_held = Column(String, nullable=False, default="0")

    ran_at = Column(DateTime, nullable=False, default=utc_now)


# The fraction of an org's active assignments a single sync run may
# deactivate before its deactivations are held for a person.
#
# @unvalidated - picked, not measured. It comes from the design prototype and
# nothing has ever run a roster sync against a real organization's feed. What
# would settle it: the distribution of how much one normal run actually
# changes, across a season, for an org of a few hundred volunteers. The
# failure mode of getting it too low is worse than it sounds - a threshold
# below the normal churn of a seasonal roster holds every run for an admin,
# which is the same as having no sync at all.
DEACTIVATION_HOLD_FRACTION = 0.10
