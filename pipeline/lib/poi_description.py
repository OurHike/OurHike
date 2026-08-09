"""Compose a shelter's or campsite's description from ATC's own columns.

ATC has no prose field describing a shelter. `Descriptio`, despite the alias
"Description", is the club acronym followed by the feature's own name on 488
of the 510 shelters and campsites that carry it, and `Comments` is a
surveyor's notebook populated on under a third of them (see lib/atc_notes.py
for both, measured).

What ATC does have is the inventory, and it is complete: `Stories`,
`Chimneys`, the fire-ring and food-storage counts, `Deck_Lengt`, `Doors`,
`Exterior_M` and `Year_Built` are non-null on **all 280 shelters**, and
`Site_Num` on 231 of 232 campsites. So the sentence a hiker wants -

    "Two-storey clapboard shelter, sleeps 14, with a fireplace, a fire ring
     and a porch. Built 1915."

- is not a field to be found, it is a sentence to be assembled, and every
clause of it is a fact ATC states rather than a phrase anybody wrote. That
also makes the coverage total instead of the 26% ATC's free text manages.

`capacity` comes from reference/shelter_capacity.json, not from ATC (see
build_shelter_capacity.py). It is optional here for the same reason it is
optional there: the clause is omitted, never guessed.

## What is left out, and why that is a choice

The inventory has more than this: window and skylight counts, step and
railing materials, gutter lengths, roof ridge heights. Composing a sentence
means selecting from it, and the line drawn here is **what changes a hiker's
decision** - whether food can be hung safely, whether there is a fire, a
roof over a porch, a door on the front. "24 windows" is a true fact about
Upper Goose Pond Cabin and it is maintenance inventory, not a description.

The selection is in FEATURES below rather than spread through the code, so
disagreeing with it is a one-line change.
"""

# Exterior_M's coded domain, as adjectives rather than the inventory's own
# noun phrases: "Log shelter" reads; "Log & Stone shelter" does not.
EXTERIOR_MATERIALS = {
    "0": "block",
    "1": "board-and-batten",
    "2": "clapboard",
    "3": "corrugated-metal",
    "4": "timber",
    "5": "log",
    "6": "log-and-stone",
    "7": "plywood",
    "8": "post-and-beam",
    # 9 "Siding - Aluminum" and 10 "Siding - Shingle" describe the siding,
    # not the structure, and read oddly as a one-word adjective. Omitted -
    # the sentence simply says "shelter".
    "11": "steel",
    "12": "stone",
}

STOREYS = {2: "Two-storey", 3: "Three-storey"}

# (phrase, predicate over the ATC attributes). Order is the order they read
# in the sentence. See the module docstring for the line this draws.
FEATURES = (
    ("a fireplace", lambda p: _count(p, "Chimneys") > 0),
    ("a fire ring", lambda p: _count(p, "Metal_Fir") + _count(p, "Mortared") > 0),
    ("bear-proof food storage", lambda p: _count(p, "Food_Boxe") + _count(p, "Food_Cabl") + _count(p, "Food_Pole") > 0),
    ("a porch", lambda p: _count(p, "Deck_Lengt") > 0),
    # `Doors` is deliberately absent. Whether a shelter is enclosed does
    # change a hiker's decision in winter, but every phrasing of it from a
    # door count reads as inventory - "Stone shelter, sleeps 8, with a
    # fireplace and a door" - and the 16 features that have one are mostly
    # huts and cabins the name already gives away.
)

CAMPSITE_FEATURES = (
    ("a fire ring", lambda p: _count(p, "Metal_Fir") + _count(p, "Mortared") > 0),
    ("bear-proof food storage", lambda p: _count(p, "Food_Boxe") + _count(p, "Food_Cabl") + _count(p, "Food_Pole") > 0),
)

# ATC writes a placeholder year on a handful of features; anything outside
# this is a data-entry artifact rather than a build date worth printing.
EARLIEST_PLAUSIBLE_YEAR = 1800
LATEST_PLAUSIBLE_YEAR = 2100


def _count(properties: dict, key: str) -> float:
    """An ATC count column as a number, treating null and non-numeric alike
    as zero - these are inventory counts, and a missing one means nobody
    recorded any, which for the purpose of a sentence is none."""
    value = properties.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    return float(value)


def _plural(count: float, singular: str) -> str:
    whole = int(count)
    return f"{whole} {singular}" if whole == 1 else f"{whole} {singular}s"


def _join(parts: list[str]) -> str:
    """ "a, b and c" - an Oxford-comma-free list, matching the client's own
    prose elsewhere."""
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _with_clause(properties: dict, features: tuple) -> str:
    present = [phrase for phrase, predicate in features if predicate(properties)]
    return f", with {_join(present)}" if present else ""


def _built_clause(properties: dict) -> str:
    year = int(_count(properties, "Year_Built"))
    return f" Built {year}." if EARLIEST_PLAUSIBLE_YEAR <= year <= LATEST_PLAUSIBLE_YEAR else ""


def _note_clause(note: str | None) -> str:
    """ATC's own words, attributed rather than blended in.

    The composed sentence is assembled from columns; the note is a person's
    prose. Running them together would present a maintainer's "Not an
    accessible shelter" as though this pipeline had asserted it, so the
    attribution stays."""
    if not note:
        return ""
    text = note.strip()
    if not text.endswith((".", "!", "?")):
        text += "."
    return f" ATC notes: {text}"


def describe_shelter(properties: dict, capacity: int | None = None, note: str | None = None) -> str | None:
    """One sentence about a shelter, or None if ATC states nothing usable.

    None is reachable in principle - a feature with no material, one storey,
    no listed feature, no plausible year and no note - and on today's data it
    never happens, because `Year_Built` alone is populated on all 280.
    """
    storeys = STOREYS.get(int(_count(properties, "Stories")))
    material = EXTERIOR_MATERIALS.get(str(properties.get("Exterior_M", "")).strip())

    head = " ".join(part for part in (storeys, material, "shelter") if part)
    head = head[0].upper() + head[1:]
    if capacity is not None:
        head += f", sleeps {capacity}"

    sentence = f"{head}{_with_clause(properties, FEATURES)}.{_built_clause(properties)}{_note_clause(note)}"
    # "Shelter." on its own says nothing the card's own type line does not.
    if sentence == "Shelter.":
        return None
    return sentence


def describe_campsite(properties: dict, note: str | None = None) -> str | None:
    """One sentence about a campsite, or None if ATC states nothing usable.

    Campsites carry a much thinner inventory than shelters - no storeys, no
    materials, no year - so this leans on the two columns that are populated:
    whether the site is a group site, and how many individual sites it holds.
    """
    is_group = str(properties.get("Type", "")).strip() == "1"
    head = "Designated group campsite" if is_group else "Designated campsite"

    sites = int(_count(properties, "Site_Num"))
    pads = int(_count(properties, "Tent_Pads"))
    platforms = int(_count(properties, "Tent_Plat"))

    counted = []
    if sites > 0:
        counted.append(_plural(sites, "site"))
    if pads > 0:
        counted.append(_plural(pads, "tent pad"))
    if platforms > 0:
        counted.append(_plural(platforms, "tent platform"))
    if counted:
        head += f", {_join(counted)}"

    sentence = f"{head}{_with_clause(properties, CAMPSITE_FEATURES)}.{_note_clause(note)}"
    if sentence in ("Designated campsite.", "Designated group campsite."):
        # The type line already says "Campsite"; "Designated" alone is not
        # worth a second line on the card.
        return None
    return sentence
