"""Normalize raw trail-line blaze-color values into one `blaze_color`
attribute, per features/TRAIL_BLAZE_COLORS.md.

Pure - no I/O, no logging. Deciding what "decoded" means is this module's
job; deciding whether to warn about a failed decode is the caller's (during
export, where the raw feature/source context is available to put in the
message).
"""

NEUTRAL_FALLBACK = "Unknown"

# The palette the client will actually paint, mirrored here so that a mapping
# table cannot name a member that does not exist (#782).
#
# WHY THIS IS A SECOND COPY, AND WHAT STOPS IT DRIFTING
#
# The one that renders is `client/src/lib/blaze.ts`'s `BLAZE_COLORS`, and this
# module cannot import it - different language, different package. So this is
# the same shape as the POI id resolver (#831): one list per runtime, held to
# the other by a contract test rather than by anybody remembering.
# `tests/test_blaze_palette_contract.py` reads the TypeScript and fails if the
# two disagree, and pipeline-tests.yml's scope list carries that file so
# editing the palette runs this suite too.
#
# The neutrals are here for the same reason a mapping table might legitimately
# name one: "this source's blank string means confirmed-unblazed" is a real
# reviewed decision, distinct from "we could not decode it".
PALETTE = (
    "White",
    "Blue",
    "Yellow",
    "Orange",
    "Red",
    "Green",
    "Purple",
    "Aqua",
)

NEUTRAL_MEMBERS = ("None", "Other", "Unknown")


class UnknownPaint(ValueError):
    """A mapping table names a palette member the client cannot paint.

    Raised rather than warned, and that is the point: a warning would let a
    release ship trails coloured by a member that renders as neutral grey
    everywhere, which looks like missing data rather than like a typo in a
    reviewed file. This is a file a person edited; the failure belongs at the
    edit, not on a phone.
    """


def load_blaze_mapping(path=None) -> dict:
    """The reviewed per-source tables, or an empty mapping.

    The one impure function in this module, and it is here rather than at the
    call site so that "which file holds the judgement" has one answer. Absent
    file reads as no tables, which is the honest state of a checkout that has
    not fetched anything: every value unmapped, every one warned about.
    """
    import json
    from pathlib import Path

    path = path or Path(__file__).resolve().parent.parent / "reference" / "blaze_mapping.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("sources", {})


def map_source_blaze(raw_value, table: dict | None) -> tuple[str, str]:
    """Resolve one source's raw blaze string to (palette member, disposition).

    The other half of `normalize_blaze_color` and deliberately separate from
    it. That function decodes an ArcGIS coded domain - a mechanical step, the
    same for everyone. This one applies JUDGEMENT recorded in
    `reference/blaze_mapping.json`: that OPRHP's "Teal" is the same paint a
    hiker sees as aqua, that its "Lime" might be Green and nobody has checked.
    Two different kinds of decision, kept apart so a reviewer reads the second
    without wading through the first.

    Three dispositions, and the middle one is why this returns a word rather
    than a bool:

      - `"mapped"` - a reviewed row named a palette member.
      - `"deferred"` - a value this project has SEEN and decided not to paint
        yet, with a reason in the file. Renders neutral, same as unmapped, and
        it is not the same event: one is a decision, the other is an
        oversight. Collapsing them is how an oversight hides inside a docket.
      - `"unmapped"` - nobody has looked at this value. The loud one.

    A missing table is not an error: a source with no reviewed mapping has
    every value unmapped, which is exactly what the first release of a new
    source should say out loud.
    """
    if raw_value is None:
        return NEUTRAL_FALLBACK, "unmapped"
    table = table or {}
    mapped = (table.get("mapped") or {}).get(raw_value)
    if mapped is not None:
        if mapped not in PALETTE and mapped not in NEUTRAL_MEMBERS:
            raise UnknownPaint(
                f"blaze mapping names {mapped!r}, which is not a palette member - "
                f"admit it in client/src/lib/blaze.ts first, or map to one of {PALETTE}"
            )
        return mapped, "mapped"
    if raw_value in (table.get("deferred") or {}):
        return NEUTRAL_FALLBACK, "deferred"
    return NEUTRAL_FALLBACK, "unmapped"


def normalize_blaze_color(raw_value, coded_domain: dict[int, str] | None, source_default: str | None = None) -> tuple[str, bool]:
    """Resolve one feature's raw blaze value to (blaze_color, decoded).

    - `raw_value` missing (None): a source with a flat per-source default
      (e.g. centerline, uniformly white with no per-feature field - see
      `blaze_default` in sources.json) resolves to that default, decoded=True.
      Without a default, this is a true non-decode: (Unknown, False).
    - `raw_value` is a real key in `coded_domain`: decode it. This includes
      code 0 -> "None" and code 9 -> "Other" (side_trails' real domain) -
      both are successful decodes, not fallbacks.
    - Anything else (an unmapped literal like "Unknown"/"Gold", an
      out-of-range code, or no domain and no default to fall back on): the
      neutral (Unknown, False) fallback.
    """
    if raw_value is None:
        if source_default is not None:
            return source_default, True
        return NEUTRAL_FALLBACK, False
    if coded_domain is not None and raw_value in coded_domain:
        return coded_domain[raw_value], True
    return NEUTRAL_FALLBACK, False
