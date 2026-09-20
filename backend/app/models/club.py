"""The `clubs` table - a maintaining organization, and who administers it.

`Club` is a first-class concept already anticipated by FEATURES.md's
multi-club support (value #7) and sketched in
../../../features/VOLUNTEERING.md. It arrived here for
../../../features/SAYING_THANKS.md, which needed somewhere for a thanks to go
when the hiker knows the club but not the person - the common case.

**`Org` is this table's name in the UI, and only in the UI.** Not every
organization that maintains a trail is a club: OPRHP is a state agency,
Mohonk is a preserve, and a land trust is neither. Renaming the table would
be a migration across every existing foreign key to buy a word, so
../../../features/ORG_ONBOARDING.md's conflict 2 keeps the route at `/clubs`
and the rename where it costs nothing.

**What onboarding added, and why each column is here rather than derived.**
Until 2026-09-17 this model held id, name and region, with a comment saying
admin tooling was VOLUNTEERING.md's larger module and would not be invented
on the strength of one feature needing a name. That module is now being
built, and these are the columns it needs:

- `slug` is the readable id in every route (`/org/ramapo-trail-conference`),
  every embed's `data-org`, and every pull-request path. A surrogate UUID in
  a URL an organization pastes onto its own website is a worse answer than a
  name, and the decision was taken deliberately early because everything
  links to it.
- `domain` plus `verified_by` is how we know an organization is itself. At
  least one admin must hold an email at `domain`; DNS is the stronger proof
  and email the one most organizations can actually complete today.
- `state` is what makes claiming coherent. An **unclaimed** org has live
  trails and no admins - which is exactly what every source a maintainer
  registered by hand looks like today (33 of them across nine organizations,
  counted 2026-08-27 in SOURCE_REGISTRY.md). Claiming is the migration path
  for the registry we already have, not a new concept.
- `membership_url` and `donation_url` are the whole of the money model.
  ONBOARDING.md records the maintainer's 2026-08-27 correction - *"There is
  no funding model today for the orgs"* - so OurHike holds nothing, takes
  nothing and links to theirs.
- `assist_opted_in_at`, `assist_opted_in_by` and `assist_opted_out_at` are
  one organization's answer to "may a model read our registry". The assist
  panels send section names, trail names, mileages and the coverage gap list
  to a third party at api.anthropic.com, and until 2026-09-17 nothing here
  recorded whether anybody had agreed to that. Off is the state of every row
  that has not said otherwise, including every row that predates the column.
"""

import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint

from app.core.time import utc_now
from app.db.base import Base


class OrgState(str, enum.Enum):
    """Where an organization is between "we hold its data" and "it holds its data".

    `frozen` is the one worth explaining: two people at the same domain
    claiming the same org is not a race to be won, so a contested claim stops
    and waits for a person. It has no automatic exit by design - a timer here
    would resolve the contest in favour of whoever was patient.

    `pending` is the newer one and the easiest to confuse with `unclaimed`.
    They are opposites. An `unclaimed` org is REAL and nobody has taken it -
    a maintainer wrote its row, hikers walk its trails, and it is public for
    exactly that reason. A `pending` org is one somebody registered where
    the only address at its domain is one THEY TYPED for a colleague: the
    organization may not know it has been registered, so nothing about it is
    published and `verified_by` stays null until a person who actually holds
    an address there approves a seat (`routers/clubs.py`'s `approve_seat`).

    Adding a value here needs no migration: the column renders as a bare
    VARCHAR(20), not an enum type or a CHECK constraint - see the note on
    `Profile.role`, which was checked against a real Postgres.
    """

    unclaimed = "unclaimed"
    pending = "pending"
    claimed = "claimed"
    frozen = "frozen"
    deleted = "deleted"


class VerifiedBy(str, enum.Enum):
    dns = "dns"
    email = "email"


class Club(Base):
    __tablename__ = "clubs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    region = Column(String, nullable=True)

    # Unique because it is an address. Nullable because rows predate it: the
    # migration backfills every existing row from its name, and a row that
    # arrives some other way later should fail loudly at the route rather
    # than silently answer as some other org.
    slug = Column(String, nullable=True, unique=True, index=True)

    domain = Column(String, nullable=True)
    website = Column(String, nullable=True)
    verified_by = Column(Enum(VerifiedBy, native_enum=False, length=10), nullable=True)

    state = Column(
        Enum(OrgState, native_enum=False, length=20),
        nullable=False,
        default=OrgState.unclaimed,
    )

    membership_url = Column(String, nullable=True)
    donation_url = Column(String, nullable=True)

    # WHETHER THIS ORGANIZATION HAS AGREED THAT A MODEL MAY READ ITS OWN
    # REGISTRY. Three columns rather than one boolean, and the extra two are
    # the point: a flag says what is true now and nothing about who decided
    # it, so an organization asking "who agreed to this, and when" would get
    # an answer nobody could produce. The shape is `OrgAdmin`'s - two
    # timestamps, the later one standing, both kept so the sequence reads.
    #
    # Nullable and null by default, which is the whole of the default: an
    # organization that has never been asked has not agreed.
    assist_opted_in_at = Column(DateTime, nullable=True)
    assist_opted_in_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    assist_opted_out_at = Column(DateTime, nullable=True)

    # Who registered or claimed it. Null for the orgs that got here because a
    # maintainer wrote a row in pipeline/sources.json, which is most of them.
    created_by = Column(String, ForeignKey("profiles.id"), nullable=True)

    created_at = Column(DateTime, nullable=False, default=utc_now)

    @property
    def assist_opted_in(self) -> bool:
        """Has this organization agreed, and not since withdrawn.

        Read by `app/core/assist.py`'s `ask` before any request leaves this
        process, and published as one boolean on `OrgOut`. The two dates and
        the person stay behind the admin gate - what an organization
        publishes about itself is public, and which of its admins clicked
        which button on which day is not.

        **A TIE IS OFF.** Two timestamps equal to the microsecond is not a
        state anybody reaches by clicking, so it means a row edited by hand
        or a clock that went backwards. Of the two ways to be wrong here,
        sending an organization's registry to a third party that never agreed
        to it is the one that cannot be taken back.
        """
        if self.assist_opted_in_at is None:
            return False
        if self.assist_opted_out_at is None:
            return True
        return self.assist_opted_out_at < self.assist_opted_in_at


class OrgAdmin(Base):
    """One person's seat at one organization - the first role this backend can grant.

    See ../../../features/ORG_ONBOARDING.md, and #1169, which measured on
    2026-08-28 that **no router in `app/routers/` assigns a role at all**:
    `core/auth.py` sets `Profile.role` once when a profile is provisioned and
    nothing ever changes it. This table is where that stops being true, and
    it is org-scoped rather than global on purpose - "club admin" is not a
    fact about a person, it is a fact about a person and an organization, and
    the same human is a trails chair at one and a maintainer at another.

    **A decline pauses the org and is reversible - it is never a rejection.**
    `declined_at` and `decline_reason` exist so the console can say who has
    not answered and why, and `approved_at` can still be set afterwards. The
    common cause of a decline is a secretary who does not know what OurHike
    is, not a board that said no, and a model that treated the two the same
    would make the recoverable case look final.

    **`is_codeowner` is the three-approvals rule.** Registry changes need all
    three codeowners; everything else needs one admin. Three-for-everything
    makes small corrections cost more than they are worth, and the
    corrections then stop happening.
    """

    __tablename__ = "club_admins"
    __table_args__ = (UniqueConstraint("club_id", "person_id", name="uq_club_admins_club_person"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Both indexed: the console reads "who administers this org" on every
    # page load, and the sign-in path reads "which orgs does this person
    # administer" to build the org switcher.
    club_id = Column(String, ForeignKey("clubs.id"), nullable=False, index=True)
    person_id = Column(String, ForeignKey("profiles.id"), nullable=False, index=True)

    # Their job at the organization, in their own words - "Trails chair",
    # "Secretary". Display only; nothing branches on it.
    title = Column(String, nullable=True)

    is_codeowner = Column(Boolean, nullable=False, default=True)

    invited_at = Column(DateTime, nullable=False, default=utc_now)
    approved_at = Column(DateTime, nullable=True)
    declined_at = Column(DateTime, nullable=True)
    decline_reason = Column(Text, nullable=True)
