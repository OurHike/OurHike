"""Turning a club's fetched pages into something a hiker can review.

`app/core/sitefetch.py` reads the pages. `app/core/assist.py` asks a model
about them. This is the seam, and it exists for one property:

**NOTHING REACHES THE HIKER THAT WAS NOT IN THE PAGES WE READ.**

A model asked "who should we contact at this club" produces plausible
addresses whether or not the pages had any, because plausible is what it is
for. `president@carolinamountainclub.org` is precisely the shape of thing
that gets invented - correct domain, obvious role, no such mailbox - and a
hiker looking at a screen headed "what we could see on their site" has no
way to tell an invention from a reading. Then we email it, in our name,
about somebody else's organization.

So `grounded` checks every address and every URL back against the literal
text of the pages, and anything absent is dropped. That is not tidying up.
It is CLAUDE.md's "never let a display outrun its source" applied to the one
path in this codebase where the display is about a named person.

**THE CITATION IS CHECKED TOO, NOT JUST THE ADDRESS.** A contact whose
`source_page` names a URL we never opened cannot answer "where did you get
this", which is the only reason `nomination_contacts.source_page` is NOT
NULL. Where the address is real and the citation is not, the citation is
corrected to the page the address actually appeared on; where no page has
it, the contact goes.

**AND WHEN THE FETCH GOT NOWHERE, THE MODEL IS NOT ASKED AT ALL.** That is
the defect this module was built to end: `POST /assist/nominate` used to
send a bare URL to a model with no tools and render the answer under "WHAT
WE COULD SEE ON THEIR SITE". Nothing had been seen. `read_at_all` is False
and the screen says so, rather than showing a recollection as a reading.

**PROSE IS NOT GROUNDED THE SAME WAY, and the difference is deliberate.**
`summary` and `licence_note` are the reading's own words about what it read
and are shown as such; an address and a URL are claims about the world that
we are about to act on. `org_name` is grounded because it is a claim rather
than a description - a club we name wrongly is a club we write to wrongly.
"""

from __future__ import annotations

import json
import re
from typing import Callable

from app.core.sitefetch import Page
from app.schemas.nomination import (
    MAX_CONTACTS,
    MAX_SOURCES,
    NominateReading,
    ProposedContact,
    ProposedSource,
)

# What one page may contribute, and what the whole prompt may run to. A club
# with a 900kB page must not become a 900kB prompt: the budget in
# app/core/assist.py is counted in tokens the API reports, so a prompt with no
# ceiling is a bill with no ceiling.
MAX_PAGE_CHARS = 8_000
MAX_PROMPT_CHARS = 40_000

VERDICTS = {"usable", "closures", "found", "not_accepted", "unreadable"}

SYSTEM = (
    "You are reading the public web pages of a trail-maintaining organization, which are "
    "given to you in full below. Report ONLY what is in those pages. Do not use anything you "
    "know about this organization from anywhere else, and do not guess an address or a URL "
    "that is not written in the text - a guess here becomes an email to a real person. "
    "If the pages do not say, leave the field out. Answer with a single JSON object and no "
    "other text, with the keys: org_name, summary, sources (label, url, verdict, detail), "
    "contacts (name, role, email, source_page), membership_url, donation_url, licence_note. "
    "verdict is one of usable, closures, found, not_accepted, unreadable. Use not_accepted "
    "for PDF or image maps, which cannot be re-read. source_page is the URL of the page the "
    "address appeared on, copied from the page headings given to you."
)


class ReadingFailed(Exception):
    """The model's answer could not be read as a reading.

    Raised rather than returning an empty reading, because an empty reading
    renders as "their site has nothing on it" - a claim about somebody's
    organization that we would be making up.
    """


#: `(prompt, system) -> (answer_text, tokens_used)`. Injected so these
#: decisions are testable without a model or a budget.
Asker = Callable[[str, str], "tuple[str, int]"]


def _haystack(pages: tuple[Page, ...]) -> str:
    """Everything we actually saw, lowercased, as one string to search.

    Link hrefs are in it as well as page text, because a FeatureServer URL
    usually appears as an anchor and not as prose, and the anchor is exactly
    as much evidence that the club published it.
    """
    parts: list[str] = []
    for page in pages:
        parts.append(page.url)
        parts.append(page.title)
        parts.append(page.text)
        parts.extend(link.href for link in page.links)
        parts.extend(link.text for link in page.links)
        parts.extend(page.emails)
    return " \n ".join(parts).lower()


def grounded(value: str | None, pages: tuple[Page, ...]) -> bool:
    """Whether this literally appeared in what we read.

    A substring test on purpose. Anything cleverer - a fuzzy match, a
    normalising step that strips a trailing slash - is a way for a near-miss
    to pass, and a near-miss is the failure: an invented address differs from
    a real one by a word, and an invented FeatureServer URL by a digit.
    """
    if not value or not pages:
        return False
    return value.strip().lower() in _haystack(pages)


def _page_holding(value: str, pages: tuple[Page, ...]) -> str | None:
    """Which page this appeared on, so a citation can be checked or repaired."""
    needle = value.strip().lower()
    for page in pages:
        haystack = " ".join([page.text, *[link.href for link in page.links], *page.emails]).lower()
        if needle in haystack:
            return page.url
    return None


def _as_json(answer: str) -> dict:
    """The object in the model's reply, however it was wrapped.

    Models preface and fence. Discarding an otherwise good answer because it
    opened with "Here is what I found:" would be throwing away a reading over
    punctuation.
    """
    text = answer.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ReadingFailed("The reading did not come back as something we could use.")
    try:
        parsed = json.loads(text[start : end + 1])
    except ValueError as exc:
        raise ReadingFailed("The reading did not come back as something we could use.") from exc
    if not isinstance(parsed, dict):
        raise ReadingFailed("The reading did not come back as something we could use.")
    return parsed


def _prompt_from(pages: tuple[Page, ...]) -> str:
    """The pages, labelled by URL, inside a budget.

    Labelled because `source_page` has to be copyable from what the model was
    shown - asking it to cite a page it was never told the address of is
    asking it to invent one.
    """
    blocks: list[str] = []
    spent = 0
    for page in pages:
        body = page.text[:MAX_PAGE_CHARS]
        block = f"--- PAGE: {page.url}\nTITLE: {page.title}\n{body}\n"
        if spent + len(block) > MAX_PROMPT_CHARS:
            break
        blocks.append(block)
        spent += len(block)
    return "".join(blocks)


def _sources_from(raw, pages: tuple[Page, ...]) -> list[ProposedSource]:
    kept: list[ProposedSource] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict) or len(kept) >= MAX_SOURCES:
            continue
        url = str(item.get("url") or "").strip()
        verdict = str(item.get("verdict") or "").strip()
        label = str(item.get("label") or "").strip()
        if not url or verdict not in VERDICTS or not label:
            continue
        if not grounded(url, pages):
            continue
        detail = item.get("detail")
        kept.append(
            ProposedSource(
                label=label[:200],
                url=url[:500],
                verdict=verdict,
                detail=str(detail)[:600] if detail else None,
            )
        )
    return kept


def _contacts_from(raw, pages: tuple[Page, ...]) -> list[ProposedContact]:
    kept: list[ProposedContact] = []
    seen: set[str] = set()
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict) or len(kept) >= MAX_CONTACTS:
            continue
        email = str(item.get("email") or "").strip()
        if not email or email.lower() in seen or not grounded(email, pages):
            continue
        # The citation is repaired rather than trusted, and a contact whose
        # address is on no page we read has already been dropped above - so
        # this can only fail if the address is in a link href on a page whose
        # text does not carry it, which is a citation we still will not make up.
        page = _page_holding(email, pages)
        if page is None:
            continue
        name = item.get("name")
        role = item.get("role")
        try:
            kept.append(
                ProposedContact(
                    name=str(name)[:200] if name else None,
                    role=str(role)[:200] if role else None,
                    email=email,
                    source_page=page,
                )
            )
        except ValueError:
            # Not an address after all. `EmailStr` is the authority, and a
            # model writing "the volunteer coordinator" into an email field
            # is a thing that happens.
            continue
        seen.add(email.lower())
    return kept


def reading_from(website: str, pages: tuple[Page, ...], *, ask: Asker) -> NominateReading:
    """What we could see, ready for a hiker to keep or drop line by line.

    Writes nothing. Everything here is handed back to the browser and only
    what the hiker sends on the submit is stored - see
    app/schemas/nomination.py for why that is two schemas and not one.
    """
    if not pages:
        return NominateReading(website=website, read_at_all=False, pages_read=0)

    answer, tokens = ask(_prompt_from(pages), SYSTEM)
    parsed = _as_json(answer)

    org_name = str(parsed.get("org_name") or "").strip() or None
    summary = str(parsed.get("summary") or "").strip() or None
    licence_note = str(parsed.get("licence_note") or "").strip() or None
    membership = str(parsed.get("membership_url") or "").strip() or None
    donation = str(parsed.get("donation_url") or "").strip() or None

    return NominateReading(
        website=website,
        read_at_all=True,
        pages_read=len(pages),
        org_name=org_name if grounded(org_name, pages) else None,
        summary=summary[:600] if summary else None,
        sources=_sources_from(parsed.get("sources"), pages),
        contacts=_contacts_from(parsed.get("contacts"), pages),
        membership_url=membership if grounded(membership, pages) else None,
        donation_url=donation if grounded(donation, pages) else None,
        licence_note=licence_note[:600] if licence_note else None,
        tokens_used=tokens,
    )
