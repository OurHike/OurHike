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

import idna
from pydantic import BaseModel, ConfigDict, field_validator

from app.core.time import UtcDatetime
from app.models.club import OrgAdmin, OrgState, VerifiedBy
from app.models.profile import Profile
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

# What a domain is once `normalise_domain` has folded it: ASCII letters,
# digits and hyphens, in two or more dot-separated labels. Matched with
# `fullmatch`, never `match` and a `$`: Python's `$` also matches before a
# trailing newline, the trap routers/analytics.py's `_version_of` documents.
_BARE_DOMAIN = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+")
_ONE_LABEL = re.compile(r"[a-z0-9-]+")


def _folded(value: str | None) -> str | None:
    """`value` stripped, lowercased, less one trailing dot and through IDNA, or None where IDNA refuses it."""
    cleaned = (value or "").strip().lower().removesuffix(".")
    if not cleaned:
        return None
    try:
        return idna.encode(cleaned, uts46=True, std3_rules=True).decode("ascii")
    except UnicodeError:  # idna.IDNAError and its subclasses
        return None


def normalise_domain(value: str | None) -> str | None:
    """`value` as the bare hostname every door compares, or None if it is not one.

    ONE NORMALISER, BECAUSE FOUR DOORS HAD FOUR (the 2026-11-04 security
    review). `OrgCreate` refused only a missing dot and a space, so it stored
    `ramapotrails.org/foo`, `ramapotrails.org:443` and `ramapotrails.org`, a
    tab and `foo` (a tab inside the name; its `strip` removed one at the
    end), and cut `https://ramapotrails.org/trails/` down to
    `ramapotrails.org/trails`. `why_domain_proves_nothing` stripped and
    lowercased, so `gmail.com` followed by a zero-width space, or typed in
    fullwidth letters, was not `gmail.com` to it. The address checks in
    routers/clubs.py and routers/nominations.py each stripped, lowercased and
    compared on their own. Every one of them asks this now and refuses on
    None, so a path, port, scheme, tab inside the name or zero-width
    character never reaches a comparison.

    In order: stripped, lowercased, one trailing ASCII dot removed
    (`ramapotrails.org.` is the same name written fully qualified; a second
    dot is not), folded with the `idna` package's UTS #46 mapping, and held to
    `_BARE_DOMAIN`. So whitespace at either end - a space, a tab, a newline,
    U+2003 EM SPACE - is stripped, not refused, and the clean name is what
    comes back. A trailing `。` or `．` is refused rather than dropped: UTS
    #46 maps it to `.` only after the trailing ASCII dot has been looked
    for, leaving an empty last label, which fails closed. What the fold
    does, measured against idna 3.18 (the version requirements.txt pins) on
    2026-11-04:

    - maps fullwidth and other compatibility letters (`ｇｍａｉｌ.com`,
      `ℊmail.com`) and the ideographic full stop (`gmail。com`) to ASCII;
    - drops the characters UTS #46 ignores, U+200B ZERO WIDTH SPACE, U+00AD
      SOFT HYPHEN, U+2060 WORD JOINER and U+FEFF among them, so
      `gmail.com` + U+200B is `gmail.com`;
    - refuses a zero-width joiner or non-joiner out of context, a `/`, `:`,
      `_` or a tab inside the name, an empty label, a label over 63
      characters and a hyphen at either end of one;
    - writes a real non-ASCII label as its `xn--` A-label (`bücher.de` is
      `xn--bcher-kva.de`), so a Unicode address and a stored domain meet in
      one spelling.

    What it does not catch:

    - **A look-alike.** A Cyrillic `а` in `gmаil.com` folds to
      `xn--gmil-63d.com`, a different domain on no list. Somebody had to
      register it, so an address there is evidence about whoever did; that a
      reader might take it for Gmail is a display risk nothing here judges.
    - **A public suffix.** `co.uk` has two labels and passes; see
      `why_domain_proves_nothing`.

    A website address is refused rather than cut down to its host, because
    cutting is how `ramapotrails.org/trails` got stored. Where a door really
    does take a website (`POST /clubs/nominations`), it reads the host with
    `urlsplit` first and normalises that.
    """
    folded = _folded(value)
    if folded is None or not _BARE_DOMAIN.fullmatch(folded):
        return None
    return folded


def address_is_at_domain(address: str | None, domain: str | None) -> bool:
    """Whether `address` is at `domain` or at a subdomain of it, both through `normalise_domain`.

    THE SUBDOMAIN RULE, WRITTEN ONCE. `_somebody_holds_the_domain` in
    routers/clubs.py (registering, releasing a held registration, claiming)
    and `_at_domain` in routers/nominations.py (a nomination's contacts, and
    whose decline closes the door for good) each wrote it out, the second
    with a docstring calling it "the same rule", and only the first
    normalised the domain it compared against. A subdomain counts
    (`maria@trails.ramapotrails.org`) because organizations really do run
    mail that way. Either side `normalise_domain` refuses matches nothing,
    so an invitation typed as `sec@ramapotrails.org/foo` no longer "holds"
    a domain stored as `ramapotrails.org/foo`.
    """
    if not address or "@" not in address:
        return False
    host = normalise_domain(address.rsplit("@", 1)[1])
    wanted = normalise_domain(domain)
    if host is None or wanted is None:
        return False
    return host == wanted or host.endswith("." + wanted)


def why_domain_proves_nothing(domain: str | None) -> str | None:
    """Why an address at `domain` cannot show who runs an organization, or None.

    Three doors take "a verified address at the organization's domain" as the
    proof of who runs it, and each asked about the domain on its own or not at
    all (#1909 - A nomination and a claim make a free webmail account the
    codeowner of any organization name, the seat #1635 closed on POST /clubs).
    `OrgCreate` below refused both cases. `POST /clubs/nominations` stored
    whatever domain the hiker's website named, and `claim_org` accepted
    whatever was stored. So this is the one rule, and all three ask it:

    - **Blank** once stripped: no address can be at it. A lone `.` is not
      blank by this test; it folds to nothing and is refused as not a
      hostname, two bullets down.
    - **No dot.** A bare top-level domain: a website of `https://com` stored
      `com`, which every `.com` address holds.
    - **Not a hostname** once folded as `normalise_domain` folds it: a
      path, a port, a scheme or a tab inside it, so no address could
      honestly be compared with it.
    - **A public mail provider** (`PUBLIC_EMAIL_DOMAINS` above): anybody can
      get an address there.
    - **A subdomain of one.** The claim takes an address at a subdomain of
      the org's domain as being at it (`trails.ramapotrails.org`), so a
      nominated `mallory.fastmail.com` would be proved by any address a
      provider hands out under that name - and Fastmail's subdomain
      addressing delivers `anything@mallory.fastmail.com` to the account
      `mallory@fastmail.com` (general knowledge, not checked here). An
      organization whose own domain really does sit under a mail
      provider's would be refused too and wait for a person; none is known,
      and that is the cheaper of the two mistakes.

    **`domain` is normalised here rather than trusted to arrive that way**,
    by the fold `normalise_domain` applies, which every door uses.
    `claim_org` asks about a STORED domain, and the rows this check exists
    for are the ones today's validators did not write - by hand, or by an
    older version of a door. The address check after it
    (`address_is_at_domain`) folds both sides the same way before comparing,
    so a rule that read the row as stored passed `GMAIL.COM` and `gmail.com `
    while `mallory@gmail.com` still matched both and was seated - and a rule
    that only stripped and lowercased passed `gmail.com` followed by a
    zero-width space, which the address check now reads as `gmail.com`.

    A public suffix such as `co.uk` has a dot and passes. Closing that needs
    the Public Suffix List, a new dependency nobody has taken on yet.
    """
    cleaned = (domain or "").strip()
    if not cleaned:
        return "That domain is blank, so no address can be at it."
    # Folded once, and read as `normalise_domain` reads it: one label is a
    # top-level domain, anything else short of `_BARE_DOMAIN` is no hostname.
    normalised = _folded(cleaned)
    if normalised is not None and _ONE_LABEL.fullmatch(normalised):
        return f"{normalised} is a top-level domain, not an organization's own, so every address under it would count."
    if normalised is None or not _BARE_DOMAIN.fullmatch(normalised):
        return f"{cleaned!r} is not a bare domain name like ramapotrails.org, so no address can be compared with it."
    if normalised in PUBLIC_EMAIL_DOMAINS:
        return (
            f"{normalised} is a public email provider, not an organization's own domain - "
            "anybody can get an address there, so it cannot prove who runs a club."
        )
    labels = normalised.split(".")
    for start in range(1, len(labels) - 1):
        provider = ".".join(labels[start:])
        if provider in PUBLIC_EMAIL_DOMAINS:
            return (
                f"{normalised} is part of {provider}, a public email provider, not an organization's own domain - "
                "an address there cannot prove who runs a club."
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

    `person_id`, `decline_reason` and the three dates are null unless the
    viewer may see them, so a null date means "not for you" as often as "has
    not happened": build one with `for_viewer`, never from the row directly.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    person_id: str | None
    title: str | None
    is_codeowner: bool
    invited_at: UtcDatetime | None
    approved_at: UtcDatetime | None
    declined_at: UtcDatetime | None
    decline_reason: str | None

    @classmethod
    def for_viewer(
        cls,
        seat: OrgAdmin,
        viewer: Profile | None,
        *,
        sees_every_holder: bool,
        sees_every_date: bool,
    ) -> OrgAdminOut:
        """The only correct way to build one. `viewer` is None when anonymous.
        `_with_admins` in routers/clubs.py works out the two flags.

        WHOSE SEAT IT IS, AND WHY THEY DECLINED, ARE NOT PUBLIC (#1914 - GET
        /clubs publishes every admin's account id and decline reason to anyone,
        and an account id is all it takes to write into that person's private
        thanks inbox). An account id was the key to that inbox, and a decline
        reason is a sentence a person wrote to their own organization. Both go
        to moderators and to the approved admins of an org that is not held
        (`sees_every_holder`), and to the seat's own holder, who needs it to
        find their seat.

        WHEN A SEAT WAS OFFERED AND ANSWERED IS THE ORG'S OWN BUSINESS TOO.
        #1914 asked for the dates to reach the console only. They go to
        moderators and to everybody holding a seat at the org, approved or not
        (`sees_every_date`) - wider than the holder rule above, because the
        console reads them for viewers who are not approved admins: the
        approval screen shows an invited admin where the other seats stand
        before they answer their own, and the setup hub and sign-off screen
        count approvals from `approved_at`. Nothing outside the console reads
        any seat field (the site's embed, `site/public/embed/v1/ourhike.js`,
        reads an org's name and giving links), so everybody else - anonymous
        callers, accounts with no seat here, the org's supervisors and
        volunteers - reads each seat's id, title and codeowner flag only.
        """
        own = viewer is not None and seat.person_id == viewer.id
        holder = sees_every_holder or own
        dates = sees_every_date or own
        return cls(
            id=seat.id,
            person_id=seat.person_id if holder else None,
            title=seat.title,
            is_codeowner=seat.is_codeowner,
            invited_at=seat.invited_at if dates else None,
            approved_at=seat.approved_at if dates else None,
            declined_at=seat.declined_at if dates else None,
            decline_reason=seat.decline_reason if holder else None,
        )


class OrgOut(BaseModel):
    """An organization as the console and the public page both read it.

    One model rather than a public/private split, because almost nothing here
    is private: the roster, the hours and the unpublished registry are all
    other resources. What an org publishes about itself is public by
    construction - that is what registering is. The exception is each seat's
    holder, decline reason and dates, which `OrgAdminOut.for_viewer` answers
    per viewer.
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
        # email address after the `@` - through `normalise_domain`, the rule
        # every door uses, so what is stored is what is compared. A website
        # address is refused with a sentence saying what to type rather than
        # cut down to its host: cutting is how
        # "https://ramapotrails.org/trails/" was stored as
        # "ramapotrails.org/trails", which no address is at.
        normalised = normalise_domain(value)
        if normalised is None:
            raise ValueError(
                "give the bare domain your organization's mail runs on, e.g. ramapotrails.org - no https://, path, port or spaces"
            )
        problem = why_domain_proves_nothing(normalised)
        if problem:
            raise ValueError(f"{problem} Give the domain your organization's own website and mail run on.")
        return normalised


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
