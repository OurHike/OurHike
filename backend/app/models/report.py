"""The `report` table - community-submitted trail condition reports.

See ../../../features/REPORT_A_PROBLEM.md for the full feature this
mirrors: six report types covering trail/infrastructure conditions, one
location mechanism (an existing map POI id, or a dropped/GPS pin), and a
status/visibility pair that feeds the moderation queue MAP_OPTIONS.md's
closures and HIKER_SAFETY.md's warning escalation both reuse rather than
building a second review workflow (see that doc's "Architecture fit"
section).

`poi_id` is deliberately a plain nullable string, not a SQLAlchemy
`ForeignKey` - it's a soft reference into the pipeline's static POI export
(e.g. "atc_shelters:12345"), a dataset that lives outside this database
entirely (see ../../../TECHNICAL_ARCHITECTURE.md), so there's no local
table for a real FK to point at.

`visibility` is set server-side from `type` alone, never accepted from the
client: `bad_hikers` reports on *people*, not trail conditions - a
meaningfully different risk profile (REPORT_A_PROBLEM.md's "Bad hikers
needs different handling" section) - so it defaults to `internal_only`
while the other five types default to `public`. `severity` likewise has no
client-facing input in v1; it stays `normal` until a later verify action
(HIKER_SAFETY.md's moderator-escalated severity tier, built elsewhere) can
raise it - there's no field for it on the create schema at all.

See app/models/profile.py for the naive-UTC convention every datetime
column here follows, and the open question about it.
"""

import enum
import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text

from app.core.time import utc_now
from app.db.base import Base


class ReportType(str, enum.Enum):
    blowdown = "blowdown"
    trash = "trash"
    bad_hikers = "bad_hikers"
    flooding = "flooding"
    shelter_repair = "shelter_repair"
    animals = "animals"
    # Problem plants or animals disrupting the local environment
    # (../../../features/REPORT_A_PROBLEM.md, 2026-07-30). Deliberately
    # separate from `animals`, which is scoped to SAFETY encounters and is
    # what HIKER_SAFETY.md escalates to severity=serious. An invasive report
    # is an ecological observation with no personal-risk dimension; folding
    # the two together would either dilute the safety signal or treat a plant
    # sighting as a hazard.
    invasive_species = "invasive_species"
    # A comment about a specific place, not a condition report - see
    # ../../../features/SAYING_THANKS.md. Shares every field; diverges in
    # visibility (club_only), states, and in skipping the moderation queue.
    thanks = "thanks"


class ReporterType(str, enum.Enum):
    thru = "thru"
    section = "section"
    day = "day"
    maintainer = "maintainer"


class ReportStatus(str, enum.Enum):
    submitted = "submitted"
    verified = "verified"
    # Load-bearing and, today, unreachable (#257): the public-visibility rule
    # deliberately keeps resolved reports visible ("it reads as 'Fixed'",
    # routers/reports.py) and the client maps it (lib/reportStatus.ts), but no
    # endpoint sets it - the lifecycle dead-ends at verified/dismissed. The
    # resolve action belongs to the moderator surface (#235); until that
    # lands, "Fixed" is a state the vocabulary holds open rather than one a
    # report can wear.
    resolved = "resolved"
    dismissed = "dismissed"


class Visibility(str, enum.Enum):
    public = "public"
    # Goes to safety moderators. Named for the bad_hikers case.
    internal_only = "internal_only"
    # Goes to the club and the maintainer - a different audience, for a
    # different reason (morale, not risk). Kept distinct from internal_only
    # so "who can see this" never depends on also reading the type.
    club_only = "club_only"


class Severity(str, enum.Enum):
    normal = "normal"
    serious = "serious"


class LocationSource(str, enum.Enum):
    """How a report came by its `lat`/`lon` (#1563).

    Three ways the client can place a report, and a moderator reads each one
    differently: `poi` is a named waypoint the hiker chose, so the coordinates
    are the waypoint's and the report is ABOUT that place; `gps` is the phone's
    own fix at the moment of filing, with `location_accuracy_m` and
    `location_fix_age_s` saying how much to trust it; `map` is a spot the hiker
    marked by hand on the map, which is as exact as their finger at that zoom
    and carries no radius at all.

    Null on every row filed before this existed and on a report with no
    coordinates. A row with coordinates and no source is a row from an older
    client, not a fourth kind of placement.
    """

    poi = "poi"
    gps = "gps"
    map = "map"


class SignedNameKind(str, enum.Enum):
    """Which of a hiker's names a report is signed with (#1563).

    `trail` is the pseudonym features/IDENTITY_AND_PRIVACY.md calls "the
    identity actually shown to others, never a hiker's real name by default";
    `real` is the hiker choosing, for this one report, to put their real
    name behind it - so a club can address them by it when it follows up.
    The default is the trail name, and the choice is per report: nothing
    here changes what any other surface shows.
    """

    trail = "trail"
    real = "real"


class Report(Base):
    __tablename__ = "reports"

    # A Python-generated UUID string primary key, not a DB-generated
    # integer one - the same shape Profile.id already uses (see profile.py,
    # where the id is Supabase's `auth.users` id and so is not this
    # database's to mint). Reports keep it because a client can name its own
    # id before the row exists, which is what makes the idempotent retry in
    # routers/reports.py possible at all.
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # index=True on the columns every hot query filters on (#658,
    # a1b7c3d95e04): the public list scans status, "my reports" scans
    # reporter_id. Cheap while the tables are small, which is exactly
    # when adding them is a one-line decision instead of an incident.
    reporter_id = Column(String, ForeignKey("profiles.id"), nullable=False, index=True)

    # native_enum=False, matching Profile.role's exact pattern - see
    # profile.py for why a native enum is the harder one to change later,
    # and for what this really renders as on Postgres (a bare VARCHAR: the
    # values are enforced in Python, not by the database).
    type = Column(Enum(ReportType, native_enum=False, length=20), nullable=False)

    # Location reference: either poi_id (a soft reference, see module
    # docstring) or a dropped/GPS pin (lat/lon) - never both required,
    # neither enforced exclusive here since v1 doesn't need that rule
    # policed server-side yet.
    poi_id = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)

    # Where along the centerline, in miles from the southern terminus (#244).
    #
    # **Client-supplied, and derived rather than measured** - the report form
    # snaps the GPS fix to the trail index it already holds and has been
    # computing this value, showing it ("mi 1,407.2"), and then dropping it at
    # submit. Same trust posture as `authored_at`: a claim, bounded at the one
    # end that can be bounded (see ReportCreate), with the server's own
    # `lat`/`lon` alongside it.
    #
    # **Nullable, and null is the ordinary state rather than a gap.** There is
    # no mile when the fix is off-trail, when the trail index has not been
    # downloaded yet, or for every row filed before this column existed. A
    # zero would be Springer Mountain, which is why it is not the default.
    #
    # Nothing server-side derives it, and nothing can: this backend holds no
    # centerline geometry - the trail is a published artifact the client and
    # the pipeline share, not a table here. That is why carrying it costs a
    # column rather than a function.
    mile = Column(Float, nullable=True)

    # HOW THE COORDINATES WERE ARRIVED AT, AND HOW FAR TO TRUST THEM (#1563).
    #
    # `lat`/`lon` alone cannot say whether they are a waypoint's surveyed
    # position, a GPS fix, or a thumb on a map - and a moderator weighing a
    # blowdown at 35.6123, -83.4987 needs to know which. So the source travels
    # with the coordinates, and for a fix so do the two things that bound it:
    #
    # `location_accuracy_m` - the radius the platform stated for the fix, in
    # metres, as `position.coords.accuracy` gives it. The W3C Geolocation
    # definition is a 95% confidence radius; the client records only the web
    # watch here (lib/useGeolocation.ts), never the native plugin's 68% figure
    # that lib/gpsTrace.ts keeps apart for exactly this reason, so one column
    # is honest. Metres rather than feet because that is the unit the platform
    # hands over - CONTRIBUTING.md's store-canonical rule.
    #
    # `location_fix_age_s` - how many seconds old the fix was when the report
    # was filed with it. The client's watch deliberately keeps the last fix
    # through a pocketed pause (#313), so a report filed the moment the phone
    # comes out of a pack can carry a fix from a mile back; a radius of 5 m on
    # a fix from forty minutes ago is not 5 m of anything. The age is what
    # lets a reader tell those two apart.
    #
    # **All three are client claims, stored as sent.** Nothing server-side can
    # check a radius against a fix it never saw, and the same trust posture as
    # `mile` and `authored_at` applies: bounded at the one end that can be
    # bounded (a negative radius or age is refused at the wire, see
    # ReportCreate), and never re-derived.
    #
    # **Nullable, and null is the ordinary state rather than a gap.** Every
    # row filed before this existed has none; a report anchored to a waypoint
    # or marked on the map has a source and no radius, because there was no
    # fix to state one for. Zero is not the default for the reason `mile`
    # gives: a 0 m radius is a claim of perfect knowledge, which no phone has
    # ever made, and an age of 0 s says the fix arrived as the tap landed.
    location_source = Column(Enum(LocationSource, native_enum=False, length=20), nullable=True)
    location_accuracy_m = Column(Float, nullable=True)
    location_fix_age_s = Column(Integer, nullable=True)

    reporter_type = Column(Enum(ReporterType, native_enum=False, length=20), nullable=False)

    # WHO THE REPORT IS SIGNED BY, IN THE HIKER'S OWN CHOICE OF NAME, and
    # whether they may be contacted about it (#1563, the maintainer's ask of
    # 2026-09-17).
    #
    # `reporter_id` already says which account filed this, and a moderator can
    # follow it to a profile whose `display_name` is the trail name. What it
    # cannot say is what the hiker wanted to be called on THIS report: the
    # trail name they hike under, or the real name they chose to put behind a
    # report about something serious. `signed_name` is that text as sent, and
    # `signed_name_kind` says which of the two it is - so "Jane Doe (real
    # name)" and "Switchback (trail name)" read as the different claims they
    # are.
    #
    # `contact_ok` is consent, and only consent: "You can contact me for more
    # information", ticked by the hiker. It carries no way to reach them - the
    # account does, through whoever holds the Supabase Auth mapping - and
    # false is the default because an unticked box is not a yes.
    #
    # **Never public.** ReportOut withholds all three from anyone who is not
    # the reporter or a moderator, the same rule as `reporter_id`: a name
    # beside a trail position and a time is exactly the linkability
    # features/IDENTITY_AND_PRIVACY.md exists to prevent, and the anonymous
    # attribution stays `reporter_type` alone. The conditions publisher's
    # column list (pipeline/export_conditions.py) never selects them.
    #
    # **Cleared when the account is deleted** (app/core/account_deletion.py),
    # the way an app-failure report's `contact` is: the report stays, because
    # other people rely on it, and the name and the consent go, because they
    # were offered by a person who is gone.
    signed_name = Column(Text, nullable=True)
    signed_name_kind = Column(Enum(SignedNameKind, native_enum=False, length=20), nullable=True)
    contact_ok = Column(Boolean, nullable=False, default=False, server_default="false")

    # When the report was WRITTEN. WIREFRAMES.md is explicit that this is
    # "the moment of writing, not of sending" - a report composed offline on
    # Monday and synced on Thursday must read as Monday, or a maintainer
    # mis-prioritises it and a `bad_hikers` timeline is distorted. The client
    # supplies it via `ReportCreate.authored_at`; the server falls back to now
    # when it is absent, and refuses a future-dated claim outright.
    timestamp = Column(DateTime, nullable=False, default=utc_now)

    # When the server actually received it - always server truth, never the
    # client's claim. Keeping both is what lets a genuinely three-day-old
    # report be told apart from a backdated one.
    received_at = Column(DateTime, nullable=False, default=utc_now)

    note = Column(Text, nullable=True)
    photo_url = Column(String, nullable=True)

    # HOW MANY PHOTOS THIS REPORT HOLDS (#1439).
    #
    # The objects are `reports/{id}/1.jpg` ... `reports/{id}/{photo_count}.jpg`
    # and their keys stay derived, which is app/core/photos.py's whole design:
    # "which objects belong to this report" is answerable from the id alone,
    # and reconciliation is a set difference rather than a join. This column
    # supplies the only part of that the id cannot - how far the numbering
    # runs. It is the authoritative half; the objects are derived and
    # disposable, in that direction and never the reverse.
    #
    # Not a `report_photos` table, and the reason is that a table would carry
    # nothing a row does not already say. Every field such a table would hold
    # - the report, the index, the key - is derivable, so it would be a join
    # whose only content is a count.
    #
    # `photo_url` IS STILL WRITTEN, and is deliberately not replaced in this
    # revision. tests/test_migration_expand_contract.py enforces RELEASING.md
    # §8c: a column dropped in the same release that stops writing it breaks
    # the previous release, which is still running during the rollout. So the
    # invariant for now is stated once, here, and kept in one function
    # (`_record_photo` in routers/reports.py): `photo_url` is `photo_key(id, 1)`
    # exactly when `photo_count >= 1`, and null otherwise. Dropping it is a
    # later revision's work.
    photo_count = Column(Integer, nullable=False, default=0, server_default="0")

    # WHERE THIS WAS, IN THE HIKER'S OWN WORDS (#1439, D16).
    #
    # Only ever set for a report with no coordinates and no `poi_id` - a phone
    # that never got a fix, filing about a place it cannot name any other way.
    # "The brook crossing about half a mile north of Fitzgerald Falls."
    #
    # **NEVER GEOCODED, and that is the point of storing prose rather than
    # resolving it.** A typed name turned into coordinates is a confident wrong
    # dot on every phone that downloads the report, which is the exact failure
    # the omitted-not-zeroed rule on `lat`/`lon`/`mile` exists to prevent -
    # 0,0 is the Atlantic off West Africa and mi 0 is Springer Mountain. So
    # `lat`, `lon` and `mile` stay null beside this: a moderator reads the
    # words and places it, and the app does not guess.
    place_words = Column(Text, nullable=True)

    # Structured, type-specific follow-up fields (species/count for
    # animals, depth for flooding, etc.) - always empty in v1 (see
    # REPORT_A_PROBLEM.md's "Follow-up info, phased" section); the column
    # exists now so it can be populated later without a schema rewrite.
    follow_up = Column(JSON, nullable=True)

    status = Column(
        Enum(ReportStatus, native_enum=False, length=20),
        nullable=False,
        default=ReportStatus.submitted,
        index=True,
    )

    # Server-controlled from `type` alone - see module docstring. No
    # column-level default: the router always computes and sets this
    # explicitly rather than relying on an implicit fallback.
    visibility = Column(Enum(Visibility, native_enum=False, length=20), nullable=False)

    # Server-controlled; only the verify action can raise this to `serious`
    # - no field on the create schema at all. That action leaves it ALONE
    # when a moderator says nothing about it, which it did not always do:
    # see app/schemas/moderation.py's ReportVerifyRequest for what a silent
    # de-escalation cost (#251).
    severity = Column(Enum(Severity, native_enum=False, length=20), nullable=False, default=Severity.normal)

    # Who moderated this, and when. The same pair `closure` has carried from
    # the start, added here because it was missing on the resource where the
    # question matters most: a `bad_hikers` report names a person, and "who
    # decided this was serious" had no answer at all.
    #
    # Nullable because most reports have never been through moderation -
    # `status` starts at `submitted` and a great many stay there. Null means
    # "nobody has verified this", which is exactly what `status` already
    # says; these two answer WHO and WHEN, not WHETHER.
    #
    # Deliberately NOT on the public `ReportOut`. Surfacing an audit trail is
    # the moderation surface's job (#235), and putting a moderator's profile
    # id into the anonymous `GET /reports` payload would walk straight into
    # the leak #252 is already open about.
    verified_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)

    # The other two thirds of the moderation trail (#658, f2c8d4a91e57).
    # verified_* records the FIRST escalation and is never overwritten - who
    # first marked a dangerous-person report serious is the fact an audit
    # needs. dismissed_* records the LATEST removal - "who took this down"
    # means the operative decision. resolved_* records who declared the
    # hazard cleared, which is what finally makes ReportStatus.resolved
    # reachable rather than a state the vocabulary held open.
    dismissed_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    dismissed_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Optional attribution for a `thanks` (SAYING_THANKS.md). Both may be
    # empty: "someone cleared forty blowdowns and I have no idea who" is a
    # complete thanks, resolved by location instead of being refused.
    maintainer_id = Column(String, ForeignKey("profiles.id"), nullable=True)
    club_id = Column(String, ForeignKey("clubs.id"), nullable=True)
