"""Request/response models for `/clubs` - the organization itself.

`Org` is the word every screen uses and `clubs` is the table's name; see
../../../features/ORG_ONBOARDING.md's conflict 2 for why the route did not
get renamed to match the UI. The schema class names follow the UI, because a
reader of a FastAPI response model is reading the API's vocabulary rather
than the database's.
"""

from __future__ import annotations

import datetime as dt
import re

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.time import UtcDatetime
from app.models.club import OrgState, VerifiedBy
from app.schemas.common import NoteText

# A slug is lowercase alphanumerics and single hyphens, 3 to 64 characters.
#
# It has to survive being a path segment, a `data-org` attribute in somebody
# else's HTML and a directory name in a pull request, so the character set is
# the intersection of what all three take without escaping rather than the
# most permissive any one of them allows.
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SLUG_MIN = 3
SLUG_MAX = 64

# Slugs nobody may register, because each already means something else under
# `/org/`. Kept short and checked rather than guessed at: these are the path
# segments this design actually uses.
RESERVED_SLUGS = frozenset(
    {"new", "claim", "nominate", "nominations", "demo", "setup", "volunteers", "admins", "admin", "api", "org"}
)

# Domains that hand an address to anybody who asks for one, so an address
# there proves nothing about who runs an organization. First listed for #1641
# - Backend and org-console findings the v1.3.2 release review deferred, all
# blocking a production backend (#600), finding 3: `register_org`'s whole
# domain proof is "this person holds an address at the org's own domain", and
# a free mail domain makes that sentence true for anybody on the internet.
# `why_domain_proves_nothing` below is where every door asks this list.
#
# @unvalidated, and it cannot be finished. Assembled by hand from general
# knowledge of which services hand out addresses - not checked against each
# provider's sign-up page, and not a maintained dataset (the kind services
# like Mailgun or Kickbox publish and update). A denylist misses by
# construction: mail.com and Fastmail each let a user pick from many more
# domains than are listed here, no ISP's domain is here, and disposable-inbox
# services add domains to stay ahead of lists like this one.
#
# **ONE MISSING PROVIDER IS ENOUGH**, because whoever registers or nominates
# an organization also picks its domain: an address at an unlisted provider
# passes as the organization's own, under whatever name the form is given.
# At `POST /clubs/nominations` that is #1909 - A nomination and a claim make a
# free webmail account the codeowner of any organization name, the seat #1635
# closed on POST /clubs - and `POST /clubs` has the same gap. So this list's
# old settle-condition, "a real attempt from a provider outside it", was
# waiting for the attack itself. More entries narrow the gap and cannot close
# it. What would close it is positive proof that somebody controls the domain
# - a DNS TXT record the organization publishes, or a person confirming a
# nominated organization's domain before anybody can claim it - and nothing
# here builds that yet.
#
# One string per provider, split on whitespace: domains sorted within it,
# providers in alphabetical order. A whitespace-separated string rather than
# a set literal because a missing comma between two literals silently glues
# them into one domain nobody listed; `tests/test_routers_clubs.py` checks
# that every entry is a plain lowercase hostname. Some entries are here for
# how an address can be had rather than for who runs the mailbox:
# `privaterelay.appleid.com` is the domain of the relay address "Sign in with
# Apple" gives an app when a person hides their own, and this app offers
# Apple sign-in; `duck.com` and `mozmail.com` hand forwarding addresses to
# anybody; and the disposable inboxes accept mail for any address at all, a
# sign-in code included.
_PUBLIC_MAIL_BY_PROVIDER = {
    "AOL": "aim.com aol.co.uk aol.com",
    "Apple": "icloud.com mac.com me.com privaterelay.appleid.com",
    "Disposable inboxes": "10minutemail.com guerrillamail.com maildrop.cc mailinator.com sharklasers.com yopmail.com",
    "DuckDuckGo Email Protection": "duck.com",
    "Fastmail": "fastmail.com fastmail.fm",
    "Firefox Relay": "mozmail.com",
    "GMX and WEB.DE": "gmx.at gmx.ch gmx.co.uk gmx.com gmx.de gmx.es gmx.fr gmx.net gmx.us web.de",
    "Google": "gmail.com googlemail.com",
    "HEY": "hey.com",
    "Kakao": "daum.net hanmail.net",
    "mail.com": """
        accountant.com asia.com cheerful.com consultant.com dr.com email.com engineer.com europe.com iname.com
        mail.com myself.com post.com techie.com usa.com writeme.com
    """,
    "Mail.ru": "bk.ru inbox.ru list.ru mail.ru",
    "Microsoft": """
        hotmail.be hotmail.co.jp hotmail.co.uk hotmail.com hotmail.com.ar hotmail.com.br hotmail.de hotmail.es
        hotmail.fr hotmail.it hotmail.nl
        live.at live.be live.ca live.co.uk live.com live.com.au live.com.mx live.de live.dk live.fr live.ie live.it
        live.nl live.no live.se
        msn.com
        outlook.com outlook.com.au outlook.com.br outlook.de outlook.es outlook.fr outlook.it outlook.jp
        windowslive.com
    """,
    "National webmail": "abv.bg interia.pl laposte.net libero.it o2.pl onet.pl rambler.ru seznam.cz ukr.net virgilio.it wp.pl",
    "Naver": "naver.com",
    "NetEase": "126.com 163.com yeah.net",
    "Proton": "pm.me proton.me protonmail.ch protonmail.com",
    "Rediff": "rediffmail.com",
    "Sina": "sina.cn sina.com",
    "Tencent": "foxmail.com qq.com",
    "Tuta": "keemail.me tuta.com tuta.io tutamail.com tutanota.com tutanota.de",
    "Yahoo": """
        rocketmail.com yahoo.ca yahoo.co.in yahoo.co.jp yahoo.co.nz yahoo.co.uk yahoo.com yahoo.com.ar yahoo.com.au
        yahoo.com.br yahoo.com.mx yahoo.de yahoo.es yahoo.fr yahoo.ie yahoo.in yahoo.it ymail.com
    """,
    "Yandex": "ya.ru yandex.by yandex.com yandex.kz yandex.ru yandex.ua",
    "Zoho": "zoho.com zohomail.com",
}
PUBLIC_EMAIL_DOMAINS = frozenset(domain for domains in _PUBLIC_MAIL_BY_PROVIDER.values() for domain in domains.split())


def why_domain_proves_nothing(domain: str) -> str | None:
    """Why an address at `domain` cannot show who runs an organization, or None.

    Three doors take "a verified address at the organization's domain" as the
    proof of who runs it, and each asked about the domain on its own or not at
    all (#1909 - A nomination and a claim make a free webmail account the
    codeowner of any organization name, the seat #1635 closed on POST /clubs).
    `OrgCreate` below refused both cases. `POST /clubs/nominations` stored
    whatever domain the hiker's website named, and `claim_org` accepted
    whatever was stored. So this is the one rule, and all three ask it:

    - **Blank**, once normalised: no address can be at it.
    - **No dot.** A bare top-level domain: a website of `https://com` stored
      `com`, which every `.com` address holds.
    - **A public mail provider** (`PUBLIC_EMAIL_DOMAINS` above): anybody can
      get an address there.

    **`domain` is normalised here rather than trusted to arrive that way**:
    stripped, lowercased, and with any trailing dot removed. `claim_org` asks
    about a STORED domain, and the rows this check exists for are the ones
    today's validators did not write - by hand, or by an older version of a
    door.
    The address check after it (`_somebody_holds_the_domain` in
    routers/clubs.py) strips and lowercases before comparing, so a rule that
    read the row as stored passed `GMAIL.COM` and `gmail.com ` while
    `mallory@gmail.com` still matched both and was seated.

    A public suffix such as `co.uk` has a dot and passes. Closing that needs
    the Public Suffix List, a new dependency nobody has taken on yet.
    """
    normalised = domain.strip().lower().rstrip(".")
    if not normalised:
        return "That domain is blank, so no address can be at it."
    if "." not in normalised:
        return f"{normalised} is a top-level domain, not an organization's own, so every address under it would count."
    if normalised in PUBLIC_EMAIL_DOMAINS:
        return (
            f"{normalised} is a public email provider, not an organization's own domain - "
            "anybody can get an address there, so it cannot prove who runs a club."
        )
    return None


def slugify(name: str) -> str:
    """A candidate slug for `name` - the same shape the migration backfills.

    Not authoritative: an org picks its own at registration, and this only
    proposes one so the form can be pre-filled. Kept beside the validator so
    the two cannot drift into proposing something the other refuses.
    """
    candidate = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return candidate[:SLUG_MAX].rstrip("-")


class OrgAdminOut(BaseModel):
    """One admin's seat, as the approval screen renders it.

    Carries `approved_at`/`declined_at` rather than a single status word,
    because a decline is reversible and a status enum would need a value for
    "declined, then approved" that means nothing to a reader. The two
    timestamps say what happened in the order it happened.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    person_id: str
    title: str | None
    is_codeowner: bool
    invited_at: UtcDatetime
    approved_at: UtcDatetime | None
    declined_at: UtcDatetime | None
    decline_reason: str | None


class OrgOut(BaseModel):
    """An organization as the console and the public page both read it.

    One model rather than a public/private split, because there is nothing
    here a hiker may not see: the roster, the hours and the unpublished
    registry are all other resources. What an org publishes about itself is
    public by construction - that is what registering is.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str | None
    name: str
    region: str | None
    domain: str | None
    website: str | None
    verified_by: VerifiedBy | None
    state: OrgState
    membership_url: str | None
    donation_url: str | None
    # WHERE THIS ORGANIZATION'S REGISTRY IS SITTING, once three codeowners
    # have signed and a pull request was opened. Null until then, and null
    # on every deployment where `registry_pr_enabled` is off - which the
    # console has to render as "nothing is waiting for you" rather than as
    # the mechanism described in the abstract. The number stays behind the
    # admin gate; the URL is what a screen needs and is public anyway.
    registry_pr_url: str | None = None
    created_at: UtcDatetime
    admins: list[OrgAdminOut] = []

    # Whether the org has agreed that a model may read its registry, read off
    # `Club.assist_opted_in` - the derived property, never the raw dates.
    # Public because it is a fact about the organization and the console
    # needs it to decide whether to draw an assist panel at all; the dates
    # and the admin who set them stay behind `GET .../assist-consent`.
    #
    # Defaulted to False rather than left required, because an `OrgOut` built
    # from anything other than a live row - a fixture, a future projection -
    # must not be able to claim a consent nobody gave by forgetting a field.
    assist_opted_in: bool = False


class OrgAdminInvite(BaseModel):
    """One of the three people named at registration.

    Email rather than a person id, because at registration none of them have
    necessarily signed in - #1169's problem 3, and the reason `RoleInvite`
    exists. The seat is created when they first sign in.
    """

    email: str
    title: str | None = None

    @field_validator("email")
    @classmethod
    def _looks_like_an_address(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned or cleaned.startswith("@") or cleaned.endswith("@"):
            raise ValueError("that does not look like an email address")
        return cleaned


# The only two URL schemes an organization may give us for a link we render.
#
# WHY THIS EXISTS, and it is the sharper of the two reasons this module
# validates anything. `membership_url` and `donation_url` are shown on the
# organization's own website through the embed, in the console, AND - by the
# design's own line - on every one of their sections in the hiker's app. A
# stored `javascript:` URL in any of those three is script running in a
# hiker's app when they tap "Support this work" on a section card, from a
# value an admin typed into a settings form. `data:` is the same hole wearing
# a different hat.
#
# An allow-list rather than a block-list, because the list of schemes a
# browser will execute is not one anybody can enumerate from memory: `vbscript:`
# and `jar:` have both been it, and the next one is not knowable here. Two
# schemes is what a membership page and a donation page need.
SAFE_URL_SCHEMES = ("https://", "http://")

URL_MAX = 2048


def safe_external_url(value: str | None) -> str | None:
    """An organization's own link, or a refusal naming what is wrong.

    None and empty both mean "they gave none", which is a real answer: an
    organization with no donation page has no donation link, and absent is
    what the card renders rather than a dead one.
    """
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > URL_MAX:
        raise ValueError(f"that link is longer than {URL_MAX} characters")
    if not cleaned.lower().startswith(SAFE_URL_SCHEMES):
        raise ValueError("a link has to start with https:// or http://")
    # A control character in an href survives some parsers and is stripped by
    # others, which is exactly the disagreement a bypass lives in.
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in cleaned):
        raise ValueError("that link contains a control character")
    return cleaned


# A way to reach a person is wider than a web page: the club's own channel
# may be an address or a number (`client/src/lib/safeLink.ts`'s
# CONTACT_SCHEMES, and `pipeline/lib/work_projects.py`'s "a mailto: or tel:
# or https: string"). Kept in step with that set by hand - two short tuples
# in two languages, and a comment in each naming the other.
SAFE_CONTACT_SCHEMES = (*SAFE_URL_SCHEMES, "mailto:", "tel:")

# What a browser treats as a scheme: a letter, then letters, digits, `+`,
# `-` or `.`, then a colon. A string with no such prefix is not a URL at
# all - `trails@ramapotrails.org` and `(201) 555-0134` are the common
# contacts and neither carries one - so it is text, and an anchor resolves
# it against the page rather than acting on it.
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")


def safe_contact_target(value: str | None) -> str | None:
    """A way to reach the organization, refused if a browser would act on it.

    Wider than `safe_external_url` and for the same reason it exists: this
    lands in an `href` at three sinks, one of them the embed running on the
    organization's own page, so the scheme is the whole question. A plain
    address or phone number carries no scheme and is passed through as the
    text it is.
    """
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > URL_MAX:
        raise ValueError(f"that contact is longer than {URL_MAX} characters")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in cleaned):
        raise ValueError("that contact contains a control character")
    if _SCHEME.match(cleaned) and not cleaned.lower().startswith(SAFE_CONTACT_SCHEMES):
        raise ValueError("a contact is a web address, an email address or a phone number")
    return cleaned


class OrgCreate(BaseModel):
    """Registering. One admin fills this in; three approve before anything publishes."""

    name: str
    slug: str
    domain: str
    website: str | None = None
    region: str | None = None
    membership_url: str | None = None
    donation_url: str | None = None
    admins: list[OrgAdminInvite] = []

    @field_validator("slug")
    @classmethod
    def _usable_as_an_address(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not SLUG_MIN <= len(cleaned) <= SLUG_MAX:
            raise ValueError(f"a slug is {SLUG_MIN} to {SLUG_MAX} characters")
        if not SLUG_PATTERN.match(cleaned):
            raise ValueError("a slug is lowercase letters, digits and single hyphens")
        if cleaned in RESERVED_SLUGS:
            raise ValueError(f"{cleaned!r} is reserved - it already means something under /org/")
        return cleaned

    @field_validator("website", "membership_url", "donation_url")
    @classmethod
    def _a_link_a_browser_will_not_execute(cls, value: str | None) -> str | None:
        return safe_external_url(value)

    @field_validator("domain")
    @classmethod
    def _a_bare_domain(cls, value: str) -> str:
        # A bare hostname, because it is compared against the part of an
        # email address after the `@`. Accepting "https://ramapotrails.org/"
        # here and comparing it to "ramapotrails.org" would fail the
        # domain check for every admin and give no reason why.
        cleaned = value.strip().lower().removeprefix("https://").removeprefix("http://").strip("/")
        if "." not in cleaned or " " in cleaned:
            raise ValueError("give the bare domain, e.g. ramapotrails.org")
        problem = why_domain_proves_nothing(cleaned)
        if problem:
            raise ValueError(f"{problem} Give the domain your organization's own website and mail run on.")
        return cleaned


class OrgSettingsUpdate(BaseModel):
    """What an admin may change afterwards, and what they may not.

    `slug` is absent on purpose. It is in every route, every embed snippet an
    org has already pasted onto their own website, and every pull-request
    path. Changing it silently breaks all three, so it is a conversation with
    a maintainer rather than a form field.
    """

    name: str | None = None
    region: str | None = None
    website: str | None = None
    membership_url: str | None = None
    donation_url: str | None = None

    # The same gate as registration. An admin who could not register a
    # `javascript:` link but could edit one in afterwards would be a gate that
    # only looked like one - and this is the form an organization actually
    # uses, because the links usually arrive after the trails do.
    @field_validator("website", "membership_url", "donation_url")
    @classmethod
    def _a_link_a_browser_will_not_execute(cls, value: str | None) -> str | None:
        return safe_external_url(value)


class OrgClaimRequest(BaseModel):
    """Claiming an org that has live trails and no admins.

    An email at the org's domain is the whole check. The address is not sent
    here: it comes from the caller's verified token, because an address the
    caller typed proves nothing.
    """

    title: str | None = None
    note: NoteText | None = None


class OrgDeclineRequest(BaseModel):
    reason: NoteText | None = None


class OrgNomination(BaseModel):
    """A hiker submitting an org's trails on its behalf.

    Deliberately thin. The hiker is not claiming to speak for the
    organization and must not be asked to - they know their local club has
    trails and roughly where to find them, and that is the whole of what this
    collects. A maintainer reads it and does the rest.
    """

    name: str
    website: str | None = None
    region: str | None = None
    data_url: str | None = None
    note: NoteText | None = None


class ScoreboardOut(BaseModel):
    """The three numbers an organization puts on its own website.

    The design's coverage badge, whose own caption says where each comes from:
    "miles from the registry, volunteers from the roster, hours from the ones a
    supervisor signed off."

    **EVERYTHING HERE IS A COUNT AND NOTHING IS A LIST**, which is what makes
    it safe to serve to a stranger on somebody else's donate page. Rule 4 keeps
    anything about a named volunteer unpublished, and three totals are not
    three names. The shape is the enforcement: there is no array to leak,
    rather than an array a client is trusted to discard.

    `season_started` is here so "this season" is checkable. A badge printing
    "164 hours this season" over an unstated window is a number nobody can
    verify and an organization cannot explain to its own board.
    """

    miles_maintained: float
    active_volunteers: int
    hours_this_season: float
    season_started: dt.date
