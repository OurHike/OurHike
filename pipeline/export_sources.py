"""Publish who the map's data belongs to, and on what terms (#927).

The hiker-facing half of features/SOURCE_REGISTRY.md. `sources.json` has
recorded a steward, a licence and an attribution per source since 2026-08-18,
and nothing has ever shown any of it to a hiker: the app's only attribution
surface is the map corner (client/src/map/credits.ts), which answers "whose
pixels am I looking at right now" and is deliberately one line. "Which
organizations' data is on this phone, and under what terms" is a different
question and has had no answer at all.

WHAT IT PUBLISHES, AND THE RULE IT INHERITS

One record per STEWARD, not per source - a hiker cares that the Appalachian
Trail Conservancy's data is on the phone, not that it arrived as eleven
layers. Grouped by `provider`, which is the registry's own key for that.

`credits.ts`'s rule is taken whole: name what is actually there, never what
could be. Its own comment is the argument - a corner that named every source
the app COULD draw "was the same category of quiet inaccuracy value #4 exists
to prevent". A sources screen naming a steward whose data does not ship is the
same error one surface over, and worse, because this one prints a LICENCE
beside the name.

So only sources with `reaches_hikers: true` count, and a steward with none of
them is not published at all. Today that excludes two organizations whose
records are otherwise complete:

  - GATC ("Nothing from this source reaches a published artifact until GATC
    answers a redistribution ask")
  - NYS OPRHP, all four layers ("Fetched for REVIEW AND THE #771 SPIKE ONLY")

Both are real stewards with real data in `data/raw/`. Neither belongs on a
hiker's screen until its licence answer lands, and the flag is what keeps that
true without anybody re-reading a paragraph.

WHY THE PER-SOURCE `licence` FIELD IS NOT PUBLISHED, THOUGH IT SOUNDS LIKE THE
ONE TO PUBLISH

It is internal documentation, not a statement for a phone. Read as prose, the
entries are notes between maintainers - `usdm_drought`'s begins "See
usdm_licence above - reproduction of the map is explicitly permitted with
NDMC's credit line, redistribution of the polygons rides on the maintainer's
declaration of 2026-08-15", and `osm_water`'s spends its second clause on which
client screen already names OpenStreetMap. Both are the right thing to have
written down and the wrong thing to render on a card under an organization's
name. The first draft of this exporter published them and the output made that
obvious immediately.

So two fields ship and one does not:

  - **`attribution`** always, verbatim, because it is what a licence actually
    OBLIGES - ODbL's condition, NDMC's required credit line. Taken from the
    source where it carries one, else from the steward's `<x>_licence` block.
  - **`licence`** only from a top-level `<x>_licence` block's `license` field,
    which is the registry's recorded TERMS for that steward and is written
    short ("© ATC, used with permission"). Never from the per-source prose,
    and never composed, shortened or prettified here.
  - Where no block matches, `licence` is null and the card shows attribution
    alone. That is a registry gap rather than a rendering decision, and it is
    real today for `osm_water`, which has no block at all. Recording one is a
    data change somebody reviews; inventing one here would be this file
    authoring a licence statement, which it has no standing to do.

    IT WAS ALSO REAL FOR THE U.S. DROUGHT MONITOR UNTIL 2026-08-27, and how
    that went unnoticed is the reason for `test_every_licence_block_joins_a
    _steward`. `usdm_licence`'s `author` read "National Drought Mitigation
    Center, USDA, NOAA and NASA" while its source's `steward` read "National
    Drought Mitigation Center, University of Nebraska-Lincoln", so the block
    matched nothing and NDMC's recorded terms never reached the sources
    screen - while every test passed, this docstring described the state
    accurately, and the entry's own `licence` prose said "See usdm_licence
    above". A gap that is written down in three places and still ships is not
    documented, it is decorated. The block's author is now the steward's own
    name and a test fails if any block goes unjoinable again.

HOW TO SUPPORT THE ORGANIZATION, AND THE ONE FIELD THAT BOUNDS IT (#932)

A steward record can now carry `support`: a destination, the organization's
own call to action, and `donate_surfaces` - the list of screens on which the
line may appear. Read from a top-level `<x>_support` block, joined on `author`
exactly the way `<x>_licence` is, because supporting an organization is a fact
about the ORGANIZATION and not about any one of its thirteen layers.

`donate_surfaces` is the point of the schema rather than a detail of it. The
v2 frames are explicit that a placement is a permission the ORG GRANTS, not
something the app decides, and equally explicit about the one value that has
to be expressible: on the map, never. So the vocabulary below is a CLOSED
opt-in list of the surfaces that exist, and there is no map member to grant -
the refusal is enforced by the vocabulary rather than by a check somebody has
to keep passing. A surface added later needs a new member here AND a fresh
answer from every org, because nobody has granted a value that did not exist
when they answered. That is the intended cost.

Money on a safety app is value #1 territory: these fields make a fundraising
ask renderable on a screen a hiker opens when they are lost. A malformed
support block is therefore a HARD FAILURE here rather than a field quietly
dropped - a block with no `donate_surfaces` would otherwise be indistinguish-
able from one whose org granted every surface.

A steward with no block publishes `support: null` and renders exactly as it
does today - no button, no empty section, no placeholder. Absent means the
organization has not asked for support, which is not the same as an
organization that wants none, and neither is a thing to guess at on a hiker's
screen. Same rule the pipeline already applies to shelter capacity.

WHAT IT REFUSES TO GUESS

`trust` is published only when every shipping source of a steward declares the
SAME tier. ATC's do not - eleven carry no `trust` field and `atc_trail_updates`
carries `authoritative` - so ATC publishes no tier, and the card shows none.

That is the omit-rather-than-guess rule doing something inconvenient, and it is
worth keeping rather than smoothing: the v2 wireframe's frame `1h` draws ATC
with an AUTHORITATIVE chip, and nothing in the registry says that. The fix is
to record `trust` on those eleven entries - a data change somebody reviews -
not to have this file infer a tier from a provider's name.

NO NETWORK. Reads `sources.json` in this checkout and nothing else. It does not
even read `data/raw/`, because whether a steward's data reaches a hiker is a
registration fact rather than a property of the last fetch.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parent
SOURCES_PATH = ROOT / "sources.json"
# `stewards.json`, NOT `sources.json`, and the difference is worth the extra
# word: `pipeline/sources.json` is the REGISTRY this reads, and a published
# bucket key sharing its name would put two different files with one name in
# every conversation about where a licence came from. The artifact is a list of
# stewards, so it is named for what it holds.
OUT_PATH = ROOT / "data" / "processed" / "stewards.json"
MANIFEST_PATH = ROOT / "data" / "processed" / "stewards_manifest.json"

# The registry's own key for "who publishes this", and the field naming the
# organization in full where an entry carries one.
PROVIDER_FIELD = "provider"
STEWARD_FIELD = "steward"

# The surfaces an organization can grant a support line on (#932). CLOSED, and
# deliberately holding no member for the map: the v2 frames say "on the map,
# never", and a vocabulary that cannot express the map is a stronger guarantee
# than a validator that rejects it, because a validator can be edited in one
# line while adding a member here is a conversation with every org that has
# already answered.
DONATE_SURFACES = frozenset(
    {
        # frame `1h` - "Where this map comes from", the settings screen (#927).
        "sources_screen",
        # frame `1f` - the card for one trail: "NYNJTC - Maintains this trail".
        "trail_card",
        # frame `1l` - the day-hike summary, where several orgs share a loop.
        "day_hike_summary",
    }
)

# What a `<x>_support` block must carry to be publishable at all. `donate_blurb`
# is deliberately NOT here: the org's own words about what the money does are
# their writing, and this project ships facts and a link until they send them.
REQUIRED_SUPPORT_FIELDS = ("author", "donate_url", "donate_cta", "donate_surfaces")


def _block(registry: dict, provider_sources: list[dict], suffix: str) -> dict:
    """The top-level `<x>{suffix}` block a steward's sources point at, if any.

    Matched by the block's `author` against the entries' `steward`, rather than
    by guessing a key name from the provider string - `atc_licence` is keyed on
    a three-letter abbreviation and its author is the full organization name,
    and a future block will not necessarily follow either convention.

    Returns `{}` when nothing matches, which is the ordinary case for a steward
    whose sources each carry their own licence, and for every steward that has
    not been asked about support.

    THE FAILURE MODE THIS MATCHING HAS: an author string that matches nothing
    is silent here and correct-looking in the registry. It happened - see this
    module's docstring on `usdm_licence` - so
    `tests/test_export_sources.py::test_every_block_joins_a_steward` reads the
    real registry and fails on an unjoinable block. That check cannot live in
    this function, because a block for a steward whose data does not ship is
    legitimate and looks identical from in here.
    """
    stewards = {s[STEWARD_FIELD] for s in provider_sources if s.get(STEWARD_FIELD)}
    for key, value in registry.items():
        if not key.endswith(suffix) or not isinstance(value, dict):
            continue
        if value.get("author") in stewards:
            return value
    return {}


def _licence_block(registry: dict, provider_sources: list[dict]) -> dict:
    return _block(registry, provider_sources, "_licence")


def _support_record(block: dict) -> dict | None:
    """One steward's support line, or None where the org has not asked for one.

    Raises rather than dropping a malformed block. A support block missing
    `donate_surfaces` is not a block with no permissions - it is a block whose
    permissions nobody wrote down, and the two must never render the same.
    """
    if not block:
        return None

    missing = [f for f in REQUIRED_SUPPORT_FIELDS if not block.get(f)]
    if missing:
        raise SystemExit(
            f"support block for {block.get('author') or '(no author)'} is missing: "
            + ", ".join(missing)
            + "\nA support block records a fundraising ask on a hiker's screen. "
            "Every field above is required; see export_sources.py's docstring."
        )

    surfaces = block["donate_surfaces"]
    if not isinstance(surfaces, list):
        raise SystemExit(f"donate_surfaces for {block['author']} must be a list, got {type(surfaces).__name__}")
    unknown = sorted(set(surfaces) - DONATE_SURFACES)
    if unknown:
        raise SystemExit(
            f"donate_surfaces for {block['author']} names surfaces that do not exist: "
            + ", ".join(unknown)
            + "\nThe vocabulary is closed and holds no member for the map, deliberately - "
            "see export_sources.py's DONATE_SURFACES."
        )

    record = {
        "donate_url": block["donate_url"],
        "donate_cta": block["donate_cta"],
        "donate_surfaces": sorted(set(surfaces)),
    }
    # Only where the money does not reach the steward the card names. Absent on
    # the ordinary case, present and REQUIRED TO RENDER where it is not - see
    # oprhp_support, whose destination is a separate 501(c)(3).
    if block.get("donate_recipient"):
        record["donate_recipient"] = block["donate_recipient"]
    # The org's own words about what the money does, when an org sends them.
    # Absent everywhere today, and that is the honest state rather than a gap.
    if block.get("donate_blurb"):
        record["donate_blurb"] = block["donate_blurb"]
    return record


def _unanimous(values: list, absent_counts: bool = True) -> str | None:
    """One value if every shipping source agrees, else None.

    `absent_counts` is the strict half: a source with no opinion is a source
    that does not agree, so eleven silent entries and one `authoritative` is
    not unanimity. See this module's docstring for why that is deliberate.
    """
    if not values:
        return None
    if absent_counts and any(v is None for v in values):
        return None
    unique = {v for v in values if v is not None}
    return unique.pop() if len(unique) == 1 else None


def build_output(registry: dict | None = None) -> dict:
    registry = registry if registry is not None else json.loads(SOURCES_PATH.read_text())
    sources = registry.get("sources", [])

    unclassified = [s["key"] for s in sources if "reaches_hikers" not in s]
    if unclassified:
        # Hard failure rather than a default. A source silently defaulting to
        # "reaches hikers" would put a steward on the screen whose licence
        # nobody checked; defaulting the other way would quietly drop a
        # steward whose licence obliges attribution. Neither is a thing to
        # discover from a hiker's screen, so a new registration blocks the
        # publish until somebody says which it is.
        raise SystemExit(
            "sources.json entries missing `reaches_hikers`: "
            + ", ".join(sorted(unclassified))
            + "\nSee the registry's reaches_hikers_comment - it is not a licence "
            "judgement, only whether an exporter ships this source's data."
        )

    shipping: dict[str, list[dict]] = {}
    for source in sources:
        if not source["reaches_hikers"]:
            continue
        shipping.setdefault(source.get(PROVIDER_FIELD, ""), []).append(source)

    stewards = []
    for provider, entries in sorted(shipping.items()):
        block = _licence_block(registry, entries)

        # The organization's full name where an entry gives one, falling back
        # to the provider key. "ATC" is what the registry calls the provider;
        # "Appalachian Trail Conservancy" is what a hiker should read.
        steward = _unanimous([e.get(STEWARD_FIELD) for e in entries]) or block.get("author")

        # Block only - never the per-source `licence`, which is prose. See the
        # module docstring; null here is an honest "no short terms recorded".
        licence = block.get("license")
        attribution = _unanimous([e.get("attribution") for e in entries]) or block.get("attribution")

        stewards.append(
            {
                "provider": provider,
                "name": steward or provider,
                "trust": _unanimous([e.get("trust") for e in entries]),
                "licence": licence,
                "attribution": attribution,
                # What this steward publishes, in the registry's own words, so
                # a card can say "Centerline, shelters, closures" without this
                # file inventing a summary of somebody else's data.
                "layers": sorted(e.get("title", e["key"]) for e in entries),
                # The registry keys behind those layers - what a graph edge's
                # `source` is (#978), so the phone can turn `oprhp_trails`
                # into the organization's name. NOT index-aligned with
                # `layers`: both lists are sorted independently, in different
                # vocabularies. Joining them positionally is the mistake this
                # comment exists to prevent.
                "keys": sorted(e["key"] for e in entries),
                # How to support this organization, or null where it has not
                # asked (#932). Null renders exactly as today: no button, no
                # empty section, no placeholder.
                "support": _support_record(_block(registry, entries, "_support")),
            }
        )

    return {"stewards": stewards}


def main() -> dict:
    output = build_output()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")

    digest = hashlib.sha256(OUT_PATH.read_bytes()).hexdigest()
    # ABSOLUTE, like every sibling manifest - publish.py resolves this against
    # its own CWD (export_club_sections.py's comment has the incident).
    manifest = {"path": str(OUT_PATH), "sha256": digest}
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"{len(output['stewards'])} stewards -> {OUT_PATH}")
    for steward in output["stewards"]:
        tier = steward["trust"] or "no tier recorded"
        licence = steward["licence"] or "NO LICENCE RECORDED"
        print(f"  {steward['name']}")
        print(f"    {len(steward['layers'])} layers · {tier}")
        print(f"    {licence}")
    return manifest


if __name__ == "__main__":
    main()
