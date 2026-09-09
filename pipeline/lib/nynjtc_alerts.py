"""Reading NYNJTC's Trail Alerts, which - unlike ATC's - are an actual API.

features/ORG_NOTICES.md is the design and #1078 is the issue. This module owns
one job - **turn NYNJTC's WordPress payload into facts** - and deliberately
owns nothing about whether those facts may be published. That split is
`lib/atc_scrape.py`/`lib/atc_updates.py`'s and is kept for the same reason:
the parse can then be tested without a network and the policy without one.

WHY THIS IS THE EASY HALF, stated so nobody budgets it like ATC's. ATC's
notices are HTML, and `lib/atc_scrape.py` has to say "their HTML is not an
API" and mean it - a theme change breaks the parse. NYNJTC runs WordPress with
the REST API left on, so the same information arrives as JSON with documented
field names:

    GET /wp-json/wp/v2/posts?categories=6      the Trail Alerts category

Measured 2026-08-27: 18 alerts, published 2024-01-11 to 2026-06-16. There is
no markup to misread here, and the fragility budget a scraper spends on a
theme this spends on nothing.

THE FIND THAT MAKES PLACEMENT POSSIBLE, and it was not in #1073's survey -
that document read the body prose and concluded "locations are names, not
miles", which is true of the prose and understates the payload. **NYNJTC tags
every alert from its own closed taxonomies**, and they come back as term ids
on the post:

    trail    45 terms    Appalachian Trail, Ramapo-Dunderberg Trail, Brook Trail
    park    100+ terms   Harriman-Bear Mountain State Parks, Hudson Highlands SPP
    region   13 terms    Harriman-Bear Mountain, Catskill, Hudson Palisades
    state     3 terms    New York, New Jersey, Pennsylvania

Coverage on the 18 alerts live that day: **park on 17, trail on 10**, region
and state on 7 each. So placing an alert is a join from a vocabulary of tens
of terms, not a fuzzy match of prose against the 21,805 network features the
build exports - which is the difference between a lookup somebody can review
in one sitting and a guess with a hiker's location attached.

Term ids are NOT stable across a WordPress site's life the way a slug is, so
this module resolves them to names at fetch time and caches the names. A join
table keyed on `trail:appalachian-trail` survives a term being renumbered; one
keyed on `40` does not.

WHAT IS DELIBERATELY NOT HERE. There is no `auto_publish_refusal` twin of
`lib/atc_updates.py`'s. That gate exists because ATC's rows can publish
without a person once they are unambiguous, and nothing about NYNJTC's is
unambiguous yet: their alerts carry no per-alert category vocabulary (every
one is filed under the single "Trail Alerts" category), the term-to-feature
join table does not exist yet, and `nynjtc_licence` in sources.json does not
cover republishing their notices at all. Inventing a publish gate before any
of those three is settled would be machinery pretending to a decision nobody
has taken. `alert_problems` says what a row is missing; a person decides.
"""

from __future__ import annotations

import html as html_module
from dataclasses import dataclass, field
from datetime import datetime, timezone

from lib.atc_scrape import strip_html

#: NYNJTC's "Trail Alerts" category, read off their own taxonomy 2026-08-27:
#: `/wp-json/wp/v2/categories?search=trail alerts` answers one term, id 6,
#: slug `trail-alerts`, 18 posts. The id rather than the slug because the
#: posts endpoint filters on ids; the slug is carried alongside so a future
#: renumbering is a caught mismatch rather than a silently empty fetch.
TRAIL_ALERTS_CATEGORY_ID = 6
TRAIL_ALERTS_CATEGORY_SLUG = "trail-alerts"

#: The taxonomies an alert is tagged from, in the order a placement should
#: prefer them: a trail is a line on our map, a park is an area containing
#: many, and region and state are context rather than location. Each is a
#: REST route under /wp-json/wp/v2/ as well as a field name on a post, which
#: is what lets one loop both fetch the vocabulary and read the tags.
PLACE_TAXONOMIES = ("trail", "park", "region", "state")


@dataclass
class Term:
    """One taxonomy term, as NYNJTC publishes it.

    Both spellings are kept on purpose. `id` is what a post carries and what
    the fetch resolves against; `slug` is what a reviewed join table should
    key on, because a term can be renumbered by a migration and keep its slug
    but cannot be renumbered and keep its meaning.
    """

    id: int
    name: str
    slug: str


@dataclass
class ParsedAlert:
    """One trail alert, as facts. Says nothing about whether it may ship.

    `modified_at` is the field that matters and is NOT a copy of
    `published_at`: NYNJTC maintains old alerts in place rather than
    reposting them. Measured 2026-08-27 - "Bear Mountain State Park Trail
    Closures & Advisories" was published 2025-11-21 and last modified
    2026-05-04, and reading its age off the publication date would have made
    a live advisory look six months abandoned.
    """

    slug: str
    title: str
    published_at: str
    modified_at: str
    source_url: str
    trails: list[Term] = field(default_factory=list)
    parks: list[Term] = field(default_factory=list)
    regions: list[Term] = field(default_factory=list)
    states: list[Term] = field(default_factory=list)
    text: str = ""

    @property
    def place_terms(self) -> list[Term]:
        """Every term that says where this is, trails first.

        Trails before parks because a trail is the thing a hiker is standing
        on and a park is the ground around it - features/ORG_NOTICES.md's
        placement preference, expressed once here rather than at each caller.
        """
        return [*self.trails, *self.parks]


def _text_of(rendered: dict | None) -> str:
    """A WordPress `{"rendered": "..."}` field as plain text.

    WordPress renders entities into the JSON (`&#8211;` for an en dash in a
    title), so unescaping is not optional - a title carried through verbatim
    would put literal `&#8211;` in front of a hiker.
    """
    if not isinstance(rendered, dict):
        return ""
    return html_module.unescape(strip_html(str(rendered.get("rendered") or "")))


def parse_terms(payload: list) -> dict[int, Term]:
    """One taxonomy's vocabulary, keyed by the id a post refers to it with.

    Ignores a malformed term rather than failing the vocabulary: a taxonomy
    is a lookup table, and one unreadable row costs the alerts that use that
    term their name - which `alert_problems` then reports - rather than
    costing every alert its whole placement.
    """
    terms: dict[int, Term] = {}
    for entry in payload if isinstance(payload, list) else []:
        if not isinstance(entry, dict):
            continue
        identifier, name, slug = entry.get("id"), entry.get("name"), entry.get("slug")
        if not isinstance(identifier, int) or not isinstance(name, str) or not isinstance(slug, str):
            continue
        terms[identifier] = Term(id=identifier, name=html_module.unescape(name), slug=slug)
    return terms


def parse_alert(post: dict, vocabularies: dict[str, dict[int, Term]]) -> ParsedAlert | None:
    """One post as facts, or None if the payload was not understood.

    None rather than a partial row, for `lib/atc_scrape.parse_update`'s
    reason: the caller's next move is to decide whether a hiker sees this,
    and a row built from the half of a payload that still parsed is the
    confident wrong answer this whole path is fenced against.

    THE REQUIRED FOUR are slug, title, `modified` and link. Everything else -
    every place taxonomy, the body - may legitimately be absent on a real
    alert (one of the 18 live on 2026-08-27 carries no park at all), and
    refusing those would be this module inventing a completeness NYNJTC does
    not promise.
    """
    if not isinstance(post, dict):
        return None

    slug = post.get("slug")
    modified = post.get("modified")
    link = post.get("link")
    if not (isinstance(slug, str) and slug.strip()):
        return None
    if not (isinstance(modified, str) and modified.strip()):
        return None
    if not (isinstance(link, str) and link.startswith("http")):
        return None

    title = _text_of(post.get("title"))
    if not title:
        return None

    published = post.get("date")

    def terms_for(taxonomy: str) -> list[Term]:
        vocabulary = vocabularies.get(taxonomy, {})
        ids = post.get(taxonomy)
        return [vocabulary[i] for i in ids if isinstance(i, int) and i in vocabulary] if isinstance(ids, list) else []

    return ParsedAlert(
        slug=slug.strip(),
        title=title,
        published_at=published.strip() if isinstance(published, str) else "",
        modified_at=modified.strip(),
        source_url=link,
        trails=terms_for("trail"),
        parks=terms_for("park"),
        regions=terms_for("region"),
        states=terms_for("state"),
        text=_text_of(post.get("content")),
    )


#: Provenance, carried into the artifact so a display cannot outrun its
#: source. `lib/atc_updates.py` holds both halves of this vocabulary; NYNJTC
#: only ever emits the second today, because no reviewed file exists for this
#: source and `export_nynjtc_alerts.py`'s docstring says why.
REVIEWED = "reviewed"
UNREVIEWED = "unreviewed"

#: The source key this publisher's rows are namespaced by, matching its
#: `sources.json` entry. features/ORG_NOTICES.md §2: a notice id is
#: `<source key>:<the org's own slug>`, because the registry key is what
#: `export_sources.py` and the client's steward registry already join on.
SOURCE_KEY = "nynjtc_trail_alerts"

#: Every field a published row carries. Facts and a link - deliberately not
#: NYNJTC's body text, which is theirs (the `licence` field on this source in
#: sources.json, and ATC_TRAIL_UPDATES.md's split applied unchanged).
PUBLISHED_FIELDS = (
    "notice_id",
    "source_key",
    "title",
    "category",
    "locality",
    "place",
    "obstructs_trail",
    "updated_at",
    "source_url",
    "review_state",
)


def _as_utc_stamp(iso: str) -> str:
    """A WordPress local timestamp in the `...Z` form the artifacts use.

    WordPress's `modified` is site-local with no offset on it (NYNJTC runs
    US/Eastern), so this cannot convert what it is not told. It stamps the
    value as UTC rather than guessing an offset, which is a known and bounded
    error of a few hours on a field a hiker reads as a DATE - and the
    alternative, hard-coding somebody's timezone, is a guess that breaks
    silently if they move the site. `modified_gmt` is the real fix and is in
    the payload; taking it is a follow-up rather than a silent change here,
    because it changes every published stamp.
    """
    try:
        stamped = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    if stamped.tzinfo is None:
        stamped = stamped.replace(tzinfo=timezone.utc)
    return stamped.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def locality_of(entry: dict) -> str:
    """The coarse "roughly where" a list entry prints, from the org's terms.

    Region and state rather than trail and park, because this is the string
    that answers "is this anywhere near me" at a glance - features/ORG_NOTICES
    .md §2's `locality`. Falls back to the parks when NYNJTC tagged neither,
    and to an empty string when they tagged nothing at all, which the client
    renders as no locality rather than as a guess.
    """
    for taxonomy in ("regions", "states", "parks"):
        names = [term.get("name") for term in entry.get(taxonomy) or [] if isinstance(term, dict)]
        named = [name for name in names if isinstance(name, str) and name.strip()]
        if named:
            return ", ".join(dict.fromkeys(named))
    return ""


def published_rows(alerts: dict) -> list[dict]:
    """The cached alerts as the artifact carries them.

    Projected onto `PUBLISHED_FIELDS` rather than passed through, so the body
    text the cache holds for a reviewer's eyes cannot reach the bucket by
    accident - `lib/atc_updates.py`'s `published_rows` and its reasoning,
    applied to a cache instead of a reviewed file.

    EVERY ROW IS `unplaced` AND UNREVIEWED, and neither is a placeholder that
    a later change should quietly relax. Placing one needs the reviewed join
    table features/ORG_NOTICES.md §4 specifies, and promoting one to reviewed
    needs a person - so both stay false until the thing that would make them
    true actually exists.
    """
    rows = []
    for slug in sorted(alerts):
        entry = alerts[slug]
        if not isinstance(entry, dict):
            continue
        rows.append(
            {
                "notice_id": f"{SOURCE_KEY}:{slug}",
                "source_key": SOURCE_KEY,
                "title": entry.get("title") or "",
                # NYNJTC files every alert under one category and publishes no
                # per-alert vocabulary, so there is nothing true to put here.
                # Absent means unknown - it must not borrow ATC's word list.
                "category": None,
                "locality": locality_of(entry),
                "place": {"kind": "unplaced"},
                "obstructs_trail": False,
                "updated_at": _as_utc_stamp(entry.get("modified_at") or ""),
                "source_url": entry.get("source_url") or "",
                "review_state": UNREVIEWED,
            }
        )
    return rows


def alert_problems(alert: ParsedAlert) -> list[str]:
    """What stops this alert being placed, in the order it was checked.

    A REVIEW AID RATHER THAN A GATE, and the distinction is the point. Nothing
    refuses to cache an alert for having problems - the cache is what a person
    reads - and no artifact is built from this. The list exists so the fetch
    log says which alerts a reviewer could place today and which ones need
    NYNJTC to have tagged something, instead of leaving that to be discovered
    one alert at a time.

    An empty list means "this alert names a place our own vocabulary could be
    joined to", NOT "this alert is publishable". Publishable additionally
    needs the join table to have a row for that term and the licence question
    in sources.json's `nynjtc_licence` to have been answered, and neither is
    this module's to assert.
    """
    problems = []
    if not alert.place_terms:
        problems.append(
            "no trail or park tag, so nothing says where it is except the prose - "
            "an unplaced notice under features/ORG_NOTICES.md, which is a real state and not a defect"
        )
    elif not alert.trails:
        parks = ", ".join(term.name for term in alert.parks)
        problems.append(f"park only ({parks}) - places it to an area, not to a line a hiker is walking")
    return problems
