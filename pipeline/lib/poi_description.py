"""Compose a POI's description from ATC's own columns.

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

## The other three facility layers (2026-08-09)

Vistas, parking areas and privies compose the same way and from the same kind
of columns. Three things about them are worth knowing before reading the code.

**The coded domains are transcribed here, not fetched.** ATC publishes real
`codedValue` domains for `parking.Type`/`Surface`, `privies.Type`/`Enclosure`
and `viewpoints.Type` (`lib/arcgis.get_field_coded_domain` can read them, and
export_spurs.py does exactly that for the blaze/side-trail domain). This
module stays pure and offline, as EXTERIOR_MATERIALS above already did, so
the maps below are transcriptions - taken from `ANST_Facilities` on
2026-08-09 and dated so the next reader knows what to re-check.

**The stored values do not all sit in those domains**, and that is the one
piece of genuinely messy data here:

  - `viewpoints.Type` is a code on 988 of 1,223, and free text on the rest -
    `Unimproved` (180) and `Improved` (55), which are near-misses of the
    labels for codes 0 and 1 rather than the labels themselves.
  - `parking.Type` is a code on 417 of 482, with `Roadside/Shoulder` (53),
    `Unknown` (6) and `User Created` (5) besides - and `Roadside/Shoulder`
    is a real category the domain does not contain at all.
  - `privies.Type` is a code on 315 of 316; `privies.Enclosure` and
    `parking.Surface` are effectively clean.

Nothing here maps a free-text value onto a code. `Roadside/Shoulder` is
recognised on its own terms because it says something a hiker acts on; every
other unrecognised value simply drops its clause, so a sentence is shorter
rather than wrong. Deciding that `Unimproved` "means" code 0 would be this
pipeline guessing at ATC's data entry, which is the one thing composing from
columns was supposed to avoid.

**A vista's direction is derived, never copied.** `Left_Beari` and
`Right_Bear` bound the view swept clockwise, and they are populated on 1,006
of 1,223. `Scope` claims to be the width and agrees with `(Right - Left) mod
360` on only 419 of the 512 features carrying it, so the arc is computed from
the bearings and `Scope` is not published at all. Where the two disagree, one
of them is wrong and there is no way here to tell which.

## An anchor's sentence names the parts around it (2026-08-13)

Since #524 a site's members draw no pin: 284 privies and 144 campsites ride an
anchor's pin instead of competing for one. That fixed the map and emptied the
words - each of those points still composes a perfectly good sentence about
itself, attached to a feature that renders nowhere. So an anchor's sentence
carries its parts, and `nearby_clause` is where that is written.

**It is a SEPARATE SENTENCE, never a `with` clause**, and the distinction is
the whole point of it. "with a fireplace, a fire ring and a porch" lists things
the shelter HAS. A privy and a water source are not among them - they are
separate points a short walk away, and folding them into that grammar would
have this pipeline assert something ATC's data does not say and the ground
plainly contradicts. They get their own sentence, and every one of them
carries how far it is.
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

# --- parking ---------------------------------------------------------------

# `Surface`'s domain, as the adjective the sentence needs. Codes 2 "Pavers"
# and 6 "Other" are deliberately absent: one is a paving detail nobody parks
# differently for, and the other is a shrug. Both fall through to a plain
# "Parking area", which is what the card would have said anyway.
PARKING_SURFACES = {"0": "asphalt", "1": "concrete", "3": "gravel", "4": "dirt", "5": "grass"}

# The one `Type` value worth a head of its own - and, as the module docstring
# says, one the coded domain does not contain. A wide spot on the shoulder is
# a different thing to arrive at in the dark than a built lot, so it gets said
# even though ATC's own domain has no code for it.
PARKING_ROADSIDE = "Roadside/Shoulder"

# --- privies ---------------------------------------------------------------

# `Type`'s domain, as an adjective. "Clivus Multrum" is a manufacturer, so it
# reads as the thing it is; 5 "Other" drops to a plain "Privy".
PRIVY_TYPES = {
    "0": "composting",
    "1": "moldering",
    "2": "composting",
    "3": "pit",
    "4": "vault",
}

# `Enclosure`'s domain. Code 0 is ATC's own word for a privy with no building
# around it, and 8 of the 316 are one - which is exactly the kind of thing a
# hiker would rather read on the card than discover on arrival. Code 1 "Single
# Privy" is the unremarkable default and says nothing; 3 "Other" is a shrug.
PRIVY_OPEN_ENCLOSURE = "0"
PRIVY_MULTI_SEAT = "2"

# --- vistas ----------------------------------------------------------------

# `Location` has no coded domain: it is free text, semicolon-separated where
# more than one applies, and populated on 1,129 of 1,223 (90 of those being
# literally "TBD"). Keyed on the lowercased first value, so "Summit; Lookout
# Tower" reads as a summit rather than being dropped for not matching whole.
#
# "Mtn/Ridge/Outcrop" is ATC's own bundle of three landforms and stays a
# bundle here - "a ridge or rock outcrop" - rather than being narrowed to one
# this pipeline cannot tell apart. `Side Trail`, `TBD` and the rest are absent
# on purpose: they say where the survey stood, not what a hiker is looking
# from, and an unrecognised value drops the clause rather than inventing one.
VISTA_LOCATIONS = {
    "mtn/ridge/outcrop": "a ridge or rock outcrop",
    "summit": "a summit",
    "lookout tower": "a lookout tower",
    "tower/platform": "a tower platform",
    "viewing platform": "a viewing platform",
    "overlook": "an overlook",
    "bridge": "a bridge",
    "water feature": "the water",
    "utility corridor - powerline": "a powerline corridor",
    "utility - powerline": "a powerline corridor",
    "utility corridor - pipeline": "a pipeline corridor",
    "open area": "an open area",
    "open area - maintained": "a maintained clearing",
    "open area - managed": "a managed clearing",
    "open area - natural": "a natural clearing",
    "shelter": "a shelter",
    "campsite": "a campsite",
}

# Above this, a bearing is not a direction any more. 98 vistas sweep 300° or
# more, and "a 340° view north-east" describes a place you can turn around in
# by naming one edge of it.
PANORAMA_DEGREES = 300

# The published arc is rounded to this, and the reason is in ATC's own field
# notes: "measured bearings 3 times, each time getting different results",
# "Will be brining a compass next time". Most surveyed arcs are already a
# multiple of ten, so rounding costs nothing real and stops the handful of
# 62°s from implying a degree of precision the instrument did not have. Same
# posture as export_spurs.py rounding its distances to the metre.
ARC_ROUNDING_DEGREES = 5

COMPASS_POINTS = ("north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west")

# --- sites -----------------------------------------------------------------

# The order an anchor's parts are named in - lib/poi_sites.py's MEMBER_TYPES,
# but sorted by what a hiker asks first at a shelter rather than alphabetically.
# features/POI_SITES.md's own framing of the question is "is there a privy, and
# is there water"; a campsite is the one of the three you can see for yourself
# once you are standing there.
#
# The client's SITE_MEMBER_TYPES (client/src/map/poiSites.ts) fixes the same
# order for the pin's footer glyphs and #526's chips. Two orders for one site
# would have the sentence, the pin and the chip strip disagree about which part
# comes first, which is drift a hiker reads as three different answers.
NEARBY_ORDER = ("privy", "water", "campsite")

# The word the parts are introduced with. One label rather than repeating
# "away" on every part: the reader carries it forward across the list, and three
# of them in a row is the sentence describing its own grammar.
NEARBY_LEAD = "Nearby"

# ATC's `Type` code for a campsite that is a group site.
GROUP_CAMPSITE_TYPE = "1"


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


def describe_shelter(properties: dict, capacity: int | None = None, note: str | None = None, nearby: str = "") -> str | None:
    """One sentence about a shelter, or None if ATC states nothing usable.

    None is reachable in principle - a feature with no material, one storey,
    no listed feature, no plausible year, no note and no parts around it - and
    on today's data it never happens, because `Year_Built` alone is populated
    on all 280.

    `nearby` is nearby_clause()'s output, spliced BEFORE the note rather than
    after it. The note is a person's prose and stays last, where the
    attribution reads as covering it and nothing else; a composed clause
    trailing "ATC notes: ..." would read as part of what ATC wrote.
    """
    storeys = STOREYS.get(int(_count(properties, "Stories")))
    material = EXTERIOR_MATERIALS.get(str(properties.get("Exterior_M", "")).strip())

    head = " ".join(part for part in (storeys, material, "shelter") if part)
    head = head[0].upper() + head[1:]
    if capacity is not None:
        head += f", sleeps {capacity}"

    sentence = f"{head}{_with_clause(properties, FEATURES)}.{_built_clause(properties)}{nearby}{_note_clause(note)}"
    # "Shelter." on its own says nothing the card's own type line does not.
    # With parts around it, it is the lead-in to the only line that mentions
    # them, and carries.
    if sentence == "Shelter.":
        return None
    return sentence


def _coded(properties: dict, field: str) -> str:
    """One of ATC's coded-domain values as a bare string, for dict lookup."""
    return str(properties.get(field, "")).strip()


def _is_group_campsite(properties: dict) -> bool:
    """Whether ATC has this campsite down as a group site.

    Read in one place because two callers need it - the campsite's own sentence
    and the nearby clause that names it from a shelter - and a group site is
    exactly the thing a party of six is deciding on. Two readings of one code
    is how the card and the sentence about the card end up disagreeing.
    """
    return _coded(properties, "Type") == GROUP_CAMPSITE_TYPE


def describe_parking(properties: dict, note: str | None = None) -> str | None:
    """One sentence about a parking area, or None if ATC states nothing.

        "Gravel parking area, room for 12 cars."

    The two facts here are the ones somebody driving to a trailhead is
    actually deciding on: what they will be parking on, and whether there is
    going to be room. The layer carries far more - guide rails, culverts,
    bollards, striping lengths - and all of it is road-maintenance inventory.

    `Year_Built` is populated on 357 of 482 and is left out too: for a
    structure a hiker sleeps in, its age says something about what to expect;
    for a car park it says nothing anyone acts on.
    """
    head = "Parking area"
    if _coded(properties, "Type") == PARKING_ROADSIDE:
        head = "Roadside parking"
    else:
        surface = PARKING_SURFACES.get(_coded(properties, "Surface"))
        if surface:
            head = f"{surface.capitalize()} parking area"

    counted = []
    spaces = int(_count(properties, "Parking_S"))
    if spaces > 0:
        # "Room for", not "12 spaces": ATC counts marked spaces where a lot
        # has them and usable car-lengths where it does not, so the number is
        # a capacity rather than a set of painted rectangles.
        counted.append(f"room for {_plural(spaces, 'car')}")
    accessible = int(_count(properties, "ADA_Space"))
    if accessible > 0:
        counted.append(f"{_plural(accessible, 'accessible space')}")
    if counted:
        head += f", {_join(counted)}"

    sentence = f"{head}.{_note_clause(note)}"
    if sentence == "Parking area.":
        # The card's type line already says "Parking".
        return None
    return sentence


def describe_privy(properties: dict, note: str | None = None) -> str | None:
    """One sentence about a privy, or None if ATC states nothing usable.

        "Multi-seat moldering privy. Built 2019."

    Type earns its place: a moldering privy is used differently from a pit
    one - what may go in it, and what a hiker is asked to add afterwards -
    and it is the kind of thing the sign on the door assumes you already know.

    `Built` stays for the reason it stays on a shelter: 308 of 316 carry a
    plausible year, and a privy rebuilt three years ago and one from 1965 are
    different propositions.
    """
    kind = PRIVY_TYPES.get(_coded(properties, "Type"))
    enclosure = _coded(properties, "Enclosure")

    head = " ".join(part for part in ("Multi-seat" if enclosure == PRIVY_MULTI_SEAT else "", kind or "", "privy") if part)
    head = head[0].upper() + head[1:]
    if enclosure == PRIVY_OPEN_ENCLOSURE:
        # ATC's own term for this is "chum", which is trail vocabulary rather
        # than plain English - so the sentence says what it means.
        head += ", open to the air with no enclosure"

    sentence = f"{head}.{_built_clause(properties)}{_note_clause(note)}"
    if sentence == "Privy.":
        return None
    return sentence


def _view_arc(properties: dict) -> tuple[int, int] | None:
    """A vista's (width, middle bearing) in degrees, or None.

    The arc is swept clockwise from `Left_Beari` to `Right_Bear` - see the
    module docstring for why it is computed rather than read off `Scope`.

    Both bearings reading 0 is treated as "not surveyed" rather than as a
    zero-width view due north, which is what 217 of the 1,223 features carry.
    A genuine full circle would have to be written some other way (0 to 360,
    or any pair a degree apart), and none of the 1,006 surveyed vistas is
    written as 0 to 0.
    """
    left, right = properties.get("Left_Beari"), properties.get("Right_Bear")
    if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
        return None
    if isinstance(left, bool) or isinstance(right, bool):
        return None
    if left == 0 and right == 0:
        return None

    # A left and right that coincide are the whole horizon, not nothing.
    width = (right - left) % 360 or 360
    rounded = int(round(width / ARC_ROUNDING_DEGREES) * ARC_ROUNDING_DEGREES)
    # Rounding must not turn a real, narrow view into a 0° one.
    return max(rounded, ARC_ROUNDING_DEGREES), int(round((left + width / 2) % 360))


def _compass(bearing: int) -> str:
    """The eight-point compass name for a bearing.

    Eight rather than sixteen deliberately: this names the middle of an arc
    that is 100° wide at the median, and "east-north-east" would be a
    precision the underlying number does not have.
    """
    return COMPASS_POINTS[int((bearing % 360) / 45 + 0.5) % 8]


def _article(degrees: int) -> str:
    """ "a" or "an" for a number that will be read aloud.

    It is the spoken form that decides: 80 is "eighty", so "an 80° view",
    while 180 is "one hundred and eighty" and keeps "a". Only a leading 8 (and
    11/18, which the 5° rounding cannot produce) take "an" in this range.
    """
    return "an" if str(degrees)[0] == "8" and degrees < 100 else "a"


def describe_viewpoint(properties: dict, note: str | None = None) -> str | None:
    """One sentence about a vista, or None if ATC states nothing usable.

        "A 100° view south-east from a ridge or rock outcrop."

    Which is the whole question a hiker has about a viewpoint they have not
    reached yet: how much is there to see, which way does it face, and what
    am I standing on.

    `Type` (Improved/Unimproved Viewpoint) is deliberately not in the
    sentence. It describes whether ATC has built something at the spot -
    decking, railings, paving - which is a maintenance distinction rather
    than a hiker's, and it is also the messiest column on this layer (see the
    module docstring). `Year_Built` is out for a related reason: on a
    viewpoint it is ambiguous between when a structure was put there and when
    the view was opened up, and printing a date whose meaning is a guess is
    the failure this whole module exists to avoid.
    """
    arc = _view_arc(properties)
    # `Location` is semicolon-separated where more than one applies; the first
    # value is the one to describe from.
    location = VISTA_LOCATIONS.get(_coded(properties, "Location").split(";")[0].strip().lower())

    if arc is None:
        head = "A view" if location else None
    else:
        width, middle = arc
        if width >= PANORAMA_DEGREES:
            head = "A panoramic view"
        else:
            head = f"{_article(width).capitalize()} {width}° view {_compass(middle)}"

    if head is None:
        # No arc and no recognised landform: nothing here that the card's own
        # "Viewpoint" line does not already say.
        return None if not note else _note_clause(note).strip()
    if location:
        head += f" from {location}"

    return f"{head}.{_note_clause(note)}"


def describe_campsite(properties: dict, note: str | None = None, nearby: str = "") -> str | None:
    """One sentence about a campsite, or None if ATC states nothing usable.

    Campsites carry a much thinner inventory than shelters - no storeys, no
    materials, no year - so this leans on the two columns that are populated:
    whether the site is a group site, and how many individual sites it holds.

    A campsite is in both of lib/poi_sites.py's tuples - a member of a
    shelter's site, and the anchor of its own where there is no shelter - so
    `nearby` is populated here for the 41 campsite-anchored sites and empty for
    the 144 campsites that fold into a shelter's.
    """
    head = "Designated group campsite" if _is_group_campsite(properties) else "Designated campsite"

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

    sentence = f"{head}{_with_clause(properties, CAMPSITE_FEATURES)}.{nearby}{_note_clause(note)}"
    if sentence in ("Designated campsite.", "Designated group campsite."):
        # The type line already says "Campsite"; "Designated" alone is not
        # worth a second line on the card.
        return None
    return sentence


# --- what an anchor says about its parts ------------------------------------


def _privy_phrase(properties: dict) -> str:
    """ "a multi-seat moldering privy" - which privy, not the privy's card.

    The adjectives are the ones describe_privy already argues for: type,
    because a moldering privy is used differently from a pit one, and the
    missing enclosure, because 8 of the 316 have none and that is the kind of
    thing a hiker would rather read here than discover on arrival. `Built` is
    not here - a rebuild date is a fact about the privy, read on the privy.
    """
    words = ["a"]
    if _coded(properties, "Enclosure") == PRIVY_MULTI_SEAT:
        words.append("multi-seat")
    kind = PRIVY_TYPES.get(_coded(properties, "Type"))
    if kind:
        words.append(kind)
    words.append("privy")
    if _coded(properties, "Enclosure") == PRIVY_OPEN_ENCLOSURE:
        # Not ", open to the air with no enclosure" as the privy's own sentence
        # has it: a comma inside a comma-joined list reads as another part.
        words.append("with no enclosure")
    return " ".join(words)


def _campsite_phrase(properties: dict) -> str:
    """ "a group campsite", or "a campsite".

    The counts describe_campsite carries - sites, tent pads, tent platforms -
    are deliberately absent, and this is the one place the selection was hard.
    They are useful, and they land a number directly against the distance:
    "a campsite with 8 tent pads 25 m" is two figures with nothing between
    them, and a reader has to stop and work out which belongs to what. Group
    or not is the fact a party of six acts on; the rest is on the campsite.
    """
    return "a group campsite" if _is_group_campsite(properties) else "a campsite"


# poi_type -> the noun phrase naming it, article included ("water" takes none).
# Every one of lib/poi_sites.py's MEMBER_TYPES is here.
#
# `water` composes from nothing because there is nothing to compose from: it is
# opentrail.org's, not ATC's, so it reaches this module with no inventory
# columns at all. Its own title ("Piped spring", "Seasonal Water Spigot") is
# free text from a third party and stays off the sentence for the reason the
# module docstring gives for every other unrecognised value - a shorter
# sentence rather than a wrong one.
NEARBY_PHRASES = {
    "privy": _privy_phrase,
    "campsite": _campsite_phrase,
    "water": lambda _properties: "water",
}


def _nearby_part(poi_type: str, properties: dict) -> str:
    """One part's noun phrase, falling back to its bare type.

    A fallback rather than a skip, and for the reason the client's `memberRank`
    sorts an unknown category last instead of dropping it: a member type a
    later release publishes would otherwise vanish from the only sentence that
    mentions it, which is the bug this whole clause exists to fix, reintroduced
    by the code that fixed it.
    """
    phrase = NEARBY_PHRASES.get(poi_type)
    if phrase is not None:
        return phrase(properties)
    article = "an" if poi_type[:1] in "aeiou" else "a"
    return f"{article} {poi_type}"


def nearby_clause(members: list[tuple[str, float, dict]]) -> str:
    """What an anchor's sentence says about the parts around it.

        " Nearby: a multi-seat moldering privy 40 m away, a group campsite
         25 m and water 90 m."

    Takes (poi_type, metres, ATC attributes) per member and returns a clause
    ready to splice in, or "" when there is nothing to say - so a POI in no
    site composes exactly the sentence it composed before this existed.

    A SEPARATE SENTENCE, NOT A `with` CLAUSE. A shelter does not have a privy
    and a water source inside it; they are separate points a short walk away.
    See the module docstring - this is the one thing about this clause that is
    not a formatting decision.

    "away" is said once and carried forward across the list. Three of them in
    a row reads as a sentence explaining its own grammar, and the label at the
    front has already said it.

    Ordered by NEARBY_ORDER and then by distance, rather than by whatever order
    the grouping produced. Two privies at one campsite - open question 4's
    "Backpacker Campsite Upper Privy" and "...Lower Privy" - come out nearest
    first, which is the only thing distinguishing them that a hiker standing at
    the anchor can act on.
    """
    ranked = sorted(
        members,
        key=lambda member: (
            NEARBY_ORDER.index(member[0]) if member[0] in NEARBY_ORDER else len(NEARBY_ORDER),
            member[1],
        ),
    )
    parts = [f"{_nearby_part(poi_type, properties or {})} {_metres(metres)}" for poi_type, metres, properties in ranked]
    if not parts:
        return ""
    parts[0] += " away"
    return f" {NEARBY_LEAD}: {_join(parts)}."


def _metres(metres: float) -> str:
    """A member's distance, in whole metres.

    METRES, AND NOT A HIKER'S UNIT PREFERENCE. features/POI_SITES.md §5 writes
    these distances in metres and #526's chips render them the same way, so the
    same fact reading "40 m" on a chip and "131 ft" in the sentence above it
    would be drift on one card. `unit_system` exists in the client's preferences
    (lib/userPreferences.ts) and reaches nothing today; when it does, this is
    published prose and changing it costs a re-export - the honest price of
    composing sentences in the pipeline rather than on the phone.

    WHOLE METRES, for the reason the view arc is rounded to 5°: a site is under
    150 m across by construction - that is the gate that grouped it - so this is
    a how-many-paces number rather than a measurement, and tenths are noise
    against two points surveyed no finer than this. Rounded the same way #526's
    `partDistance` rounds it, over the same equirectangular distance, so the
    chip and the sentence above it cannot print two numbers for one pair.

    Floored at 1 m rather than allowed to round to zero. "0 m away" reads as a
    bug; two facility points sharing a coordinate to within half a metre is one
    upstream, and the sentence should not repeat it as though it were a walk.

    Thousands separated, which cannot bind today - the widest gate admitting a
    member is 150 m - and is there for the same reason MAX_SITE_RADIUS_M is:
    the next edit to those gates.
    """
    return f"{max(1, round(metres)):,} m"
