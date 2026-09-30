"""The keys and the log behind the management-console embed.

See ../../../features/ORG_ONBOARDING.md's "Console embed auth" and #1542.

**What this is for.** An organization pastes the management console into
their own members area. Their server posts the signed-in person's email plus
a secret key to `POST /console/session`, and gets back a token scoped to one
person, one org and one origin, good for fifteen minutes. They send only the
email - we resolve roles from the roster - so **their system never mirrors
our permissions** and cannot drift out of step with them.

**This is a first-party credential rendering an org's roster on a third-party
origin, and nobody has security-reviewed it.** The maintainer's call on
2026-09-17 was to build all four embeds including this one, against a
recommendation to stop at the three public ones. So it ships **configured
off** - `console_embed_enabled` defaults False in app/config.py, the same
posture the five `R2_PHOTO_*` settings already take, where leaving them unset
is a valid deployment that simply cannot serve photos. Switching it on is a
deliberate act after a review, not a consequence of a merge.

**The six guards, and where each one lives:**

1. *The public key alone opens nothing.* `public_key` identifies the org to
   the pasted snippet; only `secret_hash` authorises, and it never leaves the
   org's server.
2. *Origins are allow-listed.* `allowed_origins` here, checked per request.
3. *Tokens expire in 15 minutes.* `CONSOLE_TOKEN_TTL_SECONDS`, signed, not
   stored - a stored session would be a fifth thing to revoke.
4. *Two keys live at once.* Rotation is "add the second, swap the server,
   delete the first", with no window where the org's page is broken. The
   unique constraint is on the key, not on the org.
5. *Every token request is logged with its origin.* `ConsoleTokenGrant`.
6. *A new key is read-only until write is deliberately granted.*
   `can_write` defaults False, which is the guard that means a leaked key
   pasted into a public page cannot change anything.

**The secret is stored as a hash, never as itself.** It is shown once, at
creation, and if the org loses it they rotate rather than recover - the same
trade every API key in the world makes, for the same reason: a secret this
database could print is a secret a database dump discloses.
"""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text

from app.core.time import utc_now
from app.db.base import Base

# How long a console token is good for. Fifteen minutes is short enough that
# a leaked one is worth little and long enough that a person reading a roster
# does not get thrown out mid-task; a page that needs longer asks for another.
#
# @unvalidated as a number - it is the design's figure, and nobody has watched
# a real session to see how long an admin actually spends on one of these
# screens. What would settle it: the distribution of time-on-page for the
# console screens once any org uses them. Erring short is the safe direction,
# which is why it is not being raised on a guess.
CONSOLE_TOKEN_TTL_SECONDS = 15 * 60


class ConsoleKey(Base):
    __tablename__ = "console_keys"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    club_id = Column(String, ForeignKey("clubs.id"), nullable=False, index=True)

    # What the pasted snippet carries. Public by construction - it is in the
    # HTML of somebody's website - and it authorises nothing on its own.
    public_key = Column(String, nullable=False, unique=True, index=True)

    # SHA-256 of the secret. See the docstring: the secret itself is shown
    # once and never stored.
    secret_hash = Column(String, nullable=False)

    # A human label, so an org rotating keys can tell which is which:
    # "members area", "staging".
    label = Column(String, nullable=True)

    # Newline-separated exact origins ("https://ramapotrails.org"). Exact,
    # scheme included, because a wildcard here is the whole guard undone -
    # the same lesson `client/scripts/screenshot.mjs` records about R2's
    # allowlist reflecting an exact `Origin` rather than sending `*`.
    allowed_origins = Column(Text, nullable=False, default="")

    # Guard 6. A new key reads; writing is granted deliberately, afterwards.
    can_write = Column(Boolean, nullable=False, default=False)

    created_by = Column(String, ForeignKey("profiles.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    revoked_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)


class ConsoleTokenGrant(Base):
    """Guard 5: one row per token issued, with the origin that asked.

    Kept even when the token has long expired, because the question this
    answers is asked after the fact - "who has been minting tokens against
    our key, and from where" - and a log that only holds live sessions cannot
    answer it. It stores the email's hash rather than the email: this row
    exists to show an org a pattern, not to build a second copy of their
    membership list in a table nobody thinks of as one.
    """

    __tablename__ = "console_token_grants"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    club_id = Column(String, ForeignKey("clubs.id"), nullable=False, index=True)
    console_key_id = Column(String, ForeignKey("console_keys.id"), nullable=False, index=True)

    origin = Column(String, nullable=False)
    email_hash = Column(String, nullable=False)

    # Whether the person resolved to anybody on the roster. False is the
    # no-permission token: somebody not on the roster gets one rather than an
    # error, so the org's page still renders instead of showing their own
    # members a stack trace.
    resolved = Column(Boolean, nullable=False, default=False)

    issued_at = Column(DateTime, nullable=False, default=utc_now)
