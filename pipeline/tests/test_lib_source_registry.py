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
    KNOWN_KINDS,
    PUBLISHED_NOTICES,
    arcgis_sources,
    find_source,
    is_arcgis_feature_layer,
    load_registry,
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
