"""Turn ATC's free-text `Comments` into something a waypoint card can show.

ATC's shelter and campsite layers carry two text fields, and only one of them
is usable:

  - **`Descriptio`**, aliased "Description", is not one. It is the club
    acronym followed by the feature's own name - "MATC Chairback Gap Lean-to
    Shelter", "AMC Liberty Springs Campsite" - on 488 of the 510 features
    that have it (the remainder are spelling variants of the same thing, or
    literally "NA" for the four AMC huts). Published, it would render
    directly under a card heading that already says the name.
  - **`Comments`** is the real free text, and it is a surveyor's notebook
    rather than a description. It is populated on 81 of 280 shelters and 65
    of 232 campsites, and what is in it ranges from genuinely useful ("Has a
    loft", "Not an accessible shelter", "One group campsite") through
    construction detail ("Shiplap siding", "272 sq ft sleeping space") to
    notes the survey wrote to itself: "Not sure about spatial info" on
    twenty-four campsites, "GIS CS629-CS635", "Added based on existing GIS
    data", "Not sure if we should include in FMSS or not".

This module keeps the first two kinds and drops the third.

## Why it filters at all, and why per sentence

Publishing `Comments` verbatim would put "Not sure about spatial info" on
twenty-four campsite cards. No reading of "show the description" wants that,
so something has to go - and the honest way to drop it is the one that can be
argued with in review, which means a named list of patterns rather than a
judgement made once by hand over 146 rows.

The unit is the **sentence**, not the whole comment, because the two kinds are
mixed inside single fields. Cable Gap Shelter reads "Log and mortar exterior.
Majority of structure is log. Please see photos." - dropping the whole comment
to lose the last sentence throws away the only description ATC wrote for it.

**Sentences are kept or dropped whole; none is ever reworded.** What reaches a
hiker is ATC's own words or nothing.

## What this does not attempt

Judging whether a note is *interesting*. "Shiplap siding" survives, because a
rule that dropped it would be a rule about taste, and the one thing worse than
a dull card is a pipeline quietly deciding which of a maintainer's notes are
worth a hiker's time. Coverage lands around a quarter of shelters and an
eighth of campsites, which is what ATC actually wrote, not a target.
"""

import re

# A sentence that is the survey talking to itself. Ordered loosely by how
# often each fires on the real data (see the module docstring's counts).
INTERNAL_PATTERNS = (
    # Asset-system and GIS bookkeeping: ids, whether a feature belongs in
    # FMSS at all, which layer a point came from.
    r"\b(?:gis|fmss|arcgis|fbms)\b",
    # Provenance of the survey point rather than of the place.
    r"\b(?:added|adjusted|adusted|updated)\s+based\s+on",
    r"\baerial\s+imagery\b",
    r"\binventory\s+form\b",
    # The surveyor's own uncertainty, which is real and is theirs, not the
    # hiker's. "Not sure about spatial info" alone accounts for 24 campsites.
    r"\bnot\s+sure\b",
    r"\bneed\s+to\s+confirm\b",
    r"\bnot\s+(?:on|in)\s+(?:the\s+)?(?:collection\s+)?list\b",
    # Notes about the photography, not the place.
    r"\b(?:please\s+)?see\s+photos?\b",
    r"\bphotos?\s+taken\b",
    r"\bi\s+(?:took|failed\s+to)\b",
    # The vista layer's own bookkeeping dialect, which the first three layers
    # did not have (added 2026-08-09 with viewpoints/parking/privies; measured
    # to change nothing on shelters or campsites).
    #
    # `Improvements = ...` is an inventory form pasted into a free-text field
    # and is the single most common thing in this column - 133 of the 640
    # populated vista comments, including "Improvements = none identified",
    # which is a form saying nothing rather than ATC saying nothing.
    r"\bimprovements\s*=",
    # The 2021 Vista Resource Inventory, and the survey's own note about which
    # points it moved. "adjused" is ATC's typo, alongside the "adusted" the
    # provenance pattern above already carries.
    r"\bvri\b",
    r"\b(?:extent|location|scope)\s+(?:adjus|based\s+on)",
    r"\badjused\s+based\s+on",
    # The surveyor's instrument, not the place: "measured bearings 3 times,
    # each time getting different results", "Will be brining a compass next
    # time". Honest field notes, and about the survey rather than the view.
    r"\btrimble\b",
    r"\bcompass\b",
    r"\bbearings?\s+(?:measured|were)\b",
    r"\bmeasured\s+(?:the\s+)?bearings?\b",
    # The vista review process and its own identifiers: "Preliminary Review
    # with VARO" is the single most repeated phrase left once the form
    # language is gone, and `VP1058` is a survey point number the hiker has
    # no way to resolve ("this is either VP1058 ot 1059").
    r"\bvaro\b",
    r"\bpreliminary\s+review\b",
    r"\bvp\s?\d+",
    r"\bnot\s+(?:on|in)\b[^.;]{0,30}\blist\b",
    r"\bneed\s+to\s+determine\b",
    # The weather on the day somebody stood there, which is a fact about the
    # visit rather than about the view.
    r"\bsocked\b",
)

INTERNAL = re.compile("|".join(INTERNAL_PATTERNS), re.IGNORECASE)

# Content-free once the internal sentences are gone: ATC uses these as
# "nothing to say" rather than as a fact about the place.
EMPTY_VALUES = frozenset(("none", "no name", "na", "n/a", "unknown", "-"))

# ATC separates thoughts with full stops and semicolons. The split keeps its
# delimiter so a kept sentence reads the way it was written.
SENTENCE = re.compile(r"[^.;]+[.;]?")


def _is_internal(sentence: str) -> bool:
    stripped = sentence.strip().rstrip(".;").strip().lower()
    if not stripped or stripped in EMPTY_VALUES:
        return True
    # A bare number or date fragment - "816/15" is the whole comment on one
    # campsite and means nothing outside the survey.
    if re.fullmatch(r"[\d\s/\-]+", stripped):
        return True
    return bool(INTERNAL.search(sentence))


def clean_note(raw: str | None) -> str | None:
    """ATC's `Comments` with its survey bookkeeping removed, or None when
    nothing a hiker can use is left.

    None rather than "" so that "ATC wrote nothing" and "ATC wrote only notes
    to itself" reach the client identically - both are a card with no
    description, which is the honest rendering of each.

    Kept sentences are spliced back out of the original string rather than
    re-joined from the split, so ATC's own spacing and punctuation survive.
    Re-joining did not: it turned "Exterior - shiplap ;skylight" into
    "... shiplap ; skylight" and "91 sq. ft., Directional sign" into
    "91 sq. ft. , Directional sign", editing text this module promises not
    to touch.
    """
    if not raw or not raw.strip():
        return None

    kept = "".join(match.group(0) for match in SENTENCE.finditer(raw) if not _is_internal(match.group(0)))

    # Collapse only the whitespace that removing a sentence left behind, and
    # tidy punctuation that now separates nothing.
    text = " ".join(kept.split())
    text = re.sub(r"\s+([.;,])", r"\1", text)
    text = text.strip(" ;,")
    # Punctuation left standing where a dropped sentence used to be is not a
    # note. One vista comment reduces to exactly "." this way, and "ATC notes:
    # ." on a card is worse than the silence it is standing in for.
    if not any(character.isalnum() for character in text):
        return None
    return text or None
