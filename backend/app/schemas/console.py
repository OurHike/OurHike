"""Request/response models for the management-console embed's key exchange.

See ../../../features/ORG_ONBOARDING.md's "Console embed auth" and #1542.
`app/models/console_key.py` carries the six guards and why this ships
configured off.

**The secret is returned exactly once, by `ConsoleKeyCreated`, and never
again.** Every other read of a key uses `ConsoleKeyOut`, which has no secret
field to forget to strip. That is the whole reason there are two models
rather than one with an optional field: an optional secret is a secret that
leaks the day somebody reuses the model on a list endpoint.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.time import UtcDatetime


def normalise_origin(value: str) -> str:
    """An exact origin - scheme, host, optional port, no trailing slash.

    Exact because a wildcard is the allow-list undone. `client/scripts/screenshot.mjs`
    records the same lesson from the other side of it: R2 answers a
    cross-origin request by reflecting an exact `Origin` back rather than
    sending `*`, and the entries are exact origins, scheme included.
    """
    cleaned = value.strip().rstrip("/")
    if not cleaned.startswith(("http://", "https://")):
        raise ValueError("an origin includes its scheme, e.g. https://ramapotrails.org")
    if "*" in cleaned:
        raise ValueError("an origin cannot contain a wildcard - list each one")
    rest = cleaned.split("://", 1)[1]
    if "/" in rest:
        raise ValueError("an origin is scheme, host and port only - no path")
    if not rest:
        raise ValueError("an origin needs a host")
    return cleaned


class ConsoleKeyCreate(BaseModel):
    label: str | None = None
    allowed_origins: list[str] = []

    @field_validator("allowed_origins")
    @classmethod
    def _exact_origins(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("a key needs at least one origin it may be used from")
        return [normalise_origin(origin) for origin in value]


class ConsoleKeyOut(BaseModel):
    """A key as every read after creation sees it - no secret, ever."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    club_id: str
    public_key: str
    label: str | None
    can_write: bool
    created_at: UtcDatetime
    revoked_at: UtcDatetime | None
    last_used_at: UtcDatetime | None
    allowed_origins: list[str] = []

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_stored_origins(cls, value: object) -> object:
        # Newline-separated on the row; a list on the wire. Stored as text so
        # an origin list stays something a person can read in psql while
        # working out why somebody's embed is refused.
        if isinstance(value, str):
            return [line.strip() for line in value.splitlines() if line.strip()]
        return value


class ConsoleKeyCreated(ConsoleKeyOut):
    """The one response that carries the secret.

    Shown once, at creation. An organization that loses it rotates rather
    than recovers - the same trade every API key makes, because a secret this
    database could print is a secret a database dump discloses.
    """

    secret: str


class ConsoleSessionRequest(BaseModel):
    """What an organization's own server posts to mint a token.

    **Only the email.** We resolve roles from the roster, so their system
    never mirrors our permissions and cannot drift out of step with them -
    which is also why there is no `role` field here to be trusted.
    """

    public_key: str
    secret: str
    email: str

    @field_validator("email")
    @classmethod
    def _looks_like_an_address(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned:
            raise ValueError("that does not look like an email address")
        return cleaned


class ConsoleSessionOut(BaseModel):
    """A scoped, short-lived token, plus what it actually permits.

    `permissions` is empty for somebody not on the roster, and that is a
    **success**: they get a no-permission token rather than an error, so the
    organization's page still renders instead of showing their own members a
    stack trace. The embed reads this list to decide what to draw.
    """

    token: str
    expires_in: int
    org_slug: str
    display_name: str | None = None
    permissions: list[str] = []
