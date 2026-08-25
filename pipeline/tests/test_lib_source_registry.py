"""sources.json's `kind` discriminator, and the registry as it really is.

The interesting case is the default. Twelve entries have no `kind` and are
ArcGIS feature layers; the thirteenth says so and is not. A default that
answered the wrong way would put ATC's Trail Updates back in fetch_all.py's
loop, where it fails its metadata check, fetches nothing, and lands in the
completeness gate as a zero-feature source - turning a gate that means
"something is broken" into one that is red on every run.
"""

from __future__ import annotations

import json
from pathlib import Path

from lib.source_registry import (
    ARCGIS_FEATURE_LAYER,
    EXTERNAL_ARCGIS_LAYER,
    KNOWN_KINDS,
    POI_SOURCE_KEYS,
    PUBLISHED_NOTICES,
    UNREGISTERED_POI_SOURCES,
    arcgis_sources,
    external_arcgis_sources,
    find_source,
    is_arcgis_feature_layer,
    load_registry,
    poi_source_entry,
    poi_source_steward,
    source_kind,
)

REAL_REGISTRY = Path(__file__).resolve().parents[1] / "sources.json"


def test_an_entry_without_a_kind_is_an_arcgis_feature_layer():
    """Where the twelve live. Writing `kind` on each of them instead would be
    a schema that discovery deletes - see this module's docstring in
    lib/source_registry.py."""
    assert source_kind({"key": "centerline"}) == ARCGIS_FEATURE_LAYER
    assert is_arcgis_feature_layer({"key": "centerline"})


def test_a_published_notices_source_is_not_a_feature_layer():
    assert not is_arcgis_feature_layer({"key": "atc_trail_updates", "kind": PUBLISHED_NOTICES})


def test_arcgis_sources_keeps_registry_order_and_drops_the_rest():
    registry = {
        "sources": [
            {"key": "centerline"},
            {"key": "atc_trail_updates", "kind": PUBLISHED_NOTICES},
            {"key": "shelters", "kind": ARCGIS_FEATURE_LAYER},
        ]
    }

    assert [entry["key"] for entry in arcgis_sources(registry)] == ["centerline", "shelters"]


def test_an_external_layer_is_kept_out_of_the_atc_loop_and_found_by_its_own():
    """The property #769 rides on, from both sides: an external-organization
    layer must never land in fetch_all.py's loop (its completeness gate is
    the A.T. release's, and OPRHP's closures layer is honestly empty in a
    good week), and fetch_external_layers.py must find exactly the entries
    that declare themselves."""
    registry = {
        "sources": [
            {"key": "centerline"},
            {"key": "oprhp_trails", "kind": EXTERNAL_ARCGIS_LAYER},
        ]
    }

    assert not is_arcgis_feature_layer({"key": "oprhp_trails", "kind": EXTERNAL_ARCGIS_LAYER})
    assert [entry["key"] for entry in arcgis_sources(registry)] == ["centerline"]
    assert [entry["key"] for entry in external_arcgis_sources(registry)] == ["oprhp_trails"]


def test_find_source_answers_none_rather_than_raising():
    """Callers turn a missing entry into UNKNOWN - check_freshness.py asks
    for the feed URL this way, and a registry that has lost the entry must
    report "could not ask" rather than take the run down."""
    assert find_source({"sources": []}, "atc_trail_updates") is None


# --- The registry this repository actually ships ---------------------------


def test_the_real_registry_registers_atc_trail_updates_as_a_reviewed_source():
    """#459's actual deliverable, checked as data rather than as prose.

    Each field is here because something reads it: `kind` keeps it out of
    fetch_all.py, `freshness.url` is where check_freshness.py asks, and
    `reviewed_input` is the file export_atc_updates.py bakes.
    """
    entry = find_source(load_registry(REAL_REGISTRY), "atc_trail_updates")

    assert entry is not None, "sources.json no longer registers ATC's Trail Updates (#459)"
    assert entry["kind"] == PUBLISHED_NOTICES
    assert entry["trust"] == "authoritative"
    assert entry["steward"] == "Appalachian Trail Conservancy"
    assert entry["licence"].strip(), "a licence field nobody filled in is the hole #458 was about"
    assert entry["reviewed_input"] == "reference/atc_updates.json"
    assert entry["freshness"]["url"].startswith("https://")


def test_every_kind_in_the_real_registry_is_one_this_module_knows():
    """A kind nobody handles is a source silently fetched by nothing, or by
    the wrong thing."""
    registry = load_registry(REAL_REGISTRY)

    unknown = {source_kind(entry) for entry in registry["sources"]} - KNOWN_KINDS
    assert not unknown, f"sources.json uses kinds lib/source_registry.py does not know: {unknown}"


def test_the_reviewed_input_the_registry_names_is_really_there():
    """The registry pointing at a file that does not exist would be a
    registration that reads as complete and bakes nothing."""
    entry = find_source(load_registry(REAL_REGISTRY), "atc_trail_updates")

    assert (REAL_REGISTRY.parent / entry["reviewed_input"]).exists()


def test_the_real_registry_registers_the_four_oprhp_layers_as_external():
    """#769's deliverable, checked as data: the four layers the NY State
    Parks Explorer app itself draws, each carrying the kind that keeps it
    out of fetch_all.py, a steward, and a licence pointing at the pending
    outreach - a licence field nobody filled in is the hole this registry
    keeps refusing."""
    registry = load_registry(REAL_REGISTRY)
    keys = ("oprhp_trails", "oprhp_trail_closures", "oprhp_facilities", "oprhp_park_polygons")

    for key in keys:
        entry = find_source(registry, key)
        assert entry is not None, f"sources.json no longer registers {key} (#769)"
        assert entry["kind"] == EXTERNAL_ARCGIS_LAYER
        assert entry["trust"] == "authoritative"
        assert entry["steward"].startswith("New York State Office of Parks")
        assert entry["licence"].strip()
        assert entry["url"].startswith("https://services.arcgis.com/1xFZPtKn1wKC6POA/")


def test_only_the_closures_layer_may_be_empty():
    """`may_be_empty` is the per-entry allowance fetch_external_layers.py's
    gate reads: zero closures is a fact about the parks, zero trails is a
    broken fetch. A flag that crept onto the other three would quietly
    disarm the gate for layers where empty always means broken."""
    registry = load_registry(REAL_REGISTRY)

    flagged = {
        entry["key"] for entry in registry["sources"] if source_kind(entry) == EXTERNAL_ARCGIS_LAYER and entry.get("may_be_empty")
    }
    assert flagged == {"oprhp_trail_closures"}


def test_the_real_registry_registers_mohonk_trails_as_external_and_shipping():
    """#992's deliverable, checked as data: Mohonk Preserve's own trails and
    carriage-road layer, registered the same way OPRHP's and NYNJTC's were -
    external kind, a steward, a licence pointing at the maintainer's
    authorisation (mohonk_licence), blaze/name fields so
    export_nearby_trails.py's network_line_sources() picks it up, and
    reaches_hikers True - the same shape nynjtc_trails' entries took once
    their own authorisation landed (#950)."""
    registry = load_registry(REAL_REGISTRY)
    entry = find_source(registry, "mohonk_trails")

    assert entry is not None, "sources.json no longer registers mohonk_trails (#992)"
    assert entry["kind"] == EXTERNAL_ARCGIS_LAYER
    assert entry["trust"] == "authoritative"
    assert entry["steward"] == "Mohonk Preserve"
    assert entry["licence"].strip()
    assert entry["url"].startswith("https://services8.arcgis.com/cQ05sucxF4UWabFF/")
    assert entry["blaze_field"] == "Blaze"
    assert entry["name_field"] == "Name"
    assert entry["reaches_hikers"] is True


def test_the_registry_records_the_mohonk_licence_block():
    """The basis mohonk_trails' reaches_hikers: True rests on, checked as
    data: the terms are recorded verbatim (not summarized, after
    oprhp_licence's truncation lesson) and the block says plainly that this
    ships on the maintainer's authorisation rather than on Mohonk Preserve's
    own stated terms - the same shape nynjtc_licence's basis reads."""
    registry = load_registry(REAL_REGISTRY)
    block = registry["mohonk_licence"]

    assert "WITHOUT ANY WARRANTY" in block["terms_verbatim"]
    assert len(block["terms_verbatim"]) > 100
    assert "992" in block["open_question"]
    assert block["basis"].startswith("Maintainer authorisation")
    assert block["recorded_date"] == "2026-08-25"


def test_the_registry_records_the_oprhp_licence_block():
    """The gate #769 exists to hold - but NOT for the reason this test used to
    give (#950, corrected 2026-08-24).

    It read "OPRHP's terms are unstated", which was wrong: the item's
    licenseInfo had been read through a 200-character truncation that cut off
    exactly where the no-warranty disclaimer ends and the actual terms begin.
    OPRHP states terms - reuse permitted, attribution required, non-commercial
    purposes - and the block now quotes all 1,095 characters verbatim so no
    future reader has to re-fetch to check.

    What the block must still do is hold the gate, on the narrower question
    that survived the correction: whether OurHike's paid tiers make this a
    commercial use. So the assertions below are about the terms being RECORDED
    and the open question being about commerciality, not about the licence
    being pending."""
    registry = load_registry(REAL_REGISTRY)
    block = registry["oprhp_licence"]

    # The verbatim text, so a truncated re-read can never quietly replace it.
    assert "non-commercial" in block["terms_verbatim"]
    assert "credit and attribution" in block["terms_verbatim"]
    assert len(block["terms_verbatim"]) > 1000
    # And the attribution OPRHP requires, named where an exporter can read it.
    assert "OPRHP" in block["attribution_required"]
    assert block["recorded_date"] == "2026-08-24"

    # The maintainer's determination on the one condition that needed a human,
    # and BOTH readings of it. A determination recorded without the argument
    # against it is an assertion wearing a date - CLAUDE.md's standard applied
    # to a licence rather than to a constant.
    assert "maintainer's determination" in block["basis"]
    assert "THE COUNTER-READING" in block["basis"]
    assert "non-commercial" in block["license"]

    # And it is still an open question with OPRHP, because they have not been
    # asked this specific thing. Recording our own answer is not their answer.
    assert "769" in block["open_question"]


def test_the_registry_still_records_the_photo_licence_block():
    """Not about ATC updates, and here because discover_sources.py used to
    drop it: the basis on which ATC's photos may be served at all is a
    top-level key, and rebuilding the document from `_comment` + `sources`
    deleted it on every discovery run."""
    registry = load_registry(REAL_REGISTRY)

    assert registry["photo_licence"]["license"]


def test_the_registry_still_records_the_atc_licence_block():
    """photo_licence's sibling (#688): the maintainer's 2026-08-13
    authorisation for reusing the data ATC publishes on its own org, which
    build_water_distance.py's licence position rides on. Same discovery-run
    survival concern, same pin."""
    registry = load_registry(REAL_REGISTRY)

    assert registry["atc_licence"]["basis"].startswith("Maintainer authorisation")
    assert registry["atc_licence"]["recorded_date"] == "2026-08-13"


def test_the_registry_is_still_parseable_as_plain_json():
    """Cheap, and the thing a hand-edited entry breaks first."""
    json.loads(REAL_REGISTRY.read_text())


# --- The POI-source join (#876) -------------------------------------------
#
# `POI_SOURCE_KEYS` is a hand-written table, and the drift it invites is
# specific: `export_poi.py` mints a new id namespace, nothing here knows the
# name, and a dispute on the new source silently routes to nobody. These two
# tests are why that table is allowed to be hand-written.


def _minted_poi_sources() -> set[str]:
    """Every source name the export can stamp on a published POI id.

    Read off export_poi.py's own constants rather than off a list here,
    because a list here is the thing being guarded.
    """
    import export_poi

    return {
        export_poi.SHELTER_SOURCE,
        export_poi.CAMPSITE_SOURCE,
        export_poi.CSI_WATER_SOURCE,
        export_poi.OPENTRAIL_SOURCE,
        export_poi.OSM_WATER_SOURCE,
        export_poi.NHD_CROSSING_SOURCE,
        export_poi.NHD_STREAM_SOURCE,
        *(source for _, _, source, _ in export_poi.DIRECT_SOURCES),
    }


def test_every_minted_poi_source_has_a_steward_or_is_named_as_having_none():
    """The drift guard. A source in neither set is not "unregistered" - it is
    unconsidered, and the difference matters because the first is a sentence
    a report prints and the second is a dispute that goes nowhere quietly."""
    unaccounted = _minted_poi_sources() - set(POI_SOURCE_KEYS) - UNREGISTERED_POI_SOURCES

    assert unaccounted == set(), (
        f"export_poi.py mints {sorted(unaccounted)}, which lib/source_registry.py neither "
        "maps to a registry key nor names in UNREGISTERED_POI_SOURCES"
    )


def test_every_mapped_key_is_really_in_the_registry():
    """The other half: a mapping pointing at a key sources.json does not have
    resolves to no steward, which looks exactly like an unregistered source
    and is a typo instead."""
    registry = load_registry(REAL_REGISTRY)

    missing = [key for key in POI_SOURCE_KEYS.values() if find_source(registry, key) is None]

    assert missing == []


def test_a_registered_poi_source_resolves_to_the_organization_to_tell():
    """ATC's shelters are the case the feature was built for. `provider` is
    read because the twelve ATC entries still carry only that field - see
    poi_source_steward's docstring."""
    registry = load_registry(REAL_REGISTRY)

    assert poi_source_steward(registry, "atc_shelters") == "ATC"
    assert poi_source_entry(registry, "atc_shelters")["title"] == "A.T. Shelters"


def test_an_unregistered_poi_source_resolves_to_nobody_rather_than_to_a_guess():
    """Null is the honest answer, and route_disputes.py prints it as one."""
    registry = load_registry(REAL_REGISTRY)

    assert poi_source_steward(registry, "nhd_crossing") is None
    assert poi_source_entry(registry, "nhd_crossing") is None
